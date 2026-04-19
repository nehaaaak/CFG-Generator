from fastapi import FastAPI, HTTPException, Depends, status, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, text
from sqlalchemy.orm import Session
from typing import List, Optional
import ast
from .database import get_db, init_db
from .db_models import User, CFGSession, AIResponse
from .ai.utils import create_input_hash  

from .auth import (
    get_password_hash, 
    verify_password, 
    create_access_token, 
    create_refresh_token,
    verify_token,
    validate_password,
    validate_email,
    set_refresh_cookie,
    clear_refresh_cookie,
    get_refresh_token_from_cookie
)
from .dependencies import get_current_user, get_current_user_optional, get_user_ai_quota

from .models.api_models import (
    UserRegister, 
    UserLogin, 
    Token, 
    UserResponse,
    RegisterResponse,
    LoginResponse,
    CodeInput,
    CFGResponse,
    SessionResponse,
    SessionListItem,
    SessionUpdate,
    AINodeExplainRequest,
    AINodeExplainResponse,
    AIPathExplainRequest,
    AIPathExplainResponse,
    AIRefactorSuggestRequest,
    AIRefactorSuggestResponse,
    AIRefactorCodeRequest,
    AIRefactorCodeResponse,
    AIQuotaResponse,
    CFGCompareMetrics,
    CFGCompareRequest,
    CFGCompareResponse  
)


from .cfg_logic.frontend_converter import generate_cfg_for_code
from .cfg_logic.code_analysis import run_complete_static_analysis
from .cfg_logic.cfg_builder import build_function_cfg

from .models.api_models import FunctionCFG, Node, Edge

from .ai.services.overall_explainer import generate_from_static_analysis as generate_overall_explanation_ai
from .ai.services.node_explainer import explain_node as explain_node_service
from .ai.services.path_explainer import explain_path as explain_path_service
from .ai.services.refactor_suggester import suggest_refactoring
from .ai.services.refactor_coder import refactor_code as refactor_code_service

import uvicorn
import os
from contextlib import asynccontextmanager
import hashlib


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


@app.get("/")
async def root():
    return {
        "message": "CFG Generator API",
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }


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

