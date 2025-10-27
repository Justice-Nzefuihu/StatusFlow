import psutil
# from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from redis import asyncio as aioredis
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from .celery_app import celery_app
from .config import setting

from app.logging_config import get_logger

logger = get_logger(__name__)


class LoadBalancerMiddleware(BaseHTTPMiddleware):
    """
    Dynamic load balancing middleware.
    Adapts based on CPU cores, available memory, and system usage trends.
    """
    async def dispatch(self, request, call_next):
        try:
            # Compute server load
            cpu_percent = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            mem_percent = mem.percent
            max_cpu, max_mem = 90, 90  # safety thresholds

            if cpu_percent > max_cpu or mem_percent > max_mem:
                logger.warning(f"Server overloaded: CPU={cpu_percent}% MEM={mem_percent}%")
                return JSONResponse(
                    {"detail": "Server is currently overloaded, please retry later."},
                    status_code=503,
                )

            response = await call_next(request)
            return response

        except Exception as e:
            logger.error(f"Load balance middleware error: {e}", exc_info=True)
            return JSONResponse({"detail": "Internal server error"}, status_code=500)

class CeleryQueueMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        i =celery_app.control.inspect()
        active_tasks = i.active()
        if active_tasks:
            active = sum(len(v) for v in active_tasks.values() if v)
            if active > 500:  # Example threshold
                return JSONResponse(
                    {"detail": "Background task queue full. Try again later."},
                    status_code=503,
                )
        return await call_next(request)


async def init_rate_limiter(redis_urls=None):
    """
    Initialize a distributed Redis cluster rate limiter for millions of users.
    """
    try:
        redis = await aioredis.from_url(
            setting.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        await FastAPILimiter.init(redis)
        logger.info(" Distributed rate limiter initialized with nodes")
        return redis
    except Exception as e:
        logger.error(f" Failed to initialize Redis cluster: {e}")
        raise


def get_rate_limit(times: int = 100, window_seconds: int = 60):
    """
    Create a rate limiter dependency.
    Example: Depends(get_rate_limit(100, 60)) -> 100 reqs/min per user.
    """
    return RateLimiter(times=times, seconds=window_seconds)