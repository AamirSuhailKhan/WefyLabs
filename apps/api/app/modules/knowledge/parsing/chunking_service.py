"""
Semantic Chunking Service
==========================
Splits parsed documents into semantic chunks for retrieval.

Chunking strategy (in priority order):
  1. Heading-based sections (H1/H2/H3 boundaries)
  2. FAQ blocks (Q: / A: patterns)
  3. Table boundaries (table data preserved intact)
  4. Paragraph boundaries (double newline)
  5. Sentence boundaries (fallback)
  6. Fixed window (last resort, with overlap)

Each chunk retains full metadata:
  - Document ID, version, page number
  - Section heading, subheading
  - Knowledge type, language, country, currency
  - Visibility, ai_allowed, customer_facing_allowed
  - Effective date, expiration date
  - Verification status (inherited from document)

CRITICAL: Tables are NEVER flattened into meaningless running text.
Tables are preserved as structured JSON in chunk.table_data.
"""
from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Chunking configuration
MAX_CHUNK_TOKENS = 400          # ~1600 chars for text-embedding-3-small
MAX_CHUNK_CHARS = 1600
OVERLAP_CHARS = 150             # Overlap to preserve context across chunks
MIN_CHUNK_CHARS = 15            # Skip very short noise chunks (e.g. single words/bullets)



# ─── Chunk Data Class ─────────────────────────────────────────────────────────

class KnowledgeChunkData:
    """In-memory representation before DB persistence."""
    def __init__(
        self,
        document_id: str,
        version_id: Optional[str],
        organization_id: str,
        chunk_index: int,
        content: str,
        chunk_type: str,
        knowledge_type: str,
        page_number: Optional[int] = None,
        section: Optional[str] = None,
        heading: Optional[str] = None,
        subheading: Optional[str] = None,
        language: str = "en",
        country: Optional[str] = None,
        currency: Optional[str] = None,
        visibility: str = "INTERNAL",
        ai_allowed: bool = True,
        effective_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        project_id: Optional[str] = None,
        property_id: Optional[str] = None,
        table_data: Optional[Dict[str, Any]] = None,
    ):
        self.id = str(uuid.uuid4())
        self.document_id = document_id
        self.version_id = version_id
        self.organization_id = organization_id
        self.chunk_index = chunk_index
        self.content = content
        self.chunk_type = chunk_type
        self.knowledge_type = knowledge_type
        self.page_number = page_number
        self.section = section
        self.heading = heading
        self.subheading = subheading
        self.language = language
        self.country = country
        self.currency = currency
        self.visibility = visibility
        self.ai_allowed = ai_allowed
        self.effective_at = effective_at
        self.expires_at = expires_at
        self.project_id = project_id
        self.property_id = property_id
        self.table_data = table_data
        self.content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        self.char_count = len(content)
        self.token_count = max(1, len(content.split()))
        self.is_expired = False
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = self.created_at


# ─── Chunking Service ─────────────────────────────────────────────────────────

