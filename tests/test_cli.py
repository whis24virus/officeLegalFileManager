import pytest
from click.testing import CliRunner
from cli import cli

def test_cli_stats(clean_db):
    runner = CliRunner()
    result = runner.invoke(cli, ["stats"])
    
    assert result.exit_code == 0
    assert "System Statistics" in result.output
    # Since clean_db ran, there should be 0 documents
    assert "0" in result.output

def test_cli_add_department(clean_db):
    runner = CliRunner()
    result = runner.invoke(cli, ["add-department", "Engineering"])
    
    assert result.exit_code == 0
    assert "created successfully" in result.output
    
    # Check that it's in the DB
    from app.database import get_all_departments
    depts = get_all_departments()
    assert "Engineering" in depts

def test_cli_add_department_duplicate(clean_db):
    runner = CliRunner()
    # "Legal" is already in the defaults
    result = runner.invoke(cli, ["add-department", "Legal"])
    
    # Depends on how the CLI handles it, but shouldn't crash
    assert result.exit_code == 0
    assert "already exists" in result.output.lower() or "exists" in result.output.lower()
