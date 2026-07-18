from enum import StrEnum


class AppMode(StrEnum):
    """Runtime mode of the application."""
    PROD = "prod"
    DEV = "dev"
    TEST = "test"


class MerkleRootStatus(StrEnum):
    """Lifecycle of a campaign's root, driven by the finalizer + signer worker."""
 
    pending = "pending"        # tree built, root computed, not yet broadcast
    submitting = "submitting"  # setMerkleRoot tx signed + persisted, broadcast in flight
    confirmed = "confirmed"    # tx mined to required confirmation depth
    failed = "failed"          # tx permanently failed (needs operator attention)
    no_winners = "no_winners"


class TxJobStatus(StrEnum):
    pending = "pending"        # queued, not yet claimed by a worker
    submitting = "submitting"  # signed, tx_hash persisted, broadcast in flight
                               # (dual-write point — written BEFORE sendRawTransaction)
    mined = "mined"            # seen in a block, awaiting confirmation depth
    confirmed = "confirmed"    # reached N confirmations — terminal success
    failed = "failed"          # permanently failed (reverted / gave up) — needs attention