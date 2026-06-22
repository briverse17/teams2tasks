"""Configuration settings for MS Teams scraper."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and dotenv."""

    model_config = SettingsConfigDict(env_prefix="TEAMS_", case_sensitive=False)

    auth_path: Path = Path("teams_auth.json")
    profile_dir: Path = Path("teams_profile")
    chats_config_path: Path = Path("chats_config.yaml")
    output_dir: Path = Path("outputs")
    user_name: str = "Nguyen Minh Vu"
    headless: bool = True
    slow_mo: int = 0
    timeout: int = 60000
    stabilize_wait: int = 30000
    click_wait: int = 10000


settings = Settings()

