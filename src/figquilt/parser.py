from pathlib import Path
from typing import Any
import yaml
from pydantic import ValidationError
from .layout import Layout
from .errors import LayoutError, AssetMissingError


def _parse_yaml_with_lines(content: str) -> tuple[Any, dict[tuple, int]]:
    """Parse YAML and return data along with a mapping of paths to line numbers."""
    line_map: dict[tuple, int] = {}

    def build_line_map(node: yaml.Node, path: tuple = ()) -> Any:
        if isinstance(node, yaml.MappingNode):
            result = {}
            for key_node, value_node in node.value:
                key = key_node.value
                line_map[(*path, key)] = value_node.start_mark.line + 1
                result[key] = build_line_map(value_node, (*path, key))
            return result
        elif isinstance(node, yaml.SequenceNode):
            result = []
            for i, item_node in enumerate(node.value):
                line_map[(*path, i)] = item_node.start_mark.line + 1
                result.append(build_line_map(item_node, (*path, i)))
            return result
        else:
            return yaml.safe_load(yaml.serialize(node))

    loader = yaml.SafeLoader(content)
    try:
        root = loader.get_single_node()
        if root is None:
            return None, {}
        data = build_line_map(root)
        return data, line_map
    finally:
        loader.dispose()


def _get_line_for_path(line_map: dict[tuple, int], path_str: str) -> int | None:
    """Convert a Pydantic error path like 'panels.0.y' to a line number."""
    parts: list[str | int] = []
    for part in path_str.split("."):
        if part.isdigit():
            parts.append(int(part))
        else:
            parts.append(part)

    return line_map.get(tuple(parts))


def parse_layout(layout_path: Path) -> Layout:
    """Parses a YAML layout file and returns a Layout object."""
    if not layout_path.exists():
        raise LayoutError(f"Layout file not found: {layout_path}")

    try:
        content = layout_path.read_text()
        data, line_map = _parse_yaml_with_lines(content)
    except yaml.YAMLError as e:
        raise LayoutError(f"Failed to parse YAML: {e}")

    try:
        layout = Layout(**data)
    except ValidationError as e:
        # Try to add line numbers to validation errors
        errors_with_lines = []
        for error in e.errors():
            loc = ".".join(str(p) for p in error["loc"])
            line = _get_line_for_path(line_map, loc)
            msg = error["msg"]
            if line:
                errors_with_lines.append(f"  {loc} (line {line}): {msg}")
            else:
                errors_with_lines.append(f"  {loc}: {msg}")
        raise LayoutError("Layout validation failed:\n" + "\n".join(errors_with_lines))
    except Exception as e:
        raise LayoutError(f"Layout validation failed: {e}")

    # Validate assets exist relative to the layout file
    base_dir = layout_path.parent

    if layout.panels:
        # Legacy mode: iterate over explicit panels
        for panel in layout.panels:
            if not panel.file.is_absolute():
                panel.file = base_dir / panel.file
            if not panel.file.exists():
                raise AssetMissingError(
                    f"Asset for panel '{panel.id}' not found: {panel.file}"
                )
    elif layout.layout:
        # Grid mode: recursively validate assets in the layout tree
        _validate_layout_assets(layout.layout, base_dir)

    return layout


def _validate_layout_assets(node, base_dir: Path) -> None:
    """Recursively validate and resolve asset paths in a layout tree."""
    if node.is_container():
        for child in node.children:
            _validate_layout_assets(child, base_dir)
    else:
        # Leaf node: validate file exists
        if not node.file.is_absolute():
            node.file = base_dir / node.file
        if not node.file.exists():
            raise AssetMissingError(
                f"Asset for panel '{node.id}' not found: {node.file}"
            )
