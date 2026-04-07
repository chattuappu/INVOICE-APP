"""
Processing Agent – ADK Agent
Downloads documents from GCS, runs Document AI extraction,
determines status, and updates Firestore.
"""
import json
import logging
import os
import tempfile
from typing import Any

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from vertexai.generative_models import Content, Part

from backend.config.gcp_config import GEMINI_MODEL
from backend.tools.gcs_tool import download_from_gcs_tool
from backend.tools.document_ai_tool import extract_document_fields_tool
from backend.tools.firestore_tool import update_extracted_data_tool

from backend.config.gcp_config import HIGH_CONFIDENCE_THRESHOLD

logger = logging.getLogger(__name__)

# ─── System Instruction ───────────────────────────────────────────────────────────
PROCESSING_AGENT_INSTRUCTION = f"""
You are the Processing Agent.

Task: Download, extract, and process a document.

Input: A JSON object with document_id and blob_name.

Steps:
1. Call download_from_gcs with: blob_name
2. Call extract_document_fields with: local_path (from download)
3. Call update_extracted_data with: document_id, extracted_fields, status="complete"
4. Return: {{"document_id": "<id>", "status": "complete", "fields_count": <count>}}

Respond ONLY with the JSON result.
"""

# ─── Agent Definition ─────────────────────────────────────────────────────────────

processing_agent = Agent(
    name="processing_agent",
    model=GEMINI_MODEL,
    description="Extracts structured data from documents via Document AI and updates Datastore.",
    instruction=PROCESSING_AGENT_INSTRUCTION,
    tools=[download_from_gcs_tool, extract_document_fields_tool, update_extracted_data_tool],
)


# ─── Runner Helper ────────────────────────────────────────────────────────────────

async def run_processing_agent(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Execute the Processing Agent for each classified record.

    Args:
        records: Output from the Classification Agent.

    Returns:
        List of processing summaries.
    """
    if not records:
        return []

    summaries: list[dict] = []

    for record in records:
        try:
            # Create a fresh session and runner for each record
            session_service = InMemorySessionService()
            runner = Runner(
                agent=processing_agent,
                app_name="invoice_pipeline",
                session_service=session_service,
            )

            session = await session_service.create_session(
                app_name="invoice_pipeline",
                user_id="system",
            )

            payload = json.dumps(record)
            response_text = ""

            # Use run_async for proper async handling
            async for event in runner.run_async(
                user_id="system",
                session_id=session.id,
                new_message=Content(
                    role="user",
                    parts=[Part.from_text(f"Process this document: {payload}")],
                ),
            ):
                if event.is_final_response() and event.content:
                    for part in event.content.parts:
                        if part.text:
                            response_text += part.text

            try:
                text = response_text.strip().replace("```json", "").replace("```", "").strip()
                summary = json.loads(text) if text else {}
                if summary:
                    summaries.append(summary)
            except json.JSONDecodeError:
                logger.warning(
                    "Processing agent returned non-JSON for %s: %s",
                    record.get("document_id"),
                    response_text[:300],
                )
        
        except Exception as exc:
            logger.exception("Processing agent failed for record: %s", exc)

    return summaries
