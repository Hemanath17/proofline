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

## Questions still open
- When does a corrected return need a new client signature? (Check IRS Publication 1345.)
- Does the packet go into the public repo, or load from Vercel Blob?
