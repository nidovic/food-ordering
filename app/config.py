from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Telegram
    telegram_bot_token: str
    
    # LLMs
    gemini_api_key: str
    groq_api_key: str
    
    # Spreeloop API
    spreeloop_api_url: str
    spreeloop_api_token: str
    spreeloop_default_place_id: str = "default_place"  # AJOUTÉ: ID du restaurant par défaut
    
    # Firebase
    firebase_credentials_json: str
    
    # App
    environment: str = "development"
    use_webhook: bool = False
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()