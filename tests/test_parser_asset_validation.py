import yaml

from figquilt.cli import compose_figure
from figquilt.errors import LayoutError
from figquilt.parser import parse_layout


def test_parse_layout_rejects_directory_assets(tmp_path):
    asset_dir = tmp_path / "panel_dir"
    asset_dir.mkdir()

    layout_file = tmp_path / "layout.yaml"
    layout_file.write_text(
        yaml.dump(
            {
                "page": {"width": 100, "height": 100},
                "panels": [
                    {
                        "id": "A",
                        "file": asset_dir.name,
                        "x": 0,
                        "y": 0,
                        "width": 50,
                        "height": 50,
                    }
                ],
            }
        )
    )

    try:
        parse_layout(layout_file)
    except LayoutError as exc:
        assert "is not a file" in str(exc)
    else:
        raise AssertionError("parse_layout unexpectedly accepted a directory asset")


def test_compose_figure_reports_directory_assets_without_renderer_errors(
    tmp_path, capsys
):
    asset_dir = tmp_path / "panel_dir"
    asset_dir.mkdir()

    layout_file = tmp_path / "layout.yaml"
    output_file = tmp_path / "output.pdf"
    layout_file.write_text(
        yaml.dump(
            {
                "page": {"width": 100, "height": 100},
                "panels": [
                    {
                        "id": "A",
                        "file": asset_dir.name,
                        "x": 0,
                        "y": 0,
                        "width": 50,
                        "height": 50,
                    }
                ],
            }
        )
    )

    result = compose_figure(layout_file, output_file, fmt="pdf", verbose=False)
    captured = capsys.readouterr()

    assert result is False
    assert "Error: Asset for panel 'A' is not a file" in captured.err
    assert "Failed to open panel file" not in captured.err
