---
name: add-endpoint
description: Adds a FastAPI endpoint to the Proofline API with Pydantic models, permission checks, masking, revision checks for writes, and tests. Use when the user asks for a new API route or to change an existing one.
argument-hint: <what the endpoint should do>
---

Add an API endpoint that: $ARGUMENTS

Show the user the plan (steps 1-2) and wait for their OK before writing code.

1. **Design the contract.** Method, path, request model, response model, which roles may call it, which fields are sensitive, and whether it writes data
2. **Check the plan.** Read the matching step of `docs/PLAN.md`; confirm the endpoint is in scope
3. **Models.** Write Pydantic v2 request and response models. Sensitive fields are masked in the response model unless the caller's role allows them
4. **Route.** Write it in `api/proofline/routes/<name>.py`, keeping it thin, following `.claude/rules/python.md`:
   - take the current staff member as a dependency and check the role first
   - call a plain function for the logic
   - for writes: require the item's revision number, return 409 with the current state on mismatch, and append the event in the same transaction, through `proofline/actions/`
   - for unmasked sensitive reads: append a view-log event
   - sensitive fields are masked via `proofline/security/redact.py` before the response leaves the route
5. **Tests** in `api/tests/unit/test_route_<endpoint_name>.py`, at minimum:
   - an allowed role succeeds
   - a disallowed role gets 403
   - for sensitive fields: an uncleared role receives masked values
   - for writes: a stale revision gets 409 and nothing is written
6. **Run** `pytest api/tests/unit/test_route_<endpoint_name>.py -q` and show the output
7. **Front-end types.** If the front end exists, regenerate the TypeScript types from the OpenAPI schema
8. **Summarize** in plain language what the endpoint does, then wait for the user's OK
