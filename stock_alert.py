   import yfinance as yf
import pandas as pd
import requests
import os
import json
import time

WEBHOOK_URL = os.environ.get("WEBHOOK")
PORTFOLIO_FILE = "portfolio.json"
WORKFLOW_URL = "https://github.com/xiongdouzekou-dev/Stock-abc/actions/workflows/schedule.yml"

TICKERS = {
    "トヨタ自動車": "7203.T",
    "三菱UFJ": "8306.T",
    "Apple": "AAPL"
}

def analyze_stocks():
    return [], []

def calculate_portfolio_pnl():
    return "・保有銘柄なし"

def send_discord(buy_list, sell_list, pnl_text):
    if not WEBHOOK_URL:
        print("エラー: WEBHOOKシークレットが設定されていません。")
        return

    message = "テスト通知です。これが届けば設定は正常です！"
    payload = {"content": message}
    
    response = requests.post(WEBHOOK_URL, json=payload)
    print(f"Discordからの応答コード: {response.status_code}")
    print(f"Discordからの応答内容: {response.text}")

if __name__ == "__main__":
    buys, sells = analyze_stocks()
    pnl_report = calculate_portfolio_pnl()
    send_discord(buys, sells, pnl_report)
