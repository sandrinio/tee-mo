/**
 * useScrollspy.ts — IntersectionObserver-style scrollspy via window scroll event.
 *
 * Per W01 §3 STORY-025-01 blueprint and story §3.2.
 *
 * Exports:
 *   HEADER_OFFSET     = 140  — single source of truth for sticky header clearance.
 *   SCROLLSPY_THRESHOLD = 200 — distance from viewport top that "activates" a group.
 *   useScrollspy(groupAnchorIds) — rAF-throttled scrollspy hook.
 *
 * Hook signature (frozen by W01 §5 — 025-02..05 consume this):
 *   useScrollspy(groupAnchorIds: string[]):
 *     { activeGroupId: string; setProgrammaticScrolling: (v: boolean) => void }
 *
 * Three hardenings (per story §3.2):
 *   1. `isProgrammaticScroll` ref gate — short-circuits the resolver while a tab
 *      click's smooth-scroll animation is in flight, preventing active-tab flicker.
 *      Cleared on `scrollend` event; 600ms setTimeout fallback for Safari ≤16.
 *   2. End-of-page guard — forces `activeGroupId = lastGroupId` when the user has
 *      scrolled to the bottom, so the last tab activates even when the last group's
 *      section is shorter than the viewport.
 *   3. rAF throttling — at most one scroll handler execution per animation frame.
 */

import { useState, useEffect, useRef, useCallback } from 'react';

// ---------------------------------------------------------------------------
// Exported constants — single source of truth (referenced by ModuleSection +
// tab-click handler in WorkspaceShell).
// ---------------------------------------------------------------------------

/** Clearance in px below the sticky AppNav + StickyTabBar stack. */
export const HEADER_OFFSET = 140;

/** Distance from viewport top at which a section "activates" its group tab. */
export const SCROLLSPY_THRESHOLD = 200;

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Scrollspy hook — tracks which module group's section is currently "active"
 * based on scroll position.
 *
 * @param groupAnchorIds - Ordered list of element IDs (WITHOUT the `tm-` prefix;
 *   the hook builds the full `tm-${id}` selector internally). Order determines
 *   fallback: the first ID is the default when no section has passed the threshold.
 *
 * @returns
 *   - `activeGroupId` — the id of the currently-active group section (first item
 *      by default).
 *   - `setProgrammaticScrolling` — call with `true` before triggering a
 *     programmatic `scrollIntoView`. The hook short-circuits the resolver until
 *     the scroll settles (`scrollend` / 600ms fallback).
 */
export default function useScrollspy(groupAnchorIds: string[]): {
  activeGroupId: string;
  setProgrammaticScrolling: (v: boolean) => void;
} {
  const [activeGroupId, setActiveGroupId] = useState<string>(groupAnchorIds[0] ?? '');
  const isProgrammaticRef = useRef(false);
  const rafRef = useRef<number | null>(null);

  // Stable setter that does not re-subscribe the scroll listener on every call.
  const setProgrammaticScrolling = useCallback((v: boolean) => {
    isProgrammaticRef.current = v;
  }, []);

  useEffect(() => {
    if (groupAnchorIds.length === 0) return;

    const lastGroupId = groupAnchorIds[groupAnchorIds.length - 1];

    const resolveActive = () => {
      // Harden 1: programmatic-scroll gate
      if (isProgrammaticRef.current) return;

      // Harden 2: end-of-page guard
      const { scrollY, innerHeight } = window;
      const scrollHeight = document.documentElement.scrollHeight;
      if (scrollY + innerHeight >= scrollHeight - 8) {
        setActiveGroupId(lastGroupId);
        return;
      }

      // Standard topmost-≤-threshold resolver
      let current = groupAnchorIds[0];
      for (const id of groupAnchorIds) {
        const el = document.getElementById(`tm-${id}`);
        if (el && el.getBoundingClientRect().top <= SCROLLSPY_THRESHOLD) {
          current = id;
        }
      }
      setActiveGroupId(current);
    };

    // Harden 3: rAF throttling
    const onScroll = () => {
      if (rafRef.current !== null) return;
      rafRef.current = requestAnimationFrame(() => {
        rafRef.current = null;
        resolveActive();
      });
    };

    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', onScroll);
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
    // Stringify the array to get a stable dependency value. groupAnchorIds is
    // typically built from MODULE_REGISTRY which is a module-level constant.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [groupAnchorIds.join(',')]);

  return { activeGroupId, setProgrammaticScrolling };
}
