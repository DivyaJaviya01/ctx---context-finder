import pytest
from pathlib import Path
from ctx_finder.models import FileAnalysis, MatchResult, Symbol
from ctx_finder.cli import generate_subsystem_map
from ctx_finder.planner import generate_strategy

def test_generate_subsystem_map_success(tmp_path):
    # Setup files and analyses to simulate Aider context subsystem
    # aider/commands.py imports aider.coders.context_coder
    # context_coder.py imports context_prompts
    # base_coder.py has no direct connection (supporting)
    # test_exceptions.py is a test file
    
    analyses = [
        FileAnalysis(
            path="aider/commands.py",
            language="python",
            size=10,
            mtime=1.0,
            symbols=[Symbol(name="main", symbol_type="function", line=1, source="aider/commands.py")],
            imports=["aider.coders.context_coder"]
        ),
        FileAnalysis(
            path="aider/coders/context_coder.py",
            language="python",
            size=10,
            mtime=1.0,
            symbols=[],
            imports=["context_prompts"]
        ),
        FileAnalysis(
            path="aider/coders/context_prompts.py",
            language="python",
            size=10,
            mtime=1.0,
            symbols=[],
            imports=[]
        ),
        FileAnalysis(
            path="aider/coders/base_coder.py",
            language="python",
            size=10,
            mtime=1.0,
            symbols=[],
            imports=[]
        )
    ]
    
    matches = [
        MatchResult(file_path="aider/commands.py", score=80.0, confidence=90.0, explanations=[]),
        MatchResult(file_path="aider/coders/context_coder.py", score=75.0, confidence=85.0, explanations=[]),
        MatchResult(file_path="aider/coders/context_prompts.py", score=70.0, confidence=80.0, explanations=[]),
        MatchResult(file_path="aider/coders/base_coder.py", score=60.0, confidence=70.0, explanations=[]),
        MatchResult(file_path="tests/basic/test_exceptions.py", score=40.0, confidence=50.0, explanations=[])
    ]
    
    # Write a dummy run file for aider/commands.py so that entry point detection can check content
    commands_file = tmp_path / "aider/commands.py"
    commands_file.parent.mkdir(parents=True, exist_ok=True)
    commands_file.write_text('if __name__ == "__main__":\n    pass')
    
    output = generate_subsystem_map("context", matches, analyses, tmp_path)
    
    assert "Relationship Map for Subsystem: 'context'" in output
    assert "Entry Points:" in output
    assert "aider/commands.py" in output
    assert "Core Flow:" in output
    assert "commands.py" in output
    assert "context_coder.py" in output
    assert "context_prompts.py" in output
    assert "Supporting Components:" in output
    assert "* base_coder.py" in output
    assert "Tests:" in output
    assert "* test_exceptions.py" in output
    assert "Why:" in output
    assert "Found import link from aider/commands.py to aider/coders/context_coder.py." in output

def test_generate_subsystem_map_fallback(tmp_path):
    # Setup analyses with no connections
    analyses = [
        FileAnalysis(path="src/a.py", language="python", size=10, mtime=1.0, symbols=[], imports=[]),
        FileAnalysis(path="src/b.py", language="python", size=10, mtime=1.0, symbols=[], imports=[])
    ]
    matches = [
        MatchResult(file_path="src/a.py", score=80.0, confidence=90.0, explanations=[]),
        MatchResult(file_path="src/b.py", score=75.0, confidence=85.0, explanations=[])
    ]
    
    output = generate_subsystem_map("unknown", matches, analyses, tmp_path)
    assert output == "No direct relationships confidently identified."

def test_generate_strategy_provider_success():
    analyses = [
        FileAnalysis(path="aider/models.py", language="python", size=10, mtime=1.0, symbols=[], imports=[]),
        FileAnalysis(path="aider/openrouter.py", language="python", size=10, mtime=1.0, symbols=[], imports=[])
    ]
    matches = [
        MatchResult(file_path="aider/models.py", score=80.0, confidence=90.0, explanations=[]),
        MatchResult(file_path="aider/openrouter.py", score=75.0, confidence=85.0, explanations=[]),
        MatchResult(file_path="tests/basic/test_models.py", score=50.0, confidence=60.0, explanations=[])
    ]
    
    output = generate_strategy("add provider", matches, analyses)
    
    assert "Existing Systems:" in output
    assert "[+] Provider-related components detected." in output
    assert "Relevant Files:" in output
    assert "* aider/models.py" in output
    assert "Suggested Approach:" in output
    assert "1. Reuse existing provider/model abstractions in aider/models.py." in output
    assert "Risks:" in output
    assert "* Avoid duplicating model connection or API client logic." in output
    assert "Confidence:" in output
    # 55 base + 15 core + 10 test = 80
    assert "80%" in output
    assert "Why:" in output

def test_generate_strategy_fallback():
    analyses = [
        FileAnalysis(path="src/a.py", language="python", size=10, mtime=1.0, symbols=[], imports=[]),
        FileAnalysis(path="src/b.py", language="python", size=10, mtime=1.0, symbols=[], imports=[])
    ]
    matches = [
        MatchResult(file_path="src/a.py", score=80.0, confidence=90.0, explanations=[]),
        MatchResult(file_path="src/b.py", score=75.0, confidence=85.0, explanations=[])
    ]
    
    output = generate_strategy("unknown task", matches, analyses)
    assert "Repository-specific guidance could not be confidently generated." in output
    assert "Confidence:\n50%" in output
    assert "Why:\nNo repository-specific domain components matched with sufficient confidence (minimum 60% required)." in output

def test_cli_options_before_query(tmp_path):
    import subprocess
    import sys
    
    # Create a dummy file
    (tmp_path / "aider").mkdir(exist_ok=True)
    (tmp_path / "aider/models.py").write_text("def load_model(): pass")
    
    # Run the cli script as a subprocess to test sys.argv preprocessing
    result = subprocess.run(
        [sys.executable, "src/ctx_finder/cli.py", "-e", "chatgpt", "provider", "-p", str(tmp_path)],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "Relevant Files" in result.stdout
    assert "aider/models.py" in result.stdout
