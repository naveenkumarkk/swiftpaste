FROM python:3.13-slim AS base
WORKDIR /app
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock* ./

ENV UV_PROJECT_ENVIRONMENT=/opt/venv
RUN uv sync --frozen --no-dev

COPY . .
EXPOSE 8000

FROM base AS dev
RUN uv sync --dev
CMD ["uv", "run", "uvicorn", "app.main:app", "--host=0.0.0.0", "--port=8000", "--reload"]

FROM base AS prod
CMD ["uv", "run", "uvicorn", "app.main:app", "--host=0.0.0.0", "--port=8000", "--workers=4"]