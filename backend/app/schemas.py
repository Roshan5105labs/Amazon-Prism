from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

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


class ReturnCaseCreate(BaseModel):
    product_name: str
    category: str
    original_price: float = Field(ge=0)
    return_reason: str
    fulfillment_type: FulfillmentType
    demand_level: DemandLevel
    reverse_logistics_cost: float = Field(ge=0)
    inspection_cost: float = Field(ge=0)
    repacking_cost: float = Field(ge=0)
    refurb_cost: float = Field(default=0, ge=0)
    relisting_cost: float = Field(default=10, ge=0)


class ReturnCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_name: str
    category: str
    original_price: float
    return_reason: str
    fulfillment_type: FulfillmentType
    demand_level: DemandLevel
    reverse_logistics_cost: float
    inspection_cost: float
    repacking_cost: float
    refurb_cost: float
    relisting_cost: float
    status: ReturnCaseStatus
    created_at: datetime
    updated_at: datetime


class ReturnMediaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    return_case_id: uuid.UUID
    stage: InspectionStage
    file_name: str
    object_key: str
    object_url: str
    content_type: str
    size_bytes: int
    created_at: datetime


class AIAssessmentCreate(BaseModel):
    stage: InspectionStage
    grade: Grade
    product_health_score: int = Field(ge=0, le=100)
    visible_damage: str
    packaging_condition: PackagingCondition
    usage_level: UsageLevel
    missing_parts: bool
    confidence: float = Field(ge=0, le=1)
    buyer_facing_summary: str


class AIAssessmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    return_case_id: uuid.UUID
    stage: InspectionStage
    grade: Grade
    product_health_score: int
    visible_damage: str
    packaging_condition: PackagingCondition
    usage_level: UsageLevel
    missing_parts: bool
    confidence: float
    buyer_facing_summary: str
    created_at: datetime


class ViabilityResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    return_case_id: uuid.UUID
    stage: InspectionStage
    expected_resale_price: float
    total_recovery_cost: float
    net_recovery_value: float
    viability_label: ViabilityLabel
    created_at: datetime


class RoutingDecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    return_case_id: uuid.UUID
    stage: InspectionStage
    decision: RoutingDecisionType
    reason: str
    requires_vendor_permission: bool
    vendor_permission_status: VendorPermissionStatus
    green_credits_awarded: int = 0
    created_at: datetime


class ProductHealthCardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    return_case_id: uuid.UUID
    stage: InspectionStage
    public_grade: Grade
    health_score: int
    condition_summary: str
    trust_badge: str
    recommended_route: RoutingDecisionType
    green_impact: str
    created_at: datetime


class ListingPreviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    return_case_id: uuid.UUID
    stage: InspectionStage
    title: str
    description: str
    condition_badge: str
    recommended_price: float
    listing_type: ListingType
    created_at: datetime


class MediaUploadResponse(BaseModel):
    uploaded: list[ReturnMediaRead]
    return_case_status: ReturnCaseStatus


class FinalCheckResponse(BaseModel):
    message: str
    return_case: ReturnCaseRead
    uploaded_media: list[ReturnMediaRead] = Field(default_factory=list)


class VendorDecisionRequest(BaseModel):
    decision: VendorPermissionStatus


class VendorDecisionResponse(BaseModel):
    message: str
    return_case: ReturnCaseRead
    routing_decision: RoutingDecisionRead


class ReturnCaseWorkflowResponse(BaseModel):
    return_case: ReturnCaseRead
    ai_assessment: AIAssessmentRead
    viability: ViabilityResultRead
    routing_decision: RoutingDecisionRead
    health_card: ProductHealthCardRead
    listing_preview: ListingPreviewRead


class ReturnCaseSummaryResponse(BaseModel):
    return_case: ReturnCaseRead
    latest_health_card: Optional[ProductHealthCardRead] = None
    latest_routing_decision: Optional[RoutingDecisionRead] = None


class ReturnCaseDetailsResponse(BaseModel):
    return_case: ReturnCaseRead
    media: list[ReturnMediaRead] = Field(default_factory=list)
    ai_assessments: list[AIAssessmentRead] = Field(default_factory=list)
    viability_results: list[ViabilityResultRead] = Field(default_factory=list)
    routing_decisions: list[RoutingDecisionRead] = Field(default_factory=list)
    health_cards: list[ProductHealthCardRead] = Field(default_factory=list)
    listing_previews: list[ListingPreviewRead] = Field(default_factory=list)


class PreventionResponse(BaseModel):
    category: str
    top_reason: Optional[str] = None
    share: Optional[float] = None
    nudge: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    app_name: str


class CaseGreenCreditsResponse(BaseModel):
    return_case_id: uuid.UUID
    decision: Optional[RoutingDecisionType] = None
    green_credits_awarded: int = 0


class GreenCreditSummaryResponse(BaseModel):
    total_credits: int
    cases_counted: int
    credits_by_disposition: dict[str, int] = Field(default_factory=dict)


class RenewedRecommendation(BaseModel):
    listing_id: uuid.UUID
    return_case_id: uuid.UUID
    title: str
    grade: str
    price: float
    health_score: int


class RenewedRecommendationsResponse(BaseModel):
    category: str
    recommendations: list[RenewedRecommendation] = Field(default_factory=list)
