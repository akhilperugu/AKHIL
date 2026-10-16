from io import BytesIO
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError
from fastapi import HTTPException, UploadFile

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
EXPECTED_FORMATS = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}


async def validate_and_prepare_image(upload: UploadFile, max_upload_mb: int) -> tuple[bytes, str]:
    if upload.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG, or WebP image.")
    raw = await upload.read(max_upload_mb * 1024 * 1024 + 1)
    if not raw:
        raise HTTPException(status_code=400, detail="The uploaded image is empty.")
    if len(raw) > max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Image exceeds the {max_upload_mb} MB upload limit.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(BytesIO(raw))
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                raise HTTPException(status_code=415, detail="The file contents are not a supported image format.")
            if image.format != EXPECTED_FORMATS[upload.content_type]:
                raise HTTPException(status_code=415, detail="The file content does not match its declared image type.")
            image.verify()
            image = Image.open(BytesIO(raw))
            image = ImageOps.exif_transpose(image).convert("RGB")
            output = BytesIO()
            image.save(output, format="JPEG", quality=92, optimize=True)
            return output.getvalue(), "image/jpeg"
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(status_code=400, detail="The image is corrupt or could not be safely decoded.") from None
