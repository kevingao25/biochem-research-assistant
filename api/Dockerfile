FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# UV_SYSTEM_PYTHON=1 installs packages into the system Python interpreter
# rather than a virtualenv. This is required because Docker Compose mounts
# ./api:/app at runtime for hot reloading — which would wipe out any .venv
# created at /app during the build step.
ENV UV_SYSTEM_PYTHON=1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

EXPOSE 8000

# --host 0.0.0.0 is required inside Docker so the server accepts connections from outside the container
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
