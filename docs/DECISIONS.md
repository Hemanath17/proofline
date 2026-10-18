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
