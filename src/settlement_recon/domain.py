"""Ingestion and reconciliation boundary. All monetary values are exact minor units."""

import csv
import hashlib
import io
import json
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from itertools import islice
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Column,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    func,
    literal,
    select,
    text,
    union_all,
)

from settlement_recon.schema import initialize_schema

SCALES = {"USD": 2, "EUR": 2, "GBP": 2, "INR": 2, "JPY": 0}
MAX_BYTES = 2_000_000
MAX_ROWS = 10_000
MAX_MINOR = 10**15
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}$")
metadata = MetaData()
batches = Table(
    "ingestion_batches",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("kind", String(16), nullable=False),
    Column("source", String(96), nullable=False),
    Column("checksum", String(64), nullable=False),
    Column("status", String(16), nullable=False),
    Column("accepted_rows", Integer, nullable=False),
    Column("errors", Text, nullable=False),
    Column("created_at", String(40), nullable=False),
    UniqueConstraint("kind", "source", "checksum"),
)
payment_table = Table(
    "payments",
    metadata,
    Column("payment_id", String(96), primary_key=True),
    Column("currency", String(3), nullable=False),
    Column("amount_minor", BigInteger, nullable=False),
    Column("batch_id", String(36), nullable=False),
)
settlements = Table(
    "settlements",
    metadata,
    Column("source", String(96), primary_key=True),
    Column("row_id", String(96), primary_key=True),
    Column("payment_id", String(96), nullable=False, index=True),
    Column("currency", String(3), nullable=False),
    Column("net_minor", BigInteger, nullable=False),
    Column("fee_minor", BigInteger, nullable=False),
    Column("settled_at", String(40), nullable=False),
    Column("batch_id", String(36), nullable=False),
)


class DomainError(ValueError):
    def __init__(self, message: str, code: str = "invalid"):
        super().__init__(message)
        self.code = code


class Archive(Protocol):
    def put(self, content: bytes) -> str: ...
    def read(self, checksum: str) -> bytes: ...


