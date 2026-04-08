"""
Email Scanner Service
Fetches unread emails natively using imaplib via the fetch_emails tool.
"""
import logging
from typing import Any

from backend.tools.email_tool import fetch_emails

logger = logging.getLogger(__name__)

def scan_for_new_emails() -> list[dict[str, Any]]:
    """
    Scans the configured inbox for new emails and their attachments.
    Uses the existing fetch_emails logic.
    
    Returns:
        List of email payload dicts:
        [
            {
                "subject": str,
                "sender": str,
                "body": str,
                "attachments": [{"filename": str, "local_path": str}]
            },
            ...
        ]
    """
    logger.info("Scanning for new unread emails via Python service...")
    result = fetch_emails(max_emails=10)
    
    if result.get("error"):
        logger.error("Error fetching emails: %s", result["error"])
        return []
        
    emails = result.get("emails", [])
    logger.info("Email scan complete. Found %d email(s).", len(emails))
    return emails
