"""
GCS File Manager - View and Delete Files from Invoice/Sales Tax Folders
"""
import os
from datetime import datetime
from google.cloud import storage
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent / ".env")

# ─── Configuration ──────────────────────────────────────────────────────────
SERVICE_ACCOUNT_PATH = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "service.json")
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "invoice-processing-bucket")
GCS_ROOT_PREFIX = os.environ.get("GCS_ROOT_PREFIX", "amal_gopi").strip("/")
GCS_ROOT_PREFIX = f"{GCS_ROOT_PREFIX}/" if GCS_ROOT_PREFIX else ""
GCS_INVOICE_PREFIX = f"{GCS_ROOT_PREFIX}INVOICE/"
GCS_SALES_TAX_PREFIX = f"{GCS_ROOT_PREFIX}SALES_TAX/"


class GCSFileManager:
    """Manage files in GCS Invoice and Sales Tax folders"""

    def __init__(self):
        """Initialize GCS client"""
        self.client = storage.Client.from_service_account_json(SERVICE_ACCOUNT_PATH)
        self.bucket = self.client.bucket(GCS_BUCKET_NAME)
        self.files_cache = {}

    def list_files(self, folder_type: str) -> list[dict]:
        """
        List all files in a specific folder.
        
        Args:
            folder_type: 'invoice' or 'sales_tax'
            
        Returns:
            List of dicts with file info (name, size, time_created)
        """
        folder_type = folder_type.lower()
        prefix = GCS_INVOICE_PREFIX if folder_type == "invoice" else GCS_SALES_TAX_PREFIX
        
        try:
            blobs = self.bucket.list_blobs(prefix=prefix)
            files = []
            
            for blob in blobs:
                # Skip if it's just the prefix itself
                if blob.name == prefix.rstrip("/"):
                    continue
                    
                files.append({
                    "name": blob.name.replace(prefix, ""),
                    "full_path": blob.name,
                    "size_mb": round(blob.size / (1024 * 1024), 2) if blob.size else 0,
                    "created": blob.time_created.strftime("%Y-%m-%d %H:%M:%S") if blob.time_created else "N/A",
                    "blob": blob
                })
            
            self.files_cache[folder_type] = files
            return files
            
        except Exception as e:
            print(f"❌ Error listing files: {e}")
            return []

    def display_files(self, folder_type: str) -> None:
        """Display files in a formatted table"""
        folder_type = folder_type.lower()
        folder_name = "🧾 INVOICE" if folder_type == "invoice" else "💰 SALES_TAX"
        
        files = self.list_files(folder_type)
        
        if not files:
            print(f"\n{folder_name}: No files found.\n")
            return
        
        print(f"\n{'='*80}")
        print(f"{folder_name}: {len(files)} files found")
        print(f"{'='*80}")
        print(f"{'#':<4} {'File Name':<45} {'Size (MB)':<12} {'Created':<20}")
        print(f"{'-'*80}")
        
        for idx, file_info in enumerate(files, 1):
            print(
                f"{idx:<4} {file_info['name']:<45} {file_info['size_mb']:<12} {file_info['created']:<20}"
            )
        
        print(f"{'='*80}\n")

    def delete_file(self, folder_type: str, file_indices: list[int]) -> None:
        """
        Delete files by their index.
        
        Args:
            folder_type: 'invoice' or 'sales_tax'
            file_indices: List of file numbers to delete (1-based)
        """
        folder_type = folder_type.lower()
        files = self.files_cache.get(folder_type, [])
        
        if not files:
            print("❌ No files in cache. Please list files first.")
            return
        
        deleted_count = 0
        for idx in file_indices:
            if 1 <= idx <= len(files):
                file_info = files[idx - 1]
                try:
                    blob = self.bucket.blob(file_info["full_path"])
                    blob.delete()
                    print(f"✅ Deleted: {file_info['name']}")
                    deleted_count += 1
                except Exception as e:
                    print(f"❌ Error deleting {file_info['name']}: {e}")
            else:
                print(f"⚠️  Invalid index: {idx}")
        
        print(f"\n✓ {deleted_count} file(s) deleted successfully.\n")

    def delete_all(self, folder_type: str, confirm: bool = True) -> None:
        """
        Delete all files in a folder.
        
        Args:
            folder_type: 'invoice' or 'sales_tax'
            confirm: Request confirmation before deletion
        """
        folder_type = folder_type.lower()
        files = self.list_files(folder_type)
        
        if not files:
            print("No files to delete.")
            return
        
        if confirm:
            self.display_files(folder_type)
            response = input(f"⚠️  Delete ALL {len(files)} files? (yes/NO): ").strip().lower()
            if response != "yes":
                print("Deletion cancelled.")
                return
        
        deleted_count = 0
        for file_info in files:
            try:
                blob = self.bucket.blob(file_info["full_path"])
                blob.delete()
                print(f"✅ Deleted: {file_info['name']}")
                deleted_count += 1
            except Exception as e:
                print(f"❌ Error deleting {file_info['name']}: {e}")
        
        print(f"\n✓ {deleted_count} file(s) deleted successfully.\n")


def main():
    """Interactive menu for file management"""
    manager = GCSFileManager()
    
    while True:
        print("\n" + "="*80)
        print("📁 GCS FILE MANAGER - Invoice & Sales Tax")
        print("="*80)
        print("1. List INVOICE files")
        print("2. List SALES_TAX files")
        print("3. Delete specific INVOICE files")
        print("4. Delete specific SALES_TAX files")
        print("5. Delete ALL INVOICE files")
        print("6. Delete ALL SALES_TAX files")
        print("7. Exit")
        print("="*80)
        
        choice = input("Select an option (1-7): ").strip()
        
        if choice == "1":
            manager.display_files("invoice")
        
        elif choice == "2":
            manager.display_files("sales_tax")
        
        elif choice == "3":
            manager.display_files("invoice")
            indices = input("Enter file numbers to delete (comma-separated, e.g., 1,3,5): ").strip()
            if indices:
                try:
                    file_indices = [int(x.strip()) for x in indices.split(",")]
                    manager.delete_file("invoice", file_indices)
                except ValueError:
                    print("❌ Invalid input. Please enter numbers separated by commas.")
        
        elif choice == "4":
            manager.display_files("sales_tax")
            indices = input("Enter file numbers to delete (comma-separated, e.g., 1,3,5): ").strip()
            if indices:
                try:
                    file_indices = [int(x.strip()) for x in indices.split(",")]
                    manager.delete_file("sales_tax", file_indices)
                except ValueError:
                    print("❌ Invalid input. Please enter numbers separated by commas.")
        
        elif choice == "5":
            manager.delete_all("invoice", confirm=True)
        
        elif choice == "6":
            manager.delete_all("sales_tax", confirm=True)
        
        elif choice == "7":
            print("\n👋 Goodbye!\n")
            break
        
        else:
            print("❌ Invalid option. Please try again.")


if __name__ == "__main__":
    main()
