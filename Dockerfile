# AI Test Generator — API (Render / Railway / Fly)
FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY ["test pdf", "/app/test pdf"]

# Optional: commit test_generator.db.deploy from scripts/prepare_deploy_db.py
RUN if [ -f /app/backend/test_generator.db.deploy ]; then \
      cp /app/backend/test_generator.db.deploy /app/backend/test_generator.db; \
    fi

ENV PYTHONPATH=/app/backend
ENV PYTHONUNBUFFERED=1
ENV SKIP_IMAGE_EXPAND=1
ENV DATABASE_URL=sqlite+aiosqlite:////data/test_generator.db

RUN mkdir -p /data /app/backend/uploads

COPY deploy/start-api.sh /app/start-api.sh
RUN chmod +x /app/start-api.sh

WORKDIR /app/backend
EXPOSE 8000

CMD ["/app/start-api.sh"]
