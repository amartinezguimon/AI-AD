# Cloud backend image. Build context is the REPO ROOT (so the `cloud` package
# copies in): docker compose handles that via context: .. below.
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY cloud/requirements.txt cloud/requirements.txt
RUN pip install -r cloud/requirements.txt

COPY cloud ./cloud

EXPOSE 8000
# Apply migrations, then serve. Migrations are idempotent (no-op once at head).
CMD ["sh", "-c", "alembic -c cloud/alembic.ini upgrade head && uvicorn cloud.app.main:app --host 0.0.0.0 --port 8000"]
