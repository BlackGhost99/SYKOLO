"""Synthetic, loopback-only HTTP load test. Never run against an existing database."""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
import http.client
import json
import math
import os
from pathlib import Path
import socket
import subprocess
import sys
from threading import Barrier
from time import perf_counter, sleep
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PORT = 8765
PUPILS = 100


def guard():
    url = urlsplit(os.environ.get("DATABASE_URL", ""))
    if (os.environ.get("APP_ENV") != "test"
            or os.environ.get("YEM_LOAD_TEST") != "synthetic"
            or url.scheme not in ("postgres", "postgresql")
            or url.hostname not in ("localhost", "127.0.0.1", "::1")
            or unquote(url.path) != "/yem_load_test"
            or url.query or url.fragment
            or os.environ.get("PGHOSTADDR") or os.environ.get("PGSERVICE")):
        raise SystemExit("Refus : PostgreSQL local dédié yem_load_test, APP_ENV=test et YEM_LOAD_TEST=synthetic obligatoires.")
    os.environ.update(DJANGO_SETTINGS_MODULE="config.settings", DJANGO_ALLOWED_HOSTS="127.0.0.1",
                      YEM_PAYMENTS_LIVE_ENABLED="false", YEM_SINGPAY_ENABLED="false",
                      YEM_YEAR_CLOSURE_ENABLED="false",
                      YEM_EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    sys.path.insert(0, str(ROOT / "backend"))


def seed(users):
    from django.contrib.auth import get_user_model
    from django.db import connection, transaction
    from django.test import Client
    from institutions.models import Organization, School, SchoolRole, SchoolMember
    from institutions.academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass
    from institutions.student_models import Student, Enrollment
    from institutions.finance_models import FeeSchedule, FeeCharge, FeePayment
    from institutions.services import ROLE_TEMPLATES
    User = get_user_model()
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        if cursor.fetchone()[0] != "yem_load_test":
            raise SystemExit("Base non autorisée.")
    if School.objects.exists() or User.objects.exists():
        raise SystemExit("Base non vide : aucune modification. Utilisez une base synthétique neuve et migrée.")
    schools, sessions = [], []
    with transaction.atomic():
        for n in range(3):
            org = Organization.objects.create(name=f"LOAD-ORG-{n}")
            school = School.objects.create(organization=org, name=f"LOAD-SCHOOL-{n}")
            role = SchoolRole.objects.create(school=school, code="direction", label="Direction",
                permissions=next(perms for code, _, perms in ROLE_TEMPLATES if code == "direction"))
            year = AcademicYear.objects.create(school=school, code="2026-2027", name="2026-2027",
                start_date=date(2026, 9, 1), end_date=date(2027, 7, 31), status="current")
            cycle = AcademicCycle.objects.create(school=school, code="college", name="Collège")
            level = AcademicLevel.objects.create(school=school, cycle=cycle, code="6e", name="Sixième")
            rooms = [AcademicClass.objects.create(school=school, year=year, level=level,
                code=f"6e-{i}", name=f"6e {i}", capacity=60) for i in range(2)]
            fee = FeeSchedule.objects.create(school=school, year=year, scope_key="", code="inscription",
                label="LOAD tarif", amount=50000, currency="XAF", due_date=date(2026, 10, 1))
            codes = set()
            for i in range(PUPILS):
                code = f"LOAD-{n}-{i:04d}"
                pupil = Student.objects.create(school=school, student_code=code,
                    first_name=f"Fictif{i}", last_name=f"LOAD-{n}")
                enrolled = Enrollment.objects.create(school=school, year=year, classroom=rooms[i % 2],
                    student=pupil, enrolled_on=date(2026, 9, 1))
                FeeCharge.objects.create(school=school, enrollment=enrolled, schedule=fee,
                    amount=50000, label=fee.label, currency="XAF", due_date=fee.due_date)
                codes.add(code)
            schools.append((str(school.pk), str(year.pk), codes, role, school))
        for i in range(users):
            n = i % 3
            _, _, _, role, school = schools[n]
            user = User.objects.create_user(username=f"load-user-{i}")
            SchoolMember.objects.create(school=school, user=user, role=role)
            client = Client()
            client.force_login(user)
            session = client.session
            session["school_id"] = str(school.pk)
            session["login_scope"] = "school"
            session.save()
            sessions.append((n, session.session_key))
    assert FeePayment.objects.count() == 0
    connection.close()
    return schools, sessions


def get(path, key=None):
    conn = http.client.HTTPConnection("127.0.0.1", PORT, timeout=45)
    headers = {"Cookie": f"sessionid={key}"} if key else {}
    start = perf_counter()
    try:
        conn.request("GET", path, headers=headers)
        response = conn.getresponse()
        body = response.read()
        return response.status, body, (perf_counter() - start) * 1000
    finally:
        conn.close()


def trial(schools, sessions, n):
    # Start distinct authenticated users together, then four requests per user.
    barrier = Barrier(n, timeout=60)

    def user(session):
        school_index, key = session
        school, year, codes, _, _ = schools[school_index]
        foreign = schools[(school_index + 1) % 3][0]
        root = f"/api/v1/schools/{school}/"
        routes = [
            ("students", root + f"overview/students?year={year}", 200),
            ("annual", root + f"academic/annual-snapshot?year={year}", 200),
            ("finance", root + f"overview/finance?year={year}&currency=XAF", 200),
            ("foreign_denied", f"/api/v1/schools/{foreign}/overview/students", 403),
        ]
        barrier.wait()
        results = []
        for label, path, expected in routes:
            try:
                status, body, elapsed = get(path, key)
                valid = status == expected
                if valid and expected == 200:
                    data = json.loads(body)
                    if label == "students":
                        valid = {r["student_code"] for r in data["students"]} == codes
                    elif label == "annual":
                        valid = data["year"]["id"] == year and data["stats"]["enrollments"] == PUPILS
                    elif label == "finance":
                        valid = data["currency"] == "XAF"
                        # Verify no foreign identifier in any financial response.
                        valid = valid and all(f"LOAD-{i}" not in body.decode()
                                              for i in range(3) if i != school_index)
                results.append((label, elapsed, valid, status))
            except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException):
                results.append((label, None, False, "exception"))
        return results

    start = perf_counter()
    with ThreadPoolExecutor(max_workers=n) as pool:
        rows = [row for result in pool.map(user, sessions[:n]) for row in result]
    duration = perf_counter() - start
    grouped = defaultdict(list)
    for row in rows:
        grouped[row[0]].append(row)
    metrics = {}
    for label, group in grouped.items():
        times = sorted(row[1] for row in group if row[1] is not None)
        p95 = round(times[math.ceil(.95 * len(times)) - 1], 1) if times else None
        metrics[label] = {"requests": len(group), "errors": sum(not row[2] for row in group),
                          "p95_ms": p95, "max_ms": round(max(times), 1) if times else None,
                          "status_counts": {str(status): sum(row[3] == status for row in group)
                                            for status in set(row[3] for row in group)}}
    return {"virtual_users": n, "requests": len(rows), "duration_s": round(duration, 2),
            "requests_per_second": round(len(rows) / duration, 2), "routes": metrics,
            "errors": sum(not row[2] for row in rows),
            "latency_target_met": all(item["p95_ms"] is not None and item["p95_ms"] <= 5000
                                      for item in metrics.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--levels", nargs="+", type=int, choices=(50, 100, 250, 500), default=[50, 100])
    args = parser.parse_args()
    guard()
    import django
    django.setup()
    from institutions.finance_models import FeeCharge, FeePayment
    # Refuse to connect to an unrelated web server already at this address.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", PORT))
    schools, sessions = seed(max(args.levels))
    process = subprocess.Popen(
        [sys.executable, "-m", "gunicorn", "config.wsgi:application",
         "--bind", f"127.0.0.1:{PORT}", "--workers", "2", "--threads", "8", "--timeout", "60"],
        cwd=ROOT / "backend", stdout=subprocess.DEVNULL,
    )
    try:
        for _ in range(60):
            if process.poll() is not None:
                raise RuntimeError("Serveur synthétique arrêté.")
            try:
                if get("/readyz")[0] == 200:
                    break
            except OSError:
                pass
            sleep(1)
        else:
            raise RuntimeError("Serveur synthétique indisponible.")
        reports = [trial(schools, sessions, n) for n in args.levels]
        integrity = FeeCharge.objects.count() == 3 * PUPILS and FeePayment.objects.count() == 0
        print(json.dumps({"synthetic_only": True, "schools": 3, "pupils": 3 * PUPILS,
                          "gunicorn_workers": 2, "threads_per_worker": 8,
                          "read_only_integrity": integrity, "results": reports}, indent=2))
        # Functional/isolation errors are hard failures; latency is a measured
        # advisory target on shared CI, not a production capacity guarantee.
        return 0 if integrity and all(row["errors"] == 0 for row in reports) else 1
    finally:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
