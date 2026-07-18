# jobs/chainwatch/constants.py

ERC20_ABI = [
    {
        "anonymous": False,
        "name": "Transfer",
        "type": "event",
        "inputs": [
            {"name": "from",  "type": "address", "indexed": True},
            {"name": "to",    "type": "address", "indexed": True},
            {"name": "value", "type": "uint256", "indexed": False},
        ],
    }
]

POLL_INTERVAL: int = 15  # seconds
BACKFILL_CHUNK_SIZE: int = 10
CONFIRMATION_BLOCKS = 12