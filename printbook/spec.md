I'd like a Python script that takes an EPUB, produces a nice PDF with Typst, then imposes it for printing.

The script should use inline `uv` metadata (PEP 723 style) to manage Python dependencies.

Typst is installed on the system (CLI available on `PATH`).

Impositioning reference (GPL3):
- https://github.com/sgelb/impositioner
- Use it as a conceptual reference only; do not copy whole functions verbatim.

## CLI

- Standard CLI with good defaults.
- Default behavior should produce an imposed/print-ready PDF.
- Should also be able to emit the intermediate “reading PDF” (pre-imposition) for debugging/inspection.

## EPUB → Typst conversion

- Aggressive conversion tuned for novels.
- Do not aim for full CSS fidelity; assume relatively simple XHTML.
- Prefer to avoid a `pandoc` dependency.
- Handle:
	- spine order
	- headings (chapter titles)
	- paragraphs, emphasis (italic/bold), blockquotes, simple lists
	- images
	- footnotes (see below)

## Typography / layout (Typst)

- Professional, easy-to-read layout with small margins (maximize text area).
- Allow specifying a font; if provided, use a local font file.
- Use Typst’s newer per-character justification/spacing features.
- Table of contents:
	- chapters only
	- no links (this is for print)
- Running headers:
	- current chapter title
	- page number
- Nice chapter headers.

## Footnotes

- Convert EPUB footnotes into real Typst footnotes at the reference point.
- No backlinks.

## Imposition

- Output should be an imposed PDF suitable for printing.
- Signature size should be controllable as “pages per signature” (multiple of 4).
- Choose a good default for pages per signature.

### A5-to-A3 duplex printing mode

Add an imposition option intended for sending A5 pages to a duplex A3 printer.

Interpretation/goal:
- Each logical page is A5.
- Printing is on A3 duplex.
- The folded book is A4, with two A5 “pages” on each A4 half.
- Reading order for one opened A3 side is: top-left, top-right, bottom-left, bottom-right.
- You then turn the bottom page upwards.

This mode will require rotations and page placement to match the above reading order.

