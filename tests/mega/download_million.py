#!/usr/bin/env python3
"""Download and prepare 1M+ dataset for BitMod full-layer stress test.

Knowledge Corpus:
  - MS MARCO passages (10K documents for ingestion)
  - Natural Questions Wikipedia contexts (5K documents)

Query Workload (1M+ queries across all cache layers):
  - MS MARCO train queries (808K) — single-hop factoid
  - Natural Questions train queries (87K) — real Google queries
  - HotpotQA train queries (90K) — multi-hop reasoning
  - Synthetic composable queries (5K) — CA vs TX decomposition
  - Synthetic skip-LLM queries (2K) — extract/count/list/validate
  - Synthetic exact repeats (10K) — sampled from all sets
  - Synthetic paraphrases (10K) — template-based rephrase
  - Synthetic invalidation scenarios (1K) — double-verify testing

Total: ~1.01M queries + 15K knowledge documents

Outputs to tests/mega/data_1m/
"""

import json
import random
import re
import sys
import time
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data_1m"
DATA_DIR.mkdir(exist_ok=True)

SEED = 42
random.seed(SEED)


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ─── Download Functions ───────────────────────────────────────────

def download_msmarco_queries():
    """Download MS MARCO train queries with answers."""
    log("Downloading MS MARCO v2.1 train set (808K queries)...")
    from datasets import load_dataset
    ds = load_dataset("microsoft/ms_marco", "v2.1", split="train")
    log(f"  Loaded {len(ds)} MS MARCO train records")
    return ds


def download_msmarco_dev():
    """Download MS MARCO dev for passage extraction."""
    log("Downloading MS MARCO v2.1 dev set (101K)...")
    from datasets import load_dataset
    ds = load_dataset("microsoft/ms_marco", "v2.1", split="validation")
    log(f"  Loaded {len(ds)} MS MARCO dev records")
    return ds


def download_natural_questions():
    """Download NQ open-domain subset."""
    log("Downloading Natural Questions (open)...")
    from datasets import load_dataset
    ds = load_dataset("google-research-datasets/nq_open", split="train")
    log(f"  Loaded {len(ds)} NQ records")
    return ds


def download_hotpotqa():
    """Download HotpotQA for multi-hop queries."""
    log("Downloading HotpotQA (distractor)...")
    from datasets import load_dataset
    ds = load_dataset("hotpot_qa", "distractor", split="train")
    log(f"  Loaded {len(ds)} HotpotQA records")
    return ds


# ─── Knowledge Corpus Extraction ─────────────────────────────────

def extract_knowledge_corpus(msmarco_dev, nq_ds):
    """Extract unique passages/documents for ingestion."""
    log("Extracting knowledge corpus from MS MARCO passages + NQ...")

    documents = []
    seen_titles = set()

    # MS MARCO passages — each record has 'passages' with 'passage_text' and 'is_selected'
    for i, row in enumerate(msmarco_dev):
        passages = row.get("passages", {})
        texts = passages.get("passage_text", [])
        for j, text in enumerate(texts):
            if not text or len(text) < 100:
                continue
            # Use first 60 chars as pseudo-title
            title = text[:60].split(".")[0].strip()
            if title in seen_titles:
                continue
            seen_titles.add(title)
            documents.append({
                "title": title,
                "text": text,
                "source": "ms_marco",
                "domain": "general",
            })
            if len(documents) >= 10000:
                break
        if len(documents) >= 10000:
            break

    # NQ contexts — each record has 'question' and 'answer' (list)
    # NQ open doesn't have contexts, so we'll generate pseudo-documents from answers
    nq_count = 0
    for row in nq_ds:
        question = row.get("question", "")
        answers = row.get("answer", [])
        if not question or not answers:
            continue
        # Create a knowledge document from Q+A
        answer_text = "; ".join(answers) if isinstance(answers, list) else str(answers)
        doc_text = f"Question: {question}\nAnswer: {answer_text}"
        title = question[:60]
        if title not in seen_titles:
            seen_titles.add(title)
            documents.append({
                "title": title,
                "text": doc_text,
                "source": "natural_questions",
                "domain": "wikipedia",
            })
            nq_count += 1
        if nq_count >= 5000:
            break

    log(f"  Corpus: {len(documents)} documents ({len(documents) - nq_count} MS MARCO, {nq_count} NQ)")
    return documents


