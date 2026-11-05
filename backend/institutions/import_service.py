"""CSV/XLSX student import input reader, suggestions and conservative normalizers.

The spreadsheet is never executed, retained, or sent to a third party.
Only a confirmed, server-revalidated preview may reach the database.
"""
import csv
import hashlib
import io
import re
import unicodedata
import zipfile
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

FILE_LIMIT = 3 * 1024 * 1024
ROWS_LIMIT = 500
COLUMNS_LIMIT = 60
CELL_LIMIT = 1200

FIELDS = [
    ("student_code", "Matricule existant"), ("last_name", "Nom de famille *"),
    ("first_name", "Prénom(s) *"), ("date_of_birth", "Date de naissance"),
    ("gender", "Sexe"), ("classroom", "Classe"), ("admission_date", "Date d'admission"),
    ("place_of_birth", "Lieu de naissance"), ("nationality", "Nationalité"),
    ("address", "Adresse de l'élève"), ("previous_school", "Ancienne école"),
    ("guardian_name", "Responsable légal *"), ("guardian_relationship", "Lien de parenté"),
    ("guardian_phone", "Téléphone du responsable"), ("guardian_email", "Email du responsable"),
    ("guardian_profession", "Profession du responsable"), ("guardian_address", "Adresse du responsable"),
]
ALIASES = {
    "student_code": ["matricule", "code eleve", "numero eleve", "numero matricule", "student id", "identifiant eleve"],
    "last_name": ["nom", "noms", "nom eleve", "nom de famille", "patronyme", "surname", "last name", "family name"],
    "first_name": ["prenom", "prenoms", "prenoms eleve", "prenom eleve", "first name", "given name"],
    "date_of_birth": ["date naissance", "date de naissance", "ne le", "nee le", "ddn", "dob", "birth date"],
    "gender": ["sexe", "genre", "sex", "gender"],
    "classroom": ["classe", "classe actuelle", "niveau classe", "class", "salle de classe"],
    "place_of_birth": ["lieu naissance", "lieu de naissance", "ville naissance", "birthplace"],
    "nationality": ["nationalite", "nationality"],
    "address": ["adresse eleve", "adresse apprenant", "domicile eleve", "quartier eleve"],
    "previous_school": ["ancienne ecole", "etablissement precedent", "ecole provenance", "previous school"],
    "admission_date": ["date inscription", "date admission", "admission date"],
    "guardian_name": ["responsable", "responsable legal", "nom parent", "nom tuteur", "contact tuteur", "parent", "tuteur", "guardian", "parent name"],
    "guardian_relationship": ["lien", "lien parente", "parent lien", "relation", "relationship"],
    "guardian_phone": ["telephone parent", "tel parent", "tel responsable", "telephone responsable", "contact parent", "telephone tuteur", "numero parent", "parent phone"],
    "guardian_email": ["email parent", "mail parent", "email responsable", "parent email"],
    "guardian_profession": ["profession parent", "profession responsable", "activite parent"],
    "guardian_address": ["adresse parent", "adresse responsable", "domicile parent"],
}


def normalized(value):
    s = unicodedata.normalize("NFKD", str(value or "")).casefold()
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


LOOKUP = {normalized(alias): key for key, aliases in ALIASES.items() for alias in aliases}


def suggested_mapping(headers, custom_fields=()):
    extra = {normalized(x["label"]): "extra." + x["key"] for x in custom_fields}
    result, used = {}, set()
    for i, label in enumerate(headers):
        key = LOOKUP.get(normalized(label)) or extra.get(normalized(label))
        if key and key not in used:
            result[str(i)] = key
            used.add(key)
    return result


def string_cell(value):
    if isinstance(value, (date, datetime)):
        value = value.date() if isinstance(value, datetime) else value
        return value.isoformat()
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    s = str(value).strip()
    if len(s) > CELL_LIMIT or "\x00" in s:
        raise ValueError("Une cellule dépasse la taille autorisée ou contient un caractère interdit.")
    return s


