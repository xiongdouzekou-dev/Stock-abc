import yfinance as yf
import pandas as pd
import requests
import os
import json
import time

WEBHOOK_URL = os.environ.get("WEBHOOK")
PORTFOLIO_FILE = "portfolio.json"

# あなたのGitHubリポジトリのワークフロー入力画面（フォーム）への直接リンク
WORKFLOW_URL = "https://github.com/xiongdouzekou-dev/Stock-abc/actions/workflows/schedule.yml"

TICKERS = {
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
    "Apple": "AAPL",
    "Microsoft": "MSFT",
    "NVIDIA": "NVDA",
    "Amazon": "AMZN",
    "Tesla": "TSLA",
    "S&P 500 ETF (SPY)": "SPY",
    "NASDAQ 100 ETF (QQQ)": "QQQ"
}

def calculate_rsi(data, period=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def analyze_stocks():
    scored_buys = []
    scored_sells = []

    for name, ticker in TICKERS.items():
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="3mo")
            if hist.empty or len(hist) < 25:
                time.sleep(0.5)
                continue

            hist['SMA5'] = hist['Close'].rolling(window=5).mean()
            hist['SMA25'] = hist['Close'].rolling(window=25).mean()
            hist['RSI'] = calculate_rsi(hist)

            latest = hist.iloc[-1]
            prev = hist.iloc[-2]
            current_price = latest['Close']

            info = stock.info
            per = info.get('trailingPE', 0)
            if not isinstance(per, (int, float)):
                per = 0

            golden_cross = (prev['SMA5'] <= prev['SMA25']) and (latest['SMA5'] > latest['SMA25'])
            dead_cross = (prev['SMA5'] >= prev['SMA25']) and (latest['SMA5'] < latest['SMA25'])

            # スコアリング計算
            buy_score = 0
            buy_reasons = []
            if latest['RSI'] <= 30:
                buy_score += (30 - latest['RSI'])
                buy_reasons.append(f"RSI {latest['RSI']:.1f}")
            if golden_cross:
                buy_score += 15
                buy_reasons.append("ゴールデンクロス")
            if per > 0 and per < 15:
                buy_score += 10
                buy_reasons.append(f"PER {per:.1f}")

            if buy_score > 0:
                scored_buys.append({
                    "name": name, "ticker": ticker, "score": buy_score, 
                    "price": current_price, "desc": ", ".join(buy_reasons)
                })

            sell_score = 0
            sell_reasons = []
            if latest['RSI'] >= 70:
                sell_score += (latest['RSI'] - 70)
                sell_reasons.append(f"RSI {latest['RSI']:.1f}")
            if dead_cross:
                sell_score += 15
                sell_reasons.append("デッドクロス")

            if sell_score > 0:
                scored_sells.append({
                    "name": name, "ticker": ticker, "score": sell_score, 
                    "price": current_price, "desc": ", ".join(sell_reasons)
                })

        except Exception as e:
            print(f"エラー: {name} - {e}")
        time.sleep(0.5)

    scored_buys.sort(key=lambda x: x['score'], reverse=True)
    scored_sells.sort(key=lambda x: x['score'], reverse=True)
    return scored_buys, scored_sells

def calculate_portfolio_pnl():
    if not os.path.exists(PORTFOLIO_FILE):
        return "・現在記録されている保有株はありません。"
    
    with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
        portfolio = json.load(f)

    if not portfolio:
        return "・保有・売買履歴が空です。"

    report_lines = []
    total_pnl = 0

    for item in portfolio:
        ticker = item["ticker"]
        buy_price = item["buy_price"]
        shares = item["shares"]
        name = item["name"]

        try:
            current_price = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
            pnl = (current_price - buy_price) * shares
            pnl_pct = ((current_price - buy_price) / buy_price) * 100
            total_pnl += pnl
            sign = "+" if pnl >= 0 else ""
            report_lines.append(f"・**{name}**: 取得単価 {buy_price:.1f} → 現在 {current_price:.1f} | 評価損益: {sign}{pnl:.1f}円 ({sign}{pnl_pct:.1f}%)")
        except:
            report_lines.append(f"・**{name}**: 価格取得失敗")

    total_sign = "+" if total_pnl >= 0 else ""
    report_lines.append(f"\n**総合評価損益合計: {total_sign}{total_pnl:.1f}円**")
    return "\n".join(report_lines)

def send_discord(buy_list, sell_list, pnl_text):
    if not WEBHOOK_URL:
        return

    message = "📊 **【株式シグナル & 収支レポート】**\n\n"

    # 買うべきベスト1 ＆ TOP5
    message += "🟢 **【買い推奨】**\n"
    if buy_list:
        best_buy = buy_list[0]
        message += f"🏆 **【👑 総合No.1買い銘柄】**\n👉 **{best_buy['name']}** ({best_buy['ticker']}) / 理由: {best_buy['desc']} / 価格: {best_buy['price']:.1f}\n\n"
 
