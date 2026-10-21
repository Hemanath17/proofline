# To do

## Done
- [x] Design: the blueprint (15 diagrams), the build spec (74 decisions), three scenarios run on paper
- [x] Step 0: repo set up with CLAUDE.md, contracts, packet guide, errors, acceptance tests and decisions
- [x] Step 1: prove we can deploy
  - [x] Next.js app in `web/`
  - [x] FastAPI app in `api/` with `/api/health`
  - [x] Root `vercel.json` with both services; checked the live link
  - [x] Neon database, with `DATABASE_URL` in `.env.local` and in Vercel
  - [x] `alembic init` and an `alembic.ini` that works from any folder
  - [x] First migration: the events table with `schema_version`
  - [x] Write an event, read it back, redeploy, and read it again
  - [x] Keep tests and fixtures out of the Python bundle
  - [x] Note the cold-start time
  - **Note:** `POST /api/events` and `GET /api/events/{id}` are throwaway proof-of-deploy routes — they write directly through `repository.py` with no revision check, no role check, no action-service transaction. Step 4 must remove them or put them behind the real action service and roles before anything else depends on them.

- [x] Part 0: fix outdated config
  - [x] `.claude/rules/checks.md`: paths, `CheckResult` location, 9 C2-scope `area` values, `claims` field, `Decimal` parsing, test path
  - [x] `.claude/skills/add-check/SKILL.md`: paths and test command
  - [x] `.claude/skills/add-check/template.py`: import, typed `Packet` param, `claims` example
  - [x] `.claude/skills/add-endpoint/SKILL.md`: route/security/actions paths, test path and command
  - [x] `.claude/hooks/format.sh`: Prettier path under `web/`
  - [x] `.claude/settings.json`: npm --prefix web allow/ask, recursive `.env` deny globs
  - [x] `api/proofline/db/connection.py`: `.env.local` resolved from repo root, not cwd
  - [x] Showed the diff of all seven
- [x] Step 2: the packet and the provenance resolver
  - [x] `proofline/packet.py`: Pydantic models, loaded once and cached
  - [x] `proofline/provenance/resolver.py`: every reference format
  - [x] `proofline/provenance/claim_identity.py`: the CONTRACTS.md claim identity table
  - [x] `proofline/provenance/tracing.py`: trace both directions + dependency graph
  - [x] `api/tests/unit/factories.py`: shared `minimal_packet` builder
  - [x] Tests: `test_packet.py`, `test_resolver.py` (incl. 0-unresolved sweep), `test_claim_identity.py`, `test_tracing.py`
  - [x] Done when: 0 unresolved references, and `F1040.1a` traces to D08+D09 with D10 excluded/noted
- [x] Step 3: checks for the confirmed errors
  - [x] `proofline/checks/models.py`: updated `CheckResult`
  - [x] E1 `DEPENDENT_SSN_INDEPENDENT_SOURCE` (fixture, check, tests)
  - [x] E2 `RSU_LOT_ZERO_BASIS_SUPPLEMENT_AVAILABLE` (fixture, check, tests)
  - [x] E3 `THIRD_PARTY_PROCESSOR_INCOME_DOUBLE_COUNTED` (fixture, check, tests)
  - [x] E4 `DOCUMENT_TOTAL_DISAGREES_WITH_EXTRACTED_DETAIL` (fixture, check, tests)
  - [x] `proofline/checks/runner.py`
  - [x] `proofline/checks/baseline.py` + `api/fixtures/baseline_expectations.json`
  - [x] `test_checks_runner.py`, `test_checks_baseline.py`, `test_checks_no_hardcoded_values.py`
  - [x] Done when: all four confirmed errors found (recall 4/4, precision 1.00), baseline prints, no hard-coded packet values in `api/proofline/checks/`
  - **Note:** checks read `packet.return_versions[-1]` as "the current version" rather than a literal `"v3"` string, so they keep working as new versions are added.
- [x] End of step: pytest output (53 passed), reviewer agent, `/deep-test`, `docs/ERRORS.md` check ids, `docs/DECISIONS.md`, `docs/AI_USAGE.md`

## Now: hardening pass on Steps 1-3 (before Step 4)
- [x] `proofline/checks/money.py`: shared `parse_money`, every check switched over
- [x] `runner.py`: isolate a failing check as a `CheckFailure`, keep running the rest
- [x] `baseline.py` + `baseline_expectations.json`: evidence/claims-overlap matching, not check_id alone
- [x] E2 rewrite: issuer/security match, prorate partial sales, blank=0, no-supplement -> possible_discrepancy
- [x] E3 rewrite: full normalized issuer name, sum all books rows, cap at the 1099-K amount
- [x] E1 rewrite: `belongs_to`-based linking, digits-only SSN compare, always check identity doc, W-2 box a for taxpayer/spouse
- [x] E4: run on any used document, not only `partial`
- [x] `TaxEffect.direction` (overstated/understated), set in E2 and E3
- [x] `packet.py`: indexes by id (documents, extracted values, lines per version, assets per version)
- [x] `tracing.py`: cache documents-used-per-version, timing test (<1s for all lines)
- [x] `tracing.py`: `LineTrace.other_sources` for non-document refs, dangling refs raise instead of swallow
- [x] `resolver.py`: resolve bare `v1`/`v2`/`v3`; sweep test covers `timeline[].refs`
- [x] Step 1 infra: `pool_pre_ping`, `/api/health` SELECT 1 + 503, JSONB+seq migration, pin requirements.txt, baseline command + dev-only note in CLAUDE.md, `ruff check --fix`
- [x] Regenerate all four check fixtures + regression test per item
- [x] pytest x2, reviewer agent, `/deep-test`, new baseline report, `docs/DECISIONS.md` entries -- no commit

