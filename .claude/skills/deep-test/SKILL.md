---
name: deep-test
description: Puts Proofline through a thorough test pass against its contracts and invariants, finds rules nobody has tested yet, and reports the gaps. Use at the end of a plan step, before committing, or whenever I ask for deep testing.
argument-hint: [an area to focus on, like "C2" or "redaction"; leave empty for everything]
---

Let's test Proofline properly. Focus: $ARGUMENTS (if that's empty, test everything).

## Where we are
Uncommitted changes:
!`git status --short`

How many tests we have:
!`pytest api --collect-only -q -m "not eval" 2>/dev/null | tail -5`

## What to do
Show me your plan for steps 1 to 3 before you write any new test, and wait for my OK.

1. **Match every rule to a test.** Go through `docs/CONTRACTS.md` and `docs/ACCEPTANCE.md` and list every rule: each case transition in C1, each change rule in C2, the labels in C3, each disposition in C4, each readiness condition in C5, the claim identity keys, redaction, storage, and invariants I1 to I7. Next to each, name the test that proves it, or write MISSING.
2. **Run everything.**
   - Run `pytest api -q -m "not eval"` twice. A test that passes once and fails once is FLAKY, so call it out.
   - Coverage: `pytest api -q -m "not eval" --cov=proofline --cov-report=term-missing`. Ask me before installing pytest-cov.
   - `alembic -c api/alembic.ini check`, to confirm the models and migrations agree.
   - The baseline: precision and recall of all checks against `docs/ERRORS.md`.
3. **Look for rule breakers**, using grep and small scripts:
   - Packet values hard-coded in `api/proofline/checks/` (things like `D\d\d`, `ev-\d{4}`, SSN shapes, known amounts)
   - Any UPDATE or DELETE aimed at the events or filed-record tables, in code or in a migration
   - SQL or SQLAlchemy outside `api/proofline/db/`
   - A route that returns data without going through `proofline/security/redact.py`
   - A write that dodges the action service or the revision check
   - Float arithmetic on money
4. **Go after the edge cases** that usually break things in the focus area:
   - Boundaries: a tax effect of exactly 1,000, and 1,000.01; federal over the limit while state is under
   - Empty or missing: no evidence, a blank basis, an unread page, a document that feeds no claim
   - Order: two events the other way round, or the same action sent twice
   - Identity: a lot that moves box, a corrected document with identical fields, offsetting changes (proceeds and basis both up 100)
   - Roles: every action tried by every role, including the client and the AI assistant
   - History: a database holding old events, migrated forward, then rebuilt. Nothing should change
   - If Hypothesis is installed (ask me first), use property tests for fingerprints, money and redaction
5. **Write the missing tests** I approve. Don't weaken or delete an existing test, and never edit a fixture to match a wrong answer.
6. **Tell me what you found**, in plain words:
   - A table of rule, test and result (PASS, FAIL, MISSING or FLAKY)
   - Coverage for `api/proofline/`, and any file under 80%
   - Precision and recall of the checks
   - Rule breakers, with file and line
   - The three gaps you'd fix first

Don't fix production code here. List what's broken and ask me before touching it.
