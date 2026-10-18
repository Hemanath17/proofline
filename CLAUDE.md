# Proofline

<!-- Note to self: keep this under ~150 lines. If a line wouldn't stop Claude from
     making a real mistake, it doesn't belong here. Details live in docs/ and .claude/rules/. -->

We're building a web workpaper for one household's 2025 tax return (the Okafor-Lindqvist
case study from MiraFlores AI). The software has already read the documents and computed
the return. Our job is to let a CPA team prove it: where every number came from, how it
was worked out, who checked it, and what's still open. A 20-year CPA should trust it more
than what they use today, and a new hire should manage on day one.

## How it's put together
- One Vercel project with two services (see `vercel.json`): `web/` is Next.js (App Router, TypeScript), `api/` is FastAPI with Pydantic v2
- `/api/*` goes to FastAPI, everything else to Next.js. Services is still a Vercel beta. If it lets us down, we split into two Vercel projects and add a Next.js rewrite. No files need to move
- Neon Postgres through SQLAlchemy 2.0, with Alembic for schema changes. Attachments go to Vercel Blob
- Tests: pytest for Python, `tsc` for the front end. AI evaluations use DeepEval and are marked `eval`
- AI comes in only at plan step 10: Pydantic AI for the Evidence Investigator, a Groq model, Langfuse for traces

## Commands (from the repo root)
```bash
pip install -r api/requirements.txt                    # Python dependencies
uvicorn index:app --app-dir api --reload --port 8000   # API on its own
pytest api -q -m "not eval"                            # every Python test, offline
pytest api/tests/unit/test_<name>.py -q                # one file
alembic -c api/alembic.ini upgrade head                # apply migrations
alembic -c api/alembic.ini check                       # do models and migrations agree?
PYTHONPATH=api python3 -m proofline.checks.baseline    # check precision/recall against docs/ERRORS.md (dev-only: excluded from the Vercel bundle)
npm --prefix web install                               # front-end dependencies
npm --prefix web run dev                               # front end on its own
npm --prefix web run typecheck                         # front-end types
vercel dev                                             # both services, the way they deploy
```

## Where things live
- `web/app/` has one folder per screen: queue, cases, areas, trace, documents, client, firm, eval. Shared pieces are in `web/components/`, and `web/lib/` holds the generated API types, the API client and the session
- `api/index.py` is just the Vercel entrypoint (`from proofline.app import app`)
- All Python code is in the `proofline` package under `api/proofline/`. Import it as `from proofline.<module> import ...`
  - `app.py` and `routes/` are the only places that know about FastAPI
  - `packet.py` is the only code that opens the packet
  - `provenance/` resolves references, claim identity and the dependency graph
  - `checks/` has one file per check, plus the runner and the baseline
  - `analysis/` covers reconciliations, the trust marker, priority, calculation (C3), grouping and readiness (C5)
  - `actions/` has the action service, case transitions (C1), sign-off (C2), disposition (C4), filing (C5) and bulk actions
  - `db/` holds the connection, SQLAlchemy models, repository, migrations and rebuild. Nothing else touches SQL
  - `security/` covers roles, actors, redaction and the view log. `ai/` waits for step 10
- `api/fixtures/`, `api/eval/` and `api/sim/scenarios/` hold expected check results, AI evaluation sets and simulation scripts
- `api/tests/unit/` mirrors the package, `api/tests/contracts/` has one file per contract, and `api/tests/acceptance/` covers the I, A and W items

## Please never
- Change `api/data/packet.json`, or read it whole. It's 1.9 MB, so query it with a small script or ask the packet-explorer agent
- Hard-code a packet value, ID or expected answer into a check (`if ssn == "666-74-3309"` is exactly what not to do). A check is a general rule that should work on any client's packet
- Commit secrets. They live in `.env.local` files and Vercel settings: `DATABASE_URL`, `BLOB_READ_WRITE_TOKEN`, and later `GROQ_API_KEY` and `LANGFUSE_*`
- Send the raw packet to the browser. A response carries only what that role may see, with sensitive values redacted, even inside document text
- Rely on the UI for permissions. The API enforces them, and every unmasked view writes a view-log event
- Change anything except through the action service. It writes the event and the current state in one transaction, or nothing at all
- Update or delete an event or the filed record. Undo is a new event that reverses an old one
- Change the schema except through a reviewed Alembic migration, or write a migration that rewrites past events

