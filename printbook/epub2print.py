#!uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fonttools",
#     "lxml",
#     "nltk",
#     "pillow",
#     "pypdf",
#     "wordfreq",
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
import math
import re
import subprocess
import tempfile
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from fontTools import ttLib
from lxml import etree
from pypdf import PdfReader, PdfWriter, PageObject, Transformation


# Scene signal word lexicon — clusters of these in a paragraph trigger index markers
SCENE_SIGNALS: dict[str, set[str]] = {
    "Intimate": {
        "breath", "skin", "lips", "pulse", "heat", "fingers", "mouth", "kiss",
        "touch", "shiver", "ache", "whisper", "naked", "desire", "moan", "gasp",
        "caress", "tongue", "throat", "hips", "chest", "thigh", "flush", "tremble",
        "pressed", "stroked", "tasted", "breathless", "hunger", "pleasure",
        "sweat", "arched", "clenched", "bare", "bed", "silk",
    },
    "Violence": {
        "blood", "blade", "sword", "fight", "scream", "pain", "wound", "strike",
        "kill", "death", "arrow", "battle", "slash", "stab", "shield", "war",
        "weapon", "dagger", "fist", "punch", "slammed", "crushed", "bleeding",
        "corpse", "gun", "shot", "explosion", "shattered", "steel",
    },
    "Magic": {
        "spell", "magic", "power", "glow", "shimmer", "ward", "rune", "enchant",
        "summon", "conjure", "aura", "sorcery", "incantation", "ritual", "arcane",
        "elemental", "mana", "curse", "hex", "alchemy", "potion", "wand",
        "crystal", "mystic", "ethereal", "sigil", "channeled", "invocation",
    },
    "Tension": {
        "secret", "betray", "lie", "reveal", "confront", "demand", "threaten",
        "warn", "suspect", "accuse", "confess", "ultimatum", "deceive", "scheme",
        "manipulate", "blackmail", "conspire", "fury", "rage", "desperate",
    },
}

# Minimum number of signal words in a paragraph to trigger a scene index marker
SCENE_SIGNAL_THRESHOLD = 3


# Proper noun rarity ceiling for scoring.  Words with zipf >= 5.0
# (War=5.46, King=5.17) score 0 and are excluded.  Character names
# sit well below (Kira=3.21, Phoenix=4.21).  No hard cutoff — scoring
# handles ranking naturally via --index-size.
_PROPER_NOUN_RARITY_CEILING = 5.0


# Contraction suffixes to strip (with both straight and curly apostrophes).
# Order matters: check longer suffixes first.
_CONTRACTION_SUFFIXES = ("'ll", "\u2019ll", "'ve", "\u2019ve", "'re", "\u2019re",
                         "'d", "\u2019d", "'t", "\u2019t",
                         "'s", "\u2019s")

# Contraction-only suffixes (excluding possessive 's).
_CONTRACTION_ONLY_SUFFIXES = ("'ll", "\u2019ll", "'ve", "\u2019ve", "'re", "\u2019re",
                              "'d", "\u2019d", "'t", "\u2019t")

_VOWELS = frozenset('aeiouy')


def _is_adjacent_to_separator(pos: int, raw_word: str, full_text: str) -> bool:
    """Check if a word is adjacent to `.`, `@`, or `/` (email/URL context)."""
    word_end = pos + len(raw_word)
    if word_end < len(full_text) and full_text[word_end] in '.@/':
        return True
    if pos > 0 and full_text[pos - 1] in '.@/':
        return True
    return False


def _clean_word(raw: str) -> str:
    """Normalize a raw token for indexing.

    Strips edge quotes, possessive suffixes (``'s``), and common
    contraction endings (``'d``, ``'ll``, ``'ve``, ``'re``, ``'t``).
    Works with both straight (') and curly (\u2019) apostrophes.

    >>> _clean_word("Sorcha's")
    'Sorcha'
    >>> _clean_word("It'd")
    'It'
    >>> _clean_word("we'll")
    'we'
    """
    # Strip leading/trailing apostrophes and curly quotes
    w = raw.strip("'\u2019")
    # Strip contraction / possessive suffixes
    for suffix in _CONTRACTION_SUFFIXES:
        if w.endswith(suffix):
            w = w[:-len(suffix)]
            break
    return w


