### FILE: app/core/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SECRET_KEY: str = "change-this-in-prod"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60*24
    ALGORITHM: str = "HS256"
    EXCEL_PATH: str = "items.xlsx"
    IMAGE_DIR: str = "static/images"
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "adminpass" # change for prod


class Config:
    env_file = '.env'
settings = Settings()