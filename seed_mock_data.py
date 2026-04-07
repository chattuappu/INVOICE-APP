"""
seed_mock_data.py – Development / Demo helper
Populates Datastore with realistic mock invoice records so you can
test the frontend without running the full email pipeline.

Usage:
    python seed_mock_data.py
"""

import os
import sys
import uuid
from datetime import datetime, timezone

# Allow running from project root
sys.path.insert(0, os.path.dirname(__file__))

from google.cloud import datastore
from backend.config.gcp_config import get_datastore_client, DATASTORE_KIND

MOCK_INVOICES = [
    {
        "document_id": str(uuid.uuid4()),
        "type": "invoice",
        "file_path": "gs://demo-bucket/INVOICE/invoice1.pdf",
        "blob_name": "INVOICE/invoice1.pdf",
        "filename": "invoice1.pdf",
        "status": "pending",
        "extracted_data": {
            "invoice_id":       {"value": "526015",      "confidence": 0.92, "manually_edited": False},
            "invoice_date":     {"value": "06-18-2024",  "confidence": 0.88, "manually_edited": False},
            "customer_address": {"value": "Segovia Cleaning Serv., 228 Sycamore Rd. Apt. #3, San Ysidro CA 92173", "confidence": 0.61, "manually_edited": False},
            "vendor_address":   {"value": "STAR TECHNOLOGIES CORP., 3 Overlook Point, Lincolnshire, IL 60069", "confidence": 0.83, "manually_edited": False},
            "net_amount":       {"value": "",            "confidence": 0.0,  "manually_edited": False},
            "grand_total":      {"value": "2250.00",     "confidence": 0.91, "manually_edited": False},
        },
        "exception_reason": "net_amount not detected",
    },
    {
        "document_id": str(uuid.uuid4()),
        "type": "invoice",
        "file_path": "gs://demo-bucket/INVOICE/invoice2.pdf",
        "blob_name": "INVOICE/invoice2.pdf",
        "filename": "invoice2.pdf",
        "status": "pending",
        "extracted_data": {
            "invoice_id":       {"value": "24000060A",   "confidence": 0.95, "manually_edited": False},
            "invoice_date":     {"value": "03-Mar-25",   "confidence": 0.90, "manually_edited": False},
            "customer_address": {"value": "'Bagmane Solarium City' Argon Block, South Tower, SY. No. 78/1 & 78/2, Ground floor, KR Puram Hobli, Bangalore east Taluk, Dodda Nekkundi, Bengaluru, Karnataka, 560037", "confidence": 0.78, "manually_edited": False},
            "vendor_address":   {"value": "2nd floor, Tower 'A', Millennium Plaza, Sector 27, Gurgaon-122001", "confidence": 0.82, "manually_edited": False},
            "net_amount":       {"value": "4,720.00",    "confidence": 0.94, "manually_edited": False},
            "grand_total":      {"value": "4,720.00",    "confidence": 0.94, "manually_edited": False},
        },
        "exception_reason": "customer_address confidence low",
    },
    {
        "document_id": str(uuid.uuid4()),
        "type": "invoice",
        "file_path": "gs://demo-bucket/INVOICE/invoice3.pdf",
        "blob_name": "INVOICE/invoice3.pdf",
        "filename": "invoice3.pdf",
        "status": "complete",
        "extracted_data": {
            "invoice_id":       {"value": "2025229R00004181", "confidence": 0.98, "manually_edited": False},
            "invoice_date":     {"value": "28/02/2025",       "confidence": 0.97, "manually_edited": False},
            "customer_address": {"value": "SYMBOL TECHNOLOGIES INDIA PVT LTD Billing Address: SY NO 78-1 & 78-2, GROUND FLOOR, KR PURAM HOBLI, BANGALORE EAST TALUK, DODDA NEKKUNDI, BENGALURU - 560037, INDIA.", "confidence": 0.96, "manually_edited": False},
            "vendor_address":   {"value": "Blue Dart Express Ltd., Connection Point, Old Airport Exit Road, Bengaluru 560017, Karnataka, India", "confidence": 0.97, "manually_edited": False},
            "net_amount":       {"value": "13,251.56",        "confidence": 0.99, "manually_edited": False},
            "grand_total":      {"value": "15,636.84",        "confidence": 0.99, "manually_edited": False},
        },
        "exception_reason": "NA",
    },
    {
        "document_id": str(uuid.uuid4()),
        "type": "invoice",
        "file_path": "gs://demo-bucket/INVOICE/invoice4.pdf",
        "blob_name": "INVOICE/invoice4.pdf",
        "filename": "invoice4.pdf",
        "status": "in_progress",
        "extracted_data": {
            "invoice_id":       {"value": "INV-2025-0042",  "confidence": 0.85, "manually_edited": False},
            "invoice_date":     {"value": "15-Jan-2025",    "confidence": 0.80, "manually_edited": False},
            "customer_address": {"value": "Tech Solutions Pvt. Ltd., 14th Floor, Cyber Hub, Gurugram 122002", "confidence": 0.72, "manually_edited": True},
            "vendor_address":   {"value": "Infra Corp., Plot 5, Phase II, Noida 201305", "confidence": 0.88, "manually_edited": False},
            "net_amount":       {"value": "87,500.00",      "confidence": 0.91, "manually_edited": False},
            "grand_total":      {"value": "1,03,250.00",    "confidence": 0.90, "manually_edited": False},
        },
        "exception_reason": "NA",
    },
    {
        "document_id": str(uuid.uuid4()),
        "type": "sales_tax",
        "file_path": "gs://demo-bucket/SALES_TAX/exemption1.pdf",
        "blob_name": "SALES_TAX/exemption1.pdf",
        "filename": "exemption1.pdf",
        "status": "complete",
        "extracted_data": {
            "invoice_id":       {"value": "ST-EX-2024-001", "confidence": 0.93, "manually_edited": False},
            "invoice_date":     {"value": "01-Jan-2024",    "confidence": 0.91, "manually_edited": False},
            "customer_address": {"value": "Exempt Corp., 500 Commerce Blvd, Albany, NY 12206", "confidence": 0.88, "manually_edited": False},
            "vendor_address":   {"value": "Supplies Inc., 200 Trade Center, Trenton, NJ 08601", "confidence": 0.86, "manually_edited": False},
            "net_amount":       {"value": "22,000.00",      "confidence": 0.95, "manually_edited": False},
            "grand_total":      {"value": "22,000.00",      "confidence": 0.95, "manually_edited": False},
        },
        "exception_reason": "NA",
    },
    {
        "document_id": str(uuid.uuid4()),
        "type": "sales_tax",
        "file_path": "gs://demo-bucket/SALES_TAX/exemption2.pdf",
        "blob_name": "SALES_TAX/exemption2.pdf",
        "filename": "exemption2.pdf",
        "status": "pending",
        "extracted_data": {
            "invoice_id":       {"value": "",              "confidence": 0.0,  "manually_edited": False},
            "invoice_date":     {"value": "10-Feb-2025",   "confidence": 0.82, "manually_edited": False},
            "customer_address": {"value": "GreenBuild LLC, 77 Eco Way, Portland, OR 97201", "confidence": 0.76, "manually_edited": False},
            "vendor_address":   {"value": "",              "confidence": 0.0,  "manually_edited": False},
            "net_amount":       {"value": "5,400.00",      "confidence": 0.89, "manually_edited": False},
            "grand_total":      {"value": "5,400.00",      "confidence": 0.89, "manually_edited": False},
        },
        "exception_reason": "invoice_id and vendor_address missing",
    },
]


def seed():
    print("Connecting to Datastore…")
    client = get_datastore_client()
    now = datetime.now(timezone.utc).isoformat()

    for doc in MOCK_INVOICES:
        doc["created_at"] = now
        doc["updated_at"] = now
        
        key = client.key(DATASTORE_KIND, doc["document_id"])
        entity = datastore.Entity(key=key)
        entity.update(doc)
        client.put(entity)
        print(f"  ✅  Seeded {doc['filename']} ({doc['type']}, {doc['status']})")

    print(f"\nSeeded {len(MOCK_INVOICES)} documents into '{DATASTORE_KIND}' kind.")


if __name__ == "__main__":
    seed()
