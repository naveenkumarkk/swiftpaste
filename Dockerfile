# --- Base image ---
FROM python:3.13-slim AS base
WORKDIR /app

# Install OS deps
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Install UV package manager
RUN pip install --no-cache-dir uv

# Copy poetry/uv project files
COPY pyproject.toml uv.lock* ./

# Set uv environment
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

# Install frozen dependencies (production)
RUN uv sync --frozen --no-dev

# Copy the app code
COPY . .

EXPOSE 8000

# --- Dev stage ---
FROM base AS dev
RUN uv sync --dev
CMD ["uv", "run", "uvicorn", "app.main:app", "--host=0.0.0.0", "--port=8000", "--reload"]

# --- Production stage ---
FROM base AS prod
CMD ["uv", "run", "uvicorn", "app.main:app", "--host=0.0.0.0", "--port=8000", "--workers=4"]

# --- Worker stage ---
FROM base AS worker
# Use UV venv for Python
ENV PATH="/opt/venv/bin:$PATH"
CMD ["python", "-m", "app.jobs.worker"]