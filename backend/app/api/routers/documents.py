import hashlib
import uuid
from pathlib import Path

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import Select, delete, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user, get_user_scoped_session
from backend.app.core.config import get_settings
from backend.app.db.models import Chunk, Document, DocumentGrant, DocumentVersion, Membership, User
from backend.app.ingestion.virus_scan import get_scanner

router = APIRouter(prefix="/documents", tags=["documents"])
UPLOAD_DIR = Path("/data/uploads")
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".md", ".markdown", ".html", ".htm", ".txt"}
ALLOWED_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/markdown",
    "text/html",
    "text/plain",
    "application/octet-stream",
}


class DocumentOut(BaseModel):
    id: str
    title: str
    filename: str
    visibility: str
    status: str
    stage_error: str | None
    current_version: int
    created_at: str


class GrantIn(BaseModel):
    principal_type: str
    principal_id: uuid.UUID


class ACLIn(BaseModel):
    visibility: str
    grants: list[GrantIn] = Field(default_factory=list)


def serialize(doc: Document) -> DocumentOut:
    return DocumentOut(
        id=str(doc.id),
        title=doc.title,
        filename=doc.filename,
        visibility=doc.visibility,
        status=doc.status,
        stage_error=doc.stage_error,
        current_version=doc.current_version,
        created_at=doc.created_at.isoformat(),
    )


def _allowed_query(user: User) -> Select[tuple[Document]]:
    user_group = exists(
        select(DocumentGrant.id).where(
            DocumentGrant.document_id == Document.id,
            DocumentGrant.principal_type == "user",
            DocumentGrant.principal_id == user.id,
        )
    )
    group_grant = exists(
        select(DocumentGrant.id).where(
            DocumentGrant.document_id == Document.id,
            DocumentGrant.principal_type == "group",
            DocumentGrant.principal_id.in_(
                select(Membership.group_id).where(Membership.user_id == user.id)
            ),
        )
    )
    owner_group = exists(
        select(Membership.id).where(
            Membership.user_id == Document.owner_id,
            Membership.group_id.in_(
                select(Membership.group_id).where(Membership.user_id == user.id)
            ),
        )
    )
    return select(Document).where(
        Document.organization_id == user.organization_id,
        Document.is_retired.is_(False),
        or_(
            Document.owner_id == user.id,
            Document.visibility == "org",
            user_group,
            group_grant,
            (Document.visibility == "group") & owner_group,
        ),
    )


@router.get("")
async def list_documents(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_user_scoped_session)
) -> list[DocumentOut]:
    docs = await session.scalars(_allowed_query(user).order_by(Document.created_at.desc()))
    return [serialize(doc) for doc in docs]


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile = File(...),
    visibility: str = Form("private"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_scoped_session),
) -> DocumentOut:
    if visibility not in {"private", "group", "org"}:
        raise HTTPException(422, "visibility must be private, group, or org")
    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED_EXTENSIONS or file.content_type not in ALLOWED_TYPES:
        raise HTTPException(415, "Supported formats are PDF, DOCX, Markdown, HTML, and TXT")
    data = await file.read(get_settings().max_upload_mb * 1024 * 1024 + 1)
    if len(data) > get_settings().max_upload_mb * 1024 * 1024:
        raise HTTPException(413, "File exceeds configured upload limit")
    if extension == ".pdf" and not data.startswith(b"%PDF-"):
        raise HTTPException(415, "File content does not match PDF type")
    if extension == ".docx":
        import io
        import zipfile

        if not zipfile.is_zipfile(io.BytesIO(data)):
            raise HTTPException(415, "Invalid DOCX file")
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if "word/document.xml" not in archive.namelist():
                raise HTTPException(415, "Invalid DOCX file")
    if extension in {".txt", ".md", ".markdown", ".html", ".htm"}:
        if b"\x00" in data:
            raise HTTPException(415, "Text document contains binary data")
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(415, "Text documents must use UTF-8 encoding") from exc
    await get_scanner().scan(data, file.filename or "document")
    checksum = hashlib.sha256(data).hexdigest()
    existing = await session.scalar(
        select(Document).where(
            Document.organization_id == user.organization_id,
            Document.owner_id == user.id,
            Document.checksum == checksum,
            Document.is_retired.is_(False),
        )
    )
    if existing:
        return serialize(existing)
    document_id = uuid.uuid4()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = UPLOAD_DIR / f"{document_id}{extension}"
    path.write_bytes(data)
    doc = Document(
        id=document_id,
        organization_id=user.organization_id,
        owner_id=user.id,
        title=Path(file.filename or "document").stem,
        filename=Path(file.filename or "document").name,
        media_type=file.content_type or "application/octet-stream",
        checksum=checksum,
        visibility=visibility,
        status="uploaded",
    )
    session.add(doc)
    session.add(
        DocumentVersion(
            document_id=document_id, version=1, storage_path=str(path), checksum=checksum
        )
    )
    await session.commit()
    redis = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    try:
        await redis.enqueue_job("ingest_document", str(document_id))
    finally:
        await redis.aclose()
    return serialize(doc)


