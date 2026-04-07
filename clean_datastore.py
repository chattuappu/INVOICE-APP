"""
clean_datastore.py – Development Helper
Deletes ONLY your records from the configured Datastore kind.
Filters by GCS_ROOT_PREFIX to avoid deleting colleagues' data.

Usage:
    python clean_datastore.py
"""

import os
import sys

# Allow running from project root
sys.path.insert(0, os.path.dirname(__file__))

from backend.config.gcp_config import (
    get_datastore_client, 
    DATASTORE_KIND, 
    GCS_ROOT_PREFIX,
    PROJECT_ID
)

def clean():
    client = get_datastore_client()
    
    # Ensure we have a prefix to filter by
    # GCS_ROOT_PREFIX in config already has a trailing slash usually, or is empty
    prefix = GCS_ROOT_PREFIX.strip("/")
    
    if not prefix:
        print("❌ ERROR: GCS_ROOT_PREFIX is empty or not set.")
        print("To protect shared data, this script requires GCS_ROOT_PREFIX to be set in your .env.")
        print("Example: GCS_ROOT_PREFIX=amal_gopi")
        return

    print(f"--- Datastore Cleanup (User-Specific) ---")
    print(f"Project ID:  {PROJECT_ID}")
    print(f"Target Kind: '{DATASTORE_KIND}'")
    print(f"Filter:      blob_name starts with '{prefix}/'")
    print(f"------------------------------------------")

    # Confirmation prompt
    confirm = input(f"Scan for your entities in '{DATASTORE_KIND}'? (y/N): ")
    if confirm.lower() != 'y':
        print("Operation cancelled.")
        return

    print(f"Fetching your entities...")
    
    # Prefix filtering in Datastore:
    # We use a trick where we filter for strings >= prefix and < prefix + high-unicode character
    query = client.query(kind=DATASTORE_KIND)
    query.add_filter("blob_name", ">=", f"{prefix}/")
    query.add_filter("blob_name", "<", f"{prefix}/" + u"\ufffd")
    
    entities = list(query.fetch())
    count = len(entities)
    
    if count == 0:
        print(f"No entities found starting with '{prefix}/'. Nothing to delete.")
        return

    print(f"\nFound {count} entities belonging to you.")
    
    # Show a few examples for safety
    print("Examples of documents found:")
    for doc in entities[:5]:
        print(f"  - {doc.get('blob_name', 'unknown')}")
    if count > 5:
        print(f"  - ... and {count - 5} more.")

    confirm_final = input(f"\nARE YOU SURE you want to delete these {count} entities? (y/N): ")
    if confirm_final.lower() != 'y':
        print("Operation cancelled.")
        return

    print(f"Deleting...")
    keys = [e.key for e in entities]
    batch_size = 500
    for i in range(0, count, batch_size):
        batch_keys = keys[i:i + batch_size]
        client.delete_multi(batch_keys)
        print(f"  Deleted {i + len(batch_keys)} / {count}...")

    print(f"\nSuccessfully removed {count} entities associated with prefix '{prefix}/'.")

if __name__ == "__main__":
    try:
        clean()
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