def parse_upload(upload, sheet="", header_row=1):
    if not upload or not hasattr(upload, "name"):
        raise ValueError("Sélectionnez un fichier CSV ou XLSX.")
    extension = Path(upload.name).suffix.lower()
    if extension not in (".csv", ".xlsx"):
        raise ValueError("Formats autorisés : CSV et XLSX, sans macro.")
    if type(header_row) is not int or not 1 <= header_row <= 10:
        raise ValueError("Ligne d'en-tête invalide (1 à 10).")
    data = upload.read(FILE_LIMIT + 1)
    if len(data) > FILE_LIMIT or not data:
        raise ValueError("Le fichier doit contenir entre 1 octet et 3 Mio.")
    digest = hashlib.sha256(data).hexdigest()
    try:
        if extension == ".csv":
            try:
                raw = data.decode("utf-8-sig")
            except UnicodeDecodeError:
                raw = data.decode("cp1252")
            if "\x00" in raw:
                raise ValueError("Fichier CSV non textuel.")
            sample = raw[:8192]
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
                delimiter = dialect.delimiter
            except csv.Error:
                delimiter = ";" if sample.count(";") >= sample.count(",") else ","
            values = csv.reader(io.StringIO(raw, newline=""), delimiter=delimiter)
            sheet_names, selected = ["CSV"], "CSV"
        else:
            if not zipfile.is_zipfile(io.BytesIO(data)):
                raise ValueError("Classeur XLSX corrompu.")
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                items = archive.infolist()
                if len(items) > 250 or sum(item.file_size for item in items) > 24 * 1024 * 1024:
                    raise ValueError("Classeur XLSX trop volumineux après décompression.")
            book = load_workbook(io.BytesIO(data), read_only=True, data_only=True, keep_links=False)
            sheet_names = book.sheetnames
            selected = sheet or sheet_names[0]
            if selected not in sheet_names:
                raise ValueError("Feuille XLSX inconnue.")
            values = book[selected].iter_rows(values_only=True)
        headers, rows = None, []
        for n, cells in enumerate(values, start=1):
            if n < header_row:
                continue
            if headers is None:
                headers = [string_cell(c)[:100] for c in cells]
                if not headers or len(headers) > COLUMNS_LIMIT or not any(headers):
                    raise ValueError("En-têtes absents ou trop nombreux.")
                if len(set(normalized(c) for c in headers if c)) != len([c for c in headers if c]):
                    raise ValueError("En-têtes répétés : renommez les colonnes ambiguës.")
                continue
            cells = [string_cell(c) for c in cells]
            if any(cells):
                if len(cells) > COLUMNS_LIMIT or len(rows) >= ROWS_LIMIT:
                    raise ValueError("Limite de 500 lignes et 60 colonnes par import.")
                rows.append({"line": n, "cells": cells[:len(headers)] + [""] * max(0, len(headers) - len(cells))})
        if not headers or not rows:
            raise ValueError("Aucune ligne d'élève après les en-têtes.")
        return {"sha256": digest, "headers": headers, "rows": rows, "sheet": selected,
                "sheets": sheet_names, "header_row": header_row}
    except (UnicodeDecodeError, csv.Error, zipfile.BadZipFile, InvalidFileException, KeyError, IndexError) as exc:
        raise ValueError("Fichier CSV/XLSX invalide ou illisible.") from exc
    finally:
        if extension == ".xlsx" and "book" in locals():
            book.close()


def validate_mapping(mapping, headers, config):
    if not isinstance(mapping, dict) or len(mapping) > COLUMNS_LIMIT:
        raise ValueError("Correspondance de colonnes invalide.")
    choices = {key for key, _ in FIELDS}
    choices.update("extra." + q["key"] for q in config.get("custom_fields", []))
    result = {}
    for key, field in mapping.items():
        if not isinstance(key, str) or not key.isdecimal() or int(key) >= len(headers):
            raise ValueError("Indice de colonne invalide.")
        if not isinstance(field, str) or field not in choices:
            raise ValueError("Champ YEM inconnu : vérifiez la fiche d'inscription de l'école.")
        result[str(int(key))] = field
    if len(set(result.values())) != len(result):
        raise ValueError("Deux colonnes pointent vers le même champ YEM.")
    if not {"first_name", "last_name"}.issubset(result.values()):
        raise ValueError("Associez obligatoirement Nom et Prénom(s). Le responsable légal peut être complété ensuite.")
    return result


def parse_date(value):
    if not value:
        return ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return date.fromisoformat(value).isoformat()
    m = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", value)
    if m:
        return date(int(m[3]), int(m[2]), int(m[1])).isoformat()
    raise ValueError("Date invalide : utilisez JJ/MM/AAAA ou AAAA-MM-JJ.")


def parse_gender(value):
    value = normalized(value)
    if not value:
        return ""
    if value in ("m", "masculin", "garcon", "garcons", "male", "homme"):
        return "M"
    if value in ("f", "feminin", "fille", "filles", "female", "femme"):
        return "F"
    raise ValueError("Sexe non reconnu : choisissez F ou M.")
