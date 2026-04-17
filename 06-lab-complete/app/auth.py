"""
API Key Authentication Module

Simple API key authentication for production agent.
In production, consider using JWT for more features.
"""
from fastapi import Header, HTTPException
from .config import settings


def verify_api_key(x_api_key: str = Header(..., description="API Key for authentication")) -> str:
    """
    Dependency: Verify API key from X-API-Key header.
    
    Args:
        x_api_key: API key from request header
        
    Returns:
        user_id: Extracted from API key or default
        
    Raises:
        HTTPException 401: If API key is invalid or missing
    """
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Include header: X-API-Key: <your-key>",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    # Verify against configured API key
    if x_api_key != settings.agent_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    # Extract user_id from API key (simplified)
    # In production, you might decode JWT or lookup in database
    user_id = f"user_{hash(x_api_key) % 10000}"
    
    return user_id