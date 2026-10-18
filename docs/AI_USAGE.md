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
