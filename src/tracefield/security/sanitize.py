"""Strip control sequences from untrusted text before terminal rendering.

Filesystem names, webpage titles, provider responses, and extracted
metadata are attacker-influenced. Rendering raw ANSI/OSC sequences lets a
hostile file manipulate the terminal (clipboard writes, title changes,
cursor movement, fake output). ``sanitize_for_terminal`` removes C0/C1
controls except tab and newline, so untrusted strings can never emit
escape sequences.
"""

from __future__ import annotations

import re

# ESC (0x1b) and C1 controls (0x80-0x9f), plus remaining C0 except \t and \n.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def sanitize_for_terminal(text: str, *, max_length: int | None = None) -> str:
    """Return ``text`` safe for terminal display.

    Removes ANSI/OSC/DCS/C1 control sequences. Tabs and newlines are kept
    because they are formatting the caller controls. ``max_length`` truncates
    the result (with a trailing ellipsis marker) to bound hostile payloads.
    """
    cleaned = _CONTROL_RE.sub("", text)
    if max_length is not None and len(cleaned) > max_length:
        cleaned = cleaned[: max_length - 1] + "…"
    return cleaned
