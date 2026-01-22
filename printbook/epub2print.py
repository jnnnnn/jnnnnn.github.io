#!uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fonttools",
#     "lxml",
#     "pillow",
#     "pypdf",
# ]
# ///
"""
EPUB to print-ready PDF converter.

Converts an EPUB to Typst, renders to PDF, then imposes for booklet printing.

# Basic conversion with imposition
uv run epub2print.py mybook.epub

# Save reading PDF for inspection
uv run epub2print.py mybook.epub --reading-pdf reading.pdf

# No imposition (just Typst-rendered PDF)
uv run epub2print.py mybook.epub --no-impose

# A3 duplex mode
uv run epub2print.py mybook.epub --a3-mode

# Custom font and page size
uv run epub2print.py mybook.epub --font ./MyFont.ttf --page-size a4

# Exclude high-ink images (e.g., dark photos that waste printer ink)
uv run epub2print.py mybook.epub --max-ink 0.3
"""

import argparse
import re
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from fontTools import ttLib
from lxml import etree
from pypdf import PdfReader, PdfWriter, PageObject, Transformation


# Namespaces used in EPUB/XHTML
NAMESPACES = {
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
    "ncx": "http://www.daisy.org/z3986/2005/ncx/",
    "epub": "http://www.idpf.org/2007/ops",
    "xhtml": "http://www.w3.org/1999/xhtml",
    "container": "urn:oasis:names:tc:opendocument:xmlns:container",
}


@dataclass
class Chapter:
    """Represents a chapter extracted from EPUB."""
    title: str
    content: str  # Typst content
    images: dict[str, bytes] = field(default_factory=dict)


@dataclass
class Book:
    """Represents an entire book."""
    title: str
    author: str
    chapters: list[Chapter]
    images: dict[str, bytes] = field(default_factory=dict)


