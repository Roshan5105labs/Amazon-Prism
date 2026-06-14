from __future__ import annotations

import uuid
from io import BytesIO
from urllib.parse import quote

from fastapi import UploadFile
from minio import Minio

from app.config import get_settings
from app.constants import InspectionStage
from app.utils.file_utils import build_object_key, guess_content_type, sanitize_filename


def get_storage_client() -> Minio:
    settings = get_settings()
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def ensure_bucket_exists() -> None:
    settings = get_settings()
    client = get_storage_client()
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)


def build_object_url(object_key: str) -> str:
    settings = get_settings()
    return f"{settings.minio_public_base_url}/{settings.minio_bucket}/{quote(object_key)}"


async def upload_file_to_storage(
    upload_file: UploadFile,
    return_case_id: uuid.UUID,
    stage: InspectionStage,
) -> dict:
    settings = get_settings()
    client = get_storage_client()
    payload = await upload_file.read()
    file_name = sanitize_filename(upload_file.filename or "upload.bin")
    object_key = build_object_key(return_case_id, stage, file_name)
    content_type = guess_content_type(upload_file)

    client.put_object(
        settings.minio_bucket,
        object_key,
        BytesIO(payload),
        length=len(payload),
        content_type=content_type,
    )

    return {
        "file_name": file_name,
        "object_key": object_key,
        "object_url": build_object_url(object_key),
        "content_type": content_type,
        "size_bytes": len(payload),
    }
