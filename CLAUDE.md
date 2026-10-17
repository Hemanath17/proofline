# Proofline

<!-- Maintainer notes (stripped from Claude's context): keep this file under ~150 lines.
     Every line must pass the test "would Claude make a mistake without it?".
     Detail belongs in docs/ or .claude/rules/, not here. Review after each work session. -->

Web workpaper that lets a CPA team prove every number on an AI-prepared 2025 tax return
(Okafor-Lindqvist household, MiraFlores AI case study): where it came from, how it was
calculated, who checked it, and what is still open.

## Stack
- Front end: Next.js (App Router) + TypeScript at the repo root; pages are client components
- Back end: FastAPI + Pydantic v2 in `api/`
- Database: Neon Postgres; attachments: Vercel Blob
- Hosting: Vercel (Next.js + Python functions in one project)
- Tests: pytest (Python), `tsc` type check (front end)

## Commands
```bash
pip install -r api/requirements.txt          # Python dependencies
uvicorn api.index:app --reload --port 8000   # run the API locally
pytest api/tests -q                          # all Python tests
pytest api/tests/test_<name>.py -q           # one test file
npm run dev                                  # front end (once it exists)
npm run typecheck                            # front end types (once it exists)
```

## Layout
- `api/index.py`: FastAPI app and routes
- `api/checks/`: pure check functions, no FastAPI imports; result model in `api/checks/models.py`
- `api/tests/`, `api/fixtures/`: tests and expected check results (JSON)
- `api/data/packet.json`: the client packet, read-only
- `app/`, `components/`, `lib/`: Next.js front end
- `docs/`: plan, packet guide, errors, decisions, to-do list, lessons, AI usage

## Critical rules
- NEVER modify `api/data/packet.json`. NEVER read it whole (1.9 MB): query it with small Python scripts or the packet-explorer agent
- NEVER hard-code a packet value, ID or expected answer inside a check (e.g. `if ssn == "666-74-3309"`). Checks are general rules that would work on any client's packet
- NEVER commit secrets. Configuration comes from `.env.local` (`DATABASE_URL`, `BLOB_READ_WRITE_TOKEN`)
- Enforce every permission in the API, never only in the UI. Mask SSNs, bank and account numbers and IP PINs on the server for users without clearance, and log every unmasked view
- Events are append-only: never UPDATE or DELETE an event row. Undo writes a reversing event

## Domain rules
- Engine snapshots (v1, v2, v3) are immutable. Human adjustments are a separate layer; never present an adjusted return as recomputed (the engine cannot be rerun)
- Label every tax effect "exact" (from a packet `what_if` result) or "estimate" (from `tax_effect_rates`)
- Label e-file submission, acceptance and the 2028 IRS letter "Simulated"; respect the app's "as of" date
- Every check returns `CheckResult`, classified as `error` or `possible_discrepancy`. Documents left unextracted on purpose are not findings
- A client statement (questionnaire, message, call note) is not verification. Accepting it is a recorded judgment
- Firm rules (packet `firm.starter_standards`): open review notes block filing; nobody reviews their own work; adjustments over $1,000 of tax effect need partner sign-off
- Every write carries the item's revision number; a stale revision returns 409 with what changed

## Workflow orchestration

### 1. Plan first
- Use plan mode for any change touching 2+ files, any data-model decision, or any new screen
- Read the matching step in `docs/PLAN.md` before planning
- If a test fails twice for the same reason, or the approach stops making sense, STOP and re-plan instead of patching

### 2. Subagents for named jobs only
- packet-explorer: any question about what is in the packet
- reviewer: before committing a feature
- A general subagent only for wide searches that would flood this session
- One task per subagent; do not spawn subagents for small lookups

### 3. Learn from corrections
- After any correction from me, add one line to `docs/LESSONS.md`: the mistake and the rule that prevents it
- Lessons are loaded below; follow them

### 4. Prove it before saying done
- Checks and API: show the pytest output, including the fixture comparison
- UI: run the app, take a screenshot, compare it with the plan, fix differences
- Never say "should work". Show the command you ran and its result

### 5. Prefer the simpler solution
- Before presenting a non-trivial change, ask whether a simpler design does the same job; if so, use it
- Skip this for small, obvious fixes. Do not over-engineer

### 6. Know when to act and when to ask
- Fix without asking: failing tests, type errors, crashes, lint errors with a clear cause
- STOP and ask me before: any product, data-model, UX or scope decision, adding a dependency, or changing anything in `docs/PLAN.md`

## Task management
1. **Plan:** write the steps for the current plan step into `docs/TODO.md` as checkboxes
2. **Check in:** show me the steps and wait for my OK before implementing
3. **Track:** tick items off as they are completed
4. **Explain:** after each step, summarize in plain language what changed and why, then wait for my OK before the next step
5. **Record:** at the end of a session, add a short review to `docs/TODO.md`, log decisions in `docs/DECISIONS.md`, and log notable AI contributions in `docs/AI_USAGE.md`

## Core principles
- **Simplicity first:** the smallest change that fully solves the problem
- **Root causes only:** never weaken, skip or delete a test to make it pass; no workaround without a `TODO` comment and a line in `docs/TODO.md`
- **Minimal impact:** touch only the files the task needs; no drive-by refactors

## Code style
- Prefer simple, explicit code: named intermediate variables, one step per line, no clever one-liners
- Python: type hints on every function; Pydantic models for all API input and output
- TypeScript: strict mode; API types generated from FastAPI's OpenAPI schema, never hand-written

## Definition of done
- Tests and type checks pass, with output shown
- The matching acceptance item in `docs/PLAN.md` is satisfied
- Estimates, exact results and simulated events are labeled
- I have approved the step

## Read when needed (not loaded automatically)
- `docs/PLAN.md`: product decisions, data model, phases, acceptance checklist
- `docs/PACKET.md`: packet sections, reference formats (`ev-`, `D`, `qa-`, `py:/`, `agency:/`, line keys), known gotchas
- `docs/ERRORS.md`: confirmed and suspected errors from the error hunt
- `docs/TODO.md`: what is done, in progress and next

## When compacting
Keep: files changed, failing tests and their errors, open decisions, and the current `docs/PLAN.md` step.

## Lessons
@docs/LESSONS.md