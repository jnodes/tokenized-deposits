# StableArch Council
# M&T Bank | Cari Network | ZKsync Prividium
# Multi-Agent ARB Package Generator

FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Environment variables (set at runtime)
# ENV OPENAI_API_KEY=your-key-here
# ENV OPENAI_MODEL_NAME=gpt-4o

ENTRYPOINT ["python", "run.py"]
CMD []
