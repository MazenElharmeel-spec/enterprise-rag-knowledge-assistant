import asyncio
import math
import statistics
import time

from sqlalchemy import select, text

from backend.app.db.models import Membership, User
from backend.app.db.session import SessionLocal
from backend.app.evals.golden import GOLDEN
from backend.app.llm.generation import answer, validate_citations
from backend.app.retrieval.hybrid import Hit, retrieve


def _scores(ranks: list[int | None]) -> dict[str, float]:
    count = max(len(ranks), 1)
    recall = sum(rank is not None and rank <= 5 for rank in ranks) / count
    mrr = sum(1 / rank for rank in ranks if rank is not None) / count
    ndcg = sum((1 / math.log2(rank + 1)) for rank in ranks if rank is not None) / count
    return {"recall@5": recall, "MRR": mrr, "nDCG": ndcg}


async def run() -> None:
    async with SessionLocal() as session:
        user = await session.scalar(select(User).where(User.email == "alice@acme-demo.com"))
        if user is None:
            raise SystemExit("Seed the demo first: make seed")
        group_ids = list(
            await session.scalars(select(Membership.group_id).where(Membership.user_id == user.id))
        )
        await session.execute(
            text("SELECT set_config('app.user_id', :v, true)"), {"v": str(user.id)}
        )
        await session.execute(
            text("SELECT set_config('app.organization_id', :v, true)"),
            {"v": str(user.organization_id)},
        )
        await session.execute(
            text("SELECT set_config('app.group_ids', :v, true)"),
            {"v": ",".join(map(str, group_ids))},
        )
        strategies = ("vector", "hybrid", "hybrid_rerank")
        ranks: dict[str, list[int | None]] = {strategy: [] for strategy in strategies}
        relevance: dict[str, list[bool]] = {strategy: [] for strategy in strategies}
        citation_precision: list[float] = []
        grounded: list[float] = []
        abstain_correct: list[float] = []
        latencies: list[float] = []
        for example in GOLDEN:
            hits: list[Hit] = []
            for strategy in strategies:
                started = time.perf_counter()
                ranked = await retrieve(session, user, example.question, limit=5, strategy=strategy)  # type: ignore[arg-type]
                elapsed = (time.perf_counter() - started) * 1000
                if strategy == "hybrid_rerank":
                    hits = ranked
                    latencies.append(elapsed)
                found_rank = (
                    next(
                        (
                            index
                            for index, hit in enumerate(ranked, 1)
                            if hit.title == example.expected_title
                        ),
                        None,
                    )
                    if example.expected_title
                    else None
                )
                ranks[strategy].append(found_rank)
                relevance[strategy].append(found_rank is not None)
            response = await answer(example.question, hits)
            clean, citations = validate_citations(response, hits)
            cited_titles = [hit.title for _, hit in citations]
            if example.expected_title is None:
                abstained = not citations and "could not find enough evidence" in clean.lower()
                abstain_correct.append(float(abstained))
                citation_precision.append(float(not citations))
                grounded.append(float(abstained))
            else:
                abstain_correct.append(float(bool(citations)))
                citation_precision.append(
                    sum(title == example.expected_title for title in cited_titles)
                    / max(len(cited_titles), 1)
                )
                grounded.append(
                    float(
                        bool(citations)
                        and any(hit.title == example.expected_title for _, hit in citations)
                    )
                )
        precision = statistics.mean(citation_precision)
        faithfulness = statistics.mean(grounded)
        abstention = statistics.mean(abstain_correct)
        ordered = sorted(latencies)
        p50 = statistics.median(ordered)
        p95 = ordered[min(len(ordered) - 1, math.ceil(len(ordered) * 0.95) - 1)]
        print("Mode                 recall@5   MRR    nDCG")
        for strategy, label in (
            ("vector", "vector only"),
            ("hybrid", "hybrid RRF"),
            ("hybrid_rerank", "hybrid + rerank"),
        ):
            scores = _scores(ranks[strategy])
            print(
                f"{label:<21} {scores['recall@5']:.3f}     {scores['MRR']:.3f}  {scores['nDCG']:.3f}"
            )
        print(
            f"Citation precision={precision:.3f}; groundedness={faithfulness:.3f}; abstention accuracy={abstention:.3f}"
        )
        print(f"Hybrid latency: p50={p50:.1f}ms p95={p95:.1f}ms over {len(GOLDEN)} queries")


if __name__ == "__main__":
    asyncio.run(run())
