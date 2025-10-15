import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .config import setting
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

# Build database URL (excluding sensitive info from logs)
DATABASE_URL = (
    f"postgresql+psycopg2://{setting.database_username}:"
    f"{setting.database_password}@{setting.database_hostname}:"
    f"{setting.database_port}/{setting.database_name}"
)

try:
    engine = create_engine(DATABASE_URL)
    logger.info("Database engine created successfully")
except SQLAlchemyError as e:
    logger.error("Failed to create engine: %s", e, exc_info=True)
    raise
except Exception as e:
    logger.error("Unexpected error creating engine: %s", e, exc_info=True)
    raise

# Session maker
try:
    sessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    logger.info("SessionLocal created successfully")
except Exception as e:
    logger.error("Error creating sessionmaker: %s", e, exc_info=True)
    raise


def get_db():
    """Dependency for FastAPI / general DB access"""
    db = None
    try:
        db = sessionLocal()
        logger.debug("Database session opened")
        yield db
    except SQLAlchemyError as e:
        logger.error("Database error in get_db: %s", e, exc_info=True)
        raise
    except Exception as e:
        logger.error("Unexpected error in get_db: %s", e, exc_info=True)
        raise
    finally:
        if db is not None:
            db.close()
            logger.debug("Database session closed")