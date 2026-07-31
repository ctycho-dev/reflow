# Reflow — Architecture

Reflow looks like one application but is really **three applications sharing a
database**, plus a blockchain that acts as both a data source and a write
target. Most of the design falls out of that shape.

```
                 ┌─────────────────────────────────────────────┐
                 │                Base Sepolia                  │
                 │   ReflowToken          RewardDistributor     │
                 └───────┬─────────────────────────▲───────┬───┘
                 events  │                  txs    │       │ events
                         ▼                         │       ▼
                  ┌────────────┐            ┌──────────┐ (Claimed)
                  │ chainwatch │            │  signer  │
                  │ Token+Claim│            └────▲─────┘
                  │  watchers  │                 │ tx_jobs
                  └─────┬──────┘                 │
                        │ transfers,       ┌─────┴─────┐
                        │ reward_claims    │ finalizer │
                        ▼                  └─────▲─────┘
                  ┌──────────────────────────────┴──────┐
                  │              PostgreSQL             │
                  └─────▲─────────────────────────▲─────┘
                        │                         │
                  ┌─────┴─────┐             ┌─────┴─────┐
                  │  checker  │             │    api    │◄── SIWE, frontend
                  └───────────┘             └───────────┘
```

## The three subsystems

**1. A CRUD web app** (`api`). Campaigns, SIWE auth (nonce → EIP-4361 message →
signature → httpOnly JWT cookie), atomic enrollment (slot reservation with DB
CHECK constraints), leaderboards, proof/claims read APIs. Ordinary FastAPI —
the unremarkable third of the system.

**2. A data pipeline** (`chainwatch` → `checker`). Classic ETL where the source
system is a chain. Chainwatch holds one WebSocket connection and runs two
watchers as asyncio tasks:

- **TokenWatcher** — ERC-20 `Transfer` events for watched tokens, filtered to
  transfers touching registered protocol contracts → `transfers` table + Redis
  pub/sub (live feed).
- **ClaimWatcher** — the distributor's `Claimed` events → idempotent UPDATE of
  `reward_claims.claimed_at/claim_tx_hash` (guarded by `claimed_at IS NULL`,
  so backfill replay is harmless).

Both share the same machinery: chunked `eth_getLogs` backfill to the safe head
(head − confirmation depth), then live polling; per-chunk checkpoints in
`checkpoints (chain_id, contract address)`. **Crash-only design**: any failure
kills the process; restart resumes from the checkpoint. This has survived
repeated real provider disconnects unattended.

The checker re-aggregates each open enrollment's qualifying volume every tick
(SUM of indexed transfers within the campaign window, scoped by the campaign's
chain/token/target) and stamps `qualified_at` when the threshold is crossed.
Per-row transactions — one bad enrollment never blocks the batch.

**3. A transaction-processing system** (`finalizer` → `signer` → chain →
ClaimWatcher). The genuinely Web3-specific third, and it is *bidirectional*:
the chain is downstream of the finalizer and upstream of the mirror.

- **Finalizer** (pure off-chain): ended campaigns with no settlement record →
  qualified winners → equal split of the reward pool (dust to first winner;
  sum == pool exactly) → Merkle tree (byte-identical to the contract's Murky
  convention; single winners padded with an unclaimable zero-leaf so proofs
  are always real) → writes `merkle_roots` (status `pending`, or terminal
  `no_winners`) + per-winner `reward_claims` rows with precomputed proofs.
  Never touches the chain.
- **Signer** (the hand-built OZ-Relayer equivalent): each tick runs
  enqueue → monitor → send.
  - *Enqueue*: pending roots **on the signer's chain** → `tx_jobs` with
    pre-built `setMerkleRoot` calldata (built once, reused verbatim on retry).
  - *Send*: claim one job with `FOR UPDATE SKIP LOCKED` (lock held across the
    send — serializes signers, no double-spend of a nonce), then the
    **dual-write invariant**: persist (status=submitting, deterministic
    tx_hash, nonce) and COMMIT *before* broadcasting. A crash between commit
    and broadcast is recoverable; the reverse is not.
  - *Monitor*: submitting → mined → confirmed at depth, flipping the root's
    status; reverted → failed; unknown-hash → rebroadcast the stored raw tx.
  - *Reconcile* (startup): every in-flight job re-checked against the chain —
    the payoff of the dual-write.
