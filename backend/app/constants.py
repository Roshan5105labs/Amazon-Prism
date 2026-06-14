from __future__ import annotations

from enum import Enum


class FulfillmentType(str, Enum):
    FBA = "FBA"
    FBM = "FBM"


class DemandLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class InspectionStage(str, Enum):
    PRECHECK = "PRECHECK"
    FINAL_CHECK = "FINAL_CHECK"


class ReturnCaseStatus(str, Enum):
    CREATED = "CREATED"
    AI_PENDING = "AI_PENDING"
    AI_ASSESSED = "AI_ASSESSED"
    ROUTED = "ROUTED"
    PRECHECK_PENDING = "AI_PENDING"
    FINAL_CHECK_PENDING = "FINAL_CHECK_PENDING"
    FINAL_CHECK_DONE = "FINAL_CHECK_DONE"
    AWAITING_FINAL_CHECK = "FINAL_CHECK_PENDING"
    VENDOR_PERMISSION_PENDING = "VENDOR_PERMISSION_PENDING"
    VENDOR_DECISION_PENDING = "VENDOR_PERMISSION_PENDING"
    VENDOR_REJECTED = "VENDOR_REJECTED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    COMPLETED = "COMPLETED"


class Grade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class ViabilityLabel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NEGATIVE = "NEGATIVE"


class RoutingDecisionType(str, Enum):
    SEND_TO_VENDOR_OR_WAREHOUSE = "SEND_TO_VENDOR_OR_WAREHOUSE"
    RESELL = "RESELL"
    BUNDLE_RESALE = "BUNDLE_RESALE"
    REFURBISH = "REFURBISH"
    DONATE = "DONATE"
    RECYCLE = "RECYCLE"
    LIQUIDATE = "LIQUIDATE"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class VendorPermissionStatus(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ListingType(str, Enum):
    INDIVIDUAL_RESALE = "INDIVIDUAL_RESALE"
    BUNDLE_RESALE = "BUNDLE_RESALE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class PackagingCondition(str, Enum):
    SEALED = "SEALED"
    GOOD = "GOOD"
    WORN = "WORN"
    DAMAGED = "DAMAGED"
    MISSING = "MISSING"


class UsageLevel(str, Enum):
    UNUSED = "UNUSED"
    LIGHT = "LIGHT"
    MODERATE = "MODERATE"
    HEAVY = "HEAVY"
    UNKNOWN = "UNKNOWN"


DEMAND_MULTIPLIER = {
    DemandLevel.LOW: 0.55,
    DemandLevel.MEDIUM: 0.75,
    DemandLevel.HIGH: 0.92,
}

GRADE_PRICE_FACTOR = {
    Grade.A: 0.88,
    Grade.B: 0.72,
    Grade.C: 0.52,
    Grade.D: 0.18,
}

GRADE_BUNDLE_FACTOR = {
    Grade.A: 0.62,
    Grade.B: 0.48,
    Grade.C: 0.30,
    Grade.D: 0.08,
}

MANUAL_REVIEW_CONFIDENCE_THRESHOLD = 0.65
TRUST_BADGE_DEFAULT = "Amazon Prism Verified"

ALL_FULFILLMENT_TYPES = tuple(item.value for item in FulfillmentType)
ALL_DEMAND_LEVELS = tuple(item.value for item in DemandLevel)
ALL_INSPECTION_STAGES = tuple(item.value for item in InspectionStage)
ALL_RETURN_CASE_STATUSES = tuple(item.value for item in ReturnCaseStatus)
ALL_GRADES = tuple(item.value for item in Grade)
ALL_VIABILITY_LABELS = tuple(item.value for item in ViabilityLabel)
ALL_ROUTING_DECISIONS = tuple(item.value for item in RoutingDecisionType)
ALL_VENDOR_PERMISSION_STATUSES = tuple(item.value for item in VendorPermissionStatus)
ALL_LISTING_TYPES = tuple(item.value for item in ListingType)
ALL_PACKAGING_CONDITIONS = tuple(item.value for item in PackagingCondition)
ALL_USAGE_LEVELS = tuple(item.value for item in UsageLevel)
