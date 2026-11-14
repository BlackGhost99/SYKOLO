"""Normalize school family contact numbers, without assuming WhatsApp availability."""
import re


def normalize_guardian_phone(value):
    if not isinstance(value, str):
        raise ValueError("Numéro du responsable légal obligatoire.")
    number = re.sub(r"[\s.()\-]", "", value.strip())
    # Gabon national numbers (0 + 8 digits) or historical eight-digit forms.
    if re.fullmatch(r"0\d{8}", number):
        number = "+241" + number[1:]
    elif re.fullmatch(r"\d{8}", number):
        number = "+241" + number
    elif number.startswith("00"):
        number = "+" + number[2:]
    if not re.fullmatch(r"\+[1-9]\d{7,14}", number):
        raise ValueError("Téléphone obligatoire au format international (+241...) ou local gabonais.")
    return number
