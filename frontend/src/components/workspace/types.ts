/**
 * types.ts — Shared type contracts for the Workspace v2 shell (STORY-025-01).
 *
 * These types are the frozen contracts that STORY-025-02 through 025-06 consume.
 * Any shape change here forces rework tax on every follow-on story.
 *
 * Per W01 §5 (blueprint), the shapes below are NON-NEGOTIABLE:
 *   - WorkspaceData  §5.2
 *   - ModuleStatus   §5.3 / design README
 *   - StatusResolver §5.3
 *   - ModuleGroup    §3 moduleRegistry.ts blueprint
 *   - StatusCell     §5.4
 *   - ModuleEntry    §3 moduleRegistry.ts blueprint
 */

import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import type {
  Workspace,
  ChannelBinding,
  KnowledgeFile,
  Skill,
  Automation,
  McpServer,
} from '../../lib/api';

// ---------------------------------------------------------------------------
// Module status
// ---------------------------------------------------------------------------

/**
 * The status value returned by a module's statusResolver.
 *
 * - `ok`      — green; fully configured.
 * - `partial` — amber; partially configured (e.g. files indexed but <15).
 * - `empty`   — slate; not yet configured.
 * - `error`   — rose; connection broken or key invalid.
 * - `neutral` — slate; not applicable / insufficient data to determine.
 */
export type ModuleStatus = 'ok' | 'partial' | 'empty' | 'error' | 'neutral';

// ---------------------------------------------------------------------------
// Module group
// ---------------------------------------------------------------------------

/**
 * Top-level navigation group identifiers.
 * Matches the sticky tab bar ordering defined in W01 §3.
 */
export type ModuleGroup = 'connections' | 'knowledge' | 'behavior' | 'workspace';

// ---------------------------------------------------------------------------
// WorkspaceData — aggregate data shape consumed by status resolvers
// ---------------------------------------------------------------------------

/**
 * Aggregated workspace data assembled by WorkspaceShell from 7 useQuery calls.
 *
 * Frozen by STORY-025-01 per W01 §5.2. STORY-025-02..05 resolvers consume this
 * shape without redeclaring it. Resolvers MUST tolerate missing nested fields
 * (use ?? defaults) — never throw.
 */
export interface WorkspaceData {
  workspace: Workspace;
  drive: { connected: boolean; email?: string | null };
  key: { has_key: boolean; provider?: string | null; key_hint?: string | null };
  channels: ChannelBinding[];
  files: KnowledgeFile[];
  skills: Skill[];
  automations: Automation[];
  mcpServers: McpServer[];
}

// ---------------------------------------------------------------------------
// Status resolver
// ---------------------------------------------------------------------------

/**
 * Function signature for module status resolvers.
 * Called once per render by WorkspaceShell to compute per-module status.
 *
 * MUST tolerate `data` fields being undefined/null (use ?? defaults).
 * MUST never throw.
 */
export type StatusResolver = (data: WorkspaceData) => ModuleStatus;

// ---------------------------------------------------------------------------
// StatusCell — StatusStrip cell shape
// ---------------------------------------------------------------------------

/**
 * A single cell in the StatusStrip.
 * Frozen by W01 §5.4.
 */
export interface StatusCell {
  /** 11px uppercase kicker label, e.g. "PROVIDER" */
  kicker: string;
  /** 14px/600 value, e.g. "OpenAI" */
  value: string;
  /** Optional 12px slate-500 caption, e.g. "sk-proj-…G7vT" */
  caption?: string;
}

// ---------------------------------------------------------------------------
// ModuleEntry — registry entry shape
// ---------------------------------------------------------------------------

/**
 * Context passed to every module's render function.
 * Carries the workspace + identifiers + the aggregated WorkspaceData.
 * Each module's render fn destructures only what it needs.
 *
 * Added by HOTFIX 2026-04-26 to plug the architectural gap where
 * STORY-025-01 left a placeholder body and STORY-025-02..05 added registry
 * metadata but no body component reference.
 */
export interface ModuleRenderContext {
  workspace: Workspace;
  workspaceId: string;
  teamId: string;
  data: WorkspaceData;
}

/**
 * A module registry entry.
 * Frozen by W01 §3 / §5.3, extended by HOTFIX 2026-04-26 with `render`.
 */
export interface ModuleEntry {
  /** Unique module ID. Section anchor becomes `tm-${id}`. */
  id: string;
  /** Navigation group this module belongs to. */
  group: ModuleGroup;
  /** Human-readable label shown in the sticky tab bar and section header. */
  label: string;
  /** Lucide icon reference for the module. */
  icon: LucideIcon;
  /** Optional one-line module summary shown in section caption. */
  summary?: string;
  /**
   * Status resolver invoked once per render with WorkspaceData.
   * Must return a ModuleStatus, never throw, never crash on missing fields.
   */
  statusResolver: StatusResolver;
  /**
   * Render function for the module body.
   * Returns the section component JSX with appropriate props pulled from ctx.
   * Wrapping ModuleSection (h2 + card border) is the shell's job — this fn
   * returns ONLY the body content per W01 §5.1 contract.
   */
  render: (ctx: ModuleRenderContext) => ReactNode;
}

// ---------------------------------------------------------------------------
// ModuleSectionProps — ModuleSection component props
// ---------------------------------------------------------------------------

/**
 * Props for the ModuleSection wrapper component.
 * Frozen by W01 §5.1.
 */
export interface ModuleSectionProps {
  /** Unique module id — becomes the `tm-${id}` anchor. */
  id: string;
  /** Section heading text (h2). */
  title: string;
  /** Optional subtitle rendered beneath the heading. */
  caption?: string;
  /** Optional top-right action slot (e.g. "Add file" button). */
  action?: ReactNode;
  /** Module body content. */
  children: ReactNode;
}
