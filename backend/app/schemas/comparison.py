from enum import StrEnum
from pydantic import BaseModel, Field


class FindingStatus(StrEnum):
    CONFLICT_DETECTED = "conflict_detected"
    POTENTIAL_CONFLICT = "potential_conflict"
    NO_CONFLICT_FOUND = "no_conflict_found"
    UNKNOWN = "unknown"
    INSUFFICIENT_INFORMATION = "insufficient_information"


class Severity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class ReasoningType(StrEnum):
    DIRECT_MATCH = "direct_match"
    SYNONYM_MATCH = "synonym_match"
    NUTRITION_THRESHOLD = "nutrition_threshold"
    CONTEXTUAL_INTERPRETATION = "contextual_interpretation"
    CERTIFICATION_EVIDENCE = "certification_evidence"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class ThresholdDirection(StrEnum):
    MAXIMUM = "maximum"
    MINIMUM = "minimum"


class Evidence(BaseModel):
    source_text: str
    field: str
    explanation: str


class Finding(BaseModel):
    preference: str
    status: FindingStatus
    severity: Severity
    summary: str
    evidence: list[Evidence] = Field(default_factory=list)
    reasoning_type: ReasoningType
    uncertainty: str | None = None


class NutrientThreshold(BaseModel):
    nutrient: str
    direction: ThresholdDirection
    value: float = Field(ge=0)
    unit: str
    basis: str = "per serving"


class DietaryProfile(BaseModel):
    allergens: list[str] = Field(default_factory=list)
    avoid_ingredients: list[str] = Field(default_factory=list)
    dietary_patterns: list[str] = Field(default_factory=list)
    nutrition_thresholds: list[NutrientThreshold] = Field(default_factory=list)
    avoid_palm_oil: bool = False
    avoid_artificial_sweeteners: bool = False
    custom_requirements: list[str] = Field(default_factory=list)


class CompareRequest(BaseModel):
    label: "LabelData"
    profile: DietaryProfile


from app.schemas.label import LabelData
CompareRequest.model_rebuild()