# ─── Query Extraction ─────────────────────────────────────────────

def extract_msmarco_queries(ds):
    """Extract all MS MARCO queries with valid answers."""
    log("Extracting MS MARCO queries...")
    queries = []
    for row in ds:
        query = row.get("query", "").strip()
        answers = row.get("answers", [])
        if not query or len(query) < 5:
            continue
        answer = ""
        if answers and answers[0] and answers[0] != "No Answer Present.":
            answer = answers[0].strip()
        queries.append({
            "question": query,
            "answer": answer,
            "source": "ms_marco",
            "type": "factoid",
        })
    log(f"  Extracted {len(queries)} MS MARCO queries")
    return queries


def extract_nq_queries(ds):
    """Extract Natural Questions."""
    log("Extracting Natural Questions...")
    queries = []
    for row in ds:
        question = row.get("question", "").strip()
        answers = row.get("answer", [])
        if not question:
            continue
        answer = "; ".join(answers) if isinstance(answers, list) else str(answers)
        queries.append({
            "question": question,
            "answer": answer,
            "source": "natural_questions",
            "type": "factoid",
        })
    log(f"  Extracted {len(queries)} NQ queries")
    return queries


def extract_hotpotqa_queries(ds):
    """Extract HotpotQA multi-hop queries with supporting facts."""
    log("Extracting HotpotQA multi-hop queries...")
    queries = []
    for row in ds:
        question = row.get("question", "").strip()
        answer = row.get("answer", "").strip()
        q_type = row.get("type", "")
        level = row.get("level", "")
        if not question or not answer:
            continue
        # Include supporting fact titles for composable testing
        sup_titles = []
        sf = row.get("supporting_facts", {})
        if isinstance(sf, dict):
            sup_titles = list(set(sf.get("title", [])))
        queries.append({
            "question": question,
            "answer": answer,
            "source": "hotpotqa",
            "type": "multi_hop",
            "hop_type": q_type,
            "level": level,
            "supporting_topics": sup_titles[:5],
        })
    log(f"  Extracted {len(queries)} HotpotQA queries")
    return queries


# ─── Synthetic Query Generators ───────────────────────────────────

US_STATES = [
    ("AL", "Alabama"), ("AK", "Alaska"), ("AZ", "Arizona"), ("AR", "Arkansas"),
    ("CA", "California"), ("CO", "Colorado"), ("CT", "Connecticut"), ("DE", "Delaware"),
    ("FL", "Florida"), ("GA", "Georgia"), ("HI", "Hawaii"), ("ID", "Idaho"),
    ("IL", "Illinois"), ("IN", "Indiana"), ("IA", "Iowa"), ("KS", "Kansas"),
    ("KY", "Kentucky"), ("LA", "Louisiana"), ("ME", "Maine"), ("MD", "Maryland"),
    ("MA", "Massachusetts"), ("MI", "Michigan"), ("MN", "Minnesota"), ("MS", "Mississippi"),
    ("MO", "Missouri"), ("MT", "Montana"), ("NE", "Nebraska"), ("NV", "Nevada"),
    ("NH", "New Hampshire"), ("NJ", "New Jersey"), ("NM", "New Mexico"), ("NY", "New York"),
    ("NC", "North Carolina"), ("ND", "North Dakota"), ("OH", "Ohio"), ("OK", "Oklahoma"),
    ("OR", "Oregon"), ("PA", "Pennsylvania"), ("RI", "Rhode Island"), ("SC", "South Carolina"),
    ("SD", "South Dakota"), ("TN", "Tennessee"), ("TX", "Texas"), ("UT", "Utah"),
    ("VT", "Vermont"), ("VA", "Virginia"), ("WA", "Washington"), ("WV", "West Virginia"),
    ("WI", "Wisconsin"), ("WY", "Wyoming"),
]

