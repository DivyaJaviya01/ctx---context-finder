import ast
import re
from pathlib import Path
from typing import List, Set, Optional
from ctx_finder.models import Symbol, FileAnalysis
from ctx_finder.cache import CacheManager

EXTENSION_LANG_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".java": "java",
    ".cs": "csharp",
    ".php": "php",
    ".rb": "ruby"
}

def get_language(file_path: Path) -> Optional[str]:
    return EXTENSION_LANG_MAP.get(file_path.suffix.lower())

def parse_python_file(content: str, file_rel_path: str) -> tuple[List[Symbol], List[str]]:
    symbols: List[Symbol] = []
    imports: List[str] = []
    
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return symbols, imports

    class PythonASTVisitor(ast.NodeVisitor):
        def __init__(self):
            self.current_class = None

        def visit_Import(self, node):
            for alias in node.names:
                imports.append(alias.name)
            self.generic_visit(node)

        def visit_ImportFrom(self, node):
            if node.module:
                imports.append(node.module)
            self.generic_visit(node)

        def visit_ClassDef(self, node):
            symbols.append(Symbol(
                name=node.name,
                symbol_type="class",
                line=node.lineno,
                source=file_rel_path
            ))
            
            old_class = self.current_class
            self.current_class = node.name
            
            # Decorators on classes
            for dec in node.decorator_list:
                dec_name = ""
                if isinstance(dec, ast.Name):
                    dec_name = dec.id
                elif isinstance(dec, ast.Attribute):
                    dec_name = dec.attr
                elif isinstance(dec, ast.Call):
                    if isinstance(dec.func, ast.Name):
                        dec_name = dec.func.id
                    elif isinstance(dec.func, ast.Attribute):
                        dec_name = dec.func.attr
                if dec_name:
                    symbols.append(Symbol(
                        name=dec_name,
                        symbol_type="decorator",
                        line=dec.lineno,
                        source=file_rel_path
                    ))
            
            self.generic_visit(node)
            self.current_class = old_class

        def visit_FunctionDef(self, node):
            self.process_function(node)

        def visit_AsyncFunctionDef(self, node):
            self.process_function(node)

        def process_function(self, node):
            is_method = self.current_class is not None
            sym_type = "method" if is_method else "function"
            
            symbols.append(Symbol(
                name=node.name,
                symbol_type=sym_type,
                line=node.lineno,
                source=file_rel_path
            ))
            
            # Check for routes or decorators
            for dec in node.decorator_list:
                dec_name = ""
                is_route = False
                
                # Check Name decorator: @route
                if isinstance(dec, ast.Name):
                    dec_name = dec.id
                # Check Attribute decorator: @app.route
                elif isinstance(dec, ast.Attribute):
                    dec_name = dec.attr
                # Check Call decorator: @app.route() or @router.get()
                elif isinstance(dec, ast.Call):
                    func = dec.func
                    if isinstance(func, ast.Name):
                        dec_name = func.id
                    elif isinstance(func, ast.Attribute):
                        dec_name = func.attr
                        # E.g. @router.get("/login") -> 'get' decorator, check parent router/route name
                        if isinstance(func.value, ast.Name) and "route" in func.value.id.lower():
                            is_route = True
                            
                if dec_name:
                    if "route" in dec_name.lower() or is_route:
                        symbols.append(Symbol(
                            name=f"{node.name} route",
                            symbol_type="route",
                            line=dec.lineno,
                            source=file_rel_path
                        ))
                    else:
                        symbols.append(Symbol(
                            name=dec_name,
                            symbol_type="decorator",
                            line=dec.lineno,
                            source=file_rel_path
                        ))
                        
            self.generic_visit(node)

    PythonASTVisitor().visit(tree)
    return symbols, imports

