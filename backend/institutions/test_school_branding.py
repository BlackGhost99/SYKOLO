"""Le branding scolaire n'a jamais le droit de modifier le branding plateforme YEM."""
import json

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from .models import Organization, OrganizationMember, School, SchoolBranding, SchoolMember, SchoolRole


class SchoolBrandingTests(TestCase):
    def setUp(self):
        User=get_user_model()
        self.founder=User.objects.create_user(username="brand-founder",password="Branding-2026-strong-test!")
        self.director=User.objects.create_user(username="brand-director",password="Branding-2026-strong-test!")
        self.cashier=User.objects.create_user(username="brand-cashier",password="Branding-2026-strong-test!")
        self.stranger=User.objects.create_user(username="brand-outsider",password="Branding-2026-strong-test!")
        owner=Organization.objects.create(name="Organisation tests de marque")
        OrganizationMember.objects.create(organization=owner,user=self.founder,role="founder")
        self.school=School.objects.create(organization=owner,name="Lycée Alpha")
        self.other=School.objects.create(organization=owner,name="Lycée Bêta")
        direction=SchoolRole.objects.create(school=self.school,code="direction",label="Directeur",permissions=[
            "school.view","school.settings.read","school.settings.write"])
        cash=SchoolRole.objects.create(school=self.school,code="econome",label="Économe",permissions=[
            "school.view","school.finance.read","school.finance.receive"])
        SchoolMember.objects.create(school=self.school,user=self.director,role=direction)
        SchoolMember.objects.create(school=self.school,user=self.cashier,role=cash)
        self.base=f"/api/v1/schools/{self.school.pk}/branding"
        self.second=f"/api/v1/schools/{self.other.pk}/branding"

    def as_user(self,user):
        self.client.force_login(user)

    def send(self,route,body):
        return self.client.post(route,json.dumps(body),content_type="application/json")

    def test_owner_can_configure_one_school_without_impacting_another(self):
        self.as_user(self.founder)
        before=self.client.get(self.base).json()
        self.assertEqual(before["revision"],0)
        self.assertIsNone(before["banner_url"])
        reply=self.send(self.base,{"revision":0,"city":"Libreville","tagline":"Savoir et réussite"})
        self.assertEqual(reply.status_code,200,reply.content)
        self.assertEqual(reply.json()["name"],"Lycée Alpha")
        self.assertEqual(reply.json()["city"],"Libreville")
        self.assertEqual(reply.json()["revision"],1)
        self.assertEqual(self.client.get(self.second).json()["city"],"")
        self.assertEqual(School.objects.get(pk=self.school.pk).primary_color,"#1B664C")
        self.assertEqual(self.client.get(self.base).json()["name"],"Lycée Alpha")

    def test_director_can_upload_and_erase_banner_with_school_revision(self):
        self.as_user(self.director)
        sample=b"\x89PNG\r\n\x1a\n"+b"valid image test bytes"+b"IEND"+b"\x00"*8
        image=SimpleUploadedFile("ecole.png",sample,content_type="image/png")
        res=self.client.post(self.base+"/banner",{"revision":"0","image":image})
        self.assertEqual(res.status_code,200,res.content)
        self.assertIn("/branding/banner?v=1",res.json()["banner_url"])
        picture=self.client.get(self.base+"/banner")
        self.assertEqual(picture.status_code,200)
        self.assertEqual(picture.content,sample)
        self.assertEqual(picture["Content-Type"],"image/png")
        self.assertIn("private", picture["Cache-Control"])
        self.assertIn("no-store", picture["Cache-Control"])
        self.assertEqual(self.client.get(self.base+"/logo").status_code,404)
        stale=self.send(self.base,{"revision":0,"city":"Port-Gentil","tagline":""})
        self.assertEqual(stale.status_code,409)
        deleted=self.client.delete(self.base+"/banner",json.dumps({"revision":1}),
                                   content_type="application/json")
        self.assertEqual(deleted.status_code,200,deleted.content)
        self.assertIsNone(deleted.json()["banner_url"])
        self.assertEqual(self.client.get(self.base+"/banner").status_code,404)

    def test_cashier_can_read_but_cannot_change_the_school_identity(self):
        self.as_user(self.director)
        self.send(self.base,{"revision":0,"city":"Libreville","tagline":"Travail"})
        self.as_user(self.cashier)
        self.assertEqual(self.client.get(self.base).json()["city"],"Libreville")
        self.assertEqual(self.send(self.base,{"revision":1,"city":"Franceville","tagline":""}).status_code,403)
        file=SimpleUploadedFile("logo.png",b"\x89PNG\r\n\x1a\n"+"a".encode()*24+b"IEND",content_type="image/png")
        self.assertEqual(self.client.post(self.base+"/logo",{"revision":"1","image":file}).status_code,403)
        self.assertEqual(self.client.delete(self.base+"/logo",json.dumps({"revision":1}),
                         content_type="application/json").status_code,403)

    def test_cross_school_images_are_never_leaked(self):
        self.as_user(self.director)
        self.assertEqual(self.client.get(self.second).status_code,404)
        self.assertEqual(self.client.get(self.second+"/logo").status_code,404)
        self.as_user(self.stranger)
        self.assertEqual(self.client.get(self.base).status_code,404)
        self.assertEqual(self.client.get(self.base+"/banner").status_code,404)

    def test_invalid_upload_and_unexpected_metadata_are_refused(self):
        self.as_user(self.founder)
        self.assertEqual(self.send(self.base,{"revision":0,"city":"Libreville","tagline":"","logo":"YEM"}).status_code,422)
        self.assertEqual(self.send(self.base,{"revision":0,"city":"x"*121,"tagline":""}).status_code,422)
        fake=SimpleUploadedFile("logo.png",b"<html>bad image</html>",content_type="image/png")
        self.assertEqual(self.client.post(self.base+"/logo",{"revision":"0","image":fake}).status_code,422)
        huge=SimpleUploadedFile("logo.jpg",b"\xff\xd8\xff"+b"x"*350_100+b"\xff\xd9",content_type="image/jpeg")
        self.assertEqual(self.client.post(self.base+"/logo",{"revision":"0","image":huge}).status_code,422)
        self.assertFalse(SchoolBranding.objects.filter(school=self.school).exists())
