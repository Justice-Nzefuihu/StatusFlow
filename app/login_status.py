from app.database import sessionLocal
from app.model import UserDB

# Configure logging
from app.logging_config import get_logger

logger = get_logger(__name__)


def get_login_status(phone: str, country: str):
    """Get login status of a user by phone and country."""
    db = sessionLocal()
    try:
        user = db.query(UserDB).filter_by(phone=phone, country=country).first()
        if user:
            logger.info(f"Fetched login_status for user {phone}, {country}: {user.login_status}")
            return user.login_status
        else:
            logger.warning(f"No user found with phone={phone}, country={country}")
            return None
    except Exception as e:
        logger.error(f"Error getting user login_status for phone={phone}, country={country}: {e}")
        return None
    finally:
        db.close()


def change_login_status(phone: str, country: str):
    """Change login status of a user to False."""
    db = sessionLocal()
    try:
        user = db.query(UserDB).filter_by(phone=phone, country=country).first()
        if not user:
            logger.warning(f"No user found to update with phone={phone}, country={country}")
            return False

        user.login_status = False
        db.commit()
        logger.info(f"Changed login_status to False for user {phone}, {country}")
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Error changing user login_status for phone={phone}, country={country}: {e}")
        return False
    finally:
        db.close()