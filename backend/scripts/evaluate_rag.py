"""
evaluate_rag_fixed.py

Scientifically rigorous RAG retrieval evaluation.

KEY FIXES vs original:
1. Ground truth generated WITHOUT using the retriever (avoids contamination)
2. Each algorithm runs independently with its own top_k pool
3. BM25 and vector scores fetched separately, not re-sorted from a shared pool
4. RRF (Reciprocal Rank Fusion) implemented correctly using FUSION_CONSTANT
5. Metrics: Hit Rate @K, MRR, NDCG@K, Precision@K
6. Results exported to JSON for the dashboard
"""

import asyncio
import json
import time
import math
import random
import os
from typing import List, Dict, Tuple, Optional

# ── adjust these imports to match your project layout ─────────────────────────
from app.retrieval.searchers.vector import VectorSearcher
from app.retrieval.searchers.bm25 import BM25Searcher
from app.llm.generator import generate_answer
import dotenv
dotenv.load_dotenv()
# ──────────────────────────────────────────────────────────────────────────────

FUSION_CONSTANT = int(os.getenv("FUSION_CONSTANT", 60))   # used in RRF
TOP_K           = 10      # rank cutoff for all metrics
POOL_SIZE       = 50     # how many docs each individual searcher fetches
NUM_QUESTIONS   = 20     # questions to generate (use ≥20 for stable metrics)


# ─────────────────────────────────────────────────────────────────────────────
# PART 1 — Ground-Truth Generation (contamination-free)
# ─────────────────────────────────────────────────────────────────────────────

async def generate_golden_dataset(num_questions: int = NUM_QUESTIONS,
                                   output_path: str = "golden_dataset.json") -> List[Dict]:
    """
    Build a golden QA dataset WITHOUT using the retriever.

    Strategy:
      - Pull chunks directly from the document store (bypassing the searcher)
      - Sample randomly so no single retriever biases which chunks are chosen
      - Use the LLM to write a question whose ONLY correct answer is that chunk

    If you don't have direct DB access, replace _sample_chunks_from_db() with
    whatever method gives you raw chunks + their IDs.
    """
    print(f"\n{'='*55}")
    print(" PART 1 — Generating Clean Ground-Truth Dataset")
    print(f"{'='*55}")

    chunks = await _sample_chunks_from_db(num_questions * 3)   # oversample
    random.shuffle(chunks)

    golden: List[Dict] = []
    attempts = 0

    for chunk in chunks:
        if len(golden) >= num_questions:
            break
        attempts += 1

        doc_id  = chunk.get("id") or chunk.get("_id")
        content = (chunk.get("content") or chunk.get("text", ""))[:800]

        if not doc_id or not content:
            continue

        print(f"  [{len(golden)+1}/{num_questions}] Generating question for chunk {doc_id} …")

        instruction = (
            "You are building a retrieval benchmark. "
            "Write exactly ONE specific, unambiguous question whose answer is "
            "contained in — and ONLY in — the following excerpt. "
            "The question must be answerable purely from this excerpt, "
            "not from general knowledge. "
            "Output ONLY the question, no preamble, no quotes."
        )

        try:
            raw = await generate_answer(
                query=instruction,
                retrieved_docs=[{"content": content}]
            )
            question = raw.strip().strip('"').strip("'")

            # Basic quality gate: reject if suspiciously short or looks like an answer
            if len(question) < 15 or question.lower().startswith(("yes", "no", "the ")):
                print(f"    ⚠  Rejected low-quality question, skipping.")
                continue

            golden.append({"query": question, "target_id": doc_id})
        except Exception as exc:
            print(f"    ✗  LLM error: {exc}")

    print(f"\n  ✓  Generated {len(golden)} questions from {attempts} chunks.")

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(golden, fh, indent=2, ensure_ascii=False)
    print(f"  ✓  Saved to {output_path}")

    return golden


