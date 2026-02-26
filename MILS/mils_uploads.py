import os
import sys
import base64
import configparser
import requests
from requests_ntlm import HttpNtlmAuth
from datetime import datetime, timedelta


# Determine script directory dynamically
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load configuration from config.ini
config = configparser.ConfigParser()
config.read(os.path.join(BASE_DIR, "config.ini"))

BASE_URL = config["ssrs"]["base_url"]
USERNAME = config["ssrs"]["username"]
PASSWORD = config["ssrs"]["password"]


# Local directory where monthly Excel reports are stored
REPORTS_DIR = r"C:\Scripts\Polaris\mils_monthly\Reports"


# Mapping of report file prefixes to their corresponding SSRS folder destinations
UPLOAD_MAP = {
    "Item_Count": "/Polaris/Custom/MILS TOP HITS/Item Counts",
    "Patron_Count": "/Polaris/Custom/MILS TOP HITS/Patron Counts",
    "Bib_Count": "/Polaris/Custom/MILS TOP HITS/Bib Counts",
    "ShelfLocation_Count": "/Polaris/Custom/MILS TOP HITS/ITEM -- Shelf Location Statistics Reports"
}


# Runtime control flag
DRY_RUN = "--dry-run" in sys.argv


def get_previous_month_string():
    today = datetime.today()
    first_of_this_month = today.replace(day=1)
    previous_month_last_day = first_of_this_month - timedelta(days=1)
    return previous_month_last_day.strftime("%Y%m")


def find_file(prefix, month_suffix):
    expected_name = f"{prefix}_{month_suffix}.xlsx"
    file_path = os.path.join(REPORTS_DIR, expected_name)

    if os.path.exists(file_path):
        return expected_name
    return None


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
        "Content": encoded_content,
        "ContentType": "application/octet-stream"
    }

    # Use ExcelWorkbooks endpoint
    url = f"{BASE_URL}/api/v2.0/ExcelWorkbooks"
    response = session.post(url, json=payload)

    if response.status_code in (200, 201):
        print(f"Uploaded: {file_name}")

    elif response.status_code == 409:
        print(f"Skipped (already exists): {file_name}")

    else:
        print(f"Upload failed: {file_name}")
        print(response.status_code)
        print(response.text)


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
            print(f"File not found: {prefix}_{month_suffix}.xlsx")


if __name__ == "__main__":
    main()
