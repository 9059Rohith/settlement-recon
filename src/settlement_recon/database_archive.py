"""Content-addressed raw storage for hosts with ephemeral local filesystems.

Raw input commits before business ingestion, so failed batches remain replayable.
This adapter uses the same durable database but a separate transaction, matching
the File/S3 archive boundary. It is appropriate for bounded portfolio workloads;
large archives should use the existing encrypted S3 adapter.
"""

import hashlib
import re

from sqlalchemy import Column, LargeBinary, MetaData, String, Table, create_engine, select, text

from settlement_recon.domain import MAX_BYTES, DomainError
from settlement_recon.schema import initialize_schema

archive_metadata = MetaData()
raw_archive = Table(
    "raw_archive",
    archive_metadata,
    Column("checksum", String(64), primary_key=True),
    Column("payload", LargeBinary, nullable=False),
)


class DatabaseArchive:
    def __init__(self, database_url):
        self.engine = create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args={"timeout": 30, "check_same_thread": False}
            if str(database_url).startswith("sqlite")
            else {"connect_timeout": 5},
        )
        initialize_schema(self.engine, archive_metadata)

    def put(self, content: bytes) -> str:
        if len(content) > MAX_BYTES:
            raise DomainError("Payload exceeds maximum size", "size")
        checksum = hashlib.sha256(content).hexdigest()
        if self.engine.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        with self.engine.begin() as connection:
            connection.execute(
                insert(raw_archive)
                .values(checksum=checksum, payload=content)
                .on_conflict_do_nothing(index_elements=["checksum"])
            )
            existing = connection.execute(
                select(raw_archive.c.payload).where(raw_archive.c.checksum == checksum)
            ).scalar_one()
            if bytes(existing) != content:
                raise OSError("Archive checksum collision or corruption")
        return checksum

    def read(self, checksum: str) -> bytes:
        if not re.fullmatch(r"[0-9a-f]{64}", checksum):
            raise DomainError("Invalid archive checksum")
        with self.engine.connect() as connection:
            value = connection.execute(
                select(raw_archive.c.payload).where(raw_archive.c.checksum == checksum)
            ).scalar_one_or_none()
        if value is None:
            raise FileNotFoundError("Archived input not found")
        content = bytes(value)
        if hashlib.sha256(content).hexdigest() != checksum:
            raise OSError("Archive corruption detected")
        return content

    def ready(self):
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1 FROM raw_archive LIMIT 1"))
