# Tara backend — modular monolith (FastAPI). Single image runs the API,
# the Celery worker, and Celery beat (command overridden per compose service).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first for better layer caching.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# App source.
COPY . .

EXPOSE 3000

# Default command runs the API; worker/beat services override this.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3000"]
