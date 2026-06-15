from __future__ import annotations

import uuid

from sqlmodel import Session, select

from app.models import ReturnCase, RoutingDecisionRecord
from app.services.workflow_service import get_latest_routing_decision


def get_case_credits(session: Session, return_case_id: uuid.UUID):
    decision = get_latest_routing_decision(session, return_case_id)
    return decision, (decision.green_credits_awarded if decision else 0)


def get_credit_summary(session: Session) -> dict:
    cases = session.exec(select(ReturnCase)).all()
    total = 0
    counted = 0
    by_disposition: dict[str, int] = {}
    for case in cases:
        decision = get_latest_routing_decision(session, case.id)
        if decision is None:
            continue
        counted += 1
        credits = decision.green_credits_awarded or 0
        total += credits
        by_disposition[decision.decision] = by_disposition.get(decision.decision, 0) + credits
    return {"total_credits": total, "cases_counted": counted, "credits_by_disposition": by_disposition}
