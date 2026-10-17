---
paths:
  - "api/**/*.py"
---

# Python rules (api/)

- Load the packet through one loader module (`api/packet.py`) that reads `api/data/packet.json` once, validates it with Pydantic, and caches it. Never open the packet file anywhere else
- Keep FastAPI routes thin: validate input, check permissions, call a plain function, return a Pydantic model. Business logic lives in plain modules that can be tested without FastAPI
- Every route that reads client data takes the current staff member as a dependency and checks their role before doing anything else
- Mask sensitive values (SSNs, bank and account numbers, IP PINs) in the response model on the server; the front end must never receive the unmasked value unless the role allows it, and every unmasked view writes a view-log event
- Writes: require the item's current revision number; on mismatch return HTTP 409 with the current state. Write the event and any derived change in one database transaction
- Money: never compare floats with `==`. Use the shared helper (`money_equal(a, b, tolerance)`) and state the tolerance. Return values are whole dollars, except Form 8949 lots, which are in cents
- Use `pathlib.Path` for file paths and `logging` instead of `print` in library code
- Errors: raise `HTTPException` with a clear `detail` message a user could act on; never return a bare 500 for a known condition
