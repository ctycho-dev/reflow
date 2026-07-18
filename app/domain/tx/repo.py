# app/domain/tx/repo.py
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.tx.model import TxJob
from app.enums.enums import TxJobStatus
from app.domain.campaign.model import MerkleRoot


class TxJobRepository:
    """Persistence + safe claiming for the signer worker's transaction queue."""

    async def claim_next(
        self, session: AsyncSession, statuses: list[str], chain_id: int
    ) -> TxJob | None:
        """
        Atomically claim the oldest job in one of `statuses`, using
        FOR UPDATE SKIP LOCKED so concurrent workers never grab the same row.

        Must run inside a transaction the caller commits: the row lock is held
        until commit, so the claim (status flip + locked_at) and the lock live
        in the same transaction. Returns the claimed TxJob, or None if no job is
        available (all either absent or locked by other workers).
        """
        result = await session.execute(
            select(TxJob)
            .where(
                TxJob.status.in_(statuses),
                TxJob.chain_id == chain_id,
            )
            .order_by(TxJob.id.asc())
            .limit(1)
            .with_for_update(skip_locked=True)   # <-- FOR UPDATE SKIP LOCKED
        )
        job = result.scalar_one_or_none()
        if job is None:
            return None

        # mark it claimed while we still hold the row lock (same transaction)
        job.locked_at = datetime.now(timezone.utc)
        await session.flush()
        return job

    async def enqueue_setmerkleroot(
        self,
        session: AsyncSession,
        *,
        chain_id: int,
        to_address: str,
        data: bytes,
        campaign_id: int,
    ) -> TxJob:
        """Create a pending tx_job for a campaign's setMerkleRoot call."""
        job = TxJob(
            chain_id=chain_id,
            to_address=to_address,
            data=data,
            campaign_id=campaign_id,
            status=TxJobStatus.pending,
        )
        session.add(job)
        await session.flush()
        return job

    async def find_pending_roots_without_job(self, session: AsyncSession, chain_id: int):
        """
        Campaigns with a merkle_roots row in status 'pending' that have no
        tx_job yet — the signer enqueues these as its first step, keeping the
        finalizer pure off-chain.
        """
        result = await session.execute(
            select(MerkleRoot)
            .outerjoin(TxJob, TxJob.campaign_id == MerkleRoot.campaign_id)
            .where(
                MerkleRoot.status == TxJobStatus.pending,
                MerkleRoot.chain_id == chain_id,
                TxJob.id.is_(None),
            )
        )
        return list(result.scalars().all())

    async def mark(
        self,
        session: AsyncSession,
        job: TxJob,
        *,
        status: str,
        nonce: int | None = None,
        tx_hash: bytes | None = None,
        gas_price=None,
        mined_block: int | None = None,
        last_error: str | None = None,
        bump_attempts: bool = False,
    ) -> None:
        """Update a claimed job's tracking fields. Caller owns the transaction."""
        job.status = status
        if nonce is not None:
            job.nonce = nonce
        if tx_hash is not None:
            job.tx_hash = tx_hash
        if gas_price is not None:
            job.gas_price = gas_price
        if mined_block is not None:
            job.mined_block = mined_block
        if last_error is not None:
            job.last_error = last_error
        if bump_attempts:
            job.attempts += 1
        await session.flush()
