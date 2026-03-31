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


def build_prompt(
    function_name: str,
    code_snippet: str,
    metrics: Dict,
    code_smells: List[Dict],
    hotspots: List[Dict],
    static_suggestions: List[Dict],
    cfg_structure: Dict
) -> str:
    """
    Build context-rich prompt for refactoring suggestions.
    
    Args:
        function_name: Function to refactor
        code_snippet: Actual code (truncated if too long)
        metrics: CFG metrics (CC, nesting, decisions, etc.)
        code_smells: Detected smells with severity
        hotspots: Complexity hotspots
        static_suggestions: Rule-based suggestions (baseline)
        cfg_structure: {
            "nodes": 12,
            "edges": 15,
            "decision_points": 5,
            "loops": 2,
            "max_nesting": 4,
            "paths": 8
        }
    
    DESIGN PRINCIPLES:
    1. Send structured data + small code snippet (not full file)
    2. Leverage static analysis (already computed)
    3. Focus on CFG-level issues (complexity, flow)
    4. Provide actionable steps, not generic advice
    """
    
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
    max_lines = 50
    code_lines = code_snippet.split('\n')
    if len(code_lines) > max_lines:
        code_snippet = '\n'.join(code_lines[:max_lines]) + f"\n... ({len(code_lines) - max_lines} more lines)"
    
    # Build prompt
    prompt = f"""ROLE: You are an expert Python refactoring advisor specializing in control flow optimization.

TASK: Analyze this function and provide prioritized refactoring suggestions.

FUNCTION: {function_name}

CODE:
```python
{code_snippet}
```

CFG ANALYSIS:

Metrics:
  • Cyclomatic Complexity: {cc} ({category})
  • Decision Points: {decisions}
  • Loops: {loops}
  • Max Nesting Depth: {nesting}
  • Execution Paths: {cfg_structure.get('paths', 'N/A')}

Structure:
  • Blocks: {cfg_structure.get('nodes', 'N/A')}
  • Edges: {cfg_structure.get('edges', 'N/A')}

"""
    
    # prompt += "Key Variables:\n"
    # for var in key_variables:
    #     prompt += f"  • {var}\n"
    # prompt += "\n"
    
    # Add code smells (prioritize critical/high)
    if critical or high or medium:
        # prompt += "─────────────────────────────────────────────────────────\n"
        prompt += "DETECTED ISSUES:\n"
        # prompt += "─────────────────────────────────────────────────────────\n"
        
        if critical:
            prompt += f"CRITICAL ({len(critical)}):\n"
            for smell in critical[:3]:  # Top 3
                prompt += f"  • {smell.get('type', 'unknown')}: {smell.get('message', '')}\n"
        
        if high:
            prompt += f"\nHIGH ({len(high)}):\n"
            for smell in high[:3]:
                prompt += f"  • {smell.get('type', 'unknown')}: {smell.get('message', '')}\n"
        
        if medium and len(critical) + len(high) < 5:  # Only if space
            prompt += f"\nMEDIUM ({len(medium)}):\n"
            for smell in medium[:2]:
                prompt += f"  • {smell.get('type', 'unknown')}: {smell.get('message', '')}\n"
        
        prompt += "\n"
    
    # Add hotspots
    if hotspots:
        # prompt += "─────────────────────────────────────────────────────────\n"
        prompt += f"COMPLEXITY HOTSPOTS ({len(hotspots)}):\n"
        # prompt += "─────────────────────────────────────────────────────────\n"
        for hotspot in hotspots[:3]:
            prompt += f"  • {hotspot.get('type', 'unknown')}: {hotspot.get('message', '')}\n"
        prompt += "\n"
    
    # Add static suggestions as baseline
    if static_suggestions:
        # prompt += "─────────────────────────────────────────────────────────\n"
        prompt += "BASELINE SUGGESTIONS (Rule-Based):\n"
        # prompt += "─────────────────────────────────────────────────────────\n"
        for i, sugg in enumerate(static_suggestions[:3], 1):
            refactor = sugg.get("refactoring", "Unknown")
            reason = sugg.get("reason", "")
            prompt += f"  {i}. {refactor}\n"
            if reason:
                prompt += f"     Reason: {reason}\n"
        prompt += "\n"
    
    # Output instructions
    prompt += """
OUTPUT INSTRUCTIONS:

Provide 3-5 refactoring suggestions in this EXACT format:

PRIORITY 1 (Most Critical):
• Refactoring: [Name of refactoring pattern]
• Problem: [Specific issue in this code]
• Solution: [What to do - 2-3 actionable steps]
• Benefit: [Expected improvement - be specific]
• Lines: [Approximate line numbers if applicable]

PRIORITY 2 (High Impact):
• Refactoring: [Name]
• Problem: [Issue]
• Solution: [Steps]
• Benefit: [Improvement]
• Lines: [Line numbers]

PRIORITY 3 (Medium Impact):
... (repeat format)

GUIDELINES:
✓ Be specific to THIS code — reference actual variable names, conditions, and line numbers
✓ Prefer structural refactoring first (extract method, reduce nesting), then suggest safe Pythonic improvements (e.g., simplify conditionals, use comprehensions where appropriate)
✓ Provide actionable steps, not vague advice
✓ Estimate impact where possible (e.g., "reduces CC from 12 to 7")
✓ Prioritize CFG-level improvements (complexity, flow, structure)
✓ Consider maintainability, readability, and testability
✓ If baseline suggestions are good, enhance them with specific steps — otherwise suggest better approaches

AVOID:
✗ Generic advice ("make it cleaner")
✗ Style-only changes (unless critical)
✗ Micro-optimizations
✗ Suggestions that don't address detected issues

Start with "PRIORITY 1" directly. No intro or label needed."""
    
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