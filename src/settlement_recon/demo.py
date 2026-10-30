"""Opt-in public demonstration, computed through the real ingestion boundary."""

import json
from collections import Counter

from sqlalchemy import select

from settlement_recon.domain import DomainError, batches

SOURCE = "portfolio-synthetic-v1"
IDS = {"demo-matched-v1", "demo-partial-v1", "demo-missing-v1"}


def seed_demo(service):
    payments = json.dumps(
        {
            "payments": [
                {"payment_id": identity, "currency": "USD", "amount": "100.00"}
                for identity in sorted(IDS)
            ]
        },
        separators=(",", ":"),
    ).encode()
    statement = (
        b"row_id,payment_id,currency,net_amount,fee,settled_at\n"
        b"demo-r1,demo-matched-v1,USD,99.00,1.00,2026-10-30T10:00:00Z\n"
        b"demo-r2,demo-partial-v1,USD,49.00,1.00,2026-10-30T10:00:00Z\n"
    )
    for kind, raw in [
        ("payments", payments),
        ("statement", statement),
        ("payments", b'{"payments":[{"invalid":"synthetic corrupt record"}]}'),
    ]:
        service.ingest(kind, SOURCE, raw)


def summary(service):
    # Only these three known synthetic identities are eligible for public output.
    rows = service.reconcile(payment_ids=IDS, source=SOURCE)
    if len(rows) != 3 or any(
        row["currency"] != "USD" or row["expected_minor"] != 10000 for row in rows
    ):
        raise DomainError("Synthetic fixture unavailable")
    with service.engine.connect() as connection:
        demo_batches = list(
            connection.execute(
                select(batches.c.id, batches.c.status).where(batches.c.source == SOURCE)
            ).mappings()
        )
    return {
        "synthetic": True,
        "calculation": "Actual SQL reconciliation; USD amounts expressed in minor units",
        "payments": len(rows),
        "outcomes": dict(Counter(row["status"] for row in rows)),
        "quarantined_batches": sum(row["status"] == "quarantined" for row in demo_batches),
        "archive_verified": bool(demo_batches)
        and all(service.verify_archive(row["id"]) for row in demo_batches),
    }
