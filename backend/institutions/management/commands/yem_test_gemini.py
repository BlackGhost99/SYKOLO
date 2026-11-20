"""One explicit Gemini request with synthetic clues for non-production acceptance."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from institutions.intelligence_providers import ProviderError, header_adapter


class Command(BaseCommand):
    help = "Make one real Gemini request with synthetic clues. Provider billing may apply."

    def handle(self, *args, **options):
        if settings.ENVIRONMENT == "production":
            raise CommandError("Ce test est réservé aux environnements hors production.")
        try:
            advisor = header_adapter(
                "gemini", model=settings.YEM_GEMINI_MODEL, api_key=settings.YEM_GEMINI_API_KEY,
            )
        except ValueError:
            raise CommandError("Clé et modèle Gemini valides requis dans le processus Django.") from None
        try:
            result = advisor({"0": ("solde",), "1": ("versement",)})
        except ProviderError:
            raise CommandError("Gemini n’a pas renvoyé de réponse valide.") from None
        if result != {"0": "balance", "1": "payment_candidate"}:
            raise CommandError("Gemini a répondu, mais le classement attendu est incorrect.")
        self.stdout.write(self.style.SUCCESS("Gemini a classé correctement les deux colonnes fictives."))
