/**
 * StickyTabBar.tsx — Sticky navigation tab bar for the workspace v2 shell.
 *
 * Per W01 §5.5 and story §1.2:
 *   - `top-14` positions the bar below the AppNav (h-14, h=56px).
 *   - `bg-slate-50/90 backdrop-blur-sm` per design handoff README §"Variation B".
 *   - Active tab: `bg-white border border-slate-200 shadow-sm`.
 *   - Each tab shows an `okCount / total` pill.
 *
 * STORY-025-06 mobile treatment (§1.2, §3.2):
 *   - Outer nav: `overflow-x-auto -mx-4 px-4 md:mx-0 md:px-0 md:overflow-visible`
 *     so the bar scrolls horizontally at <md breakpoint.
 *   - Scrollbar hidden: `[&::-webkit-scrollbar]:hidden` (WebKit) + style prop for Firefox.
 *   - Tab min-width: `min-w-max md:min-w-0` so labels don't wrap or truncate.
 *   - Active-tab auto-scroll: useEffect([activeGroupId]) → tabRefs[activeGroupId]?.current
 *     .scrollIntoView({inline:'center', block:'nearest'}) keeps active pill visible.
 *     `block:'nearest'` is critical — prevents vertical page scroll.
 *
 * Prop contract frozen by W01 §5.5. The `groups` array is computed by WorkspaceShell
 * from MODULE_REGISTRY entries filtered by group.
 */

import { useRef, useEffect } from 'react';
import type { ModuleGroup } from './types';

export interface TabGroup {
  id: ModuleGroup;
  label: string;
  okCount: number;
  total: number;
}

export interface StickyTabBarProps {
  /** Ordered list of groups with status tallies. */
  groups: TabGroup[];
  /** Currently-active group id. */
  activeGroupId: string;
  /** Called when the user clicks a tab. */
  onTabClick: (groupId: ModuleGroup) => void;
}

/**
 * StickyTabBar — renders one tab pill per module group, sticky below AppNav.
 *
 * Active tab styling: `bg-white border border-slate-200 shadow-sm text-slate-900`.
 * Inactive styling: `text-slate-600 hover:text-slate-900 hover:bg-white/60`.
 * Mobile: horizontal scroll, active pill auto-scrolled into bar viewport.
 */
export function StickyTabBar({ groups, activeGroupId, onTabClick }: StickyTabBarProps) {
  // Refs keyed by group id for active-tab auto-scroll (§1.2 + §3.2).
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({});

  // Auto-scroll the active tab pill into the bar's horizontal viewport (STORY-025-06 §3.2).
  // `block:'nearest'` ensures only horizontal scrolling occurs (no vertical page jump).
  useEffect(() => {
    const el = tabRefs.current[activeGroupId];
    if (!el) return;
    el.scrollIntoView?.({ inline: 'center', block: 'nearest' });
  }, [activeGroupId]);

  return (
    <div
      className="sticky top-14 z-20 bg-slate-50/90 backdrop-blur-sm border-b border-slate-200"
      data-testid="sticky-tab-bar"
    >
      {/* Scrollable inner row — mobile: overflow-x-auto with negative margin bleed */}
      <div
        className="overflow-x-auto -mx-4 px-4 md:mx-0 md:px-0 md:overflow-visible [&::-webkit-scrollbar]:hidden"
        style={{ scrollbarWidth: 'none' }}
        data-testid="tab-bar-scroll-container"
      >
        <div className="flex items-center gap-1 py-2">
          {groups.map((group) => {
            const isActive = activeGroupId === group.id;
            return (
              <button
                key={group.id}
                ref={(el) => { tabRefs.current[group.id] = el; }}
                type="button"
                data-group-id={group.id}
                onClick={() => onTabClick(group.id)}
                className={[
                  'h-9 px-3 rounded-md text-sm font-medium transition-colors',
                  'flex items-center gap-2 whitespace-nowrap',
                  // min-w-max keeps label intact on mobile; md resets to natural width.
                  'min-w-max md:min-w-0',
                  isActive
                    ? 'bg-white text-slate-900 border border-slate-200 shadow-sm'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-white/60',
                ].join(' ')}
              >
                <span>{group.label}</span>
                <span
                  className={[
                    'text-[11px] tabular-nums rounded-full px-1.5 py-0.5',
                    isActive ? 'bg-slate-100 text-slate-600' : 'text-slate-400',
                  ].join(' ')}
                >
                  {group.okCount} / {group.total}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
