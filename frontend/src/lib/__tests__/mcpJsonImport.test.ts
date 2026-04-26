/**
 * mcpJsonImport.test.ts — unit tests for the pure parseMcpJson function.
 *
 * All tests run in Node environment (no React, no jsdom needed).
 * Each test corresponds to a Gherkin scenario from STORY-012-04 §2.1 or
 * a minimum test expectation from §4.1.
 *
 * Fixture from STORY-012-04 §5.4 (canonical Claude Desktop shape):
 *   { "mcpServers": { "github": { "url": "https://api.githubcopilot.com/mcp/",
 *     "transport": "streamable-http", "headers": { "Authorization": "Bearer ghp_REPLACE" } } } }
 */
import { describe, it, expect } from 'vitest';
import { parseMcpJson } from '../mcpJsonImport';

// ---------------------------------------------------------------------------
// Shape A — Claude Desktop / Cursor mcpServers wrapper
// ---------------------------------------------------------------------------

describe('Shape A — Claude Desktop wrapper', () => {
  it('parses single server correctly (§5.4 fixture)', () => {
    const input = JSON.stringify({
      mcpServers: {
        github: {
          url: 'https://api.githubcopilot.com/mcp/',
          transport: 'streamable-http',
          headers: { Authorization: 'Bearer ghp_REPLACE_WITH_REAL_TOKEN' },
        },
      },
    });

    const result = parseMcpJson(input);

    expect(result.ok).toBe(true);
    if (!result.ok) throw new Error('Expected ok');

    expect(result.server.name).toBe('github');
    expect(result.server.transport).toBe('streamable_http');
    expect(result.server.url).toBe('https://api.githubcopilot.com/mcp/');
    expect(result.server.headers).toHaveLength(1);
    expect(result.server.headers[0].key).toBe('Authorization');
    expect(result.server.headers[0].value).toBe('Bearer ghp_REPLACE_WITH_REAL_TOKEN');
    expect(result.server.headers[0].placeholder).toBe(false);
    expect(result.server.warning).toBeNull();
  });

  it('emits "Paste again" warning when mcpServers has multiple entries', () => {
    const input = JSON.stringify({
      mcpServers: {
        github: { url: 'https://api.githubcopilot.com/mcp/', transport: 'streamable_http' },
        linear: { url: 'https://mcp.linear.app/sse', transport: 'sse' },
      },
    });

    const result = parseMcpJson(input);

    expect(result.ok).toBe(true);
    if (!result.ok) throw new Error('Expected ok');

    // Imports first server (github)
    expect(result.server.name).toBe('github');
    // Warning mentions the name
    expect(result.server.warning).toContain("'github'");
    expect(result.server.warning).toContain('Paste again');
  });

  it('normalises transport "streamable-http" (dash) → "streamable_http" (underscore)', () => {
    const input = JSON.stringify({
      mcpServers: {
        svc: { url: 'https://example.com/mcp', transport: 'streamable-http' },
      },
    });

    const result = parseMcpJson(input);

    expect(result.ok).toBe(true);
    if (!result.ok) throw new Error('Expected ok');
    expect(result.server.transport).toBe('streamable_http');
  });
});

// ---------------------------------------------------------------------------
// Shape B — VS Code mcp.json wrapper (type field)
// ---------------------------------------------------------------------------

describe('Shape B — VS Code servers wrapper', () => {
  it('maps type:"http" → "streamable_http" and extracts name from wrapper key', () => {
    const input = JSON.stringify({
      servers: {
        ado: { url: 'https://mcp.dev.azure.com/myorg', type: 'http' },
      },
    });

    const result = parseMcpJson(input);

    expect(result.ok).toBe(true);
    if (!result.ok) throw new Error('Expected ok');

    expect(result.server.name).toBe('ado');
    expect(result.server.transport).toBe('streamable_http');
    expect(result.server.url).toBe('https://mcp.dev.azure.com/myorg');
  });

  it('maps type:"sse" → "sse"', () => {
    const input = JSON.stringify({
      servers: {
        svc: { url: 'https://example.com/sse', type: 'sse' },
      },
    });

    const result = parseMcpJson(input);

    expect(result.ok).toBe(true);
    if (!result.ok) throw new Error('Expected ok');
    expect(result.server.transport).toBe('sse');
  });
});

// ---------------------------------------------------------------------------
// Shape C — raw single-server entry (url at root)
// ---------------------------------------------------------------------------