## Tax rules that shape the code
- Engine runs v1, v2 and v3 never change. Adjustments sit on top, and we never present the result as a recomputed return
- Every number says how we got it: engine, exact (a plain sum or carry), what-if (from the packet) or estimate (from `tax_effect_rates`). The details are in `docs/CONTRACTS.md` C3
- A claim is identified by the thing itself (the lot, the form box, the asset), not by its line key
- Every check returns a `CheckResult`, either an `error` or a `possible_discrepancy`
- What the client tells us is not verification. Accepting it is a judgment someone records
- The firm's rules: open review notes block filing, nobody reviews their own work, and a tax effect over 1,000 (federal or state) needs the partner
- Every write carries the revision the person saw. If it's stale, return 409 with the current state
- E-file, the client signature and the 2028 IRS letter are replays, so they're labelled "Simulated"
- This is tax work, not auditing. Say "review", "sign-off" and "IRS examination"

## AI, when we get there
- The AI is a user with its own role, "AI assistant". It can read and propose. It can't change a number, close a case, approve or sign off
- That limit comes from the role and the action service, not from the prompt
- AI output is a typed Pydantic object. It goes through the validator and is stored as an AI provenance event
- An AI feature stays off until it passes its evaluation in `api/eval/` and beats the plain checks

## How I'd like us to work
- **Plan first.** Use plan mode for anything touching two or more files, the data model, or a new screen. Read the matching step in `docs/PLAN.md` and the contract in `docs/CONTRACTS.md` first. If a test fails twice for the same reason, stop and rethink rather than patching
- **Use the helpers for their jobs.** Questions about the packet go to packet-explorer, and the reviewer agent looks at a change before it's committed. Run `/deep-test` at the end of each step, and `/simulate` after steps 4, 7 and 8. Don't spin up subagents for small lookups
- **Learn from corrections.** When I correct you, add one line to `docs/LESSONS.md` with the mistake and the rule that would have prevented it
- **Show, don't claim.** For checks and the API, show the pytest output. For screens, run the app, take a screenshot and compare it with the plan. "Should work" isn't an answer
- **Keep it simple.** Before a bigger change, ask whether something simpler does the same job
- **Know what to just fix.** Go ahead on failing tests, type errors, crashes and clear lint errors. Ask me first about product, data-model, UX or scope decisions, new dependencies, migrations, or changes to `docs/PLAN.md` or `docs/CONTRACTS.md`

## Each step, in order
1. Write the step's tasks into `docs/TODO.md` as checkboxes
2. Show me, and wait for my OK
3. Tick tasks off as you go
4. When it's done, tell me in plain words what changed and why, then wait for my OK
5. At the end of a session, update `docs/TODO.md`, `docs/DECISIONS.md` and `docs/AI_USAGE.md`

## Style
- Simple, explicit code: named variables, one step per line, no clever one-liners
- Python: type hints everywhere, Pydantic models for every API input and output, `Decimal` for money
- TypeScript: strict mode. API types are generated from FastAPI's OpenAPI schema, never written by hand
- Touch only the files the task needs, and never weaken or delete a test to get it passing

## Done means
- Tests and type checks pass, and you've shown the output
- The matching items in `docs/ACCEPTANCE.md` pass
- Every number and every simulated event is labelled
- I've said OK

## Worth reading when it's relevant
- `docs/PLAN.md`: the build order and what each step has to deliver
- `docs/CONTRACTS.md`: cases, sign-off, calculation, documents, readiness, claim identity, redaction, storage
- `docs/PACKET.md`: what's in the packet, the reference formats, and facts we've already checked
- `docs/ERRORS.md`: the errors we've confirmed and the leads we haven't
- `docs/ACCEPTANCE.md`: the tests that define "done"
- `docs/DECISIONS.md`: why things are the way they are
- `docs/TODO.md`: where we are

## If the conversation gets compacted
Keep the files changed, failing tests and their errors, open decisions, and the current plan step.

## Lessons so far
@docs/LESSONS.md
