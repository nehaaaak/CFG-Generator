import hashlib
import json
from typing import Dict, Any, List  


def create_input_hash(data: Dict[Any, Any]) -> str:
    """
    Create deterministic hash for caching.
    Same input = same hash = cache hit
    """
    # Sort keys for deterministic hash
    json_str = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(json_str.encode()).hexdigest()


def format_metrics_compact(metrics: Dict) -> str:
    """Format metrics in compact form for prompts"""
    return (
        f"Blocks={metrics.get('nodes', 0)}, "
        f"Edges={metrics.get('edges', 0)}, "
        f"Paths={metrics.get('path_count', 0)}, "
        f"CC={metrics.get('cyclomatic_complexity', 0)} "
        f"({metrics.get('complexity_category', 'Unknown')}), "
        f"Decisions={metrics.get('decision_points', 0)}, "
        f"Loops={metrics.get('loops', 0)}, "
        f"Nesting={metrics.get('max_nesting_depth', 0)}, "
        f"Risk={metrics.get('risk_level', 'Unknown')}"
    )


def format_smells_compact(smells: List[Dict]) -> str:
    """Format code smells in compact form"""
    if not smells:
        return "None"
    
    by_severity = {}
    for smell in smells:
        severity = smell.get('severity', 'unknown')
        by_severity[severity] = by_severity.get(severity, 0) + 1
    
    parts = []
    for severity in ['critical', 'high', 'medium', 'low']:
        count = by_severity.get(severity, 0)
        if count > 0:
            parts.append(f"{severity}={count}")
    
    return ", ".join(parts) if parts else "None"


def format_top_issues(smells: List[Dict], limit: int = 3) -> str:
    """Extract top N issues as bullet points"""
    if not smells:
        return "No issues detected"
    
    lines = []
    for smell in smells[:limit]:
        smell_type = smell.get('type', 'unknown').replace('_', ' ').title()
        message = smell.get('message', '')
        lines.append(f"- {smell_type}: {message}")
    
    return "\n".join(lines)