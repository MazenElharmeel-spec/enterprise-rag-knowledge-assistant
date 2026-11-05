import re
from dataclasses import dataclass

from backend.app.ingestion.parsers import Block


@dataclass(frozen=True)
class ChunkDraft:
    text: str
    page_start: int | None
    page_end: int | None
    heading_path: tuple[str, ...]
    char_start: int
    char_end: int


def _units(text: str) -> list[str]:
    try:
        import tiktoken

        return [str(x) for x in tiktoken.get_encoding("cl100k_base").encode(text)]
    except ImportError:
        return text.split()
    except OSError:
        # tiktoken may need to fetch its encoding table on the first run. Keep ingestion usable
        # in offline demo and deployment environments with a deterministic word/punctuation count.
        return re.findall(r"\w+|[^\w\s]", text)


def _count(text: str) -> int:
    return len(_units(text))


def _split_block(block: Block, limit: int) -> list[str]:
    if block.is_table or _count(block.text) <= limit:
        return [block.text]
    # Keep sentence boundaries when possible; fall back to word boundaries for very long sentences.
    sentences = [
        part.strip()
        for part in block.text.replace("? ", "?\n")
        .replace("! ", "!\n")
        .replace(". ", ".\n")
        .splitlines()
        if part.strip()
    ]
    if not sentences:
        sentences = block.text.split()
    result: list[str] = []
    current = ""
    for sentence in sentences:
        if _count(sentence) > limit:
            words = sentence.split()
            pieces: list[str] = []
            piece = ""
            for word in words:
                candidate = f"{piece} {word}".strip()
                if piece and _count(candidate) > limit:
                    pieces.append(piece)
                    piece = word
                else:
                    piece = candidate
            if piece:
                pieces.append(piece)
            # Append the long sentence safely without losing surrounding sentences.
            if current:
                result.append(current)
                current = ""
            result.extend(pieces)
            continue
        candidate = f"{current} {sentence}".strip()
        if current and _count(candidate) > limit:
            result.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        result.append(current)
    return result


def chunk_blocks(
    blocks: list[Block], max_tokens: int = 600, overlap_tokens: int = 80
) -> list[ChunkDraft]:
    if max_tokens < 1 or overlap_tokens < 0 or overlap_tokens >= max_tokens:
        raise ValueError("Require max_tokens > overlap_tokens >= 0")
    drafts: list[ChunkDraft] = []
    global_offset = 0
    active_text = ""
    active_pages: list[int] = []
    active_heading: tuple[str, ...] = ()
    active_start = 0

    def flush() -> None:
        nonlocal active_text, active_pages, active_start
        text = active_text.strip()
        if text:
            drafts.append(
                ChunkDraft(
                    text,
                    min(active_pages) if active_pages else None,
                    max(active_pages) if active_pages else None,
                    active_heading,
                    active_start,
                    active_start + len(text),
                )
            )
        active_text = ""
        active_pages = []

    for block in blocks:
        for piece in _split_block(block, max_tokens):
            candidate = f"{active_text}\n\n{piece}".strip()
            if active_text and (
                block.heading_path != active_heading
                or _count(candidate) > max_tokens
                or block.is_table
            ):
                prior = active_text
                flush()
                active_start = global_offset
                if overlap_tokens and not block.is_table:
                    words = prior.split()
                    overlap = " ".join(words[-overlap_tokens:])
                    if overlap:
                        active_text = overlap
                candidate = f"{active_text}\n\n{piece}".strip()
            if not active_text:
                active_start = global_offset
                active_heading = block.heading_path
            active_text = candidate
            if block.page is not None:
                active_pages.append(block.page)
            global_offset += len(piece) + 2
            if block.is_table:
                flush()
    flush()
    return drafts
