# ADR 0001: Arq and Redis for ingestion

Status: accepted.

Use Arq with Redis because the job model is small, async-native, and integrates with the async SQLAlchemy/FastAPI stack without introducing a separate broker service. The worker records ingestion state in Postgres and uses the version ID as an idempotency boundary. Redis outages reject queued work visibly; retry endpoints can re-enqueue failed documents.
