# Proofline UX

## Principles (from our research)
1. Make checking cheap, don't explain. Show the exact source with the field highlighted rather than paragraphs of reasoning; research shows written explanations increase blind acceptance, while highlighting the evidence reduces it. Any text explanation is one line and always sits next to the evidence.
2. Exceptions first, detail on demand. Every screen opens on what needs a decision; detail is one click away, never in the way.
3. Two separate labels on every number: where it came from, and what a human did with it.
4. Change is never silent. Anything that changed since you last looked is marked, and sign-offs show "signed, change pending" instead of quietly staying green.
5. Rules are visible. A disabled action stays on screen with its reason ("own work", "needs partner: tax effect over 1,000", "2 open review notes").
6. Not a spreadsheet. No grid of cells to fill. Numbers are objects you open; detail tables are read-only views with grouping.
7. Fast for experts, obvious for new hires: keyboard shortcuts for everything, plain-language labels, and a one-line "why it's here" on every item.

## Visual system
- Quiet chrome, paper for evidence. App background `--bg: #f6f5f1`; surfaces `--surface: #ffffff`; ink `--ink: #1c2230`; secondary text `--ink-2: #5b6372` (meets 4.5:1 on white); rules `--rule: #e3e0d8`; one accent `--accent: #0f5e63` (links, focus, primary button).
- State colours (always with an icon and a word, never colour alone): verified `#2f6f3e`, changed `#9a5b00`, blocking `#b42318`, info `#3d5a80`. Each has a light background tint for pills.
- Type: system UI sans for text (`next/font` with Inter is fine), and a monospace with tabular figures for every amount, id and reference (`IBM Plex Mono` via next/font, or `ui-monospace`). Amounts are right-aligned in whole dollars, except Form 8949 lots, which keep cents.
- Density: 14px base text, 32px table rows, 8px spacing grid. Comfortable, not cramped. Focus ring: 2px accent outline with offset, always visible on keyboard focus.
- Source documents render as a paper sheet: white page, subtle shadow, monospace printed_content, page number in the margin. Highlights are a translucent accent box using the extracted value's `position` (x0, y0, x1, y1 normalised to the page), with a small numbered tag.
- Light theme only for the prototype; all colours must meet WCAG 2.2 AA.

## Label vocabulary (two axes)
Where a number came from (provenance badge, small outlined pill with icon):
- `Engine v1/v2/v3`: the engine output exactly as delivered.
- `Exact`: carried forward along R-SUM / R-CARRY only.
- `Estimate`: change times a tax_effect_rates category; always says "estimate".
- `What-if`: one of the packet's five engine alternatives.
- `Adjusted`: an approved adjustment overlay (shows old → new on hover/focus).
- `AI-proposed`: suggested by the AI assistant, never final.
- `Client said`: from a questionnaire answer or message. Shows "client statement, not verification".
- `Simulated`: replayed events (e-file, signature, 2028 letter).

What a human did (review-state marker, filled icon plus word):
- `Unverified` (hollow circle)
- `Verified · DO` (check plus initials and level)
- `Changed since review` (triangle; clears only when someone re-verifies)
- `Blocking` (octagon; blocks sign-off or filing)

## Sensitive values
- Masked form keeps the last four: `***-**-3390`, account `****4471`, with a small lock icon.
- Staff without clearance (Marcus), clients and the AI assistant only ever receive masked values from the server.
- When a cleared user sees an unmasked value (e.g., on a document page), it carries a small "unmasked · logged" marker. A Reveal button (cleared roles only) asks for a typed reason and calls the reveal action.

## Layout
- Left rail (collapsible): Queue, Areas, Documents, Return, Activity. The current return and "as of" date sit at the top.
- Top bar: return name, engine version badge (v3), a search field (Cmd/Ctrl+K opens the command menu), and the role switcher. It shows the acting person's name, role and clearance, and is labelled "Demo role switcher", setting X-Proofline-Actor. The choice is kept in localStorage.
- Main area uses list plus detail: the list on the left, the selected item on the right, so reviewers never lose their place. The URL reflects the selection (deep links work).
- Any number anywhere is clickable and opens the Trace drawer from the right without leaving the page.

## Keyboard (single-key shortcuts only when a list or panel has focus; can be turned off in a settings menu, WCAG 2.1.4)
- `J` / `K` next or previous item, `Enter` open, `Esc` close or back, `X` select, `/` filter
- `G Q` queue, `G A` areas, `G D` documents
- `T` trace the focused number, `V` mark verified, `N` add review note
- `?` shortcut sheet, `Cmd/Ctrl+K` command menu (search cases, lines, documents, actions)
- Destructive or signing actions are never a single key: they need a confirm step.

