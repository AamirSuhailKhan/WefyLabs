"""
OCR Provider Abstraction
=========================
Pluggable OCR backend for scanned PDFs and image documents.

Implementations:
  TesseractOCRProvider — local open-source OCR (free, zero API cost)
  MockOCRProvider     — deterministic test responses

OCR output retains:
  - Extracted text per page
  - Confidence score per page (0-1)
  - Source coordinates when available (for table/field location)

Design:
  - If OCR confidence < threshold, field is marked UNVERIFIED
  - If OCR engine is missing, returns an honest error (never fake text)
"""
from __future__ import annotations

import io
import os
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class OCRWord:
    """A single word extracted by OCR with confidence and coordinates."""
    text: str
    confidence: float           # 0-1
    bounding_box: Optional[Dict[str, float]] = None
    # {left, top, width, height} in relative coordinates (0-1)


@dataclass
class OCRPage:
    """OCR result for a single page."""
    page_number: int
    text: str                          # Full extracted text for the page
    confidence: float                  # Average confidence for the page (0-1)
    words: List[OCRWord] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    # tables extracted by OCR: [{headers, rows}]


@dataclass
class OCRResult:
    """Complete OCR output for a document."""
    provider: str
    total_pages: int
    pages: List[OCRPage]
    full_text: str
    average_confidence: float
    cost_pages: int = 0               # Billable pages (0 for local OCR)
    raw_response: Optional[Dict] = None   # Provider-specific raw output


# ─── Abstract Interface ────────────────────────────────────────────────────────

class OCRProvider(ABC):
    """
    Abstract OCR provider.
    Implementations are plugged in via KnowledgeProvider config.
    """
    provider_name: str = "abstract"

    @abstractmethod
    async def extract(
        self,
        content: bytes,
        mime_type: str = "application/pdf",
        language_hint: Optional[str] = None,
    ) -> OCRResult:
        """
        Run OCR on document bytes.
        Returns OCRResult with per-page confidence.
        Low confidence → caller marks extracted fields as UNVERIFIED.
        """
        ...

    @classmethod
    def is_low_confidence(cls, confidence: float, threshold: float = 0.7) -> bool:
        """Returns True if confidence is below acceptable threshold."""
        return confidence < threshold


# ─── Local Open-Source Tesseract OCR Provider ────────────────────────────────

