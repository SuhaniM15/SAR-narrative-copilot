#!/bin/sh
# Default container entrypoint: prepare data, then run the API.
set -e
mkdir -p /app/data /app/data/chroma
python -m scripts.seed
python -m scripts.ingest_knowledge
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
