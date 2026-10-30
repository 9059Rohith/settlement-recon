"""Serialize first-run DDL across independently starting container instances."""

from sqlalchemy import text


def initialize_schema(engine, metadata):
    with engine.connect() as connection:
        if engine.dialect.name == "sqlite":
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        else:
            connection.begin()
            connection.execute(text("SET LOCAL lock_timeout = '10s'"))
            connection.execute(text("SELECT pg_advisory_xact_lock(58902361477)"))
        metadata.create_all(connection)
        connection.commit()
