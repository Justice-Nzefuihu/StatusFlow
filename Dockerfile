# ---------- Base Image ----------
FROM python:3.11-slim

# ---------- Working Directory ----------
WORKDIR /app


RUN apt-get update && apt-get install -y build-essential libpq-dev && rm -rf /var/lib/apt/lists/*


# ---------- Copy Files ----------
COPY . .

# ---------- Install Dependencies ----------
RUN pip install --no-cache-dir -r requirements.txt

# ---------- FastAPI Entrypoint (used by Railway) ----------
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
