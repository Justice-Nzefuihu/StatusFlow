from sqlalchemy import create_engine
from .config import setting
from sqlalchemy.orm import sessionmaker

DATABASE_URL = f"postgresql+psycopg2://{setting.database_username}:{setting.database_password}@{setting.database_hostname}:{setting.database_port}/{setting.database_name}"

engine = create_engine(DATABASE_URL)

sessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def get_db():
    try:
       db = sessionLocal()
       yield db
    finally:
        db.close()