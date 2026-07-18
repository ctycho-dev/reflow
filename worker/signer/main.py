# jobs/signer/main.py
"""
The signer worker. One process, ticking. Each tick:

  1. RECONCILE (first tick only, on startup): re-check every in-flight job
     against the chain — this resolves jobs the dual-write left in 'submitting'
     when a previous worker crashed. THE payoff of persist-before-broadcast.
  2. ENQUEUE: turn pending merkle_roots into pending tx_jobs (keeps the
     finalizer pure off-chain).
  3. MONITOR: advance in-flight jobs (submitting->mined->confirmed), flipping
     roots to confirmed at depth.
  4. SEND: claim one pending job (FOR UPDATE SKIP LOCKED) and sign+broadcast it.

Each unit of work runs in its own transaction, so one failure never rolls back
the others. The claim's row lock is held for the whole send, serializing signers.
"""
import asyncio

from web3 import Web3

from app.domain.tx.repo import TxJobRepository
from app.domain.tx.signer import TxSigner
from app.domain.tx.monitor import TxMonitor
from app.domain.tx.calldata import make_build_calldata
from app.enums.enums import TxJobStatus
from app.core.logger import get_logger, setup_logging
from app.core.sections import PostgresConfig, BlockchainConfig
from app.database.connection import DatabaseManager


logger = get_logger()

cfg = BlockchainConfig()


async def reconcile(monitor: TxMonitor, db_manager: DatabaseManager):
    """Startup: resolve every in-flight job against the chain."""
    async with db_manager.session_scope() as session:
        jobs = await monitor.find_inflight(session)
    logger.info("reconcile: %d in-flight job(s)", len(jobs))
    for job in jobs:
        try:
            async with db_manager.session_scope() as session:
                fresh = await session.get(type(job), job.id)
                await monitor.check_job(session, fresh)
                await session.commit()
        except Exception:
            logger.exception("reconcile failed on job %d", job.id)


async def enqueue(repo: TxJobRepository, db_manager: DatabaseManager, build_calldata):
    """Turn pending roots into pending tx_worker."""
    async with db_manager.session_scope() as session:
        roots = await repo.find_pending_roots_without_job(session, chain_id=cfg.chain_id)
        for root in roots:
            data = build_calldata(root)  # ABI-encode setMerkleRoot(campaignId, root)
            await repo.enqueue_setmerkleroot(
                session,
                chain_id=root.chain_id,
                to_address=cfg.distributor_address,
                data=data,
                campaign_id=root.campaign_id,
            )
        await session.commit()
        if roots:
            logger.info("enqueued %d root(s)", len(roots))


async def monitor_inflight(monitor: TxMonitor, db_manager: DatabaseManager):
    async with db_manager.session_scope() as session:
        jobs = await monitor.find_inflight(session)
        await session.commit()
    for job in jobs:
        try:
            async with db_manager.session_scope() as session:
                fresh = await session.get(type(job), job.id)
                await monitor.check_job(session, fresh)
                await session.commit()
        except Exception:
            logger.exception("monitor failed on job %d", job.id)


async def send_one(db_manager: DatabaseManager, repo: TxJobRepository, signer: TxSigner):
    """Claim + sign + broadcast a single pending job (lock held across the send)."""
    async with db_manager.session_scope() as session:
        job = await repo.claim_next(
            session, [TxJobStatus.pending.value], chain_id=cfg.chain_id
        )
        if job is None:
            return  # nothing to send
        try:
            await signer.sign_and_broadcast(session, job)
            # sign_and_broadcast commits internally at the dual-write point
        except Exception:
            logger.exception("send failed on job %d", job.id)
            # job left 'submitting' with hash -> reconcile handles it


async def tick(db_manager: DatabaseManager, repo, signer, monitor, build_calldata):
    await enqueue(repo, db_manager, build_calldata)
    await monitor_inflight(monitor, db_manager)
    await send_one(db_manager, repo, signer)


async def main():
    setup_logging()
    w3 = Web3(Web3.HTTPProvider(cfg.rpc_url))
    live_chain_id = w3.eth.chain_id
    if live_chain_id != cfg.chain_id:
        logger.error(
            "chain mismatch: connected to %d, configured for %d — refusing to start",
            live_chain_id, cfg.chain_id,
        )
        raise SystemExit(1)

    build_calldata = make_build_calldata(w3, cfg.distributor_address)

    db_manager = DatabaseManager(PostgresConfig())
    db_manager.init_engine(application_name="reflow-signer")
    repo = TxJobRepository()
    signer = TxSigner(w3, cfg.signer_private_key, repo)
    monitor = TxMonitor(w3, repo)
 
    logger.info("signer worker starting; address=%s", signer.address)
    await reconcile(monitor, db_manager)  # crash recovery on startup
 
    while True:
        try:
            await tick(db_manager, repo, signer, monitor, build_calldata)
        except Exception:
            logger.exception("tick failed")
        await asyncio.sleep(cfg.tx_tick_seconds)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
