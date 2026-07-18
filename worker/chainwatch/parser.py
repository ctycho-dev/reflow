# jobs/chainwatch/parser.py
from datetime import datetime, timezone
from app.core.logger import get_logger


logger = get_logger(__name__)


def _ensure_0x(value: str) -> str:
    """Helper to ensure the string starts with 0x and is lowercase."""
    val_lower = value.lower()
    return val_lower if val_lower.startswith("0x") else f"0x{val_lower}"


def parse_raw_event(raw: dict, block_timestamp: int, chain_id: int) -> dict:
    """Map web3 event log → transfer dict matching the DB schema. symbol param removed — unused."""
    args = raw["args"]
    return {
        "tx_hash":         _ensure_0x(raw["transactionHash"].hex()),
        "log_index":       raw["logIndex"],
        "block_number":    raw["blockNumber"],
        "block_timestamp": datetime.fromtimestamp(block_timestamp, tz=timezone.utc),
        "chain_id":        chain_id,
        "token":           _ensure_0x(raw["address"]),
        "from_address":    _ensure_0x(args["from"]),
        "to_address":      _ensure_0x(args["to"]),
        "amount":          str(args["value"])
    }


def log_event(raw: dict, symbol: str, decimals: int) -> None:
    args     = raw["args"]
    block    = raw["blockNumber"]
    amount  = args["value"] / (10 ** decimals)
    is_mint  = args["from"] == "0x0000000000000000000000000000000000000000"

    logger.info(
        "[%s] %s | block %d | logIndex %d | from=%s to=%s amount=%.6f tx=%s",
        symbol,
        "MINT" if is_mint else "Transfer",
        block,
        raw["logIndex"],
        args["from"],
        args["to"],
        amount,
        raw["transactionHash"].hex(),
    )