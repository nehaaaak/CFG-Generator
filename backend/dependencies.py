from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import date, timedelta
from .database import get_db
from .db_models import User
from .auth import verify_token
from typing import Optional

# Security scheme for JWT
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get current authenticated user from JWT token
    
    Usage:
        @app.get("/protected")
        async def protected_route(current_user: User = Depends(get_current_user)):
            return {"user": current_user.email}
    
    Raises:
        HTTPException: 401 if token is invalid or user not found
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please include a valid access token in the Authorization header.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    token = credentials.credentials
    
    # Verify token
    payload = verify_token(token, token_type="access")
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token. Please refresh your session or login again.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Get user ID from token
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload. User identifier missing.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Get user from database
    user = db.query(User).filter(User.id == int(user_id)).first()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with this token no longer exists.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    if user.is_active == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been disabled."
        )
    
    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Dependency to get current user (optional - doesn't fail if no token)
    
    Usage:
        @app.get("/maybe-protected")
        async def route(current_user: Optional[User] = Depends(get_current_user_optional)):
            if current_user:
                return {"user": current_user.email}
            return {"user": "anonymous"}
    """
    if credentials is None:
        return None
    
    try:
        token = credentials.credentials
        payload = verify_token(token, token_type="access")
        
        if payload is None:
            return None
        
        user_id = payload.get("sub")
        if user_id is None:
            return None
        
        user = db.query(User).filter(User.id == int(user_id)).first()

        if user and user.is_active == 1:
            return user
        
    except:
        return None


def verify_refresh_token(token: str) -> Optional[dict]:
    """
    Verify a refresh token
    
    Args:
        token: Refresh token string
    
    Returns:
        Token payload if valid, None if invalid
    """
    return verify_token(token, token_type="refresh")


# ==================== AI QUOTA MANAGEMENT ====================
DAILY_LIMIT_PER_FEATURE = 2  # 2 requests per feature type per day

def check_and_update_ai_quota(
    user: User, 
    feature_type: str, 
    db: Session
) -> None:
    """
    Check if user has quota remaining and update usage.
    Raises HTTPException if quota exceeded.
    
    Args:
        user: User object
        feature_type: One of: node_explain, path_explain, refactor_suggest, refactor_code, test_gen
        db: Database session
    
    Raises:
        HTTPException: 429 if quota exceeded
    """
    today = date.today()
    
    # Reset quota if it's a new day
    if user.ai_requests_reset_date is None or user.ai_requests_reset_date < today:
        user.ai_node_explain_used = 0
        user.ai_path_explain_used = 0
        user.ai_refactor_suggest_used = 0
        user.ai_refactor_code_used = 0
        user.ai_test_gen_used = 0
        user.ai_requests_reset_date = today
        db.commit()
    
    # Map feature type to column
    feature_map = {
        "node_explain": "ai_node_explain_used",
        "path_explain": "ai_path_explain_used",
        "refactor_suggest": "ai_refactor_suggest_used",
        "refactor_code": "ai_refactor_code_used",
        "test_gen": "ai_test_gen_used"
    }
    
    if feature_type not in feature_map:
        raise ValueError(f"Invalid AI feature type '{feature_type}'. Allowed values: node_explain, path_explain, refactor_suggest, refactor_code, test_gen.")
    
    # Check quota
    current_usage = getattr(user, feature_map[feature_type])
    
    if current_usage >= DAILY_LIMIT_PER_FEATURE:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily limit reached for '{feature_type}'. Each feature can be used {DAILY_LIMIT_PER_FEATURE} times per day. Quota resets tomorrow."
        )
    
    # Increment usage
    setattr(user, feature_map[feature_type], current_usage + 1)
    db.commit()


def get_user_ai_quota(user: User) -> dict:
    """Get user's remaining AI quota for all features"""
    today = date.today()
    
    # If reset date is past, all quotas are full
    if user.ai_requests_reset_date is None or user.ai_requests_reset_date < today:
        return {
            "node_explain_remaining": DAILY_LIMIT_PER_FEATURE,
            "path_explain_remaining": DAILY_LIMIT_PER_FEATURE,
            "refactor_suggest_remaining": DAILY_LIMIT_PER_FEATURE,
            "refactor_code_remaining": DAILY_LIMIT_PER_FEATURE,
            "test_gen_remaining": DAILY_LIMIT_PER_FEATURE,
            "reset_date": str(today)
        }
    
    return {
        "node_explain_remaining": DAILY_LIMIT_PER_FEATURE - user.ai_node_explain_used,
        "path_explain_remaining": DAILY_LIMIT_PER_FEATURE - user.ai_path_explain_used,
        "refactor_suggest_remaining": DAILY_LIMIT_PER_FEATURE - user.ai_refactor_suggest_used,
        "refactor_code_remaining": DAILY_LIMIT_PER_FEATURE - user.ai_refactor_code_used,
        "test_gen_remaining": DAILY_LIMIT_PER_FEATURE - user.ai_test_gen_used,
        "reset_date": str(user.ai_requests_reset_date)
    }



