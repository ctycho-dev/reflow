# app/domain/wallet/model.py
from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database.connection import Base
from app.common.audit_mixin import TimestampMixin


class Wallet(Base, TimestampMixin):
    __tablename__ = "wallets"

    chain_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=1)
    address:  Mapped[str] = mapped_column(String, primary_key=True)