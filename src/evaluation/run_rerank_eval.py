"""
Evaluation script for Cross-Encoder Reranker (BAAI/bge-reranker-base).
Evaluates Hit@1, Hit@3, and compares BM25, Dense, Hybrid, and Reranked ranks.
"""

import json
from pathlib import Path
from src.retrieval.rerank import search as rerank_search
from src.retrieval.hybrid_search import search as hybrid_search

EVAL_FILE = Path("data/eval/questions.json")


def run_rerank_evaluation():
    if not EVAL_FILE.exists():
        raise FileNotFoundError(f"Evaluation file not found: {EVAL_FILE}")

    with open(EVAL_FILE, "r", encoding="utf-8") as f:
        questions = json.load(f)

    total_questions = len(questions)
    hit_at_1_count = 0
    hit_at_3_count = 0

    comparison_records = []

    print("=" * 95)
    print("CROSS-ENCODER RERANKER EVALUATION (BAAI/bge-reranker-base)")
    print(f"Total Questions: {total_questions}")
    print("=" * 95)

    for i, item in enumerate(questions, 1):
        q = item["question"]
        expected = item["expected_chunk_id"]

        # Retrieve top 5 reranked candidates from top-5 hybrid candidates
        reranked_results = rerank_search(q, k=5, top_n_hybrid=5)
        top3_ids = [r["chunk_id"] for r in reranked_results[:3]]

        # Determine reranked rank of expected chunk
        rerank_rank = next(
            (idx for idx, r in enumerate(reranked_results, 1) if r["chunk_id"] == expected),
            None,
        )

        is_rank_1 = (rerank_rank == 1)
        in_top_3 = (rerank_rank is not None and rerank_rank <= 3)

        if is_rank_1:
            hit_at_1_count += 1
        if in_top_3:
            hit_at_3_count += 1

        rank_1_str = "YES" if is_rank_1 else "NO"
        top_3_str = "YES" if in_top_3 else "NO"

        print(f"\nQ{i}: \"{q}\"")
        print(f"  Expected:       {expected}")
        print(f"  Rank 1 Hit:     {rank_1_str}")
        print(f"  Top 3 Hit:      {top_3_str}")
        print(f"  Reranked Rank:  {rerank_rank if rerank_rank else '>5'}")
        print("  Top-3 Retrieved (Reranked):")
        for rank, res in enumerate(reranked_results[:3], 1):
            mark = "(*)" if res["chunk_id"] == expected else "   "
            print(
                f"    {rank}. {mark} [Score: {res['score']:>8.4f}] {res['chunk_id']} "
                f"(Hybrid rank: {res['hybrid_rank']}) - {res['citation']}"
            )

        # Full hybrid search to get baseline BM25, Dense, and Hybrid ranks
        all_hybrid = hybrid_search(q, k=11)
        exp_hybrid_rec = next((r for r in all_hybrid if r["chunk_id"] == expected), None)
        hybrid_rank = next((idx for idx, r in enumerate(all_hybrid, 1) if r["chunk_id"] == expected), None)
        bm25_rank = exp_hybrid_rec["bm25_rank"] if exp_hybrid_rec else None
        dense_rank = exp_hybrid_rec["dense_rank"] if exp_hybrid_rec else None

        comparison_records.append({
            "index": i,
            "question": q,
            "expected": expected,
            "bm25_rank": bm25_rank,
            "dense_rank": dense_rank,
            "hybrid_rank": hybrid_rank,
            "rerank_rank": rerank_rank,
        })

    hit_at_1_pct = (hit_at_1_count / total_questions) * 100 if total_questions else 0.0
    hit_at_3_pct = (hit_at_3_count / total_questions) * 100 if total_questions else 0.0

    print("\n" + "=" * 95)
    print("RERANKER EVALUATION SUMMARY")
    print("=" * 95)
    print(f"Hit@1: {hit_at_1_count}/{total_questions} ({hit_at_1_pct:.1f}%)")
    print(f"Hit@3: {hit_at_3_count}/{total_questions} ({hit_at_3_pct:.1f}%)")
    print("=" * 95)

    # Comparison table
    print("\n" + "=" * 95)
    print("RANK COMPARISON: BM25 vs DENSE vs HYBRID vs RERANK")
    print("=" * 95)
    header = f"{'#':<4} | {'Question':<42} | {'BM25':<6} | {'Dense':<6} | {'Hybrid':<6} | {'Rerank':<6}"
    print(header)
    print("-" * len(header))
    for rec in comparison_records:
        q_trunc = rec["question"] if len(rec["question"]) <= 42 else rec["question"][:39] + "..."
        b_str = str(rec["bm25_rank"]) if rec["bm25_rank"] is not None else "N/A"
        d_str = str(rec["dense_rank"]) if rec["dense_rank"] is not None else "N/A"
        h_str = str(rec["hybrid_rank"]) if rec["hybrid_rank"] is not None else "N/A"
        r_str = str(rec["rerank_rank"]) if rec["rerank_rank"] is not None else ">5"
        print(f"Q{rec['index']:<3} | {q_trunc:<42} | {b_str:<6} | {d_str:<6} | {h_str:<6} | {r_str:<6}")
    print("=" * 95)


if __name__ == "__main__":
    run_rerank_evaluation()
