"""
main.py
-------
FastAPI app. Run it:

    pip install -r requirements.txt
    uvicorn main:app --reload      # open http://127.0.0.1:8000/docs

SCALABLE FLOW (default):
    POST /returns         -> saves the return, returns instantly with a job id,
                             and grades/routes it IN THE BACKGROUND (non-blocking)
    GET  /returns/{id}    -> poll for status + result (Health Card, routing, listing)
    POST /returns?sync=1  -> process inline and return the full result in one call
                             (handy for demos/tests; not how you'd run at scale)

Why background: the vision grade takes ~seconds. Doing it inline would tie up a
worker per request and cap throughput at one GPU. Accepting fast + grading async
is the pattern that scales. `process_return` is queue-agnostic: swap FastAPI's
BackgroundTasks for Celery/RQ/SQS workers in production with no logic change.
"""
from __future__ import annotations

import logging
import os
import shutil
from collections import Counter
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import (BackgroundTasks, Depends, FastAPI, File, Form,
                     HTTPException, UploadFile)
from sqlmodel import Session, select

from database import engine, get_session, init_db
from grading import grade_item, needs_review
from models import (
    Disposition, Fulfillment, Grade, GradeResult, GreenCredit, Listing,
    ListingStatus, ReturnRequest, ReturnStatus,
)
from seed import seed
from services import (
    award_credits, generate_listing, get_or_default_category,
    route_non_viable, route_viable, viability_check,
)

log = logging.getLogger("api")
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed()
    yield


app = FastAPI(title="Second Life Commerce API", version="0.2.0", lifespan=lifespan)

_DONE = {ReturnStatus.LISTED, ReturnStatus.COMPLETED, ReturnStatus.FAILED}


# --------------------------------------------------------------------------- #
# The pipeline (pure-ish): grade -> viability -> route -> listing -> credits
# Used by BOTH the background worker and the sync path, so behaviour is identical.
# --------------------------------------------------------------------------- #
def _run_pipeline(rr: ReturnRequest, session: Session,
                  mock_grade: Optional[Grade] = None) -> None:
    rr.status = ReturnStatus.PROCESSING

    g: GradeResult = grade_item(rr.image_paths, rr.category,
                                mock_grade=mock_grade, video_path=rr.video_path)
    rr.provisional_grade, rr.provisional_score = g.grade, g.condition_score
    rr.confidence, rr.findings = g.confidence, g.findings
    rr.status = ReturnStatus.GRADED

    cat = get_or_default_category(session, rr.category)
    v = viability_check(rr.original_price, g.grade, cat)
    rr.viable = v.viable

    routing = route_viable(g.grade, cat) if v.viable else route_non_viable(g.grade)
    rr.disposition, rr.reason = routing.disposition, routing.reason
    rr.status = ReturnStatus.ROUTED
    session.add(rr); session.commit(); session.refresh(rr)

    # confidence-aware: too uncertain to auto-list -> leave for human review
    if needs_review(g) and routing.disposition in (Disposition.RESALE, Disposition.REFURBISH):
        rr.reason = f"{routing.reason} | LOW CONFIDENCE -> manual review"
        rr.status = ReturnStatus.COMPLETED
        session.add(rr); session.commit()
        return

    if routing.disposition in (Disposition.RESALE, Disposition.REFURBISH, Disposition.P2P):
        is_p2p = routing.disposition == Disposition.P2P
        session.add(Listing(**generate_listing(rr, g, is_p2p)))
        award_credits(session, rr.user_id, "p2p_list" if is_p2p else "return_to_resale")
        rr.status = ReturnStatus.LISTED
    else:
        if routing.disposition == Disposition.DONATE:
            award_credits(session, rr.user_id, "donate")
        rr.status = ReturnStatus.COMPLETED

    session.add(rr); session.commit()


def process_return(return_id: int, mock_grade: Optional[Grade] = None) -> None:
    """Background worker. Opens its OWN session (the request's is long gone)."""
    with Session(engine) as session:
        rr = session.get(ReturnRequest, return_id)
        if rr is None:
            return
        try:
            _run_pipeline(rr, session, mock_grade)
        except Exception as exc:                       # never lose a job silently
            log.exception("return %s failed", return_id)
            rr.status = ReturnStatus.FAILED
            rr.reason = f"processing error: {exc}"
            session.add(rr); session.commit()


