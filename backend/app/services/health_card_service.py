from __future__ import annotations

from app.constants import RoutingDecisionType, TRUST_BADGE_DEFAULT
from app.models import AIAssessment, ProductHealthCard, ReturnCase, RoutingDecisionRecord


def build_health_card(assessment: AIAssessment, routing_decision: RoutingDecisionRecord) -> dict:
    if routing_decision.decision in {
        RoutingDecisionType.RESELL,
        RoutingDecisionType.BUNDLE_RESALE,
        RoutingDecisionType.REFURBISH,
    }:
        green_impact = "Extends usable product life and reduces avoidable returns waste."
    elif routing_decision.decision == RoutingDecisionType.P2P_RESALE:
        green_impact = "Enables local resale and avoids unnecessary reverse-logistics movement."
    elif routing_decision.decision == RoutingDecisionType.EXCHANGE:
        green_impact = "Prevents an avoidable return loop by routing the customer to a better-fit replacement."
    elif routing_decision.decision == RoutingDecisionType.RETURNLESS:
        green_impact = "Avoids low-value reverse logistics while keeping the item out of landfill."
    elif routing_decision.decision == RoutingDecisionType.DONATE:
        green_impact = "Redirects a usable product to reuse instead of disposal."
    elif routing_decision.decision == RoutingDecisionType.RECYCLE:
        green_impact = "Recovers material value when reuse is no longer practical."
    else:
        green_impact = "Holding route pending operational or trust review."

    return {
        "stage": assessment.stage,
        "public_grade": assessment.grade,
        "health_score": assessment.product_health_score,
        "condition_summary": assessment.buyer_facing_summary,
        "trust_badge": TRUST_BADGE_DEFAULT,
        "recommended_route": routing_decision.decision,
        "green_impact": green_impact,
    }


def generate_health_card(
    return_case: ReturnCase,
    ai_assessment: AIAssessment,
    routing_decision: RoutingDecisionRecord,
) -> ProductHealthCard:
    values = build_health_card(ai_assessment, routing_decision)
    return ProductHealthCard(
        return_case_id=return_case.id,
        stage=ai_assessment.stage,
        public_grade=values["public_grade"],
        health_score=values["health_score"],
        condition_summary=values["condition_summary"],
        trust_badge=values["trust_badge"],
        recommended_route=values["recommended_route"],
        green_impact=values["green_impact"],
    )
