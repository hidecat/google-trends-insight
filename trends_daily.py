# -*- coding: utf-8 -*-
from pytrends.request import TrendReq
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os
import json

# ===== 設定 =====

KEYWORDS = ["楽天", "Amazon", "ふるさと納税", "ブラックフライデー", "NISA"]
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
SHEET_NAME = "Sheet1"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# ===== Google Trends の取得 =====

def get_trends_row():
    pytrends = TrendReq(hl="ja-JP", tz=540)
    pytrends.build_payload(KEYWORDS, geo="JP", timeframe="now 1-d")

    df = pytrends.interest_over_time()
    if df.empty:
        raise RuntimeError("Googleトレンドのデータが取得できませんでした")

    latest = df.iloc[-1]
    dt = df.index[-1]
    date_str = dt.strftime("%Y-%m-%d %H:%M:%S")

    row = [date_str]
    for kw in KEYWORDS:
        row.append(int(latest[kw]))

    return row

# ===== スプレッドシートへ追記 =====

def append_to_sheet(row):
    service_account_info = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not service_account_info:
        raise RuntimeError("環境変数 GOOGLE_SERVICE_ACCOUNT_JSON が設定されていません")

    sa_dict = json.loads(service_account_info)
    credentials = Credentials.from_service_account_info(sa_dict, scopes=SCOPES)

    gc = gspread.authorize(credentials)
    sh = gc.open_by_key(SPREADSHEET_ID)
    worksheet = sh.worksheet(SHEET_NAME)

    worksheet.append_row(row, value_input_option="RAW")

# ===== メイン =====

def main():
    row = get_trends_row()
    print("追加する行:", row)

    append_to_sheet(row)
    print("スプレッドシートに追記しました")

if __name__ == "__main__":
    main()
