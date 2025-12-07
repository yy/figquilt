import fitz
from PIL import Image, ImageDraw
import os
from pathlib import Path

ASSET_DIR = Path("examples/assets")
ASSET_DIR.mkdir(parents=True, exist_ok=True)

def create_pdf(name, width_pt, height_pt, color):
    doc = fitz.open()
    page = doc.new_page(width=width_pt, height=height_pt)
    # Inset rect to avoid boundary clipping of the stroke
    rect = fitz.Rect(5, 5, width_pt-5, height_pt-5)
    page.draw_rect(rect, color=color, fill=color)
    # Add text to show orientation
    page.insert_text((10, height_pt/2), f"{name} ({width_pt}x{height_pt})", fontsize=12, color=(0,0,0))
    doc.save(ASSET_DIR / f"{name}.pdf")
    doc.close()
    print(f"Created {name}.pdf")

def create_png(name, width_px, height_px, color):
    img = Image.new("RGB", (width_px, height_px), color=color)
    d = ImageDraw.Draw(img)
    d.text((10, height_px/2), f"{name}", fill=(0,0,0))
    img.save(ASSET_DIR / f"{name}.png")
    print(f"Created {name}.png")

def create_svg(name, width, height, color):
    content = f'''<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
    <rect width="100%" height="100%" fill="{color}"/>
    <text x="10" y="{height/2}" font-family="Arial" font-size="20" fill="black">{name}</text>
    <circle cx="{width}" cy="{height}" r="10" fill="white" />
</svg>'''
    with open(ASSET_DIR / f"{name}.svg", "w") as f:
        f.write(content)
    print(f"Created {name}.svg")

if __name__ == "__main__":
    # Square PDF
    create_pdf("A_square", 100, 100, (0.8, 0.8, 1)) # Light blue
    # Wide PDF (2:1)
    create_pdf("B_wide", 200, 100, (0.8, 1, 0.8)) # Light green
    # Tall PNG (1:2)
    create_png("C_tall", 100, 200, "orange")
    # SVG
    create_svg("D_icon", 100, 100, "pink")
    print("Done generating assets.")