class EPUBParser:
    """Parses EPUB files and extracts content."""

    def __init__(self, epub_path: Path, max_ink: float | None = None):
        self.epub_path = epub_path
        self.zip = zipfile.ZipFile(epub_path, "r")
        self.opf_path: str = ""
        self.opf_dir: str = ""
        self.footnotes: dict[str, str] = {}  # id -> footnote content
        self.max_ink = max_ink  # Maximum ink coverage (0.0-1.0) for images, None = no limit

    def _calculate_ink_coverage(self, img_data: bytes) -> float:
        """Calculate the ink coverage of an image (0.0 = white, 1.0 = black).
        
        Uses the average darkness of pixels as a proxy for ink usage.
        """
        try:
            from PIL import Image
            import io
            
            img = Image.open(io.BytesIO(img_data))
            # Convert to grayscale
            gray = img.convert("L")
            # Get pixel data
            pixels = list(gray.get_flattened_data())
            # Calculate average darkness (0=black, 255=white)
            # Invert so 0=white, 1=black (ink coverage)
            avg_brightness = sum(pixels) / len(pixels)
            ink_coverage = 1.0 - (avg_brightness / 255.0)
            return ink_coverage
        except Exception:
            # If we can't analyze the image, assume it's okay to include
            return 0.0

    def parse(self) -> Book:
        """Parse the EPUB and return a Book object."""
        container_xml = self.zip.read("META-INF/container.xml")
        container = etree.fromstring(container_xml)
        rootfile = container.find(
            ".//container:rootfile", namespaces=NAMESPACES
        )
        self.opf_path = rootfile.get("full-path")
        self.opf_dir = str(Path(self.opf_path).parent)
        if self.opf_dir == ".":
            self.opf_dir = ""

        opf_xml = self.zip.read(self.opf_path)
        opf = etree.fromstring(opf_xml)

        # Extract metadata
        title = self._get_metadata(opf, "title") or "Untitled"
        author = self._get_metadata(opf, "creator") or "Unknown Author"

        # Get spine order
        spine = opf.find("opf:spine", namespaces=NAMESPACES)
        manifest = opf.find("opf:manifest", namespaces=NAMESPACES)

        # Build id -> href mapping from manifest
        id_to_href = {}
        id_to_media = {}
        for item in manifest.findall("opf:item", namespaces=NAMESPACES):
            item_id = item.get("id")
            href = item.get("href")
            media = item.get("media-type", "")
            id_to_href[item_id] = href
            id_to_media[item_id] = media

        # First pass: collect all footnotes from ALL files in the EPUB
        # (including dedicated footnote files that may not be in spine)
        self._collect_all_footnotes()
        
        spine_items = []
        for itemref in spine.findall("opf:itemref", namespaces=NAMESPACES):
            idref = itemref.get("idref")
            href = id_to_href.get(idref)
            if href:
                spine_items.append(href)

        # Filter out footnote-only files from main content
        content_items = [h for h in spine_items if "footnote" not in h.lower()]
        
        # Filter out TOC/navigation files (files that are mostly links to chapters)
        content_items = [h for h in content_items if not self._is_toc_file(h)]

        # Second pass: parse chapters
        chapters = []
        images = {}
        for href in content_items:
            chapter, chapter_images = self._parse_document(href)
            if chapter and chapter.content.strip():
                chapters.append(chapter)
                images.update(chapter_images)

        return Book(title=title, author=author, chapters=chapters, images=images)

    def _get_metadata(self, opf: etree._Element, name: str) -> str | None:
        """Extract metadata from OPF."""
        elem = opf.find(f".//dc:{name}", namespaces=NAMESPACES)
        return elem.text if elem is not None else None

    def _resolve_path(self, href: str) -> str:
        """Resolve a path relative to the OPF directory."""
        if self.opf_dir:
            return f"{self.opf_dir}/{href}"
        return href

    def _is_toc_file(self, href: str) -> bool:
        """Check if a file is a table of contents / navigation file.
        
        TOC files are characterized by having multiple chapter-heading-like
        paragraphs that are all links to other files.
        """
        full_path = self._resolve_path(href)
        try:
            content = self.zip.read(full_path)
            doc = etree.fromstring(content)
        except (KeyError, etree.XMLSyntaxError):
            return False
        
        body = doc.find(".//{http://www.w3.org/1999/xhtml}body")
        if body is None:
            return False
        
        # Count chapter-like link entries vs total paragraphs
        chapter_links = 0
        total_paragraphs = 0
        
        for p in body.iter("{http://www.w3.org/1999/xhtml}p"):
            text = self._extract_text(p).strip()
            if not text:
                continue
            total_paragraphs += 1
            
            # Check if this paragraph is a chapter-heading-like link
            if self._is_chapter_heading(text):
                # Check if the paragraph is primarily a link to another file
                for a in p.iter("{http://www.w3.org/1999/xhtml}a"):
                    a_href = a.get("href", "")
                    a_text = self._extract_text(a).strip()
                    # If the link text matches the paragraph and links to another file
                    if a_text == text and a_href and not a_href.startswith("#"):
                        href_file = a_href.split("#")[0] if "#" in a_href else a_href
                        # Link points to a different file (not same file anchor)
                        if href_file and href_file != Path(href).name:
                            chapter_links += 1
                            break
        
        # If more than half the paragraphs are chapter links, it's a TOC
        if total_paragraphs > 0 and chapter_links >= 3 and chapter_links / total_paragraphs > 0.3:
            return True
        
        return False

    def _collect_all_footnotes(self) -> None:
        """Collect all footnotes from the EPUB, including dedicated footnote files."""
        for filename in self.zip.namelist():
            if filename.endswith((".html", ".xhtml")):
                try:
                    content = self.zip.read(filename)
                    self._extract_footnotes_from_content(content, filename)
                except Exception:
                    continue

    def _extract_footnotes_from_content(self, content: bytes, filename: str) -> None:
        """Extract footnotes from HTML content."""
        try:
            doc = etree.fromstring(content)
        except Exception:
            return

        # Get base filename for reference
        base_name = Path(filename).name

        # Look for elements with footnote IDs or classes
        for elem in doc.iter():
            elem_id = elem.get("id", "")
            elem_class = elem.get("class", "")
            epub_type = elem.get("{http://www.idpf.org/2007/ops}type", "")

            # Check if this is a footnote container
            is_footnote = (
                "footnote" in elem_class.lower()
                or "footnote" in epub_type.lower()
                or "endnote" in epub_type.lower()
                or (elem_id and "footnote" in elem_id.lower())
            )

            if is_footnote and elem_id:
                # Extract text, removing the footnote marker (*, †, etc.)
                text = self._extract_text(elem).strip()
                # Remove common footnote markers at start
                text = re.sub(r"^[\*†‡§¶#]+\s*", "", text)
                text = re.sub(r"^\d+\.?\s*", "", text)

                if text:
                    # Store with various key formats for matching
                    self.footnotes[elem_id] = text
                    self.footnotes[f"{base_name}#{elem_id}"] = text
                    # Also store by any internal anchor IDs
                    for anchor in elem.findall(".//{http://www.w3.org/1999/xhtml}a"):
                        anchor_id = anchor.get("id", "")
                        if anchor_id:
                            self.footnotes[anchor_id] = text
                            self.footnotes[f"{base_name}#{anchor_id}"] = text

    def _parse_document(self, href: str) -> tuple[Chapter | None, dict[str, bytes]]:
        """Parse an XHTML document into a Chapter."""
        full_path = self._resolve_path(href)
        try:
            content = self.zip.read(full_path)
        except KeyError:
            return None, {}

        doc = etree.fromstring(content)
        body = doc.find(".//xhtml:body", namespaces=NAMESPACES)
        if body is None:
            body = doc.find(".//{http://www.w3.org/1999/xhtml}body")
        if body is None:
            # Try without namespace
            body = doc.find(".//body")
        if body is None:
            return None, {}

        # Find chapter title
        title = self._find_title(body)

        # Convert body to Typst
        images = {}
        typst_content = self._element_to_typst(body, href, images)

        return Chapter(title=title, content=typst_content), images

    def _find_title(self, body: etree._Element) -> str:
        """Extract chapter title from body."""
        # Look for h1, h2, or elements with heading classes
        for tag in ["h1", "h2", "h3"]:
            for ns in ["{http://www.w3.org/1999/xhtml}", ""]:
                elem = body.find(f".//{ns}{tag}")
                if elem is not None:
                    return self._extract_text(elem).strip()
        
        # Look for chapter patterns in paragraphs (common in Calibre-converted EPUBs)
        for ns in ["{http://www.w3.org/1999/xhtml}", ""]:
            for p in body.findall(f".//{ns}p"):
                text = self._extract_text(p).strip()
                if self._is_chapter_heading(text):
                    return text
        return ""

    def _is_chapter_heading(self, text: str) -> bool:
        """Check if text looks like a chapter heading."""
        if not text:
            return False
        # Chapter headings should be short (typically just the title)
        if len(text) > 50:
            return False
        # Common chapter patterns - must match the ENTIRE text
        patterns = [
            r'^Chapter\s+(\d+|One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|Eleven|Twelve|\w+)$',
            r'^Part\s+(\d+|One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|I+|IV|V|VI+)$',
            r'^Prologue$',
            r'^Epilogue$',
            r'^Introduction$',
            r'^Acknowledgments$',
            r'^About the Author$',
        ]
        for pattern in patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        return False

    def _extract_text(self, elem: etree._Element) -> str:
        """Extract all text from an element."""
        return "".join(elem.itertext())

    def _element_to_typst(
        self, elem: etree._Element, doc_href: str, images: dict[str, bytes]
    ) -> str:
        """Convert an XHTML element to Typst markup."""
        result = []
        self._convert_element(elem, doc_href, images, result, in_paragraph=False)
        return "\n".join(result)

    def _get_local_name(self, elem: etree._Element) -> str:
        """Get the local name of an element (without namespace)."""
        tag = elem.tag
        if isinstance(tag, str) and tag.startswith("{"):
            return tag.split("}", 1)[1]
        return tag if isinstance(tag, str) else ""

    def _convert_element(
        self,
        elem: etree._Element,
        doc_href: str,
        images: dict[str, bytes],
        result: list[str],
        in_paragraph: bool = False,
    ) -> str:
        """Convert element and children to Typst, returning inline content."""
        tag = self._get_local_name(elem)

        # Skip footnote content (we inline it at the reference)
        epub_type = elem.get("{http://www.idpf.org/2007/ops}type", "")
        if "footnote" in epub_type or "endnote" in epub_type:
            return ""

        # Handle different element types
        if tag in ("h1", "h2"):
            text = self._extract_text(elem).strip()
            text = self._escape_typst(text)
            result.append(f"\n= {text}\n")
            return ""

        elif tag == "h3":
            text = self._extract_text(elem).strip()
            text = self._escape_typst(text)
            result.append(f"\n== {text}\n")
            return ""

        elif tag in ("h4", "h5", "h6"):
            text = self._extract_text(elem).strip()
            text = self._escape_typst(text)
            result.append(f"\n=== {text}\n")
            return ""

        elif tag == "p":
            # Check if this paragraph is actually a chapter heading
            raw_text = self._extract_text(elem).strip()
            
            if self._is_chapter_heading(raw_text):
                escaped = self._escape_typst(raw_text)
                result.append(f"\n= {escaped}\n")
                return ""
            
            content = self._convert_children(elem, doc_href, images, result)
            if content.strip():
                result.append(f"\n{content}\n")
            return ""

        elif tag == "blockquote":
            content = self._convert_children(elem, doc_href, images, result)
            # Format as Typst quote
            lines = content.strip().split("\n")
            quoted = "\n".join(f"  {line}" for line in lines)
            result.append(f"\n#quote[\n{quoted}\n]\n")
            return ""

        elif tag in ("em", "i"):
            content = self._convert_children(elem, doc_href, images, result)
            return f"#emph[{content}]"

        elif tag in ("strong", "b"):
            content = self._convert_children(elem, doc_href, images, result)
            return f"#strong[{content}]"

        elif tag == "br":
            return " \\\n"

        elif tag == "a":
            # Check if this is a footnote reference
            href = elem.get("href", "")
            elem_class = elem.get("class", "")
            epub_type = elem.get("{http://www.idpf.org/2007/ops}type", "")
            
            is_footnote_ref = (
                "noteref" in epub_type
                or "footnote" in elem_class.lower()
                or "footnote" in href.lower()
            )
            
            if is_footnote_ref or href.startswith("#"):
                # Try various lookup strategies for the footnote content
                footnote_text = None
                
                # Strategy 1: Direct lookup by href
                if "#" in href:
                    file_part, anchor = href.rsplit("#", 1)
                    file_name = Path(file_part).name if file_part else ""
                    # Try file#anchor format
                    footnote_text = self.footnotes.get(f"{file_name}#{anchor}")
                    if not footnote_text:
                        footnote_text = self.footnotes.get(anchor)
                else:
                    # Just an anchor
                    footnote_text = self.footnotes.get(href.lstrip("#"))
                
                if footnote_text:
                    escaped = self._escape_typst(footnote_text)
                    return f"#footnote[{escaped}]"
            
            # Regular link - just get text
            return self._convert_children(elem, doc_href, images, result)

        elif tag == "img":
            src = elem.get("src", "")
            if src:
                img_path = self._resolve_image_path(doc_href, src)
                try:
                    img_data = self.zip.read(img_path)
                    # Check ink coverage if threshold is set
                    if self.max_ink is not None:
                        ink = self._calculate_ink_coverage(img_data)
                        if ink > self.max_ink:
                            # Skip this image - too much ink
                            return ""
                    img_name = Path(src).name.replace(" ", "_")
                    images[img_name] = img_data
                    result.append(f'\n#image("{img_name}", width: 80%)\n')
                except KeyError:
                    pass
            return ""

        elif tag == "image":
            # SVG image element with xlink:href
            href = elem.get("{http://www.w3.org/1999/xlink}href", "")
            if href:
                img_path = self._resolve_image_path(doc_href, href)
                try:
                    img_data = self.zip.read(img_path)
                    # Check ink coverage if threshold is set
                    if self.max_ink is not None:
                        ink = self._calculate_ink_coverage(img_data)
                        if ink > self.max_ink:
                            # Skip this image - too much ink
                            return ""
                    img_name = Path(href).name.replace(" ", "_")
                    images[img_name] = img_data
                    result.append(f'\n#image("{img_name}", width: 80%)\n')
                except KeyError:
                    pass
            return ""

        elif tag in ("ul", "ol"):
            is_ordered = tag == "ol"
            items = []
            for child in elem:
                if self._get_local_name(child) == "li":
                    item_content = self._convert_children(child, doc_href, images, result)
                    items.append(item_content.strip())
            marker = "+" if is_ordered else "-"
            for item in items:
                result.append(f"{marker} {item}")
            result.append("")
            return ""

        elif tag == "span":
            return self._convert_children(elem, doc_href, images, result)

        elif tag in ("div", "section", "article", "body", "html"):
            return self._convert_children(elem, doc_href, images, result)

        elif tag == "sup":
            content = self._convert_children(elem, doc_href, images, result)
            return f"#super[{content}]"

        elif tag == "sub":
            content = self._convert_children(elem, doc_href, images, result)
            return f"#sub[{content}]"

        else:
            # Default: just process children
            return self._convert_children(elem, doc_href, images, result)

    def _convert_children(
        self,
        elem: etree._Element,
        doc_href: str,
        images: dict[str, bytes],
        result: list[str],
    ) -> str:
        """Convert all children of an element, returning inline content."""
        parts = []
        if elem.text:
            parts.append(self._escape_typst(elem.text))

        for child in elem:
            inline = self._convert_element(child, doc_href, images, result)
            if inline:
                parts.append(inline)
            if child.tail:
                parts.append(self._escape_typst(child.tail))

        return "".join(parts)

    def _escape_typst(self, text: str) -> str:
        """Escape special Typst characters."""
        # Escape special characters that have meaning in Typst
        text = text.replace("\\", "\\\\")
        text = text.replace("#", "\\#")
        text = text.replace("@", "\\@")
        text = text.replace("$", "\\$")
        text = text.replace("<", "\\<")
        text = text.replace(">", "\\>")
        text = text.replace("[", "\\[")
        text = text.replace("]", "\\]")
        text = text.replace("*", "\\*")
        text = text.replace("_", "\\_")
        text = text.replace("`", "\\`")
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)
        return text

    def _resolve_image_path(self, doc_href: str, img_src: str) -> str:
        """Resolve image path relative to document."""
        doc_dir = str(Path(doc_href).parent)
        if doc_dir == ".":
            doc_dir = ""

        # Handle relative paths
        if img_src.startswith("../"):
            # Go up from document directory
            parts = doc_dir.split("/") if doc_dir else []
            img_parts = img_src.split("/")
            while img_parts and img_parts[0] == "..":
                img_parts.pop(0)
                if parts:
                    parts.pop()
            resolved = "/".join(parts + img_parts)
        elif doc_dir:
            resolved = f"{doc_dir}/{img_src}"
        else:
            resolved = img_src

        return self._resolve_path(resolved)


class TypstGenerator:
    """Generates Typst source from a Book."""

    def __init__(
        self, book: Book, font_path: Path | None = None, page_size: str = "a5"
    ):
        self.book = book
        self.font_path = font_path
        self.page_size = page_size

    def generate(self) -> str:
        """Generate complete Typst source."""
        parts = []

        # Document setup
        parts.append(self._generate_setup())

        # Title page
        parts.append(self._generate_title_page())

        # Table of contents
        parts.append(self._generate_toc())

        # Chapters
        for chapter in self.book.chapters:
            parts.append(self._generate_chapter(chapter))

        return "\n".join(parts)

    def _get_font_family_name(self, font_path: Path) -> str:
        """Extract the font family name from a TTF/OTF file."""
        try:
            font = ttLib.TTFont(font_path)
            # Name ID 1 is the font family name
            for record in font["name"].names:
                if record.nameID == 1 and record.platformID == 3:  # Windows platform
                    return record.toUnicode()
            # Fallback: try any platform
            for record in font["name"].names:
                if record.nameID == 1:
                    return record.toUnicode()
        except Exception:
            pass
        # Last resort: use filename stem
        return font_path.stem

    def _generate_setup(self) -> str:
        """Generate document setup."""
        font_config = ""
        if self.font_path:
            font_name = self._get_font_family_name(self.font_path)
            font_config = f'#set text(font: "{font_name}")'

        return f'''// Document setup
#set document(title: "{self._escape_string(self.book.title)}", author: "{self._escape_string(self.book.author)}")

#set page(
  paper: "{self.page_size}",
  margin: (
    top: 1.5cm,
    bottom: 1.5cm,
    inside: 1.5cm,
    outside: 1cm,
  ),
  header: context {{
    let sel = selector(heading.where(level: 1)).before(here())
    let chapter = query(sel).last()
    if chapter != none {{
      set text(size: 9pt, style: "italic")
      align(center, chapter.body)
    }}
  }},
  numbering: "1",
)

#set text(
  size: 10pt,
  lang: "en",
)
{font_config}

// Typography settings
#set par(
  justify: true,
  leading: 0.65em,
  first-line-indent: 1em,
)

// Use Typst's advanced justification
#set text(
  costs: (hyphenation: 50%),
)

// Heading styles
#show heading.where(level: 1): it => {{
  pagebreak(weak: true)
  v(2cm)
  set text(size: 18pt, weight: "bold")
  align(center, it.body)
  v(1cm)
}}

#show heading.where(level: 2): it => {{
  v(0.5cm)
  set text(size: 14pt, weight: "bold")
  it.body
  v(0.3cm)
}}

// Quote styling
#show quote: it => {{
  set text(style: "italic")
  pad(left: 1cm, right: 1cm, it.body)
}}

// Footnote styling
#set footnote.entry(
  separator: line(length: 30%, stroke: 0.5pt),
)
'''

    def _generate_title_page(self) -> str:
        """Generate title page."""
        return f'''
// Title page
#page(header: none, numbering: none)[
  #v(1fr)
  #align(center)[
    #text(size: 24pt, weight: "bold")[{self._escape_string(self.book.title)}]
    
    #v(1cm)
    
    #text(size: 14pt)[{self._escape_string(self.book.author)}]
  ]
  #v(1fr)
]
'''

    def _generate_toc(self) -> str:
        """Generate table of contents."""
        return r'''
// Table of Contents
#page(header: none)[
  #heading(outlined: false)[Contents]
  
  #v(0.5cm)
  
  #context {
    let chapters = query(selector(heading.where(level: 1)))
    for chapter in chapters {
      let page-num = counter(page).at(chapter.location()).first()
      [#chapter.body #box(width: 1fr, repeat[.]) #page-num \ ]
    }
  }
]
'''

    def _generate_chapter(self, chapter: Chapter) -> str:
        """Generate chapter content."""
        return f"\n{chapter.content}\n"

    def _escape_string(self, text: str) -> str:
        """Escape a string for use in Typst string literals."""
        return text.replace("\\", "\\\\").replace('"', '\\"')


