"""
Prompt builder for Node Explanation (Protected Feature)

Provides 3 layers of context:
1. Local node info (code, type, position)
2. Graph context (predecessors, successors, edges)
3. Execution context (paths, loops, decisions)

This makes explanations CFG-aware, not just code-aware.
"""

from typing import Dict, List, Optional


def build_prompt(
    node_data: Dict,
    predecessors: List[Dict],
    successors: List[Dict],
    paths_through_node: List[List[str]],
    loop_context: Optional[Dict] = None,
    function_name: str = "main"
) -> str:
    """
    Build graph-aware prompt for node explanation.
    
    Args:
        node_data: {
            "block_id": "B3",
            "code_statements": ["if score >= 75:", "return 'B'"],
            "block_type": "decision" | "process" | "start" | "end",
            "line_numbers": [4, 5]
        }
        predecessors: [
            {"block_id": "B2", "edge_label": "False", "code": "score >= 90"}
        ]
        successors: [
            {"block_id": "B4", "edge_label": "True", "code": "return 'B'"},
            {"block_id": "B5", "edge_label": "False", "code": "return 'C'"}
        ]
        paths_through_node: [
            ["START", "B2", "B3", "B4", "END"],
            ["START", "B2", "B3", "B5", "END"]
        ]
        loop_context: {
            "is_in_loop": True,
            "loop_header": "B2",
            "loop_type": "for" | "while"
        }
    """
    
    # Extract node info
    block_id = node_data.get("block_id", "Unknown")
    code_lines = node_data.get("code_statements", [])
    block_type = node_data.get("block_type", "process")
    line_numbers = node_data.get("line_numbers", [])
    
    # Format code with line numbers
    code_display = "\n".join([
        f"  Line {ln}: {code}" 
        for ln, code in zip(line_numbers, code_lines)
    ]) if line_numbers else "\n".join([f"  {code}" for code in code_lines])
    
    # Build prompt
    prompt = f"""ROLE: You are a Control Flow Graph (CFG) analyst specializing in execution flow.

    TASK: Explain how block {block_id} behaves within the control flow graph and how execution flows through it.

    FUNCTION: {function_name}

    CURRENT BLOCK: {block_id} (Type: {block_type})

    Code:
    {code_display}

    """
    
    # Add predecessor context
    if predecessors:
        # prompt += "─────────────────────────────────────────────────────────\n"
        prompt += "INCOMING FLOW (How execution reaches this block):\n"
        # prompt += "─────────────────────────────────────────────────────────\n"
        for pred in predecessors:
            pred_id = pred.get("block_id", "?")
            edge_label = pred.get("edge_label", "")
            pred_code = pred.get("code", "")
            
            edge_info = f" [{edge_label}]" if edge_label else ""
            code_info = f": {pred_code}" if pred_code else ""
            
            prompt += f"  From {pred_id}{edge_info}{code_info}\n"
        prompt += "\n"
    
    # Add successor context
    if successors:
        # prompt += "─────────────────────────────────────────────────────────\n"
        prompt += "OUTGOING FLOW (Where execution goes next):\n"
        # prompt += "─────────────────────────────────────────────────────────\n"
        for succ in successors:
            succ_id = succ.get("block_id", "?")
            edge_label = succ.get("edge_label", "")
            succ_code = succ.get("code", "")
            
            edge_info = f" [{edge_label}]" if edge_label else ""
            code_info = f": {succ_code}" if succ_code else ""
            
            prompt += f"  To {succ_id}{edge_info}{code_info}\n"
        prompt += "\n"
    
    # Add loop context
    if loop_context and loop_context.get("is_in_loop"):
        # prompt += "─────────────────────────────────────────────────────────\n"
        prompt += "LOOP CONTEXT:\n"
        # prompt += "─────────────────────────────────────────────────────────\n"
        loop_header = loop_context.get("loop_header", "Unknown")
        loop_type = loop_context.get("loop_type", "loop")
        prompt += f"  This block is inside a {loop_type} loop (header: {loop_header})\n\n"
    
    # Add execution paths
    if paths_through_node:
        # prompt += "─────────────────────────────────────────────────────────\n"
        prompt += f"EXECUTION PATHS (Paths passing through {block_id}):\n"
        # prompt += "─────────────────────────────────────────────────────────\n"
        for i, path in enumerate(paths_through_node[:3], 1):  # Show max 3 paths
            path_str = " → ".join(path[:6])
            prompt += f"  Path {i}: {path_str}\n"
        if len(paths_through_node) > 3:
            prompt += f"  ... and {len(paths_through_node) - 3} more path(s)\n"
        prompt += "\n"
    
    # Output instructions
    prompt += """
    OUTPUT INSTRUCTIONS:

    Provide a clear 3-4 sentence explanation covering:

    1. PURPOSE: What this block does in the control flow
    - Include actual code in parentheses when referencing conditions/statements
    - Example: "checks if the score is at least 75 (score >= 75)"

    2. CONTEXT: How execution reaches this block
    - Mention predecessor conditions that led here
    - Example: "reached when the first condition was false"

    3. BEHAVIOR: What happens based on this block's execution
    - Explain outgoing paths and their conditions
    - Example: "if true, returns 'B' and exits; otherwise continues to check..."

    4. ROLE: This block's role in the overall flow
    - Is it a critical decision point, loop guard, return path, etc.

    STYLE:
    - Be specific and reference actual code statements in parentheses
    - Explain control flow behavior, not just what the code does
    - Use clear, educational language
    - Focus on graph structure and execution paths

    EXPLANATION:"""
    
    return prompt


