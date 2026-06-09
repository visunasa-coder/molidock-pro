FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    ca-certificates \
    wget \
    openbabel \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN wget https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.7/vina_1.2.7_linux_x86_64 \
    -O /usr/local/bin/vina \
    && chmod +x /usr/local/bin/vina

COPY . .

RUN mkdir -p /app/storage && useradd --create-home --uid 10001 molidock \
    && chown -R molidock:molidock /app

ENV VINA_BINARY=/usr/local/bin/vina
ENV OBABEL_BINARY=obabel
ENV ALLOW_DEMO_DOCKING=false

USER molidock

CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8010}"]
