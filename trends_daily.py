# -*- coding: utf-8 -*-
from pytrends.request import TrendReq
from pytrends.exceptions import ResponseError  # ★これを追加
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
SHEET_NAME_MAIN = "シート1"       # 既存の集計先（今使っているシート名）
SHEET_NAME_TRENDING = "Trending" # 急上昇ワードを書き込む新しいシート
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

# ===== Google Trends（急上昇ワード） の取得 =====

from pytrends.request import TrendReq
from pytrends.exceptions import ResponseError
from datetime import datetime

def get_trending_rows():
    """
    Googleトレンドのリアルタイム急上昇ワードを取得して、
    [datetime, type, rank, keyword] の行リストを返す
    （まずは realtime のみ。daily は一旦封印）
    """
    rows = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # リアルタイム急上昇ワード（realtime_trending_searches）
    try:
        py_rt = TrendReq(hl="ja-JP", tz=540)
        rt_df = py_rt.realtime_trending_searches(pn="JP")

        # デバッグ用：カラム構成をログに出す
        print("realtime columns:", rt_df.columns)

        if "title" in rt_df.columns:
            rt_keywords = rt_df["title"].tolist()
        else:
            # 念のためフォールバック：最初の列を使う
            rt_keywords = rt_df.iloc[:, 0].tolist()

        for rank, kw in enumerate(rt_keywords, start=1):
            rows.append([now_str, "realtime", rank, kw])

        print(f"realtime trending: {len(rt_keywords)} 件取得")
    except ResponseError as e:
        print(f"[WARN] realtime_trending_searches が失敗しました: {e}")
    except Exception as e:
        print(f"[WARN] realtime_trending_searches で予期せぬエラー: {e}")

    return rows

# ===== スプレッドシート（Trending）へ追記 =====

def get_gspread_client():
    """gspread のクライアントを返す（既存のJSON処理を共通化）"""
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw:
        raise RuntimeError("環境変数 GOOGLE_SERVICE_ACCOUNT_JSON が設定されていません")

    # JSON文字列から { ... } 部分だけ抜き出す（前に入れたガードロジック）
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise RuntimeError("サービスアカウントJSONが正しくありません（{ } が見つからない）")

    json_str = raw[start:end + 1]
    sa_dict = json.loads(json_str)

    credentials = Credentials.from_service_account_info(sa_dict, scopes=SCOPES)
    gc = gspread.authorize(credentials)
    return gc

def append_to_sheet(row):
    """メインシート（SHEET_NAME_MAIN）に1行追記する。最大3回リトライ付き。"""
    import time
    from gspread.exceptions import APIError

    gc = get_gspread_client()          # 既に定義済みの関数を使う
    sh = gc.open_by_key(SPREADSHEET_ID)

    last_error = None
    for attempt in range(3):
        try:
            print(f"Try {attempt+1}/3: open spreadsheet & append row")
            worksheet = sh.worksheet(SHEET_NAME_MAIN)   # ← ここがポイント（SHEET_NAMEじゃなくSHEET_NAME_MAIN）
            worksheet.append_row(row, value_input_option="RAW")
            print("Appended successfully.")
            return
        except APIError as e:
            last_error = e
            print(f"APIError on attempt {attempt+1}: {e}")
            if attempt < 2:
                time.sleep(5)
            else:
                raise

    # 保険（ここに来ることはほぼない）
    if last_error:
        raise last_error


def append_trending_rows(rows):
    """急上昇ワードの行リストを Trending シートにまとめて追記"""

    if not rows:
        print("急上昇ワードが空だったので何も書き込みませんでした。")
        return

    gc = get_gspread_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    worksheet = sh.worksheet(SHEET_NAME_TRENDING)

    # 一括で書き込む（1行ずつ append_row してもOKだが多少遅い）
    # gspread には append_rows はないので、単純に for で回す
    for row in rows:
        worksheet.append_row(row, value_input_option="RAW")

    print(f"急上昇ワード {len(rows)} 行を書き込みました。")

def debug_write_trending():
    """Trendingシートにテスト行を書き込む（動作確認用）"""
    test_row = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "debug", 0, "テスト書き込み"]
    append_trending_rows([test_row])

# ===== メイン =====

def main():
    # 1) 既存のキーワード群のトレンドを1行書き込み
    row = get_trends_row()
    print("追加する行:", row)
    append_to_sheet(row)
    print("メインシートに追記しました")

    # 2) 急上昇ワード（失敗しても全体は止めない）
    try:
        trending_rows = get_trending_rows()
        print(f"急上昇ワード行数: {len(trending_rows)}")
        append_trending_rows(trending_rows)
    except Exception as e:
        print(f"[WARN] 急上昇ワード処理中にエラーが発生しましたが、スキップします: {e}")

if __name__ == "__main__":
    main()
