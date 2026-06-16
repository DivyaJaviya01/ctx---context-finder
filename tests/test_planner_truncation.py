import pytest
from typer.testing import CliRunner
from ctx_finder.cli import app

runner = CliRunner()

def test_plan_steps_truncation(tmp_path):
    # Create 25 dummy python files containing 'helper' in the name
    for i in range(1, 26):
        file_path = tmp_path / f"helper_{i}.py"
        file_path.write_text(f"def help_{i}(): pass")

    # Run the plan command targeting our tmp_path
    result = runner.invoke(app, ["plan", "helper", "-p", str(tmp_path)])

    assert result.exit_code == 0
    assert "Implementation Plan for task: 'helper'" in result.stdout

    # Max visible steps is now 10; step 10 should appear, step 11 should NOT
    assert "10. " in result.stdout
    assert "11. " not in result.stdout

    # Omission message: 25 files - 10 visible = 15 omitted
    assert "additional related files omitted." in result.stdout

    # Header renamed
    assert "Suggested Modification Order:" in result.stdout
