from pathlib import Path
import tomllib


def test_hermes_console_script_is_declared():
    project = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    assert project["project"]["scripts"]["hermes"] == "src.cli:main"
    assert "src*" in project["tool"]["setuptools"]["packages"]["find"]["include"]
