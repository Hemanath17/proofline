---
paths:
  - "api/**/*.py"
---

# Writing Python in api/

- Everything lives in the `proofline` package. Import it as `from proofline.<module> import ...`, never `from api....`
- Only `proofline/packet.py` opens the packet. It finds the file relative to itself (`Path(__file__).resolve().parent.parent / "data" / "packet.json"`), reads it once per process, checks it with Pydantic and keeps it in memory
- Routes in `proofline/routes/` stay thin. They validate the input, check who's asking, call a plain function and return a Pydantic model. The real logic lives in modules you can test without FastAPI
- Any route that touches client data takes the current actor (staff member, client or AI assistant) as a dependency and checks the role before anything else
- Every response goes through `proofline/security/redact.py`, so a role only sees what it's allowed to, and sensitive values are redacted even inside document text. Revealing a value writes a view-log event
- Every write goes through `proofline/actions/`. It needs the revision the person saw; if that's stale, return 409 with the current state. The event, the current state and any check-run snapshot are written in one transaction, and if a rule fails, nothing is written
- Only `proofline/db/` talks to the database. Everything else calls `repository.py`. Schema changes are Alembic migrations, and they never rewrite events
- Money is `Decimal`, never float maths, and is compared to the cent. Show whole dollars, except Form 8949 lots, which keep their cents
- Use `pathlib.Path` for paths, and `logging` rather than `print` in library code
- Errors should help the person reading them. Raise `HTTPException` with a clear `detail`; a 403 names the rule, such as "own work". Never let a known situation become a bare 500
