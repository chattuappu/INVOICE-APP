"""
Email Fetch Tool – ADK Tool
Connects to an IMAP mailbox, fetches unread emails and extracts attachments.
"""
import imaplib
import email
import os
import tempfile
import logging
from email.header import decode_header
from typing import Any

from google.adk.tools import FunctionTool

from backend.config.gcp_config import (
    EMAIL_HOST, EMAIL_PORT, EMAIL_USER, EMAIL_PASSWORD, EMAIL_FOLDER
)

logger = logging.getLogger(__name__)


# ─── Core Implementation ─────────────────────────────────────────────────────────

def fetch_emails(max_emails: int = 10) -> dict[str, Any]:
    """
    Fetch unread emails from the configured inbox and extract PDF/image attachments.

    Args:
        max_emails: Maximum number of unread emails to process per call.

    Returns:
        A dict with keys:
            emails (list): List of email objects, each containing:
                - subject (str)
                - sender (str)
                - body (str)
                - attachments (list[dict]): Each has 'filename' and 'local_path'
            error (str | None): Error message if something went wrong.
    """
    results = []
    try:
        mail = imaplib.IMAP4_SSL(EMAIL_HOST, EMAIL_PORT)
        mail.login(EMAIL_USER, EMAIL_PASSWORD)
        mail.select(EMAIL_FOLDER)

        _, message_ids = mail.search(None, "UNSEEN")
        ids = message_ids[0].split()
        if not ids:
            return {"emails": [], "error": None}

        for msg_id in ids[-max_emails:]:
            _, msg_data = mail.fetch(msg_id, "(RFC822)")
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            subject = _decode_header_value(msg.get("Subject", ""))
            sender = msg.get("From", "")
            body = ""
            attachments = []

            for part in msg.walk():
                content_type = part.get_content_type()
                disposition = str(part.get("Content-Disposition", ""))

                if content_type == "text/plain" and "attachment" not in disposition:
                    try:
                        body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                    except Exception:
                        pass

                if "attachment" in disposition or content_type == "application/pdf":
                    filename = part.get_filename()
                    if filename:
                        filename = _decode_header_value(filename)
                        ext = os.path.splitext(filename)[1].lower()
                        if ext in (".pdf", ".png", ".jpg", ".jpeg", ".tiff"):
                            tmp = tempfile.NamedTemporaryFile(
                                delete=False, suffix=ext, prefix="email_attach_"
                            )
                            tmp.write(part.get_payload(decode=True))
                            tmp.close()
                            attachments.append(
                                {"filename": filename, "local_path": tmp.name}
                            )

            # Mark as seen
            mail.store(msg_id, "+FLAGS", "\\Seen")

            results.append(
                {
                    "subject": subject,
                    "sender": sender,
                    "body": body,
                    "attachments": attachments,
                }
            )

        mail.logout()
        logger.info("Fetched %d emails with attachments.", len(results))
        return {"emails": results, "error": None}

    except Exception as exc:
        logger.exception("Email fetch failed: %s", exc)
        return {"emails": [], "error": str(exc)}


def _decode_header_value(value: str) -> str:
    parts = decode_header(value)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


# ─── ADK Tool Registration ───────────────────────────────────────────────────────

fetch_emails_tool = FunctionTool(func=fetch_emails)
