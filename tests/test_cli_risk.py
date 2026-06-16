import pytest
from typer.testing import CliRunner
from ctx_finder.cli import app

runner = CliRunner()

def test_cli_risk_command_high(tmp_path):
    # Create a dummy file to scan and run risk analysis on
    auth_file = tmp_path / "auth.py"
    auth_file.write_text("def login(): pass")
    
    # Run the risk command targeting our tmp_path
    result = runner.invoke(app, ["risk", "modify login method", "-p", str(tmp_path)])
    
    # The output should show the risk evaluation
    assert result.exit_code == 0
    assert "Risk Evaluation for task: 'modify login method'" in result.stdout
    assert "- Risk Level: High" in result.stdout
    assert "Modifying critical infrastructure files:" in result.stdout
    assert "Isolate credential management" in result.stdout

def test_cli_risk_command_low(tmp_path):
    # Create a dummy file that does not match risk keywords
    other_file = tmp_path / "helper.py"
    other_file.write_text("def helper(): pass")
    
    # Run the risk command targeting our tmp_path
    result = runner.invoke(app, ["risk", "do helper things", "-p", str(tmp_path)])
    
    assert result.exit_code == 0
    assert "Risk Evaluation for task: 'do helper things'" in result.stdout
    assert "- Risk Level: Low" in result.stdout
    assert "Standard codebase features targeted." in result.stdout

def test_cli_risk_no_matches(tmp_path):
    # No files exist, so no matches should be found
    result = runner.invoke(app, ["risk", "anything", "-p", str(tmp_path)])
    assert result.exit_code == 0
    assert "No matching files found to evaluate risk." in result.stdout
