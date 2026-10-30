import json
import os
from uuid import uuid4

import boto3
import pytest

from settlement_recon.domain import Reconciler
from settlement_recon.s3 import S3Archive


@pytest.mark.skipif(
    not os.environ.get("TEST_S3_ENDPOINT"),
    reason="Set TEST_S3_ENDPOINT for real S3-compatible service",
)
def test_actual_s3_compatible_archive_replay_and_verification(tmp_path, monkeypatch):
    monkeypatch.setenv("AWS_ENDPOINT_URL_S3", os.environ["TEST_S3_ENDPOINT"])
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    client = boto3.session.Session().client("s3")
    bucket = "recon-test-" + uuid4().hex
    client.create_bucket(Bucket=bucket)
    archive = S3Archive(bucket)
    service = Reconciler(f"sqlite:///{tmp_path / 'test.db'}", archive)
    content = json.dumps(
        {"payments": [{"payment_id": "s3-test", "amount": "100.00", "currency": "USD"}]}
    ).encode()
    try:
        first = service.ingest("payments", "s3-test", content)
        assert archive.read(first["checksum"]) == content
        assert service.ingest("payments", "s3-test", content)["replayed"]
        assert service.verify_archive(first["batch_id"])
        archive.ready()
    finally:
        service.engine.dispose()
        for value in client.list_objects_v2(Bucket=bucket).get("Contents", []):
            client.delete_object(Bucket=bucket, Key=value["Key"])
        client.delete_bucket(Bucket=bucket)
