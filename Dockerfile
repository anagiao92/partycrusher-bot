# ---- Base Image ----
FROM python:3.12-slim

# ---- Environment Variables ----
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ENV=dev

# ---- Install Required System Packages ----
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ---- Create Non-Root User ----
RUN useradd -m botuser

# ---- Set Working Directory ----
WORKDIR /app

# ---- Install Python Dependencies ----
COPY requirements.txt .
RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r requirements.txt

# ---- Copy Project Files ----
COPY . .

# ---- Use Non-Root User ----
USER botuser

# ---- Healthcheck ----
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
  CMD python -c "import socket; exit(0)"

# ---- Entrypoint ----
CMD ["python", "bot.py"]
