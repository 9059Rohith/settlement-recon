"""Operator CLI uses the same ingestion transaction as HTTP and Airflow."""

import argparse
import json
import os
from collections import Counter
from pathlib import Path

from settlement_recon.api import from_environment
from settlement_recon.domain import MAX_BYTES
from settlement_recon.partner import pull_partner


def demo(service):
    pay = {
        "payments": [
            {"payment_id": "demo-match", "currency": "USD", "amount": "100.00"},
            {"payment_id": "demo-partial", "currency": "INR", "amount": "1000.00"},
        ]
    }
    results = [service.ingest("payments", "demo-ledger", json.dumps(pay).encode())]
    statement = (
        b"row_id,payment_id,currency,net_amount,fee,settled_at\n"
        b"demo-r1,demo-match,USD,99,1,2026-10-30T10:00:00Z\n"
        b"demo-r2,demo-partial,INR,590,10,2026-10-30T10:00:00Z\n"
    )
    results.append(service.ingest("statement", "demo-bank", statement))
    results.append(service.ingest("statement", "demo-bank", b"corrupt statement"))
    results.append(service.ingest("statement", "demo-bank", statement))
    return dict(
        Counter(row["status"] for row in service.reconcile()),
        quarantined_batches=sum(row["status"] == "quarantined" for row in service.batches()),
        attempts=results,
    )


def main():
    parser = argparse.ArgumentParser(description="Auditable synthetic payment reconciliation")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo")
    sub.add_parser("reconcile")
    sub.add_parser("batches")
    ingest = sub.add_parser("ingest")
    ingest.add_argument("kind", choices=["payments", "statement"])
    ingest.add_argument("source")
    ingest.add_argument("file", type=Path)
    verify = sub.add_parser("verify")
    verify.add_argument("batch_id")
    pull = sub.add_parser("pull-partner")
    pull.add_argument("url")
    args = parser.parse_args()
    service = from_environment().state.service
    if args.command == "demo":
        result = demo(service)
    elif args.command == "reconcile":
        result = service.reconcile()
    elif args.command == "batches":
        result = service.batches()
    elif args.command == "verify":
        result = {"intact": service.verify_archive(args.batch_id)}
    elif args.command == "pull-partner":
        result = pull_partner(
            service,
            args.url,
            os.environ.get("PARTNER_TOKEN", ""),
            set(os.environ.get("PARTNER_ALLOWED_HOSTS", "").split(",")),
        )
    else:
        with args.file.open("rb") as handle:
            content = handle.read(MAX_BYTES + 1)
        result = service.ingest(args.kind, args.source, content)
    print(json.dumps(result, indent=2))
    service.engine.dispose()
    if isinstance(result, dict) and result.get("status") == "quarantined":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
