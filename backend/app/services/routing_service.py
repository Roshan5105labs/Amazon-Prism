from __future__ import annotations

from app.constants import (
    DemandLevel,
    DEMAND_MULTIPLIER,
    FulfillmentType,
    Grade,
    GRADE_PRICE_FACTOR,
    GREEN_CREDIT_POINTS,
    InspectionStage,
    MANUAL_REVIEW_CONFIDENCE_THRESHOLD,
    RoutingDecisionType,
    VendorPermissionStatus,
    ViabilityLabel,
)
from app.models import AIAssessment, ReturnCase, RoutingDecisionRecord, ViabilityResultRecord

RETURNLESS_VALUE_CEILING = 300.0
_FIT_OR_PREFERENCE_KEYWORDS = (
    "size", "fit", "small", "large", "big", "tight", "loose",
    "colour", "color", "wrong item", "wrong product", "wrong model",
    "wrong variant", "wrong size", "incompatible", "not compatible",
    "ordered by mistake", "mistake", "changed mind", "prefer", "preference",
    "not as expected", "didn't like", "did not like", "style",
)


def _as_grade(v) -> Grade:
    return v if isinstance(v, Grade) else Grade(v)


def _as_stage(v) -> InspectionStage:
    return v if isinstance(v, InspectionStage) else InspectionStage(v)


def _as_demand(v) -> DemandLevel:
    return v if isinstance(v, DemandLevel) else DemandLevel(v)


def _is_fit_or_preference(reason) -> bool:
    text = (reason or "").lower()
    return any(k in text for k in _FIT_OR_PREFERENCE_KEYWORDS)


def _choose_decision(return_case, assessment, viability):
    grade = _as_grade(assessment.grade)
    stage = _as_stage(assessment.stage)
    demand = _as_demand(return_case.demand_level)
    net = viability.net_recovery_value
    health = assessment.product_health_score

    demand_mult = DEMAND_MULTIPLIER.get(demand, 0.75)
    asis_resale = viability.expected_resale_price
    refurb_resale = round(return_case.original_price * GRADE_PRICE_FACTOR[Grade.A] * demand_mult, 2)
    refurb_uplift = round(refurb_resale - asis_resale, 2)
    refurb_worth_it = grade in (Grade.B, Grade.C) and refurb_uplift > return_case.refurb_cost

    good_condition = grade in (Grade.A, Grade.B) or health >= 75
    usable = health >= 55
    missing_parts = bool(getattr(assessment, "missing_parts", False))
    usage = str(getattr(assessment, "usage_level", "UNKNOWN"))
    packaging = str(getattr(assessment, "packaging_condition", "GOOD"))
    resellable_for_exchange = (
        good_condition
        or (grade == Grade.C and health >= 55 and not missing_parts and usage != "HEAVY" and packaging != "DAMAGED")
    )
    is_cheap = return_case.original_price <= RETURNLESS_VALUE_CEILING

    # Exchange: wrong size/model/preference return of a still-resellable item.
    if _is_fit_or_preference(return_case.return_reason) and resellable_for_exchange:
        return (RoutingDecisionType.EXCHANGE,
                "Wrong fit/model/preference return in resellable condition -> offer a replacement; "
                "the returned unit re-enters resale or renewed inventory.")

    if stage == InspectionStage.PRECHECK:
        if refurb_worth_it or (health >= 70 and net >= 40):
            return (RoutingDecisionType.SEND_TO_VENDOR_OR_WAREHOUSE,
                    "Recovery potential justifies bringing the item in for final inspection.")
        if good_condition and net < 0 and is_cheap:
            return (RoutingDecisionType.RETURNLESS,
                    "Negative recovery on a low-value item -> customer keeps it (returnless); "
                    "reverse logistics is skipped entirely.")
        if good_condition:
            return (RoutingDecisionType.P2P_RESALE,
                    "Good condition but uneconomical to warehouse -> list to a local peer (P2P) buyer.")
        if usable:
            return (RoutingDecisionType.DONATE,
                    "Usable but no resale upside and not worth warehousing -> donate locally.")
        if health >= 40:
            return (RoutingDecisionType.LIQUIDATE, "Limited residual value -> liquidate in bulk.")
        return (RoutingDecisionType.RECYCLE, "Not usable -> recycle for material recovery.")

    # FINAL_CHECK: terminal disposition.
    if refurb_worth_it:
        return (RoutingDecisionType.REFURBISH,
                f"Refurbish uplift Rs{refurb_uplift:.0f} exceeds refurb cost "
                f"Rs{return_case.refurb_cost:.0f}; restore to like-new and resell.")
    if health >= 80 and net >= 80 and demand in (DemandLevel.HIGH, DemandLevel.MEDIUM):
        return (RoutingDecisionType.RESELL,
                "High health and strong recovery value support individual resale.")
    if health >= 70 and net >= 20:
        return (RoutingDecisionType.BUNDLE_RESALE,
                "Good condition but moderate economics -> bundle resale recovers more than singles.")
    if net < 20:
        if good_condition and net < 0 and is_cheap:
            return (RoutingDecisionType.RETURNLESS,
                    "Negative recovery on a low-value item -> returnless; customer keeps it.")
        if good_condition:
            return (RoutingDecisionType.P2P_RESALE,
                    "Good condition but uneconomical to warehouse -> local peer (P2P) resale.")
        if usable:
            return (RoutingDecisionType.DONATE,
                    "Usable but no resale upside -> donate for reuse and sustainability credit.")
    if health < 40:
        return (RoutingDecisionType.RECYCLE, "Low health score -> recycle for material recovery.")
    return (RoutingDecisionType.LIQUIDATE, "Does not meet stronger recovery thresholds -> liquidate.")


def build_routing_decision(return_case: ReturnCase, assessment: AIAssessment, viability: ViabilityResultRecord) -> dict:
    if assessment.confidence < MANUAL_REVIEW_CONFIDENCE_THRESHOLD:
        return {
            "stage": assessment.stage,
            "decision": RoutingDecisionType.MANUAL_REVIEW,
            "reason": "Assessment confidence is too low to automate safely.",
            "requires_vendor_permission": False,
            "vendor_permission_status": VendorPermissionStatus.NOT_REQUIRED,
            "green_credits_awarded": 0,
        }

    decision, reason = _choose_decision(return_case, assessment, viability)
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
        "green_credits_awarded": GREEN_CREDIT_POINTS.get(decision, 0),
    }


def route_product(return_case, ai_assessment, viability_result) -> RoutingDecisionRecord:
    v = build_routing_decision(return_case, ai_assessment, viability_result)
    return RoutingDecisionRecord(
        return_case_id=return_case.id,
        stage=ai_assessment.stage,
        decision=v["decision"],
        reason=v["reason"],
        requires_vendor_permission=v["requires_vendor_permission"],
        vendor_permission_status=v["vendor_permission_status"],
        green_credits_awarded=v["green_credits_awarded"],
    )
