"""
Cost Guard Module

Protects against unexpected LLM API bills by:
1. Tracking daily spending per user
2. Blocking requests when budget exceeded
3. Warning when approaching limit
"""
import time
import redis
import logging
from datetime import datetime
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
            logger.error(f"Cost guard Redis connection failed: {e}")
            _redis_client = None
    return _redis_client

# Token pricing (GPT-4o-mini example)
PRICE_PER_1K_INPUT_TOKENS = 0.00015   # $0.15/1M input tokens
PRICE_PER_1K_OUTPUT_TOKENS = 0.0006   # $0.60/1M output tokens


def check_budget(user_id: str = Depends(verify_api_key)) -> None:
    """
    Dependency: Check if user has budget remaining.
    
    Tracks daily spending in Redis and blocks if exceeded.
    
    Args:
        user_id: User identifier from auth
        
    Raises:
        HTTPException 402: If daily budget exceeded
        HTTPException 503: If global budget exceeded
    """
    client = get_redis_client()
    if not client:
        # Fail-open: allow request if Redis not available
        logger.warning("Cost guard disabled - Redis not available")
        return
    
    today = datetime.now().strftime("%Y-%m-%d")
    user_key = f"budget:{user_id}:{today}"
    global_key = f"budget:global:{today}"
    
    try:
        # Get current spending
        user_spent = float(client.get(user_key) or 0)
        global_spent = float(client.get(global_key) or 0)
        
        # Check global budget (all users combined)
        global_budget = settings.monthly_budget_usd / 30  # Daily from monthly
        if global_spent >= global_budget:
            logger.critical(f"GLOBAL BUDGET EXCEEDED: ${global_spent:.4f}")
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "Service temporarily unavailable",
                    "reason": "Daily budget limit reached",
                    "resets_at": "midnight UTC",
                },
            )
        
        # Check per-user budget
        user_budget = settings.daily_budget_usd
        if user_spent >= user_budget:
            raise HTTPException(
                status_code=402,  # Payment Required
                detail={
                    "error": "Daily budget exceeded",
                    "used_usd": round(user_spent, 4),
                    "budget_usd": user_budget,
                    "resets_at": "midnight UTC",
                },
            )
        
        # Warning when approaching limit (80%)
        if user_spent >= user_budget * 0.8:
            logger.warning(
                f"User {user_id} at {user_spent/user_budget*100:.0f}% of daily budget"
            )
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Cost guard error: {e}")
        # Fail-open: allow request if Redis fails
        pass


def record_usage(user_id: str, input_tokens: int, output_tokens: int) -> float:
    """
    Record token usage and calculate cost.
    Call this AFTER LLM response is received.
    
    Args:
        user_id: User identifier
        input_tokens: Number of input tokens used
        output_tokens: Number of output tokens used
        
    Returns:
        cost_usd: Cost of this request in USD
    """
    client = get_redis_client()
    if not client:
        logger.warning("Cannot record usage - Redis not available")
        return 0.0
    
    today = datetime.now().strftime("%Y-%m-%d")
    user_key = f"budget:{user_id}:{today}"
    global_key = f"budget:global:{today}"
    
    # Calculate cost
    input_cost = (input_tokens / 1000) * PRICE_PER_1K_INPUT_TOKENS
    output_cost = (output_tokens / 1000) * PRICE_PER_1K_OUTPUT_TOKENS
    total_cost = input_cost + output_cost
    
    try:
        # Increment spending in Redis
        client.incrbyfloat(user_key, total_cost)
        client.incrbyfloat(global_key, total_cost)
        
        # Set expiry (32 days to be safe)
        client.expire(user_key, 32 * 24 * 3600)
        client.expire(global_key, 32 * 24 * 3600)
        
        # Get updated total
        user_spent = float(client.get(user_key) or 0)
        
        logger.info(
            f"Usage recorded: user={user_id} cost=${total_cost:.6f} "
            f"total=${user_spent:.4f}/{settings.daily_budget_usd}"
        )
        
    except Exception as e:
        logger.error(f"Failed to record usage: {e}")
    
    return total_cost


def get_usage_stats(user_id: str) -> dict:
    """
    Get current usage statistics for a user.
    
    Args:
        user_id: User identifier
        
    Returns:
        dict with usage stats
    """
    client = get_redis_client()
    if not client:
        return {"error": "Redis not available"}
    
    today = datetime.now().strftime("%Y-%m-%d")
    user_key = f"budget:{user_id}:{today}"
    
    try:
        user_spent = float(client.get(user_key) or 0)
        budget = settings.daily_budget_usd
        
        return {
            "user_id": user_id,
            "date": today,
            "spent_usd": round(user_spent, 4),
            "budget_usd": budget,
            "remaining_usd": round(max(0, budget - user_spent), 4),
            "used_percent": round(user_spent / budget * 100, 1),
        }
    except Exception as e:
        logger.error(f"Failed to get usage stats: {e}")
        return {"error": str(e)}