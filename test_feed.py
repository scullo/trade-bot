import asyncio
import aiohttp
import json

async def test_binance():
    url = "wss://fstream.binance.com/stream?streams=btcusdt@ticker/ethusdt@ticker"
    print("Connecting to:", url)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(url) as ws:
                print("Connected! Waiting for messages...")
                for i in range(10):
                    msg = await ws.receive()
                    print(f"Message {i}: type={msg.type}")
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        print("RECEIVED DATA:", json.dumps(data)[:200])
                    elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        print("CLOSED/ERROR:", msg)
                        break
    except Exception as e:
        print("EXCEPTION:", e)

if __name__ == "__main__":
    asyncio.run(test_binance())
