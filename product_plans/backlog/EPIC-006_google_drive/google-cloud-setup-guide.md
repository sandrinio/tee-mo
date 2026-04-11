---
guide_id: "google-cloud-setup"
status: "In Progress — user adding credentials 2026-04-12"
owner: "Solo dev"
parent_epic: "EPIC-006"
purpose: "Operational runbook for creating the Google OAuth 2.0 Web Application credentials that EPIC-006 (Google Drive Integration) will consume. User can complete this in parallel with unrelated sprints — no code dependency."
---

# Google Cloud Console Setup — OAuth 2.0 Credentials for Drive

> **Status:** User has added `GOOGLE_API_CLIENT_ID` and `GOOGLE_API_SECRET` to `.env` (2026-04-12) but has NOT yet configured **Authorized JavaScript origins** or **Authorized redirect URIs** in the Google Cloud Console. This file tells you exactly what to paste.

---

## What you're setting up

Google OAuth 2.0 "Web application" credentials for Tee-Mo to access Google Drive files on behalf of users. This uses the **offline refresh token flow** (Roadmap ADR-009) so the backend can mint short-lived access tokens later without re-prompting the user.

This credential is consumed by **EPIC-006: Google Drive Integration** (much later in the project — not needed for S-03, S-04, or S-05). Setting it up now in parallel is a good use of wait time.

---

## Prerequisites — already done

- [x] Google Cloud project created
- [x] OAuth 2.0 Client ID created, type **"Web application"** (confirm — if it's "Desktop" or "TV" it won't work for our redirect flow)
- [x] `GOOGLE_API_CLIENT_ID` and `GOOGLE_API_SECRET` copied into project-root `.env`
- [ ] **Authorized JavaScript origins** configured ← THIS GUIDE
- [ ] **Authorized redirect URIs** configured ← THIS GUIDE
- [ ] Google Drive API v3 enabled in the "Enabled APIs & services" tab
- [ ] Google Picker API enabled in the "Enabled APIs & services" tab
- [ ] (Optional for Picker) Google Cloud API Key created with HTTP-referrer restrictions

---

## Step 1 — Authorized JavaScript origins

Go to **Google Cloud Console → APIs & Services → Credentials → click your OAuth 2.0 Client ID → scroll to "Authorized JavaScript origins"**.

Add these exact values, one per row:

```
https://teemo.soula.ge
http://localhost:5173
```

**Why both:**
- `https://teemo.soula.ge` — production frontend origin. Required for the browser to initiate OAuth when the user clicks "Connect Drive" in the live deploy.
- `http://localhost:5173` — Vite dev server origin. Required so you can test the OAuth flow against the local backend during development. Google allows `http://localhost` as a special case even though they require HTTPS for every other host.

