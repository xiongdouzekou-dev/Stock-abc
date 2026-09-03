import yfinance as yf
import pandas as pd
import requests
import os
import json
import time

# Webhook URL
WEBHOOK_URL = "https://discord.com/api/webhooks/1544954027769466900/qc2WGESgTRdfPsLKULa5MwOZeFDC0Zf2pqxoNwfc3-_msbbCP6dJx9_wnQ8vH3n7uo1c"
PORTFOLIO_FILE = "portfolio.json"
TICKERS_FILE = "tickers.json"
WORKFLOW_URL = "https://github.com/xiongdouzekou-dev/Stock-abc/actions/workflows/schedule.yml"

def load_tickers():
    if not os.path.exists(TICKERS_FILE):
        return {}
    with open(TICKERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def calculate_rsi(data, period=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def analyze_stocks():
    tickers = load_tickers()
    scored_buys = []
    scored_sells = []

    for name, ticker in tickers.items():
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="3mo")
            if hist.empty or len(hist) < 25:
                time.sleep(0.1)
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
            pass
        time.sleep(0.1)

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

    message += "🟢 **【買い推奨】**\n"
    if buy_list:
        best_buy = buy_list[0]
        message += f"🏆 **【👑 総合No.1買い銘柄】**\n👉 **{best_buy['name']}** ({best_buy['ticker']}) / 理由: {best_buy['desc']} / 価格: {best_buy['price']:.1f}\n\n"

        top5_buys = buy_list[1:6]
        if top5_buys:
            message += "🌟 **【買い推奨 TOP5】**\n"
            for i, b in enumerate(top5_buys, 1):
                message += f"{i}. **{b['name']}** ({b['ticker']}) - {b['desc']}\n"
    else:
        message += "・現在条件を満たす銘柄はありません。\n"

    message += "\n"

    message += "🔴 **【売り推奨】**\n"
    if sell_list:
        best_sell = sell_list[0]
        message += f"⚠️ **【👑 総合No.1売り銘柄】**\n👉 **{best_sell['name']}** ({best_sell['ticker']}) / 理由: {best_sell['desc']} / 価格: {best_sell['price']:.1f}\n\n"
        
        top5_sells = sell_list[1:6]
        if top5_sells:
            message += "🔥 **【売り推奨 TOP5】**\n"
            for i, s in enumerate(top5_sells, 1):
                message += f"{i}. **{s['name']}** ({s['ticker']}) - {s['desc']}\n"
    else:
        message += "・現在条件を満たす銘柄はありません。\n"

    message += "\n💼 **【あなたの保有銘柄・収支報告】**\n" + pnl_text
    
    message += f"\n\n📝 **【売買記録の入力方法】**\n" \
               f"株を購入したら、下のリンクからフォームを開いて記録してください！\n" \
               f"👉 [売買記録入力フォームを開く]({WORKFLOW_URL})\n\n" \
               f"**【フォームの入力手順】**\n" \
               f"1. リンク先の右側にある **「Run workflow ▼」** ボタンを押す\n" \
               f"2. 各項目に以下のように入力する：\n" \
               f"   - **action_type**: `add` のままでOK\n" \
               f"   - **stock_name**: 銘柄名 (例: `トヨタ自動車`)\n" \
               f"   - **buy_price**: 購入したときの株価 (例: `2500`)\n" \
               f"   - **shares**: 購入した株数 (例: `1`)\n" \
               f"3. 緑色の **「Run workflow」** ボタンを押す"

    if len(message) > 2000:
        message = message[:1950] + "..."

    payload = {"content": message}
    response = requests.post(WEBHOOK_URL, json=payload)
    
    if response.status_code not in [200, 204]:
        print(f"Discord Error: {response.status_code} - {response.text}")
        exit(1)
    else:
        print("Discord notification sent successfully.")

if __name__ == "__main__":
    buys, sells = analyze_stocks()
    pnl_report = calculate_portfolio_pnl()
    send_discord(buys, sells, pnl_report)
