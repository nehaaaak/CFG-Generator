from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum


class BlockType(Enum):
    """Types of basic blocks"""
    START = "start"
    END = "end"
    PROCESS = "process"
    DECISION = "decision"
    LOOP_HEADER = "loop_header"
    EXCEPTION = "exception"
    CALL = "call"
    RETURN = "return"


@dataclass
class Statement:
    """Individual statement within a basic block"""
    text: str
    line_no: int
    ast_node_type: str


class BasicBlock:
    """
    A Basic Block is a sequence of statements with:
    - Single entry point (at the beginning)
    - Single exit point (at the end)
    - No branching except at the end
    """
    
    def __init__(self, id: int, block_type: BlockType = BlockType.PROCESS):
        self.id = id
        self.statements: List[Statement] = []
        self.successors: List[Tuple[int, str]] = []  # (block_id, edge_label)
        self.predecessors: Set[int] = set()
        self.block_type = block_type
        self.function_name: Optional[str] = None  # For function call blocks
        
    def add_statement(self, text: str, line_no: int, node_type: str = ""):
        """Add a statement to this basic block"""
        self.statements.append(Statement(text.strip(), line_no, node_type))
    
    def add_successor(self, block_id: int, label: str = ""):
        """Add a successor block"""
        if (block_id, label) not in self.successors:
            self.successors.append((block_id, label))
    
    def add_predecessor(self, block_id: int):
        """Add a predecessor block"""
        self.predecessors.add(block_id)
    
    @property
    def text(self) -> str:
        """Get display text for the block"""
        if not self.statements:
            return self.block_type.value.upper()
        if len(self.statements) == 1:
            return self.statements[0].text
        return "\n".join(s.text for s in self.statements)
    
    @property
    def first_line(self) -> Optional[int]:
        """Get first line number"""
        return self.statements[0].line_no if self.statements else None
    
    @property
    def last_line(self) -> Optional[int]:
        """Get last line number"""
        return self.statements[-1].line_no if self.statements else None
    
    @property
    def is_branch(self) -> bool:
        """Check if this is a branching block"""
        return len(self.successors) > 1
    
    @property
    def is_merge(self) -> bool:
        """Check if this is a merge point"""
        return len(self.predecessors) > 1
    
    def __repr__(self):
        return f"BB{self.id}({self.block_type.value}, {len(self.statements)} stmts)"


