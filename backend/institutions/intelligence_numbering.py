"""Local, advisory discovery of school matricule series; no allocation or writes."""
import re
from collections import Counter

from .student_numbering import MAX_NUMBER, render_code

LIMIT = 10000
RUN = re.compile(r"[0-9]+")


def suggest_series(codes):
    # Bound the inspection; the existing locked numbering preview checks ALL
    # school records before saving and allocation, even if this is a sample.
    seen = set()
    groups = {}
    examined = 0
    truncated = False
    for raw in codes:
        if examined >= LIMIT:
            truncated = True
            break
        examined += 1
        code = str(raw or "").strip()
        folded = code.casefold()
        if not code or folded in seen or folded.startswith("yem-"):
            continue
        seen.add(folded)
        for match in RUN.finditer(code):
            digits = match.group()
            if len(digits) > 15:
                continue
            template = code[:match.start()] + "{n}" + code[match.end():]
            fixed = template.replace("{n}", "")
            if (len(template) > 38 or not template.isprintable()
                    or "{" in fixed or "}" in fixed):
                continue
            key = template.casefold()
            group = groups.setdefault(key, {"template": template, "widths": Counter(), "maximum": -1})
            group["widths"][len(digits)] += 1
            group["maximum"] = max(group["maximum"], int(digits))
    candidates = []
    for group in groups.values():
        count = sum(group["widths"].values())
        # A single observed value cannot establish a sequence, except as an
        # explicitly low-evidence proposal when no recurring group exists.
        width = min(group["widths"], key=lambda w: (-group["widths"][w], w))
        next_number = group["maximum"] + 1
        next_code = render_code(group["template"], width, next_number)
        if next_number > MAX_NUMBER or len(next_code) > 50:
            next_number, next_code = None, None
        candidates.append({"template": group["template"], "digits": width,
                           "matched": count, "largest_number": group["maximum"],
                           "next_number": next_number, "next_code": next_code})
    recurring = [item for item in candidates if item["matched"] >= 2]
    candidates = sorted(recurring or candidates,
                        key=lambda c: (-c["matched"], c["template"].casefold()))[:8]
    return {"engine": "local", "examined": examined, "distinct_local_codes": len(seen),
            "truncated": truncated, "candidates": candidates,
            "confirmation_required": True,
            "ambiguous": len(candidates) != 1 or any(c["matched"] < 2 for c in candidates)
                         or truncated or (bool(candidates) and candidates[0]["matched"] < len(seen))}
