FROM ghcr.io/shopify/toxiproxy:2.12.0

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

HEALTHCHECK --interval=30s --timeout=5s --retries=3\
    CMD curl --fail http://localhost:8474 || exit 1
