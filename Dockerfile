# SAR Narrative Copilot — API + Streamlit image
FROM python:3.12-slim

WORKDIR /app

# Minimal build deps for some wheels (e.g. chroma-related)
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY ui ./ui
COPY scripts ./scripts
COPY data/knowledge ./data/knowledge
COPY docs ./docs

# Normalize CRLF (Windows checkouts) so the shebang works in Linux containers
RUN sed -i 's/\r$//' scripts/docker_entrypoint.sh \
    && chmod +x scripts/docker_entrypoint.sh \
    && mkdir -p data/chroma

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000 8501

ENTRYPOINT ["./scripts/docker_entrypoint.sh"]
