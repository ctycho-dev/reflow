# app/domain/tx/calldata.py
"""
ABI-encode contract calls into the `data` bytes a TxJob carries.

Uses web3.py's contract encoder so the selector + argument packing exactly
match what the deployed RewardDistributor expects. The ABI fragment below is
the minimal piece needed for setMerkleRoot — no need for the full ABI file,
just this function's signature.
"""
from web3 import Web3

from app.domain.campaign.model import MerkleRoot

# minimal ABI fragment for the one call we encode
SET_MERKLE_ROOT_ABI = [
    {
        "type": "function",
        "name": "setMerkleRoot",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "campaignId", "type": "uint256"},
            {"name": "root", "type": "bytes32"},
        ],
        "outputs": [],
    }
]


def make_build_calldata(w3: Web3, distributor_address: str):
    """
    Returns a build_calldata(root: MerkleRoot) -> bytes function, closed over a
    contract bound to the distributor. Pass the result into the worker.
    """
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(distributor_address),
        abi=SET_MERKLE_ROOT_ABI,
    )

    def build_calldata(root: MerkleRoot) -> bytes:
        # root.root_hash is LargeBinary(32) -> raw 32 bytes -> bytes32
        # campaign_id is the uint256
        encoded = contract.encode_abi(
            "setMerkleRoot",
            args=[root.campaign_id, root.root_hash],
        )
        # encode_abi returns a hex string ('0x...'); tx_job.data is bytes
        return bytes.fromhex(encoded[2:] if encoded.startswith("0x") else encoded)

    return build_calldata
