import asyncio
import hashlib
import uuid
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from backend.app.core.security import hash_password
from backend.app.db.models import Document, DocumentVersion, Group, Membership, Organization, User
from backend.app.db.session import SessionLocal
from backend.app.ingestion.worker import ingest_document

SEED_DIR = Path("/data/uploads")
DEMO_DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "demo"


async def seed() -> None:
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    async with SessionLocal() as session:
        org = await session.scalar(select(Organization).where(Organization.name == "Acme Demo"))
        if org is None:
            org = Organization(name="Acme Demo")
            session.add(org)
            await session.flush()
        users = {}
        for email, name, role in [
            ("admin@acme-demo.com", "Alex Admin", "admin"),
            ("alice@acme-demo.com", "Alice Chen", "member"),
            ("bob@acme-demo.com", "Bob Rivera", "member"),
        ]:
            user = await session.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(
                    organization_id=org.id,
                    email=email,
                    full_name=name,
                    role=role,
                    password_hash=hash_password("demo-pass-123"),
                )
                session.add(user)
                await session.flush()
            users[email] = user
        group = await session.scalar(
            select(Group).where(Group.organization_id == org.id, Group.name == "Strategy")
        )
        if group is None:
            group = Group(organization_id=org.id, name="Strategy")
            session.add(group)
            await session.flush()
        for user_email in ("alice@acme-demo.com", "admin@acme-demo.com"):
            exists = await session.scalar(
                select(Membership.id).where(
                    Membership.user_id == users[user_email].id, Membership.group_id == group.id
                )
            )
            if not exists:
                session.add(Membership(user_id=users[user_email].id, group_id=group.id))
        await session.flush()
        documents = [
            (
                "Expansion overview",
                "expansion-overview.md",
                "org",
                "admin@acme-demo.com",
            ),
            (
                "Project Phoenix",
                "project-phoenix.md",
                "private",
                "alice@acme-demo.com",
            ),
            (
                "Strategy notes",
                "strategy-notes.md",
                "group",
                "alice@acme-demo.com",
            ),
        ]
        ids: list[UUID] = []
        for title, filename, visibility, owner_email in documents:
            content = (DEMO_DATA_DIR / filename).read_text()
            checksum = hashlib.sha256(content.encode()).hexdigest()
            doc = await session.scalar(
                select(Document).where(
                    Document.organization_id == org.id, Document.checksum == checksum
                )
            )
            if doc is None:
                doc_id = uuid.uuid4()
                path = SEED_DIR / f"{doc_id}.md"
                path.write_text(content)
                doc = Document(
                    id=doc_id,
                    organization_id=org.id,
                    owner_id=users[owner_email].id,
                    title=title,
                    filename=filename,
                    media_type="text/markdown",
                    checksum=checksum,
                    visibility=visibility,
                    status="uploaded",
                )
                session.add(doc)
                session.add(
                    DocumentVersion(
                        document_id=doc_id, version=1, storage_path=str(path), checksum=checksum
                    )
                )
                await session.flush()
            ids.append(doc.id)
        await session.commit()
    for doc_id in ids:
        await ingest_document({}, str(doc_id))
    print(
        "Seed complete. Demo credentials: admin@acme-demo.com, alice@acme-demo.com, bob@acme-demo.com / demo-pass-123"
    )


if __name__ == "__main__":
    asyncio.run(seed())
