"""
Document Parsing Service
=========================
Orchestrates the full document parsing workflow for a given document.

This service is called by the Celery parse worker and coordinates:
  1. Load file bytes from storage
  2. Select appropriate parser based on MIME type
  3. Run parser → ParsedDocument
  4. If confidence < threshold → flag for OCR
  5. Return ParsedDocument for downstream chunking / extraction

Parsers are resolved from ProviderRegistry (supports per-org overrides).

Design notes:
  - This service is stateless; all state is stored in KnowledgeDocument / DB.
  - ParsedDocument is an in-memory object; it is NOT persisted to DB.
    Only metadata (page count, OCR flag, confidence) is stored on the document.
  - Tables from parsing flow into both: (a) chunking as preserved blocks,
    (b) fact extraction as structured input.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.providers.document_parser import (
    DocumentParser, ParsedDocument, get_parser
)
from app.modules.knowledge.ingestion.storage_service import get_storage_provider

logger = logging.getLogger(__name__)

# If parser confidence is below this threshold, flag document for OCR
OCR_CONFIDENCE_THRESHOLD = 0.6


class DocumentParsingService:
    """
    Coordinates document parsing for the knowledge pipeline.
    Used by: Celery `process_document` task.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def parse_document(
        self,
        document_id: str,
        organization_id: str,
        storage_key: str,
        storage_provider_name: str,
        mime_type: str,
        file_name: str,
    ) -> ParsedDocument:
        """
        Parse a document file and return a ParsedDocument.

        Steps:
          1. Retrieve file bytes from storage
          2. Resolve parser for MIME type
          3. Execute parse
          4. Validate confidence and flag OCR if needed

        Returns:
            ParsedDocument — in-memory result with full text, pages, tables, metadata.

        Raises:
            ValueError: if no parser found or parsing fails critically.
        """
        start = time.monotonic()

        # ── Step 1: Retrieve file ─────────────────────────────────────────────
        storage = get_storage_provider(storage_provider_name)
        try:
            content = await storage.retrieve(storage_key)
        except FileNotFoundError:
            raise ValueError(
                f"Document file not found in storage: key={storage_key}"
            )

        logger.info(
            f"[PARSING] doc={document_id} file={file_name} "
            f"size={len(content):,} bytes mime={mime_type}"
        )

        # ── Step 2: Resolve parser ────────────────────────────────────────────
        parser = get_parser(mime_type, file_name)
        if parser is None:
            raise ValueError(
                f"No document parser available for MIME type: {mime_type} "
                f"file: {file_name}"
            )

        logger.info(
            f"[PARSING] Using parser: {parser.parser_name} "
            f"for doc={document_id}"
        )

        # ── Step 3: Parse ─────────────────────────────────────────────────────
        try:
            parsed = await parser.parse(content, file_name)
        except Exception as exc:
            logger.error(
                f"[PARSING FAILED] doc={document_id} "
                f"parser={parser.parser_name}: {exc}",
                exc_info=True,
            )
            raise ValueError(f"Document parsing failed: {exc}") from exc

        # ── Step 4: OCR flag assessment ───────────────────────────────────────
        if parsed.confidence < OCR_CONFIDENCE_THRESHOLD and not parsed.requires_ocr:
            logger.info(
                f"[PARSING] Low confidence ({parsed.confidence:.2f}) on "
                f"doc={document_id} — flagging for OCR review."
            )
            parsed.requires_ocr = True

        elapsed = time.monotonic() - start
        logger.info(
            f"[PARSING COMPLETE] doc={document_id} "
            f"pages={parsed.total_pages} "
            f"chars={len(parsed.full_text):,} "
            f"tables={len(parsed.tables)} "
            f"confidence={parsed.confidence:.2f} "
            f"ocr={parsed.requires_ocr} "
            f"{elapsed:.2f}s"
        )

        return parsed

    def extract_table_summary(self, parsed: ParsedDocument) -> List[Dict[str, Any]]:
        """
        Returns a lightweight summary of all tables found in the document.
        Used for logging and metadata storage.
        """
        summaries = []
        for i, table in enumerate(parsed.tables):
            summaries.append({
                "index": i,
                "caption": table.get("caption", ""),
                "row_count": len(table.get("rows", [])),
                "column_count": len(table.get("headers", [])),
                "page": table.get("page_number"),
            })
        return summaries

    def extract_language_hint(self, parsed: ParsedDocument) -> str:
        """
        Detect the dominant language from parsed text (first 2000 chars).
        Falls back to 'en' if detection fails or text is too short.
        """
        sample = parsed.full_text[:2000].strip()
        if not sample or len(sample) < 50:
            return "en"

        # Simple heuristic: Arabic script detection
        arabic_chars = sum(1 for c in sample if "\u0600" <= c <= "\u06FF")
        if arabic_chars / max(len(sample), 1) > 0.15:
            return "ar"

        # Hindi/Urdu
        devanagari_chars = sum(1 for c in sample if "\u0900" <= c <= "\u097F")
        if devanagari_chars / max(len(sample), 1) > 0.10:
            return "hi"

        return "en"
