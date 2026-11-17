"""Private commercial documents, issued by BWETEK rather than by a school.

The ledger is the source of truth. Downloading a document never creates a
contract, changes a balance, or confirms a PSP transaction.
"""
from io import BytesIO
from zoneinfo import ZoneInfo

from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from .finance_document_pdf import _font, _amount, _paragraph, amount_in_words

ACCENT = colors.HexColor("#17634E")
TEXT = colors.HexColor("#1E293B")
MUTED = colors.HexColor("#64748B")
PAPER = colors.HexColor("#F2F6F5")
RED = colors.HexColor("#A11D32")
METHODS = {"especes": "Espèces", "mobile_money": "Mobile Money déclaré",
           "virement": "Virement déclaré", "autre": "Autre règlement déclaré"}
LOC = ZoneInfo("Africa/Libreville")


def invoice_reference(row):
    return f"YEM-FAC-{row.pk:010d}"


def receipt_reference(payment):
    return f"YEM-REC-{payment.pk:010d}"


def amendment_reference(amendment):
    return f"YEM-AV-{amendment.pk:010d}"


def document_links(row, *, school_scope=False):
    school_id = row.year.school_id
    prefix = (f"/api/v1/schools/{school_id}/owner/subscriptions/" if school_scope else
              f"/api/v1/platform/schools/{school_id}/subscriptions/")
    root = prefix + str(row.pk)
    payments = sorted(row.payments.all(), key=lambda p: (p.recorded_at, p.pk))
    return {
        "invoice": {"reference": invoice_reference(row), "url": root + "/invoice"},
        "amendments": [{"id": a.pk, "reference": amendment_reference(a), "amount_xaf": a.amount_xaf,
                        "url": root + f"/amendments/{a.pk}/document"} for a in sorted(row.amendments.all(), key=lambda a: a.revision)],
        "receipts": [{"id": p.pk, "reference": receipt_reference(p),
                      "url": root + f"/payments/{p.pk}/receipt",
                      "amount_xaf": p.amount_xaf, "recorded_at": p.recorded_at.isoformat(),
                      "voided": p.voided_at is not None} for p in payments],
    }


def invoice_lines(row):
    """Use the frozen commercial terms, never the live tariff or roster."""
    items = [(f"{line['label']} — {line['students']} élève(s) × {_amount(line['rate_xaf'], 'XAF')}",
              line["amount_xaf"]) for line in row.lines]
    terms = row.commercial_terms or {}
    if terms.get("period"):
        for label, key, sign in (("Complément de minimum annuel", "minimum_adjustment_xaf", 1),
                                 ("Remise commerciale", "discount_xaf", -1),
                                 ("Mise en service (unique)", "setup_xaf", 1)):
            if terms.get(key):
                items.append((label, sign * terms[key]))
    if sum(amount for _, amount in items) != row.total_xaf:
        raise ValueError("Montants contractuels incohérents : document indisponible.")
    schedule = terms.get("schedule", [])
    if schedule and sum(s["amount_xaf"] for s in schedule) != row.total_xaf:
        raise ValueError("Échéancier incohérent : document indisponible.")
    return items, schedule


def _date(value):
    return timezone.localtime(value, LOC).strftime("%d/%m/%Y à %H:%M")


