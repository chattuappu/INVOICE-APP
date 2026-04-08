"""
Document Classification Agent – ADK Agent
Receives discovered document events from the Email Scan Agent,
uploads files to GCS, and creates Firestore records.
"""
import json
import logging
import uuid
from typing import Any

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from backend.config.gcp_config import GEMINI_MODEL
from backend.tools.gcs_tool import upload_to_gcs_tool
from backend.tools.firestore_tool import create_document_record_tool

logger = logging.getLogger(__name__)

# ─── System Instruction ───────────────────────────────────────────────────────────
CLASSIFICATION_AGENT_INSTRUCTION = """
You are the Document Classification Agent.

Task: Evaluate email payloads to determine if they contain invoices or sales tax documents, then upload relevant attachments to GCS and create a Firestore record.

Input: A JSON object representing an email, containing 'subject', 'body', and an array of 'attachments' (each with 'filename' and 'local_path').

Steps:
1. Analyze the email subject and body to classify the email as exactly one of: "invoice", "sales_tax", or "ignore".
2. If the classification is "ignore" or there are no attachments, respond ONLY with an empty JSON array: []
3. If the classification is "invoice" or "sales_tax", iterate over each file in the 'attachments' list.
4. For each attachment, call upload_to_gcs with its local_path, the determined document_type ("invoice" or "sales_tax"), and the filename.
5. After upload completes, call create_document_record with a newly generated document_id (UUID string), the document_type, the returned blob_name from upload, and the filename.
6. Return a JSON array containing objects for each processed attachment:
   [{"document_id": "<uuid>", "blob_name": "<blob>", "filename": "<name>", "document_type": "<type>"}]

Respond ONLY with valid JSON.
"""

# ─── Agent Definition ─────────────────────────────────────────────────────────────

classification_agent = Agent(
    name="classification_agent",
    model=GEMINI_MODEL,
    description="Evaluates emails, uploads relevant attachments to GCS, and creates Firestore records.",
    instruction=CLASSIFICATION_AGENT_INSTRUCTION,
    tools=[upload_to_gcs_tool, create_document_record_tool],
)


# ─── Runner Helper ────────────────────────────────────────────────────────────────

async def run_classification_agent(
    discovered_docs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Execute the Classification Agent for each discovered document.

    Args:
        discovered_docs: Output from the Email Scan Agent.

    Returns:
        List of created Firestore record stubs.
    """
    if not discovered_docs:
        return []

    created_records: list[dict] = []

    for doc in discovered_docs:
        try:
            # Create a fresh session and runner for each document
            session_service = InMemorySessionService()
            runner = Runner(
                agent=classification_agent,
                app_name="invoice_pipeline",
                session_service=session_service,
            )

            session = await session_service.create_session(
                app_name="invoice_pipeline",
                user_id="system",
            )

            payload = json.dumps(doc)
            response_text = ""

            # Use run_async for proper async handling
            async for event in runner.run_async(
                user_id="system",
                session_id=session.id,
                new_message=genai_types.Content(
                    role="user",
                    parts=[genai_types.Part(text=f"Process this document batch: {payload}")],
                ),
            ):
                if event.is_final_response() and event.content:
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            response_text += part.text

            try:
                text = response_text.strip().replace("```json", "").replace("```", "").strip()
                records = json.loads(text) if text else []
                if isinstance(records, list):
                    created_records.extend(records)
            except json.JSONDecodeError:
                logger.warning(
                    "Classification agent returned non-JSON: %s", response_text[:300]
                )
        
        except Exception as exc:
            logger.exception("Classification agent failed for document: %s", exc)

    return created_records
