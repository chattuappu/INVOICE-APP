"""
Pipeline Orchestration – ADK Workflow
Chains Email Scan → Classification → Processing agents with
retry logic, logging, and idempotency guards.
"""
import asyncio
import logging
import time
from typing import Any

from backend.agents.email_agent import run_email_scan_agent
from backend.agents.classification_agent import run_classification_agent
from backend.agents.processing_agent import run_processing_agent

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


# ─── Pipeline ─────────────────────────────────────────────────────────────────────

class InvoicePipeline:
    """
    Orchestrates the full document-processing pipeline:
      Email Scan → Classification → Processing
    """

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
