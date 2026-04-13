"""
Datastore Tool – ADK Tool
All Datastore reads and writes are routed through this module.
(Using Google Cloud Datastore / Firestore in Datastore Mode)
"""
import logging
from datetime import datetime, timezone
from typing import Any

from google.adk.tools import FunctionTool
from google.cloud import datastore

from backend.config.gcp_config import (
    DATASTORE_KIND,
    get_datastore_client,
)

logger = logging.getLogger(__name__)


# ─── Create ───────────────────────────────────────────────────────────────────────

def create_document_record(
    document_id: str,
    document_type: str,
    file_path: str,
    blob_name: str,
    filename: str,
    sender_email: str = "",
) -> dict[str, Any]:
    """
    Create a new Datastore entity record.

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
        client = get_datastore_client()
        now = datetime.now(timezone.utc).isoformat()
        
        key = client.key(DATASTORE_KIND, document_id)
        entity = datastore.Entity(key=key)
        entity.update({
            "document_id": document_id,
            "type": document_type,
            "file_path": file_path,
            "blob_name": blob_name,
            "filename": filename,
            "sender_email": sender_email,
            "extracted_data": {},
            "status": "pending",
            "created_at": now,
            "updated_at": now,
        })
        client.put(entity)
        logger.info("Created Datastore record for %s", document_id)
        return {"success": True, "document_id": document_id, "error": None}

    except Exception as exc:
        logger.exception("Datastore create failed: %s", exc)
        return {"success": False, "document_id": document_id, "error": str(exc)}


# ─── Update Extracted Data ────────────────────────────────────────────────────────

def update_extracted_data(
    document_id: str,
    extracted_data: dict,
    status: str,
) -> dict[str, Any]:
    """
    Update the extracted_data and status for an existing Datastore entity.

    Args:
        document_id:    Datastore entity ID.
        extracted_data: Dict of field → {value, confidence, manually_edited}.
        status:         'pending', 'in_progress', or 'complete'.

    Returns:
        {"success": bool, "error": None | str}
    """
    try:
        client = get_datastore_client()
        now = datetime.now(timezone.utc).isoformat()
        
        key = client.key(DATASTORE_KIND, document_id)
        entity = client.get(key)
        
        if not entity:
            return {"success": False, "error": "Entity not found"}
        
        entity["extracted_data"] = extracted_data
        entity["status"] = status
        entity["updated_at"] = now
        
        client.put(entity)
        logger.info("Updated extracted data for %s → status=%s", document_id, status)

        # Trigger notification if status is complete
        if status == "complete":
            from backend.tools.notification_tool import send_completion_notification
            send_completion_notification(
                recipient_email=entity.get("sender_email", ""),
                document_id=document_id,
                filename=entity.get("filename", "document"),
                extracted_data=extracted_data,
            )

        return {"success": True, "error": None}

    except Exception as exc:
        logger.exception("Datastore update failed: %s", exc)
        return {"success": False, "error": str(exc)}



# ─── Update Status Only ───────────────────────────────────────────────────────────

def _update_status_impl(document_id: str, status: str) -> dict[str, Any]:
    """
    Update only the status field of a Datastore entity.

    Args:
        document_id: Datastore entity ID.
        status:      New status value.

    Returns:
        {"success": bool, "error": None | str}
    """
    try:
        client = get_datastore_client()
        now = datetime.now(timezone.utc).isoformat()
        
        key = client.key(DATASTORE_KIND, document_id)
        entity = client.get(key)
        
        if not entity:
            return {"success": False, "error": "Entity not found"}
        
        entity["status"] = status
        entity["updated_at"] = now
        
        client.put(entity)

        # Trigger notification if status is complete
        if status == "complete":
            from backend.tools.notification_tool import send_completion_notification
            send_completion_notification(
                recipient_email=entity.get("sender_email", ""),
                document_id=document_id,
                filename=entity.get("filename", "document"),
                extracted_data=entity.get("extracted_data", {}),
            )

        return {"success": True, "error": None}

    except Exception as exc:
        logger.exception("Datastore status update failed: %s", exc)
        return {"success": False, "error": str(exc)}


# ─── Get All Documents ────────────────────────────────────────────────────────────

def _get_all_documents_impl(document_type: str | None = None) -> dict[str, Any]:
    """
    Retrieve all entities, optionally filtered by type.

    Args:
        document_type: 'invoice', 'sales_tax', or None for all.

    Returns:
        {"documents": list[dict], "error": None | str}
    """
    try:
        client = get_datastore_client()
        query = client.query(kind=DATASTORE_KIND)
        
        if document_type:
            query.add_filter("type", "=", document_type)

        docs = [dict(entity) for entity in query.fetch()]
        return {"documents": docs, "error": None}

    except Exception as exc:
        logger.exception("Datastore get_all failed: %s", exc)
        return {"documents": [], "error": str(exc)}


# ─── Get Single Document ──────────────────────────────────────────────────────────

def _get_document_impl(document_id: str) -> dict[str, Any]:
    """
    Retrieve a single entity by ID.

    Returns:
        {"document": dict | None, "error": None | str}
    """
    try:
        client = get_datastore_client()
        key = client.key(DATASTORE_KIND, document_id)
        entity = client.get(key)
        
        if entity:
            return {"document": dict(entity), "error": None}
        return {"document": None, "error": "Not found"}

    except Exception as exc:
        logger.exception("Datastore get_document failed: %s", exc)
        return {"document": None, "error": str(exc)}


# ─── Update Manual Edits ─────────────────────────────────────────────────────────

def _save_manual_edits_impl(
    document_id: str, edits: dict
) -> dict[str, Any]:
    """
    Save human-edited field values and set status to 'in_progress'.

    Args:
        document_id: Datastore entity ID.
        edits:       {field_name: new_value, ...}

    Returns:
        {"success": bool, "error": None | str}
    """
    try:
        client = get_datastore_client()
        key = client.key(DATASTORE_KIND, document_id)
        entity = client.get(key)
        
        if not entity:
            return {"success": False, "error": "Entity not found"}

        extracted = entity.get("extracted_data", {})

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
        entity["extracted_data"] = extracted
        entity["status"] = "in_progress"
        entity["updated_at"] = now
        
        client.put(entity)
        return {"success": True, "error": None}

    except Exception as exc:
        logger.exception("Datastore manual edit save failed: %s", exc)
        return {"success": False, "error": str(exc)}


# ─── ADK Tool Registration ───────────────────────────────────────────────────────

create_document_record_tool = FunctionTool(func=create_document_record)
update_extracted_data_tool = FunctionTool(func=update_extracted_data)
update_status_tool = FunctionTool(func=_update_status_impl)
get_all_documents_tool = FunctionTool(func=_get_all_documents_impl)
get_document_tool = FunctionTool(func=_get_document_impl)
save_manual_edits_tool = FunctionTool(func=_save_manual_edits_impl)
