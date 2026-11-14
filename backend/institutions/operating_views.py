"""M3.4 — Operating expenditure workflow, separated from school-fee cash and payroll.

Supplier -> proposed budget -> independent budget approval -> expense draft
-> independent expense approval (serialised budget lock) -> manual declared
partial/full disbursements -> independently voidable, retained payment history.
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
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from accounts.views import authorized
from .academic_models import AcademicYear
from .operating_models import OperatingSupplier, OperatingBudget, OperatingExpense, OperatingExpensePayment
from .services import has_permission
from .views import access, refuse, parse_body, log_event

ZERO = Decimal("0.00")
MONEY = re.compile(r"^(?:0|[1-9][0-9]{0,8})(?:\.[0-9]{1,2})?$")
CURRENCY = re.compile(r"^[A-Z]{3}$")
METHODS = {"especes", "virement", "mobile_money", "autre"}


def fail(message, status=422):
    return JsonResponse({"error": message}, status=status, headers={"Cache-Control": "private, no-store"})


def result(data, status=200):
    return JsonResponse(data, status=status, headers={"Cache-Control": "private, no-store"})


def gate(request, school_id, permission):
    school, err = access(request, school_id)
    if err is not None:
        return None, err
    if not has_permission(request.user, school, permission):
        return None, refuse()
    return school, None


def body(request, allowed, required=None):
    data, err = parse_body(request)
    if err is not None:
        return None, err
    if not isinstance(data, dict) or set(data) - allowed or not (required or set()) <= set(data):
        return None, fail("Champs non reconnus ou manquants.")
    return data, None


def txt(value, size, name, *, optional=False):
    if not isinstance(value, str):
        raise ValueError(name + " : texte attendu.")
    v = value.strip()
    if len(v) > size or (not optional and not v):
        raise ValueError(name + " : longueur invalide.")
    return v


def uuidval(value):
    if not isinstance(value, str):
        raise ValueError("Identifiant UUID requis.")
    try:
        return uuid.UUID(value)
    except ValueError:
        raise ValueError("Identifiant UUID invalide.") from None


def money(value):
    if not isinstance(value, str) or not MONEY.fullmatch(value):
        raise ValueError("Montant décimal strictement positif requis.")
    value = Decimal(value).quantize(Decimal("0.01"))
    if value <= ZERO:
        raise ValueError("Le montant doit être supérieur à zéro.")
    return value


def day(value):
    if not isinstance(value, str):
        raise ValueError("Date ISO requise.")
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError()
        return parsed
    except ValueError:
        raise ValueError("Date ISO invalide.") from None


def fmt(value):
    return format(value.quantize(Decimal("0.01")), ".2f")


def validation(exc):
    if hasattr(exc, "message_dict"):
        return fail("; ".join(str(t) for messages in exc.message_dict.values() for t in messages)[:400])
    return fail("; ".join(exc.messages)[:400])


def current_year(school):
    return AcademicYear.objects.filter(school=school, status="current").first()


def year_for(school, raw):
    if raw is None:
        return current_year(school)
    return AcademicYear.objects.filter(school=school, pk=uuidval(raw)).first()


def open_year(year):
    return bool(year and year.status != "closed")


def supplier_data(s):
    return {"id": str(s.pk), "name": s.name, "contact": s.contact,
            "phone": s.phone, "email": s.email, "active": s.active, "revision": s.revision}


def authorised_total(budget):
    return OperatingExpense.objects.filter(
        school=budget.school, budget=budget, approved_at__isnull=False,
    ).aggregate(t=Sum("amount"))["t"] or ZERO


def cleared_total(expense):
    return OperatingExpensePayment.objects.filter(
        school=expense.school, expense=expense, voided_at__isnull=True,
    ).aggregate(t=Sum("amount"))["t"] or ZERO


def budget_data(b):
    authorised = authorised_total(b)
    return {"id": str(b.pk), "year": str(b.year_id), "category": b.category,
            "currency": b.currency, "ceiling": fmt(b.ceiling),
            "committed": fmt(authorised),
            "available": fmt(b.ceiling - authorised) if b.approved_at else "0.00",
            "revision": b.revision, "approved": bool(b.approved_at),
            "proposed_by": str(b.proposed_by_id),
            "approved_by": str(b.approved_by_id) if b.approved_by_id else None}


def expense_data(e):
    paid = cleared_total(e)
    return {"id": str(e.pk), "year": str(e.year_id),
            "budget": str(e.budget_id), "category": e.budget.category, "currency": e.budget.currency,
            "supplier": str(e.supplier_id), "supplier_name": e.supplier.name,
            "label": e.label, "amount": fmt(e.amount), "expense_on": e.expense_on.isoformat(),
            "invoice_reference": e.invoice_reference, "revision": e.revision,
            "paid": fmt(paid), "balance": fmt(e.amount - paid),
            "status": ("draft" if not e.approved_at else "paid" if paid == e.amount
                       else "partially_paid" if paid > ZERO else "approved"),
            "prepared_by": str(e.prepared_by_id),
            "approved_by": str(e.approved_by_id) if e.approved_by_id else None}


def payment_data(p):
    return {"id": str(p.pk), "expense": str(p.expense_id), "amount": fmt(p.amount),
            "method": p.method, "reference": p.reference, "paid_on": p.paid_on.isoformat(),
            "voided": bool(p.voided_at), "void_reason": p.void_reason if p.voided_at else ""}


@never_cache
@require_http_methods(["GET", "POST"])
@authorized
def suppliers(request, school_id):
    school, err = gate(request, school_id, "school.operating.read" if request.method == "GET" else "school.operating.manage")
    if err is not None:
        return err
    if request.method == "GET":
        rows = OperatingSupplier.objects.filter(school=school).order_by("name")[:400]
        return result({"suppliers": [supplier_data(s) for s in rows]})
    data, err = body(request, {"name", "contact", "phone", "email"}, {"name"})
    if err is not None:
        return err
    try:
        values = {"name": txt(data["name"], 180, "Fournisseur"),
                  "contact": txt(data.get("contact", ""), 160, "Contact", optional=True),
                  "phone": txt(data.get("phone", ""), 50, "Téléphone", optional=True),
                  "email": txt(data.get("email", ""), 254, "Courriel", optional=True)}
        with transaction.atomic():
            supplier = OperatingSupplier(school=school, **values)
            supplier.full_clean()
            supplier.save()
            log_event(school, request, "operating_supplier_created", supplier.pk)
    except ValueError as exc:
        return fail(str(exc))
    except ValidationError as exc:
        return validation(exc)
    return result(supplier_data(supplier), 201)


@never_cache
@require_http_methods(["GET", "PATCH"])
@authorized
def supplier_detail(request, school_id, supplier_id):
    school, err = gate(request, school_id, "school.operating.read" if request.method == "GET" else "school.operating.manage")
    if err is not None:
        return err
    if request.method == "GET":
        row = OperatingSupplier.objects.filter(school=school, pk=supplier_id).first()
        return result(supplier_data(row)) if row else fail("Fournisseur introuvable.", 404)
    data, err = body(request, {"name", "contact", "phone", "email", "active", "revision"}, {"revision"})
    if err is not None:
        return err
    if type(data["revision"]) is not int or not set(data).difference({"revision"}):
        return fail("Révision et modification obligatoires.")
    with transaction.atomic():
        row = OperatingSupplier.objects.select_for_update().filter(school=school, pk=supplier_id).first()
        if not row:
            return fail("Fournisseur introuvable.", 404)
        if row.revision != data["revision"]:
            return fail("Fiche modifiée par un autre agent.", 409)
        try:
            for name in ("name", "contact", "phone", "email"):
                if name in data:
                    setattr(row, name, txt(data[name], {"name": 180, "contact": 160, "phone": 50, "email": 254}[name], name, optional=name!="name"))
            if "active" in data:
                if type(data["active"]) is not bool:
                    raise ValueError("État invalide.")
                row.active = data["active"]
            row.full_clean()
        except ValueError as exc:
            return fail(str(exc))
        except ValidationError as exc:
            return validation(exc)
        row.revision += 1
        row.save()
        log_event(school, request, "operating_supplier_updated", row.pk)
    return result(supplier_data(row))


@never_cache
@require_http_methods(["GET", "POST"])
@authorized
def budgets(request, school_id):
    school, err = gate(request, school_id, "school.operating.read" if request.method == "GET" else "school.operating.manage")
    if err is not None:
        return err
    if request.method == "GET":
        try:
            year = year_for(school, request.GET.get("year"))
        except ValueError as exc:
            return fail(str(exc))
        qs = OperatingBudget.objects.filter(school=school)
        if year:
            qs = qs.filter(year=year)
        return result({"budgets": [budget_data(b) for b in qs.order_by("category", "currency")[:200]]})
    data, err = body(request, {"year", "category", "currency", "ceiling"}, {"year", "category", "currency", "ceiling"})
    if err is not None:
        return err
    try:
        year = year_for(school, data["year"])
        if not year:
            return fail("Année d'un autre établissement.", 404)
        if not open_year(year):
            return fail("Année scolaire clôturée.", 409)
        category = txt(data["category"], 100, "Catégorie")
        currency = txt(data["currency"], 3, "Devise")
        if not CURRENCY.fullmatch(currency):
            raise ValueError("Devise ISO invalide.")
        amount = money(data["ceiling"])
        with transaction.atomic():
            budget = OperatingBudget(school=school, year=year, category=category,
                                    currency=currency, ceiling=amount, proposed_by=request.user)
            budget.full_clean()
            budget.save()
            log_event(school, request, "operating_budget_proposed", budget.pk)
    except ValueError as exc:
        return fail(str(exc))
    except ValidationError as exc:
        return validation(exc)
    except IntegrityError:
        return fail("Une enveloppe existe déjà pour cette catégorie, devise et année.", 409)
    return result(budget_data(budget), 201)


@never_cache
@require_http_methods(["GET", "PATCH"])
@authorized
def budget_detail(request, school_id, budget_id):
    school, err = gate(request, school_id, "school.operating.read" if request.method == "GET" else "school.operating.manage")
    if err is not None:
        return err
    if request.method == "GET":
        row = OperatingBudget.objects.filter(school=school, pk=budget_id).first()
        return result(budget_data(row)) if row else fail("Budget introuvable.", 404)
    data, err = body(request, {"revision", "ceiling"}, {"revision", "ceiling"})
    if err is not None:
        return err
    if type(data["revision"]) is not int:
        return fail("Version obligatoire.")
    try:
        cap = money(data["ceiling"])
    except ValueError as exc:
        return fail(str(exc))
    with transaction.atomic():
        row = OperatingBudget.objects.select_for_update().select_related("year").filter(school=school, pk=budget_id).first()
        if not row:
            return fail("Budget introuvable.", 404)
        if row.approved_at or not open_year(row.year):
            return fail("Budget approuvé ou année clôturée : modification refusée.", 409)
        if row.revision != data["revision"]:
            return fail("Budget modifié par un autre agent.", 409)
        row.ceiling = cap
        row.revision += 1
        row.save(update_fields=["ceiling", "revision"])
        log_event(school, request, "operating_budget_updated", row.pk)
    return result(budget_data(row))


@never_cache
@require_POST
@authorized
def approve_budget(request, school_id, budget_id):
    school, err = gate(request, school_id, "school.operating.approve")
    if err is not None:
        return err
    data, err = body(request, {"revision"}, {"revision"})
    if err is not None:
        return err
    if type(data["revision"]) is not int:
        return fail("Révision obligatoire.")
    with transaction.atomic():
        row = OperatingBudget.objects.select_for_update().select_related("year").filter(school=school, pk=budget_id).first()
        if not row:
            return fail("Budget introuvable.", 404)
        if not open_year(row.year) or row.approved_at or row.revision != data["revision"]:
            return fail("Budget déjà validé, obsolète ou année clôturée.", 409)
        if request.user.pk == row.proposed_by_id:
            return fail("L'auteur du budget ne peut pas l'approuver.", 403)
        row.approved_by = request.user
        row.approved_at = timezone.now()
        row.revision += 1
        row.save(update_fields=["approved_by", "approved_at", "revision"])
        log_event(school, request, "operating_budget_approved", row.pk)
    return result(budget_data(row))


def expense_fields(school, data):
    budget = OperatingBudget.objects.select_related("year").filter(
        school=school, pk=uuidval(data["budget"]),
    ).first()
    supplier = OperatingSupplier.objects.filter(school=school, pk=uuidval(data["supplier"])).first()
    if not budget or not supplier:
        raise LookupError("Enveloppe ou fournisseur d'un autre établissement.")
    if not supplier.active:
        raise ValueError("Fournisseur archivé : demande refusée.")
    if not budget.approved_at:
        raise ValueError("Le budget doit être approuvé avant une dépense.")
    if not open_year(budget.year):
        raise ValueError("Année scolaire clôturée.")
    return {
        "budget": budget, "year": budget.year, "supplier": supplier,
        "label": txt(data["label"], 200, "Libellé"),
        "invoice_reference": txt(data["invoice_reference"], 120, "Référence justificative"),
        "expense_on": day(data["expense_on"]), "amount": money(data["amount"]),
    }


@never_cache
@require_http_methods(["GET", "POST"])
@authorized
def expenses(request, school_id):
    school, err = gate(request, school_id, "school.operating.read" if request.method == "GET" else "school.operating.manage")
    if err is not None:
        return err
    if request.method == "GET":
        try:
            year = year_for(school, request.GET.get("year"))
        except ValueError as exc:
            return fail(str(exc))
        qs = OperatingExpense.objects.filter(school=school).select_related("supplier", "budget")
        if year:
            qs = qs.filter(year=year)
        return result({"expenses": [expense_data(row) for row in qs.order_by("-expense_on", "-created_at")[:400]]})
    data, err = body(request, {"budget", "supplier", "label", "invoice_reference", "expense_on", "amount"},
                     {"budget", "supplier", "label", "invoice_reference", "expense_on", "amount"})
    if err is not None:
        return err
    try:
        fields = expense_fields(school, data)
        with transaction.atomic():
            row = OperatingExpense(school=school, prepared_by=request.user, **fields)
            row.full_clean()
            row.save()
            log_event(school, request, "operating_expense_prepared", row.pk)
    except LookupError as exc:
        return fail(str(exc), 404)
    except ValueError as exc:
        return fail(str(exc))
    except ValidationError as exc:
        return validation(exc)
    return result(expense_data(row), 201)


@never_cache
@require_http_methods(["GET", "PATCH"])
@authorized
def expense_detail(request, school_id, expense_id):
    school, err = gate(request, school_id, "school.operating.read" if request.method == "GET" else "school.operating.manage")
    if err is not None:
        return err
    if request.method == "GET":
        row = OperatingExpense.objects.select_related("supplier", "budget").filter(school=school, pk=expense_id).first()
        if not row:
            return fail("Dépense introuvable.", 404)
        return result({"expense": expense_data(row),
                       "payments": [payment_data(p) for p in row.payments.order_by("recorded_at")]})
    data, err = body(request, {"revision", "label", "invoice_reference", "expense_on", "amount", "supplier"}, {"revision"})
    if err is not None:
        return err
    if type(data["revision"]) is not int or not set(data).difference({"revision"}):
        return fail("Version et modification requises.")
    with transaction.atomic():
        row = OperatingExpense.objects.select_for_update().select_related("year", "supplier", "budget").filter(
            school=school, pk=expense_id,
        ).first()
        if not row:
            return fail("Dépense introuvable.", 404)
        if row.approved_at or not open_year(row.year):
            return fail("Dépense déjà approuvée ou exercice clôturé.", 409)
        if row.revision != data["revision"]:
            return fail("Demande modifiée par un autre agent.", 409)
        try:
            if "label" in data:
                row.label = txt(data["label"], 200, "Libellé")
            if "invoice_reference" in data:
                row.invoice_reference = txt(data["invoice_reference"], 120, "Justificatif")
            if "expense_on" in data:
                row.expense_on = day(data["expense_on"])
            if "amount" in data:
                row.amount = money(data["amount"])
            if "supplier" in data:
                new_supplier = OperatingSupplier.objects.filter(
                    school=school, pk=uuidval(data["supplier"]), active=True,
                ).first()
                if not new_supplier:
                    return fail("Fournisseur absent ou archivé.", 404)
                row.supplier = new_supplier
            row.full_clean()
        except ValueError as exc:
            return fail(str(exc))
        except ValidationError as exc:
            return validation(exc)
        row.revision += 1
        row.save()
        log_event(school, request, "operating_expense_updated", row.pk)
    return result(expense_data(row))


@never_cache
@require_POST
@authorized
def approve_expense(request, school_id, expense_id):
    school, err = gate(request, school_id, "school.operating.approve")
    if err is not None:
        return err
    data, err = body(request, {"revision"}, {"revision"})
    if err is not None:
        return err
    if type(data["revision"]) is not int:
        return fail("Révision obligatoire.")
    with transaction.atomic():
        # Lock the spending envelope before checking its commitments to
        # serialise independent approvals competing for the last funds.
        initial = OperatingExpense.objects.filter(school=school, pk=expense_id).values("budget_id").first()
        if not initial:
            return fail("Dépense introuvable.", 404)
        budget = OperatingBudget.objects.select_for_update().select_related("year").filter(
            school=school, pk=initial["budget_id"],
        ).first()
        row = OperatingExpense.objects.select_for_update().select_related("budget", "supplier", "year").filter(
            school=school, pk=expense_id, budget=budget,
        ).first()
        if not budget or not row:
            return fail("Dépense introuvable.", 404)
        if not open_year(row.year) or not budget.approved_at or row.approved_at or row.revision != data["revision"]:
            return fail("Dépense déjà approuvée, modifiée ou année clôturée.", 409)
        if request.user.pk == row.prepared_by_id:
            return fail("Le préparateur ne peut approuver sa propre dépense.", 403)
        if authorised_total(budget) + row.amount > budget.ceiling:
            return fail("Budget insuffisant : la dépense dépasse les fonds non engagés.", 409)
        row.approved_by = request.user
        row.approved_at = timezone.now()
        row.revision += 1
        row.full_clean()
        row.save()
        log_event(school, request, "operating_expense_approved", row.pk)
    return result(expense_data(row))


@never_cache
@require_POST
@authorized
def pay_expense(request, school_id, expense_id):
    school, err = gate(request, school_id, "school.operating.pay")
    if err is not None:
        return err
    keys = {"amount", "method", "reference", "paid_on", "idempotency_key"}
    data, err = body(request, keys, keys)
    if err is not None:
        return err
    try:
        amount = money(data["amount"])
        method = txt(data["method"], 20, "Mode de paiement")
        if method not in METHODS:
            raise ValueError("Mode de paiement déclaré invalide.")
        reference = txt(data["reference"], 120, "Justificatif")
        paid_on = day(data["paid_on"])
        key = uuidval(data["idempotency_key"])
        if paid_on > timezone.localdate():
            raise ValueError("Date future interdite.")
    except ValueError as exc:
        return fail(str(exc))
    with transaction.atomic():
        # The school lock protects the uniqueness decision across requests,
        # and the expense lock protects against overpaying a shared balance.
        school.__class__.objects.select_for_update().get(pk=school.pk)
        previous = OperatingExpensePayment.objects.filter(school=school, idempotency_key=key).first()
        if previous:
            if (previous.voided_at is None and previous.expense_id == expense_id and
                    previous.amount == amount and previous.method == method and
                    previous.reference == reference and previous.paid_on == paid_on):
                return result(payment_data(previous))
            return fail("Clé anti-doublon déjà utilisée avec une autre opération.", 409)
        row = OperatingExpense.objects.select_for_update().select_related("year", "budget", "supplier").filter(
            school=school, pk=expense_id,
        ).first()
        if not row:
            return fail("Dépense introuvable.", 404)
        if not row.approved_at or not open_year(row.year):
            return fail("Dépense non approuvée ou année clôturée.", 409)
        if request.user.pk in (row.prepared_by_id, row.approved_by_id):
            return fail("Le règlement exige un caissier indépendant du préparateur et du contrôleur.", 403)
        if cleared_total(row) + amount > row.amount:
            return fail("Règlement supérieur au solde restant.", 409)
        payment = OperatingExpensePayment(
            school=school, expense=row, amount=amount, method=method,
            reference=reference, paid_on=paid_on, idempotency_key=key, recorded_by=request.user,
        )
        try:
            payment.full_clean()
        except ValidationError as exc:
            return validation(exc)
        payment.save()
        log_event(school, request, "operating_expense_disbursed", payment.pk,
                  {"expense": str(row.pk)})
    return result(payment_data(payment), 201)


@never_cache
@require_POST
@authorized
def void_expense_payment(request, school_id, payment_id):
    school, err = gate(request, school_id, "school.operating.reverse")
    if err is not None:
        return err
    data, err = body(request, {"reason"}, {"reason"})
    if err is not None:
        return err
    try:
        reason = txt(data["reason"], 240, "Motif de l'annulation")
        if len(reason) < 10:
            raise ValueError("Motif de 10 caractères minimum requis.")
    except ValueError as exc:
        return fail(str(exc))
    with transaction.atomic():
        payment = OperatingExpensePayment.objects.select_for_update().select_related(
            "expense__year",
        ).filter(school=school, pk=payment_id).first()
        if not payment:
            return fail("Règlement introuvable.", 404)
        if payment.voided_at or not open_year(payment.expense.year):
            return fail("Règlement déjà annulé ou exercice clôturé.", 409)
        if request.user.pk == payment.recorded_by_id:
            return fail("Un autre contrôleur doit annuler ce règlement.", 403)
        payment.voided_at = timezone.now()
        payment.voided_by = request.user
        payment.void_reason = reason
        payment.full_clean()
        payment.save(update_fields=["voided_at", "voided_by", "void_reason"])
        log_event(school, request, "operating_expense_payment_voided", payment.pk,
                  {"expense": str(payment.expense_id)})
    return result(payment_data(payment))


@never_cache
@require_GET
@authorized
def summary(request, school_id):
    school, err = gate(request, school_id, "school.operating.read")
    if err is not None:
        return err
    try:
        year = year_for(school, request.GET.get("year"))
    except ValueError as exc:
        return fail(str(exc))
    if not year:
        return result({"year": None, "budgets": [], "totals": {}})
    budgets = OperatingBudget.objects.filter(school=school, year=year).order_by("category")
    output = []
    totals = {}
    for budget in budgets[:200]:
        data = budget_data(budget)
        payments = OperatingExpensePayment.objects.filter(
            school=school, expense__budget=budget, voided_at__isnull=True,
        ).aggregate(t=Sum("amount"))["t"] or ZERO
        data["paid"] = fmt(payments)
        data["unpaid_commitments"] = fmt(Decimal(data["committed"]) - payments)
        output.append(data)
        entry = totals.setdefault(budget.currency, {"ceiling": ZERO, "committed": ZERO, "paid": ZERO, "remaining": ZERO})
        entry["ceiling"] += budget.ceiling if budget.approved_at else ZERO
        entry["committed"] += Decimal(data["committed"])
        entry["paid"] += payments
        entry["remaining"] += (budget.ceiling - Decimal(data["committed"])) if budget.approved_at else ZERO
    return result({"year": str(year.pk), "budgets": output,
                   "totals": {currency: {key: fmt(amount) for key, amount in items.items()}
                              for currency, items in totals.items()}})
