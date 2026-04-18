"""
Prompt builder for Path Explanation (Protected Feature)

Explains an execution path through the CFG by:
1. Path sequence (ordered blocks)
2. Decision points and conditions taken
3. Execution scenario (what inputs trigger this path)
4. Outcome (what happens at the end)

Optimized for free tier - structured, concise, high-value context.
"""

from typing import Dict, List


def classify_path(path_blocks: List[Dict], edge_conditions: List[str]) -> str:
    """
    Classify execution path type.
    """

    # Detect early return
    for block in path_blocks:
        code = block.get("code", "").lower()
        if "return" in code:
            if block != path_blocks[-1]:
                return "Early Return"

    # Detect loops
    block_ids = [b["block_id"] for b in path_blocks]

    if len(block_ids) != len(set(block_ids)):
        return "Loop Iteration"

    # Detect loop exit
    for cond in edge_conditions:
        if cond.lower() in ["false", "done"]:
            return "Loop Exit"

    return "Normal Completion"


def calculate_path_metrics(path_blocks: List[Dict]) -> Dict:
    """
    Compute simple metrics for the execution path.
    """

    length = len(path_blocks)

    decisions = sum(
        1 for b in path_blocks
        if b.get("type") == "decision"
    )

    loops = sum(
        1 for b in path_blocks
        if b.get("type") == "loop_header"
    )

    return {
        "length": length,
        "decisions": decisions,
        "loops": loops
    }


def find_dominant_decision(path_blocks: List[Dict]) -> str:
    """
    Identify the most influential decision block in the path.
    """

    for block in path_blocks:
        if block.get("type") == "decision":
            return block.get("block_id")

    return ""


def build_prompt(
    path_blocks: List[Dict],
    edge_conditions: List[str],
    function_name: str = "main"
) -> str:
    """
    Build prompt for path explanation.
    
    Args:
        path_blocks: [
            {"block_id": "START", "code": "START", "type": "start"},
            {"block_id": "B2", "code": "score >= 90", "type": "decision"},
            {"block_id": "B3", "code": "return 'A'", "type": "process"},
            {"block_id": "END", "code": "END", "type": "end"}
        ]
        edge_conditions: [
            "",  # START -> B2 (no condition)
            "True",  # B2 -> B3 (condition was true)
            ""  # B3 -> END
        ]
        function_name: Function name
    
    DESIGN: Keep it compact - only essential context
    """
    MAX_BLOCKS = 8
    path_blocks = path_blocks[:MAX_BLOCKS]

    path_type = classify_path(path_blocks, edge_conditions)
    path_metrics = calculate_path_metrics(path_blocks)

    # dominant_block = find_dominant_decision(path_blocks)

    # Build path sequence
    path_sequence = " → ".join([b["block_id"] for b in path_blocks])
    
    # Extract decision points (blocks with conditions taken)
    # decision_points = []
    # for i, block in enumerate(path_blocks):
    #     if block["type"] == "decision" and i < len(edge_conditions):
    #         condition_taken = edge_conditions[i]
    #         # if condition_taken:
    #         if condition_taken and condition_taken.lower() not in ["next", ""]:
    #             decision_points.append({
    #                 "block": block["block_id"],
    #                 "code": block["code"],
    #                 "branch": condition_taken
    #             })

    decision_points = []
    for i in range(min(len(edge_conditions), len(path_blocks))):
        condition_taken = (edge_conditions[i] or "").strip()

        # Skip edges without real conditions
        if not condition_taken:
            continue

        # Ignore structural loop-flow labels
        if condition_taken.lower() in ["next", "done", "loop", "continue"]:
            continue

        block = path_blocks[i]

        decision_points.append({
            "block": block["block_id"],
            "code": block["code"],
            "branch": condition_taken
        })
    
    # Extract entry and exit
    entry = path_blocks[0] if path_blocks else None
    exit_block = path_blocks[-1] if path_blocks else None
    
    # Get return/output block (last non-END block)
    outcome_block = None
    for block in reversed(path_blocks):
        if block["type"] not in ["start", "end"]:
            outcome_block = block
            break
    
    # Build compact prompt
    prompt = f"""ROLE: You are a CFG path analyzer.

TASK: Explain this execution path through the {function_name} function.

EXECUTION PATH:
{path_sequence}

TYPE:
{path_type}
The TYPE above is already determined — do NOT override it.

PATH METRICS:
Length: {path_metrics['length']} blocks
Decision Points: {path_metrics['decisions']}
"""
    
    # if dominant_block:
    #     prompt += f"\nDOMINANT DECISION:\n{dominant_block}\n\n"

    # Add decision points (most important context)
    if decision_points:
        # prompt += "─────────────────────────────────────────────────────────\n"
        prompt += "DECISIONS(conditions):\n"
        # prompt += "─────────────────────────────────────────────────────────\n"
        for dp in decision_points:
            prompt += f"  {dp['block']}: ({dp['code']}) evaluated {dp['branch']}\n"
        prompt += "\n"
    
    # Add block details (compact)
    # prompt += "─────────────────────────────────────────────────────────\n"
    prompt += "PATH BLOCKS:\n"
    # prompt += "─────────────────────────────────────────────────────────\n"
    for block in path_blocks:
        if block["type"] not in ["start", "end"] and block["code"]:
            prompt += f"  {block['block_id']}: {block['code']}\n"
    prompt += "\n"
    
    # Add outcome
    if outcome_block:
        # prompt += "─────────────────────────────────────────────────────────\n"
        prompt += "OUTCOME:\n"
        # prompt += "─────────────────────────────────────────────────────────\n"
        prompt += f"  {outcome_block['code']}\n\n"
    
    # Output instructions
    prompt += """
STRICT RULES:
- Do not assume specific inputs
- Describe behavior only from the given path and decisions
- Do not infer conditions not explicitly shown
- Explain only what the path guarantees, not what inputs might cause it

OUTPUT INSTRUCTIONS:
Explain in 3–4 concise sentences based strictly on the given execution path:
- Mention what kind of execution path this represents(e.g., early return, loop iteration, normal completion)
- What execution scenario this path represents based on control flow (e.g., condition never satisfied, loop completes without match)
- How execution proceeds through key decisions. Example: "the first condition (score >= 90) evaluates to true"
- What the final outcome is(what gets returned or executed). Example: "returns grade 'A' and exits the function"

Reference actual code/conditions in parentheses. Explain in terms of execution flow, not just code.
Start naturally ("This path...", "When execution...", "Along this path...")."""
    
    return prompt


