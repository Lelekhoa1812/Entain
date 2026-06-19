FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY source_code ./source_code

# Install the package with optional parquet support. If your environment has
# strict build limits, change this to `pip install --no-cache-dir .` and the
# pipeline will still emit CSV outputs.
RUN pip install --no-cache-dir ".[parquet]"

ENTRYPOINT ["bet-pipeline"]

FROM runtime AS test

COPY tests ./tests
RUN pip install --no-cache-dir ".[dev,parquet]" && pytest
