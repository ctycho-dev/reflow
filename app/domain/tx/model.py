# app/domain/tx/model.py
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger, CheckConstraint, DateTime, Integer, LargeBinary,
    Numeric, String, Text, Index,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.database.connection import Base
from app.common.audit_mixin import TimestampMixin
from app.enums.enums import TxJobStatus


class TxJob(Base, TimestampMixin):
    """
    A queue of on-chain transactions the signer worker must get mined reliably.

    Lifecycle (status, stored as string — app-level enum TxJobStatus):
        pending    -> queued, not yet touched by a worker
        submitting -> signed, tx_hash persisted, broadcast in flight (DUAL-WRITE
                      point: this row is written BEFORE eth_sendRawTransaction, so
                      a crash mid-broadcast is recoverable by checking the chain
                      for tx_hash on restart)
        mined      -> seen in a block, awaiting confirmation depth
        confirmed  -> reached N confirmations; terminal success
        failed     -> permanently failed (reverted, or gave up); needs attention

    One TxJob typically corresponds to one setMerkleRoot call for a campaign.
    """
    __tablename__ = "tx_jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # --- what to send ---
    chain_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    to_address: Mapped[str] = mapped_column(String, nullable=False)   # target contract
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)  # ABI-encoded calldata
    # link back to the domain object this tx settles (nullable — not all jobs are roots)
    campaign_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # --- status + tracking ---
    status: Mapped[str] = mapped_column(
        String, nullable=False, server_default=TxJobStatus.pending
    )
    # the nonce assigned at signing time (null until we sign)
    nonce: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # deterministic tx hash, persisted BEFORE broadcast (the reconcile anchor)
    tx_hash: Mapped[bytes | None] = mapped_column(LargeBinary(32), nullable=True)
    # gas price we last signed with (wei) — needed for RBF bump decisions
    gas_price: Mapped[Decimal | None] = mapped_column(Numeric(78, 0), nullable=True)

    # --- queue mechanics ---
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # when a worker claimed this row (FOR UPDATE SKIP LOCKED); lets us detect
    # stale claims from a crashed worker
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # block number where mined (null until mined) — for confirmation-depth math
    mined_block: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    __table_args__ = (
        CheckConstraint("attempts >= 0", name="ck_tx_jobs_attempts_nonneg"),
        CheckConstraint("nonce >= 0", name="ck_tx_jobs_nonce_nonneg"),
        # worker claim query: find claimable jobs by status, oldest first
        Index("ix_tx_jobs_status", "status", "id"),
    )
