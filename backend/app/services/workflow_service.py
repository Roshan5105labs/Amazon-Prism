from __future__ import annotations

import uuid

from sqlmodel import Session, desc, select

from app.constants import InspectionStage, ReturnCaseStatus, RoutingDecisionType, VendorPermissionStatus
from app.models import (
    AIAssessment,
    ListingPreview,
    ProductHealthCard,
    ReturnCase,
    ReturnMedia,
    RoutingDecisionRecord,
    ViabilityResultRecord,
)
from app.schemas import (
    AIAssessmentCreate,
    AIAssessmentRead,
    ListingPreviewRead,
    ProductHealthCardRead,
    ReturnCaseDetailsResponse,
    ReturnCaseRead,
    ReturnCaseSummaryResponse,
    ReturnCaseWorkflowResponse,
    ReturnMediaRead,
    RoutingDecisionRead,
    VendorDecisionResponse,
    ViabilityResultRead,
)
from app.services.health_card_service import generate_health_card
from app.services.listing_service import generate_listing_preview
from app.services.routing_service import route_product
from app.services.viability_service import calculate_viability


def _ordered_records(session: Session, model, return_case_id: uuid.UUID):
    statement = (
        select(model)
        .where(model.return_case_id == return_case_id)
        .order_by(model.created_at)
    )
    return list(session.exec(statement).all())


def _latest_record(session: Session, model, return_case_id: uuid.UUID, stage: InspectionStage | None = None):
    statement = select(model).where(model.return_case_id == return_case_id)
    if stage is not None:
        statement = statement.where(model.stage == stage)
    statement = statement.order_by(desc(model.created_at))
    return session.exec(statement).first()


def get_authoritative_stage(session: Session, return_case_id: uuid.UUID) -> InspectionStage | None:
    final_assessment = _latest_record(session, AIAssessment, return_case_id, InspectionStage.FINAL_CHECK)
    if final_assessment is not None:
        return InspectionStage.FINAL_CHECK
    precheck_assessment = _latest_record(session, AIAssessment, return_case_id, InspectionStage.PRECHECK)
    if precheck_assessment is not None:
        return InspectionStage.PRECHECK
    return None


def get_latest_routing_decision(session: Session, return_case_id: uuid.UUID) -> RoutingDecisionRecord | None:
    authoritative_stage = get_authoritative_stage(session, return_case_id)
    if authoritative_stage is not None:
        record = _latest_record(session, RoutingDecisionRecord, return_case_id, authoritative_stage)
        if record is not None:
            return record
    return _latest_record(session, RoutingDecisionRecord, return_case_id)


def get_latest_health_card(session: Session, return_case_id: uuid.UUID) -> ProductHealthCard | None:
    authoritative_stage = get_authoritative_stage(session, return_case_id)
    if authoritative_stage is not None:
        record = _latest_record(session, ProductHealthCard, return_case_id, authoritative_stage)
        if record is not None:
            return record
    return _latest_record(session, ProductHealthCard, return_case_id)


def get_latest_listing_preview(session: Session, return_case_id: uuid.UUID) -> ListingPreview | None:
    authoritative_stage = get_authoritative_stage(session, return_case_id)
    if authoritative_stage is not None:
        record = _latest_record(session, ListingPreview, return_case_id, authoritative_stage)
        if record is not None:
            return record
    return _latest_record(session, ListingPreview, return_case_id)


def mark_case_for_uploaded_media(return_case: ReturnCase, stage: InspectionStage) -> ReturnCaseStatus:
    return (
        ReturnCaseStatus.AI_PENDING
        if stage == InspectionStage.PRECHECK
        else ReturnCaseStatus.FINAL_CHECK_PENDING
    )


def resolve_case_status_after_assessment(
    routing_decision: RoutingDecisionRecord,
    stage: InspectionStage,
) -> ReturnCaseStatus:
    if routing_decision.decision == RoutingDecisionType.MANUAL_REVIEW:
        return ReturnCaseStatus.MANUAL_REVIEW
    if routing_decision.requires_vendor_permission and routing_decision.vendor_permission_status == VendorPermissionStatus.PENDING:
        return ReturnCaseStatus.VENDOR_DECISION_PENDING
    if stage == InspectionStage.FINAL_CHECK:
        return ReturnCaseStatus.COMPLETED
    return ReturnCaseStatus.FINAL_CHECK_PENDING


