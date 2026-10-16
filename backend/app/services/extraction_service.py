from app.schemas.label import LabelData
from app.services.normalization_service import normalize_label
from app.services.vision_provider import VisionProvider


class ExtractionService:
    def __init__(self, provider: VisionProvider | None = None):
        self.provider = provider or VisionProvider()

    def extract(self, image_bytes: bytes, mime_type: str) -> LabelData:
        return normalize_label(self.provider.extract(image_bytes, mime_type))
