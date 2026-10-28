# AI Test Generator — API (Render / Railway / Fly)
FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    libreoffice-writer \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
# EC2 28G root cannot fit CUDA torch/triton. Install CPU torch first, skip easyocr's torch dep.
RUN grep -viE '^\s*easyocr' /app/backend/requirements.txt > /tmp/requirements.noocr.txt \
    && pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r /tmp/requirements.noocr.txt \
    && pip install --no-cache-dir easyocr --no-deps \
    && pip install --no-cache-dir opencv-python-headless scikit-image python-bidi ninja Shapely pyclipper \
    && pip cache purge || true

COPY backend /app/backend
COPY ["test pdf", "/app/test pdf"]

# Optional: commit test_generator.db.deploy from scripts/prepare_deploy_db.py
RUN if [ -f /app/backend/test_generator.db.deploy ]; then \
      cp /app/backend/test_generator.db.deploy /app/backend/test_generator.db; \
    fi

ENV PYTHONPATH=/app/backend
ENV PYTHONUNBUFFERED=1
ENV SKIP_IMAGE_EXPAND=1
ENV SKIP_RUNTIME_VLM=1
ENV LLM_MAX_CONCURRENT=1
ENV MAX_LLM_CONTEXT_CHARS=8000
ENV DATABASE_URL=sqlite+aiosqlite:////data/test_generator.db

RUN mkdir -p /data /app/backend/uploads

COPY deploy/start-api.sh /app/start-api.sh
RUN chmod +x /app/start-api.sh

WORKDIR /app/backend
EXPOSE 8000

CMD ["/app/start-api.sh"]
