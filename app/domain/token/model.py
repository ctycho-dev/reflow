# app/domain/token/model.py
from sqlalchemy import BigInteger, String, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.database.connection import Base
from app.common.audit_mixin import TimestampMixin


class Token(Base, TimestampMixin):
    __tablename__ = "tokens"

    chain_id:  Mapped[int]  = mapped_column(BigInteger, primary_key=True)
    address:   Mapped[str]  = mapped_column(String, primary_key=True)
    symbol:    Mapped[str]  = mapped_column(String, nullable=False)
    name:      Mapped[str]  = mapped_column(String, nullable=False)
    decimals:  Mapped[int]  = mapped_column(Integer, nullable=False)
    color:     Mapped[str]  = mapped_column(String(7), nullable=False, default="#000000")
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true", nullable=False)