---
name: simulate
description: Stress-tests the running prototype with realistic and hostile scenarios (a season replay, concurrency, role abuse, late documents, failures) and writes up what broke. Run it by hand with /simulate.
argument-hint: <scenario name, or "all"> [local | live]
disable-model-invocation: true
---

Run these scenarios: $ARGUMENTS

## Ground rules
- The target is `local` by default: the API at http://localhost:8000, or `vercel dev`. Use `live` only if I've typed "live", and then use the URL in `SIM_BASE_URL`.
- Never run against the demo data. Use a Neon branch made for the simulation, or a local database, migrated with `alembic -c api/alembic.ini upgrade head`, and reset it before each scenario.
- Work through the HTTP API as a named person, using that person's session or role header, the way a real user would. Don't call internal functions. The point is to test what people can actually do.
- Scenarios live in `api/sim/scenarios/` as short Python scripts using httpx. If one is missing, write it from the list below, show it to me, and wait for my OK before running it.

## The scenarios
1. **season**: replay the packet timeline in order: documents arriving, v1 to v3, client messages, approval, rejection, acceptance, payments, the notice. A1 to A3 should pass, and no step should leave the app half-updated.
2. **rsu**: A1 from start to finish, including Daniel's return and Helen's approval.
3. **corrected-1099**: A2. Then send D31 twice, and once while a delta approval is in progress.
4. **efile**: A3, then try to edit the filed record. It has to refuse.
5. **concurrency**: Daniel and a second reviewer approve the same revision at the same moment. Exactly one succeeds and the other gets 409. Then fire 20 writes at one case at once, and confirm a reader polling meanwhile never sees half a change.
6. **role-abuse**: every role tries every action. Each refusal should be a 403 that names the rule. Include a preparer approving their own work, Marcus revealing an SSN, the AI assistant approving or adjusting, the client opening a case, and a reviewer signing a scope with their own adjustment in it.
7. **leak-scan**: as Marcus, as the client and as the AI assistant, call every read endpoint and render every document page, then search the responses for every known sensitive value.
8. **bulk-undo**: verify a 260-lot group in one go with one bad item in it. Nothing should apply, and the bad item should be reported. Fix it, apply, then undo. All 260 go back, and the history stays.
9. **filing-guard**: try to file with a pending change, an open review note, an undecided outside filing and a document with no disposition. Each one has to block, and say which condition failed.
10. **failure**: break the database connection halfway through an action. No event and no state change should survive. Then take the AI model away; the app falls back to fixed wording and carries on.
11. **migration**: load a database with a full season of events, apply the newest migration, rebuild the current state, and compare it with before. It must be identical.
12. **load**: 50 people reading the queue and trace pages for 60 seconds. Report p50 and p95 latency and any errors.

## Steps
1. Tell me which scenarios you'll run and which need writing first, then wait for my OK.
2. Reset the simulation database.
3. Run each scenario. For anything that doesn't match what we expected, keep the request, the response and the events around it.
4. After each scenario, check the invariants: rebuild the current state from events and compare, confirm no event was changed or removed, and run the leak scan.
5. Write `docs/SIMULATION_REPORT.md` with:
   - a table of scenario, what was checked, PASS or FAIL, and the evidence
   - each failure in plain words: what a user would have seen, and why it matters
   - latency numbers from the load scenario
   - suggested fixes, most serious first
6. Add a line to `docs/TODO.md` for each failure. Don't fix code here; ask me first.
