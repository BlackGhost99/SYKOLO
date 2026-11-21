"""School-scoped, auditable expense category catalog (not the tuition fee catalog)."""
import re
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from accounts.views import authorized

from .operating_models import ACTIVE_ACTIVITY_POLES, OperatingExpenseCategory
from .operating_views import gate, body, fail, result, txt, uuidval, validation
from .views import log_event

CATEGORY_CODE = re.compile(r"^[a-z][a-z0-9_-]{0,39}$")


def category_data(item):
    return {
        "id": str(item.pk),
        "parent": str(item.parent_id) if item.parent_id else None,
        "code": item.code,
        "name": item.name,
        "suggested_pole": item.suggested_pole,
        "active": item.active,
        "revision": item.revision,
    }


def valid_pole(value):
    if not isinstance(value, str) or (value and value not in ACTIVE_ACTIVITY_POLES):
        raise ValueError("Pôle suggéré invalide.")
    return value


@never_cache
@require_http_methods(["GET", "POST"])
@authorized
def categories(request, school_id):
    school, err = gate(request, school_id, "school.operating.read" if request.method == "GET"
                       else "school.operating.manage")
    if err is not None:
        return err
    if request.method == "GET":
        items = OperatingExpenseCategory.objects.filter(school=school).order_by("name", "code")
        return result({"categories": [category_data(item) for item in items.iterator()]})
    data, err = body(request, {"code", "name", "parent", "suggested_pole"}, {"code", "name"})
    if err is not None:
        return err
    try:
        code = txt(data["code"], 40, "Code").lower()
        if not CATEGORY_CODE.fullmatch(code):
            raise ValueError("Code de catégorie : lettres minuscules, chiffres, _ ou -.")
        name = txt(data["name"], 100, "Nom")
        pole = valid_pole(data.get("suggested_pole", ""))
        with transaction.atomic():
            parent = None
            if data.get("parent"):
                parent = OperatingExpenseCategory.objects.select_for_update().filter(
                    school=school, pk=uuidval(data["parent"]),
                ).first()
                if parent is None:
                    return fail("Catégorie parente introuvable.", 404)
                if not parent.active or parent.parent_id:
                    return fail("La catégorie parente doit être une catégorie principale active.", 409)
            item = OperatingExpenseCategory(
                school=school, parent=parent, code=code, name=name, suggested_pole=pole
            )
            item.full_clean()
            item.save()
            log_event(school, request, "operating_category_created", item.pk)
    except ValueError as exc:
        return fail(str(exc))
    except ValidationError as exc:
        return validation(exc)
    except IntegrityError:
        return fail("Ce code de catégorie existe déjà dans cet établissement.", 409)
    return result(category_data(item), 201)


@never_cache
@require_http_methods(["GET", "PATCH"])
@authorized
def category_detail(request, school_id, category_id):
    school, err = gate(request, school_id, "school.operating.read" if request.method == "GET"
                       else "school.operating.manage")
    if err is not None:
        return err
    if request.method == "GET":
        row = OperatingExpenseCategory.objects.filter(school=school, pk=category_id).first()
        return result(category_data(row)) if row else fail("Catégorie introuvable.", 404)
    data, err = body(request, {"revision", "name", "suggested_pole", "active"}, {"revision"})
    if err is not None:
        return err
    if type(data["revision"]) is not int or not set(data).difference({"revision"}):
        return fail("Version et modification requises.")
    try:
        with transaction.atomic():
            row = OperatingExpenseCategory.objects.select_for_update().filter(
                school=school, pk=category_id,
            ).first()
            if not row:
                return fail("Catégorie introuvable.", 404)
            if row.revision != data["revision"]:
                return fail("Catégorie modifiée par un autre utilisateur.", 409)
            if "active" in data and type(data["active"]) is not bool:
                return fail("Valeur d'archivage invalide.")
            if "name" in data:
                row.name = txt(data["name"], 100, "Nom")
            if "suggested_pole" in data:
                row.suggested_pole = valid_pole(data["suggested_pole"])
            if "active" in data:
                row.active = data["active"]
            if not row.active and not row.parent_id and OperatingExpenseCategory.objects.filter(
                school=school, parent=row, active=True,
            ).exists():
                return fail("Archivez d'abord les sous-catégories actives.", 409)
            row.full_clean()
            row.revision += 1
            row.save()
            log_event(school, request, "operating_category_updated", row.pk)
    except ValueError as exc:
        return fail(str(exc))
    except ValidationError as exc:
        return validation(exc)
    return result(category_data(row))
