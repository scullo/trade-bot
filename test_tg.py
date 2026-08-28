import requests

token = "8893395987:AAGKAzD4sUg5LwMLLWHSt5U1VRRS7JE-m9c"
chat_id = "829687700"

msg = """<b>⚡ TRADE DESK — BİLDİRİM TESTİ</b>
━━━━━━━━━━━━━━━━━━━━
🟢 <b>Sistem Durumu:</b> Aktif ve Canlı
💰 <b>Kasa:</b> 100.00 USDT
📊 <b>Kaldıraç:</b> 5x (Marjin: 10 USDT)
━━━━━━━━━━━━━━━━━━━━
<i>Tüm işlemler bu kanala anlık olarak raporlanacaktır.</i>"""

url = f"https://api.telegram.org/bot{token}/sendMessage"
r = requests.post(url, json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
print("STATUS:", r.status_code, "RESPONSE:", r.json())
