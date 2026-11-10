"""Two end-to-end school application rehearsals, strictly using disposable test DB.

No paid provider, bank credentials, school fee ledger or production personal
information is involved. The guardrail is a per-school and per-parent allowlist.
"""
import json
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass, AcademicTrack
from .admission_models import AdmissionApplication, AdmissionPolicy
from .admission_policy import policy_key
from .finance_models import FeePayment
from .models import Organization, School, SchoolMember, SchoolRole
from .parent_admission_models import ParentAdmissionRequest, SchoolPublicListing
from .parent_payment_models import ParentPaymentAttempt, AdmissionCashReceipt, SchoolAdmissionFee
from .services import ROLE_TEMPLATES, SECONDARY_ROLE_TEMPLATES
from .student_models import Student, StudentGuardian, Enrollment

@override_settings(PARENT_EMAIL_VERIFICATION_REQUIRED=False)
class DualPilotAdmissionTests(TestCase):
    def setUp(self):
        User=get_user_model()
        org=Organization.objects.create(name="YEM Recette fictive")
        self.school=School.objects.create(
            organization=org,name="Lycée Privé 2 (TEST)",
            school_type="lycee_general",education_cycles=["lycee_general"])
        for code,label,perms in ROLE_TEMPLATES:
            SchoolRole.objects.create(school=self.school,code=code,label=label,permissions=perms)
        # A test proviseur may approve, but does not accept or reverse payments.
        SchoolRole.objects.create(school=self.school,code="proviseur",label="Proviseur",
            permissions=SchoolRole.objects.get(school=self.school,code="direction").permissions)
        self.manager=User.objects.create_user(
            username="manager-test-pay",password="Mot-de-passe-fictif-long-2026!")
        member=SchoolMember.objects.create(school=self.school,user=self.manager,
            role=SchoolRole.objects.get(school=self.school,code="secretariat"))
        member.additional_roles.add(SchoolRole.objects.get(school=self.school,code="tarification"))
        self.secretary=User.objects.create_user(username="secretary-test-pay",password="Mot-de-passe-fictif-long-2026!")
        SchoolMember.objects.create(school=self.school,user=self.secretary,
            role=SchoolRole.objects.get(school=self.school,code="secretariat"))
        self.cashier=User.objects.create_user(username="cashier-test-pay",password="Mot-de-passe-fictif-long-2026!")
        SchoolMember.objects.create(school=self.school,user=self.cashier,
            role=SchoolRole.objects.get(school=self.school,code="econome"))
        self.proviseur=User.objects.create_user(username="head-test-pay",password="Mot-de-passe-fictif-long-2026!")
        SchoolMember.objects.create(school=self.school,user=self.proviseur,
            role=SchoolRole.objects.get(school=self.school,code="proviseur"))
        self.year=AcademicYear.objects.create(school=self.school,code="2026-27",name="2026-2027",
            start_date="2026-09-01",end_date="2027-07-30",status="current")
        cycle=AcademicCycle.objects.create(school=self.school,code="lycee_general",name="Lycée général")
        self.pairs=[]
        for level_code, series, amount in (("seconde","S",2500),("terminale","C",3500)):
            level=AcademicLevel.objects.create(school=self.school,cycle=cycle,code=level_code,name=level_code.title())
            track=AcademicTrack.objects.create(school=self.school,level=level,code=series.lower(),name=series)
            room=AcademicClass.objects.create(school=self.school,year=self.year,level=level,
                track=track,code=level_code+"-"+series.lower(),name=level_code.title()+" "+series,capacity=30)
            AdmissionPolicy.objects.create(school=self.school,year=self.year,level=level,
                scope_key=policy_key(self.year.id,level.id),
                enabled_routes=["direct"],required_documents={"direct":["birth_certificate","previous_reports"]})
            self.pairs.append((room,amount))
        SchoolPublicListing.objects.create(school=self.school,published=True,cash_at_school=True)
        self.client=Client(enforce_csrf_checks=True)

    def login(self,user):
        self.client.force_login(user)
        self.csrf=self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def post(self,path,data):
        return self.client.post("/api/v1/"+path,data=json.dumps(data),
            content_type="application/json",HTTP_X_CSRFTOKEN=self.csrf)

    def good(self,response,status):
        self.assertEqual(response.status_code,status,response.content)
        return response.json()

    def test_both_parents_are_enrolled_with_test_payment_only(self):
        parents=[]
        for name in ("yemtest-parent-s","yemtest-parent-c"):
            self.client.logout()
            self.csrf=self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value
            status=self.good(self.client.get("/api/v1/auth/parents/registration-status"),200)
            self.assertFalse(status["email_verification_required"])
            self.good(self.post("auth/parents/register",{
                "username":name,"first_name":"Parent","last_name":"Fictif",
                "email":name+"@example.test","password":"Long-mot-de-passe-test-2026!",
            }),200)
            parents.append(get_user_model().objects.get(username=name))

        self.login(self.manager)
        amounts={f"{self.year.pk}:{r.level_id}":amount for r,amount in self.pairs}
        config=self.good(self.post(f"schools/{self.school.pk}/demo-admission-payments",{
            "revision":0,"enabled":True,"level_amounts_xaf":amounts,
            "allowed_usernames":[p.username for p in parents],
        }),200)
        self.assertEqual(config["level_amounts_xaf"],amounts)

        for idx,((room,amount),parent) in enumerate(zip(self.pairs,parents),1):
            self.client.logout()
            self.csrf=self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value
            self.good(self.post("auth/login",{
                "username":parent.username,"password":"Long-mot-de-passe-test-2026!","scope":"parent",
            }),200)
            self.csrf=self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value
            listed=self.good(self.client.get("/api/v1/parents/catalog"),200)
            school=next(s for s in listed["schools"] if s["id"]==str(self.school.pk))
            classroom=next(c for c in school["classes"] if c["id"]==str(room.pk))
            self.assertTrue(classroom["demo_payment_available"])
            self.assertEqual(classroom["demo_fee_amount_xaf"],amount)
            child=self.good(self.post("parents/family-children",{
                "first_name":f"TEST-{idx}","last_name":"ESSAI-YEM",
                "date_of_birth":"2010-01-02" if idx==1 else "2008-01-02",
            }),201)
            submission=self.good(self.post("parents/applications",{
                "child":child["id"],"classroom":str(room.pk),"route":"direct",
                "payment_choice":"cash","guardian_relationship":"Parent",
                "guardian_phone":"+24107123456","origin_school":"","route_reference":"",
            }),201)
            link=ParentAdmissionRequest.objects.get(pk=submission["id"])
            app=link.application
            self.assertEqual(app.status,"submitted")
            self.assertFalse(Enrollment.objects.filter(student__first_name=f"TEST-{idx}").exists())
            self.assertEqual(link.fee_amount_xaf,amount)
            self.assertTrue(link.is_demo_cash)
            self.assertEqual(self.post(f"schools/{self.school.pk}/admission-cash/{link.pk}/confirm",{
                "reference":"TEST-CAISSE","received_on":"2026-11-10",
                "received_cash":False,"acknowledge_demo":True,
            }).status_code,404)
            self.login(self.secretary)
            cash_base=f"schools/{self.school.pk}/admission-cash/{link.pk}"
            self.assertEqual(self.post(cash_base+"/confirm",{
                "reference":"TEST-CAISSE","received_on":"2026-11-10",
                "received_cash":False,"acknowledge_demo":True,
            }).status_code,403)
            self.login(self.cashier)
            bad=self.post(cash_base+"/confirm",{
                "reference":f"TEST-CAISSE-{idx}","received_on":"2026-11-10",
                "received_cash":True,"acknowledge_demo":False,
            })
            self.assertEqual(bad.status_code,409,bad.content)
            payload={
                "reference":f"TEST-CAISSE-{idx}","received_on":"2026-11-10",
                "received_cash":False,"acknowledge_demo":True,
            }
            payment=self.good(self.post(cash_base+"/confirm",payload),201)
            self.assertEqual(payment["status"],"simule")
            self.assertFalse(payment["received_confirmed"])
            self.assertIn("0 FCFA reçu",payment["notice"])
            self.good(self.post(cash_base+"/confirm",payload),200)
            self.assertEqual(AdmissionCashReceipt.objects.filter(request=link).count(),1)
            self.assertEqual(ParentPaymentAttempt.objects.filter(request=link).count(),0)
            self.assertEqual(FeePayment.objects.count(),0)
            from .finance_cash_policy import recorded_cash_total
            self.assertEqual(int(recorded_cash_total(
                school=self.school,day=__import__("datetime").date(2026,11,10),
                currency="XAF",user=self.cashier)),0)
            self.login(parent)
            receipt=self.client.get(f"/api/v1/parents/applications/{link.pk}/cash-receipt")
            self.assertEqual(receipt.status_code,200,receipt.content)
            self.assertEqual(receipt["Content-Type"],"application/pdf")
            self.assertTrue(receipt.content.startswith(b"%PDF"))
            state=self.client.get("/api/v1/parents/applications").json()["applications"]
            self.assertEqual(next(x for x in state if x["id"]==str(link.pk))["payment_status"],"simule")
            notices=self.client.get("/api/v1/parents/notifications").json()["notifications"]
            self.assertTrue(any(note["status"]=="cash_simulated" for note in notices))

            self.login(self.secretary)
            base=f"schools/{self.school.pk}/admissions/{app.pk}"
            for code in app.required_documents:
                app.refresh_from_db()
                self.good(self.post(base+"/documents",{
                    "revision":app.revision,"code":code,
                    "reference":f"PIÈCE TEST papier {idx} {code}",
                }),201)
            self.assertEqual(self.post(base+"/decide",{
                "revision":app.revision,"status":"accepted","reason":"Ne peut pas s'auto-approuver",
            }).status_code,403)
            self.login(self.proviseur)
            app.refresh_from_db()
            self.assertEqual(self.post(base+"/decide",{
                "revision":app.revision,"status":"accepted","reason":"Preuves pas encore revues",
            }).status_code,409)
            for doc in app.documents.all():
                app.refresh_from_db()
                self.good(self.post(base+f"/documents/{doc.pk}/review",{
                    "revision":app.revision,"status":"verified","reason":"Vérification TEST",
                }),200)
            app.refresh_from_db()
            self.good(self.post(base+"/decide",{
                "revision":app.revision,"status":"accepted","reason":"Admis après vérification",
            }),200)
            self.login(self.secretary)
            app.refresh_from_db()
            result=self.good(self.post(base+"/convert",{
                "revision":app.revision,"enrolled_on":"2026-11-10",
            }),201)
            self.assertEqual(result["status"],"enrolled")
            pupil=Student.objects.get(school=self.school,first_name=f"TEST-{idx}")
            enrollment=Enrollment.objects.get(school=self.school,student=pupil)
            self.assertEqual(enrollment.classroom,room)
            self.assertTrue(pupil.matricule_yem.startswith("YEM-"))
            self.assertEqual(StudentGuardian.objects.filter(student=pupil).count(),1)
            self.assertEqual(FeePayment.objects.count(),0)
            self.assertEqual(self.client.get(f"/api/v1/schools/{self.school.pk}/classes/{room.pk}/students").status_code,200)

            SchoolMember.objects.create(school=self.school,user=parent,
                role=SchoolRole.objects.get(school=self.school,code="parent"))
            self.login(self.proviseur)
            guardian=StudentGuardian.objects.get(student=pupil)
            self.good(self.post(f"schools/{self.school.pk}/parent-links",{
                "guardian":str(guardian.pk),"username":parent.username,
            }),201)
            self.login(parent)
            linked=self.good(self.client.get("/api/v1/parents/children"),200)
            self.assertTrue(any(p["student"]==str(pupil.pk) for p in linked["children"]))

        self.assertEqual(Enrollment.objects.filter(school=self.school).count(),2)
        self.assertEqual({e.classroom.name for e in Enrollment.objects.filter(school=self.school).select_related("classroom")},
                         {"Seconde S","Terminale C"})
        self.assertEqual(AdmissionCashReceipt.objects.filter(school=self.school).count(),2)
        self.assertEqual(ParentPaymentAttempt.objects.filter(school=self.school).count(),0)
        self.assertEqual(FeePayment.objects.filter(school=self.school).count(),0)

    def test_non_authorized_parent_cannot_fake_pay(self):
        outsider=get_user_model().objects.create_user(username="nonpilot",password="Other-long-test-password-2026!")
        self.login(outsider)
        catalog=self.client.get("/api/v1/parents/catalog").json()
        school=next(s for s in catalog["schools"] if s["id"]==str(self.school.pk))
        self.assertFalse(any(c["demo_payment_available"] for c in school["classes"]))


    def test_real_cash_is_confirmed_only_after_cashier_receives_money(self):
        parent=get_user_model().objects.create_user(
            username="parent-physique-test",password="Password-test-cash-2026!",
            first_name="Parent",last_name="Guichet",email="parent-guichet@example.test",
        )
        room,amount=self.pairs[0]
        SchoolAdmissionFee.objects.create(school=self.school,year=self.year,level=room.level,
            amount_xaf=amount,active=True)
        self.login(parent)
        child=self.good(self.post("parents/family-children",{
            "first_name":"TEST-CASH","last_name":"ESSAI","date_of_birth":"2010-04-02",
        }),201)
        request=self.good(self.post("parents/applications",{
            "child":child["id"],"classroom":str(room.pk),
            "route":"direct","payment_choice":"cash","guardian_relationship":"Parent",
            "guardian_phone":"+24107123456","origin_school":"","route_reference":"",
        }),201)
        link=ParentAdmissionRequest.objects.get(pk=request["id"])
        self.assertFalse(link.is_demo_cash)
        self.assertEqual(link.fee_amount_xaf,amount)
        cash_path=f"schools/{self.school.pk}/admission-cash/{link.pk}"
        self.assertEqual(self.client.get(
            f"/api/v1/parents/applications/{link.pk}/cash-receipt"
        ).status_code,404)
        self.login(self.proviseur)
        self.assertEqual(self.post(cash_path+"/confirm",{
            "reference":"FAUX-PROVISEUR","received_on":"2026-11-10",
            "received_cash":True,"acknowledge_demo":False,
        }).status_code,403)
        self.login(self.cashier)
        self.assertEqual(self.post(cash_path+"/confirm",{
            "reference":"CAISSE-NON-RECU","received_on":"2026-11-10",
            "received_cash":False,"acknowledge_demo":True,
        }).status_code,409)
        real=self.good(self.post(cash_path+"/confirm",{
            "reference":"CASH-TEST-RECU","received_on":"2026-11-10",
            "received_cash":True,"acknowledge_demo":False,
        }),201)
        self.assertEqual(real["status"],"recu")
        self.assertTrue(real["received_confirmed"])
        self.assertEqual(FeePayment.objects.count(),0)
        from datetime import date
        from .finance_cash_policy import recorded_cash_total
        self.assertEqual(int(recorded_cash_total(
            school=self.school,day=date(2026,11,10),
            currency="XAF",user=self.cashier)),amount)
        self.login(parent)
        state=self.client.get("/api/v1/parents/applications").json()["applications"]
        row=next(x for x in state if x["id"]==str(link.pk))
        self.assertTrue(row["paid_confirmed"])
        self.assertEqual(row["payment_status"],"recu")
        self.assertTrue(row["cash_receipt_url"])
        pdf=self.client.get(f"/api/v1/parents/applications/{link.pk}/cash-receipt")
        self.assertEqual(pdf.status_code,200)
        self.assertEqual(pdf["Content-Type"],"application/pdf")
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        inbox=self.client.get("/api/v1/parents/notifications").json()["notifications"]
        self.assertTrue(any(m["status"]=="cash_received" for m in inbox))
        self.client.force_login(self.proviseur)
        self.assertEqual(self.client.get(
            f"/api/v1/parents/applications/{link.pk}/cash-receipt"
        ).status_code,404)
        self.assertEqual(self.client.get(
            f"/api/v1/schools/{self.school.pk}/admission-cash/{link.pk}/receipt"
        ).status_code,200)


    def test_two_enrolled_pupils_reach_teacher_timetable_grades_and_parent_bulletin(self):
        """All business roles take turns after the real parent/cash/admission sequence.

        The parent journey is replayed entirely in the isolated CI database.
        The teacher receives pupils through roster and timetable, performs a roll
        call and a graded assessment. Parents see only their own published results.
        """
        from copy import deepcopy
        from pedagogy.views import PRESETS
        from .academic_models import AcademicPeriod
        from .models import SchoolSetting
        from .services import key_for_scope
        from .staff_models import StaffRecord, StaffAssignment
        from .curriculum_models import CourseOffering, CourseInstructor

        self.test_both_parents_are_enrolled_with_test_payment_only()
        User = get_user_model()
        from .services import SECONDARY_ROLE_TEMPLATES
        secondary = {code: (label, perms) for code, label, perms in SECONDARY_ROLE_TEMPLATES["lycee_general"]}
        actors = {}
        for code in ("etudes", "vie_scolaire", "enseignant", "comptabilite"):
            if code in secondary:
                label, perms = secondary[code]
                role, _ = SchoolRole.objects.get_or_create(
                    school=self.school, code=code,
                    defaults={"label": label, "permissions": list(perms)},
                )
            else:
                role = SchoolRole.objects.get(school=self.school, code=code)
            user = User.objects.create_user(
                username="journey-"+code, password="Strong-E2E-Passphrase-2026!",
            )
            SchoolMember.objects.create(school=self.school, user=user, role=role)
            actors[code] = user

        grading = deepcopy(next(p["policy"] for p in PRESETS if p["id"] == "numeric-20"))
        SchoolSetting.objects.update_or_create(
            school=self.school, scope_key=key_for_scope({}),
            defaults={"scope": {}, "values": {
                "grading": grading,
                "bulletin": {"title": "Bulletin YEM de recette", "precision": 2,
                             "show_score": True, "show_label": True,
                             "show_rank": False, "missing_entry": "exclude"},
                "attendance": {"statuses": [
                    {"code": "p", "label": "Présent", "group": "present"},
                    {"code": "a", "label": "Absent", "group": "absent"},
                    {"code": "r", "label": "Retard", "group": "late"},
                ]},
            }},
        )
        period = AcademicPeriod.objects.create(
            school=self.school, year=self.year, code="t1", name="Premier trimestre",
            start_date="2026-09-01", end_date="2026-12-31",
        )
        self.login(actors["etudes"])
        root = f"schools/{self.school.pk}/"
        subject = self.good(self.post(root+"subjects",{
            "code":"maths-recette", "name":"Mathématiques",
        }),201)
        staff = StaffRecord.objects.create(
            school=self.school, staff_code="PROF-TEST",
            first_name="Enseignant",last_name="E2E",
            position="enseignant",account=actors["enseignant"],
        )
        test_students = []
        for i,(room,_) in enumerate(self.pairs,1):
            pupil = Student.objects.get(school=self.school, first_name=f"TEST-{i}")
            enroll = Enrollment.objects.get(school=self.school, student=pupil, year=self.year)
            assignment = StaffAssignment.objects.create(
                school=self.school,staff=staff,year=self.year,
                classroom=room,duty="enseignant",
            )
            course=self.good(self.post(root+"courses", {
                "year":str(self.year.pk),"classroom":str(room.pk),
                "subject":subject["id"],"coefficient":"3",
            }),201)
            instructor=self.good(self.post(root+f"courses/{course['id']}/instructors", {
                "staff_assignment":str(assignment.pk),
            }),201)
            slot=self.good(self.post(root+"timetable/slots",{
                "year":str(self.year.pk),"code":f"test-matin-{i}",
                "label":f"Créneau recette {i}",
                "start_time":"08:00" if i==1 else "09:00",
                "end_time":"09:00" if i==1 else "10:00",
            }),201)
            entry=self.good(self.post(root+"timetable/entries",{
                "course":course["id"],"instructor":instructor["id"],
                "slot":slot["id"],"weekday":1,
                "effective_from":"2026-09-01","effective_to":"2026-12-31",
            }),201)
            self.assertEqual(entry["classroom"],str(room.pk))
            test_students.append((pupil,enroll,room,course,entry))

        for i,(pupil,enroll,room,course,entry) in enumerate(test_students,1):
            # Without school.students.read, pedagogical staff may see a scoped roster.
            self.login(actors["etudes"])
            roster = self.good(self.client.get("/api/v1/"+root+f"classes/{room.pk}/students"),200)
            self.assertEqual(len(roster["students"]),1)
            self.assertEqual(self.client.get("/api/v1/"+root+"students").status_code,403)
            self.login(actors["vie_scolaire"])
            self.assertEqual(self.client.get("/api/v1/"+root+f"classes/{room.pk}/students").status_code,200)
            self.assertEqual(self.client.get("/api/v1/"+root+"students").status_code,403)
            self.login(actors["enseignant"])
            teacher_roster=self.good(self.client.get("/api/v1/"+root+f"classes/{room.pk}/students"),200)
            self.assertEqual(teacher_roster["students"][0]["id"],str(pupil.pk))
            teacher_schedule=self.good(self.client.get("/api/v1/"+root+f"timetable/entries?classroom={room.pk}"),200)
            self.assertEqual(len(teacher_schedule["entries"]),1)
            self.assertEqual(teacher_schedule["entries"][0]["subject"],"Mathématiques")
            session=self.good(self.post(root+"attendance/sessions",{
                "classroom":str(room.pk),"date":"2026-11-10",
                "slot":"matin","label":"Appel de classe",
            }),201)
            marked=self.good(self.post(root+f"attendance/sessions/{session['id']}/marks",{
                "marks":[{
                    "enrollment":str(enroll.pk),"status":"p",
                    "note":"","justification":"","justified":False,
                    "revision":0,"reason":"",
                }],
            }),200)
            self.assertEqual(marked["marks"][0]["status"],"p")
            self.login(actors["vie_scolaire"])
            # A teacher can take attendance, but only school life staff finalize it.
            closed=self.good(self.post(root+f"attendance/sessions/{session['id']}/close",{
                "revision":marked["session_revision"],
            }),200)
            self.assertIsNotNone(closed["closed_at"])

            self.login(actors["enseignant"])
            assessment=self.good(self.post(root+f"courses/{course['id']}/assessments",{
                "name":"Contrôle continu de recette", "kind":"devoir",
                "assessment_date":"2026-11-10","weight":"1",
                "period":str(period.pk),
            }),201)
            grade=self.good(self.post(root+f"assessments/{assessment['id']}/grades",{
                "enrollment":str(enroll.pk),"score":16+i,"feedback":"Évaluation de recette",
            }),201)
            self.assertEqual(grade["status"],"calculated")
            # Teacher cannot publish an official bulletin.
            self.assertEqual(self.post(root+"reports",{
                "enrollment":str(enroll.pk),"period":str(period.pk),"revision":0,
            }).status_code,403)

            self.login(self.proviseur)
            self.good(self.post(root+f"assessments/{assessment['id']}/publish",{
                "revision":assessment["revision"],
            }),200)
            report=self.good(self.post(root+"reports",{
                "enrollment":str(enroll.pk),"period":str(period.pk),"revision":0,
            }),201)
            parent=User.objects.get(username="yemtest-parent-s" if i==1 else "yemtest-parent-c")
            self.login(parent)
            reports_before=self.good(self.client.get(
                f"/api/v1/parents/children/{pupil.pk}/reports"
            ),200)
            self.assertEqual(reports_before["reports"],[])
            self.login(self.proviseur)
            self.good(self.post(root+f"reports/{report['id']}/publish",{
                "revision":report["revision"],
            }),200)
            self.login(parent)
            own_reports=self.good(self.client.get(f"/api/v1/parents/children/{pupil.pk}/reports"),200)
            self.assertEqual(len(own_reports["reports"]),1)
            pdf=self.client.get(f"/api/v1/parents/children/{pupil.pk}/reports/{report['id']}/pdf")
            self.assertEqual(pdf.status_code,200)
            self.assertTrue(pdf.content.startswith(b"%PDF"))
            attendance=self.good(self.client.get(f"/api/v1/parents/children/{pupil.pk}/attendance"),200)
            self.assertEqual(len(attendance["attendance"]),1)
            timetable=self.good(self.client.get(f"/api/v1/parents/children/{pupil.pk}/timetable"),200)
            self.assertEqual(len(timetable["entries"]),1)
            self.assertEqual(timetable["entries"][0]["subject"],"Mathématiques")
            other=test_students[1-i][0]
            self.assertEqual(self.client.get(f"/api/v1/parents/children/{other.pk}/reports").status_code,404)
            self.assertEqual(self.client.get(f"/api/v1/parents/children/{other.pk}/timetable").status_code,404)

        # Financial controller must see the cashier queue but cannot accept cash.
        self.login(actors["comptabilite"])
        self.assertEqual(self.client.get("/api/v1/"+root+"admission-cash").status_code,200)
        link=ParentAdmissionRequest.objects.first()
        self.assertEqual(self.post(root+f"admission-cash/{link.pk}/confirm",{
            "reference":"TEST-REFUSE","received_on":"2026-11-10",
            "received_cash":False,"acknowledge_demo":True,
        }).status_code,403)
        self.assertEqual(Enrollment.objects.filter(school=self.school).count(),2)
