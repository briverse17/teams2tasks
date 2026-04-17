from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TEAMS_", case_sensitive=False)

    auth_path: Path = Path("teams_auth.json")
    output_dir: Path = Path("outputs")
    user_name: str = "Nguyen Minh Vu"
    headless: bool = False
    slow_mo: int = 0
    timeout: int = 60000
    stabilize_wait: int = 30000
    click_wait: int = 10000


settings = Settings()
