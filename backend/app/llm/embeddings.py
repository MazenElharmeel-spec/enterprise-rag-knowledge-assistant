import asyncio
import hashlib
import math
from collections.abc import Sequence
from typing import Protocol

from openai import AsyncOpenAI

from backend.app.core.config import get_settings


class Embedder(Protocol):
    model: str

    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class FakeEmbedder:
    model = "fake-hash-v1"

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        result = []
        for text in texts:
            vector = [0.0] * 1536
            tokens = text.lower().split()
            for token in tokens:
                digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
                index = int.from_bytes(digest[:4], "big") % len(vector)
                sign = 1.0 if digest[4] % 2 else -1.0
                vector[index] += sign
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            result.append([value / norm for value in vector])
        return result


class OpenAIEmbedder:
    model = "text-embedding-3-small"

    def __init__(self) -> None:
        settings = get_settings()
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=30, max_retries=3)

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        response = await self.client.embeddings.create(model=self.model, input=list(texts))
        return [item.embedding for item in response.data]


class LocalEmbedder:
    model = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

        self.encoder = SentenceTransformer(self.model)

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        values = await asyncio.to_thread(
            self.encoder.encode, list(texts), normalize_embeddings=True
        )
        # MiniLM uses 384 dimensions. The current pgvector column is 1536, so map output
        # into the configured storage dimension deterministically for a single schema.
        return [list(value) + [0.0] * (1536 - len(value)) for value in values]


def get_embedder() -> Embedder:
    if get_settings().embedding_provider == "openai":
        return OpenAIEmbedder()
    if get_settings().embedding_provider == "local":
        return LocalEmbedder()
    return FakeEmbedder()
