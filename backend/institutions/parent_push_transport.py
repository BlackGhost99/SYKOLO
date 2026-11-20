"""FCM HTTP v1 transport; no secrets, tokens or response bodies in logs."""
import base64
import json
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, HTTPRedirectHandler, build_opener

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


OAUTH = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class PushError(Exception):
    def __init__(self, *, unregistered=False, retry_after=60, fatal=False):
        super().__init__("FCM delivery unavailable")
        self.unregistered = unregistered
        self.retry_after = retry_after
        self.fatal = fatal


def b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def compact(value):
    return json.dumps(value, separators=(",", ":")).encode("utf-8")


def retry_seconds(value):
    try:
        return max(60, int(value))
    except (TypeError, ValueError):
        try:
            return max(60, int((parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()))
        except (TypeError, ValueError, OverflowError):
            return 60


class FcmTransport:
    def __init__(self, raw_credentials, project, *, timeout=15):
        self.timeout = timeout
        credentials = json.loads(raw_credentials)
        if not re.fullmatch(r"[a-z][a-z0-9-]{4,62}", project) or credentials.get("type") != "service_account":
            raise ValueError("FCM configuration invalid")
        self.email = credentials["client_email"]
        self.key = serialization.load_pem_private_key(credentials["private_key"].encode(), password=None)
        if not isinstance(self.key, rsa.RSAPrivateKey) or self.key.key_size < 2048:
            raise ValueError("FCM signing key invalid")
        self.url = f"https://fcm.googleapis.com/v1/projects/{project}/messages:send"
        self.opener = build_opener(NoRedirect)
        self.access_token = None
        self.expires = 0

    def _post(self, url, data, headers, *, sending=False):
        try:
            with self.opener.open(Request(url, data=data, headers=headers, method="POST"), timeout=self.timeout) as response:
                raw = response.read(65537)
                if len(raw) > 65536:
                    raise PushError()
                return json.loads(raw)
        except HTTPError as exc:
            retry = retry_seconds(exc.headers.get("Retry-After"))
            unregistered = False
            if sending and exc.code == 404:
                try:
                    body = json.loads(exc.read(65536))
                    unregistered = any(d.get("errorCode") == "UNREGISTERED" for d in body.get("error", {}).get("details", []))
                except (ValueError, AttributeError, TypeError):
                    pass
            raise PushError(unregistered=unregistered, retry_after=retry,
                            fatal=not unregistered and exc.code not in (429, 500, 502, 503, 504)) from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise PushError() from None

    def _access(self):
        now = int(time.time())
        if self.access_token and now < self.expires - 60:
            return self.access_token
        claims = {"iss": self.email, "scope": SCOPE, "aud": OAUTH, "iat": now, "exp": now + 3600}
        unsigned = (b64(compact({"alg": "RS256", "typ": "JWT"})) + "." + b64(compact(claims))).encode()
        proof = self.key.sign(unsigned, padding.PKCS1v15(), hashes.SHA256())
        assertion = unsigned.decode() + "." + b64(proof)
        result = self._post(OAUTH, urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion}).encode(),
                            {"Content-Type": "application/x-www-form-urlencoded"})
        token = result.get("access_token")
        if not isinstance(token, str) or not token:
            raise PushError(fatal=True)
        self.access_token = token
        self.expires = now + min(int(result.get("expires_in", 3600)), 3600)
        return token

    def send(self, registration_token):
        # Only generic data, no student/parent/school identifiers or private text.
        payload = {"message": {"token": registration_token, "data": {"kind": "family_update"},
                               "android": {"ttl": "300s", "priority": "HIGH", "collapse_key": "yem_family_update"}}}
        result = self._post(self.url, compact(payload),
                            {"Authorization": "Bearer " + self._access(), "Content-Type": "application/json"}, sending=True)
        if not isinstance(result.get("name"), str):
            raise PushError()
