import sqlite3
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from ctx_finder.models import Symbol, FileAnalysis

class CacheManager:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root.resolve()
        # Store cache db in the repository root directory
        self.db_path = self.repo_root / ".ctx_cache.db"
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS repo_metadata (
                    repo_root TEXT PRIMARY KEY,
                    fingerprint TEXT,
                    file_count INTEGER,
                    last_mtime REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    path TEXT PRIMARY KEY,
                    language TEXT,
                    size INTEGER,
                    mtime REAL,
                    imports TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS symbols (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT,
                    name TEXT,
                    symbol_type TEXT,
                    line INTEGER,
                    FOREIGN KEY (file_path) REFERENCES files(path) ON DELETE CASCADE
                )
            """)
            conn.commit()

    def compute_fingerprint(self, file_paths: List[Path]) -> str:
        """
        Compute a fingerprint hash based on repo root, file paths, file count, and latest mtime.
        """
        if not file_paths:
            raw_str = f"{self.repo_root}|empty|0|0"
            return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

        rel_paths = sorted([str(p.relative_to(self.repo_root)).replace("\\", "/") for p in file_paths])
        
        # Collect mtimes and counts
        mtimes = []
        for p in file_paths:
            try:
                mtimes.append(p.stat().st_mtime)
            except OSError:
                mtimes.append(0.0)
                
        max_mtime = max(mtimes) if mtimes else 0.0
        file_count = len(file_paths)
        
        raw_str = f"{self.repo_root}|{','.join(rel_paths)}|{file_count}|{max_mtime}"
        return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

    def get_repo_fingerprint(self) -> Optional[str]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT fingerprint FROM repo_metadata WHERE repo_root = ?",
                (str(self.repo_root),)
            ).fetchone()
            return row["fingerprint"] if row else None

    def update_repo_fingerprint(self, fingerprint: str, file_count: int, last_mtime: float):
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO repo_metadata (repo_root, fingerprint, file_count, last_mtime)
                VALUES (?, ?, ?, ?)
                """,
                (str(self.repo_root), fingerprint, file_count, last_mtime)
            )
            conn.commit()

    def get_cached_file(self, rel_path: str, current_size: int, current_mtime: float) -> Optional[FileAnalysis]:
        """
        Get cached FileAnalysis if the file size and mtime match.
        """
        path_str = str(rel_path).replace("\\", "/")
        with self._get_connection() as conn:
            # Check if file row exists with matching size and mtime
            file_row = conn.execute(
                "SELECT * FROM files WHERE path = ? AND size = ? AND mtime = ?",
                (path_str, current_size, current_mtime)
            ).fetchone()
            
            if not file_row:
                return None
                
            # Load symbols
            symbol_rows = conn.execute(
                "SELECT name, symbol_type, line FROM symbols WHERE file_path = ?",
                (path_str,)
            ).fetchall()
            
            symbols = [
                Symbol(
                    name=s["name"],
                    symbol_type=s["symbol_type"],
                    line=s["line"],
                    source=path_str
                )
                for s in symbol_rows
            ]
            
            # Parse imports
            try:
                imports = json.loads(file_row["imports"])
            except Exception:
                imports = []
                
            return FileAnalysis(
                path=path_str,
                language=file_row["language"],
                size=file_row["size"],
                mtime=file_row["mtime"],
                symbols=symbols,
                imports=imports
            )

    def save_file_analysis(self, rel_path: str, analysis: FileAnalysis):
        """
        Cache file analysis and its symbols.
        """
        path_str = str(rel_path).replace("\\", "/")
        with self._get_connection() as conn:
            # Delete old symbols and file row
            conn.execute("DELETE FROM symbols WHERE file_path = ?", (path_str,))
            
            # Save file metadata
            conn.execute(
                """
                INSERT OR REPLACE INTO files (path, language, size, mtime, imports)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    path_str,
                    analysis.language,
                    analysis.size,
                    analysis.mtime,
                    json.dumps(analysis.imports)
                )
            )
            
            # Save symbols
            for sym in analysis.symbols:
                conn.execute(
                    """
                    INSERT INTO symbols (file_path, name, symbol_type, line)
                    VALUES (?, ?, ?, ?)
                    """,
                    (path_str, sym.name, sym.symbol_type, sym.line)
                )
            conn.commit()

    def get_all_cached_files(self) -> List[FileAnalysis]:
        """
        Return all cached FileAnalysis records.
        """
        analyses = []
        with self._get_connection() as conn:
            file_rows = conn.execute("SELECT * FROM files").fetchall()
            for r in file_rows:
                path_str = r["path"]
                symbol_rows = conn.execute(
                    "SELECT name, symbol_type, line FROM symbols WHERE file_path = ?",
                    (path_str,)
                ).fetchall()
                
                symbols = [
                    Symbol(
                        name=s["name"],
                        symbol_type=s["symbol_type"],
                        line=s["line"],
                        source=path_str
                    )
                    for s in symbol_rows
                ]
                
                try:
                    imports = json.loads(r["imports"])
                except Exception:
                    imports = []
                    
                analyses.append(
                    FileAnalysis(
                        path=path_str,
                        language=r["language"],
                        size=r["size"],
                        mtime=r["mtime"],
                        symbols=symbols,
                        imports=imports
                    )
                )
        return analyses

    def clear_stale_cache(self, active_rel_paths: List[str]):
        """
        Remove files from cache that are no longer in the repository.
        """
        normalized_paths = [p.replace("\\", "/") for p in active_rel_paths]
        with self._get_connection() as conn:
            # Find stale files
            placeholders = ",".join("?" for _ in normalized_paths)
            if placeholders:
                conn.execute(
                    f"DELETE FROM files WHERE path NOT IN ({placeholders})",
                    normalized_paths
                )
            else:
                conn.execute("DELETE FROM files")
            conn.commit()
