import os
from pathlib import Path
from typing import List, Set
from ctx_finder.models import FileAnalysis
from ctx_finder.cache import CacheManager
from ctx_finder.parser import parse_file

DEFAULT_IGNORE_DIRS: Set[str] = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    "dist",
    "build",
    ".pytest_cache",
}

SUPPORTED_EXTENSIONS: Set[str] = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".go",
    ".java",
    ".cs",
    ".php",
    ".rb"
}

def scan_repository_files(base_path: Path, ignore_dirs: Set[str] = DEFAULT_IGNORE_DIRS) -> List[Path]:
    """
    Recursively scan base_path for supported files.
    Skips ignored directories.
    """
    scanned_files: List[Path] = []
    
    if not base_path.exists():
        return scanned_files
        
    if base_path.is_file():
        if base_path.suffix.lower() in SUPPORTED_EXTENSIONS:
            scanned_files.append(base_path)
        return scanned_files

    for root, dirs, files in os.walk(base_path):
        # Modifying dirs in-place to prevent os.walk from traversing ignored subdirectories
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        
        for file in files:
            file_path = Path(root) / file
            if file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                scanned_files.append(file_path)
                
    return scanned_files

def analyze_repository(base_path: Path, cache_mgr: CacheManager) -> List[FileAnalysis]:
    """
    Scan repository files and parse them using CacheManager for incremental analysis.
    """
    file_paths = scan_repository_files(base_path)
    
    # Calculate current fingerprint
    fingerprint = cache_mgr.compute_fingerprint(file_paths)
    cached_fingerprint = cache_mgr.get_repo_fingerprint()
    
    # Get active relative paths for stale cache purging
    active_rel_paths = []
    for p in file_paths:
        try:
            rel = str(p.resolve().relative_to(base_path.resolve())).replace("\\", "/")
            active_rel_paths.append(rel)
        except ValueError:
            pass

    # Clear stale database entries
    cache_mgr.clear_stale_cache(active_rel_paths)

    # Check if whole repo fingerprint matches
    if cached_fingerprint == fingerprint:
        # Load everything directly from database!
        return cache_mgr.get_all_cached_files()
        
    # Otherwise, check files incrementally
    analyses: List[FileAnalysis] = []
    last_mtime = 0.0
    
    for p in file_paths:
        analysis = parse_file(p, base_path, cache_mgr)
        analyses.append(analysis)
        if analysis.mtime > last_mtime:
            last_mtime = analysis.mtime
            
    # Update repository fingerprint in cache
    cache_mgr.update_repo_fingerprint(fingerprint, len(file_paths), last_mtime)
    
    return analyses

def is_test_file(file_path: str) -> bool:
    """
    Check if the file path belongs to a test file.
    Matches files containing '/test_', 'test_', or 'tests/'.
    """
    path_str = file_path.replace("\\", "/").lower()
    return "/test_" in path_str or "test_" in path_str or "tests/" in path_str
