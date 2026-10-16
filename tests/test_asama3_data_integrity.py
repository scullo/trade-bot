import unittest
import asyncio
import time
from collections import deque
from paper_trader import PaperTrader
import market_data
from market_data import MarketDataManager, normalize_symbol, to_exchange_symbol
import live_trader


class TestAsama3DataIntegrity(unittest.TestCase):
    def setUp(self):
        self.pt = PaperTrader(initial_balance=10000.0)
        self.pt.balance = 10000.0
        self.pt.open_positions.clear()
        self.pt.history.clear()
        self.pt.save_history = lambda critical=False: None

    def test_01_funding_rate_normalization_and_100x_bug_fix(self):
        """
        TASK-3.1 Doğrulaması (DATA-001):
        100x fonlama hatasının çözüldüğünün kanıtı:
        %0.01 (0.0100) veya 0.0001 girildiğinde $250 pozisyonda kesinti tam $0.025 olmalıdır ($2.50 değil).
        """
        now = time.time()
        past_epoch = (int(now) // 28800) - 1

        # Case A: entry_funding_rate yüzde formatında (0.0100 = %0.01)
        self.pt.open_positions["BTC/USDT"] = {
            "symbol": "BTC/USDT",
            "side": "LONG",
            "entry_price": 60000.0,
            "margin": 50.0,
            "leverage": 5,
            "position_value": 250.0,
            "quantity": 250.0 / 60000.0,
            "entry_funding_rate": 0.0100,  # %0.01
            "last_funding_epoch": past_epoch,
            "accumulated_funding_fee": 0.0
        }

        # Market data olmaksızın pozisyon içindeki entry_funding_rate ile kesinti testi
        settled = self.pt.check_and_settle_funding_fees(market_data=None)
        self.assertEqual(len(settled), 1)
        evt = settled[0]
        self.assertAlmostEqual(evt["funding_rate"], 0.0001, places=6)
        self.assertAlmostEqual(evt["total_payment"], 0.0250, places=4)
        self.assertAlmostEqual(self.pt.balance, 10000.0 - 0.0250, places=4)
        self.assertAlmostEqual(self.pt.open_positions["BTC/USDT"]["accumulated_funding_fee"], 0.0250, places=4)

        # Case B: entry_funding_rate zaten ondalık formatta (0.0001)
        self.pt.balance = 10000.0
        self.pt.open_positions["ETH/USDT"] = {
            "symbol": "ETH/USDT",
            "side": "LONG",
            "entry_price": 3000.0,
            "margin": 50.0,
            "leverage": 5,
            "position_value": 250.0,
            "quantity": 250.0 / 3000.0,
            "entry_funding_rate": 0.0001,  # 0.0001
            "last_funding_epoch": past_epoch,
            "accumulated_funding_fee": 0.0
        }
        settled_eth = self.pt.check_and_settle_funding_fees(market_data=None)
        eth_evt = [e for e in settled_eth if e["symbol"] == "ETH/USDT"][0]
        self.assertAlmostEqual(eth_evt["funding_rate"], 0.0001, places=6)
        self.assertAlmostEqual(eth_evt["total_payment"], 0.0250, places=4)

    def test_02_funding_rate_with_market_data_lookup(self):
        """
        TASK-3.1 Doğrulaması:
        market_data.funding_rates ve get_funding_info üzerinden doğru veri çekimi
        """
        now = time.time()
        past_epoch = (int(now) // 28800) - 1

        class MockMarketData:
            def __init__(self):
                self.funding_rates = {
                    "SOL/USDT": {
                        "symbol": "SOL/USDT",
                        "rate": 0.00015,  # %0.015
                        "rate_pct": 0.0150
                    }
                }

            def _clean_symbol(self, s):
                return s

            def get_funding_info(self, s):
                clean = s.split(":")[0]
                return self.funding_rates.get(clean)

        mock_md = MockMarketData()
        self.pt.balance = 10000.0
        self.pt.open_positions["SOL/USDT"] = {
            "symbol": "SOL/USDT",
            "side": "SHORT",
            "entry_price": 150.0,
            "margin": 100.0,
            "leverage": 5,
            "position_value": 500.0,
            "quantity": 500.0 / 150.0,
            "entry_funding_rate": 0.0100,
            "last_funding_epoch": past_epoch,
            "accumulated_funding_fee": 0.0
        }

        settled = self.pt.check_and_settle_funding_fees(market_data=mock_md)
        self.assertEqual(len(settled), 1)
        evt = settled[0]
        # SHORT pozisyon pozitif fonlamada para kazanır: -pos_val * rate = -500 * 0.00015 = -$0.075 (ödemesi negatif, kasa artar)
        self.assertAlmostEqual(evt["funding_rate"], 0.00015, places=6)
        self.assertAlmostEqual(evt["total_payment"], -0.0750, places=4)
        self.assertAlmostEqual(self.pt.balance, 10000.075, places=3)

    def test_03_funding_rate_exchange_clamping(self):
        """
        TASK-3.1 Doğrulaması:
        Binance aşırı fonlama sınırları [-0.0075, +0.0075] clamping testi
        """
        now = time.time()
        past_epoch = (int(now) // 28800) - 1

        self.pt.open_positions["MEME/USDT"] = {
            "symbol": "MEME/USDT",
            "side": "LONG",
            "entry_price": 1.0,
            "margin": 100.0,
            "leverage": 1,
            "position_value": 100.0,
            "quantity": 100.0,
            "entry_funding_rate": 5.0,  # Aşırı %5.0 veri hatası
            "last_funding_epoch": past_epoch,
            "accumulated_funding_fee": 0.0
        }
        settled = self.pt.check_and_settle_funding_fees(market_data=None)
        self.assertEqual(len(settled), 1)
        evt = settled[0]
        # %5.0 -> 0.05 ondalık -> clamp: 0.0075 (%0.75 max limit)
        self.assertAlmostEqual(evt["funding_rate"], 0.0075, places=6)
        self.assertAlmostEqual(evt["total_payment"], 100.0 * 0.0075, places=4)

    def test_04_symbol_normalization_parity(self):
        """
        Sembol standardizasyonu ve format uyumu testi:
        market_data ve live_trader sembol normalizasyonları tam parity sağlamalıdır.
        """
        test_symbols = [
            ("BTC/USDT:USDT", "BTC/USDT"),
            ("BTCUSDT", "BTC/USDT"),
            ("BTC/USDT", "BTC/USDT"),
            ("ETH/USDT:USDT", "ETH/USDT"),
            ("ETHUSDT", "ETH/USDT"),
            ("1000PEPEUSDT", "1000PEPE/USDT"),
            ("1000PEPE/USDT:USDT", "1000PEPE/USDT"),
            ("SOL/USDT:USDT", "SOL/USDT")
        ]

        for raw, expected in test_symbols:
            md_norm = normalize_symbol(raw)
            lt_norm = live_trader.normalize_symbol(raw)
            self.assertEqual(md_norm, expected, f"market_data normalize_symbol failed for {raw}")
            self.assertEqual(lt_norm, expected, f"live_trader normalize_symbol failed for {raw}")
            self.assertEqual(md_norm, lt_norm, f"Parity mismatch for {raw}")

            # to_exchange_symbol parity
            md_ex = to_exchange_symbol(expected)
            lt_ex = live_trader.to_exchange_symbol(expected)
            self.assertEqual(md_ex, f"{expected}:USDT")
            self.assertEqual(lt_ex, f"{expected}:USDT")

    def test_05_market_data_get_funding_info_aliases(self):
        """
        MarketDataManager get_funding_info çoklu sembol biçimi desteği testi
        """
        md = MarketDataManager(all_symbols=["BTC/USDT"], active_symbols=["BTC/USDT"])
        md.funding_rates["BTC/USDT"] = {
            "symbol": "BTC/USDT",
            "rate": 0.0001,
            "rate_pct": 0.0100,
            "mark_price": 65000.0,
            "squeeze_status": "BALANCED"
        }

        # Standart form
        info1 = md.get_funding_info("BTC/USDT")
        self.assertEqual(info1["rate"], 0.0001)

        # CCXT futures form
        info2 = md.get_funding_info("BTC/USDT:USDT")
        self.assertEqual(info2["rate"], 0.0001)

        # Ham Binance form
        info3 = md.get_funding_info("BTCUSDT")
        self.assertEqual(info3["rate"], 0.0001)

        # Bilinmeyen coin fallback
        info_unknown = md.get_funding_info("UNKNOWN/USDT")
        self.assertEqual(info_unknown["rate"], 0.0001)
        self.assertEqual(info_unknown["squeeze_status"], "BALANCED")

    def test_06_reconnect_buffer_and_queue_cleanup(self):
        """
        TASK-3.2 Doğrulaması:
        reconnect() çağrıldığında bayat tasfiye tamponunun ve veri kuyruklarının temizlenmesi
        """
        async def run_reconnect_test():
            md = MarketDataManager(all_symbols=["BTC/USDT"], active_symbols=["BTC/USDT"])
            now = time.time()

            # Eski ve yeni tasfiyeler ekle
            md.recent_liquidations = [
                {"timestamp": now - 1200.0, "symbol": "BTC/USDT", "usd": 50000},  # Bayat (> 900s)
                {"timestamp": now - 300.0, "symbol": "BTC/USDT", "usd": 25000}    # Güncel (< 900s)
            ]
            md.symbol_liquidations_deque = {
                "BTC/USDT": deque([{"timestamp": now - 1000.0, "usd": 10000}])
            }

            # Reconnect çağır
            await md.reconnect()

            # Doğrulamalar:
            # 1. Bayat tasfiyeler ayıklandı, güncel tasfiye kaldı
            self.assertEqual(len(md.recent_liquidations), 1)
            self.assertEqual(md.recent_liquidations[0]["usd"], 25000)

            # 2. Deque sıfırlandı
            self.assertEqual(len(md.symbol_liquidations_deque["BTC/USDT"]), 0)

            # 3. Stream tick time güncellendi
            self.assertGreaterEqual(md.last_stream_tick_time, now - 5.0)

        asyncio.run(run_reconnect_test())


if __name__ == "__main__":
    unittest.main()
