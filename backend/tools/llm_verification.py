"""
LLM Field Verification – Gemini-powered confidence booster.

After Document AI extracts fields, any field whose confidence is below the
HIGH_CONFIDENCE_THRESHOLD is sent to Gemini along with the raw document text.
Gemini then:
  1. Confirms the extracted value is correct (updates confidence), OR
  2. Corrects the value if it can find a better one (updates value + confidence).

If Gemini itself fails or is not confident enough, the original Document AI
result is returned unchanged.
"""
import json
import logging
from typing import Any

import google.genai as genai

from backend.config.gcp_config import (
    GEMINI_MODEL,
    GEMINI_API_KEY,
    HIGH_CONFIDENCE_THRESHOLD,
)

logger = logging.getLogger(__name__)

# ─── Lazy Gemini Client ───────────────────────────────────────────────────────────

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


# ─── Single Field Verificaion ─────────────────────────────────────────────────────

def _verify_single_field(
    field_name: str,
    extracted_value: str,
    raw_text: str,
) -> dict[str, Any]:
    """
    Ask Gemini to verify / correct a single low-confidence field.

    Returns:
        {
            "value":      str   – verified or corrected value,
            "confidence": float – Gemini's confidence in its answer,
            "llm_verified": True,
            "error":      None | str,
        }
    """
    prompt = f"""You are an invoice-data extraction auditor.

A document processing system extracted the following field from a document but
is not very confident about it.

Field name     : {field_name}
Extracted value: {extracted_value!r}

Below is the raw OCR text of the document (may be truncated):
---
{raw_text[:3000]}
---

Your task:
1. Check whether the extracted value is correct.
2. If it is correct, confirm it.
3. If it is wrong or missing, find the correct value from the raw text.
4. If you cannot determine the correct value at all, say so.

Reply ONLY with valid JSON (no markdown fences), exactly in this format:
{{
  "field_name": "{field_name}",
  "verified_value": "<the correct value, or empty string if unknown>",
  "confidence": <float 0.0-1.0 representing your confidence>,
  "reasoning": "<one-sentence explanation>"
}}"""

    try:
        client = _get_client()
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        text = response.text.strip().replace("```json", "").replace("```", "").strip()
        result = json.loads(text)

        verified_value = str(result.get("verified_value", "")).strip()
        llm_confidence = float(result.get("confidence", 0.0))

        return {
            "value": verified_value,
            "confidence": round(llm_confidence, 4),
            "llm_verified": True,
            "error": None,
        }

    except json.JSONDecodeError as exc:
        logger.warning(
            "LLM field verification returned non-JSON for field '%s': %s",
            field_name,
            exc,
        )
        return {"value": extracted_value, "confidence": None, "llm_verified": False, "error": str(exc)}

    except Exception as exc:
        logger.exception("LLM field verification failed for field '%s': %s", field_name, exc)
        return {"value": extracted_value, "confidence": None, "llm_verified": False, "error": str(exc)}


# ─── Public Entry Point ───────────────────────────────────────────────────────────

def verify_low_confidence_fields(
    fields: dict[str, dict],
    raw_text: str,
    threshold: float = HIGH_CONFIDENCE_THRESHOLD,
) -> dict[str, dict]:
    """
    Iterate over all extracted fields and apply LLM verification to any whose
    confidence is below `threshold`.

    Args:
        fields:    Dict of field_name → {value, confidence, manually_edited, ...}
        raw_text:  Raw OCR text from Document AI (used as context for the LLM).
        threshold: Confidence cut-off; fields at or above this are left untouched.

    Returns:
        Updated fields dict with verified / corrected values where applicable.
    """
    updated_fields = dict(fields)

    for field_name, field_data in fields.items():
        original_confidence = field_data.get("confidence", 0.0)

        # Skip fields that already meet the threshold
        if original_confidence >= threshold:
            continue

        logger.info(
            "Field '%s' has low confidence (%.2f) – sending to LLM for verification.",
            field_name,
            original_confidence,
        )

        llm_result = _verify_single_field(
            field_name=field_name,
            extracted_value=field_data.get("value", ""),
            raw_text=raw_text,
        )

        if llm_result.get("error") or not llm_result.get("llm_verified"):
            # LLM failed – keep original Document AI result unchanged
            logger.warning(
                "LLM verification failed for '%s'; keeping original confidence %.2f.",
                field_name,
                original_confidence,
            )
            # Annotate that LLM was attempted but failed
            updated_fields[field_name] = {
                **field_data,
                "llm_verification_attempted": True,
                "llm_verification_failed": True,
            }
            continue

        llm_confidence = llm_result["confidence"]
        llm_value = llm_result["value"]

        # Only accept the LLM's answer if it is more confident than Document AI
        if llm_confidence is not None and llm_confidence > original_confidence:
            old_value = field_data.get("value", "")
            logger.info(
                "LLM improved field '%s': confidence %.2f → %.2f, value %r → %r.",
                field_name,
                original_confidence,
                llm_confidence,
                old_value,
                llm_value,
            )
            print(
                f"\n🔍 [LLM VERIFICATION] Field updated: '{field_name}'\n"
                f"   Value     : {old_value!r}  →  {llm_value!r}\n"
                f"   Confidence: {original_confidence:.2%}  →  {llm_confidence:.2%}\n",
                flush=True,
            )
            updated_fields[field_name] = {
                **field_data,
                "value": llm_value,
                "confidence": llm_confidence,
                "llm_verified": True,
                "llm_verification_attempted": True,
                "llm_verification_failed": False,
            }
        else:
            # LLM is no more confident – keep original but record the attempt
            logger.info(
                "LLM did not improve confidence for '%s' (LLM: %.2f vs DocAI: %.2f); keeping original.",
                field_name,
                llm_confidence if llm_confidence is not None else -1,
                original_confidence,
            )
            updated_fields[field_name] = {
                **field_data,
                "llm_verified": False,
                "llm_verification_attempted": True,
                "llm_verification_failed": False,
            }

    return updated_fields
