"""Extract explicit residual obligations and source-scoped orphan legs in one snapshot."""

import hashlib

from sqlalchemy import and_, case, func, or_, select

from settlement_recon.domain import DomainError, batches, identifier, payment_table, settlements
from settlement_recon.forensics_models import ForensicsCase


def extract_case(engine, payment_ids, source):
    identifier(source)
    if not isinstance(payment_ids, (list, tuple)) or not 1 <= len(payment_ids) <= 24:
        raise DomainError("Select between1 and24 payment identifiers")
    for value in payment_ids:
        identifier(value)
    if len(set(payment_ids)) != len(payment_ids):
        raise DomainError("Select unique payment identifiers")
    selected = sorted(payment_ids)
    invalid_receipt = or_(
        batches.c.id.is_(None),
        batches.c.kind != "statement",
        batches.c.status != "accepted",
        batches.c.source != settlements.c.source,
    )
    balances = (
        select(
            settlements.c.payment_id,
            settlements.c.currency,
            func.sum(settlements.c.net_minor + settlements.c.fee_minor).label("recorded"),
            func.sum(case((invalid_receipt, 1), else_=0)).label("invalid"),
        )
        .select_from(settlements.outerjoin(batches, settlements.c.batch_id == batches.c.id))
        .where(settlements.c.payment_id.in_(selected))
        .group_by(settlements.c.payment_id, settlements.c.currency)
        .subquery("balances")
    )
    with engine.connect() as connection:
        if engine.dialect.name == "postgresql":
            connection = connection.execution_options(isolation_level="REPEATABLE READ")
            connection.begin()
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            connection.exec_driver_sql("SET LOCAL statement_timeout = '10s'")
        else:
            connection.exec_driver_sql("BEGIN")
        payments = (
            connection.execute(
                select(
                    payment_table.c.payment_id,
                    payment_table.c.currency,
                    payment_table.c.amount_minor,
                    payment_table.c.batch_id,
                    batches.c.checksum,
                    batches.c.kind,
                    batches.c.status,
                    func.coalesce(balances.c.recorded, 0).label("recorded"),
                    func.coalesce(balances.c.invalid, 0).label("invalid"),
                )
                .select_from(
                    payment_table.outerjoin(
                        batches, payment_table.c.batch_id == batches.c.id
                    ).outerjoin(
                        balances,
                        and_(
                            payment_table.c.payment_id == balances.c.payment_id,
                            payment_table.c.currency == balances.c.currency,
                        ),
                    )
                )
                .where(payment_table.c.payment_id.in_(selected))
                .order_by(payment_table.c.payment_id)
            )
            .mappings()
            .all()
        )
        if len(payments) != len(selected):
            raise DomainError("Selected payment not found", "not_found")
        for payment in payments:
            if (
                payment["kind"] != "payments"
                or payment["status"] != "accepted"
                or not payment["checksum"]
                or payment["invalid"]
            ):
                raise DomainError("Selected payment lineage is unavailable", "integrity")
            if payment["amount_minor"] - payment["recorded"] <= 0:
                raise DomainError("Selected payment must have a positive residual obligation")
        known_payment = (
            select(payment_table.c.payment_id)
            .where(
                payment_table.c.payment_id == settlements.c.payment_id,
                payment_table.c.currency == settlements.c.currency,
            )
            .exists()
        )
        legs = (
            connection.execute(
                select(
                    settlements,
                    batches.c.checksum,
                    batches.c.kind,
                    batches.c.status,
                    batches.c.source.label("receipt_source"),
                )
                .select_from(settlements.outerjoin(batches, settlements.c.batch_id == batches.c.id))
                .where(settlements.c.source == source, ~known_payment)
                .order_by(settlements.c.row_id)
                .limit(33)
            )
            .mappings()
            .all()
        )
        if len(legs) > 32:
            raise DomainError(
                "Source has more than32 orphan legs; narrow the investigation upstream", "size"
            )
        case_legs, provenance_legs = [], []
        for leg in legs:
            if (
                leg["kind"] != "statement"
                or leg["status"] != "accepted"
                or not leg["checksum"]
                or leg["receipt_source"] != source
            ):
                raise DomainError("Selected bank-leg lineage is unavailable", "integrity")
            identity = hashlib.sha256((source + "\0" + leg["row_id"]).encode()).hexdigest()
            case_legs.append(
                {
                    "leg_id": identity,
                    "currency": leg["currency"],
                    "net_minor": leg["net_minor"],
                    "fee_minor": leg["fee_minor"],
                    "settled_on": leg["settled_at"][:10],
                }
            )
            provenance_legs.append(
                {
                    "leg_id": identity,
                    "source": source,
                    "row_id": leg["row_id"],
                    "batch_id": leg["batch_id"],
                    "checksum": leg["checksum"],
                }
            )
        result = {
            "case": {
                "payments": [
                    {
                        "payment_id": row["payment_id"],
                        "currency": row["currency"],
                        "amount_minor": int(row["amount_minor"]) - int(row["recorded"]),
                    }
                    for row in payments
                ],
                "legs": case_legs,
            },
            "provenance": {
                "snapshot": "repeatable-read"
                if engine.dialect.name == "postgresql"
                else "sqlite-read-transaction",
                "source": source,
                "archive_integrity_checked": False,
                "payments": [
                    {
                        "payment_id": row["payment_id"],
                        "original_amount_minor": row["amount_minor"],
                        "recorded_settled_minor": int(row["recorded"]),
                        "batch_id": row["batch_id"],
                        "checksum": row["checksum"],
                    }
                    for row in payments
                ],
                "legs": provenance_legs,
            },
            "warnings": [
                "Only selected residual obligations and orphan legs from one source are included.",
                "References/dates are incomplete; a unique amount is not business identity.",
                "No raw archive is re-read and no bank row is linked by extraction or analysis.",
            ],
        }
        return ForensicsCase.model_validate(result).model_dump(mode="json")
