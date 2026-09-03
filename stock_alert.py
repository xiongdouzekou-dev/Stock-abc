import yfinance as yf
import pandas as pd
import requests
import os

# GitHubのシークレットからWebhook URLを読み込む
# ※あなたが保存した「WEBHOOK」という名前を指定しています
WEBHOOK_URL = os.environ.get("WEBHOOK")

# 監視したい銘柄のリスト（日本株は末尾に .T をつけます）
# ※ここを増やせば監視銘柄を追加できます
TICKERS = {
    "トヨタ自動車": "7203.T",
    "三菱UFJ": "8306.T",
    "Apple": "AAPL",
    "NVIDIA": "NVDA"
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
            # 過去3ヶ月のデータを取得
            stock = yf.Ticker(ticker)
            hist = stock.history(period="3mo")
            if hist.empty:
                continue

            # 移動平均線とRSIを計算
            hist['SMA5'] = hist['Close'].rolling(window=5).mean()
            hist['SMA25'] = hist['Close'].rolling(window=25).mean()
            hist['RSI'] = calculate_rsi(hist)

            latest = hist.iloc[-1]
            prev = hist.iloc[-2]

            # PERを取得
            info = stock.info
            per = info.get('trailingPE', 'データなし')
            if isinstance(per, float):
                per = round(per, 1)

            # クロスの判定
            golden_cross = (prev['SMA5'] <= prev['SMA25']) and (latest['SMA5'] > latest['SMA25'])
            dead_cross = (prev['SMA5'] >= prev['SMA25']) and (latest['SMA5'] < latest['SMA25'])

            # 買い条件（RSI 30以下 または ゴールデンクロス）
            buy_reasons = []
            if latest['RSI'] <= 30:
                buy_reasons.append(f"RSI {latest['RSI']:.1f} (売られすぎ)")
            if golden_cross:
                buy_reasons.append("ゴールデンクロス発生")
            
            if buy_reasons:
                buy_list.append(f"・**{name}** ({ticker}): {', '.join(buy_reasons)} / PER: {per}")

            # 売り条件（RSI 70以上 または デッドクロス）
            sell_reasons = []
            if latest['RSI'] >= 70:
                sell_reasons.append(f"RSI {latest['RSI']:.1f} (買われすぎ)")
            if dead_cross:
                sell_reasons.append("デッドクロス発生")
            
            if sell_reasons:
                sell_list.append(f"・**{name}** ({ticker}): {', '.join(sell_reasons)} / PER: {per}")

        except Exception as e:
            print(f"エラー: {name} - {e}")

        return buy_list, sell_list

def send_discord(buy_list, sell_list):
    if not WEBHOOK_URL:
        print("Webhook URLが設定されていません。")
        return

    message = "📊 **【定期確認】株式シグナルレポート**\n\n"
    
    if buy_list:
        message += "🟢 **【買い候補】**\n" + "\n".join(buy_list) + "\n\n"
    else:
        message += "🟢 **【買い候補】**\n・現在条件を満たす銘柄はありません。\n\n"

    if sell_list:
        message += "🔴 **【売り候補】**\n" + "\n".join(sell_list) + "\n\n"
    else:
        message += "🔴 **【売り候補】**\n・現在条件を満たす銘柄はありません。\n\n"

    # Discordへ送信
    payload = {"content": message}
    requests.post(WEBHOOK_URL, json=payload)

if __name__ == "__main__":
    buy, sell = check_signals()
    send_discord(buy, sell)

