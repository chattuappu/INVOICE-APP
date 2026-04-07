"""
Backend Entry Point – FastAPI REST API
Exposes endpoints consumed by the HTML/JS frontend and
starts the pipeline in a background thread.
"""
import logging
import os
import threading
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Load environment variables from .env file
load_dotenv()

from backend.config.gcp_config import EMAIL_POLL_INTERVAL
from backend.tools.firestore_tool import (
    get_all_documents_tool,
    get_document_tool,
    save_manual_edits_tool,
    update_status_tool,
)
from backend.tools.gcs_tool import generate_signed_url_tool
from backend.workflows.pipeline import pipeline

# ─── Logging ──────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)

# ─── App ──────────────────────────────────────────────────────────────────────────
app = FastAPI(title="Invoice & Sales Tax Processing API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Models ───────────────────────────────────────────────────────────────────────

class ManualEditRequest(BaseModel):
    edits: dict  # {field_name: new_value}


# ─── Routes ───────────────────────────────────────────────────────────────────────

@app.get("/api/documents")
def get_documents(type: str | None = None):
    """Return all documents, optionally filtered by type (invoice | sales_tax)."""
    result = get_all_documents_tool.func(document_type=type)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result["documents"]


@app.get("/api/documents/{document_id}")
def get_document(document_id: str):
    """Return a single document by ID."""
    result = get_document_tool.func(document_id=document_id)
    if result.get("error") or not result.get("document"):
        raise HTTPException(status_code=404, detail="Document not found")
    return result["document"]


@app.get("/api/documents/{document_id}/signed-url")
def get_signed_url(document_id: str):
    """Generate a signed GCS URL for the PDF viewer."""
    doc_result = get_document_tool.func(document_id=document_id)
    if not doc_result.get("document"):
        raise HTTPException(status_code=404, detail="Document not found")

    blob_name = doc_result["document"].get("blob_name", "")
    url_result = generate_signed_url_tool.func(blob_name=blob_name)

    if url_result.get("error"):
        raise HTTPException(status_code=500, detail=url_result["error"])
    return {"signed_url": url_result["signed_url"]}


@app.patch("/api/documents/{document_id}/edits")
def save_edits(document_id: str, body: ManualEditRequest):
    """Save human-edited field values and set status to in_progress."""
    result = save_manual_edits_tool.func(document_id=document_id, edits=body.edits)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return {"success": True}


@app.post("/api/documents/{document_id}/submit")
def submit_document(document_id: str):
    """Mark an in_progress document as complete (sent to ERP)."""
    result = update_status_tool.func(document_id=document_id, status="complete")
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return {"success": True}


@app.post("/api/pipeline/run")
def trigger_pipeline(background_tasks: BackgroundTasks):
    """Manually trigger a single pipeline cycle."""
    background_tasks.add_task(pipeline.run_once)
    return {"message": "Pipeline cycle triggered in background"}


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    """Serve the main frontend page."""
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"), media_type="text/html")


# ─── Background Pipeline Thread ───────────────────────────────────────────────────

def _start_background_pipeline():
    t = threading.Thread(
        target=pipeline.run_continuous,
        kwargs={"poll_interval_seconds": EMAIL_POLL_INTERVAL},
        daemon=True,
        name="pipeline-thread",
    )
    t.start()
    logger.info("Background pipeline thread started (interval=%ds)", EMAIL_POLL_INTERVAL)


@app.on_event("startup")
def startup_event():
    _start_background_pipeline()


# ─── Static Files (Frontend) ──────────────────────────────────────────────────────
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
FRONTEND_DIR = os.path.abspath(FRONTEND_DIR)
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


# ─── Dev entrypoint ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
