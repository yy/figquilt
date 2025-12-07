from pathlib import Path
import yaml
from .layout import Layout
from .errors import LayoutError, AssetMissingError

def parse_layout(layout_path: Path) -> Layout:
    """Parses a YAML layout file and returns a Layout object."""
    if not layout_path.exists():
        raise LayoutError(f"Layout file not found: {layout_path}")

    try:
        with open(layout_path, 'r') as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise LayoutError(f"Failed to parse YAML: {e}")

    try:
        layout = Layout(**data)
    except Exception as e:
        raise LayoutError(f"Layout validation failed: {e}")

    # Validate assets exist relative to the layout file
    base_dir = layout_path.parent
    for panel in layout.panels:
        # Resolve path relative to layout file if not absolute
        if not panel.file.is_absolute():
            panel.file = base_dir / panel.file
        
        if not panel.file.exists():
            raise AssetMissingError(f"Asset for panel '{panel.id}' not found: {panel.file}")

    return layout
