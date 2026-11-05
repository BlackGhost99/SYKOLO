"""Two-phase school-scoped student imports: inspect, preview, then atomic commit.

No arbitrary workbook macros, remote fetches, generated finance or implicit parent accounts.
The uploaded file is re-sent for commit, fingerprinted and validated again under
the same school lock used by manual registrations. No server file staging.
"""
import csv
import hashlib
import io
import json
import re
from collections import Counter
from datetime import date
from uuid import UUID

from django.core import signing
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from accounts.views import authorized

from .academic_models import AcademicClass, AcademicYear
from .enrollment_form import load_config, check_base, clean_answers
from .import_models import StudentImportBatch, StudentImportProfile
from .import_service import FIELDS, normalized, parse_upload, parse_date, parse_gender, suggested_mapping, validate_mapping
from .models import School, SchoolAdminPolicy
from .overview_views import gate
from .registration_views import next_student_code
from .services import quota_reached
from .student_models import Student, StudentGuardian, Enrollment, EnrollmentEvent
from .student_views import parse_fields, validate_enrollment_slot
from .views import log_event, parse_body

TOKEN_SALT = "yem.students.import.preview.v1"
STUDENT_KEYS = {"student_code", "first_name", "last_name", "date_of_birth", "admission_date",
                "gender", "place_of_birth", "nationality", "address", "previous_school"}
GUARDIAN_KEYS = {"full_name", "relationship", "phone", "email", "profession", "address"}


def invalid(message, status=422):
    return JsonResponse({"error": str(message)}, status=status)


def inputs(request):
    if request.content_type not in ("multipart/form-data",) and not request.content_type.startswith("multipart/form-data;"):
        raise ValueError("Le formulaire doit contenir un fichier.")
    sheet = request.POST.get("sheet", "")
    if len(sheet) > 120:
        raise ValueError("Nom de feuille trop long.")
    try:
        row = int(request.POST.get("header_row", "1"))
    except (TypeError, ValueError):
        raise ValueError("Ligne d'en-tête invalide.") from None
    data = parse_upload(request.FILES.get("file"), sheet=sheet, header_row=row)
    return data


def options(config):
    return [{"value": k, "label": label} for k, label in FIELDS] + [
        {"value": "extra." + q["key"], "label": "Personnalisé : " + q["label"]}
        for q in config.get("custom_fields", []) if q.get("section", "eleve") == "eleve"
    ]


def class_options(school):
    years = list(AcademicYear.objects.filter(school=school, active=True).order_by("-start_date")[:30])
    classes = list(AcademicClass.objects.filter(school=school, active=True, year__active=True)
                   .select_related("year").order_by("year__start_date", "name")[:1000])
    return ([{"id": str(y.pk), "name": y.name} for y in years],
            [{"id": str(c.pk), "year": str(c.year_id), "name": c.name, "code": c.code} for c in classes])


def pick_class(school, year_id, label):
    if not label:
        return None
    if not year_id:
        raise ValueError("Sélectionnez l'année scolaire pour importer une classe.")
    matches = [c for c in AcademicClass.objects.filter(
        school=school, year_id=year_id, active=True, year__active=True)
        if normalized(c.name) == normalized(label) or normalized(c.code) == normalized(label)]
    matches = list({c.pk: c for c in matches}.values())
    if len(matches) != 1:
        raise ValueError("Classe inconnue ou ambiguë : " + label[:70])
    return matches[0]


