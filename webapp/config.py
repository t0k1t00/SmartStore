from pydantic_settings import BaseSettings
from typing import Optional
import os
from pathlib import Path


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "SmartStoreDB Web API"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    
    # API
    API_V1_PREFIX: str = "/api/v1"
    ALLOWED_HOSTS: list = ["*"]
    
    # Security
    SECRET_KEY: str = "SECRET-KEY"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Base directory of the webapp
    BASE_DIR: Path = Path(__file__).resolve().parent.parent  # /webapp

    # Data directory (absolute)
    DATA_DIR: Path = BASE_DIR / "data"

    # Database files
    SMARTSTORE_DB_FILE: str = str(DATA_DIR / "smartstore.db")
    SMARTSTORE_DB_LOCK: str = str(DATA_DIR / "smartstore.db.lock")
    USERS_DB_FILE: str = str(DATA_DIR / "users.db")

    # Model directory
    MODELS_DIR: Path = DATA_DIR / "models"
    CACHE_MODEL_FILE: str = str(MODELS_DIR / "cache_lstm.h5")
    ANOMALY_MODEL_FILE: str = str(MODELS_DIR / "anomaly_iforest.joblib")
    PROPHET_MODEL_FILE: str = str(MODELS_DIR / "prophet_forecast.joblib")
    DBSCAN_MODEL_FILE: str = str(MODELS_DIR / "dbscan_clusters.joblib")

    # Logging
    LOG_FILE: str = str(DATA_DIR / "logs" / "app.log")

    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_URL: str = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

    # Celery
    CELERY_BROKER_URL: str = REDIS_URL
    CELERY_RESULT_BACKEND: str = REDIS_URL
    CELERY_TASK_TRACK_STARTED: bool = True
    CELERY_TASK_TIME_LIMIT: int = 3600

    # Performance
    MAX_WORKERS: int = 4
    CACHE_SIZE: int = 10000
    FILE_LOCK_TIMEOUT: int = 10

    # ML
    LSTM_SEQUENCE_LENGTH: int = 10
    LSTM_EPOCHS: int = 50
    LSTM_BATCH_SIZE: int = 32

    IFOREST_CONTAMINATION: float = 0.1
    IFOREST_N_ESTIMATORS: int = 100

    DBSCAN_EPS: float = 0.5
    DBSCAN_MIN_SAMPLES: int = 5

    # Monitoring
    LOG_LEVEL: str = "INFO"
    ENABLE_PROMETHEUS: bool = True

    # CORS
    CORS_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080"
    ]

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 100

    class Config:
        env_file = ".env"
        case_sensitive = True


# Instantiate settings
settings = Settings()

# Ensure directories exist (convert Path to string)
os.makedirs(str(settings.DATA_DIR), exist_ok=True)
os.makedirs(str(settings.MODELS_DIR), exist_ok=True)
os.makedirs(os.path.dirname(settings.LOG_FILE), exist_ok=True)
