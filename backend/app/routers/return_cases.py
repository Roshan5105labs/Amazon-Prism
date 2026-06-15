from __future__ import annotations

import uuid
from collections import Counter

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlmodel import Session, desc, select

from app.constants import InspectionStage, ReturnCaseStatus, VendorPermissionStatus
from app.database import get_session
from app.models import ReturnCase, ReturnMedia
from app.schemas import (
    AIAssessmentCreate,
    CaseGreenCreditsResponse,
    FinalCheckResponse,
    GreenCreditSummaryResponse,
    RenewedRecommendation,
    RenewedRecommendationsResponse,
    ListingPreviewRead,
    MediaUploadResponse,
    PreventionResponse,
    ProductHealthCardRead,
    ReturnCaseCreate,
    ReturnCaseDetailsResponse,
    ReturnCaseRead,
    ReturnCaseSummaryResponse,
    ReturnCaseWorkflowResponse,
    ReturnMediaRead,
    VendorDecisionRequest,
    VendorDecisionResponse,
)
from app.services.vision_service import assess_media
from app.services.green_credit_service import get_case_credits, get_credit_summary
from app.services.storage_service import get_file_bytes, upload_file_to_storage
from app.services.workflow_service import (
    apply_assessment_workflow,
    apply_vendor_decision,
    build_return_case_detail,
    build_return_case_summary,
    get_latest_health_card,
    get_latest_listing_preview,
    mark_case_for_uploaded_media,
)

router = APIRouter(tags=["returns"])


def _get_return_case_or_404(return_case_id: uuid.UUID, session: Session) -> ReturnCase:
    return_case = session.get(ReturnCase, return_case_id)
    if return_case is None:
        raise HTTPException(status_code=404, detail="Return case not found")
    return return_case


async def _store_media(
    session: Session,
    return_case: ReturnCase,
    stage: InspectionStage,
    upload: UploadFile,
) -> ReturnMedia:
    stored = await upload_file_to_storage(upload, return_case_id=return_case.id, stage=stage)
    media = ReturnMedia(
        return_case_id=return_case.id,
        stage=stage,
        file_name=stored["file_name"],
        object_key=stored["object_key"],
        object_url=stored["object_url"],
        content_type=stored["content_type"],
        size_bytes=stored["size_bytes"],
    )
    session.add(media)
    session.flush()
    session.refresh(media)
    return media


@router.post("/return-cases", response_model=ReturnCaseRead)
@router.post("/returns", response_model=ReturnCaseRead, include_in_schema=False)
def create_return_case(payload: ReturnCaseCreate, session: Session = Depends(get_session)):
    return_case = ReturnCase(**payload.model_dump(), status=ReturnCaseStatus.CREATED)
    session.add(return_case)
    session.commit()
    session.refresh(return_case)
    return ReturnCaseRead.model_validate(return_case)


