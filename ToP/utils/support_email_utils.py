# ToP/utils/support_email_utils.py

from typing import Optional
from django.core.mail import EmailMessage


def sanitize_email(value: Optional[str]) -> str:
    """
    Minimal cleaning to preserve your existing behavior:
    - strip spaces
    - return "" if missing
    (You can add stronger validation later without changing the service/view contract.)
    """
    if not value:
        return ""
    return str(value).strip()


def sanitize_message(value: Optional[str]) -> str:
    """
    Minimal cleaning:
    - strip
    - return "" if missing
    """
    if not value:
        return ""
    return str(value).strip()


def build_support_subject(sender_email: str) -> str:
    return f"Support Message from {sender_email}"


def build_support_email(*, subject: str, body: str, from_email: str, to_email: str, reply_to_email: str) -> EmailMessage:
    """
    Centralized email construction.
    """
    return EmailMessage(
        subject=subject,
        body=body,
        from_email=from_email,
        to=[to_email],
        reply_to=[reply_to_email],
    )
