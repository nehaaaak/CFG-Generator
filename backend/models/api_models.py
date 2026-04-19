from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


# ==================== AUTH MODELS ====================

class UserRegister(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=60)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: str
    is_active: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class RegisterResponse(BaseModel):
    message: str
    user: UserResponse


class LoginResponse(BaseModel):
    message: str
    full_name: str
    user_id: int
    access_token: str
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
    static_analysis: Optional[Dict[str, Any]] = None
    ai_explanation: Optional[str] = None
    session_id: Optional[str] = None
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


# class AITestGenRequest(BaseModel):
#     """Request test case generation"""
#     session_id: str
#     function_name: str


class AIResponse(BaseModel):
    """Generic AI response"""
    success: bool
    content: str
    tokens_used: Optional[int] = None
    cached: bool = False
    error: Optional[str] = None


class AINodeExplainResponse(BaseModel):
    """Response from node explanation"""
    explanation: str
    tokens_used: Optional[int] = None
    cached: bool
    error: Optional[str] = None


class AIPathExplainResponse(BaseModel):
    """Response from path explanation"""
    explanation: str
    tokens_used: Optional[int] = None
    cached: bool
    error: Optional[str] = None


class RefactorSuggestionItem(BaseModel):
    priority: int
    refactoring: str
    problem: str
    solution: str
    benefit: str
    lines: str


class AIRefactorSuggestResponse(BaseModel):
    """Response with refactoring suggestions"""
    parsed_suggestions: List[RefactorSuggestionItem]
    suggestions: str
    tokens_used: Optional[int] = None
    cached: bool
    error: Optional[str] = None


class AIRefactorCodeResponse(BaseModel):
    original_code: str
    refactored_code: str
    changes: Optional[str] = ""  
    tokens_used: Optional[int] = None
    cached: bool
    error: Optional[str] = None  


class AIQuotaResponse(BaseModel):
    """User's AI quota status"""
    node_explain_remaining: int
    path_explain_remaining: int
    refactor_suggest_remaining: int
    refactor_code_remaining: int
    # test_gen_remaining: int
    reset_date: Optional[str] = None


# ==================== COMPARE MODELS ====================

class CFGCompareRequest(BaseModel):
    session_id: str
    function_name: str

class CFGCompareMetrics(BaseModel):
    cyclomatic_complexity: int
    nodes: int
    edges: int
    decision_points: int
    loops: int
    risk_level: str
    complexity_category: str
    issues_count: int  
    code_smells: List[Dict[str, Any]] = []
    hotspots: List[Dict[str, Any]] = []

class CFGData(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]

class CFGCompareResult(BaseModel):
    metrics: CFGCompareMetrics
    cfg: CFGData

class CFGCompareResponse(BaseModel):
    original: CFGCompareResult
    refactored: CFGCompareResult
    error: Optional[str] = None

# class CFGCompareResponse(BaseModel):
#     original: CFGCompareMetrics
#     refactored: CFGCompareMetrics
#     error: Optional[str] = None