def render_commercial_document(row, payment=None, *, amendment=None):
    if amendment is not None and (payment is not None or amendment.subscription_id != row.pk):
        raise ValueError("Avenant incompatible.")
    if payment is not None and payment.subscription_id != row.pk:
        raise ValueError("Règlement incompatible.")
    normal, bold = _font()
    def style(size=9, color=TEXT, strong=False, right=False):
        return ParagraphStyle("CommercialDoc", fontName=bold if strong else normal,
                              fontSize=size, leading=size * 1.5, textColor=color,
                              alignment=TA_RIGHT if right else 0)
    def p(value, size=9, color=TEXT, strong=False, right=False):
        return _paragraph(value, style(size, color, strong, right))
    is_receipt = payment is not None
    voided = is_receipt and payment.voided_at is not None
    reference = receipt_reference(payment) if is_receipt else amendment_reference(amendment) if amendment else invoice_reference(row)
    title = "Reçu de règlement commercial" if is_receipt else "Avenant commercial — abonnement YEM" if amendment else "Facture commerciale — abonnement YEM"
    total = payment.amount_xaf if is_receipt else amendment.amount_xaf if amendment else row.total_xaf
    issue = payment.recorded_at if is_receipt else amendment.issued_at if amendment else row.issued_at
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm,
                            topMargin=18*mm, bottomMargin=20*mm,
                            title=f"{title} — {reference}", author="BWETEK Informatyk")
    width = 169*mm
    def table(rows, widths, header=False):
        result = Table(rows, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
        spec = [("VALIGN",(0,0),(-1,-1),"TOP"),
                ("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7),
                ("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8),
                ("ROWBACKGROUNDS",(0,0),(-1,-1),[PAPER,colors.white])]
        if header:
            spec.append(("BACKGROUND",(0,0),(-1,0),ACCENT))
        result.setStyle(TableStyle(spec))
        return result
    story = [p("BWETEK Informatyk",18,ACCENT,True), p("YEM • Gestion scolaire",9,MUTED),
             Spacer(1,6*mm),p(title,16,TEXT,True),p(f"N° {reference}  |  Émis le {_date(issue)}",9,MUTED),
             Spacer(1,5*mm)]
    if voided:
        story.extend([p("ANNULÉ — NE CONSTITUE PLUS UN JUSTIFICATIF DE RÈGLEMENT",11,RED,True),
                      p(f"Écriture annulée le {_date(payment.voided_at)}",9,RED),Spacer(1,4*mm)])
    story.append(table([[p("Émetteur",8,MUTED),p("BWETEK Informatyk — YEM",10,TEXT,True)],
                        [p("Établissement client",8,MUTED),p(row.year.school.name,10,TEXT,True)],
                        [p("Année scolaire",8,MUTED),p(row.year.name)],
                        [p("Référence du contrat",8,MUTED),p(invoice_reference(row))]],
                       [46*mm,width-46*mm]))
    story.append(Spacer(1,5*mm))
    if is_receipt:
        items = [("Règlement enregistré au titre de l’abonnement YEM",total)]
        schedule = []
    elif amendment:
        snapshot = amendment.snapshot
        items = [("Supplément proratisé des effectifs", snapshot["gross_prorata_xaf"])]
        if snapshot["minimum_absorbed_xaf"]:
            items.append(("Couvert par le minimum initial", -snapshot["minimum_absorbed_xaf"]))
        if sum(amount for _, amount in items) != total:
            raise ValueError("Montant d’avenant incohérent.")
        schedule = [{"kind": "avenant", "number": amendment.revision, "due_date": amendment.effective_on.isoformat(), "amount_xaf": total}]
        story.extend([p(f"Avenant n° {amendment.revision} — effet le {amendment.effective_on.isoformat()}",10,ACCENT,True),
                      p(f"Prorata : {snapshot['remaining_days']} / {snapshot['duration_days']} jours"),
                      *[p(f"{line['label']} : +{line['students']} élève(s) × {_amount(line['rate_xaf'], 'XAF')} / an") for line in snapshot["additions"]],Spacer(1,3*mm)])
    else:
        items,schedule = invoice_lines(row)
    rows = [[p("DÉSIGNATION",8,colors.white,True),p("MONTANT (FCFA)",8,colors.white,True,True)]]
    rows.extend([[p(label),p(_amount(amount,"XAF"),9,TEXT,True,True)] for label,amount in items])
    story.extend([table(rows,[width*.72,width*.28],True),Spacer(1,4*mm),
                  table([[p("MONTANT ANNULÉ" if voided else "TOTAL DU RÈGLEMENT DÉCLARÉ" if is_receipt else "TOTAL CONTRACTUEL",10,ACCENT,True),
                          p(_amount(total,"XAF"),13,RED if voided else ACCENT,True,True)]],
                        [width*.66,width*.34]),Spacer(1,3*mm),p(amount_in_words(total,"XAF"),9,MUTED)])
    if is_receipt:
        story.extend([Spacer(1,4*mm),p("Mode : "+METHODS.get(payment.method,"Autre règlement déclaré")),
                      p("Référence déclarée : "+payment.reference),
                      p("Ce reçu atteste uniquement l’enregistrement du règlement par BWETEK. Il ne certifie pas un transfert bancaire ou Mobile Money indépendant.",8,MUTED)])
    else:
        if schedule:
            story.extend([Spacer(1,5*mm),p("Échéancier contractuel",11,ACCENT,True)])
            plan = [[p("ÉCHÉANCE",8,colors.white,True),p("DATE",8,colors.white,True),
                     p("MONTANT (FCFA)",8,colors.white,True,True)]]
            for item in schedule:
                label = "Mise en service" if item["kind"] == "mise_en_service" else f"Avenant {item['number']}" if item["kind"] == "avenant" else f"Versement {item['number']}"
                plan.append([p(label),p(item["due_date"]),p(_amount(item["amount_xaf"],"XAF"),9,TEXT,False,True)])
            story.append(table(plan,[width*.44,width*.26,width*.30],True))
        else:
            story.append(p("Contrat historique : aucun échéancier figé enregistré.",8,MUTED))
        story.extend([Spacer(1,4*mm),p("Cette facture commerciale n’est pas une preuve de paiement. Les reçus de règlement sont délivrés séparément.",8,MUTED)])
    story.extend([Spacer(1,4*mm),p("Document commercial du registre YEM. Identification fiscale et mentions légales de l’émetteur non configurées : ne vaut pas facture fiscale certifiée.",8,MUTED)])
    def footer(canvas, rendered):
        canvas.saveState()
        canvas.setStrokeColor(PAPER)
        canvas.line(18*mm,15*mm,A4[0]-18*mm,15*mm)
        canvas.setFont(normal,7)
        canvas.setFillColor(MUTED)
        canvas.drawString(18*mm,10*mm,"BWETEK Informatyk | Document privé YEM")
        canvas.drawRightString(A4[0]-18*mm,10*mm,f"Page {rendered.page}")
        if voided:
            canvas.translate(A4[0]/2,A4[1]/2)
            canvas.rotate(32)
            canvas.setFillColor(colors.Color(.65,.1,.2,alpha=.18))
            canvas.setFont(bold,44)
            canvas.drawCentredString(0,0,"ANNULÉ")
        canvas.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    response = HttpResponse(buffer.getvalue(),content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{reference}.pdf"'
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-YEM-Document-Reference"] = reference
    response["X-YEM-Document-Status"] = "voided" if voided else "issued"
    return response
