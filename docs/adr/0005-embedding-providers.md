# ADR 0005: Embedding provider interface

Status: accepted.

Hide embedding model choice behind a small async interface. The fake deterministic provider supports local demos and tests; OpenAI and optional local sentence-transformers adapters are configuration-controlled. Store model and version per chunk, and re-index after changing providers. Keep a common 1536-dimensional vector column for the default OpenAI and padded local model path.
