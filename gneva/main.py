"""Gneva FastAPI application."""

import logging
import sys

# Configure logging so bot INFO messages are visible
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    stream=sys.stderr,
)
from contextlib import asynccontextmanager

# Fix: Windows asyncio subprocess support for Playwright
# uvicorn uses ProactorEventLoop on Windows but Playwright needs subprocess support
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gneva.config import get_settings
from gneva.api import auth, meetings, bot, memory, ask, actions
from gneva.api.webhook import router as webhook_router
from gneva.api.demo import router as demo_router
from gneva.api.upload import router as upload_router
from gneva.api.calendar import router as calendar_router
from gneva.api.notifications import router as notifications_router
from gneva.api.analytics import router as analytics_router
from gneva.api.slack import router as slack_router
from gneva.api.realtime import router as realtime_router
from gneva.api.scheduler import router as pm_router
from gneva.api.settings import router as settings_router

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
app.include_router(demo_router)
app.include_router(upload_router)
app.include_router(calendar_router)
app.include_router(notifications_router)
app.include_router(analytics_router)
app.include_router(slack_router)
app.include_router(realtime_router)
app.include_router(pm_router)
app.include_router(settings_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "gneva"}
