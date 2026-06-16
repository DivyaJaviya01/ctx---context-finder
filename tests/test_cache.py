import time
from pathlib import Path
from ctx_finder.cache import CacheManager
from ctx_finder.models import FileAnalysis, Symbol

def test_cache_manager_fingerprint(tmp_path):
    mgr = CacheManager(tmp_path)
    
    file1 = tmp_path / "main.py"
    file1.write_text("print('hello')")
    file2 = tmp_path / "utils.py"
    file2.write_text("print('utils')")
    
    fp1 = mgr.compute_fingerprint([file1, file2])
    fp2 = mgr.compute_fingerprint([file1])
    
    assert fp1 != fp2
    
    mgr.update_repo_fingerprint(fp1, 2, time.time())
    assert mgr.get_repo_fingerprint() == fp1

def test_cache_file_retrieval(tmp_path):
    mgr = CacheManager(tmp_path)
    rel_path = "auth/login.py"
    
    # Save dummy file analysis
    symbols = [
        Symbol(name="authenticate", symbol_type="function", line=5, source=rel_path)
    ]
    analysis = FileAnalysis(
        path=rel_path,
        language="python",
        size=123,
        mtime=12345.67,
        symbols=symbols,
        imports=["jwt", "sys"]
    )
    
    mgr.save_file_analysis(rel_path, analysis)
    
    # Retrieve with correct size and mtime
    cached = mgr.get_cached_file(rel_path, 123, 12345.67)
    assert cached is not None
    assert cached.language == "python"
    assert cached.imports == ["jwt", "sys"]
    assert len(cached.symbols) == 1
    assert cached.symbols[0].name == "authenticate"
    
    # Retrieve with mismatching size or mtime -> should be None
    cached_mismatch = mgr.get_cached_file(rel_path, 123, 99999.99)
    assert cached_mismatch is None
