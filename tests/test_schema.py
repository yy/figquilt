"""Tests for JSON schema generation and validation."""

import json
from pathlib import Path

from figquilt.layout import Layout

SCHEMA_PATH = Path(__file__).parent.parent / "schema" / "layout.schema.json"


def test_schema_matches_pydantic_model():
    """The stored JSON schema should match the Pydantic model.

    If this test fails, regenerate the schema by running:
        uv run python -c "from figquilt.layout import Layout; import json; print(json.dumps(Layout.model_json_schema(), indent=2))" > schema/layout.schema.json

    Then manually add the $schema and $id fields at the top.
    """
    # Generate schema from Pydantic model
    generated_schema = Layout.model_json_schema()

    # Load stored schema
    with open(SCHEMA_PATH) as f:
        stored_schema = json.load(f)

    # The stored schema may have extra metadata like $schema and $id
    # which Pydantic doesn't generate. We should compare the core structure.
    # Remove the metadata fields for comparison
    stored_schema_copy = stored_schema.copy()
    stored_schema_copy.pop("$schema", None)
    stored_schema_copy.pop("$id", None)

    # Compare the schemas
    assert stored_schema_copy == generated_schema, (
        "The stored JSON schema is out of sync with the Pydantic models. "
        "Regenerate the schema using: "
        'uv run python -c "from figquilt.layout import Layout; import json; print(json.dumps(Layout.model_json_schema(), indent=2))" > schema/layout.schema.json'
    )


def test_schema_file_exists():
    """The JSON schema file should exist."""
    assert SCHEMA_PATH.exists(), f"Schema file not found at {SCHEMA_PATH}"


def test_schema_has_metadata():
    """The stored schema should have proper JSON Schema metadata."""
    with open(SCHEMA_PATH) as f:
        stored_schema = json.load(f)

    assert "$schema" in stored_schema, "Schema should have a $schema field"
    assert "json-schema.org" in stored_schema["$schema"], (
        "$schema should reference json-schema.org"
    )
