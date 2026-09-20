from io import BytesIO
import hashlib
import logging
import os
from typing import Annotated

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image

from app.models import (
    ErrorResponse,
    HealthResponse,
    RootResponse,
    TournamentPosterExtraction,
)
from app.services.gemini_service import GeminiServiceException, gemini_service

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("tournament_api")

# Configuration
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
DEBUG_UPLOAD = os.getenv("DEBUG_UPLOAD", "false").strip().lower() in ("1", "true", "yes")

SUPPORTED_MIME_TYPES: set[str] = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}

SUPPORTED_EXTENSIONS: set[str] = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}


def detect_image_format_and_mime(image_bytes: bytes) -> tuple[str | None, str | None]:
    """
    Detect the actual image format and standard MIME type from raw file signatures and contents.
    Supported formats: JPEG, PNG, WEBP.
    Returns (detected_format, detected_mime) e.g. ('JPEG', 'image/jpeg') or (None, None).
    """
    if not image_bytes or len(image_bytes) < 12:
        return None, None

    # Fast check via magic bytes / file signatures
    # JPEG: starts with FF D8 FF
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "JPEG", "image/jpeg"

    # PNG: starts with 89 50 4E 47 0D 0A 1A 0A
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG", "image/png"

    # WEBP: starts with 'RIFF' and bytes 8..12 are 'WEBP'
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return "WEBP", "image/webp"

    # Fallback verification via Pillow
    try:
        with Image.open(BytesIO(image_bytes)) as img:
            fmt = (img.format or "").upper()
            if fmt in ("JPEG", "JPG"):
                return "JPEG", "image/jpeg"
            elif fmt == "PNG":
                return "PNG", "image/png"
            elif fmt == "WEBP":
                return "WEBP", "image/webp"
    except Exception:
        pass

    return None, None


# FastAPI App initialization
app = FastAPI(
    title="Tournament Poster Extraction API",
    description="Production-ready REST API that extracts structured tournament and sports-event information from poster images using Google Gemini Vision AI.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Configuration
allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "*")
allowed_origins = (
    ["*"]
    if allowed_origins_raw.strip() == "*"
    else [origin.strip() for origin in allowed_origins_raw.split(",") if origin.strip()]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception Handlers
@app.exception_handler(GeminiServiceException)
async def gemini_service_exception_handler(
    request: Request, exc: GeminiServiceException
):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message, "detail": exc.detail},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    error_title = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        413: "Payload Too Large",
        415: "Unsupported Media Type",
        422: "Unprocessable Entity",
        500: "Internal Server Error",
        502: "Bad Gateway",
        503: "Service Unavailable",
    }.get(exc.status_code, "Error")

    return JSONResponse(
        status_code=exc.status_code,
        content={"error": error_title, "detail": detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    first_error = errors[0] if errors else {}
    msg = first_error.get("msg", "Invalid request parameters")
    loc = " -> ".join(str(l) for l in first_error.get("loc", []))
    detail = f"{loc}: {msg}" if loc else msg

    return JSONResponse(
        status_code=422,
        content={"error": "Validation Error", "detail": detail},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled server exception occurred")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "detail": "An unexpected error occurred while processing your request.",
        },
    )


# API Endpoints
@app.get(
    "/",
    response_model=RootResponse,
    summary="Root API Info",
    tags=["General"],
)
async def root():
    """Returns basic API name and running status."""
    return {"message": "Tournament Poster Extraction API", "status": "running"}


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    tags=["General"],
)
async def health_check():
    """Health check endpoint to verify that service is operational."""
    return {"status": "healthy"}


