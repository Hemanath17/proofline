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
