FROM python:3.13-slim AS builder

WORKDIR /build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

FROM python:3.13-slim AS runtime

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/orbital/.local/bin:${PATH}"

RUN groupadd --system orbital \
    && useradd --system --gid orbital --home /home/orbital --create-home orbital \
    && mkdir -p /app/data/demo_images /app/data/demo_cache /app/data/uploads /app/data/storage \
    && chown -R orbital:orbital /app /home/orbital

COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

COPY --chown=orbital:orbital . .

USER orbital
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/api/health').raise_for_status()"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
