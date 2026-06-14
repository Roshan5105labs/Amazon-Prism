from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session

from app.constants import InspectionStage
from app.database import get_session
from app.models import ReturnCase, ReturnMedia
from app.schemas import MediaUploadResponse, ReturnMediaRead
from app.services.storage_service import upload_file_to_storage
from app.services.workflow_service import mark_case_for_uploaded_media

router = APIRouter(prefix="/media", tags=["media"])


@router.post("/upload", response_model=MediaUploadResponse)
async def upload_media(
    return_case_id: uuid.UUID = Form(...),
    stage: InspectionStage = Form(...),
    files: list[UploadFile] = File(...),
    session: Session = Depends(get_session),
):
    return_case = session.get(ReturnCase, return_case_id)
    if return_case is None:
        raise HTTPException(status_code=404, detail="Return case not found")

    uploaded_assets: list[ReturnMedia] = []
    for upload in files:
        stored = await upload_file_to_storage(upload, return_case_id=return_case_id, stage=stage)
        asset = ReturnMedia(
            return_case_id=return_case_id,
            stage=stage,
            file_name=stored["file_name"],
            object_key=stored["object_key"],
            object_url=stored["object_url"],
            content_type=stored["content_type"],
            size_bytes=stored["size_bytes"],
        )
        session.add(asset)
        uploaded_assets.append(asset)

    return_case.status = mark_case_for_uploaded_media(return_case, stage)
    session.add(return_case)
    session.commit()
    session.refresh(return_case)
    for asset in uploaded_assets:
        session.refresh(asset)

    return MediaUploadResponse(
        uploaded=[ReturnMediaRead.model_validate(asset) for asset in uploaded_assets],
        return_case_status=return_case.status,
    )


@router.get("/{media_id}", response_model=ReturnMediaRead)
def get_media(media_id: uuid.UUID, session: Session = Depends(get_session)):
    asset = session.get(ReturnMedia, media_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Media asset not found")
    return ReturnMediaRead.model_validate(asset)
