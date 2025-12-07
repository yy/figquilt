import argparse
import sys
from pathlib import Path
from .parser import parse_layout
from .errors import FigQuiltError

def main():
    parser = argparse.ArgumentParser(description="FigQuilt: Compose figures from multiple panels.")
    parser.add_argument("layout", type=Path, help="Path to layout YAML file")
    parser.add_argument("output", type=Path, help="Path to output file (PDF/SVG/PNG)")
    parser.add_argument("--format", choices=["pdf", "svg", "png"], help="Override output format")
    parser.add_argument("--check", action="store_true", help="Validate layout only")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()

    try:
        layout = parse_layout(args.layout)
        print(f"Layout parsed successfully: {args.layout}")
        print(f"Page size: {layout.page.width}x{layout.page.height} {layout.page.units}")
        print(f"Panels: {len(layout.panels)}")
        
        if args.check:
            sys.exit(0)

        # Determine output format
        suffix = args.output.suffix.lower()
        fmt = args.format or suffix.lstrip('.')
        
        if fmt == 'pdf':
            from .compose_pdf import PDFComposer
            composer = PDFComposer(layout)
            composer.compose(args.output)
            print(f"Successfully created: {args.output}")
        
        elif fmt == 'svg':
            from .compose_svg import SVGComposer
            composer = SVGComposer(layout)
            composer.compose(args.output)
            print(f"Successfully created: {args.output}")
            
        elif fmt == 'png':
            from .compose_pdf import PDFComposer
            composer = PDFComposer(layout)
            doc = composer.build()
            # Rasterize first page
            page = doc[0]
            pix = page.get_pixmap(dpi=layout.page.dpi)
            pix.save(str(args.output))
            doc.close()
            print(f"Successfully created: {args.output}")
            
        else:
            print(f"Unsupported format: {fmt}", file=sys.stderr)
            sys.exit(1)

    except FigQuiltError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
