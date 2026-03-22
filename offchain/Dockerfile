FROM python:3.12-slim AS base

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY offchain/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY offchain/ /app/offchain/
COPY integration/ /app/integration/
COPY reconciliation/ /app/reconciliation/
COPY middleware/ /app/middleware/

# Set Python path so imports resolve
ENV PYTHONPATH=/app
ENV CARI_ENVIRONMENT=production
ENV CARI_DEBUG=false

EXPOSE 8000

CMD ["uvicorn", "offchain.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
