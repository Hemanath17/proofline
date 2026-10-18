# The build plan

Proofline is a web workpaper for one household's 2025 return. Every number is traced to its proof, every decision keeps what the person saw, and nothing gets overwritten.

The design work behind this lives in two private pages (only I can open them):
- Proofline Blueprint, 15 diagrams: https://claude.ai/artifact/CxLfgFRpgeTfJkWTn8qSQx
- Proofline Build Spec, 74 decisions: https://claude.ai/artifact/Ub6b2aXhqgbbGgKWTTQzvZ

The rules from both are in `docs/CONTRACTS.md`, and that's the version the code follows.

## The idea in three lines
- There are three kinds of information: the packet (facts we never change), the analysis (worked out fresh), and what people did (events plus current state, written together).
- Cases are where problems get investigated. Areas are where completeness gets approved.
- The provenance resolver sits in the middle. It understands every packet reference, identifies claims by the thing itself, and answers "what depends on this?"

## Build order
Each step finishes with its tests passing, its acceptance items passing, my OK, and a commit.

### Step 1: Prove we can deploy
- Set up the `web/` (Next.js) and `api/` (FastAPI) services with the root `vercel.json`, and confirm `/api/health` and the home page both work on the live link
- Wire up Neon: `DATABASE_URL` as a `postgresql+psycopg://` URL with SSL required, in `.env.local` and in Vercel
- Run `alembic init`, then make `api/alembic.ini` independent of the folder it's run from (`script_location = %(here)s/proofline/db/migrations`, `prepend_sys_path = %(here)s`). The first migration creates the events table with `schema_version`
- One endpoint writes an event and another reads it back. The event survives a redeploy
- Keep tests, fixtures, evaluation sets and simulation scripts out of the Python bundle (check Vercel's service configuration reference for the exact setting)
- Note how long a cold start takes
- If Services misbehaves, switch to two Vercel projects with a Next.js rewrite and write the switch down in `docs/DECISIONS.md`
- **Done when:** the live link shows an event written from the live app, and it's still there after a redeploy

### Step 2: The packet and the provenance resolver
- `proofline/packet.py` with Pydantic models for the parts of the packet we use
- Resolve every reference format: `D`, `ev-`, `qa-`/`msg-`/`call-`, `py:/`, `agency:/`, `household:`, `asset:`, `ref:`, `timeline:`, line keys and `doc:D#pageN`
- Claim identity keys (from CONTRACTS), tracing in both directions, and the dependency graph over line inputs
- **Done when:** every reference in the packet resolves, and tracing F1040.1a returns D08 and D09 with D10 marked as a duplicate

### Step 3: Checks for the errors we've confirmed
- The `CheckResult` model, and one general check per confirmed error in `docs/ERRORS.md`, each with its fixture
- A baseline report: precision and recall of all checks against `docs/ERRORS.md`
- **Done when:** every confirmed error is found, nothing is hard-coded, and the baseline prints

### Step 4: Events, current state, the action service, roles and redaction
- SQLAlchemy models and migrations for events, current state and check runs, plus triggers that refuse updates and deletes on events
- The action service with revision checks, and `rebuild.py` for replaying events
- Roles from the packet's staff list, plus the client users and the AI assistant. The role switcher works through the API too, so `/simulate` can act as anyone
- The redaction module and the leak-scan test
- **Done when:** I1 to I7 pass, then run `/simulate` with role-abuse, concurrency, leak-scan, failure and migration

### Step 5: Cases and the review queue
- C1: the case schema, transitions, evidence requirements and root-cause grouping
- The queue screen (S1), with "why it's here" and "since you last looked"
- **Done when:** W3 passes and every transition in C1 has a test

### Step 6: Tracing and source documents
- The trace view (S4), and documents rendered from `printed_content` with the field highlighted and redacted
- **Done when:** W2 passes and the leak scan covers every rendered page

### Step 7: Areas, sign-off, calculation, documents and large detail
- Contracts C2, C3 and C4, and the area page (S3), with grouping, tie-outs, exceptions and bulk verification with undo
- **Done when:** A1 and A2 pass, then run `/simulate` with rsu, corrected-1099 and bulk-undo

### Step 8: Readiness, packages and the filed record
- C5, plus the filed-record table and its immutability trigger
- Replay the timeline: extension, approval, rejection, acceptance, payments, the notice
- **Done when:** A3 passes, then run `/simulate` with efile, filing-guard and season

### Step 9: Everything else the brief asks for
- The client workspace (S5), live updates, notifications, time against budget, search, comparing versions, what-ifs, judgments and elections, and the CPA record views R01 to R16
- **Done when:** every row of the Build Spec coverage map is built or labelled simulated, and W4 passes

### Step 10: The AI layer
- The Evidence Investigator (Pydantic AI, read-only tools, the AI assistant role), its validator and AI provenance events
- The evaluation set and a DeepEval run (hard gates, retrieval, faithfulness), with the judge checked against hand labels first
- Langfuse traces, redacted, and an MCP server for the same tools
- **Done when:** the investigator passes the hard gates at 100% and beats the baseline. If it doesn't, it stays off and we write down why

### Step 11: What we hand in
- One page on the core idea and data model, the errors write-up, the AI-usage statement, and the video walkthrough
