"""
Configuration for the Mech Arena AI Assistant bot.
Reads from environment variables / .env file.
Completely separate from the Tournament Bot config.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class MechSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Discord — separate token from the Tournament Bot
    mech_discord_token: str = ""

    # AI (reuses the same Groq key as the main bot)
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Knowledge base
    knowledge_dir: str = "knowledge"

    # App
    log_level: str = "INFO"
    environment: str = "development"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


mech_settings = MechSettings()
