from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from datetime import datetime
import uvicorn
import logging
from typing import Optional
from urllib.parse import unquote

from .config import settings
from .repository import repository
from .models import (
    KeyCreateRequest, KeyResponse, KeyListResponse,
    OperationResponse, StatsResponse, HealthResponse
)
from .routes import streaming, ml
from .routes import auth as auth_routes

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(" SmartStoreDB Web Application Starting...")
    logger.info(f" Database: {settings.SMARTSTORE_DB_FILE}")
    logger.info(f" Lock File: {settings.SMARTSTORE_DB_LOCK}")
    logger.info(f" Redis: {settings.REDIS_URL}")
    logger.info(f"  Max Workers: {settings.MAX_WORKERS}")
    logger.info(f" Cache Size: {settings.CACHE_SIZE}")
    
    yield
    
    # Shutdown
    logger.info(" SmartStoreDB Web Application Shutting Down...")
    # call repository.shutdown() if exists
    try:
        repository.shutdown()
    except Exception:
        pass


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-grade Key-Value Store with ML-powered caching, anomaly detection, and predictive analytics",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(streaming.router, prefix=settings.API_V1_PREFIX)
app.include_router(ml.router, prefix=settings.API_V1_PREFIX)
app.include_router(auth_routes.router, prefix=settings.API_V1_PREFIX)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url)
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url)
        }
    )

@app.get("/")
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational",
        "timestamp": datetime.now().isoformat(),
        "documentation": f"{settings.API_V1_PREFIX}/docs"
    }


@app.get("/health")
async def health_check():
    try:
        # Test repository connectivity
        stats = repository.get_stats()
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": {
                "connected": True,
                "total_keys": stats['total_keys']
            },
            "cache": {
                "size": stats['cache_size'],
                "hit_rate": stats['hit_rate']
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
        )

@app.get(f"{settings.API_V1_PREFIX}/keys", response_model=KeyListResponse)
def list_keys():
    try:
        keys = repository.get_all_keys()
        return KeyListResponse(
            keys=keys,
            count=len(keys),
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(f"{settings.API_V1_PREFIX}/keys/{{key}}", response_model=KeyResponse)
def get_key(key: str):
    key = unquote(key)
    value = repository.get(key)
    if value is None:
        raise HTTPException(status_code=404, detail=f"Key '{key}' not found")
    return KeyResponse(
        key=key,
        value=value,
        timestamp=datetime.now().isoformat()
    )


@app.post(f"{settings.API_V1_PREFIX}/keys", response_model=OperationResponse)
def create_key(request: KeyCreateRequest):
    try:
        # check existence first
        existing = repository.get(request.key)
        if existing is not None:
            raise HTTPException(status_code=409, detail=f"Key '{request.key}' already exists. Use PUT to update.")

        success = repository.put(
            request.key,
            request.value,
            request.ttl,
            request.data_type
        )

        return OperationResponse(
            success=success,
            message=f"Key '{request.key}' stored successfully",
            timestamp=datetime.now().isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put(f"{settings.API_V1_PREFIX}/keys/{{key}}", response_model=OperationResponse)
def update_key(key: str, request: KeyCreateRequest):
    key = unquote(key)
    try:
        # ensure key exists
        existing = repository.get(key)
        if existing is None:
            raise HTTPException(status_code=404, detail=f"Key '{key}' not found")

        success = repository.put(key, request.value, request.ttl, request.data_type)

        return OperationResponse(
            success=success,
            message=f"Key '{key}' updated successfully",
            timestamp=datetime.now().isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete(f"{settings.API_V1_PREFIX}/keys/{{key}}", response_model=OperationResponse)
def delete_key(key: str):
    success = repository.delete(key)
    if not success:
        raise HTTPException(status_code=404, detail=f"Key '{key}' not found")
    return OperationResponse(
        success=success,
        message=f"Key '{key}' deleted successfully",
        timestamp=datetime.now().isoformat()
    )


@app.get(f"{settings.API_V1_PREFIX}/stats", response_model=StatsResponse)
def get_stats():
    try:
        stats = repository.get_stats()
        return StatsResponse(
            stats=stats,
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Development mode only
        workers=1,
        log_level=settings.LOG_LEVEL.lower()
    )
