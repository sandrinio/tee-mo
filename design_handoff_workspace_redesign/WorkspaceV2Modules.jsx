/**
 * Module definitions and per-module content cards for the workspace settings page.
 * Each module = one section the admin manages. Grouped into Connections / Knowledge / Behavior.
 */

const TM_MODULES = [
  // Connections
  { id: 'slack',      group: 'connections', label: 'Slack',         icon: 'message-square',status: 'ok',     summary: 'acme.slack.com · installed Apr 14' },
  { id: 'drive',      group: 'connections', label: 'Google Drive',  icon: 'folder-open',   status: 'ok',     summary: 'alex@acme.com · 12 files visible' },
  { id: 'key',        group: 'connections', label: 'AI provider',   icon: 'key-round',     status: 'ok',     summary: 'OpenAI · sk-…G7vT' },
  { id: 'channels',   group: 'connections', label: 'Channels',      icon: 'hash',          status: 'ok',     summary: '3 channels bound' },
  // Knowledge
  { id: 'files',      group: 'knowledge',   label: 'Files',         icon: 'file-text',     status: 'partial',summary: '12 / 15 indexed' },
  // Behavior
  { id: 'persona',    group: 'behavior',    label: 'Persona',       icon: 'user-round',    status: 'partial',summary: 'Default voice — not customized' },
  { id: 'skills',     group: 'behavior',    label: 'Skills',        icon: 'sparkles',      status: 'ok',     summary: '4 skills · 1 created in Slack' },
  { id: 'automation', group: 'behavior',    label: 'Automation',    icon: 'zap',           status: 'empty',  summary: 'No triggers yet' },
  // Future
  { id: 'audit',      group: 'observability', label: 'Audit log',   icon: 'scroll-text',   status: 'ok',     summary: '218 events · last 7d' },
  { id: 'usage',      group: 'observability', label: 'Usage',       icon: 'bar-chart-3',   status: 'ok',     summary: '1,420 calls · $4.18' },
  { id: 'danger',     group: 'danger',      label: 'Danger zone',   icon: 'alert-triangle',status: 'neutral',summary: 'Delete or transfer workspace' },
];

const TM_GROUPS = {
  connections:   { label: 'Connections',   caption: 'Slack, Drive, key, channels' },
  knowledge:     { label: 'Knowledge',     caption: 'Files Tee-Mo can read' },
  behavior:      { label: 'Behavior',      caption: 'How Tee-Mo answers' },
  observability: { label: 'Observability', caption: 'What Tee-Mo did' },
  danger:        { label: 'Workspace',     caption: '' },
};

/* Compact status dot used in nav rails */
function StatusDot({ status }) {
  const cls = {
    ok:      'bg-emerald-500',
    partial: 'bg-amber-500',
    empty:   'bg-slate-300',
    error:   'bg-rose-500',
    neutral: 'bg-slate-300',
  }[status] || 'bg-slate-300';
  return <span className={['inline-block h-1.5 w-1.5 rounded-full shrink-0', cls].join(' ')} />;
}

/* Section frame used inside the right-hand content column. Anchored for scrollspy. */
function ModuleSection({ id, title, caption, children, action }) {
  return (
    <section id={`tm-${id}`} className="scroll-mt-24">
      <header className="flex items-end justify-between gap-4 mb-3">
        <div>
          <h2 className="text-base font-semibold text-slate-900" style={{letterSpacing:'-0.01em'}}>{title}</h2>
          {caption && <p className="text-xs text-slate-500 mt-0.5">{caption}</p>}
        </div>
        {action}
      </header>
      <div className="rounded-lg border border-slate-200 bg-white">
        {children}
      </div>
    </section>
  );
}

/* ----- Per-module bodies (deliberately concise — show shape, not all content) ----- */

function SlackBody() {
  return (
    <div className="p-5 flex items-center justify-between gap-4">
      <div className="flex items-center gap-3 min-w-0">
        <div className="h-10 w-10 rounded-md bg-slate-100 flex items-center justify-center text-slate-600">
          <Icon name="message-square" className="w-5 h-5" />
        </div>
        <div className="min-w-0">
          <div className="text-sm font-medium text-slate-900">Acme Corp</div>
          <div className="text-xs text-slate-500 font-mono truncate">T01ACME · acme.slack.com</div>
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <Badge variant="success">Installed</Badge>
        <Button variant="secondary" size="sm">Reinstall</Button>
      </div>
    </div>
  );
}

