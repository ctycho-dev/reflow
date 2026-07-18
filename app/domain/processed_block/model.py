# app/domain/processed_block/model.py
from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database.connection import Base
from app.common.audit_mixin import TimestampMixin


class ProcessedBlock(Base, TimestampMixin):
    __tablename__ = "processed_blocks"

    chain_id:     Mapped[int] = mapped_column(BigInteger, primary_key=True)
    token:        Mapped[str] = mapped_column(String, primary_key=True)
    block_number: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    block_hash:   Mapped[str] = mapped_column(String(66), nullable=False)
    parent_hash:  Mapped[str] = mapped_column(String(66), nullable=False)