## Now: Step 4, events/current state/action service/roles/redaction
- [x] Part A: migrations
  - [x] `add_event_metadata_columns`: actor_id, entity_type, entity_id, revision, occurred_at on events (nullable), indexes on (entity_type, entity_id) and seq
  - [x] `create_review_notes_and_check_runs_tables`
  - [x] `events_immutability_triggers`: Postgres trigger refusing UPDATE/DELETE/TRUNCATE on events
  - [x] Edit `8a1aa2459a26` downgrade() to raise instead of dropping the events table
  - [x] `proofline/db/canonical.py`: to_canonical_json, canonical_hash, prepare_payload_for_storage; fix the Decimal-in-payload crash
- [x] Part B: the action service
  - [x] `proofline/actions/service.py`: perform(), one transaction, permission -> validate -> CAS -> event -> check-run snapshot
  - [x] Generic `apply_revision_cas` helper (INSERT-at-1 or UPDATE...WHERE revision=:expected)
  - [x] `proofline/actions/review_notes.py`: add_review_note, respond_review_note, resolve_review_note
  - [x] `proofline/actions/reveal.py`: reveal_sensitive_value
  - [x] `proofline/actions/check_runs.py`: record_check_run + is_decision snapshot hook
  - [x] `proofline/db/rebuild.py`: replay events in seq order into fresh current state
  - [x] Remove `routes/events.py` and its test
- [x] Part C: actors and roles
  - [x] `proofline/packet.py`: typed StaffMember, ClientUser, Firm
  - [x] `proofline/security/actors.py`: Actor, load_actors (staff + client_users by name match + ai-assistant)
  - [x] `proofline/security/permissions.py`: check_permission with named 403 rules
  - [x] `proofline/security/dependencies.py`: get_current_actor (X-Proofline-Actor header, demo switcher, 401 if unknown/missing)
- [x] Part D: redaction
  - [x] `proofline/security/redact.py`: collect_sensitive_values, generate_variants, mask, redact_text, redact_json, redact_for_actor
  - [x] Logging filter for sensitive values
  - [x] Reveal-on-read wiring for document pages
- [x] Read endpoints: household, documents, document page, trace line, trace document, checks, review-notes list
- [x] Write endpoints: review-notes add/respond/resolve, reveal, check-runs
- [x] Part E: tests
  - [x] test_canonical.py, test_actors.py, test_permissions.py (I3), test_action_service.py (I1, I2), test_rebuild.py (I5), test_redact.py, test_leak_scan.py (I4)
  - [x] api/tests/pg/: test_events_immutable.py (I6), test_migration_replay.py (I7), test_concurrency.py; `pg` marker in pytest.ini
