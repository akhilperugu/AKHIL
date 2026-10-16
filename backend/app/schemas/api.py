from pydantic import BaseModel, Field
from app.schemas.comparison import DietaryProfile, Finding
from app.schemas.label import LabelData


class AnalysisResponse(BaseModel):
    label: LabelData
    findings: list[Finding] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    provider_configured: bool
    max_upload_mb: int