@router.post("/{document_id}/versions", status_code=status.HTTP_202_ACCEPTED)
async def upload_new_version(
    document_id: uuid.UUID,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_scoped_session),
) -> DocumentOut:
    doc = await session.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == user.organization_id,
            Document.owner_id == user.id,
            Document.is_retired.is_(False),
        )
    )
    if doc is None:
        raise HTTPException(404, "Document not found")
    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED_EXTENSIONS or file.content_type not in ALLOWED_TYPES:
        raise HTTPException(415, "Supported formats are PDF, DOCX, Markdown, HTML, and TXT")
    data = await file.read(get_settings().max_upload_mb * 1024 * 1024 + 1)
    if len(data) > get_settings().max_upload_mb * 1024 * 1024:
        raise HTTPException(413, "File exceeds configured upload limit")
    if extension == ".pdf" and not data.startswith(b"%PDF-"):
        raise HTTPException(415, "File content does not match PDF type")
    if extension == ".docx":
        import io
        import zipfile

        if not zipfile.is_zipfile(io.BytesIO(data)):
            raise HTTPException(415, "Invalid DOCX file")
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if "word/document.xml" not in archive.namelist():
                raise HTTPException(415, "Invalid DOCX file")
    if extension in {".txt", ".md", ".markdown", ".html", ".htm"}:
        if b"\x00" in data:
            raise HTTPException(415, "Text document contains binary data")
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(415, "Text documents must use UTF-8 encoding") from exc
    await get_scanner().scan(data, file.filename or "document")
    checksum = hashlib.sha256(data).hexdigest()
    new_version = doc.current_version + 1
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = UPLOAD_DIR / f"{document_id}-v{new_version}{extension}"
    path.write_bytes(data)
    doc.filename = Path(file.filename or doc.filename).name
    doc.media_type = file.content_type or "application/octet-stream"
    doc.checksum = checksum
    doc.current_version = new_version
    doc.status = "uploaded"
    doc.stage_error = None
    session.add(
        DocumentVersion(
            document_id=doc.id, version=new_version, storage_path=str(path), checksum=checksum
        )
    )
    await session.commit()
    redis = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    try:
        await redis.enqueue_job("ingest_document", str(document_id))
    finally:
        await redis.aclose()
    return serialize(doc)


@router.get("/{document_id}")
async def get_document(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_scoped_session),
) -> DocumentOut:
    doc = await session.scalar(_allowed_query(user).where(Document.id == document_id))
    if doc is None:
        raise HTTPException(404, "Document not found")
    return serialize(doc)


@router.get("/{document_id}/file")
async def get_document_file(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_scoped_session),
) -> FileResponse:
    doc = await session.scalar(_allowed_query(user).where(Document.id == document_id))
    if doc is None:
        raise HTTPException(404, "Document not found")
    version = await session.scalar(
        select(DocumentVersion).where(
            DocumentVersion.document_id == doc.id, DocumentVersion.version == doc.current_version
        )
    )
    if version is None or not Path(version.storage_path).is_file():
        raise HTTPException(404, "Document content unavailable")
    return FileResponse(version.storage_path, filename=doc.filename, media_type=doc.media_type)


@router.get("/{document_id}/chunks/{chunk_id}")
async def get_chunk(
    document_id: uuid.UUID,
    chunk_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_scoped_session),
) -> dict[str, object]:
    doc = await session.scalar(_allowed_query(user).where(Document.id == document_id))
    chunk = await session.scalar(
        select(Chunk).where(
            Chunk.document_id == document_id,
            Chunk.id == chunk_id,
            Chunk.organization_id == user.organization_id,
            Chunk.is_retired.is_(False),
        )
    )
    if doc is None or chunk is None:
        raise HTTPException(404, "Source passage not found")
    return {
        "id": str(chunk.id),
        "text": chunk.text,
        "page_start": chunk.page_start,
        "page_end": chunk.page_end,
        "heading_path": chunk.heading_path,
        "char_start": chunk.char_start,
        "char_end": chunk.char_end,
    }


@router.put("/{document_id}/acl")
async def replace_acl(
    document_id: uuid.UUID,
    payload: ACLIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_scoped_session),
) -> DocumentOut:
    doc = await session.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == user.organization_id,
            Document.owner_id == user.id,
            Document.is_retired.is_(False),
        )
    )
    if doc is None:
        raise HTTPException(404, "Document not found")
    if payload.visibility not in {"private", "group", "org"}:
        raise HTTPException(422, "Invalid visibility")
    for grant in payload.grants:
        if grant.principal_type == "user":
            principal = await session.scalar(
                select(User.id).where(
                    User.id == grant.principal_id, User.organization_id == user.organization_id
                )
            )
        elif grant.principal_type == "group":
            from backend.app.db.models import Group

            principal = await session.scalar(
                select(Group.id).where(
                    Group.id == grant.principal_id, Group.organization_id == user.organization_id
                )
            )
        else:
            raise HTTPException(422, "Grant principal_type must be user or group")
        if principal is None:
            raise HTTPException(422, "Grant principal must belong to your organization")
    doc.visibility = payload.visibility
    doc.status = "uploaded"
    await session.execute(delete(DocumentGrant).where(DocumentGrant.document_id == doc.id))
    for grant in payload.grants:
        session.add(
            DocumentGrant(
                document_id=doc.id,
                principal_type=grant.principal_type,
                principal_id=grant.principal_id,
            )
        )
    await session.commit()
    redis = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    try:
        await redis.enqueue_job("ingest_document", str(document_id))
    finally:
        await redis.aclose()
    return serialize(doc)


@router.post("/{document_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_document(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_scoped_session),
) -> DocumentOut:
    doc = await session.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == user.organization_id,
            Document.owner_id == user.id,
            Document.is_retired.is_(False),
        )
    )
    if doc is None:
        raise HTTPException(404, "Document not found")
    doc.status = "uploaded"
    doc.stage_error = None
    await session.commit()
    redis = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    try:
        await redis.enqueue_job("ingest_document", str(document_id))
    finally:
        await redis.aclose()
    return serialize(doc)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def retire_document(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_scoped_session),
) -> None:
    doc = await session.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == user.organization_id,
            Document.owner_id == user.id,
        )
    )
    if doc is None:
        raise HTTPException(404, "Document not found")
    doc.is_retired = True
    doc.status = "retired"
    await session.commit()