COMPARISON_TOPICS = [
    "employment laws", "minimum wage", "privacy laws", "DUI penalties",
    "gun laws", "landlord tenant laws", "workers compensation", "tax rates",
    "environmental regulations", "healthcare regulations", "marijuana legality",
    "child custody rules", "divorce laws", "property tax rates", "death penalty laws",
    "voting requirements", "education funding", "abortion laws", "immigration enforcement",
    "renewable energy incentives", "building codes", "zoning regulations",
    "occupational licensing", "non-compete agreements", "unemployment benefits",
    "workers rights", "whistleblower protections", "data privacy laws",
    "cybersecurity requirements", "insurance regulations", "banking laws",
    "real estate laws", "consumer protection", "food safety regulations",
    "animal welfare laws", "traffic laws", "juvenile justice",
    "domestic violence laws", "hate crime legislation", "public records laws",
]

TOPIC_COMPARISONS = [
    ("HIPAA", "GDPR"), ("SOC 2", "ISO 27001"), ("CCPA", "GDPR"),
    ("LLC", "S-Corp"), ("patent", "trademark"), ("NIST", "CIS Controls"),
    ("OSHA", "EPA regulations"), ("FHA", "VA loan"), ("401k", "IRA"),
    ("HTTP", "HTTPS"), ("TCP", "UDP"), ("SQL", "NoSQL"),
    ("REST", "GraphQL"), ("Docker", "Kubernetes"), ("React", "Angular"),
    ("Python", "JavaScript"), ("machine learning", "deep learning"),
    ("encryption", "hashing"), ("VPN", "proxy"), ("firewall", "IDS"),
]


def generate_composable_queries(n=5000):
    """Generate comparison queries that trigger composable decomposition."""
    log(f"Generating {n} composable comparison queries...")
    queries = []
    templates = [
        "Compare {topic} in {s1} vs {s2}",
        "Differences between {topic} in {s1} and {s2}",
        "{topic} {s1} versus {s2}",
        "How do {topic} differ in {s1} compared to {s2}",
        "Compare {topic} in {s1} vs {s2} vs {s3}",
        "{s1} and {s2} {topic} comparison",
        "Compare {t1} vs {t2}",
        "Differences between {t1} and {t2}",
        "{t1} versus {t2} comparison",
        "How does {t1} compare to {t2}",
    ]

    for i in range(n):
        template = templates[i % len(templates)]
        if "{s3}" in template:
            states = random.sample(US_STATES, 3)
            topic = COMPARISON_TOPICS[i % len(COMPARISON_TOPICS)]
            q = template.format(
                topic=topic,
                s1=random.choice([states[0][0], states[0][1]]),
                s2=random.choice([states[1][0], states[1][1]]),
                s3=random.choice([states[2][0], states[2][1]]),
            )
        elif "{t1}" in template:
            pair = TOPIC_COMPARISONS[i % len(TOPIC_COMPARISONS)]
            q = template.format(t1=pair[0], t2=pair[1])
        elif "{s1}" in template:
            states = random.sample(US_STATES, 2)
            topic = COMPARISON_TOPICS[i % len(COMPARISON_TOPICS)]
            q = template.format(
                topic=topic,
                s1=random.choice([states[0][0], states[0][1]]),
                s2=random.choice([states[1][0], states[1][1]]),
            )
        else:
            topic = COMPARISON_TOPICS[i % len(COMPARISON_TOPICS)]
            states = random.sample(US_STATES, 2)
            q = f"Compare {topic} in {states[0][1]} vs {states[1][1]}"

        queries.append({
            "question": q,
            "source": "synthetic",
            "type": "composable",
            "expected_layer": "composable_cache",
        })

    log(f"  Generated {len(queries)} composable queries")
    return queries


SKIP_LLM_TEMPLATES = [
    "Extract all {entity} from {topic}",
    "List all {entity} related to {topic}",
    "Count the number of {entity} in {topic}",
    "List the key {entity} for {topic}",
    "Extract the {entity} from {topic} documents",
    "Validate the {entity} in {topic}",
    "Count {entity} by {topic}",
    "List all {topic} {entity}",
    "Extract {entity} mentioned in {topic}",
    "How many {entity} are there for {topic}",
]

