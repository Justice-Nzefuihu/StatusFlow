from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_hostname: str
    database_username: str
    database_password: str
    database_port: int
    database_name: str
    access_token: str
    phone_number_id: str
    verify_token: str
    app_secret: str
    google_scopes: str
    credentials_file: str
    token_file: str
    fernet_key: str

    class Config:
        env_file = ".env"


setting = Settings()