"""MinIO object storage service — upload and download files (photos, documents)."""

import logging
from io import BytesIO

from minio import Minio
from minio.error import S3Error

from app.config import settings

logger = logging.getLogger(__name__)

_client: Minio | None = None


def _get_client() -> Minio:
    """Lazy-init MinIO client (singleton)."""
    global _client
    if _client is not None:
        return _client

    _client = Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )

    # Ensure bucket exists
    bucket = settings.MINIO_BUCKET
    if not _client.bucket_exists(bucket):
        _client.make_bucket(bucket)
        logger.info("Created MinIO bucket: %s", bucket)
    else:
        logger.debug("MinIO bucket exists: %s", bucket)

    return _client


async def upload_file(
    user_id: str,
    file_bytes: bytes,
    filename: str,
    content_type: str = "application/octet-stream",
) -> str | None:
    """
    Upload a file to MinIO.
    Returns the object key (path) on success, None on failure.

    Object key format: {user_id}/{filename}
    """
    if not file_bytes:
        return None

    client = _get_client()
    bucket = settings.MINIO_BUCKET
    object_key = f"{user_id}/{filename}"
    data = BytesIO(file_bytes)
    length = len(file_bytes)

    try:
        client.put_object(
            bucket_name=bucket,
            object_name=object_key,
            data=data,
            length=length,
            content_type=content_type,
        )
        logger.info("Uploaded to MinIO: %s (%d bytes)", object_key, length)
        return object_key

    except S3Error as exc:
        logger.error("MinIO upload failed for %s: %s", object_key, exc)
        return None


async def download_file(object_key: str) -> bytes | None:
    """
    Download a file from MinIO by object key.
    Returns file bytes or None on failure.
    """
    client = _get_client()
    bucket = settings.MINIO_BUCKET

    try:
        response = client.get_object(bucket_name=bucket, object_name=object_key)
        data = response.read()
        response.close()
        response.release_conn()
        logger.info("Downloaded from MinIO: %s (%d bytes)", object_key, len(data))
        return data

    except S3Error as exc:
        logger.error("MinIO download failed for %s: %s", object_key, exc)
        return None


async def delete_file(object_key: str) -> bool:
    """Delete a file from MinIO. Returns True on success."""
    client = _get_client()
    bucket = settings.MINIO_BUCKET

    try:
        client.remove_object(bucket_name=bucket, object_name=object_key)
        logger.info("Deleted from MinIO: %s", object_key)
        return True
    except S3Error as exc:
        logger.error("MinIO delete failed for %s: %s", object_key, exc)
        return False
