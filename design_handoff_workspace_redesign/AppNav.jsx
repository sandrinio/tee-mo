/**
 * AppNav — sticky top bar. Mirrors frontend/src/components/layout/AppNav.tsx.
 */
function AppNav({ userEmail = 'alex@acme.com', onLogout }) {
  return (
    <nav className="sticky top-0 z-10 bg-white border-b border-slate-200 px-6 h-14 flex items-center justify-between">
      <a href="#" className="flex items-center gap-2 text-lg font-semibold text-brand-500" style={{letterSpacing: '-0.01em'}}>
        <LogoMark size={22} />
        Tee-Mo
      </a>
      <a href="#" className="text-sm font-medium text-slate-900">Workspaces</a>
      <div className="flex items-center gap-3">
        <span className="text-sm text-slate-700">{userEmail}</span>
        <Button variant="ghost" size="sm" onClick={onLogout}>Log out</Button>
      </div>
    </nav>
  );
}

Object.assign(window, { AppNav });
