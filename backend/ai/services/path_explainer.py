"""
Path Explanation Service
Generates explanations for execution paths through the CFG
"""

from typing import Dict, List
from sqlalchemy.orm import Session
from ..client_wrapper import generate_completion
from ..prompts.path_explain import build_prompt, extract_path_from_selection
from ..utils import create_input_hash
from ...db_models import CFGSession, AIResponse
from ...dependencies import check_ai_quota, update_ai_quota
from fastapi import HTTPException


def explain_path(
    session_id: str,
    function_name: str,
    path_node_ids: List[str],
    user,
    db: Session
) -> Dict:
    """
    Generate explanation for an execution path.
    
    Args:
        session_id: CFG session ID
        function_name: Function containing the path
        path_node_ids: Ordered list of node IDs forming the path
        db: Database session for caching
    
    Returns:
        {
            "explanation": str,
            "tokens_used": int,
            "cached": bool,
            "error": str | None
        }
    """
    # Get session data
    session = db.query(CFGSession).filter(
        CFGSession.session_id == session_id
    ).first()
    
    if not session:
        return {
            "explanation": "Session not found",
            "tokens_used": 0,
            "cached": False,
            "error": "Session not found"
        }
    
    # Extract CFG data
    cfg_data = session.cfg_data
    
    # Find the function
    # function_cfg = None
    # for func in cfg_data.get("functions", []):
    #     if func["name"] == function_name:
    #         function_cfg = func
    #         break

    function_cfg = None
    functions = cfg_data.get("functions", {})
    if isinstance(functions, dict):
        function_cfg = functions.get(function_name)
    else:
        for func in functions:
            if func["name"] == function_name:
                function_cfg = func
                break
    
    if not function_cfg:
        return {
            "explanation": "Function not found",
            "tokens_used": 0,
            "cached": False,
            "error": "Function not found"
        }
    
    # Validate path
    if not path_node_ids or len(path_node_ids) < 2:
        return {
            "explanation": "Path must contain at least 2 nodes",
            "tokens_used": 0,
            "cached": False,
            "error": "Invalid path"
        }
    
    # Normalize node IDs for consistent caching
    path_node_ids = [str(i).replace("B", "").strip() for i in path_node_ids]
    # path_node_ids = [str(i).strip() for i in path_node_ids]
    
    # Extract path context
    path_data = extract_path_from_selection(
        path_node_ids,
        function_cfg["nodes"],
        function_cfg["edges"]
    )

    # Safety check
    if not path_data["path_blocks"]:
        return {
            "explanation": "Unable to reconstruct the selected path",
            "tokens_used": 0,
            "cached": False,
            "error": "Invalid path structure"
        }
    
    # Create cache key
    cache_input = {
        "feature": "path_explain",
        "function": function_name,
        "path_nodes": tuple(path_node_ids)
    }

    input_hash = create_input_hash(cache_input)
    
    # Check cache
    cached = db.query(AIResponse).filter(
        AIResponse.feature_type == "path_explain",
        AIResponse.input_hash == input_hash
    ).first()
    
    if cached:
        return {
            "explanation": cached.response_data.get("explanation", ""),
            "tokens_used": cached.tokens_used or 0,
            "cached": True,
            "error": None
        }
    
    try:
        check_ai_quota(user, "path_explain", db)
    except HTTPException as e:
        return {
            "explanation": "",
            "tokens_used": 0,
            "cached": False,
            "error": e.detail if hasattr(e, "detail") else str(e)
        }
    
    # Generate explanation
    prompt = build_prompt(
        path_blocks=path_data["path_blocks"],
        edge_conditions=path_data["edge_conditions"],
        function_name=function_name
    )

    print("DEBUG path prompt:", prompt)
    
    result = generate_completion(
        prompt=prompt,
        max_tokens=510,
        temperature=0.4,
        thinking_budget=60
    )
    text = result.get("text", "").strip()
    if not text:
        text = "This path represents a sequence of execution steps through the control flow graph."
    
    if result["error"]:
        return {
            "explanation": text,
            "tokens_used": result["tokens_used"],
            "cached": False,
            "error": result["error"]
        }
    
    update_ai_quota(user, "path_explain", db)

    # Store in cache
    try:
        ai_response = AIResponse(
            session_id=None,
            user_id=None,
            feature_type="path_explain",
            input_hash=input_hash,
            response_data={"explanation": text},
            tokens_used=result["tokens_used"],
            model_used="gemini-2.5-flash"
        )
        db.add(ai_response)
        db.commit()
    except Exception as e:
        print(f"Cache storage error: {e}")
    
    return {
        "explanation": text,
        "tokens_used": result["tokens_used"],
        "cached": False,
        "error": None
    }