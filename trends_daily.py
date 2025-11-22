from pytrends.request import TrendReq
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os

# ===== 設定ここから =====

# 監視したいキーワード
KEYWORDS = ["楽天", "Amazon", "ふるさと納税", "ブラックフライデー", "NISA", "ChatGPT"]

# GoogleスプレッドシートのID（URLの /d/ と /edit の間の部分）
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")  # GitHub Secretsから渡す

# 書き込み先のシート名
SHEET_NAME = "Sheet1"

# サービスアカウントのスコープ
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# ===== 設定ここまで =====


def get_trends_row():
    """今日のGoogleトレンドスコアを1行分取得して、[日付, k1, k2, ...] の形で返す"""

    pytrends = TrendReq(hl="ja-JP", tz=540)

    # 直近1日のデータを取得（today 1-d だと時間単位になるので now 1-d）
    pytrends.build_payload(KEYWORDS, geo="JP", timeframe="now 1-d")
    df = pytrends.interest_over_time()

    if df.empty:
        raise RuntimeError("Googleトレンドのデータが取得できませんでした")

    # 一番新しい行を使う
    latest = df.iloc[-1]

    # 日付はindexから取る
    dt = df.index[-1]  # pandasのTimestamp
    date_str = dt.strftime("%Y-%m-%d %H:%M:%S")

    row = [date_str]
    for kw in KEYWORDS:
        row.append(int(latest[kw]))

    return row


def append_to_sheet(row):
    """スプレッドシートの末尾に1行追加"""

    # GitHub SecretsからJSON文字列で受け取ったもの
    service_account_info = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not service_account_info:
        raise RuntimeError("環境変数 GOOGLE_SERVICE_ACCOUNT_JSON が設定されていません")

    import json
    sa_dict = json.loads(service_account_info)

    credentials = Credentials.from_service_account_info(sa_dict, scopes=SCOPES)

    gc = gspread.authorize(credentials)
    sh = gc.open_by_key(SPREADSHEET_ID)
    worksheet = sh.worksheet(SHEET_NAME)

    worksheet.append_row(row, value_input_option="RAW")


def main():
    # 1行分のデータを取得
    row = get_trends_row()
    print("追加する行:", row)

    # 追記
    append_to_sheet(row)
    print("スプレッドシートに追記しました")


if __name__ == "__main__":
    main()
