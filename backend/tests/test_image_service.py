import asyncio
from io import BytesIO
from PIL import Image
import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers
from app.services.image_service import validate_and_prepare_image


def make_upload(content, content_type="image/png"):
    return UploadFile(filename="label.png", file=BytesIO(content), headers=Headers({"content-type": content_type}))


def png_bytes():
    output = BytesIO()
    Image.new("RGB", (20, 20), "white").save(output, format="PNG")
    return output.getvalue()


def test_valid_image_is_normalized_to_oriented_jpeg():
    image_bytes, mime = asyncio.run(validate_and_prepare_image(make_upload(png_bytes()), 1))
    assert mime == "image/jpeg"
    assert Image.open(BytesIO(image_bytes)).format == "JPEG"


def test_rejects_unsupported_mime_and_corrupt_content():
    with pytest.raises(HTTPException) as unsupported:
        asyncio.run(validate_and_prepare_image(make_upload(b"file", "image/svg+xml"), 1))
    assert unsupported.value.status_code == 415
    with pytest.raises(HTTPException) as corrupt:
        asyncio.run(validate_and_prepare_image(make_upload(b"not an image"), 1))
    assert corrupt.value.status_code == 400


def test_rejects_file_over_configured_limit():
    with pytest.raises(HTTPException) as oversized:
        asyncio.run(validate_and_prepare_image(make_upload(b"x" * (1024 * 1024 + 1)), 1))
    assert oversized.value.status_code == 413
