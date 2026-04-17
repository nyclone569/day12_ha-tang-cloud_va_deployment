"""
Production-Ready AI Agent
Combines: Auth + Rate Limiting + Cost Guard + Stateless Design
"""
import logging
import json
import time
import signal
import redis
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import settings
from .auth import verify_api_key
from .rate_limiter import check_rate_limit
from .cost_guard import check_budget

# Setup structured JSON logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='{"time":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

# Redis connection (stateless design)
# Lazy connection - only connect when needed
redis_client = None

def get_redis():
    """Get Redis client with lazy connection"""
    global redis_client
    if redis_client is None:
        try:
            redis_client = redis.from_url(settings.redis_url, decode_responses=True)
            redis_client.ping()  # Test connection
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            redis_client = None
    return redis_client

# Track startup time
START_TIME = time.time()
is_ready = False


# Mock LLM function (replace with real OpenAI call in production)
def mock_llm(question: str) -> str:
    """Mock LLM response for testing without API key"""
    import random
    responses = [
        f"Đây là câu trả lời cho: '{question}' (mock response)",
        f"Agent đã xử lý câu hỏi của bạn: '{question}'",
        f"Production agent đang hoạt động! Câu hỏi: '{question}'",
    ]
    return random.choice(responses)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management: startup and graceful shutdown"""
    global is_ready
    
    # Startup
    logger.info(json.dumps({
        "event": "startup",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }))
    
    # Check Redis connection (non-blocking)
    try:
        client = get_redis()
        if client:
            client.ping()
            logger.info("Redis connection established")
            is_ready = True
        else:
            logger.warning("Redis not available - some features may be limited")
            is_ready = True  # Still mark as ready
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        is_ready = True  # Still mark as ready, fail gracefully
    
    yield  # App running
    
    # Shutdown
    is_ready = False
    logger.info("Shutting down gracefully...")
    if redis_client:
        redis_client.close()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# Request/Response models
class AskRequest(BaseModel):
    question: str
    user_id: str = "default"


class AskResponse(BaseModel):
    question: str
    answer: str
    user_id: str
    timestamp: str


@app.get("/")
def root():
    """Root endpoint with app info"""
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "status": "running",
    }


@app.get("/health")
def health():
    """
    Liveness probe: Is the container alive?
    Platform uses this to decide when to restart.
    """
    uptime = round(time.time() - START_TIME, 1)
    return {
        "status": "ok",
        "uptime_seconds": uptime,
        "version": settings.app_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready")
def ready():
    """
    Readiness probe: Is the app ready to receive traffic?
    Load balancer uses this to route traffic.
    """
    if not is_ready:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    # Check Redis connection
    try:
        client = get_redis()
        if client:
            client.ping()
            return {
                "ready": True,
                "redis": "connected",
            }
        else:
            return {
                "ready": True,
                "redis": "not available",
            }
    except Exception as e:
        logger.warning(f"Redis check failed: {e}")
        return {
            "ready": True,
            "redis": "not available",
        }


@app.post("/ask", response_model=AskResponse)
def ask(
    request: AskRequest,
    user_id: str = Depends(verify_api_key),
    _rate_limit: None = Depends(check_rate_limit),
    _budget: None = Depends(check_budget)
):
    """
    Main agent endpoint with full protection:
    1. Authentication (API key)
    2. Rate limiting (10 req/min)
    3. Cost guard (budget check)
    4. Stateless design (history in Redis)
    """
    question = request.question
    
    if not question or not question.strip():
        raise HTTPException(status_code=422, detail="Question cannot be empty")
    
    # Log request (structured)
    logger.info(json.dumps({
        "event": "agent_request",
        "user_id": user_id,
        "question_length": len(question),
    }))
    
    # 1. Get conversation history from Redis (stateless design)
    history_key = f"history:{user_id}"
    history = []
    try:
        client = get_redis()
        if client:
            history = client.lrange(history_key, -5, -1)  # Last 5 messages
    except Exception as e:
        logger.error(f"Redis error: {e}")
        history = []
    
    # 2. Call LLM (mock for now)
    try:
        answer = mock_llm(question)
        
        # Estimate tokens for cost tracking (rough estimate)
        input_tokens = len(question.split()) * 1.3
        output_tokens = len(answer.split()) * 1.3
        
    except Exception as e:
        logger.error(f"LLM error: {e}")
        raise HTTPException(status_code=500, detail="LLM processing failed")
    
    # 3. Save to Redis (conversation history)
    try:
        client = get_redis()
        if client:
            conversation_entry = json.dumps({
                "question": question,
                "answer": answer,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            client.rpush(history_key, conversation_entry)
            client.expire(history_key, 86400)  # 24 hours TTL
    except Exception as e:
        logger.error(f"Failed to save history: {e}")
    
    # Log response
    logger.info(json.dumps({
        "event": "agent_response",
        "user_id": user_id,
        "answer_length": len(answer),
    }))
    
    # 4. Return response
    return AskResponse(
        question=question,
        answer=answer,
        user_id=user_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# Graceful shutdown handler
def handle_sigterm(*args):
    """Handle SIGTERM signal for graceful shutdown"""
    logger.info("Received SIGTERM - initiating graceful shutdown")


signal.signal(signal.SIGTERM, handle_sigterm)