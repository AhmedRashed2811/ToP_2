# ToP/services/support_email_service.py

from dataclasses import dataclass
from typing import Optional, Tuple

from django.core.mail import EmailMessage

from ..utils.support_email_utils import (
    sanitize_email,
    sanitize_message,
    build_support_subject,
    build_support_email,
)


@dataclass(frozen=True)
class SupportEmailConfig:
    """
    Central config for Support Email feature.
    You can later move receiver_email to DB/settings without touching the view.
    """
    receiver_email: str = "ahmedrashed2811@gmail.com"


class SupportEmailService:
    """
    Handles validation + email composition + sending.
    Keeps view very thin and testable.
    """

    def __init__(self, config: Optional[SupportEmailConfig] = None):
        self.config = config or SupportEmailConfig()

    def validate(self, sender_email: Optional[str], message: Optional[str]) -> Tuple[bool, str, str]:
        """
        Returns:
          (is_valid, cleaned_sender_email, cleaned_message)
        """
        cleaned_sender = sanitize_email(sender_email)
        cleaned_message = sanitize_message(message)

        if not cleaned_sender or not cleaned_message:
            return False, "", ""

        return True, cleaned_sender, cleaned_message

    def send_support_email(self, sender_email: str, message: str) -> None:
        """
        Sends support email. Raises exceptions if sending fails (fail_silently=False behavior preserved).
        """
        subject = build_support_subject(sender_email)

        email: EmailMessage = build_support_email(
            subject=subject,
            body=message,
            from_email=sender_email,
            to_email=self.config.receiver_email,
            reply_to_email=sender_email,
        )
        email.send(fail_silently=False)
