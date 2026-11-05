# Evaluation report

The evaluation runner is `backend.app.evals.cli` and includes 40 fixed cases: 30 answerable questions mapped to seeded document titles and 10 abstention/adversarial questions. It reports vector-only, hybrid RRF, and hybrid-plus-rerank recall@5, MRR, and nDCG, as well as citation precision, groundedness, abstention accuracy, and retrieval latency p50/p95.

## Latest measured run

Measured locally with the default deterministic demo providers after `docker compose up --build -d`, seeding, and running `backend.app.evals.cli` (40 questions):

| Mode | Recall@5 | MRR | nDCG |
|---|---:|---:|---:|
| Vector only | 0.750 | 0.688 | 0.703 |
| Hybrid RRF | 0.750 | 0.700 | 0.713 |
| Hybrid + lexical rerank | 0.650 | 0.650 | 0.650 |

Citation precision: 0.800; groundedness: 0.800; abstention accuracy: 0.800. Hybrid retrieval latency: p50 0.8 ms, p95 1.0 ms over 40 queries. These figures are from one small local run and are not a production performance claim.

## Interpretation limits

The demo corpus has three short documents and uses deterministic token-hash vectors plus a lexical demo reranker. The conservative answerability gate favors abstention when exact query terms do not overlap enough, which can lower recall on paraphrases. Metrics are a wiring check, not evidence of production retrieval quality. Re-run after switching embedding providers, expanding the corpus, and adding reviewer-labeled expected chunks.
