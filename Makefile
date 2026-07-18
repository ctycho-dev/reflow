# Makefile — root of repo

API := http://localhost:8000/api/v1

POSTGRES_HOST=localhost
POSTGRES_USER=root
POSTGRES_PASSWORD=password
POSTGRES_DB=reflow
POSTGRES_PORT=5432
REDIS_URL    := redis://:password@localhost:6379/0

# -----------------------------------------------------------------
# Setup
# -----------------------------------------------------------------

.PHONY: seed seed-no-wipe checker chainwatch api

seed:
	python -m scripts.seed_dev_environment

wipe:
	python -m scripts.wipe_dev_database

# Convenience: wipe then re-seed, no prompts (use carefully)
wipe-and-seed:
	python -m scripts.wipe_dev_database --yes
	python -m scripts.seed_dev_environment

# -----------------------------------------------------------------
# Smoke checks (manual curls)
# -----------------------------------------------------------------

.PHONY: campaigns campaign leaderboard enroll enroll-twice

campaigns:
	@curl -s "$(API)/campaign?chainId=1" | python3 -m json.tool

# usage: make campaign ID=18
campaign:
	@test -n "$(ID)" || (echo "usage: make campaign ID=18" && exit 1)
	@curl -s "$(API)/campaign/$(ID)" | python3 -m json.tool

# usage: make leaderboard ID=18
leaderboard:
	@test -n "$(ID)" || (echo "usage: make leaderboard ID=18" && exit 1)
	@curl -s "$(API)/campaign/$(ID)/leaderboard" | python3 -m json.tool

# usage: make enroll ID=18
enroll:
	@test -n "$(ID)" || (echo "usage: make enroll ID=18" && exit 1)
	@curl -s -X POST "$(API)/campaign/$(ID)/enroll" \
	  -H "Content-Type: application/json" \
	  -w "\nHTTP %{http_code}\n" | python3 -m json.tool || true

# Atomicity sanity check: enroll twice, verify counter stays at 1
# usage: make enroll-twice ID=18
enroll-twice:
	@test -n "$(ID)" || (echo "usage: make enroll-twice ID=18" && exit 1)
	@echo "--- first enroll ---"
	@curl -s -X POST "$(API)/campaign/$(ID)/enroll" -w "\nHTTP %{http_code}\n"
	@echo "--- second enroll (should be 409) ---"
	@curl -s -X POST "$(API)/campaign/$(ID)/enroll" -w "\nHTTP %{http_code}\n"
	@echo "--- enrolledCount (should be 1) ---"
	@curl -s "$(API)/campaign?chainId=1" | python3 -m json.tool | grep -A1 "\"id\": $(ID)" | grep enrolledCount


# usage: make eligibility ADDR=0x0000000000000000000000000000000000000001
eligibility:
	@test -n "$(ADDR)" || (echo "usage: make eligibility ADDR=0x..." && exit 1)
	@curl -s "$(API)/wallet/$(ADDR)/eligibility?chainId=1" | python3 -m json.tool


checker:
	python -m worker.checker.main


chainwatch:
	python -m worker.chainwatch.main


finalize:
	python -m worker.finalizer.main


signer:
	python -m worker.signer.main


db:
	psql -h localhost -p 5432 -U root -d reflow


api:
	POSTGRES_URL=$(POSTGRES_URL) REDIS_URL=$(REDIS_URL) \
	uvicorn app.main:app --host 0.0.0.0 --port 8000