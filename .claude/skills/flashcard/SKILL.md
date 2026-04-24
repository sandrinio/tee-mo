---
name: flashcard
description: Append-only project lesson log at .cleargate/FLASHCARD.md. Use BEFORE starting non-trivial work to read past gotchas ("check" mode). Use WHEN you (a) hit a surprise, (b) found the winning path after a non-trivial task succeeded, or (c) were corrected by the user — record a one-liner for future agents ("record: <text>" mode). One-liners only; tag with #schema/#auth/#test-harness/etc. Also triggers on phrases: "turns out", "unexpected", "gotcha", "wasted time on", "starting work on", "before implementing", "user pushed back", "prefer X over Y", "winning path", "after several attempts", "the recipe that worked".
---

# Flashcard — Project Lesson Log

Append-only one-liner log of non-obvious gotchas that future agents in this project should know. Lives at `.cleargate/FLASHCARD.md` in the project root. Not a general wiki — only things that surprised us and would surprise someone else.

## Modes

### `check` — read before work
Read `.cleargate/FLASHCARD.md`. Apply the Rule 8 filter: skip cards marked `[S]` (stale) or `[R]` (resolved) unless your current task directly matches a tag in a superseded card. Scan active cards for tags relevant to your task (grep by `#schema`, `#auth`, etc.). If unsure whether a card applies, err on applying it — reading 20 one-liners is cheap.

Use `check-all` instead when investigating history or debugging a recurring issue — it includes `[S]` and `[R]` cards.

### `record: <text>` — three trigger classes, same format
Append a single line to `.cleargate/FLASHCARD.md`. Same 120-char cap regardless of trigger:

1. **Surprise** — something bit us. Lead with the surprise, not the context.
2. **Recipe** — the winning path after a non-trivial task succeeded (roughly 5+ tool calls, or one clear dead-end recovery). Lead with the *action that worked*, not the failures traversed. Tag `#recipe` alongside the domain tag.
3. **Correction** — the user pushed back on an approach. Capture the rule, not the exchange. Prefer the shape "prefer X over Y because Z". Tag `#correction` alongside the domain tag.

Format (unchanged):

```
YYYY-MM-DD · #tag1 #tag2 · <lesson ≤ 120 chars>
```

Examples:
```
2026-04-18 · #redis #auth · Invite tokens in Redis-only vanish on eviction — use Postgres invites table as source of truth.
2026-04-19 · #recipe #wiki · For wiki drift detection, git SHA beats content hash — drops the metadata-lifecycle dependency.
2026-04-19 · #correction #planning · Prefer two L1/L2 stories over one L3 at epic-decomposition (user: splits are free pre-push).
```

### Tag vocabulary (append new tags freely, but prefer these)
- `#schema` — Drizzle / migration / Postgres table shape gotcha
- `#auth` — JWT / refresh / bcrypt / token handling
- `#keychain` — macOS Keychain / libsecret / `@napi-rs/keyring` / `keytar`
- `#redis` — Redis key shape, TTL, persistence
- `#test-harness` — local docker compose, Postgres 18, Redis 8, flaky tests
- `#ci` — pipeline / GitHub Actions / pre-commit hooks
- `#mcp` — MCP SDK / Streamable HTTP / session protocol
- `#cli` — Commander / tsup / bin entry / npm publish
- `#admin-api` — Admin API contract / OpenAPI snapshot / zod
- `#ui` — SvelteKit / Tailwind / DaisyUI
- `#reporting` — sprint report generation
- `#qa` — recurring QA kickback patterns
- `#ambiguity` — story-spec ambiguities that bit us

## Rules

1. **Grep before append.** `grep -iF "<key phrase>" .cleargate/FLASHCARD.md` — if a matching card exists, skip or edit the existing line with a date suffix (e.g. `… (reconfirmed 2026-05-10)`). Never duplicate.
2. **One line per card.** Hard cap 120 characters for the lesson body. If it needs more, you are writing docs, not a flashcard — put docs elsewhere.
3. **Lead with the surprise, not the context.** Good: "Drizzle 0.45 silently drops `DEFAULT gen_random_uuid()` — use `sql` template." Bad: "When working on schema migrations yesterday we found that sometimes…"
4. **Lessons, not events.** "Shipped STORY-004-07 today" is NOT a flashcard. "Postgres 18 needs `pgcrypto` extension for gen_random_uuid — not enabled by default in official docker image" IS.
5. **Ordered newest-first after the header** — new entries go at the TOP of the log section, not bottom. Readers scan the top; old stuff drifts down.
6. **Never delete.** Edit to add reconfirmations, supersede pointers, or status markers (Rule 7); keep the original text. History is the point.
7. **Status markers for cleanup.** A card may carry a status marker placed *immediately after the second `·`* and before the lesson body:
   - no marker → active (default; the vast majority of cards).
   - `[S]` → stale. The symbol the card references no longer exists in the repo.
   - `[R] → superseded-by <short-ref>` → resolved or replaced by a later card / shipped fix. `<short-ref>` is a date+tag (e.g. `2026-04-19/#hooks-sentinel`) or a STORY/CR ID.
   Markers are additive — the original lesson text is preserved. The reporter agent flags candidates at sprint end; a human approves the batch before markers are applied (see `.claude/agents/reporter.md` → "Flashcard audit").
8. **Check-mode filter.** `check` reads active cards only (no marker). Include `[S]` / `[R]` cards only when: (a) their tags directly match the current task area, or (b) the invocation is `check-all` (explicit history read). This keeps `check` signal-dense without losing the historical record.

## Invocation contract

When an agent invokes this skill:

- **`Skill(flashcard, "check")`** — open `.cleargate/FLASHCARD.md`, apply the Rule 8 filter, summarize matching active cards in one line per card. If none apply, respond "no relevant flashcards" and proceed.
- **`Skill(flashcard, "check-all")`** — same as `check` but includes `[S]` / `[R]` cards. Use when investigating history, debugging a recurring issue, or tracing a supersede chain.
- **`Skill(flashcard, "record: <text>")`** — parse the text for date + tags + body. If date missing, insert today's UTC date. If tags missing, refuse with "add at least one tag." For recipe-class entries include `#recipe`; for correction-class entries include `#correction`. Grep for duplicates; if dup, reconfirm the existing line instead of appending. Append to the top of the log section in the file.

## File shape

`.cleargate/FLASHCARD.md` layout:

```markdown
# ClearGate Flashcards

One-liner gotcha log. Newest first. Grep by tag (e.g. `grep '#schema'`).
Active cards have no marker; `[S]` = stale, `[R]` = resolved (see SKILL.md Rule 7).
Format: `YYYY-MM-DD · #tags · [marker]? lesson`

---

2026-04-19 · #redis #auth · <newest active lesson>
2026-04-17 · #schema · [S] drizzle-kit v0.42 silently drops indexes — fixed in v0.45 upgrade.
2026-04-15 · #hooks · [R] → superseded-by 2026-04-19/#hooks-sentinel · SubagentStop fires on orchestrator not subagents.
...
```
