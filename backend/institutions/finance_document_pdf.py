"""Professional, school-branded PDFs for YEM's financial ledger.

Presentation only: no debit, payment verification or accounting mutation.
Images are read from the school's already validated private branding record.
"""
import re
from decimal import Decimal
from html import escape
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.utils import ImageReader

from .models import SchoolBranding
from .student_models import StudentGuardian


TEXT = colors.HexColor("#1E293B")
MUTED = colors.HexColor("#64748B")
BORDER = colors.HexColor("#DCE3E8")
PAPER = colors.HexColor("#F4F7F8")
ZERO = Decimal("0.00")


def payment_evidence(method, charge_label):
    """Conservative classification compatible with the pending finance safety PR."""
    if method == "simulation" or re.match(
        r"^(?:d[eé]mo)(?:\s*[-—:]|\s*$|\s*\[)", (charge_label or "").strip(), re.I
    ):
        return "simulation"
    if method == "cash":
        return "legacy_unverified"
    return "manual_record"



def _font():
    """Keep accented French text readable; stay functional in minimal containers."""
    source = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    bold = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    if source.is_file() and bold.is_file():
        if "YEMSans" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("YEMSans", str(source)))
            pdfmetrics.registerFont(TTFont("YEMSans-Bold", str(bold)))
            pdfmetrics.registerFontFamily("YEMSans", normal="YEMSans", bold="YEMSans-Bold")
        return "YEMSans", "YEMSans-Bold"
    return "Helvetica", "Helvetica-Bold"


def _amount(value, currency):
    value = Decimal(str(value)).quantize(Decimal("0.01"))
    whole, cents = f"{value:,.2f}".split(".")
    whole = whole.replace(",", " ")
    unit = "FCFA" if currency == "XAF" else currency
    return (whole if cents == "00" else f"{whole},{cents}") + " " + unit


def _words_below_1000(value):
    ones = ("zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf",
            "dix", "onze", "douze", "treize", "quatorze", "quinze", "seize",
            "dix-sept", "dix-huit", "dix-neuf")
    tens = ("", "", "vingt", "trente", "quarante", "cinquante", "soixante")
    def under_100(number):
        if number < 20:
            return ones[number]
        if number < 70:
            t, u = divmod(number, 10)
            return tens[t] + (" et un" if u == 1 else "-" + ones[u] if u else "")
        if number < 80:
            u = number - 60
            return "soixante et onze" if u == 11 else "soixante-" + under_100(u)
        u = number - 80
        return "quatre-vingts" if u == 0 else "quatre-vingt-" + under_100(u)
    if value < 100:
        return under_100(value)
    hundreds, rest = divmod(value, 100)
    prefix = "cent" if hundreds == 1 else ones[hundreds] + " cent"
    if rest:
        return prefix + " " + under_100(rest)
    return prefix + ("s" if hundreds > 1 else "")


def amount_in_words(value, currency):
    """French literal amounts without guessing any school data."""
    value = Decimal(str(value)).quantize(Decimal("0.01"))
    integral = int(value)
    if integral > 9_999_999_999 or integral < 0:
        return _amount(value, currency)
    parts = []
    remaining = integral
    for divisor, singular, plural in (
        (1_000_000_000, "milliard", "milliards"),
        (1_000_000, "million", "millions"),
        (1_000, "mille", "mille"),
    ):
        group, remaining = divmod(remaining, divisor)
        if group:
            group_words = _words_below_1000(group)
            if divisor == 1_000:
                if group_words.endswith("cents") or group_words.endswith("vingts"):
                    group_words = group_words[:-1]
            prefix = "" if divisor == 1_000 and group == 1 else group_words + " "
            parts.append(prefix + (singular if group == 1 else plural))
    if remaining or not parts:
        parts.append(_words_below_1000(remaining))
    label = "francs CFA" if currency == "XAF" else currency
    cents = int((value - integral) * 100)
    return " ".join(parts).capitalize() + " " + label + (
        f" et {cents:02d} centimes" if cents else ""
    )


def school_guardian(student):
    row = StudentGuardian.objects.filter(
        school_id=student.school_id, student_id=student.pk, active=True,
    ).order_by("-is_primary", "pk").first()
    return row.full_name if row else ""


def _paragraph(value, style):
    return Paragraph(escape(str(value or "")).replace("\n", "<br/>"), style)


