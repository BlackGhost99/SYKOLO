"""P1a document preflight: tests use synthetic bytes only."""
from hashlib import sha256
from io import BytesIO
from unittest import TestCase

from .intelligence_document_preflight import (
    MAX_DOCUMENT_BYTES, DocumentPreflightError, inspect_document,
)


class NamedBytes(BytesIO):
    def __init__(self, name, data):
        super().__init__(data)
        self.name = name


class DocumentPreflightTests(TestCase):
    def test_accepts_supported_headers_without_extraction(self):
        samples = (
            ("registre.pdf", b"%PDF-1.7\n" + b"synthetic", "pdf", "application/pdf"),
            ("fiche.PNG", b"\x89PNG\r\n\x1a\n" + b"synthetic", "png", "image/png"),
            ("photo.jpg", b"\xff\xd8\xff\xe0" + b"synthetic", "jpeg", "image/jpeg"),
            ("photo.jpeg", b"\xff\xd8\xff\xe0" + b"synthetic", "jpeg", "image/jpeg"),
        )
        for name, raw, kind, media_type in samples:
            with self.subTest(name=name):
                upload = NamedBytes(name, raw)
                upload.seek(3)
                result = inspect_document(upload)
                self.assertEqual(result.kind, kind)
                self.assertEqual(result.media_type, media_type)
                self.assertEqual(result.sha256, sha256(raw).hexdigest())
                self.assertEqual(result.size_bytes, len(raw))
                self.assertEqual(upload.tell(), 3)
                self.assertEqual(result.extraction_status, "not_performed")
                self.assertEqual(result.persistence_status, "not_stored")
                self.assertFalse(result.external_provider_used)
                self.assertTrue(result.needs_human_validation)

    def test_refuses_disguised_extension_and_unrecognized_payload(self):
        cases = (
            ("invoice.pdf.exe", b"%PDF-1.7\nsynthetic"),
            ("macro.docm", b"%PDF-1.7\nsynthetic"),
            ("invoice.pdf", b"\x89PNG\r\n\x1a\nsynthetic"),
            ("invoice.png", b"%PDF-1.7\nsynthetic"),
            ("invoice.pdf", b"<script>invalid</script>"),
            ("invoice.jpg", b"fake jpg header"),
            ("invoice.pdf", b""),
            ("bad\nname.pdf", b"%PDF-1.7\nsynthetic"),
        )
        for name, raw in cases:
            with self.subTest(name=name):
                with self.assertRaises(DocumentPreflightError):
                    inspect_document(NamedBytes(name, raw))

    def test_size_limit_and_binary_only(self):
        with self.assertRaises(DocumentPreflightError):
            inspect_document(NamedBytes("large.pdf", b"%PDF-1.7\n" + b"x" * MAX_DOCUMENT_BYTES))
        with self.assertRaises(DocumentPreflightError):
            inspect_document(NamedBytes("small.pdf", b"%PDF-1.7"))
        with self.assertRaises(DocumentPreflightError):
            inspect_document(NamedBytes("text.pdf", b"not a pdf stream"))

    def test_metadata_never_contains_original_filename_or_content(self):
        result = inspect_document(NamedBytes("nom eleve confidentiel.pdf", b"%PDF-1.7\nsynthetic"))
        output = result.metadata()
        self.assertEqual(output["sha256"], sha256(b"%PDF-1.7\nsynthetic").hexdigest())
        self.assertNotIn("name", output)
        self.assertNotIn("content", output)
        self.assertNotIn("nom eleve confidentiel", str(output))

    def test_preflight_does_not_modify_uploaded_stream(self):
        upload = NamedBytes("registre.pdf", b"%PDF-1.7\nsynthetic")
        upload.seek(4)
        inspect_document(upload)
        self.assertEqual(upload.tell(), 4)
        self.assertEqual(upload.read(), b"-1.7\nsynthetic")
