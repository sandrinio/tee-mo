/**
 * Variation B — Status strip + sticky tabbed sub-nav with scrollspy.
 * One scrolling page; sticky tabs jump between anchored sections; status visible always.
 */

function StatusStrip({ modules }) {
  const tally = {
    ok:      modules.filter(m => m.status === 'ok').length,
    partial: modules.filter(m => m.status === 'partial').length,
    empty:   modules.filter(m => m.status === 'empty').length,
  };
  const total = modules.length;
  const cells = [
    { k: 'Workspace',   v: 'Acme Corp',          sub: 'Default · DMs route here' },
    { k: 'Slack',       v: 'acme.slack.com',     sub: '3 channels bound' },
    { k: 'Provider',    v: 'OpenAI',             sub: 'sk-…G7vT · validated' },
    { k: 'Knowledge',   v: '12 / 15 files',      sub: 'Last sync 1h ago' },
    { k: 'Setup',       v: `${tally.ok} of ${total}`, sub: `${tally.partial} partial · ${tally.empty} empty` },
  ];
  return (
    <div className="rounded-lg border border-slate-200 bg-white grid grid-cols-2 md:grid-cols-5">
      {cells.map((c, i) => (
        <div key={c.k} className={[
          'p-4',
          i > 0 ? 'md:border-l border-slate-100' : '',
          i % 2 === 1 ? 'border-l border-slate-100 md:border-l' : '',
          i < 3 ? 'border-b md:border-b-0 border-slate-100' : '',
        ].join(' ')}>
          <div className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">{c.k}</div>
          <div className="mt-1 text-sm font-semibold text-slate-900 truncate">{c.v}</div>
          <div className="text-xs text-slate-500 truncate">{c.sub}</div>
        </div>
      ))}
    </div>
  );
}

function TabBar({ groups, active, onSelect, modules }) {
  return (
    <div className="sticky top-14 z-20 bg-slate-50/90 backdrop-blur-sm -mx-8 px-8 py-3 border-b border-slate-200">
      <div className="flex items-center gap-1 overflow-x-auto">
        {Object.entries(groups).map(([gid, g]) => {
          const items = modules.filter(m => m.group === gid);
          if (!items.length) return null;
          const isActive = active === gid;
          const okCount = items.filter(m => m.status === 'ok').length;
          return (
            <button
              key={gid}
              onClick={() => onSelect(gid)}
              className={[
                'group h-9 px-3 rounded-md text-sm font-medium transition-colors flex items-center gap-2 whitespace-nowrap',
                isActive ? 'bg-white text-slate-900 border border-slate-200 shadow-sm' : 'text-slate-600 hover:text-slate-900 hover:bg-white/60',
              ].join(' ')}
            >
              <span>{g.label}</span>
              <span className={[
                'text-[11px] tabular-nums rounded-full px-1.5 py-0.5',
                isActive ? 'bg-slate-100 text-slate-600' : 'text-slate-400',
              ].join(' ')}>{okCount}/{items.length}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function VariationB({ files, channels }) {
  const [active, setActive] = React.useState('connections');
  const scrollRef = React.useRef(null);

  React.useEffect(() => { lucide.createIcons(); });

  // scrollspy
  React.useEffect(() => {
    const onScroll = () => {
      const groups = Object.keys(TM_GROUPS);
      let current = groups[0];
      for (const gid of groups) {
        const items = TM_MODULES.filter(m => m.group === gid);
        if (!items.length) continue;
        const el = document.getElementById(`tm-${items[0].id}`);
        if (el && el.getBoundingClientRect().top < 200) current = gid;
      }
      setActive(current);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const jump = (gid) => {
    const items = TM_MODULES.filter(m => m.group === gid);
    if (!items.length) return;
    const el = document.getElementById(`tm-${items[0].id}`);
    if (el) {
      const top = el.getBoundingClientRect().top + window.scrollY - 140;
      window.scrollTo({ top, behavior: 'smooth' });
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-8 pt-6 pb-16">
      {/* Header */}
      <div className="flex items-end justify-between mb-4 gap-4">
        <div>
          <button className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800 mb-1.5 transition-colors">
            <Icon name="chevron-left" className="w-3.5 h-3.5" />
            All workspaces
          </button>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold text-slate-900" style={{letterSpacing:'-0.015em'}}>Acme Corp</h1>
            <Badge variant="success">Connected</Badge>
            <span className="text-xs font-medium text-brand-600 bg-brand-50 rounded-full px-2 py-0.5">DMs route here</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm">Rename</Button>
          <Button variant="secondary" size="sm">Open in Slack</Button>
        </div>
      </div>

      {/* Status strip */}
      <StatusStrip modules={TM_MODULES} />

      {/* Sticky tab nav */}
      <TabBar groups={TM_GROUPS} active={active} onSelect={jump} modules={TM_MODULES} />

      {/* Sections */}
      <div ref={scrollRef} className="mt-6 space-y-10">
        {Object.entries(TM_GROUPS).map(([gid, g]) => {
          const items = TM_MODULES.filter(m => m.group === gid);
          if (!items.length) return null;
          return (
            <div key={gid} className="space-y-5">
              <div className="flex items-baseline gap-2">
                <h2 className="text-xs font-medium text-slate-400 uppercase tracking-wider">{g.label}</h2>
                {g.caption && <span className="text-xs text-slate-400">— {g.caption}</span>}
              </div>
              {items.map(m => (
                <ModuleSection
                  key={m.id}
                  id={m.id}
                  title={m.label}
                  caption={m.summary}
                  action={<StatusDot status={m.status} />}
                >
                  <ModuleBody id={m.id} files={files} channels={channels} />
                </ModuleSection>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}

Object.assign(window, { VariationB });