def prepare_school_row(school, config, extracted, year_id):
    raw = extracted
    data = {key: value for key, value in raw.items() if key in STUDENT_KEYS and value != ""}
    for key in ("date_of_birth", "admission_date"):
        if key in data:
            data[key] = parse_date(data[key])
    if data.get("gender"):
        data["gender"] = parse_gender(data["gender"])
    student = parse_fields(data, STUDENT_KEYS, ("first_name", "last_name"))
    student["last_name"] = student["last_name"].upper()

    guardian_values = {
        "full_name": raw.get("guardian_name", ""), "relationship": raw.get("guardian_relationship", ""),
        "phone": raw.get("guardian_phone", ""), "email": raw.get("guardian_email", ""),
        "profession": raw.get("guardian_profession", ""), "address": raw.get("guardian_address", "")
    }
    guardian = None
    if guardian_values["full_name"]:
        guardian = parse_fields({k: v for k, v in guardian_values.items() if v != ""},
                                GUARDIAN_KEYS, ("full_name",))
        if guardian.get("email"):
            validate_email(guardian["email"])
        guardian["is_primary"] = True
    elif any(v for k, v in guardian_values.items() if k != "full_name"):
        raise ValueError("Coordonnées du responsable sans nom : corrigez ou ignorez ces colonnes.")
    extra = {}
    questions = {q["key"]: q for q in config.get("custom_fields", [])}
    for k, v in raw.items():
        if not k.startswith("extra.") or v == "":
            continue
        q = questions[k.split(".", 1)[1]]
        if q.get("section", "eleve") != "eleve":
            raise ValueError("Ce champ personnalisé n'est pas une information d'élève.")
        if q["type"] == "number":
            try:
                v = float(v.replace(",", ".")) if "." in v.replace(",", ".") else int(v)
            except ValueError:
                raise ValueError("Nombre invalide pour « " + q["label"] + " ».") from None
        elif q["type"] == "yesno":
            s = normalized(v)
            if s not in ("oui", "non", "yes", "no", "1", "0", "true", "false"):
                raise ValueError("Réponse oui/non invalide pour « " + q["label"] + " ».")
            v = s in ("oui", "yes", "1", "true")
        elif q["type"] == "date":
            v = parse_date(v)
        extra[q["key"]] = v
    extra, _ = clean_answers(config, extra, {})
    if guardian is None:
        # A register containing only learners remains importable, without inventing relatives.
        student_rules = {"fields": {k: v for k, v in config.get("fields", {}).items()
                                    if not k.startswith("guardian_")}}
        check_base(student_rules, student, {})
    else:
        check_base(config, student, guardian)
    classroom = pick_class(school, year_id, raw.get("classroom", ""))
    return {"student": student, "guardian": guardian, "extra": extra, "classroom": classroom}


def evaluate(school, table, mapping, year_id, config):
    """Non-writing inspection; rerun inside a school lock at confirmation."""
    assignments = []
    classes_count = Counter()
    existing_codes = set()
    existing_people = set()
    reports = []
    for item in table["rows"]:
        error = ""
        value = None
        label = "(incomplet)"
        try:
            raw = {key: item["cells"][int(index)] for index, key in mapping.items()}
            label = (raw.get("last_name", "") + " " + raw.get("first_name", "")).strip()[:180] or label
            value = prepare_school_row(school, config, raw, year_id)
            person = value["student"]
            identity = (normalized(person["last_name"]), normalized(person["first_name"]),
                        str(person.get("date_of_birth") or ""))
            code = person.get("student_code", "").casefold()
            if code:
                if code in existing_codes or Student.objects.filter(school=school, student_code__iexact=person["student_code"]).exists():
                    raise ValueError("Matricule déjà présent dans ce fichier ou dans l'école.")
                existing_codes.add(code)
            if identity in existing_people:
                raise ValueError("Élève en double dans le fichier.")
            existing_people.add(identity)
            matched = Student.objects.filter(school=school, first_name__iexact=person["first_name"],
                                             last_name__iexact=person["last_name"])
            if person.get("date_of_birth"):
                matched = matched.filter(date_of_birth__in=[person["date_of_birth"], None])
            if matched.exists():
                raise ValueError("Élève similaire déjà présent dans cet établissement : vérification manuelle requise.")
            if value["classroom"]:
                klass = value["classroom"]
                classes_count[klass.pk] += 1
                occupied = Enrollment.objects.filter(classroom=klass, active=True).count()
                if klass.capacity is not None and occupied + classes_count[klass.pk] > klass.capacity:
                    raise ValueError("Capacité de la classe dépassée.")
        except (ValueError, ValidationError, KeyError, TypeError) as exc:
            error = "; ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
        warning = ("Responsable légal absent : compléter le dossier avant accès parent."
                   if value and not value["guardian"] and not error else "")
        reports.append({"line": item["line"], "name": label, "valid": not bool(error),
                        "error": error, "warning": warning,
                        "class": value["classroom"].name if value and value["classroom"] else ""})
        assignments.append(value if not error else None)
    policy = SchoolAdminPolicy.objects.filter(school=school).first()
    if policy and policy.max_students is not None:
        active = Student.objects.filter(school=school, active=True).count()
        if active + len(assignments) > policy.max_students:
            reports.append({"line": 0, "name": "Quota", "valid": False,
                            "error": "Plafond d'élèves de l'établissement dépassé.", "class": ""})
    return assignments, reports


