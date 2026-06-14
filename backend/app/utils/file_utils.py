from __future__ import annotations

import mimetypes
import re
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.constants import InspectionStage


def sanitize_filename(filename: str) -> str:
    safe_name = Path(filename or "upload.bin").name
    return re.sub(r"[^A-Za-z0-9._-]", "_", safe_name)


def guess_content_type(upload_file: UploadFile) -> str:
    if upload_file.content_type:
        return upload_file.content_type
    guessed, _ = mimetypes.guess_type(upload_file.filename or "")
    return guessed or "application/octet-stream"


def build_object_key(return_case_id: uuid.UUID, stage: InspectionStage, filename: str) -> str:
    return (
        f"return-cases/{return_case_id}/{stage.value.lower()}/"
        f"{uuid.uuid4().hex}-{sanitize_filename(filename)}"
    )
