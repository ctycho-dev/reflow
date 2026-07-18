# Fresh DB, seeded:
make seed

# Look at campaigns:
make campaigns

# Look at a specific leaderboard:
make leaderboard ID=1   # whatever ID the seeded "USDC Power Users" got

# Smoke-test enrollment atomicity:
make enroll-twice ID=2

# Re-seed without wiping (idempotent on reference data only):
make seed-no-wipe