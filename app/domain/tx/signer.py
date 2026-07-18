# app/domain/tx/signer.py
"""
Local-key transaction signer + broadcaster with the dual-write crash-safety
invariant. Swap-to-KMS later happens at ONE seam: _sign_transaction().

The load-bearing rule:
    persist (status=submitting, tx_hash, nonce) BEFORE eth_sendRawTransaction.

Why: broadcasting is external + irreversible. If we broadcast first and crash
before recording it, restart can't tell the tx was already sent and would send
again (double-send / nonce collision). By persisting the deterministic tx_hash
first, a crashed worker's job is recoverable: on restart we look up tx_hash on
chain — mined? -> confirm. absent? -> rebroadcast. The persisted hash is our
memory across the crash.
"""
from decimal import Decimal

from eth_account import Account
from web3 import Web3

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.tx.model import TxJob
from app.domain.tx.repo import TxJobRepository
from app.enums.enums import TxJobStatus


class TxSigner:
    def __init__(self, w3: Web3, private_key: str, repo: TxJobRepository):
        self.w3 = w3
        self.account = Account.from_key(private_key)  # LOCAL KEY (swap: KMS)
        self.repo = repo

    @property
    def address(self) -> str:
        return self.account.address

    def _next_nonce(self) -> int:
        """
        Nonce at signing time. 'pending' count includes txs we've broadcast but
        that aren't mined yet, so sequential sends get sequential nonces. (A more
        robust design tracks a local nonce cursor to avoid RPC races; for a
        single serialized signer, pending-count is adequate.)
        """
        return self.w3.eth.get_transaction_count(self.address, "pending")

    def _sign_transaction(self, tx: dict) -> bytes:
        """
        THE KMS SEAM. Today: sign locally with the in-memory key. Later: send the
        tx hash to AWS KMS, get a DER signature, parse (r,s) + recover v, assemble
        the raw tx. Everything else in this class stays identical.
        """
        signed = self.account.sign_transaction(tx)
        return signed.raw_transaction

    async def sign_and_broadcast(
        self, session: AsyncSession, job: TxJob
    ) -> None:
        """
        Build -> sign -> PERSIST(submitting, hash) -> broadcast.
        Caller owns the transaction; this stages the dual-write and sends.
        """
        # --- build the transaction ---
        nonce = self._next_nonce()
        gas_price = self.w3.eth.gas_price
        tx = {
            "chainId": job.chain_id,
            "to": Web3.to_checksum_address(job.to_address),
            "data": job.data,
            "nonce": nonce,
            "gasPrice": gas_price,
            "value": 0,
        }
        # estimate gas (fail early on a reverting call, before we persist/broadcast)
        tx["gas"] = self.w3.eth.estimate_gas(
            {"from": self.address, "to": tx["to"], "data": job.data}
        )

        # --- sign (produces the deterministic raw tx + its hash) ---
        raw = self._sign_transaction(tx)
        tx_hash = self.w3.keccak(raw)  # deterministic hash of the signed tx

        # === DUAL-WRITE: persist BEFORE broadcast =========================
        # If we crash immediately after this commit but before/after broadcast,
        # reconcile-on-restart uses tx_hash to find out what actually happened.
        await self.repo.mark(
            session,
            job,
            status=TxJobStatus.submitting,
            nonce=nonce,
            tx_hash=bytes(tx_hash),
            gas_price=Decimal(gas_price),
            bump_attempts=True,
        )
        await session.commit()   # <-- the write lands before we touch the chain
        # ==================================================================

        # --- broadcast (external, irreversible) ---
        try:
            self.w3.eth.send_raw_transaction(raw)
        except Exception as e:
            # Broadcast failed. The row is 'submitting' with a known hash, so
            # reconcile will re-check the chain and rebroadcast if it never
            # landed. Record the error; do NOT flip to failed here (the tx may
            # actually have propagated despite the error).
            await self.repo.mark(
                session, job,
                status=TxJobStatus.submitting,
                last_error=str(e),
            )
            await session.commit()
            raise
