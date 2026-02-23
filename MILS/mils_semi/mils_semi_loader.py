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
import paramiko
import os
from datetime import datetime
from datetime import date

#logging
import logging

logging.basicConfig(
    filename="mils_annual_reports.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

logger = logging.getLogger(__name__)

console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(console)

# test mode flag
TEST_MODE = False        # Set to False for production
TEST_LIMIT = 10          # Small result set to validate structure


# save files to Reports directory to avoid clutter
# Reports directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(BASE_DIR, "Reports") 
    
# Create Reports directory if it doesn't exist
os.makedirs(REPORTS_DIR, exist_ok=True)

# populate csv file with results of a sql query
def csv_writer(query_results, headers, csv_file):

    with open(csv_file, "w", encoding="utf-8", newline="") as tempFile:
        myFile = csv.writer(tempFile, delimiter=",")
        myFile.writerow(headers)
        myFile.writerows(query_results)

    return csv_file

def get_previous_semiannual_period():
    """
    Returns:
        start_date (datetime)
        end_date (datetime)
        label (string formatted as YYYYMM_YYYYMM)
    """

    today = date.today()
    year = today.year

    if today.month <= 6:
        # Running Jan–Jun → report previous Jul–Dec
        start = datetime(year - 1, 7, 1)
        end = datetime(year - 1, 12, 31, 23, 59, 59)
    else:
        # Running Jul–Dec → report previous Jan–Jun
        start = datetime(year, 1, 1)
        end = datetime(year, 6, 30, 23, 59, 59)

    label = f"{start.strftime('%Y%m')}_{end.strftime('%Y%m')}"
    return start, end, label
    
    
# connect to MILS Polaris SQL DB and store results of an sql query
def run_query(query, csv_file):

    logger.info(f"Starting query for {csv_file}")

    config = configparser.ConfigParser()
    config.read(os.path.join(BASE_DIR, "config.ini"))

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

    end_file = csv_writer(rows, headers, csv_file)

    logger.info(f"CSV file written: {csv_file}")

    return end_file


# add a LIMIT to test mode

def apply_test_limit(query):
    """
    Adds TOP clause for SQL Server when TEST_MODE is enabled.
    """
    return query.replace("SELECT", f"SELECT TOP {TEST_LIMIT}", 1)


def main():

    logger.info("MILS Annual Report export job started")

    start_date, end_date, period_label = get_previous_semiannual_period()
    
    logger.info(f"Reporting period start: {start_date}")
    logger.info(f"Reporting period end: {end_date}")
    logger.info(f"File label: {period_label}")

    CircTrxStatistics_query = f"""
    DECLARE @StartDate DATETIME = '{start_date.strftime('%Y-%m-%d %H:%M:%S')}'
    DECLARE @EndDate DATETIME = '{end_date.strftime('%Y-%m-%d %H:%M:%S')}'

    SELECT
        O.OrganizationID [TransactionBranch ID],
        O.Name AS [TransactionBranch],
        TH.TranClientDate AS [TransactionDate],
        TH.TransactionTypeID AS [TransactionTypeID],
        TH.TransactionID AS [TransactionID],
        TD.Numvalue AS [PatronCode],
        PC.Description AS [PatronCodeDesc],
        PO.OrganizationID AS [PatronBranchID],
        PO.Name AS [PatronBranch],
        IO.OrganizationID AS [ItemBranchID],
        IO.Name AS [ItemBranch],
        IR.Numvalue AS [ItemRecord],
        ISC.Numvalue AS [ItemStatCode]

    FROM

    PolarisTransactions.Polaris.TransactionDetails TD with (NOLOCK)

    INNER JOIN 
        PolarisTransactions.Polaris.TransactionHeaders TH WITH (NOLOCK) 
    ON (TD.TransactionID = TH.TransactionID AND TD.TransactionSubTypeID = 7)

    INNER JOIN --- Gets the Transaction branch from TransactionDetails
    Polaris.Organizations O with (NOLOCK)
            ON (TH.OrganizationID = O.OrganizationID)

    INNER JOIN --- Gets the patron's assigned branch from TransactionDetails
    PolarisTransactions.Polaris.TransactionDetails PB WITH (NOLOCK)
            ON (TH.TransactionID = PB.TransactionID AND PB.TransactionSubTypeID = 123)

    INNER JOIN --- Gets the item’s assigned branch from TransactionDetails
        PolarisTransactions.Polaris.TransactionDetails IB WITH (NOLOCK)
            ON (TH.TransactionID = IB.TransactionID AND IB.TransactionSubTypeID = 125)
            
    INNER JOIN --- Gets the item record number from TransactionDetails
        PolarisTransactions.Polaris.TransactionDetails IR WITH (NOLOCK)
            ON (TH.TransactionID = IR.TransactionID AND IR.TransactionSubTypeID = 38)

    INNER JOIN --- Gets the item statistical code from TransactionDetails
        PolarisTransactions.Polaris.TransactionDetails ISC WITH (NOLOCK)
            ON (TH.TransactionID = ISC.TransactionID AND ISC.TransactionSubTypeID = 60)

    INNER JOIN --- Hooks up Organizations to the patron’s assigned branch from TransactionDetails
        Polaris.Polaris.Organizations PO WITH (NOLOCK)
            ON (PO.OrganizationID = PB.numValue)

    INNER JOIN --- Hooks up Organizations to the item’s assigned branch from TransactionDetails
        Polaris.Polaris.Organizations IO WITH (NOLOCK)
            ON (IO.OrganizationID = IB.numValue)

    INNER JOIN ---Gets the TransactionDetails patron code values
        Polaris.PatronCodes PC with (NOLOCK)
            ON (PC.PatronCodeID = TD.NumValue)

    WHERE

        TH.TranClientDate BETWEEN @StartDate AND @EndDate
    AND
        TH.TransactionTypeID = 6001

    ORDER BY

        O.Name, PC.Description
	"""

    ILLRequestStatistics_query = f"""
    DECLARE @StartDate DATETIME = '{start_date.strftime('%Y-%m-%d %H:%M:%S')}'
    DECLARE @EndDate DATETIME = '{end_date.strftime('%Y-%m-%d %H:%M:%S')}'

    SELECT TH.TransactionTypeID, 
        TH.TranClientDate as TransactionDate, 
        TH.WorkstationID, 
        W.ComputerName,
        TD.NumValue as PatronCode,
        PC.Description,
        TD1.NumvAlue as PatronOrganizationID,
        O.Name as PatronLibrary,
        O2.Name as TransactionOrgName,
        Pickup.OrganizationID,
        Pickup.Name as PickupLibrary
            
    FROM PolarisTransactions.Polaris.TransactionHeaders TH WITH (NOLOCK)

    INNER JOIN PolarisTransactions.Polaris.TransactionDetails TD WITH (NOLOCK)
            ON TH.TransactionID = TD.TransactionID AND TD.TransactionSubTypeID = 7
            
    INNER JOIN PolarisTransactions.Polaris.TransactionDetails TD1 WITH (NOLOCK)
            ON TH.TransactionID = TD1.TransactionID AND TD1.TransactionSubTypeID = 13
            
    INNER JOIN PolarisTransactions.Polaris.TransactionDetails TD2 WITH (NOLOCK)
            ON TH.TransactionID = TD2.TransactionID AND TD2.TransactionSubTypeID = 149
            
    INNER JOIN Polaris.Organizations O WITH (NOLOCK)
            ON TD1.numvalue = O.OrganizationID
            
    INNER JOIN Polaris.Organizations Pickup WITH (NOLOCK)
            ON TD2.numvalue = Pickup.OrganizationID
            
    INNER JOIN Polaris.PatronCodes PC WITH (NOLOCK)
            ON TD.numValue = PC.PatronCodeID
            
    INNER JOIN Polaris.Organizations O2 WITH (NOLOCK)
            ON TH.OrganizationID = O2.OrganizationID
            
    INNER JOIN Polaris.Workstations W WITH (NOLOCK)
            ON TH.WorkstationID = W.WorkstationID					
            
    WHERE 
        TH.TransactionTypeID = 6033
    AND
        TH.TranClientDate BETWEEN @StartDate AND @EndDate
	
	"""        

    # Instantiate .csv files with names including today's date
    CircTrxStatistics_file = os.path.join(
    REPORTS_DIR,
    f"CircTrxStatistics_{period_label}.csv"
    )

    ILLRequestStatistics_file = os.path.join(
    REPORTS_DIR,
    f"ILLRequestStatistics_{period_label}.csv"
    )
    
    run_query(CircTrxStatistics_query, CircTrxStatistics_file)
    run_query(ILLRequestStatistics_query, ILLRequestStatistics_file)


    logger.info("MILS Annual Report export job completed")

if __name__ == "__main__":
    main()
