# ADR 0003: Reciprocal Rank Fusion

Status: accepted.

Retrieve independent vector and PostgreSQL full-text candidate sets, apply reciprocal rank fusion with a constant of 60, then rerank the fused candidate pool. RRF needs no score calibration between cosine distance and FTS rank and remains stable when one candidate source is sparse.
