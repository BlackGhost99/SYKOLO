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
        return self.get_response(request)
