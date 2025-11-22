# coding: utf-8
from pytrends.request import TrendReq
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os
import json

# Keywords to track (English-safe labels)
KEYWORDS = ["楽天", "Amazon", "ふるさと納税", "ブラックフライデー", "NISA", "ChatGPT"]

# Spreadsheet settings
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
SHEET_NAME = "Sheet1"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def get_trends_row():
    """Get latest Google Trends values and return one row."""
    pytrends = TrendReq(hl="ja-JP", tz=540)
    pytrends.build_payload(KEYWORDS, geo="JP", timeframe="now 1-d")

    df = pytrends.interest_over_time()
    if df.empty:
        raise RuntimeError("No Google Trends data fetched.")

    latest = df.iloc[-1]
    dt = df.index[-1]
    date_str = dt.strftime("%Y-%m-%d %H:%M:%S")

    row = [date_str]
    for kw in KEYWORDS:
        row.append(int(latest[kw]))

    return row

def append_to_sheet(row):
    """Append one row to Google Spreadsheet."""
    service_account_info = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not service_account_info:
        raise RuntimeError("Env GOOGLE_SERVICE_ACCOUNT_JSON is not set.")

    sa_dict = json.loads(service_account_info)
    credentials = Credentials.from_service_account_info(sa_dict, scopes=SCOPES)

    gc = gspread.authorize(credentials)
    sh = gc.open_by_key(SPREADSHEET_ID)
    worksheet = sh.worksheet(SHEET_NAME)

    worksheet.append_row(row, value_input_option="RAW")

def main():
    row = get_trends_row()
    print("Row to append:", row)
    append_to_sheet(row)
    print("Appended to Google Spreadsheet.")

if __name__ == "__main__":
    main()
