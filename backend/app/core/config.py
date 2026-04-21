"""
Configurações gerais da aplicação
"""
from datetime import timedelta
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configurações da aplicação"""

    # JWT Configuration
    JWT_SECRET_KEY: str = "your-super-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 72  # 3 days

    # Admin user (fixo)
    ADMIN_USERNAME: str = "Admin"
    ADMIN_PASSWORD: str = "#agenciatitan2026"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"  # Permite variáveis extras no ambiente


settings = Settings()


# Token expiration time
TOKEN_EXPIRE_DELTA = timedelta(hours=settings.JWT_EXPIRATION_HOURS)
