# Contracts

These are the rules the code has to keep. If a rule matters, it should have a test. If you find a case these rules don't cover, stop and ask rather than guessing.

## Claim identity
A claim is identified by the thing itself, not by where it sits on the return. In the corrected Meridian 1099, lot M14 moved from Form 8949 box A to box D. It's still the same claim.

| Kind of claim | How we identify it |
|---|---|
| W-2 box | employer EIN + employee + tax year + box |
| 1099-B lot on a composite statement | issuer + account + lot id (M14, N1, X54); with no lot id, security + acquired + sold + quantity |
| Digital asset lot | broker + lot id (C6) |
| 1099-INT, -DIV, -NEC or -K amount | payer TIN or name + recipient + box |
| K-1 item | entity EIN + partner or shareholder + box code |
| Depreciation asset | the packet's `asset_id` |
| Rental or property line | property + line |
| Carryover | its name, e.g. `minimum_tax_credit_from_2025_amt` |
| Household fact | `household:<id>` + field |
| Return-wide total (AGI, taxable income, tax, credits, penalty) | the line key |

A corrected document keeps the identities of its claims: same issuer, same account, same lot ids.

## Redaction
- Sensitive values: SSNs and ITINs, bank and account numbers (IBANs too), IP PINs and e-file signature PINs.
- How: collect every sensitive value we know about (the household record, extracted values typed ssn or account_number, the PINs in the timeline) and replace each exact occurrence in anything we send out. A regex for SSN-like and account-like strings backs it up.
- Masked values keep the last four characters, e.g. `***-**-3390`.
- The test: render every page and every API response as someone without clearance, and confirm none of those values appears anywhere.

## Storage
- The database is Neon Postgres, reached through SQLAlchemy 2.0. The only code that touches it is `proofline/db/`; everything else goes through `repository.py`.
- Every action writes its event, the current-state rows and any check-run snapshot in one transaction. If anything fails, nothing is written.
- Events carry a `schema_version`. When an event's shape changes, `rebuild.py` knows how to read the old versions, so old events stay valid forever.
- Schema changes happen only through reviewed Alembic migrations. New columns are nullable or have a default. No migration ever updates or deletes an event.
- Database triggers refuse UPDATE and DELETE on the events table and the filed-record table, so immutability doesn't depend on the code behaving.
- Migrations run as their own step (`alembic -c api/alembic.ini upgrade head`), never when the app starts. Test a migration on a Neon branch before running it on the demo database.
- Rebuild and migration solve different problems. Migrations change the shape of tables. Rebuild replays events into current state. Rebuilding after a migration must give the same state as before it.

## C1. Cases
A case is where a problem gets investigated. It has: case_id, root_cause_key, origin (check, preparer, reviewer, client, document, completeness, agency), origin_ref, scope, claims, severity (blocks filing, penalty risk, tax amount, info), priority, assignee and status.

Findings that share a root cause become one case, not a pile of alerts. The root-cause key is the check id plus its claim identities, or the replaced document, the notice, the question thread, or a fresh id for a case someone opened by hand.

| Action | From | To | Who | Only when |
|---|---|---|---|---|
| pick_up | open | investigating | Preparer | |
| ask_client | investigating | waiting_on_client | Preparer | the question is specific and tied to the case |
| client_answered | waiting_on_client | investigating | Client or system | the answer is saved as client-statement evidence |
| submit_proposal | investigating | in_review | Preparer | the revision has the evidence its type needs |
| return | in_review | investigating | A reviewer who didn't propose it | there's a note |
| approve | in_review | resolved | A reviewer who didn't propose it | the tax effect is 1,000 or less, federal and state |
| approve | in_review | awaiting_partner | A reviewer who didn't propose it | the tax effect is over 1,000, federal or state |
| partner_approve | awaiting_partner | resolved | Partner | |
| partner_return | awaiting_partner | investigating | Partner | there's a note |
| clear | open, investigating | cleared | System | the finding stopped firing; the reason is saved |
| reopen | resolved | investigating | System or reviewer | an approved input changed (C2), or a reviewer left a note |
| reassign | any open state | same | Preparer, reviewer or admin | |

