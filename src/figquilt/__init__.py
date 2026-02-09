from importlib.metadata import PackageNotFoundError, version


try:
    __version__ = version("figquilt")
except PackageNotFoundError:
    # Fallback for source-tree usage before package installation.
    __version__ = "0.1.10"
