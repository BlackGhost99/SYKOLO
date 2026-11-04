"""Transactional email over HTTPS for Render Free (SMTP ports are blocked).

Requires a verified sender domain, YEM_RESEND_API_KEY and YEM_FROM_EMAIL.
No API key, recipient address, message content or one-time link is logged.
"""
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


class ResendEmailBackend(BaseEmailBackend):
    API_URL = "https://api.resend.com/emails"

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        key = getattr(settings, "YEM_RESEND_API_KEY", "")
        if not key or not settings.DEFAULT_FROM_EMAIL:
            if self.fail_silently:
                return 0
            raise RuntimeError("Envoi HTTPS non configuré.")

        count = 0
        for msg in email_messages:
            # Authentication messages must have a single private recipient.
            if (len(msg.to) != 1 or msg.cc or msg.bcc or msg.attachments
                    or msg.alternatives):
                if self.fail_silently:
                    return count
                raise ValueError("Seuls les e-mails transactionnels individuels sont autorisés.")
            body = json.dumps({
                "from": msg.from_email or settings.DEFAULT_FROM_EMAIL,
                "to": msg.to,
                "subject": msg.subject,
                "text": msg.body,
            }, ensure_ascii=False).encode("utf-8")
            req = Request(
                self.API_URL, data=body, method="POST",
                headers={
                    "Authorization": "Bearer " + key,
                    "Content-Type": "application/json",
                    "User-Agent": "YEM/1.0",
                },
            )
            try:
                with urlopen(req, timeout=8) as resp:
                    if resp.status not in (200, 201, 202):
                        raise RuntimeError("Le fournisseur de messagerie a refusé l'envoi.")
                count += 1
            except (HTTPError, URLError, TimeoutError, OSError) as exc:
                if not self.fail_silently:
                    raise RuntimeError("Le service d'e-mails est temporairement indisponible.") from None
        return count
