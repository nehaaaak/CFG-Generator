"""
Prompt builder for Refactoring Suggestions (Protected Feature)

Provides context-aware refactoring suggestions by analyzing:
1. Static analysis results (smells, hotspots, metrics)
2. CFG structure (complexity, nesting, branching)
3. Code snippets (actual problem areas)
4. Existing static suggestions (as baseline)

Returns prioritized, actionable suggestions with reasoning.
Optimized for free tier - sends structured data, not full code.
"""

from typing import Dict, List, Optional
import re


def extract_relevant_lines(code: str, code_smells: List[Dict], hotspots: List[Dict], max_lines: int = 25) -> str:
    """
    Extract lines most relevant to detected issues.
    Falls back to first max_lines if no line info available.
    """
    lines = code.split('\n')
    
    if len(lines) <= max_lines:
        return code
    
    # Collect issue line numbers
    issue_lines = set()
    for issue in code_smells + hotspots:
        line = issue.get("line")
        if line:
            # Add line and context (2 lines before and after)
            for l in range(max(0, line - 3), min(len(lines), line + 3)):
                issue_lines.add(l)
    
    # Always include function signature (first 2 lines)
    for l in range(min(2, len(lines))):
        issue_lines.add(l)

    if not issue_lines or len(issue_lines) < 5:
        # No line info in issues — fall back to first max_lines
        truncated = '\n'.join(lines[:max_lines])
        return truncated + f"\n# ... ({len(lines) - max_lines} more lines not shown)"

    # Build relevant snippet
    sorted_lines = sorted(issue_lines)
    result = []
    prev = -1
    for ln in sorted_lines:
        if prev != -1 and ln > prev + 1:
            result.append("# ...")
        result.append(lines[ln])
        prev = ln

    # If still under max_lines budget, fill with beginning of function
    if len(result) < max_lines:
        remaining = max_lines - len(result)
        for l in range(min(remaining, len(lines))):
            if l not in issue_lines:
                result.insert(l, lines[l])

    total = len('\n'.join(result).split('\n'))
    if len(lines) > max_lines:
        result.append(f"# ... ({len(lines) - total} more lines not shown)")

    return '\n'.join(result)


def build_prompt(
    function_name: str,
    code_snippet: str,
    metrics: Dict,
    code_smells: List[Dict],
    hotspots: List[Dict],
    static_suggestions: List[Dict],
    cfg_structure: Dict
) -> str:    
    # Extract key metrics
    cc = metrics.get("cyclomatic_complexity", 0)
    category = metrics.get("complexity_category", "Unknown")
    nesting = metrics.get("max_nesting_depth", 0)
    decisions = metrics.get("decision_points", 0)
    loops = metrics.get("loops", 0)
    
    # Categorize smells by severity
    critical = [s for s in code_smells if s.get("severity") == "critical"]
    high = [s for s in code_smells if s.get("severity") == "high"]
    medium = [s for s in code_smells if s.get("severity") == "medium"]
    
    # variables = list(set(re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', code_snippet)))
    # key_variables = variables[:5]

    # Truncate code if too long (save tokens)
    # max_lines = 50
    # code_lines = code_snippet.split('\n')
    # if len(code_lines) > max_lines:
    #     code_snippet = '\n'.join(code_lines[:max_lines]) + f"\n... ({len(code_lines) - max_lines} more lines)"

    code_snippet = extract_relevant_lines(code_snippet, code_smells, hotspots, max_lines=25)
    
    # Build prompt
    prompt = f"""You are an expert Python refactoring assistant focused on improving control flow, readability,
and maintainability.

FUNCTION: {function_name}

CODE:
```python
{code_snippet}
```

CFG ANALYSIS:
  • Cyclomatic Complexity: {cc} ({category})
  • Decision Points: {decisions}
  • Loops: {loops}
  • Max Nesting Depth: {nesting}
  • Execution Paths: {cfg_structure.get('paths', 'N/A')}
"""
    
    # prompt += "Key Variables:\n"
    # for var in key_variables:
    #     prompt += f"  • {var}\n"
    # prompt += "\n"
    
    # Add code smells (prioritize critical/high)
    if critical or high or medium:
        # prompt += "DETECTED ISSUES:\n"
        # if critical:
        #     prompt += f"CRITICAL ({len(critical)}):\n"
        #     for smell in critical[:3]:  # Top 3
        #         prompt += f"  • {smell.get('type', 'unknown')}: {smell.get('message', '')}\n"
        
        # if high:
        #     prompt += f"\nHIGH ({len(high)}):\n"
        #     for smell in high[:3]:
        #         prompt += f"  • {smell.get('type', 'unknown')}: {smell.get('message', '')}\n"
        
        # if medium and len(critical) + len(high) < 5:  # Only if space
        #     prompt += f"\nMEDIUM ({len(medium)}):\n"
        #     for smell in medium[:2]:
        #         prompt += f"  • {smell.get('type', 'unknown')}: {smell.get('message', '')}\n"
        
        # prompt += "\n"

        prompt += "\nISSUES:\n"
        for s in (critical[:2] + high[:2] + medium[:1]):
            prompt += f"- {s.get('type')}: {s.get('message')}\n"
    
    # Add hotspots
    # if hotspots:
    #     prompt += f"COMPLEXITY HOTSPOTS ({len(hotspots)}):\n"
    #     for hotspot in hotspots[:3]:
    #         prompt += f"  • {hotspot.get('type', 'unknown')}: {hotspot.get('message', '')}\n"
    #     prompt += "\n"

    if hotspots:
        prompt += "\nHOTSPOTS:\n"
        for h in hotspots[:2]:
            prompt += f"- {h.get('type')}: {h.get('message')}\n"
    
    # Add static suggestions as baseline
    # if static_suggestions:
    #     prompt += "BASELINE SUGGESTIONS (Rule-Based):\n"
    #     for i, sugg in enumerate(static_suggestions[:3], 1):
    #         refactor = sugg.get("refactoring", "Unknown")
    #         reason = sugg.get("reason", "")
    #         prompt += f"  {i}. {refactor}\n"
    #         if reason:
    #             prompt += f"     Reason: {reason}\n"
    #     prompt += "\n"

    if static_suggestions:
        prompt += "\nBASELINE SUGGESTIONS:\n"
        for s in static_suggestions[:2]:
            prompt += f"- {s.get('refactoring')}: {s.get('reason')}\n"
    
    # Output instructions
    prompt += """
Rules:
- Be specific to this code
- Focus on structural improvements (extract method, reduce nesting, simplify flow)
- Estimate impact where possible (e.g., "reduces CC from 12 to 7")
- Do not suggest changes that alter program logic or behavior
- Avoid generic or stylistic advice
- Keep each suggestion short and actionable. Limit each suggestion to 60–80 words
    
OUTPUT INSTRUCTIONS:
Provide 3-4 prioritized refactoring suggestions.

FORMAT:
1. [Refactoring Name]  
   [1–2 line explanation of what to do and why]

2. ... (repeat format)

Start directly with suggestion 1. No intro or label needed."""
    
    return prompt


