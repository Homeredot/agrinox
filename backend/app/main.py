import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import router
from app.core.config import settings
from app.db.models import User
from app.db.session import SessionLocal
from app.services.notifications import configured as email_configured, send_due_calendar_reminders


def _dispatch_due_emails() -> None:
    with SessionLocal() as db:
        users = db.query(User).filter(User.is_active.is_(True)).all()
        for user in users:
            send_due_calendar_reminders(db, user)


async def _email_reminder_loop() -> None:
    while True:
        await asyncio.to_thread(_dispatch_due_emails)
        await asyncio.sleep(settings.email_poll_seconds)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(_email_reminder_loop()) if email_configured() else None
    try:
        yield
    finally:
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


app = FastAPI(title="Agrinox API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list({settings.frontend_origin, "http://127.0.0.1:3000"}),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.exception_handler(Exception)
async def unhandled(_request: Request, _exc: Exception):
    return JSONResponse(status_code=500, content={"detail": "An unexpected server error occurred"})

