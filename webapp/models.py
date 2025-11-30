from pydantic import BaseModel, Field, validator
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum

class KeyCreateRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=256, description="Key name")
    value: Any = Field(..., description="Value to store")
    ttl: Optional[int] = Field(None, ge=0, description="Time-to-live in seconds")
    data_type: str = Field("string", description="Data type hint")
    
    @validator('key')
    def validate_key(cls, v):
        if not v or not v.strip():
            raise ValueError("Key cannot be empty")
        
        # Disallow special characters that might cause issues
        forbidden_chars = ['/', '\\', '\0', '\n', '\r']
        if any(char in v for char in forbidden_chars):
            raise ValueError(f"Key cannot contain: {forbidden_chars}")
        
        return v.strip()
    
    class Config:
        json_schema_extra = {
            "example": {
                "key": "user:1001",
                "value": "John Doe",
                "ttl": 3600,
                "data_type": "string"
            }
        }


class KeyBatchCreateRequest(BaseModel):
    keys: List[KeyCreateRequest] = Field(..., min_items=1, max_items=1000)
    
    class Config:
        json_schema_extra = {
            "example": {
                "keys": [
                    {"key": "user:1001", "value": "John", "ttl": 3600},
                    {"key": "user:1002", "value": "Jane", "ttl": 3600}
                ]
            }
        }

class KeyResponse(BaseModel):
    key: str
    value: Any
    timestamp: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "key": "user:1001",
                "value": "John Doe",
                "timestamp": "2025-01-15T10:30:00"
            }
        }


class KeyListResponse(BaseModel):
    keys: List[str]
    count: int
    timestamp: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "keys": ["user:1001", "user:1002", "session:abc"],
                "count": 3,
                "timestamp": "2025-01-15T10:30:00"
            }
        }


class OperationResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    timestamp: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "timestamp": "2025-01-15T10:30:00"
            }
        }


class StatsResponse(BaseModel):
    stats: dict
    timestamp: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "stats": {
                    "total_keys": 1500,
                    "cache_size": 500,
                    "hits": 10000,
                    "misses": 2000,
                    "hit_rate": 83.33,
                    "writes": 5000,
                    "deletes": 200,
                    "errors": 5
                },
                "timestamp": "2025-01-15T10:30:00"
            }
        }


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    database: dict
    cache: dict
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2025-01-15T10:30:00",
                "database": {
                    "connected": True,
                    "total_keys": 1500
                },
                "cache": {
                    "size": 500,
                    "hit_rate": 83.33
                }
            }
        }

class MLModelType(str, Enum):
    CACHE_PREDICTION = "cache_prediction"
    ANOMALY_DETECTION = "anomaly_detection"
    TIME_SERIES_FORECAST = "time_series_forecast"
    CLUSTERING = "clustering"


class MLTrainingRequest(BaseModel):
    model_type: MLModelType
    parameters: Optional[dict] = Field(default_factory=dict)
    
    class Config:
        json_schema_extra = {
            "example": {
                "model_type": "anomaly_detection",
                "parameters": {
                    "contamination": 0.1,
                    "n_estimators": 100
                }
            }
        }

class MLPredictionResponse(BaseModel):
    model_type: MLModelType
    prediction: Any
    confidence: Optional[float] = None
    timestamp: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "model_type": "cache_prediction",
                "prediction": ["user:1001", "user:1002", "session:abc"],
                "confidence": 0.87,
                "timestamp": "2025-01-15T10:30:00"
            }
        }

class ErrorResponse(BaseModel):
    error: str
    timestamp: str
    path: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "Key not found",
                "timestamp": "2025-01-15T10:30:00",
                "path": "/api/v1/keys/nonexistent"
            }
        }
