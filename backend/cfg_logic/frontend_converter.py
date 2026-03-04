from typing import Dict, List
from .classes import CFG, BlockType
from .cfg_builder import build_function_cfg, build_module_cfg, build_interprocedural_cfg
import ast


# ==================== MODELS (matching your existing structure) ====================

class Node:
    """Frontend node model"""
    def __init__(self, id: str, label: str, type: str, x: int = 0, y: int = 0, line_number: int = None):
        self.id = id
        self.label = label
        self.type = type
        self.x = x
        self.y = y
        self.line_number = line_number
    
    def to_dict(self):
        return {
            "id": self.id,
            "label": self.label,
            "type": self.type,
            "x": self.x,
            "y": self.y,
            "line_number": self.line_number
        }


class Edge:
    """Frontend edge model"""
    def __init__(self, from_node: str, to_node: str, label: str = ""):
        self.from_node = from_node
        self.to_node = to_node
        self.label = label
    
    def to_dict(self):
        return {
            "from": self.from_node,
            "to": self.to_node,
            "label": self.label
        }


class FunctionCFG:
    """Complete CFG for frontend consumption"""
    def __init__(self, name: str, nodes: List[Node], edges: List[Edge], 
                 cc: int, metrics: Dict, paths: List[List[str]] = None):
        self.name = name
        self.nodes = nodes
        self.edges = edges
        self.cc = cc
        self.metrics = metrics
        self.paths = paths or []
    
    def to_dict(self):
        return {
            "name": self.name,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "cyclomatic_complexity": self.cc,
            "metrics": self.metrics,
            "paths": self.paths
        }


# ==================== CFG TO FRONTEND CONVERSION ====================

def cfg_to_frontend(cfg: CFG, func_name: str = "main") -> FunctionCFG:
    """
    Convert internal CFG to frontend-compatible format.
    Dagre will handle layout in frontend (x, y set to 0).
    """
    
    # Create nodes
    nodes = []
    for block_id, block in cfg.blocks.items():
        # Determine node type for frontend
        node_type = _map_block_type_to_frontend(block.block_type)
        
        # Get label text
        label = _get_block_label(block)
        
        nodes.append(Node(
            id=str(block_id),
            label=label,
            type=node_type,
            x=0,  # Dagre calculates layout
            y=0,
            line_number=block.first_line
        ))
    
    # Create edges
    edges = []
    for block_id, block in cfg.blocks.items():
        for succ_id, label in block.successors:
            edges.append(Edge(
                from_node=str(block_id),
                to_node=str(succ_id),
                label=label or ""
            ))
    
    # Calculate metrics
    metrics = cfg.get_comprehensive_metrics()
    cc = metrics["cyclomatic_complexity"]
    
    # Get execution paths
    paths = _format_paths(cfg)
    
    return FunctionCFG(
        name=func_name,
        nodes=nodes,
        edges=edges,
        cc=cc,
        metrics=metrics,
        paths=paths
    )


def _map_block_type_to_frontend(block_type: BlockType) -> str:
    """Map internal block type to frontend type"""
    mapping = {
        BlockType.START: "start",
        BlockType.END: "end",
        BlockType.PROCESS: "process",
        BlockType.DECISION: "decision",
        BlockType.LOOP_HEADER: "decision",  # Loops are decisions
        BlockType.EXCEPTION: "process",
        BlockType.CALL: "process",
        BlockType.RETURN: "process"
    }
    return mapping.get(block_type, "process")


def _get_block_label(block) -> str:
    """Get display label for block"""
    if block.block_type == BlockType.START:
        return "START"
    elif block.block_type == BlockType.END:
        return "END"
    elif not block.statements:
        return "..."
    
    # For blocks with multiple statements, show first few
    if len(block.statements) == 1:
        return block.statements[0].text
    elif len(block.statements) <= 3:
        return "\n".join(s.text for s in block.statements)
    else:
        # Show first 3 statements + indicator
        lines = [s.text for s in block.statements[:3]]
        lines.append(f"... ({len(block.statements) - 3} more)")
        return "\n".join(lines)


def _format_paths(cfg: CFG) -> List[List[str]]:
    """Format execution paths for frontend"""
    raw_paths = cfg.find_all_paths(max_paths=10)
    
    formatted_paths = []
    for path in raw_paths:
        path_labels = []
        for block_id in path:
            if block_id in cfg.blocks:
                block = cfg.blocks[block_id]
                label = _get_block_label(block)
                path_labels.append(label)
        formatted_paths.append(path_labels)
    
    return formatted_paths


# ==================== MAIN API FUNCTIONS ====================