- [x] Part F: finish
  - [x] pytest unit x2 (241 passed, 5 skipped both times -- no flaky tests), pg tests x2 against a throwaway local Postgres (5 passed), `alembic check` against that same local Postgres at head (no differences), reviewer agent
  - [x] `/deep-test`: rule-to-test map, coverage (96% overall, every Step 4 file at 100% except `get_engine()`'s real-DB branch, deliberately not unit-tested), 8 real coverage gaps found and closed with new tests (no production code changed), rule-breaker grep scan clean, baseline unchanged (4/4 recall, 1.00 precision)
  - [ ] `/simulate` role-abuse concurrency leak-scan failure migration; docs/SIMULATION_REPORT.md -- **skipped this session**: `TEST_DATABASE_URL` still isn't actually present in `.env.local` (confirmed with `dotenv_values()`, which lists only `DATABASE_URL`, `BLOB_READ_WRITE_TOKEN`, `GROQ_API_KEY`, the `LANGFUSE_*` keys, `SIM_BASE_URL` and `VERCEL_OIDC_TOKEN`), so the user chose to skip the pg tests and `/simulate` against the Neon test branch for now rather than keep debugging the save
  - [x] Update docs/DECISIONS.md and docs/AI_USAGE.md
  - **Note:** once `TEST_DATABASE_URL` actually lands in `.env.local`, re-run `pytest api -m pg -q` (should show tests actually running, not skipped) and `/simulate role-abuse concurrency leak-scan failure migration` against it, then write `docs/SIMULATION_REPORT.md`

## Now: Steps 5-7, cases/queue, tracing/documents, areas/sign-off/calculation
- [x] Part 0: `docs/UX.md` written verbatim from the user's spec

### Step 5: cases and the review queue (C1)
- [x] Migration: `cases`, `case_proposals`, `case_decisions` tables
- [x] Migration: `review_notes.body` column (+ backfill plan n/a, new table)
- [x] Migration: `last_seen` table (actor_id, entity_type, entity_id, seen_at), no trigger
- [x] `alembic check` clean after each migration (against throwaway local Postgres)
- [x] `proofline/analysis/grouping.py`: `root_cause_key()`, finding-to-case matching
- [x] `proofline/actions/cases.py`: `sync_cases_from_findings`, all C1 transitions (pick_up, ask_client, client_answered, submit_proposal, return, approve, partner_approve, partner_return, clear, reopen, reassign), resolution-type validators
- [x] `proofline/security/permissions.py`: C1 rules added to `check_permission`
- [x] `proofline/actions/service.py`: new `_HANDLERS` entries wired through `perform()`
- [x] `proofline/actions/review_notes.py` + `db/models.py`: `body` stored in current state
- [x] `proofline/db/repository.py`: `record_last_seen`, `get_last_seen`
- [x] `routes/cases.py`: `GET /api/cases` (tabs/grouping/counts), `GET /api/cases/{id}`, one POST per C1 action
- [x] `routes/actors.py`: `GET /api/actors` for the role switcher
- [x] `db/rebuild.py`: replay handlers for every new case event + `review_notes.body`
- [x] `changed_since_last_seen` + `change_summary` wired into queue/case responses (area/document land in Step 6-7)
- [x] Tests: one per C1 transition row (`test_action_cases.py`, 44 tests), resolution-type validation, root-cause grouping/clearing, rebuild fidelity, leak scan extended to `/api/cases` and `/api/actors`
- [x] `web/package.json`: add `openapi-typescript` devDependency
- [x] `web/lib/api-types.ts` generated from running API's OpenAPI schema (via `api/export_openapi.py` + `npm run gen-api-types`)
- [x] `web/lib/api-client.ts`, `web/lib/session.ts` (X-Proofline-Actor, localStorage role switcher via `useSyncExternalStore`)
- [x] App shell: `web/app/layout.tsx`, left rail, top bar, role switcher, keyboard layer, command menu, Trace-drawer slot (slot established, drawer UI itself is Step 6)
- [x] `web/app/queue/page.tsx` (S1) -- tabs, severity groups, J/K/Enter/Esc//, list+detail split with URL-reflected selection
- [x] `web/app/cases/[id]/page.tsx` (S2) -- full page wrapping the shared `CaseDetailPanel`
- [x] Extra API routes added to support the shell/screens: `GET /api/actors`, `GET /api/return`, `GET /api/cases/{id}/activity`
- [x] `npm run typecheck` and `npm run lint` both clean (one lint rule, `react-hooks/set-state-in-effect`, downgraded to warn -- see DECISIONS.md)
- [x] Verified with a real dev server (uvicorn + `npm run dev` against the throwaway Postgres): fonts load, `/api` rewrite works, queue/case pages render, `/api/cases/sync` against the real packet produces the 4 expected cases (incl. RSU tax effect 15,535.56/1,619.08 matching ERRORS.md) with no duplication on rerun
- [x] Playwright script: screenshots + W1 click-count for Daniel's RSU approval (npx, not a package.json dep) -- `screenshots.js`, run successfully against the real dev servers (chromium-1208, the complete cached build; chromium-1148's cached copy turned out to have a corrupt/partial framework)
- [x] Step 5 done-when: every C1 transition tested, W3 holds, screens render per UX -- confirmed visually via Playwright screenshots

### Step 6: tracing and source documents
- [x] `routes/trace.py`: `GET /api/trace/line/{key}` with full S4 payload (calculation stack, highlight boxes, excluded docs)
- [x] `routes/documents.py`: `GET /api/documents/{id}` rendered pages + highlights + landed-in
- [x] `web/components/TraceDrawer.tsx` + `web/app/trace/line/[key]/page.tsx` (S4)
- [x] `web/app/documents/[id]/page.tsx`
- [x] `web/components/TraceableNumber.tsx` shared component, used everywhere a number renders
- [x] Extend leak-scan test to every new rendered page/endpoint (W2)
- [x] Step 6 done-when: W2 holds, leak scan covers every rendered page

