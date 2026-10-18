# Errors found

Status: confirmed (independent evidence), possible (needs evidence or judgment), handled (engine already correct), lead (not yet checked).

## Confirmed
E1. Dependent SSN typed wrong (blocks filing)
- Household record: Theo 666-74-3309. Social Security card (D71, ev-1080) and the 2024 return: 666-74-3390
- The scripted e-file was rejected for this (R0000-504-02, 2026-07-13); the client confirmed the typo (msg-10)

E2. RSU lots at zero basis (tax amount)
- F8949.B.N1, F8949.B.N3, F8949.E.N4 use basis 0.00 from the Northlake 1099-B (D28, noncovered)
- The Corvane supplement (D11, ev-0066, ev-0068, ev-0070) gives 19,100, 19,100 and 9,420: 47,620 in total
- W-2 box 14 RSU 38,200 (D08, ev-0027) matches the two 2025 vests
- Estimate: about 15,536 federal (short-term 0.348, long-term 0.238), about 1,619 California

E3. 1099-K receipts counted twice (tax amount)
- SchC.1 gross receipts 163,700 = books income 151,300 (D14, ev-0103) + Form 1099-K 12,400 (D21, ev-0127)
- D15 page 3: 12,400 of Atlas Outdoor Gear's 41,200 arrived through Paywell and was deposited gross, so it is already in the books
- Reconciliation: third-party forms 154,400 (1099-NEC 142,000 + 1099-K 12,400) minus 12,400 reported twice plus 9,300 from clients with no 1099 = 151,300, the books
- Estimate: about 4,402 federal (0.355). The 2028 IRS letter asks for this reconciliation

E4. Brokerage page not extracted (tax amount)
- D31 page 32 was not read: lot M18, Ironwood REIT 6.8 shares, proceeds 250.00, basis 310.00, short-term noncovered
- Summary proceeds 71,965.00 (ev-0703) against extracted detail 71,715.00

## Possible
E5. Digital asset lot with no basis
- Coinhaven lot C6 (0.05 BTC, proceeds 5,325) transferred in; basis blank (ev-0919, confidence 0.6); the engine used zero
- Erik (msg-07): bought March 2021 for about 3,050 on an exchange that closed; only a bank statement line remains. If accepted, basis about 3,050 and the holding period may become long-term
- Needs the bank statement; accepting the message alone is a recorded judgment

E6. S-corporation basis rolled forward from gaps
- F7203.1 beginning basis 2,300 = 21,300 (2022, client worksheet) + 14,100 - 20,000 (2023, D40) + 16,900 - 30,000 (2024)
- 2023 and 2024 ending basis records are blank; distributions over basis 21,215 are taxed as gain

E7. Questionnaire answer conflicts with documents
- qa-14 "No" to selling investments; documents show 282 brokerage sales and 12 digital asset dispositions

E8. Outside filings
- Foreign account maximum 149,567 USD (F8938.1.max): FBAR due separately, outside the engagement
- Prior preparer open item: 2023 Form 3520 for the foreign inheritance, no note of resolution (the Swedish account was opened 09/2023 from an inheritance, D36)
- Client paid two contractors 600 or more without filing Forms 1099-NEC (engine diagnostic)

E9. Handwritten charity receipt
- D64 reads "$?,500.00" (first digit 1 or 7); ev-1049 1,500 at confidence 0.41
- Ngozi (msg-08): the parish confirmed 1,500 by phone; bank check #2207. Needs the bank record

## Handled by the engine
- D10 duplicate of D09: counted once in F1040.1a

## Leads (not yet checked)
- Halvorsen payroll kept California as the work state through 09/30/2025, after the 07/15 move to Texas (state wage split)
- Home office area 240 square feet against 300 in 2024
- Mileage: business miles are the sum of page totals on the log; check the totals against the log lines
- Form 8606 basis 7,000; the 2024 Form 5498 was never obtained
- California AMT not computed for the incentive stock option exercise
- Form 8867 due diligence required for the child and dependent credits
