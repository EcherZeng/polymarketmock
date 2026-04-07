# ── Stage 1: install dependencies ────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# ── Stage 2: runtime ────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

COPY --from=builder /opt/venv /opt/venv

COPY config.py .
COPY main.py .
COPY strategy_presets.json .
COPY core/ core/
COPY api/ api/
COPY strategies/ strategies/

RUN mkdir -p /app/results

EXPOSE 8072

CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8072", "--timeout-keep-alive", "120", "--limit-max-incomplete-event-size", "65536"]
