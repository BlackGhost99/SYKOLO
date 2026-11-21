"""Per-school editable activity labels, cost centers and accounting natures.

Activity poles remain five stable accounting dimensions. Only labels and
availability are configurable; center/nature directories are independent.
No write occurs on GET, and old expense labels are never backfilled.
"""
import re
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from accounts.views import authorized

from .operating_models import (
    ACTIVITY_POLES, ACTIVE_ACTIVITY_POLES, OperatingClassificationOption, OperatingExpense,
)
from .operating_views import gate, body, fail, result, txt, validation
from .views import log_event

CODE = re.compile(r"^[a-z][a-z0-9_-]{0,39}$")
EDITABLE = {"cost_center", "accounting_nature"}


def option_data(row):
    return {
        "id": str(row.pk),
        "kind": row.kind, "code": row.code, "name": row.name,
        "activity_pole": row.activity_pole, "active": row.active,
        "revision": row.revision,
    }


def listed_poles(school):
    saved = {
        row.code: row for row in OperatingClassificationOption.objects.filter(
            school=school, kind="pole"
        )
    }
    return [
        {"id": str(saved[code].pk) if code in saved else None,
         "code": code,
         "label": saved[code].name if code in saved else default_name,
         "active": saved[code].active if code in saved else True,
         "revision": saved[code].revision if code in saved else 0}
        for code, default_name in ACTIVITY_POLES if code in ACTIVE_ACTIVITY_POLES
    ]


def validate_code(code):
    code = txt(code, 40, "Code").lower()
    if not CODE.fullmatch(code):
        raise ValueError("Code : commencez par une lettre, puis a-z, 0-9, _ ou -.")
    return code


@never_cache
@require_http_methods(["GET", "POST"])
@authorized
def classification(request, school_id):
    school, err = gate(request, school_id,
                       "school.operating.read" if request.method == "GET"
                       else "school.operating.manage")
    if err is not None:
        return err
    if request.method == "GET":
        items = list(OperatingClassificationOption.objects.filter(
            school=school, kind__in=EDITABLE,
        ).order_by("kind", "name", "code"))
        return result({
            "poles": listed_poles(school),
            "centers": [option_data(v) for v in items if v.kind == "cost_center"],
            "natures": [option_data(v) for v in items if v.kind == "accounting_nature"],
        })
    data, err = body(
        request, {"kind", "code", "name", "activity_pole"}, {"kind", "code", "name"}
    )
    if err is not None:
        return err
    try:
        kind = data["kind"]
        if kind not in EDITABLE:
            raise ValueError("Type : centre de coûts ou nature comptable attendu.")
        pole = data.get("activity_pole", "")
        if not isinstance(pole, str) or (pole and pole not in ACTIVE_ACTIVITY_POLES):
            raise ValueError("Pôle de rattachement invalide.")
        if kind == "accounting_nature" and pole:
            raise ValueError("La nature comptable doit rester indépendante du pôle.")
        with transaction.atomic():
            row = OperatingClassificationOption(
                school=school, kind=kind, code=validate_code(data["code"]),
                name=txt(data["name"], 100, "Nom"), activity_pole=pole,
            )
            row.full_clean()
            row.save()
            log_event(school, request, "operating_classification_created", row.pk)
    except (ValueError, TypeError) as exc:
        return fail(str(exc))
    except ValidationError as exc:
        return validation(exc)
    except IntegrityError:
        return fail("Code déjà enregistré pour ce type dans cet établissement.", 409)
    return result(option_data(row), 201)


@never_cache
@require_http_methods(["GET", "PATCH"])
@authorized
def classification_detail(request, school_id, option_id):
    school, err = gate(request, school_id,
                       "school.operating.read" if request.method == "GET"
                       else "school.operating.manage")
    if err is not None:
        return err
    if request.method == "GET":
        row = OperatingClassificationOption.objects.filter(
            school=school, pk=option_id, kind__in=EDITABLE
        ).first()
        return result(option_data(row)) if row else fail("Référence introuvable.", 404)
    data, err = body(request, {"revision", "name", "activity_pole", "active"}, {"revision"})
    if err is not None:
        return err
    if type(data["revision"]) is not int or len(data) == 1:
        return fail("Révision et modification obligatoires.")
    try:
        with transaction.atomic():
            row = OperatingClassificationOption.objects.select_for_update().filter(
                school=school, pk=option_id, kind__in=EDITABLE
            ).first()
            if row is None:
                return fail("Référence introuvable.", 404)
            if row.revision != data["revision"]:
                return fail("Référence mise à jour par un autre utilisateur.", 409)
            if "name" in data:
                row.name = txt(data["name"], 100, "Nom")
            if "active" in data:
                if type(data["active"]) is not bool:
                    raise ValueError("Statut d'archivage invalide.")
                row.active = data["active"]
            if "activity_pole" in data:
                pole = data["activity_pole"]
                if not isinstance(pole, str) or (pole and pole not in ACTIVE_ACTIVITY_POLES):
                    raise ValueError("Pôle de rattachement invalide.")
                if row.kind != "cost_center" and pole:
                    raise ValueError("Une nature comptable n'a pas de pôle.")
                if pole != row.activity_pole and OperatingExpense.objects.filter(
                    school=school, cost_center_ref=row
                ).exists():
                    return fail(
                        "Centre déjà utilisé : créez un autre centre pour ce pôle.", 409
                    )
                row.activity_pole = pole
            row.full_clean()
            row.revision += 1
            row.save()
            log_event(school, request, "operating_classification_updated", row.pk)
    except ValueError as exc:
        return fail(str(exc))
    except ValidationError as exc:
        return validation(exc)
    return result(option_data(row))


@never_cache
@require_http_methods(["PATCH"])
@authorized
def pole_detail(request, school_id, pole_code):
    school, err = gate(request, school_id, "school.operating.manage")
    if err is not None:
        return err
    if pole_code not in ACTIVE_ACTIVITY_POLES:
        return fail("Pôle S1–S5 introuvable.", 404)
    data, err = body(request, {"revision", "label", "active"}, {"revision"})
    if err is not None:
        return err
    if type(data["revision"]) is not int or len(data) == 1:
        return fail("Révision et changement requis.")
    default_name = dict(ACTIVITY_POLES)[pole_code]
    try:
        with transaction.atomic():
            school.__class__.objects.select_for_update().get(pk=school.pk)
            row = OperatingClassificationOption.objects.select_for_update().filter(
                school=school, kind="pole", code=pole_code,
            ).first()
            current_version = row.revision if row else 0
            if current_version != data["revision"]:
                return fail("Pôle modifié par un autre utilisateur.", 409)
            if "active" in data and type(data["active"]) is not bool:
                raise ValueError("Statut de pôle invalide.")
            if row is None:
                row = OperatingClassificationOption(
                    school=school, kind="pole", code=pole_code,
                    name=default_name,
                )
            if "label" in data:
                row.name = txt(data["label"], 100, "Libellé")
            if "active" in data:
                row.active = data["active"]
            row.full_clean()
            row.revision = current_version + 1
            row.save()
            log_event(school, request, "operating_pole_configured", row.pk)
    except ValueError as exc:
        return fail(str(exc))
    except ValidationError as exc:
        return validation(exc)
    except IntegrityError:
        return fail("Pôle modifié simultanément : recommencez.", 409)
    return result({
        "id": str(row.pk), "code": row.code, "label": row.name,
        "active": row.active, "revision": row.revision,
    })