What each kind of resolution needs before anyone reviews it:
- **Resolve an evidence conflict:** both sources, the one chosen, a reason from a short list, and at least one piece of supporting evidence. If the chosen source is something the client made or said, it gets flagged.
- **Record a judgment:** the reasoning, the authority relied on, and a CPA's approval.
- **Adjust a number:** the claim, the old value, the new value, the evidence, and the tax effect labelled exact or estimate.
- **Mark as legitimate:** why the difference is expected, with evidence. It still goes to review.

Every revision of a proposal is kept, and a decision points at one exact revision. Any case that isn't resolved or cleared blocks filing.

## C2. Sign-off
Areas are where completeness gets approved. Each claim belongs to exactly one scope: Identity and household; Wages and stock compensation; Investments and digital assets; Business; Rentals and sale; Pass-throughs and basis; Deductions and credits; California; and Tax computation, which holds the return-wide totals.

A sign-off records the scope, its version, who signed and in what role, when, the engine version and active adjustments, the check runs they saw, and four fingerprints:
- **Evidence:** for each claim, the document lineage and every field the claim relied on
- **Values:** each claim and its accepted value
- **Decisions:** resolved cases and judgments in the scope, with the revision approved
- **Scope:** which claims are in it

| What changed | What happens |
|---|---|
| A value | That claim and anything linked to it are flagged, and the scope shows "signed, change pending" |
| Only the evidence | The approval carries over only if the new document is a corrected version from the same issuer, every relied-on field is identical, the source isn't weaker, and no judgment points at the old document. The reviewer confirms each replaced document once. Otherwise, treat it as a value change |
| A decision | Change pending |
| The scope | New claims need review before the next version |
| A tie-out broke, or a judgment no longer holds | It becomes a case, and the scope is reopened |
| The reviewer approves the change | Version n+1 is version n plus that change. Both are kept |

Reviewers sign areas, and the partner signs Tax computation and the final return. Nobody signs a scope that contains their own adjustment. A scope only shows green at its current version with nothing pending.

## C3. Calculation
- **Engine value:** v1, v2 and v3 exactly as delivered. Never edited.
- **Adjustment:** an overlay on one claim, with the old value, the new one, the evidence, who and when.
- **Workpaper value:** engine v3 plus the approved adjustments.
- **Exact:** we only carry a change forward along R-SUM and R-CARRY lines, because those are plain sums and carries.
- **What-if:** the packet's five alternatives (equipment_section179, equipment_no_bonus, hvac_improvement, standard_deduction, penalty_annualized) are exact engine results.
- **Estimate:** at the first rule that isn't R-SUM or R-CARRY, we stop and estimate the effect as change times the matching `tax_effect_rates` category, federal and California separately.
- Every number on screen carries one of these labels.

## C4. Documents
Every document gets exactly one disposition: used, duplicate of, superseded by, reference, identity and engagement, agency record, excluded (with a reason), or pending, which is the default. Rules propose a disposition and the preparer confirms it. A document with pages the pipeline didn't read isn't complete until that gap is dealt with. Filing needs nothing left pending.

## C5. Readiness and the filed record
We file only when every one of these holds. First, the firm's 12 steps: engagement and consents signed; identity verified; prior-year return reviewed; all documents accounted for; prior-year variances explained; carryovers agreed; estimated payments agreed to IRS and FTB records; due diligence done; diagnostics resolved; reviewer sign-off; partner sign-off; client approval and e-file authorization. Then ours: no open cases or review notes, no pending changes, and every outside filing decided.

- **Package:** the workpaper values with their labels, the sign-off versions, the adjustments, the document versions (id plus content hash), an amounts fingerprint and an identity fingerprint.
- **Authorization:** the client, the package and both fingerprints. PINs are sensitive.
- **Submission:** the package, jurisdiction, result and codes. Replayed, and labelled simulated.
- **Filed record:** written once, when the return is accepted, and the database refuses to change it.
- **After filing:** payments, refunds, quality review, next year and notices all point to the filed record. An amendment is a new package that points to it.
- **Re-signing:** per Publication 1345 and the Form 8879 instructions, correcting the taxpayer's SSN, name or address after signing always needs a new signature, whether or not the refund or balance due changed at all -- no threshold, no judgment call. An amounts-only change needs one too, per this same contract's "even $2 is $2." In practice this is one rule, not two: the package reference is a hash over everything in the package, so any change to either fingerprint changes the reference, and submission is refused unless the package being submitted is exactly the one most recently authorized.
