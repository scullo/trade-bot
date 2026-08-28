import requests
import time

endpoints = [
    "https://fapi.binance.com/fapi/v1/ticker/price?symbols=[\"BTCUSDT\",\"ETHUSDT\",\"SOLUSDT\",\"ENAUSDT\",\"XRPUSDT\"]",
    "https://api.binance.com/api/v3/ticker/price?symbols=[\"BTCUSDT\",\"ETHUSDT\",\"SOLUSDT\",\"ENAUSDT\",\"XRPUSDT\"]"
]

for ep in endpoints:
    t0 = time.time()
    try:
        r = requests.get(ep, timeout=3)
        dt = (time.time() - t0) * 1000
        print(f"SUCCESS ({dt:.1f}ms): {ep[:35]}... -> {r.json()}")
    except Exception as e:
        print(f"FAILED: {ep[:35]}... -> {e}")
