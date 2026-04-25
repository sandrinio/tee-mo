/**
 * Shared UI primitives for Tee-Mo dashboard kit.
 * Mirrors frontend/src/components/ui/*.
 */

function Button({ variant = 'primary', size = 'md', className = '', children, ...rest }) {
  const variants = {
    primary: 'bg-brand-500 text-white hover:bg-brand-600',
    secondary: 'bg-white text-slate-900 border border-slate-300 hover:bg-slate-50 hover:border-slate-400',
    ghost: 'text-slate-700 hover:bg-slate-100',
    danger: 'bg-rose-600 text-white hover:bg-rose-700',
  };
  const sizes = {
    sm: 'h-8 px-3 text-xs',
    md: 'h-10 px-4 text-sm',
    lg: 'h-12 px-6 text-base',
  };
  return (
    <button
      className={[
        'inline-flex items-center gap-2 font-medium rounded-md transition-colors duration-150',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2',
        variants[variant], sizes[size], className,
      ].join(' ')}
      {...rest}
    >{children}</button>
  );
}

function Card({ className = '', children, ...rest }) {
  return (
    <div className={['rounded-lg border border-slate-200 bg-white p-6', className].join(' ')} {...rest}>
      {children}
    </div>
  );
}

function Badge({ variant = 'neutral', className = '', children }) {
  const v = {
    success: 'bg-emerald-50 text-emerald-700',
    warning: 'bg-amber-50 text-amber-700',
    danger: 'bg-rose-50 text-rose-700',
    info: 'bg-sky-50 text-sky-700',
    neutral: 'bg-slate-100 text-slate-700',
  }[variant];
  const dot = {
    success: 'bg-emerald-500',
    warning: 'bg-amber-500',
    danger: 'bg-rose-500',
    info: 'bg-sky-500',
    neutral: 'bg-slate-400',
  }[variant];
  return (
    <span className={['inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium', v, className].join(' ')}>
      <span className={['h-1.5 w-1.5 rounded-full', dot].join(' ')} />
      {children}
    </span>
  );
}

function Icon({ name, className = 'w-4 h-4' }) {
  // Lucide via <i data-lucide>; ensure lucide.createIcons runs after mount.
  return <i data-lucide={name} className={className} />;
}

function LogoMark({ size = 24 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="46" y="41" width="28" height="60" rx="14" fill="#BE123C" />
      <rect x="18" y="19" width="46" height="28" rx="14" fill="#E11D48" />
      <rect x="56" y="19" width="46" height="28" rx="14" fill="#F43F5E" />
    </svg>
  );
}

Object.assign(window, { Button, Card, Badge, Icon, LogoMark });
