"""Main FastAPI application module for Tournament Poster Extraction API."""

import logging
import os
from typing import Annotated

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
    # 1. Validate MIME type and file extension
    content_type = poster.content_type.lower() if poster.content_type else ""
    filename = poster.filename.lower() if poster.filename else ""
    file_ext = os.path.splitext(filename)[1] if filename else ""

    is_supported_mime = content_type in SUPPORTED_MIME_TYPES
    is_supported_ext = file_ext in SUPPORTED_EXTENSIONS

    if not is_supported_mime and not is_supported_ext:
        raise HTTPException(
            status_code=415,
            detail="Unsupported image format. Only JPEG, JPG, PNG, and WEBP images are supported.",
        )

    # Normalize MIME type for Gemini if content_type was generic or missing
    if not is_supported_mime:
        mime_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }
        content_type = mime_map.get(file_ext, "image/jpeg")

    # 2. Read file content and validate size
    try:
        image_bytes = await poster.read()
    except Exception as e:
        logger.error("Failed to read uploaded file: %s", str(e))
        raise HTTPException(
            status_code=400,
            detail="Failed to read the uploaded image file.",
        ) from e

    # 3. Validate non-empty file
    if not image_bytes or len(image_bytes) == 0:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty. Please upload a valid image file.",
        )

    # 4. Validate max file size
    if len(image_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Image file exceeds maximum allowable size of {MAX_FILE_SIZE_MB}MB.",
        )

    # 5. Extract structured data via Gemini Service
    extraction_result = await gemini_service.extract_tournament_from_image(
        image_bytes=image_bytes,
        mime_type=content_type,
    )

    return extraction_result
