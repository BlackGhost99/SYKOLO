"""PWA must be installable without caching any confidential school data."""
import json
import struct
from pathlib import Path
from unittest import skipUnless

from django.conf import settings
from django.test import Client, SimpleTestCase

DIST=Path(settings.ROOT_DIR) / "dist"


@skipUnless((DIST/"manifest.webmanifest").is_file(), "npm run build required")
class PWAReleaseTests(SimpleTestCase):
    def setUp(self):
        self.client=Client()

    def test_manifest_is_valid_and_icons_are_real_pictures(self):
        response=self.client.get("/manifest.webmanifest")
        self.assertEqual(response.status_code,200)
        manifest=json.loads(b"".join(response.streaming_content))
        self.assertEqual(manifest["display"],"standalone")
        self.assertEqual(manifest["scope"],"/")
        expected={"192x192","512x512"}
        self.assertEqual({x["sizes"] for x in manifest["icons"]},expected)
        for size in (192,512):
            response=self.client.get("/icons/icon-"+str(size)+".png")
            self.assertEqual(response.status_code,200)
            self.assertEqual(response["Content-Type"],"image/png")
            blob=b"".join(response.streaming_content)
            self.assertTrue(blob.startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertEqual(struct.unpack(">II",blob[16:24]),(size,size))

    def test_service_worker_is_restricted_to_static_assets_and_online_html(self):
        response=self.client.get("/service-worker.js")
        self.assertEqual(response.status_code,200)
        self.assertEqual(response["Service-Worker-Allowed"],"/")
        self.assertIn("no-store",response["Cache-Control"])
        source=b"".join(response.streaming_content).decode("utf8")
        self.assertIn('startsWith("/api/")',source)
        self.assertIn('request.mode==="navigate"',source)
        self.assertNotIn("cache.put(request)",source.split('if(request.mode==="navigate")')[0])
        self.assertIn("caches.match(\"/offline.html\")",source)

    def test_private_api_still_requires_authentication(self):
        response=self.client.get("/api/v1/parents/family-children")
        self.assertEqual(response.status_code,401)
        response=self.client.get("/api/v1/parents/applications")
        self.assertEqual(response.status_code,401)
