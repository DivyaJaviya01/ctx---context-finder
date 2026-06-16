from ctx_finder.models import FileAnalysis
from ctx_finder.architecture import detect_architecture, detect_constraints, detect_file_entry_point

def test_detect_architecture_mvc():
    analyses = [
        FileAnalysis(path="controllers/user_controller.py", language="python", size=10, mtime=1.0),
        FileAnalysis(path="views/user_view.py", language="python", size=10, mtime=1.0),
        FileAnalysis(path="models/user_model.py", language="python", size=10, mtime=1.0),
    ]
    signals = detect_architecture(analyses)
    mvc_signals = [s for s in signals if s.pattern_name == "MVC Pattern"]
    assert len(mvc_signals) == 1
    assert mvc_signals[0].confidence >= 60.0

def test_detect_architecture_service():
    analyses = [
        FileAnalysis(path="services/user_service.py", language="python", size=10, mtime=1.0),
        FileAnalysis(path="repositories/user_repo.py", language="python", size=10, mtime=1.0),
    ]
    signals = detect_architecture(analyses)
    svc_signals = [s for s in signals if s.pattern_name == "Service Layer Pattern"]
    assert len(svc_signals) == 1
    assert svc_signals[0].confidence >= 60.0

def test_detect_constraints():
    analyses = [
        FileAnalysis(path="utils/jwt_token.py", language="python", size=10, mtime=1.0),
        FileAnalysis(path="services/aws_s3_storage.py", language="python", size=10, mtime=1.0),
        FileAnalysis(path="utils/smtp_mailer.py", language="python", size=10, mtime=1.0),
    ]
    constraints = detect_constraints(analyses)
    assert "Token System" in constraints
    assert "Storage System" in constraints
    assert "Email System" in constraints
    assert constraints["Token System"][0] == "utils/jwt_token.py"

def test_detect_file_entry_point(tmp_path):
    from pathlib import Path
    from ctx_finder.architecture import detect_file_entry_point
    from ctx_finder.models import Symbol, FileAnalysis
    
    # 1. Test symbol signals: contains main
    analysis_main = FileAnalysis(
        path="main_script.py",
        language="python",
        size=10,
        mtime=1.0,
        symbols=[Symbol(name="main", symbol_type="function", line=1, source="main_script.py")],
        imports=[]
    )
    result = detect_file_entry_point(analysis_main, tmp_path)
    assert result is not None
    assert result[0] >= 40.0
    assert "main() function" in result[1]
    
    # 2. Test symbol signals: contains cmd_
    analysis_cmd = FileAnalysis(
        path="commands.py",
        language="python",
        size=10,
        mtime=1.0,
        symbols=[Symbol(name="cmd_run", symbol_type="function", line=1, source="commands.py")],
        imports=[]
    )
    result_cmd = detect_file_entry_point(analysis_cmd, tmp_path)
    assert result_cmd is not None
    assert "command registration and dispatch logic" in result_cmd[1]
    
    # 3. Test content signals: contains __main__ block
    script_path = tmp_path / "run.py"
    script_path.write_text('if __name__ == "__main__":\n    pass')
    
    analysis_content = FileAnalysis(
        path="run.py",
        language="python",
        size=10,
        mtime=1.0,
        symbols=[],
        imports=[]
    )
    result_content = detect_file_entry_point(analysis_content, tmp_path)
    assert result_content is not None
    assert "__main__ execution block" in result_content[1]
