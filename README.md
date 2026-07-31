# Reflow

On-chain activity campaign platform on Base Sepolia. Protocols create campaigns
("move ≥N of token X into contract Y during this window"), wallets enroll and
qualify by real on-chain activity, and rewards settle on-chain through a Merkle
distributor — indexed, finalized, signed, and mirrored back by this backend.

Built as a learning vehicle for senior Web3 backend patterns: own event indexer
with checkpoint recovery, SIWE auth, a hand-built transaction signer worker
(the self-hosted OZ-Relayer shape: queue, dual-write crash recovery, nonce
management, confirmation tracking), byte-exact Merkle tree construction shared
between Python and Solidity, and bidirectional chain↔DB state convergence.

See **[ARCHITECTURE.md](./ARCHITECTURE.md)** for how the pieces fit.

## Stack

FastAPI · SQLAlchemy (async) · PostgreSQL · Alembic · APScheduler · Redis ·
web3.py · siwe · Foundry / Solidity 0.8.30 (contracts) · Docker Compose

Frontend lives in a separate repo (`reflow-frontend`): Next.js, wagmi v3, viem.

## The five processes

One Docker image, five entrypoints:

| Process | Role |
|---|---|
| `api` | FastAPI app: campaigns, SIWE auth, enrollment, leaderboard, proofs, claims |
| `chainwatch` | Event indexer: token Transfers + distributor Claimed events, checkpointed backfill + live poll |
| `checker` | Re-aggregates qualifying volume per enrollment, sets `qualified_at` |
| `finalizer` | Ended campaigns → winners → Merkle tree → `merkle_roots` (pending) + `reward_claims` with proofs |
| `signer` | Chain writer: turns pending roots into `setMerkleRoot` transactions, reliably mined (queue, dual-write, reconcile) |

## Contracts (Base Sepolia, 84532)

| | |
|---|---|
| ReflowToken | `0xDE41931Eb4742187F015315a7388D3b4e8A7fB1d` |
| RewardDistributor | `0x626300b270705aF188Aa1a0d7F7084D98B89e46d` |

Foundry project under `reflow-contract/` (separate repo): role-gated ERC-20 +
Merkle distributor (immutable-once-set roots, proof claims, replay guard).

## Quickstart

```bash
cp .env.example .env          # fill in RPC/WS urls + signer key
docker compose up -d --build  # postgres, redis + all 5 processes
```

Migrations run on api startup. For native iteration against dockerized
postgres/redis, use the Makefile targets (`make api`, `make chainwatch`, …) —
they export localhost overrides. **Don't run a compose worker and its native
twin simultaneously** (checkpoint race).

```bash
make db          # psql into the dev database
make campaigns   # smoke-check the API
```

## Configuration

Each process boots with only its own config section (`app/core/sections.py`,
independent `BaseSettings` per section):

- `POSTGRES_*` — components, assembled into the async url
- `BLOCKCHAIN_*` — chain id, RPC/WS urls, token + distributor addresses,
  signer private key, confirmation depth, signer tick seconds
- `REDIS_*` — live transfer feed pub/sub

Startup guards verify the connected chain matches `BLOCKCHAIN_CHAIN_ID` in
both chainwatch and the signer — config declares intent, the connection
proves it.

## Conventions

- **Amounts are base units** (wei, `Numeric(78,0)`) in DB and API; JSON
  serializes them as **strings**, never numbers. Conversion only at UI edges.
- Addresses stored lowercase; `chain_id` leads every composite key.
- Sessions: `session_scope` with explicit commits; repos are stateless and
  take sessions per call; no ORM relationships.
- Multi-chain-aware schema, single-chain runtime: chainwatch and signer are
  per-chain (connection-bound), checker and finalizer are chain-agnostic
  singletons.