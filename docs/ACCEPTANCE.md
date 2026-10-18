# Acceptance tests

These define "done". Each one should become an automated test where we can manage it, and a plan step isn't finished until its items pass.

## Things that must always hold
- **I1.** A successful action writes the event and the current state together. A failed one writes neither.
- **I2.** A stale revision gets a 409 with the current state, and nothing is written.
- **I3.** A role that isn't allowed gets a 403 that names the rule, such as "own work".
- **I4.** Marcus never sees an SSN, account number or PIN in any API response or rendered page. The leak scan proves it.
- **I5.** Rebuilding the current state from events gives exactly what's stored.
- **I6.** The database refuses to update or delete the filed record or any event.
- **I7.** Applying a new migration to a database full of past events leaves every event readable, and rebuilding gives the same state as before.

## Scenarios
**A1. The RSU basis correction**
- The check finds three lots and opens one case. Priya proposes revision 1, Daniel returns it, and Priya sends revision 2 with the W-2 box 14 evidence.
- Daniel approves revision 2, and the case moves to "awaiting partner" because the effect is over 1,000. Helen approves, and it's resolved.
- Revision 1, both decisions and the original engine values can all still be read.
- Schedule D line 2 shows -480, labelled exact. The tax effect shows about 15,536 federal, labelled estimate.

**A2. A corrected brokerage statement**
- Investments is signed at v1 using D30, then D31 arrives.
- The provenance resolver finds the 24 lines that depended on D30. Three claims changed (M6's wash sale, M9's basis, M14 now long-term), and 21 are identical in every field they relied on.
- M14 keeps its identity even though its line key moves from box A to box D.
- Investments shows "signed, change pending", Business stays signed, and Tax computation shows a pending change.
- The reviewer confirms the carry-over once and approves the change. Sign-off v2 exists, and v1 is still there.

**A3. The e-file rejection and the 2028 examination**
- Package F1 is authorized and submitted, then rejected with R0000-504-02. F1 is kept and never counts as filed.
- The SSN is corrected from D71. Package F2 has the same amounts fingerprint and a new identity fingerprint.
- F2 is accepted, and the filed record is written once.
- The Letter 566 pack uses the filed values and shows the receipts reconciliation coming to 151,300.

## Walkthroughs with real people in mind
- **W1.** Daniel approves the RSU correction from his queue in four clicks or fewer.
- **W2.** Marcus opens the SSN case and sees only masked values, and nothing is logged as revealed.
- **W3.** A new hire finds a "why this is flagged" explanation and source links on every case, and only sees the actions their role allows.
- **W4.** The client sees a labelled summary, answers their questions, approves and signs, and the signature is tied to that exact package.