**Do NOT add:**
- `http://teemo.soula.ge` (no HTTPS — Google rejects it)
- `https://teemo.soula.ge/` (trailing slash — Google rejects it)
- `https://*.soula.ge` (wildcards — Google doesn't support them in JS origins)

---

## Step 2 — Authorized redirect URIs

Same credential page, scroll to **"Authorized redirect URIs"**.

Add these exact values:

```
https://teemo.soula.ge/api/drive/oauth/callback
http://localhost:8000/api/drive/oauth/callback
```

**Why:**
- Offline refresh token flow (ADR-009) has the user's browser redirect to a **backend** endpoint after they grant consent, NOT back to the frontend. The backend then exchanges the authorization code for an access token + refresh token, encrypts the refresh token with AES-256-GCM (per ADR-002/010), and stores it on the workspace row in `teemo_workspaces.encrypted_google_refresh_token`.
- The backend URL in prod is `https://teemo.soula.ge` (same-origin per ADR-026 — frontend + backend served from one Coolify container, `/api/*` routes to FastAPI).
- The backend URL in dev is `http://localhost:8000` (Vite dev runs on 5173, FastAPI dev runs on 8000 — they're on different ports but `localhost` is always allowed by Google).
- Path `/api/drive/oauth/callback` is a Tee-Mo convention — the actual endpoint doesn't exist yet (EPIC-006 builds it). Google doesn't care that the endpoint is absent at credential-creation time; it only cares when the user actually completes an OAuth flow. Since we're setting this up in parallel with unrelated sprints, the absence is fine — EPIC-006 will wire the endpoint when it ships.

**Do NOT add:**
- Anything with a trailing slash
- Anything with query params — Google rejects them
- A frontend-side `/oauth/callback` path — that's not how offline refresh works for our design

---

## Step 3 — Enable the Drive API and Picker API

Go to **Google Cloud Console → APIs & Services → Enabled APIs & services → + ENABLE APIS AND SERVICES**.

Search for and enable each:

1. **Google Drive API** — required for `files.get`, `files.export`, `files.list` (EPIC-006 core).
2. **Google Picker API** — required for the Drive file picker UI in `frontend/` (EPIC-006 UX). Per Charter §3.2 and Roadmap §4, the Picker is listed as available / P1. If enabling it is annoying, skip for now — we can fall back to manual `drive_file_id` entry per the Roadmap §4 note.

You'll see a confirmation banner for each. Wait ~30 seconds per API for propagation.

---

## Step 4 — (Optional) Create an API Key for Google Picker

The Google Picker widget requires a client-side API Key, separate from the OAuth Client ID/Secret. If you're skipping the Picker for now (per Roadmap §4 fallback), skip this step.

1. Same **Credentials** page → **+ CREATE CREDENTIALS** → **API key**
2. Copy the generated key — this becomes `GOOGLE_PICKER_API_KEY` in `.env`
3. Click **RESTRICT KEY** (important — unrestricted keys are a security risk):
   - **Application restrictions** → **HTTP referrers (websites)**
   - Add referrers:
     ```
     https://teemo.soula.ge/*
     http://localhost:5173/*
     ```
   - **API restrictions** → **Restrict key** → select **Google Picker API**
4. Save

---

## Step 5 — Test user setup (required for unpublished app)

Until the Google Cloud project is verified (long process — Charter §1.3 / Roadmap Open Question "Parked — revisit Sprint 8"), your OAuth app is in **testing mode**. This means only **designated test users** can complete the OAuth flow. Everyone else gets an "unverified app" error.

1. **OAuth consent screen** tab → scroll to **Test users**
2. Add your own Google account email
3. Add any hackathon judges' Google emails if/when they're known
4. Save

---

## Verification

Once Steps 1–3 are done, the credential is complete on Google's side. You can verify by:

1. The Credentials page shows your OAuth 2.0 Client ID with both sections populated.
2. There are no red warnings on the credential.

You do NOT need to test the OAuth flow right now. EPIC-006 will exercise it when it ships.

---

## Environment variables to add to Coolify (when EPIC-006 ships)

When the prod deploy (ADR-026) needs Google Drive, you'll inject these via Coolify env vars:

```
GOOGLE_API_CLIENT_ID=<value from .env>
GOOGLE_API_SECRET=<value from .env>
GOOGLE_PICKER_API_KEY=<value from Step 4, if you did it>
```

**Important note on naming:** You chose `GOOGLE_API_CLIENT_ID` and `GOOGLE_API_SECRET` in `.env`. Standard Google SDK convention uses `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET`, but your names are fine — EPIC-006 will read them under the names you chose. Just don't rename them between now and when EPIC-006 lands.

---

## What this guide does NOT cover (out of scope for now)

- How to write the backend code that consumes these credentials — that's EPIC-006
- How to publish the Google Cloud project to production — Roadmap Open Question "Parked — revisit Sprint 8"
- Scopes (`https://www.googleapis.com/auth/drive.readonly` + picker scopes) — EPIC-006 declares these in the backend code when it builds the OAuth URL

---

## Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-04-12 | Guide created in parallel with ADR-026 planning. User added `GOOGLE_API_CLIENT_ID` / `GOOGLE_API_SECRET` to `.env` and asked what to put in JS origins / redirect URIs. | Team Lead |
