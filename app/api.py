import logging
from fastapi import FastAPI, Depends, HTTPException, status as s
from sqlalchemy.orm import Session
from typing import Annotated
from uuid import UUID

from .routers import webhook, user, status
from .model import UserDB
from .database import get_db

# Configure logging
logger = logging.getLogger(__name__)

app = FastAPI()

@app.get("/")
def home():
    try:
        logger.info("Home endpoint accessed successfully")
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error in home endpoint: {e}", exc_info=True)
        raise HTTPException(s.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal Server Error")


@app.post("/confirma-login/{user_id}")
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
    logger.info("Routers registered successfully")
except Exception as e:
    logger.error(f"Error including routers: {e}", exc_info=True)
    raise
