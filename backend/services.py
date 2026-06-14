"""
services.py
-----------
The deterministic brain. Everything here is plain Python you can read, test,
and defend line-by-line to a judge — no black box. Four parts:

  1. viability_check   -> is it worth bringing back to a warehouse at all?
  2. route_*           -> given the answer, pick the best disposition
  3. generate_listing  -> build the relisting + Health Card (copy is stubbed)
  4. award_credits     -> green-credit ledger
"""
from __future__ import annotations

from typing import Optional

from sqlmodel import Session

from models import (
    CategoryData, Disposition, Grade, GreenCredit, ListingStatus,
    GradeResult, ReturnRequest, RoutingResult, ViabilityResult,
)

# ---- tunable parameters (your model's, NOT Amazon's published numbers) ----- #
REVERSE_LOGISTICS_COST = 60.0        # ₹ to pick up + handle a small return
VIABILITY_MARGIN = 0.0               # require recovery to beat cost by this much

# how much of avg_resale_price a unit of each grade can recover
_GRADE_RECOVERY = {Grade.A: 0.85, Grade.B: 0.60, Grade.C: 0.30, Grade.D: 0.05}
# discount factor applied to original_price when pricing a renewed listing
_GRADE_PRICE = {Grade.A: 0.85, Grade.B: 0.70, Grade.C: 0.50, Grade.D: 0.20}
_GRADE_WARRANTY = {Grade.A: 90, Grade.B: 90, Grade.C: 30, Grade.D: 0}

CREDITS = {
    "return_to_resale": 50,
    "p2p_list": 20,
    "donate": 40,
    "buy_renewed": 30,
}


# --------------------------------------------------------------------------- #
# 1. Viability  — the "cost viability check" gate
# --------------------------------------------------------------------------- #
def viability_check(
    original_price: float, grade: Grade, cat: CategoryData
) -> ViabilityResult:
    """Is the BEST achievable recovery worth the reverse-logistics cost?
    Considers selling as-is AND refurbishing to like-new, so a cheaply-fixable
    item (e.g. a dirty mouse that just needs a clean + new glide pad) isn't
    wrongly judged worthless at its as-is grade before routing even runs.
    If not worth it, the item is handled locally (P2P/donate) — never warehoused.
    """
    d = cat.avg_demand
    asis_ev = cat.avg_resale_price * _GRADE_RECOVERY[grade] * d
    refurb_ev = (
        cat.avg_resale_price * _GRADE_RECOVERY[Grade.A] * d - cat.refurb_cost
        if grade != Grade.D else asis_ev          # broken items can't be refurbished
    )
    recovery = max(asis_ev, refurb_ev)
    viable = (recovery - REVERSE_LOGISTICS_COST) > VIABILITY_MARGIN
    reason = (
        f"Best recovery Rs{recovery:.0f} (as-is or refurbished) vs reverse cost "
        f"Rs{REVERSE_LOGISTICS_COST:.0f}: "
        + ("worth processing" if viable else "not worth a warehouse trip")
    )
    return ViabilityResult(
        viable=viable,
        est_reverse_cost=REVERSE_LOGISTICS_COST,
        est_recovery=round(recovery, 2),
        reason=reason,
    )


# --------------------------------------------------------------------------- #
# 2. Routing
# --------------------------------------------------------------------------- #
def route_non_viable(grade: Grade) -> RoutingResult:
    """Cheap to return, so keep it local. Good item -> find a local owner (P2P);
    otherwise donate or recycle. The product still gets a second life."""
    if grade in (Grade.A, Grade.B):
        return RoutingResult(
            disposition=Disposition.P2P,
            reason="Good condition but uneconomical to warehouse -> local peer resale",
        )
    if grade == Grade.C:
        return RoutingResult(
            disposition=Disposition.DONATE,
            reason="Usable but low value -> donate for reuse + green credit",
        )
    return RoutingResult(
        disposition=Disposition.RECYCLE,
        reason="Not usable -> recycle for material recovery",
    )