@dataclass
class CandidateWord:
    """A candidate rare word recorded during pass 1."""
    word: str           # cleaned surface form (e.g. "gossamer")
    lower: str          # lowered form
    stem: str           # snowball-stemmed form
    zipf: float         # wordfreq zipf_frequency score (0–8)
    chapter_idx: int    # which chapter it appeared in
    position: int       # character offset in un-escaped text


class IndexTracker:
    """Tracks index state and identifies interesting words during Typst generation.

    Uses a unified two-pass approach:
    - Pass 1 (during HTML→Typst conversion): collects proper noun and rare word
      candidates.  Scene and chapter markers are inserted inline.
      annotate_text() returns escaped text UNCHANGED (no noun markers inline).
    - Scoring: after all chapters, scores all candidates (nouns + rare words)
      in a unified pool, selects top N (--index-size).
    - Pass 2 (post-processing): inserts #index[] markers for ALL selected
      entries into the Typst source.
    """

    def __init__(self):
        from wordfreq import zipf_frequency
        from nltk.stem.snowball import SnowballStemmer
        self._zipf = zipf_frequency
        self._stemmer = SnowballStemmer('english')
        # Proper noun collection (two-pass)
        self.noun_candidates: dict[str, set[int]] = {}   # word → {chapter_idxs}
        self._noun_chapter_seen: set[str] = set()        # per-chapter dedup
        self._chapter_idx = -1
        # Rare word two-pass state
        self.rare_candidates: list[CandidateWord] = []
        self.stem_counts: dict[str, Counter[str]] = {}  # stem → {surface_form: count}

    def new_chapter(self) -> None:
        """Reset per-chapter state, increment chapter index."""
        self._noun_chapter_seen = set()
        self._chapter_idx += 1

    def check_scene_signals(self, plain_text: str) -> list[str]:
        """Check if a paragraph contains a cluster of scene signal words.

        Returns list of matched category names (e.g. ["Intimate", "Violence"]).
        """
        words_lower = set(re.findall(r"[a-z]+", plain_text.lower()))
        results = []
        for category, signals in SCENE_SIGNALS.items():
            hits = words_lower & signals
            if len(hits) >= SCENE_SIGNAL_THRESHOLD:
                results.append(category)
        return results

    def annotate_text(self, text: str, escaped: str) -> str:
        """Collect index candidates from text (pass 1 — no modification).

        Scans text for proper nouns and rare words, recording them as
        candidates.  Returns escaped unchanged; actual #index[] markers
        are inserted in pass 2 by postprocess_index_markers().

        Args:
            text: original plain text (for word detection).
            escaped: Typst-escaped version (returned unchanged).

        Returns:
            The escaped string, unchanged.
        """
        if not text or not text.strip():
            return escaped

        for match in re.finditer(r"[A-Za-z'\u2019]+", text):
            raw_word = match.group()
            word_start = match.start()

            is_noun = self._check_proper_noun(raw_word, word_start, text)
            if not is_noun:
                self.collect_word(raw_word, word_start, text)

        return escaped

    def collect_word(self, raw_word: str, pos: int, full_text: str) -> None:
        """Record a candidate rare word if it passes basic filters (pass 1).

        Casts a wide net: alphabetic, 4+ chars, zipf < 4.0.
        Actual selection happens in select_all().
        """
        # Skip contraction fragments: if the raw token ends with a
        # contraction suffix, the cleaned result (Hadn, Couldn, etc.)
        # is a meaningless fragment, not a real word.
        stripped = raw_word.strip("'\u2019")
        for suffix in _CONTRACTION_ONLY_SUFFIXES:
            if stripped.endswith(suffix):
                return  # contraction fragment

        clean = _clean_word(raw_word)
        lower = clean.lower()

        if len(clean) < 4 or not clean.isalpha():
            return
        if _is_adjacent_to_separator(pos, raw_word, full_text):
            return

        zipf = self._zipf(lower, 'en')
        if zipf >= 4.0:
            return  # too common

        stem = self._stemmer.stem(lower)

        # Track stem → surface form counts
        if stem not in self.stem_counts:
            self.stem_counts[stem] = Counter()
        self.stem_counts[stem][lower] += 1

        self.rare_candidates.append(CandidateWord(
            word=clean,
            lower=lower,
            stem=stem,
            zipf=zipf,
            chapter_idx=self._chapter_idx,
            position=pos,
        ))

    def _check_proper_noun(self, raw_word: str, pos: int, full_text: str) -> bool:
        """Check if a word is a proper noun and record it as a candidate.

        Collects proper noun candidates for later scoring.  No zipf ceiling;
        scoring in select_all() handles ranking naturally.

        Returns True if the word was recorded as a noun candidate.
        """
        # Strip edge quotes
        word = raw_word.strip("'\u2019")

        # If the word is a contraction (Don't, I'll, etc.), skip entirely
        for suffix in _CONTRACTION_ONLY_SUFFIXES:
            if word.endswith(suffix):
                return False

        # Strip possessive 's / \u2019s
        for suffix in ("'s", "\u2019s"):
            if word.endswith(suffix):
                word = word[:-len(suffix)]
                break

        if len(word) < 3:
            return False
        # Must be purely alphabetic (filters C'mon, O'Brien-style words)
        if not word.isalpha():
            return False
        if _is_adjacent_to_separator(pos, raw_word, full_text):
            return False

        # Must be Title-case (not ALL CAPS)
        if not (word[0].isupper() and (len(word) == 1 or not word[1:].isupper())):
            return False

        # Must contain at least one vowel (filters interjections: Mmhmm, Pfft, Hmph)
        if not any(c in _VOWELS for c in word.lower()):
            return False

        if not self._is_mid_sentence(pos, full_text):
            return False

        # Deduplicate: record each noun once per chapter
        if word in self._noun_chapter_seen:
            return True  # already collected this chapter, still a noun
        self._noun_chapter_seen.add(word)

        # Record candidate
        if word not in self.noun_candidates:
            self.noun_candidates[word] = set()
        self.noun_candidates[word].add(self._chapter_idx)
        return True

    def select_all(
        self, budget: int = 120,
    ) -> tuple[dict[str, tuple[str, set[int]]], list[tuple[float, str, str, str, float, int]]]:
        """Score and select the top index entries (nouns + rare words).

        Returns:
            selected: {lowercase_word: (DisplayForm, {chapter_indices})}
                for the top *budget* entries.
            all_scored: full scored list for printing, each entry is
                (score, category, display_word, lower, zipf, spread).
        """
        all_scored: list[tuple[float, str, str, str, float, int]] = []

        # --- Score rare words (grouped by stem) ---
        if self.rare_candidates:
            stem_groups: dict[str, list[CandidateWord]] = {}
            for cand in self.rare_candidates:
                stem_groups.setdefault(cand.stem, []).append(cand)

            for stem, candidates in stem_groups.items():
                form_counts = self.stem_counts.get(stem, Counter())
                display_lower = (
                    form_counts.most_common(1)[0][0]
                    if form_counts else candidates[0].lower
                )
                display_word = display_lower.capitalize()

                zipf = self._zipf(display_lower, 'en')
                rarity = max(0.0, 4.0 - zipf)
                if rarity == 0:
                    continue

                chapters = {c.chapter_idx for c in candidates}
                spread = len(chapters)
                count = sum(form_counts.values())
                usedness = min(math.log2(count + 1), 3.0)
                score = rarity * usedness * (1 + 0.2 * min(spread, 5))

                all_scored.append(
                    (score, "word", display_word, display_lower, zipf, spread)
                )

        # --- Score proper nouns ---
        for word, chapter_idxs in self.noun_candidates.items():
            zipf = self._zipf(word.lower(), 'en')
            rarity = max(0.0, _PROPER_NOUN_RARITY_CEILING - zipf)
            if rarity == 0:
                continue
            spread = len(chapter_idxs)
            score = rarity * (1 + 0.2 * min(spread, 5))
            all_scored.append(
                (score, "noun", word, word.lower(), zipf, spread)
            )

        # --- Deduplicate: same lowercase → keep higher score ---
        best_by_lower: dict[str, tuple[float, str, str, str, float, int]] = {}
        for entry in all_scored:
            lower = entry[3]
            if lower not in best_by_lower or entry[0] > best_by_lower[lower][0]:
                best_by_lower[lower] = entry
        all_scored = sorted(best_by_lower.values(), key=lambda x: x[0], reverse=True)

        # --- Select top N ---
        selected: dict[str, tuple[str, set[int]]] = {}
        for i, (score, cat, display, lower, zipf, spread) in enumerate(all_scored):
            if i >= budget:
                break
            if cat == "noun":
                # Cap proper nouns at 3 chapters (first 3 in reading order)
                chapter_idxs = self.noun_candidates.get(display, set())
                chapters = set(sorted(chapter_idxs)[:3])
            else:
                # Rare words: find all chapters from candidates
                chapters: set[int] = set()
                for cand in self.rare_candidates:
                    if cand.lower == lower:
                        chapters.add(cand.chapter_idx)
            selected[lower] = (display, chapters)

        return selected, all_scored

    def _is_mid_sentence(self, pos: int, text: str) -> bool:
        """Check if position is mid-sentence (not after sentence-ending punctuation)."""
        if pos == 0:
            return False
        i = pos - 1
        while i >= 0 and text[i] in ' \t\n\r':
            i -= 1
        if i < 0:
            return False
        if text[i] in '.!?:;\u2014\u2026':
            return False
        if text[i] in '"\u201d\u2019\u201c\'' and i > 0 and text[i-1] in '.!?':
            return False
        return True

    def heading_marker(self, title: str) -> str:
        """Return an #index marker for a chapter heading (bold page number)."""
        safe = title.replace('"', '\\"')
        return f'#index(fmt: strong, [{safe}])'


