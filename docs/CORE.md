# Proofline: Core Idea and Data Model

## The problem

A tax return already gets computed correctly by the engine. What's missing is
proof: where did each number come from, how was it worked out, who checked
it, and what's still open. A 20-year CPA reviewing this return should trust
it more than a spreadsheet, and a new hire should be able to pick up any case
and know what to do. Proofline is a workpaper built for that trust, for one
household's 2025 return (the Okafor-Lindqvist case, MiraFlores AI).

## The core idea, in three lines

- There are three kinds of information, kept strictly separate: **the
  packet** (facts we never change), **the analysis** (worked out fresh from
  the packet every time), and **what people did** (events plus the current
  state, written together, in one transaction, or not at all).
- **Cases** are where problems get investigated and resolved. **Areas** are
  where completeness gets signed off. A case closes by producing a decision;
  an area closes by a CPA confirming nothing in it still needs attention.
- A **provenance resolver** sits in the middle of both. It understands every
  reference format in the packet (a document, an extracted value, a
  questionnaire answer, a prior-year pointer, a line key), identifies a claim
  by the thing itself rather than where it currently sits on the return, and
  can answer "what does this depend on, and what depends on it?" in both
  directions.

## The data model

**Append-only events are the single source of truth.** Every action — a case
moving state, a sign-off, an adjustment, a document being revealed to a
cleared reviewer — writes one event, carrying a `schema_version` so its shape
can evolve without ever rewriting history. Current-state tables exist only as
a materialized view: `rebuild.py` can replay every event from scratch and
reproduce the same state. Nothing is ever updated or deleted on the events
table — a database trigger enforces that independent of the application code,
so immutability doesn't rely on the code behaving. Undo is never a delete; it
is a new event that reverses an old one.

**Every write goes through one action service.** It takes the revision the
caller last saw; if that's stale, it returns 409 with the current state
rather than silently overwriting a decision someone else just made. The
event, the new current state, and any check-run snapshot are written in a
single transaction — a half-applied write is not a state this system can be
in.

**A claim is identified by the thing itself, never by its position on the
return.** A 1099-B lot is identified by issuer + account + lot id; a W-2 box
by employer EIN + employee + tax year + box; a household fact by
`household:<id>` + field, and so on for every kind of claim the packet can
produce. When a corrected document moves a lot from one form box to another,
it is still the same claim — this is what lets the system say "this changed"
instead of treating a corrected document as an unrelated new fact.

**Every number carries two separate labels**, never collapsed into one:
where it came from (the engine's own output, a plain carried-forward sum, a
what-if the packet already computed, an estimate from tax-effect rates, an
approved adjustment, something the AI proposed, something the client merely
said, or a simulated replay), and what a human did with it (unverified,
verified by whom at what level, changed since that verification, or actively
blocking sign-off or filing). The first label is a fact about the number; the
second is a fact about a person's judgment. Conflating them was the design
mistake the research behind this app explicitly ruled out.

**Roles are enforced once, in the API, never in the UI.** Staff, clients, and
a synthetic AI-assistant role are each defined by what they may read and
write; a client role, for instance, can read and submit evidence for their
own case but can never see another household's sensitive values, approve
anything, or sign off. Every response passes through one redaction module
before it leaves the server, masking sensitive values even inside rendered
document text, and every unmasked reveal writes its own audit event.

**The AI layer is a user, not a shortcut.** The Evidence Investigator reads
through the same four tools that wrap the API's own existing read routes (so
masking and permissions are enforced exactly once, never reimplemented for
the AI), and its output is a typed, schema-validated suggestion that passes
through a deterministic validator before a human ever sees it: every cited
claim must belong to the case under investigation, every cited document must
be reachable from that case's own evidence, and every cited number must
actually appear in that case's evidence. The AI can read and propose. It
cannot change a number, close a case, approve, or sign off — that limit comes
from the role and the action service, the same enforcement every other actor
goes through, not from anything in its prompt.
