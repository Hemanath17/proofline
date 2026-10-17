---
name: wrap-session
description: Ends a work session by updating the project's tracking docs. Run manually with /wrap-session.
disable-model-invocation: true
---

## Current state

Uncommitted changes:
!`git status --short`

Recent commits:
!`git log --oneline -10`

## Instructions

Using the state above and this session's conversation:

1. **docs/TODO.md:** tick completed items, add new items discovered, and add a short "Session review" (date, what was done, what is next, open questions)
2. **docs/DECISIONS.md:** add one line per decision made this session: date, decision, why
3. **docs/AI_USAGE.md:** add what Claude built or suggested this session, what the user decided or changed, and any AI mistake that was caught and fixed
4. **docs/LESSONS.md:** if the user corrected the same kind of mistake this session, make sure a one-line lesson exists for it; keep the file short
5. **Report** to the user in plain language: what was updated, whether there are uncommitted changes, and the suggested first step for next session

Do not commit. Ask the user whether to commit.
