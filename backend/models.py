"""
models.py
---------
All data shapes in one place:
  - Enums      : the controlled vocabularies (grade, disposition, ...)
  - Tables     : SQLModel tables persisted in the DB
  - Results    : plain pydantic models passed BETWEEN pipeline stages
                 (not persisted; they are the 'contract' each stage returns)

Second Life Commerce — HackOn backend.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


# --------------------------------------------------------------------------- #
# Enums  (str-based so they serialise cleanly to JSON / DB)
# --------------------------------------------------------------------------- #
class Fulfillment(str, Enum):
    FBM = "FBM"   # merchant-fulfilled  -> item lives with the vendor
    FBA = "FBA"   # Amazon-fulfilled    -> item lives at an Amazon hub


class Grade(str, Enum):
    A = "A"   # like-new / unused
    B = "B"   # light wear, easily refurbished
    C = "C"   # usable but not resell-grade
    D = "D"   # broken / unsellable


class Disposition(str, Enum):
    RESALE = "RESALE"
    REFURBISH = "REFURBISH"
    P2P = "P2P"                      # local peer-to-peer second owner
    DONATE = "DONATE"
    RECYCLE = "RECYCLE"
    LIQUIDATE = "LIQUIDATE"
    RETURN_TO_VENDOR = "RETURN_TO_VENDOR"


class ReturnStatus(str, Enum):
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    GRADED = "GRADED"
    ROUTED = "ROUTED"
    LISTED = "LISTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ListingStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SOLD = "SOLD"


# --------------------------------------------------------------------------- #
# Tables
# --------------------------------------------------------------------------- #
class CategoryData(SQLModel, table=True):
    """Seeded reference data the rule engine reads (demand, costs)."""
    category: str = Field(primary_key=True)
    avg_demand: float = 0.5          # 0..1, how easily this category resells
    refurb_cost: float = 0.0         # cost to refurbish one unit
    avg_resale_price: float = 0.0    # typical renewed selling price


class ReturnRequest(SQLModel, table=True):
    """One return event flowing through the pipeline."""
    id: Optional[int] = Field(default=None, primary_key=True)
    sku: str
    category: str
    original_price: float
    user_id: str
    fulfillment: Fulfillment
    return_reason: Optional[str] = None
    image_paths: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    # filled in by the pipeline
    provisional_grade: Optional[Grade] = None
    provisional_score: Optional[int] = None
    confidence: Optional[float] = None
    findings: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    viable: Optional[bool] = None
    disposition: Optional[Disposition] = None
    reason: Optional[str] = None
    status: ReturnStatus = ReturnStatus.RECEIVED
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Listing(SQLModel, table=True):
    """A renewed / P2P item on the marketplace, with its Health Card fields."""
    id: Optional[int] = Field(default=None, primary_key=True)
    return_id: int = Field(foreign_key="returnrequest.id")
    sku: str
    category: str
    title: str
    description: str
    grade: Grade
    health_score: int
    findings: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    price: float
    original_price: float
    warranty_days: int = 0
    is_p2p: bool = False
    status: ListingStatus = ListingStatus.ACTIVE
    created_at: datetime = Field(default_factory=datetime.utcnow)


class GreenCredit(SQLModel, table=True):
    """Append-only green-credit ledger."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str
    points: int
    reason: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


# --------------------------------------------------------------------------- #
# Results  (passed between pipeline stages — the stage 'contracts')
# --------------------------------------------------------------------------- #
class GradeResult(BaseModel):
    grade: Grade
    condition_score: int          # 0..100
    findings: list[str]
    confidence: float             # 0..1


class ViabilityResult(BaseModel):
    viable: bool
    est_reverse_cost: float
    est_recovery: float
    reason: str


class RoutingResult(BaseModel):
    disposition: Disposition
    reason: str
    expected_value: Optional[float] = None
