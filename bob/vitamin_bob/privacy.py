"""Privacy helpers: masking for the screen, a keyed patient key for anything that leaves Kevin."""

import base64
import hashlib
import hmac
import re

from . import config


def norm_phone(phone: str | None) -> str:
    """'+1 412-595 4322' -> '+14125954322' (E.164, as Stuart sends it), so seeded numbers always match."""
    return "".join(ch for ch in (phone or "") if ch.isdigit() or ch == "+")


def mask(phone: str | None) -> str:
    """+919812345678 -> +91 ••••••5678. Every phone number on the dashboard goes through this."""
    if not phone:
        return ""
    if len(phone) <= 6:
        return "•" * len(phone)
    cc = phone[:3] if phone.startswith("+") else ""
    return f"{cc} {'•' * (len(phone) - len(cc) - 4)}{phone[-4:]}".strip()


def patient_key(phone: str) -> str:
    """HMAC-SHA256(hub secret, phone) as 13 base32 characters (64 bits). Sent to Central instead of
    the number. Base32 (mostly letters), not hex, so it practically never contains a phone-like digit run."""
    digest = hmac.new(config.patient_key_secret(), phone.encode(), hashlib.sha256).digest()[:8]
    return base64.b32encode(digest).decode().rstrip("=").lower()


_PHONE = re.compile(r"\+?\d[\d ]{8,}\d")


def mask_text(text: str | None) -> str:
    """Mask every phone number inside free text (e.g. an alert SMS shown on the dashboard)."""
    return _PHONE.sub(lambda m: mask(m.group(0).replace(" ", "")), text or "")