def build_return_case_summary(return_case: ReturnCase, session: Session) -> ReturnCaseSummaryResponse:
    latest_health_card = get_latest_health_card(session, return_case.id)
    latest_routing_decision = get_latest_routing_decision(session, return_case.id)
    return ReturnCaseSummaryResponse(
        return_case=ReturnCaseRead.model_validate(return_case),
        latest_health_card=ProductHealthCardRead.model_validate(latest_health_card) if latest_health_card else None,
        latest_routing_decision=RoutingDecisionRead.model_validate(latest_routing_decision) if latest_routing_decision else None,
    )


def build_return_case_detail(return_case: ReturnCase, session: Session) -> ReturnCaseDetailsResponse:
    return ReturnCaseDetailsResponse(
        return_case=ReturnCaseRead.model_validate(return_case),
        media=[ReturnMediaRead.model_validate(item) for item in _ordered_records(session, ReturnMedia, return_case.id)],
        ai_assessments=[AIAssessmentRead.model_validate(item) for item in _ordered_records(session, AIAssessment, return_case.id)],
        viability_results=[ViabilityResultRead.model_validate(item) for item in _ordered_records(session, ViabilityResultRecord, return_case.id)],
        routing_decisions=[RoutingDecisionRead.model_validate(item) for item in _ordered_records(session, RoutingDecisionRecord, return_case.id)],
        health_cards=[ProductHealthCardRead.model_validate(item) for item in _ordered_records(session, ProductHealthCard, return_case.id)],
        listing_previews=[ListingPreviewRead.model_validate(item) for item in _ordered_records(session, ListingPreview, return_case.id)],
    )


def apply_assessment_workflow(
    return_case: ReturnCase,
    payload: AIAssessmentCreate,
    session: Session,
) -> ReturnCaseWorkflowResponse:
    assessment = AIAssessment(return_case_id=return_case.id, **payload.model_dump())
    session.add(assessment)
    session.flush()

    viability = calculate_viability(return_case, assessment)
    session.add(viability)
    session.flush()

    routing = route_product(return_case, assessment, viability)
    session.add(routing)
    session.flush()

    health_card = generate_health_card(return_case, assessment, routing)
    session.add(health_card)
    session.flush()

    listing_preview = generate_listing_preview(return_case, assessment, viability, routing)
    session.add(listing_preview)
    session.flush()

    return_case.status = resolve_case_status_after_assessment(routing, payload.stage)
    session.add(return_case)
    session.commit()
    session.refresh(return_case)
    session.refresh(assessment)
    session.refresh(viability)
    session.refresh(routing)
    session.refresh(health_card)
    session.refresh(listing_preview)

    return ReturnCaseWorkflowResponse(
        return_case=ReturnCaseRead.model_validate(return_case),
        ai_assessment=AIAssessmentRead.model_validate(assessment),
        viability=ViabilityResultRead.model_validate(viability),
        routing_decision=RoutingDecisionRead.model_validate(routing),
        health_card=ProductHealthCardRead.model_validate(health_card),
        listing_preview=ListingPreviewRead.model_validate(listing_preview),
    )


def apply_vendor_decision(
    return_case: ReturnCase,
    decision: VendorPermissionStatus,
    session: Session,
) -> VendorDecisionResponse:
    latest_routing = get_latest_routing_decision(session, return_case.id)
    if latest_routing is None or latest_routing.vendor_permission_status != VendorPermissionStatus.PENDING:
        raise ValueError("No routing decision is awaiting vendor approval.")
    if decision not in {VendorPermissionStatus.APPROVED, VendorPermissionStatus.REJECTED}:
        raise ValueError("Vendor decision must be APPROVED or REJECTED.")

    latest_routing.vendor_permission_status = decision
    if decision == VendorPermissionStatus.APPROVED:
        return_case.status = ReturnCaseStatus.COMPLETED
        message = "Vendor approved the routing decision."
    else:
        return_case.status = ReturnCaseStatus.VENDOR_REJECTED
        message = "Vendor rejected the routing decision."

    session.add(latest_routing)
    session.add(return_case)
    session.commit()
    session.refresh(return_case)
    session.refresh(latest_routing)

    return VendorDecisionResponse(
        message=message,
        return_case=ReturnCaseRead.model_validate(return_case),
        routing_decision=RoutingDecisionRead.model_validate(latest_routing),
    )
