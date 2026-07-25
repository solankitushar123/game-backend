"""
Application configuration.
All secrets/env-specific values are loaded from environment variables in production.
Defaults here are for local development only.
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    APP_NAME: str = "ArenaForge"
    ENV: str = "development"

    # Database
    DATABASE_URL: str = "mysql+pymysql://root:root@localhost:3306/gamejackpot"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_SECRET_KEY: str = "dev-secret-change-in-production-use-256-bit-random-value"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    # CORS
    CORS_ORIGINS: List[str] = ["https://game-frontend-3bsrgb2qy-tejasvi-solankis-projects.vercel.app","http://localhost:5173", "http://localhost:3000"]
    # Matches ANY Vercel preview deployment for this project too (they get a new random
    # hash every deploy, e.g. game-frontend-<hash>-tejasvi-solankis-projects.vercel.app)
    CORS_ORIGIN_REGEX: str = r"^https://game-frontend(-[a-z0-9]+)?-tejasvi-solankis-projects\.vercel\.app$"

    # Wallet / business rules
    MIN_DEPOSIT_PAISE: int = 5000          # ₹50.00 minimum deposit
    MAX_DEPOSIT_PAISE: int = 10000000      # ₹1,00,000 max single deposit (anti-fraud guard)
    MIN_AGE_YEARS: int = 18

    # Simulated payment gateway (swap for Razorpay/Cashfree in production)
    PAYMENT_GATEWAY_MODE: str = "simulated"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
