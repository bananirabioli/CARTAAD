"""Storage interface: local disk (default) or S3/MinIO-compatible."""

import mimetypes
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.config import get_settings


class Storage(Protocol):
    def save(self, key: str, data: bytes, content_type: str | None = None) -> str: ...
    def read(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def delete(self, key: str) -> None: ...


def guess_type(key: str) -> str:
    return mimetypes.guess_type(key)[0] or "application/octet-stream"


class LocalStorage:
    def __init__(self, base_dir: str):
        self.base = Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.base / key).resolve()
        if self.base.resolve() not in path.parents:
            raise ValueError("invalid storage key")
        return path

    def save(self, key: str, data: bytes, content_type: str | None = None) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class S3Storage:
    def __init__(self) -> None:
        import boto3

        s = get_settings()
        self.bucket = s.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=s.s3_endpoint_url,
            aws_access_key_id=s.s3_access_key,
            aws_secret_access_key=s.s3_secret_key,
            region_name=s.s3_region,
        )
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception:  # noqa: BLE001
            self.client.create_bucket(Bucket=self.bucket)

    def save(self, key: str, data: bytes, content_type: str | None = None) -> str:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type or guess_type(key))
        return key

    def read(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:  # noqa: BLE001
            return False

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)


@lru_cache
def get_storage() -> Storage:
    s = get_settings()
    return S3Storage() if s.storage_backend == "s3" else LocalStorage(s.storage_dir)


def client_key(client_id: int, *parts: str) -> str:
    return "/".join([f"c{client_id}", *parts])