describe('Shape C — raw entry', () => {
  it('parses raw entry with url at root', () => {
    const input = JSON.stringify({
      url: 'https://example.com/mcp',
      transport: 'sse',
      headers: { 'X-Token': 'abc' },
    });

    const result = parseMcpJson(input);

    expect(result.ok).toBe(true);
    if (!result.ok) throw new Error('Expected ok');

    expect(result.server.name).toBeNull();
    expect(result.server.transport).toBe('sse');
    expect(result.server.url).toBe('https://example.com/mcp');
    expect(result.server.headers[0].key).toBe('X-Token');
  });

  it('defaults transport to "streamable_http" when transport field is absent', () => {
    const input = JSON.stringify({ url: 'https://example.com/mcp' });

    const result = parseMcpJson(input);

    expect(result.ok).toBe(true);
    if (!result.ok) throw new Error('Expected ok');
    expect(result.server.transport).toBe('streamable_http');
  });
});

// ---------------------------------------------------------------------------
// Stdio rejection
// ---------------------------------------------------------------------------

describe('Stdio rejection', () => {
  it('rejects config with "command" key with the literal error string', () => {
    const input = JSON.stringify({ command: 'npx', args: ['-y', 'azure-devops-mcp'] });

    const result = parseMcpJson(input);

    expect(result.ok).toBe(false);
    if (result.ok) throw new Error('Expected failure');
    expect(result.error).toBe(
      "Tee-Mo only supports HTTP-based MCP servers (SSE / Streamable HTTP). The config you pasted is for a local stdio server, which we don't support for security reasons.",
    );
  });

  it('rejects stdio config nested inside mcpServers wrapper', () => {
    const input = JSON.stringify({
      mcpServers: {
        bad: { command: 'python', args: ['server.py'] },
      },
    });

    const result = parseMcpJson(input);

    expect(result.ok).toBe(false);
    if (result.ok) throw new Error('Expected failure');
    expect(result.error).toContain('stdio server');
  });
});

// ---------------------------------------------------------------------------
// Placeholder header values
// ---------------------------------------------------------------------------

describe('Placeholder header detection', () => {
  it('clears ${env:...} placeholder values and sets placeholder=true', () => {
    const input = JSON.stringify({
      url: 'https://example.com/mcp',
      headers: { Authorization: '${env:GITHUB_TOKEN}' },
    });

    const result = parseMcpJson(input);

    expect(result.ok).toBe(true);
    if (!result.ok) throw new Error('Expected ok');

    const header = result.server.headers[0];
    expect(header.key).toBe('Authorization');
    expect(header.value).toBe('');
    expect(header.placeholder).toBe(true);
  });

  it('clears ${input:...} placeholder values', () => {
    const input = JSON.stringify({
      url: 'https://example.com/mcp',
      headers: { 'X-API-Key': '${input:Enter your API key}' },
    });

    const result = parseMcpJson(input);

    expect(result.ok).toBe(true);
    if (!result.ok) throw new Error('Expected ok');

    const header = result.server.headers[0];
    expect(header.value).toBe('');
    expect(header.placeholder).toBe(true);
  });

  it('does NOT flag non-placeholder values as placeholder', () => {
    const input = JSON.stringify({
      url: 'https://example.com/mcp',
      headers: { Authorization: 'Bearer real-token-here' },
    });

    const result = parseMcpJson(input);

    expect(result.ok).toBe(true);
    if (!result.ok) throw new Error('Expected ok');

    expect(result.server.headers[0].placeholder).toBe(false);
    expect(result.server.headers[0].value).toBe('Bearer real-token-here');
  });
});

// ---------------------------------------------------------------------------
// Invalid JSON
// ---------------------------------------------------------------------------

describe('Invalid JSON', () => {
  it('returns ok:false with parser error for malformed JSON', () => {
    const result = parseMcpJson('{not valid json}');

    expect(result.ok).toBe(false);
    if (result.ok) throw new Error('Expected failure');
    expect(result.error).toMatch(/Couldn't parse JSON/);
  });

  it('returns ok:false for JSON that is an array not an object', () => {
    const result = parseMcpJson('[1, 2, 3]');

    expect(result.ok).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Missing url
// ---------------------------------------------------------------------------

describe('Missing url', () => {
  it('rejects entry missing url field', () => {
    const input = JSON.stringify({ transport: 'sse', headers: {} });

    const result = parseMcpJson(input);

    expect(result.ok).toBe(false);
    if (result.ok) throw new Error('Expected failure');
    expect(result.error).toContain('url');
  });
});
