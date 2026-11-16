"""Actionable YEM in-app mailbox: staff ↔ parents, automatic request alerts.

No client-supplied recipient or student ID is sufficient to grant school access.
Messages are scoped by school, verified family link or a parent-owned request.
"""
from datetime import timedelta
from uuid import UUID

from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import JsonResponse
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from accounts.views import authorized
from .family_notification_models import SchoolFamilyNotification as Notice
from .models import School, SchoolMember
from .parent_existing_models import ExistingStudentLinkRequest as LinkRequest
from .parent_models import GuardianAccountLink
from .services import has_permission
from .student_models import Student
from .views import access, log_event, parse_body, refuse

User = get_user_model()


def fail(message, status=422):
    return JsonResponse({"error": message}, status=status)


def uid(value):
    try:
        return UUID(value) if isinstance(value, str) else None
    except ValueError:
        return None


def notice_output(row):
    return {
        "id": str(row.pk), "school_id": str(row.school_id),
        "school": row.school.name, "parent_username": row.parent.get_username(),
        "origin": row.origin, "destination": row.destination,
        "request_id": str(row.existing_request_id) if row.existing_request_id else None,
        "message": row.message, "at": row.created_at.isoformat(),
        "read": row.read_at is not None, "kind": "family_message",
    }


def send_system_notice(*, school, parent, destination, message, related_request=None):
    """Call inside the originating transaction for an auditable event."""
    return Notice.objects.create(
        school=school, parent=parent, destination=destination,
        origin="system", message=message, existing_request=related_request,
    )