def prepare_refactor_context(
    function_name: str,
    static_analysis: Dict,
    code: str
) -> Dict:
    """
    Prepare all context data for refactoring suggestions.
    
    Args:
        function_name: Function to analyze
        static_analysis: Full static analysis results for function
        code: Source code of the function
    
    Returns:
        Dict with all data needed for build_prompt()
    """
    metrics = static_analysis.get("metrics", {})
    code_smells = static_analysis.get("code_smells", [])
    hotspots = static_analysis.get("hotspots", [])
    static_suggestions = static_analysis.get("refactoring_suggestions", [])
    
    # Build CFG structure summary
    cfg_structure = {
        "nodes": metrics.get("nodes", 0),
        "edges": metrics.get("edges", 0),
        "decision_points": metrics.get("decision_points", 0),
        "loops": metrics.get("loops", 0),
        "max_nesting": metrics.get("max_nesting_depth", 0),
        "paths": len(static_analysis.get("paths", []))
    }
    
    return {
        "function_name": function_name,
        "code_snippet": code,
        "metrics": metrics,
        "code_smells": code_smells,
        "hotspots": hotspots,
        "static_suggestions": static_suggestions,
        "cfg_structure": cfg_structure
    }





# """ROLE: You are an expert Python refactoring advisor specializing in control flow optimization.

# TASK: Analyze this function and provide prioritized refactoring suggestions.

# FUNCTION: {function_name}

# CODE:
# ```python
# {code_snippet}
# ```

# CFG ANALYSIS:

# Metrics:
#   • Cyclomatic Complexity: {cc} ({category})
#   • Decision Points: {decisions}
#   • Loops: {loops}
#   • Max Nesting Depth: {nesting}
#   • Execution Paths: {cfg_structure.get('paths', 'N/A')}

# Structure:
#   • Blocks: {cfg_structure.get('nodes', 'N/A')}
#   • Edges: {cfg_structure.get('edges', 'N/A')}"""


# OUTPUT INSTRUCTIONS:
# Provide 3-4 refactoring suggestions in this EXACT format:

# PRIORITY 1 (Most Critical):
# • Refactoring: [Name of refactoring pattern]
# • Problem: [Specific issue in this code]
# • Solution: [What to do - 2-3 actionable steps]
# • Benefit: [Expected improvement - be specific]
# • Lines: [Approximate line numbers if applicable]

# PRIORITY 2 (High Impact):
# • Refactoring: [Name]
# • Problem: [Issue]
# • Solution: [Steps]
# • Benefit: [Improvement]
# • Lines: [Line numbers]

# PRIORITY 3 (Medium Impact):
# ... (repeat format)

# GUIDELINES:
# ✓ Be specific to THIS code — reference actual variable names, conditions, and line numbers
# ✓ Prefer structural refactoring first (extract method, reduce nesting), then suggest safe Pythonic improvements (e.g., simplify conditionals, use comprehensions where appropriate)
# ✓ Provide actionable steps, not vague advice
# ✓ Estimate impact where possible (e.g., "reduces CC from 12 to 7")
# ✓ Prioritize CFG-level improvements (complexity, flow, structure)
# ✓ Consider maintainability, readability, and testability
# ✓ If baseline suggestions are good, enhance them with specific steps — otherwise suggest better approaches

# AVOID:
# ✗ Generic advice ("make it cleaner")
# ✗ Style-only changes (unless critical)
# ✗ Micro-optimizations
# ✗ Suggestions that don't address detected issues

# Start with "PRIORITY 1" directly. No intro or label needed.