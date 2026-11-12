"""Parent-owned child profiles and opt-in school discovery.

A family profile is not an official student record. The school still decides
admission, and verified guardian access is never granted from a submission.
"""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .models import School
from .admission_models import AdmissionApplication


class SchoolPublicListing(models.Model):
    school = models.OneToOneField(School, on_delete=models.CASCADE, primary_key=True, related_name="public_listing")
    published = models.BooleanField(default=False)
    city = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    description = models.CharField(max_length=600, blank=True)
    contact_phone = models.CharField(max_length=45, blank=True)
    cash_at_school = models.BooleanField(default=True)
    revision = models.PositiveIntegerField(default=1)


class FamilyChild(models.Model):
    """Private, account-scoped pre-enrollment details, not school credentials."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="family_children")
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    date_of_birth = models.DateField(null=True, blank=True)
    profile = models.JSONField(default=dict, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class FamilyChildPhoto(models.Model):
    """Tiny compressed portrait in private PostgreSQL storage, not Render's ephemeral disk."""
    child = models.OneToOneField(FamilyChild, on_delete=models.CASCADE, primary_key=True, related_name="portrait")
    data = models.BinaryField()
    content_type = models.CharField(max_length=30, default="image/jpeg")
    updated_at = models.DateTimeField(auto_now=True)


class ParentAdmissionRequest(models.Model):
    """Ownership proof for a submission in the existing school admission flow.

    Payment choice is an intention only; neither this row nor the application
    is a financial receipt or proof of a booked place.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="parent_admission_requests")
    child = models.ForeignKey(FamilyChild, on_delete=models.PROTECT, related_name="admission_requests")
    application = models.OneToOneField(AdmissionApplication, on_delete=models.PROTECT, related_name="parent_request")
    payment_choice = models.CharField(max_length=16, choices=[("cash", "Espèces sur place"), ("online", "Mobile Money en ligne")], default="cash")
    fee_amount_xaf = models.PositiveIntegerField(null=True, blank=True)
    # Snapshot of the school's questions and requirements at submission time.
    form_revision = models.PositiveIntegerField(default=0)
    form_data = models.JSONField(default=dict, blank=True)
    document_requirements = models.JSONField(default=list, blank=True)
    is_demo_cash = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.child_id and self.owner_id and self.child.owner_id != self.owner_id:
            raise ValidationError("Ce profil enfant appartient à un autre compte.")
        if self.application_id and self.owner_id and self.application.submitted_by_id != self.owner_id:
            raise ValidationError("Cette candidature appartient à un autre compte.")


class ParentDocumentUpload(models.Model):
    """Private parent-supplied evidence attached to a document awaiting staff review."""
    document = models.OneToOneField("institutions.AdmissionDocument",
        on_delete=models.CASCADE, primary_key=True, related_name="parent_upload")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT, related_name="+")
    filename = models.CharField(max_length=120)
    content_type = models.CharField(max_length=50)
    content = models.BinaryField()
    size = models.PositiveIntegerField()
    uploaded_at = models.DateTimeField(auto_now=True)
