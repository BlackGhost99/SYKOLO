"""Optional provider adapters for sanitized financial clues. No runtime registration."""
import json
import re
from collections.abc import Callable
from urllib.error import URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .intelligence_engine import COLUMN_INDEX, FINANCIAL_KINDS, FINANCIAL_TYPES

CHAT_ENDPOINTS = {
    "openai": ("https://api.openai.com/v1/chat/completions", "max_completion_tokens"),
    "mistral": ("https://api.mistral.ai/v1/chat/completions", "max_tokens"),
}
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/"
MAX_COLUMNS = 24
MAX_OUTPUT_TOKENS = 1024
MAX_RESPONSE_BYTES = 64 * 1024
REQUEST_TIMEOUT = 8
MODEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
JsonTransport = Callable[[str, dict, dict], dict]


class ProviderError(RuntimeError):
    """Failure safe to report without disclosing credentials or provider content."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def post_json(url: str, headers: dict, payload: dict) -> dict:
    request = Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with build_opener(NoRedirect()).open(request, timeout=REQUEST_TIMEOUT) as response:
            data = response.read(MAX_RESPONSE_BYTES + 1)
        if len(data) > MAX_RESPONSE_BYTES:
            raise ProviderError("Provider response exceeds the allowed size")
        return json.loads(data)
    except (URLError, OSError, ValueError):
        raise ProviderError("Provider request failed") from None


def verify_clues(clues):
    if type(clues) is not dict or not 1 <= len(clues) <= MAX_COLUMNS:
        raise ProviderError("Unsupported number of advisory columns")
    for index, words in clues.items():
        if (type(index) is not str or not COLUMN_INDEX.fullmatch(index)
                or type(words) is not tuple or not 1 <= len(words) <= 8
                or any(type(word) is not str or len(word) > 32 or not any(
                    pattern.fullmatch(word) for _, pattern in FINANCIAL_TYPES
                ) for word in words)):
            raise ProviderError("Unsupported advisory clues")


def unique_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("Duplicate object keys")
    return result


def header_adapter(provider, *, model, api_key, transport: JsonTransport = post_json):
    """Build a callable for explicit server-side use. Construction performs no I/O."""
    if provider not in (*CHAT_ENDPOINTS, "gemini"):
        raise ValueError("Unsupported provider")
    if (not isinstance(model, str) or not MODEL_ID.fullmatch(model)
            or not isinstance(api_key, str) or not api_key.isascii()
            or not api_key or any(ch.isspace() or not ch.isprintable() for ch in api_key)):
        raise ValueError("A valid model and server credential are required")

    def classify(clues):
        verify_clues(clues)
        prompt = (
            "Classify each supplied financial column using its vocabulary clues. "
            "Return a JSON object with exactly the supplied indices as keys and one "
            "category per key. Use ambiguous when evidence is insufficient. Categories: "
            + ", ".join(sorted(FINANCIAL_KINDS))
            + ". Clues: " + json.dumps(clues, ensure_ascii=True, separators=(",", ":"))
        )
        try:
            if provider == "gemini":
                response = transport(
                    f"{GEMINI_ENDPOINT}{model}:generateContent", {"x-goog-api-key": api_key},
                    {"contents": [{"parts": [{"text": prompt}]}],
                     "generationConfig": {"responseMimeType": "application/json",
                                          "maxOutputTokens": MAX_OUTPUT_TOKENS}},
                )
                candidate = response["candidates"][0]
                if candidate["finishReason"] != "STOP":
                    raise ValueError("Incomplete answer")
                content = "".join(
                    part["text"] for part in candidate["content"]["parts"] if not part.get("thought")
                )
            else:
                endpoint, token_field = CHAT_ENDPOINTS[provider]
                response = transport(
                    endpoint, {"Authorization": f"Bearer {api_key}"},
                    {"model": model, "messages": [{"role": "user", "content": prompt}],
                     "response_format": {"type": "json_object"}, token_field: MAX_OUTPUT_TOKENS},
                )
                choice = response["choices"][0]
                if choice["finish_reason"] != "stop" or choice["message"].get("refusal"):
                    raise ValueError("Incomplete answer")
                content = choice["message"]["content"]
            if type(content) is not str or len(content) > MAX_RESPONSE_BYTES:
                raise ValueError("Invalid answer")
            result = json.loads(content, object_pairs_hook=unique_object)
            if (type(result) is not dict or result.keys() != clues.keys()
                    or any(type(value) is not str or value not in FINANCIAL_KINDS
                           for value in result.values())):
                raise ValueError("Invalid categories")
            return result
        except (KeyError, IndexError, AttributeError, TypeError, ValueError, OSError):
            raise ProviderError("Provider returned an unusable answer") from None

    return classify