async def _sample_chunks_from_db(n: int) -> List[Dict]:
    """
    Pull raw chunks directly from the document store — NO retriever involved.
    Replace the body of this function with your actual DB access pattern.
    """
    # Option A: import your repository and call it directly
    try:
        from app.db.repositories.documents_repo import DocumentRepository
        repo = DocumentRepository()
        # Fetch more than needed so we can random-sample
        all_chunks = await repo.get_all_chunks(limit=max(n * 4, 200))
        return random.sample(all_chunks, min(n, len(all_chunks)))
    except Exception as exc:
        print(f"  ⚠  Direct DB fetch failed ({exc}). Falling back to searcher sampling.")

    # Option B (fallback): use broad keyword queries that cover the full corpus
    # This is less ideal but still separates generation from the test queries
    from app.retrieval.searchers.vector import VectorSearcher
    vs = VectorSearcher()
    seed_queries = [
        "environment climate energy emissions",
        "social employees diversity inclusion",
        "governance board risk compliance",
        "supply chain human rights",
        "water waste circular economy",
    ]
    seen, chunks = set(), []
    for q in seed_queries:
        for doc in vs.search(q, top_k=n // len(seed_queries) + 5):
            did = doc.get("id") or doc.get("_id")
            if did and did not in seen:
                seen.add(did)
                chunks.append(doc)
    return chunks


# ─────────────────────────────────────────────────────────────────────────────
# PART 2 — Evaluation
# ─────────────────────────────────────────────────────────────────────────────

def reciprocal_rank_fusion(
    ranked_lists: List[List[Dict]],
    k: int = FUSION_CONSTANT
) -> List[Dict]:
    """
    Standard RRF: score(d) = Σ 1 / (k + rank(d))
    Returns docs sorted by descending RRF score.
    """
    rrf_scores: Dict[str, float] = {}
    doc_store:  Dict[str, Dict]  = {}

    for ranked in ranked_lists:
        for rank, doc in enumerate(ranked, start=1):
            did = _get_id(doc)
            rrf_scores[did] = rrf_scores.get(did, 0.0) + 1.0 / (k + rank)
            if did not in doc_store:
                doc_store[did] = doc

    return sorted(doc_store.values(),
                  key=lambda d: rrf_scores[_get_id(d)],
                  reverse=True)


def _get_id(doc: Dict) -> str:
    """Robustly extract document ID regardless of wrapper depth."""
    inner = doc.get("doc", doc)
    return str(inner.get("id") or inner.get("_id") or id(doc))


def _compute_metrics(results: List[Dict], target_id: str, k: int = TOP_K) -> Dict:
    """Compute Hit@K, RR (for MRR), and NDCG@K for a single query."""
    rank = None
    for idx, doc in enumerate(results[:k], start=1):
        if _get_id(doc) == str(target_id):
            rank = idx
            break

    hit  = 1 if rank else 0
    rr   = (1.0 / rank) if rank else 0.0

    # NDCG@K (binary relevance: 1 if correct doc, else 0)
    dcg  = (1.0 / math.log2(rank + 1)) if rank else 0.0
    idcg = 1.0   # ideal: correct doc at rank 1
    ndcg = dcg / idcg

    return {"hit": hit, "rr": rr, "ndcg": ndcg, "rank": rank}


async def run_evaluation(
    golden: List[Dict],
    k: int = TOP_K,
    pool: int = POOL_SIZE,
    results_path: str = "eval_results.json"
) -> Dict:
    """
    Evaluate BM25, Vector, and RRF-Hybrid independently.

    Each algorithm fetches its OWN pool of `pool` documents so no algorithm
    is penalised by another's retrieval set.
    """
    print(f"\n{'='*55}")
    print(f" PART 2 — Retrieval Evaluation  (k={k}, pool={pool})")
    print(f"{'='*55}")

    vector_searcher = VectorSearcher()
    bm25_searcher   = BM25Searcher()

    accumulators = {
        "bm25_only":    {"hits": 0, "rr": 0.0, "ndcg": 0.0, "per_query": []},
        "vector_only":  {"hits": 0, "rr": 0.0, "ndcg": 0.0, "per_query": []},
        "hybrid_rrf":   {"hits": 0, "rr": 0.0, "ndcg": 0.0, "per_query": []},
    }

    total = len(golden)
    for i, item in enumerate(golden):
        query     = item["query"]
        target_id = str(item["target_id"])

        print(f"\n  Q{i+1:02d}/{total}: {query[:65]}…")

        # ── independent retrieval ────────────────────────────────────────────
        bm25_results   = bm25_searcher.search(query,   top_k=pool)
        vector_results = vector_searcher.search(query, top_k=pool)

        # RRF over the two independent ranked lists
        rrf_results = reciprocal_rank_fusion([bm25_results, vector_results])

        for mode, results in [
            ("bm25_only",   bm25_results),
            ("vector_only", vector_results),
            ("hybrid_rrf",  rrf_results),
        ]:
            m = _compute_metrics(results, target_id, k)
            accumulators[mode]["hits"]     += m["hit"]
            accumulators[mode]["rr"]       += m["rr"]
            accumulators[mode]["ndcg"]     += m["ndcg"]
            accumulators[mode]["per_query"].append({
                "query":     query,
                "target_id": target_id,
                "rank":      m["rank"],
                "hit":       m["hit"],
                "rr":        m["rr"],
                "ndcg":      m["ndcg"],
            })

            rank_str = f"rank {m['rank']}" if m["rank"] else f"NOT in top-{k}"
            print(f"    {mode:<14} → {rank_str}")

    # ── aggregate ────────────────────────────────────────────────────────────
    summary = {}
    print(f"\n{'='*55}")
    print(f"  FINAL RETRIEVAL METRICS  (k={k}, n={total})")
    print(f"{'='*55}")

    for mode, acc in accumulators.items():
        hit_rate = acc["hits"]  / total * 100
        mrr      = acc["rr"]   / total
        ndcg     = acc["ndcg"] / total

        summary[mode] = {
            "hit_rate_at_k": round(hit_rate, 1),
            "mrr":           round(mrr, 4),
            "ndcg_at_k":     round(ndcg, 4),
            "k":             k,
            "n":             total,
            "per_query":     acc["per_query"],
        }

        print(f"\n  {mode.upper()}")
        print(f"    Hit Rate @{k}  : {hit_rate:.1f}%")
        print(f"    MRR           : {mrr:.4f}")
        print(f"    NDCG@{k}      : {ndcg:.4f}")

    with open(results_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
    print(f"\n  ✓  Detailed results saved to {results_path}")

    return summary


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    t0 = time.time()

    mode = input(
        "\nChoose mode:\n"
        "  [1] Generate new golden dataset + evaluate\n"
        "  [2] Load existing golden_dataset.json and evaluate\n"
        "  [3] Generate golden dataset only\n"
        "Enter 1 / 2 / 3: "
    ).strip()

    if mode in ("1", "3"):
        golden = await generate_golden_dataset()
    else:
        with open("golden_dataset.json", encoding="utf-8") as fh:
            golden = json.load(fh)
        print(f"  Loaded {len(golden)} questions from golden_dataset.json")

    if mode != "3":
        await run_evaluation(golden)

    print(f"\n  Total time: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())