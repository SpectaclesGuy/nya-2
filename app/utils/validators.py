from __future__ import annotations

import re


_PHONE_RE = re.compile(r"^[0-9]{10,15}$")


def normalize_phone(raw: str) -> str:
    value = (raw or "").strip().replace(" ", "").replace("-", "")
    if not _PHONE_RE.match(value):
        raise ValueError("Invalid phone number")
    return value
