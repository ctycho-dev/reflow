# app/common/audit_mixin.py
from sqlalchemy import DateTime
from sqlalchemy.orm import declarative_mixin, declared_attr, Mapped, mapped_column
from datetime import datetime, timezone


@declarative_mixin
class TimestampMixin:
    """Basic timestamp audit fields."""
    
    @declared_attr
    def created_at(cls) -> Mapped[datetime]:
        return mapped_column(
            DateTime(timezone=True),
            default=lambda: datetime.now(timezone.utc),
            nullable=False
        )

    @declared_attr
    def updated_at(cls) -> Mapped[datetime]:
        return mapped_column(
            DateTime(timezone=True),
            default=lambda: datetime.now(timezone.utc),
            onupdate=lambda: datetime.now(timezone.utc),
            nullable=False
        )
