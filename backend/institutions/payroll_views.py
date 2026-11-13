"""Private payroll ledger: draft -> independent approval -> declared payment.

This module does not initiate bank transfers, mobile-money charges or public
payslips. Every mutation is tenant-scoped, permission-checked and audited
without leaking salary amounts into the general audit log.
"""
import re
import uuid
from datetime import date
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from accounts.views import authorized
from .academic_models import AcademicYear
from .staff_models import StaffRecord
from .payroll_models import StaffPayRun, StaffPayDisbursement
from .services import has_permission
from .views import access, refuse, parse_body, log_event

ZERO = Decimal("0.00")
AMOUNT = re.compile(r"^(?:0|[1-9][0-9]{0,8})(?:\.[0-9]{1,2})?$")
CURRENCY = re.compile(r"^[A-Z]{3}$")
BASIS = {"monthly", "hourly", "session", "fixed"}
METHOD = {"especes", "virement", "mobile_money", "autre"}


def gate(request, school_id, permission):
    school, error = access(request, school_id)
    if error is not None:
        return None, error
    if not has_permission(request.user, school, permission):
        return None, refuse()
    return school, None


def error(message, status=422):
    return JsonResponse({"error": message}, status=status)


def money(value, *, allow_zero=False):
    if not isinstance(value, str) or not AMOUNT.fullmatch(value):
        raise ValueError("Montant décimal invalide.")
    number = Decimal(value).quantize(Decimal("0.01"))
    if number < ZERO or (number == ZERO and not allow_zero):
        raise ValueError("Montant strictement positif requis.")
    return number


def money_str(value):
    return format(value.quantize(Decimal("0.01")), ".2f")


def parse_uuid(value):
    if not isinstance(value, str):
        raise ValueError("Identifiant UUID obligatoire.")
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        raise ValueError("Identifiant UUID invalide.") from None


def iso_day(value):
    if not isinstance(value, str):
        raise ValueError("Date ISO obligatoire.")
    try:
        result = date.fromisoformat(value)
        if result.isoformat() != value:
            raise ValueError()
        return result
    except ValueError:
        raise ValueError("Date ISO invalide.") from None


def current_year(school):
    return AcademicYear.objects.filter(school=school, status="current").first()


def editable_year(year):
    return year is not None and year.status != "closed"


def cleared_sum(run):
    return StaffPayDisbursement.objects.filter(
        school=run.school, pay_run=run, voided_at__isnull=True,
    ).aggregate(total=Sum("amount"))["total"] or ZERO


def run_data(run):
    paid = cleared_sum(run)
    return {
        "id": str(run.pk), "staff": str(run.staff_id),
        "staff_name": f"{run.staff.first_name} {run.staff.last_name}",
        "staff_code": run.staff.staff_code, "year": str(run.year_id),
        "period": run.period.isoformat(), "basis": run.basis,
        "gross_amount": money_str(run.gross_amount),
        "deductions": money_str(run.deductions),
        "net_amount": money_str(run.net_amount),
        "currency": run.currency, "note": run.note,
        "status": ("draft" if not run.approved_at else
                   "paid" if paid == run.net_amount else
                   "partially_paid" if paid > ZERO else "approved"),
        "approved_at": run.approved_at.isoformat() if run.approved_at else None,
        "prepared_by": str(run.prepared_by_id),
        "approved_by": str(run.approved_by_id) if run.approved_by_id else None,
        "paid": money_str(paid),
        "balance": money_str(run.net_amount - paid),
        "revision": run.revision,
    }


def payment_data(row):
    return {
        "id": str(row.pk), "pay_run": str(row.pay_run_id),
        "amount": money_str(row.amount), "method": row.method,
        "reference": row.reference, "paid_on": row.paid_on.isoformat(),
        "recorded_at": row.recorded_at.isoformat(),
        "voided": bool(row.voided_at),
        "void_reason": row.void_reason if row.voided_at else "",
    }


def salary_payload(data, *, creation):
    allowed = {"period", "year", "staff", "basis", "gross_amount", "deductions", "currency", "note"} if creation else {"gross_amount", "deductions", "note", "revision"}
    if set(data) - allowed or (creation and not {"period", "year", "staff", "basis", "gross_amount", "deductions", "currency", "note"} <= set(data)):
        raise ValueError("Champs de rémunération invalides.")
    if not creation and (type(data.get("revision")) is not int or data["revision"] < 1 or not (set(data) & {"gross_amount", "deductions", "note"})):
        raise ValueError("Révision et modification obligatoires.")
    out = {}
    if creation:
        out["staff_id"] = parse_uuid(data["staff"])
        out["year_id"] = parse_uuid(data["year"])
        out["period"] = iso_day(data["period"])
        if out["period"].day != 1:
            raise ValueError("La période doit commencer le premier du mois.")
        if data["basis"] not in BASIS:
            raise ValueError("Base de rémunération invalide.")
        out["basis"] = data["basis"]
        if not isinstance(data["currency"], str) or not CURRENCY.fullmatch(data["currency"]):
            raise ValueError("Devise ISO invalide.")
        out["currency"] = data["currency"]
    for key in ("gross_amount", "deductions"):
        if key in data:
            out[key] = money(data[key], allow_zero=(key=="deductions"))
    if "note" in data:
        if not isinstance(data["note"], str) or len(data["note"].strip()) > 240:
            raise ValueError("Observation invalide.")
        out["note"] = data["note"].strip()
    return out


