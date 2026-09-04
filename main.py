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
    await start_server(market_data, trader_manager, notifier, live_trader=live_trader)
    await init_task

    # Sistem Hazır — İlk 5M Mum Taramasını Yap
    print(">> [SİSTEM HAZIR] 100 Parite seviyeleri hesaplandı. İlk 5M mum taraması başlatılıyor...")
    try:
        await market_data.poll_all_candles_once()
    except Exception as e:
        print(f">> [ILK TARAMA UYARI]: {e}")

    # 60 Saniyelik Bellek Temizleyici + 5 Dakikalık Periyodik GitHub Sync (OOM & Veri Kaybı Kalkanı)
    async def memory_and_sync_watchdog():
        import gc
        sync_counter = 0
        while True:
            await asyncio.sleep(60)
            # Agresif bellek temizliği
            gc.collect()
            # 5M mum verilerini 200 satıra sınırla (her döngüde, OOM önleme)
            try:
                for sym in list(market_data.candles_5m.keys()):
                    df = market_data.candles_5m[sym]
                    if hasattr(df, '__len__') and len(df) > 200:
                        market_data.candles_5m[sym] = df.iloc[-200:].reset_index(drop=True)
            except Exception:
                pass
            # Her 5 dakikada bir (5 * 60s = 5 döngü) GitHub'a zorla push
            sync_counter += 1
            if sync_counter >= 5:
                sync_counter = 0
                try:
                    paper_trader.retry_pending_push()
                except Exception as e:
                    print(f">> [PERİYODİK SYNC HATA] {e}")

    asyncio.create_task(memory_and_sync_watchdog())

    # Saatlik otomatik Telegram Kasa & Portföy Raporlayıcıyı Başlat
    asyncio.create_task(notifier.start_hourly_scheduler(trader_manager, initial_balance=INITIAL_BALANCE, market_data=market_data))
    # Telegram /kasa ve kasa İnteraktif Komut Dinleyicisini Başlat
    asyncio.create_task(notifier.start_command_listener(trader_manager, market_data=market_data))

    try:
        await market_data.start_websocket()
    except KeyboardInterrupt:
        print("\n>> Robot durduruluyor...")
    finally:
        await market_data.close()

if __name__ == "__main__":
    asyncio.run(main())
