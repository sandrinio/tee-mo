/**
 * Card — Design Guide §6.3
 *
 * A simple container with a white background, subtle slate border, rounded
 * corners, and inner padding. Accepts `className` for composition (e.g.,
 * overriding padding or adding margin from the call site).
 *
 * Companion exports `CardHeader` and `CardBody` provide semantic landmark
 * structure within a card when the content warrants it. Both are thin
 * wrappers — no additional styling beyond what the parent `Card` already
 * provides — so they can be used or omitted freely.
 *
 * @example
 * ```tsx
 * <Card>
 *   <CardHeader><h2>Title</h2></CardHeader>
 *   <CardBody>Content goes here.</CardBody>
 * </Card>
 * ```
 */
import type { HTMLAttributes } from 'react';

/**
 * Card container — `rounded-lg border border-slate-200 bg-white p-6` per Design Guide §6.3.
 */
export function Card({ className = '', ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={['rounded-lg border border-slate-200 bg-white p-6', className].join(' ')}
      {...rest}
    />
  );
}

/**
 * Semantic header slot inside a `<Card>`. Renders a `<div>` with bottom margin
 * to separate it from the body content below.
 */
export function CardHeader({ className = '', ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={['mb-4', className].join(' ')}
      {...rest}
    />
  );
}

/**
 * Semantic body slot inside a `<Card>`. Passthrough `<div>` — no additional
 * styling so content controls its own layout.
 */
export function CardBody({ className = '', ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={className} {...rest} />;
}