def generate_cfg_for_code(source_code: str, function_name: str = None) -> Dict:
    """
    Main API function to generate CFG from source code.
    
    Args:
        source_code: Python source code
        function_name: Specific function to analyze, or None for all functions
    
    Returns:
        Dictionary with CFGs and metrics for frontend
    """
    result = {
        "success": True,
        "functions": {},
        "module_metrics": None,
        "errors": []
    }
    
    try:
        tree = ast.parse(source_code)
        
        # Extract all functions
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append((node.name, node))
        
        # If specific function requested
        if function_name:
            matching = [f for f in functions if f[0] == function_name]
            if not matching:
                result["success"] = False
                result["errors"].append(f"Function '{function_name}' not found")
                return result
            functions = matching
        
        # Build CFG for each function
        if functions:
            for fname, fnode in functions:
                cfg = build_function_cfg(fnode, fname)
                frontend_cfg = cfg_to_frontend(cfg, fname)
                result["functions"][fname] = frontend_cfg.to_dict()
        else:
            # No functions, analyze module-level code
            cfg = build_module_cfg(source_code)
            frontend_cfg = cfg_to_frontend(cfg, "module")
            result["functions"]["module"] = frontend_cfg.to_dict()
        
        # Add interprocedural metrics if multiple functions
        if len(functions) > 1:
            icfg = build_interprocedural_cfg(source_code)
            result["module_metrics"] = icfg.get_module_metrics()
            result["call_graph"] = icfg.call_graph
        
    except SyntaxError as e:
        result["success"] = False
        result["errors"].append(f"Syntax error: {str(e)}")
    except Exception as e:
        result["success"] = False
        result["errors"].append(f"Error: {str(e)}")
    
    return result


def generate_cfg_for_function(source_code: str, function_name: str) -> Dict:
    """
    Generate CFG for a specific function.
    
    This is the function your API endpoint should call.
    """
    return generate_cfg_for_code(source_code, function_name)


def generate_interprocedural_cfg(source_code: str) -> Dict:
    """
    Generate interprocedural CFG with call graph.
    """
    result = {
        "success": True,
        "functions": {},
        "call_graph": {},
        "module_metrics": {},
        "errors": []
    }
    
    try:
        icfg = build_interprocedural_cfg(source_code)
        
        # Convert each function CFG
        for func_name, cfg in icfg.function_cfgs.items():
            frontend_cfg = cfg_to_frontend(cfg, func_name)
            result["functions"][func_name] = frontend_cfg.to_dict()
        
        # Add module-level metrics
        result["module_metrics"] = icfg.get_module_metrics()
        result["call_graph"] = icfg.call_graph
        
    except Exception as e:
        result["success"] = False
        result["errors"].append(str(e))
    
    return result


# ==================== DEBUGGING / VALIDATION ====================

def validate_cfg_metrics(cfg: CFG) -> Dict:
    """
    Validate that CFG metrics are calculated correctly.
    Returns diagnostic information.
    """
    diagnostics = {
        "valid": True,
        "issues": [],
        "details": {}
    }
    
    # Count nodes and edges
    node_count = len(cfg.blocks)
    edge_count = sum(len(block.successors) for block in cfg.blocks.values())
    
    diagnostics["details"]["node_count"] = node_count
    diagnostics["details"]["edge_count"] = edge_count
    
    # Check for orphaned blocks (no predecessors or successors)
    orphaned = []
    for block_id, block in cfg.blocks.items():
        if block_id not in (cfg.start_block, cfg.end_block):
            if not block.predecessors and not block.successors:
                orphaned.append(block_id)
    
    if orphaned:
        diagnostics["valid"] = False
        diagnostics["issues"].append(f"Orphaned blocks: {orphaned}")
    
    # Check START has no predecessors
    if cfg.start_block and cfg.blocks[cfg.start_block].predecessors:
        diagnostics["valid"] = False
        diagnostics["issues"].append("START block has predecessors")
    
    # Check END has no successors
    if cfg.end_block and cfg.blocks[cfg.end_block].successors:
        diagnostics["valid"] = False
        diagnostics["issues"].append("END block has successors")
    
    # Verify cyclomatic complexity calculation
    cc_formula = edge_count - node_count + 2
    cc_actual = cfg.calculate_cyclomatic_complexity()
    
    diagnostics["details"]["cc_formula"] = cc_formula
    diagnostics["details"]["cc_actual"] = cc_actual
    
    if abs(cc_formula - cc_actual) > 1:  # Allow for rounding
        diagnostics["issues"].append(
            f"CC mismatch: formula={cc_formula}, actual={cc_actual}"
        )
    
    return diagnostics


# ==================== EXAMPLE USAGE ====================

def example_usage():
    """Example of how to use this module"""
    
    code = """
        def grade(score):
            if score >= 90:
                return "A"
            elif score >= 75:
                return "B"
            else:
                return "C"
        """
    
    # Generate CFG
    result = generate_cfg_for_code(code)
    
    if result["success"]:
        print("✓ CFG generated successfully")
        
        for func_name, cfg_data in result["functions"].items():
            print(f"\nFunction: {func_name}")
            print(f"  Nodes: {len(cfg_data['nodes'])}")
            print(f"  Edges: {len(cfg_data['edges'])}")
            print(f"  Cyclomatic Complexity: {cfg_data['cyclomatic_complexity']}")
            print(f"  Metrics: {cfg_data['metrics']}")
    else:
        print("✗ Errors:")
        for error in result["errors"]:
            print(f"  - {error}")


if __name__ == "__main__":
    example_usage()