def _logo(branding):
    if not branding or not branding.logo_data or branding.logo_content_type not in ("image/png", "image/jpeg"):
        return None
    data = bytes(branding.logo_data)
    if len(data) > 350_000:
        return None
    try:
        source = BytesIO(data)
        width, height = ImageReader(source).getSize()
        if not (0 < width <= 5000 and 0 < height <= 5000 and width * height <= 12_000_000):
            return None
        scale = min(25 * mm / width, 23 * mm / height)
        source.seek(0)
        return Image(source, width=width * scale, height=height * scale, hAlign="LEFT")
    except (OSError, ValueError, TypeError):
        return None


def render_school_financial_pdf(
    *, school, title, reference, issued_on, student_name, matricule="",
    classroom="", year="", payer="", rows=(), currency="XAF",
    total=ZERO, paid=None, balance=None, due_on=None, method="",
    external_reference="", cashier="", note="", cancelled=False,
    demo=False, review_required=False, correction=False, discount=None,
    filename="yem-document.pdf", receipt=False,
):
    """Render one document from trusted ledger values; never alter ledger state.

    rows: sequence of (label, Decimal amount); no client-supplied totals.
    paid is used for invoice settlement; receipt total is actual cash received.
    """
    normal_font, bold_font = _font()
    hue = school.primary_color if re.fullmatch(r"#[0-9a-fA-F]{6}", school.primary_color or "") else "#1B664C"
    rgb = tuple(int(hue[i:i+2], 16) for i in (1, 3, 5))
    if sum(rgb[i] * weight for i, weight in enumerate((0.2126, 0.7152, 0.0722))) > 165:
        hue = "#1B664C"  # Keep white table headings legible on pale school themes.
    accent = colors.HexColor(hue)
    branding = SchoolBranding.objects.filter(school=school).first()
    if getattr(issued_on, "tzinfo", None) is not None:
        local_issued = timezone.localtime(issued_on, ZoneInfo("Africa/Libreville"))
        date = local_issued.date()
        issued_text = local_issued.strftime("%d/%m/%Y à %H:%M")
    else:
        date = issued_on.date() if hasattr(issued_on, "date") else issued_on
        issued_text = date.strftime("%d/%m/%Y")
    value = Decimal(str(total))
    font = lambda size=9, color=TEXT, bold=False, align=TA_LEFT, leading=None: ParagraphStyle(
        "YEMDoc", fontName=bold_font if bold else normal_font,
        fontSize=size, leading=leading or size * 1.48, textColor=color,
        alignment=align, spaceAfter=0, allowWidows=0, allowOrphans=0,
    )
    header_style = font(14, accent, True, TA_LEFT, 18)
    heading_style = font(16, TEXT, True)
    subdued = font(8, MUTED)
    body = font(9)
    bold = font(9, TEXT, True)
    amount_style = font(9, TEXT, True, TA_RIGHT)
    tiny = font(7, MUTED)
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=19 * mm, title=f"{title} – {school.name}",
        author=school.name,
    )
    page_width = A4[0] - 36 * mm
    logo = _logo(branding)
    ident_lines = [_paragraph(school.name, header_style)]
    if branding and branding.tagline:
        ident_lines.append(_paragraph(branding.tagline, font(8, MUTED)))
    if branding and branding.city:
        ident_lines.append(_paragraph(branding.city + " — Gabon", subdued))
    # Do not fabricate unconfigured school phone, address or tax identifiers.
    header = Table([[logo or "", ident_lines]], colWidths=[31 * mm, page_width - 31 * mm])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 1.6, accent),
    ]))
    story = [header, Spacer(1, 8 * mm)]
    kind = _paragraph(title.upper(), heading_style)
    ref_line = [_paragraph("N° " + reference, font(8, MUTED)), _paragraph(
        "Émis le " + issued_text, font(8, MUTED, align=TA_RIGHT)
    )]
    title_table = Table([[kind], [Table([ref_line], colWidths=[page_width * .56, page_width * .44])]],
                        colWidths=[page_width])
    title_table.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (0, 0), 7),
    ]))
    story.extend([title_table, Spacer(1, 7 * mm)])
    fields = [
        ("Élève", student_name), ("Classe", classroom),
        ("Matricule", matricule), ("Année scolaire", year),
        ("Responsable / payeur", payer),
    ]
    field_rows = []
    for name, value_text in fields:
        if value_text:
            field_rows.append([_paragraph(name, subdued), _paragraph(value_text, bold)])
    if field_rows:
        info = Table(field_rows, colWidths=[43 * mm, page_width - 43 * mm], hAlign="LEFT")
        info.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PAPER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ]))
        story.extend([info, Spacer(1, 9 * mm)])
    items = [[_paragraph("DÉSIGNATION", font(8, colors.white, True)),
              _paragraph("MONTANT", font(8, colors.white, True, TA_RIGHT))]]
    for label, amount in rows:
        items.append([_paragraph(label, body), _paragraph(_amount(amount, currency), amount_style)])
    if not rows:
        items.append([_paragraph("Aucune ligne", body), _paragraph(_amount(ZERO, currency), amount_style)])
    table = Table(items, colWidths=[page_width * .7, page_width * .3], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), accent),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PAPER]),
        ("LINEBELOW", (0, -1), (-1, -1), .7, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.extend([table, Spacer(1, 5 * mm)])
    totals = []
    if discount is not None and Decimal(str(discount)) > ZERO:
        totals.append(("Prise en charge / bourse", "-" + _amount(discount, currency)))
    if correction:
        totals.append(("MONTANT ANNULÉ", _amount(value, currency)))
    elif receipt:
        totals.append(("TOTAL SIMULÉ" if demo else "MONTANT À RAPPROCHER" if review_required else "TOTAL ENCAISSÉ",
                       _amount(value, currency)))
        if balance is not None:
            totals.append(("Reste dû sur les frais concernés", _amount(balance, currency)))
    else:
        totals.append(("TOTAL FACTURÉ (NET)", _amount(value, currency)))
        if paid is not None:
            totals.append(("Déjà réglé", _amount(paid, currency)))
        if balance is not None:
            totals.append(("RESTE À PAYER", _amount(balance, currency)))
    total_rows = [[_paragraph(name, bold if "TOTAL" in name or "RESTE À PAYER" in name else body),
                   _paragraph(amt, font(10, accent, True, TA_RIGHT) if
                              ("TOTAL" in name or "RESTE À PAYER" in name) else amount_style)]
                  for name, amt in totals]
    totals_table = Table(total_rows, colWidths=[page_width * .6, page_width * .4])
    totals_table.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1, accent),
        ("BACKGROUND", (0, 0), (-1, -1), PAPER),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.extend([totals_table, Spacer(1, 6 * mm)])
    if receipt and not demo and not review_required:
        story.append(_paragraph("Arrêté la présente somme à : " + amount_in_words(value, currency) + ".", body))
    if demo or review_required:
        story.append(_paragraph(
            "AUCUNE PREUVE DE RECETTE RÉELLE" if demo
            else "ÉCRITURE HISTORIQUE NON RAPPROCHÉE : justificatif de caisse requis.",
            font(9, colors.HexColor("#A11D32"), True),
        ))
    if due_on:
        story.append(_paragraph("Date limite de règlement : " + due_on.strftime("%d/%m/%Y"), bold))
    if method:
        names = {
            "especes": "Espèces", "airtel_money": "Airtel Money (déclaré)",
            "moov_money": "Moov Money (déclaré)", "virement": "Virement déclaré",
            "cash": "Espèces historiques (à rapprocher)", "simulation": "Simulation",
            "singpay": "SingPay confirmé par le serveur",
        }
        story.append(_paragraph("Mode de paiement : " + names.get(method, method.replace("_", " ").title()), body))
    if external_reference:
        story.append(_paragraph("Référence de paiement déclarée : " + external_reference, body))
    if cashier:
        story.append(_paragraph("Enregistré par : " + cashier, body))
    if note:
        story.extend([Spacer(1, 4 * mm), _paragraph(note, font(8, MUTED))])
    if not receipt and not correction:
        story.extend([Spacer(1, 3 * mm), _paragraph(
            "Cette facture ne constitue pas une preuve de paiement. Un reçu distinct est remis après "
            "confirmation de chaque encaissement.", font(8, MUTED))])
    if receipt and method and method not in ("especes", "cash"):
        story.extend([Spacer(1, 3 * mm), _paragraph(
            "Paiement enregistré par l'établissement : ce reçu ne constitue pas une attestation "
            "indépendante du prestataire bancaire ou Mobile Money.", font(8, MUTED))])

    def decorate(canvas, rendered):
        canvas.saveState()
        width, height = A4
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(.5)
        canvas.line(18 * mm, 15 * mm, width - 18 * mm, 15 * mm)
        canvas.setFont(normal_font, 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 11 * mm, "Document émis par l'établissement • Généré avec YEM")
        canvas.drawRightString(width - 18 * mm, 11 * mm, f"Page {rendered.page}")
        if cancelled or demo or review_required:
            canvas.translate(width / 2, height / 2)
            canvas.rotate(32)
            canvas.setFillColor(colors.Color(.78, .18, .2, alpha=.19))
            canvas.setFont(bold_font, 33 if demo else 44)
            canvas.drawCentredString(0, 0, "ANNULÉ" if cancelled else "SPÉCIMEN - NON VALABLE" if demo else "À RAPPROCHER")
        canvas.restoreState()

    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return response
