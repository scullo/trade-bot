import os
import sys
import json
import base64
import urllib.request
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import INITIAL_BALANCE
from paper_trader import _get_gh_token
from excel_exporter import create_styled_excel_report

GITHUB_RAW_URL = "https://raw.githubusercontent.com/scullo/trade-bot/main/trade_history.json"

def run_backup():
    token = _get_gh_token()
    if not token:
        print("GITHUB_TOKEN bulunamadi!")
        return

    print(">> GitHub'dan en guncel trade_history.json indiriliyor...")
    req = urllib.request.Request(GITHUB_RAW_URL, headers={
        "Authorization": f"token {token}",
        "User-Agent": "TradeBot/1.0"
    })

    try:
        res = urllib.request.urlopen(req, timeout=15)
        data = json.loads(res.read().decode("utf-8"))
    except Exception as e:
        print(f"HATA: GitHub'dan veri cekilemedi: {e}")
        return

    history = data.get("history", [])
    balance = data.get("balance", INITIAL_BALANCE)

    print(f">> Excel raporu olusturuluyor ({len(history)} islem)...")
    buf = create_styled_excel_report(history, current_balance=balance, initial_balance=INITIAL_BALANCE)

    desktop_path = os.path.join(os.environ["USERPROFILE"], "Desktop")
    back_dir = os.path.join(desktop_path, "Back")
    
    now = datetime.now()
    date_str = now.strftime("%d.%m.%Y")
    time_str = now.strftime("%H-%M")
    
    daily_dir = os.path.join(back_dir, date_str)
    os.makedirs(daily_dir, exist_ok=True)
    
    file_name = f"Rapor_{time_str}.xlsx"
    file_path = os.path.join(daily_dir, file_name)
    
    with open(file_path, "wb") as f:
        f.write(buf.getvalue())
        
    print(f"BASARILI! Excel kaydedildi: {file_path}")

if __name__ == "__main__":
    run_backup()
