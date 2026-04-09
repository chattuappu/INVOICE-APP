"""
Document AI Tool – ADK Tool
Sends a document to Google Cloud Document AI and returns extracted fields
with confidence scores.

After extraction, any field whose confidence falls below HIGH_CONFIDENCE_THRESHOLD
is automatically sent to Gemini for LLM-based verification and correction.
"""
import logging
import mimetypes
from typing import Any

from google.adk.tools import FunctionTool
from google.api_core.client_options import ClientOptions
from google.cloud import documentai_v1 as documentai
from google.oauth2 import service_account

from backend.config.gcp_config import (
    PROJECT_ID,
    DOCUMENT_AI_PROCESSOR_ID,
    DOCUMENT_AI_LOCATION,
    SERVICE_ACCOUNT_PATH,
    HIGH_CONFIDENCE_THRESHOLD,
)
from backend.tools.llm_verification import verify_low_confidence_fields

logger = logging.getLogger(__name__)

# ─── Field Mapping ───────────────────────────────────────────────────────────────
# Maps Document AI entity types → our internal field names
FIELD_MAP = {
    "invoice_id": ["invoice_id", "invoice_number", "invoice #", "bill number"],
    "invoice_date": ["invoice_date", "date", "bill_date", "invoice date"],
    "customer_address": ["ship_to_address", "customer_address", "bill_to_address", "receiver_address"],
    "vendor_address": ["supplier_address", "vendor_address", "remit_to_address", "from_address"],
    "net_amount": ["net_amount", "subtotal", "total_amount", "amount_due_net"],
    "grand_total": ["total_amount", "grand_total", "amount_due", "total_due", "invoice_total"],
}


def _normalize_field(entity_type: str) -> str | None:
    """Return our internal field name for a Document AI entity type."""
    et_lower = entity_type.lower().replace(" ", "_")
    for internal, aliases in FIELD_MAP.items():
        if et_lower in aliases or entity_type.lower() in aliases:
            return internal
    return None


# ─── Core Implementation ─────────────────────────────────────────────────────────

def extract_document_fields(local_path: str) -> dict[str, Any]:
    """
    Send a local PDF/image file to Document AI and extract invoice fields.

    Args:
        local_path: Absolute path to the document file.

    Returns:
        {
            "fields": {
                "invoice_id": {"value": "...", "confidence": 0.95},
                ...
            },
            "raw_text": "...",
            "error": None | str
        }
    """
    try:
        opts = ClientOptions(
            api_endpoint=f"{DOCUMENT_AI_LOCATION}-documentai.googleapis.com"
        )
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_PATH
        )
        client = documentai.DocumentProcessorServiceClient(
            client_options=opts, credentials=creds
        )

        processor_name = client.processor_path(
            PROJECT_ID, DOCUMENT_AI_LOCATION, DOCUMENT_AI_PROCESSOR_ID
        )

        with open(local_path, "rb") as f:
            content = f.read()

        mime_type, _ = mimetypes.guess_type(local_path)
        mime_type = mime_type or "application/pdf"

        raw_document = documentai.RawDocument(content=content, mime_type=mime_type)
        request = documentai.ProcessRequest(
            name=processor_name, raw_document=raw_document
        )

        result = client.process_document(request=request)
        document = result.document

        extracted: dict[str, dict] = {}

        for entity in document.entities:
            internal_name = _normalize_field(entity.type_)
            if internal_name and internal_name not in extracted:
                text_value = (
                    entity.normalized_value.text
                    if entity.normalized_value and entity.normalized_value.text
                    else entity.mention_text
                )
                extracted[internal_name] = {
                    "value": text_value.strip() if text_value else "",
                    "confidence": round(float(entity.confidence), 4),
                    "manually_edited": False,
                }

        # Ensure all expected fields are present even if not found
        for field in FIELD_MAP:
            if field not in extracted:
                extracted[field] = {
                    "value": "",
                    "confidence": 0.0,
                    "manually_edited": False,
                }

        raw_text = document.text[:3000] if document.text else ""

        logger.info(
            "Document AI extraction complete for %s. Fields: %s",
            local_path,
            list(extracted.keys()),
        )

        # ── LLM Verification for low-confidence fields ────────────────────────
        logger.info(
            "Running LLM verification on fields with confidence < %.2f …",
            HIGH_CONFIDENCE_THRESHOLD,
        )
        verified_fields = verify_low_confidence_fields(
            fields=extracted,
            raw_text=raw_text,
            threshold=HIGH_CONFIDENCE_THRESHOLD,
        )

        return {
            "fields": verified_fields,
            "raw_text": raw_text,
            "error": None,
        }

    except Exception as exc:
        logger.exception("Document AI extraction failed: %s", exc)
        return {"fields": {}, "raw_text": "", "error": str(exc)}


# ─── ADK Tool Registration ───────────────────────────────────────────────────────

extract_document_fields_tool = FunctionTool(func=extract_document_fields)
