# Coolify Setup Runbook — Tee-Mo on `teemo.soula.ge`

**Story:** STORY-003-02-coolify-wiring  
**Sprint:** S-03  
**Last updated:** 2026-04-11  
**ADR refs:** ADR-019 (deploy target), ADR-026 (deploy pulled forward)

---

## Preamble

### What this runbook does
Walks you through creating and configuring the Tee-Mo service in Coolify so that every future push to `origin/main` automatically builds the Docker image, deploys the container, and exposes `https://teemo.soula.ge` with a valid Let's Encrypt certificate.

### Who runs it
You — the solo developer — in the Coolify web UI. This runbook is not executable by an AI agent; it describes UI clicks and field values you paste.

### When to run it
Run Steps 1–5 now, in parallel with other S-03 stories. The first **successful** deploy fires automatically at sprint close when `sprint/S-03` merges to `main` (STORY-003-06). Until then, Coolify will attempt to deploy from `main` and fail because `main` has no Dockerfile yet. That failure is expected and harmless — see Step 5 for detail.

### What this runbook does NOT do
- It does not trigger a successful deploy today (that's STORY-003-06 at sprint close).
- It does not configure monitoring, alerting, or log aggregation.
- It does not set up CI/CD test-before-deploy (Coolify auto-deploy on push IS the pipeline).
- It does not handle multi-region or staging environments.

### Prerequisites (verify before Step 1)

| Prerequisite | Expected state |
|---|---|
| DNS | `teemo.soula.ge` A-record points at the Coolify VPS IP (user confirmed 2026-04-12) |
| GitHub repo | `github.com/sandrinio/tee-mo` is **public** — Coolify pulls without auth tokens |
| Coolify access | You have admin access to the Coolify instance |
| Coolify GitHub integration | GitHub app installed in Coolify → Settings → Source Control → GitHub (verify green status) |
| Local `.env` | Repo-root `.env` on your machine with valid `SUPABASE_*` + `GOOGLE_API_*` values |
| Slack credentials | Not required yet — leave `SLACK_*` env vars empty; EPIC-005 Phase A (S-04) populates them |

---

## Step 1 — Create the Coolify service from GitHub

1. Open your Coolify instance in a browser and log in as admin.
2. In the left sidebar, click **Projects** → select your project (or create one named `tee-mo-prod`).
3. Click **+ New Resource**.
4. Choose **Application**.
5. Under "Source", select **GitHub** (GitHub App integration).
6. Select the repository `sandrinio/tee-mo`.
7. **Branch selection** — choose based on your preference:
   - **Option A (recommended, default):** select `main`. First successful deploy happens at sprint close (STORY-003-06). Current deploy attempts will fail with "no Dockerfile" — this is expected and documented in Step 5.
   - **Option B (optional preview):** select `sprint/S-03`. First successful deploy fires now. You switch back to `main` at sprint close. See Step 5b for full details.
8. Under **Build Pack**, select **Dockerfile**.
9. Set these build configuration fields:

   | Field | Value |
   |---|---|
   | Dockerfile location | `Dockerfile` |
   | Base directory | `/` |
   | Publish directory | *(leave blank)* |
   | Docker build target | *(leave blank — uses the default `runtime` stage)* |
   | Port | `8000` |

10. Click **Save** (or **Continue** depending on your Coolify version).

---

## Step 2 — Configure environment variables

1. In the Coolify service settings, navigate to the **Environment Variables** tab.
2. Add the following variables one by one (or use the bulk-paste field if your Coolify version supports it). Copy values from your local `.env` file where indicated.

```
SUPABASE_URL=https://sulabase.soula.ge
SUPABASE_ANON_KEY=<copy from local .env>
SUPABASE_SERVICE_ROLE_KEY=<copy from local .env>
SUPABASE_JWT_SECRET=<copy from local .env>
DEBUG=false
CORS_ORIGINS=https://teemo.soula.ge
GOOGLE_API_CLIENT_ID=<copy from local .env>
GOOGLE_API_SECRET=<copy from local .env>
SLACK_CLIENT_ID=
SLACK_CLIENT_SECRET=
SLACK_SIGNING_SECRET=
```

### Critical differences from your local `.env`

| Variable | Local value | Production value | Why |
|---|---|---|---|
| `DEBUG` | `true` | **`false`** | `DEBUG=true` enables dev-only FastAPI docs and disables `Secure` flag on cookies. NEVER true in prod. |
| `CORS_ORIGINS` | `http://localhost:5173` | **`https://teemo.soula.ge`** | CORS allowed-origins must match the production domain. Wrong value causes all browser API calls to fail with CORS error. |

### Notes on blank Slack variables
`SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, and `SLACK_SIGNING_SECRET` are left empty intentionally. S-03 code does not consume them. You will populate them after completing the Slack app setup guide (Steps 1–3 of EPIC-005 Phase A, Sprint S-04). Empty strings are safe — the Slack Bolt app scaffold handles missing credentials gracefully at startup.

### Security note
Coolify stores env vars encrypted in its own database. They are injected into the container at runtime via Docker environment. They are **never** written to the image — the `.dockerignore` in the repo root excludes `.env` at build time.

---

## Step 3 — Bind the domain

1. In the Coolify service settings, navigate to the **Domains** tab.
2. Click **+ Add Domain**.
3. Enter: `https://teemo.soula.ge`
4. Click **Save**.

Coolify's built-in Traefik reverse proxy:
- Automatically provisions a Let's Encrypt TLS certificate for `teemo.soula.ge` on first deploy.
- Renews the certificate automatically before expiry.
- Routes HTTPS traffic on port 443 → container port 8000.

**No additional Traefik config is needed.** Coolify handles it.

### What to expect after cert provisioning
- First time: cert provisioning takes 30–90 seconds after the container starts. During this window you may see a browser TLS warning — this is normal; wait and refresh.
- If the cert fails to provision after 3 minutes: verify DNS resolves correctly (`dig teemo.soula.ge` should return the Coolify VPS IP). Let's Encrypt requires DNS to resolve before it can issue a cert.

---

## Step 4 — Configure the healthcheck

1. In the Coolify service settings, navigate to the **Healthchecks** tab.
2. Set:

   | Field | Value |
   |---|---|
   | Protocol | HTTP |
   | Path | `/api/health` |
   | Port | `8000` |
   | Method | GET |
   | Expected status | `200` |
   | Interval | `30` seconds |
   | Timeout | `10` seconds |
   | Retries | `3` |
   | Start period | `60` seconds |

3. Click **Save**.

The **start period** of 60 seconds gives the FastAPI + Uvicorn process time to complete cold-start initialization (especially on first deploy when Python dependencies are warm-loaded). Without this buffer, Coolify may mark the container unhealthy and kill it before it has finished starting.

The `/api/health` endpoint returns:
```json
{
  "status": "ok",
  "service": "tee-mo",
  "database": {
    "teemo_users": "ok",
    "teemo_workspaces": "ok",
    "teemo_knowledge_index": "ok",
    "teemo_skills": "ok"
  }
}
```
After S-03 migrations land (STORY-003-03), the database object will include 2 additional tables. The healthcheck pass/fail logic keys off HTTP 200 — it does not inspect the JSON body.

---

## Step 5 — First deploy attempt (Option A — watch `main`, default)

**If you selected `main` as the branch in Step 1, read this section.**

### Current state
`main` does not have the Dockerfile yet. Coolify will automatically attempt a deploy when it detects a push to `main` (or when you click **Deploy** manually). That deploy will fail with a build error like:

```
ERROR [internal] load metadata for docker.io/library/node:22-alpine
  ... or ...
No Dockerfile found at /Dockerfile
```

**This is expected and not a bug.** The Dockerfile lives on `sprint/S-03`, which merges to `main` at sprint close.

### What to do
1. Let Coolify attempt and fail. Do not try to fix it.
2. Note the failure in the Coolify logs (the build log will confirm the missing Dockerfile).
3. Report back to the Team Lead: "Coolify service configured; I chose Option A (watching main); current deploy state: failed as expected (no Dockerfile on main yet)."

### When the first successful deploy fires
At sprint close, STORY-003-06 merges `sprint/S-03` → `main` and pushes to `origin/main`. Coolify detects the push, builds the Dockerfile, deploys the container, and the healthcheck at `https://teemo.soula.ge/api/health` becomes reachable for the first time. STORY-003-06 does the full curl-based verification.

---

## Step 5b — (Optional) Option B: mid-sprint preview from `sprint/S-03`

**Only follow this section if you want to verify the full deploy chain now, mid-sprint, without waiting for sprint close.**

### What Option B gives you
- Confirms the Dockerfile builds successfully in Coolify's environment.
- Confirms `https://teemo.soula.ge/api/health` returns 200 against the self-hosted Supabase.
- Confirms TLS cert provisioning works end-to-end.
- Higher confidence before sprint close — at the cost of a manual branch-switch step later.

### How to switch to `sprint/S-03`

If you selected `main` in Step 1 and now want to switch:
1. In Coolify service settings → **General** tab.
2. Find the **Branch** field.
3. Change from `main` to `sprint/S-03`.
4. Click **Save**.

If you selected `sprint/S-03` in Step 1, you're already here.

### Trigger the deploy
1. In Coolify, click the **Deploy** button (or **Redeploy** if a prior attempt ran).
2. Monitor the build log — the multi-stage Docker build takes 2–5 minutes on first run.
3. When the build completes, Coolify starts the container. The healthcheck (60s start period) fires after the container is up.

### Verify (run these from your terminal after Coolify shows "Running")

```bash
# Health endpoint — should return 200 + 4-table JSON
curl -s https://teemo.soula.ge/api/health | python3 -m json.tool

# Frontend — should return HTML
curl -sI https://teemo.soula.ge/ | grep -E 'HTTP|content-type'

# SPA fallback — should return same HTML as /
curl -sI https://teemo.soula.ge/login | grep -E 'HTTP|content-type'

# TLS certificate verification
curl -vI https://teemo.soula.ge/ 2>&1 | grep -E 'SSL certificate verify|subject:|issuer:'
```

Expected outputs:
- `curl /api/health` → JSON with `"status": "ok"` and 4 `teemo_*` keys all `"ok"`
- `curl -sI /` → `HTTP/2 200` + `content-type: text/html`
- `curl -sI /login` → `HTTP/2 200` + `content-type: text/html`
- TLS grep → `SSL certificate verify ok`

### CRITICAL — switch back to `main` at sprint close
`sprint/S-03` is deleted when STORY-003-06 closes (sprint close). If Coolify is still watching `sprint/S-03` after the branch is deleted, it will break and stop auto-deploying on pushes to `main`.

**At sprint close, before or immediately after STORY-003-06 runs:**
1. Coolify service settings → **General** tab.
2. Change **Branch** from `sprint/S-03` to `main`.
3. Click **Save**.
4. Coolify will fire a deploy from `main` (which now has the Dockerfile). Let it succeed — this is the STORY-003-06 deploy.

---

## Step 6 — Troubleshooting

### Build fails: "no Dockerfile found"
- **Cause:** You're watching `main` and the Dockerfile hasn't merged yet. Expected.
- **Fix:** Wait for sprint close, or switch to `sprint/S-03` temporarily (Option B above).

### Build fails at the Node stage: "npm ci" errors or package-lock mismatch
- **Cause:** Coolify cached a stale layer and the package-lock.json changed.
- **Fix:** In Coolify, click **Redeploy** → enable "Clear build cache" checkbox → Redeploy.

### Build fails at the Python stage: "gcc not found" or C compiler errors
- **Cause:** Unlikely — the Dockerfile already installs `build-essential`. If this occurs, the apt-get layer may have a mirror issue.
- **Fix:** Retrigger the build. If it fails twice in a row, raise it to the Team Lead.

### Container starts but browser gets 502 Bad Gateway
- **Cause:** Traefik can't reach port 8000 — usually a port mismatch in Coolify config.
- **Fix:** Verify the Coolify service **Port** field is `8000` (Step 1). If it says `3000` or `80`, correct it and redeploy.

### Healthcheck fails: container marked unhealthy immediately
- **Cause:** Container starts but FastAPI hasn't finished loading (cold-start). Coolify's default start period may be 0.
- **Fix:** Verify the **Start period** in the Healthchecks tab is `60` seconds (Step 4). Increase to `90` if cold-starts are consistently slow.

### TLS certificate not provisioning (browser shows "not secure" warning)
- **Cause:** Coolify's Traefik can't complete the Let's Encrypt ACME challenge. This requires DNS to be live and pointing at the VPS.
- **Fix:**
  1. Confirm DNS is resolving: `dig teemo.soula.ge` should return the Coolify VPS IP.
  2. Wait 2–3 minutes after DNS propagates.
  3. Retrigger a deploy — Traefik reattempts cert provisioning on each new deploy.
  4. Check Coolify's Traefik logs (Settings → Traefik → View logs) for ACME errors.

### `/api/health` returns 200 but `status: "degraded"`
- **Cause:** One or more `teemo_*` tables are unreachable (Supabase connectivity issue or wrong key).
- **Fix:**
  1. Check the JSON body — the degraded table will show an error string instead of `"ok"`.
  2. Verify `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in the Coolify env vars match your local `.env` exactly (no trailing spaces, correct URL scheme).
  3. Confirm `https://sulabase.soula.ge` is reachable from the Coolify VPS: you can test this from a browser or with `curl https://sulabase.soula.ge/rest/v1/ -H "apikey: <anon_key>"`.

### CORS error in browser (fetch from `teemo.soula.ge` to `/api/*` fails)
- **Cause:** `CORS_ORIGINS` env var is missing or set to the wrong value in Coolify.
- **Fix:** Verify `CORS_ORIGINS=https://teemo.soula.ge` in the Coolify env vars (Step 2). Note: same-origin requests (browser on `teemo.soula.ge` fetching `/api/*` on the same domain) do NOT go through CORS — if you're seeing a CORS error on same-origin, the issue is in the URL construction, not the CORS config.

---

## Step 7 — Rollback procedure

Coolify auto-deploys every push to the watched branch. To roll back a bad deploy:

### Option A — push a revert commit (preferred)

```bash
# From your local machine
git log --oneline origin/main | head -5   # find the bad commit SHA
git revert <bad-commit-sha>               # creates a new revert commit
git push origin main                      # Coolify detects the push and auto-deploys the revert
```

Coolify picks up the push within ~60 seconds and begins a new build from the reverted state.

### Option B — use Coolify's "Deploy previous" button (if available)

1. In Coolify service → **Deployments** tab.
2. Find the last known-good deploy in the list.
3. Click the **Redeploy** (or **Deploy this version**) button on that row.
4. Coolify pulls that commit's image layer (if cached) or rebuilds it.

### Option C — emergency stop (if both A and B fail)

1. In Coolify service → click **Stop**.
2. This takes the container down. `teemo.soula.ge` will return 502 until you redeploy.
3. Fix the underlying issue in a new commit and push to `main` to resume.

---

## Change Log

| Date | Author | Change |
|---|---|---|
| 2026-04-11 | DevOps agent (STORY-003-02) | Initial runbook created |
