import os
from pathlib import Path

os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key")

from services.storage_service import LocalStorageBackend, S3CompatibleStorageBackend


class _FakeBody:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data


class _FakeS3Client:
    def __init__(self):
        self.created_buckets: list[dict] = []
        self.objects: dict[tuple[str, str], bytes] = {}
        self.metadata: dict[tuple[str, str], dict] = {}
        self._bucket_exists = False

    def head_bucket(self, Bucket: str):
        if not self._bucket_exists:
            raise RuntimeError(f"missing bucket: {Bucket}")

    def create_bucket(self, **kwargs):
        self.created_buckets.append(kwargs)
        self._bucket_exists = True

    def put_object(self, **kwargs):
        bucket = kwargs["Bucket"]
        key = kwargs["Key"]
        self.objects[(bucket, key)] = kwargs["Body"]
        self.metadata[(bucket, key)] = kwargs.get("Metadata", {})

    def get_object(self, Bucket: str, Key: str):
        return {"Body": _FakeBody(self.objects[(Bucket, Key)])}


def test_local_storage_backend_round_trips_bytes(tmp_path):
    backend = LocalStorageBackend(tmp_path)

    stored = backend.store_bytes(
        category="uploads",
        filename="sample.jpg",
        data=b"image-bytes",
        content_type="image/jpeg",
        metadata={"analysis_id": "analysis-1"},
        object_name="analysis-1-primary",
    )

    assert stored.uri.startswith("file://")
    assert stored.key == "uploads/analysis-1-primary.jpg"
    assert stored.checksum_sha256
    assert stored.local_path
    assert Path(stored.local_path).exists()
    assert Path(stored.local_path).read_bytes() == b"image-bytes"
    assert backend.read_bytes(stored.uri) == b"image-bytes"


def test_s3_compatible_storage_backend_creates_bucket_and_stores_object():
    fake_client = _FakeS3Client()
    backend = S3CompatibleStorageBackend(
        bucket="orbital-inspect-e2e",
        prefix="runtime",
        region="us-east-1",
        endpoint_url="http://127.0.0.1:9000",
        access_key_id="orbital",
        secret_access_key="orbital_storage_password",
        force_path_style=True,
        create_bucket=True,
        client_factory=lambda: fake_client,
    )

    stored = backend.store_bytes(
        category="reports",
        filename="analysis.html",
        data=b"<html>report</html>",
        content_type="text/html",
        metadata={"analysis_id": "analysis-2", "kind": "html"},
        object_name="analysis-2-v1",
    )

    assert fake_client.created_buckets == [{"Bucket": "orbital-inspect-e2e"}]
    assert stored.uri == "s3://orbital-inspect-e2e/runtime/reports/analysis-2-v1.html"
    assert stored.key == "runtime/reports/analysis-2-v1.html"
    assert fake_client.metadata[("orbital-inspect-e2e", stored.key)] == {
        "analysis_id": "analysis-2",
        "kind": "html",
    }
    assert backend.read_bytes(stored.uri) == b"<html>report</html>"
