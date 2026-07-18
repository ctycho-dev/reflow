"""
Cross-check the Python Merkle module against vectors exported by the Solidity
test harness (Murky + OZ MerkleProof).

The fixture file `merkle_vectors.json` is produced by the Foundry test
`test/MerkleExport.t.sol::test_ExportVectors`. Each vector is a Murky-computed
root plus the exact winner set that produced it, across several tree sizes
(including odd ones, which exercise the hash-with-zero edge).

If either side's convention ever drifts, this test fails. Regenerate the fixture
by re-running the Foundry export whenever the contract-side hashing changes.

Run: pytest test_merkle_crosscheck.py -v
"""

import json
from pathlib import Path

import pytest
from app.utils import merkle

VECTORS_PATH = Path(__file__).parent / "../../merkle_vectors.json"


def _load_vectors():
    data = json.loads(VECTORS_PATH.read_text())
    # normalize: hex root -> bytes, winners -> [(address, int_amount)]
    out = []
    for v in data:
        root = bytes.fromhex(v["root"][2:])
        winners = [(w["address"], int(w["amount"])) for w in v["winners"]]
        out.append((root, winners))
    return out


VECTORS = _load_vectors()


def _verify_proof(leaf: bytes, proof: list[bytes], root: bytes) -> bool:
    """Fold a leaf with its proof siblings (sorted-pair) and compare to root —
    exactly what the on-chain verifier does."""
    h = leaf
    for sibling in proof:
        h = merkle._hash_pair(h, sibling)
    return h == root


@pytest.mark.parametrize("root,winners", VECTORS, ids=[f"n={len(w)}" for _, w in VECTORS])
def test_root_matches_murky(root, winners):
    """Python-built root must equal the Murky-computed root for the same winners."""
    computed, _proofs = merkle.build_tree(winners)
    assert computed == root, (
        f"root mismatch for {len(winners)} winners: "
        f"got {computed.hex()}, expected {root.hex()}"
    )


@pytest.mark.parametrize("root,winners", VECTORS, ids=[f"n={len(w)}" for _, w in VECTORS])
def test_every_proof_verifies(root, winners):
    """Every winner's generated proof must fold back to the root (contract-side check)."""
    _computed, proofs = merkle.build_tree(winners)
    for addr, amount in winners:
        leaf = merkle.leaf_hash(addr, amount)
        proof = proofs[addr.lower()]
        assert _verify_proof(leaf, proof, root), (
            f"proof failed to verify for {addr} in a tree of {len(winners)}"
        )


def test_vectors_present():
    """Guard against an empty/missing fixture silently passing the suite."""
    assert len(VECTORS) >= 3, "expected several vectors including odd-sized trees"
    assert any(len(w) % 2 == 1 for _, w in VECTORS), "need at least one odd-sized tree"