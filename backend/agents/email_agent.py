"""
Email Scan Agent – ADK Agent
Continuously monitors the inbox, classifies emails, and emits
structured events for the Document Classification Agent.
"""
import logging
from typing import Any

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from backend.tools.email_tool import fetch_emails_tool
from backend.tools.llm_tool import classify_email_tool

logger = logging.getLogger(__name__)

EMAIL_AGENT_INSTRUCTION = """
You are the Email Scan Agent for an invoice-processing pipeline.

Your task:
1. First, call the fetch_emails tool to get unread emails from the inbox.
2. For the emails returned, analyze each one for attachments.
3. For emails with attachments, call the classify_email tool with: subject, body, and attachment filenames.
4. Return a JSON array with documents classified as 'invoice' or 'sales_tax'.

Output format:
[
  {"document_type": "invoice", "files": [{"filename": "...", "local_path": "..."}]},
  {"document_type": "sales_tax", "files": [{"filename": "...", "local_path": "..."}]}
]

If no qualifying emails found, return: []
Always respond with ONLY valid JSON. No explanations.
"""

# ─── Agent Definition ─────────────────────────────────────────────────────────────

from backend.config.gcp_config import GEMINI_MODEL

email_scan_agent = Agent(
    name="email_scan_agent",
    model=GEMINI_MODEL,
    description="Monitors email inbox, classifies emails as invoice/sales_tax/ignore, and extracts attachment paths.",
    instruction=EMAIL_AGENT_INSTRUCTION,
    tools=[fetch_emails_tool, classify_email_tool],
)


# ─── Runner Helper ────────────────────────────────────────────────────────────────

async def run_email_scan_agent() -> list[dict[str, Any]]:
    """
    Execute the Email Scan Agent and return the list of discovered documents.
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

        from google.genai import types as genai_types

        response_text = ""
        async for event in runner.run_async(
            user_id="system",
            session_id=session.id,
            new_message=genai_types.Content(
                role="user",
                parts=[genai_types.Part(text="Scan the inbox and return discovered documents as JSON.")],
            ),
        ):
            if event.is_final_response() and event.content:
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        response_text += part.text

        import json

        try:
            text = response_text.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(text) if text else []
        except json.JSONDecodeError:
            logger.warning("Email agent returned non-JSON: %s", response_text[:300])
            return []
    
    except Exception as exc:
        logger.exception("Email scan agent execution failed: %s", exc)
        return []
