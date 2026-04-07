"""
GCS Upload / Download / Signed-URL Tool – ADK Tool
All Cloud Storage interactions are routed through this module.
"""
import logging
import os
from datetime import timedelta
from typing import Any

from google.adk.tools import FunctionTool

from backend.config.gcp_config import (
    GCS_BUCKET_NAME,
    GCS_INVOICE_PREFIX,
    GCS_SALES_TAX_PREFIX,
    get_storage_client,
    get_credentials,
)

logger = logging.getLogger(__name__)


# ─── Upload ──────────────────────────────────────────────────────────────────────

def upload_to_gcs(
    local_path: str, document_type: str, filename: str
) -> dict[str, Any]:
    """
    Upload a local file to the appropriate GCS prefix based on document_type.

    Args:
        local_path:     Absolute path to the local file.
        document_type:  'invoice' or 'sales_tax'.
        filename:       Destination filename inside the GCS prefix.

    Returns:
        {
            "gcs_path": "gs://bucket/PREFIX/filename",
            "blob_name": "PREFIX/filename",
            "error": None | str
        }
    """
    try:
        client = get_storage_client()
        bucket = client.bucket(GCS_BUCKET_NAME)

        prefix = (
            GCS_INVOICE_PREFIX
            if document_type.lower() == "invoice"
            else GCS_SALES_TAX_PREFIX
        )
        blob_name = f"{prefix}{filename}"
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(local_path)

        gcs_path = f"gs://{GCS_BUCKET_NAME}/{blob_name}"
        logger.info("Uploaded %s → %s", local_path, gcs_path)
        return {"gcs_path": gcs_path, "blob_name": blob_name, "error": None}

    except Exception as exc:
        logger.exception("GCS upload failed: %s", exc)
        return {"gcs_path": None, "blob_name": None, "error": str(exc)}


# ─── Signed URL ──────────────────────────────────────────────────────────────────

def _generate_signed_url_impl(blob_name: str, expiration_minutes: int = 60) -> dict[str, Any]:
    """
    Generate a signed URL for a GCS blob so the frontend can display PDFs.

    Args:
        blob_name:           Full blob path inside the bucket (e.g. 'INVOICE/file.pdf').
        expiration_minutes:  How long (minutes) the URL stays valid.

    Returns:
        {"signed_url": str, "error": None | str}
    """
    try:
        client = get_storage_client()
        bucket = client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(blob_name)

        credentials = get_credentials()
        url = blob.generate_signed_url(
            expiration=timedelta(minutes=expiration_minutes),
            method="GET",
            credentials=credentials,
            version="v4",
        )
        return {"signed_url": url, "error": None}

    except Exception as exc:
        logger.exception("Signed URL generation failed: %s", exc)
        return {"signed_url": None, "error": str(exc)}


# ─── Download ────────────────────────────────────────────────────────────────────

def download_from_gcs(blob_name: str, local_path: str) -> dict[str, Any]:
    """
    Download a GCS blob to a local file path (used by the Processing Agent).

    Args:
        blob_name:  Full blob path inside the bucket.
        local_path: Where to save the file locally.

    Returns:
        {"local_path": str, "error": None | str}
    """
    try:
        client = get_storage_client()
        bucket = client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(blob_name)
        blob.download_to_filename(local_path)
        logger.info("Downloaded %s → %s", blob_name, local_path)
        return {"local_path": local_path, "error": None}

    except Exception as exc:
        logger.exception("GCS download failed: %s", exc)
        return {"local_path": None, "error": str(exc)}


# ─── ADK Tool Registration ───────────────────────────────────────────────────────

upload_to_gcs_tool = FunctionTool(func=upload_to_gcs)
generate_signed_url_tool = FunctionTool(func=_generate_signed_url_impl)
download_from_gcs_tool = FunctionTool(func=download_from_gcs)
