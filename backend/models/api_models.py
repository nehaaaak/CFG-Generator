from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


# ==================== AUTH MODELS ====================

class UserRegister(BaseModel):
    """User registration request"""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)


class UserLogin(BaseModel):
    """User login request"""
    email: EmailStr
    password: str


class Token(BaseModel):
    """JWT token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    """Refresh token request"""
    refresh_token: str


class UserResponse(BaseModel):
    """User data response"""
    id: int
    email: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class RegisterResponse(BaseModel):
    message: str
    user: UserResponse


class LoginResponse(BaseModel):
    message: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"



# ==================== CFG MODELS ====================

class CodeInput(BaseModel):
    """Input for CFG generation"""
    code: str
    name: Optional[str] = None
    description: Optional[str] = None


class Node(BaseModel):
    """CFG Node"""
    id: str
    label: str
    type: str
    x: int = 0
    y: int = 0
    line_number: Optional[int] = None
    block_number: Optional[int] = None  
    code_statements: Optional[List[str]] = None


class Edge(BaseModel):
    """CFG Edge"""
    from_node: str
    to_node: str
    label: str = ""


class FunctionCFG(BaseModel):
    """CFG for a single function"""
    name: str
    nodes: List[Node]
    edges: List[Edge]
    cc: int
    metrics: Dict[str, Any]
    paths: Optional[List[List[str]]] = []
    unreachable_code: Optional[List[Dict[str, Any]]] = []


class CFGResponse(BaseModel):
    """Response from CFG generation"""
    success: bool
    functions: List[FunctionCFG]
    overall_cc: int
    error: Optional[str] = None


# ==================== SESSION MODELS ====================

class SessionCreate(BaseModel):
    """Create a CFG session"""
    code: str
    cfg_data: Dict[str, Any]
    name: Optional[str] = None
    description: Optional[str] = None
    overall_cc: Optional[int] = None
    function_count: Optional[int] = None


class SessionResponse(BaseModel):
    """CFG session response"""
    id: int
    session_id: str
    user_id: int
    code: str
    cfg_data: Dict[str, Any]
    name: Optional[str] = None
    description: Optional[str] = None
    overall_cc: Optional[int] = None
    function_count: Optional[int] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class SessionListItem(BaseModel):
    """Simplified session for list view"""
    id: int
    session_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    overall_cc: Optional[int] = None
    function_count: Optional[int] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class SessionUpdate(BaseModel):
    """Update session metadata"""
    name: Optional[str] = None
    description: Optional[str] = None


# ==================== AI REQUEST/RESPONSE MODELS ====================

class AINodeExplainRequest(BaseModel):
    """Request to explain a specific node"""
    session_id: str
    function_name: str
    node_id: str


class AIPathExplainRequest(BaseModel):
    """Request to explain an execution path"""
    session_id: str
    function_name: str
    path_node_ids: List[str]


class AIRefactorSuggestRequest(BaseModel):
    """Request refactoring suggestions"""
    session_id: str
    function_name: Optional[str] = None  # None = entire code


class AIRefactorCodeRequest(BaseModel):
    """Request actual code refactoring"""
    session_id: str
    function_name: Optional[str] = None
    target_goal: str  # e.g., "reduce_cc", "simplify_nesting"


class AITestGenRequest(BaseModel):
    """Request test case generation"""
    session_id: str
    function_name: str


class AIResponse(BaseModel):
    """Generic AI response"""
    success: bool
    content: str
    tokens_used: Optional[int] = None
    cached: bool = False
    error: Optional[str] = None


class AIQuotaResponse(BaseModel):
    """User's AI quota status"""
    node_explain_remaining: int
    path_explain_remaining: int
    refactor_suggest_remaining: int
    refactor_code_remaining: int
    test_gen_remaining: int
    reset_date: Optional[str] = None



