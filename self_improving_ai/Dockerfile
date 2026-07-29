FROM python:3.11-slim

LABEL org.opencontainers.image.title="Self-Improving AI System"
LABEL org.opencontainers.image.description="Production-grade AI platform that continuously optimizes itself"
LABEL org.opencontainers.image.version="0.1.0"

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Application code
COPY . .

# Create data directories
RUN mkdir -p /app/data /app/data/logs /app/data/experiments /app/data/prompts \
    /app/data/workflows /app/data/tools /app/data/rollback /app/data/benchmarks \
    /app/data/vector_db /app/data/long_term_memory

# Run as non-root
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["python", "-m", "self_improving_ai"]
CMD ["--host", "0.0.0.0", "--port", "8000"]
