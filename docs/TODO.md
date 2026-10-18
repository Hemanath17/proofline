# To do

## Done
- [x] Design: the blueprint (15 diagrams), the build spec (74 decisions), three scenarios run on paper
- [x] Step 0: repo set up with CLAUDE.md, contracts, packet guide, errors, acceptance tests and decisions

## Now: Step 1, prove we can deploy
- [ ] Next.js app in `web/`
- [ ] FastAPI app in `api/` with `/api/health`
- [ ] Root `vercel.json` with both services; check the live link
- [ ] Neon database, with `DATABASE_URL` in `.env.local` and in Vercel
- [ ] `alembic init` and an `alembic.ini` that works from any folder
- [ ] First migration: the events table with `schema_version`
- [ ] Write an event, read it back, redeploy, and read it again
- [ ] Keep tests and fixtures out of the Python bundle
- [ ] Note the cold-start time

## Questions still open
- When does a corrected return need a new client signature? (Check IRS Publication 1345.)
- Does the packet go into the public repo, or load from Vercel Blob?