- **ClaimWatcher** closes the loop: users claim on-chain (frontend wagmi call
  with the served proof); the mirror converges the DB to chain truth. The
  frontend never tells the backend a claim happened — it refetches into it.

## Who writes what

| Table | Written by | Read by |
|---|---|---|
| campaigns | api | api, checker, finalizer |
| wallets, enrollments | api (enroll), checker (volume/qualified_at) | api, checker, finalizer |
| tokens, protocol_contracts | seed / (future admin) | api, chainwatch, checker |
| transfers | chainwatch (TokenWatcher) | checker |
| checkpoints | chainwatch (both watchers) | chainwatch |
| merkle_roots | finalizer (create), signer (status) | signer, api |
| reward_claims | finalizer (create), chainwatch/ClaimWatcher (claimed mirror) | api |
| tx_jobs | signer | signer |

Two processes never write the same column. All cross-process communication is
through table state (e.g. `merkle_roots.status` is the finalizer→signer
contract); no process knows another exists.

## Chain affinity

The rule, learned from a real incident (see below): a process is **per-chain
iff it holds a chain connection**.

- `chainwatch`, `signer` — connection-bound → one instance per chain, each
  with a startup guard (`connected chain_id == configured chain_id`, refuse
  otherwise) and chain-filtered work selection.
- `checker`, `finalizer` — DB-only → singletons serving all chains; chain
  enters as data (`campaign.chain_id` parameterizes every query, and the
  finalizer stamps it into `merkle_roots.chain_id`).

A root for a chain with no running signer sits visibly `pending` forever —
by design: visible and inert beats silent and wrong.

## Consistency model

DB truth and chain truth are never guaranteed equal — only converged toward,
by three independent mechanisms:

1. **Checkpoints** (read side): indexing resumes exactly where it stopped;
   at-least-once processing with idempotent writes (composite-PK inserts
   ignore duplicates; the claim mirror updates only NULL rows).
2. **Reconcile** (write side): the dual-write makes every broadcast
   recoverable — on restart, persisted tx hashes are checked against the
   chain and jobs advanced or rebroadcast.
3. **Event mirroring**: on-chain effects caused by third parties (user claims)
   flow back through the indexer, not through the frontend's word.

## Incidents that shaped the design

- **Cross-chain root settlement.** Demo campaigns on chain 1, pushed into the
  finalization grace window, were finalized (correctly — the finalizer is
  chain-agnostic) and their roots broadcast to the Base Sepolia distributor.
  The finalizer had written honest chain_ids throughout; the signer's enqueue
  fetched roots chain-blind and stamped its own configured chain over them.
  Fix: chain-filtered fetch + claim, jobs stamped from `root.chain_id`,
  startup guard. A deliberately-seeded chain-1 root remains in the dev DB as
  a standing regression proof (pending forever, signer silent).
- **Provider constraints are architecture.** `BACKFILL_CHUNK_SIZE = 10` is
  Alchemy's free-tier `eth_getLogs` cap, not a tuning choice. Manual
  checkpoint moves require stopping the watcher first — it checkpoints per
  chunk and wins any write race.
- **Serialization boundaries.** 256-bit amounts exceed IEEE-754 safe integers;
  every amount crosses JSON as a string, validated as integer strings on the
  way in (`Numeric(78,0)` semantics end to end).

## Deliberate simplifications (known, not accidental)

- Signer key is a local env var; the KMS swap is one seam
  (`TxSigner._sign_transaction`). RBF/stuck-tx replacement deferred.
- Migrations run in the api container's CMD — safe only at 1 api replica;
  the ECS-style fix is a one-off migration task.
- Operator endpoints (finalize, delete) are unauthenticated — acceptable
  locally, a blocker for any public deploy.
- Funding invariant (distributor balance ≥ committed totals) is enforced by
  operational discipline, not code.
- The indexer layer (both watchers) is designed to be replaced wholesale by
  Envio; the checker would read its GraphQL instead of `transfers`.