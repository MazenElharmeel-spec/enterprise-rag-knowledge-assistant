from pathlib import Path
from uuid import UUID

from arq.connections import RedisSettings
from sqlalchemy import delete, select, text, update

from backend.app.core.config import get_settings
from backend.app.db.models import Chunk, Document, DocumentGrant, DocumentVersion, Membership
from backend.app.db.session import SessionLocal
from backend.app.ingestion.chunker import chunk_blocks
from backend.app.ingestion.parsers import parse_file
from backend.app.llm.embeddings import get_embedder


async def ingest_document(ctx: dict[str, object], document_id: str) -> None:
    async with SessionLocal() as session:
        doc = await session.get(Document, UUID(document_id))
        if doc is None or doc.is_retired:
            return
        organization_id = doc.organization_id
        owner_id = doc.owner_id

        async def set_context() -> None:
            await session.execute(
                text("SELECT set_config('app.organization_id', :v, true)"),
                {"v": str(organization_id)},
            )
            await session.execute(
                text("SELECT set_config('app.user_id', :v, true)"), {"v": str(owner_id)}
            )
            await session.execute(text("SELECT set_config('app.group_ids', :v, true)"), {"v": ""})

        doc.status = "parsing"
        doc.stage_error = None
        await set_context()
        await session.commit()
        try:
            version = await session.scalar(
                select(DocumentVersion).where(
                    DocumentVersion.document_id == doc.id,
                    DocumentVersion.version == doc.current_version,
                )
            )
            if version is None:
                raise ValueError("Document version record is missing")
            blocks = parse_file(Path(version.storage_path))
            doc.status = "chunking"
            await set_context()
            await session.commit()
            drafts = chunk_blocks(
                blocks, get_settings().chunk_size_tokens, get_settings().chunk_overlap_tokens
            )
            # Reprocessing a version replaces its prior chunks, making retries idempotent.
            await set_context()
            await session.execute(
                delete(Chunk).where(
                    Chunk.document_id == doc.id, Chunk.version == doc.current_version
                )
            )
            grants = list(
                (
                    await session.scalars(
                        select(DocumentGrant).where(DocumentGrant.document_id == doc.id)
                    )
                ).all()
            )
            memberships = list(
                (
                    await session.scalars(
                        select(Membership.group_id).where(Membership.user_id == doc.owner_id)
                    )
                ).all()
            )
            principals = [f"user:{doc.owner_id}"]
            principals.extend(f"{grant.principal_type}:{grant.principal_id}" for grant in grants)
            principals.extend(f"group:{group_id}" for group_id in memberships)
            if doc.visibility == "org":
                principals.append(f"org:{doc.organization_id}")
            elif doc.visibility == "group":
                principals.extend(f"group:{group_id}" for group_id in memberships)
            doc.status = "embedding"
            await set_context()
            await session.commit()
            embedder = get_embedder()
            for start in range(0, len(drafts), 64):
                batch = drafts[start : start + 64]
                vectors = await embedder.embed([draft.text for draft in batch])
                await set_context()
                for draft, vector in zip(batch, vectors, strict=True):
                    session.add(
                        Chunk(
                            document_id=doc.id,
                            version=doc.current_version,
                            organization_id=doc.organization_id,
                            text=draft.text,
                            page_start=draft.page_start,
                            page_end=draft.page_end,
                            heading_path=list(draft.heading_path),
                            char_start=draft.char_start,
                            char_end=draft.char_end,
                            acl_principals=principals,
                            embedding=vector,
                            embedding_model=embedder.model,
                            embedding_version="1",
                        )
                    )
                await session.flush()
            await set_context()
            await session.execute(
                update(Chunk)
                .where(Chunk.document_id == doc.id, Chunk.version < doc.current_version)
                .values(is_retired=True)
            )
            doc.status = "indexed"
            doc.stage_error = None
            await session.commit()
        except Exception as exc:
            await session.rollback()
            doc = await session.get(Document, UUID(document_id))
            if doc is not None:
                doc.status = "failed"
                doc.stage_error = f"{type(exc).__name__}: {exc}"[:2000]
                await session.commit()
            raise


class WorkerSettings:
    functions = [ingest_document]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 10
    job_timeout = 600