class Impositioner:
    """Imposes PDF pages for booklet printing."""

    def __init__(self, pages_per_signature: int = 16):
        self.pages_per_signature = pages_per_signature
        # Must be multiple of 4
        if self.pages_per_signature % 4 != 0:
            self.pages_per_signature = ((self.pages_per_signature // 4) + 1) * 4

    def impose_booklet(self, input_pdf: Path, output_pdf: Path) -> None:
        """
        Create a booklet-imposed PDF.
        
        Pages are arranged so that when printed duplex and folded,
        they create a booklet with correct page order.
        """
        reader = PdfReader(input_pdf)
        writer = PdfWriter()

        total_pages = len(reader.pages)
        page_width = float(reader.pages[0].mediabox.width)
        page_height = float(reader.pages[0].mediabox.height)

        # Pad to multiple of signature size
        padded_total = (
            (total_pages + self.pages_per_signature - 1)
            // self.pages_per_signature
            * self.pages_per_signature
        )

        # Process each signature
        for sig_start in range(0, padded_total, self.pages_per_signature):
            sig_pages = list(range(sig_start, sig_start + self.pages_per_signature))
            sheet_order = self._get_booklet_order(len(sig_pages))

            for sheet_idx in range(0, len(sheet_order), 2):
                left_page_num = sheet_order[sheet_idx]
                right_page_num = sheet_order[sheet_idx + 1]

                # Create new sheet (landscape, 2x page width)
                sheet = PageObject.create_blank_page(
                    width=page_width * 2, height=page_height
                )

                # Add left page
                if left_page_num is not None:
                    actual_page = sig_start + left_page_num
                    if actual_page < total_pages:
                        src_page = reader.pages[actual_page]
                        sheet.merge_transformed_page(
                            src_page, Transformation()
                        )

                # Add right page
                if right_page_num is not None:
                    actual_page = sig_start + right_page_num
                    if actual_page < total_pages:
                        src_page = reader.pages[actual_page]
                        sheet.merge_transformed_page(
                            src_page, Transformation().translate(tx=page_width)
                        )

                writer.add_page(sheet)

        with open(output_pdf, "wb") as f:
            writer.write(f)

    def _get_booklet_order(self, num_pages: int) -> list[int | None]:
        """
        Get page order for booklet imposition.
        
        For a 4-page booklet:
        - Sheet 1 front: 4, 1 (back, front cover)
        - Sheet 1 back: 2, 3 (inside pages)
        """
        order = []
        for sheet in range(num_pages // 4):
            # Front side: last, first
            left = num_pages - 1 - (sheet * 2)
            right = sheet * 2
            order.extend([left, right])
            # Back side: second, second-to-last
            left = sheet * 2 + 1
            right = num_pages - 2 - (sheet * 2)
            order.extend([left, right])
        return order

    def impose_a5_to_a3(self, input_pdf: Path, output_pdf: Path) -> None:
        """
        Impose A5 pages for A3 duplex printing.
        
        Layout per A3 sheet:
        - Reading order: top-left, top-right, bottom-left, bottom-right
        - Bottom pages are rotated 180° so reader flips bottom up
        
        Each A3 sheet holds 4 A5 pages (2x2 grid).
        The folded result is A4 sized, with A5 pages.
        """
        reader = PdfReader(input_pdf)
        writer = PdfWriter()

        total_pages = len(reader.pages)
        page_width = float(reader.pages[0].mediabox.width)
        page_height = float(reader.pages[0].mediabox.height)

        # A3 dimensions (2x A4, or 4x A5 in 2x2)
        # A5: 148mm x 210mm, A3: 297mm x 420mm
        a3_width = page_width * 2  # Two A5 pages wide
        a3_height = page_height * 2  # Two A5 pages tall

        # Pad to multiple of 8 (4 pages per side, duplex = 8 per sheet)
        pages_per_sheet = 8
        padded_total = (
            (total_pages + pages_per_sheet - 1) // pages_per_sheet * pages_per_sheet
        )

        # Process sheets
        for sheet_start in range(0, padded_total, pages_per_sheet):
            # Front side: pages 0, 1, 2, 3 (top-left, top-right, bottom-left, bottom-right)
            # Back side: pages 4, 5, 6, 7
            for side in range(2):
                sheet = PageObject.create_blank_page(width=a3_width, height=a3_height)

                base = sheet_start + side * 4
                positions = [
                    # (page_offset, x, y, rotation)
                    (0, 0, page_height, 0),  # top-left
                    (1, page_width, page_height, 0),  # top-right
                    (2, page_width, page_height, 180),  # bottom-left (rotated)
                    (3, 0, page_height, 180),  # bottom-right (rotated)
                ]

                for offset, x, y, rotation in positions:
                    page_num = base + offset
                    if page_num < total_pages:
                        src_page = reader.pages[page_num]
                        transform = Transformation()
                        if rotation == 180:
                            # Rotate 180° around page center, then translate
                            transform = (
                                Transformation()
                                .translate(tx=-page_width / 2, ty=-page_height / 2)
                                .rotate(180)
                                .translate(tx=page_width / 2, ty=page_height / 2)
                                .translate(tx=x, ty=y - page_height)
                            )
                        else:
                            transform = Transformation().translate(tx=x, ty=y)
                        sheet.merge_transformed_page(src_page, transform)

                writer.add_page(sheet)

        with open(output_pdf, "wb") as f:
            writer.write(f)


def convert_epub_to_pdf(
    epub_path: Path,
    output_pdf: Path,
    font_path: Path | None = None,
    page_size: str = "a5",
    reading_pdf: Path | None = None,
    impose: bool = True,
    pages_per_signature: int = 16,
    a3_mode: bool = False,
    wait: bool = False,
    max_ink: float | None = None,
) -> None:
    """Convert an EPUB to a print-ready PDF."""

    # Parse EPUB
    print(f"Parsing {epub_path}...")
    parser = EPUBParser(epub_path, max_ink=max_ink)
    book = parser.parse()
    print(f"  Found {len(book.chapters)} chapters")

    # Generate Typst source
    print("Generating Typst source...")
    generator = TypstGenerator(book, font_path, page_size)
    typst_source = generator.generate()

    # Create temp directory for Typst compilation
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        print(f"Using temporary directory {tmppath}")

        # Write Typst source
        typst_file = tmppath / "book.typ"
        typst_file.write_text(typst_source, encoding="utf-8")

        # Write images
        for name, data in book.images.items():
            (tmppath / name).write_bytes(data)

        # Copy font if provided
        if font_path and font_path.exists():
            font_dest = tmppath / font_path.name
            font_dest.write_bytes(font_path.read_bytes())

        # Compile with Typst
        print("Compiling with Typst...")
        intermediate_pdf = tmppath / "book.pdf"
        result = subprocess.run(
            ["typst", "compile", str(typst_file), str(intermediate_pdf)],
            capture_output=True,
            text=True,
            cwd=tmppath,
        )
        if result.returncode != 0:
            print("Typst compilation failed:")
            print(result.stderr)
            raise RuntimeError("Typst compilation failed")

        # Save reading PDF if requested
        if reading_pdf:
            print(f"Saving reading PDF to {reading_pdf}...")
            reading_pdf.write_bytes(intermediate_pdf.read_bytes())

        # Impose if requested
        if impose:
            print("Imposing pages...")
            impositioner = Impositioner(pages_per_signature)
            if a3_mode:
                impositioner.impose_a5_to_a3(intermediate_pdf, output_pdf)
            else:
                impositioner.impose_booklet(intermediate_pdf, output_pdf)
            print(f"Saved imposed PDF to {output_pdf}")
        else:
            output_pdf.write_bytes(intermediate_pdf.read_bytes())
            print(f"Saved PDF to {output_pdf}")

        

        if wait:
            input("Press Enter to exit...")




def main():
    parser = argparse.ArgumentParser(
        description="Convert EPUB to print-ready PDF",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("epub", type=Path, help="Input EPUB file")
    parser.add_argument( "-o", "--output", type=Path, help="Output PDF file (default: <epub-name>.pdf)" )
    parser.add_argument( "--font", type=Path, default="Dyslexie-Regular.ttf", help="Path to a local font file to use" )
    parser.add_argument( "--page-size", default="a5", help="Page size (e.g., a5, a4, letter)", )
    parser.add_argument( "--reading-pdf", type=Path, help="Also save the intermediate (non-imposed) reading PDF", )
    parser.add_argument( "--no-impose", action="store_true", help="Don't impose pages; output the reading PDF directly", ) 
    parser.add_argument( "--pages-per-signature", type=int, default=32, help="Pages per signature (must be multiple of 4)", )
    parser.add_argument( "--a3-mode", action="store_true", help="Use A5-to-A3 duplex imposition mode", )
    parser.add_argument( "--wait", action="store_true", help="Wait for user input before exiting (for debugging)", )
    parser.add_argument( "--max-ink", type=float, default=0.4, help="Exclude images with ink coverage above this threshold (0.0-1.0, e.g., 0.3 for 30%%)", )

    args = parser.parse_args()

    # Default output filename
    if args.output is None:
        args.output = args.epub.with_suffix(".pdf")

    convert_epub_to_pdf(
        epub_path=args.epub,
        output_pdf=args.output,
        font_path=args.font,
        page_size=args.page_size,
        reading_pdf=args.reading_pdf,
        impose=not args.no_impose,
        pages_per_signature=args.pages_per_signature,
        a3_mode=args.a3_mode,
        wait=args.wait,
        max_ink=args.max_ink,
    )

if __name__ == "__main__":
    main()
