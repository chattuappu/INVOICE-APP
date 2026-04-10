"""
Email Scan Agent – ADK Agent
Scans the configured inbox for new emails and their attachments.
"""
import json
import logging
from typing import Any

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from backend.config.gcp_config import GEMINI_MODEL
from backend.tools.email_tool import fetch_emails_tool

logger = logging.getLogger(__name__)

# ─── System Instruction ───────────────────────────────────────────────────────────
EMAIL_SCAN_AGENT_INSTRUCTION = """
You are the Email Scan Agent.

Task: Scan for new unread emails and extract their metadata and attachment paths.

Steps:
1. Call fetch_emails (from your tools).
2. If fetch_emails returns an error, report it.
3. If fetch_emails returns a list of emails, return that list exactly as a JSON array.

Respond ONLY with valid JSON.
"""

# ─── Agent Definition ─────────────────────────────────────────────────────────────

email_scan_agent = Agent(
    name="email_scan_agent",
    model=GEMINI_MODEL,
    description="Connects to the inbox and fetches unread emails with attachments.",
    instruction=EMAIL_SCAN_AGENT_INSTRUCTION,
    tools=[fetch_emails_tool],
)

# ─── Runner Helper ────────────────────────────────────────────────────────────────

async def run_email_scan_agent() -> list[dict[str, Any]]:
    """
    Execute the Email Scan Agent to discover new documents.

    Returns:
        List of email payload dicts.
    """
    try:
        session_service = InMemorySessionService()
        runner = Runner(
            agent=email_scan_agent,
            app_name="invoice_pipeline",
            session_service=session_service,
        )

        session = await session_service.create_session(
            app_name="invoice_pipeline",
            user_id="system",
        )

        response_text = ""

        # Use run_async for proper async handling
        async for event in runner.run_async(
            user_id="system",
            session_id=session.id,
            new_message=genai_types.Content(
                role="user",
                parts=[genai_types.Part(text="Scan for new unread emails.")],
            ),
        ):
            if event.is_final_response() and event.content:
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        response_text += part.text

        try:
            text = response_text.strip().replace("```json", "").replace("```", "").strip()
            emails = json.loads(text) if text else []
            return emails if isinstance(emails, list) else []
        except json.JSONDecodeError:
            logger.warning(
                "Email scan agent returned non-JSON: %s", response_text[:300]
            )
            return []

    except Exception as exc:
        logger.exception("Email scan agent failed: %s", exc)
        return []
