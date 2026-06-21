"""Generate 100K diverse prompts to exercise every cache layer.

Prompt categories (designed to trigger specific pipeline behaviors):
- exact_repeat: Same query verbatim → Exact Cache HIT
- minor_rephrase: Trivial rewording → Semantic Direct HIT (>=0.92)
- related_topic: Same domain, different scope → Semantic PARTIAL (0.75-0.92)
- comparison: "Compare X vs Y" → Composable Cache
- follow_up: Conversational continuation → Semantic PARTIAL + context
- novel: Completely new topic → Full LLM generation (builds cache)
- fuzzy_variant: Same words, different order → Fuzzy Match
"""

import random
import json
import hashlib
from pathlib import Path

TOPICS = [
    "data privacy", "cybersecurity", "HIPAA compliance", "GDPR requirements",
    "SOC 2 principles", "encryption standards", "access control",
    "network security", "cloud computing", "API security",
    "authentication protocols", "zero trust architecture",
    "incident response", "vulnerability management", "penetration testing",
    "data classification", "identity management", "firewall rules",
    "backup strategies", "disaster recovery", "compliance auditing",
    "risk assessment", "security awareness training", "endpoint protection",
    "supply chain security", "container security", "DevSecOps",
    "threat modeling", "security operations center", "log management",
]

STATES = ["CA", "TX", "NY", "FL", "CO", "WA", "IL", "PA", "OH", "GA",
          "NC", "MI", "NJ", "VA", "AZ", "MA", "TN", "IN", "MO", "MD"]

STATE_NAMES = {
    "CA": "California", "TX": "Texas", "NY": "New York", "FL": "Florida",
    "CO": "Colorado", "WA": "Washington", "IL": "Illinois", "PA": "Pennsylvania",
    "OH": "Ohio", "GA": "Georgia", "NC": "North Carolina", "MI": "Michigan",
    "NJ": "New Jersey", "VA": "Virginia", "AZ": "Arizona", "MA": "Massachusetts",
    "TN": "Tennessee", "IN": "Indiana", "MO": "Missouri", "MD": "Maryland",
}

QUESTION_TEMPLATES = [
    "What is {topic}?",
    "Explain {topic}",
    "Tell me about {topic}",
    "What are the key principles of {topic}?",
    "How does {topic} work?",
    "What are the requirements for {topic}?",
    "Describe {topic} in detail",
    "What are best practices for {topic}?",
    "What are the main components of {topic}?",
    "Why is {topic} important?",
]

REPHRASE_TEMPLATES = [
    "Can you explain {topic}?",
    "I'd like to know about {topic}",
    "What should I know about {topic}?",
    "Give me an overview of {topic}",
    "Help me understand {topic}",
    "What does {topic} involve?",
    "Break down {topic} for me",
]

FOLLOW_UP_TEMPLATES = [
    "Tell me more about that",
    "What else can you tell me about {topic}?",
    "How does that apply to {subtopic}?",
    "What about the {aspect} aspect?",
    "Can you go deeper on {topic}?",
    "What are the challenges with {topic}?",
    "How has {topic} evolved recently?",
]

COMPARISON_TEMPLATES = [
    "Compare {topic} in {state1} vs {state2}",
    "What are the differences between {topic} in {state1} and {state2}?",
    "Compare {topic_a} versus {topic_b}",
    "{topic} in {state1} compared to {state2}",
]

ASPECTS = ["implementation", "cost", "compliance", "enforcement",
           "penalties", "scope", "limitations", "benefits",
           "requirements", "timeline", "impact", "effectiveness"]

SUBTOPICS = {
    "data privacy": ["consent management", "data minimization", "right to delete", "data portability"],
    "cybersecurity": ["ransomware", "phishing", "DDoS", "insider threats"],
    "HIPAA compliance": ["PHI handling", "breach notification", "business associates", "minimum necessary"],
    "GDPR requirements": ["data processing agreements", "DPO requirements", "cross-border transfers", "consent"],
    "SOC 2 principles": ["trust services criteria", "type I vs type II", "audit process", "remediation"],
    "encryption standards": ["AES-256", "RSA", "TLS 1.3", "post-quantum"],
    "access control": ["RBAC", "ABAC", "least privilege", "MFA"],
    "network security": ["segmentation", "IDS/IPS", "VPN", "DNS security"],
    "cloud computing": ["shared responsibility", "multi-cloud", "serverless", "IaC"],
    "API security": ["OAuth 2.0", "rate limiting", "input validation", "API gateway"],
}