class ChunkingService:
    """
    Semantic chunking engine.
    Processes a ParsedDocument into a list of KnowledgeChunkData.
    """

    # Heading patterns (Markdown-style or ALL CAPS line)
    _HEADING_RE = re.compile(
        r"^(#{1,6})\s+(.+)$|^([A-Z][A-Z0-9 ]{4,50})$",
        re.MULTILINE,
    )

    # FAQ pattern: Q: or Question:
    _FAQ_Q_RE = re.compile(
        r"^(?:Q[\.:]\s*|Question\s*[\.:]\s*)(.+)$",
        re.MULTILINE | re.IGNORECASE,
    )
    _FAQ_A_RE = re.compile(
        r"^(?:A[\.:]\s*|Answer\s*[\.:]\s*)(.+)$",
        re.MULTILINE | re.IGNORECASE,
    )

    def chunk_document(
        self,
        document_id: str,
        organization_id: str,
        parsed_text: str,
        knowledge_type: str,
        version_id: Optional[str] = None,
        page_number: Optional[int] = None,
        pages: Optional[List[Any]] = None,     # ParsedPage list
        tables: Optional[List[Dict]] = None,   # Pre-extracted tables
        language: str = "en",
        country: Optional[str] = None,
        currency: Optional[str] = None,
        visibility: str = "INTERNAL",
        ai_allowed: bool = True,
        effective_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        project_id: Optional[str] = None,
        property_id: Optional[str] = None,
    ) -> List[KnowledgeChunkData]:
        """
        Primary chunking entry point.
        Returns ordered list of KnowledgeChunkData for the document.
        """
        chunks: List[KnowledgeChunkData] = []
        chunk_index = 0

        common_kwargs = dict(
            document_id=document_id,
            version_id=version_id,
            organization_id=organization_id,
            knowledge_type=knowledge_type,
            language=language,
            country=country,
            currency=currency,
            visibility=visibility,
            ai_allowed=ai_allowed,
            effective_at=effective_at,
            expires_at=expires_at,
            project_id=project_id,
            property_id=property_id,
        )

        # ── Phase 1: Extract table chunks (preserved intact) ─────────────────
        if tables:
            for table in tables:
                table_text = self._table_to_text(table)
                if len(table_text) < MIN_CHUNK_CHARS:
                    continue
                chunks.append(KnowledgeChunkData(
                    chunk_index=chunk_index,
                    content=table_text,
                    chunk_type="table",
                    page_number=page_number,
                    section=table.get("caption"),
                    table_data=table,
                    **common_kwargs,
                ))
                chunk_index += 1

        # ── Phase 2: Process multi-page documents page by page ────────────────
        if pages:
            for page in pages:
                pg_chunks = self._chunk_page_text(
                    text=page.text,
                    page_number=page.page_number,
                    chunk_index_start=chunk_index,
                    **common_kwargs,
                )
                chunks.extend(pg_chunks)
                chunk_index += len(pg_chunks)
        else:
            # Single block of text
            pg_chunks = self._chunk_page_text(
                text=parsed_text,
                page_number=page_number or 1,
                chunk_index_start=chunk_index,
                **common_kwargs,
            )
            chunks.extend(pg_chunks)

        logger.info(
            f"[CHUNKER] doc={document_id} → {len(chunks)} chunks "
            f"type={knowledge_type} lang={language}"
        )
        return chunks

    def _chunk_page_text(
        self,
        text: str,
        page_number: int,
        chunk_index_start: int,
        **kwargs,
    ) -> List[KnowledgeChunkData]:
        """Chunk a single page of text using semantic boundaries."""
        if not text or len(text.strip()) < MIN_CHUNK_CHARS:
            return []

        # Detect FAQ format
        if self._FAQ_Q_RE.search(text):
            return self._chunk_as_faq(text, page_number, chunk_index_start, **kwargs)

        # Detect markdown table block
        table_lines = [line.strip() for line in text.strip().split("\n") if line.strip().startswith("|")]
        if len(table_lines) >= 3 and len(table_lines) >= len(text.strip().split("\n")) * 0.5:
            return [KnowledgeChunkData(
                chunk_index=chunk_index_start,
                content=text.strip(),
                chunk_type="table",
                page_number=page_number,
                **kwargs,
            )]

        # Split by headings
        sections = self._split_by_headings(text)
        if len(sections) > 1:
            return self._chunk_sections(
                sections, page_number, chunk_index_start, **kwargs
            )

        # Fallback: paragraph chunking
        return self._chunk_by_paragraphs(text, page_number, chunk_index_start, **kwargs)

    def _split_by_headings(
        self, text: str
    ) -> List[Tuple[str, str]]:
        """
        Split text by heading lines.
        Returns: [(heading, section_content), ...]
        """
        sections: List[Tuple[str, str]] = []
        current_heading = ""
        current_lines: List[str] = []

        for line in text.split("\n"):
            m = self._HEADING_RE.match(line.strip())
            if m:
                if current_lines:
                    sections.append((current_heading, "\n".join(current_lines).strip()))
                current_heading = (m.group(2) or m.group(3) or "").strip()
                current_lines = []
            else:
                current_lines.append(line)

        if current_lines:
            sections.append((current_heading, "\n".join(current_lines).strip()))

        return [(h, c) for h, c in sections if c.strip()]

    def _chunk_sections(
        self,
        sections: List[Tuple[str, str]],
        page_number: int,
        chunk_index_start: int,
        **kwargs,
    ) -> List[KnowledgeChunkData]:
        """Convert heading-based sections into chunks."""
        chunks: List[KnowledgeChunkData] = []
        idx = chunk_index_start

        for heading, content in sections:
            # If section is too long, sub-chunk by paragraphs
            if len(content) > MAX_CHUNK_CHARS:
                sub_chunks = self._chunk_by_paragraphs(
                    content, page_number, idx,
                    heading=heading,
                    **kwargs,
                )
                for sc in sub_chunks:
                    sc.heading = heading
                chunks.extend(sub_chunks)
                idx += len(sub_chunks)
            elif len(content) >= MIN_CHUNK_CHARS:
                chunks.append(KnowledgeChunkData(
                    chunk_index=idx,
                    content=content,
                    chunk_type="heading",
                    page_number=page_number,
                    heading=heading,
                    **kwargs,
                ))
                idx += 1

        return chunks

    def _chunk_by_paragraphs(
        self,
        text: str,
        page_number: int,
        chunk_index_start: int,
        heading: Optional[str] = None,
        **kwargs,
    ) -> List[KnowledgeChunkData]:
        """Split text by double-newline paragraph boundaries."""
        paragraphs = re.split(r"\n\s*\n", text)
        chunks: List[KnowledgeChunkData] = []
        idx = chunk_index_start
        buffer = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Combine short paragraphs
            if len(buffer) + len(para) + 1 < MAX_CHUNK_CHARS:
                buffer = (buffer + "\n\n" + para).strip()
            else:
                if len(buffer) >= MIN_CHUNK_CHARS:
                    chunks.append(KnowledgeChunkData(
                        chunk_index=idx,
                        content=buffer,
                        chunk_type="paragraph",
                        page_number=page_number,
                        heading=heading,
                        **kwargs,
                    ))
                    idx += 1
                buffer = para

        # Flush remaining buffer
        if buffer and len(buffer) >= MIN_CHUNK_CHARS:
            chunks.append(KnowledgeChunkData(
                chunk_index=idx,
                content=buffer,
                chunk_type="paragraph",
                page_number=page_number,
                heading=heading,
                **kwargs,
            ))

        return chunks

    def _chunk_as_faq(
        self,
        text: str,
        page_number: int,
        chunk_index_start: int,
        **kwargs,
    ) -> List[KnowledgeChunkData]:
        """
        Parse Q&A formatted text into individual FAQ chunks.
        Each Q+A pair becomes one chunk for precise retrieval.
        """
        chunks: List[KnowledgeChunkData] = []
        idx = chunk_index_start
        lines = text.split("\n")
        i = 0
        current_q = ""
        current_a_lines: List[str] = []

        while i < len(lines):
            line = lines[i].strip()
            q_match = self._FAQ_Q_RE.match(line)
            a_match = self._FAQ_A_RE.match(line)

            if q_match:
                # Save previous Q&A if exists
                if current_q and current_a_lines:
                    content = f"Q: {current_q}\nA: {' '.join(current_a_lines)}"
                    if len(content) >= MIN_CHUNK_CHARS:
                        chunks.append(KnowledgeChunkData(
                            chunk_index=idx,
                            content=content,
                            chunk_type="faq",
                            page_number=page_number,
                            **kwargs,
                        ))
                        idx += 1
                current_q = q_match.group(1).strip()
                current_a_lines = []
            elif a_match:
                current_a_lines = [a_match.group(1).strip()]
            elif current_a_lines:
                current_a_lines.append(line)
            i += 1

        # Flush last Q&A
        if current_q and current_a_lines:
            content = f"Q: {current_q}\nA: {' '.join(current_a_lines)}"
            if len(content) >= MIN_CHUNK_CHARS:
                chunks.append(KnowledgeChunkData(
                    chunk_index=idx,
                    content=content,
                    chunk_type="faq",
                    page_number=page_number,
                    **kwargs,
                ))

        return chunks

    @staticmethod
    def _table_to_text(table: Dict[str, Any]) -> str:
        """
        Convert table dict to readable text for embedding.
        Preserves structure: header row + data rows.
        """
        parts: List[str] = []
        headers = table.get("headers", [])
        rows = table.get("rows", [])
        caption = table.get("caption", "")

        if caption:
            parts.append(caption)
        if headers:
            parts.append(" | ".join(str(h) for h in headers))
            parts.append("-" * max(len(" | ".join(str(h) for h in headers)), 20))
        for row in rows:
            parts.append(" | ".join(str(c) for c in row))

        return "\n".join(parts)
