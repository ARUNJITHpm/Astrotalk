"""Object storage — generated media (cards, PDFs, logos) lives here, not on disk.

The prod host (HF Spaces Docker) has an ephemeral filesystem, so anything
generated that must survive a restart goes through this interface:

  - ``LocalStorage``  (mock_storage=True, default) — files under
    ``settings.storage_dir``; served back via ``GET /media/{key}``. Zero
    setup, right for dev and tests.
  - ``R2Storage``     (mock_storage=False) — Cloudflare R2 via the
    S3-compatible API (boto3, imported lazily so it stays optional in dev).

Keys are POSIX-style relative paths ("cards/2026-07-07/ashwathi.png"). The
API is synchronous (Pillow/reportlab producers are CPU-bound anyway); call
sites on the async path should offload via ``anyio.to_thread.run_sync``.
"""

from __future__ import annotations

import posixpath
from pathlib import Path

from app.platform.config import get_settings
from app.platform.logging_config import get_logger

logger = get_logger(__name__)


class StorageKeyError(ValueError):
    """Raised for keys that are absolute, escape the root, or are empty."""


def _clean_key(key: str) -> str:
    """Normalise and validate a storage key (defends the local impl against
    path traversal — /media/{key} serves straight from this namespace)."""
    key = (key or "").replace("\\", "/").strip("/")
    if not key:
        raise StorageKeyError("empty storage key")
    normalised = posixpath.normpath(key)
    if normalised.startswith("..") or "/../" in normalised or normalised.startswith("/"):
        raise StorageKeyError(f"unsafe storage key: {key!r}")
    return normalised


class Storage:
    """Interface. put() returns the key; url() returns where a browser can GET it."""

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        raise NotImplementedError

    def get(self, key: str) -> bytes | None:
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        raise NotImplementedError

    def delete(self, key: str) -> bool:
        raise NotImplementedError

    def url(self, key: str) -> str:
        """Browser-reachable URL. Default: proxied through GET /media/{key}."""
        return f"/media/{_clean_key(key)}"


class LocalStorage(Storage):
    """Dev/test impl — plain files under ``root`` (settings.storage_dir)."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        return self.root / _clean_key(key)

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        key = _clean_key(key)
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def get(self, key: str) -> bytes | None:
        path = self._path(key)
        return path.read_bytes() if path.is_file() else None

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete(self, key: str) -> bool:
        path = self._path(key)
        if path.is_file():
            path.unlink()
            return True
        return False


class R2Storage(Storage):
    """Cloudflare R2 through the S3-compatible API.

    boto3 is imported lazily: dev machines and CI never need it installed
    while mock_storage=True.
    """

    def __init__(
        self,
        *,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        public_base_url: str = "",
    ) -> None:
        import boto3  # lazy: only needed when storage is live

        self.bucket = bucket
        self.public_base_url = public_base_url.rstrip("/")
        self._client = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
        )

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        key = _clean_key(key)
        self._client.put_object(
            Bucket=self.bucket, Key=key, Body=data, ContentType=content_type
        )
        return key

    def get(self, key: str) -> bytes | None:
        try:
            response = self._client.get_object(Bucket=self.bucket, Key=_clean_key(key))
        except self._client.exceptions.NoSuchKey:
            return None
        return response["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=_clean_key(key))
        except self._client.exceptions.ClientError:
            return False
        return True

    def delete(self, key: str) -> bool:
        # S3 DeleteObject is idempotent and doesn't say whether the key existed.
        existed = self.exists(key)
        self._client.delete_object(Bucket=self.bucket, Key=_clean_key(key))
        return existed

    def url(self, key: str) -> str:
        key = _clean_key(key)
        if self.public_base_url:
            return f"{self.public_base_url}/{key}"
        return super().url(key)


_storage: Storage | None = None


def get_storage() -> Storage:
    """Process-wide storage singleton, chosen from settings on first use."""
    global _storage
    if _storage is None:
        settings = get_settings()
        if settings.mock_storage or not settings.r2_access_key_id:
            _storage = LocalStorage(settings.storage_dir)
            logger.info("storage: local disk at %s", settings.storage_dir)
        else:
            _storage = R2Storage(
                account_id=settings.r2_account_id,
                access_key_id=settings.r2_access_key_id,
                secret_access_key=settings.r2_secret_access_key,
                bucket=settings.r2_bucket,
                public_base_url=settings.r2_public_base_url,
            )
            logger.info("storage: Cloudflare R2 bucket %s", settings.r2_bucket)
    return _storage


def reset_storage() -> None:
    """Testing hook — forget the singleton so settings changes take effect."""
    global _storage
    _storage = None
