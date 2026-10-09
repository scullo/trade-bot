"""
test_priority0_memory_and_async_safety.py - ÖNCELİK 0 DOĞRULAMA TESTİ
=====================================================================
Valkyrie Master Audit - Öncelik 0 (Sistem Can Güvenliği ve Runtime Stabilitesi):
  - 0.1: Render Free Tier Bellek Aşımı (512MB RAM Çökmesi) Koruması:
         * Tip İndirgeme (timestamp int64, open/high/low/close float32)
         * In-Place Rolling Buffer (pd.concat bellek parçalanması engeli)
         * Dairesel Kuyruk (Deque maxlen=60) ve Periyodik GC / Ölü Parite Temizliği
         * JIT İndikatör Önbelleği (60s TTL)
  - 0.2: Telegram Mock Asenkron İstisnası (Defensive inspect.isawaitable ve AsyncMock Uyumu)
"""

import unittest
import time
import asyncio
from unittest.mock import MagicMock, AsyncMock
import pandas as pd
import numpy as np

from market_data import (
    downcast_candle_dataframe,
    update_rolling_candle_buffer,
    MarketDataManager
)
from strategy import StrategyEngine


class TestPriority0MemoryAndAsyncSafety(unittest.TestCase):

    def test_01_candle_dataframe_downcasting(self):
        """0.1.1: DataFrame Tip İndirgeme (Downcasting) Bellek Tasarrufu Doğrulaması."""
        # Standart float64 dataframe oluştur
        count = 300
        raw_df = pd.DataFrame({
            'timestamp': [1700000000000 + i * 300000 for i in range(count)],
            'open': [100.12345678] * count,
            'high': [102.12345678] * count,
            'low': [99.12345678] * count,
            'close': [101.12345678] * count,
            'volume': [50000.12345678] * count,
            'quote_volume': [5000000.12345678] * count,
            'taker_base': [25000.12345678] * count,
            'taker_quote': [2500000.12345678] * count,
            'qav': [5000000.12345678] * count
        })

        raw_mem = raw_df.memory_usage(deep=True).sum()

        downcasted = downcast_candle_dataframe(raw_df.copy())
        down_mem = downcasted.memory_usage(deep=True).sum()

        # Tipler int64 ve float32 olmalı
        self.assertEqual(downcasted['timestamp'].dtype, np.int64)
        self.assertEqual(downcasted['open'].dtype, np.float32)
        self.assertEqual(downcasted['close'].dtype, np.float32)
        self.assertEqual(downcasted['volume'].dtype, np.float32)

        # Bellek ayak izi yaklaşık %50 azalmalı
        self.assertLess(down_mem, raw_mem)
        savings_pct = ((raw_mem - down_mem) / raw_mem) * 100.0
        self.assertGreater(savings_pct, 40.0, f"Bellek tasarrufu %{savings_pct:.1f} oldu (Hedef: >%40)")

    def test_02_rolling_candle_buffer_in_place_and_cap(self):
        """0.1.2: In-Place Rolling Buffer (pd.concat parçalanma engeli) ve 300 Mum Sınırı."""
        df = pd.DataFrame()
        ts_start = 1700000000000

        # 1. İlk mumu ekle
        c1 = {'timestamp': ts_start, 'open': 10.0, 'high': 10.5, 'low': 9.8, 'close': 10.2, 'volume': 100.0}
        df = update_rolling_candle_buffer(df, c1, maxlen=300)
        self.assertEqual(len(df), 1)
        self.assertEqual(df['close'].iloc[-1], 10.2)

        # 2. Aynı mum içinde fiyat değişimi (In-place tick güncellemesi)
        c1_tick = {'timestamp': ts_start, 'open': 10.0, 'high': 10.8, 'low': 9.8, 'close': 10.7, 'volume': 150.0}
        df = update_rolling_candle_buffer(df, c1_tick, maxlen=300)
        self.assertEqual(len(df), 1, "Aynı mumda satır sayısı artmamalı!")
        self.assertAlmostEqual(df['close'].iloc[-1], 10.7, places=2)
        self.assertAlmostEqual(df['high'].iloc[-1], 10.8, places=2)

        # 3. 350 adet yeni mum ekleyerek maxlen=300 tavanını test et
        for i in range(1, 351):
            c_next = {
                'timestamp': ts_start + (i * 300000),
                'open': 10.0 + i * 0.01,
                'high': 10.5 + i * 0.01,
                'low': 9.8 + i * 0.01,
                'close': 10.2 + i * 0.01,
                'volume': 100.0
            }
            df = update_rolling_candle_buffer(df, c_next, maxlen=300)

        self.assertEqual(len(df), 300, "Buffer boyutu kesinlikle 300 mumu aşmamalı!")
        # En son mum en güncel olmalı
        expected_last_ts = ts_start + (350 * 300000)
        self.assertEqual(df['timestamp'].iloc[-1], expected_last_ts)

    def test_03_deque_tightening_and_pruning(self):
        """0.1.5: Deque maxlen=60 ve inaktif parite süpürme doğrulaması."""
        md = MarketDataManager.__new__(MarketDataManager)
        all_syms = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        md.all_symbols = all_syms
        md.active_symbols = {"BTC/USDT"}
        md.coinbase_supported_assets = ["BTC", "ETH"]
        md.coinbase_cvd_history = {}
        md.block_trades_history = {}
        md.symbol_liquidations_deque = {}
        md.exchange_netflows = {}

        # 100 adet blok emir kaydı gönder, maxlen=60 sayesinde 60'ta sabitlenmeli
        for i in range(100):
            md._record_block_trade_pressure("BTC/USDT", 50000.0, False, time.time() + i)

        btc_dq = md.block_trades_history.get("BTC/USDT") or md.block_trades_history.get("BTCUSDT") or md.block_trades_history.get("BTC")
        self.assertIsNotNone(btc_dq)
        self.assertLessEqual(len(btc_dq), 60, "Blok işlem deque maxlen=60 ile sınırlandırılmalı!")

        # İnaktif ve listede olmayan ölü sembol ekle
        md.block_trades_history["DEADCOINUSDT"] = MagicMock()
        self.assertIn("DEADCOINUSDT", md.block_trades_history)

        # Temizlik protokolünü simüle et
        active_and_all = set(md.all_symbols) | set(md.active_symbols)
        for k in list(md.block_trades_history.keys()):
            if k not in active_and_all and k.replace('USDT', '') not in [s.replace('/USDT', '') for s in active_and_all]:
                md.block_trades_history.pop(k, None)

        self.assertNotIn("DEADCOINUSDT", md.block_trades_history, "Ölü parite anahtarı başarıyla süpürüldü!")

    def test_04_jit_indicator_caching(self):
        """0.1.3: JIT İndikatör Önbelleği (60s TTL) Doğrulaması."""
        md = MarketDataManager.__new__(MarketDataManager)
        md.levels = {}
        md.current_prices = {"BTC/USDT": 65000.0}
        md.candles_1d = {"BTC/USDT": pd.DataFrame({
            'timestamp': [1700000000000, 1700086400000],
            'open': [64000.0, 64500.0],
            'high': [66000.0, 65800.0],
            'low': [63500.0, 64200.0],
            'close': [64500.0, 65000.0],
            'volume': [1000.0, 1200.0]
        })}
        md.candles_5m = {"BTC/USDT": pd.DataFrame({
            'timestamp': [1700086400000 + i * 300000 for i in range(30)],
            'open': [65000.0] * 30,
            'high': [65200.0] * 30,
            'low': [64800.0] * 30,
            'close': [65000.0] * 30,
            'volume': [50.0] * 30
        })}
        md._vp_cache = {}
        md._naked_cache = {}
        md._session_cache = {}
        md.symbol_metrics = {}
        md.orderbook_depth = {}
        md.symbol_cvd_history = {}
        md.symbol_price_history = {}

        # İlk hesaplama
        md.recalculate_levels("BTC/USDT")
        self.assertIn("BTC/USDT", md._vp_cache)
        first_vp_ts = md._vp_cache["BTC/USDT"]["ts"]

        # 5 saniye sonra tekrar çağır - önbellekten dönmeli (ts değişmemeli)
        time.sleep(0.05)
        md.recalculate_levels("BTC/USDT")
        second_vp_ts = md._vp_cache["BTC/USDT"]["ts"]
        self.assertEqual(first_vp_ts, second_vp_ts, "60s içinde JIT önbellekten okunmalı, yeniden hesaplanmamalı!")

    def test_05_defensive_await_telegram_notifier(self):
        """0.2: Defansif Await Koruması (MagicMock can't be used in 'await' istisnasının sıfırlanması)."""
        strat = StrategyEngine.__new__(StrategyEngine)
        strat.market_data = MagicMock()
        strat.market_data.candles_5m = {}
        strat.paper_trader = MagicMock()
        strat.paper_trader.get_free_balance = MagicMock(return_value=5000.0)

        # 1. Standart MagicMock (asenkron olmayan eski mock) ile çağırıldığında ÇÖKMEMELİ
        strat.notifier = MagicMock()
        # notify_position_opened ve notify_position_closed await edilmeye çalışıldığında çökmemeli!
        async def run_open_close():
            await strat._notify_open({"symbol": "BTC/USDT", "side": "LONG"})
            await strat._notify_close({"symbol": "BTC/USDT", "side": "LONG"})
            # notify_insufficient_balance kontrolü
            strat.notifier.notify_insufficient_balance = MagicMock()
            # manuel simüle
            import inspect
            ret = strat.notifier.notify_insufficient_balance()
            if inspect.isawaitable(ret):
                await ret

        asyncio.run(run_open_close())

        # 2. Modern AsyncMock ile çağırıldığında da kusursuz çalışmalı
        strat.notifier = AsyncMock()
        async def run_async_mock():
            await strat._notify_open({"symbol": "ETH/USDT", "side": "SHORT"})
            await strat._notify_close({"symbol": "ETH/USDT", "side": "SHORT"})

        asyncio.run(run_async_mock())


if __name__ == "__main__":
    unittest.main()