class CFG:
    """Control Flow Graph with Basic Blocks"""
    
    def __init__(self, name: str = "main"):
        self.name = name
        self.blocks: Dict[int, BasicBlock] = {}
        self.start_block: Optional[int] = None
        self.end_block: Optional[int] = None
        self.next_id = 1
        
        # Advanced tracking
        self.return_blocks: List[int] = []
        self.loop_headers: List[int] = []
        self.exception_blocks: List[int] = []

        # Unreachable code tracking
        self.unreachable_blocks: Dict[int, BasicBlock] = {}  # Store before deletion
        
    def new_block(self, block_type: BlockType = BlockType.PROCESS) -> int:
        """Create a new basic block"""
        block = BasicBlock(self.next_id, block_type)
        self.blocks[block.id] = block
        self.next_id += 1
        return block.id
    
    def add_edge(self, src: int, dst: int, label: str = ""):
        """Add an edge between blocks"""
        if src in self.blocks and dst in self.blocks:
            self.blocks[src].add_successor(dst, label)
            self.blocks[dst].add_predecessor(src)
    
    def remove_edge(self, src: int, dst: int):
        """Remove an edge between blocks"""
        if src in self.blocks and dst in self.blocks:
            self.blocks[src].successors = [
                (b, l) for b, l in self.blocks[src].successors if b != dst
            ]
            self.blocks[dst].predecessors.discard(src)
    
    def merge_blocks(self, src: int, dst: int):
        """
        Merge two blocks if they form a linear sequence:
        - src has only one successor (dst)
        - dst has only one predecessor (src)
        """
        if src not in self.blocks or dst not in self.blocks:
            return False
        
        src_block = self.blocks[src]
        dst_block = self.blocks[dst]
        
        # Can only merge if it's a linear flow
        if len(src_block.successors) != 1 or len(dst_block.predecessors) != 1:
            return False
        
        if src_block.successors[0][0] != dst:
            return False
        
        # Don't merge special blocks
        if src_block.block_type != BlockType.PROCESS or dst_block.block_type != BlockType.PROCESS:
            return False
        
        # Merge statements
        src_block.statements.extend(dst_block.statements)
        
        # Transfer successors
        src_block.successors = dst_block.successors
        
        # Update predecessors of dst's successors
        for succ_id, _ in dst_block.successors:
            if succ_id in self.blocks:
                self.blocks[succ_id].predecessors.discard(dst)
                self.blocks[succ_id].predecessors.add(src)
        
        # Remove dst block
        del self.blocks[dst]
        
        return True
    
    def optimize(self):
        """Optimize CFG by merging sequential blocks"""
        changed = True
        iterations = 0
        max_iterations = 100
        
        while changed and iterations < max_iterations:
            changed = False
            iterations += 1
            
            # Find mergeable blocks
            for block_id in list(self.blocks.keys()):
                if block_id not in self.blocks:
                    continue
                block = self.blocks[block_id]
                if len(block.successors) == 1:
                    succ_id = block.successors[0][0]
                    if self.merge_blocks(block_id, succ_id):
                        changed = True
                        break
        
        # Remove empty intermediate blocks
        self._remove_empty_blocks()
    
    def remove_unreachable_blocks(self):
        """Remove blocks that are not reachable from start and store them"""
        if not self.start_block:
            return
        
        reachable = set()
        stack = [self.start_block]
        
        while stack:
            current = stack.pop()
            if current in reachable:
                continue
            reachable.add(current)
            
            if current in self.blocks:
                for succ, _ in self.blocks[current].successors:
                    if succ not in reachable:
                        stack.append(succ)
        
        # Remove unreachable blocks
        for block_id in list(self.blocks.keys()):
            if block_id not in reachable:
                self.unreachable_blocks[block_id] = self.blocks[block_id]
                del self.blocks[block_id]
    
    def _remove_empty_blocks(self):
        """
        Remove empty intermediate blocks by connecting predecessors directly to successors.
        Only removes blocks that have:
        - No statements
        - BlockType.PROCESS
        - Not START or END
        """
        changed = True
        while changed:
            changed = False
            
            for block_id in list(self.blocks.keys()):
                if block_id not in self.blocks:
                    continue
                
                # Skip START and END
                if block_id in (self.start_block, self.end_block):
                    continue
                
                block = self.blocks[block_id]
                
                # Only remove empty PROCESS blocks
                if block.statements or block.block_type != BlockType.PROCESS:
                    continue
                
                # Must have exactly one successor
                if len(block.successors) != 1:
                    continue
                
                succ_id, edge_label = block.successors[0]
                
                # Redirect all predecessors to successor
                for pred_id in list(block.predecessors):
                    if pred_id in self.blocks:
                        pred_block = self.blocks[pred_id]
                        
                        # Update predecessor's successors
                        new_successors = []
                        for s_id, s_label in pred_block.successors:
                            if s_id == block_id:
                                # Use the label from predecessor -> empty_block if exists,
                                # otherwise use empty_block -> successor label
                                final_label = s_label if s_label else edge_label
                                new_successors.append((succ_id, final_label))
                            else:
                                new_successors.append((s_id, s_label))
                        pred_block.successors = new_successors
                        
                        # Update successor's predecessors
                        if succ_id in self.blocks:
                            self.blocks[succ_id].predecessors.discard(block_id)
                            self.blocks[succ_id].predecessors.add(pred_id)
                
                # Remove the empty block
                del self.blocks[block_id]
                changed = True
                break
    
    # ==================== METRICS ====================
    
    def calculate_cyclomatic_complexity(self) -> int:
        """
        Cyclomatic Complexity (McCabe's)
        CC = E - N + 2P
        where E = edges, N = nodes, P = connected components
        
        Alternative: CC = decision_points + 1
        """
        if not self.blocks:
            return 0
        
        edges = sum(len(block.successors) for block in self.blocks.values())
        nodes = len(self.blocks)
        components = self._count_connected_components()
        
        cc = edges - nodes + 2 * components
        decision_cc = self.count_decision_points() + 1

        # If graph structure has anomalies, fall back to decision formula
        if abs(cc - decision_cc) > 1:
            return max(1, decision_cc)
        return max(1, cc)
    
    def calculate_cognitive_complexity(self) -> int:
        """
        Cognitive Complexity (Sonar)
        More human-oriented than cyclomatic complexity
        Counts nesting and structural complexity
        """
        complexity = 0
        
        # This is a simplified version - full implementation would need AST
        for block in self.blocks.values():
            if block.block_type == BlockType.DECISION:
                complexity += 1
            elif block.block_type == BlockType.LOOP_HEADER:
                complexity += 1
        
        return complexity
    
    def calculate_nesting_depth(self) -> int:
        """Calculate maximum nesting depth"""
        # Would need AST for accurate calculation
        # Approximation: count nested decision/loop blocks
        return self._calculate_depth_recursive(self.start_block, 0, set())
    
    def _calculate_depth_recursive(self, block_id: int, depth: int, visited: Set[int]) -> int:
        if not block_id or block_id not in self.blocks or block_id in visited:
            return depth
        
        visited.add(block_id)
        block = self.blocks[block_id]
        
        current_depth = depth
        if block.block_type in (BlockType.DECISION, BlockType.LOOP_HEADER):
            current_depth += 1
        
        max_depth = current_depth
        for succ, _ in block.successors:
            max_depth = max(max_depth, self._calculate_depth_recursive(succ, current_depth, visited.copy()))
        
        return max_depth
    
    def count_decision_points(self) -> int:
        """Count number of decision points"""
        return sum(1 for b in self.blocks.values() if b.is_branch)
    
    def count_loops(self) -> int:
        """Count number of loops (back edges)"""
        # return len(self._find_back_edges())
        return len(self.loop_headers)
    
    def count_nested_loops(self) -> int:
        """
        Detect nested loops using dominator relationships.
        If loop A dominates loop B, B is nested inside A.
        """
        if not self.loop_headers:
            return 0

        dominators = self.get_block_dominators()

        nested_count = 0

        for outer in self.loop_headers:
            for inner in self.loop_headers:
                if outer != inner and outer in dominators.get(inner, set()):
                    nested_count += 1

        return nested_count
    
    def _find_back_edges(self) -> List[Tuple[int, int]]:
        """Find back edges (indicating loops)"""
        back_edges = []
        visited = set()
        rec_stack = set()
        
        def dfs(node: int):
            visited.add(node)
            rec_stack.add(node)
            
            if node in self.blocks:
                for succ, _ in self.blocks[node].successors:
                    if succ not in visited:
                        dfs(succ)
                    elif succ in rec_stack:
                        back_edges.append((node, succ))
            
            rec_stack.remove(node)
        
        if self.start_block:
            dfs(self.start_block)
        
        return back_edges
    
    def _count_connected_components(self) -> int:
        """Count connected components in the graph"""
        if not self.blocks:
            return 0
        
        visited = set()
        components = 0
        
        def dfs(node: int):
            visited.add(node)
            if node in self.blocks:
                for succ, _ in self.blocks[node].successors:
                    if succ not in visited:
                        dfs(succ)
                for pred in self.blocks[node].predecessors:
                    if pred not in visited:
                        dfs(pred)
        
        for block_id in self.blocks:
            if block_id not in visited:
                dfs(block_id)
                components += 1
        
        return components
    
    # def find_all_paths(self, max_paths: int = 20) -> List[List[int]]:
    #     """Find all paths from start to end"""
    #     if not self.start_block or not self.end_block:
    #         return []
        
    #     paths = []
        
    #     def dfs(current: int, path: List[int], visited: Set[int]):
    #         if len(paths) >= max_paths:
    #             return
            
    #         if current == self.end_block:
    #             paths.append(path)
    #             return
            
    #         if current not in self.blocks or current in visited:
    #             return
            
    #         visited_copy = visited.copy()
    #         visited_copy.add(current)
            
    #         for succ, _ in self.blocks[current].successors:
    #             dfs(succ, path + [succ], visited_copy)
        
    #     dfs(self.start_block, [self.start_block], set())
    #     return paths

    def find_all_paths(self, max_paths: int = 20) -> List[List[int]]:
        """
        Find execution paths from START to END.
        Handles loops by allowing limited revisits.
        """
        if not self.start_block or not self.end_block:
            return []

        paths: List[List[int]] = []

        def dfs(current: int, path: List[int], visit_count: Dict[int, int]):
            if len(paths) >= max_paths:
                return

            if current not in self.blocks:
                return

            # Record visit
            visit_count[current] = visit_count.get(current, 0) + 1

            #EXTRA            
            block = self.blocks[current]
            # Loop headers may be visited twice
            limit = 2 if block.block_type == BlockType.LOOP_HEADER else 1

            if visit_count[current] > limit:
                visit_count[current] -= 1
                return

            # # Allow visiting a node at most twice (loop traversal)
            # if visit_count[current] > 2:
            #     visit_count[current] -= 1
            #     return

            path.append(current)

            # Stop path if RETURN block
            block = self.blocks[current]

            if current == self.end_block or block.block_type == BlockType.RETURN:
                # ensure path ends at END
                if current != self.end_block and self.end_block:
                    path_with_end = path.copy() + [self.end_block]
                    paths.append(path_with_end)
                else:
                    paths.append(path.copy())
            else:
                for succ, _ in block.successors:
                    dfs(succ, path, visit_count)

            # # Reached END
            # if current == self.end_block:
            #     paths.append(path.copy())
            # else:
            #     for succ, _ in self.blocks[current].successors:
            #         dfs(succ, path, visit_count)

            path.pop()
            visit_count[current] -= 1

        dfs(self.start_block, [], {})
        return paths
    
    def calculate_maintainability_index(self, lines_of_code: int, halstead_volume: float = 100) -> float:
        """
        Maintainability Index
        MI = 171 - 5.2 * ln(HV) - 0.23 * CC - 16.2 * ln(LOC)
        Normalized to 0-100 scale
        """
        import math
        
        cc = self.calculate_cyclomatic_complexity()
        
        if lines_of_code == 0:
            return 100.0
        
        mi = 171 - 5.2 * math.log(halstead_volume) - 0.23 * cc - 16.2 * math.log(lines_of_code)
        mi_normalized = max(0, (mi / 171) * 100)
        
        return round(mi_normalized, 2)
    
    def get_critical_path(self) -> List[int]:
        """
        Estimate critical execution path (longest acyclic path).
        """
        memo = {}

        def dfs(node, visited):
            if node in visited:
                return []

            if node == self.end_block:
                return [node]

            if node in memo:
                return memo[node]

            visited.add(node)

            longest = []
            for succ, _ in self.blocks[node].successors:
                path = dfs(succ, visited.copy())
                if len(path) > len(longest):
                    longest = path

            result = [node] + longest
            memo[node] = result
            return result

        if not self.start_block:
            return []

        return dfs(self.start_block, set())
    
    def get_decision_nodes(self) -> List[int]:
        """
        Return nodes representing decision points.
        """
        return [
            block_id
            for block_id, block in self.blocks.items()
            if block.block_type in (BlockType.DECISION, BlockType.LOOP_HEADER)
        ]
    
    def get_comprehensive_metrics(self) -> Dict:
        """Get all metrics in one call"""
        edges = sum(len(block.successors) for block in self.blocks.values())
        nodes = len(self.blocks)
        cc = self.calculate_cyclomatic_complexity()
        loc = sum(len(block.statements) for block in self.blocks.values())
        mi = self.calculate_maintainability_index(loc)
        critical_path = self.get_critical_path()
        decision_nodes = self.get_decision_nodes()
        
        return {
            "nodes": nodes,
            "edges": edges,
            "lines_of_code": loc,
            "cyclomatic_complexity": cc,
            "cognitive_complexity": self.calculate_cognitive_complexity(),
            "maintainability_index": mi,    
            "decision_points": self.count_decision_points(),
            "loops": self.count_loops(),
            "nested_loops": self.count_nested_loops(),
            "max_nesting_depth": self.calculate_nesting_depth(),
            "decision_nodes": decision_nodes,
            "critical_path_length": len(critical_path),
            "complexity_category": self._categorize_complexity(cc),
            "risk_level": self._calculate_risk_level(cc),
        }
    
    def _categorize_complexity(self, cc: int) -> str:
        """Categorize complexity level"""
        if cc <= 5:
            return "Low"
        elif cc <= 10:
            return "Moderate"
        elif cc <= 20:
            return "High"
        else:
            return "Very High"
    
    def _calculate_risk_level(self, cc: int) -> str:
        """Calculate risk level based on complexity"""
        if cc <= 10:
            return "Low Risk"
        elif cc <= 20:
            return "Medium Risk"
        elif cc <= 50:
            return "High Risk"
        else:
            return "Critical Risk"
    
    def get_block_dominators(self) -> Dict[int, Set[int]]:
        """
        Calculate dominators for each block.
        Block A dominates block B if every path from start to B goes through A.
        """
        if not self.start_block:
            return {}
        
        dominators = {block_id: set(self.blocks.keys()) for block_id in self.blocks}
        dominators[self.start_block] = {self.start_block}
        
        changed = True
        while changed:
            changed = False
            for block_id in self.blocks:
                if block_id == self.start_block:
                    continue
                
                block = self.blocks[block_id]
                if not block.predecessors:
                    continue
                
                # New dominators = {block} ∪ (∩ dominators of predecessors)
                new_dom = set([block_id])
                pred_doms = [dominators[pred] for pred in block.predecessors if pred in dominators]
                if pred_doms:
                    new_dom |= set.intersection(*pred_doms)
                
                if new_dom != dominators[block_id]:
                    dominators[block_id] = new_dom
                    changed = True
        
        return dominators
    
    def __repr__(self):
        return f"CFG({self.name}, {len(self.blocks)} blocks, CC={self.calculate_cyclomatic_complexity()})"


