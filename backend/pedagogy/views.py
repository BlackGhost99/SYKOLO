import json
import os
from pathlib import Path
from django.conf import settings
from django.db import connection, DatabaseError
from django.http import JsonResponse, FileResponse
from django.core.exceptions import RequestDataTooBig
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from .domain import evaluate, validate_policy, ValidationError

PRESETS = json.loads(
    (Path(__file__).parent / "presets.json").read_text(encoding="utf-8")
)


@require_GET
@ensure_csrf_cookie
def index(request):
    index_file = settings.ROOT_DIR / "dist" / "index.html"
    if not index_file.exists():
        return JsonResponse(
            {"error": "Construire le frontend avec npm run build."}, status=503
        )
    return FileResponse(index_file.open("rb"), content_type="text/html; charset=utf-8")


@require_GET
def health(request):
    return JsonResponse(
        {
            "status": "ok",
            "product": "YEM",
            "version": "0.4.0",
            "commit": os.environ.get("RENDER_GIT_COMMIT", "local"),
            "environment": settings.ENVIRONMENT,
            "stack": {
                "api": "django",
                "frontend": "react",
                "database": "postgresql"
                if connection.vendor == "postgresql"
                else connection.vendor,
            },
        }
    )


@require_GET
def ready(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            if cursor.fetchone()[0] != 1:
                raise DatabaseError()
        return JsonResponse({"status": "ready", "database": connection.vendor})
    except DatabaseError:
        return JsonResponse({"status": "unavailable"}, status=503)


@require_GET
@ensure_csrf_cookie
def preset_list(request):
    return JsonResponse(PRESETS, safe=False)


def parse(request):
    if request.content_type != "application/json":
        return None, JsonResponse({"error": "Format JSON requis."}, status=415)
    try:
        if int(request.META.get("CONTENT_LENGTH") or 0) > 65536:
            raise RequestDataTooBig()
        body = request.body
        if len(body) > 65536:
            raise RequestDataTooBig()
        return json.loads(body, parse_constant=lambda _: fail_json()), None
    except RequestDataTooBig:
        return None, JsonResponse(
            {"error": "Configuration trop volumineuse."}, status=413
        )
    except (ValueError, UnicodeDecodeError):
        return None, JsonResponse({"error": "JSON invalide."}, status=400)


def fail_json():
    raise ValueError("JSON invalide")


@require_POST
def validate(request):
    data, error = parse(request)
    if error is not None:
        return error
    try:
        validate_policy(data)
        return JsonResponse({"valid": True})
    except (ValidationError, TypeError) as error:
        return JsonResponse({"error": str(error)}, status=422)


@require_POST
def simulate(request):
    data, error = parse(request)
    if error is not None:
        return error
    try:
        if not isinstance(data, dict):
            raise ValidationError("Requête invalide.")
        return JsonResponse(evaluate(data.get("policy"), data.get("entries")))
    except (ValidationError, TypeError) as error:
        return JsonResponse({"error": str(error)}, status=422)
