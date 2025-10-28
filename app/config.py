# app/config.py
from pydantic_settings import BaseSettings
from pydantic import DirectoryPath, ConfigDict
from pathlib import Path
from functools import lru_cache

class Settings(BaseSettings):
    ENV: str = "development"
    DATA_DIR: Path = Path("data")  # where CSV / XLSX files will live
    USERS_FILE: str = "users.csv"  # can be users.xlsx if you prefer Excel
    PRODUCTS_FILE: str = "products.csv"
    ORDERS_FILE: str = "orders.csv"
    CARTS_FILE: str = "carts.csv"
    WISHLISTS_FILE: str = "wishlists.csv"  # added wishlist file mapping
    REVIEWS_FILE: str = "reviews.csv"      # added reviews file mapping

    image_dir: str = "static/images"

    # If you want to use Excel files, set the file names to .xlsx in .env or edit these values.
    # Example .env:
    # DATA_DIR=./data
    # USERS_FILE=users.xlsx

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

@lru_cache()
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()

settings = Settings()
