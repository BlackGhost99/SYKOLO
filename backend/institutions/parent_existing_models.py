"""Demande d'association d'un compte parent a un eleve deja inscrit.

Aucune recherche d'eleve ni preuve d'identite n'est realisee par cette table.
Seul un agent habilite peut confirmer le lien legal avec le dossier scolaire.
"""
import uuid

from django.conf import settings
from django.db import models

from .models import School
from .student_models import StudentGuardian


class ExistingStudentLinkRequest(models.Model):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (PENDING, "En attente"),
        (APPROVED, "Validée"),
        (REJECTED, "Refusée"),
        (CANCELLED, "Annulée"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="existing_parent_requests")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="existing_student_requests")
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    student_code = models.CharField(max_length=50, blank=True)
    guardian_name = models.CharField(max_length=180)
    contact_phone = models.CharField(max_length=45, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=PENDING, db_index=True)
    linked_guardian = models.ForeignKey(StudentGuardian, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["school", "status", "created_at"], name="yem_link_req_school_idx"),
            models.Index(fields=["owner", "created_at"], name="yem_link_req_owner_idx"),
        ]