@router.post("/return-cases/{return_case_id}/media", response_model=MediaUploadResponse)
async def upload_return_case_media(
    return_case_id: uuid.UUID,
    stage: InspectionStage = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    return_case = _get_return_case_or_404(return_case_id, session)
    media = await _store_media(session, return_case, stage, file)
    return_case.status = mark_case_for_uploaded_media(return_case, stage)
    session.add(return_case)
    session.commit()
    session.refresh(return_case)
    return MediaUploadResponse(
        uploaded=[ReturnMediaRead.model_validate(media)],
        return_case_status=return_case.status,
    )


@router.post("/return-cases/{return_case_id}/ai-assessment", response_model=ReturnCaseWorkflowResponse)
@router.post("/returns/{return_case_id}/assessments", response_model=ReturnCaseWorkflowResponse, include_in_schema=False)
def submit_ai_assessment(
    return_case_id: uuid.UUID,
    payload: AIAssessmentCreate,
    session: Session = Depends(get_session),
):
    return_case = _get_return_case_or_404(return_case_id, session)
    return apply_assessment_workflow(return_case, payload, session)


@router.post("/return-cases/{return_case_id}/run-ai-assessment", response_model=ReturnCaseWorkflowResponse)
def run_ai_assessment(
    return_case_id: uuid.UUID,
    stage: InspectionStage = Query(default=InspectionStage.PRECHECK),
    session: Session = Depends(get_session),
):
    """Run the vision model on the case's media for `stage` (images and/or a
    video) and push the result through the assessment workflow."""
    return_case = _get_return_case_or_404(return_case_id, session)
    media = session.exec(
        select(ReturnMedia)
        .where(ReturnMedia.return_case_id == return_case_id, ReturnMedia.stage == stage)
        .order_by(desc(ReturnMedia.created_at))
    ).all()
    if not media:
        raise HTTPException(status_code=400, detail=f"Upload {stage.value} media first")

    images: list[tuple[bytes, str]] = []
    video = None
    for m in media:
        ctype = (m.content_type or "").lower()
        if ctype.startswith("video/") and video is None:
            video = (get_file_bytes(m.object_key), ctype, m.file_name)
        elif ctype.startswith("image/"):
            images.append((get_file_bytes(m.object_key), ctype))

    payload = assess_media(return_case, stage, images, video)
    return apply_assessment_workflow(return_case, payload, session)


@router.post("/return-cases/{return_case_id}/final-check", response_model=FinalCheckResponse)
async def upload_final_check(
    return_case_id: uuid.UUID,
    file: UploadFile | None = File(default=None),
    session: Session = Depends(get_session),
):
    return_case = _get_return_case_or_404(return_case_id, session)
    uploaded_media: list[ReturnMediaRead] = []
    if file is not None:
        media = await _store_media(session, return_case, InspectionStage.FINAL_CHECK, file)
        uploaded_media.append(ReturnMediaRead.model_validate(media))

    return_case.status = ReturnCaseStatus.FINAL_CHECK_PENDING
    session.add(return_case)
    session.commit()
    session.refresh(return_case)

    return FinalCheckResponse(
        message="Final check media uploaded. AI assessment pending.",
        return_case=ReturnCaseRead.model_validate(return_case),
        uploaded_media=uploaded_media,
    )


@router.post("/return-cases/{return_case_id}/vendor-decision", response_model=VendorDecisionResponse)
def submit_vendor_decision(
    return_case_id: uuid.UUID,
    payload: VendorDecisionRequest,
    session: Session = Depends(get_session),
):
    if payload.decision not in {VendorPermissionStatus.APPROVED, VendorPermissionStatus.REJECTED}:
        raise HTTPException(status_code=422, detail="decision must be APPROVED or REJECTED")
    return_case = _get_return_case_or_404(return_case_id, session)
    try:
        return apply_vendor_decision(return_case, payload.decision, session)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/return-cases", response_model=list[ReturnCaseSummaryResponse])
@router.get("/returns", response_model=list[ReturnCaseSummaryResponse], include_in_schema=False)
def list_return_cases(session: Session = Depends(get_session)):
    cases = session.exec(select(ReturnCase).order_by(ReturnCase.created_at.desc())).all()
    return [build_return_case_summary(item, session) for item in cases]


@router.get("/return-cases/{return_case_id}", response_model=ReturnCaseDetailsResponse)
@router.get("/returns/{return_case_id}", response_model=ReturnCaseDetailsResponse, include_in_schema=False)
def get_return_case(return_case_id: uuid.UUID, session: Session = Depends(get_session)):
    return_case = _get_return_case_or_404(return_case_id, session)
    return build_return_case_detail(return_case, session)


@router.get("/return-cases/{return_case_id}/health-card", response_model=ProductHealthCardRead)
def get_return_case_health_card(return_case_id: uuid.UUID, session: Session = Depends(get_session)):
    _get_return_case_or_404(return_case_id, session)
    health_card = get_latest_health_card(session, return_case_id)
    if health_card is None:
        raise HTTPException(status_code=404, detail="Health card not found")
    return ProductHealthCardRead.model_validate(health_card)


@router.get("/return-cases/{return_case_id}/listing-preview", response_model=ListingPreviewRead)
def get_return_case_listing_preview(return_case_id: uuid.UUID, session: Session = Depends(get_session)):
    _get_return_case_or_404(return_case_id, session)
    listing_preview = get_latest_listing_preview(session, return_case_id)
    if listing_preview is None:
        raise HTTPException(status_code=404, detail="Listing preview not found")
    return ListingPreviewRead.model_validate(listing_preview)


@router.get("/return-cases/{return_case_id}/green-credits", response_model=CaseGreenCreditsResponse, tags=["green-credits"])
def get_case_green_credits(return_case_id: uuid.UUID, session: Session = Depends(get_session)):
    _get_return_case_or_404(return_case_id, session)
    decision, credits = get_case_credits(session, return_case_id)
    return CaseGreenCreditsResponse(
        return_case_id=return_case_id,
        decision=decision.decision if decision else None,
        green_credits_awarded=credits,
    )


@router.get("/green-credits/summary", response_model=GreenCreditSummaryResponse, tags=["green-credits"])
def get_green_credits_summary(session: Session = Depends(get_session)):
    return GreenCreditSummaryResponse(**get_credit_summary(session))


@router.get("/recommendations", response_model=RenewedRecommendationsResponse, tags=["recommendations"])
def renewed_recommendations(category: str, limit: int = 5, session: Session = Depends(get_session)):
    """Personalized renewed recommendations: live renewed listings in a category."""
    cases = session.exec(
        select(ReturnCase).where(ReturnCase.category == category).order_by(desc(ReturnCase.created_at))
    ).all()
    recs: list[RenewedRecommendation] = []
    for case in cases:
        listing = get_latest_listing_preview(session, case.id)
        card = get_latest_health_card(session, case.id)
        if listing is None or card is None:
            continue
        recs.append(RenewedRecommendation(
            listing_id=listing.id, return_case_id=case.id, title=listing.title,
            grade=card.public_grade, price=listing.recommended_price, health_score=card.health_score,
        ))
        if len(recs) >= limit:
            break
    return RenewedRecommendationsResponse(category=category, recommendations=recs)


@router.get("/prevention", response_model=PreventionResponse, tags=["prevention"])
def prevention_nudge(category: str, session: Session = Depends(get_session)):
    rows = session.exec(select(ReturnCase).where(ReturnCase.category == category)).all()
    reasons = Counter(row.return_reason for row in rows if row.return_reason)
    if not reasons:
        return PreventionResponse(category=category, nudge=None)
    top_reason, count = reasons.most_common(1)[0]
    share = count / sum(reasons.values())
    nudge = None
    if share >= 0.5:
        nudge = f"{share:.0%} of returns for this category were '{top_reason}'. Consider this before buying."
    return PreventionResponse(
        category=category,
        top_reason=top_reason,
        share=round(share, 2),
        nudge=nudge,
    )