def extract_path_from_selection(
    selected_node_ids: List[str],
    cfg_nodes: List[Dict],
    cfg_edges: List[Dict]
) -> Dict:
    """
    Extract path context from user's node selection.
    
    Args:
        selected_node_ids: ["1", "2", "3", "13"] (node IDs in order)
        cfg_nodes: Full node list
        cfg_edges: Full edge list
    
    Returns:
        {
            "path_blocks": [...],
            "edge_conditions": [...]
        }
    """
    # Normalize IDs so both "3" and "B3" work
    selected_node_ids = [str(i).replace("B", "").strip() for i in selected_node_ids]

    path_blocks = []
    edge_conditions = []
    
    # Get full node data for each selected node
    for node_id in selected_node_ids:
        node = next((n for n in cfg_nodes if n["id"] == node_id), None)
        if node:
            # block_id = f"B{node.get('block_number', node['id'])}"
            bn = node.get('block_number')
            block_id = f"B{bn}" if bn is not None else node.get('id', '?')
            if node["type"] == "start":
                block_id = "START"
            elif node["type"] == "end":
                block_id = "END"
            
            # code_statements = node.get("code_statements") or [node.get("label", "")]
            code_statements = node.get("code_statements")
            if not code_statements:
                label = node.get("label")
                code_statements = [label] if label else ["<no code available>"]

            path_blocks.append({
                "block_id": block_id,
                # "code": node.get("label", ""),
                "code": " | ".join(code_statements),
                "type": node.get("type", "process")
            })
    print("DEBUG cfg_edges (path):", cfg_edges[:3])

    # Extract edge conditions between consecutive nodes
    for i in range(len(selected_node_ids) - 1):
        from_id = selected_node_ids[i]
        to_id = selected_node_ids[i + 1]
        
        # Find edge
        # edge = next(
        #     (e for e in cfg_edges if e["from_node"] == from_id and e["to_node"] == to_id),
        #     None
        # )
        edge = next(
            (
                e for e in cfg_edges
                if (e.get("from_node") or e.get("from")) == from_id
                and (e.get("to_node") or e.get("to")) == to_id
            ),
            None
        )
        
        if edge:
            edge_conditions.append(edge.get("label", ""))
        else:
            edge_conditions.append("")
    
    return {
        "path_blocks": path_blocks,
        "edge_conditions": edge_conditions
    }






# Loop Headers: {path_metrics['loops']}
# Provide a 4 concise lines explanation covering:
# 1. PATH TYPE: Mention what kind of execution path this represents
# (e.g., early return, loop iteration, normal completion)

# 2. SCENARIO: What input/condition triggers this path
# - Example: "when the score is 90 or above"
# - Reference actual conditions from the path

# 3. EXECUTION FLOW: How execution proceeds through the path
# - Mention key decision points and branches taken
# - Example: "the first condition (score >= 90) evaluates to true"

# 4. OUTCOME: What happens at the end of this path
# - What gets returned or executed
# - Example: "returns grade 'A' and exits the function"

# STYLE:
# - Reference actual code/conditions in parentheses
# - Explain in terms of execution flow, not just code
# - Be specific about conditions that trigger this path
# - Keep it concise but complete

# Start naturally ("This path...", "When execution...", "Along this path...").
# No labels or prefixes. Write the explanation now: