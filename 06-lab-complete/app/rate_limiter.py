"""
Redis-based Rate Limiter

Uses sliding window algorithm to limit requests per user.
Stores request timestamps in Redis for stateless design.
"""
import time
import redis
import logging
from fastapi import HTTPException, Depends

from .config import settings
from .auth import verify_api_key

logger = logging.getLogger(__name__)

# Redis connection - lazy loading
_redis_client = None

def get_redis_client():
    """Get Redis client with lazy connection"""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
            _redis_client.ping()
        except Exception as e:
            logger.error(f"Rate limiter Redis connection failed: {e}")
            _redis_client = None
    return _redis_client


def check_rate_limit(user_id: str = Depends(verify_api_key)) -> None:
    """
    Dependency: Check if user has exceeded rate limit.
    
    Algorithm: Sliding Window Counter
    - Store timestamps of requests in Redis sorted set
    - Remove old timestamps outside the window
    - Count remaining timestamps
    - Block if exceeds limit
    
    Args:
        user_id: User identifier from auth
        
    Raises:
        HTTPException 429: If rate limit exceeded
    """
    client = get_redis_client()
    if not client:
        # Fail-open: allow request if Redis not available
        logger.warning("Rate limiter disabled - Redis not available")
        return
    
    now = time.time()
    window_seconds = 60  # 1 minute window
    max_requests = settings.rate_limit_per_minute
    
    # Redis key for this user's rate limit
    key = f"ratelimit:{user_id}"
    
    try:
        # Remove old timestamps (outside window)
        client.zremrangebyscore(key, 0, now - window_seconds)
        
        # Count requests in current window
        current_count = client.zcard(key)
        
        if current_count >= max_requests:
            # Get oldest timestamp to calculate retry_after
            oldest = client.zrange(key, 0, 0, withscores=True)
            if oldest:
                oldest_time = oldest[0][1]
                retry_after = int(oldest_time + window_seconds - now) + 1
            else:
                retry_after = window_seconds
            
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "limit": max_requests,
                    "window_seconds": window_seconds,
                    "retry_after_seconds": retry_after,
                },
                headers={
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(now + window_seconds)),
                    "Retry-After": str(retry_after),
                },
            )
        
        # Add current request timestamp
        client.zadd(key, {str(now): now})
        
        # Set expiry on key (cleanup)
        client.expire(key, window_seconds * 2)
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        # Log error but don't block request if Redis fails
        logger.error(f"Rate limiter error: {e}")
        # Fail-open: allow request
        pass