### Step 7: areas, sign-off, calculation, documents, large detail (C2, C3, C4)
- [x] Migration: `sign_offs`, `adjustments`, `document_dispositions` tables (`f1a9c6d2e4b7`), `claim_verifications` table (`066bc41a1488`, new this session -- see DECISIONS.md)
- [x] `proofline/analysis/calculation.py`: C3 `workpaper_value()` (exact/estimate/what-if/adjusted labeling) -- proven against the real A1 RSU scenario
- [x] `proofline/actions/sign_offs.py`: `sign_off`, `confirm_carryover`, change-pending detection -- wired into `_HANDLERS`/`check_permission` this session; fixed a permanent-block bug, a concurrency race (bare 500 instead of 409, with a new pg-marked test), and two fingerprint gaps (decisions/scope never actually compared) -- see DECISIONS.md
- [x] `proofline/actions/disposition.py`: rule-based proposal (`analysis/disposition.py`, reusing `tracing.py`/`signoff.py`'s existing generic document matching) + `confirm_disposition` action
- [x] `proofline/actions/bulk.py`: `bulk_verify` (all-or-nothing, new `claim_verifications` table) + `undo_bulk_verify` (reversing event)
- [x] `routes/areas.py`: `GET /api/areas/{scope}`, sign-off/carryover/bulk-verify/undo POSTs; `routes/documents.py` extended with disposition fields
- [x] `web/app/areas/[scope]/page.tsx` (S3): blocks, changes+carryover, tie-outs, grouped detail (flat, not grouped by issuer/box -- known gap, see DECISIONS.md), sign-off button with disabled reasons; `web/app/areas/page.tsx` rebuilt as a real scope list (was a Step 5 placeholder)
- [x] `api/tests/acceptance/test_a1_rsu.py` -- full lifecycle, passes
- [x] `api/tests/acceptance/test_a2_corrected_1099.py` -- full lifecycle, passes
- [x] Step 7 done-when: A1 and A2 pass

### Finish
- [x] `pytest api -q -m "not eval"` x2 -- 410 passed, 8 skipped (pg), both times, no flakiness
- [x] pg-marked tests against the throwaway local Postgres (`/tmp/proofline_test_pg:55432`) -- 8 passed, incl. the new sign-off race test (run 3x, no flakiness)
- [x] `npm --prefix web run typecheck`, `npm --prefix web run lint` -- both clean (one pre-existing downgraded-to-warn rule, four instances incl. the new `AreaDetail.tsx`)
- [x] `alembic -c api/alembic.ini check` against test database -- no drift
- [x] Playwright screenshots: queue (Daniel), RSU case (Daniel), SSN case (Marcus), trace drawer F1040.1a, D31 document page, Investments area, areas list -> `/tmp/proofline_screenshots/` (not committed into `docs/screenshots/` since nothing is committed this session)
- [x] Compared screenshots against `docs/UX.md` -- renders correctly; one known gap (flat detail table, not grouped by issuer/box) logged in DECISIONS.md rather than fixed under time pressure
- [x] Ran `reviewer` agent -- found 3 real issues (`confirm_carryover` validated nothing about the document pair it confirmed, `undo_bulk_verify` could clobber an unrelated later re-verification, `confirm_disposition`'s lazy row-creation had the same uncaught-`IntegrityError` race class as `sign_off`'s), all fixed with new regression tests (two unit, one new pg-marked concurrency test) and logged in DECISIONS.md
- [x] Ran `/deep-test` (focused on Step 7 per the skill's own "if empty, test everything" framing) -- found and fixed 2 real correctness gaps (fingerprints never wired to real data) and 1 real concurrency bug (uncaught IntegrityError -> bare 500), all logged in DECISIONS.md with new regression tests
- [ ] Run `/simulate rsu corrected-1099 bulk-undo role-abuse leak-scan` against test database -- **not run this session**, time/scope cut; A1/A2 already cover rsu/corrected-1099 as automated tests, and leak-scan/role-abuse are covered by `test_leak_scan.py`/`test_permissions.py`, but the formal `/simulate` skill pass and `docs/SIMULATION_REPORT.md` are still open
- [ ] Write `docs/SIMULATION_REPORT.md` -- blocked on the above
- [x] Update `docs/TODO.md`, `docs/DECISIONS.md`, `docs/AI_USAGE.md`
- [ ] Report migration command for the demo database; do not commit -- see end-of-session report

### Blocked
- `/simulate rsu corrected-1099 bulk-undo role-abuse leak-scan` and `docs/SIMULATION_REPORT.md` -- not run this session (time/scope cut after the deep-test pass found and fixed real bugs that took priority). The individual scenarios are substantially covered by existing automated tests (A1/A2 acceptance tests, `test_leak_scan.py`, `test_permissions.py`, the new bulk-verify/undo tests), but the formal simulate pass and its write-up haven't happened.
- Area page large detail is a flat table, not grouped by issuer and box with an expand-to-lots summary row (docs/UX.md S3) -- functionally complete, confirmed via Playwright screenshot against the real Investments scope (300+ rows render correctly, trace/verify/bulk-verify all work), but not the compact grouped view the spec describes. See DECISIONS.md.
- `confirm_carryover` doesn't independently verify "the source isn't weaker, and no judgment points at the old document" (CONTRACTS.md C2) -- trusts the reviewer's own judgment when they call it. See DECISIONS.md.
- A broken tie-out is surfaced as a blocking reason but doesn't automatically open a case / reopen the scope (CONTRACTS.md C2). See DECISIONS.md.
- The area page's "Changes" tab shows only changes since the last sign-off, not the full v1→v2→v3 history docs/UX.md describes.
- "Nobody signs a scope that contains their own adjustment" (CONTRACTS.md C2) only actually fires for scope "investments" -- `line_claim_identity` only resolves Form 8949 lot claims today, so every other scope's own-adjustment check is a silent no-op. See DECISIONS.md.

## Now: Step 8, readiness, the filed-record package, and the post-filing timeline

### Step 8: readiness (C5), the package, authorization, submission, the filed record (I6)
- [x] `proofline/analysis/readiness.py`: 8 derived items (reusing `changes_since_sign_off`, `get_latest_sign_off`, `get_document_disposition`, `list_cases`/`list_review_notes` -- no re-decided logic) + 4 attestation items read back from their own events, each with a named reason when unmet
- [x] `proofline/actions/readiness.py`: `confirm_readiness_item` (log-only, staff-only, closed item list)
- [x] `proofline/analysis/filing.py`: `build_package` (lines with provenance labels, sign-off versions, active adjustments, document ids + content hash, amounts/identity fingerprints, a combined `reference`), `identity_fingerprint` (new; honors an adjustment on a household SSN/name claim), `document_content_hash` (sha256 over sorted `printed_content` pages), `resolved_line_value` (narrow SchC.1-shaped workaround, see DECISIONS.md), `letter_566_pack` (reads the notice and its items from the packet, traces each to a line generically, reconciles from the already-adjusted workpaper value)
- [x] `proofline/actions/filing.py`: `authorize_filing` (client or staff-on-client's-behalf, PINs required for every signing role, builds the package itself rather than trusting the caller's fingerprints), `submit_filing` (staff-only, refuses unless the submitted `package_reference` is exactly the latest authorization's -- the one rule that covers both "identity changed" and "amounts changed, no threshold")
- [x] Migration `9c3a7f2b5e1d`: `filed_records` table + its own refuse-UPDATE/DELETE/TRUNCATE trigger, mirroring `60f9607200ec`
- [x] `db/rebuild.py`: replay handler for `filing_submitted` -- only an accepted result leaves a `FiledRecord` row, using the id the event itself carries
- [x] `routes/readiness.py`: `GET /api/readiness`, `POST /api/readiness/{item}/confirm`
- [x] `routes/filing.py`: `GET /api/filing/package`, `POST /api/filing/authorize`, `POST /api/filing/{jurisdiction}/submit`, `GET /api/filing` (authorization/submission history + filed records, with the same reveal-and-log treatment as a document page for a cleared actor seeing a PIN), `GET /api/filing/letter-566`
- [x] `security/permissions.py`: `confirm_readiness_item` (staff only), `authorize_filing` (client or staff), `submit_filing` (staff only)
- [x] No new frontend screen -- Step 8's plan entry doesn't list one (unlike Steps 5-7), so this step stayed API + actions + migration; noted in DECISIONS.md
- [x] `docs/CONTRACTS.md` C5 "still open" resolved: Publication 1345 requires re-signing for identity OR amounts changes, no threshold; enforced generically via `package_reference` equality rather than special-casing which fingerprint changed

### Tests
- [x] `test_analysis_readiness.py`, `test_analysis_filing.py`, `test_action_readiness.py`, `test_action_filing.py`, `test_routes_readiness.py`, `test_routes_filing.py` -- 99% line coverage on the six new modules (one deliberately-untested defensive branch, same as Step 4's `get_engine()`)
- [x] `test_permissions.py`, `test_rebuild.py`, `test_leak_scan.py` extended for the three new actions/routes, including a leak test that authorizes with the real PINs and confirms they never reach an uncleared actor
- [x] `api/tests/acceptance/test_a3_efile_rejection.py`: the full A3 scenario against the real packet -- F1 rejected with the packet's own R0000-504-02 and kept, never filed; the SSN corrected through the normal case-resolution pipeline (no SSN-specific code); F2 has the same amounts fingerprint and a new identity fingerprint; F2 accepted for both jurisdictions, exactly one filed record each; the Letter 566 pack's reconciliation lands at 151,300 once E3 is resolved, not 142,000 + 12,400
- [x] `api/tests/pg/test_filed_records_immutable.py` (I6): written, modeled directly on `test_events_immutable.py`'s proven pattern -- **could not be run against a real Postgres this session**, same `TEST_DATABASE_URL` gap noted at the end of Step 7 (still only `DATABASE_URL` etc. in `.env.local`); a local Postgres start was attempted and denied by the sandbox. Needs a Neon test branch or local Postgres before it can actually run
- [x] `pytest api -q -m "not eval"` -- 492 passed, 13 skipped (9 pre-existing `pg` skips + 4 new), run twice both before and after the reviewer-driven fixes below, no flakiness
- [x] `alembic -c api/alembic.ini heads`/`history` -- single head, clean chain; `alembic check` itself needs a real database connection and is blocked on the same `TEST_DATABASE_URL` gap
- [x] `PYTHONPATH=api python3 -m proofline.checks.baseline` -- unchanged, 4/4 recall, 1.00 precision
- [x] Ran `reviewer` agent against the whole change -- found 3 real issues (a PIN leak for any PIN not already in the packet's own timeline text, `readiness.py` missing a decisions-fingerprint comparison so a resolved-but-unsigned-for adjustment could read as "no pending change," and `build_package` disagreeing with `letter_566_pack` about an adjusted `return_total` line's value), all fixed with regression tests; see docs/DECISIONS.md
- [x] Ran `/deep-test` -- rule-to-test map for C5/I6, coverage (98% across the touched Step 8 + consolidated signoff modules), `pytest` x2, baseline, rule-breaker greps (no hardcoded packet values, no raw SQL outside `db/`, every route redacted), edge cases -- found and fixed a real gap of its own (submitting "accepted" twice for the same jurisdiction silently wrote a second `FiledRecord`; fixed with a unique index + a check, see docs/DECISIONS.md)
- [ ] `/simulate efile filing-guard season` -- **not run this session**: the skill itself refuses model invocation ("reserved for explicit user invocation"), unlike Step 7's gap this isn't a missing credential, it needs the user to type `/simulate efile filing-guard season` themselves

### Blocked
- The `pg`-marked tests (`test_filed_records_immutable.py`, plus the pre-existing I6/I7/concurrency suite, now also a filed-record accept-race test) still can't run: `TEST_DATABASE_URL` isn't in `.env.local`, and starting a local throwaway Postgres this session was denied. Needs the user to either add a Neon test branch URL or allow a local Postgres start.
- `/simulate` needs the user to run it directly -- the Skill tool refuses to invoke it on the model's behalf.
- "Diagnostics resolved" (one of C5's firm 12 steps) isn't a readiness item -- the packet's `ReturnVersion.diagnostics` field isn't wired into cases or anywhere else yet, and the Step 8 prompt's own item breakdown didn't include it either. See DECISIONS.md.
- `build_package`'s adjustment-awareness (and `letter_566_pack`'s) covers a directly-adjusted `return_total` line itself, not propagation through a dependent R-SUM/R-CARRY chain (e.g. total income summing over an adjusted SchC.1) -- `workpaper_value`'s own recursion still isn't `return_total`-aware at every level, only `line_claim_identity`'s F8949 case propagates that way today. See docs/DECISIONS.md.

## Now: Step 9, everything else the brief asks for

Design call made up front (see docs/DECISIONS.md for the full reasoning): nothing
in this step needs a new table or a migration. Time entries, judgments/elections
and outside-filing decisions are all append-only facts nobody edits or CASes
against -- modeled as log-only events (`confirm_carryover`/`confirm_readiness_item`'s
own pattern), read back by replaying each entity's own events, exactly like a
readiness attestation item already does. Everything else (notifications,
versions diff, what-ifs, search, the record views) is a read computed from
data that already exists.

### Part A: packet modeling (api/proofline/packet.py)
- [x] Typed `firm.assignment_at_start`, `firm.deadlines`, `firm.budget_hours`, and a new `firm.starter_standards` (with `variance_review`), per packet-explorer's confirmed shapes
- [x] Typed `Asset.disposition` (was silently dropped before -- no other prior_years/tax_agency_records sub-shape needed typing; R07/R08/R10/R15/R16 read them generically as loose dicts)

### Part B: live updates, notifications, "since you last looked" (B14, B26)
- [x] `proofline/analysis/changes.py`: extracted `cases_needing_actor` from `routes/cases.py`'s private `_needs_me`; `routes/cases.py` now calls the moved function
- [x] `proofline/analysis/notifications.py`: `notifications_report(session, packet, actor)`
- [x] `routes/notifications.py`: `GET /api/notifications`, staff + AI assistant only
- [x] `web/app/activity/page.tsx`: real notifications feed (needs-me, changed, deadlines)

### Part C: time against budget (B37)
- [x] `proofline/actions/time_tracking.py`: `log_time`, staff-only
- [x] `proofline/analysis/time_tracking.py`: `AREA_TO_BUDGET_KEY`, `hours_logged_by_area`, `time_budget_report` -- reads `firm.budget_hours` directly, no hardcoded figure
- [x] `routes/time.py`: `POST`/`GET /api/time`
- [x] `AreaDetail.tsx`: a "Time against budget" section per area with a log-time form

### Part D: search (B38)
- [x] `proofline/analysis/search.py`: `search(packet, session, query)` over cases/lines/documents/notes; document snippets always redacted, even for a cleared actor (decision logged)
- [x] `routes/search.py`: `GET /api/search?q=...`, staff + AI assistant only
- [x] `web/components/CommandMenu.tsx`: wired to the real endpoint, debounced, grouped results routed to the right screen

### Part E: comparing versions (B15)
- [x] `proofline/analysis/version_diff.py`: `diff_versions(packet, session, from_version, to_version)` over any pair of v1/v2/v3/`workpaper`
- [x] `routes/versions.py`: `GET /api/versions/diff?from=...&to=...&only_changed=...`
- [x] `web/app/return/page.tsx`: version-diff tab, filterable to only changed

### Part F: what-ifs (B16)
- [x] `routes/versions.py`: `GET /api/what-ifs` -- the packet's five named alternatives alongside the current workpaper value
- [x] `web/app/return/page.tsx`: what-ifs tab, side-by-side with current values

### Part G: judgments and elections (B19) + Form 8867
- [x] `proofline/actions/judgments.py`: `record_judgment_election`, staff-only; validates `what_if_id` against the packet when `is_election`
- [x] `proofline/analysis/judgments.py`: `list_judgments(session)`
- [x] `proofline/analysis/due_diligence.py`: `due_diligence_checklist(packet)` -- the packet has no itemized checklist at all (confirmed by packet-explorer), so this surfaces the firm's own due-diligence rule text and the engine's `F8867.status` line, generically matched; "done" is still the existing `due_diligence_done` attestation
- [x] `routes/judgments.py`: `POST`/`GET /api/judgments`, `GET /api/due-diligence`
- [x] `web/app/judgments/page.tsx`: judgments list + form, due-diligence checklist, outside filings (folded in, see Part H)

### Part H: outside filings (last C5 condition, B20)
- [x] `proofline/analysis/outside_filings.py`: `outside_filing_items(packet)` found generically (fixed diagnostic codes, text patterns in the prior preparer's open items and `household.related_returns`) -- confirmed against the real packet to find exactly the four named items (fbar, contractor_1099_nec, form_3520_2023, oregon_composite); `outside_filings_report`
- [x] `proofline/actions/outside_filings.py`: `confirm_outside_filing`, staff-only
- [x] `proofline/analysis/readiness.py`: added `_outside_filings_decided` to `readiness_report`
- [x] `routes/outside_filings.py`: `GET /api/outside-filings`, `POST /api/outside-filings/{item}/confirm`
- [x] `web/app/judgments/page.tsx`: outside-filings section with owner + status (folded in rather than a separate route)

### Part I: the client workspace (S5, B27, B31, W4)
- [x] `security/dependencies.py`: `require_non_client`, `require_client`
- [x] Retrofitted `require_non_client` onto every pre-existing staff-surface GET route: `areas`, `cases` (reads), `documents`, `trace`, `readiness`, `review-notes`, `checks`, `filing` (package/status/letter-566 -- not `authorize_filing`)
- [x] `proofline/analysis/client_workspace.py`: `client_summary`, `client_questions`, `client_documents`, `client_changes`, `client_package_summary`
- [x] `routes/client.py`: `GET /api/client/summary|questions|documents|changes|package`, all `require_client`; signing is the existing `POST /api/filing/authorize`
- [x] `web/app/client/page.tsx`: summary/questions/documents/sign tabs; `AppShell`'s left rail swaps to a client-only nav for the `client` role
- [x] W4 as a test (see Tests below)

### Part J: the sixteen CPA record views (R01-R16)
`routes/records.py` + `analysis/records.py`, reusing an existing module directly wherever a view is "the same thing already built, surfaced as a report." One generic frontend renderer (`web/components/JsonValue.tsx`) instead of sixteen bespoke layouts (decision logged).
- [x] R01 return summary vs last year -- `prior_years.return_2024.lines` vs. v3, flagged by the packet's own `firm.starter_standards.variance_review`
- [x] R02 tax computation -- `scope_lines`/`workpaper_value`
- [x] R03 area summaries -- tie-outs, open case count, sign-off version, time used
- [x] R04 document index -- disposition, `trace_document`'s "landed in"
- [x] R05 depreciation by asset -- federal/california/amt, the condo sale's Form 4797 recapture (needed the new `Asset.disposition` field)
- [x] R06 sales detail -- reuses the new public `scope_detail_rows` (moved out of `routes/areas.py`)
- [x] R07 books to tax -- D14's books lines + every `SchC` line with a non-null `note` as the adjustment
- [x] R08 rentals and passive losses -- `SchE.*`/`F8582.*` lines, prior-year `F8582.unallowed.*`, carried-out passive amounts
- [x] R09 K-1 lines -- every K-1 document's extracted boxes mapped to the lines whose `sources` cite them (provenance resolver, not a hardcoded box table)
- [x] R10 retirement and foreign items -- `F8606`/`F8889`/`F8938` lines, SEP (`Sch1.16`), every `*_sek` extracted value, the FBAR outside-filing status
- [x] R11 deductions and credits -- `SchA`/`F8283`/`F8812` lines, the standard-deduction parameter
- [x] R12 payments -- reuses the now-public `federal_estimated_payments_posted`/`california_estimated_payments_posted`
- [x] R13 state split -- every line with `jurisdiction == "california"`, plus residency dates
- [x] R14 carryovers -- `prior_years.carryovers_into_2025` in, `ReturnVersion.carryovers_out` out
- [x] R15 basis by year -- `prior_years.basis_records`; a real gap (`None`) passes straight through
- [x] R16 prior preparer vs. what we changed -- the packet has no line-level prior-preparer data to diff (confirmed by packet-explorer), so this matches each open item against judgments/outside-filing decisions by word overlap instead, rather than forcing the version-diff shape onto data that isn't line-shaped
- [x] `web/app/records/page.tsx`: one view selector + the generic renderer

### Tests
- [x] Unit tests for every new action/analysis/route (`test_action_time_tracking.py`, `test_analysis_time_tracking.py`, `test_routes_time.py`, `test_action_outside_filings.py`, `test_analysis_outside_filings.py`, `test_routes_outside_filings.py`, `test_action_judgments.py`, `test_routes_judgments.py`, `test_routes_notifications.py`, `test_routes_search.py`, `test_routes_versions.py`, `test_routes_client.py`, `test_routes_records.py`), plus new `test_permissions.py` cases for `log_time`/`record_judgment_election`/`confirm_outside_filing`
- [x] Role/permission test proving a client actor gets 403 on every retrofitted staff-surface route (`test_staff_surface_routes_blocked_for_client`), the reverse guard for staff on `/api/client/*` (`test_client_workspace_routes_blocked_for_staff`), and a leak-scan pass over the client workspace itself (`test_client_workspace_never_leaks`)
- [x] W4 as an automated acceptance test (`api/tests/acceptance/test_w4_client_workspace.py`)
- [x] `pytest api -q -m "not eval"` x4 total this session (607 passed, 13 skipped three of the four times; one isolated flake in `test_rebuild_matches_a_full_case_lifecycle`, pre-existing and unrelated to Step 9 -- passed immediately on its own retry and on two subsequent full-suite reruns; not a file this session touched. See DECISIONS.md), `npm --prefix web run typecheck` and `npm --prefix web run lint` both clean
- [x] `ruff check .` -- only pre-existing `B008` noise (FastAPI's `Depends(...)` default pattern, present codebase-wide before this step); the three real findings this step introduced (two import-order, one unused import) fixed
- [x] Verified live against a real `uvicorn` process (SQLite-backed, see DECISIONS.md) + the real `npm run dev` Next.js server, with Playwright screenshots of activity (needs-me/changed/deadlines), return (version diff showing the real M14 box-move, what-ifs showing all five alternatives), judgments (due-diligence + all four outside filings), records (R01 and R05, incl. the new `Asset.disposition` recapture data), the area page's new time-against-budget section (4.0 real hours from the packet), and the full client workspace including the sign screen's two fingerprints -- every screen rendered real data correctly
- [ ] Update `docs/AI_USAGE.md`
- [ ] `/deep-test`, then `/simulate` covering the client-workspace leak scan specifically -- `/simulate` needs the user to type it themselves (the skill refuses model invocation, same as Steps 7-8)

## Step 10: the AI layer

### Part 0: Step 9 fix
- [x] `routes/household.py`, `routes/return_info.py`: `require_non_client` instead of a bare `get_current_actor`
- [x] `web/components/AppShell.tsx`: skip the `/api/return` fetch for the client role (it's now staff-surface)
- [x] Regression tests: `test_household_and_return_are_staff_surface_not_client` (`test_routes.py`), extended `_STAFF_SURFACE_GET_ROUTES` leak-scan sweep

### Part 1: the Evidence Investigator
- [x] Dependencies: `pydantic-ai-slim[groq]==1.30.1`, `mcp==1.30.0`, `deepeval==4.3.1`, `langfuse==4.15.6` (plus pinned `sse-starlette`/`opentelemetry-*` to keep them compatible with the existing `fastapi==0.119.1`/`pydantic==2.11.9` pins -- see DECISIONS.md)
- [x] `proofline/ai/tools.py`: `trace_claim`, `open_case`, `read_evidence`, `find_related_documents` -- thin wrappers over the existing route functions
- [x] `proofline/ai/schema.py`: `InvestigatorSuggestion`
- [x] `proofline/ai/investigator.py`: the Pydantic AI agent, Groq model, usage limits, deps, `AI_INVESTIGATOR_ENABLED`
- [x] `proofline/ai/validator.py`: deterministic citation/number/role-transition validation
- [x] `proofline/ai/events.py`/`suggestions.py`: `ai_suggestion_recorded` / `ai_suggestion_reviewed` events (no migration needed)
- [x] `POST /api/cases/{case_id}/investigate`, `POST /api/cases/{case_id}/suggestions/{id}/review`, suggestions surfaced on `GET /api/cases/{case_id}` (`ai_suggestions`)
- [x] New `trigger_investigation`/`review_ai_suggestion` staff-only permissions; negative permission tests for the `ai_assistant` role across every write action in `permissions.py`

### Part 2: MCP server
- [x] `proofline/ai/mcp_server.py` exposing the same four tools, same role/masking
- [x] In-process test driving it with the SDK's own memory transport (`test_ai_mcp_server.py`)

### Part 3: Langfuse tracing
- [x] `proofline/ai/tracing.py`: wraps the investigator's run; no-ops cleanly with no keys set or on any Langfuse failure; redacts through `redact_for_actor`

### Part 4: golden set, baseline, DeepEval gate
- [x] `api/eval/golden_cases.py` from ERRORS.md E1-E4 plus two of E5/E9 (digital asset lot, handwritten receipt), with a real distractor (D63 vs D64) -- sanity-checked against the real packet and validator in `test_ai_golden_cases_sanity.py` (24 passed, no model needed)
- [x] Baseline recall for the deterministic checks against the golden set (`test_baseline_recall_on_golden_set`, passes with no key: checks catch E1-E4, catch neither E5 nor E9)
- [x] Hard-gate test, judge calibration (10 real hand-labeled cases), judge metrics (Faithfulness + "new-hire usefulness" GEval via a Groq-backed judge) all built in `api/eval/test_investigator_eval.py` -- **could not be executed this session, no GROQ_API_KEY available** (confirmed: skip cleanly with reason "GROQ_API_KEY not set", 1 passed / 14 skipped, no hang)
- [x] Ship decision: `AI_INVESTIGATOR_ENABLED` defaults `false`; stays `false` -- not because it failed, but because it was never run. See docs/DECISIONS.md
- [x] All of Part 4 marked `eval`, skipping cleanly with no `GROQ_API_KEY`/`LANGFUSE_*`

### Tests
- [x] `pytest api -q -m "not eval"` (run from the repo root): 701 passed, 13 skipped, 15 deselected (the eval suite)
- [x] `pytest api/eval`: 1 passed, 14 skipped (all with an explicit "GROQ_API_KEY not set" reason)
- [x] Update `docs/AI_USAGE.md`

## Queue usability refinement (S1/S2) -- not a numbered plan step, a targeted UX pass
- [x] Batch 0: Vitest + Testing Library added to `web/` (devDependencies only, `test` script)
- [x] Batch 1: `GET /api/trace/evidence?ref=` in `routes/trace.py`, reusing `resolve()`/`_position_dict`; tests
- [x] Batch 2: Trace drawer generalized to a `DrawerTarget` union; new `EvidenceContent.tsx`
- [x] Batch 3: Case Detail evidence refs are clickable; proposal evidence picker replaces free text
- [x] Batch 4: status stepper replaced with current-status + next-action; `docs/UX.md`/`docs/DECISIONS.md` updated
- [x] Batch 5: Queue row layout simplified for the split pane
- [x] Batch 6: loading/error+retry/empty-queue/no-search-results states on Queue and Case Detail
- [x] Batch 7: keyboard shortcuts respect `isTypingTarget` (incl. SELECT) and `shortcutsEnabled()`
- [x] Batch 8: group totals recomputed from visible rows, not the unfiltered server total
- [x] Verification: `tsc`, `vitest`, `pytest api -q -m "not eval"`, Playwright screenshots at 1440/1280/768px -- all pass; live-browser verification of the evidence drawer, proposal picker, error/retry, empty/no-results states and the keyboard fix (see docs/DECISIONS.md)

## Questions still open
- Does the packet go into the public repo, or load from Vercel Blob?
- Step 5 will need a way to read a review note's actual text back (body currently lives only in its `review_note_added`/`review_note_responded` events, never on the `review_notes` current-state row) -- flagged by the reviewer agent, not a Step 4 defect since there's no screen yet to show it on.
