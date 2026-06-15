from __future__ import annotations

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel

from app.constants import (
    DemandLevel,
    FulfillmentType,
    Grade,
    InspectionStage,
    ListingType,
    PackagingCondition,
    ReturnCaseStatus,
    RoutingDecisionType,
    UsageLevel,
    VendorPermissionStatus,
    ViabilityLabel,
)


class ReturnCase(SQLModel, table=True):
    __tablename__ = "return_cases"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    product_name: str
    category: str
    original_price: float
    return_reason: str
    fulfillment_type: str
    demand_level: str
    reverse_logistics_cost: float
    inspection_cost: float
    repacking_cost: float
    refurb_cost: float = 0
    relisting_cost: float = 10
    status: str = Field(default=ReturnCaseStatus.CREATED, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow},
    )


class ReturnMedia(SQLModel, table=True):
    __tablename__ = "return_media"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    return_case_id: uuid.UUID = Field(foreign_key="return_cases.id", index=True)
    stage: str = Field(index=True)
    file_name: str
    object_key: str = Field(index=True)
    object_url: str
    content_type: str
    size_bytes: int
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AIAssessment(SQLModel, table=True):
    __tablename__ = "ai_assessments"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    return_case_id: uuid.UUID = Field(foreign_key="return_cases.id", index=True)
    stage: str = Field(index=True)
    grade: str
    product_health_score: int
    visible_damage: str
    packaging_condition: str
    usage_level: str
    missing_parts: bool
    confidence: float
    buyer_facing_summary: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ViabilityResultRecord(SQLModel, table=True):
    __tablename__ = "viability_results"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    return_case_id: uuid.UUID = Field(foreign_key="return_cases.id", index=True)
    stage: str = Field(index=True)
    expected_resale_price: float
    total_recovery_cost: float
    net_recovery_value: float
    viability_label: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RoutingDecisionRecord(SQLModel, table=True):
    __tablename__ = "routing_decisions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    return_case_id: uuid.UUID = Field(foreign_key="return_cases.id", index=True)
    stage: str = Field(index=True)
    decision: str
    reason: str
    requires_vendor_permission: bool
    vendor_permission_status: str
    green_credits_awarded: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ProductHealthCard(SQLModel, table=True):
    __tablename__ = "product_health_cards"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    return_case_id: uuid.UUID = Field(foreign_key="return_cases.id", index=True)
    stage: str = Field(index=True)
    public_grade: str
    health_score: int
    condition_summary: str
    trust_badge: str = "Amazon Prism Verified"
    recommended_route: str
    green_impact: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ListingPreview(SQLModel, table=True):
    __tablename__ = "listing_previews"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    return_case_id: uuid.UUID = Field(foreign_key="return_cases.id", index=True)
    stage: str = Field(index=True)
    title: str
    description: str
    condition_badge: str
    recommended_price: float
    listing_type: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
