"""
Refactor Code Service
Generates actual refactored code using AI
"""

from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from ..client_wrapper import generate_completion
from ..prompts.refactor_code import build_prompt, prepare_refactor_input, parse_refactor_response
from ..prompts.refactor_suggest import build_prompt as suggest_prompt, prepare_refactor_context
from ..services.refactor_suggester import parse_refactor_suggestions
from ..utils import create_input_hash, normalize_code
from ...db_models import CFGSession, AIResponse
from ...dependencies import check_ai_quota, update_ai_quota
from fastapi import HTTPException
import ast
import hashlib


MAX_CODE_LINES = 30


def refactor_code(
    session_id: str,
    user,
    function_name: Optional[str] = None,
    db: Session = None
) -> Dict:
    # Get session
    session = db.query(CFGSession).filter(
        CFGSession.session_id == session_id
    ).first()

    if not session:
        return _error_response("Session not found")

    static_analysis = session.static_analysis
    if not static_analysis:
        return _error_response("No static analysis available")

    # Determine target function
    if not function_name:
        function_name = list(static_analysis.keys())[0] if static_analysis else None

    if not function_name or function_name not in static_analysis:
        return _error_response("Function not found")

    # Extract function code
    function_code = _extract_function_code(session.code, function_name)
    if not function_code:
        return _error_response("Could not extract function code")

    # code_hash = hashlib.sha256(function_code.encode()).hexdigest()

    # Check line limit
    code_lines = function_code.split('\n')
    if len(code_lines) > MAX_CODE_LINES:
        return _error_response(
            f"Function is too long to refactor automatically ({len(code_lines)} lines). "
            f"Use AI Suggestions instead to identify what to improve manually."
        )
    
    normalized_code = normalize_code(function_code)
    # Cache key
    cache_input = {
        "feature": "refactor_code",
        "function": function_name,
        # "code_hash": hashlib.sha256(function_code.encode()).hexdigest()
        "code": normalized_code
    }
    input_hash = create_input_hash(cache_input)

    # Check cache
    cached = db.query(AIResponse).filter(
        AIResponse.feature_type == "refactor_code",
        AIResponse.input_hash == input_hash
    ).first()

    if cached:
        data = cached.response_data
        return {
            "original_code": function_code,
            "refactored_code": data.get("refactored_code", ""),
            "changes": data.get("changes", ""),
            "tokens_used": cached.tokens_used or 0,
            "cached": True,
            "error": None
        }

    try:
        check_ai_quota(user, "refactor_code", db)
    except HTTPException as e:
        return {
            "original_code": function_code,
            "refactored_code": "",
            "changes": "",
            "tokens_used": 0,
            "cached": False,
            "error": e.detail if hasattr(e, "detail") else str(e)
        }

    # Get cached AI suggestions silently if available
    # ai_suggestions = None
    ai_suggestions: Optional[list] = None
    try:
        cache_input = {
        "feature": "refactor_suggest",
        "function": function_name,
        # "code_hash": hashlib.sha256(function_code.encode()).hexdigest()
        "code": normalized_code
        }
        input_hash = create_input_hash(cache_input)

        cached_suggestion = db.query(AIResponse).filter(
            AIResponse.feature_type == "refactor_suggest",
            AIResponse.input_hash == input_hash
        ).first()

        if cached_suggestion:
            # ai_suggestions = cached_suggestion.response_data.get("suggestions")
            ai_suggestions = cached_suggestion.response_data.get("parsed_suggestions")
    except Exception:
        pass

    # If no cached suggestions, generate silently
    if ai_suggestions is None:
        ai_suggestions = _generate_suggestions_silently(
            session_id, function_name, static_analysis, function_code, normalized_code, session, db
        )

    if ai_suggestions is None:
        ai_suggestions = []

    # Prepare context
    context = prepare_refactor_input(
        function_name=function_name,
        static_analysis=static_analysis[function_name],
        code=function_code,
        ai_suggestions=ai_suggestions
    )

    # Generate
    prompt = build_prompt(**context)

    print("DEBUG code refactor prompt:", prompt)

    result = generate_completion(
        prompt=prompt,
        max_tokens=680,
        temperature=0.2,
        thinking_budget=100
    )

    if result["error"]:
        return {
        "original_code": function_code,
        "refactored_code": function_code,
        "changes": "Refactoring temporarily unavailable. Please try again.",
        "tokens_used": 0,
        "cached": False,
        "error": result["error"]
    }

    # Parse response
    parsed = parse_refactor_response(result["text"])

    if not parsed["refactored_code"]:
        return _error_response("Failed to extract refactored code from response")

    # Syntax validation
    try:
        ast.parse(parsed["refactored_code"])
    except SyntaxError as e:
        return {
            "original_code": function_code,
            "refactored_code": parsed["refactored_code"],
            "changes": parsed["changes"],
            "tokens_used": result["tokens_used"],
            "cached": False,
            "error": f"Generated code has syntax error: {str(e)}"
        }

    update_ai_quota(user, "refactor_code", db)

    # Store in cache
    try:
        ai_response = AIResponse(
            feature_type="refactor_code",
            input_hash=input_hash,
            response_data={
                "refactored_code": parsed["refactored_code"],
                "changes": parsed["changes"]
            },
            tokens_used=result["tokens_used"],
            model_used="gemini-2.5-flash"
        )
        db.add(ai_response)
        db.commit()
    except Exception as e:
        print(f"Cache storage error: {e}")

    return {
        "original_code": function_code,
        "refactored_code": parsed["refactored_code"],
        "changes": parsed["changes"],
        "tokens_used": result["tokens_used"],
        "cached": False,
        "error": None
    }


def _generate_suggestions_silently(
    session_id: str,
    function_name: str,
    static_analysis: Dict,
    function_code: str,
    normalized_code: str,
    session,
    db: Session
) -> Optional[List[Dict]]:
    """Generate AI suggestions silently for use in refactoring."""
    try:
        context = prepare_refactor_context(
            function_name,
            static_analysis[function_name],
            function_code
        )

        prompt = suggest_prompt(**context)
        result = generate_completion(
            prompt=prompt,
            max_tokens=520,
            temperature=0.3,
            thinking_budget=50 
        )

        if result["error"] or not result["text"]:
            return None

        try:
            parsed = parse_refactor_suggestions(result["text"])
            if not parsed:
                raise ValueError("Empty parsed suggestions")
        except Exception:
            parsed = []

        suggestions_text = result.get("text", "").strip()

        if not suggestions_text:
            suggestions_text = "No refactoring suggestions generated."

        # parsed = parse_refactor_suggestions(result["text"])

        # Cache it
        try:
            cache_input = {
                "feature": "refactor_suggest",
                "function": function_name,
                # "code_hash": hashlib.sha256(function_code.encode()).hexdigest()
                "code": normalized_code
            }
            input_hash = create_input_hash(cache_input)

            ai_response = AIResponse(
                feature_type="refactor_suggest",
                input_hash=input_hash,
                response_data={"parsed_suggestions": parsed, "suggestions": suggestions_text},
                tokens_used=result["tokens_used"],
                model_used="gemini-2.5-flash"
            )
            db.add(ai_response)
            db.commit()
        except Exception:
            pass

        # return result["text"]
        return parsed if parsed else None

    except Exception as e:
        print(f"Silent suggestion generation failed: {e}")
        return None


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


def _error_response(message: str) -> Dict:
    return {
        "original_code": "",
        "refactored_code": "",
        "changes": "",
        "tokens_used": 0,
        "cached": False,
        "error": message
    }