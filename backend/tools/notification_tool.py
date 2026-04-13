"""
Notification Tool – SMTP Email Notifications
Sends emails to notify users about document processing completion.
"""
import smtplib
import logging
from email.message import EmailMessage
from typing import Any

from backend.config.gcp_config import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
)

logger = logging.getLogger(__name__)

def send_completion_notification(
    recipient_email: str,
    document_id: str,
    filename: str,
    extracted_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Send an email notification to the original sender when an invoice is processed.

    Args:
        recipient_email: The email address to notify.
        document_id:     The ID of the document.
        filename:        The filename of the processed document.
        extracted_data:  The extracted field data to check for human intervention.

    Returns:
        {"success": bool, "error": str | None}
    """
    if not recipient_email or "@" not in recipient_email:
        logger.warning("Invalid recipient email: %s. Skipping notification.", recipient_email)
        return {"success": False, "error": "Invalid recipient email"}

    try:
        # Check for human intervention
        human_intervention = any(
            field.get("manually_edited", False) 
            for field in extracted_data.values() 
            if isinstance(field, dict)
        )

        subject = f"Invoice Processed: {filename}"
        
        intervention_text = ""
        if human_intervention:
            intervention_text = "\nNote: Manual human intervention/editing was required to ensure the accuracy of the extracted data.\n"

        body = (
            f"Hello,\n\n"
            f"The invoice you sent ({filename}) has been successfully processed and sent to the ERP system.\n"
            f"{intervention_text}\n"
            f"Thank you,\n"
            f"Invoice Processing System"
        )

        msg = EmailMessage()
        msg.set_content(body)
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = recipient_email

        logger.info("Sending completion notification to %s for document %s", recipient_email, document_id)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)

        return {"success": True, "error": None}

    except Exception as exc:
        logger.exception("Failed to send notification email: %s", exc)
        return {"success": False, "error": str(exc)}
