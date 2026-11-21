"""Installation facultative et idempotente des familles B01–B20 par établissement.

Le catalogue n'est jamais écrit à la lecture, ni injecté dans toutes les
écoles par migration. Une famille existante (même personnalisée/archivée)
est conservée : pas de restauration silencieuse ni de réécriture d'historique.
"""
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from accounts.views import authorized

from .operating_models import OperatingExpenseCategory
from .operating_seed_catalog import DEFAULT_EXPENSE_FAMILIES, DEFAULT_FAMILY_CODES
from .operating_views import gate, body, fail, result, validation
from .views import log_event


@never_cache
@require_http_methods(["GET", "POST"])
@authorized
def default_catalog(request, school_id):
    school, err = gate(request, school_id, (
        "school.operating.read" if request.method == "GET" else "school.operating.manage"
    ))
    if err is not None:
        return err

    if request.method == "GET":
        installed_codes = set(OperatingExpenseCategory.objects.filter(
            school=school, code__in=DEFAULT_FAMILY_CODES
        ).values_list("code", flat=True))
        return result({
            "families": [{
                "code": code, "name": name, "suggested_pole": pole,
                "subcategory_count": len(children),
                "installed": code in installed_codes,
            } for code, name, pole, children in DEFAULT_EXPENSE_FAMILIES],
            "total_families": len(DEFAULT_EXPENSE_FAMILIES),
            "total_subcategories": sum(len(x[3]) for x in DEFAULT_EXPENSE_FAMILIES),
        })

    data, err = body(request, {"families", "include_subcategories"}, {"families"})
    if err is not None:
        return err
    selected = data["families"]
    include = data.get("include_subcategories", True)
    if not isinstance(selected, list) or not selected or any(
        not isinstance(v, str) or v not in DEFAULT_FAMILY_CODES for v in selected
    ) or len(selected) != len(set(selected)):
        return fail("Sélection des familles B01–B20 invalide.")
    if type(include) is not bool:
        return fail("Option de sous-catégories invalide.")

    created_families = 0
    created_subcategories = 0
    skipped_archived = 0
    try:
        with transaction.atomic():
            # Serialize two import requests from the same school; the unique
            # constraint independently protects against standard catalog edits.
            school.__class__.objects.select_for_update().get(pk=school.pk)
            known = {row.code: row for row in OperatingExpenseCategory.objects.filter(
                school=school,
            )}
            for code, name, pole, children in DEFAULT_EXPENSE_FAMILIES:
                if code not in selected:
                    continue
                root = known.get(code)
                if root is None:
                    root = OperatingExpenseCategory(
                        school=school, code=code, name=name, suggested_pole=pole
                    )
                    root.full_clean()
                    root.save()
                    known[code] = root
                    created_families += 1
                elif root.parent_id:
                    raise ValueError(
                        f"Code {code} déjà utilisé par une sous-catégorie : import annulé."
                    )
                # Deliberately leave archived roots untouched.
                if not include:
                    continue
                if not root.active:
                    skipped_archived += 1
                    continue
                for child_code, child_name in children:
                    existing = known.get(child_code)
                    if existing:
                        if existing.parent_id != root.pk:
                            raise ValueError(
                                f"Code {child_code} déjà utilisé ailleurs : import annulé."
                            )
                        # Never reactivate an archived child or rename a custom one.
                        continue
                    item = OperatingExpenseCategory(
                        school=school, parent=root, code=child_code, name=child_name
                    )
                    item.full_clean()
                    item.save()
                    known[child_code] = item
                    created_subcategories += 1
            log_event(school, request, "operating_catalog_defaults_installed", school.pk)
    except ValueError as exc:
        return fail(str(exc), 409)
    except ValidationError as exc:
        return validation(exc)
    except IntegrityError:
        return fail("Catalogue modifié simultanément : actualisez et recommencez.", 409)

    return result({
        "created_families": created_families,
        "created_subcategories": created_subcategories,
        "skipped_archived_families": skipped_archived,
        "installed_families": sorted(selected),
        "idempotent": created_families == 0 and created_subcategories == 0,
    })
