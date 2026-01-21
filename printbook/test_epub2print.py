#!/usr/bin/env python3
"""Tests for epub2print.py"""

import pytest
import tempfile
import zipfile
from pathlib import Path
from lxml import etree

from epub2print import EPUBParser, TypstGenerator, Book, Chapter


class TestChapterHeadingDetection:
    """Tests for _is_chapter_heading method."""

    @pytest.fixture
    def parser(self, tmp_path):
        """Create a minimal EPUB for testing."""
        epub_path = tmp_path / "test.epub"
        with zipfile.ZipFile(epub_path, "w") as zf:
            # container.xml
            zf.writestr(
                "META-INF/container.xml",
                """<?xml version="1.0"?>
                <container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
                  <rootfiles>
                    <rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>
                  </rootfiles>
                </container>""",
            )
            # minimal OPF
            zf.writestr(
                "content.opf",
                """<?xml version="1.0"?>
                <package xmlns="http://www.idpf.org/2007/opf">
                  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
                    <dc:title>Test Book</dc:title>
                    <dc:creator>Test Author</dc:creator>
                  </metadata>
                  <manifest>
                    <item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
                  </manifest>
                  <spine><itemref idref="ch1"/></spine>
                </package>""",
            )
            # minimal chapter
            zf.writestr(
                "ch1.xhtml",
                """<?xml version="1.0"?>
                <html xmlns="http://www.w3.org/1999/xhtml">
                  <head><title>Test</title></head>
                  <body><p>Test content</p></body>
                </html>""",
            )
        return EPUBParser(epub_path)

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
                """<?xml version="1.0"?>
                <package xmlns="http://www.idpf.org/2007/opf">
                  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
                    <dc:title>Test</dc:title>
                  </metadata>
                  <manifest/>
                  <spine/>
                </package>""",
            )
        return EPUBParser(epub_path)

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
                filename = f"ch{i+1}.xhtml"
                manifest_items.append(
                    f'<item id="ch{i+1}" href="{filename}" media-type="application/xhtml+xml"/>'
                )
                spine_items.append(f'<itemref idref="ch{i+1}"/>')
                
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
                {''.join(manifest_items)}
              </manifest>
              <spine>
                {''.join(spine_items)}
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
                Chapter(title="Chapter One", content="= Chapter One\n\nSome content here."),
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
        path = Path(__file__).parent / "(The Murderbot Diaries 1) Wells, Martha - All Systems Red.epub"
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
        headings = re.findall(r'^= .+$', typst, re.MULTILINE)
        # Should have multiple chapter headings
        assert len(headings) >= 8, f"Expected at least 8 headings, found {len(headings)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