def print_index_scores(
    all_scored: list[tuple[float, str, str, str, float, int]],
    budget: int,
) -> None:
    """Print the full scored index list showing what's selected vs excluded."""
    if not all_scored:
        print("  No index candidates found.")
        return

    print(f"  Index: {len(all_scored)} candidates scored, selecting top {budget}")
    print(f"  {'Score':>7s}  {'Cat':<4s}  {'Word':<20s}  {'Zipf':>4s}  {'Spread':>6s}")
    for i, (score, cat, display, lower, zipf, spread) in enumerate(all_scored):
        if i == budget:
            print(f"  {'---- index-size cutoff (' + str(budget) + ') ----':^53s}")
        print(f"  {score:7.2f}  {cat:<4s}  {display:<20s}  {zipf:4.2f}  {spread:6d}")


def postprocess_index_markers(
    chapters: list['Chapter'],
    selected: dict[str, tuple[str, set[int]]],
) -> None:
    """Insert #index[] markers for selected entries into chapter Typst content.

    Pass 2: for each selected entry (proper noun or rare word), finds its
    first occurrence in each chapter and inserts #index[Display] after it.
    Modifies chapters in place.

    Args:
        chapters: List of Chapter objects with Typst content.
        selected: {lowercase_word: (DisplayForm, {chapter_indices})} from
                  IndexTracker.select_all().
    """
    if not selected:
        return

    for word_lower, (display, chapter_idxs) in selected.items():
        # Match the word at a word boundary, but not inside existing
        # #index[...] blocks or other Typst markup.
        pattern = re.compile(
            rf'(?<![#\[])(\b{re.escape(word_lower)}\b)(?![^\[]*\])',
            re.IGNORECASE,
        )
        for ch_idx in chapter_idxs:
            if ch_idx < 0 or ch_idx >= len(chapters):
                continue
            chapter = chapters[ch_idx]
            m = pattern.search(chapter.content)
            if m:
                insert_pos = m.end()
                chapter.content = (
                    chapter.content[:insert_pos]
                    + f"#index[{display}]"
                    + chapter.content[insert_pos:]
                )


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

    def __init__(self, epub_path: Path, max_ink: float | None = None,
                 index_tracker: IndexTracker | None = None):
        self.epub_path = epub_path
        self.index_tracker = index_tracker
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
            pixels = list(gray.getdata())
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

        # Parse NCX/nav TOC for chapter title fallback
        self.toc_titles = self._parse_toc_titles()

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

    def _parse_toc_titles(self) -> dict[str, str]:
        """Parse the NCX table of contents to build a href -> title mapping.
        
        This provides chapter titles as a fallback when they can't be detected
        from heading tags (e.g. EPUBs that use styled <p>/<span> for headings).
        """
        titles = {}
        # Try NCX first
        try:
            ncx_content = None
            for filename in self.zip.namelist():
                if filename.endswith(".ncx"):
                    ncx_content = self.zip.read(filename)
                    break
            if ncx_content:
                ncx = etree.fromstring(ncx_content)
                for nav_point in ncx.iter("{http://www.daisy.org/z3986/2005/ncx/}navPoint"):
                    label = nav_point.find(
                        "ncx:navLabel/ncx:text", namespaces=NAMESPACES
                    )
                    content = nav_point.find(
                        "ncx:content", namespaces=NAMESPACES
                    )
                    if label is not None and content is not None and label.text:
                        src = content.get("src", "")
                        # Strip fragment (e.g. "text/part0005.html#Chapter_1" -> "text/part0005.html")
                        href = src.split("#")[0] if "#" in src else src
                        # Store relative to OPF dir (matching spine href format)
                        titles[href] = label.text.strip()
        except Exception:
            pass
        return titles

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

        # Find chapter title from content, falling back to NCX TOC
        title = self._find_title(body)
        toc_title = self.toc_titles.get(href, "")
        # Prefer the NCX title over a bare number (e.g. "Chapter 1" vs "1")
        if not title or (re.match(r'^\d+$', title) and toc_title):
            title = toc_title or title

        # Convert body to Typst, passing the TOC title so bare-number
        # paragraphs can be replaced with the proper chapter name
        images = {}
        typst_content = self._element_to_typst(body, href, images, toc_title=toc_title)

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
            r'^\d+$',  # Bare chapter numbers (e.g. "1", "23")
            r'^Prologue$',
            r'^Epilogue$',
            r'^Introduction$',
            r'^Acknowledgments$',
            r'^Acknowledgements$',
            r'^About the Author$',
            r"^Author'?s? Note$",
        ]
        for pattern in patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        return False

    def _extract_text(self, elem: etree._Element) -> str:
        """Extract all text from an element."""
        return "".join(elem.itertext())

    def _element_to_typst(
        self, elem: etree._Element, doc_href: str, images: dict[str, bytes],
        toc_title: str = "",
    ) -> str:
        """Convert an XHTML element to Typst markup."""
        result = []
        self._convert_element(elem, doc_href, images, result, in_paragraph=False,
                              toc_title=toc_title)
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
        toc_title: str = "",
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
            escaped = self._escape_typst(text)
            result.append(f"\n= {escaped}\n")
            if self.index_tracker:
                self.index_tracker.new_chapter()
                result.append(self.index_tracker.heading_marker(text))
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
                # Use the NCX TOC title if available (e.g. "Chapter 1" instead of bare "1")
                if toc_title and re.match(r'^\d+$', raw_text):
                    heading_text = toc_title
                else:
                    heading_text = raw_text
                escaped = self._escape_typst(heading_text)
                result.append(f"\n= {escaped}\n")
                if self.index_tracker:
                    self.index_tracker.new_chapter()
                    result.append(self.index_tracker.heading_marker(heading_text))
                return ""
            
            # Check for scene signals before converting the paragraph
            if self.index_tracker:
                scenes = self.index_tracker.check_scene_signals(raw_text)
                for scene in scenes:
                    result.append(f'#index("Scenes", "{scene}")')

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
            return self._convert_children(elem, doc_href, images, result,
                                          toc_title=toc_title)

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
        toc_title: str = "",
    ) -> str:
        """Convert all children of an element, returning inline content."""
        parts = []
        if elem.text:
            parts.append(self._escape_and_index(elem.text))

        for child in elem:
            inline = self._convert_element(child, doc_href, images, result,
                                           toc_title=toc_title)
            if inline:
                parts.append(inline)
            if child.tail:
                parts.append(self._escape_and_index(child.tail))

        return "".join(parts)

    def _escape_and_index(self, text: str) -> str:
        """Escape text for Typst and optionally insert index markers."""
        escaped = self._escape_typst(text)
        if self.index_tracker:
            return self.index_tracker.annotate_text(text, escaped)
        return escaped

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
        self, book: Book, font_path: Path | None = None, page_size: str = "a5",
        generate_index: bool = False,
    ):
        self.book = book
        self.font_path = font_path
        self.page_size = page_size
        self.generate_index = generate_index

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

        # Index page (if enabled)
        if self.generate_index:
            parts.append(self._generate_index_page())

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

        index_import = '\n#import "@preview/in-dexter:0.7.2": *\n' if self.generate_index else ''

        return f'''{index_import}// Document setup
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

    def _generate_index_page(self) -> str:
        """Generate the back-of-book index page using in-dexter."""
        return r'''
