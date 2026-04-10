/**
 * Badge — Design Guide §6.6
 *
 * Inline status indicator with a colored dot and label. Five semantic variants
 * map to Tailwind 4 built-in palette colors (emerald, amber, rose, sky, slate)
 * rather than the custom `@theme` semantic tokens — this is intentional per the
 * FLASHCARDS rule that `@theme` should only hold truly custom tokens, and these
 * built-ins already express the correct hues from the Design Guide.
 *
 * Variants:
 *   - `success` — emerald (green)  — table/backend healthy
 *   - `warning` — amber (yellow)   — degraded state
 *   - `danger`  — rose (red)       — error / down
 *   - `info`    — sky (blue)       — informational
 *   - `neutral` — slate (grey)     — loading / unknown. Default.
 *
 * @example
 * ```tsx
 * <Badge variant="success">teemo_users: ok</Badge>
 * <Badge variant="danger">Backend: error</Badge>
 * ```
 */
import type { HTMLAttributes } from 'react';

type BadgeVariant = 'success' | 'warning' | 'danger' | 'info' | 'neutral';

const variantClasses: Record<BadgeVariant, { bg: string; text: string; dot: string }> = {
  success: { bg: 'bg-emerald-50', text: 'text-emerald-700', dot: 'bg-emerald-500' },
  warning: { bg: 'bg-amber-50',   text: 'text-amber-700',   dot: 'bg-amber-500'   },
  danger:  { bg: 'bg-rose-50',    text: 'text-rose-700',    dot: 'bg-rose-500'    },
  info:    { bg: 'bg-sky-50',     text: 'text-sky-700',     dot: 'bg-sky-500'     },
  neutral: { bg: 'bg-slate-100',  text: 'text-slate-700',   dot: 'bg-slate-400'   },
};

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  /** Visual variant controlling color scheme. Defaults to `neutral`. */
  variant?: BadgeVariant;
}

/**
 * Tee-Mo status badge with a colored dot indicator.
 */
export function Badge({ variant = 'neutral', className = '', children, ...rest }: BadgeProps) {
  const v = variantClasses[variant];
  return (
    <span
      className={[
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium',
        v.bg, v.text, className,
      ].join(' ')}
      {...rest}
    >
      <span className={['h-1.5 w-1.5 rounded-full', v.dot].join(' ')} aria-hidden="true" />
      {children}
    </span>
  );
}
