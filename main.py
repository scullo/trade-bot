import asyncio
import os
import time
from config import ALL_AVAILABLE_SYMBOLS, DEFAULT_ACTIVE_SYMBOLS, TIMEFRAME, INITIAL_BALANCE, LEVERAGE, POSITION_SIZE_USDT
from market_data import MarketDataManager
from paper_trader import PaperTrader
from live_trader import LiveTrader
from trader_manager import TraderManager
from telegram_bot import TelegramNotifier
from strategy import StrategyEngine
from web_server import start_server, broadcast_tick

async def main():
    print("=" * 65)
    print("      CANLI GRAFIK IZLEME & AL-SAT ROBOTU (VALKYRIE QUANT)      ")
    print("=" * 65)
    print(f"• Takip Edilen Pariteler ({len(DEFAULT_ACTIVE_SYMBOLS)} Aktif / {len(ALL_AVAILABLE_SYMBOLS)} Toplam)")
    print(f"• Zaman Dilimi         : {TIMEFRAME}")
    print("=" * 65)

    market_data = MarketDataManager(all_symbols=ALL_AVAILABLE_SYMBOLS, active_symbols=DEFAULT_ACTIVE_SYMBOLS, timeframe=TIMEFRAME)
    paper_trader = PaperTrader(initial_balance=INITIAL_BALANCE, leverage=LEVERAGE, margin_per_trade=POSITION_SIZE_USDT)
    live_trader = LiveTrader()
    trader_manager = TraderManager(paper_trader, live_trader)
    notifier = TelegramNotifier()
    strategy = StrategyEngine(trader_manager, notifier, market_data=market_data)

    async def on_tick(symbol, price):
        await broadcast_tick(symbol, price)
        if symbol in market_data.active_symbols:
            levels = market_data.levels.get(symbol, {})
            await strategy.evaluate_tick(symbol, price, levels)

    async def on_candle_close(symbol, current_candle, prev_candle):
        levels = market_data.levels.get(symbol, {})
        print(f">> [MUM KAPANDI] {symbol} | Kapanis: {current_candle['close']} (Onceki: {prev_candle['close']})")
        await strategy.evaluate_candle_close(symbol, current_candle, prev_candle, levels)

    market_data.on_tick_callback = on_tick
    market_data.on_candle_close_callback = on_candle_close

    init_task = asyncio.create_task(market_data.initialize())
    await start_server(market_data, trader_manager, notifier, live_trader=live_trader, strategy=strategy)
    await init_task

    # Sistem Hazır — WebSocket döngüsüne geçiliyor (candle_poller_worker ısınma sonrası ilk taramayı yapacaktır)
    print(">> [SİSTEM HAZIR] 100 Parite seviyeleri ve veritabanı hazır. Canlı WebSocket ve tarayıcı başlatılıyor...")

    # 60 Saniyelik Bellek Temizleyici + 5 Dakikalık Periyodik GitHub Sync + Bellek Baskısı Algılama (OOM & Veri Kaybı Kalkanı)
    async def memory_and_sync_watchdog():
        import gc
        sync_counter = 0
        while True:
            await asyncio.sleep(60)
            # Agresif bellek temizliği (Render 512MB RAM Koruması)
            gc.collect()
            # 5M mum verilerini 150 satıra sınırla (her döngüde, OOM önleme)
            try:
                for sym in list(market_data.candles_5m.keys()):
                    df = market_data.candles_5m[sym]
                    if hasattr(df, '__len__') and len(df) > 150:
                        market_data.candles_5m[sym] = df.iloc[-150:].reset_index(drop=True)
            except Exception:
                pass

            # Her 15 dakikada bir (15 * 60s = 15 döngü) bekleyen GitHub state sync kontrolü
            sync_counter += 1
            if sync_counter >= 15:
                sync_counter = 0
                try:
                    paper_trader.retry_pending_push()
                except Exception as e:
                    print(f">> [PERİYODİK SYNC HATA] {e}")

    asyncio.create_task(memory_and_sync_watchdog())

    # Render 15 Dakikalık Hareketsizlik Uyku Kalkanı (Keep-Alive Self-Ping)
    async def render_keepalive_watchdog():
        import aiohttp
        render_url = os.environ.get("RENDER_EXTERNAL_URL", "https://trade-bot-0te2.onrender.com") + "/ping"
        await asyncio.sleep(30)
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(render_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status == 200:
                            print(">> [KEEP-ALIVE] Render uyku kalkanı aktif (ping 200 OK)")
                        else:
                            print(f">> [KEEP-ALIVE UYARI] Render ping yanıtı: {resp.status}")
            except Exception as e:
                print(f">> [KEEP-ALIVE HATA] {e}")
            await asyncio.sleep(180)  # Her 3 dakikada bir (Render 15dk uyku sınırı için güvenli aralık)

    asyncio.create_task(render_keepalive_watchdog())

    # Saatlik otomatik Telegram Kasa & Portföy Raporlayıcıyı Başlat
    asyncio.create_task(notifier.start_hourly_scheduler(trader_manager, initial_balance=INITIAL_BALANCE, market_data=market_data))
    # Telegram /kasa ve kasa İnteraktif Komut Dinleyicisini Başlat
    asyncio.create_task(notifier.start_command_listener(trader_manager, market_data=market_data))

    # Global Crash Recovery Loop — WebSocket çöktüğünde bot ölmez, otomatik yeniden başlar
    ws_backoff = 5
    while True:
        try:
            await market_data.start_websocket()
        except KeyboardInterrupt:
            print("\n>> Robot durduruluyor...")
            break
        except Exception as e:
            print(f">> [KRİTİK] WebSocket ana döngüsü çöktü: {e}. {ws_backoff}s sonra yeniden başlatılıyor...")
            await asyncio.sleep(ws_backoff)
            ws_backoff = min(ws_backoff * 2, 120)  # Max 2dk bekleme
        else:
            ws_backoff = 5  # Başarılı çalışma sonrası sıfırla

    await market_data.close()

if __name__ == "__main__":
    asyncio.run(main())
