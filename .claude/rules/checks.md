---
paths:
  - "api/checks/**"
  - "api/tests/**"
  - "api/fixtures/**"
---

# Check rules

## Every check returns `CheckResult` (defined in `api/checks/models.py`)
- `check_id`: stable, uppercase, e.g. `DEPENDENT_SSN_PRIOR_YEAR`; `check_version`: integer, bumped when logic changes
- `area`: wages, investments, business, rentals, pass_throughs, retirement, deductions_credits, payments, state, identity, documents
- `scope`: document, extracted_value, transaction, asset or return
- `finding_type`: `error` (confirmed by an independent source) or `possible_discrepancy` (needs a human)
- `severity`: `blocks_filing`, `penalty_risk`, `tax_amount` or `info`
- `evidence_refs`: exact packet references (`ev-0012`, `D08`, `qa-31`, `py:/return_2024/dependents`, `agency:/efile/0`, line keys like `F1040.1a`)
- `observed` and `expected`: plain-language statements of what was found and what should agree
- `tax_effect`: federal and California amounts with `kind` = `exact` (packet what-if) or `estimate` (tax_effect_rates); `None` with `impact_unknown = True` when no credible amount exists
- `limitations`: what the check cannot see or assumes
- `recommended_action`: the next step for the preparer, in plain language

## How to write a check
- A check is a general rule that would work on any client's packet. NEVER hard-code a packet value, ID, name or expected answer
- Compare numbers after normalizing format ("156,039.0" and "156,039.00" are equal) and with a stated tolerance
- Documents with `extraction.status = not_extracted` and a stated reason (data reproduced elsewhere) are not findings
- A client statement can create a `possible_discrepancy`, never confirm an `error` on its own
- One check per file in `api/checks/`, named after the check, e.g. `dependent_ssn_prior_year.py`

## Tests and fixtures
- Write the fixture first: `api/fixtures/<check_id>.json` lists the expected findings for this packet
- The test runs the check on the real packet and compares to the fixture; it also runs the check on a small hand-made packet where nothing is wrong and expects zero findings
- Never edit a fixture just to make a failing test pass; explain the difference to the user first
