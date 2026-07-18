# app/domain/checkpoint/model.py
from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database.connection import Base
from app.common.audit_mixin import TimestampMixin


class Checkpoint(Base, TimestampMixin):
    __tablename__ = "checkpoints"

    chain_id:    Mapped[int]        = mapped_column(BigInteger, primary_key=True, default=1)
    token:       Mapped[str]        = mapped_column(String, primary_key=True)
    start_block: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_block:  Mapped[int]        = mapped_column(BigInteger, nullable=False)