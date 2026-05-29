"""File routes — upload, download, parse."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from starlette import status

from app.api.v1.deps import get_current_user_id, get_file_service, rate_limit
from app.schemas.file import FileResponse, FileUploadResponse
from app.services.file_service import FileService

router = APIRouter(prefix="/files", tags=["files"], dependencies=[Depends(rate_limit)])


@router.post("/upload", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    user_id: uuid.UUID = Depends(get_current_user_id),
    file_service: FileService = Depends(get_file_service),
):
    content = await file.read()
    record = await file_service.upload(user_id, file.filename or "unknown", content, file.content_type or "application/octet-stream")
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
