"""Gneva FastAPI application."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gneva.config import get_settings
from gneva.api import auth, meetings, bot, memory, ask, actions
from gneva.api.webhook import router as webhook_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown
    from gneva.db import engine
    await engine.dispose()


app = FastAPI(
    title="Gneva",
    description="AI team member that joins your meetings and builds organizational memory",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(meetings.router)
app.include_router(bot.router)
app.include_router(memory.router)
app.include_router(ask.router)
app.include_router(actions.router)
app.include_router(webhook_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "gneva"}
