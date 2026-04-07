from pathlib import Path
import tomllib

from figquilt import _fallback_version


def test_fallback_version_matches_pyproject():
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject_path.open("rb") as fh:
        expected_version = tomllib.load(fh)["project"]["version"]

    assert _fallback_version() == expected_version
