from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import tomllib


def _version_from_pyproject() -> str:
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = data.get("project")
    if not isinstance(project, dict):
        raise KeyError("project")

    project_version = project["version"]
    if not isinstance(project_version, str):
        raise TypeError("project.version")

    return project_version


try:
    __version__ = version("steammetadatatool")
except PackageNotFoundError:
    __version__ = _version_from_pyproject()

__all__ = ["__version__", "core"]
