FROM python:3.11-slim AS build

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN pip install --no-cache-dir uv==0.12.24 \
    && uv sync --locked --no-dev --no-install-project

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:${PATH}"
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY backend ./backend
RUN mkdir -p /var/lib/bsi && chown -R 10001:10001 /var/lib/bsi
WORKDIR /app/backend
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
