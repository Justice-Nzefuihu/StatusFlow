from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
import os


# Read config from environment
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
if allowed_origins_env:
    # split by comma and strip whitespace
    ALLOWED_ORIGINS = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
else:
    ALLOWED_ORIGINS = []


app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE",],
    allow_headers=["*"],
)


@app.middleware("http")
async def block_request(request: Request, call_back):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, 
        detail="Forbidden"
        )
