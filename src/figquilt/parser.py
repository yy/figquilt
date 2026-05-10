from pathlib import Path
from typing import Any
import yaml
from yaml.constructor import ConstructorError
from pydantic import ValidationError
from .layout import Layout, iter_panels
from .errors import LayoutError, AssetMissingError

LocationPath = tuple[str | int, ...]
ROOT_LAYOUT_KEYS = {"page", "panels", "layout"}
YAML_MERGE_TAG = "tag:yaml.org,2002:merge"


def _collect_merge_source_node_ids(node: yaml.Node) -> set[int]:
    """Return node IDs referenced by YAML merge keys beneath this node."""
    merge_sources: set[int] = set()

    def visit(current: yaml.Node) -> None:
        if isinstance(current, yaml.MappingNode):
            for key_node, value_node in current.value:
                if key_node.tag == YAML_MERGE_TAG or key_node.value == "<<":
                    if isinstance(value_node, yaml.SequenceNode):
                        merge_sources.update(
                            id(item_node) for item_node in value_node.value
                        )
                    else:
                        merge_sources.add(id(value_node))
                    continue
                visit(value_node)
            return

        if isinstance(current, yaml.SequenceNode):
            for item_node in current.value:
                visit(item_node)

    visit(node)
    return merge_sources


def _top_level_merge_helper_keys(root: yaml.Node) -> set[str]:
    """Return root keys that only exist to provide YAML merge defaults."""
    if not isinstance(root, yaml.MappingNode):
        return set()

    merge_source_ids = _collect_merge_source_node_ids(root)
    helper_keys: set[str] = set()
    for key_node, value_node in root.value:
        key = key_node.value
        if key not in ROOT_LAYOUT_KEYS and id(value_node) in merge_source_ids:
            helper_keys.add(key)
    return helper_keys


def _parse_yaml_with_lines(content: str) -> tuple[Any, dict[LocationPath, int]]:
    """Parse YAML and return data along with a mapping of paths to line numbers."""
    line_map: dict[LocationPath, int] = {}

    def build_line_map(node: yaml.Node, path: LocationPath = ()) -> Any:
        if isinstance(node, yaml.MappingNode):
            result = {}
            seen_keys: set[str] = set()
            for key_node, value_node in node.value:
                key = key_node.value
                if key == "<<":
                    continue
                if key in seen_keys:
                    raise ConstructorError(
                        "while constructing a mapping",
                        node.start_mark,
                        f"found duplicate key {key!r}",
                        key_node.start_mark,
                    )
                seen_keys.add(key)

            loader.flatten_mapping(node)
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
        merge_helper_keys = _top_level_merge_helper_keys(root)
        data = build_line_map(root)
        if isinstance(data, dict):
            for key in merge_helper_keys:
                data.pop(key, None)
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

    _resolve_layout_asset_paths(
        layout,
        base_dir=layout_path.parent,
        validate_exists=validate_assets,
    )

    return layout


def _resolve_layout_asset_paths(
    layout: Layout,
    base_dir: Path,
    *,
    validate_exists: bool,
) -> None:
    """Resolve every declared panel asset relative to the layout file."""
    for panel in iter_panels(layout):
        if panel.id is None or panel.file is None:
            raise LayoutError("Leaf node must define both 'id' and 'file'")
        panel.file = _resolve_asset_path(
            panel.id,
            panel.file,
            base_dir,
            validate_exists=validate_exists,
        )


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
