import asyncio
import aiohttp
import json

async def test_ws():
    urls = [
        "wss://stream.binance.com:9443/stream?streams=btcusdt@ticker/ethusdt@ticker/solusdt@ticker/enausdt@ticker/xrpusdt@ticker",
        "wss://data-stream.binance.vision/stream?streams=btcusdt@ticker/ethusdt@ticker/solusdt@ticker/enausdt@ticker/xrpusdt@ticker"
    ]
    for url in urls:
        print(f"Testing WS: {url[:45]}...")
        try:
            async with aiohttp.ClientSession() as s:
                async with s.ws_connect(url, timeout=4) as ws:
                    print("  CONNECTED!")
                    for _ in range(3):
                        msg = await asyncio.wait_for(ws.receive_str(), timeout=3)
                        data = json.loads(msg)
                        print("  MSG:", data.get('stream'), "Price:", data['data']['c'])
                    print("  SUCCESS!")
                    return url
        except Exception as e:
            print("  FAIL:", type(e).__name__, e)
    return None

if __name__ == "__main__":
    asyncio.run(test_ws())