// Index
#pagebreak()
#page(header: none)[
  #heading(outlined: true)[Index]
  #v(0.3cm)
  #set text(size: 8pt)
  #columns(2, gutter: 0.5cm)[
    #make-index(title: none)
  ]
]
'''

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

    def _get_booklet_order(self, num_pages: int) -> list[int]:
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

    def _impose_virtual_pages(
        self,
        writer: PdfWriter,
        virtual_pages: list[PageObject | None],
        page_width: float,
        page_height: float,
    ) -> None:
        """
        Impose virtual pages as a booklet.
        
        Takes a list of virtual pages (which may be None for blanks) and
        arranges them 2-up for booklet printing.
        """
        num_pages = len(virtual_pages)
        
        # Pad to multiple of signature size
        padded_total = (
            (num_pages + self.pages_per_signature - 1)
            // self.pages_per_signature
            * self.pages_per_signature
        )
        
        # Extend with None for padding
        virtual_pages = virtual_pages + [None] * (padded_total - num_pages)
        
        # Process each signature
        for sig_start in range(0, padded_total, self.pages_per_signature):
            sheet_order = self._get_booklet_order(self.pages_per_signature)

            for sheet_idx in range(0, len(sheet_order), 2):
                left_idx = sig_start + sheet_order[sheet_idx]
                right_idx = sig_start + sheet_order[sheet_idx + 1]

                # Create new sheet (2x page width)
                sheet = PageObject.create_blank_page(
                    width=page_width * 2, height=page_height
                )

                # Add left page
                if left_idx < len(virtual_pages) and virtual_pages[left_idx] is not None:
                    sheet.merge_transformed_page(
                        virtual_pages[left_idx], Transformation()
                    )

                # Add right page
                if right_idx < len(virtual_pages) and virtual_pages[right_idx] is not None:
                    sheet.merge_transformed_page(
                        virtual_pages[right_idx], Transformation().translate(tx=page_width)
                    )

                writer.add_page(sheet)

    def impose_booklet(self, input_pdf: Path, output_pdf: Path) -> None:
        """
        Create a booklet-imposed PDF.
        
        Pages are arranged so that when printed duplex and folded,
        they create a booklet with correct page order.
        """
        reader = PdfReader(input_pdf)
        writer = PdfWriter()

        page_width = float(reader.pages[0].mediabox.width)
        page_height = float(reader.pages[0].mediabox.height)

        # Use source pages directly as virtual pages
        virtual_pages = list(reader.pages)
        
        self._impose_virtual_pages(writer, virtual_pages, page_width, page_height)

        with open(output_pdf, "wb") as f:
            writer.write(f)

    def impose_a5_to_a3(self, input_pdf: Path, output_pdf: Path) -> None:
        """
        Impose A5 pages for A3 duplex printing.
        
        Process:
        1. Combine A5 pages 2-up into A4 spreads (landscape)
        2. Rotate each spread 90° to become portrait A4 pages
        3. Use standard booklet imposition on those A4 pages
        
        Output is landscape A3 sheets. When printed duplex and folded,
        the result is a booklet with A5-sized pages.
        """
        reader = PdfReader(input_pdf)
        writer = PdfWriter()

        total_pages = len(reader.pages)
        a5_width = float(reader.pages[0].mediabox.width)
        a5_height = float(reader.pages[0].mediabox.height)

        # A4 spread = 2 A5 pages side by side (landscape)
        a4_landscape_width = a5_width * 2
        a4_landscape_height = a5_height
        
        # After 90° rotation: portrait A4
        a4_portrait_width = a5_height
        a4_portrait_height = a5_width * 2

        # Create A4 spreads from consecutive A5 pages, then rotate 90°
        rotated_spreads = []
        for i in range(0, total_pages, 2):
            # Create landscape A4 spread
            spread = PageObject.create_blank_page(
                width=a4_landscape_width, height=a4_landscape_height
            )
            
            # Left A5 page
            spread.merge_transformed_page(
                reader.pages[i], Transformation()
            )
            
            # Right A5 page (if exists)
            if i + 1 < total_pages:
                spread.merge_transformed_page(
                    reader.pages[i + 1], Transformation().translate(tx=a5_width)
                )
            
            # Create rotated version (portrait A4)
            rotated = PageObject.create_blank_page(
                width=a4_portrait_width, height=a4_portrait_height
            )
            # Rotate 90° counter-clockwise around origin, then translate to fit
            # After 90° CCW: (x,y) → (-y, x)
            # Content spans x from -height to 0, so translate by (height, 0)
            rotated.merge_transformed_page(
                spread,
                Transformation()
                .rotate(90)
                .translate(tx=a4_landscape_height, ty=0)
            )
            
            rotated_spreads.append(rotated)

        # Use standard booklet imposition on the rotated A4 pages
        # This will create landscape A3 output (2 portrait A4s side by side)
        self._impose_virtual_pages(
            writer, rotated_spreads, a4_portrait_width, a4_portrait_height
        )

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
    generate_index: bool = False,
    index_size: int = 120,
) -> None:
    """Convert an EPUB to a print-ready PDF."""

    # Set up index tracker if requested
    index_tracker = None
    if generate_index:
        print("Index generation enabled")
        index_tracker = IndexTracker()

    # Parse EPUB
    print(f"Parsing {epub_path}...")
    parser = EPUBParser(epub_path, max_ink=max_ink, index_tracker=index_tracker)
    book = parser.parse()
    print(f"  Found {len(book.chapters)} chapters")

    if index_tracker:
        noun_count = len(index_tracker.noun_candidates)
        candidate_count = len(index_tracker.rare_candidates)
        print(f"  Collected {noun_count} proper nouns, {candidate_count} rare word candidates")

        # Score and select top entries, print scored list
        selected, all_scored = index_tracker.select_all(budget=index_size)
        print_index_scores(all_scored, index_size)
        if selected:
            postprocess_index_markers(book.chapters, selected)
            print(f"  Selected {len(selected)} entries for index")

    # Generate Typst source
    print("Generating Typst source...")
    generator = TypstGenerator(book, font_path, page_size, generate_index=generate_index)
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
            # Save the .typ source next to the output for debugging
            debug_typ = output_pdf.with_suffix('.typ')
            import shutil
            shutil.copy2(typst_file, debug_typ)
            print(f"Typst compilation failed (source saved to {debug_typ}):")
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
    parser.add_argument( "--index", action="store_true", help="Generate a back-of-book index (proper nouns, rare words, scene markers)", )
    parser.add_argument( "--index-size", type=int, default=40, help="Number of scored index entries (proper nouns + rare words) to include", )

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
        generate_index=args.index,
        index_size=args.index_size,
    )

if __name__ == "__main__":
    main()
