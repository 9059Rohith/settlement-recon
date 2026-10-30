"""Bounded reconciliation evidence from one database read snapshot."""

from sqlalchemy import case, func, or_, select

from settlement_recon.domain import (
    SCALES,
    DomainError,
    batches,
    classify_reconciliation,
    identifier,
    payment_table,
    settlements,
)

RULES = {
    "orphan": ("no-payment-in-currency", "Bank rows exist without a payment in this currency."),
    "missing": ("no-settlement-rows", "A payment exists but no bank rows exist in this currency."),
    "matched": ("settled-equals-expected", "Net proceeds plus fees exactly equal the payment."),
    "partial": ("settled-less-than-expected", "Net proceeds plus fees are below the payment."),
    "overpaid": ("settled-exceeds-expected", "Net proceeds plus fees exceed the payment."),
}


def explain_payment(engine, payment_id: str, currency: str, limit: int = 25) -> dict:
    identifier(payment_id)
    if not isinstance(currency, str) or currency not in SCALES:
        raise DomainError("Unsupported currency")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise DomainError("Evidence limit must be between 1 and 100")
    with engine.connect() as connection:
        if engine.dialect.name == "postgresql":
            connection = connection.execution_options(isolation_level="REPEATABLE READ")
            connection.begin()
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            connection.exec_driver_sql("SET LOCAL statement_timeout = '10s'")
        else:
            # SQLite's legacy driver needs an explicit BEGIN for SELECT snapshots.
            connection.exec_driver_sql("BEGIN")
        payment = (
            connection.execute(
                select(
                    payment_table.c.amount_minor,
                    payment_table.c.batch_id,
                    batches.c.source,
                    batches.c.checksum,
                    batches.c.kind,
                    batches.c.status,
                )
                .select_from(
                    payment_table.outerjoin(batches, payment_table.c.batch_id == batches.c.id)
                )
                .where(
                    payment_table.c.payment_id == payment_id, payment_table.c.currency == currency
                )
            )
            .mappings()
            .first()
        )
        predicate = (settlements.c.payment_id == payment_id, settlements.c.currency == currency)
        totals = (
            connection.execute(
                select(
                    func.coalesce(func.sum(settlements.c.net_minor), 0).label("net_minor"),
                    func.coalesce(func.sum(settlements.c.fee_minor), 0).label("fee_minor"),
                    func.count().label("count"),
                    func.count(batches.c.checksum).label("receipts"),
                    func.coalesce(
                        func.sum(
                            case(
                                (
                                    or_(
                                        batches.c.source != settlements.c.source,
                                        batches.c.kind != "statement",
                                        batches.c.status != "accepted",
                                    ),
                                    1,
                                ),
                                else_=0,
                            )
                        ),
                        0,
                    ).label("invalid_receipts"),
                )
                .select_from(settlements.outerjoin(batches, settlements.c.batch_id == batches.c.id))
                .where(*predicate)
            )
            .mappings()
            .one()
        )
        count = int(totals["count"])
        if payment is None and not count:
            raise DomainError("Payment/currency group not found", "not_found")
        if payment is not None and (
            payment["source"] is None
            or payment["checksum"] is None
            or payment["kind"] != "payments"
            or payment["status"] != "accepted"
        ):
            raise DomainError("Payment lineage is unavailable", "integrity")
        if count != int(totals["receipts"]) or int(totals["invalid_receipts"]):
            raise DomainError("Settlement lineage is unavailable", "integrity")
        legs = (
            connection.execute(
                select(
                    settlements.c.source,
                    settlements.c.row_id,
                    settlements.c.net_minor,
                    settlements.c.fee_minor,
                    settlements.c.settled_at,
                    settlements.c.batch_id,
                    batches.c.checksum,
                    batches.c.source.label("receipt_source"),
                )
                .select_from(settlements.outerjoin(batches, settlements.c.batch_id == batches.c.id))
                .where(*predicate)
                .order_by(settlements.c.source, settlements.c.row_id)
                .limit(limit)
            )
            .mappings()
            .all()
        )
        if any(row["checksum"] is None or row["source"] != row["receipt_source"] for row in legs):
            raise DomainError("Settlement lineage is unavailable", "integrity")
        expected = int(payment["amount_minor"]) if payment is not None else 0
        net, fee = int(totals["net_minor"]), int(totals["fee_minor"])
        result = classify_reconciliation(
            {
                "payment_id": payment_id,
                "currency": currency,
                "has_payment": int(payment is not None),
                "expected_minor": expected,
                "settled_minor": net + fee,
                "settlement_rows": count,
            }
        )
        rule, description = RULES[result["status"]]
        return {
            "payment_id": payment_id,
            "currency": currency,
            "currency_scale": SCALES[currency],
            "status": result["status"],
            "rule": {"id": rule, "description": description},
            "totals": {
                "expected_minor": expected,
                "net_minor": net,
                "fee_minor": fee,
                "settled_minor": net + fee,
                "difference_minor": expected - net - fee,
            },
            "payment": {
                key: value for key, value in payment.items() if key not in {"kind", "status"}
            }
            if payment is not None
            else None,
            "settlements": {
                "total_rows": count,
                "returned_rows": len(legs),
                "truncated": count > len(legs),
                "records": [
                    {key: value for key, value in row.items() if key != "receipt_source"}
                    for row in legs
                ],
            },
            "snapshot": "repeatable-read"
            if engine.dialect.name == "postgresql"
            else "sqlite-read-transaction",
            "archive_integrity_checked": False,
        }