def route_viable(grade: Grade, cat: CategoryData) -> RoutingResult:
    """Item is worth processing. Pick the disposition with the best net value.
    B and C share the SAME economic decision: refurbishing lifts the item toward
    like-new (recovery at grade-A level) for a refurb cost; we refurbish only when
    that nets more than selling as-is. This is what lets a Grade-C item whose
    defects are cheap to fix (clean + replace a worn glide pad) route to REFURBISH
    instead of being thrown away.
    """
    d = cat.avg_demand
    asis_ev = cat.avg_resale_price * _GRADE_RECOVERY[grade] * d

    if grade == Grade.A:
        return RoutingResult(disposition=Disposition.RESALE,
                             reason="Grade A -> resell as Certified Renewed",
                             expected_value=round(asis_ev, 2))
    if grade == Grade.D:
        return RoutingResult(disposition=Disposition.RECYCLE,
                             reason="Grade D -> recycle (not recoverable)")

    # B and C: refurbish-to-like-new vs resell-as-is, decided by EV.
    refurb_ev = cat.avg_resale_price * _GRADE_RECOVERY[Grade.A] * d - cat.refurb_cost
    if max(asis_ev, refurb_ev) <= 0:
        return RoutingResult(disposition=Disposition.DONATE,
                             reason=f"Grade {grade.value} -> recovery below cost; "
                                    f"donate for reuse + green credit")
    if refurb_ev > asis_ev:
        return RoutingResult(disposition=Disposition.REFURBISH,
                             reason=f"Grade {grade.value} -> refurbish "
                                    f"(EV Rs{refurb_ev:.0f} > as-is Rs{asis_ev:.0f})",
                             expected_value=round(refurb_ev, 2))
    return RoutingResult(disposition=Disposition.RESALE,
                         reason=f"Grade {grade.value} -> resell as-is "
                                f"(EV Rs{asis_ev:.0f} >= refurb Rs{refurb_ev:.0f})",
                         expected_value=round(asis_ev, 2))


# --------------------------------------------------------------------------- #
# 3. Listing + Health Card
# --------------------------------------------------------------------------- #
def generate_listing(rr: ReturnRequest, g: GradeResult, is_p2p: bool) -> dict:
    """Build the marketplace listing + Health Card.
    NOTE: title/description are templated stubs -> swap for an LLM later."""
    price = round(rr.original_price * _GRADE_PRICE[g.grade], 2)
    tag = "Peer Renewed" if is_p2p else "Certified Renewed"
    # >>> TODO: replace title/description with LLM-generated copy
    title = f"{rr.category.title()} — {tag} (Grade {g.grade.value})"
    description = (
        f"Verified Grade {g.grade.value} ({g.condition_score}/100). "
        f"Condition: {'; '.join(g.findings)}. "
        f"Returned reason: {rr.return_reason or 'n/a'}. Backed by buyer guarantee."
    )
    return dict(
        return_id=rr.id, sku=rr.sku, category=rr.category, title=title,
        description=description, grade=g.grade, health_score=g.condition_score,
        findings=g.findings, price=price, original_price=rr.original_price,
        warranty_days=_GRADE_WARRANTY[g.grade], is_p2p=is_p2p,
    )


# --------------------------------------------------------------------------- #
# 4. Green credits
# --------------------------------------------------------------------------- #
def award_credits(session: Session, user_id: str, action: str) -> GreenCredit:
    points = CREDITS.get(action, 0)
    credit = GreenCredit(user_id=user_id, points=points, reason=action)
    session.add(credit)
    return credit


# --------------------------------------------------------------------------- #
# helper: never crash if a category wasn't seeded
# --------------------------------------------------------------------------- #
def get_or_default_category(session: Session, category: str) -> CategoryData:
    cat = session.get(CategoryData, category)
    if cat is None:
        # sensible fallback so the pipeline still runs for unknown categories
        cat = CategoryData(category=category, avg_demand=0.5,
                            refurb_cost=50.0, avg_resale_price=300.0)
    return cat