function DriveBody() {
  return (
    <div className="p-5 flex items-center justify-between gap-4">
      <div className="flex items-center gap-3 min-w-0">
        <div className="h-10 w-10 rounded-md bg-slate-100 flex items-center justify-center text-slate-600">
          <Icon name="folder-open" className="w-5 h-5" />
        </div>
        <div className="min-w-0">
          <div className="text-sm font-medium text-slate-900">alex@acme.com</div>
          <div className="text-xs text-slate-500">Read-only access · scoped to selected files</div>
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <Button variant="ghost" size="sm">Disconnect</Button>
      </div>
    </div>
  );
}

function KeyBody() {
  const providers = ['google', 'openai', 'anthropic'];
  const [provider, setProvider] = React.useState('openai');
  return (
    <div className="p-5 space-y-4">
      <div className="flex gap-2">
        {providers.map(p => (
          <button key={p} onClick={() => setProvider(p)} className={[
            'h-8 px-3 rounded-md text-xs font-medium border transition-colors capitalize',
            provider === p ? 'bg-brand-50 text-brand-700 border-brand-200' : 'bg-white text-slate-700 border-slate-200 hover:border-slate-300'
          ].join(' ')}>{p}</button>
        ))}
      </div>
      <div className="flex items-center justify-between gap-3">
        <div className="font-mono text-sm text-slate-700 bg-slate-50 border border-slate-200 rounded-md px-3 py-2 flex-1 truncate">
          sk-proj-•••••••••••••••••••••••••••• G7vT
        </div>
        <Button variant="secondary" size="sm">Rotate</Button>
      </div>
      <p className="text-xs text-slate-500">Encrypted with AES-256-GCM. Last validated 2 minutes ago.</p>
    </div>
  );
}

function ChannelsBody({ channels }) {
  return (
    <ul className="divide-y divide-slate-100">
      {channels.map(c => (
        <li key={c.name} className="px-5 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-slate-400"><Icon name="hash" className="w-4 h-4" /></span>
            <span className="text-sm text-slate-900">{c.name}</span>
            {c.bound && <Badge variant="success">Bound</Badge>}
          </div>
          <Button variant={c.bound ? 'ghost' : 'secondary'} size="sm">{c.bound ? 'Unbind' : 'Bind'}</Button>
        </li>
      ))}
    </ul>
  );
}

function FilesBody({ files }) {
  return (
    <>
      <div className="px-5 py-3 flex items-center justify-between border-b border-slate-100">
        <div className="text-xs text-slate-500">{files.length} of 15 files indexed</div>
        <Button size="sm"><Icon name="plus" className="w-4 h-4" /> Add file</Button>
      </div>
      <ul className="divide-y divide-slate-100">
        {files.map(f => (
          <li key={f.id} className="px-5 py-3 flex items-start gap-3 group">
            <span className="mt-0.5 text-slate-400"><Icon name={f.icon || 'file-text'} className="w-4 h-4" /></span>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium text-slate-900 truncate">{f.title}</div>
              <p className="text-xs text-slate-500 mt-0.5 line-clamp-1 italic">{f.description}</p>
            </div>
            <button className="text-xs text-slate-400 hover:text-rose-500 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">Remove</button>
          </li>
        ))}
      </ul>
    </>
  );
}

function PersonaBody() {
  return (
    <div className="p-5 space-y-4">
      <div>
        <label className="text-xs font-medium text-slate-700">Voice</label>
        <div className="mt-1.5 flex gap-2">
          {['Default', 'Concise', 'Warm', 'Formal'].map((v, i) => (
            <button key={v} className={[
              'h-8 px-3 rounded-md text-xs font-medium border transition-colors',
              i === 0 ? 'bg-brand-50 text-brand-700 border-brand-200' : 'bg-white text-slate-700 border-slate-200 hover:border-slate-300'
            ].join(' ')}>{v}</button>
          ))}
        </div>
      </div>
      <div>
        <label className="text-xs font-medium text-slate-700">Custom instructions</label>
        <textarea
          className="mt-1.5 w-full h-20 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:border-brand-500"
          placeholder="Always cite the source file. Default to bullets for lists of >3 items."
        />
      </div>
    </div>
  );
}

