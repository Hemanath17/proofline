---
name: frontend-design
description: Use whenever building a new screen or component, or reshaping an existing one, in web/app/ or web/components/ (queue, cases, areas, trace, documents, client workspace, firm status, eval page). Read this before writing JSX, CSS or Tailwind classes for any of Proofline's screens.
---

# Frontend design for Proofline

Proofline is a CPA's working tool, not a marketing site or a consumer app. Approach this the way a design lead at a studio that specializes in professional, data-dense software would: the job is to make a 20-year CPA trust this more than a spreadsheet, a new hire feel oriented on day one. That is a specific brief with a specific visual vocabulary (dense tables, tie-outs, trust markers, provenance, redaction) — not a generic SaaS dashboard, and not a template.

## The visual system is already decided — read it first

`docs/UX.md` is the agreed design: color tokens, the two-axis label vocabulary (source/calculation trust marker), sensitive-value masking treatment, layout, keyboard shortcuts, and the S1-S4 screen specs. Read it before touching any screen. This skill is about **execution quality within that system** — typography, hierarchy, spacing, restraint, avoiding templated defaults — not about replacing it. If something here seems to conflict with docs/UX.md, docs/UX.md wins; flag the conflict instead of silently picking one.

## Avoid the tells of generated UI

These are the commonest signs a screen was defaulted rather than designed, and they show up constantly in dashboards and admin tools specifically — watch for them here:
- The SaaS-cardy section chopped into identical rounded cards, one border-radius on everything regardless of hierarchy, the same soft grey shadow under each, gradient washes as decoration.
- Numbered markers (01 / 02 / 03) or tracked-out ALL-CAPS eyebrow labels on content that isn't actually a sequence. A case queue is not a 3-step process; don't dress it like one.
- Meta strings joined with middle dots ("Daniel - Reviewer - 2 days ago"), labels built as "WORD - fragment" with a spaced em dash, a arrow appended to every button and link, a monospace face for every small data label out of habit rather than because it's actually tabular/numeric data.
- Fade-and-slide-up entrance animation on every card, hover-lift on every row. Reserve motion for things that answer what the person did (an item resolving, a batch verifying, a value updating since they last looked) — not decoration on load.
- Accenting a single word in a headline with color or italics; adding a typographic eyebrow label above content that doesn't need framin

Hierarchy on a page like the review queue or an area page should come from real structure — severity, whether something blocks filing, whose turn it is — not from decorative repetition of the same card shape for everything.

## Where this tool actually needs visual distinctiveness

Spend design effort on the places a CPA looks at for hours, not on chrome:
- **The trust marker** (source/calculation, two axes) is the single most load-bearing piece of UI in the product. It must be instantly scannable and never ambiguous — this is the "spend your boldness in one place" moment, more than any hero or landing treatment.
- **Grouped large detail** (L1-L6: sales lots, depreciation assets, K-1 lines) needs a layout that reads as groups-with-exceptions-surfaced, not a flat table of 300 rows. Exceptions should be visually first, not just sorted first.
- **Redaction** (masked SSNs, PINs inside document text) needs a treatment that reads as "intentionally withheld," not as a rendering bug or a placeholder that looken.
- **"Since you last looked"** highlighting needs to be visible at a glance without being noisy on a page the person reopens dozens of times a day.

Typography: pick one or two type families deliberately for this tool (something built for dense data and long reading sessions - not a display face chosen for a hero). If docs/UX.md already names fonts/tokens, use those; don't introduce a second system. Line length under ~80 characters for prose (case notes, review comments); tabular numeric data can and should be set in a face that aligns digits cleanly.

## Process

1. **Plan before coding.** For any new screen or a real reshape of an existing one, write a short plan first: what's the one thing on this screen that matters most (the hero of a CPA tool's screen is usually "what do I need to act on," not an image), what's the layout concept (describe it in a sentence plus a rough ASCII wireframe), and what in docs/UX.md this screen must respect.
2. **Review the plan against the brief before building.** Ask: does any part of this read like the generic admin-dashboard default rather than something shaped by Proofline's actual content (cases, tie-outs, trust markers, redaction)? If so, revise and say what changed and why - a line in your summary is enough, it doesn't need its own docs/DECISIONS.md entry unless it's a real design decision worth remembering.
3. **Build**, following CLAUDE.md's existing style rules (simple, explicit TSX, strict types) and watching CSS specificity - don't let a type-based selector and a utility class silently cancel each other on spacing.
4. **Critique with a screenshot**, exactly as CLAUDE.md already requires ("Show, don't claim... run the app, take a screenshot and compare it with the plan"). Look specifically for the generated-UI tells above before calling it done. If you can't run Playwright in this environment, say so explicitly rather than describing what the screen "should" look like.

## Writing on screen

Button and action labels use the product's own vocabulary and active voice: "Sign off", "Approve", "Mark as duplicate", "Confirm disposition" - never a generic "Submit" or "Save". The label that triggers an action should match the label of its result (a "Sign off" button produces a sign-off confirmation, not a generic "Saved" toast). Error and conflict states (a 409 stale revision, a blocked filing) explain what happened and what to do next, in the product's voice - never vague, never apologetic. An empty state (no open cases, nothing pending) is a legitimate good state here, not a placeholder to dress up - say plainly what it means ("Nothing is waiting on you").

## Restraint

Within a tool this information-dense, restraint matters more than usual: don't let decoration compete with the numbers. One considered hierarchy per screen, consistent spacing, real keyboard-focus visibility (CPAs live in keyboard shortcuts per docs/UX.md), and nothing that doesn't help someone understand what to look at first.
