# jobs/finalizer/main.py
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.sections import PostgresConfig
from app.database.connection import DatabaseManager
from app.domain.campaign.model import Campaign, MerkleRoot
from app.domain.campaign.finalizer_repo import FinalizerRepository
from app.domain.campaign.finalizer_service import FinalizerService, FinalizationError
from app.core.logger import setup_logging, get_logger

logger = get_logger()

TICK_SECONDS = 60
BATCH_SIZE = 100


async def find_finalizable_campaign_ids(session) -> list[int]:
    """Campaigns that have ended and have NO merkle_roots row yet."""
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(Campaign.id)
        .outerjoin(MerkleRoot, MerkleRoot.campaign_id == Campaign.id)
        .where(
            Campaign.ends_at <= now,
            MerkleRoot.campaign_id.is_(None),
        )
        .order_by(Campaign.id.asc())
        .limit(BATCH_SIZE)
    )
    return [row.id for row in result.all()]


async def tick(db: DatabaseManager, service: FinalizerService):
    """One sweep. Each campaign finalized in its OWN transaction so one failure
    doesn't roll back the others."""
    async with db.session_scope() as session:
        ids = await find_finalizable_campaign_ids(session)

    if not ids:
        return

    logger.info("finalizer: %d campaign(s) to finalize", len(ids))
    for cid in ids:
        try:
            async with db.session_scope() as session:
                root = await service.finalize_campaign(session, cid)
                await session.commit()
            logger.info(
                "finalized campaign %d: status=%s winners=%d",
                cid, root.status, root.winner_count,
            )
        except FinalizationError as e:
            logger.warning("skip campaign %d: %s", cid, e)
        except Exception:
            logger.exception("finalizer failed on campaign %d", cid)


async def main():
    db = DatabaseManager(PostgresConfig())
    db.init_engine(application_name="reflow-finalizer")
    service = FinalizerService(FinalizerRepository())

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        tick, "interval", seconds=TICK_SECONDS, max_instances=1,
        args=[db, service],
    )
    scheduler.start()
    logger.info("finalizer started (tick=%ds)", TICK_SECONDS)
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
    finally:
        await db.close()


if __name__ == "__main__":
    setup_logging()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass