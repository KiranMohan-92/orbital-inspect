"""
Storage abstraction for uploads and generated artifacts.

Supports local filesystem storage for development and S3-compatible object
storage for production-like environments such as MinIO, AWS S3, or R2.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse
import mimetypes
import uuid

from config import settings


@dataclass(frozen=True)
class StoredObject:
    uri: str
    key: str
    size_bytes: int
    content_type: str
    checksum_sha256: str
    local_path: str | None = None


def _metadata_strings(metadata: dict[str, Any] | None) -> dict[str, str]:
    if not metadata:
        return {}
    return {str(key): str(value) for key, value in metadata.items()}


def _suffix_for(filename: str, content_type: str) -> str:
    suffix = Path(filename).suffix
    if suffix:
        return suffix
    guessed = mimetypes.guess_extension(content_type or "")
    return guessed or ".bin"


def _object_key(category: str, filename: str, content_type: str, object_name: str | None = None) -> str:
    suffix = _suffix_for(filename, content_type)
    object_stem = object_name or uuid.uuid4().hex
    safe_category = category.strip("/").replace("..", "")
    return f"{safe_category}/{object_stem}{suffix}"


class LocalStorageBackend:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir

    def store_bytes(
        self,
        *,
        category: str,
        filename: str,
        data: bytes,
        content_type: str,
        metadata: dict[str, Any] | None = None,
        object_name: str | None = None,
    ) -> StoredObject:
        del metadata  # Metadata is implicit in local storage and DB records.
        key = _object_key(category, filename, content_type, object_name=object_name)
        target_path = self.root_dir / key
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(data)
        checksum = sha256(data).hexdigest()
        return StoredObject(
            uri=target_path.resolve().as_uri(),
            key=key,
            size_bytes=len(data),
            content_type=content_type,
            checksum_sha256=checksum,
            local_path=str(target_path.resolve()),
        )

    def read_bytes(self, uri: str) -> bytes:
        parsed = urlparse(uri)
        if parsed.scheme and parsed.scheme != "file":
            raise ValueError(f"Unsupported local storage URI scheme: {parsed.scheme}")
        path = Path(parsed.path if parsed.scheme == "file" else uri)
        return path.read_bytes()


class S3CompatibleStorageBackend:
    def __init__(
        self,
        *,
        bucket: str,
        prefix: str,
        region: str,
        endpoint_url: str | None,
        access_key_id: str | None,
        secret_access_key: str | None,
        force_path_style: bool,
        create_bucket: bool,
        client_factory: Callable[[], Any] | None = None,
    ):
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.region = region
        self.endpoint_url = endpoint_url
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.force_path_style = force_path_style
        self.create_bucket = create_bucket
        self._client_factory = client_factory
        self._bucket_ready = False
        self._client: Any | None = None

    def _build_client(self):
        if self._client_factory:
            return self._client_factory()
        import boto3
        from botocore.config import Config

        return boto3.client(
            "s3",
            region_name=self.region,
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            config=Config(
                s3={"addressing_style": "path" if self.force_path_style else "auto"},
                retries={"max_attempts": 5, "mode": "standard"},
            ),
        )

    @property
    def client(self):
        if self._client is None:
            self._client = self._build_client()
        return self._client

    def _ensure_bucket(self) -> None:
        if self._bucket_ready:
            return

        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception:
            if not self.create_bucket:
                raise
            create_args: dict[str, Any] = {"Bucket": self.bucket}
            if self.region != "us-east-1":
                create_args["CreateBucketConfiguration"] = {"LocationConstraint": self.region}
            self.client.create_bucket(**create_args)
        self._bucket_ready = True

    def store_bytes(
        self,
        *,
        category: str,
        filename: str,
        data: bytes,
        content_type: str,
        metadata: dict[str, Any] | None = None,
        object_name: str | None = None,
    ) -> StoredObject:
        key = _object_key(category, filename, content_type, object_name=object_name)
        if self.prefix:
            key = f"{self.prefix}/{key}"
        self._ensure_bucket()
        checksum = sha256(data).hexdigest()
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            Metadata=_metadata_strings(metadata),
        )
        return StoredObject(
            uri=f"s3://{self.bucket}/{key}",
            key=key,
            size_bytes=len(data),
            content_type=content_type,
            checksum_sha256=checksum,
        )

    def read_bytes(self, uri: str) -> bytes:
        parsed = urlparse(uri)
        if parsed.scheme != "s3":
            raise ValueError(f"Unsupported object storage URI scheme: {parsed.scheme}")
        bucket = parsed.netloc or self.bucket
        key = parsed.path.lstrip("/")
        response = self.client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()


def get_storage_backend():
    backend = settings.STORAGE_BACKEND.lower().strip()
    if backend == "s3":
        return S3CompatibleStorageBackend(
            bucket=settings.STORAGE_BUCKET or "",
            prefix=settings.STORAGE_PREFIX,
            region=settings.STORAGE_REGION,
            endpoint_url=settings.STORAGE_ENDPOINT_URL,
            access_key_id=settings.STORAGE_ACCESS_KEY_ID,
            secret_access_key=settings.STORAGE_SECRET_ACCESS_KEY,
            force_path_style=settings.STORAGE_FORCE_PATH_STYLE,
            create_bucket=settings.STORAGE_CREATE_BUCKET,
        )
    return LocalStorageBackend(settings.storage_local_root_path)
