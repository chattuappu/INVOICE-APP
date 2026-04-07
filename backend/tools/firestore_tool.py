"""
Firestore Tool – ADK Tool
All Firestore reads and writes are routed through this module.
"""
import logging
from datetime import datetime, timezone
from typing import Any

from google.adk.tools import FunctionTool
from google.cloud import firestore

from backend.config.gcp_config import (
    FIRESTORE_COLLECTION,
    get_firestore_client,
)

logger = logging.getLogger(__name__)


# ─── Create ───────────────────────────────────────────────────────────────────────

def create_document_record(
    document_id: str,
    document_type: str,
    file_path: str,
    blob_name: str,
    filename: str,
) -> dict[str, Any]:
    """
    Create a new Firestore document record.

    Args:
        document_id:    Unique ID for the document.
        document_type:  'invoice' or 'sales_tax'.
        file_path:      GCS path (gs://...).
        blob_name:      Blob name inside the bucket.
        filename:       Original filename.

    Returns:
        {"success": bool, "document_id": str, "error": None | str}
    """
    try:
        db = get_firestore_client()
        now = datetime.now(timezone.utc).isoformat()
        data = {
            "document_id": document_id,
            "type": document_type,
            "file_path": file_path,
            "blob_name": blob_name,
            "filename": filename,
            "extracted_data": {},
            "status": "pending",
            "created_at": now,
            "updated_at": now,
        }
        db.collection(FIRESTORE_COLLECTION).document(document_id).set(data)
        logger.info("Created Firestore record for %s", document_id)
        return {"success": True, "document_id": document_id, "error": None}

    except Exception as exc:
        logger.exception("Firestore create failed: %s", exc)
        return {"success": False, "document_id": document_id, "error": str(exc)}


# ─── Update Extracted Data ────────────────────────────────────────────────────────

def update_extracted_data(
    document_id: str,
    extracted_data: dict,
    status: str,
) -> dict[str, Any]:
    """
    Update the extracted_data and status for an existing Firestore document.

    Args:
        document_id:    Firestore document ID.
        extracted_data: Dict of field → {value, confidence, manually_edited}.
        status:         'pending', 'in_progress', or 'complete'.

    Returns:
        {"success": bool, "error": None | str}
    """
    try:
        db = get_firestore_client()
        now = datetime.now(timezone.utc).isoformat()
        db.collection(FIRESTORE_COLLECTION).document(document_id).update(
            {
                "extracted_data": extracted_data,
                "status": status,
                "updated_at": now,
            }
        )
        logger.info("Updated extracted data for %s → status=%s", document_id, status)
        return {"success": True, "error": None}

    except Exception as exc:
        logger.exception("Firestore update failed: %s", exc)
        return {"success": False, "error": str(exc)}


# ─── Update Status Only ───────────────────────────────────────────────────────────

def _update_status_impl(document_id: str, status: str) -> dict[str, Any]:
    """
    Update only the status field of a Firestore document.

    Args:
        document_id: Firestore document ID.
        status:      New status value.

    Returns:
        {"success": bool, "error": None | str}
    """
    try:
        db = get_firestore_client()
        now = datetime.now(timezone.utc).isoformat()
        db.collection(FIRESTORE_COLLECTION).document(document_id).update(
            {"status": status, "updated_at": now}
        )
        return {"success": True, "error": None}

    except Exception as exc:
        logger.exception("Firestore status update failed: %s", exc)
        return {"success": False, "error": str(exc)}


# ─── Get All Documents ────────────────────────────────────────────────────────────

def _get_all_documents_impl(document_type: str | None = None) -> dict[str, Any]:
    """
    Retrieve all documents, optionally filtered by type.

    Args:
        document_type: 'invoice', 'sales_tax', or None for all.

    Returns:
        {"documents": list[dict], "error": None | str}
    """
    try:
        db = get_firestore_client()
        query = db.collection(FIRESTORE_COLLECTION)
        if document_type:
            query = query.where("type", "==", document_type)

        docs = [d.to_dict() for d in query.stream()]
        return {"documents": docs, "error": None}

    except Exception as exc:
        logger.exception("Firestore get_all failed: %s", exc)
        return {"documents": [], "error": str(exc)}


# ─── Get Single Document ──────────────────────────────────────────────────────────

def _get_document_impl(document_id: str) -> dict[str, Any]:
    """
    Retrieve a single document by ID.

    Returns:
        {"document": dict | None, "error": None | str}
    """
    try:
        db = get_firestore_client()
        doc = db.collection(FIRESTORE_COLLECTION).document(document_id).get()
        if doc.exists:
            return {"document": doc.to_dict(), "error": None}
        return {"document": None, "error": "Not found"}

    except Exception as exc:
        logger.exception("Firestore get_document failed: %s", exc)
        return {"document": None, "error": str(exc)}


# ─── Update Manual Edits ─────────────────────────────────────────────────────────

def _save_manual_edits_impl(
    document_id: str, edits: dict
) -> dict[str, Any]:
    """
    Save human-edited field values and set status to 'in_progress'.

    Args:
        document_id: Firestore document ID.
        edits:       {field_name: new_value, ...}

    Returns:
        {"success": bool, "error": None | str}
    """
    try:
        db = get_firestore_client()
        doc_ref = db.collection(FIRESTORE_COLLECTION).document(document_id)
        doc = doc_ref.get()
        if not doc.exists:
            return {"success": False, "error": "Document not found"}

        data = doc.to_dict()
        extracted = data.get("extracted_data", {})

        for field, new_val in edits.items():
            if field in extracted:
                extracted[field]["value"] = new_val
                extracted[field]["manually_edited"] = True
            else:
                extracted[field] = {
                    "value": new_val,
                    "confidence": 1.0,
                    "manually_edited": True,
                }

        now = datetime.now(timezone.utc).isoformat()
        doc_ref.update(
            {
                "extracted_data": extracted,
                "status": "in_progress",
                "updated_at": now,
            }
        )
        return {"success": True, "error": None}

    except Exception as exc:
        logger.exception("Firestore manual edit save failed: %s", exc)
        return {"success": False, "error": str(exc)}


# ─── ADK Tool Registration ───────────────────────────────────────────────────────

create_document_record_tool = FunctionTool(func=create_document_record)
update_extracted_data_tool = FunctionTool(func=update_extracted_data)
update_status_tool = FunctionTool(func=_update_status_impl)
get_all_documents_tool = FunctionTool(func=_get_all_documents_impl)
get_document_tool = FunctionTool(func=_get_document_impl)
save_manual_edits_tool = FunctionTool(func=_save_manual_edits_impl)
