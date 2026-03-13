"""
Node Explanation Service
Generates graph-aware explanations for individual CFG nodes
"""

from typing import Dict, Optional
from sqlalchemy.orm import Session
from ..client_wrapper import generate_completion
from ..prompts.node_explain import build_prompt, format_node_context_for_prompt
from ..utils import create_input_hash
from ...db_models import CFGSession, AIResponse
import json


def explain_node(
    session_id: str,
    function_name: str,
    node_id: str,
    db: Session
) -> Dict:
    """
    Generate explanation for a specific CFG node.
    
    Args:
        session_id: CFG session ID
        function_name: Function containing the node
        node_id: Node ID to explain (can be numeric ID or block number)
        db: Database session for caching
    
    Returns:
        {
            "explanation": str,
            "tokens_used": int,
            "cached": bool,
            "error": str | None
        }
    """
    node_id_str = str(node_id)
    node_id_normalized = node_id_str.replace("B", "")

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
    function_cfg = None
    for func in cfg_data.get("functions", []):
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
    
    # # Find the node
    # target_node = None
    # for node in function_cfg["nodes"]:
    #     # Match by ID or block number
    #     if (node["id"] == node_id or 
    #         str(node.get("block_number")) == str(node_id) or
    #         f"B{node.get('block_number')}" == node_id):
    #         target_node = node
    #         break

    # Find the node
    target_node = None

    for node in function_cfg["nodes"]:

        node_block = str(node.get("block_number"))
        node_internal = str(node.get("id"))

        if (
            node_internal == node_id_str or
            node_block == node_id_normalized
        ):
            target_node = node
            break
    
    if not target_node:
        return {
            "explanation": "Node not found",
            "tokens_used": 0,
            "cached": False,
            "error": "Node not found"
        }
    
    # ------------------------------
    # SAFEGUARDS (no AI required)
    # ------------------------------

    block_type = target_node.get("type", "").lower()
    code_statements = target_node.get("code_statements") or []

    # START node
    if block_type == "start":
        return {
            "explanation": (
                "This is the entry point of the control flow graph. "
                "Execution begins here before moving to the first executable block."
            ),
            "tokens_used": 0,
            "cached": False,
            "error": None
        }

    # END node
    if block_type == "end":
        return {
            "explanation": (
                "This is the termination point of the control flow graph. "
                "Execution reaches this block after the program finishes or returns."
            ),
            "tokens_used": 0,
            "cached": False,
            "error": None
        }

    # Empty block safeguard
    if not code_statements:
        return {
            "explanation": (
                "This block represents a structural control point in the control flow graph "
                "but does not contain executable statements."
            ),
            "tokens_used": 0,
            "cached": False,
            "error": None
        }

    # Format context
    context = format_node_context_for_prompt(
        target_node,
        function_cfg["nodes"],
        function_cfg["edges"],
        function_cfg.get("paths", [])
    )
    
    # Create cache key
    cache_input = {
        "session_id": session_id,
        "function": function_name,
        "node_id": node_id,
        "context": context
    }
    input_hash = create_input_hash(cache_input)
    
    # Check cache
    cached = db.query(AIResponse).filter(
        AIResponse.session_id == session_id,
        AIResponse.feature_type == "node_explain",
        AIResponse.input_hash == input_hash
    ).first()
    
    if cached:
        return {
            "explanation": cached.response_data.get("explanation", ""),
            "tokens_used": cached.tokens_used or 0,
            "cached": True,
            "error": None
        }
    
    # Generate explanation
    prompt = build_prompt(
        node_data=context["node_data"],
        predecessors=context["predecessors"],
        successors=context["successors"],
        paths_through_node=context["paths_through_node"],
        loop_context=context["loop_context"],
        function_name=function_name
    )
    
    result = generate_completion(
        prompt=prompt,
        max_tokens=200,  # Slightly longer for detailed explanation
        temperature=0.4
    )
    
    if result["error"]:
        return {
            "explanation": result["text"],
            "tokens_used": result["tokens_used"],
            "cached": False,
            "error": result["error"]
        }
    
    # Store in cache
    try:
        ai_response = AIResponse(
            session_id=session_id,
            user_id=session.user_id,
            feature_type="node_explain",
            input_hash=input_hash,
            response_data={"explanation": result["text"]},
            tokens_used=result["tokens_used"],
            model_used="gemini-2.5-flash"
        )
        db.add(ai_response)
        db.commit()
    except Exception as e:
        print(f"Cache storage error: {e}")
    
    return {
        "explanation": result["text"],
        "tokens_used": result["tokens_used"],
        "cached": False,
        "error": None
    }