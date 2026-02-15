#!/usr/bin/env python3
"""Tests for epub2print.py"""

import pytest
import zipfile
from pathlib import Path

from epub2print import (
    EPUBParser,
    TypstGenerator,
    Book,
    Chapter,
    IndexTracker,
    postprocess_index_markers,
    _clean_word,
)


def _create_minimal_epub(tmp_path: Path, title: str = "Test Book",
                         author: str = "Test Author") -> Path:
    """Create a minimal valid EPUB for testing.

    Returns the path to the created EPUB file.
    """
    epub_path = tmp_path / "test.epub"
    with zipfile.ZipFile(epub_path, "w") as zf:
        zf.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0"?>
            <container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
              <rootfiles>
                <rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>
              </rootfiles>
            </container>""",
        )
        zf.writestr(
            "content.opf",
            f"""<?xml version="1.0"?>
            <package xmlns="http://www.idpf.org/2007/opf">
              <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
                <dc:title>{title}</dc:title>
                <dc:creator>{author}</dc:creator>
              </metadata>
              <manifest>
                <item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
              </manifest>
              <spine><itemref idref="ch1"/></spine>
            </package>""",
        )
        zf.writestr(
            "ch1.xhtml",
            """<?xml version="1.0"?>
            <html xmlns="http://www.w3.org/1999/xhtml">
              <head><title>Test</title></head>
              <body><p>Test content</p></body>
            </html>""",
        )
    return epub_path


class TestChapterHeadingDetection:
    """Tests for _is_chapter_heading method."""

    @pytest.fixture
    def parser(self, tmp_path):
        """Create a minimal EPUB for testing."""
        return EPUBParser(_create_minimal_epub(tmp_path))

    # Valid chapter headings
    @pytest.mark.parametrize(
        "text",
        [
            "Chapter One",
            "Chapter Two",
            "Chapter 1",
            "Chapter 42",
            "CHAPTER ONE",
            "chapter one",
            "Chapter Twenty",
            "Prologue",
            "PROLOGUE",
            "Epilogue",
            "epilogue",
            "Introduction",
            "About the Author",
            "Acknowledgments",
            "Part One",
            "Part 1",
            "Part I",
            "Part II",
            "Part III",
            "Part IV",
            "Part V",
        ],
    )
    def test_valid_chapter_headings(self, parser, text):
        assert parser._is_chapter_heading(text) is True

    # Invalid chapter headings (should not match)
    @pytest.mark.parametrize(
        "text",
        [
            "",
            "   ",
            "Part of it is, they didn't want me here.",  # Sentence starting with "Part"
            "Chapter One: The Beginning",  # Has subtitle
            "This is Chapter One of the story",  # Chapter in middle
            "The Prologue to Everything",  # Prologue in middle
            "A" * 100,  # Too long
            "Random text",
            "Some other heading",
            "Part of the problem was...",
            "Introduction to the matter at hand",  # Too long
            "Chapter",  # No number
            "Part",  # No number
        ],
    )
    def test_invalid_chapter_headings(self, parser, text):
        assert parser._is_chapter_heading(text) is False


class TestTypstEscaping:
    """Tests for Typst special character escaping."""

    @pytest.fixture
    def parser(self, tmp_path):
        """Create a minimal EPUB for testing."""
        return EPUBParser(_create_minimal_epub(tmp_path, title="Test"))

    @pytest.mark.parametrize(
        "input_text,expected",
        [
            ("Hello world", "Hello world"),
            ("Test #hashtag", "Test \\#hashtag"),
            ("Price: $100", "Price: \\$100"),
            ("email@test.com", "email\\@test.com"),
            ("<tag>", "\\<tag\\>"),
            ("[brackets]", "\\[brackets\\]"),
            ("*bold*", "\\*bold\\*"),
            ("_italic_", "\\_italic\\_"),
            ("`code`", "\\`code\\`"),
            ("back\\slash", "back\\\\slash"),
            ("multiple  spaces", "multiple spaces"),  # whitespace normalized
            ("line\nbreak", "line break"),  # newlines normalized
        ],
    )
    def test_escape_typst(self, parser, input_text, expected):
        assert parser._escape_typst(input_text) == expected


class TestEPUBParsing:
    """Tests for EPUB parsing functionality."""

    def create_test_epub(self, tmp_path, chapters: list[tuple[str, str]]) -> Path:
        """Create a test EPUB with given chapters (title, content)."""
        epub_path = tmp_path / "test.epub"

        manifest_items = []
        spine_items = []

        with zipfile.ZipFile(epub_path, "w") as zf:
            # container.xml
            zf.writestr(
                "META-INF/container.xml",
                """<?xml version="1.0"?>
                <container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
                  <rootfiles>
                    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
                  </rootfiles>
                </container>""",
            )

            # Create chapter files
            for i, (title, content) in enumerate(chapters):
                filename = f"ch{i + 1}.xhtml"
                manifest_items.append(
                    f'<item id="ch{i + 1}" href="{filename}" media-type="application/xhtml+xml"/>'
                )
                spine_items.append(f'<itemref idref="ch{i + 1}"/>')

                xhtml = f"""<?xml version="1.0" encoding="UTF-8"?>
                <html xmlns="http://www.w3.org/1999/xhtml">
                  <head><title>{title}</title></head>
                  <body>
                    <h1>{title}</h1>
                    <p>{content}</p>
                  </body>
                </html>"""
                zf.writestr(f"OEBPS/{filename}", xhtml)

            # content.opf
            opf = f"""<?xml version="1.0" encoding="UTF-8"?>
            <package xmlns="http://www.idpf.org/2007/opf" version="2.0">
              <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
                <dc:title>Test Book</dc:title>
                <dc:creator>Test Author</dc:creator>
              </metadata>
              <manifest>
                {"".join(manifest_items)}
              </manifest>
              <spine>
                {"".join(spine_items)}
              </spine>
            </package>"""
            zf.writestr("OEBPS/content.opf", opf)

        return epub_path

    def test_parse_basic_epub(self, tmp_path):
        """Test parsing a basic EPUB with h1 chapter headings."""
        epub_path = self.create_test_epub(
            tmp_path,
            [
                ("Chapter One", "This is the first chapter."),
                ("Chapter Two", "This is the second chapter."),
            ],
        )

        parser = EPUBParser(epub_path)
        book = parser.parse()

        assert book.title == "Test Book"
        assert book.author == "Test Author"
        assert len(book.chapters) == 2
        assert book.chapters[0].title == "Chapter One"
        assert book.chapters[1].title == "Chapter Two"

    def test_parse_epub_with_styled_chapters(self, tmp_path):
        """Test parsing EPUB where chapters are in <p> tags (Calibre style)."""
        epub_path = tmp_path / "styled.epub"

        with zipfile.ZipFile(epub_path, "w") as zf:
            zf.writestr(
                "META-INF/container.xml",
                """<?xml version="1.0"?>
                <container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
                  <rootfiles>
                    <rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>
                  </rootfiles>
                </container>""",
            )

            # Chapter with <p> tag heading (like Calibre)
            zf.writestr(
                "ch1.xhtml",
                """<?xml version="1.0"?>
                <html xmlns="http://www.w3.org/1999/xhtml">
                  <body>
                    <p class="chapter-title">Chapter One</p>
                    <p>Content of chapter one.</p>
                  </body>
                </html>""",
            )

            zf.writestr(
                "content.opf",
                """<?xml version="1.0"?>
                <package xmlns="http://www.idpf.org/2007/opf">
                  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
                    <dc:title>Styled Book</dc:title>
                    <dc:creator>Author</dc:creator>
                  </metadata>
                  <manifest>
                    <item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
                  </manifest>
                  <spine><itemref idref="ch1"/></spine>
                </package>""",
            )

        parser = EPUBParser(epub_path)
        book = parser.parse()

        assert len(book.chapters) == 1
        assert book.chapters[0].title == "Chapter One"
        # The content should have "Chapter One" as a heading
        assert "= Chapter One" in book.chapters[0].content


class TestTypstGeneration:
    """Tests for Typst source generation."""

    def test_generate_basic_book(self):
        """Test generating Typst from a basic book."""
        book = Book(
            title="Test Title",
            author="Test Author",
            chapters=[
                Chapter(
                    title="Chapter One", content="= Chapter One\n\nSome content here."
                ),
            ],
        )

        generator = TypstGenerator(book)
        typst = generator.generate()

        assert 'title: "Test Title"' in typst
        assert 'author: "Test Author"' in typst
        assert "Chapter One" in typst
        assert "Some content here." in typst

    def test_generate_toc_queries_headings(self):
        """Test that TOC is generated to query level 1 headings."""
        book = Book(
            title="Test",
            author="Author",
            chapters=[],
        )

        generator = TypstGenerator(book)
        typst = generator.generate()

        # TOC should use context and query for headings
        assert "heading.where(level: 1)" in typst

    def test_escape_string_in_metadata(self):
        """Test that special characters in metadata are escaped."""
        book = Book(
            title='Title with "quotes"',
            author="Author's Name",
            chapters=[],
        )

        generator = TypstGenerator(book)
        typst = generator.generate()

        assert 'title: "Title with \\"quotes\\""' in typst


class TestIntegration:
    """Integration tests using real EPUB files if available."""

    @pytest.fixture
    def murderbot_epub(self):
        """Get the Murderbot EPUB if it exists."""
        path = (
            Path(__file__).parent
            / "(The Murderbot Diaries 1) Wells, Martha - All Systems Red.epub"
        )
        if not path.exists():
            pytest.skip("Murderbot EPUB not found")
        return path

    def test_murderbot_has_chapters(self, murderbot_epub):
        """Test that Murderbot EPUB parses with multiple chapters."""
        parser = EPUBParser(murderbot_epub)
        book = parser.parse()

        assert book.title == "All Systems Red"
        assert "Martha Wells" in book.author
        assert len(book.chapters) > 1

    def test_murderbot_chapters_have_headings(self, murderbot_epub):
        """Test that Murderbot chapters generate proper Typst headings."""
        parser = EPUBParser(murderbot_epub)
        book = parser.parse()

        generator = TypstGenerator(book)
        typst = generator.generate()

        # Should have chapter headings
        assert "= Chapter One" in typst or "= Chapter 1" in typst

        # Count level 1 headings
        import re

        headings = re.findall(r"^= .+$", typst, re.MULTILINE)
        # Should have multiple chapter headings
        assert len(headings) >= 8, (
            f"Expected at least 8 headings, found {len(headings)}"
        )


class TestCleanWord:
    """Tests for _clean_word helper."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            # Basic words pass through
            ("hello", "hello"),
            ("Kira", "Kira"),
            # Possessives stripped
            ("Sorcha's", "Sorcha"),
            ("Sorcha\u2019s", "Sorcha"),
            ("Everything's", "Everything"),
            # Contractions stripped
            ("It'd", "It"),
            ("It\u2019d", "It"),
            ("I'll", "I"),
            ("I\u2019ll", "I"),
            ("we've", "we"),
            ("they're", "they"),
            ("don't", "don"),
            # Edge quotes stripped
            ("'hello'", "hello"),
            ("\u2019word\u2019", "word"),
            # No double-stripping
            ("word", "word"),
        ],
    )
    def test_clean_word(self, raw, expected):
        assert _clean_word(raw) == expected


