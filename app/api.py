from fastapi import FastAPI, Depends, HTTPException, status as s
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Annotated
from uuid import UUID
import os

from .routers import flow, webhook, user, status
from .model import UserDB
from .database import get_db
from app.middlewares import LoadBalancerMiddleware, CeleryQueueMiddleware, init_rate_limiter
from app.middlewares import get_rate_limit

# Configure logging
from app.logging_config import get_logger

logger = get_logger(__name__)

# Read config from environment
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
if allowed_origins_env:
    # split by comma and strip whitespace
    ALLOWED_ORIGINS = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
else:
    ALLOWED_ORIGINS = []


app = FastAPI(title="StatusFlow")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE",],
    allow_headers=["*"],
)

# Add load balancer
app.add_middleware(LoadBalancerMiddleware)
app.add_middleware(CeleryQueueMiddleware)

@app.on_event("startup")
async def startup_event():
    await init_rate_limiter()

@app.get("/", dependencies=[Depends(get_rate_limit(50, 60))])
def home():
    try:
        logger.info("Home endpoint accessed successfully")
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error in home endpoint: {e}", exc_info=True)
        raise HTTPException(s.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal Server Error")


@app.post("/confirma-login/{user_id}", dependencies=[Depends(get_rate_limit(50, 60))])
def confirm_login(user_id: UUID, db: Annotated[Session, Depends(get_db)]):
    try:
        logger.info("Received confirm_login request")
        
        user = db.query(UserDB).filter_by(id=user_id).first()
        if not user:
            logger.warning("User not found during confirm_login")
            raise HTTPException(
                s.HTTP_404_NOT_FOUND, 
                detail="User not found"
            )
        
        user.login_status = True
        db.commit()
        logger.info("User login status successfully updated")
        return {"status": "ok"}

    except HTTPException as http_err:
        # Re-raise HTTPExceptions (already handled)
        raise http_err

    except Exception as e:
        db.rollback()
        logger.error(f"Error confirming login: {e}", exc_info=True)
        raise HTTPException(s.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error confirming login")

    finally:
        db.close()
        logger.debug("Database session closed for confirm_login")


# Include routers
try:
    app.include_router(webhook.router)
    app.include_router(user.router)
    app.include_router(status.router)
    app.include_router(flow.router)
    logger.info("Routers registered successfully")
except Exception as e:
    logger.error(f"Error including routers: {e}", exc_info=True)
    raise
