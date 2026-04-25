/**
 * Variation A — Sidebar settings rail.
 * Left rail with grouped modules (status dots), right column scrolls with content.
 * Quiet, scannable; scales to many modules.
 */

function SidebarRail({ active, onSelect, modules, groups, progress }) {
  return (
    <aside className="flex flex-col w-[240px] shrink-0 border-r border-slate-200 bg-white">
      <div className="px-5 py-5 border-b border-slate-100">
        <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">Workspace</div>
        <div className="mt-1 text-base font-semibold text-slate-900" style={{letterSpacing:'-0.01em'}}>Acme Corp</div>
        <div className="mt-3 flex items-center gap-2">
          <div className="flex-1 h-1 rounded-full bg-slate-100 overflow-hidden">
            <div className="h-full bg-emerald-500" style={{width: `${progress}%`}} />
          </div>
          <span className="text-xs text-slate-500 tabular-nums">{progress}%</span>
        </div>
        <div className="mt-1 text-[11px] text-slate-400">Setup complete</div>
      </div>

      <nav className="flex-1 overflow-y-auto py-3">
        {Object.entries(groups).map(([gid, g]) => {
          const items = modules.filter(m => m.group === gid);
          if (!items.length) return null;
          return (
            <div key={gid} className="mb-3">
              <div className="px-5 pb-1 pt-2 text-[11px] font-medium text-slate-400 uppercase tracking-wider">{g.label}</div>
              <ul>
                {items.map(m => {
                  const isActive = active === m.id;
                  return (
                    <li key={m.id}>
                      <button
                        onClick={() => onSelect(m.id)}
                        className={[
                          'w-full px-5 py-1.5 flex items-center gap-2.5 text-sm text-left transition-colors',
                          isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-700 hover:bg-slate-50',
                        ].join(' ')}
                      >
                        <span className={isActive ? 'text-brand-600' : 'text-slate-400'}>
                          <Icon name={m.icon} className="w-4 h-4" />
                        </span>
                        <span className="flex-1 truncate">{m.label}</span>
                        <StatusDot status={m.status} />
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </nav>

      <div className="p-3 border-t border-slate-100">
        <button className="w-full px-3 py-2 flex items-center gap-2 text-xs text-slate-500 hover:bg-slate-50 rounded-md transition-colors">
          <Icon name="search" className="w-3.5 h-3.5" />
          <span className="flex-1 text-left">Jump to setting</span>
          <kbd className="font-mono text-[10px] text-slate-400 bg-slate-100 rounded px-1.5 py-0.5">⌘K</kbd>
        </button>
      </div>
    </aside>
  );
}

function VariationA({ files, channels }) {
  const [active, setActive] = React.useState('files');
  const mod = TM_MODULES.find(m => m.id === active);
  const okCount = TM_MODULES.filter(m => m.status === 'ok').length;
  const progress = Math.round((okCount / TM_MODULES.length) * 100);

  React.useEffect(() => { lucide.createIcons(); }, [active]);

  return (
    <div className="flex min-h-[720px]">
      <SidebarRail active={active} onSelect={setActive} modules={TM_MODULES} groups={TM_GROUPS} progress={progress} />
      <div className="flex-1 min-w-0 bg-slate-50">
        <div className="max-w-3xl mx-auto px-6 md:px-8 py-8">
          <div className="flex items-center gap-2 text-xs text-slate-500 mb-1">
            <span>{TM_GROUPS[mod.group].label}</span>
            <span className="text-slate-300">/</span>
            <span className="text-slate-700">{mod.label}</span>
          </div>
          <h1 className="text-2xl font-semibold text-slate-900" style={{letterSpacing:'-0.015em'}}>{mod.label}</h1>
          <p className="text-sm text-slate-500 mt-1">{mod.summary}</p>

          <div className="mt-6">
            <div className="rounded-lg border border-slate-200 bg-white">
              <ModuleBody id={active} files={files} channels={channels} />
            </div>
          </div>

          <div className="mt-8 pt-6 border-t border-slate-100 flex items-center justify-between text-xs text-slate-400">
            <span>Last edited 2 minutes ago by alex@acme.com</span>
            <span className="font-mono">workspace_id: ws_acme_8f2a</span>
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { VariationA });
