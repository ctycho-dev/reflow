# app/domain/contract/model.py
from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database.connection import Base
from app.common.audit_mixin import TimestampMixin


class ProtocolContract(Base, TimestampMixin):
    __tablename__ = "protocol_contracts"

    chain_id:       Mapped[int] = mapped_column(BigInteger, primary_key=True)
    address:        Mapped[str] = mapped_column(String, primary_key=True)  # 0x-prefixed, lowercase

    protocol_slug:  Mapped[str] = mapped_column(String, nullable=False, index=True)
    protocol_name:  Mapped[str] = mapped_column(String, nullable=False)
    protocol_color: Mapped[str] = mapped_column(String(7), nullable=False, default="#000000")
    label:          Mapped[str] = mapped_column(String, nullable=False)