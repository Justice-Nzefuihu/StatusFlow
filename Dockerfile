# ---------- Base Image ----------
FROM python:3.11-slim

# ---------- Working Directory ----------
WORKDIR /app


# ---------- System Dependencies ----------
RUN apt-get update && apt-get install -y \
    xvfb \
    wget \
    unzip \
    libnss3 \
    libxss1 \
    libgbm-dev \
    libxkbcommon-x11-0 \
    fonts-liberation \
    xdg-utils \
    libasound2 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*
    
# ---------- Copy Files ----------
COPY . .

# ---------- Install Dependencies ----------
RUN pip install --no-cache-dir -r requirements.txt

# ---------- FastAPI Entrypoint (used by Railway) ----------
CMD alembic upgrade head && uvicorn app.api:app --host 0.0.0.0 --port 8000
