from __future__ import annotations

from app.constants import (
    DemandLevel,
    FulfillmentType,
    Grade,
    InspectionStage,
    MANUAL_REVIEW_CONFIDENCE_THRESHOLD,
    RoutingDecisionType,
    VendorPermissionStatus,
    ViabilityLabel,
)
from app.models import AIAssessment, ReturnCase, RoutingDecisionRecord, ViabilityResultRecord


def build_routing_decision(return_case: ReturnCase, assessment: AIAssessment, viability: ViabilityResultRecord) -> dict:
    if assessment.confidence < MANUAL_REVIEW_CONFIDENCE_THRESHOLD:
        return {
            "stage": assessment.stage,
            "decision": RoutingDecisionType.MANUAL_REVIEW,
            "reason": "Assessment confidence is too low to automate safely.",
            "requires_vendor_permission": False,
            "vendor_permission_status": VendorPermissionStatus.NOT_REQUIRED,
        }

    net = viability.net_recovery_value
    health_score = assessment.product_health_score

    if assessment.stage == InspectionStage.PRECHECK and net >= 80 and health_score >= 80:
        decision = RoutingDecisionType.SEND_TO_VENDOR_OR_WAREHOUSE
        reason = "Precheck indicates strong recovery potential and good product health."
    elif health_score >= 85 and net >= 100 and return_case.demand_level in {DemandLevel.HIGH, DemandLevel.MEDIUM}:
        decision = RoutingDecisionType.RESELL
        reason = "High health score and strong recovery value support individual resale."
    elif health_score >= 80 and 20 <= net < 100:
        decision = RoutingDecisionType.BUNDLE_RESALE
        reason = "Good condition but moderate economics make bundle resale the better path."
    elif assessment.grade == Grade.B and health_score >= 65 and return_case.refurb_cost <= net:
        decision = RoutingDecisionType.REFURBISH
        reason = "Refurbishment cost is justified by the expected net recovery value."
    elif health_score >= 60 and net < 20:
        decision = RoutingDecisionType.DONATE
        reason = "Low economic upside but still usable enough to donate."
    elif 40 <= health_score < 60:
        decision = RoutingDecisionType.LIQUIDATE
        reason = "Mid-tier condition with limited value recovery is best suited for liquidation."
    elif health_score < 40:
        decision = RoutingDecisionType.RECYCLE
        reason = "Low health score makes recycling the safest route."
    else:
        decision = RoutingDecisionType.LIQUIDATE
        reason = "Fallback route selected because the item does not meet stronger recovery thresholds."

    requires_vendor_permission = (
        return_case.fulfillment_type == FulfillmentType.FBM
        and decision != RoutingDecisionType.MANUAL_REVIEW
    )
    vendor_permission_status = (
        VendorPermissionStatus.PENDING if requires_vendor_permission else VendorPermissionStatus.NOT_REQUIRED
    )

    return {
        "stage": assessment.stage,
        "decision": decision,
        "reason": reason,
        "requires_vendor_permission": requires_vendor_permission,
        "vendor_permission_status": vendor_permission_status,
    }


def route_product(
    return_case: ReturnCase,
    ai_assessment: AIAssessment,
    viability_result: ViabilityResultRecord,
) -> RoutingDecisionRecord:
    values = build_routing_decision(return_case, ai_assessment, viability_result)
    return RoutingDecisionRecord(
        return_case_id=return_case.id,
        stage=ai_assessment.stage,
        decision=values["decision"],
        reason=values["reason"],
        requires_vendor_permission=values["requires_vendor_permission"],
        vendor_permission_status=values["vendor_permission_status"],
    )
