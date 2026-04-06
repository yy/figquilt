from pathlib import Path
from typing import Any
import yaml
from pydantic import ValidationError
from .layout import Layout, iter_layout_leaves
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


def parse_layout(layout_path: Path, *, validate_assets: bool = True) -> Layout:
    """Parse a layout file into a Layout model.

    Args:
        layout_path: Path to the YAML/JSON layout file.
        validate_assets: When True, referenced asset files must already exist.
            Watch mode uses False so it can still track missing assets.
    """
    if not layout_path.exists():
        raise LayoutError(f"Layout file not found: {layout_path}")

    try:
        content = layout_path.read_text()
    except (OSError, UnicodeDecodeError) as e:
        raise LayoutError(f"Failed to read layout file: {layout_path}: {e}") from e

    try:
        data, line_map = _parse_yaml_with_lines(content)
    except yaml.YAMLError as e:
        raise LayoutError(f"Failed to parse YAML: {e}") from e

    if data is None:
        raise LayoutError("Layout file is empty")
    if not isinstance(data, dict):
        raise LayoutError(
            f"Layout root must be a mapping/object, got {type(data).__name__}"
        )

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

    if layout.panels is not None:
        for panel in layout.panels:
            panel.file = _resolve_asset_path(
                panel.id,
                panel.file,
                base_dir,
                validate_exists=validate_assets,
            )
    elif layout.layout is not None:
        for leaf in iter_layout_leaves(layout.layout):
            if leaf.id is None or leaf.file is None:
                raise LayoutError("Leaf node must define both 'id' and 'file'")
            leaf.file = _resolve_asset_path(
                leaf.id,
                leaf.file,
                base_dir,
                validate_exists=validate_assets,
            )

    return layout


def _resolve_asset_path(
    panel_id: str,
    file_path: Path,
    base_dir: Path,
    *,
    validate_exists: bool = True,
) -> Path:
    """Resolve an asset path relative to the layout file."""
    resolved = file_path if file_path.is_absolute() else base_dir / file_path
    if validate_exists and not resolved.exists():
        raise AssetMissingError(f"Asset for panel '{panel_id}' not found: {resolved}")
    return resolved
