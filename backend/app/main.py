from collections import defaultdict, deque
from time import monotonic
import json
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from app.core.config import get_settings
from app.schemas.api import AnalysisResponse, HealthResponse
from app.schemas.comparison import CompareRequest, DietaryProfile
from app.core.security import client_identifier, reject_oversized_content_length
from app.services.comparison_engine import compare_label
from app.services.extraction_service import ExtractionService
from app.services.image_service import validate_and_prepare_image
from app.services.normalization_service import normalize_label
from app.services.vision_provider import ProviderAnalysisError, ProviderConfigurationError

settings = get_settings()
app = FastAPI(title="LabelLens AI", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin], allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
_request_times: dict[str, deque[float]] = defaultdict(deque)


@app.middleware("http")
async def simple_rate_limit(request: Request, call_next):
    if request.url.path == "/api/analyze-label":
        now = monotonic()
        visits = _request_times[client_identifier(request)]
        while visits and now - visits[0] > 60:
            visits.popleft()
        if len(visits) >= settings.requests_per_minute:
            return JSONResponse(status_code=429, content={"detail": "Too many analysis requests. Please wait a minute and try again."})
        visits.append(now)
    return await call_next(request)


@app.get("/api/health", response_model=HealthResponse)
def health():
    configured = bool(settings.openai_api_key and settings.vision_model)
    return HealthResponse(status="ready" if configured else "configuration_required", provider_configured=configured, max_upload_mb=settings.max_upload_mb)


@app.post("/api/analyze-label", response_model=AnalysisResponse)
async def analyze_label(request: Request, image: UploadFile = File(...), profile: str = Form("{}")):
    reject_oversized_content_length(request, settings.max_upload_mb * 1024 * 1024)
    try:
        dietary_profile = DietaryProfile.model_validate(json.loads(profile))
    except (json.JSONDecodeError, ValidationError):
        raise HTTPException(status_code=422, detail="Dietary profile is not valid JSON or does not match the expected format.") from None
    prepared, mime_type = await validate_and_prepare_image(image, settings.max_upload_mb)
    try:
        label = ExtractionService().extract(prepared, mime_type)
    except ProviderConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    except ProviderAnalysisError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    findings = compare_label(label, dietary_profile)
    return AnalysisResponse(label=label, findings=findings, warnings=label.extraction_warnings)


@app.post("/api/compare", response_model=AnalysisResponse)
def compare(request: CompareRequest):
    label = normalize_label(request.label)
    return AnalysisResponse(label=label, findings=compare_label(label, request.profile), warnings=label.extraction_warnings)


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    return JSONResponse(status_code=422, content={"detail": "Structured label data did not pass validation."})
