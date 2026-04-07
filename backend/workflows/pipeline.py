"""
Pipeline Orchestration – ADK Workflow
Chains Email Scan → Classification → Processing agents with
retry logic, logging, and idempotency guards.
"""
import asyncio
import logging
import os
import time
import uuid
from typing import Any

from backend.agents.email_agent import run_email_scan_agent
from backend.agents.classification_agent import run_classification_agent
from backend.agents.processing_agent import run_processing_agent
from backend.config.gcp_config import (
    GCS_BUCKET_NAME,
    GCS_INVOICE_PREFIX,
    GCS_SALES_TAX_PREFIX,
    get_storage_client,
)
from backend.tools.firestore_tool import create_document_record, get_all_documents_tool

logger = logging.getLogger(__name__)

# ─── Retry Helper ─────────────────────────────────────────────────────────────────

def _with_retry(fn, *args, retries: int = 3, delay: float = 2.0, **kwargs) -> Any:
    """Run a callable with simple exponential-backoff retries."""
    import asyncio
    
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            # Check if the function is async
            if asyncio.iscoroutinefunction(fn):
                # Use asyncio.run() for async functions
                return asyncio.run(fn(*args, **kwargs))
            else:
                return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "Attempt %d/%d failed for %s: %s", attempt, retries, fn.__name__, exc
            )
            if attempt < retries:
                time.sleep(delay * attempt)
    raise RuntimeError(
        f"All {retries} attempts failed for {fn.__name__}"
    ) from last_exc


def _list_pdf_blobs(prefix: str) -> list[str]:
    client = get_storage_client()
    bucket = client.bucket(GCS_BUCKET_NAME)
    blobs = bucket.list_blobs(prefix=prefix)
    return [blob.name for blob in blobs if blob.name.lower().endswith('.pdf')]


def _existing_blob_names() -> set[str]:
    docs_result = get_all_documents_tool.func(document_type=None)
    if docs_result.get('error'):
        logger.warning('Unable to load existing document blob names: %s', docs_result.get('error'))
        return set()
    return {doc.get('blob_name') for doc in docs_result['documents'] if doc.get('blob_name')}


def _create_records_for_blobs(blob_names: list[str]) -> list[dict[str, Any]]:
    created: list[dict[str, Any]] = []
    existing = _existing_blob_names()

    for blob_name in blob_names:
        if blob_name in existing:
            continue

        document_type = (
            'invoice' if blob_name.startswith(GCS_INVOICE_PREFIX) else 'sales_tax'
        )
        filename = os.path.basename(blob_name)
        document_id = str(uuid.uuid4())
        file_path = f'gs://{GCS_BUCKET_NAME}/{blob_name}'

        result = create_document_record(
            document_id=document_id,
            document_type=document_type,
            file_path=file_path,
            blob_name=blob_name,
            filename=filename,
        )

        if result.get('success'):
            created.append({
                'document_id': document_id,
                'blob_name': blob_name,
            })
        else:
            logger.warning(
                'Failed to create document record for bucket blob %s: %s',
                blob_name,
                result.get('error'),
            )

    return created


# ─── Pipeline ─────────────────────────────────────────────────────────────────────

class InvoicePipeline:
    """
    Orchestrates the full document-processing pipeline:
      Email Scan → Classification → Processing
    """

    def run_bucket_scan_once(self) -> dict[str, Any]:
        """
        Scan the configured GCS bucket prefixes for PDFs that have not yet
        been recorded in Datastore, create records, and process them.
        """
        logger.info("═══ GCS bucket scan started ═══")
        result: dict[str, Any] = {
            "new_documents_found": 0,
            "documents_processed": 0,
            "summaries": [],
        }

        try:
            invoice_blobs = _list_pdf_blobs(GCS_INVOICE_PREFIX)
            sales_blobs = _list_pdf_blobs(GCS_SALES_TAX_PREFIX)
            bucket_blobs = invoice_blobs + sales_blobs

            new_records = _create_records_for_blobs(bucket_blobs)
            result["new_documents_found"] = len(new_records)
            logger.info("Found %d new bucket document(s).", len(new_records))

            if new_records:
                summaries = _with_retry(run_processing_agent, new_records)
                result["documents_processed"] = len(summaries)
                result["summaries"] = summaries
                logger.info("Processed %d new bucket document(s).", len(summaries))
            else:
                logger.info("No new bucket documents to import.")

        except Exception as exc:
            logger.exception("GCS bucket scan error: %s", exc)

        return result

    def run_once(self) -> dict[str, Any]:
        """
        Execute one full pipeline cycle.

        Returns:
            {
                "emails_discovered": int,
                "documents_classified": int,
                "documents_processed": int,
                "summaries": list[dict]
            }
        """
        logger.info("═══ Pipeline cycle started ═══")
        result: dict[str, Any] = {
            "emails_discovered": 0,
            "documents_classified": 0,
            "documents_processed": 0,
            "summaries": [],
        }

        # ── Step 1: Email Scan ──────────────────────────────────────────────────
        logger.info("Step 1 – Email Scan Agent")
        discovered = _with_retry(run_email_scan_agent)
        result["emails_discovered"] = len(discovered)
        logger.info("Discovered %d document(s) from email.", len(discovered))

        if not discovered:
            logger.info("No new documents found. Pipeline cycle complete.")
            return result

        # ── Step 2: Document Classification ────────────────────────────────────
        logger.info("Step 2 – Classification Agent")
        classified = _with_retry(run_classification_agent, discovered)
        result["documents_classified"] = len(classified)
        logger.info("Classified %d document(s).", len(classified))

        if not classified:
            logger.warning("Classification produced no records. Pipeline stopping.")
            return result

        # ── Step 3: Document Processing ─────────────────────────────────────────
        logger.info("Step 3 – Processing Agent")
        summaries = _with_retry(run_processing_agent, classified)
        result["documents_processed"] = len(summaries)
        result["summaries"] = summaries
        logger.info("Processed %d document(s).", len(summaries))

        logger.info("═══ Pipeline cycle complete ═══ %s", result)
        return result

    def run_continuous(self, poll_interval_seconds: int = 60) -> None:
        """
        Run the pipeline in a continuous loop (use in a background thread).

        Args:
            poll_interval_seconds: How often to check for new emails.
        """
        logger.info(
            "Starting continuous pipeline (poll interval: %ds)", poll_interval_seconds
        )
        while True:
            try:
                self.run_once()
            except Exception as exc:
                logger.exception("Pipeline cycle error: %s", exc)
            logger.info("Sleeping %ds before next cycle…", poll_interval_seconds)
            time.sleep(poll_interval_seconds)


# ─── Singleton ────────────────────────────────────────────────────────────────────
pipeline = InvoicePipeline()
