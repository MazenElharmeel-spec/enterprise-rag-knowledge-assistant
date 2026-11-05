from uuid import uuid4

from backend.app.llm.generation import validate_citations
from backend.app.retrieval.hybrid import Hit


def test_citation_validation_strips_out_of_range_markers() -> None:
    hit = Hit(
        uuid4(), uuid4(), "Policy", "Only approved data", 1, 1, ["Rules"], 0.5, "/documents/1"
    )
    content, citations = validate_citations("Supported [1]. Unsupported [8].", [hit])
    assert content == "Supported [1]. Unsupported ."
    assert len(citations) == 1
    assert citations[0][1].chunk_id == hit.chunk_id


def test_no_sources_yields_no_citations() -> None:
    content, citations = validate_citations("I do not know [1].", [])
    assert content == "I do not know ."
    assert citations == []
