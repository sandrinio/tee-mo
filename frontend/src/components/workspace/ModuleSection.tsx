/**
 * ModuleSection.tsx — Anchored section wrapper for workspace v2 modules.
 *
 * Renders an anchored <section> with id="tm-{id}" so scrollspy and deep-links
 * can target it. The `scrollMarginTop` inline style equals HEADER_OFFSET (140px),
 * which is the single source of truth shared with the tab-click handler.
 *
 * Prop contract frozen by W01 §5.1. STORY-025-02..05 section components render
 * ONLY the body content and pass it as `children` — they do NOT render their
 * own h2 or outer card border (that would double-border).
 */

import type { ReactNode } from 'react';
import { HEADER_OFFSET } from './useScrollspy';

export interface ModuleSectionProps {
  /** Unique module id — becomes the anchor `tm-${id}`. */
  id: string;
  /** Section heading text (h2). */
  title: string;
  /** Optional sub-headline displayed below the title. */
  caption?: string;
  /** Optional top-right slot (e.g. "Add file" button). */
  action?: ReactNode;
  /** Module body content. */
  children: ReactNode;
}

/**
 * ModuleSection — wraps a single workspace module in its anchor container.
 *
 * The section id uses the `tm-{id}` convention so deep-links like `#tm-files`
 * work without any extra mapping. `scrollMarginTop` ensures the browser's native
 * anchor scroll (cold-load deep link) lands at the same offset as the programmatic
 * `scrollIntoView` triggered by tab clicks.
 */
export function ModuleSection({ id, title, caption, action, children }: ModuleSectionProps) {
  return (
    <section
      id={`tm-${id}`}
      style={{ scrollMarginTop: HEADER_OFFSET }}
      className="space-y-4"
    >
      {/* Section header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-slate-900">{title}</h2>
          {caption && (
            <p className="mt-0.5 text-sm text-slate-500">{caption}</p>
          )}
        </div>
        {action && (
          <div className="flex-shrink-0">{action}</div>
        )}
      </div>

      {/* Module body card */}
      <div className="rounded-lg border border-slate-200 bg-white">
        {children}
      </div>
    </section>
  );
}
