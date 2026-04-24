# ClearGate Delivery Index — Tee-Mo

> Curated map of what's planned, in-flight, and shipped. Hand-maintained. Updated on every sprint close + epic status change. Full historical detail is in `product_plans.vbounce-archive/` and referenced ADRs at `.cleargate/knowledge/adrs.md`.

**Initiative:** [PROPOSAL-001: Tee-Mo — Context-Aware Slack AI Agent (BYOK)](./archive/PROPOSAL-001-teemo-platform.md) · `approved: true`

---

## Epic Status

### Active (unshipped, in `delivery/pending-sync/`)

| Epic | Title | Ambiguity | Stories | Notes |
|---|---|---|---|---|
| EPIC-002 | Auth — remaining work | 🔴 | 0 | Residual polish on top of shipped S-02 auth |
| EPIC-003 | Dashboard Shell | 🔴 | 0 | Most dashboard work landed S-03/S-05; residual scope only |
| EPIC-005 | Slack Integration — Phase B (events + bindings) | 🔴 | 0 | Phase A shipped S-04; Phase B scoped but not decomposed |
| EPIC-011 | Slack AI Apps Surface | 🔴 | 0 | Deferred to EPIC-005 Phase B per project memory |
| EPIC-012 | MCP Integration | 🔴 | 0 | Ideation stage |
| EPIC-014 | Local Upload | 🔴 | 0 | Ideation stage |
| EPIC-017 | Wiki Karpathy Parity (Phase A complete; B–E remain) | 🟡 | 1 | Phase A (`search_wiki`) shipped post-S-11 |
| EPIC-018 | Scheduled Automations | 🟢 | 6 | Active in SPRINT-12 (backend); UI deferred |
| EPIC-022 | Frontend Token Management | 🟢 | 1 | API refresh interceptor |
| EPIC-023 | UX Production Readiness | 🟢 | 2 | Skills list UI + landing page removal |
| EPIC-024 | Concurrency Hardening | 🟢 | 4 | DB queue RPC + worker locks + FastAPI thread wrapper + legacy test fix |

### Shipped (in `delivery/archive/`)

| Epic | Title | Sprint | Notes |
|---|---|---|---|
| EPIC-001 | Project Scaffold + Supabase Schema | S-01 | Partial — ADR-024 tables reassigned to EPIC-003 Slice A |
| EPIC-002 | Auth (Email + Password + JWT) | S-02 | `v0.2.0-auth` — 22 backend + 10 frontend tests |
| EPIC-003 Slice A | Dashboard Shell — schema foundation | S-03 | Ships deploy + ADR-024 migrations + PyJWT fix |
| EPIC-003 Slice B | Dashboard Shell — workspace CRUD | S-05 | `v0.5.0` |
| EPIC-004 | BYOK Key Management | S-06 | `v0.6.0` — 4 routes, 23 tests |
| EPIC-005 Phase A | Slack OAuth Install | S-04 | `v0.4.0` — 0 QA / 0 Arch bounces |
| EPIC-006 | Google Drive Integration | S-08 + S-10 | 11 stories — 120+ tests, multimodal PDF fallback |
| EPIC-007 | AI Agent + Two-Tier Models + Skills | S-07 | `v0.7.0` |
| EPIC-008 | Workspace Setup Wizard Polish | S-09 | 5/5 stories, 86 new tests |
| EPIC-013 | Wiki Knowledge Pipeline | S-11 | `search_wiki` + `read_wiki_page` tools |
| EPIC-015 | Agent Document Creation | S-11 | `teemo_documents` redesign |
| EPIC-016 | Structured Logging | S-11 | JSON logs + token redaction |

---

## Sprint Delivery Log

> Condensed from V-Bounce Roadmap §7 Delivery Log. Full sprint plans + reports live in `product_plans.vbounce-archive/archive/sprints/sprint-{01..11}/` and `.cleargate/sprint-runs/SPRINT-{01..12}/` after Phase 7 port.

| Sprint | Delivery | Epic(s) | Tag | Status |
|---|---|---|---|---|
| S-01 | D-01 Foundation | EPIC-001 (partial) | — | Shipped |
| S-02 | D-01 Foundation | EPIC-002 | `v0.2.0-auth` | Shipped |
| S-03 | D-01 Foundation + Deploy | EPIC-003 Slice A + deploy + PyJWT fix | `v0.3.0-deploy` | Shipped |
| S-04 | D-01 Foundation + Slack Install | EPIC-005 Phase A | `v0.4.0` | Shipped |
| S-05 | D-02 | EPIC-003 Slice B | `v0.5.0` | Shipped |
| S-06 | D-03 | EPIC-004 | `v0.6.0` | Shipped |
| S-07 | D-03 | EPIC-007 | `v0.7.0` | Shipped |
| S-08 | D-04 | EPIC-006 Phase A | — | Shipped |
| S-09 | D-05 Demo Polish | EPIC-008 | — | Shipped |
| S-10 | D-06 | EPIC-006 enhancement wave | — | Shipped |
| S-11 | D-06 | EPIC-013 + EPIC-015 + EPIC-016 | — | Shipped |
| Post-S-11 | direct commits | EPIC-017 Phase A | — | Shipped (outside V-Bounce) |
| **S-12** | — | EPIC-018 backend | — | **Active** |

---

## Open Gates

Items currently halted for human input:

_(empty as of 2026-04-24 migration cutover — all active epics are 🟢 or 🔴-but-unscoped)_

---

## Next Work (next 2-3 sprints of detail only)

_Per project convention: plan 2-3 sprints ahead in detail; long-horizon scope stays in this INDEX and the archived Roadmap, not in sprint plans._

- **SPRINT-13 candidate:** Close out EPIC-024 concurrency hardening (4 stories, 🟢).
- **SPRINT-14 candidate:** EPIC-023 UX readiness (2 stories) + EPIC-022 token mgmt (1 story).
- **Beyond:** EPIC-017 Phases B–E (wiki synthesis, cascade, curation UI); EPIC-005 Phase B if Slack events hardening bubbles up.

---

## References

- **Umbrella Proposal:** [`archive/PROPOSAL-001-teemo-platform.md`](./archive/PROPOSAL-001-teemo-platform.md)
- **ADRs (architectural decisions, ADR-001 through ADR-027):** [`.cleargate/knowledge/adrs.md`](../knowledge/adrs.md)
- **Design Guide:** [`.cleargate/knowledge/design-guide.md`](../knowledge/design-guide.md)
- **Protocol:** [`.cleargate/knowledge/cleargate-protocol.md`](../knowledge/cleargate-protocol.md)
- **Flashcards:** [`.cleargate/FLASHCARD.md`](../FLASHCARD.md)
- **V-Bounce archive (full history):** `product_plans.vbounce-archive/`, `.vbounce-archive/`
- **Migration plan & port map:** [`MIGRATION_CLEARGATE.md`](../../MIGRATION_CLEARGATE.md) · [`MIGRATION_PORT_MAP.md`](../../MIGRATION_PORT_MAP.md)

## Change Log

| Date | Change | By |
|------|--------|----|
| 2026-04-24 | Initial INDEX created during ClearGate migration from V-Bounce Roadmap §2 Release Plan + §7 Delivery Log | Claude Opus 4.7 (migration/cleargate) |
