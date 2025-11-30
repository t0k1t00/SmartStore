import asyncio
import json
import logging
from typing import AsyncGenerator
from datetime import datetime

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
import redis.asyncio as aioredis

from ..config import settings
from ..repository import repository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/streaming", tags=["streaming"])

# Redis client for pub/sub
redis_client = None


async def get_redis_client():
    """Get or create async Redis client"""
    global redis_client
    if redis_client is None:
        redis_client = await aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
    return redis_client


async def metrics_generator(request: Request) -> AsyncGenerator[str, None]:
    redis = await get_redis_client()
    pubsub = redis.pubsub()
    
    try:
        # Subscribe to metrics channel
        await pubsub.subscribe('smartstore-metrics')
        logger.info("Client connected to metrics stream")
        
        # Send initial stats
        stats = repository.get_stats()
        initial_event = {
            'type': 'initial_stats',
            'timestamp': datetime.now().isoformat(),
            'data': stats
        }
        yield {
            "event": "message",
            "data": json.dumps(initial_event)
        }
        
        # Stream events from Redis
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                logger.info("Client disconnected from metrics stream")
                break
            
            # Get message from Redis (with timeout)
            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True),
                    timeout=1.0
                )
                
                if message and message['type'] == 'message':
                    # Forward event to client
                    yield {
                        "event": "message",
                        "data": message['data']
                    }
                
                # Also send periodic heartbeat with current stats
                if not message:
                    stats = repository.get_stats()
                    heartbeat = {
                        'type': 'heartbeat',
                        'timestamp': datetime.now().isoformat(),
                        'data': stats
                    }
                    yield {
                        "event": "heartbeat",
                        "data": json.dumps(heartbeat)
                    }
            
            except asyncio.TimeoutError:
                # Send heartbeat on timeout
                stats = repository.get_stats()
                heartbeat = {
                    'type': 'heartbeat',
                    'timestamp': datetime.now().isoformat(),
                    'data': stats
                }
                yield {
                    "event": "heartbeat",
                    "data": json.dumps(heartbeat)
                }
            
            await asyncio.sleep(0.1)  # Small delay to prevent busy loop
    
    except Exception as e:
        logger.error(f"Error in metrics stream: {e}", exc_info=True)
    
    finally:
        await pubsub.unsubscribe('smartstore-metrics')
        await pubsub.close()
        logger.info("Metrics stream closed")


@router.get("/metrics")
async def metrics_stream(request: Request):
    return EventSourceResponse(metrics_generator(request))


@router.get("/test")
async def test_stream(request: Request):
    async def counter_generator():
        counter = 0
        while True:
            if await request.is_disconnected():
                break
            
            counter += 1
            yield {
                "event": "count",
                "data": json.dumps({
                    'counter': counter,
                    'timestamp': datetime.now().isoformat()
                })
            }
            
            await asyncio.sleep(1)
    
    return EventSourceResponse(counter_generator())


@router.post("/publish")
async def publish_test_event(event_type: str, data: dict):
    redis = await get_redis_client()
    
    event = {
        'type': event_type,
        'timestamp': datetime.now().isoformat(),
        **data
    }
    
    await redis.publish('smartstore-metrics', json.dumps(event))
    
    return {
        'success': True,
        'message': 'Event published',
        'event': event
    }
