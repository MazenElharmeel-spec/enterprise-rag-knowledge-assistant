# Architecture

## Request path

The API validates a short-lived JWT, resolves the active account, reads current group membership, and sets PostgreSQL transaction context. The chat service builds a standalone query for follow-ups, runs permission-filtered hybrid retrieval, reranks and deduplicates passages, generates an answer from quoted untrusted context, validates every citation marker against the retrieved list, and persists the messages before returning SSE events. FastAPI, SQLAlchemy, and outbound HTTP calls are instrumented with OpenTelemetry; configure `OTEL_EXPORTER_OTLP_ENDPOINT` and start the optional `observability` Compose profile to export spans.

## Ingestion path

Uploads are size-limited, MIME/extension checked, checksummed, written under an opaque UUID filename, and recorded as a version. Arq queues work through Redis. The worker advances `uploaded → parsing → chunking → embedding → indexed`; failures record the stage error and are retryable. Each version has its own chunk rows. Current version and retired flags keep old content out of retrieval.

## Data and permissions

Document visibility can be private, group, or organization-wide, with explicit user/group grants. Chunk principal strings are materialized during ingestion. Candidate SQL filters both vector and lexical paths by organization and principal overlap before rank ordering and limiting. RLS applies the same organization/user/group context as defense in depth. ACL edits set documents to a non-indexed state while chunks are rebuilt.

## Reliability and extension points

Provider calls use bounded timeouts/retries. Fake providers keep local demos deterministic. OpenAI embeddings, local sentence-transformers embeddings, Anthropic generation, cross-encoder ranking, and Anthropic ranking can be selected with configuration. Redis is a required queue dependency; uploaded content is stored on a dedicated volume in Compose.

## Operational notes

Alembic creates pgvector, the schema, HNSW and GIN indexes, and chunk RLS. The API container migrates on startup; readiness probes PostgreSQL. API and web containers run as non-root users. The Prometheus endpoint currently exports process metrics and the request ID logs include elapsed request time.
