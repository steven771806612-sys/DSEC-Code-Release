"""S3 attachment service."""
import uuid
from uuid import UUID
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError, ForbiddenError
from app.models.case import Attachment, Case, CaseStatusEnum
from app.models.user import User, RoleEnum
from app.schemas.case import AttachmentUploadRequest


def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
    )


class AttachmentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_upload_url(
        self, case_id: UUID, payload: AttachmentUploadRequest, actor: User
    ) -> tuple[Attachment, str]:
        """Create an attachment record + return a presigned S3 PUT URL."""
        # Verify case exists and is editable
        result = await self.db.execute(select(Case).where(Case.id == case_id))
        case = result.scalar_one_or_none()
        if not case:
            raise NotFoundError("Case", str(case_id))
        if case.status != CaseStatusEnum.DRAFT:
            raise ForbiddenError("Attachments can only be uploaded to DRAFT cases")

        s3_key = f"cases/{case_id}/{uuid.uuid4()}/{payload.file_name}"

        attachment = Attachment(
            case_id=case_id,
            case_version_id=case.current_version_id or uuid.uuid4(),
            file_name=payload.file_name,
            file_type=payload.file_type,
            s3_key=s3_key,
            file_size_bytes=payload.file_size_bytes,
            uploaded_by=actor.id,
            is_primary=payload.is_primary,
        )
        self.db.add(attachment)
        await self.db.flush()

        s3 = _get_s3_client()
        presigned_url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.S3_BUCKET,
                "Key": s3_key,
                "ContentType": payload.file_type,
            },
            ExpiresIn=settings.S3_PRESIGN_EXPIRE_SECONDS,
        )
        return attachment, presigned_url

    async def get_download_url(
        self, case_id: UUID, attachment_id: UUID, actor: User
    ) -> str:
        result = await self.db.execute(
            select(Attachment).where(
                Attachment.id == attachment_id,
                Attachment.case_id == case_id,
            )
        )
        attachment = result.scalar_one_or_none()
        if not attachment:
            raise NotFoundError("Attachment", str(attachment_id))

        # RBAC: agent can only access own org's attachments
        case_result = await self.db.execute(
            select(Case).where(Case.id == case_id)
        )
        case = case_result.scalar_one_or_none()
        if (
            actor.role == RoleEnum.AGENT
            and case
            and case.org_id != actor.org_id
        ):
            raise ForbiddenError("Access denied")

        s3 = _get_s3_client()
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET, "Key": attachment.s3_key},
            ExpiresIn=settings.S3_PRESIGN_EXPIRE_SECONDS,
        )
        return url

    async def delete_attachment(
        self, case_id: UUID, attachment_id: UUID, actor: User
    ) -> None:
        result = await self.db.execute(
            select(Attachment).where(
                Attachment.id == attachment_id,
                Attachment.case_id == case_id,
            )
        )
        attachment = result.scalar_one_or_none()
        if not attachment:
            raise NotFoundError("Attachment", str(attachment_id))

        # Delete from S3
        try:
            s3 = _get_s3_client()
            s3.delete_object(Bucket=settings.S3_BUCKET, Key=attachment.s3_key)
        except ClientError:
            pass  # Log but don't fail

        await self.db.delete(attachment)
