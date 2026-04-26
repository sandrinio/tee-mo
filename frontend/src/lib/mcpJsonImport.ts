/**
 * mcpJsonImport.ts — Pure JSON parser for MCP server config payloads.
 *
 * Accepts JSON pasted from Claude Desktop, VS Code, or raw single-server
 * entries and normalises them into a canonical ParsedMcpServer shape.
 *
 * No React imports — this module is intentionally dumb and fully unit-testable
 * in isolation (STORY-012-04 §3.2).
 *
 * Supported input shapes:
 *   Shape A — Claude Desktop / Cursor: { "mcpServers": { "<name>": { url, transport, headers } } }
 *   Shape B — VS Code mcp.json:        { "servers": { "<name>": { url, type, headers } } }
 *   Shape C — Raw single entry:         { url, transport?, headers? }
 *   Shape D — Name-keyed map:           { "<name>": { url, transport?, headers? } }
 *
 * Transport normalisation:
 *   "streamable-http" (dash) → "streamable_http" (underscore)
 *   VS Code "http" type → "streamable_http"
 *   VS Code "sse" type → "sse"
 *   Missing transport → default "streamable_http"
 *
 * Header placeholder detection:
 *   Values matching /^\$\{(env|input):/ have placeholder=true and value cleared.
 */

import type { McpTransport } from './api';

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

export interface ParsedMcpHeader {
  key: string;
  value: string;
  placeholder: boolean;
}

export interface ParsedMcpServer {
  /** Wrapper key name if one was present in the input; null for raw entry. */
  name: string | null;
  transport: McpTransport;
  url: string;
  headers: ParsedMcpHeader[];
  /** Non-null when the input had multiple servers and only the first was imported. */
  warning: string | null;
}

export type ParseResult =
  | { ok: true; server: ParsedMcpServer }
  | { ok: false; error: string };

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Regex for VS Code / env placeholder values. */
const PLACEHOLDER_RE = /^\$\{(env|input):/;

/** Stdio-only config signals — reject these with a friendly error. */
const STDIO_KEYS = new Set(['command', 'args']);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function normaliseTransport(raw: string | undefined): McpTransport {
  if (!raw) return 'streamable_http';
  const t = raw.trim().toLowerCase();
  if (t === 'sse') return 'sse';
  if (t === 'streamable_http' || t === 'streamable-http' || t === 'http') return 'streamable_http';
  return 'streamable_http';
}

function mapHeaders(headersObj: unknown): ParsedMcpHeader[] {
  if (!headersObj || typeof headersObj !== 'object' || Array.isArray(headersObj)) {
    return [];
  }
  return Object.entries(headersObj as Record<string, unknown>).map(([key, val]) => {
    const strVal = typeof val === 'string' ? val : String(val ?? '');
    const isPlaceholder = PLACEHOLDER_RE.test(strVal);
    return {
      key,
      value: isPlaceholder ? '' : strVal,
      placeholder: isPlaceholder,
    };
  });
}

function buildServer(
  name: string | null,
  entry: Record<string, unknown>,
  warning: string | null,
): ParseResult {
  // Reject stdio configs
  for (const k of STDIO_KEYS) {
    if (k in entry) {
      return {
        ok: false,
        error:
          "Tee-Mo only supports HTTP-based MCP servers (SSE / Streamable HTTP). The config you pasted is for a local stdio server, which we don't support for security reasons.",
      };
    }
  }

  // Require url
  if (!entry.url || typeof entry.url !== 'string') {
    return { ok: false, error: 'JSON is missing a `url` field' };
  }

  // Resolve transport — VS Code uses "type" instead of "transport"
  const rawTransport =
    typeof entry.transport === 'string'
      ? entry.transport
      : typeof entry.type === 'string'
        ? entry.type
        : undefined;

  return {
    ok: true,
    server: {
      name,
      transport: normaliseTransport(rawTransport),
      url: entry.url,
      headers: mapHeaders(entry.headers),
      warning,
    },
  };
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

/**
 * parseMcpJson — parse an MCP server config string into a canonical form.
 *
 * @param input - Raw string value from the "Paste from another client" textarea.
 * @returns ParseResult — either `{ok: true, server}` or `{ok: false, error}`.
 */
export function parseMcpJson(input: string): ParseResult {
  // Step 1: Parse JSON
  let parsed: unknown;
  try {
    parsed = JSON.parse(input.trim());
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return { ok: false, error: `Couldn't parse JSON: ${msg}` };
  }

  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    return { ok: false, error: 'Couldn\'t parse JSON: expected an object' };
  }

  const obj = parsed as Record<string, unknown>;

  // Step 2: Shape A — Claude Desktop / Cursor wrapper
  if ('mcpServers' in obj) {
    const servers = obj.mcpServers;
    if (!servers || typeof servers !== 'object' || Array.isArray(servers)) {
      return { ok: false, error: 'JSON is missing a `url` field' };
    }
    const entries = Object.entries(servers as Record<string, unknown>);
    if (entries.length === 0) {
      return { ok: false, error: 'JSON is missing a `url` field' };
    }
    const [firstName, firstEntry] = entries[0];
    const warning =
      entries.length > 1
        ? `Imported '${firstName}'. Paste again to import the others.`
        : null;
    if (!firstEntry || typeof firstEntry !== 'object' || Array.isArray(firstEntry)) {
      return { ok: false, error: 'JSON is missing a `url` field' };
    }
    return buildServer(firstName, firstEntry as Record<string, unknown>, warning);
  }

  // Step 3: Shape B — VS Code mcp.json wrapper
  if ('servers' in obj) {
    const servers = obj.servers;
    if (!servers || typeof servers !== 'object' || Array.isArray(servers)) {
      return { ok: false, error: 'JSON is missing a `url` field' };
    }
    const entries = Object.entries(servers as Record<string, unknown>);
    if (entries.length === 0) {
      return { ok: false, error: 'JSON is missing a `url` field' };
    }
    const [firstName, firstEntry] = entries[0];
    const warning =
      entries.length > 1
        ? `Imported '${firstName}'. Paste again to import the others.`
        : null;
    if (!firstEntry || typeof firstEntry !== 'object' || Array.isArray(firstEntry)) {
      return { ok: false, error: 'JSON is missing a `url` field' };
    }
    return buildServer(firstName, firstEntry as Record<string, unknown>, warning);
  }

  // Step 4: Shape C — raw single-server entry (has url at root OR stdio at root)
  // Check for stdio before checking for url — a raw {command, args} entry is Shape C (rejected).
  if ('url' in obj || 'command' in obj || 'args' in obj) {
    return buildServer(null, obj, null);
  }

  // Step 5: Shape D — name-keyed map without wrapper
  const entries = Object.entries(obj);
  if (entries.length === 0) {
    return { ok: false, error: 'JSON is missing a `url` field' };
  }
  const [firstName, firstEntry] = entries[0];
  const warning =
    entries.length > 1
      ? `Imported '${firstName}'. Paste again to import the others.`
      : null;
  if (!firstEntry || typeof firstEntry !== 'object' || Array.isArray(firstEntry)) {
    return { ok: false, error: 'JSON is missing a `url` field' };
  }
  return buildServer(firstName, firstEntry as Record<string, unknown>, warning);
}
