from typing import Dict, List, Optional
from ..client_wrapper import generate_completion
from ..prompts.overall_explain import build_prompt


def generate_overall_explanation(
    function_names: List[str],
    metrics: Dict,
    unreachable_code: List[Dict] = None,
    path_count: int = 0
) -> Dict:
    
    # Build optimized prompt
    prompt = build_prompt(
        function_names,
        metrics,
        unreachable_code,
        path_count=path_count
    )
    
    print("DEBUG prompt:", prompt)

    result = generate_completion(
        prompt=prompt,
        max_tokens=370,
        temperature=0.4,
        thinking_budget=50
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
    try:
        print("Entered overall explanation")
        if not static_analysis:
            return None
        
        # first_func_data = cfg_data.get("functions", [{}])[0] if isinstance(cfg_data.get("functions"), list) else {}
        # metrics = first_func_data.get("metrics", {})
        # path_count = len(first_func_data.get("paths", []))


        # function_names = list(cfg_data.get("functions", {}).keys())
        functions = cfg_data.get("functions", [])
        print("FUNCTIONS")
        if not functions:
            print("DEBUG: No functions found")
            return None
        
        function_names = [functions[0]["name"]] if isinstance(functions, list) else [list(functions.keys())[0]]
        # if isinstance(functions, list):
        #     function_names = [f["name"] for f in functions if "name" in f]
        # else:
        #     function_names = list(functions.keys())

        print("func name:", function_names)
        functions_data = cfg_data.get("functions", {})
        if isinstance(functions_data, dict):
            first_func_data = list(functions_data.values())[0] if functions_data else {}
        else:
            first_func_data = functions_data[0] if functions_data else {}

        metrics = first_func_data.get("metrics", {})
        path_count = len(first_func_data.get("paths", []))
        print("metrics:", metrics)
                
        result = generate_overall_explanation(
            function_names,
            metrics,
            # smells,
            # hotspots,
            unreachable_code,
            path_count=path_count
        )

        print("DEBUG cfg_data keys:", cfg_data.keys())
        print("DEBUG functions:", cfg_data.get("functions", []))
        print("RESULT:", result)
        
        return result["explanation"] if not result["error"] else None
    
    except Exception as e:
        print("AI overall explanation failed:", str(e))
        return None










# def generate_from_static_analysis(
#     cfg_data: Dict,
#     static_analysis: Dict,
#     unreachable_code: List[Dict] = None
# ) -> Optional[str]:
#     try:
#         if not cfg_data:
#             return None
        
#         if not static_analysis:
#             return None

#         functions = cfg_data.get("functions", {})

#         if isinstance(functions, dict):
#             functions_iter = list(functions.items())
#         else:
#             functions_iter = [(f["name"], f) for f in functions if "name" in f]

#         if not functions_iter:
#             return None

#         # Sort by complexity, take most complex
#         functions_iter.sort(
#             key=lambda x: x[1].get("metrics", {}).get("cyclomatic_complexity", 0),
#             reverse=True
#         )

#         # Limit to 1 for free tier — explain most complex function
#         func_name, func_data = functions_iter[0]

#         metrics = func_data.get("metrics", {})
#         path_count = len(func_data.get("paths", []))

#         result = generate_overall_explanation(
#             function_names=[func_name],
#             metrics=metrics,
#             unreachable_code=func_data.get("unreachable_code", []),
#             path_count=path_count
#         )

#         return result["explanation"] if not result["error"] else None

#     except Exception as e:
#         print("AI overall explanation failed:", str(e))
#         return None
    