@app.post("/api/auth/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """Register a new user"""
    
    # Validate email
    is_valid, error = validate_email(user_data.email)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)
    
    # Validate password
    is_valid, errors = validate_password(user_data.password)

    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail={"message": "Password requirements not met", "errors": errors}
        )
    
    # Check if user already exists
    existing_user = db.query(User).filter(func.lower(User.email) == user_data.email.lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="An account with this email already exists. Try logging in instead."
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        full_name=user_data.full_name.strip(),
        email=user_data.email,
        hashed_password=hashed_password
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {
    "message": "User created successfully!",
    "user": new_user
    }


@app.post("/api/auth/login", response_model=LoginResponse)
async def login(user_data: UserLogin, response: Response, db: Session = Depends(get_db)):
    """Login and get JWT tokens"""
    
    # Find user
    user = db.query(User).filter(User.email == user_data.email).first()

    if user and user.is_active == 0:
        raise HTTPException(
            status_code=403,
            detail="This account has been disabled."
        )
    
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Invalid login credentials. Please check your email and password."
        )
    
    # Create tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    # Store refresh token in secure HTTP-only cookie
    set_refresh_cookie(response, refresh_token)
    
    return {
        "message": "Login successful!",
        "full_name": user.full_name,
        "user_id": user.id,
        "access_token": access_token,
        # "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@app.post("/api/auth/refresh", response_model=Token)
async def refresh_token(request: Request, response: Response, db: Session = Depends(get_db)):
    refresh_token = get_refresh_token_from_cookie(request)
    if not refresh_token:
        raise HTTPException(
            status_code=401,
            detail="Refresh token cookie not found. User may not be logged in or cookie expired."
        )

    payload = verify_token(refresh_token, token_type="refresh")

    if payload is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired refresh token. Please login again."
        )

    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Malformed token payload: user ID missing."
        )

    user = db.query(User).filter(User.id == int(user_id)).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User associated with this token no longer exists."
        )

    new_access_token = create_access_token(data={"sub": str(user.id)})

    # Optional: rotate refresh token (good practice)
    new_refresh_token = create_refresh_token(data={"sub": str(user.id)})
    set_refresh_cookie(response, new_refresh_token)

    return {
        "access_token": new_access_token,
        "token_type": "bearer"
    }


# @app.post("/api/auth/refresh", response_model=Token)
# async def refresh_token(token_data: TokenRefresh, db: Session = Depends(get_db)):
#     """Refresh access token using refresh token"""
    
#     # Verify refresh token
#     payload = verify_token(token_data.refresh_token, token_type="refresh")
    
#     if payload is None:
#         raise HTTPException(
#             status_code=401,
#             detail="Invalid or expired refresh token"
#         )
    
#     user_id = payload.get("sub")
#     if not user_id:
#         raise HTTPException(status_code=401, detail="Invalid token payload")
    
#     # Verify user exists
#     user = db.query(User).filter(User.id == int(user_id)).first()
#     if not user:
#         raise HTTPException(status_code=401, detail="User not found")
    
#     # Create new tokens
#     access_token = create_access_token(data={"sub": str(user.id)})
#     refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
#     return {
#         "access_token": access_token,
#         "refresh_token": refresh_token,
#         "token_type": "bearer"
#     }


@app.get("/api/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return current_user


@app.post("/api/auth/logout")
async def logout(response: Response, current_user: User = Depends(get_current_user)):
    clear_refresh_cookie(response)
    return {
        "message": "Logout successful. Refresh token cookie cleared."
    }


@app.get("/api/auth/quota", response_model=AIQuotaResponse)
async def get_ai_quota(current_user: User = Depends(get_current_user)):
    """Get user's AI feature quota status"""
    return get_user_ai_quota(current_user)


# ==================== CFG ENDPOINTS ====================

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
        
        # if not result["success"]:
        #     return CFGResponse(
        #         success=False,
        #         functions=[],
        #         overall_cc=0,
        #         error=result["errors"][0] if result["errors"] else "Unknown error"
        #     )

        if not result["success"]:
            raise HTTPException(
                status_code=400,
                detail=result["errors"][0] if result["errors"] else "Unknown error"
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
                    line_number=n.get("line_number"),
                    block_number=n.get("block_number"),
                    code_statements=n.get("code_statements")
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
        
        static_analysis_results = {}
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_cfg = build_function_cfg(node, node.name)
                    func_code = ast.unparse(node)
                    
                    analysis = run_complete_static_analysis(func_cfg, func_code)
                    static_analysis_results[node.name] = analysis
        except Exception as e:
            print(f"Static analysis error: {e}")
            static_analysis_results = {"error": str(e)}

        # Generate AI explanation (PUBLIC-for all users)
        # overall_ai_explanation = None
        # try:
        #     # Collect unreachable code from all functions
        #     all_unreachable = []
        #     for func_cfg in function_cfgs:
        #         if hasattr(func_cfg, 'unreachable_code') and func_cfg.unreachable_code:
        #             all_unreachable.extend(func_cfg.unreachable_code)
            
        #     overall_ai_explanation = generate_overall_explanation_ai(
        #         result, 
        #         static_analysis_results,
        #         all_unreachable
        #     )
        # except Exception as e:
        #     print(f"AI explanation error: {e}")
        #     overall_ai_explanation = None

        # # Save to database
        # if current_user:
        #     session = CFGSession(
        #         user_id=current_user.id,
        #         code=code,
        #         cfg_data=result,
        #         static_analysis=static_analysis_results,  
        #         overall_explanation=overall_ai_explanation,
        #         name=input_data.name,
        #         description=input_data.description,
        #         overall_cc=overall_cc,
        #         function_count=len(function_cfgs)
        #     )
        
        #     db.add(session)
        #     db.commit()
        #     db.refresh(session)

        # session_id_to_return = session.session_id if current_user and session else None

        # return CFGResponse(
        #     success=True,
        #     functions=function_cfgs,
        #     overall_cc=overall_cc,
        #     static_analysis=static_analysis_results,
        #     ai_explanation=overall_ai_explanation,
        #     session_id=session_id_to_return,
        #     error=None
        # )

        all_unreachable = []
        for func_cfg in function_cfgs:
            if hasattr(func_cfg, 'unreachable_code') and func_cfg.unreachable_code:
                all_unreachable.extend(func_cfg.unreachable_code)

        session = None
        if current_user:
            session = CFGSession(
                user_id=current_user.id,
                code=code,
                cfg_data=result,
                static_analysis=static_analysis_results,
                overall_explanation=None,  # will update after AI call
                name=input_data.name,
                description=input_data.description,
                overall_cc=overall_cc,
                function_count=len(function_cfgs)
            )
            db.add(session)
            db.commit()
            db.refresh(session)

        overall_ai_explanation = None
        try:
            cache_input = {
                "code": code,
                "feature": "overall_explain"
            }
            input_hash = create_input_hash(cache_input)

            # ✅ Logged-in users → cache
            if current_user and session:
                cached = db.query(AIResponse).filter(
                    AIResponse.session_id == session.session_id,
                    AIResponse.feature_type == "overall_explain",
                    AIResponse.input_hash == input_hash
                ).first()

                if cached:
                    overall_ai_explanation = cached.response_data.get("explanation", "")
                else:
                    overall_ai_explanation = generate_overall_explanation_ai(
                        result,
                        static_analysis_results,
                        all_unreachable
                    )

                    # store in cache
                    try:
                        ai_response = AIResponse(
                            session_id=session.session_id,
                            user_id=current_user.id,
                            feature_type="overall_explain",
                            input_hash=input_hash,
                            response_data={"explanation": overall_ai_explanation},
                            tokens_used=None,
                            model_used="gemini-2.5-flash"
                        )
                        db.add(ai_response)
                        db.commit()
                    except Exception as e:
                        print("Cache save error:", e)

            # ✅ Non-logged-in users → no cache
            else:
                overall_ai_explanation = generate_overall_explanation_ai(
                    result,
                    static_analysis_results,
                    all_unreachable
                )

        except Exception as e:
            print(f"AI explanation error: {e}")
            overall_ai_explanation = None

        if session:
            session.overall_explanation = overall_ai_explanation
            db.commit()

        session_id_to_return = session.session_id if session else None

        return CFGResponse(
            success=True,
            functions=function_cfgs,
            overall_cc=overall_cc,
            static_analysis=static_analysis_results,
            ai_explanation=overall_ai_explanation,
            session_id=session_id_to_return,
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


@app.post("/api/cfg/analyze-static")
async def analyze_static(
    input_data: CodeInput,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    try:
        code = input_data.code.strip()
        if not code:
            raise HTTPException(status_code=400, detail="Code cannot be empty")
        
        tree = ast.parse(code)
        results = {}
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_cfg = build_function_cfg(node, node.name)
                func_code = ast.unparse(node)
                analysis = run_complete_static_analysis(func_cfg, func_code)
                results[node.name] = analysis
        
        return {
            "success": True,
            "analysis": results
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# ==================== AI ENDPOINTS ====================
@app.post("/api/ai/explain-node", response_model=AINodeExplainResponse)
async def explain_node(
    request: AINodeExplainRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Explain a specific CFG node (Protected - 2/day limit)
    """
    # Check quota
    # try:
    #     check_and_update_ai_quota(current_user, "node_explain", db)
    # except HTTPException as e:
    #     raise e
    
    # Generate explanation
    result = explain_node_service(
        session_id=request.session_id,
        function_name=request.function_name,
        node_id=request.node_id,
        user=current_user,
        db=db
    )
    
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    
    return AINodeExplainResponse(
        explanation=result["explanation"],
        tokens_used=result["tokens_used"],
        cached=result["cached"],
        error=result.get("error")
    )


@app.post("/api/ai/explain-path", response_model=AIPathExplainResponse)
async def explain_path(
    request: AIPathExplainRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Explain an execution path through the CFG (Protected - 2/day limit)
    """
    # Check quota
    # try:
    #     check_and_update_ai_quota(current_user, "path_explain", db)
    # except HTTPException as e:
    #     raise e
    
    # Generate explanation
    result = explain_path_service(
        session_id=request.session_id,
        function_name=request.function_name,
        path_node_ids=request.path_node_ids,
        user=current_user,
        db=db
    )
    
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return AIPathExplainResponse(
        explanation=result["explanation"],
        tokens_used=result["tokens_used"],
        cached=result["cached"],
        error=result.get("error")
    )


@app.post("/api/ai/refactor-suggest", response_model=AIRefactorSuggestResponse)
async def refactor_suggest(
    request: AIRefactorSuggestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get AI refactoring suggestions (Protected - 2/day limit)
    """
    # Check quota
    # try:
    #     check_and_update_ai_quota(current_user, "refactor_suggest", db)
    # except HTTPException as e:
    #     raise e
    
    # Generate suggestions
    result = suggest_refactoring(
        session_id=request.session_id,
        user=current_user,
        function_name=request.function_name,
        db=db
    )

    if result.get("error"):
        return AIRefactorSuggestResponse(
            parsed_suggestions=[],
            suggestions=result.get("suggestions", ""),
            tokens_used=result.get("tokens_used", 0),
            cached=result.get("cached", False),
            error=result["error"]
        )
    
    return AIRefactorSuggestResponse(
        parsed_suggestions=result.get("parsed_suggestions", []),
        suggestions=result.get("suggestions", ""),
        tokens_used=result["tokens_used"],
        cached=result["cached"],
        error=result.get("error")
    )


@app.post("/api/ai/refactor-code", response_model=AIRefactorCodeResponse)
async def refactor_code_endpoint(
    request: AIRefactorCodeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):  
    # try:
    #     check_and_update_ai_quota(current_user, "refactor_code", db)
    # except HTTPException as e:
    #     raise e

    result = refactor_code_service(
        session_id=request.session_id,
        user=current_user,
        function_name=request.function_name,
        db=db
    )
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    
    return AIRefactorCodeResponse(**result)


@app.post("/api/ai/compare-cfg", response_model=CFGCompareResponse)
async def compare_cfg_endpoint(
    request: CFGCompareRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Get original metrics from session
        session = db.query(CFGSession).filter(
            CFGSession.session_id == request.session_id
        ).first()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        static_analysis = session.static_analysis or {}
        if request.function_name not in static_analysis:
            raise HTTPException(status_code=404, detail="Function not found")

        # Extract original function metrics from stored static analysis
        original_analysis = session.static_analysis.get(request.function_name, {})
        original_metrics = original_analysis.get("metrics", {})
        original_issues = (
            len(original_analysis.get("code_smells", [])) +
            len(original_analysis.get("hotspots", []))
        )

        original_cfg = None
        functions = session.cfg_data.get("functions", {})

        for fname, fdata in functions.items():
            if fname == request.function_name:
                original_cfg = {
                    "nodes": fdata.get("nodes", []),
                    "edges": fdata.get("edges", [])
                }
                break

        if not original_cfg:
            raise HTTPException(status_code=404, detail="Original CFG not found")

        original = CFGCompareMetrics(
            cyclomatic_complexity=original_metrics.get("cyclomatic_complexity", 0),
            nodes=original_metrics.get("nodes", 0),
            edges=original_metrics.get("edges", 0),
            decision_points=original_metrics.get("decision_points", 0),
            loops=original_metrics.get("loops", 0),
            risk_level=original_metrics.get("risk_level", "Unknown"),
            complexity_category=original_metrics.get("complexity_category", "Unknown"),
            issues_count=original_issues,
            code_smells=original_analysis.get("code_smells", []),
            hotspots=original_analysis.get("hotspots", [])
        )

        function_code = _extract_function_code(session.code, request.function_name)

        if not function_code:
            raise HTTPException(status_code=400, detail="Original function extraction failed")

        code_hash = hashlib.sha256(function_code.encode()).hexdigest()

        cache_input = {
            "session_id": request.session_id,
            "function": request.function_name,
            "code_hash": code_hash
        }

        input_hash = create_input_hash(cache_input)

        # Get refactored code from cache
        cached_refactor = db.query(AIResponse).filter(
            AIResponse.session_id == request.session_id,
            AIResponse.feature_type == "refactor_code",
            AIResponse.input_hash == input_hash
        ).first()

        if not cached_refactor:
            raise HTTPException(status_code=404, detail="No refactored code found. Generate refactoring first.")

        refactored_code = cached_refactor.response_data.get("refactored_code", "")
        if not refactored_code:
            raise HTTPException(status_code=404, detail="Refactored code is empty")

        # Generate CFG for refactored code
        try:
            refactored_result = generate_cfg_for_code(refactored_code)
            if not refactored_result["success"]:
                raise HTTPException(status_code=400, detail="Failed to generate CFG for refactored code")

            ref_func = refactored_result["functions"].get(request.function_name)

            if not ref_func:
                ref_func = list(refactored_result["functions"].values())[0]

            ref_cfg = {
                "nodes": ref_func.get("nodes", []),
                "edges": ref_func.get("edges", [])
            }

            # Get the specific function's data
            func_data = refactored_result["functions"].get(request.function_name)
            if not func_data:
                # fallback to first function
                func_data = list(refactored_result["functions"].values())[0]

            refactored_metrics_raw = func_data.get("metrics", {})

            # Run static analysis for issues count
            refactored_issues = 0
            refactored_smells = []
            refactored_hotspots = []

            target_func_node = None
            try:
                tree = ast.parse(refactored_code)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name == request.function_name:
                        target_func_node = node
                        break

                # fallback (if name mismatch)
                if not target_func_node:
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            target_func_node = node
                            break
                    
                if target_func_node:
                    func_cfg = build_function_cfg(node, node.name)
                    func_code = ast.unparse(node)
                    analysis = run_complete_static_analysis(func_cfg, func_code)
                    refactored_smells = analysis.get("code_smells", [])
                    refactored_hotspots = analysis.get("hotspots", [])
                    refactored_issues = (
                        len(refactored_smells) +
                        len(refactored_hotspots)
                        )
                    # break
            except Exception as e:
                print(f"Refactored static analysis error: {e}")

            refactored = CFGCompareMetrics(
                cyclomatic_complexity=refactored_metrics_raw.get("cyclomatic_complexity", 0),
                nodes=refactored_metrics_raw.get("nodes", 0),
                edges=refactored_metrics_raw.get("edges", 0),
                decision_points=refactored_metrics_raw.get("decision_points", 0),
                loops=refactored_metrics_raw.get("loops", 0),
                risk_level=refactored_metrics_raw.get("risk_level", "Unknown"),
                complexity_category=refactored_metrics_raw.get("complexity_category", "Unknown"),
                issues_count=refactored_issues,
                code_smells=refactored_smells,
                hotspots=refactored_hotspots
            )

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"CFG generation error: {str(e)}")

        return CFGCompareResponse(
            original={
                "metrics": original,
                "cfg": original_cfg
            },
            refactored={
                "metrics": refactored,
                "cfg": ref_cfg
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        return CFGCompareResponse(
            original={
                "metrics": CFGCompareMetrics(
                    cyclomatic_complexity=0,
                    nodes=0,
                    edges=0,
                    decision_points=0,
                    loops=0,
                    risk_level="Unknown",
                    complexity_category="Unknown",
                    issues_count=0
                ),
                "cfg": {
                    "nodes": [],
                    "edges": []
                }
            },
            refactored={
                "metrics": CFGCompareMetrics(
                    cyclomatic_complexity=0,
                    nodes=0,
                    edges=0,
                    decision_points=0,
                    loops=0,
                    risk_level="Unknown",
                    complexity_category="Unknown",
                    issues_count=0
                ),
                "cfg": {
                    "nodes": [],
                    "edges": []
                }
            },
            error=str(e)
        )

def _extract_function_code(full_code: str, function_name: str) -> Optional[str]:
    try:
        tree = ast.parse(full_code)
        lines = full_code.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                start = node.lineno - 1
                end = node.end_lineno
                return '\n'.join(lines[start:end])
        return None
    except Exception as e:
        print(f"Function extraction error: {e}")
        return None






if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

