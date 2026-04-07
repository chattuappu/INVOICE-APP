import os
from pathlib import Path
from dotenv import load_dotenv
from google.oauth2 import service_account
from google.cloud import firestore, storage

# Load .env file before reading environment variables
load_dotenv(Path(__file__).parent.parent.parent / ".env")

# ─── Credentials ────────────────────────────────────────────────────────────────
SERVICE_ACCOUNT_PATH = os.environ.get(
    "GOOGLE_APPLICATION_CREDENTIALS", "service.json"
)

SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/datastore",
]


def get_credentials():
    return service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_PATH, scopes=SCOPES
    )


# ─── GCP Project Settings ────────────────────────────────────────────────────────
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "your-gcp-project-id")
LOCATION = os.environ.get("GCP_LOCATION", "us-central1")

# ─── GCS Settings ───────────────────────────────────────────────────────────────
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "invoice-processing-bucket")
GCS_INVOICE_PREFIX = "INVOICE/"
GCS_SALES_TAX_PREFIX = "SALES_TAX/"

# ─── Document AI Settings ───────────────────────────────────────────────────────
DOCUMENT_AI_PROCESSOR_ID = os.environ.get("DOCUMENT_AI_PROCESSOR_ID", "your-processor-id")
DOCUMENT_AI_LOCATION = os.environ.get("DOCUMENT_AI_LOCATION", "us")

# ─── Firestore Settings ─────────────────────────────────────────────────────────
FIRESTORE_COLLECTION = os.environ.get("FIRESTORE_COLLECTION", "documents")

# ─── Email Settings ─────────────────────────────────────────────────────────────
EMAIL_HOST = os.environ.get("EMAIL_HOST", "imap.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "993"))
EMAIL_USER = os.environ.get("EMAIL_USER", "your@email.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "your-app-password")
EMAIL_FOLDER = os.environ.get("EMAIL_FOLDER", "INBOX")
EMAIL_POLL_INTERVAL = int(os.environ.get("EMAIL_POLL_INTERVAL", "60"))  # seconds

# ─── Gemini / GenAI Settings ────────────────────────────────────────────────────
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# ─── Confidence Thresholds ──────────────────────────────────────────────────────
HIGH_CONFIDENCE_THRESHOLD = 0.80

# ─── Client Factories ───────────────────────────────────────────────────────────

def get_firestore_client():
    creds = get_credentials()
    return firestore.Client(project=PROJECT_ID, credentials=creds)


def get_storage_client():
    creds = get_credentials()
    return storage.Client(project=PROJECT_ID, credentials=creds)
