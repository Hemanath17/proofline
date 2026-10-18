# Packet guide

File: `api/data/packet.json` (1.9 MB, read-only). All people, numbers and IDs are invented.

## Sections
packet, readme, household, documents (74), extracted_values (3,012), client (questionnaire, messages, call_notes), firm, prior_years, tax_agency_records, timeline, engine_reference (parameters, rules), return_versions (v1, v2, v3), what_if, planning_reference_2026, post_filing_rates, fx_rates.

## Reference formats
- `ev-NNNN` extracted value; `D01` to `D74` document; `qa-NN`, `msg-NN`, `call-NN` client items
- `py:/<json pointer>` inside prior_years; `agency:/<json pointer>` inside tax_agency_records
- `asset:<id>`, `household:<id>`, `ref:param.<name>`, `ref:fx.SEK.<rate>`, `timeline:<id>`
- `doc:<id>#page<n>` a page the pipeline did not extract
- Line keys `<form>.<line>`, e.g. `F1040.1a`; a line's `inputs` are other line keys in the same version

## Truth and trust
- `documents[].pages[].printed_content` is what is actually printed. Extracted values and engine results can be wrong
- Confidence is poorly calibrated: only 2 of 3,012 values are below 0.9, yet confident mistakes exist
- `position` values are synthetic; use them only to place highlights
- The engine cannot be rerun. v3 (2026-06-23) is current. Timeline events after v3 are scripted for replay

## Verified facts
- People: Ngozi Okafor (taxpayer), Erik Lindqvist (spouse), Ada and Theo (dependents)
- Staff: Priya Raman (preparer), Daniel Ortiz (reviewer, CPA), Helen Strand (partner, CPA), Marcus Bell (preparer, no sensitive-data clearance), Jo Kimura (firm administrator), Sam Adeyemi (quality reviewer). Client users: Ngozi, Erik
- Residency: California 2025-01-01 to 2025-07-14, Texas from 2025-07-15
- Versions: v1 (2026-03-04), v2 after the corrected Meridian 1099 (D31 supersedes D30), v3 after the Ridgeline K-1, the 2023 Woodworks K-1 and other documents
- Form 8949: 302 lines (box A 120, D 161, H 8, K 6, B 3, E 2, F 2)
- D74 Brightpath: 27 pages, 1,826 values, 260 lots; ties to its summary to the cent (proceeds 334,728.52, basis 338,300.26, wash 2,906.29); 28 lots have wash sales
- Engine rules used most: R-8949-LOT, R-SUM, R-CARRY. Only R-SUM and R-CARRY are plain sums or carries
- `tax_effect_rates` keys include wages, interest, schc_profit, stcg, ltcg, ordinary_income, adjustment, salt
- Budget hours by area: intake 1.5, wages and stock 3.0, investments and digital assets 4.0, business 3.5, rentals and sale 3.5, pass-throughs and basis 2.0, deductions and credits 2.0, California 1.5, partner review 1.0
- Firm standards: 5 verification types, variance rule (over 10% and over 1,000 against prior year), 7 rules, 12 required steps

## Gotchas
- Printed amounts may omit cents ("8,400") while values are stored as 8400.0; parse numbers before comparing
- D30 and D31 are partial extractions: page 32 was not read
- D10 is a phone photo of D09; the engine counts it once
- The 2023 Woodworks K-1 (D40) arrived in June 2026 and changed the S-corporation basis in v3
- Timeline tl-20 contains the 8879 PINs: treat them as sensitive