def school_gate(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return None, error
    if not has_permission(request.user, school, "school.parents.manage"):
        return None, refuse()
    return school, None


def message_text(data):
    if not isinstance(data, dict):
        raise ValueError("Message attendu.")
    message = data.get("message")
    if not isinstance(message, str):
        raise ValueError("Saisissez un message.")
    message = message.strip()
    if not 1 <= len(message) <= 700 or any(ord(char) < 32 and char not in "\n\t" for char in message):
        raise ValueError("Le message doit contenir de 1 à 700 caractères.")
    return message


def parent_has_school_link(user, school):
    return GuardianAccountLink.objects.filter(
        user=user, school=school, active=True,
        guardian__active=True, guardian__student__active=True,
        guardian__school=school, guardian__student__school=school,
    ).exists()


@never_cache
@require_http_methods(["GET", "POST"])
@authorized
def school_inbox(request, school_id):
    school, error = school_gate(request, school_id)
    if error is not None:
        return error
    if request.method == "GET":
        from .parent_existing_views import staff_summary
        pending = LinkRequest.objects.select_related("school", "owner").filter(
            school=school, status=LinkRequest.PENDING
        ).order_by("created_at", "pk")[:150]
        messages = Notice.objects.select_related("school", "parent").filter(
            school=school, destination=Notice.TO_SCHOOL
        ).order_by("-created_at", "-pk")[:150]
        results = [notice_output(item) for item in messages]
        requests = [staff_summary(item) for item in pending]
        return JsonResponse({
            "requests": requests, "messages": results,
            "unread": len(requests) + sum(not item["read"] for item in results),
        })

    data, error = parse_body(request)
    if error is not None:
        return error
    if not isinstance(data, dict) or set(data) - {"username", "message", "request_id"}:
        return fail("Destinataire et message requis.")
    username = data.get("username")
    if not isinstance(username, str) or not username.strip() or len(username) > 150:
        return fail("Identifiant parent invalide.")
    try:
        message = message_text(data)
    except ValueError as exc:
        return fail(str(exc))
    if Notice.objects.filter(
        school=school, actor=request.user, origin="school",
        created_at__gte=timezone.now() - timedelta(hours=1)
    ).count() >= 30:
        return fail("Limite de messages atteinte. Réessayez ultérieurement.", 429)
    recipient = User.objects.filter(username=username.strip(), is_active=True).first()
    if recipient is None:
        return fail("Compte parent introuvable.", 404)
    related = None
    if "request_id" in data:
        rid = uid(data["request_id"])
        if rid is None:
            return fail("Demande invalide.")
        related = LinkRequest.objects.filter(pk=rid, owner=recipient, school=school).first()
        if related is None:
            return fail("Cette demande ne correspond pas au parent.", 404)
    elif not (
        LinkRequest.objects.filter(owner=recipient, school=school).exists()
        or parent_has_school_link(recipient, school)
    ):
        return fail("Ce compte n'a pas de dossier familial dans cet établissement.", 404)
    with transaction.atomic():
        notice = Notice.objects.create(
            school=school, parent=recipient, actor=request.user,
            existing_request=related, origin="school",
            destination=Notice.TO_PARENT, message=message,
        )
        log_event(school, request, "school_parent_message", notice.pk)
    return JsonResponse(notice_output(notice), status=201)


@never_cache
@require_http_methods(["PATCH"])
@authorized
def school_notice_detail(request, school_id, notice_id):
    school, error = school_gate(request, school_id)
    if error is not None:
        return error
    data, error = parse_body(request)
    if error is not None:
        return error
    if data != {"read": True}:
        return fail("Marquer comme lu uniquement.")
    with transaction.atomic():
        row = Notice.objects.select_for_update().select_related("school", "parent").filter(
            pk=notice_id, school=school, destination=Notice.TO_SCHOOL
        ).first()
        if row is None:
            return fail("Notification introuvable.", 404)
        if row.read_at is None:
            row.read_at = timezone.now()
            row.save(update_fields=["read_at"])
    return JsonResponse(notice_output(row))


@never_cache
@require_GET
@authorized
def request_candidates(request, school_id, request_id):
    """Only the authorized school authority can inspect matching guardian files."""
    school, error = school_gate(request, school_id)
    if error is not None:
        return error
    item = LinkRequest.objects.filter(
        pk=request_id, school=school, status=LinkRequest.PENDING
    ).first()
    if item is None:
        return fail("Demande introuvable ou déjà traitée.", 404)
    students = Student.objects.filter(
        school=school, active=True,
        first_name__iexact=item.first_name, last_name__iexact=item.last_name,
    )
    if item.student_code:
        students = students.filter(student_code__iexact=item.student_code)
    rows = students.prefetch_related("guardians").order_by("student_code")[:15]
    return JsonResponse({"candidates": [{
        "student": str(row.pk), "student_name": f"{row.first_name} {row.last_name}",
        "student_code": row.student_code,
        "guardians": [{
            "id": str(g.pk), "name": g.full_name,
            "relationship": g.relationship, "phone": g.phone,
        } for g in row.guardians.all() if g.active and g.school_id == school.pk],
    } for row in rows]})


@never_cache
@require_http_methods(["POST"])
@authorized
def parent_message(request):
    data, error = parse_body(request)
    if error is not None:
        return error
    if not isinstance(data, dict) or set(data) - {"school", "message", "request_id"}:
        return fail("École et message requis.")
    school_id = uid(data.get("school"))
    if school_id is None:
        return fail("Établissement invalide.")
    school = School.objects.filter(pk=school_id, is_active=True).first()
    if school is None:
        return fail("Établissement introuvable.", 404)
    try:
        message = message_text(data)
    except ValueError as exc:
        return fail(str(exc))
    if Notice.objects.filter(
        school=school, parent=request.user, origin="parent",
        created_at__gte=timezone.now() - timedelta(hours=1),
    ).count() >= 10:
        return fail("Limite de messages atteinte. Réessayez ultérieurement.", 429)
    related = None
    if "request_id" in data and data["request_id"] is not None:
        rid = uid(data["request_id"])
        if rid is None:
            return fail("Demande invalide.")
        related = LinkRequest.objects.filter(pk=rid, school=school, owner=request.user).first()
        if related is None:
            return fail("Demande introuvable.", 404)
    if related is None:
        related = LinkRequest.objects.filter(school=school, owner=request.user).order_by("-created_at").first()
    if related is None and not parent_has_school_link(request.user, school):
        return fail("Aucun dossier familial lié à cet établissement.", 404)
    with transaction.atomic():
        notice = Notice.objects.create(
            school=school, parent=request.user, actor=request.user,
            existing_request=related, origin="parent",
            destination=Notice.TO_SCHOOL, message=message,
        )
        log_event(school, request, "parent_school_message", notice.pk)
    return JsonResponse(notice_output(notice), status=201)


@never_cache
@require_http_methods(["PATCH"])
@authorized
def parent_notice_detail(request, notice_id):
    data, error = parse_body(request)
    if error is not None:
        return error
    if data != {"read": True}:
        return fail("Marquer comme lu uniquement.")
    with transaction.atomic():
        from .pedagogical_family_notices import visible_notices
        row = visible_notices(request.user, Notice.objects.select_for_update().select_related("school", "parent")).filter(
            pk=notice_id, parent=request.user, destination=Notice.TO_PARENT, school__is_active=True,
        ).first()
        if row is None:
            return fail("Notification introuvable.", 404)
        if row.read_at is None:
            row.read_at = timezone.now()
            row.save(update_fields=["read_at"])
    return JsonResponse(notice_output(row))

@never_cache
@require_POST
@authorized
def send_payment_reminder(request, school_id, enrollment_id):
    from .finance_views import CURRENCY_PATTERN
    from .overview_views import enrollment_balances
    from .student_models import Enrollment

    school, error = access(request, school_id)
    if error is not None:
        return error
    if not has_permission(request.user, school, "school.finance.read") or not any(
        has_permission(request.user, school, permission)
        for permission in ("school.finance.receive", "school.finance.approve")
    ):
        return refuse()
    data, error = parse_body(request)
    if error is not None:
        return error
    currency = data.get("currency")
    if set(data) != {"currency"} or not isinstance(currency, str) or not CURRENCY_PATTERN.fullmatch(currency):
        return fail("Devise invalide.")

    with transaction.atomic():
        School.objects.select_for_update().get(pk=school.pk)
        enrollment = Enrollment.objects.select_related("student", "year").filter(
            pk=enrollment_id, school=school, student__school=school, student__active=True,
        ).first()
        if enrollment is None:
            return fail("Inscription introuvable.", 404)
        _, balances = enrollment_balances(school, [enrollment.pk], currency)
        if not balances.get(enrollment.pk) or balances[enrollment.pk]["overdue"] <= 0:
            return fail("Aucun solde en retard. Actualisez le relevé.", 409)
        parent_membership = SchoolMember.objects.filter(
            school=school, user_id=OuterRef("user_id"), active=True, role__school=school,
        ).filter(Q(role__code="parent") | Q(additional_roles__school=school, additional_roles__code="parent"))
        recipients = set(GuardianAccountLink.objects.select_for_update(of=("self",)).filter(
            school=school, guardian__school=school, guardian__student=enrollment.student,
            guardian__active=True, active=True, user__is_active=True,
        ).filter(Exists(parent_membership)).values_list("user_id", flat=True))
        if not recipients:
            return fail("Aucun responsable ne dispose d’un compte YEM vérifié pour cet élève.", 409)

        student = enrollment.student
        message = (
            f"Rappel de scolarité pour {student.first_name} {student.last_name} "
            f"({student.student_code}), année {enrollment.year.name}, en {currency}. "
            "Consultez le relevé dans Mes enfants → Frais pour voir les échéances en retard et le solde à jour."
        )
        sent_today = set(Notice.objects.filter(
            school=school, parent_id__in=recipients, origin="school", destination=Notice.TO_PARENT,
            message=message, created_at__date=timezone.localdate(),
        ).values_list("parent_id", flat=True))
        notices = [
            Notice(school=school, parent_id=parent_id, actor=request.user,
                   origin="school", destination=Notice.TO_PARENT, message=message)
            for parent_id in recipients - sent_today
        ]
        Notice.objects.bulk_create(notices)
        for notice in notices:
            log_event(school, request, "finance_reminder_sent", notice.pk,
                      {"enrollment": str(enrollment.pk), "currency": currency})
    return JsonResponse({"sent": len(notices), "already_sent": len(sent_today)}, status=201 if notices else 200)
