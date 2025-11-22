# -*- coding: utf-8 -*-
from pytrends.request import TrendReq
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os
import json

# ===== 設定 =====

KEYWORD_GROUPS = [
    # --- OZmall ブランドワード ---
    ["OZmall", "オズモール", "オズマガジン", "OZmagazine", "オズモール レストラン"],
    ["オズモール ホテル", "オズモール 美容院", "オズモール エステ", "OZmall 限定", "オズモール 予約"],

    # --- OZmall 主要カテゴリ ---
    ["誕生日 ディナー", "記念日 レストラン", "アフタヌーンティー", "個室 レストラン", "女子会"],
    ["温泉 宿", "露天風呂付き客室", "おこもりステイ", "サウナ付き 宿", "ホテル アフタヌーンティー"],
    ["髪質改善", "インナーカラー", "白髪ぼかし", "痩身エステ", "眉毛サロン"],

    # --- 特集・季節ワード ---
    ["いちご ビュッフェ", "クリスマス ディナー", "イルミネーション", "推し活 ホテル", "女子旅"],

    # --- 競合モニタリング ---
    ["食べログ", "一休", "ホットペッパー グルメ", "Retty", "ヒトサラ"],
    ["楽天トラベル", "じゃらん", "Booking.com", "Yahoo!トラベル", "るるぶ"],
    ["ホットペッパービューティー", "minimo", "Rakuten Beauty", "美容院 予約", "エステ 予約"]
]

SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
SHEET_NAME = "シート1"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# ===== Google Trends の取得 =====

def get_trends_row():
    """Google Trendsの複数キーワードグループをまとめて取得する"""
    pytrends = TrendReq(hl="ja-JP", tz=540)

    all_values = []
    current_timestamp = None

    for group in KEYWORD_GROUPS:
        pytrends.build_payload(group, geo="JP", timeframe="today 1-m")
        df = pytrends.interest_over_time()
        if df.empty:
            raise RuntimeError("Googleトレンドのデータが取得できませんでした")

        # 日付（index）はどのグループも同じなので、最初の1回だけ保存
        if current_timestamp is None:
            dt = df.index[-1]
            current_timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")

        latest = df.iloc[-1]
        for kw in group:
            all_values.append(int(latest[kw]))

    # 先頭に日付を付ける
    row = [current_timestamp] + all_values

    return row


# ===== スプレッドシートへ追記 =====

def append_to_sheet(row):
    """スプレッドシートの末尾に1行追加（最大3回リトライ）"""

    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw:
        raise RuntimeError("環境変数 GOOGLE_SERVICE_ACCOUNT_JSON が設定されていません")

    import json
    import time
    from gspread.exceptions import APIError

    # raw から { ... } 部分だけを抜き出す
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise RuntimeError("サービスアカウントJSONが正しくありません（{ } が見つからない）")

    json_str = raw[start:end + 1]
    sa_dict = json.loads(json_str)

    credentials = Credentials.from_service_account_info(sa_dict, scopes=SCOPES)
    gc = gspread.authorize(credentials)

    # 最大3回リトライ
    last_error = None
    for attempt in range(3):
        try:
            print(f"Try {attempt+1}/3: open spreadsheet & append row")
            sh = gc.open_by_key(SPREADSHEET_ID)
            worksheet = sh.worksheet(SHEET_NAME)
            worksheet.append_row(row, value_input_option="RAW")
            print("Appended successfully.")
            return
        except APIError as e:
            last_error = e
            print(f"APIError on attempt {attempt+1}: {e}")
            # 500系は一時的なことが多いので、少し待って再試行
            if attempt < 2:
                time.sleep(5)
            else:
                # 3回失敗したら諦める
                raise

    # ここに来ることはあまりないはず
    raise last_error

# ===== メイン =====

def main():
    row = get_trends_row()
    print("追加する行:", row)

    append_to_sheet(row)
    print("スプレッドシートに追記しました")

if __name__ == "__main__":
    main()
