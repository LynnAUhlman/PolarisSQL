#!/usr/bin/env python3
# Run in sic

"""
Modified from script by Jeremy Goldstein.
Updated queries and removed unnecessary elements for this process
Lynn Uhlman - Maine InfoNet
"""

import pyodbc
import csv
import configparser
import os
from datetime import date, timedelta
import logging


# ----------------------------
# Logging
# ----------------------------

logging.basicConfig(
    filename="mils_reports.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

logger = logging.getLogger(__name__)

console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(console)


# ----------------------------
# Test Mode
# ----------------------------

TEST_MODE = False
TEST_LIMIT = 10


# ----------------------------
# Reports Directory
# ----------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(BASE_DIR, "Reports")

os.makedirs(REPORTS_DIR, exist_ok=True)


# ----------------------------
# CSV Writer
# ----------------------------

def csv_writer(query_results, headers, csv_file):
    with open(csv_file, "w", encoding="utf-8", newline="") as tempFile:
        writer = csv.writer(tempFile, delimiter=",")
        writer.writerow(headers)
        writer.writerows(query_results)
    return csv_file


# ----------------------------
# Run Query
# ----------------------------

def run_query(query, csv_file):
    logger.info(f"Starting query for {csv_file}")

    config = configparser.ConfigParser()
    config.read("config.ini")

    try:
        conn = pyodbc.connect(config["sql"]["connection_string"])
        logger.info("Database connection established")
    except Exception:
        logger.exception("Database connection failed")
        return

    cursor = conn.cursor()

    safe_query = apply_test_limit(query) if TEST_MODE else query

    try:
        cursor.execute(safe_query)
        headers = [column[0] for column in cursor.description]
        rows = cursor.fetchall()
        logger.info(f"Query returned {len(rows)} rows")
    except Exception:
        logger.exception("Query execution failed")
        conn.close()
        return

    conn.close()

    csv_writer(rows, headers, csv_file)
    logger.info(f"CSV file written: {csv_file}")

    return csv_file


# ----------------------------
# Apply Test Limit
# ----------------------------

def apply_test_limit(query):
    return f"SELECT TOP {TEST_LIMIT} * FROM ({query}) AS test_query"


# ----------------------------
# Main
# ----------------------------

def main():
    logger.info("MILS export job started")

    # ----------------------------------
    # Calculate Previous Month (YYYYMM)
    # ----------------------------------

    today = date.today()
    first_of_this_month = today.replace(day=1)
    last_day_previous_month = first_of_this_month - timedelta(days=1)
    previous_year_month = last_day_previous_month.strftime("%Y%m")

    # ----------------------------------
    # Queries
    # ----------------------------------

    bib_count_query = """
    SELECT 
        cir.AssignedBranchID,
        o.Name,
        COUNT(DISTINCT b.BibliographicRecordID) AS BibCount
    FROM BibliographicRecords b
    INNER JOIN CircItemRecords cir
        ON b.BibliographicRecordID = cir.AssociatedBibRecordID
    INNER JOIN Organizations o
        ON cir.AssignedBranchID = o.OrganizationID
    WHERE b.RecordStatusID = 1
    GROUP BY cir.AssignedBranchID, o.Name
    ORDER BY cir.AssignedBranchID;
    """

    item_count_query = """
    SELECT
        o.Name AS AssignedBranch,
        sc.Description AS StatisticalCodeName,
        COUNT(DISTINCT cir.ItemRecordID) AS ItemCount
    FROM CircItemRecords cir WITH (NOLOCK)
    INNER JOIN Organizations o WITH (NOLOCK)
        ON cir.AssignedBranchID = o.OrganizationID
    INNER JOIN StatisticalCodes sc WITH (NOLOCK)
        ON cir.StatisticalCodeID = sc.StatisticalCodeID
    WHERE cir.RecordStatusID = 1
        AND cir.ItemStatusID NOT IN (7,10,11)
        AND cir.ILLFlag = 0
    GROUP BY o.Name, sc.Description
    ORDER BY o.Name, sc.Description;
    """

    patron_count_query = """
    SELECT
        o.Name,
        pc.Description,
        COUNT(DISTINCT p.PatronID) AS PatronCount
    FROM Patrons p WITH (NOLOCK)
    INNER JOIN PatronRegistration pr WITH (NOLOCK)
        ON p.PatronID = pr.PatronID
    INNER JOIN Organizations o WITH (NOLOCK)
        ON p.OrganizationID = o.OrganizationID
    INNER JOIN PatronCodes pc WITH (NOLOCK)
        ON p.PatronCodeID = pc.PatronCodeID
    WHERE pr.ExpirationDate IS NOT NULL
        AND pr.ExpirationDate >= DATEADD(YEAR, -3, CAST(GETDATE() AS DATE))
        AND p.RecordStatusID = 1
    GROUP BY o.Name, pc.Description
    ORDER BY o.Name, pc.Description;
    """

    shelflocation_count_query = """
    SELECT
        o.Name,
        pc.Description,
        COUNT(DISTINCT p.PatronID) AS PatronCount
    FROM Patrons p WITH (NOLOCK)
    INNER JOIN PatronRegistration pr WITH (NOLOCK)
        ON p.PatronID = pr.PatronID
    INNER JOIN Organizations o WITH (NOLOCK)
        ON p.OrganizationID = o.OrganizationID
    INNER JOIN PatronCodes pc WITH (NOLOCK)
        ON p.PatronCodeID = pc.PatronCodeID
    WHERE pr.ExpirationDate IS NOT NULL
        AND pr.ExpirationDate >= DATEADD(YEAR, -3, CAST(GETDATE() AS DATE))
        AND p.RecordStatusID = 1
    GROUP BY o.Name, pc.Description
    ORDER BY o.Name, pc.Description;
    """

    # ----------------------------------
    # File Names (Previous Month)
    # ----------------------------------

    bib_count_file = os.path.join(
        REPORTS_DIR, f"Bib_Count_{previous_year_month}.csv"
    )

    item_count_file = os.path.join(
        REPORTS_DIR, f"Item_Count_{previous_year_month}.csv"
    )

    patron_count_file = os.path.join(
        REPORTS_DIR, f"Patron_Count_{previous_year_month}.csv"
    )

    shelflocation_count_file = os.path.join(
        REPORTS_DIR, f"ShelfLocation_Count_{previous_year_month}.csv"
    )

    # ----------------------------------
    # Execute Queries
    # ----------------------------------

    run_query(bib_count_query, bib_count_file)
    run_query(item_count_query, item_count_file)
    run_query(patron_count_query, patron_count_file)
    run_query(shelflocation_count_query, shelflocation_count_file)

    logger.info("MILS export job completed")


if __name__ == "__main__":
    main()