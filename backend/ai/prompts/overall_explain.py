"""
Prompt builder for Overall CFG Explanation (Public Feature)

Structure:
- ROLE: You are a CFG structure analyzer
- TASK: Explain the control flow graph structure
- INPUT: Structured CFG metrics (not full code)
- OUTPUT: 2-3 sentence CFG explanation
- CONSTRAINTS: Focus on flow, structure, complexity
"""

from typing import Dict, List


def build_prompt(
    function_names: List[str],
    metrics: Dict,
    unreachable_code: List[Dict] = None,
    path_count: int = 0
) -> str:
    """
    Build optimized prompt for CFG structure explanation.
    
    DESIGN PRINCIPLES:
    1. Focus on CONTROL FLOW, not code quality
    2. Explain graph structure (nodes, edges, paths)
    3. Describe execution flow patterns
    4. Mention complexity only as context
    """
    
    # Extract CFG structure metrics
    cc = metrics.get('cyclomatic_complexity', 0)
    nodes = metrics.get('nodes', 0)
    edges = metrics.get('edges', 0)
    # path_count = metrics.get('path_count', 0)
    decisions = metrics.get('decision_points', 0)
    loops = metrics.get('loops', 0)
    nesting = metrics.get('max_nesting_depth', 0)
    category = metrics.get('complexity_category', 'Unknown')
    
    # Function list
    funcs = ", ".join(function_names) if function_names else "main code"
    
    # Build structured prompt
    prompt = f"""Explain the control flow structure of this Python code's CFG.

CFG STRUCTURE:
- Function(s): {funcs}
- Total Blocks: {nodes}
- Control Edges: {edges}
- Execution Paths: {path_count}
- Decision Points: {decisions}
- Loops: {loops}
- Max Nesting Depth: {nesting}
- Cyclomatic Complexity: {cc} ({category})
"""
    
    if unreachable_code:
        prompt += f"- Unreachable Blocks: {len(unreachable_code)}\n"
    
    prompt += """
IMPORTANT:
- Write 2–3 concise sentences (max ~80–100 words)
- Use a single paragraph (no bullets or numbering)
- Keep the explanation short, clear, and complete.

Describe how execution flows through the CFG clearly and concisely.
Start naturally ("This CFG...", "The control flow...")."""
    
    return prompt





# ROLE: You are a Control Flow Graph (CFG) structure analyst.
# TASK: Explain the control flow structure of this Python code's CFG.

# - Be clear and complete

# No labels or prefixes.
# Ensure the explanation is complete and does not end abruptly.

# FOCUS ON:
# - How execution moves through the graph
# - Where branches or loops influence the flow
# - Key characteristics of the CFG structure

# Write the explanation now: