from typing import Dict, List, Optional
from ..client_wrapper import generate_completion
from ..prompts.overall_explain import build_prompt


def generate_overall_explanation(
    function_names: List[str],
    metrics: Dict,
    # smells: List[Dict],
    # hotspots: List[Dict],
    unreachable_code: List[Dict] = None
) -> Dict:
    """
    Generate overall CFG explanation.
    
    Returns:
        {
            "explanation": str,
            "tokens_used": int,
            "error": str | None
        }
    """
    
    # Build optimized prompt
    prompt = build_prompt(
        function_names,
        metrics,
        # smells,
        # hotspots,
        unreachable_code
    )
    
    # Generate completion (max 150 tokens for free tier)
    result = generate_completion(
        prompt=prompt,
        max_tokens=180,
        temperature=0.3
    )
    
    return {
        "explanation": result["text"],
        "tokens_used": result["tokens_used"],
        "error": result["error"]
    }


def generate_from_static_analysis(
    cfg_data: Dict,
    static_analysis: Dict,
    unreachable_code: List[Dict] = None
) -> Optional[str]:
    """
    Wrapper for main.py integration.
    Extracts data from static analysis and calls service.
    """
    try:
        if not static_analysis:
            return None
        
        # Extract from first function
        first_func = list(static_analysis.values())[0] if static_analysis else {}
        
        metrics = first_func.get("metrics", {})
        # smells = first_func.get("code_smells", [])
        # hotspots = first_func.get("hotspots", [])
        
        function_names = list(cfg_data.get("functions", {}).keys())
        
        result = generate_overall_explanation(
            function_names,
            metrics,
            # smells,
            # hotspots,
            unreachable_code
        )
        
        return result["explanation"] if not result["error"] else None
    
    except Exception as e:
        print("AI overall explanation failed:", str(e))
        return None
