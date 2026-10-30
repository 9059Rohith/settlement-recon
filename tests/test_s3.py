import hashlib
import io

import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber

from settlement_recon.domain import DomainError
from settlement_recon.s3 import S3Archive


@pytest.fixture
def archive(monkeypatch):
    # Explicit dummy credentials for unit-only SDK request validation, no AWS calls.
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "unit-test-only")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "unit-test-only")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-south-1")
    return S3Archive("synthetic-test-bucket")


def test_s3_encrypted_conditional_put(archive):
    content = b"synthetic input"
    checksum = hashlib.sha256(content).hexdigest()
    with Stubber(archive.client) as stub:
        stub.add_response(
            "put_object",
            {},
            {
                "Bucket": archive.bucket,
                "Key": f"raw/{checksum}",
                "Body": content,
                "IfNoneMatch": "*",
                "Metadata": {"sha256": checksum},
                "ServerSideEncryption": "AES256",
            },
        )
        assert archive.put(content) == checksum
        stub.assert_no_pending_responses()


def test_s3_existing_object_is_verified(archive):
    content = b"synthetic"
    checksum = hashlib.sha256(content).hexdigest()
    with Stubber(archive.client) as stub:
        stub.add_client_error(
            "put_object", service_error_code="PreconditionFailed", http_status_code=412
        )
        stub.add_response("get_object", {"Body": StreamingBody(io.BytesIO(content), len(content))})
        assert archive.put(content) == checksum


def test_s3_error_is_sanitized(archive):
    with Stubber(archive.client) as stub:
        stub.add_client_error(
            "put_object",
            service_error_code="AccessDenied",
            service_message="sensitive upstream details",
            http_status_code=403,
        )
        with pytest.raises(OSError, match="S3 archival unavailable"):
            archive.put(b"data")


def test_s3_checksum_namespace_validation():
    with pytest.raises(DomainError):
        S3Archive.key("../../escape")


def test_aws_kms_bucket_key_request_is_explicit(archive):
    archive.kms_key_arn = "arn:aws:kms:ap-south-1:123456789012:key/unit-test-only"
    content = b"synthetic KMS input"
    checksum = hashlib.sha256(content).hexdigest()
    with Stubber(archive.client) as stub:
        stub.add_response(
            "put_object",
            {},
            {
                "Bucket": archive.bucket,
                "Key": f"raw/{checksum}",
                "Body": content,
                "IfNoneMatch": "*",
                "Metadata": {"sha256": checksum},
                "ServerSideEncryption": "aws:kms",
                "SSEKMSKeyId": archive.kms_key_arn,
                "BucketKeyEnabled": True,
            },
        )
        assert archive.put(content) == checksum
