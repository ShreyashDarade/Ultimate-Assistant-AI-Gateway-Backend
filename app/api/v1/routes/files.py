"""File routes — upload, download, parse with proper validation.

Supports uploading documents (PDF, DOCX, TXT, CSV, JSON, Markdown)
and images/audio files. Files are stored in S3/MinIO and optionally
parsed for text extraction.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from starlette import status

from app.api.v1.deps import get_current_user_id, get_file_service, rate_limit
from app.schemas.file import FileResponse, FileUploadResponse
from app.services.file_service import FileService

router = APIRouter(prefix="/files", tags=["files"], dependencies=[Depends(rate_limit)])

# ── Limits ───────────────────────────────────────────

MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024  # 50 MB

ALLOWED_MIME_TYPES = {
    # Documents
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "text/plain",
    "text/csv",
    "text/markdown",
    "application/json",
    "text/html",
    "application/xml",
    "text/xml",
    # Images
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/gif",
    "image/webp",
    "image/svg+xml",
    "image/bmp",
    "image/tiff",
    # Audio
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/webm",
    "audio/ogg",
    "audio/flac",
    "audio/mp4",
    "audio/x-m4a",
    # Video
    "video/mp4",
    "video/webm",
    "video/quicktime",
    # Archives & data
    "application/zip",
    "application/x-tar",
    "application/gzip",
}

# Extension-based fallback for common files
ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".txt", ".csv", ".md", ".json", ".html", ".xml",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".tiff",
    ".mp3", ".wav", ".webm", ".ogg", ".flac", ".m4a", ".opus",
    ".mp4", ".mov",
    ".zip", ".tar", ".gz",
}


@router.post("/upload", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(..., description="File to upload"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    file_service: FileService = Depends(get_file_service),
):
    """Upload a file to the gateway.

    Max file size: 50 MB.
    Supported formats:
      - Documents: PDF, DOCX, TXT, CSV, Markdown, JSON, HTML, XML
      - Images: PNG, JPEG, GIF, WebP, SVG, BMP, TIFF
      - Audio: MP3, WAV, WebM, OGG, FLAC, M4A, Opus
      - Video: MP4, WebM, MOV
      - Archives: ZIP, TAR, GZ

    Documents (PDF, DOCX, TXT) are auto-parsed for text extraction.
    """
    content_type = file.content_type or "application/octet-stream"
    filename = file.filename or "unknown"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    # Validate content type or extension
    if content_type not in ALLOWED_MIME_TYPES and ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Unsupported file type: {content_type} ({ext or 'no extension'}). "
            f"See API docs for supported formats.",
        )

    # Read and validate size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"File exceeds max size of {MAX_FILE_SIZE_MB} MB "
            f"(received {len(content) / 1024 / 1024:.1f} MB)",
        )

    if len(content) == 0:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "File is empty.",
        )

    record = await file_service.upload(user_id, filename, content, content_type)
    return FileUploadResponse(
        id=str(record.id),
        filename=record.filename,
        mime_type=record.mime_type,
        size_bytes=record.size_bytes,
    )


@router.get("/{file_id}", response_model=FileResponse)
async def get_file(
    file_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    file_service: FileService = Depends(get_file_service),
):
    """Get file metadata and download URL.

    Returns a pre-signed download URL valid for 1 hour.
    If the file is a document, `parsed_text` contains the extracted text.
    """
    record = await file_service.get_file(file_id, user_id)
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    download_url = await file_service.download_url(record)
    return FileResponse(
        id=str(record.id),
        filename=record.filename,
        mime_type=record.mime_type,
        size_bytes=record.size_bytes,
        download_url=download_url,
        parsed_text=record.parsed_text,
        created_at=str(record.created_at),
    )


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    file_service: FileService = Depends(get_file_service),
):
    """Delete a file from storage.

    Removes both the database record and the S3 object.
    """
    record = await file_service.get_file(file_id, user_id)
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    await file_service.delete(file_id, user_id)
