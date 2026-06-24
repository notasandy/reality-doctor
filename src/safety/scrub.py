"""Strip secrets from user input *before* it is logged or sent to an LLM.

Reality Doctor users will paste real share links and configs that contain
private keys, UUIDs, passwords and shortIds. We remove the secret material up
front while keeping the diagnostic structure (protocol, transport, sni, flow,
port) that the bot actually needs to help.

This is intentionally conservative: it errs toward over-redacting credentials.
It is not a guarantee — the README still tells users not to paste real secrets.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Share-link schemes we know how to handle.
_SHARE_RE = re.compile(
    r"\b(?:vless|vmess|trojan|ss|tuic|hysteria2?|hy2)://[^\s'\"<>]+",
    re.IGNORECASE,
)

# Query-param names whose VALUE is sensitive (publicKey, shortId, password, ...).
_SECRET_PARAMS = {"pbk", "sid", "password", "pwd", "spx", "key"}

# Standalone UUID (Xray client id).
_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)

# key: "value" / key = value for known-secret keys (JSON or plain text).
_KV_RE = re.compile(
    r"(?i)(\"?\b(?:privateKey|publicKey|password|secret|shortIds?|pbk|sid|pwd)\b\"?\s*[:=]\s*)"
    r"(\"?)([A-Za-z0-9_\-+/=]{6,})(\"?)"
)

_IP_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")


@dataclass
class ScrubResult:
    """Outcome of scrubbing one piece of user text."""
    text: str
    redacted: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.redacted)

    def notice(self) -> str | None:
        """Human-facing line telling the user what we removed."""
        if not self.redacted:
            return None
        # de-duplicate while keeping order
        seen: list[str] = []
        for r in self.redacted:
            if r not in seen:
                seen.append(r)
        return "🔒 I removed from your message: " + ", ".join(seen) + " — I only see the structure, not your secrets."


def _scrub_share_uri(uri: str) -> str:
    """Redact the credential parts of a single share link, keep the structure."""
    parts = urlsplit(uri)
    scheme = parts.scheme.lower()

    # vmess packs everything (id, host, port) into one base64 blob → drop it whole.
    if scheme == "vmess":
        return f"{parts.scheme}://<REDACTED_VMESS_CONFIG>"

    # ss without userinfo is base64(method:password) → drop the blob.
    if scheme == "ss" and "@" not in parts.netloc:
        return f"{parts.scheme}://<REDACTED>"

    host = parts.hostname
    if host is None:
        return f"{parts.scheme}://<REDACTED>"
    host_token = "<SERVER_IP>" if _IP_RE.match(host) else "<SERVER_DOMAIN>"

    netloc = ""
    if "@" in parts.netloc:           # userinfo = UUID or password
        netloc += "<CREDENTIAL>@"
    netloc += host_token
    if parts.port:
        netloc += f":{parts.port}"

    new_q = [
        (k, "<redacted>" if k.lower() in _SECRET_PARAMS else v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
    ]
    # fragment (the #remark label) is dropped entirely.
    return urlunsplit((parts.scheme, netloc, parts.path, urlencode(new_q), ""))


def scrub(text: str) -> ScrubResult:
    """Return text with secrets redacted plus a list of what was removed."""
    redacted: list[str] = []

    def _share_sub(m: re.Match) -> str:
        scheme = m.group(0).split("://", 1)[0].lower()
        redacted.append(f"a {scheme.upper()} link")
        return _scrub_share_uri(m.group(0))

    out = _SHARE_RE.sub(_share_sub, text)

    def _kv_sub(m: re.Match) -> str:
        redacted.append("a key/secret")
        return f"{m.group(1)}{m.group(2)}<redacted>{m.group(4)}"

    out = _KV_RE.sub(_kv_sub, out)

    def _uuid_sub(m: re.Match) -> str:
        redacted.append("a UUID")
        return "<UUID>"

    out = _UUID_RE.sub(_uuid_sub, out)

    return ScrubResult(text=out, redacted=redacted)
