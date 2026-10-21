"""
Evaluation script for Hybrid Retrieval (BM25 + Dense with RRF, k=60).
Evaluates Hit@1, Hit@3, and compares BM25, Dense, and Hybrid ranks for benchmark questions.
"""

import json
from pathlib import Path
from src.retrieval.hybrid_search import search as hybrid_search

EVAL_FILE = Path("data/eval/questions.json")


def run_hybrid_evaluation():
    if not EVAL_FILE.exists():
        raise FileNotFoundError(f"Evaluation file not found: {EVAL_FILE}")

    with open(EVAL_FILE, "r", encoding="utf-8") as f:
        questions = json.load(f)

    total_questions = len(questions)
    hit_at_1_count = 0
    hit_at_3_count = 0

    comparison_records = []

    print("=" * 85)
    print("HYBRID RETRIEVAL EVALUATION (BM25 + Dense RRF, k=60)")
    print(f"Total Questions: {total_questions}")
    print("=" * 85)

    for i, item in enumerate(questions, 1):
        q = item["question"]
        expected = item["expected_chunk_id"]

        # Top-3 hybrid retrieval for evaluation metrics
        top3_results = hybrid_search(q, k=3)
        retrieved_ids = [r["chunk_id"] for r in top3_results]

        is_rank_1 = len(retrieved_ids) > 0 and retrieved_ids[0] == expected
        in_top_3 = expected in retrieved_ids

        if is_rank_1:
            hit_at_1_count += 1
        if in_top_3:
            hit_at_3_count += 1

        rank_1_str = "YES" if is_rank_1 else "NO"
        top_3_str = "YES" if in_top_3 else "NO"

        print(f"\nQ{i}: \"{q}\"")
        print(f"  Expected:    {expected}")
        print(f"  Rank 1 Hit:  {rank_1_str}")
        print(f"  Top 3 Hit:   {top_3_str}")
        print("  Top-3 Retrieved (Hybrid):")
        for rank, res in enumerate(top3_results, 1):
            mark = "(*)" if res["chunk_id"] == expected else "   "
            print(
                f"    {rank}. {mark} [{res['score']:.6f}] {res['chunk_id']} "
                f"(BM25: {res['bm25_rank']}, Dense: {res['dense_rank']}) - {res['citation']}"
            )

        # Full ranking to determine exact ranks for the expected chunk
        all_results = hybrid_search(q, k=11)
        expected_rec = next((r for r in all_results if r["chunk_id"] == expected), None)
        hybrid_rank = next((idx for idx, r in enumerate(all_results, 1) if r["chunk_id"] == expected), None)
        bm25_rank = expected_rec["bm25_rank"] if expected_rec else None
        dense_rank = expected_rec["dense_rank"] if expected_rec else None

        comparison_records.append({
            "index": i,
            "question": q,
            "expected": expected,
            "bm25_rank": bm25_rank,
            "dense_rank": dense_rank,
            "hybrid_rank": hybrid_rank,
        })

    hit_at_1_pct = (hit_at_1_count / total_questions) * 100 if total_questions else 0.0
    hit_at_3_pct = (hit_at_3_count / total_questions) * 100 if total_questions else 0.0

    print("\n" + "=" * 85)
    print("HYBRID EVALUATION SUMMARY")
    print("=" * 85)
    print(f"Hit@1: {hit_at_1_count}/{total_questions} ({hit_at_1_pct:.1f}%)")
    print(f"Hit@3: {hit_at_3_count}/{total_questions} ({hit_at_3_pct:.1f}%)")
    print("=" * 85)

    # Comparison table
    print("\n" + "=" * 85)
    print("RANK COMPARISON: BM25 vs DENSE vs HYBRID (RRF k=60)")
    print("=" * 85)
    header = f"{'#':<4} | {'Question':<48} | {'BM25':<6} | {'Dense':<6} | {'Hybrid':<6}"
    print(header)
    print("-" * len(header))
    for rec in comparison_records:
        q_trunc = rec["question"] if len(rec["question"]) <= 48 else rec["question"][:45] + "..."
        b_str = str(rec["bm25_rank"]) if rec["bm25_rank"] is not None else "N/A"
        d_str = str(rec["dense_rank"]) if rec["dense_rank"] is not None else "N/A"
        h_str = str(rec["hybrid_rank"]) if rec["hybrid_rank"] is not None else "N/A"
        print(f"Q{rec['index']:<3} | {q_trunc:<48} | {b_str:<6} | {d_str:<6} | {h_str:<6}")
    print("=" * 85)


if __name__ == "__main__":
    run_hybrid_evaluation()
