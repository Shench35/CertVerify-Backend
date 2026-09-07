from io import BytesIO

import fitz
from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 20
MAX_IMAGE_WIDTH = 10_000
MAX_IMAGE_HEIGHT = 10_000
MAX_IMAGE_PIXELS = 50_000_000

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
    "application/pdf": b"%PDF-",
}


def _invalid_upload(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=detail,
    )


def _validate_image(file_bytes: bytes) -> None:
    try:
        with Image.open(BytesIO(file_bytes)) as image:
            width, height = image.size
            if (
                width > MAX_IMAGE_WIDTH
                or height > MAX_IMAGE_HEIGHT
                or width * height > MAX_IMAGE_PIXELS
            ):
                raise _invalid_upload("Image dimensions exceed the allowed limits.")
            image.verify()
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise _invalid_upload("The uploaded image is invalid or corrupted.") from exc


def _validate_pdf(file_bytes: bytes) -> None:
    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as document:
            if document.page_count > MAX_PDF_PAGES:
                raise _invalid_upload("PDF page count exceeds the allowed limit.")
    except HTTPException:
        raise
    except (fitz.FileDataError, RuntimeError, ValueError) as exc:
        raise _invalid_upload("The uploaded PDF is invalid or corrupted.") from exc


async def read_and_validate_upload(file: UploadFile) -> bytes:
    """Read a bounded upload and validate its declared and detected content."""
    content_type = file.content_type
    expected_signature = ALLOWED_CONTENT_TYPES.get(content_type)
    if expected_signature is None:
        raise _invalid_upload(
            "Invalid file format. Only JPEG, PNG, and PDF are supported."
        )

    file_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise _invalid_upload("File exceeds the 10 MB size limit.")
    if not file_bytes.startswith(expected_signature):
        raise _invalid_upload("File content does not match its declared format.")

    if content_type.startswith("image/"):
        _validate_image(file_bytes)
    else:
        _validate_pdf(file_bytes)

    return file_bytes