def detect_loop_context(node, cfg_nodes, cfg_edges):
    """
    Detect loop context for a node:
    - loop_header
    - loop_body
    - loop_exit
    """

    node_id = node["id"]

    # Build adjacency map
    successors = {}
    for edge in cfg_edges:
        src = edge["from_node"]
        dst = edge["to_node"]
        successors.setdefault(src, []).append(dst)

    # Detect back edges using DFS
    visited = set()
    stack = set()
    back_edges = []

    def dfs(n):
        visited.add(n)
        stack.add(n)

        for succ in successors.get(n, []):
            if succ not in visited:
                dfs(succ)
            elif succ in stack:
                back_edges.append((n, succ))

        stack.remove(n)

    if successors:
        dfs(list(successors.keys())[0])

    # Identify loop structures
    for src, dst in back_edges:

        # dst = loop header
        header_node = next((n for n in cfg_nodes if n["id"] == dst), None)

        if node_id == dst:
            return {
                "is_in_loop": True,
                "loop_header": f"B{header_node.get('block_number')}",
                "loop_role": "loop_header",
                "loop_type": "loop"
            }

        if node_id == src:
            return {
                "is_in_loop": True,
                "loop_header": f"B{header_node.get('block_number')}",
                "loop_role": "loop_back_edge",
                "loop_type": "loop"
            }

    # Detect loop body nodes
    for src, dst in back_edges:
        if node_id != dst:
            return {
                "is_in_loop": True,
                "loop_header": f"B{dst}",
                "loop_role": "loop_body",
                "loop_type": "loop"
            }

    return None


def format_node_context_for_prompt(
    node: Dict,
    cfg_nodes: List[Dict],
    cfg_edges: List[Dict],
    all_paths: List[List[str]]
) -> Dict:
    """
    Helper to extract and format node context from CFG data.
    Returns formatted data ready for build_prompt().
    """
    # block_id = node.get("block_number") or node.get("id")
    block_number = node.get("block_number")
    block_id = f"B{block_number}" if block_number else node.get("id")
    
    # Find predecessors
    predecessors = []
    for edge in cfg_edges:
        if edge["to_node"] == node["id"]:
            pred_node = next((n for n in cfg_nodes if n["id"] == edge["from_node"]), None)
            if pred_node:
                predecessors.append({
                    # "block_id": f"B{pred_node.get('block_number', pred_node['id'])}",
                    "block_id": f"B{pred_node.get('block_number')}",
                    "edge_label": edge.get("label", ""),
                    "code": pred_node.get("label", "")
                })
    
    # Find successors
    successors = []
    for edge in cfg_edges:
        if edge["from_node"] == node["id"]:
            succ_node = next((n for n in cfg_nodes if n["id"] == edge["to_node"]), None)
            if succ_node:
                successors.append({
                    # "block_id": f"B{succ_node.get('block_number', succ_node['id'])}",
                    "block_id": f"B{succ_node.get('block_number')}",
                    "edge_label": edge.get("label", ""),
                    "code": succ_node.get("label", "")
                })
    
    # Find paths through this node
    paths_through = []
    block_tag = f"B{node.get('block_number')}"

    for path in all_paths:
        for step in path:
            if step.startswith(block_tag):
                paths_through.append(path)
                break
    
    # Check loop context (simplified - can be enhanced)
    # loop_context = None
    loop_context = detect_loop_context(node, cfg_nodes, cfg_edges)
    
    code_statements = node.get("code_statements") or [node.get("label", "")]
    line_no = node.get("line_number")
    line_numbers = [line_no] * len(code_statements) if line_no else []
    return {
        "node_data": {
            "block_id": f"B{block_id}",
            # "code_statements": node.get("code_statements", [node.get("label", "")]),
            "code_statements": code_statements,
            "block_type": node.get("type", "process"),
            # "line_numbers": [node.get("line_number")] if node.get("line_number") else []
            "line_numbers": line_numbers
        },
        "predecessors": predecessors,
        "successors": successors,
        "paths_through_node": paths_through,
        "loop_context": loop_context
    }   