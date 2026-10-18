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

## Questions still open
- When does a corrected return need a new client signature? (Check IRS Publication 1345.)
- Does the packet go into the public repo, or load from Vercel Blob?
