"""
PDF Inspection Utility
Inspects a PDF to determine whether it is digital/text-based or scanned (image-based).
Prints page count, and character counts & first 500 characters for the first 3 pages.
"""

import sys
from pathlib import Path
import pymupdf


def inspect_pdf(pdf_path: str) -> None:
    path = Path(pdf_path)
    if not path.exists():
        print(f"Error: File not found at '{pdf_path}'")
        sys.exit(1)

    if not path.is_file() or path.suffix.lower() != ".pdf":
        print(f"Error: '{pdf_path}' is not a valid PDF file.")
        sys.exit(1)

    try:
        doc = pymupdf.open(path)
    except Exception as e:
        print(f"Error opening PDF: {e}")
        sys.exit(1)

    total_pages = len(doc)
    print("=" * 60)
    print(f"PDF Inspection: {path.name}")
    print(f"Total Pages: {total_pages}")
    print("=" * 60)

    pages_to_check = min(3, total_pages)
    for page_idx in range(pages_to_check):
        page = doc[page_idx]
        text = page.get_text()
        char_count = len(text.strip())

        print(f"\n--- Page {page_idx + 1} ---")
        print(f"Character Count: {char_count}")

        if char_count == 0:
            print("Status: [NO TEXT DETECTED - Likely Scanned / Image-Only]")
        else:
            print("Status: [TEXT DETECTED]")
            preview = text.strip()[:500]
            print("First 500 Characters Preview:")
            print("-" * 40)
            print(preview)
            print("-" * 40)

    doc.close()
    print("\n" + "=" * 60)
    print("Inspection complete.")
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python src/ingestion/inspect_pdf.py <path_to_pdf>")
        sys.exit(1)

    inspect_pdf(sys.argv[1])
