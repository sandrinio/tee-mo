# Universal Discovery Protocol

After running the archetype playbook from `exploration-strategies.md`, apply these four discovery layers to find **behaviors** — not just files. The archetype playbook tells you WHERE to look. This protocol tells you WHAT to look for.

Run all four layers regardless of archetype. Each layer produces signals that feed the documentation plan.

---

## Layer 1 — Capability Surface

**Goal:** Map everything a user/consumer can DO.

The capability surface is the complete set of entry points into your system. Every entry point = a potential doc.

| Project Type | Capability Source | How to Find |
|-------------|------------------|-------------|
| SPA / Mobile | Route definitions | Glob: `**/routes*`, `**/router*`, `**/app/**/page.*`, `**/screens/**` |
| Web API | Endpoint definitions | Glob: `**/routes/**`, `**/controllers/**`; Grep: `@Get\|@Post\|app.get\|router.` |
| CLI | Command definitions | Glob: `**/commands/**`, `**/cmd/**`; Grep: `.command(\|.subcommand\|Subcommand` |
| Library/SDK | Public exports | Read main entry point (`index.*`), check `exports` in package config |
| Pipeline | DAG/flow definitions | Glob: `**/dags/**`, `**/pipelines/**`, `**/flows/**`, `**/workflows/**` |
| Event-driven | Event handlers | Grep: `on\(\|addEventListener\|@EventHandler\|subscribe\|consumer` |

### SPA-Specific: Route Tree = Feature Map

For SPAs (React, Angular, Vue, Svelte), the route tree IS the documentation outline:

1. **Extract the full route tree** — read router config, `app/` directory structure, or navigation definitions
2. **Classify each route:**
   - **Core domain** — the primary value (e.g., `/projects/:id`, `/dashboard`)
   - **Auth** — login, register, forgot password, OAuth callbacks
   - **Settings/Admin** — configuration, user management
   - **Utility** — 404, error pages, maintenance
3. **For each core domain route, identify:**
   - What data it displays (state selectors, API calls, props)
   - What actions the user can take (buttons, forms, modals)
   - What happens after each action (navigation, API mutation, toast)

**Framework-specific best signals:**

| Framework | Best Feature Signal | Pattern to Grep |
|-----------|-------------------|-----------------|
| React | Custom hooks | `export function use[A-Z]` or `export const use[A-Z]` |
| Angular | Feature modules + services | `@NgModule\|@Injectable` |
| Vue 3 | Composables | `export function use[A-Z]` in `composables/` |
| Svelte | Stores + loaders | `writable\|readable\|derived` or `+page.ts` `load` functions |
| Solid | Signals + resources | `createSignal\|createResource` |

Each custom hook/composable/service that encapsulates a reusable behavior = one documentable feature.

### API-Specific: Endpoint Map

1. **Check for API specs first** — OpenAPI/Swagger (`swagger.json`, `openapi.yaml`), GraphQL schemas (`schema.graphql`, `*.gql`), protobuf definitions (`*.proto`), tRPC routers. These are free structured input — parse them instead of re-discovering.
2. **Group endpoints by resource** — `/users/*`, `/projects/*`, `/billing/*` — each group is a feature.
3. **Trace middleware chains** — what runs before each endpoint? (auth, validation, rate limiting, logging)

---

## Layer 2 — Data Flows

**Goal:** For each capability, trace how data moves from source to screen (or from input to storage).

### Discovery questions per feature:
1. **Where does the data come from?** (API call, local state, URL params, localStorage, real-time subscription)
2. **How is it transformed?** (selectors, computed values, mappers, formatters)
3. **Where is it displayed?** (which components/views consume it)
4. **How does the user modify it?** (forms, inline edits, drag-drop, toggles)
5. **Where does the mutation go?** (API endpoint, store dispatch, optimistic update)
6. **What's the loading/error/empty state?** (skeleton, spinner, error boundary, empty state message)

### Patterns to discover:

| Pattern | Grep Signal | What It Reveals |
|---------|------------|-----------------|
| API client calls | `fetch\|axios\|httpClient\|trpc\|useSWR\|useQuery\|graphql` | Backend dependencies per feature |
| State management | `useSelector\|useStore\|mapState\|inject\|useContext\|getState` | Shared state between features |
| Form handling | `useForm\|FormGroup\|Formik\|react-hook-form\|zod\|yup\|validate` | User input flows + validation rules |
| Caching | `cache\|staleTime\|revalidate\|TTL\|memo\|persist` | Data freshness strategy |
| Optimistic updates | `optimistic\|rollback\|onMutate\|pending` | UX patterns for mutations |

### SPA data flow trace template:
```
Feature: [name]
  User action → Component → Hook/Service → API call → Backend endpoint
  Response → Transform → State update → Re-render → User sees [result]
  Error → Error handler → User sees [error state]
```

---

## Layer 3 — Shared Behaviors

**Goal:** Find cross-cutting concerns that affect multiple features.

These don't belong to any single feature — they're system-wide patterns that deserve their own docs or dedicated sections.

### Must-find behaviors:

