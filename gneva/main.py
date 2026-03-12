"""Gneva FastAPI application."""

import logging
import sys

# Configure logging so bot INFO messages are visible
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    stream=sys.stderr,
)
from contextlib import asynccontextmanager

# Fix: Windows asyncio subprocess support for Playwright
# uvicorn uses ProactorEventLoop on Windows but Playwright needs subprocess support
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from gneva.config import get_settings
from gneva.api import auth, meetings, bot, memory, ask, actions
from gneva.api.webhook import router as webhook_router
from gneva.api.upload import router as upload_router
from gneva.api.calendar import router as calendar_router
from gneva.api.notifications import router as notifications_router
from gneva.api.analytics import router as analytics_router
from gneva.api.slack import router as slack_router
from gneva.api.realtime import router as realtime_router
from gneva.api.scheduler import router as pm_router
from gneva.api.settings import router as settings_router
from gneva.api.roi import router as roi_router
from gneva.api.followups import router as followups_router
from gneva.api.dynamics import router as dynamics_router
from gneva.api.contradictions import router as contradictions_router
from gneva.api.agents import router as agents_router
from gneva.api.acs import router as acs_router
from gneva.bot.twilio_dialin import router as twilio_router
from gneva.api.elevenlabs_tools import router as el_tools_router

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — initialize bot manager
    from gneva.bot.manager import BotManager
    from gneva.api.bot import set_bot_manager

    bot_manager = BotManager(
        bot_name=settings.bot_name,
        consent_message=settings.bot_consent_message,
        audio_dir=settings.audio_storage_path,
        max_concurrent=settings.bot_max_concurrent,
        lobby_timeout=settings.bot_lobby_timeout_sec,
        max_duration=settings.bot_max_duration_sec,
    )
    # Apply database indexes
    try:
        from gneva.migrations.add_indexes import add_indexes
        from gneva.db import engine
        await add_indexes(engine)
        logger.info("Database indexes applied")
    except Exception as e:
        logger.warning(f"Database index creation failed: {e}")

    # Seed builtin agent profiles
    try:
        from gneva.bot.agent_router import seed_builtin_agents
        agent_count = await seed_builtin_agents()
        logger.info(f"Startup: {agent_count} builtin agent profiles ready")
    except Exception as e:
        logger.warning(f"Agent profile seeding failed: {e}")

    try:
        await bot_manager.start()
        set_bot_manager(bot_manager)
        logger.info("Bot manager initialized")
    except Exception as e:
        logger.warning(f"Bot manager init failed (Playwright not installed?): {e}")
        logger.warning("Meeting bot joining will be unavailable")

    # Start background scheduler (Stage 5)
    scheduler = None
    if settings.scheduler_enabled:
        try:
            from gneva.services.scheduler import Scheduler
            from gneva.api.scheduler import set_scheduler
            scheduler = Scheduler()
            await scheduler.start()
            set_scheduler(scheduler)
            logger.info("Background scheduler started")
        except Exception as e:
            logger.warning(f"Scheduler init failed: {e}")

    yield

    # Shutdown
    if scheduler:
        try:
            await scheduler.stop()
        except Exception:
            pass
    try:
        await bot_manager.stop()
    except Exception:
        pass
    from gneva.db import engine
    await engine.dispose()


app = FastAPI(
    title="Gneva",
    description="AI team member that joins your meetings and builds organizational memory",
    version="0.1.0",
    lifespan=lifespan,
)


# --- S14: Security headers middleware ---
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if not settings.debug:
            response.headers["Content-Security-Policy"] = "default-src 'self'"
        return response


app.add_middleware(SecurityHeadersMiddleware)


# --- S11: CORS production mode safety ---
_cors_origins = list(settings.cors_origins)
if not settings.debug and "*" in _cors_origins:
    logger.warning(
        "Wildcard '*' in CORS origins is unsafe in production — removing it."
    )
    _cors_origins = [o for o in _cors_origins if o != "*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
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
app.include_router(upload_router)
app.include_router(calendar_router)
app.include_router(notifications_router)
app.include_router(analytics_router)
app.include_router(slack_router)
app.include_router(realtime_router)
app.include_router(pm_router)
app.include_router(settings_router)

# Serve ACS Calling SDK static files (HTML + JS bundle)
try:
    from pathlib import Path
    from starlette.staticfiles import StaticFiles
    acs_calling_dir = Path(__file__).parent / "bot" / "acs_calling"
    if acs_calling_dir.exists():
        app.mount("/acs-calling", StaticFiles(directory=str(acs_calling_dir)), name="acs-calling")
        logger.info(f"Mounted ACS Calling SDK static files at /acs-calling")
except Exception as e:
    logger.debug(f"ACS calling static mount skipped: {e}")
app.include_router(roi_router)
app.include_router(followups_router)
app.include_router(dynamics_router)
app.include_router(contradictions_router)
app.include_router(agents_router)
app.include_router(acs_router)
app.include_router(twilio_router)
app.include_router(el_tools_router)


@app.get("/health")
async def health():
    from sqlalchemy import text
    from gneva.db import engine
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "service": "gneva", "db": "up"}
    except Exception:
        return {"status": "degraded", "db": "down"}
