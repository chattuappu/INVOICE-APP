"""
LLM Classification Tool – ADK Tool
Uses Gemini REST API to classify whether an email / document is an Invoice or Sales Tax form.
"""
import json
import logging
from typing import Any

import google.genai as genai
from google.adk.tools import FunctionTool

from backend.config.gcp_config import (
    GEMINI_MODEL,
    GEMINI_API_KEY,
)

logger = logging.getLogger(__name__)

# ─── Lazy init ───────────────────────────────────────────────────────────────────
_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


# ─── Email Classification ─────────────────────────────────────────────────────────

def classify_email(subject: str, body: str, attachment_names: list[str]) -> dict[str, Any]:
    """
    Classify an email as 'invoice', 'sales_tax', or 'ignore'.

    Args:
        subject:          Email subject line.
        body:             Plain-text email body (first 2000 chars).
        attachment_names: List of attachment filenames.

    Returns:
        {
            "document_type": "invoice" | "sales_tax" | "ignore",
            "confidence": float,
            "reasoning": str,
            "error": None | str
        }
    """
    try:
        client = _get_client()
        prompt = f"""
You are a document classification assistant for an accounts-payable system.

Analyze this email and determine whether it contains an INVOICE, a SALES TAX EXEMPTION CERTIFICATE, or should be IGNORED.

Email Subject: {subject}
Email Body (truncated): {body[:1500]}
Attachments: {', '.join(attachment_names) if attachment_names else 'None'}

Rules:
- Reply ONLY with valid JSON, no markdown.
- "document_type" must be exactly one of: "invoice", "sales_tax", "ignore"
- "confidence" must be a float between 0.0 and 1.0
- "reasoning" must be a brief explanation

Example response:
{{"document_type": "invoice", "confidence": 0.97, "reasoning": "Subject mentions invoice and attachment is a PDF bill."}}
"""
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )
        text = response.text.strip()
        # Strip any accidental markdown fences
        text = text.replace("```json", "").replace("```", "").strip()
        result = json.loads(text)
        result["error"] = None
        return result

    except json.JSONDecodeError as exc:
        logger.warning("LLM returned non-JSON for email classification: %s", exc)
        return {
            "document_type": "ignore",
            "confidence": 0.0,
            "reasoning": "LLM returned unparseable response",
            "error": str(exc),
        }
    except Exception as exc:
        logger.exception("LLM classification failed: %s", exc)
        return {
            "document_type": "ignore",
            "confidence": 0.0,
            "reasoning": "",
            "error": str(exc),
        }


# ─── ADK Tool Wrapper ────────────────────────────────────────────────────────────

def _classify_email_impl(subject: str, body: str, attachment_names: list[str]) -> dict[str, Any]:
    """ADK tool wrapper that calls the direct classification function."""
    return classify_email(subject, body, attachment_names)


# ─── Document Type Verification ──────────────────────────────────────────────────

def _verify_document_type_impl(raw_text: str) -> dict[str, Any]:
    """
    Given raw OCR text from Document AI, verify / refine the document type.

    Args:
        raw_text: First ~2000 characters of OCR text from the document.

    Returns:
        {
            "document_type": "invoice" | "sales_tax",
            "confidence": float,
            "error": None | str
        }
    """
    try:
        model = _get_model()
        prompt = f"""
Classify the following document text as either "invoice" or "sales_tax".
Reply ONLY with valid JSON: {{"document_type": "invoice"|"sales_tax", "confidence": float}}

Document text (truncated):
{raw_text[:2000]}
"""
        response = model.generate_content(prompt)
        text = response.text.strip().replace("```json", "").replace("```", "").strip()
        result = json.loads(text)
        result["error"] = None
        return result

    except Exception as exc:
        logger.exception("Document type verification failed: %s", exc)
        return {"document_type": "invoice", "confidence": 0.5, "error": str(exc)}


# ─── ADK Tool Registration ───────────────────────────────────────────────────────

classify_email_tool = FunctionTool(func=classify_email)
verify_document_type_tool = FunctionTool(func=_verify_document_type_impl)
