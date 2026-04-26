# Tee-Mo Architecture

> AI assistant platform for Slack workspaces with multi-provider LLM support via Bring-Your-Own-Key (BYOK).

## Table of Contents

- [System Overview](#system-overview)
- [Tech Stack](#tech-stack)
- [Multi-Tenancy & Scalability](#multi-tenancy--scalability)
- [Bot Configuration](#bot-configuration)
- [Metadata Model](#metadata-model)
- [Authentication & Security](#authentication--security)
- [Slack Integration](#slack-integration)
- [Encryption Pipeline](#encryption-pipeline)
- [Database Schema](#database-schema)
- [Deployment](#deployment)

---

## System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                          INTERNET                                    │
└──────────┬──────────────────┬──────────────────┬─────────────────────┘
           │                  │                  │
           ▼                  ▼                  ▼
    ┌─────────────┐   ┌─────────────┐   ┌──────────────┐
    │   Browser   │   │ Slack API   │   │  LLM Provider │
    │  (React SPA)│   │  (Events +  │   │  (Google /    │
    │             │   │   OAuth)    │   │  OpenAI /     │
    │             │   │             │   │  Anthropic)   │
    └──────┬──────┘   └──────┬──────┘   └──────▲───────┘
           │                 │                  │
           │ HTTPS           │ HTTPS            │ HTTPS (BYOK key)
           │ (cookies)       │ (signatures)     │
           ▼                 ▼                  │
    ┌──────────────────────────────────────────────────────┐
    │                  FastAPI (Uvicorn)                    │
    │                                                      │
    │  ┌────────────┐  ┌────────────┐  ┌────────────────┐  │
    │  │ Auth Routes │  │Slack Routes│  │ Workspace/Key  │  │
    │  │ /api/auth/* │  │/api/slack/*│  │  /api/*        │  │
    │  └─────┬──────┘  └─────┬──────┘  └───────┬────────┘  │
    │        │               │                  │           │
    │  ┌─────▼───────────────▼──────────────────▼────────┐  │
    │  │              Core Services                       │  │
    │  │  security.py │ encryption.py │ key_validator.py  │  │
    │  └─────────────────────┬───────────────────────────┘  │
    │                        │                              │
    │  ┌─────────────────────▼───────────────────────────┐  │
    │  │             Supabase Client (PostgREST)          │  │
    │  └─────────────────────┬───────────────────────────┘  │
    └────────────────────────┼──────────────────────────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │   Self-Hosted        │
                  │   Supabase           │
                  │   (PostgreSQL)       │
                  │                      │
                  │   teemo_users        │
                  │   teemo_slack_teams  │
                  │   teemo_workspaces   │
                  │   teemo_knowledge_*  │
                  │   teemo_skills       │
                  └─────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TypeScript, TanStack Router + Query, Zustand, Tailwind CSS v4 |
| Backend | FastAPI (Python 3.11), Uvicorn |
| Database | Self-hosted Supabase (PostgreSQL) |
| Encryption | AES-256-GCM (`cryptography` library) |
| Auth | PyJWT (HS256), bcrypt |
| Deployment | Docker (multi-stage), Coolify |

---

## Multi-Tenancy & Scalability

### Tenancy Hierarchy

```mermaid
graph TD
    U[User<br><i>teemo_users</i>] -->|owns 1:N| ST[Slack Team<br><i>teemo_slack_teams</i>]
    ST -->|contains 1:N| W[Workspace<br><i>teemo_workspaces</i>]
    W -->|has 0:N| KI[Knowledge Index<br><i>teemo_knowledge_index</i>]
    W -->|has 0:N| SK[Skills<br><i>teemo_skills</i>]
    W -->|has 0:1| KEY["BYOK API Key<br>(encrypted)"]
    ST -->|has 1| BOT["Bot Token<br>(encrypted)"]

    style U fill:#4A90D9,color:#fff
    style ST fill:#7B68EE,color:#fff
    style W fill:#50C878,color:#fff
    style KI fill:#FFB347,color:#000
    style SK fill:#FFB347,color:#000
    style KEY fill:#FF6B6B,color:#fff
    style BOT fill:#FF6B6B,color:#fff
```

### Scalability Model

```
                    Stateless
                 ┌─────────────┐
  Request ──────►│  FastAPI #1  │──────┐
                 └─────────────┘      │
                 ┌─────────────┐      │     ┌──────────────┐
  Request ──────►│  FastAPI #2  │──────┼────►│   Supabase   │
                 └─────────────┘      │     │  (all state)  │
                 ┌─────────────┐      │     └──────────────┘
  Request ──────►│  FastAPI #N  │──────┘
                 └─────────────┘
```

**Key design decisions:**

- **Zero in-process state** — every request decrypts keys and resolves context from the DB. No caches, no singletons holding bot instances.
- **Horizontal scaling** — add more FastAPI containers behind a load balancer. All state lives in Supabase.
- **Isolation is application-enforced** — RLS is disabled. Every DB query includes `WHERE user_id = :current_user` or `WHERE owner_user_id = :current_user`. Team ownership is verified via `assert_team_owner()` before any workspace mutation.
- **One default workspace per team** — enforced by a PostgreSQL partial unique index on `(slack_team_id) WHERE is_default_for_team = true`.

---

## Bot Configuration

Each bot instance is configured through three layers:

```mermaid
graph LR
    subgraph "Layer 1: Environment"
        ENV["TEEMO_ENCRYPTION_KEY<br>SUPABASE_JWT_SECRET<br>SLACK_CLIENT_ID/SECRET<br>SLACK_SIGNING_SECRET"]
    end

    subgraph "Layer 2: Slack Team"
        TEAM["encrypted_slack_bot_token<br>slack_bot_user_id<br>owner_user_id"]
    end

    subgraph "Layer 3: Workspace"
        WS["ai_provider (google|openai|anthropic)<br>ai_model (e.g. gemini-2.5-flash)<br>encrypted_api_key<br>key_mask"]
    end

    ENV --> TEAM
    TEAM --> WS

    style ENV fill:#2C3E50,color:#fff
    style TEAM fill:#7B68EE,color:#fff
    style WS fill:#50C878,color:#fff
```

### Provider Defaults

| Provider | Default Model |
|----------|--------------|
| `google` | `gemini-2.5-flash` |
| `openai` | `gpt-4o` |
| `anthropic` | `claude-sonnet-4-6` |

### Key Resolution at Inference Time

```mermaid
sequenceDiagram
    participant Slack as Slack Event
    participant API as FastAPI
    participant DB as Supabase
    participant Enc as encryption.py
    participant LLM as LLM Provider

    Slack->>API: Event (message/mention)
    API->>DB: Get workspace for team
    DB-->>API: workspace row (encrypted_api_key)
    API->>Enc: decrypt(encrypted_api_key)
    Enc-->>API: plaintext API key
    API->>LLM: Chat completion (with BYOK key)
    LLM-->>API: Response
    API->>Slack: Post reply
```

---

## Metadata Model

Metadata serves four distinct purposes across the system:

```mermaid
graph TD
    subgraph "Display Metadata"
        KM["key_mask<br><i>first 4 + last 4 chars</i><br>No decryption needed"]
    end

    subgraph "Knowledge Metadata"
        AI["ai_description<br><i>2-3 sentence AI summary</i>"]
        CH["content_hash<br><i>MD5 of file content</i>"]
        LS["last_scanned_at<br><i>Cache timestamp</i>"]
        MT["mime_type<br><i>6 allowed types</i>"]
    end

    subgraph "Skill Metadata"
        SN["name<br><i>slug format</i>"]
        SS["summary<br><i>'Use when...' ≤160 chars</i>"]
        SI["instructions<br><i>Workflow ≤2000 chars</i>"]
        SA["is_active<br><i>Catalog toggle</i>"]
    end

    subgraph "Workspace Metadata"
        WP["ai_provider + ai_model"]
        WD["is_default_for_team"]
        WT["slack_team_id"]
    end

    style KM fill:#FF6B6B,color:#fff
    style AI fill:#FFB347,color:#000
    style CH fill:#FFB347,color:#000
    style LS fill:#FFB347,color:#000
    style MT fill:#FFB347,color:#000
    style SN fill:#87CEEB,color:#000
    style SS fill:#87CEEB,color:#000
    style SI fill:#87CEEB,color:#000
    style SA fill:#87CEEB,color:#000
    style WP fill:#50C878,color:#000
    style WD fill:#50C878,color:#000
    style WT fill:#50C878,color:#000
```

### Knowledge Index — Cache & Diff System

```
  Google Drive File
        │
        ▼
  ┌─────────────┐     content changed?
  │  Scan File   │────────────────────────┐
  │  (MD5 hash)  │                        │
  └──────┬───────┘                    NO  │
         │ YES                            │
         ▼                                ▼
  ┌─────────────┐                  ┌─────────────┐
  │ Re-generate  │                  │  Skip scan   │
  │ AI summary   │                  │  (use cached) │
  │ Update hash  │                  └──────────────┘
  │ Update ts    │
  └──────────────┘
```

The `content_hash` (MD5) enables **incremental re-scanning** — only files whose content actually changed get re-processed. The `ai_description` provides semantic search capability without re-reading the full document.

### Skills — Routing Table

```
  Incoming message
        │
        ▼
  ┌─────────────────┐
  │ Match against    │──── summary: "Use when user asks about..."
  │ active skills    │
  └────────┬────────┘
           │ matched
           ▼
  ┌─────────────────┐
  │ Inject into LLM │──── instructions: workflow steps (≤2000 chars)
  │ context          │
  └─────────────────┘
```

---

## Google Drive Knowledge Pipeline

The knowledge system is **not RAG** — there are no embeddings or vector databases. Files are read on-demand at inference time, with metadata acting as a routing layer so the AI knows *which* file to read.

### End-to-End Flow

```mermaid
sequenceDiagram
    participant U as User (Dashboard)
    participant GP as Google Picker
    participant API as FastAPI
    participant GD as Google Drive API
    participant LLM as LLM Provider (Scan Tier)
    participant DB as Supabase

    Note over U,DB: Phase 1: Connect Google Drive
    U->>API: "Connect Google Drive"
    API->>U: 307 → Google OAuth consent
    U->>API: Callback with auth code
    API->>API: Exchange code → refresh_token
    API->>API: encrypt(refresh_token)
    API->>DB: Store encrypted_google_refresh_token on workspace

    Note over U,DB: Phase 2: Index a File
    U->>GP: Open Google Picker
    GP-->>U: User selects file (drive_file_id)
    U->>API: POST /api/knowledge {drive_file_id, workspace_id}
    API->>API: Check: BYOK key exists? Files < 15?
    API->>DB: Decrypt refresh_token → mint access_token
    API->>GD: Read file content (export or media download)
    GD-->>API: File content (text)
    API->>API: MD5(content) → content_hash
    API->>LLM: "Summarize in 2-3 sentences, focus on what questions it answers"
    LLM-->>API: ai_description
    API->>DB: INSERT teemo_knowledge_index row

    Note over U,DB: Phase 3: AI Uses Knowledge at Inference
    U->>API: @mention in Slack: "What's our refund policy?"
    API->>DB: Load workspace's knowledge_index (all rows)
    API->>LLM: System prompt includes file catalog:<br>- title, ai_description for each file
    LLM->>LLM: Decides which file(s) are relevant
    LLM->>API: Tool call: read_drive_file(file_id)
    API->>GD: Fetch full file content
    GD-->>API: Content
    API->>API: Check content_hash — rescan if changed
    API-->>LLM: File content injected into context
    LLM-->>API: Final answer using file content
    API->>U: Slack reply in thread
```

### How the AI Knows Which File to Read

The knowledge index acts as a **semantic routing table** — not a search index, but a catalog the AI reasons over:

```mermaid
graph TD
    subgraph "Knowledge Index (per workspace, max 15 files)"
        F1["📄 refund-policy.docx<br><b>ai_description:</b> Covers return windows,<br>refund eligibility, and exception cases<br>for digital vs physical products"]
        F2["📊 Q1-metrics.xlsx<br><b>ai_description:</b> Revenue, churn rate,<br>and NPS scores broken down by<br>product line for Q1 2026"]
        F3["📑 onboarding-guide.pdf<br><b>ai_description:</b> Step-by-step new hire<br>checklist covering IT setup, team intros,<br>and first-week deliverables"]
    end

    Q["User: 'What's our refund policy<br>for digital products?'"]
    Q --> AGENT["AI Agent reviews catalog"]
    AGENT -->|ai_description matches| F1
    AGENT -.->|not relevant| F2
    AGENT -.->|not relevant| F3
    F1 -->|read_drive_file tool call| CONTENT["Full file content<br>injected into context"]
    CONTENT --> REPLY["Agent composes answer<br>from actual document text"]

    style Q fill:#4A90D9,color:#fff
    style AGENT fill:#7B68EE,color:#fff
    style F1 fill:#50C878,color:#000
    style F2 fill:#ddd,color:#666
    style F3 fill:#ddd,color:#666
    style CONTENT fill:#FFB347,color:#000
    style REPLY fill:#4A90D9,color:#fff
```

**Key design decisions:**

1. **No vector DB / embeddings** — the AI reads `ai_description` for all 15 files and decides which to fetch. At 15 files max, full-catalog reasoning is trivially fast and more accurate than cosine similarity.
2. **On-demand file reads** — files are fetched from Google Drive at inference time via `read_drive_file` tool. No content is stored locally. Always fresh.
3. **Two-tier LLM usage** — file summarization uses the **scan tier** (cheapest model: `gemini-2.0-flash-lite`, `gpt-4o-mini`, `claude-haiku-4-5`). Conversation uses the **conversation tier** (user-selected model). Both use the same BYOK key.
4. **Content-hash diffing** — at inference time, if the file's MD5 has changed since `last_scanned_at`, the AI re-summarizes before answering. Self-healing metadata.
5. **`drive.file` scope, not `drive.readonly`** — only files the user explicitly picks via Google Picker are accessible. No full-Drive enumeration. Zero security review needed from Google.

### File Type Handling

The `read_drive_file` tool branches by MIME type to extract text:

```mermaid
graph LR
    FILE["Drive File"] --> CHECK{"MIME type?"}

    CHECK -->|Google Docs| EX1["files.export → text/plain"]
    CHECK -->|Google Sheets| EX2["files.export → text/csv"]
    CHECK -->|Google Slides| EX3["files.export → text/plain"]
    CHECK -->|PDF| EX4["files.get media → pypdf"]
    CHECK -->|Word .docx| EX5["files.get media → python-docx"]
    CHECK -->|Excel .xlsx| EX6["files.get media → openpyxl"]
    CHECK -->|Other| REJ["Rejected at index time"]

    style FILE fill:#4A90D9,color:#fff
    style CHECK fill:#7B68EE,color:#fff
    style EX1 fill:#50C878,color:#000
    style EX2 fill:#50C878,color:#000
    style EX3 fill:#50C878,color:#000
    style EX4 fill:#FFB347,color:#000
    style EX5 fill:#FFB347,color:#000
    style EX6 fill:#FFB347,color:#000
    style REJ fill:#FF6B6B,color:#fff
```

### Google Drive OAuth (per Workspace)

Each workspace has its **own** Google Drive credential — workspaces under the same Slack team never share Drive auth:

```mermaid
graph TD
    ST["Slack Team<br>(1 bot token)"]
    ST --> W1["Workspace A<br>encrypted_google_refresh_token_A"]
    ST --> W2["Workspace B<br>encrypted_google_refresh_token_B"]

    W1 --> DA["Drive Account: alice@corp.com<br>Files: policy.docx, metrics.xlsx"]
    W2 --> DB["Drive Account: bob@corp.com<br>Files: onboarding.pdf"]

    style ST fill:#7B68EE,color:#fff
    style W1 fill:#50C878,color:#000
    style W2 fill:#50C878,color:#000
    style DA fill:#FFB347,color:#000
    style DB fill:#FFB347,color:#000
```

The refresh token flow (ADR-009):
1. User clicks "Connect Drive" → Google OAuth consent (`drive.file` + `userinfo.email` scopes)
2. Backend receives auth code → exchanges for `access_token` + `refresh_token`
3. `refresh_token` encrypted with AES-256-GCM → stored in `teemo_workspaces.encrypted_google_refresh_token`
4. At inference time: decrypt refresh token → exchange for short-lived access token → read file → discard access token

### Guardrails

| Constraint | Enforcement |
|-----------|-------------|
| Max 15 files per workspace | DB trigger (`trg_teemo_knowledge_index_cap`) + backend pre-check |
| BYOK key required before adding files | Backend rejects with 400 if no `encrypted_api_key` |
| Supported MIME types only | DB CHECK constraint on `mime_type` column (6 allowed types) |
| One file indexed once per workspace | UNIQUE constraint on `(workspace_id, drive_file_id)` |
| Refresh token revoked by user | Backend detects `invalid_grant` → prompts reconnect via dashboard |

---

## Authentication & Security

### Token Architecture

```mermaid
graph TD
    subgraph "Token Types"
        AT["Access Token<br>15 min TTL<br>Cookie: access_token<br>Claims: sub, role, iat, exp"]
        RT["Refresh Token<br>7 day TTL<br>Cookie: refresh_token<br>Path: /api/auth<br>Claims: sub, type:refresh, iat, exp"]
        SS["Slack State Token<br>5 min TTL<br>Query param: state<br>Claims: user_id, aud:slack-install, iat, exp"]
    end

    AT ---|"Same signing key<br>(supabase_jwt_secret)"| RT
    RT ---|"Audience-namespaced<br>(prevents cross-use)"| SS

    style AT fill:#4A90D9,color:#fff
    style RT fill:#7B68EE,color:#fff
    style SS fill:#FF6B6B,color:#fff
```

### Auth Flow

```mermaid
sequenceDiagram
    participant B as Browser
    participant API as FastAPI
    participant DB as Supabase

    Note over B,DB: Login
    B->>API: POST /api/auth/login {email, password}
    API->>DB: Lookup teemo_users by email
    DB-->>API: user row (password_hash)
    API->>API: bcrypt.checkpw()
    API-->>B: Set-Cookie: access_token (15m) + refresh_token (7d)

    Note over B,DB: Authenticated Request
    B->>API: GET /api/workspaces (Cookie: access_token)
    API->>API: decode_token() → user_id
    API->>DB: SELECT ... WHERE user_id = :uid
    DB-->>API: results
    API-->>B: JSON response

    Note over B,DB: Token Refresh
    B->>API: POST /api/auth/refresh (Cookie: refresh_token)
    API->>API: decode_token() → check type="refresh"
    API-->>B: New access_token cookie
```

---

## Slack Integration

### OAuth Install Flow

```mermaid
sequenceDiagram
    participant U as User (Browser)
    participant API as FastAPI
    participant S as Slack API
    participant DB as Supabase

    U->>API: GET /api/slack/install
    API->>API: create_slack_state_token(user_id)<br>5 min JWT, aud="slack-install"
    API-->>U: 307 → slack.com/oauth/v2/authorize

    U->>S: Consent screen
    S-->>U: Redirect → /api/slack/oauth/callback?code=...&state=...

    U->>API: GET /api/slack/oauth/callback
    API->>API: verify_slack_state_token(state)

    alt State expired
        API-->>U: 302 → /app?slack_install=expired
    end
    alt User cancelled
        API-->>U: 302 → /app?slack_install=cancelled
    end

    API->>S: POST oauth.v2.access {code, client_id, client_secret}
    S-->>API: {ok: true, access_token, bot_user_id, team.id}

    API->>DB: Check existing team owner
    alt Different owner
        API-->>U: 409 Conflict
    end

    API->>API: encrypt(bot_token) → AES-256-GCM
    API->>DB: UPSERT teemo_slack_teams
    API-->>U: 302 → /app?slack_install=ok
```

### Event Handling

```mermaid
sequenceDiagram
    participant S as Slack
    participant API as FastAPI

    S->>API: POST /api/slack/events<br>X-Slack-Signature: v0=...<br>X-Slack-Request-Timestamp: ...

    API->>API: verify_slack_signature()<br>HMAC-SHA256 (constant-time)<br>300s replay window

    alt Signature invalid
        API-->>S: 403
    end

    alt url_verification challenge
        API-->>S: 200 {challenge: "..."}
    end

    API-->>S: 202 Accepted
    Note over API: Event processing (Phase B)
```

**8 Required Scopes (ADR-021 + ADR-025):**
`app_mentions:read`, `channels:history`, `channels:read`, `chat:write`, `groups:history`, `groups:read`, `im:history`, `users:read`

(`users:read` added 2026-04-27 — needed for sender display-name + tz resolution. Existing installs must re-authorize.)

---

## Encryption Pipeline

All secrets at rest use AES-256-GCM with a single master key (`TEEMO_ENCRYPTION_KEY`).

```
 ENCRYPT                                    DECRYPT
 ═══════                                    ═══════

 plaintext                                  base64url blob
     │                                           │
     ▼                                           ▼
 ┌──────────┐                              ┌──────────┐
 │ Generate  │                              │ base64url│
 │ 12-byte   │                              │ decode   │
 │ nonce     │                              └────┬─────┘
 └─────┬─────┘                                   │
       │                                    ┌────┴─────┐
       ▼                                    │ Split:   │
 ┌──────────┐                               │ nonce[12]│
 │ AES-256- │                               │ ct+tag   │
 │ GCM      │                               └────┬─────┘
 │ encrypt  │                                    │
 └─────┬─────┘                                   ▼
       │                                   ┌──────────┐
       ▼                                   │ AES-256- │
 nonce ║ ciphertext ║ tag                  │ GCM      │
       │                                   │ decrypt  │
       ▼                                   └────┬─────┘
 ┌──────────┐                                   │
 │ base64url│                                   ▼
 │ encode   │                              plaintext
 └─────┬────┘
       │
       ▼
  stored in DB

 Wire format: base64url( nonce[12] || ciphertext || gcm_tag[16] )
 Fresh nonce per call → same plaintext produces different ciphertext
```

**What gets encrypted:**

| Secret | Table | Column |
|--------|-------|--------|
| Slack bot token | `teemo_slack_teams` | `encrypted_slack_bot_token` |
| BYOK API key | `teemo_workspaces` | `encrypted_api_key` |
| Google refresh token | `teemo_workspaces` | `encrypted_google_refresh_token` (planned) |

**Logging safety:** Only `key_fingerprint()` (first 8 hex of SHA-256) is ever logged. Raw keys, ciphertext, and Slack secrets never appear in logs.

---

## Database Schema

```mermaid
erDiagram
    teemo_users {
        uuid id PK
        varchar email UK
        varchar password_hash
        timestamp created_at
        timestamp updated_at
    }

    teemo_slack_teams {
        varchar slack_team_id PK
        uuid owner_user_id FK
        varchar slack_bot_user_id
        text encrypted_slack_bot_token
        timestamp installed_at
    }

    teemo_workspaces {
        uuid id PK
        uuid user_id FK
        varchar slack_team_id FK
        varchar name
        varchar ai_provider
        varchar ai_model
        text encrypted_api_key
        varchar key_mask
        boolean is_default_for_team
        timestamp created_at
        timestamp updated_at
    }

    teemo_knowledge_index {
        uuid id PK
        uuid workspace_id FK
        varchar drive_file_id
        varchar title
        varchar link
        varchar mime_type
        text ai_description
        varchar content_hash
        timestamp last_scanned_at
        timestamp created_at
    }

    teemo_skills {
        uuid id PK
        uuid workspace_id FK
        varchar name
        varchar summary
        text instructions
        boolean is_active
        timestamp created_at
        timestamp updated_at
    }

    teemo_users ||--o{ teemo_slack_teams : "owns"
    teemo_users ||--o{ teemo_workspaces : "owns"
    teemo_slack_teams ||--o{ teemo_workspaces : "contains"
    teemo_workspaces ||--o{ teemo_knowledge_index : "indexes"
    teemo_workspaces ||--o{ teemo_skills : "has"
```

**Constraints:**
- `ai_provider` CHECK: `google`, `openai`, or `anthropic`
- `is_default_for_team`: partial unique index ensures max one default per team
- `teemo_skills.name`: slug regex (`^[a-z0-9]+(-[a-z0-9]+)*$`)
- `teemo_skills.summary`: max 160 chars; `instructions`: max 2000 chars
- `teemo_knowledge_index.mime_type`: 6 allowed MIME types
- All `updated_at` columns use the shared `teemo_set_updated_at()` trigger

---

## Deployment

### Docker Multi-Stage Build

```
 Stage 1: builder-frontend          Stage 2: runtime
 ══════════════════════════          ══════════════════════
 Node 22-alpine                     Python 3.11-slim
     │                                   │
     ├─ npm ci                           ├─ pip install (FastAPI deps)
     ├─ npm run build                    ├─ COPY backend/
     └─ Output: /build/dist/            ├─ COPY --from=stage1 dist/ → static/
                                         └─ CMD: uvicorn app.main:app
                                              --host 0.0.0.0 --port 8000
```

### Request Routing

```
  Incoming Request
       │
       ├── /api/*  ──────────► FastAPI route handlers
       │
       ├── /static/* ────────► Built React assets (JS, CSS, images)
       │
       └── /* (anything else) ► index.html (SPA fallback)
                                  │
                                  └─► TanStack Router (client-side routing)
```

### Development Setup

```
  Terminal 1:                    Terminal 2:
  cd frontend && npm run dev     cd backend && uvicorn app.main:app --reload
       │                              │
       │ :5173                        │ :8000
       │                              │
       └── /api/* proxy ──────────────┘
           (vite.config.ts)
```
