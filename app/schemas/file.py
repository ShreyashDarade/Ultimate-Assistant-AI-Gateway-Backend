from pydantic import BaseModel


class FileResponse(BaseModel):
    id: str
    filename: str
    mime_type: str
    size_bytes: int
    download_url: str | None = None
    parsed_text: str | None = None
    created_at: str

    model_config = {"from_attributes": True}


class FileUploadResponse(BaseModel):
    id: str
    filename: str
    mime_type: str
    size_bytes: int
