"""Allocate a school-local reference independently of the permanent learner identity."""
import re

from .models import School
from .student_models import Student, StudentNumbering

MAX_NUMBER = 999_999_999_999_999


def render_code(template, digits, number):
    return template.replace("{n}", str(number).zfill(digits))


def largest_number(template, codes):
    before, after = template.casefold().split("{n}")
    pattern = re.compile(re.escape(before) + r"([0-9]+)" + re.escape(after))
    maximum = -1
    for code in codes:
        if match := pattern.fullmatch(code.casefold()):
            maximum = max(maximum, int(match[1]))
    return maximum


def allocate_local_code(school_id, fallback, database):
    # This lock is shared with intake, import, and rule changes.
    School.objects.using(database).select_for_update().get(pk=school_id)
    rule = StudentNumbering.objects.using(database).filter(school_id=school_id, enabled=True).first()
    if rule is None:
        return fallback
    number = rule.next_number
    rows = Student.objects.using(database).filter(school_id=school_id)
    while number <= MAX_NUMBER:
        code = render_code(rule.template, rule.digits, number)
        if not rows.filter(student_code__iexact=code).exists():
            rule.next_number = number + 1
            rule.save(update_fields=["next_number"], using=database)
            return code
        number += 1
    raise ValueError("La série de matricules est épuisée. Configurez une autre série dans les paramètres.")


def synchronize_import(school, codes):
    """Reserve explicitly imported values before assigning numbers to blank rows."""
    rule = StudentNumbering.objects.filter(school=school, enabled=True).first()
    if rule is None:
        return
    next_number = min(largest_number(rule.template, codes), MAX_NUMBER) + 1
    if next_number > rule.next_number:
        rule.next_number = next_number
        rule.save(update_fields=["next_number"])
