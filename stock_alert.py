import yfinance as yf
import pandas as pd
import requests
import os
import time

WEBHOOK_URL = os.environ.get("WEBHOOK")

# PayPay証券で取引可能な代表的・主要な日本株および米国株の拡張リスト
TICKERS = {
    # 日本株（主要・高配当・グロース）
    "トヨタ自動車": "7203.T",
    "三菱UFJフィナンシャル・グループ": "8306.T",
    "日本電信電話 (NTT)": "9432.T",
    "ソフトバンクグループ": "9984.T",
    "ソニーグループ": "6758.T",
    "任天堂": "7974.T",
    "三菱商事": "8058.T",
    "三井住友フィナンシャルグループ": "8316.T",
    "本田技研工業": "7267.T",
    "伊藤忠商事": "8001.T",
    "武田薬品工業": "4502.T",
    "KDDI": "9433.T",
    "オリックス": "8591.T",
    "キーエンス": "6861.T",
    "ファーストリテイリング": "9983.T",
    "東京エレクトロン": "8035.T",
    "リクルートホールディングス": "6098.T",
    "信越化学工業": "4063.T",
    "日立製作所": "6501.T",
    "三菱重工業": "7011.T",
    "富士通": "6702.T",
    "デンソー": "6902.T",
    "コマツ": "6301.T",
    "パナソニック ホールディングス": "6752.T",
    "ENEOSホールディングス": "5020.T",

    # 米国株（GAFAM・主要ハイテク・バリュー・高配当）
    "Apple": "AAPL",
    "Microsoft": "MSFT",
    "NVIDIA": "NVDA",
    "Amazon": "AMZN",
    "Alphabet (Google)": "GOOGL",
    "Meta Platforms": "META",
    "Tesla": "TSLA",
    "Netflix": "NFLX",
    "Intel": "INTC",
    "AMD": "AMD",
    "Qualcomm": "QCOM",
    "Broadcom": "AVGO",
    "Adobe": "ADBE",
    "Salesforce": "CRM",
    "Coca-Cola": "KO",
    "PepsiCo": "PEP",
    "Procter & Gamble": "PG",
    "Johnson & Johnson": "JNJ",
    "Pfizer": "PFE",
    "Merck": "MRK",
    "JPMorgan Chase": "JPM",
    "Bank of America": "BAC",
    "Visa": "V",
    "Mastercard": "MA",
    "Walmart": "WMT",
    "Costco": "COST",
    "McDonald's": "MCD",
    "Disney": "DIS",
    "Nike": "NKE",
    "Exxon Mobil": "XOM",
    "Chevron": "CVX",
    
    # 主要ETF
    "S&P 500 ETF (SPY)": "SPY",
    "NASDAQ 100 ETF (QQQ)": "QQQ",
    "ダウ工業株30種平均ETF (DIA)": "DIA",
    "高配当株ETF (VYM)": "VYM",
    "Vanguard Total Stock Market (VTI)": "VTI"
}

def calculate_rsi(data, period=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def check_signals():
    buy_list = []
    sell_list = []

    for name, ticker in TICKERS.items():
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="3mo")
            if hist.empty or len(hist) < 25:
                # データが足りない場合はスキップして次の銘柄へ
                time.sleep(1.0)
                continue

            hist['SMA5'] = hist['Close'].rolling(window=5).mean()
            hist['SMA25'] = hist['Close'].rolling(window=25).mean()
            hist['RSI'] = calculate_rsi(hist)

            latest = hist.iloc[-1]
            prev = hist.iloc[-2]

            info = stock.info
            per = info.get('trailingPE', 'データなし')
            if isinstance(per, float):
                per = round(per, 1)

            golden_cross = (prev['SMA5'] <= prev['SMA25']) and (latest['SMA5'] > latest['SMA25'])
            dead_cross = (prev['SMA5'] >= prev['SMA25']) and (latest['SMA5'] < latest['SMA25'])

            buy_reasons = []
            if latest['RSI'] <= 30:
                buy_reasons.append(f"RSI {latest['RSI']:.1f} (売られすぎ)")
            if golden_cross:
                buy_reasons.append("ゴールデンクロス発生")
            
            if buy_reasons:
                buy_list.append(f"・**{name}** ({ticker}): {', '.join(buy_reasons)} / PER: {per}")

            sell_reasons = []
            if latest['RSI'] >= 70:
                sell_reasons.append(f"RSI {latest['RSI']:.1f} (買われすぎ)")
            if dead_cross:
                sell_reasons.append("デッドクロス発生")
            
            if sell_reasons:
                sell_list.append(f"・**{name}** ({ticker}): {', '.join(sell_reasons)} / PER: {per}")

        except Exception as e:
            print(f"エラー: {name} - {e}")

        # サーバーに負荷をかけず確実に取得するため、1銘柄ごとに1秒間スパンを開ける
        time.sleep(1.0)

    return buy_list, sell_list

def send_discord(buy_list, sell_list):
    if not WEBHOOK_URL:
        print("Webhook URLが設定されていません。")
        return

    # 多くの銘柄がヒットした場合にDiscordの文字数制限（2000文字）を超えないよう上位20件に制限
    message = "📊 **【定期確認】株式シグナルレポート（全主要銘柄チェック版）**\n\n"
    
    if buy_list:
        message += "🟢 **【買い候補】**\n" + "\n".join(buy_list[:20]) + "\n\n"
    else:
        message += "🟢 **【買い候補】**\n・現在条件を満たす銘柄はありません。\n\n"

    if sell_list:
        message += "🔴 **【売り候補】**\n" + "\n".join(sell_list[:20]) + "\n\n"
    else:
        message += "🔴 **【売り候補】**\n・現在条件を満たす銘柄はありません。\n\n"

    payload = {"content": message}
    requests.post(WEBHOOK_URL, json=payload)

if __name__ == "__main__":
    buy, sell = check_signals()
    send_discord(buy, sell)
