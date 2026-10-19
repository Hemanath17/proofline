# How AI was used

## Tools
- Claude (chat): design partner for the core model, the blueprint diagrams, the build spec and the scenario simulations; also ran the packet queries behind every number in `docs/ERRORS.md`
- ChatGPT: second opinion that criticized the design; several of its points were adopted
- Claude Code: builds the app from `docs/PLAN.md`, with project rules, hooks, skills and subagents in `.claude/`

## What I decided or corrected
- Required discussion before any design or file; rejected an early switch of the front-end framework
- Pushed for an authentic CPA workflow and judged each idea from the user's side
- Rejected a materiality threshold: any change to an approved value counts
- Challenged area-wide reopening, which led to delta approval
- Challenged carrying approvals over when only the evidence changed, which led to the relied-on-field rule
- Chose Pydantic AI for the investigator and asked for evaluation with DeepEval

## AI mistakes caught
- Wrong roles for staff (corrected against the packet)
- Overstated errors before they were checked
- An AI explanation test showed valid citations alongside unsupported claims in 4 of 10 cases, which is why a person checks meaning

## Measured result
- AI explanations of findings helped in 3 of 10 real cases; not built. Evidence: the ten-case test in the design notes

## Step 1 (Claude Code)
- Scaffolded `web/` (Next.js) and `api/proofline/` (FastAPI: `db/connection.py`, `db/models.py`, `db/repository.py`, `routes/health.py`, `routes/events.py`), wrote the first Alembic migration for the `events` table, and wrote offline pytest coverage (in-memory SQLite, no network) for the repository and routes
- Researched Vercel's current Services/Functions/env-var docs via its own skills before writing `vercel.json`'s `functions.excludeFiles`, rather than guessing the config shape
- Deployed to a new Vercel project (`proofline`, team `deployapps`), ran the migration against the real Neon database, wrote and re-read a proof event across a redeploy, and measured cold-start time, all without ever printing `DATABASE_URL`
- I flagged, and the user confirmed, that the Step 1 events endpoints are throwaway and must be replaced by the real action service in Step 4

## Part 0 + Steps 2-3 (Claude Code)
- Fixed seven config files still pointing at the pre-`proofline`-package layout (`.claude/rules/checks.md`, the add-check and add-endpoint skills, `format.sh`, `settings.json`, `connection.py`'s `.env.local` path), shown as a diff before any Step 2 code
- Used the packet-explorer agent to learn the packet's actual shape before designing `proofline/packet.py` and `proofline/provenance/`, rather than guessing from `docs/PACKET.md` alone -- five of its findings (no line-to-extracted-value link in that direction, lot prefixes not unique across documents, no structured document-duplicate field, `tax_effect_rates` per version not under `engine_reference`, `what_if`'s ids on `alternatives[].id`) directly reshaped the design. Validating the Pydantic models against the real packet immediately caught two more wrong assumptions (`Line.value` and `Person.own_income` aren't always numeric) before they could propagate
- Built the claim-identity table from `docs/CONTRACTS.md` as functions, adapting the 1099-B lot key (issuer + lot id, not issuer + account + lot id -- no structured account field exists in this packet) and flagged that adaptation rather than deciding it silently
- Designed the "D10 is excluded from F1040.1a" result to be found from data (same issuer/type as a primary source, contributing to no line) instead of checking for the literal id "D10", then verified the real packet actually produces that result
- Wrote four checks for the confirmed errors (E1-E4); for E2 and E3 the computed tax-effect estimates matched `docs/ERRORS.md`'s hand-written numbers (~15,536/~1,619 and ~4,402) before I ever looked at those numbers again, which is the kind of agreement that's worth noting rather than assuming
- Ran the (now correctly registered) `reviewer` agent and `/deep-test` against the combined diff before calling this done

## Step 4 (Claude Code)
- Used the packet-explorer agent to get exact firm/staff/sensitive-value data (roles, `sensitive_data_clearance` booleans, printed/extracted SSN and PIN formats, the lack of any client-user-to-household-person link in the packet) before designing the roles and redaction modules, rather than guessing from `docs/PACKET.md` alone
- Asked the user two data-model questions the contracts don't cover before writing code: whether clients ever get clearance for their own sensitive values (no, not in Step 4), and who may resolve a review note (the user specified real review-note practice directly: reviewer/partner/quality_reviewer raise, any staff responds, only the author or partner resolves -- reshaping the planned action set to add a `respond_review_note` action that wasn't in the original plan)
- Caught and fixed, by testing against an actual SQLite-backed `TestClient` and a real local Postgres instance rather than trusting the design on paper: a `Decimal`-in-payload crash (the reason `proofline/db/canonical.py` exists), a SQLite-in-memory-plus-threadpool bug where `TestClient` requests saw an empty database, a case where SQLAlchemy's bulk-UPDATE session sync silently applied some but not all of a multi-column `SET` to an already-loaded object, and a model/migration drift (`alembic check`) on the `review_notes` about-type/about-id index that the migration created but the SQLAlchemy model didn't declare
- Verified the three new migrations and the edited `downgrade()` end to end (upgrade, downgrade, upgrade again, `alembic check`) against a throwaway local Postgres instance it started and tore down itself, specifically to avoid touching the demo database before the user says so, while still proving the migrations actually work against real Postgres rather than only against the SQLite test fixtures
- Flagged, rather than silently deciding, that `TEST_DATABASE_URL` isn't set in `.env.local`, so the new `pg`-marked tests (I6, I7, concurrency) are skipped in a normal `pytest` run; they were verified by hand this session but need a Neon test branch or local Postgres configured to run as part of normal testing going forward