def fingerprint(school_id, table, mapping, year_id, revision):
    canonical = json.dumps([str(school_id), table["sha256"], table["sheet"], table["header_row"],
                            mapping, year_id, revision], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


@require_GET
@authorized
def profiles(request, school_id):
    school, error = gate(request, school_id, "school.students.manage")
    if error is not None:
        return error
    config, revision = load_config(school)
    years, classes = class_options(school)
    saved = StudentImportProfile.objects.filter(school=school).order_by("-updated_at")[:20]
    return JsonResponse({"choices": options(config), "years": years, "classes": classes,
                         "config_revision": revision,
                         "profiles": [{"id": str(p.pk), "name": p.name, "headers": p.headers, "mapping": p.mapping}
                                      for p in saved]})


@require_POST
@authorized
def inspect(request, school_id):
    school, error = gate(request, school_id, "school.students.manage")
    if error is not None:
        return error
    try:
        table = inputs(request)
    except ValueError as exc:
        return invalid(exc)
    config, revision = load_config(school)
    years, classes = class_options(school)
    return JsonResponse({"headers": table["headers"], "sheets": table["sheets"], "sheet": table["sheet"],
                         "header_row": table["header_row"], "row_count": len(table["rows"]),
                         "samples": [x["cells"] for x in table["rows"][:3]],
                         "suggested_mapping": suggested_mapping(table["headers"], config.get("custom_fields", [])),
                         "choices": options(config), "years": years, "classes": classes,
                         "config_revision": revision})


def import_context(request, school):
    table = inputs(request)
    raw_mapping = request.POST.get("mapping", "")
    if len(raw_mapping) > 10000:
        raise ValueError("Correspondances trop volumineuses.")
    try:
        mapping = json.loads(raw_mapping)
    except (TypeError, ValueError):
        raise ValueError("Correspondances JSON invalides.") from None
    config, revision = load_config(school)
    mapping = validate_mapping(mapping, table["headers"], config)
    year_id = request.POST.get("year", "").strip()
    if year_id:
        try:
            year_id = str(UUID(year_id))
        except ValueError:
            raise ValueError("Année scolaire invalide.") from None
        if not AcademicYear.objects.filter(school=school, pk=year_id, active=True).exists():
            raise ValueError("Année scolaire introuvable.")
    return table, mapping, year_id, config, revision


@require_POST
@authorized
def preview(request, school_id):
    school, error = gate(request, school_id, "school.students.manage")
    if error is not None:
        return error
    try:
        table, mapping, year_id, config, revision = import_context(request, school)
        assignments, reports = evaluate(school, table, mapping, year_id, config)
    except ValueError as exc:
        return invalid(exc)
    digest = fingerprint(school.pk, table, mapping, year_id, revision)
    token = signing.dumps({"school": str(school.pk), "user": str(request.user.pk),
                           "fingerprint": digest, "revision": revision}, salt=TOKEN_SALT)
    return JsonResponse({"token": token, "row_count": len(assignments),
                         "valid": sum(r["valid"] for r in reports),
                         "errors": sum(not r["valid"] for r in reports),
                         "warnings": sum(bool(r.get("warning")) for r in reports),
                         "rows": reports, "notice": "Aucune donnée écrite. Les frais ne sont jamais créés par import."})


@require_POST
@authorized
def commit(request, school_id):
    school, error = gate(request, school_id, "school.students.manage")
    if error is not None:
        return error
    token = request.POST.get("token", "")
    if len(token) > 1500:
        return invalid("Jeton de prévisualisation invalide.")
    try:
        accepted = signing.loads(token, salt=TOKEN_SALT, max_age=900)
    except (signing.BadSignature, signing.SignatureExpired):
        return invalid("Prévisualisation expirée ou modifiée : recommencez.", 409)
    if not isinstance(accepted, dict) or accepted.get("school") != str(school.pk) or accepted.get("user") != str(request.user.pk):
        return invalid("Prévisualisation non autorisée.", 403)
    try:
        table, mapping, year_id, config, revision = import_context(request, school)
    except ValueError as exc:
        return invalid(exc)
    digest = fingerprint(school.pk, table, mapping, year_id, revision)
    if digest != accepted.get("fingerprint") or revision != accepted.get("revision"):
        return invalid("Le fichier, les paramètres ou les correspondances ont changé : revalidez l'aperçu.", 409)

    template_name = request.POST.get("template_name", "").strip()
    if template_name and (len(template_name) > 80 or any(ord(c) < 32 for c in template_name)):
        return invalid("Nom du modèle invalide.")
    try:
        with transaction.atomic():
            school = School.objects.select_for_update().get(pk=school.pk)
            previous = StudentImportBatch.objects.filter(school=school, fingerprint=digest).first()
            if previous is not None:
                return JsonResponse({"imported": previous.row_count, "already_imported": True,
                                     "batch": str(previous.pk), "notice": "Ce fichier a déjà été importé."})
            # It must be freshly evaluated while concurrent registration is blocked.
            fresh_config, fresh_revision = load_config(school)
            if fresh_revision != revision or fresh_config != config:
                return invalid("La fiche d'inscription a été modifiée : recommencez l'aperçu.", 409)
            assignments, reports = evaluate(school, table, mapping, year_id, fresh_config)
            if any(not r["valid"] for r in reports):
                return JsonResponse({"error": "Importation refusée : corrigez les lignes et prévisualisez à nouveau.",
                                     "rows": reports}, status=409)
            if quota_reached(school, "students"):
                return invalid("Quota élèves atteint.", 409)
            created = []
            for value in assignments:
                student_fields = dict(value["student"])
                if not student_fields.get("student_code"):
                    student_fields["student_code"] = next_student_code(school)
                student = Student(school=school, extra_fields=value["extra"], **student_fields)
                student.full_clean()
                student.save()
                if value["guardian"] is not None:
                    guardian = StudentGuardian(school=school, student=student, **value["guardian"])
                    guardian.full_clean()
                    guardian.save()
                klass = value["classroom"]
                if klass is not None:
                    klass = AcademicClass.objects.select_for_update().get(pk=klass.pk, school=school)
                    year = klass.year
                    validate_enrollment_slot(klass, student, year)
                    today = timezone.localdate()
                    day = today if year.start_date <= today <= year.end_date else year.start_date
                    enrollment = Enrollment(school=school, student=student, year=year, classroom=klass,
                                            enrolled_on=day, status="inscrit")
                    enrollment.full_clean()
                    enrollment.save()
                    EnrollmentEvent.objects.create(enrollment=enrollment, school=school, actor=request.user,
                                                   previous_class_id=None, new_class_id=klass.pk,
                                                   new_status=enrollment.status)
                created.append(student.pk)
            batch = StudentImportBatch.objects.create(school=school, fingerprint=digest,
                                                      row_count=len(created), imported_by=request.user)
            if template_name:
                profile = StudentImportProfile.objects.filter(school=school, name=template_name).first()
                if profile is None:
                    if StudentImportProfile.objects.filter(school=school).count() >= 20:
                        raise ValueError("20 modèles d'import au maximum par établissement.")
                    profile = StudentImportProfile(school=school, name=template_name)
                else:
                    profile.revision += 1
                profile.headers = table["headers"]
                profile.mapping = mapping
                profile.save()
            log_event(school, request, "students_imported", batch.pk,
                      {"count": len(created), "batch": str(batch.pk), "filename_sha256": table["sha256"]})
        return JsonResponse({"imported": len(created), "already_imported": False, "batch": str(batch.pk),
                             "notice": "Import enregistré. Aucun frais généré automatiquement."}, status=201)
    except (IntegrityError, ValidationError, ValueError) as exc:
        message = ("Validation échouée. Aucune ligne n'a été importée."
                   if isinstance(exc, IntegrityError) else
                   "; ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc))
        return invalid(message, 409)


def safe_spreadsheet_cell(value):
    """Prevent spreadsheet formula execution when CSV is opened by Excel/LibreOffice."""
    if value is None:
        return ""
    if type(value) is bool:
        value = "Oui" if value else "Non"
    value = str(value).replace("\x00", "")
    if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
        return "'" + value
    return value


@require_POST
@authorized
def export_students(request, school_id):
    """Private school-scoped CSV export, explicitly initiated by an authorized manager."""
    school, error = gate(request, school_id, "school.students.manage")
    if error is not None:
        return error
    data, error = parse_body(request)
    if error is not None:
        return error
    if set(data) - {"year"}:
        return invalid("Paramètres inconnus.")
    requested_year = data.get("year") or ""
    if not isinstance(requested_year, str) or len(requested_year) > 36:
        return invalid("Année invalide.")
    if requested_year:
        try:
            requested_year = str(UUID(requested_year))
        except ValueError:
            return invalid("Année invalide.")
        if not AcademicYear.objects.filter(school=school, pk=requested_year).exists():
            return invalid("Année étrangère ou introuvable.", 404)

    students = Student.objects.filter(school=school).order_by("last_name", "first_name", "id")
    if requested_year:
        students = students.filter(enrollments__school=school, enrollments__year_id=requested_year).distinct()
    total = students.count()
    if total > 10000:
        return invalid("Export supérieur à 10 000 élèves : fractionnez par année scolaire.", 409)
    enrollments = Enrollment.objects.filter(school=school).select_related("year", "classroom").order_by("-year__start_date")
    if requested_year:
        enrollments = enrollments.filter(year_id=requested_year)
    guardians = StudentGuardian.objects.filter(school=school, active=True).order_by("-is_primary", "full_name")
    students = students.prefetch_related(
        Prefetch("enrollments", queryset=enrollments, to_attr="export_enrollments"),
        Prefetch("guardians", queryset=guardians, to_attr="export_guardians"))
    config, _ = load_config(school)
    custom = [q for q in config.get("custom_fields", []) if q.get("section", "eleve") == "eleve"]
    headings = [
        "Matricule", "Nom", "Prénoms", "Date de naissance", "Sexe", "Classe", "Année scolaire",
        "Responsable", "Lien de parenté", "Téléphone parent", "Email parent", "Lieu de naissance",
        "Nationalité", "Adresse élève", "Établissement précédent",
    ] + [q["label"] for q in custom]
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    writer.writerow(headings)
    for student in students:
        enrollment = student.export_enrollments[0] if student.export_enrollments else None
        guardian = student.export_guardians[0] if student.export_guardians else None
        fields = [
            student.student_code, student.last_name, student.first_name,
            student.date_of_birth.isoformat() if student.date_of_birth else "",
            student.gender, enrollment.classroom.name if enrollment else "",
            enrollment.year.name if enrollment else "", guardian.full_name if guardian else "",
            guardian.relationship if guardian else "", guardian.phone if guardian else "",
            guardian.email if guardian else "", student.place_of_birth, student.nationality,
            student.address, student.previous_school,
        ] + [student.extra_fields.get(q["key"], "") for q in custom]
        writer.writerow([safe_spreadsheet_cell(v) for v in fields])
    payload = "\ufeff" + output.getvalue()
    result = HttpResponse(payload, content_type="text/csv; charset=utf-8")
    result["Content-Disposition"] = 'attachment; filename="yem-eleves-' + str(school.pk)[:8] + '.csv"'
    result["Cache-Control"] = "private, no-store"
    result["Pragma"] = "no-cache"
    result["X-Content-Type-Options"] = "nosniff"
    log_event(school, request, "students_exported", school.pk,
              {"count": total, "year": requested_year or None})
    return result
