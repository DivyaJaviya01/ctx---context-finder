from pathlib import Path
from ctx_finder.models import FileAnalysis, Symbol
from ctx_finder.ranker import rank_files
from ctx_finder.semantic import normalize_tokens, expand_query

def test_normalize_tokens():
    assert normalize_tokens("Fix login bug!") == ["login"]
    assert normalize_tokens("how to create a token") == ["token"]

def test_expand_query():
    expanded = expand_query("Fix login bug")
    assert "login" in expanded
    # "login" expands to "auth" synonyms
    assert "jwt" in expanded
    assert "auth" in expanded
    
    # Verify new synonyms
    expanded_auth = expand_query("authentication")
    assert "auth" in expanded_auth
    assert "jwt" in expanded_auth
    
    expanded_repo = expand_query("repository")
    assert "repo" in expanded_repo

def test_is_test_file():
    from ctx_finder.utils import is_test_file
    assert is_test_file("tests/test_ranker.py") is True
    assert is_test_file("src/ctx_finder/cli.py") is False
    assert is_test_file("auth/test_login.py") is True
    assert is_test_file("test-repo/fastapi/tests/test_tutorial.py") is True

def test_scoring_weights():
    # Setup test file analyses
    analyses = [
        FileAnalysis(
            path="auth/jwt.py",
            language="python",
            size=10,
            mtime=1.0,
            symbols=[Symbol(name="create_token", symbol_type="function", line=2, source="auth/jwt.py")],
            imports=[]
        ),
        FileAnalysis(
            path="tests/test_jwt.py",
            language="python",
            size=10,
            mtime=1.0,
            symbols=[Symbol(name="test_jwt", symbol_type="function", line=2, source="tests/test_jwt.py")],
            imports=[]
        )
    ]
    
    # Query: "jwt"
    results = rank_files(analyses, "jwt")
    
    assert len(results) == 2
    
    # auth/jwt.py matches 'jwt' exactly in filename stem -> +20
    # directory matches 'auth' (expanded synonym of jwt) -> +3
    # symbol 'create_token' has exact token match 'token' (expanded synonym of jwt) -> +15
    # Total score should be 38.0
    r1 = results[0]
    assert r1.file_path == "auth/jwt.py"
    assert r1.score == 38.0
    assert r1.confidence > 0
    assert any("Exact match in filename" in exp for exp in r1.explanations)
    assert any("Match in parent directory" in exp for exp in r1.explanations)
    
    # tests/test_jwt.py matches 'jwt' exactly in filename stem tokens ('test', 'jwt') -> +20
    # matches 'jwt' exactly in symbol 'test_jwt' tokens -> +15
    # test file penalty -> -2
    # Total score: 33.0
    r2 = results[1]
    assert r2.file_path == "tests/test_jwt.py"
    assert r2.score == 33.0
    assert any("Test file penalty" in exp for exp in r2.explanations)

def test_exporter_section_separation():
    from ctx_finder.exporter import format_context_pack
    from ctx_finder.models import ContextPack, MatchResult
    
    pack = ContextPack(
        query="test auth",
        matches=[
            MatchResult(file_path="src/auth.py", score=40.0, confidence=80.0, explanations=["Match"]),
            MatchResult(file_path="tests/test_auth.py", score=30.0, confidence=60.0, explanations=["Test Match"])
        ],
        architecture_signals=[],
        risks=[],
        plan=[],
        conventions=[],
        why_summary="Summary"
    )
    
    output = format_context_pack(pack, "claude")
    assert "#### Core Files" in output
    assert "**src/auth.py**" in output
    assert "#### Related Tests" in output
    assert "**tests/test_auth.py**" in output