def _status_view(rr: ReturnRequest, session: Session) -> dict:
    """Single source of truth for what a return looks like, in any state."""
    listing = session.exec(
        select(Listing).where(Listing.return_id == rr.id)
    ).first()
    health = None
    if rr.provisional_grade is not None:
        health = {"grade": rr.provisional_grade, "score": rr.provisional_score,
                  "findings": rr.findings, "confidence": rr.confidence}
    return {
        "return_id": rr.id,
        "status": rr.status,
        "done": rr.status in _DONE,
        "fulfillment": rr.fulfillment,
        "destination": "vendor warehouse" if rr.fulfillment == Fulfillment.FBM else "Amazon hub",
        "health_card": health,
        "viable": rr.viable,
        "disposition": rr.disposition,
        "reason": rr.reason,
        "listing_id": listing.id if listing else None,
    }


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
@app.post("/returns", tags=["pipeline"])
async def create_return(
    background: BackgroundTasks,
    sku: str = Form(...),
    category: str = Form(...),
    original_price: float = Form(...),
    user_id: str = Form(...),
    fulfillment: Fulfillment = Form(...),
    return_reason: Optional[str] = Form(None),
    mock_grade: Optional[Grade] = Form(None),
    sync: bool = Form(False),                  # sync=true -> full result in one call
    images: list[UploadFile] = File(default=[]),
    video: Optional[UploadFile] = File(default=None),
    session: Session = Depends(get_session),
):
    paths: list[str] = []
    for img in images:
        dest = os.path.join(UPLOAD_DIR, f"{sku}_{img.filename}")
        with open(dest, "wb") as f:
            shutil.copyfileobj(img.file, f)
        paths.append(dest)

    video_path = None
    if video is not None and video.filename:
        video_path = os.path.join(UPLOAD_DIR, f"{sku}_{video.filename}")
        with open(video_path, "wb") as f:
            shutil.copyfileobj(video.file, f)

    rr = ReturnRequest(
        sku=sku, category=category, original_price=original_price,
        user_id=user_id, fulfillment=fulfillment, return_reason=return_reason,
        image_paths=paths, video_path=video_path, status=ReturnStatus.RECEIVED,
    )
    session.add(rr); session.commit(); session.refresh(rr)

    if sync:                                   # process now, return everything
        _run_pipeline(rr, session, mock_grade)
        return _status_view(rr, session)

    # accept instantly; grade in the background
    background.add_task(process_return, rr.id, mock_grade)
    return {"return_id": rr.id, "status": "PROCESSING",
            "poll_url": f"/returns/{rr.id}"}


@app.get("/returns/{return_id}", tags=["pipeline"])
def get_return(return_id: int, session: Session = Depends(get_session)):
    rr = session.get(ReturnRequest, return_id)
    if rr is None:
        raise HTTPException(404, "Return not found")
    return _status_view(rr, session)


# --------------------------------------------------------------------------- #
# Marketplace + buyer
# --------------------------------------------------------------------------- #
@app.get("/listings", tags=["marketplace"])
def list_listings(session: Session = Depends(get_session)):
    return session.exec(select(Listing).where(Listing.status == ListingStatus.ACTIVE)).all()


@app.get("/listings/{listing_id}", tags=["marketplace"])
def get_listing(listing_id: int, session: Session = Depends(get_session)):
    listing = session.get(Listing, listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")
    return listing


@app.post("/listings/{listing_id}/buy", tags=["marketplace"])
def buy_listing(listing_id: int, buyer_id: str = Form(...),
                session: Session = Depends(get_session)):
    listing = session.get(Listing, listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")
    if listing.status == ListingStatus.SOLD:
        raise HTTPException(400, "Already sold")
    listing.status = ListingStatus.SOLD
    award_credits(session, buyer_id, "buy_renewed")
    session.add(listing); session.commit()
    return {"bought": listing_id, "price": listing.price, "buyer": buyer_id,
            "credits_awarded": True}


# --------------------------------------------------------------------------- #
# Green credits
# --------------------------------------------------------------------------- #
@app.get("/credits/{user_id}", tags=["credits"])
def get_credits(user_id: str, session: Session = Depends(get_session)):
    entries = session.exec(select(GreenCredit).where(GreenCredit.user_id == user_id)).all()
    return {"user_id": user_id, "total": sum(e.points for e in entries),
            "entries": entries}


# --------------------------------------------------------------------------- #
# Prevention (bonus)
# --------------------------------------------------------------------------- #
@app.get("/prevention", tags=["prevention"])
def prevention_nudge(category: str, session: Session = Depends(get_session)):
    rows = session.exec(select(ReturnRequest).where(ReturnRequest.category == category)).all()
    reasons = Counter(r.return_reason for r in rows if r.return_reason)
    if not reasons:
        return {"category": category, "nudge": None}
    top_reason, count = reasons.most_common(1)[0]
    share = count / sum(reasons.values())
    nudge = (f"{share:.0%} of returns for this category were '{top_reason}'. "
             "Consider this before buying.") if share >= 0.5 else None
    return {"category": category, "top_reason": top_reason,
            "share": round(share, 2), "nudge": nudge}
