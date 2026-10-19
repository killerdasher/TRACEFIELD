"""Redact secrets and authentication material from text destined for logs,
reports, or terminal output.

Pattern rules:
- Key/value patterns keep ONE capturing group (the prefix) so the
  replacement never reintroduces fragments of the secret (the old
  ``password=hunter2`` -> ``[REDACTED]word`` bug).
- Unquoted values stop at ``&`` so query-string siblings survive
  (``?token=X&other=1`` must redact only the secret, never ``other=1``).
- Quoted values (JSON, logs) are consumed whole, so ``&`` inside quotes
  is still redacted.
- An optional quote is tolerated after the key so JSON keys
  (``"token": "..."``) are recognized.
"""

from __future__ import annotations

import re

_REDACTED = "[REDACTED]"


def _kv(keys: str) -> re.Pattern[str]:
    """Key/value secret: value stops at ``&`` (query-string safe); quoted
    values are consumed whole. Exactly ONE capturing group (the prefix)."""
    return re.compile(rf'(?i)\b({keys}["\']?\s*[:=]\s*)(?:"[^"]*"|\'[^\']*\'|[^\s&"\']+)')


def _cookie_kv(keys: str) -> re.Pattern[str]:
    """Cookie-style value: semicolon-separated segments, ``&``-safe,
    quoted values consumed whole. ONE capturing group."""
    return re.compile(
        rf'(?i)\b({keys}["\']?\s*[:=]\s*)'
        rf'(?:"[^"]*"|\'[^\']*\'|(?:[^\s;&"\']+;\s*)*[^\s;&"\']+)'
    )


_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Authorization: allow scheme prefixes, keep the whole quoted or
    # &-delimited-safe value.
    re.compile(
        r'(?i)\b(authorization["\']?\s*[:=]\s*)'
        r"(?:bearer\s+|basic\s+|digest\s+)?"
        r'(?:"[^"]*"|\'[^\']*\'|[^\s&"\']+)'
    ),
    _cookie_kv("set-cookie"),
    _cookie_kv("cookie"),
    # api keys / tokens — suffix variants share one rule set
    _kv("(?:x[_-]?api[_-]?key|api[_-]?key)"),
    _kv("access[_-]?token"),
    _kv("refresh[_-]?token"),
    _kv("token"),
    # password / passwd / pwd — word boundary stops the "hunter2word" bug
    _kv("(?:pass(?:word)?|pwd|secret)"),
    # URL-embedded credentials (2 groups: userinfo prefix + trailing @)
    re.compile(r"(?i)(://[^/\s:@]+:)[^@/\s]+(@)"),
    # Query-string tokens: ?key=, ?sig=, ?token=, ?apikey= ... value stops
    # at & so sibling parameters survive redaction.
    re.compile(r"(?i)([?&](?:api[_-]?key|key|sig|token|access[_-]?token)=)[^&\s\"']+"),
    # Bearer tokens anywhere
    re.compile(r"(?i)\b(bearer\s+)[a-z0-9._\-]{16,}"),
    # AWS access key ids
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    # GitHub tokens (all modern prefixes)
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    # Slack tokens
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    # Google API keys (real keys are AIza+35; tolerate 30..40 so partial
    # or rotated-format keys still redact)
    re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}\b"),
    # OpenAI-style secret keys
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    # JWTs
    re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
    # PEM private key blocks (whole block)
    re.compile(
        r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----"
        r".*?"
        r"-----END (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----",
        re.DOTALL,
    ),
)


def redact_secrets(text: str) -> str:
    """Replace recognized secret material in ``text`` with ``[REDACTED]``."""
    out = text
    for pattern in _PATTERNS:
        groups = pattern.groups
        if groups >= 2:
            # Preserve the prefix (group 1) and optional quote/@ (group 2).
            out = pattern.sub(rf"\g<1>{_REDACTED}\g<2>", out)
        elif groups == 1:
            out = pattern.sub(rf"\g<1>{_REDACTED}", out)
        else:
            out = pattern.sub(_REDACTED, out)
    return out
