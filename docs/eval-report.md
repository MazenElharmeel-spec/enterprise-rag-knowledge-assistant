# Local retrieval evaluation

## Setup and scope

The CLI evaluates 40 fixed questions against 3 short synthetic documents: 30 answerable questions and 10 abstention or adversarial questions. This is a deterministic local demo using the fake hash embedder, lexical fallback reranker, and fake answer generator. The latency numbers are from one local run and should not be read as production performance.

## Reranking change

The lexical fallback previously applied a hard overlap cutoff after candidate retrieval. That removed fused candidates when a relevant passage expressed the answer with different wording. It now keeps the fused candidate pool and blends normalized reciprocal-rank-fusion and lexical scores at equal weight. This lets lexical overlap improve ordering without acting as a hard gate.

On the same seeded corpus and fixed questions, hybrid retrieval plus reranking changed as follows:

| Measure | Before | After |
| --- | ---: | ---: |
| Recall@5 | 0.625 | 0.750 |
| MRR | 0.625 | 0.738 |
| nDCG | 0.625 | 0.741 |

The vector-only and hybrid-RRF baselines remained at Recall@5 0.750. The post-change hybrid RRF baseline scored MRR 0.658 and nDCG 0.682; the reranked path scored MRR 0.738 and nDCG 0.741. Citation precision, groundedness, and abstention accuracy were each 0.700 in the post-change run. Retrieval p50/p95 was 0.7/1.0 ms for 40 queries in the latest run.

These results show improvement on this small fixed set, not general semantic retrieval quality. In a separate two-user ACL smoke test, Bob received no unauthorized citations across two requests (one direct access query and one injection-style query) and received HTTP 404 when opening Alice's restricted citation.
