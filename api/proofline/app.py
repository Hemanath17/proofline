from fastapi import FastAPI

from proofline.routes import events, health

app = FastAPI(title="Proofline API")

app.include_router(health.router, prefix="/api")
app.include_router(events.router, prefix="/api")
