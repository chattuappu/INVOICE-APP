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
from vertexai.generative_models import Content, Part

from backend.config.gcp_config import GEMINI_MODEL
from backend.tools.gcs_tool import upload_to_gcs_tool
from backend.tools.firestore_tool import create_document_record_tool

logger = logging.getLogger(__name__)

# ─── System Instruction ───────────────────────────────────────────────────────────
CLASSIFICATION_AGENT_INSTRUCTION = """
You are the Document Classification Agent.

Task: Upload a document to GCS and create a Firestore record.

Input: A JSON object with document_type, filename, and local_path.

Steps:
1. Call upload_to_gcs with: local_path, document_type, filename
2. When upload completes, call create_document_record with: document_id (generate UUID), document_type, blob_name (from upload), filename
3. Return: {"document_id": "<uuid>", "blob_name": "<blob>", "filename": "<name>", "document_type": "<type>"}

Respond ONLY with the JSON result.
"""

# ─── Agent Definition ─────────────────────────────────────────────────────────────

classification_agent = Agent(
    name="classification_agent",
    model=GEMINI_MODEL,
    description="Uploads documents to GCS and creates Firestore records.",
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
                new_message=Content(
                    role="user",
                    parts=[Part.from_text(f"Process this document batch: {payload}")],
                ),
            ):
                if event.is_final_response() and event.content:
                    for part in event.content.parts:
                        if part.text:
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
