# app/domain/enrollment/model.py
from decimal import Decimal
from datetime import datetime
from sqlalchemy import (
    BigInteger, CheckConstraint, DateTime, ForeignKey, Numeric, String,
    UniqueConstraint, ForeignKeyConstraint, Index,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.database.connection import Base
from app.common.audit_mixin import TimestampMixin


class Enrollment(Base, TimestampMixin):
    __tablename__ = "enrollments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    wallet_chain_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    wallet_address: Mapped[str] = mapped_column(String, nullable=False)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), nullable=False)

    total_volume: Mapped[Decimal] = mapped_column(
        Numeric(78, 0), nullable=False, default=Decimal(0), server_default="0"
    )
    qualified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["wallet_chain_id", "wallet_address"],
            ["wallets.chain_id", "wallets.address"],
        ),
        UniqueConstraint(
            "wallet_chain_id", "wallet_address", "campaign_id",
            name="uq_enrollment_wallet_campaign",
        ),
        CheckConstraint("total_volume >= 0", name="ck_enrollments_volume_nonneg"),
        Index("ix_enrollments_wallet", "wallet_chain_id", "wallet_address"),
        Index("ix_enrollments_campaign", "campaign_id"),
        Index(
            "ix_enrollments_campaign_volume",
            "campaign_id", "total_volume",
        ),
    )