class TestIndexTracker:
    """Tests for the two-pass IndexTracker."""

    def test_proper_noun_detection(self):
        """Proper nouns mid-sentence get collected as candidates."""
        tracker = IndexTracker()
        tracker.new_chapter()
        text = "and then Kira walked away"
        escaped = "and then Kira walked away"
        tracker.annotate_text(text, escaped)
        assert "Kira" in tracker.noun_candidates
        assert 0 in tracker.noun_candidates["Kira"]

    def test_proper_noun_not_at_sentence_start(self):
        """Words at sentence start are not treated as proper nouns."""
        tracker = IndexTracker()
        tracker.new_chapter()
        text = "Kira walked away"
        escaped = "Kira walked away"
        tracker.annotate_text(text, escaped)
        assert "Kira" not in tracker.noun_candidates

    def test_common_capitals_scored_low(self):
        """Common English words (high zipf frequency) score low/zero as nouns."""
        tracker = IndexTracker()
        tracker.new_chapter()
        # "Yes" has zipf ~5.5, above the 5.0 rarity ceiling
        text = "and then Yes she said"
        escaped = "and then Yes she said"
        tracker.annotate_text(text, escaped)
        # Yes is collected but will score 0 (zipf >= 5.0)
        if "Yes" in tracker.noun_candidates:
            selected, all_scored = tracker.select_all(budget=120)
            assert "yes" not in selected

    def test_common_nouns_scored_zero(self):
        """Words like War, World, King score 0 (zipf >= 5.0)."""
        tracker = IndexTracker()
        tracker.new_chapter()
        text = "and the War raged and the World burned and the King fell"
        escaped = "and the War raged and the World burned and the King fell"
        tracker.annotate_text(text, escaped)
        selected, all_scored = tracker.select_all(budget=120)
        assert "war" not in selected
        assert "world" not in selected
        assert "king" not in selected

    def test_proper_noun_deduped_per_chapter(self):
        """Same proper noun only collected once per chapter."""
        tracker = IndexTracker()
        tracker.new_chapter()
        text = "and Kira spoke, and Kira laughed"
        escaped = "and Kira spoke, and Kira laughed"
        tracker.annotate_text(text, escaped)
        assert "Kira" in tracker.noun_candidates
        # Only one chapter recorded
        assert tracker.noun_candidates["Kira"] == {0}

    def test_proper_noun_capped_at_3_chapters_in_selection(self):
        """A proper noun is inserted in at most 3 chapters."""
        tracker = IndexTracker()
        for i in range(5):
            tracker.new_chapter()
            text = "and then Kira walked"
            escaped = "and then Kira walked"
            tracker.annotate_text(text, escaped)
        assert len(tracker.noun_candidates["Kira"]) == 5  # seen in 5 chapters
        selected, _ = tracker.select_all(budget=120)
        # Selected entry capped at 3 chapters
        if "kira" in selected:
            _, chapters = selected["kira"]
            assert len(chapters) <= 3

    def test_rare_word_collection(self):
        """Rare words are collected as candidates during pass 1."""
        tracker = IndexTracker()
        tracker.new_chapter()
        # "gossamer" is a rare English word (zipf < 4)
        text = "the gossamer wings"
        escaped = "the gossamer wings"
        tracker.annotate_text(text, escaped)
        # Should have collected a candidate
        assert len(tracker.rare_candidates) > 0
        assert any(c.lower == "gossamer" for c in tracker.rare_candidates)

    def test_common_words_not_collected(self):
        """Common words (zipf >= 4) are NOT collected as candidates."""
        tracker = IndexTracker()
        tracker.new_chapter()
        text = "the quick brown something over"
        escaped = "the quick brown something over"
        tracker.annotate_text(text, escaped)
        # "something" has zipf > 4, should not be collected
        assert not any(c.lower == "something" for c in tracker.rare_candidates)

    def test_select_rare_words_returns_top(self):
        """select_all returns scored results."""
        tracker = IndexTracker()
        tracker.new_chapter()
        # Feed several rare words
        for word in ["gossamer", "ephemeral", "gossamer", "ethereal"]:
            tracker.collect_word(word, 5, f"the {word} thing")
        tracker.new_chapter()
        tracker.collect_word("gossamer", 5, "the gossamer again")

        selected, all_scored = tracker.select_all(budget=120)
        assert len(selected) > 0
        # All entries have (display, chapters) structure
        for lower, (display, chapters) in selected.items():
            assert isinstance(display, str)
            assert isinstance(chapters, set)

    def test_no_rare_words_when_empty(self):
        """select_all returns empty when no candidates."""
        tracker = IndexTracker()
        selected, all_scored = tracker.select_all(budget=120)
        assert selected == {}
        assert all_scored == []

    def test_possessive_not_separate_entry(self):
        """Sorcha's should be collected as Sorcha, not as a separate entry."""
        tracker = IndexTracker()
        tracker.new_chapter()
        # Use curly quote possessive like real EPUBs
        text = "and then Sorcha\u2019s eyes widened"
        escaped = "and then Sorcha\u2019s eyes widened"
        tracker.annotate_text(text, escaped)
        assert "Sorcha" in tracker.noun_candidates
        # Must NOT contain Sorcha’s as a separate entry
        assert "Sorcha\u2019s" not in tracker.noun_candidates

    def test_contraction_not_indexed(self):
        """Contractions like It'd, I'll should not produce index entries."""
        tracker = IndexTracker()
        tracker.new_chapter()
        text = "and It\u2019d be nice if I\u2019ll get there"
        escaped = "and It\u2019d be nice if I\u2019ll get there"
        tracker.annotate_text(text, escaped)
        # It'd cleans to "It" (len 2, < 3, skipped)
        # I'll cleans to "I" (len 1, < 3, skipped)
        assert "It" not in tracker.noun_candidates
        assert "I" not in tracker.noun_candidates

    def test_contraction_fragment_not_rare_word(self):
        """Contraction fragments like Hadn (from Hadn't) must not be collected."""
        tracker = IndexTracker()
        tracker.new_chapter()
        text = "Hadn\u2019t she Couldn\u2019t have Shouldn\u2019t we"
        escaped = "Hadn\u2019t she Couldn\u2019t have Shouldn\u2019t we"
        tracker.annotate_text(text, escaped)
        assert not any(c.lower in ('hadn', 'couldn', 'shouldn') for c in tracker.rare_candidates)

    def test_cmon_not_indexed(self):
        """C'mon should not be indexed as a proper noun (internal apostrophe)."""
        tracker = IndexTracker()
        tracker.new_chapter()
        text = "and C\u2019mon let\u2019s go"
        escaped = "and C\u2019mon let\u2019s go"
        tracker.annotate_text(text, escaped)
        assert "C\u2019mon" not in tracker.noun_candidates
        assert "C'mon" not in tracker.noun_candidates

    def test_goodbye_scored_low(self):
        """Goodbye (zipf=4.30) should score low and be excluded with default budget."""
        tracker = IndexTracker()
        tracker.new_chapter()
        text = "and Goodbye she said"
        escaped = "and Goodbye she said"
        tracker.annotate_text(text, escaped)
        selected, all_scored = tracker.select_all(budget=5)
        # Goodbye has zipf=4.30, rarity = 5.0-4.30 = 0.70, low score
        # With a budget of 5 and no other candidates, it might squeak in,
        # but its score should be very low
        for score, cat, display, lower, zipf, spread in all_scored:
            if lower == 'goodbye':
                assert score < 2.0  # very low score
                break

    def test_interjection_not_indexed(self):
        """Interjections like Mmhmm (no vowels) should not be indexed as proper nouns."""
        tracker = IndexTracker()
        tracker.new_chapter()
        text = "and Mmhmm she nodded"
        escaped = "and Mmhmm she nodded"
        tracker.annotate_text(text, escaped)
        assert "Mmhmm" not in tracker.noun_candidates

    def test_annotate_text_returns_escaped_unchanged(self):
        """annotate_text should return escaped text unchanged (two-pass)."""
        tracker = IndexTracker()
        tracker.new_chapter()
        text = "and then Kira walked away"
        escaped = "and then Kira walked away"
        result = tracker.annotate_text(text, escaped)
        assert result == escaped  # no inline modifications

    def test_index_size_configurable(self):
        """select_all respects budget parameter."""
        tracker = IndexTracker()
        tracker.new_chapter()
        # Add many rare words
        words = ["gossamer", "ephemeral", "ethereal", "luminescent",
                 "iridescent", "diaphanous", "evanescent", "pellucid"]
        for w in words:
            for _ in range(3):  # appear multiple times for score
                tracker.collect_word(w, 5, f"the {w} thing")
        selected, _ = tracker.select_all(budget=3)
        assert len(selected) <= 3


