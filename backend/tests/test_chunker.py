import pytest

from backend.app.ingestion.chunker import chunk_blocks
from backend.app.ingestion.parsers import Block


def test_heading_changes_create_chunk_boundary() -> None:
    chunks = chunk_blocks(
        [
            Block("A useful paragraph.", heading_path=("Overview",)),
            Block("Another useful paragraph.", heading_path=("Budget",)),
        ],
        100,
        0,
    )
    assert len(chunks) == 2
    assert chunks[0].heading_path == ("Overview",)
    assert chunks[1].heading_path == ("Budget",)


def test_table_is_never_merged_with_regular_prose() -> None:
    table = "| City | Pilot |\n| --- | --- |\n| Chicago | Q2 |"
    chunks = chunk_blocks(
        [
            Block("Introductory paragraph.", heading_path=("Plans",)),
            Block(table, heading_path=("Plans",), is_table=True),
            Block("Closing paragraph.", heading_path=("Plans",)),
        ],
        100,
        0,
    )
    table_chunks = [chunk for chunk in chunks if "| City |" in chunk.text]
    assert len(table_chunks) == 1
    assert table_chunks[0].text == table


def test_invalid_chunk_size_is_rejected() -> None:
    try:
        chunk_blocks([Block("content")], 80, 80)
    except ValueError as exc:
        assert "max_tokens" in str(exc)
    else:
        raise AssertionError("Expected invalid overlap to be rejected")


def test_chunker_falls_back_when_tiktoken_assets_are_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import tiktoken

    def offline(_encoding: str) -> object:
        raise OSError("tokenizer assets are not cached")

    monkeypatch.setattr(tiktoken, "get_encoding", offline)
    chunks = chunk_blocks([Block("alpha beta gamma delta")], max_tokens=2, overlap_tokens=0)
    assert [chunk.text for chunk in chunks] == ["alpha beta", "gamma delta"]
