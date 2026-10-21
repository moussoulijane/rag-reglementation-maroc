FROM node:24-alpine AS frontend

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.11-slim

ARG INSTALL_EXTRAS=opensearch
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    RAG_DATA_DIR=/app/data RAG_ENCODER=none RAG_BACKEND=local RAG_GENERATOR=extractive
WORKDIR /app
COPY pyproject.toml README.md LICENSE MANIFEST.in ./
COPY src ./src
COPY --from=frontend /app/src/rag_reglementation_ui/static ./src/rag_reglementation_ui/static
COPY evaluation ./evaluation
RUN python -m pip install --no-cache-dir ".[${INSTALL_EXTRAS}]" \
    && useradd --create-home --uid 10001 rag \
    && mkdir -p /app/data \
    && chown -R rag:rag /app
USER rag
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["python", "-m", "uvicorn", "rag_reglementation_ui.app:app", "--host", "0.0.0.0", "--port", "8000"]