class InterprocedralCFG:
    """
    Interprocedural CFG - links multiple function CFGs together
    """
    
    def __init__(self):
        self.function_cfgs: Dict[str, CFG] = {}
        self.call_graph: Dict[str, List[str]] = {}  # caller -> [callees]
        self.global_cfg: Optional[CFG] = None
    
    def add_function(self, name: str, cfg: CFG):
        """Add a function CFG"""
        self.function_cfgs[name] = cfg
        self.call_graph[name] = []
    
    def add_call(self, caller: str, callee: str):
        """Record a function call"""
        if caller in self.call_graph:
            if callee not in self.call_graph[caller]:
                self.call_graph[caller].append(callee)
    
    def get_call_chain(self, function: str) -> List[str]:
        """Get the call chain starting from a function"""
        visited = set()
        chain = []
        
        def dfs(func: str):
            if func in visited:
                return
            visited.add(func)
            chain.append(func)
            
            for callee in self.call_graph.get(func, []):
                dfs(callee)
        
        dfs(function)
        return chain
    
    def calculate_total_complexity(self) -> int:
        """Calculate total cyclomatic complexity across all functions"""
        return sum(cfg.calculate_cyclomatic_complexity() 
                  for cfg in self.function_cfgs.values())
    
    def get_module_metrics(self) -> Dict:
        """Get metrics for the entire module"""
        total_cc = self.calculate_total_complexity()
        avg_cc = total_cc / len(self.function_cfgs) if self.function_cfgs else 0
        
        return {
            "total_functions": len(self.function_cfgs),
            "total_cyclomatic_complexity": total_cc,
            "average_cyclomatic_complexity": round(avg_cc, 2),
            "max_complexity_function": max(
                self.function_cfgs.items(),
                key=lambda x: x[1].calculate_cyclomatic_complexity()
            )[0] if self.function_cfgs else None,
            "call_graph_size": sum(len(v) for v in self.call_graph.values()),
        }



