---
guide_id: "slack-app-setup"
status: "Waiting on user — app not yet created in api.slack.com"
owner: "Solo dev"
parent_epic: "EPIC-005"
purpose: "Step-by-step runbook for creating the Tee-Mo Slack app in api.slack.com. Runs in parallel with S-03 (deploy + schema). Must be complete BEFORE S-04 can start building OAuth install."
blocker: "Slack's app creation flow verifies the Request URL for Event Subscriptions by POSTing a challenge — requires https://teemo.soula.ge/api/slack/events to return 200 with the challenge body. S-03 lands a minimal verification endpoint for this."
---

# Slack App Setup — api.slack.com

> **When to follow this guide:** Start Step 1 at the beginning of S-03. Steps 1–4 can be done immediately. **Steps 5–7 must wait until S-03 has deployed the minimal `/api/slack/events` verification endpoint to `https://teemo.soula.ge`** — because Slack will POST a challenge to that URL and won't let you save the Event Subscriptions config until it succeeds.

---

## What you're creating

A Slack app that Tee-Mo users will later install into their Slack workspaces via OAuth. This is the **developer-side registration** — you create the app definition once, and end users install it many times into their own workspaces.

You'll end up with:
- A **Client ID** + **Client Secret** (OAuth credentials — stored in Coolify env vars)
- A **Signing Secret** (for verifying Slack request signatures — Coolify env vars)
- A **Bot User OAuth Token** (just for your personal dev workspace — you won't use this directly, but it proves install works)

---

## Step 1 — Create the app from a manifest

1. Go to **https://api.slack.com/apps** (log in with the Slack account you want to own the app — can be any Slack account).
2. Click **Create New App**.
3. Choose **From an app manifest** (NOT "from scratch" — the manifest is declarative and ensures the scopes + events are set correctly on the first try).
4. Pick a workspace to install into. Use any Slack workspace where you have admin rights. A personal throwaway workspace is fine — this is just for dev testing. Tee-Mo can later be installed into other workspaces via the OAuth flow.
5. Select **YAML** as the manifest format.
6. Paste the manifest below (see Step 2).
7. Click **Next** → review → **Create**.

---

## Step 2 — App manifest (paste this verbatim)

```yaml
display_information:
  name: Tee-Mo
  description: Context-aware AI assistant for Slack, powered by your own API key. Answers questions using thread history and curated Google Drive knowledge.
  background_color: "#F43F5E"
  long_description: Tee-Mo is a BYOK (Bring Your Own Key) AI assistant that lives in Slack. It reads your Google Drive files in real time and answers @mentions in-thread. No vector database, no data indexing, no usage billing. Each workspace provides its own OpenAI, Anthropic, or Google API key. Users teach Tee-Mo custom skills through conversation.
features:
  bot_user:
    display_name: Tee-Mo
    always_online: true
  app_home:
    home_tab_enabled: false
    messages_tab_enabled: false
    messages_tab_read_only_enabled: false
oauth_config:
  redirect_urls:
    - https://teemo.soula.ge/api/slack/oauth/callback
  scopes:
    bot:
      - app_mentions:read
      - channels:history
      - channels:read
      - chat:write
      - groups:history
      - groups:read
      - im:history
settings:
  event_subscriptions:
    request_url: https://teemo.soula.ge/api/slack/events
    bot_events:
      - app_mention
      - message.im
  interactivity:
    is_enabled: false
  org_deploy_enabled: false
  socket_mode_enabled: false
  token_rotation_enabled: false
```

**Why these choices:**

- **`display_information.name: Tee-Mo`** + **`background_color: "#F43F5E"`** — coral brand per ADR-022 Design Guide §2.
- **`features.bot_user.display_name: Tee-Mo`** — what users see when they @mention the bot in Slack.
- **`app_home: all false`** — Charter §1.2: "does not expose a skills management UI on the dashboard". No app home means Slack doesn't show a "Home" tab when users click the bot avatar. Skills are chat-only per ADR-023.
- **`oauth_config.redirect_urls`**: only `https://teemo.soula.ge/api/slack/oauth/callback`. This is where Slack redirects the user after they approve installation. The backend endpoint lives in `backend/app/api/routes/slack_oauth.py` (built in S-04).
- **`oauth_config.scopes.bot`**: exactly the 7 scopes matching Roadmap ADR-021 + ADR-025:
  - `app_mentions:read` — receive `app_mention` events
  - `channels:history` — read history of public channels the bot is in (for thread context)
  - `groups:history` — same for private channels
  - `im:history` — read DM history (for thread context in DMs)
  - `chat:write` — post messages (replies)
  - `channels:read` — list public channels (for the dashboard channel picker in EPIC-005 Phase B)
  - `groups:read` — list private channels the bot is in
- **`event_subscriptions.request_url`** — Slack's server will POST events to this URL. Must be HTTPS. Slack verifies this URL is reachable by POSTing a `url_verification` challenge at app-creation time — the backend must respond with the `challenge` value. S-03 lands a minimal endpoint for this.
- **`event_subscriptions.bot_events: [app_mention, message.im]`** — matches ADR-021 exactly. No `message.channels` (avoids running AI on every message).
- **`interactivity: false`** — Tee-Mo v1 doesn't use interactive components (buttons, modals in Slack). All interaction is conversational.
- **`socket_mode: false`** — HTTP mode, not Socket Mode, because we have public HTTPS via Coolify. Socket Mode is for local dev without public URLs. We don't need it.
- **`token_rotation: false`** — keeps the OAuth flow simple. Tokens don't expire unless explicitly revoked by the installer.

---

## Step 3 — Capture the credentials

After the app is created, Slack takes you to the app's settings page. You need three values:

1. **Basic Information** tab → **App Credentials** section:
   - **Client ID** — copy this. Goes in `.env` as `SLACK_CLIENT_ID`.
   - **Client Secret** — click **Show** → copy this. Goes in `.env` as `SLACK_CLIENT_SECRET`.
   - **Signing Secret** — click **Show** → copy this. Goes in `.env` as `SLACK_SIGNING_SECRET`. The backend uses this to verify that incoming webhook POSTs are actually from Slack and not forged.

2. Do NOT copy the **Verification Token** (legacy, deprecated — we use the signing secret instead).
3. Do NOT copy any **App-Level Token** — we're not using Socket Mode.

**Add to `.env`** (at the project root, alongside your existing `SUPABASE_*` and `GOOGLE_API_*` entries):

```
# Slack app credentials (S-04 EPIC-005 Phase A will consume these)
SLACK_CLIENT_ID=<value from Basic Information>
SLACK_CLIENT_SECRET=<value from Basic Information>
SLACK_SIGNING_SECRET=<value from Basic Information>
```

**Do NOT commit `.env`** — it's already gitignored.

---

## Step 4 — (PAUSE) Wait for S-03 to deploy the verification endpoint

At this point Slack has your app, but the **Event Subscriptions** section is probably showing a red error: *"Your URL didn't respond with the value of the `challenge` parameter."* That's expected — we haven't deployed the backend endpoint yet.

**Stop here** and let S-03 finish. S-03 ships:

1. The Dockerfile + Coolify deploy pipeline
2. A minimal `/api/slack/events` endpoint in FastAPI that handles ONLY the `url_verification` POST and returns the `challenge` value

Once S-03 is merged and `https://teemo.soula.ge/api/slack/events` is live, come back here for Step 5.

---

## Step 5 — Verify the Events Request URL

1. Go back to the app settings → **Event Subscriptions** tab.
2. The **Request URL** should already be set to `https://teemo.soula.ge/api/slack/events` (from the manifest).
3. Click **Retry** next to the URL field, or re-save the URL by toggling the **Enable Events** switch off and back on.
4. Slack POSTs a fresh challenge. The backend responds with the challenge value.
5. Slack shows **✅ Verified** next to the URL.

If it fails:
- Open a browser tab to `https://teemo.soula.ge/api/health` — it should return `{"status": "ok", ...}`. If not, deploy is broken — fix that before re-trying.
- Check Coolify logs for the backend service — look for an incoming POST to `/api/slack/events` with a `url_verification` body.
- The backend endpoint must respond within 3 seconds. Coolify cold-start latency on a small VPS might hit that. If so, warm up the backend by hitting `/api/health` once, then immediately retry verification.

---

## Step 6 — Install the app to your dev workspace

1. App settings → **Install App** tab (may be labeled "Install your app" if not installed yet).
2. Click **Install to Workspace**.
3. Slack shows a consent screen listing the 7 scopes. Click **Allow**.
4. Slack redirects to `https://teemo.soula.ge/api/slack/oauth/callback?code=...&state=...`.
5. **At this point EPIC-005 Phase A (S-04) hasn't landed yet**, so the callback URL will return 404. That's expected. You've still installed the app — Slack has recorded the install. You just can't see the confirmation UI because the backend handler doesn't exist yet.
6. In the app settings → **Install App** tab → you'll now see a **Bot User OAuth Token** starting with `xoxb-`. You don't need to copy this — it's only for your personal dev workspace. When EPIC-005 Phase A ships, the real OAuth flow will generate fresh tokens for each install and store them encrypted in `teemo_slack_teams.encrypted_slack_bot_token`.

---

## Step 7 — (Optional but recommended) Invite the bot to a test channel

This step verifies Slack event delivery works end-to-end once EPIC-005 Phase B lands:

1. In your Slack workspace, go to a channel you control (create one like `#tee-mo-test` if you want).
2. Type `/invite @Tee-Mo` to add the bot.
3. The bot will appear in the channel member list.
4. When EPIC-005 Phase B ships, @mentioning the bot in this channel will POST an `app_mention` event to `https://teemo.soula.ge/api/slack/events`, which will then resolve the channel binding and call the agent.

---

## Environment variables to add to Coolify (before S-04 deploys)

Once Steps 1–6 are done and you have the three credentials, add them as Coolify env vars on the Tee-Mo service:

| Env var | Source |
|---|---|
| `SLACK_CLIENT_ID` | Basic Information → App Credentials |
| `SLACK_CLIENT_SECRET` | Basic Information → App Credentials |
| `SLACK_SIGNING_SECRET` | Basic Information → App Credentials |

Do NOT add the `xoxb-` bot token to Coolify — that's a per-install artifact and EPIC-005 Phase A generates fresh ones encrypted per-team.

---

## Common gotchas

- **"Your URL didn't respond with the value of the challenge parameter"** — backend endpoint isn't responding correctly. The handler must return `200` with the request body's `challenge` field as the response body (or as JSON `{"challenge": "..."}` — Slack accepts both). S-03's minimal endpoint handles this.
- **"Invalid redirect_uri"** during install — the redirect URL you registered in the manifest (`https://teemo.soula.ge/api/slack/oauth/callback`) must match EXACTLY what the backend sends in the OAuth start URL. Trailing slash matters. HTTPS matters.
- **"not_authed" errors after install** — you're trying to call Slack APIs without a valid bot token in the `Authorization: Bearer xoxb-...` header. EPIC-005 handles this once Phase A is in.
- **Scope mismatch** — if the manifest and the backend disagree on scopes (e.g., backend expects `reactions:read` and the manifest doesn't declare it), re-install is required. Change the manifest, update the app, then re-install from a fresh workspace.

---

## Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-04-12 | Guide created. User confirmed no Slack app exists yet and asked for guidance. Guide gated on S-03 deploy for Step 5. | Team Lead |