## "Since you last looked"
- Per person, the app records when they last opened each case, area and document (stored per actor; this is UI state, not a workpaper event).
- Lists show a dot on anything changed since then. Opening an item shows a one-line banner: "Changed since you last looked (Oct 18, 4:10 PM): revision 2 submitted by Priya; tax effect now 15,536 estimate".
- A "Viewed" mark per item clears itself automatically when the item changes (like GitHub's "Viewed" on files).

## S1 Review queue (Step 5)
- Tabs with counts, role-aware. "Needs me": preparer = open and returned cases assigned to me; reviewer = in_review not proposed by me; partner = awaiting_partner. Then "All open", "Waiting on client", "Resolved".
- Grouped by severity: Blocks filing, Tax amount, Penalty risk, Info. The group header shows the count and total tax effect.
- Each row: unread dot; plain-language title ("Theo's SSN doesn't match his Social Security card"); one-line "why it's here" from the finding; area; tax effect (federal / CA with provenance label and direction, e.g. "overstated 15,536 · Estimate"); status pill; assignee initials; age.
- Selecting a row opens the case on the right. Keyboard J/K walks the list.
- Empty state says what "done" means ("Nothing needs you. 3 cases are waiting on the client.").

## S2 Case detail (Step 5)
- Header: title, status stepper showing the C1 path (open → investigating → in review → awaiting partner → resolved) with the current step marked, severity, area, tax effect with labels, assignee.
- "Why this is flagged": the check's observed and expected sentences, limitations in smaller text, and the check id and version in mono.
- Evidence: one card per evidence reference. Document evidence shows a small snippet of the source page with the field highlighted; a click opens the Trace drawer. Client statements carry the "Client said" label and the warning "client statement, not verification". Prior-year and agency references show as typed cards.
- Proposal: the resolution type (resolve evidence conflict, record judgment, adjust number, mark legitimate), each with exactly the fields C1 names. Submit is disabled with a named reason until the required evidence is attached. Revisions are listed (Revision 1, Revision 2) with what changed between them; a decision always names the revision it applies to.
- Decision bar (sticky at the bottom): only the actions this role may take now. Others are shown disabled with the rule ("You proposed this. Nobody reviews their own work."). Approve shows where it will go next ("→ Resolved" or "→ Awaiting partner: tax effect over 1,000").
- Activity: the event timeline for this case, newest first, with actor, role, time and revision.
- W1 must hold: Daniel approves the RSU revision 2 from his queue in four clicks or fewer (open queue item → Approve → confirm).

## S4 Trace view (Step 6)
- Opens as a right drawer from any number, or full page at /trace/line/{key}.
- Left: the number card. Line key and label, value with provenance and review-state labels; the rule (R-SUM, R-CARRY, ...); the calculation stack (Engine v3 value → each adjustment with label + value); inputs above, one level at a time with expand; "used by" below, one level at a time.
- Right: the source. Document sources render the page as paper with every field this line used highlighted and numbered; tabs if several documents. Non-document sources render as typed cards (client statement, prior-year pointer, engine parameter, household fact), so no line ever traces to nothing.
- Excluded or duplicate documents are listed under "Not used here" with the reason ("D10 is a second image of D09, counted once").
- Document trace (/documents/{id}): the page viewer, the disposition, and "Landed in" (every line that uses it) or why it didn't land (duplicate, superseded, unread page).
- Redaction applies to the rendered page text for the acting role (W2: Marcus sees only masked values and nothing is logged as revealed).

## S3 Area page (Step 7)
- Header: area name, sign-off state ("Not signed", "Signed v2 · DO · Oct 18", or "Signed, change pending"), engine version, active adjustments count.
- Order of the page: (1) what blocks sign-off, (2) changes since the last sign-off (with "confirm carry-over" per replaced document, A2), (3) tie-outs (totals that must agree, each ✓ or ✗ with the difference), (4) exceptions, (5) grouped detail.
- Large detail (e.g., Form 8949's 302 lines): grouped by issuer and box, with a summary row per group (count, proceeds, basis, gain, how many verified); expand to see lots. Bulk verify a group: if any item can't be verified, nothing applies and the bad item is named. After applying, an Undo toast appears; undo writes reversing events.
- The Sign-off button is always visible. When disabled, it lists the reasons. Signing shows what is being signed (scope version, engine version, adjustments, fingerprints in short form).
- "Changes" tab: v1 → v2 → v3 line changes with the cause (which document or decision), filterable to "only changed".

## Accessibility
- WCAG 2.2 AA. All actions reachable by keyboard; visible focus; 24×24px minimum targets; status changes announced via live regions; tables use proper headers and `aria-sort`; drawers trap focus and return it on close; no information by colour alone.
