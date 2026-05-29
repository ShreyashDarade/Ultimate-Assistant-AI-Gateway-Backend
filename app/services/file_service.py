"""File service — upload, download, parse via S3 + type-aware parsers."""

import uuid
from io import BytesIO

import aioboto3
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.repositories.conversation_repo import ConversationRepository
from app.models.file import File
from app.utils.ids import generate_uuid

logger = get_logger(__name__)


class FileService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self._s3_session = aioboto3.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )

    async def upload(
        self, user_id: uuid.UUID, filename: str, content: bytes, mime_type: str
    ) -> File:
        file_id = generate_uuid()
        storage_key = f"uploads/{user_id}/{file_id}/{filename}"

        # Upload to S3
        async with self._s3_session.client(
            "s3", endpoint_url=settings.S3_ENDPOINT_URL
        ) as s3:
            await s3.upload_fileobj(
                BytesIO(content),
                settings.S3_BUCKET,
                storage_key,
                ExtraArgs={"ContentType": mime_type},
            )

        # Parse text content if applicable
        parsed_text = await self._parse_file(content, mime_type)

        # Create DB record
        file_record = File(
            id=file_id,
            user_id=user_id,
            storage_key=storage_key,
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(content),
            parsed_text=parsed_text,
        )
        self.session.add(file_record)
        await self.session.flush()

        logger.info("file_uploaded", file_id=str(file_id), size=len(content), mime=mime_type)
        return file_record

    async def download_url(self, file_record: File) -> str:
        async with self._s3_session.client(
            "s3", endpoint_url=settings.S3_ENDPOINT_URL
        ) as s3:
            url = await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.S3_BUCKET, "Key": file_record.storage_key},
                ExpiresIn=3600,
            )
            return url

    async def get_file(self, file_id: uuid.UUID, user_id: uuid.UUID) -> File | None:
        from sqlalchemy import select
        result = await self.session.execute(
            select(File).where(File.id == file_id, File.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def _parse_file(self, content: bytes, mime_type: str) -> str | None:
        try:
            if mime_type == "application/pdf":
                from app.services.parsers.pdf import parse_pdf
                return parse_pdf(content)
            elif mime_type in (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/msword",
            ):
                from app.services.parsers.docx import parse_docx
                return parse_docx(content)
            elif mime_type.startswith("text/"):
                return content.decode("utf-8", errors="replace")
        except Exception as e:
            logger.warning("parse_failed", mime=mime_type, error=str(e))
        return None