@app.post(
    "/extract",
    response_model=TournamentPosterExtraction,
    responses={
        200: {
            "description": "Structured tournament information extracted from poster",
            "model": TournamentPosterExtraction,
        },
        400: {"description": "Invalid or empty image file", "model": ErrorResponse},
        413: {"description": "Image file too large", "model": ErrorResponse},
        415: {"description": "Unsupported image format", "model": ErrorResponse},
        422: {"description": "Corrupt or unprocessable image", "model": ErrorResponse},
        500: {
            "description": "Internal server or API configuration error",
            "model": ErrorResponse,
        },
        502: {
            "description": "Gemini upstream communication error",
            "model": ErrorResponse,
        },
    },
    summary="Extract Structured Data from Tournament Poster",
    tags=["Extraction"],
)
async def extract_tournament_poster(
    poster: Annotated[
        UploadFile,
        File(description="Poster image file in JPEG, JPG, PNG, or WEBP format."),
    ],
):
    """
    Extract comprehensive structured tournament details from an uploaded poster image.

    - **poster**: Image file upload (JPEG, PNG, WEBP, up to max configured MB).
    - Returns structured JSON adhering to the tournament information schema.
    """
    # 1. Read file content and validate size
    try:
        image_bytes = await poster.read()
    except Exception as e:
        logger.error("Failed to read uploaded file: %s", str(e))
        raise HTTPException(
            status_code=400,
            detail="Failed to read the uploaded image file.",
        ) from e

    # 2. Validate non-empty file
    if not image_bytes or len(image_bytes) == 0:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty. Please upload a valid image file.",
        )

    # 3. Validate max file size
    if len(image_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Image file exceeds maximum allowable size of {MAX_FILE_SIZE_MB}MB.",
        )

    # 4. Extract metadata and detect actual format from bytes
    client_content_type = poster.content_type if poster.content_type else ""
    filename = poster.filename if poster.filename else ""
    file_ext = os.path.splitext(filename.lower())[1] if filename else ""

    detected_format, detected_mime = detect_image_format_and_mime(image_bytes)
    sha256_hash = hashlib.sha256(image_bytes).hexdigest()

    # Pillow inspection
    pillow_valid = False
    width = None
    height = None
    pillow_format = None

    try:
        with Image.open(BytesIO(image_bytes)) as img:
            pillow_valid = True
            width = img.width
            height = img.height
            pillow_format = img.format
    except Exception:
        pass

    # 5. Diagnostic logging ONLY (do not expose in API response or log sensitive data)
    logger.info(
        "UPLOAD DEBUG:\n"
        "filename=%s\n"
        "client_content_type=%s\n"
        "size=%d\n"
        "sha256=%s\n"
        "detected_format=%s\n"
        "detected_mime=%s\n"
        "pillow_valid=%s\n"
        "width=%s\n"
        "height=%s\n"
        "pillow_format=%s\n"
        "gemini_mime=%s\n"
        "gemini_bytes=%d",
        filename,
        client_content_type,
        len(image_bytes),
        sha256_hash,
        detected_format,
        detected_mime,
        "true" if pillow_valid else "false",
        width,
        height,
        pillow_format,
        detected_mime,
        len(image_bytes),
    )

    debug_payload = {
        "filename": filename,
        "client_content_type": client_content_type,
        "size": len(image_bytes),
        "sha256": sha256_hash,
        "detected_format": detected_format,
        "detected_mime": detected_mime,
        "pillow_valid": pillow_valid,
        "width": width,
        "height": height,
        "pillow_format": pillow_format,
        "gemini_mime": detected_mime,
        "gemini_bytes": len(image_bytes),
    }

    # 6. Validate detected image format
    if not detected_format or not detected_mime:
        # Check if client uploaded an explicitly unsupported non-image extension/mime (e.g. .txt, text/plain)
        if (file_ext and file_ext not in SUPPORTED_EXTENSIONS) or (
            client_content_type
            and not client_content_type.startswith("image/")
            and client_content_type not in SUPPORTED_MIME_TYPES
        ):
            raise HTTPException(
                status_code=415,
                detail="Unsupported image format. Only JPEG, JPG, PNG, and WEBP images are supported.",
            )
        # Corrupted or unsupported image bytes
        raise HTTPException(
            status_code=422,
            detail="The uploaded file is corrupt or not a supported image format (JPEG, PNG, WEBP).",
        )

    # 7. Extract structured data via Gemini Service using detected MIME type and original bytes
    extraction_result = await gemini_service.extract_tournament_from_image(
        image_bytes=image_bytes,
        mime_type=detected_mime,
    )

    if DEBUG_UPLOAD:
        data = extraction_result.model_dump()
        data["debug"] = debug_payload
        return JSONResponse(status_code=200, content=data)

    return extraction_result
