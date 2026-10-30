"""Immutable S3 raw adapter using conditional puts, never public ACLs."""

import hashlib
import re

import boto3
from botocore.exceptions import ClientError

from settlement_recon.domain import DomainError


class S3Archive:
    def __init__(self, bucket: str, kms_key_arn: str | None = None):
        self.bucket = bucket
        self.kms_key_arn = kms_key_arn
        self.client = boto3.session.Session().client(
            "s3",
            config=boto3.session.Config(
                connect_timeout=3, read_timeout=10, retries={"max_attempts": 3, "mode": "standard"}
            ),
        )

    @staticmethod
    def key(checksum: str) -> str:
        if not re.fullmatch(r"[0-9a-f]{64}", checksum):
            raise DomainError("Invalid archive checksum")
        return f"raw/{checksum}"

    def put(self, content: bytes) -> str:
        checksum = hashlib.sha256(content).hexdigest()
        try:
            encryption = {"ServerSideEncryption": "AES256"}
            if self.kms_key_arn:
                encryption = {
                    "ServerSideEncryption": "aws:kms",
                    "SSEKMSKeyId": self.kms_key_arn,
                    "BucketKeyEnabled": True,
                }
            self.client.put_object(
                Bucket=self.bucket,
                Key=self.key(checksum),
                Body=content,
                IfNoneMatch="*",
                Metadata={"sha256": checksum},
                **encryption,
            )
        except ClientError as exc:
            if exc.response["ResponseMetadata"]["HTTPStatusCode"] != 412:
                raise OSError("S3 archival unavailable") from None
            if self.read(checksum) != content:
                raise OSError("S3 archive checksum conflict") from None
        return checksum

    def read(self, checksum: str) -> bytes:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=self.key(checksum))
            with response["Body"] as body:
                return body.read()
        except ClientError:
            raise OSError("S3 archive read unavailable") from None

    def ready(self):
        self.client.head_bucket(Bucket=self.bucket)
