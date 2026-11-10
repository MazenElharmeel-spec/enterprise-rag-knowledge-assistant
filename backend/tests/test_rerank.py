from types import SimpleNamespace
from uuid import uuid4

import pytest

import backend.app.retrieval.rerank as rerank_module
from backend.app.retrieval.hybrid import Hit


@pytest.mark.asyncio
async def test_lexical_fallback_keeps_low_overlap_fused_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        rerank_module,
        "get_settings",
        lambda: SimpleNamespace(reranker_provider="lexical", anthropic_api_key=""),
    )
    paraphrase = Hit(
        chunk_id=uuid4(),
        document_id=uuid4(),
        title="Workflow guide",
        text="Human signoff governs durable task orchestration.",
        page_start=None,
        page_end=None,
        heading_path=[],
        score=0.016,
        url="/documents/workflow",
    )
    exact_match = Hit(
        chunk_id=uuid4(),
        document_id=uuid4(),
        title="Deployment checklist",
        text="Deployment approval workflow checklist.",
        page_start=None,
        page_end=None,
        heading_path=[],
        score=0.015,
        url="/documents/deployment",
    )

    ranked = await rerank_module.rerank(
        "deployment approval workflow", [paraphrase, exact_match]
    )

    assert {hit.chunk_id for hit in ranked} == {paraphrase.chunk_id, exact_match.chunk_id}
    assert ranked[0].chunk_id == exact_match.chunk_id
    assert all(hit.score >= 0 for hit in ranked)
