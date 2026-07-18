# app/domain/campaign/model.py
from decimal import Decimal
from datetime import datetime
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database.connection import Base
from app.common.audit_mixin import TimestampMixin
from app.enums.enums import MerkleRootStatus


class Campaign(Base, TimestampMixin):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    chain_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
    token_address: Mapped[str] = mapped_column(String, nullable=False)

    target_contract_address: Mapped[str | None] = mapped_column(String, nullable=True)

    min_total_volume: Mapped[Decimal] = mapped_column(Numeric(78, 0), nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_amount: Mapped[Decimal] = mapped_column(Numeric(78, 0), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Cap & counter — atomic enrollment uses these together.
    max_recipients: Mapped[int] = mapped_column(Integer, nullable=False)
    enrolled_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    __table_args__ = (
        ForeignKeyConstraint(
            ["chain_id", "token_address"],
            ["tokens.chain_id", "tokens.address"],
        ),
        ForeignKeyConstraint(
            ["chain_id", "target_contract_address"],
            ["protocol_contracts.chain_id", "protocol_contracts.address"],
        ),
        # DB-level guarantees: cap can't be exceeded, count can't go negative.
        CheckConstraint("enrolled_count >= 0", name="ck_campaigns_enrolled_count_nonneg"),
        CheckConstraint("enrolled_count <= max_recipients", name="ck_campaigns_enrolled_within_cap"),
        CheckConstraint("max_recipients > 0", name="ck_campaigns_max_recipients_positive"),
        CheckConstraint("ends_at > starts_at", name="ck_campaigns_window_valid"),
        Index("ix_campaigns_chain_token", "chain_id", "token_address"),
        Index("ix_campaigns_chain_target", "chain_id", "target_contract_address"),
        Index("ix_campaigns_active", "starts_at", "ends_at"),
    )


class MerkleRoot(Base, TimestampMixin):
    __tablename__ = "merkle_roots"

    # one root per campaign; campaign_id is the natural PK
    campaign_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("campaigns.id"), primary_key=True)

    # the chain this root is settled on (rewards may settle on a different chain
    # than activity is indexed on — keep it explicit)
    chain_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # 32-byte root; byte-native because it is submitted/compared on-chain
    root_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)

    # tx that called setMerkleRoot (nullable until broadcast)
    set_tx_hash: Mapped[bytes | None] = mapped_column(LargeBinary(32), nullable=True)

    status: Mapped[MerkleRootStatus] = mapped_column(
        String,
        nullable=False,
        server_default=MerkleRootStatus.pending.value,
    )

    # total wei committed to this campaign's tree — sanity/funding check
    total_amount: Mapped[Decimal] = mapped_column(Numeric(78, 0), nullable=False)
    winner_count: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("total_amount >= 0", name="ck_merkle_roots_total_nonneg"),
        CheckConstraint("winner_count >= 0", name="ck_merkle_roots_winner_nonneg"),
    )


class RewardClaim(Base, TimestampMixin):
    __tablename__ = "reward_claims"

    campaign_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("campaigns.id"), primary_key=True)
    wallet_address: Mapped[str] = mapped_column(String, primary_key=True)

    # raw wei of reward token (REFLOW), matches transfers/amounts convention
    amount: Mapped[Decimal] = mapped_column(Numeric(78, 0), nullable=False)

    # position in the tree — fixes ordering, useful for regenerate/debug
    leaf_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # precomputed proof: JSONB array of 0x-prefixed sibling hashes, served
    # directly to the frontend/contract. Immutable once the root is set.
    proof: Mapped[list[str]] = mapped_column(JSONB, nullable=False)

    # claim state — mirrored from on-chain Claimed events, NOT set on API read.
    # NULL claimed_at == unclaimed.
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claim_tx_hash: Mapped[bytes | None] = mapped_column(LargeBinary(32), nullable=True)

    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_reward_claims_amount_nonneg"),
        CheckConstraint("leaf_index >= 0", name="ck_reward_claims_leaf_nonneg"),
        CheckConstraint("wallet_address = lower(wallet_address)", name="ck_reward_claims_addr_lower"),
        Index("ix_reward_claims_wallet", "wallet_address"),
    )