class FileArchive:
    """Content-addressed durable raw files. Existing bytes can never be silently replaced."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, content: bytes) -> str:
        checksum = hashlib.sha256(content).hexdigest()
        path = self.root / checksum
        descriptor, pending = tempfile.mkstemp(dir=self.root, prefix=".pending-")
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(pending, path)
            except FileExistsError:
                if path.read_bytes() != content:
                    raise OSError("Archive checksum collision or corruption") from None
            if os.name == "posix":
                directory = os.open(self.root, os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
        finally:
            Path(pending).unlink(missing_ok=True)
        return checksum

    def read(self, checksum: str) -> bytes:
        if not re.fullmatch(r"[0-9a-f]{64}", checksum):
            raise DomainError("Invalid archive checksum")
        return (self.root / checksum).read_bytes()


def money(value: str, currency: str) -> int:
    if currency not in SCALES:
        raise DomainError("Unsupported currency")
    if not isinstance(value, str) or not re.fullmatch(r"\d{1,13}(?:\.\d{1,3})?", value):
        raise DomainError("Money must be a nonnegative decimal string")
    amount = Decimal(value) * (10 ** SCALES[currency])
    if amount != amount.to_integral_value() or amount > MAX_MINOR:
        raise DomainError("Invalid monetary precision or limit")
    return int(amount)


def identifier(value: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise DomainError("Invalid identifier")
    return value


def unique_json_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DomainError("Duplicate JSON field")
        result[key] = value
    return result


def parse(kind: str, raw: bytes) -> list[dict]:
    try:
        decoded = raw.decode("utf-8-sig")
        if kind == "payments":
            body = json.loads(decoded, object_pairs_hook=unique_json_fields)
            if not isinstance(body, dict) or set(body) != {"payments"}:
                raise DomainError("Expected an object containing payments")
            rows = body["payments"]
            required = {"payment_id", "amount", "currency"}
        else:
            reader = csv.DictReader(io.StringIO(decoded, newline=""), strict=True)
            required = {"row_id", "payment_id", "currency", "net_amount", "fee", "settled_at"}
            if not reader.fieldnames or set(reader.fieldnames) != required:
                raise DomainError("Statement columns must match the documented schema")
            if len(reader.fieldnames) != len(required):
                raise DomainError("Duplicate CSV columns")
            rows = list(islice(reader, MAX_ROWS + 1))
        if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ROWS:
            raise DomainError("Batch must contain between 1 and 10000 rows")
        normal = []
        for row in rows:
            if (
                not isinstance(row, dict)
                or set(row) != required
                or any(v is None for v in row.values())
            ):
                raise DomainError("Unexpected row schema")
            currency = row["currency"]
            if not isinstance(currency, str):
                raise DomainError("Invalid currency")
            item = {"payment_id": identifier(row["payment_id"]), "currency": currency}
            if kind == "payments":
                item["amount_minor"] = money(row["amount"], currency)
            else:
                item["row_id"] = identifier(row["row_id"])
                item["net_minor"] = money(row["net_amount"], currency)
                item["fee_minor"] = money(row["fee"], currency)
                moment = datetime.fromisoformat(row["settled_at"].replace("Z", "+00:00"))
                if moment.tzinfo is None or moment.utcoffset() is None:
                    raise DomainError("Settlement timestamp requires timezone")
                item["settled_at"] = moment.astimezone(UTC).isoformat()
            normal.append(item)
        return normal
    except (KeyError, TypeError, ValueError, UnicodeError, RecursionError, csv.Error) as exc:
        if isinstance(exc, DomainError):
            raise
        raise DomainError("Invalid encoding, JSON, CSV or timestamp") from None


class Reconciler:
    def __init__(self, database_url: str, archive: Archive):
        self.archive = archive
        self.engine = create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args={"timeout": 30, "check_same_thread": False}
            if str(database_url).startswith("sqlite")
            else {"connect_timeout": 5},
        )
        initialize_schema(self.engine, metadata)

    @contextmanager
    def transaction(self):
        with self.engine.connect() as connection:
            try:
                if self.engine.dialect.name == "sqlite":
                    connection.exec_driver_sql("BEGIN IMMEDIATE")
                else:
                    connection.begin()
                    # Same namespace for every writer; bounded wait avoids hung ingestion.
                    connection.execute(text("SET LOCAL lock_timeout = '10s'"))
                    connection.execute(text("SELECT pg_advisory_xact_lock(508172)"))
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    def ingest(self, kind: str, source: str, raw: bytes) -> dict:
        if kind not in {"payments", "statement"}:
            raise DomainError("Unknown input kind")
        identifier(source)
        if not raw or len(raw) > MAX_BYTES:
            raise DomainError("Payload must contain 1 to 2000000 bytes", "size")
        checksum = self.archive.put(raw)  # no database effects if archival fails
        rows, errors = [], []
        try:
            rows = parse(kind, raw)
        except DomainError as exc:
            errors = [{"code": exc.code, "message": str(exc)}]
        with self.transaction() as connection:
            existing = (
                connection.execute(
                    select(batches).where(
                        batches.c.kind == kind,
                        batches.c.source == source,
                        batches.c.checksum == checksum,
                    )
                )
                .mappings()
                .first()
            )
            if existing:
                return self._batch(existing, replayed=True)
            batch_id = str(uuid4())
            if not errors:
                try:
                    rows = self._validate_existing(connection, kind, source, rows)
                except DomainError as exc:
                    errors = [{"code": exc.code, "message": str(exc)}]
            inserted = 0
            if not errors:
                table = payment_table if kind == "payments" else settlements
                values = [dict(row, batch_id=batch_id) for row in rows]
                if kind == "statement":
                    for row in values:
                        row["source"] = source
                if values:
                    connection.execute(table.insert(), values)
                inserted = len(values)
            record = {
                "id": batch_id,
                "kind": kind,
                "source": source,
                "checksum": checksum,
                "status": "quarantined" if errors else "accepted",
                "accepted_rows": inserted,
                "errors": json.dumps(errors),
                "created_at": datetime.now(UTC).isoformat(),
            }
            connection.execute(batches.insert().values(**record))
            return self._batch(record)

    def _validate_existing(self, connection, kind, source, rows):
        table = payment_table if kind == "payments" else settlements
        key_field = "payment_id" if kind == "payments" else "row_id"
        predicates = [table.c[key_field].in_({row[key_field] for row in rows})]
        if kind == "statement":
            predicates.append(table.c.source == source)
        seen = {
            row[key_field]: row
            for row in connection.execute(select(table).where(*predicates)).mappings()
        }
        new_rows = []
        for row in rows:
            key = row[key_field]
            old = seen.get(key)
            if old and any(old[field] != value for field, value in row.items()):
                raise DomainError("Existing identifier has conflicting business fields", "conflict")
            if old is None:
                new_rows.append(row)
            seen[key] = row
        if kind == "statement" and new_rows:
            totals = {
                (r.payment_id, r.currency): int(r.total)
                for r in connection.execute(
                    select(
                        settlements.c.payment_id,
                        settlements.c.currency,
                        func.sum(settlements.c.net_minor + settlements.c.fee_minor).label("total"),
                    )
                    .where(settlements.c.payment_id.in_({r["payment_id"] for r in new_rows}))
                    .group_by(settlements.c.payment_id, settlements.c.currency)
                )
            }
            for row in new_rows:
                key = (row["payment_id"], row["currency"])
                totals[key] = totals.get(key, 0) + row["net_minor"] + row["fee_minor"]
                if totals[key] > MAX_MINOR:
                    raise DomainError("Cumulative settlement exceeds currency-group limit", "limit")
        return new_rows

    @staticmethod
    def _batch(row, replayed=False):
        result = dict(row)
        result["batch_id"] = result.pop("id")
        result["errors"] = json.loads(result["errors"])
        result["replayed"] = replayed
        return result

    def batches(self, limit=100) -> list[dict]:
        with self.engine.connect() as connection:
            return [
                self._batch(row)
                for row in connection.execute(
                    select(batches).order_by(batches.c.created_at.desc()).limit(limit)
                ).mappings()
            ]

    def verify_archive(self, batch_id: str) -> bool:
        with self.engine.connect() as connection:
            checksum = connection.execute(
                select(batches.c.checksum).where(batches.c.id == batch_id)
            ).scalar_one_or_none()
        if checksum is None:
            raise DomainError("Batch not found", "not_found")
        return hashlib.sha256(self.archive.read(checksum)).hexdigest() == checksum

    def reconcile(self, limit=10000, *, payment_ids=None, source=None) -> list[dict]:
        # A single UNION statement gives expected + orphan groups one database snapshot.
        settlement_query = select(
            settlements.c.payment_id,
            settlements.c.currency,
            func.sum(settlements.c.net_minor + settlements.c.fee_minor).label("settled_minor"),
            func.count().label("settlement_rows"),
        )
        if payment_ids is not None:
            payment_ids = [identifier(value) for value in payment_ids]
            settlement_query = settlement_query.where(settlements.c.payment_id.in_(payment_ids))
        if source is not None:
            identifier(source)
            source_batches = select(batches.c.id).where(batches.c.source == source)
            settlement_query = settlement_query.where(settlements.c.batch_id.in_(source_batches))
        aggregate = settlement_query.group_by(
            settlements.c.payment_id, settlements.c.currency
        ).subquery()
        join = (payment_table.c.payment_id == aggregate.c.payment_id) & (
            payment_table.c.currency == aggregate.c.currency
        )
        expected = select(
            payment_table.c.payment_id,
            payment_table.c.currency,
            payment_table.c.amount_minor.label("expected_minor"),
            func.coalesce(aggregate.c.settled_minor, 0).label("settled_minor"),
            func.coalesce(aggregate.c.settlement_rows, 0).label("settlement_rows"),
            literal(1).label("has_payment"),
        ).select_from(payment_table.outerjoin(aggregate, join))
        orphan = (
            select(
                aggregate.c.payment_id,
                aggregate.c.currency,
                literal(0).label("expected_minor"),
                aggregate.c.settled_minor,
                aggregate.c.settlement_rows,
                literal(0).label("has_payment"),
            )
            .select_from(aggregate.outerjoin(payment_table, join))
            .where(payment_table.c.payment_id.is_(None))
        )
        if payment_ids is not None:
            expected = expected.where(payment_table.c.payment_id.in_(payment_ids))
            orphan = orphan.where(aggregate.c.payment_id.in_(payment_ids))
        if source is not None:
            expected = expected.where(payment_table.c.batch_id.in_(source_batches))
        combined = union_all(expected, orphan).subquery()
        query = select(combined).order_by(combined.c.payment_id, combined.c.currency).limit(limit)
        with self.engine.connect() as connection:
            values = connection.execute(query).mappings().all()
        result = []
        for value in values:
            row = {
                k: int(v) if k.endswith("minor") or k == "settlement_rows" else v
                for k, v in value.items()
            }
            has_payment = row.pop("has_payment")
            if not has_payment:
                row["status"] = "orphan"
            elif row["settlement_rows"] == 0:
                row["status"] = "missing"
            elif row["settled_minor"] == row["expected_minor"]:
                row["status"] = "matched"
            elif row["settled_minor"] < row["expected_minor"]:
                row["status"] = "partial"
            else:
                row["status"] = "overpaid"
            row["difference_minor"] = row["expected_minor"] - row["settled_minor"]
            result.append(row)
        return result
