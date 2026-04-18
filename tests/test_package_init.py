import subprocess
from pathlib import Path
import sys
import tomllib

from figquilt import _fallback_version


def test_fallback_version_matches_pyproject():
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject_path.open("rb") as fh:
        expected_version = tomllib.load(fh)["project"]["version"]

    assert _fallback_version() == expected_version


def test_package_runs_via_python_module_flag():
    result = subprocess.run(
        [sys.executable, "-m", "figquilt", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "FigQuilt: Compose figures from multiple panels." in result.stdout
