from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db, init_db
from db_models import User, CFGSession

from auth import (
    get_password_hash, 
    verify_password, 
    create_access_token, 
    create_refresh_token,
    verify_token,
    validate_password,
    validate_email
)
from dependencies import get_current_user, get_current_user_optional

from models.api_models import (
    UserRegister, 
    UserLogin, 
    Token, 
    TokenRefresh,
    UserResponse,
    CodeInput,
    CFGResponse,
    SessionResponse,
    SessionListItem,
    SessionUpdate,
    AIQuotaResponse  
)


from cfg_logic.frontend_converter import generate_cfg_for_code
from models import FunctionCFG, Node, Edge

import uvicorn
import os
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print("CFG Generator API is running")
    yield
    print("API shutdown")


app = FastAPI(title="CFG Generator API", version="1.0", lifespan=lifespan)


origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Add your frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health(db: Session = Depends(get_db)):
    """Health check with DB connection test"""
    try:
        # Test database
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except:
        db_status = "disconnected"

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "database": db_status,
        "environment": os.getenv("ENVIRONMENT", "development")
    }
    

# ==================== AUTH ENDPOINTS ====================

@app.post("/api/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """Register a new user"""
    
    # Validate email
    is_valid, error = validate_email(user_data.email)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)
    
    # Validate password
    is_valid, error = validate_password(user_data.password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)
    
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        hashed_password=hashed_password
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user


@app.post("/api/auth/login", response_model=Token)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    """Login and get JWT tokens"""
    
    # Find user
    user = db.query(User).filter(User.email == user_data.email).first()
    
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password"
        )
    
    # Create tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@app.post("/api/auth/refresh", response_model=Token)
async def refresh_token(token_data: TokenRefresh, db: Session = Depends(get_db)):
    """Refresh access token using refresh token"""
    
    # Verify refresh token
    payload = verify_token(token_data.refresh_token, token_type="refresh")
    
    if payload is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired refresh token"
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    
    # Verify user exists
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    # Create new tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@app.get("/api/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return current_user


@app.get("/api/auth/quota", response_model=AIQuotaResponse)
async def get_ai_quota(current_user: User = Depends(get_current_user)):
    """Get user's AI feature quota status"""
    from dependencies import get_user_ai_quota
    return get_user_ai_quota(current_user)


# ==================== CFG ENDPOINTS (PROTECTED) ====================

@app.post("/api/cfg/generate", response_model=CFGResponse)
async def generate_cfg(
    input_data: CodeInput,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Generate CFG from Python code (requires authentication)"""
    try:
        code = input_data.code.strip()
        
        if not code:
            raise HTTPException(status_code=400, detail="Code cannot be empty")
        
        # Generate CFG using new system
        result = generate_cfg_for_code(code)
        
        if not result["success"]:
            return CFGResponse(
                success=False,
                functions=[],
                overall_cc=0,
                error=result["errors"][0] if result["errors"] else "Unknown error"
            )
        
        # Convert to response format
        function_cfgs = []
        for func_name, cfg_data in result["functions"].items():
            nodes = [
                Node(
                    id=n["id"],
                    label=n["label"],
                    type=n["type"],
                    x=n["x"],
                    y=n["y"],
                    line_number=n.get("line_number")
                )
                for n in cfg_data["nodes"]
            ]
            
            edges = [
                Edge(
                    from_node=e["from"],
                    to_node=e["to"],
                    label=e.get("label", "")
                )
                for e in cfg_data["edges"]
            ]
            
            func_cfg = FunctionCFG(
                name=func_name,
                nodes=nodes,
                edges=edges,
                cc=cfg_data["cyclomatic_complexity"],
                metrics=cfg_data["metrics"],
                paths=cfg_data.get("paths", [])
            )
            function_cfgs.append(func_cfg)
        
        overall_cc = sum(f.cc for f in function_cfgs)
        
        # Save to database
        if current_user:
            session = CFGSession(
                user_id=current_user.id,
                code=code,
                cfg_data=result,
                static_analysis={},  # Will populate with AI features later
                overall_explanation=None,  # Will populate with AI
                name=input_data.name,
                description=input_data.description,
                overall_cc=overall_cc,
                function_count=len(function_cfgs)
            )
        
        db.add(session)
        db.commit()
        db.refresh(session)
        
        return CFGResponse(
            success=True,
            functions=function_cfgs,
            overall_cc=overall_cc,
            error=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        return CFGResponse(
            success=False,
            functions=[],
            overall_cc=0,
            error=f"Error: {str(e)}"
        )


@app.get("/api/cfg/history", response_model=List[SessionListItem])
async def get_user_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0
):
    """Get user's CFG generation history"""
    sessions = db.query(CFGSession)\
        .filter(CFGSession.user_id == current_user.id)\
        .order_by(CFGSession.created_at.desc())\
        .limit(limit)\
        .offset(offset)\
        .all()
    
    return sessions


@app.get("/api/cfg/session/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific CFG session"""
    session = db.query(CFGSession)\
        .filter(CFGSession.session_id == session_id)\
        .filter(CFGSession.user_id == current_user.id)\
        .first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return session


@app.patch("/api/cfg/session/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    update_data: SessionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update session metadata (name, description)"""
    session = db.query(CFGSession)\
        .filter(CFGSession.session_id == session_id)\
        .filter(CFGSession.user_id == current_user.id)\
        .first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if update_data.name is not None:
        session.name = update_data.name
    if update_data.description is not None:
        session.description = update_data.description
    
    db.commit()
    db.refresh(session)
    
    return session


@app.delete("/api/cfg/session/{session_id}")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a CFG session"""
    session = db.query(CFGSession)\
        .filter(CFGSession.session_id == session_id)\
        .filter(CFGSession.user_id == current_user.id)\
        .first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    db.delete(session)
    db.commit()
    
    return {"message": "Session deleted successfully"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

