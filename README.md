# Proofline

Every number, traced to its proof.

Proofline is a web workpaper for one household's 2025 tax return, built for the MiraFlores AI "Redesign the Tax Workpaper" case study. Software has already read the client's documents and computed the return; Proofline lets a CPA team prove it. Click any number to see where it came from and how it was worked out. Every check, question, adjustment and sign-off is kept, and nothing is ever overwritten.

## What's inside
- `web/`: the Next.js front end
- `api/`: the FastAPI back end (Python package `proofline`)
- `docs/`: the plan, the contracts the code follows, the errors we found, and the decisions behind them
- `.claude/`: project instructions, agents and skills for building with Claude Code

## Running it locally
```bash
pip install -r api/requirements.txt
npm --prefix web install
cp .env.example .env.local      # then fill in the values
alembic -c api/alembic.ini upgrade head
vercel dev
```

## A note on the data
The household, the people, the numbers and every ID in the packet are invented by MiraFlores AI for the case study.