function SkillsBody() {
  const skills = [
    { name: 'summarize-thread', source: 'built-in', uses: 142 },
    { name: 'pull-policy',      source: 'built-in', uses: 38  },
    { name: 'standup-recap',    source: 'built-in', uses: 21  },
    { name: 'brief-the-cmo',    source: 'created in Slack', uses: 4 },
  ];
  return (
    <ul className="divide-y divide-slate-100">
      {skills.map(s => (
        <li key={s.name} className="px-5 py-3 flex items-center justify-between gap-3">
          <div className="min-w-0 flex items-center gap-3">
            <span className="text-slate-400"><Icon name="sparkles" className="w-4 h-4" /></span>
            <div className="min-w-0">
              <div className="text-sm font-mono text-slate-900 truncate">/teemo {s.name}</div>
              <div className="text-xs text-slate-500">{s.source} · {s.uses} uses this month</div>
            </div>
          </div>
          <Button variant="ghost" size="sm">Edit</Button>
        </li>
      ))}
    </ul>
  );
}

function AutomationBody() {
  return (
    <div className="p-8 text-center">
      <div className="mx-auto h-10 w-10 rounded-md bg-slate-100 flex items-center justify-center text-slate-500">
        <Icon name="zap" className="w-5 h-5" />
      </div>
      <h3 className="mt-3 text-sm font-semibold text-slate-900">No automations yet</h3>
      <p className="mt-1 text-xs text-slate-500 max-w-sm mx-auto">Trigger Tee-Mo on a schedule, on a Slack event, or from a webhook.</p>
      <div className="mt-3"><Button size="sm" variant="secondary">Create automation</Button></div>
    </div>
  );
}

function AuditBody() {
  const rows = [
    { t: '2m',   who: 'alex@acme.com',  what: 'rotated OpenAI key' },
    { t: '14m',  who: '@kira (Slack)',  what: 'asked /teemo brief-the-cmo' },
    { t: '1h',   who: 'tee-mo',         what: 'indexed Q1 Budget.xlsx' },
    { t: '3h',   who: 'alex@acme.com',  what: 'bound #product' },
  ];
  return (
    <ul className="divide-y divide-slate-100 font-mono text-xs">
      {rows.map((r, i) => (
        <li key={i} className="px-5 py-2.5 grid grid-cols-[40px_180px_1fr] gap-3">
          <span className="text-slate-400">{r.t}</span>
          <span className="text-slate-700 truncate">{r.who}</span>
          <span className="text-slate-900 truncate">{r.what}</span>
        </li>
      ))}
    </ul>
  );
}

function UsageBody() {
  const cells = [
    { label: 'Calls (7d)',     value: '1,420',  delta: '+12%' },
    { label: 'Tokens',         value: '4.1M',   delta: '+8%'  },
    { label: 'Est. spend',     value: '$4.18',  delta: '+$0.30' },
    { label: 'Files indexed',  value: '12 / 15',delta: ''     },
  ];
  return (
    <div className="grid grid-cols-2 md:grid-cols-4">
      {cells.map((c, i) => (
        <div key={c.label} className={[
          'p-5',
          i < cells.length - 1 ? 'border-r border-slate-100' : '',
          i < 2 ? 'md:border-b-0 border-b border-slate-100' : '',
        ].join(' ')}>
          <div className="text-xs text-slate-500">{c.label}</div>
          <div className="mt-1 text-xl font-semibold text-slate-900" style={{letterSpacing:'-0.01em'}}>{c.value}</div>
          {c.delta && <div className="text-xs text-emerald-600 mt-0.5">{c.delta}</div>}
        </div>
      ))}
    </div>
  );
}

function DangerBody() {
  return (
    <div className="p-5 flex items-center justify-between gap-4">
      <div>
        <div className="text-sm font-medium text-slate-900">Delete workspace</div>
        <div className="text-xs text-slate-500">Removes the bot, the key, and all indexed file metadata. Cannot be undone.</div>
      </div>
      <Button variant="danger" size="sm">Delete</Button>
    </div>
  );
}

function ModuleBody({ id, files, channels }) {
  switch (id) {
    case 'slack':      return <SlackBody />;
    case 'drive':      return <DriveBody />;
    case 'key':        return <KeyBody />;
    case 'channels':   return <ChannelsBody channels={channels} />;
    case 'files':      return <FilesBody files={files} />;
    case 'persona':    return <PersonaBody />;
    case 'skills':     return <SkillsBody />;
    case 'automation': return <AutomationBody />;
    case 'audit':      return <AuditBody />;
    case 'usage':      return <UsageBody />;
    case 'danger':     return <DangerBody />;
    default:           return null;
  }
}

Object.assign(window, { TM_MODULES, TM_GROUPS, StatusDot, ModuleSection, ModuleBody });
