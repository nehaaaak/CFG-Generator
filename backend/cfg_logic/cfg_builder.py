import ast
from typing import Dict, List, Optional, Set, Tuple
from .classes import CFG, BasicBlock, BlockType, InterprocedralCFG


class BasicBlockCFGBuilder(ast.NodeVisitor):
    """
    Builds a Control Flow Graph using Basic Blocks.
    
    A Basic Block is a maximal sequence of consecutive statements with:
    - Single entry point (first statement)
    - Single exit point (last statement)
    - No internal branches
    """
    
    def __init__(self, source_code: str, function_name: str = "main"):
        self.source = source_code
        self.lines = source_code.split("\n")
        self.cfg = CFG(function_name)
        
        # Current block being built
        self.current_block: Optional[int] = None
        
        # Control flow management
        self.break_targets: List[int] = []
        self.continue_targets: List[int] = []
        self.loop_exits: List[int] = []
        
        # Function call tracking for interprocedural analysis
        self.function_calls: List[Tuple[str, int]] = []  # (function_name, line_no)
    
    def build(self) -> CFG:
        """Build the CFG from source code"""
        try:
            tree = ast.parse(self.source)
            
            # Create START block
            self.cfg.start_block = self.cfg.new_block(BlockType.START)
            self.current_block = self.cfg.start_block
            
            # Process module-level statements
            for stmt in tree.body:
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue  # Skip definitions in module-level CFG
                self.visit(stmt)
            
            # Create END block
            self.cfg.end_block = self.cfg.new_block(BlockType.END)
            
            # Connect all blocks without successors to END
            self._connect_loose_ends()
            
            # Optimize: merge sequential blocks
            self.cfg.optimize()
            
            # Remove unreachable blocks
            self.cfg.remove_unreachable_blocks()
            
            return self.cfg
            
        except Exception as e:
            raise Exception(f"CFG build error: {str(e)}")
    
    def _connect_loose_ends(self):
        """Connect all blocks without successors to the END block"""
        for block_id, block in list(self.cfg.blocks.items()):
            if block_id == self.cfg.end_block:
                continue
            
            # Connect blocks without successors (except returns)
            if not block.successors:
                # Check if last statement is a return
                is_return = False
                if block.statements:
                    last_stmt = block.statements[-1].text.strip()
                    if last_stmt.startswith("return") or last_stmt.startswith("raise"):
                        is_return = True
                
                # Always connect to END, even returns
                self.cfg.add_edge(block_id, self.cfg.end_block)
    
    def _start_new_block(self, block_type: BlockType = BlockType.PROCESS) -> int:
        """Start a new basic block"""
        new_block_id = self.cfg.new_block(block_type)
        
        # Connect previous block to new block if it exists
        if self.current_block is not None:
            current = self.cfg.blocks[self.current_block]
            # Only auto-connect if current block has no successors
            if not current.successors:
                self.cfg.add_edge(self.current_block, new_block_id)
        
        self.current_block = new_block_id
        return new_block_id
    
    def _add_statement_to_current_block(self, text: str, line_no: int, node_type: str = ""):
        """Add statement to current block"""
        if self.current_block is not None:
            self.cfg.blocks[self.current_block].add_statement(text, line_no, node_type)
    
    def _is_leader(self, stmt, prev_stmt) -> bool:
        """
        Determine if a statement is a leader (starts a new basic block).
        Leaders are:
        1. First statement in the program
        2. Target of a conditional or unconditional jump
        3. Statement immediately following a conditional or unconditional jump
        """
        # Branch statements end a block, so next statement is a leader
        if prev_stmt and isinstance(prev_stmt, (ast.If, ast.While, ast.For, ast.Break, 
                                                  ast.Continue, ast.Return, ast.Raise)):
            return True
        
        # First statement
        if prev_stmt is None:
            return True
        
        return False
    
    # ==================== SIMPLE STATEMENTS ====================
    
    def visit_Expr(self, node):
        """Expression statement (function call, etc.)"""
        text = ast.unparse(node.value)
        
        # Check for function calls
        if isinstance(node.value, ast.Call):
            func_name = self._get_function_name(node.value.func)
            if func_name:
                self.function_calls.append((func_name, node.lineno))
        
        self._add_statement_to_current_block(text, node.lineno, "Expr")
    
    def visit_Assign(self, node):
        """Assignment statement"""
        text = ast.unparse(node)
        self._add_statement_to_current_block(text, node.lineno, "Assign")
    
    def visit_AugAssign(self, node):
        """Augmented assignment (+=, -=, etc.)"""
        text = ast.unparse(node)
        self._add_statement_to_current_block(text, node.lineno, "AugAssign")
    
    def visit_AnnAssign(self, node):
        """Annotated assignment"""
        text = ast.unparse(node)
        self._add_statement_to_current_block(text, node.lineno, "AnnAssign")
    
    def visit_Delete(self, node):
        """Delete statement"""
        text = ast.unparse(node)
        self._add_statement_to_current_block(text, node.lineno, "Delete")
    
    def visit_Pass(self, node):
        """Pass statement"""
        self._add_statement_to_current_block("pass", node.lineno, "Pass")
    
    def visit_Import(self, node):
        """Import statement"""
        text = ast.unparse(node)
        self._add_statement_to_current_block(text, node.lineno, "Import")
    
    def visit_ImportFrom(self, node):
        """From import statement"""
        text = ast.unparse(node)
        self._add_statement_to_current_block(text, node.lineno, "ImportFrom")
    
    def visit_Global(self, node):
        """Global statement"""
        text = ast.unparse(node)
        self._add_statement_to_current_block(text, node.lineno, "Global")
    
    def visit_Nonlocal(self, node):
        """Nonlocal statement"""
        text = ast.unparse(node)
        self._add_statement_to_current_block(text, node.lineno, "Nonlocal")
    
    def visit_Assert(self, node):
        """Assert statement"""
        text = ast.unparse(node)
        self._add_statement_to_current_block(text, node.lineno, "Assert")
    
    # ==================== CONTROL FLOW ====================
    
    def visit_Return(self, node):
        """Return statement - ends current block"""
        text = f"return {ast.unparse(node.value) if node.value else ''}"
        
        # Add to current block
        self._add_statement_to_current_block(text, node.lineno, "Return")
        
        # Mark current block as return
        if self.current_block:
            self.cfg.blocks[self.current_block].block_type = BlockType.RETURN
            self.cfg.return_blocks.append(self.current_block)
        
        # Start new block (dead code follows return)
        self._start_new_block()
    
    def visit_Raise(self, node):
        """Raise statement - ends current block"""
        text = ast.unparse(node)
        self._add_statement_to_current_block(text, node.lineno, "Raise")
        
        # Mark as exception
        if self.current_block:
            self.cfg.blocks[self.current_block].block_type = BlockType.EXCEPTION
        
        # Start new block
        self._start_new_block()
    
    def visit_If(self, node):
        """
        If/elif/else statement
        
        Structure:
        [current] -> [condition] -> [true_branch]
                                 -> [false_branch/elif/else]
        Both branches -> [merge_point]
        """
        # Save entry block
        entry_block = self.current_block
        
        # Create decision block
        condition_text = ast.unparse(node.test)
        decision_block = self._start_new_block(BlockType.DECISION)
        self.cfg.blocks[decision_block].add_statement(condition_text, node.lineno, "If")
        
        # Process TRUE branch
        true_branch_start = self._start_new_block()
        for stmt in node.body:
            self.visit(stmt)
        true_branch_end = self.current_block
        
        # Process FALSE branch (elif/else)
        false_branch_end = None
        if node.orelse:
            # Create false branch starting block
            false_branch_start = self.cfg.new_block()
            self.cfg.add_edge(decision_block, false_branch_start, "False")
            self.current_block = false_branch_start
            
            for stmt in node.orelse:
                self.visit(stmt)
            false_branch_end = self.current_block
        
        # Create merge point
        merge_block = self.cfg.new_block()
        
        # Connect true branch to merge
        if true_branch_end and true_branch_end in self.cfg.blocks:
            if not self.cfg.blocks[true_branch_end].successors:
                self.cfg.add_edge(true_branch_end, merge_block)
        
        # Connect false branch to merge
        if false_branch_end and false_branch_end in self.cfg.blocks:
            if not self.cfg.blocks[false_branch_end].successors:
                self.cfg.add_edge(false_branch_end, merge_block)
        
        # If no else, connect decision directly to merge
        if not node.orelse:
            self.cfg.add_edge(decision_block, merge_block, "False")
        
        # Fix edge labels
        if true_branch_start in self.cfg.blocks:
            # Remove auto-added edge and add labeled one
            self.cfg.remove_edge(decision_block, true_branch_start)
            self.cfg.add_edge(decision_block, true_branch_start, "True")
        
        self.current_block = merge_block
    
    def visit_While(self, node):
        """
        While loop
        
        Structure:
        [entry] -> [condition] -> [body] -> back to [condition]
                               -> [exit]
        """
        # Create loop condition block (loop header)
        condition_text = ast.unparse(node.test)
        loop_header = self._start_new_block(BlockType.LOOP_HEADER)
        self.cfg.blocks[loop_header].add_statement(condition_text, node.lineno, "While")
        self.cfg.loop_headers.append(loop_header)
        
        # Create exit block
        exit_block = self.cfg.new_block()
        self.loop_exits.append(exit_block)
        
        # Set break/continue targets
        self.break_targets.append(exit_block)
        self.continue_targets.append(loop_header)
        
        # Process loop body
        body_start = self._start_new_block()
        self.cfg.remove_edge(loop_header, body_start)  # Remove auto-edge
        self.cfg.add_edge(loop_header, body_start, "True")
        
        for stmt in node.body:
            self.visit(stmt)
        body_end = self.current_block
        
        # Back edge from body to condition
        if body_end and body_end in self.cfg.blocks:
            if not self.cfg.blocks[body_end].successors:
                self.cfg.add_edge(body_end, loop_header)
        
        # Exit edge from condition
        self.cfg.add_edge(loop_header, exit_block, "False")
        
        # Clean up
        self.break_targets.pop()
        self.continue_targets.pop()
        self.loop_exits.pop()
        
        self.current_block = exit_block
    
    def visit_For(self, node):
        """
        For loop
        
        Structure similar to while loop
        """
        target = ast.unparse(node.target)
        iter_val = ast.unparse(node.iter)
        condition_text = f"for {target} in {iter_val}"
        
        # Loop header
        loop_header = self._start_new_block(BlockType.LOOP_HEADER)
        self.cfg.blocks[loop_header].add_statement(condition_text, node.lineno, "For")
        self.cfg.loop_headers.append(loop_header)
        
        # Exit block
        exit_block = self.cfg.new_block()
        self.loop_exits.append(exit_block)
        
        # Set targets
        self.break_targets.append(exit_block)
        self.continue_targets.append(loop_header)
        
        # Loop body
        body_start = self._start_new_block()
        self.cfg.remove_edge(loop_header, body_start)
        self.cfg.add_edge(loop_header, body_start, "Next")
        
        for stmt in node.body:
            self.visit(stmt)
        body_end = self.current_block
        
        # Process else clause (executed if loop completes normally)
        if node.orelse:
            else_start = self.cfg.new_block()
            self.cfg.add_edge(loop_header, else_start, "Done")
            self.current_block = else_start
            
            for stmt in node.orelse:
                self.visit(stmt)
            
            # Else flows to exit
            if self.current_block and not self.cfg.blocks[self.current_block].successors:
                self.cfg.add_edge(self.current_block, exit_block)
        else:
            # Direct exit from loop
            self.cfg.add_edge(loop_header, exit_block, "Done")
        
        # Back edge
        if body_end and body_end in self.cfg.blocks:
            if not self.cfg.blocks[body_end].successors:
                self.cfg.add_edge(body_end, loop_header)
        
        # Clean up
        self.break_targets.pop()
        self.continue_targets.pop()
        self.loop_exits.pop()
        
        self.current_block = exit_block
    
    def visit_Break(self, node):
        """Break statement - jumps to loop exit"""
        self._add_statement_to_current_block("break", node.lineno, "Break")
        
        if self.break_targets:
            self.cfg.add_edge(self.current_block, self.break_targets[-1])
        
        # Start new block (code after break is unreachable until next leader)
        self._start_new_block()
    
    def visit_Continue(self, node):
        """Continue statement - jumps to loop header"""
        self._add_statement_to_current_block("continue", node.lineno, "Continue")
        
        if self.continue_targets:
            self.cfg.add_edge(self.current_block, self.continue_targets[-1])
        
        # Start new block
        self._start_new_block()
    
    def visit_Try(self, node):
        """
        Try-except-finally statement
        
        Complex structure with multiple paths
        """
        # Try block
        try_start = self._start_new_block()
        self.cfg.blocks[try_start].add_statement("try:", node.lineno, "Try")
        
        for stmt in node.body:
            self.visit(stmt)
        try_end = self.current_block
        
        # Exception handlers
        handler_ends = []
        for handler in node.handlers:
            exc_type = ast.unparse(handler.type) if handler.type else "Exception"
            exc_name = f" as {handler.name}" if handler.name else ""
            
            handler_start = self.cfg.new_block(BlockType.EXCEPTION)
            self.cfg.blocks[handler_start].add_statement(
                f"except {exc_type}{exc_name}:", handler.lineno, "Except"
            )
            self.cfg.exception_blocks.append(handler_start)
            
            # Connect try to handler (exception edge)
            self.cfg.add_edge(try_start, handler_start, f"{exc_type}")
            
            # Process handler body
            self.current_block = handler_start
            for stmt in handler.body:
                self.visit(stmt)
            
            handler_ends.append(self.current_block)
        
        # Else clause (executed if no exception)
        else_end = None
        if node.orelse:
            else_start = self.cfg.new_block()
            if try_end:
                self.cfg.add_edge(try_end, else_start)
            
            self.current_block = else_start
            for stmt in node.orelse:
                self.visit(stmt)
            else_end = self.current_block
        
        # Finally clause (always executed)
        if node.finalbody:
            finally_start = self.cfg.new_block()
            self.cfg.blocks[finally_start].add_statement("finally:", node.finalbody[0].lineno, "Finally")
            
            # Connect all paths to finally
            if try_end:
                self.cfg.add_edge(try_end, finally_start)
            if else_end:
                self.cfg.add_edge(else_end, finally_start)
            for handler_end in handler_ends:
                if handler_end:
                    self.cfg.add_edge(handler_end, finally_start)
            
            # Process finally body
            self.current_block = finally_start
            for stmt in node.finalbody:
                self.visit(stmt)
        else:
            # Create merge point
            merge = self.cfg.new_block()
            if try_end:
                self.cfg.add_edge(try_end, merge)
            if else_end:
                self.cfg.add_edge(else_end, merge)
            for handler_end in handler_ends:
                if handler_end:
                    self.cfg.add_edge(handler_end, merge)
            
            self.current_block = merge
    
    def visit_With(self, node):
        """
        With statement (context manager)
        """
        items = ", ".join(ast.unparse(item) for item in node.items)
        
        with_start = self._start_new_block()
        self.cfg.blocks[with_start].add_statement(f"with {items}:", node.lineno, "With")
        
        for stmt in node.body:
            self.visit(stmt)
    
    def visit_Match(self, node):
        """
        Match statement (Python 3.10+)
        """
        match_val = ast.unparse(node.subject)
        
        match_block = self._start_new_block(BlockType.DECISION)
        self.cfg.blocks[match_block].add_statement(f"match {match_val}:", node.lineno, "Match")
        
        case_ends = []
        for case in node.cases:
            pattern = ast.unparse(case.pattern)
            
            case_start = self.cfg.new_block()
            self.cfg.blocks[case_start].add_statement(f"case {pattern}:", case.lineno, "Case")
            self.cfg.add_edge(match_block, case_start, f"case {pattern}")
            
            self.current_block = case_start
            for stmt in case.body:
                self.visit(stmt)
            
            case_ends.append(self.current_block)
        
        # Merge point
        merge = self.cfg.new_block()
        for case_end in case_ends:
            if case_end and not self.cfg.blocks[case_end].successors:
                self.cfg.add_edge(case_end, merge)
        
        self.current_block = merge
    
    def visit_FunctionDef(self, node):
        """Skip function definitions in main flow"""
        pass
    
    def visit_AsyncFunctionDef(self, node):
        """Skip async function definitions"""
        pass
    
    def visit_ClassDef(self, node):
        """Skip class definitions"""
        pass
    
    # ==================== HELPER METHODS ====================
    
    def _get_function_name(self, node) -> Optional[str]:
        """Extract function name from call node"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        return None


# ==================== INTERPROCEDURAL ANALYSIS ====================

def build_interprocedural_cfg(source_code: str) -> InterprocedralCFG:
    """
    Build an interprocedural CFG linking all functions in the code
    """
    icfg = InterprocedralCFG()
    
    try:
        tree = ast.parse(source_code)
        
        # Extract all function definitions
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_code = ast.unparse(node)
                func_cfg = build_function_cfg(node, node.name)
                icfg.add_function(node.name, func_cfg)
        
        # Build call graph
        for func_name, func_cfg in icfg.function_cfgs.items():
            # Extract function calls from CFG
            for block in func_cfg.blocks.values():
                for stmt in block.statements:
                    # Simple heuristic: look for function call patterns
                    if "(" in stmt.text and ")" in stmt.text:
                        # Try to extract called function name
                        try:
                            call_tree = ast.parse(stmt.text)
                            for node in ast.walk(call_tree):
                                if isinstance(node, ast.Call):
                                    if isinstance(node.func, ast.Name):
                                        callee = node.func.id
                                        if callee in icfg.function_cfgs:
                                            icfg.add_call(func_name, callee)
                        except:
                            pass
        
        return icfg
        
    except Exception as e:
        raise Exception(f"Interprocedural CFG build error: {str(e)}")


def build_function_cfg(func_node: ast.FunctionDef, func_name: str) -> CFG:
    """Build CFG for a single function"""
    # Create dummy source for the function
    func_code = ast.unparse(func_node)
    
    # Create builder
    builder = BasicBlockCFGBuilder(func_code, func_name)
    builder.cfg = CFG(func_name)
    
    # Create START
    builder.cfg.start_block = builder.cfg.new_block(BlockType.START)
    builder.current_block = builder.cfg.start_block
    
    # Process function body
    for stmt in func_node.body:
        builder.visit(stmt)
    
    # Create END
    builder.cfg.end_block = builder.cfg.new_block(BlockType.END)
    
    # Connect loose ends
    builder._connect_loose_ends()
    
    # Optimize
    builder.cfg.optimize()
    builder.cfg.remove_unreachable_blocks()
    
    return builder.cfg


def build_module_cfg(source_code: str) -> CFG:
    """Build CFG for module-level code (non-function code)"""
    builder = BasicBlockCFGBuilder(source_code, "module")
    return builder.build()


# ==================== CONVENIENCE FUNCTION ====================

def analyze_code(source_code: str, mode: str = "function") -> Dict:
    """
    Analyze code and return CFG with metrics
    
    Args:
        source_code: Python source code
        mode: "function" (per-function analysis) or "module" (module-level) or "interprocedural"
    
    Returns:
        Dictionary with CFG and metrics
    """
    result = {
        "success": True,
        "cfgs": {},
        "metrics": {},
        "errors": []
    }
    
    try:
        if mode == "interprocedural":
            icfg = build_interprocedural_cfg(source_code)
            result["icfg"] = icfg
            result["metrics"]["module"] = icfg.get_module_metrics()
            
            for func_name, cfg in icfg.function_cfgs.items():
                result["cfgs"][func_name] = cfg
                result["metrics"][func_name] = cfg.get_comprehensive_metrics()
        
        elif mode == "function":
            tree = ast.parse(source_code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    cfg = build_function_cfg(node, node.name)
                    result["cfgs"][node.name] = cfg
                    result["metrics"][node.name] = cfg.get_comprehensive_metrics()
        
        else:  # module
            cfg = build_module_cfg(source_code)
            result["cfgs"]["module"] = cfg
            result["metrics"]["module"] = cfg.get_comprehensive_metrics()
    
    except Exception as e:
        result["success"] = False
        result["errors"].append(str(e))
    
    return result



