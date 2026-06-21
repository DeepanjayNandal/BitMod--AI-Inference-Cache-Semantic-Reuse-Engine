#!/bin/bash
# Bitmod Docker quickstart.
# Clone the repo first: git clone https://github.com/OpenRights/bitmod && cd bitmod

# --- Minimal (SQLite, bring your own LLM key) ---
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
docker compose up -d

# --- With local Ollama (no API keys needed) ---
docker compose --profile ollama up -d

# --- With PostgreSQL + pgvector ---
docker compose --profile postgres up -d

# --- Full stack (Ollama + Postgres) ---
docker compose --profile ollama --profile postgres up -d

# Health check
curl -s http://localhost:8000/health | jq .

# Ingest via API
curl -s -X POST http://localhost:8000/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{"text": "Returns must be filed within 30 days.", "title": "Policy"}' | jq .

# Query via API
curl -s -X POST http://localhost:8000/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the return policy?"}' | jq '{answer, cached, model_used}'

# Status
curl -s http://localhost:8000/v1/status | jq .

# Cache stats
curl -s http://localhost:8000/v1/cache/stats | jq '{hit_rate, total_entries}'

# Tear down
docker compose down
