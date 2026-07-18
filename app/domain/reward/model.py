# app/domain/reward/model.py
from decimal import Decimal
from sqlalchemy import (
    BigInteger, Numeric, ForeignKey, String,
    UniqueConstraint, ForeignKeyConstraint, Index,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.database.connection import Base
from app.common.audit_mixin import TimestampMixin


class Reward(Base, TimestampMixin):
    __tablename__ = "rewards"

    id:              Mapped[int]     = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    wallet_chain_id: Mapped[int]     = mapped_column(BigInteger, nullable=False)
    wallet_address:  Mapped[str]     = mapped_column(String, nullable=False)
    campaign_id:     Mapped[int]     = mapped_column(ForeignKey("campaigns.id"), nullable=False)
    amount:          Mapped[Decimal] = mapped_column(Numeric(78, 0), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["wallet_chain_id", "wallet_address"],
            ["wallets.chain_id", "wallets.address"],
        ),
        UniqueConstraint("wallet_chain_id", "wallet_address", "campaign_id",
                         name="uq_reward_wallet_campaign"),
        Index("ix_rewards_wallet", "wallet_chain_id", "wallet_address"),
        Index("ix_rewards_campaign", "campaign_id"),
    )