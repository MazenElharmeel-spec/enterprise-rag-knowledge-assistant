from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import get_settings
from backend.app.db.models import User
from backend.app.llm.embeddings import get_embedder
from backend.app.retrieval.rerank import rerank


@dataclass(frozen=True)
class Hit:
    chunk_id: UUID
    document_id: UUID
    title: str
    text: str
    page_start: int | None
    page_end: int | None
    heading_path: list[str]
    score: float
    url: str


async def retrieve(
    session: AsyncSession,
    user: User,
    query: str,
    limit: int | None = None,
    strategy: Literal["vector", "hybrid", "hybrid_rerank"] = "hybrid_rerank",
) -> list[Hit]:
    top_k = limit or get_settings().retrieval_top_k
    memberships = await session.execute(
        text("SELECT group_id FROM memberships WHERE user_id = :user_id"), {"user_id": user.id}
    )
    principals = [f"user:{user.id}", f"org:{user.organization_id}"]
    principals.extend(f"group:{row.group_id}" for row in memberships)
    vector = (await get_embedder().embed([query]))[0]
    params = {
        "org_id": user.organization_id,
        "principals": principals,
        "query": query,
        "vector": str(vector),
        "take": top_k * 4,
        "strategy": strategy,
    }
    # ACL predicate is applied in both candidate queries, before ORDER BY/LIMIT.
    # RLS independently enforces the same per-request user/group/org scope.
    rows = await session.execute(
        text("""
            WITH vector_candidates AS (
              SELECT c.id, c.document_id, c.text, c.page_start, c.page_end, c.heading_path,
                     d.title, 1 - (c.embedding <=> CAST(:vector AS vector)) AS score,
                     row_number() OVER (ORDER BY c.embedding <=> CAST(:vector AS vector)) AS rank
              FROM chunks c JOIN documents d ON d.id = c.document_id
              WHERE c.organization_id = :org_id AND c.acl_principals && CAST(:principals AS varchar[])
                AND NOT c.is_retired AND NOT d.is_retired AND d.status = 'indexed'
                AND c.embedding IS NOT NULL AND c.version = d.current_version
              ORDER BY c.embedding <=> CAST(:vector AS vector) LIMIT :take
            ), lexical_candidates AS (
              SELECT c.id, c.document_id, c.text, c.page_start, c.page_end, c.heading_path,
                     d.title, ts_rank(c.search_vector, websearch_to_tsquery('english', :query)) AS score,
                     row_number() OVER (ORDER BY ts_rank(c.search_vector, websearch_to_tsquery('english', :query)) DESC) AS rank
              FROM chunks c JOIN documents d ON d.id = c.document_id
              WHERE c.organization_id = :org_id AND c.acl_principals && CAST(:principals AS varchar[])
                AND NOT c.is_retired AND NOT d.is_retired AND d.status = 'indexed'
                AND c.version = d.current_version AND c.search_vector @@ websearch_to_tsquery('english', :query)
              ORDER BY score DESC LIMIT :take
            ), fused AS (
              SELECT id, document_id, text, page_start, page_end, heading_path, title,
                     SUM(1.0 / (60 + rank)) AS rrf_score
              FROM (
                SELECT id, document_id, text, page_start, page_end, heading_path, title, rank
                FROM vector_candidates
                WHERE :strategy IN ('vector', 'hybrid', 'hybrid_rerank')
                UNION ALL
                SELECT id, document_id, text, page_start, page_end, heading_path, title, rank
                FROM lexical_candidates
                WHERE :strategy IN ('hybrid', 'hybrid_rerank')
              ) candidates
              GROUP BY id, document_id, text, page_start, page_end, heading_path, title
            )
            SELECT * FROM fused ORDER BY rrf_score DESC LIMIT :take
        """),
        params,
    )
    hits = []
    for row in rows.mappings():
        hits.append(
            Hit(
                row["id"],
                row["document_id"],
                row["title"],
                row["text"],
                row["page_start"],
                row["page_end"],
                row["heading_path"],
                float(row["rrf_score"]),
                f"/documents/{row['document_id']}?chunk={row['id']}",
            )
        )
    # Deterministic lexical rerank in demo mode, then cap near duplicate passages.
    if strategy == "hybrid_rerank":
        hits = await rerank(query, hits)
    else:
        hits.sort(key=lambda hit: hit.score, reverse=True)
    selected: list[Hit] = []
    fingerprints: set[str] = set()
    for hit in hits:
        key = " ".join(hit.text.lower().split()[:16])
        if key not in fingerprints:
            fingerprints.add(key)
            selected.append(hit)
        if len(selected) == top_k:
            break
    return selected
