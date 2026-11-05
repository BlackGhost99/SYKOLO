"""Serve only explicitly allowlisted public PWA assets from the Vite dist.

Never expose source paths, user documents, or private API responses to a
service-worker cache. Django owns the root origin; Vite serves these in dev.
"""
from pathlib import Path
from django.conf import settings
from django.http import FileResponse, Http404
from django.views.decorators.http import require_GET

PUBLIC = {
    "manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
    "service-worker.js": ("service-worker.js", "application/javascript"),
    "offline.html": ("offline.html", "text/html; charset=utf-8"),
    "icons/icon-192.png": ("icons/icon-192.png", "image/png"),
    "icons/icon-512.png": ("icons/icon-512.png", "image/png"),
}

@require_GET
def pwa_asset(request, name):
    if name not in PUBLIC:
        raise Http404()
    relative, content_type = PUBLIC[name]
    path = Path(settings.ROOT_DIR) / "dist" / relative
    if not path.is_file():
        raise Http404()
    response = FileResponse(path.open("rb"), content_type=content_type)
    response["X-Content-Type-Options"] = "nosniff"
    if name == "service-worker.js":
        response["Service-Worker-Allowed"] = "/"
        response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    elif name.startswith("icons/"):
        response["Cache-Control"] = "public, max-age=86400"
    else:
        response["Cache-Control"] = "no-cache"
    return response
