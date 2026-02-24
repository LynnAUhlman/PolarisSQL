# Import required libraries for file handling, encoding, HTTP requests, authentication, and date logic

import os
import sys
import base64
import requests
from requests_ntlm import HttpNtlmAuth
from datetime import datetime, timedelta


# Server connection details and authentication credentials

BASE_URL = "https://mils.polarislibrary.com/reports"
USERNAME = "DOMAIN\\username"
PASSWORD = "your_password"


# Local directory where the monthly CSV reports are stored

REPORTS_DIR = r"C:\Scripts\Polaris\mils_monthly\Reports"


# Mapping of report file prefixes to their corresponding SSRS folder destinations

UPLOAD_MAP = {
    "Item_Count": "/Polaris/Custom/MILS TOP HITS/Item Counts",
    "Patron_Count": "/Polaris/Custom/MILS TOP HITS/Patron Counts",
    "Bib_Count": "/Polaris/Custom/MILS TOP HITS/Bib Counts",
    "ShelfLocation_Count": "/Polaris/Custom/MILS TOP HITS/ITEM -- Shelf Location Statistics Reports"
}


# Runtime control flag for testing without performing actual uploads

DRY_RUN = "--dry-run" in sys.argv


# Determine the previous month in YYYYMM format (handles year rollover correctly)

def get_previous_month_string():
    today = datetime.today()
    first_of_this_month = today.replace(day=1)
    previous_month_last_day = first_of_this_month - timedelta(days=1)
    return previous_month_last_day.strftime("%Y%m")


# Locate the expected monthly report file based on prefix and previous month

def find_file(prefix, month_suffix):
    expected_name = f"{prefix}_{month_suffix}.csv"
    file_path = os.path.join(REPORTS_DIR, expected_name)

    if os.path.exists(file_path):
        return expected_name
    else:
        return None


# Upload a file to the SSRS Reports server as a Resource item

def upload_file(session, file_name, folder_path):

    print(f"\nProcessing: {file_name}")
    print(f"Destination: {folder_path}")

    if DRY_RUN:
        print("DRY RUN: Upload skipped.")
        return

    file_path = os.path.join(REPORTS_DIR, file_name)

    with open(file_path, "rb") as f:
        encoded_content = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "Name": file_name,
        "Path": f"{folder_path}/{file_name}",
        "Type": "Resource",
        "Content": encoded_content,
        "ContentType": "text/csv"
    }

    url = f"{BASE_URL}/api/v2.0/CatalogItems"
    response = session.post(url, json=payload)

    if response.status_code in (200, 201):
        print(f"Uploaded: {file_name}")
    elif response.status_code == 409:
        print(f"File exists. Attempting overwrite: {file_name}")
        overwrite_file(session, file_name, folder_path, encoded_content)
    else:
        print(f"Upload failed: {file_name}")
        print(response.status_code)
        print(response.text)


# Overwrite an existing Resource file if it already exists on the server

def overwrite_file(session, file_name, folder_path, encoded_content):

    item_path = f"{folder_path}/{file_name}"
    encoded_path = requests.utils.quote(item_path, safe="")

    url = f"{BASE_URL}/api/v2.0/CatalogItems(Path='{encoded_path}')"

    payload = {
        "Content": encoded_content,
        "ContentType": "text/csv"
    }

    response = session.patch(url, json=payload)

    if response.status_code == 200:
        print(f"Overwritten: {file_name}")
    else:
        print(f"Overwrite failed: {file_name}")
        print(response.status_code)
        print(response.text)


# Main workflow: determine month, establish session, locate files, and upload

def main():

    print("Starting Monthly Upload Process")

    month_suffix = get_previous_month_string()
    print(f"Target Month: {month_suffix}")

    session = requests.Session()
    session.auth = HttpNtlmAuth(USERNAME, PASSWORD)
    session.headers.update({"Content-Type": "application/json"})

    for prefix, folder_path in UPLOAD_MAP.items():

        file_name = find_file(prefix, month_suffix)

        if file_name:
            upload_file(session, file_name, folder_path)
        else:
            print(f"File not found: {prefix}_{month_suffix}.csv")


# Execute script when run directly

if __name__ == "__main__":
    main()