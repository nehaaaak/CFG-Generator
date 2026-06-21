"""
Prompt builder for Actual Code Refactoring (Protected Feature)

Generates production-quality refactored code by:
1. Analyzing target issues (from suggestions or metrics)
2. Applying safe, proven refactoring patterns
3. Preserving behavior (no logic changes)
4. Explaining changes made

Focus: Structural improvements that reduce complexity
Safe patterns: Extract method, guard clauses, early returns, comprehensions

Token optimization: Send only essential context + code
"""

from typing import Dict, List, Optional
import re


def build_prompt(
    function_name: str,
    original_code: str,
    # target_goal: str,
    metrics: Dict,
    issues: List[Dict],
    suggestions: Optional[List[Dict]] = None
) -> str:
    """
    Build prompt for code refactoring.
    
    Args:
        function_name: Function to refactor
        original_code: Current code
        target_goal: What to improve (e.g., "reduce_cc", "reduce_nesting", "simplify_logic")
        metrics: Current metrics (CC, nesting, etc.)
        issues: Specific issues to fix
        suggestions: AI suggestions from previous step (optional)
    
    DESIGN:
    - Send minimal context (code + metrics only)
    - Clear refactoring goal
    - Request structured output (code + changes)
    - Emphasize behavior preservation
    """
    # Extract key metrics
    cc = metrics.get("cyclomatic_complexity", 0)
    nesting = metrics.get("max_nesting_depth", 0)
    decisions = metrics.get("decision_points", 0)   

    # Format issues concisely
    issue_summary = ""
    if issues:
        critical = [i for i in issues if i.get("severity") in ["critical", "high"]]
        if critical:
            issue_summary = "Key Issues:\n"
            for issue in critical[:2]:
                issue_summary += f"  • {issue.get('type', 'unknown')}: {issue.get('message', '')}\n"
    
    # Build prompt
    prompt = f"""ROLE: You are an expert Python refactoring engineer.

TASK: Refactor the function `{function_name}` to improve its structure while preserving exact behavior.

ORIGINAL CODE:
```python
{original_code}
```

METRICS:
Cyclomatic Complexity: {cc}, Max Nesting Depth: {nesting}, Decision Points: {decisions}

{issue_summary}
"""

    if suggestions:
        prompt += "\nRefactoring Hints:\n"
        compressed_suggestions = compress_suggestions(suggestions)
        prompt += f"{compressed_suggestions}\n"

    # Refactoring instructions
    prompt += f"""
REFACTORING REQUIREMENTS:
Apply these improvements wherever applicable:

- Reduce nesting using guard clauses / early returns   
- Simplify conditionals and control flow 
- Remove unused or duplicate code  
- Use Pythonic constructs where safe (comprehensions, enumerate, etc.)  
- Extract helpers only if there are clearly independent logical sections and CFG remains meaningful

CONSTRAINTS:
✓ PRESERVE exact behavior — same inputs must produce same outputs
✓ Keep function signature identical  
✓ Do not add/remove logic branches
✓ Avoid changes that trivialize the main function’s CFG

OUTPUT FORMAT: Provide your response in this EXACT structure:

REFACTORED CODE:
```python
[paste complete refactored function here]
```

CHANGES MADE:
[describe changes and improvement made by them in 2-3 concise lines]

Begin refactoring:"""
    
    return prompt


def parse_refactor_response(response_text: str) -> Dict:
    """
    Parse AI response to extract code and metadata.
    
    Returns:
        {
            "refactored_code": str,
            "changes": List[str],
            "metrics_impact": str,
            "behavior_guarantee": str
        }
    """
    result = {
        "refactored_code": "",
        "changes": ""
    }
    
    # Extract code block    
    code_match = re.search(r'```python\n(.*?)```', response_text, re.DOTALL)
    if code_match:
        result["refactored_code"] = code_match.group(1).strip()
    
    # Extract changes
    changes_match = re.search(r'CHANGES MADE:\s*(.*?)(?=\Z)', response_text, re.DOTALL)
    if changes_match:
        result["changes"] = changes_match.group(1).strip()
    
    return result


def prepare_refactor_input(
    function_name: str,
    static_analysis: Dict,
    code: str,
    # target_goal: str,
    ai_suggestions: Optional[List[Dict]] = None
) -> Dict:
    """
    Prepare input data for refactoring prompt.
    
    Args:
        function_name: Function to refactor
        static_analysis: Static analysis results
        code: Function source code
        target_goal: Refactoring goal
        ai_suggestions: Previous AI suggestions (optional)
    
    Returns:
        Dict ready for build_prompt()
    """
    metrics = static_analysis.get("metrics", {})
    
    # Collect issues (smells + hotspots)
    issues = []
    issues.extend(static_analysis.get("code_smells", []))
    issues.extend(static_analysis.get("hotspots", []))
    
    # Sort by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    issues.sort(key=lambda x: severity_order.get(x.get("severity", "low"), 99))
    
    return {
        "function_name": function_name,
        "original_code": code,
        # "target_goal": target_goal,
        "metrics": metrics,
        "issues": issues,
        "suggestions": ai_suggestions
    }


def compress_suggestions(parsed_suggestions):
    compressed = []

    for s in parsed_suggestions:
        title = s.get("title", "")
        compressed.append(f"- {title}")

    return "\n".join(compressed)    

