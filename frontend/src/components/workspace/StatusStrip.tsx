/**
 * StatusStrip.tsx — 4-cell informational card grid for the workspace v2 shell.
 *
 * Per W01 §5.4 and story §1.2:
 *   - Always exactly 4 cells (Workspace / Slack / Provider / Knowledge).
 *   - "Setup" cell dropped per epic §6 Q4 — wizard retired.
 *   - Cells are informational, NOT clickable — rendered as <div>, not <button>.
 *   - 4 columns at md+, 2 columns below md.
 *
 * Per-cell markup per W01 §3:
 *   11px uppercase kicker + 14px/600 value + optional 12px slate-500 caption.
 */

import type { StatusCell } from './types';

export interface StatusStripProps {
  /** Exactly 4 cells. Fewer or more are accepted but the design expects 4. */
  cells: StatusCell[];
}

/**
 * StatusStrip — displays workspace health at a glance.
 *
 * Responsive: 2 columns below md breakpoint, 4 columns at md+.
 */
export function StatusStrip({ cells }: StatusStripProps) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {cells.map((cell) => (
        <div
          key={cell.kicker}
          className="rounded-lg border border-slate-200 bg-white p-4"
        >
          <div className="text-[11px] font-medium uppercase tracking-wider text-slate-500">
            {cell.kicker}
          </div>
          <div className="mt-1 text-sm font-semibold text-slate-900 truncate">
            {cell.value}
          </div>
          {cell.caption && (
            <div className="mt-0.5 text-xs text-slate-500 truncate">
              {cell.caption}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
