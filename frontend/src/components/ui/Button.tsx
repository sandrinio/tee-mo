/**
 * Button — Design Guide §6.1
 *
 * Reusable button primitive with four visual variants and three sizes.
 * Forwards ref to the underlying `<button>` element so it can be composed
 * inside form libraries and focus-management utilities.
 *
 * Variants:
 *   - `primary`   — coral fill (brand-500), white text. Default.
 *   - `secondary` — white fill, slate border.
 *   - `ghost`     — transparent, slate text; no border.
 *   - `danger`    — rose fill, white text. Destructive actions only.
 *
 * Sizes: `sm` (h-8), `md` (h-10, default), `lg` (h-12).
 *
 * Disabled state: 50% opacity + not-allowed cursor via Tailwind utility classes.
 * Focus ring: 2px coral brand-500 ring with white offset (keyboard accessible).
 */
import { forwardRef, type ButtonHTMLAttributes } from 'react';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
type Size = 'sm' | 'md' | 'lg';

const variantClasses: Record<Variant, string> = {
  primary:   'bg-brand-500 text-white hover:bg-brand-600',
  secondary: 'bg-white text-slate-900 border border-slate-300 hover:bg-slate-50 hover:border-slate-400',
  ghost:     'text-slate-700 hover:bg-slate-100',
  danger:    'bg-rose-600 text-white hover:bg-rose-700',
};

const sizeClasses: Record<Size, string> = {
  sm: 'h-8 px-3 text-xs',
  md: 'h-10 px-4 text-sm',
  lg: 'h-12 px-6 text-base',
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Visual style variant. Defaults to `primary`. */
  variant?: Variant;
  /** Height + padding scale. Defaults to `md`. */
  size?: Size;
}

/**
 * Tee-Mo design system button.
 *
 * @example
 * ```tsx
 * <Button variant="primary" onClick={handleSubmit}>Save</Button>
 * <Button variant="secondary" size="sm">Cancel</Button>
 * <Button variant="danger" disabled>Delete</Button>
 * ```
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', className = '', ...rest }, ref) => (
    <button
      ref={ref}
      className={[
        'inline-flex items-center gap-2 font-medium rounded-md transition-colors duration-150',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white',
        variantClasses[variant],
        sizeClasses[size],
        className,
      ].join(' ')}
      {...rest}
    />
  ),
);

Button.displayName = 'Button';
