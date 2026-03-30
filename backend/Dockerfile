# ── Stage 1: install dependencies ────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml .

# Install build tools, then install Python deps into a virtual-env so we can
# copy only the site-packages to the runtime image.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir .

# ── Stage 2: runtime ────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Copy only the virtual-env from builder (keeps image small)
COPY --from=builder /opt/venv /opt/venv

COPY app/ app/

# Data directory will be bind-mounted at runtime
RUN mkdir -p /app/data/sessions /app/data/logs

EXPOSE 8071

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8071"]
