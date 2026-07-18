"""
Merkle tree construction for Reflow reward distribution.

This module produces roots and proofs that are byte-identical to what the
on-chain RewardDistributor verifies. It MUST stay in lockstep with three
conventions, all verified against the Solidity test harness (Murky + OZ
MerkleProof):

  1. LEAF FORMAT
       leaf = keccak256(keccak256(abi.encode(address, uint256)))
     Double-hashed; ABI-encoded as (address, uint256). The inner hash is the
     standard guard against second-preimage attacks (an internal node can't be
     passed off as a leaf).

  2. PAIR HASHING — sorted
       hash_pair(a, b) = keccak256(min(a,b) ++ max(a,b))
     Smaller 32-byte value first. This matches OpenZeppelin's MerkleProof.verify,
     which is the on-chain verifier. Because pairs are sorted, proofs don't need
     to encode left/right position — order is recoverable from the values.

  3. ODD-NODE HANDLING — hash with zero  (!!! Murky-specific !!!)
       When a tree level has an odd number of nodes, the lone trailing node is
       hashed against bytes32(0):  hash_pair(node, ZERO).
       It is NOT promoted unchanged, and NOT duplicated (hashed with itself).

     This is a convention specific to the Murky library, which is our Solidity
     test harness. It is NOT the same as OpenZeppelin's JS library
     (@openzeppelin/merkle-tree), which builds trees differently. We match Murky
     because Murky (build) + OZ MerkleProof (verify) is our end-to-end path and
     it is internally consistent. If the test harness ever changes to OZ-JS, or
     OZ-JS compatibility is required, THIS rule (and get_proof's mirror of it) is
     what must change.

Verified: a 5-leaf tree built here reproduces Murky's getRoot() exactly.
"""

from eth_abi import encode
from eth_utils import keccak

# The zero sibling used when hashing an odd trailing node (Murky convention).
ZERO = b"\x00" * 32


def leaf_hash(account: str, amount: int) -> bytes:
    """
    One Merkle leaf, byte-identical to the contract's:
        keccak256(bytes.concat(keccak256(abi.encode(account, amount))))
    `account` is a hex address string ('0x...'); `amount` is an int (wei).
    """
    inner = keccak(encode(["address", "uint256"], [account, amount]))
    return keccak(inner)


def _hash_pair(a: bytes, b: bytes) -> bytes:
    """Sorted-pair hash: smaller 32-byte value first, matching OZ MerkleProof."""
    lo, hi = (a, b) if a < b else (b, a)
    return keccak(lo + hi)


def _hash_level(data: list[bytes]) -> list[bytes]:
    """
    Hash one level into its parent level (bottom-up), Murky-style.
    Even pairs hash normally; a lone trailing node hashes against ZERO.
    """
    result: list[bytes] = []
    length = len(data)
    for i in range(0, length - 1, 2):
        result.append(_hash_pair(data[i], data[i + 1]))
    if length & 1:  # odd count -> last node hashed with zero
        result.append(_hash_pair(data[length - 1], ZERO))
    return result


def build_levels(leaves: list[bytes]) -> list[list[bytes]]:
    """
    Build every level of the tree, bottom-up.
    Returns levels where levels[0] == leaves and levels[-1] == [root].
    Requires at least 2 leaves (matches Murky, which refuses a single-leaf tree).
    """
    if len(leaves) < 2:
        raise ValueError("need at least 2 leaves to build a tree")
    levels = [list(leaves)]
    while len(levels[-1]) > 1:
        levels.append(_hash_level(levels[-1]))
    return levels


def get_root(levels: list[list[bytes]]) -> bytes:
    """The single root hash at the top of the tree."""
    return levels[-1][0]


def get_proof(levels: list[list[bytes]], index: int) -> list[bytes]:
    """
    Sibling hashes from the leaf at `index` up to the root.

    Mirrors Murky's getProof odd-node rule: when the node is the unpaired last
    element of an odd-length level, its sibling in the proof is ZERO (the same
    zero it was hashed against during construction).
    """
    proof: list[bytes] = []
    for level in levels[:-1]:  # all levels except the root
        if index & 1:  # right child -> sibling is the left neighbor
            proof.append(level[index - 1])
        elif index + 1 == len(level):  # unpaired last node on an odd level
            proof.append(ZERO)
        else:  # left child -> sibling is the right neighbor
            proof.append(level[index + 1])
        index //= 2
    return proof


def build_tree(winners: list[tuple[str, int]]) -> tuple[bytes, dict[str, list[bytes]]]:
    """
    Convenience entry point. Takes [(address, amount), ...] and returns:
        (root, {address: proof})
    Proofs are keyed by lowercase address. Amounts are ints (wei).

    Note: leaf order is the order given. The caller is responsible for a stable,
    reproducible ordering (e.g. sorted by address) so the tree is deterministic.
    """
    leaves = [leaf_hash(addr, amt) for addr, amt in winners]
    levels = build_levels(leaves)
    root = get_root(levels)
    proofs = {
        addr.lower(): get_proof(levels, i)
        for i, (addr, _amt) in enumerate(winners)
    }
    return root, proofs
