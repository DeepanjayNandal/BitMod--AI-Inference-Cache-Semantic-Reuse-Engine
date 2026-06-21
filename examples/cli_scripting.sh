#!/bin/bash
# Bitmod CLI scripting examples.
# Install: pip install bitmod
# Docs: https://bitmod.io/docs

# Initialize a project (creates bitmod.yaml + SQLite DB)
bitmod init

# Ingest files
bitmod ingest ./documents/
bitmod ingest policy.pdf
bitmod ingest "Raw text can be ingested directly too"

# Query (connects to local server, falls back to offline mode)
bitmod query "What is the refund policy?"

# JSON output for scripting — pipe through jq
bitmod --format json query "What is the refund policy?" | jq '.answer'
bitmod --format json query "Summarize the docs" | jq '{answer, cached, model_used}'

# Cache stats
bitmod cache stats
bitmod --format json cache stats | jq '{hit_rate, total_entries, total_compute_saved_s}'

# Recent cached queries
bitmod cache recent --limit 5

# System status
bitmod status
bitmod --format json status | jq '{documents, llm_provider, db_backend}'

# Start the API server (gateway + chat)
bitmod serve
