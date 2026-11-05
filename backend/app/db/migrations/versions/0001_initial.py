"""Initial schema, vector/FTS indexes, and row-level security.

Revision ID: 0001_initial
Revises:
"""

from alembic import op

from backend.app.db import models  # noqa: F401
from backend.app.db.base import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind=op.get_bind())
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )
    op.execute(
        "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS search_vector tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(text, ''))) STORED"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_chunks_search_vector_gin ON chunks USING gin (search_vector)"
    )
    op.execute("ALTER TABLE chunks ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE chunks FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY chunk_scope ON chunks
        USING (
          organization_id::text = current_setting('app.organization_id', true)
          AND (
            'org:' || organization_id::text = ANY(acl_principals)
            OR 'user:' || current_setting('app.user_id', true) = ANY(acl_principals)
            OR EXISTS (
              SELECT 1 FROM unnest(string_to_array(current_setting('app.group_ids', true), ',')) AS gid
              WHERE 'group:' || gid = ANY(acl_principals)
            )
          )
        )
        WITH CHECK (organization_id::text = current_setting('app.organization_id', true))
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS chunk_scope ON chunks")
    op.execute("DROP INDEX IF EXISTS ix_chunks_search_vector_gin")
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw")
    Base.metadata.drop_all(bind=op.get_bind())