ENTITIES = [
    "sections", "requirements", "regulations", "penalties", "citations",
    "definitions", "procedures", "exceptions", "deadlines", "thresholds",
    "categories", "standards", "guidelines", "provisions", "clauses",
]

TOPICS = [
    "HIPAA", "GDPR", "SOC 2", "PCI DSS", "CCPA", "FERPA", "GLBA",
    "NIST 800-53", "ISO 27001", "OSHA", "ADA", "COPPA", "FCRA",
    "data classification", "access control", "encryption", "incident response",
    "business continuity", "risk assessment", "security awareness training",
    "vulnerability management", "network security", "cloud security",
    "identity management", "audit logging", "compliance monitoring",
]


def generate_skip_llm_queries(n=2000):
    """Generate queries that should trigger skip-LLM (deterministic intents)."""
    log(f"Generating {n} skip-LLM queries...")
    queries = []
    for i in range(n):
        template = SKIP_LLM_TEMPLATES[i % len(SKIP_LLM_TEMPLATES)]
        entity = ENTITIES[i % len(ENTITIES)]
        topic = TOPICS[i % len(TOPICS)]
        q = template.format(entity=entity, topic=topic)
        queries.append({
            "question": q,
            "source": "synthetic",
            "type": "skip_llm",
            "expected_layer": "skip_llm",
        })
    log(f"  Generated {len(queries)} skip-LLM queries")
    return queries


REPHRASE_TEMPLATES = [
    lambda q: f"Can you explain {q.lower().rstrip('?')}?",
    lambda q: f"What do you know about {q.lower().rstrip('?')}?",
    lambda q: f"Tell me about {q.lower().rstrip('?')}",
    lambda q: f"I'd like to understand {q.lower().rstrip('?')}",
    lambda q: f"Please describe {q.lower().rstrip('?')}",
    lambda q: f"Explain: {q}",
    lambda q: f"Quick question: {q}",
    lambda q: f"I need info on {q.lower().rstrip('?')}",
    lambda q: f"What's the deal with {q.lower().rstrip('?')}?",
    lambda q: f"Help me understand {q.lower().rstrip('?')}",
]


def generate_exact_repeats(all_queries, n=10000):
    """Sample queries for exact-repeat testing."""
    log(f"Generating {n} exact repeat queries...")
    sample = random.sample(all_queries, min(n, len(all_queries)))
    return [{"question": q["question"], "source": "exact_repeat", "type": "exact"} for q in sample]


def generate_paraphrases(all_queries, n=10000):
    """Generate paraphrased versions of existing queries."""
    log(f"Generating {n} paraphrase queries...")
    sample = random.sample(all_queries, min(n, len(all_queries)))
    paraphrases = []
    for i, q in enumerate(sample):
        template = REPHRASE_TEMPLATES[i % len(REPHRASE_TEMPLATES)]
        rephrased = template(q["question"])
        paraphrases.append({
            "question": rephrased,
            "original_question": q["question"],
            "source": "paraphrase",
            "type": "rephrase",
            "expected_layer": "semantic_cache",
        })
    return paraphrases


def generate_invalidation_scenarios(all_queries, n=1000):
    """Generate query pairs for double-verify invalidation testing."""
    log(f"Generating {n} invalidation scenario queries...")
    sample = random.sample(all_queries, min(n, len(all_queries)))
    scenarios = []
    for q in sample:
        scenarios.append({
            "question": q["question"],
            "source": "invalidation",
            "type": "invalidation",
            "phase": "seed",  # First ask to populate cache
        })
        scenarios.append({
            "question": q["question"],
            "source": "invalidation",
            "type": "invalidation",
            "phase": "verify",  # Re-ask after source change to test double-verify
        })
    return scenarios


# ─── Write Functions ──────────────────────────────────────────────

def write_jsonl(path, records):
    with open(path, "w") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    size_mb = path.stat().st_size / (1024 * 1024)
    log(f"  Wrote {len(records):,} records to {path.name} ({size_mb:.1f} MB)")


