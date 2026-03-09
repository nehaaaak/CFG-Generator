from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy import Index
from .database import Base
import uuid


class User(Base):
    """User model for authentication"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(60), nullable=False, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)

    is_active = Column(Integer, default=1)

    # ai_requests_used = Column(Integer, default=0)
    # AI Usage Tracking - Per Feature Type 
    ai_node_explain_used = Column(Integer, default=0)
    ai_path_explain_used = Column(Integer, default=0)
    ai_refactor_suggest_used = Column(Integer, default=0)
    ai_refactor_code_used = Column(Integer, default=0)
    ai_test_gen_used = Column(Integer, default=0)
    ai_requests_reset_date = Column(Date, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    sessions = relationship("CFGSession", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User {self.email}>"


class CFGSession(Base):
    """CFG Session model for storing user's CFG generations"""
    __tablename__ = "cfg_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), unique=True, index=True, nullable=False, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # CFG Data
    code = Column(Text, nullable=False)  # Original Python code
    cfg_data = Column(JSON, nullable=False)  # Complete CFG JSON response

    # Static Analysis Data
    static_analysis = Column(JSON, nullable=True)  # Reaching defs, live vars, smells
    
    # AI Generated Content
    overall_explanation = Column(Text, nullable=True)  # Public AI explanation
    
    # Metadata
    name = Column(String(255), nullable=True)  # Optional: user-given name
    description = Column(Text, nullable=True)  # Optional: description
    
    # Metrics for quick access
    overall_cc = Column(Integer, nullable=True)
    function_count = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    def __repr__(self):
        return f"<CFGSession {self.session_id}>"
    

class AIResponse(Base):
    """Store AI-generated responses for caching"""
    __tablename__ = "ai_responses"
    __table_args__ = (
    Index("idx_ai_cache", "input_hash", "feature_type"),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), ForeignKey("cfg_sessions.session_id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # AI Response Data
    feature_type = Column(String(50), nullable=False)  # node_explain, path_explain, etc.
    input_hash = Column(String(64), nullable=False, index=True)  # Hash of input for caching
    response_data = Column(JSON, nullable=False)
    
    # Metadata
    tokens_used = Column(Integer, nullable=True)
    model_used = Column(String(50), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<AIResponse {self.feature_type} for session {self.session_id}>"


class RefreshToken(Base):
    """Refresh tokens for JWT authentication"""
    __tablename__ = "refresh_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(500), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")
    
    def __repr__(self):
        return f"<RefreshToken for user {self.user_id}>"