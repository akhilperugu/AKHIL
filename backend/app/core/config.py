import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    xai_api_key: str
    vision_model: str
    max_upload_mb: int
    frontend_origin: str
    requests_per_minute: int


def get_settings() -> Settings:
    return Settings(
        xai_api_key=os.getenv("XAI_API_KEY", "").strip(),
        vision_model=os.getenv("XAI_VISION_MODEL", "grok-4.7").strip(),
        max_upload_mb=max(1, int(os.getenv("MAX_UPLOAD_MB", "10"))),
        frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").strip(),
        requests_per_minute=max(1, int(os.getenv("REQUESTS_PER_MINUTE", "12"))),
    )