def main():
    t0 = time.time()
    print("=" * 70)
    print("  BitMod Million-Record Dataset Preparation")
    print("=" * 70)

    # ── Download all datasets ──
    msmarco_train = download_msmarco_queries()
    msmarco_dev = download_msmarco_dev()
    nq_ds = download_natural_questions()
    hotpot_ds = download_hotpotqa()

    # ── Extract knowledge corpus ──
    print("\n" + "-" * 70)
    corpus = extract_knowledge_corpus(msmarco_dev, nq_ds)
    write_jsonl(DATA_DIR / "knowledge_corpus.jsonl", corpus)

    # ── Extract real queries ──
    print("\n" + "-" * 70)
    msmarco_queries = extract_msmarco_queries(msmarco_train)
    nq_queries = extract_nq_queries(nq_ds)
    hotpot_queries = extract_hotpotqa_queries(hotpot_ds)

    # ── Generate synthetic queries ──
    print("\n" + "-" * 70)
    composable_queries = generate_composable_queries(5000)
    skip_llm_queries = generate_skip_llm_queries(2000)

    # Combine all real queries for sampling
    all_real_queries = msmarco_queries + nq_queries + hotpot_queries
    exact_queries = generate_exact_repeats(all_real_queries, 10000)
    rephrase_queries = generate_paraphrases(all_real_queries, 10000)
    invalidation_queries = generate_invalidation_scenarios(all_real_queries, 1000)

    # ── Write all query sets ──
    print("\n" + "-" * 70)
    log("Writing query datasets...")

    # Main query files
    write_jsonl(DATA_DIR / "msmarco_queries.jsonl", msmarco_queries)
    write_jsonl(DATA_DIR / "nq_queries.jsonl", nq_queries)
    write_jsonl(DATA_DIR / "hotpot_queries.jsonl", hotpot_queries)
    write_jsonl(DATA_DIR / "composable_queries.jsonl", composable_queries)
    write_jsonl(DATA_DIR / "skip_llm_queries.jsonl", skip_llm_queries)
    write_jsonl(DATA_DIR / "exact_queries.jsonl", exact_queries)
    write_jsonl(DATA_DIR / "rephrase_queries.jsonl", rephrase_queries)
    write_jsonl(DATA_DIR / "invalidation_queries.jsonl", invalidation_queries)

    # Combined master file (all queries shuffled)
    all_queries = (
        msmarco_queries + nq_queries + hotpot_queries +
        composable_queries + skip_llm_queries +
        exact_queries + rephrase_queries + invalidation_queries
    )
    random.shuffle(all_queries)
    write_jsonl(DATA_DIR / "all_queries.jsonl", all_queries)

    # ── Summary ──
    elapsed = time.time() - t0
    total_queries = len(all_queries)
    total_docs = len(corpus)

    print("\n" + "=" * 70)
    print("  DATASET SUMMARY")
    print("=" * 70)
    print(f"  Knowledge Corpus:        {total_docs:>10,} documents")
    print(f"  ─────────────────────────────────────────")
    print(f"  MS MARCO queries:        {len(msmarco_queries):>10,}")
    print(f"  Natural Questions:       {len(nq_queries):>10,}")
    print(f"  HotpotQA (multi-hop):    {len(hotpot_queries):>10,}")
    print(f"  Composable (synthetic):  {len(composable_queries):>10,}")
    print(f"  Skip-LLM (synthetic):    {len(skip_llm_queries):>10,}")
    print(f"  Exact repeats:           {len(exact_queries):>10,}")
    print(f"  Paraphrases:             {len(rephrase_queries):>10,}")
    print(f"  Invalidation scenarios:  {len(invalidation_queries):>10,}")
    print(f"  ─────────────────────────────────────────")
    print(f"  TOTAL QUERIES:           {total_queries:>10,}")
    print(f"  ─────────────────────────────────────────")
    print(f"  Elapsed: {elapsed:.0f}s ({elapsed/60:.1f}min)")
    print(f"  Data directory: {DATA_DIR}")
    print("=" * 70)


if __name__ == "__main__":
    main()
