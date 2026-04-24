FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./

# Install into /opt/venv so the virtualenv survives the ./api:/app volume
# mount that Docker Compose uses for hot reloading. Without this, the default
# /app/.venv gets wiped when the host directory is mounted over /app.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
RUN uv sync --frozen --no-dev --no-install-project

ENV PATH="/opt/venv/bin:$PATH"

COPY api/ ./
COPY src/ ./src

EXPOSE 8000

# --host 0.0.0.0 is required inside Docker so the server accepts connections from outside the container
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
