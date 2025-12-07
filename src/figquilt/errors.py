class FigQuiltError(Exception):
    """Base exception for figquilt."""
    pass

class LayoutError(FigQuiltError):
    """Raised when there is an issue with the layout configuration."""
    pass

class AssetMissingError(FigQuiltError):
    """Raised when an input file cannot be found."""
    pass
