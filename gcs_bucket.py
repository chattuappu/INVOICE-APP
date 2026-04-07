import os
from google.cloud import storage

client = storage.Client.from_service_account_json("service.json")
bucket = client.bucket("invoice-exception-usecase")

files = [
    "./documents/Invoice_test.pdf"
]

root_prefix = "amal_gopi/"
folder_path = f"{root_prefix}INVOICE/"

for file in files:
    filename = os.path.basename(file)  # extract only file name
    blob = bucket.blob(folder_path + filename)
    blob.upload_from_filename(file)
    print(f"{filename} uploaded!")

print("Done 🚀")