@require_GET
@authorized
def personnel(request, school_id):
    school, err = gate(request, school_id, "school.payroll.read")
    if err is not None:
        return err
    rows = StaffRecord.objects.filter(school=school).order_by("last_name", "first_name")[:500]
    return JsonResponse({"staff": [
        {"id": str(row.pk), "name": f"{row.first_name} {row.last_name}",
         "staff_code": row.staff_code, "position": row.position, "active": row.active}
        for row in rows
    ]}, headers={"Cache-Control": "private, no-store"})


@require_http_methods(["GET", "POST"])
@authorized
def runs(request, school_id):
    school, err = gate(request, school_id, "school.payroll.read" if request.method == "GET" else "school.payroll.manage")
    if err is not None:
        return err
    if request.method == "GET":
        query = StaffPayRun.objects.filter(school=school).select_related("staff", "year")
        try:
            if request.GET.get("staff"):
                query = query.filter(staff_id=parse_uuid(request.GET["staff"]))
            if request.GET.get("year"):
                year_id = parse_uuid(request.GET["year"])
                if not AcademicYear.objects.filter(school=school, pk=year_id).exists():
                    return error("Année scolaire introuvable.", 422)
                query = query.filter(year_id=year_id)
            elif current_year(school):
                query = query.filter(year=current_year(school))
        except ValueError as exc:
            return error(str(exc))
        items = list(query.order_by("-period", "staff__last_name")[:300])
        return JsonResponse({"runs": [run_data(item) for item in items]},
                            headers={"Cache-Control": "private, no-store"})
    data, err = parse_body(request)
    if err is not None:
        return err
    try:
        fields = salary_payload(data, creation=True)
    except ValueError as exc:
        return error(str(exc))
    staff = StaffRecord.objects.filter(school=school, pk=fields["staff_id"]).first()
    year = AcademicYear.objects.filter(school=school, pk=fields["year_id"]).first()
    if not staff or not year:
        return error("Collaborateur ou année d'un autre établissement.", 404)
    if staff.account_id == request.user.pk:
        return error("Interdiction de préparer sa propre rémunération.", 403)
    if not editable_year(year):
        return error("Année scolaire clôturée.", 409)
    try:
        with transaction.atomic():
            row = StaffPayRun(school=school, prepared_by=request.user, **fields)
            row.full_clean()
            row.save()
            log_event(school, request, "staff_pay_run_prepared", row.pk)
    except ValidationError as exc:
        return error("Dossier de rémunération invalide : " + "; ".join(exc.messages if hasattr(exc,"messages") else ["vérifiez les données."]))
    except IntegrityError:
        return error("Une rémunération existe déjà pour cette période et catégorie.", 409)
    return JsonResponse(run_data(row), status=201, headers={"Cache-Control": "private, no-store"})


@require_http_methods(["GET", "PATCH"])
@authorized
def run_detail(request, school_id, run_id):
    school, err = gate(request, school_id, "school.payroll.read" if request.method=="GET" else "school.payroll.manage")
    if err is not None:
        return err
    if request.method == "GET":
        row = StaffPayRun.objects.select_related("staff", "year").filter(school=school, pk=run_id).first()
        if not row:
            return error("Rémunération introuvable.", 404)
        return JsonResponse({
            "run": run_data(row),
            "payments": [payment_data(p) for p in row.disbursements.order_by("recorded_at")],
        }, headers={"Cache-Control":"private, no-store"})
    data, err = parse_body(request)
    if err is not None:
        return err
    try:
        fields=salary_payload(data, creation=False)
    except ValueError as exc:
        return error(str(exc))
    with transaction.atomic():
        row = StaffPayRun.objects.select_for_update().select_related("staff","year").filter(
            school=school, pk=run_id
        ).first()
        if not row:
            return error("Rémunération introuvable.", 404)
        if not editable_year(row.year) or row.approved_at:
            return error("Paie validée ou exercice clôturé : modification interdite.", 409)
        if row.staff.account_id == request.user.pk:
            return error("Interdiction de modifier sa propre rémunération.", 403)
        if data["revision"] != row.revision:
            return error("Version modifiée. Actualisez la fiche.", 409)
        for name,value in fields.items():
            setattr(row,name,value)
        try:
            row.full_clean()
        except ValidationError:
            return error("Montants ou données de rémunération invalides.")
        row.revision+=1
        row.save()
        log_event(school,request,"staff_pay_run_updated",row.pk,{"revision":row.revision})
    return JsonResponse(run_data(row), headers={"Cache-Control":"private, no-store"})


