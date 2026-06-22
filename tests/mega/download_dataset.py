#!/usr/bin/env python3
"""Download and prepare MS MARCO + Dolly-15k datasets for BitMod mega test.

Outputs:
  tests/mega/data/training_pairs.jsonl   — Q&A pairs for ingestion as cache seed
  tests/mega/data/exact_queries.jsonl    — Exact repeats (should be 100% cache hit)
  tests/mega/data/rephrase_queries.jsonl — Paraphrased queries (semantic matching)
  tests/mega/data/novel_queries.jsonl    — Novel queries (full LLM generation)
"""

import json
import random
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

SEED = 42
random.seed(SEED)

# Target counts
TRAINING_PAIRS = 1000   # Q&A pairs to ingest
EXACT_QUERIES = 200     # Exact repeats from training
REPHRASE_QUERIES = 300  # Paraphrased versions
NOVEL_QUERIES = 500     # Novel questions never seen

def download_ms_marco():
    """Download MS MARCO QA dev set via HuggingFace datasets."""
    print("Downloading MS MARCO v2.1 (QA dev set)...")
    from datasets import load_dataset
    ds = load_dataset("microsoft/ms_marco", "v2.1", split="validation")
    print(f"  Loaded {len(ds)} records")
    return ds

def download_dolly():
    """Download Databricks Dolly-15k."""
    print("Downloading Dolly-15k...")
    from datasets import load_dataset
    ds = load_dataset("databricks/databricks-dolly-15k", split="train")
    print(f"  Loaded {len(ds)} records")
    return ds

def extract_marco_pairs(ds, n=2000):
    """Extract high-quality Q&A pairs from MS MARCO."""
    pairs = []
    for row in ds:
        query = row.get("query", "").strip()
        # MS MARCO has 'answers' as a list; take the first well-formed one
        answers = row.get("answers", [])
        if not answers:
            continue
        answer = answers[0].strip() if answers[0] else ""
        if not query or not answer or answer == "No Answer Present.":
            continue
        if len(query) < 10 or len(answer) < 20:
            continue
        pairs.append({"question": query, "answer": answer, "source": "ms_marco"})
        if len(pairs) >= n:
            break
    return pairs

def extract_dolly_pairs(ds, n=500):
    """Extract instruction/response pairs from Dolly-15k."""
    pairs = []
    for row in ds:
        instruction = row.get("instruction", "").strip()
        response = row.get("response", "").strip()
        context = row.get("context", "").strip()
        if not instruction or not response:
            continue
        if len(instruction) < 10 or len(response) < 20:
            continue
        pairs.append({
            "question": instruction,
            "answer": response,
            "context": context[:500] if context else "",
            "source": "dolly_15k",
            "category": row.get("category", ""),
        })
        if len(pairs) >= n:
            break
    return pairs

# ─── Rephrase generation (deterministic, no LLM needed) ──────────

REPHRASE_TEMPLATES = [
    lambda q: f"Can you explain {q.lower().rstrip('?')}?",
    lambda q: f"What do you know about {q.lower().rstrip('?')}?",
    lambda q: f"Tell me about {q.lower().rstrip('?')}",
    lambda q: f"I'd like to understand {q.lower().rstrip('?')}",
    lambda q: f"Please describe {q.lower().rstrip('?')}",
    lambda q: q.replace("what is", "define").replace("What is", "Define") if "what is" in q.lower() else f"Explain: {q}",
    lambda q: q.replace("how", "in what way").replace("How", "In what way") if q.lower().startswith("how") else f"How would you describe {q.lower().rstrip('?')}?",
    lambda q: f"{q.rstrip('?')} — give me a detailed answer",
    lambda q: f"Quick question: {q}",
    lambda q: f"I need info on {q.lower().rstrip('?')}",
]

def generate_rephrases(pairs, n=300):
    """Generate deterministic paraphrases of training queries."""
    rephrases = []
    source_pairs = random.sample(pairs, min(n, len(pairs)))
    for i, pair in enumerate(source_pairs):
        template = REPHRASE_TEMPLATES[i % len(REPHRASE_TEMPLATES)]
        rephrased = template(pair["question"])
        rephrases.append({
            "question": rephrased,
            "original_question": pair["question"],
            "expected_answer": pair["answer"],
            "rephrase_type": f"template_{i % len(REPHRASE_TEMPLATES)}",
        })
    return rephrases

def write_jsonl(path, records):
    """Write records as JSONL."""
    with open(path, "w") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"  Wrote {len(records)} records to {path}")

def main():
    print("=" * 60)
    print("BitMod Mega Test — Dataset Preparation")
    print("=" * 60)

    # Download
    marco_ds = download_ms_marco()
    dolly_ds = download_dolly()

    # Extract pairs
    print("\nExtracting Q&A pairs...")
    marco_pairs = extract_marco_pairs(marco_ds, n=1500)
    dolly_pairs = extract_dolly_pairs(dolly_ds, n=500)
    print(f"  MS MARCO: {len(marco_pairs)} pairs")
    print(f"  Dolly-15k: {len(dolly_pairs)} pairs")

    # Combine and shuffle
    all_pairs = marco_pairs + dolly_pairs
    random.shuffle(all_pairs)

    # Split into training (ingested) and novel (never seen)
    training = all_pairs[:TRAINING_PAIRS]
    novel_pool = all_pairs[TRAINING_PAIRS:]

    # Exact queries = random subset of training questions
    exact_indices = random.sample(range(len(training)), min(EXACT_QUERIES, len(training)))
    exact_queries = [{"question": training[i]["question"], "expected_cached": True} for i in exact_indices]

    # Rephrase queries
    rephrase_queries = generate_rephrases(training, n=REPHRASE_QUERIES)

    # Novel queries
    novel_queries = [{"question": p["question"], "expected_cached": False} for p in novel_pool[:NOVEL_QUERIES]]

    # Write outputs
    print("\nWriting test data...")
    write_jsonl(DATA_DIR / "training_pairs.jsonl", training)
    write_jsonl(DATA_DIR / "exact_queries.jsonl", exact_queries)
    write_jsonl(DATA_DIR / "rephrase_queries.jsonl", rephrase_queries)
    write_jsonl(DATA_DIR / "novel_queries.jsonl", novel_queries)

    # Summary
    print("\n" + "=" * 60)
    print("Dataset Summary:")
    print(f"  Training pairs (for ingestion): {len(training)}")
    print(f"  Exact repeat queries:           {len(exact_queries)}")
    print(f"  Paraphrased queries:            {len(rephrase_queries)}")
    print(f"  Novel queries:                  {len(novel_queries)}")
    print(f"  Total test queries:             {len(exact_queries) + len(rephrase_queries) + len(novel_queries)}")
    print(f"\n  Data directory: {DATA_DIR}")
    print("=" * 60)

if __name__ == "__main__":
    main()
