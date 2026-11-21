"""Non-persistent file preflight for YEM Intelligence document intake.

This module does NOT parse PDF structures, decode images, perform OCR, store
uploads, contact a provider or assert that a file is malware-free. It only
checks the bounded byte stream before a future, isolated extractor may run.
"""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import PurePosixPath

MAX_DOCUMENT_BYTES = 5 * 1024 * 1024
SUPPORTED_EXTENSIONS = {
    ".pdf": ("pdf", "application/pdf"),
    ".png": ("png", "image/png"),
    ".jpg": ("jpeg", "image/jpeg"),
    ".jpeg": ("jpeg", "image/jpeg"),
}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class DocumentPreflightError(ValueError):
    """User-safe refusal without echoing filenames or uploaded contents."""


@dataclass(frozen=True)
class DocumentPreflight:
    kind: str
    media_type: str
    size_bytes: int
    sha256: str
    extraction_status: str = "not_performed"
    persistence_status: str = "not_stored"
    external_provider_used: bool = False
    needs_human_validation: bool = True

    def metadata(self):
        """Internal metadata only; the digest is not a public lookup key."""
        return {
            "kind": self.kind,
            "media_type": self.media_type,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "extraction_status": self.extraction_status,
            "persistence_status": self.persistence_status,
            "external_provider_used": self.external_provider_used,
            "needs_human_validation": self.needs_human_validation,
        }


def inspect_document(upload):
    """Inspect an uploaded PDF, PNG or JPEG without parsing or retaining it.

    The input is a server-side binary file object with a name and read().
    Reading is strictly capped and the previous stream position is restored
    whenever the source is seekable. File headers are type hints, NOT proof
    that the document is structurally valid or safe to render.
    """
    name = getattr(upload, "name", None)
    if not isinstance(name, str) or not 1 <= len(name) <= 255:
        raise DocumentPreflightError("Nom de fichier invalide.")
    if any(ord(char) < 32 or ord(char) == 127 for char in name):
        raise DocumentPreflightError("Nom de fichier invalide.")
    extension = PurePosixPath(name.replace("\\", "/")).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise DocumentPreflightError("Formats autorisés : PDF, PNG et JPEG.")
    if not callable(getattr(upload, "read", None)):
        raise DocumentPreflightError("Fichier illisible.")

    position = None
    try:
        if callable(getattr(upload, "tell", None)):
            position = upload.tell()
        if callable(getattr(upload, "seek", None)):
            upload.seek(0)
        data = upload.read(MAX_DOCUMENT_BYTES + 1)
    except (OSError, ValueError, TypeError):
        raise DocumentPreflightError("Fichier illisible.") from None
    finally:
        if position is not None and callable(getattr(upload, "seek", None)):
            try:
                upload.seek(position)
            except (OSError, ValueError):
                pass

    if not isinstance(data, bytes) or not 12 <= len(data) <= MAX_DOCUMENT_BYTES:
        raise DocumentPreflightError("Fichier vide, non binaire ou supérieur à 5 Mio.")

    if data.startswith(b"%PDF-"):
        detected = "pdf"
    elif data.startswith(PNG_SIGNATURE):
        detected = "png"
    elif data.startswith(b"\xff\xd8\xff"):
        detected = "jpeg"
    else:
        raise DocumentPreflightError("Signature de document non reconnue.")

    kind, media_type = SUPPORTED_EXTENSIONS[extension]
    if kind != detected:
        raise DocumentPreflightError("Le type réel ne correspond pas à l'extension.")
    return DocumentPreflight(kind=kind, media_type=media_type,
                             size_bytes=len(data), sha256=sha256(data).hexdigest())
