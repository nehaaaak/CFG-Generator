"""
Refactoring Service
Generates AI-powered refactoring suggestions and code transformations
"""

from typing import Dict, Optional
from sqlalchemy.orm import Session
from ..client_wrapper import generate_completion
from ..prompts.refactor_suggest import build_prompt, prepare_refactor_context
from ..utils import create_input_hash
from ...db_models import CFGSession, AIResponse
import ast
import hashlib
import re


def suggest_refactoring(
    session_id: str,
    function_name: Optional[str] = None,
    db: Session = None
) -> Dict:
    # Get session data
    session = db.query(CFGSession).filter(
        CFGSession.session_id == session_id
    ).first()
    
    if not session:
        return {
            "suggestions": "Session not found",
            "tokens_used": 0,
            "cached": False,
            "error": "Session not found"
        }
    
    # Get static analysis
    static_analysis = session.static_analysis
    if not static_analysis:
        return {
            "suggestions": "No static analysis available. Please regenerate CFG.",
            "tokens_used": 0,
            "cached": False,
            "error": "No static analysis"
        }
    
    # Determine target function
    if not function_name:
        # Use first function
        function_name = list(static_analysis.keys())[0] if static_analysis else None
    
    if not function_name or function_name not in static_analysis:
        return {
            "suggestions": "Function not found in analysis",
            "tokens_used": 0,
            "cached": False,
            "error": "Function not found"
        }
    
    # Extract function code from original source
    function_code = _extract_function_code(session.code, function_name)
    
    if not function_code:
        return {
            "suggestions": "Could not extract function code",
            "tokens_used": 0,
            "cached": False,
            "error": "Code extraction failed"
        }
    
    # Prepare context
    context = prepare_refactor_context(
        function_name,
        static_analysis[function_name],
        function_code
    )
    
    # Create cache key
    cache_input = {
        "session_id": session_id,
        "function": function_name,
        # "code_hash": hash(function_code)
        "code_hash": hashlib.sha256(function_code.encode()).hexdigest()
    }
    input_hash = create_input_hash(cache_input)
    
    # Check cache
    cached = db.query(AIResponse).filter(
        AIResponse.session_id == session_id,
        AIResponse.feature_type == "refactor_suggest",
        AIResponse.input_hash == input_hash
    ).first()
    
    if cached:
        return {
            "parsed_suggestions": cached.response_data.get("parsed_suggestions", []),
            "suggestions": cached.response_data.get("suggestions", ""),
            "tokens_used": cached.tokens_used or 0,
            "cached": True,
            "error": None
        }
    
    # Generate suggestions
    prompt = build_prompt(**context)
    
    result = generate_completion(
        prompt=prompt,
        max_tokens=470,  
        temperature=0.3,
        thinking_budget=60      
    )
    
    if result["error"]:
        return {
            "parsed_suggestions": [],
            "suggestions": result.get("text", ""),
            "tokens_used": result.get("tokens_used", 0),
            "cached": False,
            "error": result["error"]
        }
    try:
        parsed = parse_refactor_suggestions(result["text"])
        if not parsed:
            raise ValueError("Empty parsed suggestions")
    except Exception:
        parsed = []

    suggestions_text = result.get("text", "").strip()

    if not suggestions_text:
        suggestions_text = "No refactoring suggestions generated."

    # Store in cache
    try:
        ai_response = AIResponse(
            session_id=session_id,
            user_id=session.user_id,
            feature_type="refactor_suggest",
            input_hash=input_hash,
            # response_data={"suggestions": result["text"]},
            response_data={"parsed_suggestions": parsed, "suggestions": suggestions_text},
            tokens_used=result["tokens_used"],
            model_used="gemini-2.5-flash"
        )
        db.add(ai_response)
        db.commit()
    except Exception as e:
        print(f"Cache storage error: {e}")
    
    return {
        # "suggestions": result["text"],
        "parsed_suggestions": parsed,
        "suggestions": suggestions_text,
        "tokens_used": result["tokens_used"],
        "cached": False,
        "error": None
    }


def _extract_function_code(full_code: str, function_name: str) -> Optional[str]:
    """
    Extract specific function code from full source.
    
    Args:
        full_code: Complete source code
        function_name: Function to extract
    
    Returns:
        Function source code or None
    """
    try:
        tree = ast.parse(full_code)
        lines = full_code.splitlines()
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                # return ast.unparse(node)
                start = node.lineno - 1
                end = node.end_lineno
                return '\n'.join(lines[start:end])
        
        return None
    
    except Exception as e:
        print(f"Function extraction error: {e}")
        return None
    

def parse_refactor_suggestions(text: str):
    suggestions = []

    # Match numbered suggestions like:
    # 1. Extract Method
    #    explanation...
    pattern = r'\d+\.\s*(.+?)(?=\n\d+\.|\Z)'

    matches = re.findall(pattern, text, re.DOTALL)

    for i, match in enumerate(matches, start=1):
        lines = match.strip().split("\n")

        title = lines[0].strip()
        description = " ".join(line.strip() for line in lines[1:]).strip()

        suggestions.append({
            "id": i,
            "title": title,
            "description": description
        })

    return suggestions


    

# def parse_refactor_suggestions(text: str):
#     suggestions = []

#     # Split by PRIORITY blocks (robust split)
#     blocks = re.split(r'PRIORITY\s*\d+[^\n]*\n?', text, flags=re.IGNORECASE)

#     # First split part is empty → skip
#     for i, block in enumerate(blocks[1:], start=1):
#         suggestion = {
#             "priority": i,
#             "refactoring": "",
#             "problem": "",
#             "solution": "",
#             "benefit": "",
#             "lines": ""
#         }

#         fields = ["Refactoring", "Problem", "Solution", "Benefit", "Lines"]
#         for j, field in enumerate(fields):
#             # Match from this field to the next field or end of block
#             next_fields = '|'.join(fields[j+1:]) if j+1 < len(fields) else None
#             if next_fields:
#                 pattern = rf'•?\s*{field}:\s*(.*?)(?=•?\s*(?:{next_fields}):|\Z)'
#             else:
#                 pattern = rf'•?\s*{field}:\s*(.*?)(?=\Z)'
            
#             match = re.search(pattern, block, re.IGNORECASE | re.DOTALL)
#             if match:
#                 suggestion[field.lower()] = match.group(1).strip()

#         suggestions.append(suggestion)

#     return suggestions

    #     # Extract fields using regex (robust)
    #     refactoring = re.search(r'Refactoring:\s*(.+)', block, re.IGNORECASE)
    #     problem = re.search(r'Problem:\s*(.+)', block, re.IGNORECASE)
    #     solution = re.search(r'Solution:\s*(.+)', block, re.IGNORECASE)
    #     benefit = re.search(r'Benefit:\s*(.+)', block, re.IGNORECASE)
    #     lines = re.search(r'Lines:\s*(.+)', block, re.IGNORECASE)

    #     if refactoring:
    #         suggestion["refactoring"] = refactoring.group(1).strip()
    #     if problem:
    #         suggestion["problem"] = problem.group(1).strip()
    #     if solution:
    #         suggestion["solution"] = solution.group(1).strip()
    #     if benefit:
    #         suggestion["benefit"] = benefit.group(1).strip()
    #     if lines:
    #         suggestion["lines"] = lines.group(1).strip()

    #     suggestions.append(suggestion)

    # return suggestions