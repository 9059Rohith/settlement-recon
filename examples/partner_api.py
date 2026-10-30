"""Run: uvicorn examples.partner_api:app --port 9901 (synthetic partner, operator token)."""

import hmac
import os

from fastapi import FastAPI, Header, HTTPException

app = FastAPI(title="Synthetic partner ledger")


@app.get("/payments")
def payments(authorization: str = Header(default="")):
    token = os.environ.get("PARTNER_TOKEN", "")
    if len(token) < 32 or not hmac.compare_digest(authorization, f"Bearer {token}"):
        raise HTTPException(401, "Partner token required")
    return {"payments": [{"payment_id": "partner-1", "currency": "USD", "amount": "125.50"}]}
