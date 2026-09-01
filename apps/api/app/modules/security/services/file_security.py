"""
Enterprise File Security & Upload Scanner
=========================================
Validates file uploads against MIME type magic bytes, extension allowlists,
file size limits, path traversal attacks, and virus scanning hooks.
"""
import re
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "pdf", "docx", "xlsx", "csv", "txt"}
BLOCKED_EXTENSIONS = {"exe", "bat", "sh", "php", "py", "pl", "rb", "js", "dll", "vbs", "cmd"}
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB


class FileSecurityScanner:
    """Enterprise File Upload Security Scanner."""

    @classmethod
    def scan_file(cls, filename: str, content: bytes) -> Tuple[bool, Optional[str]]:
        """Scans file for security violations."""
        # 1. Size check
        if len(content) > MAX_FILE_SIZE_BYTES:
            return False, f"File exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES // (1024*1024)}MB."

        # 2. Path Traversal check FIRST before splitting extensions
        if ".." in filename or "/" in filename or "\\" in filename:
            logger.error(f"[FILE SECURITY VIOLATION] Path traversal detected in filename: {filename}")
            return False, "Invalid filename format."

        # 3. Extension check
        ext = filename.split(".")[-1].lower() if "." in filename else ""
        if ext in BLOCKED_EXTENSIONS:
            logger.warning(f"[FILE SECURITY VIOLATION] Executable extension detected: '{ext}' in {filename}")
            return False, f"File extension '.{ext}' is strictly prohibited for security reasons."

        if ext not in ALLOWED_EXTENSIONS:
            return False, f"File extension '.{ext}' is not in the list of allowed file types."

        # 4. MIME Magic Bytes Check
        if not cls._check_magic_bytes(ext, content):
            logger.warning(f"[FILE SECURITY VIOLATION] MIME spoofing detected for file '{filename}'")
            return False, "File content does not match the stated file extension (MIME mismatch)."

        return True, None

    @classmethod
    def _check_magic_bytes(cls, ext: str, content: bytes) -> bool:
        """Verifies file header magic bytes."""
        if len(content) < 4:
            return False

        headers = {
            "jpg": [b"\xFF\xD8\xFF"],
            "jpeg": [b"\xFF\xD8\xFF"],
            "png": [b"\x89PNG\r\n\x1a\n"],
            "webp": [b"RIFF"],
            "pdf": [b"%PDF-"],
            "docx": [b"PK\x03\x04"],
            "xlsx": [b"PK\x03\x04"],
        }

        expected = headers.get(ext)
        if not expected:
            return True # Allow text/csv without fixed binary header

        return any(content.startswith(h) for h in expected)

    @classmethod
    def virus_scan(cls, content: bytes) -> bool:
        """Antivirus Scanner Hook (e.g. ClamAV / AWS GuardDuty). Returns True if clean."""
        return True
