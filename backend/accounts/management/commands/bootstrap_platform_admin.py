"""One-time, non-public platform administrator bootstrap for a fresh installation."""
import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Create the initial YEM platform administrator from temporary environment secrets."

    def handle(self, *args, **options):
        keys = ("YEM_BOOTSTRAP_USERNAME", "YEM_BOOTSTRAP_EMAIL", "YEM_BOOTSTRAP_PASSWORD")
        values = {key: os.environ.get(key, "") for key in keys}
        if not any(values.values()):
            self.stdout.write("Initialisation administrateur : non demandée.")
            return
        if not all(values.values()):
            raise CommandError("Les trois variables YEM_BOOTSTRAP_* sont obligatoires ensemble.")

        username = values["YEM_BOOTSTRAP_USERNAME"].strip()
        email = values["YEM_BOOTSTRAP_EMAIL"].strip()
        password = values["YEM_BOOTSTRAP_PASSWORD"]
        User = get_user_model()
        if not username or len(username) > 150 or not email or len(email) > 254 or "@" not in email:
            raise CommandError("Identifiant ou adresse email invalide.")
        if len(password) < 16:
            raise CommandError("Mot de passe initial : 16 caractères minimum.")
        candidate = User(username=username, email=email)
        try:
            validate_password(password, user=candidate)
        except ValidationError as error:
            raise CommandError("Mot de passe insuffisant : " + "; ".join(error.messages)) from error

        with transaction.atomic():
            # Never grant admin rights to an existing identity or a populated installation.
            if User.objects.exists():
                self.stdout.write("Initialisation ignorée : des comptes existent déjà.")
                return
            User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(
            "Compte administrateur initial créé. Supprimez immédiatement les variables YEM_BOOTSTRAP_* de Render."
        ))
