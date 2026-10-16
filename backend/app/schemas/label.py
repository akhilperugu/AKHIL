from enum import StrEnum
from pydantic import BaseModel, Field


class DataStatus(StrEnum):
    VISIBLE = "visible"
    PARTIALLY_READABLE = "partially_readable"
    UNREADABLE = "unreadable"
    NOT_FOUND_IN_IMAGE = "not_found_in_image"
    UNKNOWN = "unknown"


class ImageQuality(StrEnum):
    CLEAR = "clear"
    LIMITED = "limited"
    UNREADABLE = "unreadable"
    UNKNOWN = "unknown"


class ImageIssue(StrEnum):
    BLURRY = "blurry"
    PARTIALLY_OBSCURED = "partially_obscured"
    CURVED_SURFACE = "curved_surface"
    GLARE = "glare"
    LOW_RESOLUTION = "low_resolution"
    CROPPED = "cropped"
    LOW_CONTRAST = "low_contrast"
    PERSPECTIVE_DISTORTION = "perspective_distortion"
    OTHER = "other"


class LabelField(BaseModel):
    value: str | None = None
    source_text: str | None = None
    status: DataStatus = DataStatus.UNKNOWN
    confidence: float | None = Field(default=None, ge=0, le=1)


class Ingredient(BaseModel):
    name: str
    source_text: str
    normalized_name: str | None = None
    status: DataStatus = DataStatus.VISIBLE
    confidence: float | None = Field(default=None, ge=0, le=1)


class NutritionFact(BaseModel):
    nutrient: str
    value: float | None = None
    unit: str | None = None
    basis: str | None = None
    source_text: str | None = None
    status: DataStatus = DataStatus.UNKNOWN


class LabelData(BaseModel):
    image_quality: ImageQuality = ImageQuality.UNKNOWN
    image_issues: list[ImageIssue] = Field(default_factory=list)
    product_name: LabelField = Field(default_factory=LabelField)
    ingredients: list[Ingredient] = Field(default_factory=list)
    ingredients_status: DataStatus = DataStatus.UNKNOWN
    allergen_statement: LabelField = Field(default_factory=LabelField)
    nutrition: list[NutritionFact] = Field(default_factory=list)
    serving_size: LabelField = Field(default_factory=LabelField)
    dietary_claims: list[LabelField] = Field(default_factory=list)
    certifications: list[LabelField] = Field(default_factory=list)
    other_visible_text: list[str] = Field(default_factory=list)
    unreadable_regions: list[str] = Field(default_factory=list)
    extraction_warnings: list[str] = Field(default_factory=list)
    full_text: str = ""
