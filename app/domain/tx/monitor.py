# app/domain/tx/monitor.py
"""
Monitor + reconcile for the signer worker.

monitor: for jobs in 'submitting'/'mined', check the chain and advance them:
    submitting -> mined (tx found in a block)
    mined      -> confirmed (>= CONFIRMATIONS deep) -> flip merkle_root confirmed

reconcile: same logic, run on startup, to resolve jobs the dual-write left in
'submitting' when a worker crashed. This is the payoff of persisting tx_hash
BEFORE broadcast — we can ask the chain "did 0xABC land?" and act on the truth.

The chain is the source of truth. We never trust our own send-call return; we
always confirm against on-chain state.
"""
from web3 import Web3
from web3.exceptions import TransactionNotFound

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.tx.model import TxJob
from app.domain.tx.repo import TxJobRepository
from app.domain.campaign.model import MerkleRoot
from app.enums.enums import TxJobStatus, MerkleRootStatus

CONFIRMATIONS = 3  # confirmation depth before we consider a root settled


class TxMonitor:
    def __init__(self, w3: Web3, repo: TxJobRepository):
        self.w3 = w3
        self.repo = repo

    async def check_job(self, session: AsyncSession, job: TxJob) -> None:
        """
        Resolve one in-flight job against the chain. Advances its status and,
        on confirmation, flips the linked merkle_root to confirmed.
        Caller owns the transaction.
        """
        if job.tx_hash is None:
            # 'submitting' with no hash = we crashed before signing. Reset to
            # pending so it gets re-picked and signed fresh.
            await self.repo.mark(session, job, status=TxJobStatus.pending)
            return

        tx_hash_hex = "0x" + job.tx_hash.hex()

        try:
            receipt = self.w3.eth.get_transaction_receipt(tx_hash_hex)
        except TransactionNotFound:
            # Not mined yet. Two sub-cases:
            #  (a) still propagating/pending -> leave as-is, check again next tick
            #  (b) it never made it on-chain (dropped) -> reconcile will rebroadcast
            # Distinguish by whether the mempool knows it:
            try:
                self.w3.eth.get_transaction(tx_hash_hex)
                # known to the node, just not mined -> wait
                return
            except TransactionNotFound:
                # unknown to the node -> it was dropped/never landed. Reset to
                # pending so the signer rebuilds + rebroadcasts (new hash/nonce).
                await self.repo.mark(
                    session, job,
                    status=TxJobStatus.pending,
                    last_error="tx not found on chain; will rebroadcast",
                )
                return

        # we have a receipt — it's mined
        if receipt["status"] == 0:
            # tx reverted on-chain (e.g. lost a race, role revoked). Terminal.
            await self.repo.mark(
                session, job,
                status=TxJobStatus.failed,
                mined_block=receipt["blockNumber"],
                last_error="tx reverted on-chain (receipt status 0)",
            )
            await self._fail_root(session, job)
            return

        # mined successfully — check confirmation depth
        current_block = self.w3.eth.block_number
        depth = current_block - receipt["blockNumber"]

        if depth < CONFIRMATIONS:
            # mined but not deep enough yet
            await self.repo.mark(
                session, job,
                status=TxJobStatus.mined,
                mined_block=receipt["blockNumber"],
            )
            return

        # confirmed to required depth -> terminal success
        await self.repo.mark(
            session, job,
            status=TxJobStatus.confirmed,
            mined_block=receipt["blockNumber"],
        )
        await self._confirm_root(session, job)

    async def _confirm_root(self, session: AsyncSession, job: TxJob) -> None:
        """Flip the linked merkle_root pending/submitting -> confirmed."""
        if job.campaign_id is None:
            return
        result = await session.execute(
            select(MerkleRoot).where(MerkleRoot.campaign_id == job.campaign_id)
        )
        root = result.scalar_one_or_none()
        if root is not None:
            root.status = MerkleRootStatus.confirmed
            root.set_tx_hash = job.tx_hash
            await session.flush()

    async def _fail_root(self, session: AsyncSession, job: TxJob) -> None:
        if job.campaign_id is None:
            return
        result = await session.execute(
            select(MerkleRoot).where(MerkleRoot.campaign_id == job.campaign_id)
        )
        root = result.scalar_one_or_none()
        if root is not None:
            root.status = MerkleRootStatus.failed
            await session.flush()

    async def find_inflight(self, session: AsyncSession) -> list[TxJob]:
        """Jobs that need chain-checking: submitting or mined."""
        result = await session.execute(
            select(TxJob).where(
                TxJob.status.in_(
                    [TxJobStatus.submitting.value, TxJobStatus.mined.value]
                )
            )
        )
        return list(result.scalars().all())