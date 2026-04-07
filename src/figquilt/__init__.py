from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import tomllib


def _fallback_version() -> str:
    """Read the source-tree version from pyproject.toml when not installed."""
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    try:
        with pyproject_path.open("rb") as fh:
            project = tomllib.load(fh).get("project", {})
    except (OSError, tomllib.TOMLDecodeError):
        return "0.0.0"

    version_value = project.get("version")
    if isinstance(version_value, str) and version_value:
        return version_value
    return "0.0.0"


try:
    __version__ = version("figquilt")
except PackageNotFoundError:
    __version__ = _fallback_version()
