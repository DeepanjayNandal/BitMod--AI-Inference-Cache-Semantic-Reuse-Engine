"""Configure Bitmod with a specific LLM provider.

Set one of these env var combos before running:
  Anthropic:  export ANTHROPIC_API_KEY=sk-ant-...
  OpenAI:     export OPENAI_API_KEY=sk-...
  Groq:       export GROQ_API_KEY=gsk_...
  Ollama:     (no key needed, just run `ollama serve`)
"""
from __future__ import annotations

from bitmod import Bitmod

# Option A: auto-detect from env vars (picks first available key)
bm = Bitmod()

# Option B: explicit provider via kwargs
# bm = Bitmod(llm_provider="anthropic", llm_model="claude-sonnet-4-20250514")
# bm = Bitmod(llm_provider="openai", llm_model="gpt-4o")
# bm = Bitmod(llm_provider="groq", llm_model="llama-3.3-70b-versatile")
# bm = Bitmod(llm_provider="ollama", llm_model="llama3")

# Option C: use a bitmod.yaml config file
# bm = Bitmod(config_path="bitmod.yaml")

bm.ingest("The system processes returns within 5 business days.", title="Returns")

result = bm.query("How long do returns take?")
print(result.answer)
print(f"Provider: {result.model_used}")

status = bm.status()
print(f"Backend: {status.db_backend}  |  LLM: {status.llm_provider}  |  Docs: {status.documents}")

bm.close()
