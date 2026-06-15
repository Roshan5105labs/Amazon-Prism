from __future__ import annotations

from app.constants import ListingType, RoutingDecisionType
from app.models import AIAssessment, ListingPreview, ReturnCase, RoutingDecisionRecord, ViabilityResultRecord


def _string_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def build_listing_preview(
    return_case: ReturnCase,
    assessment: AIAssessment,
    routing_decision: RoutingDecisionRecord,
    viability: ViabilityResultRecord,
) -> dict:
    if routing_decision.decision == RoutingDecisionType.BUNDLE_RESALE:
        listing_type = ListingType.BUNDLE_RESALE
        recommended_price = round(max(viability.expected_resale_price * 0.82, 0), 2)
    elif routing_decision.decision in {RoutingDecisionType.RESELL, RoutingDecisionType.REFURBISH}:
        listing_type = ListingType.INDIVIDUAL_RESALE
        recommended_price = round(max(viability.expected_resale_price, 0), 2)
    elif routing_decision.decision == RoutingDecisionType.P2P_RESALE:
        listing_type = ListingType.INDIVIDUAL_RESALE
        recommended_price = round(max(viability.expected_resale_price * 0.85, 0), 2)
    elif routing_decision.decision == RoutingDecisionType.EXCHANGE:
        listing_type = ListingType.INDIVIDUAL_RESALE
        recommended_price = round(max(viability.expected_resale_price * 0.90, 0), 2)
    else:
        listing_type = ListingType.NOT_APPLICABLE
        recommended_price = 0.0

    grade_value = _string_value(assessment.grade)
    packaging_value = _string_value(assessment.packaging_condition)
    usage_value = _string_value(assessment.usage_level)
    condition_badge = f"Grade {grade_value} | Score {assessment.product_health_score}"
    description = (
        f"{assessment.buyer_facing_summary} Packaging: {packaging_value}. "
        f"Usage level: {usage_value}. Missing parts: {'Yes' if assessment.missing_parts else 'No'}."
    )

    return {
        "stage": assessment.stage,
        "title": f"{return_case.product_name} - {condition_badge}",
        "description": description,
        "condition_badge": condition_badge,
        "recommended_price": recommended_price,
        "listing_type": listing_type,
    }


def generate_listing_preview(
    return_case: ReturnCase,
    ai_assessment: AIAssessment,
    viability_result: ViabilityResultRecord,
    routing_decision: RoutingDecisionRecord,
) -> ListingPreview:
    values = build_listing_preview(return_case, ai_assessment, routing_decision, viability_result)
    return ListingPreview(
        return_case_id=return_case.id,
        stage=ai_assessment.stage,
        title=values["title"],
        description=values["description"],
        condition_badge=values["condition_badge"],
        recommended_price=values["recommended_price"],
        listing_type=values["listing_type"],
    )
