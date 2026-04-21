from pathlib import Path
from typing import Any
import yaml
from yaml.constructor import ConstructorError
from pydantic import ValidationError
from .layout import Layout, iter_panels
from .errors import LayoutError, AssetMissingError

LocationPath = tuple[str | int, ...]


def _parse_yaml_with_lines(content: str) -> tuple[Any, dict[LocationPath, int]]:
    """Parse YAML and return data along with a mapping of paths to line numbers."""
    line_map: dict[LocationPath, int] = {}

    def build_line_map(node: yaml.Node, path: LocationPath = ()) -> Any:
        if isinstance(node, yaml.MappingNode):
            result = {}
            seen_keys: set[str] = set()
            for key_node, value_node in node.value:
                key = key_node.value
                if key in seen_keys:
                    raise ConstructorError(
                        "while constructing a mapping",
                        node.start_mark,
                        f"found duplicate key {key!r}",
                        key_node.start_mark,
                    )
                seen_keys.add(key)
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


def _get_line_for_location(
    line_map: dict[LocationPath, int], loc: tuple[Any, ...]
) -> int | None:
    """Map a structured Pydantic error location to a YAML line number."""
    path: list[str | int] = []
    for part in loc:
        if isinstance(part, (str, int)):
            path.append(part)
            continue
        return None
    return line_map.get(tuple(path))


def _format_validation_errors(
    error: ValidationError, line_map: dict[LocationPath, int]
) -> str:
    """Format Pydantic validation errors, adding YAML line numbers when available."""
    formatted_errors = []
    for details in error.errors():
        loc = details["loc"]
        loc_str = ".".join(str(part) for part in loc)
        line = _get_line_for_location(line_map, loc)
        msg = details["msg"]
        if line:
            formatted_errors.append(f"  {loc_str} (line {line}): {msg}")
        else:
            formatted_errors.append(f"  {loc_str}: {msg}")
    return "Layout validation failed:\n" + "\n".join(formatted_errors)


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
        raise LayoutError(_format_validation_errors(e, line_map)) from e
    except Exception as e:
        raise LayoutError(f"Layout validation failed: {e}")

    # Validate assets exist relative to the layout file
    base_dir = layout_path.parent

    for panel in iter_panels(layout):
        if panel.id is None or panel.file is None:
            raise LayoutError("Leaf node must define both 'id' and 'file'")
        panel.file = _resolve_asset_path(
            panel.id,
            panel.file,
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
    if validate_exists:
        if not resolved.exists():
            raise AssetMissingError(
                f"Asset for panel '{panel_id}' not found: {resolved}"
            )
        if not resolved.is_file():
            raise LayoutError(f"Asset for panel '{panel_id}' is not a file: {resolved}")
    return resolved
