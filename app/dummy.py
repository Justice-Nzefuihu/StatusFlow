import os
from dotenv import load_dotenv

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

# Basic logger setup
from app.logging_config import get_logger

logger = get_logger(__name__)


load_dotenv()

# Read config from environment
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
if allowed_origins_env:
    # split by comma and strip whitespace
    ALLOWED_ORIGINS = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
else:
    ALLOWED_ORIGINS = []

INTERNAL_SECRET = os.getenv("INTERNAL_SECRET", "")
MAINTENANCE_MODE = os.getenv("MAINTENANCE_MODE", "1") == "1"

app = FastAPI(title="Dummy")

# Add CORS middleware first so it runs early.
# Only allow the configured origins. Do not use '*' for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE",],
    allow_headers=["*"],
)



@app.middleware("http")
async def protected_health_and_maintenance(request: Request, call_next):
    """
    Behavior:
    - If request.path == /health:
        require header x-internal-secret == INTERNAL_SECRET
        otherwise return 403
    - If MAINTENANCE_MODE is enabled:
        block all requests except /health
    - Otherwise allow request to proceed
    """
    path = request.url.path

    # handle health endpoint
    if path == "/health":
        header_value = request.headers.get("x-internal-secret", "")
        if INTERNAL_SECRET and header_value == INTERNAL_SECRET:
            # health ok
            return await call_next(request)
        # secret mismatch or not provided
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    # If maintenance mode, block all non health requests
    if MAINTENANCE_MODE:
        # You can allow specific internal paths here if needed
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service under maintenance")

    # normal flow
    return await call_next(request)


@app.get("/health")
async def health():
    # This route will only succeed if the middleware allowed it
    return {"status": "ok"}


# Example real endpoint
@app.get("/ping")
async def ping():
    return {"pong": True}
