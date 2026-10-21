"""
Evaluation script for Dense (Embedding-based) Retrieval against benchmark questions.
Compares BM25 rank vs Dense rank for each question.
"""

import json
from pathlib import Path
from src.retrieval.dense_search import search as dense_search
from src.retrieval.bm25_search import search as bm25_search

EVAL_FILE = Path("data/eval/questions.json")


def run_dense_evaluation():
    if not EVAL_FILE.exists():
        raise FileNotFoundError(f"Evaluation file not found: {EVAL_FILE}")

    with open(EVAL_FILE, "r", encoding="utf-8") as f:
        questions = json.load(f)

    total_questions = len(questions)
    hit_at_1_count = 0
    hit_at_3_count = 0

    comparison_records = []

    print("=" * 80)
    print("DENSE RETRIEVAL EVALUATION (BAAI/bge-small-en-v1.5)")
    print(f"Total Questions: {total_questions}")
    print("=" * 80)

    for i, item in enumerate(questions, 1):
        q = item["question"]
        expected = item["expected_chunk_id"]

        # Dense top-3 search for evaluation metrics
        dense_top3 = dense_search(q, k=3)
        retrieved_ids = [r["chunk_id"] for r in dense_top3]

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
        print("  Top-3 Retrieved (Dense):")
        for rank, res in enumerate(dense_top3, 1):
            mark = "(*)" if res["chunk_id"] == expected else "   "
            print(f"    {rank}. {mark} [{res['score']:.4f}] {res['chunk_id']} ({res['citation']})")

        # Full rankings for comparison table (11 chunks total)
        all_dense = dense_search(q, k=11)
        dense_rank = next((idx for idx, r in enumerate(all_dense, 1) if r["chunk_id"] == expected), None)

        all_bm25 = bm25_search(q, k=11)
        bm25_rank = next((idx for idx, r in enumerate(all_bm25, 1) if r["chunk_id"] == expected), None)

        comparison_records.append({
            "index": i,
            "question": q,
            "expected": expected,
            "bm25_rank": bm25_rank,
            "dense_rank": dense_rank,
        })

    hit_at_1_pct = (hit_at_1_count / total_questions) * 100 if total_questions else 0.0
    hit_at_3_pct = (hit_at_3_count / total_questions) * 100 if total_questions else 0.0

    print("\n" + "=" * 80)
    print("DENSE EVALUATION SUMMARY")
    print("=" * 80)
    print(f"Hit@1: {hit_at_1_count}/{total_questions} ({hit_at_1_pct:.1f}%)")
    print(f"Hit@3: {hit_at_3_count}/{total_questions} ({hit_at_3_pct:.1f}%)")
    print("=" * 80)

    # Comparison table
    print("\n" + "=" * 80)
    print("RANK COMPARISON: BM25 vs DENSE (BAAI/bge-small-en-v1.5)")
    print("=" * 80)
    header = f"{'#':<4} | {'Question':<55} | {'BM25':<6} | {'Dense':<6}"
    print(header)
    print("-" * len(header))
    for rec in comparison_records:
        q_trunc = rec["question"] if len(rec["question"]) <= 55 else rec["question"][:52] + "..."
        b_str = str(rec["bm25_rank"]) if rec["bm25_rank"] is not None else "N/A"
        d_str = str(rec["dense_rank"]) if rec["dense_rank"] is not None else "N/A"
        print(f"Q{rec['index']:<3} | {q_trunc:<55} | {b_str:<6} | {d_str:<6}")
    print("=" * 80)


if __name__ == "__main__":
    run_dense_evaluation()
