class ResponseHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        )
        if not request.path.startswith("/assets/"):
            response.setdefault("Cache-Control", "no-store")
        return response


class SchoolSessionMiddleware:
    """Bind every school request, including legacy routes, to the login tenant."""
    _PUBLIC_FAMILY_PATHS = {
        "/api/v1/parents/catalog",
        "/api/v1/parents/paycentral/webhook",
        "/api/v1/parents/singpay/webhook",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        import re
        from django.http import JsonResponse
        from institutions.services import school_access
        tenant = request.session.get("school_id")
        if tenant and request.user.is_authenticated:
            if not school_access(request.user, tenant):
                request.session.flush()
                return JsonResponse({"error": "Accès à l'établissement retiré."}, status=401)
            match = re.match(r"/api/v1/schools/([^/]+)(?:/|$)", request.path)
            if (match and match.group(1) != tenant) or request.path.startswith(("/api/v1/platform/", "/api/v1/organizations")):
                return JsonResponse({"error": "Session limitée à l'établissement choisi."}, status=403)
        path = request.path_info.rstrip("/")
        if (path.startswith("/api/v1/parents/") and path not in self._PUBLIC_FAMILY_PATHS
                and request.user.is_authenticated):
            from institutions.models import SchoolMember
            # Older school-issued parent accounts can still sign in with a school code.
            if request.user.is_superuser or (tenant and not SchoolMember.objects.filter(
                user=request.user, school_id=tenant, active=True,
                role__school_id=tenant, role__code="parent",
            ).exists()):
                return JsonResponse({"error": "Cette action est réservée à l’espace familles."},
                                    status=403, headers={"Cache-Control": "no-store"})
        return self.get_response(request)


class SchoolCycleBoundaryMiddleware:
    """Refuser toutes les routes non auditées pour un compte limité à des cycles.

    Une simple liste de permissions ne peut pas filtrer des dossiers à elle seule.
    Uniquement les routes explicitement filtrées côté requête sont autorisées.
    """
    _UUID = r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}"
    _ALLOW_GET = (
        r"my-access",
        r"academic/(?:years|cycles|levels|tracks|classes)",
        rf"academic/(?:years|cycles|levels|tracks|classes)/{_UUID}",
        r"students",
        rf"students/{_UUID}",
        rf"students/{_UUID}/guardians",
        r"enrollments",
        rf"enrollments/{_UUID}",
        r"staff/onboard",
        r"staff/me/assignments",
        r"staff/me/dossier",
        r"organization/my-appointments",
    )
    _ALLOW_POST = (r"staff/onboard",)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        import re
        from django.http import JsonResponse
        from institutions.cycle_scope import scoped_cycle_ids
        from institutions.services import school_access

        match = re.fullmatch(
            rf"/api/v1/schools/({self._UUID})(?:/(.*?))?/?", request.path
        )
        if match and request.user.is_authenticated and request.user.is_active:
            school = school_access(request.user, match.group(1))
            if school is not None and scoped_cycle_ids(request.user, school) is not None:
                suffix = (match.group(2) or "").rstrip("/")
                patterns = self._ALLOW_GET if request.method == "GET" else (
                    self._ALLOW_POST if request.method == "POST" else ()
                )
                if not any(re.fullmatch(pattern, suffix) for pattern in patterns):
                    return JsonResponse({
                        "error": "Ce module n'est pas encore sécurisé pour l'accès limité par cycle."
                    }, status=403)
        return self.get_response(request)


class ClosedYearWriteErrorMiddleware:
    """Translate an uncaught PostgreSQL year-archive trigger into an API conflict.

    Only the named database guard is handled; unrelated integrity errors still
    propagate normally. This is intentionally process_exception middleware,
    because Django converts view exceptions into responses inside __call__.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        from django.db import IntegrityError
        from django.http import JsonResponse
        if (isinstance(exception, IntegrityError)
                and "Année scolaire clôturée" in str(exception)
                and request.path.startswith("/api/v1/")):
            return JsonResponse({
                "error": "Année scolaire clôturée : les écritures historiques sont interdites."
            }, status=409)
        return None
