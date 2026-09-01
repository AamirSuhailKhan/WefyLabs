"""
Document Parser Provider Abstraction
======================================
Pluggable parsers for all supported document types.

Supported formats:
  PDF     → pdfminer.six / pypdf (text-layer extraction)
  DOCX    → python-docx
  TXT     → plain text
  CSV     → csv module (structured table extraction)
  XLSX    → openpyxl (table extraction)
  HTML    → html.parser
  Markdown→ markdown stripping
  Image   → delegates to OCR provider

Each parser returns a ParsedDocument with:
  - Full text content
  - Structured tables (list of rows)
  - Page-level content for multi-page docs
  - Metadata extracted from document properties
  - Parsing confidence
"""
from __future__ import annotations

import csv
import html
import io
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class ParsedPage:
    """Content of a single parsed page."""
    page_number: int
    text: str
    tables: List[Dict[str, Any]] = field(default_factory=list)
    # tables: [{headers: [...], rows: [[...]], caption: "..."}]


@dataclass
class ParsedDocument:
    """Full parsed output of a document."""
    mime_type: str
    total_pages: int
    full_text: str
    pages: List[ParsedPage] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    # metadata: {title, author, created_at, subject, language_hint}
    confidence: float = 1.0          # 0-1; lower for OCR-heavy docs
    requires_ocr: bool = False       # True if page is image-only
    parse_errors: List[str] = field(default_factory=list)


# ─── Abstract Interface ────────────────────────────────────────────────────────

class DocumentParser(ABC):
    """
    Abstract document parser.
    Each implementation handles one or more MIME types.
    """
    supported_mime_types: List[str] = []

    @abstractmethod
    async def parse(
        self, content: bytes, filename: str = ""
    ) -> ParsedDocument:
        """
        Parse document bytes into structured content.
        Never returns None — always returns ParsedDocument (with errors if failed).
        """
        ...


# ─── PDF Parser ───────────────────────────────────────────────────────────────

class PDFParser(DocumentParser):
    """
    PDF parser using pdfminer.six for text-layer extraction.
    Falls back to requires_ocr=True for image-only PDFs.
    Preserves page boundaries for accurate citation (page numbers).
    """
    supported_mime_types = ["application/pdf"]

    async def parse(self, content: bytes, filename: str = "") -> ParsedDocument:
        try:
            from pdfminer.high_level import extract_pages
            from pdfminer.layout import LTTextContainer, LTFigure, LTLayoutContainer
        except ImportError:
            logger.warning("[PDF PARSER] pdfminer not installed, falling back to text")
            return ParsedDocument(
                mime_type="application/pdf",
                total_pages=1,
                full_text=content.decode("utf-8", errors="replace"),
                confidence=0.5,
                parse_errors=["pdfminer not installed"],
            )

        pdf_file = io.BytesIO(content)
        pages: List[ParsedPage] = []
        full_text_parts: List[str] = []
        parse_errors: List[str] = []
        requires_ocr = False

        try:
            for page_num, page_layout in enumerate(extract_pages(pdf_file), start=1):
                page_text_parts: List[str] = []
                for element in page_layout:
                    if isinstance(element, LTTextContainer):
                        page_text_parts.append(element.get_text())
                    elif isinstance(element, LTFigure):
                        requires_ocr = True

                page_text = "".join(page_text_parts).strip()
                if not page_text and page_num == 1:
                    requires_ocr = True

                pages.append(ParsedPage(
                    page_number=page_num,
                    text=page_text,
                ))
                full_text_parts.append(page_text)

        except Exception as exc:
            parse_errors.append(f"PDF parse error: {exc}")
            logger.error(f"[PDF PARSER] Error: {exc}", exc_info=True)

        full_text = "\n\n".join(full_text_parts)
        confidence = 0.9 if not requires_ocr else 0.4

        return ParsedDocument(
            mime_type="application/pdf",
            total_pages=len(pages),
            full_text=full_text,
            pages=pages,
            confidence=confidence,
            requires_ocr=requires_ocr,
            parse_errors=parse_errors,
        )


# ─── DOCX Parser ──────────────────────────────────────────────────────────────

class DOCXParser(DocumentParser):
    """
    DOCX parser using python-docx.
    Extracts paragraphs, headings, and tables.
    Preserves table structure for payment plans / pricing grids.
    """
    supported_mime_types = [
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ]

    async def parse(self, content: bytes, filename: str = "") -> ParsedDocument:
        try:
            import docx
        except ImportError:
            return ParsedDocument(
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                total_pages=1,
                full_text=content.decode("utf-8", errors="replace"),
                confidence=0.3,
                parse_errors=["python-docx not installed"],
            )

        try:
            doc = docx.Document(io.BytesIO(content))
            paragraphs: List[str] = []
            tables: List[Dict[str, Any]] = []

            for para in doc.paragraphs:
                text = para.text.strip()
                if text:
                    paragraphs.append(text)

            for i, table in enumerate(doc.tables):
                rows = []
                headers: List[str] = []
                for r_idx, row in enumerate(table.rows):
                    cells = [cell.text.strip() for cell in row.cells]
                    if r_idx == 0:
                        headers = cells
                    else:
                        rows.append(cells)
                tables.append({
                    "table_index": i,
                    "headers": headers,
                    "rows": rows,
                    "caption": f"Table {i + 1}",
                })

            full_text = "\n".join(paragraphs)
            return ParsedDocument(
                mime_type=self.supported_mime_types[0],
                total_pages=1,
                full_text=full_text,
                pages=[ParsedPage(page_number=1, text=full_text, tables=tables)],
                tables=tables,
                confidence=0.95,
            )
        except Exception as exc:
            return ParsedDocument(
                mime_type=self.supported_mime_types[0],
                total_pages=1,
                full_text="",
                confidence=0.0,
                parse_errors=[f"DOCX parse error: {exc}"],
            )


