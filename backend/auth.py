from datetime import datetime, timezone, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 15))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))

if not SECRET_KEY:
    raise ValueError("SECRET_KEY not found in environment variables")

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ==================== PASSWORD HASHING ====================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


# ==================== JWT TOKEN CREATION ====================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token
    
    Args:
        data: Dictionary with user data (typically {"sub": user_id})
        expires_delta: Optional custom expiration time
    
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "type": "access"
    })
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT refresh token
    
    Args:
        data: Dictionary with user data (typically {"sub": user_id})
        expires_delta: Optional custom expiration time
    
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "exp": expire,
        "type": "refresh"
    })
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# ==================== JWT TOKEN VERIFICATION ====================

def verify_token(token: str, token_type: str = "access") -> Optional[dict]:
    """
    Verify a JWT token and return payload
    
    Args:
        token: JWT token string
        token_type: "access" or "refresh"
    
    Returns:
        Token payload if valid, None if invalid
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Check token type
        if payload.get("type") != token_type:
            return None
        
        # Check expiration
        exp = payload.get("exp")
        if exp is None or datetime.fromtimestamp(exp, timezone.utc) < datetime.now(timezone.utc):
            return None
        
        return payload
    
    except JWTError:
        return None


def decode_token(token: str) -> Optional[dict]:
    """
    Decode a JWT token without verification (for debugging)
    
    Args:
        token: JWT token string
    
    Returns:
        Token payload if decodable, None if invalid
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_signature": False})
        return payload
    except JWTError:
        return None


# ==================== PASSWORD VALIDATION ====================
def validate_password(password: str) -> tuple[bool, list[str]]:
    rules = [
        (lambda p: len(p) >= 8, "at least 8 characters"),
        (lambda p: len(p.encode("utf-8")) <= 72, "maximum 72 characters"),
        (lambda p: any(c.isupper() for c in p), "one uppercase letter"),
        (lambda p: any(c.islower() for c in p), "one lowercase letter"),
        (lambda p: any(c.isdigit() for c in p), "one digit"),
    ]

    errors = [message for rule, message in rules if not rule(password)]

    return len(errors) == 0, errors

# def validate_password(password: str) -> tuple[bool, str]:
#     """
#     Validate password strength
    
#     Args:
#         password: Password to validate
    
#     Returns:
#         Tuple of (is_valid, error_message)
#     """
#     if len(password) < 8:
#         return False, "Password must be at least 8 characters long"
    
#     if not any(c.isupper() for c in password):
#         return False, "Password must contain at least one uppercase letter"
    
#     if not any(c.islower() for c in password):
#         return False, "Password must contain at least one lowercase letter"
    
#     if not any(c.isdigit() for c in password):
#         return False, "Password must contain at least one digit"
    
#     return True, ""


def validate_email(email: str) -> tuple[bool, str]:
    """
    Basic email validation
    
    Args:
        email: Email to validate
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    import re
    
    if not email:
        return False, "Email is required"
    
    # Basic email regex
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(pattern, email):
        return False, "Invalid email format"
    
    if len(email) > 255:
        return False, "Email too long"
    
    return True, ""


# ==================== TOKEN UTILITIES ====================

def get_token_expiry(token: str) -> Optional[datetime]:
    """
    Get expiration time of a token
    
    Args:
        token: JWT token string
    
    Returns:
        Expiration datetime if valid, None if invalid
    """
    payload = decode_token(token)
    if payload and "exp" in payload:
        return datetime.fromtimestamp(payload["exp"])
    return None


def is_token_expired(token: str) -> bool:
    """
    Check if a token is expired
    
    Args:
        token: JWT token string
    
    Returns:
        True if expired, False if still valid
    """
    expiry = get_token_expiry(token)
    if expiry is None:
        return True
    return expiry < datetime.now(timezone.utc)