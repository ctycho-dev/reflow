# jobs/checker/main.py
import asyncio
import signal
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.logger import get_logger, setup_logging
from app.core.sections import PostgresConfig
from app.database.connection import DatabaseManager
from worker.checker.job import CheckerJob

# ==============================
# python3 -m worker.checker.main
# ==============================

logger = get_logger(__name__)

TICK_INTERVAL_SECONDS = 60


async def main() -> None:
    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    db = DatabaseManager(PostgresConfig())
    db.init_engine(application_name="reflow-checker")

    job = CheckerJob(db)  # pass the manager in — see note about CheckerJob

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        job.run,
        trigger=IntervalTrigger(seconds=TICK_INTERVAL_SECONDS),
        id="enrollment_checker",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=30,
        next_run_time=datetime.now(timezone.utc),
    )

    scheduler.start()
    logger.info(
        "checker started: tick every %ds, batch=500, grace=12h. Press Ctrl+C to stop.",
        TICK_INTERVAL_SECONDS,
    )

    await stop_event.wait()

    logger.info("checker shutting down...")
    scheduler.shutdown(wait=True)
    await db.close()
    logger.info("checker shutdown complete.")


if __name__ == "__main__":
    setup_logging()
    asyncio.run(main())