def parse_regex_file(content: str, language: str, file_rel_path: str) -> tuple[List[Symbol], List[str]]:
    symbols: List[Symbol] = []
    imports: List[str] = []
    
    lines = content.splitlines()
    
    # Regular expressions for different languages
    patterns = {
        "javascript": {
            "imports": [
                r"import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]",
                r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"
            ],
            "classes": [r"class\s+(\w+)"],
            "functions": [
                r"function\s+(\w+)",
                r"const\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>",
                r"export\s+const\s+(\w+)\s*=",
                r"export\s+default\s+function\s+(\w+)"
            ]
        },
        "typescript": {
            "imports": [
                r"import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]",
                r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"
            ],
            "classes": [r"class\s+(\w+)", r"interface\s+(\w+)", r"type\s+(\w+)\s*="],
            "functions": [
                r"function\s+(\w+)",
                r"const\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>",
                r"export\s+const\s+(\w+)\s*="
            ]
        },
        "go": {
            "imports": [
                r"import\s+\(\s*([^)]+)\s*\)",
                r"import\s+['\"]([^'\"]+)['\"]"
            ],
            "classes": [r"type\s+(\w+)\s+struct", r"type\s+(\w+)\s+interface"],
            "functions": [
                r"func\s+(\w+)\s*\(",
                r"func\s*\([^)]*\)\s*(\w+)\s*\("
            ]
        },
        "java": {
            "imports": [r"import\s+([\w.]+);"],
            "classes": [r"class\s+(\w+)", r"interface\s+(\w+)", r"enum\s+(\w+)"],
            "functions": [r"(?:public|protected|private|static|\s)+[\w<>]+\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+[\w, ]+)?\s*\{"]
        },
        "csharp": {
            "imports": [r"using\s+([\w.]+);"],
            "classes": [r"class\s+(\w+)", r"interface\s+(\w+)", r"struct\s+(\w+)"],
            "functions": [r"(?:public|protected|private|static|internal|\s)+[\w<>]+\s+(\w+)\s*\([^)]*\)\s*(?:\{|=>)"]
        },
        "php": {
            "imports": [r"use\s+([\w\\]+);", r"(?:require|include)(?:_once)?\s*\(?['\"]([^'\"]+)['\"]"],
            "classes": [r"class\s+(\w+)", r"interface\s+(\w+)", r"trait\s+(\w+)"],
            "functions": [r"function\s+(\w+)"]
        },
        "ruby": {
            "imports": [r"require\s+['\"]([^'\"]+)['\"]", r"require_relative\s+['\"]([^'\"]+)['\"]"],
            "classes": [r"class\s+(\w+)", r"module\s+(\w+)"],
            "functions": [r"def\s+(\w+)"]
        }
    }
    
    lang_patterns = patterns.get(language)
    if not lang_patterns:
        return symbols, imports
        
    in_multiline_import_go = False
    
    for idx, line in enumerate(lines, start=1):
        line_strip = line.strip()
        
        # Handle Go multi-line import block
        if language == "go":
            if line_strip.startswith("import ("):
                in_multiline_import_go = True
                continue
            elif in_multiline_import_go and line_strip.startswith(")"):
                in_multiline_import_go = False
                continue
            elif in_multiline_import_go:
                # Extract quoted import path
                m = re.search(r'["\']([^"\']+)["\']', line_strip)
                if m:
                    imports.append(m.group(1))
                continue

        # Check imports
        for pat in lang_patterns["imports"]:
            m = re.search(pat, line)
            if m:
                imports.append(m.group(1).strip())
                
        # Check classes
        for pat in lang_patterns["classes"]:
            m = re.search(pat, line)
            if m:
                symbols.append(Symbol(
                    name=m.group(1),
                    symbol_type="class",
                    line=idx,
                    source=file_rel_path
                ))
                
        # Check functions/methods
        for pat in lang_patterns["functions"]:
            m = re.search(pat, line)
            if m:
                symbols.append(Symbol(
                    name=m.group(1),
                    symbol_type="function",
                    line=idx,
                    source=file_rel_path
                ))
                
    return symbols, imports

def parse_file(file_path: Path, repo_root: Path, cache_mgr: Optional[CacheManager] = None) -> FileAnalysis:
    """
    Parse a file. Uses cached results if available and up to date.
    """
    abs_path = file_path.resolve()
    rel_path = str(abs_path.relative_to(repo_root.resolve())).replace("\\", "/")
    
    try:
        stat = abs_path.stat()
        size = stat.st_size
        mtime = stat.st_mtime
    except OSError:
        return FileAnalysis(path=rel_path, language="unknown", size=0, mtime=0.0)

    # Check cache
    if cache_mgr:
        cached = cache_mgr.get_cached_file(rel_path, size, mtime)
        if cached:
            return cached

    # Determine language
    lang = get_language(abs_path) or "unknown"
    symbols: List[Symbol] = []
    imports: List[str] = []

    if lang != "unknown":
        try:
            content = abs_path.read_text(encoding="utf-8", errors="ignore")
            if lang == "python":
                symbols, imports = parse_python_file(content, rel_path)
            else:
                symbols, imports = parse_regex_file(content, lang, rel_path)
        except Exception:
            pass

    analysis = FileAnalysis(
        path=rel_path,
        language=lang,
        size=size,
        mtime=mtime,
        symbols=symbols,
        imports=imports
    )

    # Save cache
    if cache_mgr:
        cache_mgr.save_file_analysis(rel_path, analysis)

    return analysis
