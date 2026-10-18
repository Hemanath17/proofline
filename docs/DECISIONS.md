# Decisions

| Date | Decision | Why |
|---|---|---|
| 2026-10-17 | Next.js + FastAPI + Neon on Vercel, free tier | One project, Python for the domain logic, no cost |
| 2026-10-17 | Three kinds of information: packet, analysis, actions | Facts never change; analysis stays fresh; decisions are kept |
| 2026-10-17 | Current-state tables written in the same transaction as events | Fast reads and easy debugging; events stay the audit history; state can be rebuilt |
| 2026-10-17 | Check runs saved at each decision | Proves what a person saw even after code changes |
| 2026-10-17 | Cases for investigation, areas for approval | One place to work, one place to prove completeness |
| 2026-10-17 | One root cause opens one case | Prevents alert fatigue |
| 2026-10-17 | No per-number workflow states; verification recorded per claim, done in bulk for tied groups | Avoids clicking through 3,000 values while still recording how each was verified |
| 2026-10-17 | Provenance resolver as a central component | Powers tracing and targeted invalidation |
| 2026-10-17 | Claim identity by item, not line key | Lot M14 moved from box A to box D in the corrected 1099 |
| 2026-10-17 | No materiality threshold; any change to an approved value counts | A program should not decide a change is too small for a CPA |
| 2026-10-17 | Approve the change, not the area again (delta approval) | Re-reviewing 299 unchanged lots adds no assurance |
| 2026-10-17 | Carry-over only when every relied-on field is identical, confirmed once per replaced document | A same result can hide offsetting changes |
| 2026-10-17 | Four sign-off fingerprints and a Tax computation scope | Return-wide totals would otherwise reopen unrelated areas |
| 2026-10-17 | Typed conflict resolution, no plain Accept; evidence required per resolution type | Stops disagreements disappearing and confirmation bias |
| 2026-10-17 | Awaiting-partner state for effects over 1,000 | Firm rule |
| 2026-10-17 | Green means "approved for a version", never "correct" | Agreement is not correctness |
| 2026-10-17 | Exact only along R-SUM and R-CARRY and packet what-ifs; otherwise estimate | The engine cannot be rerun |
| 2026-10-17 | Readiness evaluator separate from cases | Zero open cases is not enough to file |
| 2026-10-17 | Packages, client authorization bound to fingerprints, immutable filed record | The accepted return can be rebuilt years later |
| 2026-10-17 | Never the raw packet in the browser; redaction inside document text | Documents print SSNs |
| 2026-10-17 | Client approval workspace, not only questions | The brief requires approval, signature and a filed copy |
| 2026-10-17 | AI explanations of findings not built | Helped in 3 of 10 tested cases; fixed wording was as good |
| 2026-10-17 | One Pydantic AI Evidence Investigator under an AI-assistant role | Tool calling and typed output; permissions enforced by the role |
| 2026-10-17 | DeepEval with hard gates, judge checked against hand labels | Measured value, not demos |
| 2026-10-17 | Langfuse for redacted traces; AI provenance in our own events | Debugging versus audit record |
| 2026-10-17 | MCP server for the same tools, after the core | Outside agents get exactly the AI-assistant permissions |
| 2026-10-17 | Not used: embeddings and pgvector, DSPy, multi-agent frameworks, anomaly models, open Q&A, fine-tuning | Each fails a stated need; see the Blueprint |
| 2026-10-17 | Tax wording: review, sign-off, IRS examination | This is tax compliance work, not auditing |
| 2026-10-18 | Vercel Services (one project, `web/` + `api/`) worked as documented; no fallback to two projects needed | `vercel link` auto-detected and connected the GitHub repo, and both services deployed and routed correctly on the first try |
| 2026-10-18 | Cold-start measured at ~336ms for the first `/api/health` request on a fresh production deployment (vs. ~289ms on the next request) | Fluid Compute pre-warming keeps cold start close to warm; no action needed at this step |
| 2026-10-18 | Added `python-dotenv` to `api/requirements.txt` | Local `uvicorn` and `alembic` runs need `.env.local` loaded manually; Vercel injects env vars directly in production so this is dev-only |
| 2026-10-18 | A 1099-B lot's claim identity is issuer + lot id (falling back to issuer + security + acquired + sold + quantity), not issuer + account + lot id | The packet has no structured per-document account field; account numbers, where printed at all, are inside free-text `printed_content`. A same-issuer correction still keeps the same identity across a box move, which is the behavior CONTRACTS.md cares about |
| 2026-10-18 | A line's "excluded" documents (e.g. D10 relative to D09 for F1040.1a) are found by data, not by id: same issuer + same document type as a primary source, contributing zero extracted values to any line in that return version | Avoids hardcoding a specific document id while still satisfying the Step 2 Done criterion; full document disposition (used/duplicate of/superseded by) is still Step 7, this is only the provenance layer surfacing what the packet's own `sources` already say |
| 2026-10-18 | Checks read `packet.return_versions[-1]` as "the current version" rather than the literal string `"v3"` | Keeps every check working unchanged once a v4 exists, without any code change |
| 2026-10-18 | `TaxEffect.direction` is `"overstated"` or `"understated"`, describing the effect on tax as currently reported, not on income or basis | A reader of a finding wants to know which way the return is wrong, not which underlying number moved |
| 2026-10-18 | The baseline (`baseline.py` + `baseline_expectations.json`) counts a finding as confirming an error only when evidence or claims overlap, not on `check_id` alone | A later bug fix inside a check module could produce an unrelated finding that happens to share a `check_id` with a confirmed error; matching on `check_id` alone would hide that regression by reporting it as "found" |
| 2026-10-18 | `events.seq` is a Postgres identity column, `NOT NULL`, with `repository.insert_event()` assigning a placeholder (`0`) only when the session's dialect is `sqlite` | Postgres requires an identity column to be `NOT NULL` and rejects dropping that constraint afterwards (confirmed against the real database); SQLite (used only by the fast in-memory test fixtures) has no equivalent generation mechanism, so it needs *some* value supplied. Production never takes the sqlite branch, so Postgres's real sequence always assigns the value there |
| 2026-10-18 | `baseline_expectations.json` stays in `api/fixtures/` (excluded from the Vercel function bundle) and `baseline.py` stays dev-only, documented as such in `CLAUDE.md`, rather than relocating the fixture | Nothing in `proofline/app.py` or `routes/` imports `baseline.py` -- only tests and its own `__main__` block do -- so it was already dev-only in practice; moving the fixture would be a bigger change for no behavior difference |
| 2026-10-18 | `proofline/provenance/tracing.py` caches "documents used by any line" on the `ReturnVersion` object itself (a private attribute, populated lazily on first use) rather than in a module-level dict | A module-level cache keyed by `id(packet)`/`id(rv)` risks a stale hit after Python reuses a garbage-collected object's id across unrelated test packets; caching on the object instance lives and dies with it, so there's nothing to invalidate |
| 2026-10-18 | `/api/health`'s 503 body says only `"database unreachable"`; the real driver exception is logged server-side (`logger.error(..., exc_info=exc)`), never returned | The endpoint is unauthenticated; a driver's exception text can carry a hostname, database name or file path |
| 2026-10-18 | Moved the actual `SELECT 1` call into `proofline/db/connection.py` (`check_connection(engine)`); `routes/health.py` calls that instead of importing `sqlalchemy` and executing SQL itself | CONTRACTS.md's Storage section says `proofline/db/` is the only code that touches the database; the first version of the health check broke that by executing raw SQL from `routes/` |
| 2026-10-18 | The sqlite/seq placeholder is a named, directly-unit-tested function (`repository._needs_sqlite_seq_placeholder`), not an inline dialect check | Lets a test assert the gate is `True` only for `"sqlite"` and `False` for `"postgresql"` without a network connection (both engines are constructed, never connected to), rather than trusting the inline condition by inspection |
| 2026-10-18 | `runner._run_module` materializes a check's findings into a plain list and checks every item's type *before* any of them are added to `CheckRunResult.findings` | A check that returns a generator raising partway through, or the wrong type, could otherwise leave partial or malformed findings in the result while also being recorded as a `CheckFailure` for the same check |
