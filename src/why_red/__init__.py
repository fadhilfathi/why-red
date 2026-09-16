"""why-red: explain why a GitHub Actions run failed."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("why-red")
except PackageNotFoundError:  # pragma: no cover - only when running from a bare checkout
    __version__ = "0.0.0"

__all__ = ["__version__"]
