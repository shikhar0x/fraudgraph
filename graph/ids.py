"""ID helpers. Never invent IDs — only derive card_id when the CSV has no card_id column."""
from __future__ import annotations


def device_profile_id(device_info: str, os: str, browser: str, screen: str) -> str:
    parts = [(device_info or "").strip(), (os or "").strip(), (browser or "").strip(), (screen or "").strip()]
    if not any(parts):
        return ""
    return " | ".join(parts).strip()


def stringify(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    text = str(value).strip()
    if text.lower() in {"nan", "none", "nat"}:
        return ""
    return text
