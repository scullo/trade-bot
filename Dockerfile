FROM python:3.11-slim

WORKDIR /app

# Sistem paketleri (curl ve sertifikalar)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV MALLOC_ARENA_MAX=2
ENV PORT=5000

EXPOSE 5000

CMD ["python", "main.py"]
