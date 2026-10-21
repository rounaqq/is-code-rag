"""
Evaluation script for BM25 retrieval against benchmark questions.
Calculates Hit@1 and Hit@3 metrics.
"""

import json
from pathlib import Path
from src.retrieval.bm25_search import search

EVAL_FILE = Path("data/eval/questions.json")


def run_evaluation():
    if not EVAL_FILE.exists():
        raise FileNotFoundError(f"Evaluation file not found: {EVAL_FILE}")

    with open(EVAL_FILE, "r", encoding="utf-8") as f:
        questions = json.load(f)

    total_questions = len(questions)
    hit_at_1_count = 0
    hit_at_3_count = 0

    print("=" * 80)
    print("BM25 RETRIEVAL EVALUATION")
    print(f"Total Questions: {total_questions}")
    print("=" * 80)

    for i, item in enumerate(questions, 1):
        q = item["question"]
        expected = item["expected_chunk_id"]

        results = search(q, k=3)
        retrieved_ids = [r["chunk_id"] for r in results]

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
        print("  Top-3 Retrieved:")
        for rank, res in enumerate(results, 1):
            mark = "(*)" if res["chunk_id"] == expected else "   "
            print(f"    {rank}. {mark} [{res['score']:.4f}] {res['chunk_id']} ({res['citation']})")

    hit_at_1_pct = (hit_at_1_count / total_questions) * 100 if total_questions else 0.0
    hit_at_3_pct = (hit_at_3_count / total_questions) * 100 if total_questions else 0.0

    print("\n" + "=" * 80)
    print("FINAL METRICS")
    print("=" * 80)
    print(f"Hit@1: {hit_at_1_count}/{total_questions} ({hit_at_1_pct:.1f}%)")
    print(f"Hit@3: {hit_at_3_count}/{total_questions} ({hit_at_3_pct:.1f}%)")
    print("=" * 80)


if __name__ == "__main__":
    run_evaluation()
