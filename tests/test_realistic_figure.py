import pytest
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from pathlib import Path
import yaml
from figquilt.compose_pdf import PDFComposer
from figquilt.parser import parse_layout

@pytest.fixture
def realistic_assets(tmp_path):
    # Set style for professional look
    sns.set_theme(style="whitegrid")

    # 1. Scatter Plot (PDF)
    df_scatter = pd.DataFrame({
        'x': np.random.randn(100),
        'y': np.random.randn(100),
        'category': np.random.choice(['A', 'B'], 100)
    })
    plt.figure(figsize=(4, 3))
    sns.scatterplot(data=df_scatter, x='x', y='y', hue='category')
    plt.title("Random Scatter")
    plt.tight_layout()
    path_scatter = tmp_path / "scatter.pdf"
    plt.savefig(path_scatter)
    plt.close()

    # 2. Line Plot (PDF)
    df_line = pd.DataFrame({
        'time': np.arange(50),
        'value': np.sin(np.arange(50) * 0.2) + np.random.normal(0, 0.1, 50)
    })
    plt.figure(figsize=(4, 3))
    sns.lineplot(data=df_line, x='time', y='value')
    plt.title("Time Series")
    plt.tight_layout()
    path_line = tmp_path / "line.pdf"
    plt.savefig(path_line)
    plt.close()

    # 3. Heatmap (PNG) - often raster is better for dense heatmaps
    data_heatmap = np.random.rand(10, 12)
    plt.figure(figsize=(5, 4))
    sns.heatmap(data_heatmap, cmap="viridis")
    plt.title("Correlation Matrix")
    plt.tight_layout()
    path_heatmap = tmp_path / "heatmap.png"
    plt.savefig(path_heatmap, dpi=300)
    plt.close()

    return path_scatter, path_line, path_heatmap

def test_realistic_composition(tmp_path, realistic_assets):
    path_scatter, path_line, path_heatmap = realistic_assets

    # Define a layout that mimics a real figure (e.g. 2 columns)
    # Page A4 width is approx 210mm. Let's make a figure that fits in A4 width.
    # Top row: Scatter and Line
    # Bottom row: Heatmap spanning full width (or centered)

    layout_data = {
        "page": {
            "width": 180,  # mm (approx full width for journals)
            "height": 150,  # mm
            "units": "mm"
        },
        "panels": [
            {
                "id": "A",
                "file": str(path_scatter),
                "x": 0,
                "y": 0,
                "width": 85,
                "label": "a", # Custom text
                "label_style": {
                    "font_size_pt": 12.0,
                    "bold": True
                }
            },
            {
                "id": "B",
                "file": str(path_line),
                "x": 95, # 10mm gap
                "y": 0,
                "width": 85
            },
            {
                "id": "C",
                "file": str(path_heatmap),
                "x": 45, # Centered (180 - 90)/2
                "y": 70,
                "width": 90
            }
        ]
    }

    layout_file = tmp_path / "figure1_layout.yaml"
    with open(layout_file, "w") as f:
        yaml.dump(layout_data, f)

    layout = parse_layout(layout_file)

    out_pdf = tmp_path / "figure1.pdf"
    composer = PDFComposer(layout)
    composer.compose(out_pdf)

    assert out_pdf.exists()
    assert out_pdf.stat().st_size > 0

    # We could inspect the PDF content if needed, but existence is a good start.
