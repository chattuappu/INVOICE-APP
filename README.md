# DocFlow — Invoice & Sales Tax Exception Processing Application

A full-stack AI-powered document processing system built with **Google ADK (Agent Development Kit)**, Document AI, Firestore, GCS, and a pure HTML/CSS/JS frontend.

---

## Architecture

```
Email Inbox
    │
    ▼
┌─────────────────────────────────────────────────┐
│  Email Scan Agent  (ADK Agent + Gemini)         │
│  Tools: fetch_emails_tool, classify_email_tool  │
└───────────────────┬─────────────────────────────┘
                    │ discovered documents
                    ▼
┌─────────────────────────────────────────────────┐
│  Classification Agent  (ADK Agent + Gemini)     │
│  Tools: upload_to_gcs_tool,                     │
│         create_document_record_tool             │
└───────────────────┬─────────────────────────────┘
                    │ Firestore stubs created
                    ▼
┌─────────────────────────────────────────────────┐
│  Processing Agent  (ADK Agent + Gemini)         │
│  Tools: download_from_gcs_tool,                 │
│         extract_document_fields_tool,           │
│         update_extracted_data_tool              │
└───────────────────┬─────────────────────────────┘
                    │ Firestore updated
                    ▼
           FastAPI REST API
                    │
                    ▼
        HTML/CSS/JS Frontend
```

---

## Prerequisites

- Python 3.11+
- A Google Cloud Project with the following APIs enabled:
  - Cloud Firestore
  - Cloud Storage
  - Cloud Document AI
  - Vertex AI (Gemini)
- A service account with IAM roles:
  - `roles/datastore.user`
  - `roles/storage.admin`
  - `roles/documentai.apiUser`
  - `roles/aiplatform.user`
- Gmail account (or any IMAP-compatible email) with an App Password

---

## Setup

### 1. Clone & Install

```bash
git clone <repo-url>
cd invoice-app
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Service Account

Place your `service.json` file in the project root.

```bash
export GOOGLE_APPLICATION_CREDENTIALS=service.json
```

### 3. Configure Environment Variables

Copy and edit the environment template:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# GCP
GOOGLE_APPLICATION_CREDENTIALS=service.json
GCP_PROJECT_ID=your-gcp-project-id
GCP_LOCATION=us-central1

# GCS
GCS_BUCKET_NAME=your-gcs-bucket-name

# Document AI
DOCUMENT_AI_PROCESSOR_ID=your-processor-id
DOCUMENT_AI_LOCATION=us

# Email (IMAP)
EMAIL_HOST=imap.gmail.com
EMAIL_PORT=993
EMAIL_USER=your@gmail.com
EMAIL_PASSWORD=your-app-password
EMAIL_FOLDER=INBOX
EMAIL_POLL_INTERVAL=60

# Firestore
# (uses GCP_PROJECT_ID + service account, no extra config needed)
```

### 4. GCS Bucket Setup

```bash
gcloud storage buckets create gs://your-gcs-bucket-name \
  --project=your-gcp-project-id \
  --location=us-central1

# Create folders
gcloud storage objects create gs://your-gcs-bucket-name/INVOICE/.keep --content-type=text/plain
gcloud storage objects create gs://your-gcs-bucket-name/SALES_TAX/.keep --content-type=text/plain
```

### 5. Firestore Setup

```bash
gcloud firestore databases create \
  --project=your-gcp-project-id \
  --location=us-central1
```

### 6. Document AI Processor

1. Go to GCP Console → Document AI
2. Create a new **Invoice Parser** processor
3. Copy the Processor ID to your `.env`

### 7. Run the Backend

```bash
cd invoice-app
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

The backend will:
- Start the FastAPI REST API on `http://localhost:8000`
- Start the pipeline in a background thread (polling email every 60s)
- Serve the frontend at `http://localhost:8000/`

---

## Folder Structure

```
invoice-app/
├── backend/
│   ├── agents/
│   │   ├── email_agent.py          # ADK Email Scan Agent
│   │   ├── classification_agent.py # ADK Classification Agent
│   │   └── processing_agent.py     # ADK Processing Agent
│   ├── tools/
│   │   ├── email_tool.py           # ADK Tool: IMAP email fetch
│   │   ├── gcs_tool.py             # ADK Tool: GCS upload/download/signed-URL
│   │   ├── document_ai_tool.py     # ADK Tool: Document AI extraction
│   │   ├── firestore_tool.py       # ADK Tool: Firestore CRUD
│   │   └── llm_tool.py             # ADK Tool: Gemini classification
│   ├── workflows/
│   │   └── pipeline.py             # ADK Pipeline orchestration
│   ├── config/
│   │   └── gcp_config.py           # GCP credentials & settings
│   └── main.py                     # FastAPI app + REST API
├── frontend/
│   ├── index.html                  # Dashboard + Detail Modal
│   ├── css/style.css               # Dark industrial UI
│   └── js/app.js                   # Frontend logic
├── requirements.txt
└── README.md
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/documents` | List all documents (optional `?type=invoice\|sales_tax`) |
| `GET` | `/api/documents/{id}` | Get single document |
| `GET` | `/api/documents/{id}/signed-url` | Get GCS signed URL for PDF viewer |
| `PATCH` | `/api/documents/{id}/edits` | Save human edits → status: in_progress |
| `POST` | `/api/documents/{id}/submit` | Mark document as complete → ERP |
| `POST` | `/api/pipeline/run` | Manually trigger pipeline cycle |
| `GET` | `/api/health` | Health check |

---

## Document Status Lifecycle

```
Email received
     │
     ▼
  pending   ◄─── Missing or low-confidence fields
     │
     │  User edits fields
     ▼
 in_progress
     │
     │  User clicks "Submit to ERP"
     ▼
  complete   (Sent To ERP)
```

---

## Firestore Data Model

```json
{
  "document_id": "uuid",
  "type": "invoice | sales_tax",
  "file_path": "gs://bucket/INVOICE/file.pdf",
  "blob_name": "INVOICE/file.pdf",
  "filename": "invoice1.pdf",
  "extracted_data": {
    "invoice_id":        { "value": "INV-001", "confidence": 0.97, "manually_edited": false },
    "invoice_date":      { "value": "2025-02-28", "confidence": 0.91, "manually_edited": false },
    "customer_address":  { "value": "...", "confidence": 0.85, "manually_edited": false },
    "vendor_address":    { "value": "...", "confidence": 0.88, "manually_edited": false },
    "net_amount":        { "value": "13251.56", "confidence": 0.95, "manually_edited": false },
    "grand_total":       { "value": "15636.84", "confidence": 0.95, "manually_edited": false }
  },
  "status": "pending | in_progress | complete",
  "created_at": "2025-03-01T10:00:00Z",
  "updated_at": "2025-03-01T10:05:00Z"
}
```

---

## Manual Pipeline Trigger

To trigger processing without waiting for email:

```bash
curl -X POST http://localhost:8000/api/pipeline/run
```

Or click the **↺ Sync** button in the UI.
