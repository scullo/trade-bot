import asyncio
import json
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from live_trader import normalize_symbol, to_exchange_symbol, LiveTrader, save_positions_state, load_positions_state
from trader_manager import TraderManager
from paper_trader import PaperTrader
import config


class TestLiveReadinessSuite(unittest.TestCase):

    def test_01_symbol_normalization(self):
        """1. Sembol adları uyumluluk testi: CCXT Binance USD-M ile bot formatı dönüşümleri"""
        self.assertEqual(normalize_symbol("BTC/USDT:USDT"), "BTC/USDT")
        self.assertEqual(normalize_symbol("BTCUSDT"), "BTC/USDT")
        self.assertEqual(normalize_symbol("BTC/USDT"), "BTC/USDT")
        self.assertEqual(normalize_symbol("ETH/USDT:USDT"), "ETH/USDT")
        self.assertEqual(normalize_symbol("1000PEPE/USDT:USDT"), "1000PEPE/USDT")
        self.assertEqual(normalize_symbol("SOL/USDT"), "SOL/USDT")

        mock_markets = {
            "BTC/USDT:USDT": {"id": "BTCUSDT", "symbol": "BTC/USDT:USDT"},
            "ETH/USDT:USDT": {"id": "ETHUSDT", "symbol": "ETH/USDT:USDT"},
        }
        self.assertEqual(to_exchange_symbol("BTC/USDT", mock_markets), "BTC/USDT:USDT")
        self.assertEqual(to_exchange_symbol("BTC/USDT:USDT", mock_markets), "BTC/USDT:USDT")
        self.assertEqual(to_exchange_symbol("ETH/USDT", mock_markets), "ETH/USDT:USDT")

    def test_02_config_safety_defaults(self):
        """2. Güvenlik ayarları: Günlük devre kesici ve bekleme süresi AKTİF mi?"""
        self.assertTrue(config.ENABLE_DAILY_CIRCUIT_BREAKER, "ENABLE_DAILY_CIRCUIT_BREAKER True olmalıdır.")
        self.assertTrue(config.ENABLE_COOLDOWN_THROTTLE, "ENABLE_COOLDOWN_THROTTLE True olmalıdır.")
        self.assertGreaterEqual(config.SYMBOL_MIN_COOLDOWN_MINUTES, 1, "Soğuma süresi en az 1 dakika olmalıdır.")
        self.assertAlmostEqual(config.MAX_DAILY_LOSS_PCT, 0.05, places=2)

    def test_03_trader_manager_proxy_delegation(self):
        """3. TraderManager proxy ve metot yönlendirme testi"""
        paper = PaperTrader(initial_balance=10000.0, leverage=5, margin_per_trade=50.0)
        live = LiveTrader()
        mgr = TraderManager(paper, live)

        # DEMO modunda paper trader'a yönlenmeli
        mgr.set_mode("DEMO")
        self.assertEqual(mgr.mode, "DEMO")
        self.assertIs(mgr.active_trader, paper)
        self.assertEqual(mgr.balance, paper.balance)
        self.assertIs(mgr.open_positions, paper.open_positions)

        # __getattr__ ile PaperTrader'a özgü metotları doğrudan çağırabilmeli
        self.assertTrue(hasattr(mgr, "save_local_history"))
        self.assertTrue(callable(mgr.save_local_history))

        # LIVE moduna geçişte live_trader'a yönlenmeli
        mgr.set_mode("LIVE")
        self.assertEqual(mgr.mode, "LIVE")
        self.assertIs(mgr.active_trader, live)
        self.assertIs(mgr.open_positions, live.open_positions)
        self.assertTrue(hasattr(mgr, "save_local_history"))

    def test_04_positions_state_persistence(self):
        """4. Pozisyon meta verisi kalıcılık testi (live_positions_state.json)"""
        sample_positions = {
            "BTC/USDT": {
                "symbol": "BTC/USDT",
                "side": "LONG",
                "entry_price": 65000.0,
                "amount": 0.01,
                "leverage": 5,
                "hard_stop": 63000.0,
                "tp1": 68000.0,
                "sl_order_id": "123456",
                "tp_order_id": "789012"
            }
        }
        save_positions_state(sample_positions)
        restored = load_positions_state()
        self.assertIn("BTC/USDT", restored)
        self.assertEqual(restored["BTC/USDT"]["hard_stop"], 63000.0)
        self.assertEqual(restored["BTC/USDT"]["sl_order_id"], "123456")

    def test_05_live_trader_order_and_sl_tp_lifecycle(self):
        """5. LiveTrader: Borsa Stop-Loss / Take-Profit (auto_sl_tp), load_markets ve kapatma lifecycle testi"""
        async def _run():
            trader = LiveTrader()
            mock_ex = AsyncMock()
            mock_ex.markets = {
                "BTC/USDT:USDT": {
                    "id": "BTCUSDT",
                    "symbol": "BTC/USDT:USDT",
                    "precision": {"amount": 3, "price": 1},
                    "limits": {"amount": {"min": 0.001}}
                }
            }
            mock_ex.load_markets = AsyncMock(return_value=mock_ex.markets)
            mock_ex.amount_to_precision = MagicMock(side_effect=lambda s, a: f"{round(a, 3):.3f}")
            mock_ex.price_to_precision = MagicMock(side_effect=lambda s, p: f"{round(p, 1):.1f}")
            mock_ex.set_leverage = AsyncMock(return_value={})
            mock_ex.set_margin_mode = AsyncMock(return_value={})
            mock_ex.create_order = AsyncMock(side_effect=[
                {"id": "main_order_101", "average": 60000.0, "price": 60000.0},     # market entry
                {"id": "sl_order_202"},                                              # STOP_MARKET
                {"id": "tp_order_303"},                                              # TAKE_PROFIT_MARKET
                {"id": "close_order_404", "average": 62000.0, "price": 62000.0}     # close position
            ])
            mock_ex.cancel_all_orders = AsyncMock(return_value=[])
            mock_ex.cancel_order = AsyncMock(return_value={})
            mock_ex.fetch_balance = AsyncMock(return_value={"USDT": {"total": 5000.0, "free": 4500.0}})

            trader.exchange = mock_ex
            trader._markets_loaded = True
            trader.config["auto_sl_tp"] = True

            # Pozisyon aç
            pos = await trader.open_position(
                symbol="BTC/USDT",
                side="LONG",
                current_price=60000.0,
                trade_type="BREAKOUT",
                reason="TEST_ENTRY",
                hard_stop=58500.0,
                tp1=63000.0,
                custom_margin=100.0,
                custom_leverage=5
            )

            self.assertIsNotNone(pos)
            self.assertEqual(pos["symbol"], "BTC/USDT")
            self.assertEqual(pos["sl_order_id"], "sl_order_202")
            self.assertEqual(pos["tp_order_id"], "tp_order_303")
            self.assertIn("BTC/USDT", trader.open_positions)

            # mock_ex çağrılarını denetle
            self.assertEqual(mock_ex.create_order.call_count, 3)
            # 1. Ana emir
            first_call = mock_ex.create_order.call_args_list[0]
            self.assertEqual(first_call.kwargs["symbol"], "BTC/USDT:USDT")
            self.assertEqual(first_call.kwargs["type"], "market")
            self.assertEqual(first_call.kwargs["side"], "buy")

            # 2. SL emri
            sl_call = mock_ex.create_order.call_args_list[1]
            self.assertEqual(sl_call.kwargs["symbol"], "BTC/USDT:USDT")
            self.assertEqual(sl_call.kwargs["type"], "STOP_MARKET")
            self.assertEqual(sl_call.kwargs["side"], "sell")
            self.assertEqual(sl_call.kwargs["params"]["stopPrice"], 58500.0)
            self.assertTrue(sl_call.kwargs["params"]["reduceOnly"])

            # 3. TP emri
            tp_call = mock_ex.create_order.call_args_list[2]
            self.assertEqual(tp_call.kwargs["symbol"], "BTC/USDT:USDT")
            self.assertEqual(tp_call.kwargs["type"], "TAKE_PROFIT_MARKET")
            self.assertEqual(tp_call.kwargs["side"], "sell")
            self.assertEqual(tp_call.kwargs["params"]["stopPrice"], 63000.0)
            self.assertTrue(tp_call.kwargs["params"]["reduceOnly"])

            # Pozisyon kapat
            closed = await trader.close_position("BTC/USDT", current_price=62000.0, reason="TP_HIT")
            self.assertIsNotNone(closed)
            self.assertEqual(closed["symbol"], "BTC/USDT")
            self.assertNotIn("BTC/USDT", trader.open_positions)
            # cancel_all_orders çağrıldı mı?
            mock_ex.cancel_all_orders.assert_called_with("BTC/USDT:USDT")

        asyncio.run(_run())

    def test_06_sync_open_positions_with_exchange_reconciliation(self):
        """6. sync_open_positions: Yeniden başlatma sonrası borsa pozisyonlarını alma ve eşleme"""
        async def _run():
            trader = LiveTrader()
            trader.open_positions = {
                "BTC/USDT": {
                    "id": "saved_1",
                    "symbol": "BTC/USDT",
                    "hard_stop": 64000.0,
                    "tp1": 69000.0,
                    "sl_order_id": "sl_old_1",
                    "reason": "ORIGINAL_SIGNAL"
                }
            }

            mock_ex = AsyncMock()
            mock_ex.fetch_positions = AsyncMock(return_value=[
                {
                    "symbol": "BTC/USDT:USDT",
                    "side": "long",
                    "contracts": 0.05,
                    "entryPrice": 65500.0,
                    "leverage": 5,
                    "notional": 3275.0,
                    "unrealizedPnl": 45.2,
                    "timestamp": 1700000000000
                }
            ])
            trader.exchange = mock_ex

            await trader.sync_open_positions()

            self.assertIn("BTC/USDT", trader.open_positions)
            pos = trader.open_positions["BTC/USDT"]
            # Borsa verileri güncellendi
            self.assertEqual(pos["amount"], 0.05)
            self.assertEqual(pos["entry_price"], 65500.0)
            self.assertEqual(pos["unrealized_pnl"], 45.2)
            # Yerel meta veriler korundu
            self.assertEqual(pos["hard_stop"], 64000.0)
            self.assertEqual(pos["tp1"], 69000.0)
            self.assertEqual(pos["sl_order_id"], "sl_old_1")
            self.assertEqual(pos["reason"], "ORIGINAL_SIGNAL")

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