@require_POST
@authorized
def approve(request, school_id, run_id):
    school, err = gate(request, school_id, "school.payroll.approve")
    if err is not None:
        return err
    data, err = parse_body(request)
    if err is not None:
        return err
    if set(data) != {"revision"} or type(data["revision"]) is not int:
        return error("Révision obligatoire.")
    with transaction.atomic():
        row = StaffPayRun.objects.select_for_update().select_related("staff","year").filter(
            school=school, pk=run_id
        ).first()
        if not row:
            return error("Rémunération introuvable.", 404)
        if not editable_year(row.year) or row.approved_at or row.revision != data["revision"]:
            return error("Paie déjà validée, modifiée ou année clôturée.", 409)
        if request.user.pk in (row.prepared_by_id, row.staff.account_id):
            return error("La préparation et la validation exigent des personnes distinctes.", 403)
        row.approved_by=request.user
        row.approved_at=timezone.now()
        row.revision+=1
        row.full_clean()
        row.save()
        log_event(school,request,"staff_pay_run_approved",row.pk)
    return JsonResponse(run_data(row), headers={"Cache-Control":"private, no-store"})


@require_POST
@authorized
def pay(request, school_id, run_id):
    school, err = gate(request, school_id, "school.payroll.pay")
    if err is not None:
        return err
    data, err = parse_body(request)
    if err is not None:
        return err
    if set(data) != {"amount", "method", "reference", "paid_on", "idempotency_key"}:
        return error("Champs de règlement invalides.")
    try:
        amount=money(data["amount"])
        if data["method"] not in METHOD or not isinstance(data["method"],str):
            raise ValueError("Mode de paiement déclaré invalide.")
        reference=data["reference"]
        if not isinstance(reference,str) or not 2<=len(reference.strip())<=120:
            raise ValueError("Référence du justificatif obligatoire.")
        day=iso_day(data["paid_on"])
        idem=parse_uuid(data["idempotency_key"])
        if day>timezone.localdate():
            raise ValueError("Date de paiement future interdite.")
    except ValueError as exc:
        return error(str(exc))
    with transaction.atomic():
        # Serialize all salary disbursements for the same establishment and
        # idempotency key, then lock the target obligation before allocating.
        school.__class__.objects.select_for_update().get(pk=school.pk)
        previous=StaffPayDisbursement.objects.filter(school=school,idempotency_key=idem).first()
        if previous:
            if (previous.pay_run_id==run_id and previous.amount==amount and
                previous.method==data["method"] and previous.reference==reference.strip() and
                previous.paid_on==day):
                return JsonResponse(payment_data(previous),headers={"Cache-Control":"private, no-store"})
            return error("Clé anti-doublon réutilisée avec d'autres informations.",409)
        run=StaffPayRun.objects.select_for_update().select_related("staff","year").filter(
            school=school,pk=run_id
        ).first()
        if not run:
            return error("Rémunération introuvable.",404)
        if not run.approved_at or not editable_year(run.year):
            return error("Paie non validée ou année clôturée.",409)
        if run.staff.account_id==request.user.pk:
            return error("Impossible d'enregistrer son propre versement.",403)
        if cleared_sum(run)+amount>run.net_amount:
            return error("Montant supérieur au reste à payer.",409)
        payment=StaffPayDisbursement(
            school=school,pay_run=run,amount=amount,method=data["method"],
            reference=reference.strip(),paid_on=day,idempotency_key=idem,recorded_by=request.user,
        )
        payment.full_clean()
        payment.save()
        log_event(school,request,"staff_pay_disbursed",payment.pk,{"pay_run":str(run.pk)})
    return JsonResponse(payment_data(payment),status=201,headers={"Cache-Control":"private, no-store"})


@require_POST
@authorized
def void(request,school_id,payment_id):
    school,err=gate(request,school_id,"school.payroll.reverse")
    if err is not None:
        return err
    data,err=parse_body(request)
    if err is not None:
        return err
    reason=data.get("reason")
    if set(data)!={"reason"} or not isinstance(reason,str) or not 10<=len(reason.strip())<=240:
        return error("Motif d'annulation de 10 à 240 caractères requis.")
    with transaction.atomic():
        payment=StaffPayDisbursement.objects.select_for_update().select_related("pay_run__staff","pay_run__year").filter(
            school=school,pk=payment_id
        ).first()
        if not payment:
            return error("Versement introuvable.",404)
        if payment.voided_at or not editable_year(payment.pay_run.year):
            return error("Versement déjà annulé ou année clôturée.",409)
        if request.user.pk in (payment.recorded_by_id,payment.pay_run.staff.account_id):
            return error("L'annulation exige un autre contrôleur.",403)
        payment.voided_by=request.user
        payment.voided_at=timezone.now()
        payment.void_reason=reason.strip()
        payment.full_clean()
        payment.save(update_fields=["voided_by","voided_at","void_reason"])
        log_event(school,request,"staff_pay_voided",payment.pk,{"pay_run":str(payment.pay_run_id)})
    return JsonResponse(payment_data(payment),headers={"Cache-Control":"private, no-store"})
