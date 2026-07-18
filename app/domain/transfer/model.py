# app/domain/transfer/model.py
from decimal import Decimal
from datetime import datetime
from sqlalchemy import BigInteger, Numeric, DateTime, String, ForeignKeyConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database.connection import Base


class Transfer(Base):
    __tablename__ = "transfers"

    chain_id:        Mapped[int]      = mapped_column(BigInteger, primary_key=True)
    tx_hash:         Mapped[str]      = mapped_column(String, primary_key=True)
    log_index:       Mapped[int]      = mapped_column(primary_key=True)

    block_number:    Mapped[int]      = mapped_column(BigInteger, nullable=False)
    block_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    token:           Mapped[str]      = mapped_column(String, nullable=False)
    from_address:    Mapped[str]      = mapped_column(String, nullable=False)
    to_address:      Mapped[str]      = mapped_column(String, nullable=False)
    amount:          Mapped[Decimal]  = mapped_column(Numeric(precision=78, scale=0), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["chain_id", "token"],
            ["tokens.chain_id", "tokens.address"],
        ),
        Index("ix_transfers_chain_cursor",
              "chain_id", "block_number", "log_index"),
        Index("ix_transfers_chain_from_cursor",
              "chain_id", "from_address", "block_number", "log_index"),
        Index("ix_transfers_chain_to_cursor",
              "chain_id", "to_address", "block_number", "log_index"),
        Index("ix_transfers_chain_token_cursor",
              "chain_id", "token", "block_number", "log_index"),
    )