# ─── Plain Text Parser ────────────────────────────────────────────────────────

class PlainTextParser(DocumentParser):
    """Simple UTF-8 text parser."""
    supported_mime_types = ["text/plain"]

    async def parse(self, content: bytes, filename: str = "") -> ParsedDocument:
        text = content.decode("utf-8", errors="replace")
        return ParsedDocument(
            mime_type="text/plain",
            total_pages=1,
            full_text=text,
            pages=[ParsedPage(page_number=1, text=text)],
            confidence=1.0,
        )


# ─── CSV Parser ───────────────────────────────────────────────────────────────

class CSVParser(DocumentParser):
    """
    CSV parser with table structure preservation.
    Extracts headers and rows — does NOT flatten to meaningless text.
    """
    supported_mime_types = ["text/csv", "application/csv"]

    async def parse(self, content: bytes, filename: str = "") -> ParsedDocument:
        text = content.decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(text))
        rows_raw = list(reader)
        if not rows_raw:
            return ParsedDocument(mime_type="text/csv", total_pages=1, full_text="")

        headers = rows_raw[0] if rows_raw else []
        data_rows = rows_raw[1:] if len(rows_raw) > 1 else []

        table = {
            "table_index": 0,
            "headers": headers,
            "rows": data_rows,
            "caption": filename or "CSV Data",
        }

        # Convert to readable text representation
        full_text_lines = [" | ".join(headers)]
        for row in data_rows:
            full_text_lines.append(" | ".join(str(c) for c in row))
        full_text = "\n".join(full_text_lines)

        return ParsedDocument(
            mime_type="text/csv",
            total_pages=1,
            full_text=full_text,
            pages=[ParsedPage(page_number=1, text=full_text, tables=[table])],
            tables=[table],
            confidence=1.0,
        )


# ─── HTML Parser ──────────────────────────────────────────────────────────────

class HTMLParser(DocumentParser):
    """HTML content parser — strips tags, preserves readable text."""
    supported_mime_types = ["text/html"]

    async def parse(self, content: bytes, filename: str = "") -> ParsedDocument:
        raw = content.decode("utf-8", errors="replace")
        # Remove script and style blocks
        clean = re.sub(r"<script[^>]*>.*?</script>", "", raw, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r"<style[^>]*>.*?</style>", "", clean, flags=re.DOTALL | re.IGNORECASE)
        # Remove remaining HTML tags
        clean = re.sub(r"<[^>]+>", " ", clean)
        # Decode HTML entities
        clean = html.unescape(clean)
        # Normalize whitespace
        clean = re.sub(r"\s+", " ", clean).strip()

        return ParsedDocument(
            mime_type="text/html",
            total_pages=1,
            full_text=clean,
            pages=[ParsedPage(page_number=1, text=clean)],
            confidence=0.9,
        )


# ─── Markdown Parser ──────────────────────────────────────────────────────────

class MarkdownParser(DocumentParser):
    """Markdown parser — strips markers, preserves structure."""
    supported_mime_types = ["text/markdown", "text/x-markdown"]

    async def parse(self, content: bytes, filename: str = "") -> ParsedDocument:
        text = content.decode("utf-8", errors="replace")
        # Strip markdown syntax but keep content
        clean = re.sub(r"#{1,6}\s+", "", text)   # headings
        clean = re.sub(r"\*\*(.*?)\*\*", r"\1", clean)   # bold
        clean = re.sub(r"\*(.*?)\*", r"\1", clean)       # italic
        clean = re.sub(r"`{1,3}(.*?)`{1,3}", r"\1", clean, flags=re.DOTALL)  # code
        clean = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", clean)  # links

        return ParsedDocument(
            mime_type="text/markdown",
            total_pages=1,
            full_text=clean.strip(),
            pages=[ParsedPage(page_number=1, text=clean.strip())],
            confidence=1.0,
        )


# ─── Parser Registry ──────────────────────────────────────────────────────────

_PARSERS: Dict[str, DocumentParser] = {
    "application/pdf": PDFParser(),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DOCXParser(),
    "text/plain": PlainTextParser(),
    "text/csv": CSVParser(),
    "application/csv": CSVParser(),
    "text/html": HTMLParser(),
    "text/markdown": MarkdownParser(),
    "text/x-markdown": MarkdownParser(),
}

_EXTENSION_MAP: Dict[str, str] = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
    "csv": "text/csv",
    "html": "text/html",
    "htm": "text/html",
    "md": "text/markdown",
    "markdown": "text/markdown",
}


def get_parser(mime_type: str, filename: str = "") -> Optional[DocumentParser]:
    """
    Resolve a document parser by MIME type or filename extension.
    Returns None if no parser is registered for the type.
    """
    parser = _PARSERS.get(mime_type)
    if parser:
        return parser

    # Try by extension
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        resolved_mime = _EXTENSION_MAP.get(ext)
        if resolved_mime:
            return _PARSERS.get(resolved_mime)

    logger.warning(f"[PARSER REGISTRY] No parser found for mime='{mime_type}' file='{filename}'")
    return None
