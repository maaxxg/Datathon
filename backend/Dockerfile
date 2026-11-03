# Build context: repository root (see docker-compose.yml).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 GEORIZIK_DATA=/data
WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY backend/app ./app
COPY pipeline ./pipeline
COPY scripts ./scripts

EXPOSE 8000
# --no-access-log is required: request URLs contain coordinates and address queries.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