def generate_prompts(count: int = 100_000, seed: int = 42) -> list[dict]:
    """Generate a diverse prompt dataset.

    Distribution:
    - 15% exact repeats (cache warmers + exact hit tests)
    - 15% minor rephrases (semantic direct hit)
    - 15% related topics (semantic partial)
    - 10% comparisons (composable cache)
    - 10% follow-ups (conversation context)
    - 10% fuzzy variants (word reorder)
    - 25% novel queries (fresh LLM generation, builds cache)
    """
    rng = random.Random(seed)
    prompts = []
    # Track generated queries for exact repeat and rephrase pools
    generated_pool = []

    for i in range(count):
        r = rng.random()
        category = _pick_category(r)

        if category == "novel":
            prompt = _novel_prompt(rng)
            generated_pool.append(prompt["message"])

        elif category == "exact_repeat" and generated_pool:
            original = rng.choice(generated_pool)
            prompt = {"message": original, "category": "exact_repeat", "index": i}

        elif category == "minor_rephrase":
            topic = rng.choice(TOPICS)
            template = rng.choice(REPHRASE_TEMPLATES)
            prompt = {
                "message": template.format(topic=topic),
                "category": "minor_rephrase",
                "index": i,
            }

        elif category == "related_topic":
            topic = rng.choice(TOPICS)
            if topic in SUBTOPICS:
                subtopic = rng.choice(SUBTOPICS[topic])
                prompt = {
                    "message": f"What about {subtopic} in the context of {topic}?",
                    "category": "related_topic",
                    "index": i,
                }
            else:
                aspect = rng.choice(ASPECTS)
                prompt = {
                    "message": f"What are the {aspect} aspects of {topic}?",
                    "category": "related_topic",
                    "index": i,
                }

        elif category == "comparison":
            prompt = _comparison_prompt(rng)

        elif category == "follow_up":
            topic = rng.choice(TOPICS)
            template = rng.choice(FOLLOW_UP_TEMPLATES)
            subtopic = rng.choice(SUBTOPICS.get(topic, ASPECTS))
            aspect = rng.choice(ASPECTS)
            prompt = {
                "message": template.format(topic=topic, subtopic=subtopic, aspect=aspect),
                "category": "follow_up",
                "index": i,
            }

        elif category == "fuzzy_variant" and generated_pool:
            original = rng.choice(generated_pool)
            words = original.split()
            if len(words) > 3:
                rng.shuffle(words)
                prompt = {
                    "message": " ".join(words),
                    "category": "fuzzy_variant",
                    "index": i,
                }
            else:
                prompt = _novel_prompt(rng)
        else:
            prompt = _novel_prompt(rng)

        prompt["index"] = i
        prompts.append(prompt)

    return prompts


def _pick_category(r: float) -> str:
    if r < 0.15:
        return "exact_repeat"
    elif r < 0.30:
        return "minor_rephrase"
    elif r < 0.45:
        return "related_topic"
    elif r < 0.55:
        return "comparison"
    elif r < 0.65:
        return "follow_up"
    elif r < 0.75:
        return "fuzzy_variant"
    else:
        return "novel"


def _novel_prompt(rng) -> dict:
    topic = rng.choice(TOPICS)
    template = rng.choice(QUESTION_TEMPLATES)
    msg = template.format(topic=topic)
    return {"message": msg, "category": "novel"}


def _comparison_prompt(rng) -> dict:
    template = rng.choice(COMPARISON_TEMPLATES)
    topic = rng.choice(TOPICS)

    if "{state1}" in template:
        s1, s2 = rng.sample(STATES, 2)
        msg = template.format(
            topic=topic, state1=s1, state2=s2,
            topic_a=topic, topic_b=rng.choice(TOPICS),
        )
    elif "{topic_a}" in template:
        t1, t2 = rng.sample(TOPICS, 2)
        msg = template.format(topic_a=t1, topic_b=t2, topic=topic,
                              state1="CA", state2="TX")
    else:
        msg = template.format(topic=topic, state1=rng.choice(STATES),
                              state2=rng.choice(STATES),
                              topic_a=topic, topic_b=rng.choice(TOPICS))
    return {"message": msg, "category": "comparison"}


if __name__ == "__main__":
    prompts = generate_prompts(100_000)

    # Stats
    from collections import Counter
    cats = Counter(p["category"] for p in prompts)
    print(f"Generated {len(prompts)} prompts:")
    for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count} ({count/len(prompts)*100:.1f}%)")

    # Write to file
    out = Path(__file__).parent / "prompts_100k.jsonl"
    with open(out, "w") as f:
        for p in prompts:
            f.write(json.dumps(p) + "\n")
    print(f"\nWritten to {out}")