| Behavior | Where to Look | Grep Patterns |
|----------|--------------|---------------|
| **Authentication** | Middleware, guards, interceptors, context providers | `auth\|token\|session\|jwt\|oauth\|login\|guard\|protect\|interceptor` |
| **Authorization** | Route guards, role checks, permission gates | `role\|permission\|can\|ability\|policy\|rbac\|acl\|isAdmin\|gate` |
| **Error handling** | Error boundaries, global handlers, interceptors | `ErrorBoundary\|catch\|onError\|handleError\|errorHandler\|fallback\|retry` |
| **Notifications** | Toast systems, push notifications, in-app alerts | `toast\|notify\|alert\|snackbar\|notification\|push\|banner` |
| **Real-time** | WebSocket, SSE, polling, subscriptions | `WebSocket\|socket\|SSE\|EventSource\|subscribe\|polling\|realtime\|live` |
| **Theming/i18n** | Theme providers, translation files, locale configs | `theme\|dark\|light\|i18n\|locale\|translate\|intl\|t\(` |
| **Analytics** | Tracking calls, event logging | `track\|analytics\|gtag\|mixpanel\|segment\|posthog\|amplitude` |
| **Feature flags** | Flag checks, A/B tests, experimental UI | `feature.*flag\|experiment\|variant\|canary\|flipper\|unleash\|launchDarkly` |

### Discovery process:
1. Grep for each behavior's patterns across the codebase
2. If found, read the implementation to understand scope
3. In the exploration log, note which features are affected
4. In the plan, decide: standalone doc vs dedicated section in each affected feature doc

---

## Layer 4 — Integration Boundary

**Goal:** Find every point where the system touches the outside world.

### Outgoing integrations (your app calls external services):

| Pattern | How to Find |
|---------|------------|
| HTTP clients | Grep: `fetch\|axios\|got\|httpClient\|request\|urllib` — read the base URL and endpoint |
| SDK imports | Grep: `import.*from ['"]@?(?:aws-sdk\|stripe\|twilio\|sendgrid\|firebase\|supabase)` |
| Database connections | Grep: `createClient\|createPool\|mongoose.connect\|PrismaClient\|createConnection` |
| Cache connections | Grep: `redis\|memcache\|createClient.*cache` |
| Queue producers | Grep: `publish\|sendMessage\|enqueue\|dispatch.*queue\|produce` |

### Incoming integrations (external services call your app):

| Pattern | How to Find |
|---------|------------|
| Webhook handlers | Grep: `webhook\|/hook\|/callback` in route definitions |
| OAuth callbacks | Grep: `callback\|/auth/.*callback\|redirect_uri` |
| Queue consumers | Grep: `consume\|subscribe\|onMessage\|process.*queue\|worker` |
| Cron / scheduled tasks | Grep: `cron\|schedule\|@Cron\|setInterval.*60\|recurring`; Glob: `**/cron/**`, `**/jobs/**`, `**/tasks/**`, `**/workers/**` |

### Hidden work (no user present):

This is the most underdocumented layer in any project. Actively hunt for:

1. **Background jobs** — Glob: `**/jobs/**`, `**/workers/**`, `**/queues/**`, `**/tasks/**`
2. **Scheduled tasks** — Grep: `cron\|schedule\|@Scheduled\|setInterval`; check CI/CD configs for scheduled workflows
3. **Event handlers** — Grep: `on\(\|emit\(\|EventEmitter\|addEventListener\|subscribe`; check for pub/sub patterns
4. **Database triggers** — Read migration files for trigger definitions
5. **Cleanup / maintenance** — Grep: `cleanup\|purge\|archive\|expire\|gc\|garbage`

### Environment as documentation:

Read `.env.example`, `.env.sample`, or environment config files. Each env var is a configuration surface:
- `DATABASE_URL` → database dependency
- `STRIPE_SECRET_KEY` → payment integration
- `REDIS_URL` → caching layer
- `WEBHOOK_SECRET` → incoming integration

Group env vars by feature — they reveal the integration map without reading any code.

---

## How to Use This Protocol

### During Init (Step 1 — Explore):

After the archetype playbook:
1. Run Layer 1 to build the capability map
2. For each capability, run Layer 2 to trace data flows
3. Run Layer 3 once for the whole project to find shared behaviors
4. Run Layer 4 once to map the integration boundary

### During Audit:

Layers 1 and 4 are the best sources for coverage gaps:
- New routes/endpoints = new capabilities not yet documented
- New env vars with external URLs = new integrations not yet documented
- New cron/job files = new background work not yet documented

### In the Exploration Log:

Add a section per layer:

```markdown
## Capability Surface
| Entry Point | Type | Proposed Doc |
|-------------|------|-------------|
| /api/auth/* | Auth routes (5 endpoints) | AUTHENTICATION_DOC.md |
| /dashboard | Page + 3 sub-routes | DASHBOARD_DOC.md |

## Data Flows
| Feature | State Source | API Calls | Mutations |
|---------|-------------|-----------|-----------|
| Dashboard | useDashboardStore | GET /api/stats, GET /api/projects | None (read-only) |
| Project Editor | useProjectStore | GET /api/projects/:id | PUT /api/projects/:id, POST /api/tasks |

## Shared Behaviors
| Behavior | Scope | Implementation |
|----------|-------|----------------|
| Auth | All /app/* routes | NextAuth middleware + useSession hook |
| Error handling | Global | ErrorBoundary + toast on API errors |
| Feature flags | 3 features | LaunchDarkly SDK, checked in useFeatureFlag hook |

## Integration Boundary
| Direction | System | Purpose | Env Var |
|-----------|--------|---------|---------|
| Outgoing | Stripe API | Payments | STRIPE_SECRET_KEY |
| Outgoing | SendGrid | Emails | SENDGRID_API_KEY |
| Incoming | Stripe webhooks | Payment events | /api/webhooks/stripe |
| Background | Cron: cleanup-sessions | Expire old sessions | runs daily via Vercel Cron |
```
