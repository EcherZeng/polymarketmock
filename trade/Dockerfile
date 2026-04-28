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
COPY api/ api/
COPY core/ core/
COPY engine/ engine/
COPY execution/ execution/
COPY infra/ infra/
COPY market/ market/
COPY models/ models/
COPY portfolio/ portfolio/
COPY strategies/ strategies/

RUN mkdir -p /app/data

EXPOSE 8073

CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8073", "--timeout-keep-alive", "120"]
