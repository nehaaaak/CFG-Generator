from typing import Dict, List, Optional
from ..client_wrapper import generate_completion
from ..prompts.overall_explain import build_prompt


def generate_overall_explanation(
    function_names: List[str],
    metrics: Dict,
    # smells: List[Dict],
    # hotspots: List[Dict],
    unreachable_code: List[Dict] = None,
    path_count: int = 0
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
        unreachable_code,
        path_count
    )
    
    # Generate completion (max 180 tokens for free tier)
    result = generate_completion(
        prompt=prompt,
        max_tokens=350,
        temperature=0.4
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
        
        first_func_data = cfg_data.get("functions", [{}])[0] if isinstance(cfg_data.get("functions"), list) else {}
        path_count = len(first_func_data.get("paths", []))

        # function_names = list(cfg_data.get("functions", {}).keys())
        functions = cfg_data.get("functions", [])
        if isinstance(functions, list):
            function_names = [f["name"] for f in functions if "name" in f]
        else:
            function_names = list(functions.keys())
        
        result = generate_overall_explanation(
            function_names,
            metrics,
            # smells,
            # hotspots,
            unreachable_code,
            path_count
        )
        
        return result["explanation"] if not result["error"] else None
    
    except Exception as e:
        print("AI overall explanation failed:", str(e))
        return None
