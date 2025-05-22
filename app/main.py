from __future__ import annotations

from fastapi import FastAPI

from app.handlers import webhook_handler, scheduled_handler

app = FastAPI(title="DietBot API")

app.include_router(webhook_handler.router)
app.include_router(scheduled_handler.router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"} 