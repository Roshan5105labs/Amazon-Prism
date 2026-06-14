from __future__ import annotations

from app.constants import ViabilityLabel
from app.models import AIAssessment, ReturnCase, ViabilityResultRecord


def calculate_expected_resale_price(return_case: ReturnCase, assessment: AIAssessment) -> float:
    multiplier = 0.70 if return_case.original_price < 500 else 0.75
    return round(return_case.original_price * multiplier, 2)


def calculate_total_recovery_cost(return_case: ReturnCase, assessment: AIAssessment) -> float:
    total = (
        return_case.reverse_logistics_cost
        + return_case.inspection_cost
        + return_case.repacking_cost
        + return_case.relisting_cost
        + return_case.refurb_cost
    )
    return round(total, 2)


def build_viability_values(return_case: ReturnCase, assessment: AIAssessment) -> dict:
    expected_resale_price = calculate_expected_resale_price(return_case, assessment)
    total_recovery_cost = calculate_total_recovery_cost(return_case, assessment)
    net_recovery_value = round(expected_resale_price - total_recovery_cost, 2)

    if net_recovery_value >= 120:
        label = ViabilityLabel.HIGH
    elif net_recovery_value >= 40:
        label = ViabilityLabel.MEDIUM
    elif net_recovery_value >= 0:
        label = ViabilityLabel.LOW
    else:
        label = ViabilityLabel.NEGATIVE

    return {
        "stage": assessment.stage,
        "expected_resale_price": expected_resale_price,
        "total_recovery_cost": total_recovery_cost,
        "net_recovery_value": net_recovery_value,
        "viability_label": label,
    }


def calculate_viability(return_case: ReturnCase, ai_assessment: AIAssessment) -> ViabilityResultRecord:
    values = build_viability_values(return_case, ai_assessment)
    return ViabilityResultRecord(
        return_case_id=return_case.id,
        stage=ai_assessment.stage,
        expected_resale_price=values["expected_resale_price"],
        total_recovery_cost=values["total_recovery_cost"],
        net_recovery_value=values["net_recovery_value"],
        viability_label=values["viability_label"],
    )
