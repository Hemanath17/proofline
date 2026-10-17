---
name: add-check
description: Adds a new Proofline check to api/checks/ with its fixture and tests. Use when the user asks to add, create or change a check that finds errors or discrepancies in the packet.
argument-hint: <what the check should verify>
---

Add a check that verifies: $ARGUMENTS

Follow these steps in order. Show the user the plan (steps 1-3) and wait for their OK before writing code.

1. **Understand the data.** Use the packet-explorer agent to find exactly which packet fields this check needs. Note the reference formats it returns
2. **Define the rule in one sentence.** It must be general, e.g. "every dependent's SSN must match the prior-year return". If you can only state it using a specific value from this packet, it is not a valid check: stop and tell the user
3. **Decide the classification.** `finding_type` (`error` only if an independent source confirms it), `severity`, `area`, `scope`, and how the tax effect is labeled (`exact`, `estimate`, or impact unknown)
4. **Write the fixture first** at `api/fixtures/<CHECK_ID>.json` with the findings you expect on this packet, and explain to the user why each is expected
5. **Write the check** at `api/checks/<check_name>.py`, starting from [template.py](template.py). Follow `.claude/rules/checks.md`
6. **Write the tests** at `api/tests/test_<check_name>.py`:
   - the real packet produces exactly the fixture's findings
   - a small hand-made clean input produces zero findings
7. **Run** `pytest api/tests/test_<check_name>.py -q` and show the full output
8. **Record** the confirmed or suspected error in `docs/ERRORS.md`: what is wrong, check ID, `finding_type`, severity, evidence references
9. **Summarize** in plain language what the check does and what it found, then wait for the user's OK

Never hard-code a packet value, ID, name or expected answer inside the check.