class TesseractOCRProvider(OCRProvider):
    """
    Local Tesseract OCR provider (Apache 2.0 open-source).
    Requires: pytesseract and Pillow (PIL).
    Zero API cost, processes scanned documents and images locally.
    """
    provider_name = "tesseract"

    def __init__(self, tesseract_cmd: Optional[str] = None, default_lang: str = "eng"):
        self._tesseract_cmd = tesseract_cmd
        self._default_lang = default_lang

    def _preprocess_image(self, image):
        """Preprocesses image to enhance OCR accuracy (grayscale, contrast)."""
        try:
            from PIL import ImageOps, ImageEnhance
            # Convert to grayscale
            gray = ImageOps.grayscale(image)
            # Enhance contrast
            enhancer = ImageEnhance.Contrast(gray)
            enhanced = enhancer.enhance(1.8)
            return enhanced
        except Exception:
            return image

    async def extract(
        self,
        content: bytes,
        mime_type: str = "application/pdf",
        language_hint: Optional[str] = None,
    ) -> OCRResult:
        import asyncio

        lang = language_hint or self._default_lang
        if lang in ("hi", "hin", "hindi"):
            lang = "hin+eng"
        elif lang in ("en", "eng", "english"):
            lang = "eng"

        def _do_ocr() -> OCRResult:
            try:
                import pytesseract
                from PIL import Image
            except ImportError:
                logger.error("[OCR:Tesseract] pytesseract or Pillow not installed.")
                return OCRResult(
                    provider=self.provider_name,
                    total_pages=0,
                    pages=[],
                    full_text="",
                    average_confidence=0.0,
                    raw_response={"error": "pytesseract or Pillow is not installed."}
                )

            cmd = self._tesseract_cmd or os.getenv("TESSERACT_CMD")
            if not cmd and os.name == "nt":
                for p in (
                    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
                ):
                    if os.path.exists(p):
                        cmd = p
                        break
            if cmd:
                pytesseract.pytesseract.tesseract_cmd = cmd
                tessdata_dir = os.path.join(os.path.dirname(cmd), "tessdata")
                if os.path.exists(tessdata_dir) and "TESSDATA_PREFIX" not in os.environ:
                    os.environ["TESSDATA_PREFIX"] = tessdata_dir

            images = []
            if mime_type.startswith("image/"):
                try:
                    img = Image.open(io.BytesIO(content))
                    images.append(img)
                except Exception as e:
                    logger.error(f"[OCR:Tesseract] Failed to load image: {e}")
                    return OCRResult(
                        provider=self.provider_name,
                        total_pages=0,
                        pages=[],
                        full_text="",
                        average_confidence=0.0,
                        raw_response={"error": f"Invalid image format: {e}"}
                    )
            elif mime_type == "application/pdf":
                # For PDF bytes in local OCR, attempt to render pages or extract images
                try:
                    import fitz  # PyMuPDF
                    doc = fitz.open(stream=content, filetype="pdf")
                    for page_num in range(len(doc)):
                        page = doc[page_num]
                        pix = page.get_pixmap(dpi=200)
                        img = Image.open(io.BytesIO(pix.tobytes("png")))
                        images.append(img)
                except Exception:
                    # Fallback: treat raw bytes if image-like or try pdf2image
                    try:
                        from pdf2image import convert_from_bytes
                        images = convert_from_bytes(content)
                    except Exception as e:
                        logger.warning(f"[OCR:Tesseract] PDF rendering for OCR not available: {e}")

            if not images:
                return OCRResult(
                    provider=self.provider_name,
                    total_pages=0,
                    pages=[],
                    full_text="",
                    average_confidence=0.0,
                    raw_response={"error": "No processable image layers found for OCR."}
                )

            pages_out = []
            full_texts = []
            confidences = []

            for idx, img in enumerate(images, 1):
                try:
                    preprocessed = self._preprocess_image(img)
                    
                    # Extract OCR text and word data with confidence
                    data = pytesseract.image_to_data(
                        preprocessed, 
                        lang=lang, 
                        output_type=pytesseract.Output.DICT
                    )
                    
                    page_words = []
                    page_text_parts = []
                    word_confs = []

                    n_boxes = len(data.get("text", []))
                    w_img, h_img = img.size

                    for b in range(n_boxes):
                        w_text = data["text"][b].strip()
                        raw_conf = data["conf"][b]
                        
                        if w_text:
                            page_text_parts.append(w_text)
                            conf_float = max(0.0, min(1.0, float(raw_conf) / 100.0)) if float(raw_conf) >= 0 else 0.5
                            word_confs.append(conf_float)
                            
                            left = data["left"][b] / max(w_img, 1)
                            top = data["top"][b] / max(h_img, 1)
                            width = data["width"][b] / max(w_img, 1)
                            height = data["height"][b] / max(h_img, 1)

                            page_words.append(OCRWord(
                                text=w_text,
                                confidence=conf_float,
                                bounding_box={"left": left, "top": top, "width": width, "height": height}
                            ))

                    page_full_text = " ".join(page_text_parts)
                    avg_p_conf = sum(word_confs) / len(word_confs) if word_confs else (0.85 if page_full_text else 0.0)

                    pages_out.append(OCRPage(
                        page_number=idx,
                        text=page_full_text,
                        confidence=round(avg_p_conf, 2),
                        words=page_words
                    ))
                    full_texts.append(page_full_text)
                    confidences.append(avg_p_conf)
                except Exception as page_exc:
                    logger.error(f"[OCR:Tesseract] Error processing page {idx}: {page_exc}")
                    # If Tesseract binary is not installed on system
                    if "tesseract is not installed" in str(page_exc).lower() or "not found" in str(page_exc).lower():
                        return OCRResult(
                            provider=self.provider_name,
                            total_pages=0,
                            pages=[],
                            full_text="",
                            average_confidence=0.0,
                            raw_response={"error": "Tesseract OCR engine is not installed or available on this system."}
                        )

            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
            return OCRResult(
                provider=self.provider_name,
                total_pages=len(pages_out),
                pages=pages_out,
                full_text="\n\n".join(full_texts),
                average_confidence=round(avg_conf, 2),
                cost_pages=0
            )

        return await asyncio.to_thread(_do_ocr)


# ─── Mock OCR Provider (Tests) ────────────────────────────────────────────────

class MockOCRProvider(OCRProvider):
    """
    Deterministic mock OCR for unit tests.
    Returns configurable fixed text with high confidence by default.
    """
    provider_name = "mock"

    def __init__(
        self,
        fixed_text: str = "Mock OCR extracted text.",
        confidence: float = 0.95,
    ):
        self._fixed_text = fixed_text
        self._confidence = confidence

    async def extract(
        self,
        content: bytes,
        mime_type: str = "application/pdf",
        language_hint: Optional[str] = None,
    ) -> OCRResult:
        page = OCRPage(
            page_number=1,
            text=self._fixed_text,
            confidence=self._confidence,
        )
        return OCRResult(
            provider=self.provider_name,
            total_pages=1,
            pages=[page],
            full_text=self._fixed_text,
            average_confidence=self._confidence,
            cost_pages=0,
        )


# ─── Factory ──────────────────────────────────────────────────────────────────

def get_ocr_provider(
    provider_name: str = "tesseract",
    config: Optional[Dict[str, Any]] = None,
) -> OCRProvider:
    """Resolve OCR provider by name. Defaults to Tesseract."""
    config = config or {}
    if provider_name in ("tesseract", "local", "auto"):
        return TesseractOCRProvider(
            tesseract_cmd=config.get("tesseract_cmd"),
            default_lang=config.get("default_lang", "eng")
        )
    if provider_name == "mock":
        return MockOCRProvider(
            fixed_text=config.get("fixed_text", "Mock OCR extracted text."),
            confidence=config.get("confidence", 0.95),
        )
    logger.warning(
        f"[OCR FACTORY] Unknown provider '{provider_name}', falling back to Tesseract OCR"
    )
    return TesseractOCRProvider()