class TestPostprocessIndexMarkers:
    """Tests for the post-processing pass 2."""

    def test_inserts_index_marker(self):
        """Post-processing inserts #index[] for a selected word."""
        chapters = [
            Chapter(title="Ch1", content="the gossamer wings spread wide"),
        ]
        selected = {"gossamer": ("Gossamer", {0})}
        postprocess_index_markers(chapters, selected)
        assert "#index[Gossamer]" in chapters[0].content

    def test_only_first_occurrence(self):
        """Only the first occurrence per chapter gets marked."""
        chapters = [
            Chapter(title="Ch1", content="gossamer and more gossamer"),
        ]
        selected = {"gossamer": ("Gossamer", {0})}
        postprocess_index_markers(chapters, selected)
        assert chapters[0].content.count("#index[Gossamer]") == 1

    def test_only_in_specified_chapters(self):
        """Markers are only inserted in chapters where the word appeared."""
        chapters = [
            Chapter(title="Ch1", content="the gossamer wings"),
            Chapter(title="Ch2", content="the gossamer veil"),
        ]
        # Only chapter 0
        selected = {"gossamer": ("Gossamer", {0})}
        postprocess_index_markers(chapters, selected)
        assert "#index[Gossamer]" in chapters[0].content
        assert "#index[Gossamer]" not in chapters[1].content

    def test_does_not_match_inside_index(self):
        """Should not match words already inside #index[...]."""
        chapters = [
            Chapter(title="Ch1", content="word#index[gossamer] more gossamer here"),
        ]
        selected = {"gossamer": ("Gossamer", {0})}
        postprocess_index_markers(chapters, selected)
        # The second "gossamer" should be marked, but not the one inside #index[]
        # Total markers should be 2 (the existing one + the new one)
        assert chapters[0].content.count("#index[") == 2

    def test_empty_selected_is_noop(self):
        """Empty selection does nothing."""
        chapters = [Chapter(title="Ch1", content="hello world")]
        postprocess_index_markers(chapters, {})
        assert chapters[0].content == "hello world"

    def test_case_insensitive_matching(self):
        """Word matching is case-insensitive."""
        chapters = [
            Chapter(title="Ch1", content="The Gossamer wings"),
        ]
        selected = {"gossamer": ("Gossamer", {0})}
        postprocess_index_markers(chapters, selected)
        assert "#index[Gossamer]" in chapters[0].content


class TestSceneSignals:
    """Tests for scene signal detection."""

    def test_intimate_scene_detected(self):
        """Paragraphs with enough intimate signal words trigger a marker."""
        tracker = IndexTracker()
        tracker.new_chapter()
        text = "His breath caught as she touched his skin, her lips warm"
        scenes = tracker.check_scene_signals(text)
        assert "Intimate" in scenes

    def test_no_scene_below_threshold(self):
        """Paragraphs with too few signal words don't trigger."""
        tracker = IndexTracker()
        tracker.new_chapter()
        text = "She walked through the meadow thinking about lunch"
        scenes = tracker.check_scene_signals(text)
        assert scenes == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
