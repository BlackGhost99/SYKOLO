from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from accounts.views import authorized

from .models import School
from .services import has_permission
from .student_models import StudentNumbering
from .student_numbering import MAX_NUMBER, largest_number, render_code
from .views import access, log_event, parse_body, refuse


def preview(school, saved, values):
    maximum = largest_number(values["template"], school.students.values_list("student_code", flat=True).iterator())
    previous = saved.next_number if saved.pk and saved.template.casefold() == values["template"].casefold() else 0
    number = max(values["start_number"], maximum + 1, previous)
    return {
        "enabled": values["enabled"], "template": values["template"], "digits": values["digits"],
        "revision": saved.revision if saved.pk else 0, "largest_number": str(maximum) if maximum >= 0 else None,
        "next_number": number if number <= MAX_NUMBER else None,
        "next_code": render_code(values["template"], values["digits"], number)
        if values["enabled"] and number <= MAX_NUMBER else None,
    }


def clean_rule(body):
    if set(body) != {"enabled", "template", "digits", "start_number", "revision"}:
        raise ValueError("Paramètres de numérotation incomplets.")
    template = body["template"]
    if not isinstance(template, str) or len(template) > 38 or not template.isprintable() or template.count("{n}") != 1:
        raise ValueError("Le format doit contenir exactement une fois {n} et au plus 35 caractères fixes.")
    fixed = template.replace("{n}", "")
    if "{" in fixed or "}" in fixed or template != template.strip():
        raise ValueError("Format invalide. Les accolades sont réservées à {n} et les espaces aux séparateurs intérieurs.")
    if type(body["enabled"]) is not bool:
        raise ValueError("Mode de numérotation invalide.")
    for key, minimum, maximum in (("digits", 1, 15), ("start_number", 0, MAX_NUMBER), ("revision", 0, MAX_NUMBER)):
        if type(body[key]) is not int or not minimum <= body[key] <= maximum:
            raise ValueError("Vérifiez la largeur et le numéro de départ de la série.")
    return body


@require_http_methods(["GET", "POST", "PUT"])
@authorized
def numbering(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if not has_permission(request.user, school, "school.settings.write"):
        return refuse()
    if request.method == "GET":
        rule = StudentNumbering.objects.filter(school=school).first() or StudentNumbering(school=school)
        return JsonResponse(preview(school, rule, {
            "enabled": rule.enabled, "template": rule.template, "digits": rule.digits,
            "start_number": rule.next_number,
        }))
    body, error = parse_body(request)
    if error is not None:
        return error
    try:
        values = clean_rule(body)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    with transaction.atomic():
        school = School.objects.select_for_update().get(pk=school.pk)
        rule = StudentNumbering.objects.filter(school=school).first() or StudentNumbering(school=school)
        if values["revision"] != (rule.revision if rule.pk else 0):
            return JsonResponse({"error": "La règle a changé. Rechargez les paramètres."}, status=409)
        result = preview(school, rule, values)
        if request.method == "POST":
            return JsonResponse(result)
        if result["enabled"] and result["next_number"] is None:
            return JsonResponse({"error": "Série épuisée. Choisissez un autre format."}, status=422)
        rule.enabled = values["enabled"]
        rule.template = values["template"]
        rule.digits = values["digits"]
        rule.next_number = result["next_number"] if result["next_number"] is not None else MAX_NUMBER + 1
        rule.revision = result["revision"] + 1
        rule.save()
        result["revision"] = rule.revision
        log_event(school, request, "student_numbering_updated", rule.pk, {
            "enabled": rule.enabled, "template": rule.template, "digits": rule.digits,
            "next_number": result["next_number"],
        })
        return JsonResponse(result)
