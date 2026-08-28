import requests
import json

test_urls = [
    "https://api.binance.com/api/v3/ticker/price?symbols=[\"BTCUSDT\",\"ETHUSDT\",\"SOLUSDT\",\"ENAUSDT\",\"XRPUSDT\"]",
    "https://api.binance.me/api/v3/ticker/price?symbols=[\"BTCUSDT\",\"ETHUSDT\",\"SOLUSDT\",\"ENAUSDT\",\"XRPUSDT\"]",
    "https://fapi.binance.me/fapi/v1/ticker/price?symbols=[\"BTCUSDT\",\"ETHUSDT\",\"SOLUSDT\",\"ENAUSDT\",\"XRPUSDT\"]",
    "https://data-api.binance.vision/api/v3/ticker/price?symbols=[\"BTCUSDT\",\"ETHUSDT\",\"SOLUSDT\",\"ENAUSDT\",\"XRPUSDT\"]"
]

for url in test_urls:
    try:
        r = requests.get(url, timeout=3)
        if r.status_code == 200:
            print("[OK]", url[:35], "->", r.json()[:2])
        else:
            print("[HTTP", r.status_code, "]", url[:35])
    except Exception as e:
        print("[FAIL]", url[:35], "->", type(e).__name__)
