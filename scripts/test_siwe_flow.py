# scripts/test_siwe_flow.py
"""
End-to-end SIWE flow test against the running backend.

Generates a throwaway private key (or uses TEST_PRIVATE_KEY from env),
runs the full nonce → sign → verify → /me → enroll → logout dance,
asserts each step.

Usage:
    python -m scripts.test_siwe_flow
    TEST_PRIVATE_KEY=0xabc... python -m scripts.test_siwe_flow   # use specific key
    BASE_URL=http://localhost:8000 python -m scripts.test_siwe_flow

Requires backend running. Doesn't need a real campaign — if /enroll fails on
"campaign not found" that's still a successful auth (the request reached the
authenticated endpoint with the cookie attached).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

import httpx
from eth_account import Account
from eth_account.messages import encode_defunct
from siwe import SiweMessage

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
SIWE_DOMAIN = os.environ.get("SIWE_DOMAIN", "localhost:3000")
CHAIN_ID = 1


def _generate_or_load_key() -> Account:
    raw = os.environ.get("TEST_PRIVATE_KEY")
    if raw:
        if not raw.startswith("0x"):
            raw = "0x" + raw
        account = Account.from_key(raw)
        print(f"[*] using provided key for {account.address}")
        return account
    account = Account.create()
    print(f"[*] generated fresh test wallet: {account.address}")
    print(f"[*] (export TEST_PRIVATE_KEY={account.key.hex()} to reuse)")
    return account


def _build_siwe_message(*, address: str, nonce: str) -> str:
    """Construct an EIP-4361 message using the siwe library."""
    now = datetime.now(timezone.utc)
    msg = SiweMessage(
        domain=SIWE_DOMAIN,
        address=address,
        statement="Sign in to Reflow (test).",
        uri=f"http://{SIWE_DOMAIN}",
        version="1",
        chain_id=CHAIN_ID,
        nonce=nonce,
        issued_at=now.isoformat().replace("+00:00", "Z"),
        expiration_time=(now + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
    )
    return msg.prepare_message()


def _sign(account: Account, message: str) -> str:
    """Sign the SIWE message with EIP-191 personal_sign (the same path MetaMask uses)."""
    signable = encode_defunct(text=message)
    signed = Account.sign_message(signable, private_key=account.key)
    return signed.signature.hex()


def main() -> int:
    print(f"[*] backend: {BASE_URL}")
    print(f"[*] siwe domain (must match settings.siwe.domain): {SIWE_DOMAIN}")

    account = _generate_or_load_key()
    address = account.address  # checksum form — backend lowercases internally

    # Cookie jar persists session between calls (httponly cookie from /verify
    # lives here, gets sent on subsequent requests).
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:

        # ── Step 1: request nonce ────────────────────────────────────────────
        print("\n[1] POST /api/v1/auth/nonce")
        r = client.post("/api/v1/auth/nonce", json={"address": address})
        if r.status_code != 200:
            print(f"   ✗ {r.status_code} {r.text}")
            return 1
        nonce = r.json()["nonce"]
        print(f"   ✓ got nonce: {nonce}")

        # ── Step 2: build + sign SIWE message ────────────────────────────────
        print("\n[2] build + sign SIWE message")
        message = _build_siwe_message(address=address, nonce=nonce)
        print("   message:")
        for line in message.splitlines():
            print(f"     {line}")
        signature = _sign(account, message)
        print(f"   ✓ signature: {signature[:18]}...")

        # ── Step 3: verify ───────────────────────────────────────────────────
        print("\n[3] POST /api/v1/auth/verify")
        r = client.post(
            "/api/v1/auth/verify",
            json={"message": message, "signature": signature},
        )
        if r.status_code != 200:
            print(f"   ✗ {r.status_code} {r.text}")
            return 1
        body = r.json()
        cookies = dict(client.cookies)
        print(f"   ✓ response: {body}")
        print(f"   ✓ cookies: {list(cookies.keys())}")
        if not any(k for k in cookies if "reflow" in k.lower() or "access" in k.lower()):
            print("   ⚠ no session cookie set — check cookie_secure / samesite config")

        # ── Step 4: /me confirms the cookie auth works ───────────────────────
        print("\n[4] GET /api/v1/auth/me (cookie auth)")
        r = client.get("/api/v1/auth/me")
        if r.status_code != 200:
            print(f"   ✗ {r.status_code} {r.text}")
            return 1
        me = r.json()
        print(f"   ✓ {me}")
        if me["address"].lower() != address.lower():
            print(f"   ✗ wallet mismatch: expected {address.lower()}, got {me['address']}")
            return 1

        # ── Step 5: try a protected endpoint (enroll in any campaign) ────────
        print("\n[5] POST /api/v1/campaign/1/enroll (cookie auth)")
        r = client.post("/api/v1/campaign/1/enroll")
        # 201 = enrolled (campaign 1 exists, wallet is new)
        # 409 = already enrolled (we ran this before) — still proves auth worked
        # 404 = no campaign with id=1 — still proves auth worked
        # 401 = auth failed — bug
        if r.status_code == 401:
            print(f"   ✗ 401 — cookie not being sent or JWT invalid: {r.text}")
            return 1
        print(f"   ✓ {r.status_code} {r.json() if r.headers.get('content-type','').startswith('application/json') else r.text}")

        # ── Step 6: replay attack — same signature should now fail ───────────
        print("\n[6] POST /api/v1/auth/verify with same message+signature (replay)")
        # New client without cookie so we're not authenticated from step 3
        with httpx.Client(base_url=BASE_URL, timeout=10.0) as fresh:
            r = fresh.post(
                "/api/v1/auth/verify",
                json={"message": message, "signature": signature},
            )
        if r.status_code == 401:
            print(f"   ✓ {r.status_code} — replay correctly rejected: {r.json()}")
        else:
            print(f"   ✗ {r.status_code} — replay NOT rejected! nonce wasn't consumed.")
            print(f"     body: {r.text}")
            return 1

        # ── Step 7: logout clears cookie ─────────────────────────────────────
        print("\n[7] POST /api/v1/auth/logout")
        r = client.post("/api/v1/auth/logout")
        print(f"   ✓ {r.status_code}")

        print("\n[8] GET /api/v1/auth/me (should now be 401)")
        r = client.get("/api/v1/auth/me")
        if r.status_code == 401:
            print(f"   ✓ {r.status_code} — logout cleared the cookie")
        else:
            print(f"   ✗ {r.status_code} — cookie still alive after logout")
            return 1

    print("\n[✓] SIWE flow OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())