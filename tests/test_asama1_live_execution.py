import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock
from live_trader import LiveTrader, normalize_symbol, to_exchange_symbol
from security_vault import SecurityVault
import config

class TestAsama1LiveExecution(unittest.TestCase):
    """
    Aşama 1 Doğrulama Test Süiti:
    - EXEC-001: LiveTrader.close_position kwargs ve partial close desteği
    - EXEC-002: LiveTrader.open_position entry_price / current_price / kwargs desteği
    - TRADE-001: check_daily_circuit_breaker %500 çarpan hatası düzeltmesi
    - TRADE-004: StrategyEngine marjin tavanı dönüş kontrolü
    - ORPHAN-CLEAN: sync_open_positions yetim emir iptali
    """

    def setUp(self):
        self.trader = LiveTrader()
        mock_ex = AsyncMock()
        mock_ex.markets = {
            "BTC/USDT:USDT": {
                "id": "BTCUSDT",
                "symbol": "BTC/USDT:USDT",
                "precision": {"amount": 3, "price": 1},
                "limits": {"amount": {"min": 0.001}}
            }
        }
        mock_ex.amount_to_precision = MagicMock(side_effect=lambda s, a: f"{round(a, 3):.3f}")
        mock_ex.price_to_precision = MagicMock(side_effect=lambda s, p: f"{round(p, 1):.1f}")
        mock_ex.set_leverage = AsyncMock(return_value={})
        mock_ex.set_margin_mode = AsyncMock(return_value={})
        mock_ex.create_order = AsyncMock(side_effect=[
            {"id": "entry_101", "average": 60000.0, "price": 60000.0},
            {"id": "sl_201"},
            {"id": "tp_301"},
            {"id": "partial_close_401", "average": 61500.0, "price": 61500.0},
            {"id": "breakeven_sl_501"},
            {"id": "full_close_601", "average": 63000.0, "price": 63000.0}
        ])
        mock_ex.cancel_all_orders = AsyncMock(return_value=[])
        mock_ex.cancel_order = AsyncMock(return_value={})
        mock_ex.fetch_balance = AsyncMock(return_value={"USDT": {"total": 10000.0, "free": 9000.0}})
        mock_ex.fetch_my_trades = AsyncMock(return_value=[
            {"price": 58500.0, "fee": {"cost": 0.5}}
        ])

        self.trader.exchange = mock_ex
        self.trader._markets_loaded = True
        self.trader.config["auto_sl_tp"] = True

    def test_01_open_position_kwargs_from_strategy(self):
        """EXEC-002: strategy.py:4026'dan gelen entry_price ve kwargs parametreleri hatasız açılmalı"""
        async def _run():
            # strategy.py tarafından gönderilen tam kwargs çağrısı simülasyonu
            res = await self.trader.open_position(
                symbol="BTC/USDT",
                side="LONG",
                entry_price=60000.0,
                reason="Sniper Long",
                soft_stop=59000.0,
                hard_stop=58500.0,
                tp1=61500.0,
                tp2=63000.0,
                trade_type="BREAKOUT",
                snapshot_levels={"R4": 61000.0},
                setup_id="SETUP_1_R4_BREAKOUT",
                confluence_list=["EMA_CROSS", "MACRO_BULL"],
                atr_pct=0.015,
                slippage_pct=0.0005,
                custom_margin=100.0,
                custom_leverage=5
            )
            self.assertIsNotNone(res)
            self.assertEqual(res["symbol"], "BTC/USDT")
            self.assertEqual(res["side"], "LONG")
            self.assertEqual(res["entry_price"], 60000.0)
            self.assertEqual(res["hard_stop"], 58500.0)
            self.assertEqual(res["sl_order_id"], "sl_201")
            self.assertEqual(res["tp_order_id"], "tp_301")
            self.assertIn("BTC/USDT", self.trader.open_positions)
        asyncio.run(_run())

    def test_02_close_position_kwargs_and_partial_tp1(self):
        """EXEC-001: close_position slippage_pct kwargs kabul etmeli ve is_partial ile TP1 kâr alıp stop maliyete çekmeli"""
        async def _run():
            # Önce pozisyon aç
            await self.trader.open_position(
                symbol="BTC/USDT",
                side="LONG",
                entry_price=60000.0,
                hard_stop=58500.0,
                tp1=61500.0,
                custom_margin=100.0,
                custom_leverage=5
            )
            initial_amount = self.trader.open_positions["BTC/USDT"]["amount"]

            # TP1 Kısmi Kapatma (strategy.py:885 çağrısı)
            part_res = await self.trader.close_position(
                symbol="BTC/USDT",
                current_price=61500.0,
                reason="TP1_HIT",
                is_partial=True,
                slippage_pct=0.0006,
                close_reason="TP1 Partial %50"
            )
            self.assertIsNotNone(part_res)
            self.assertTrue(part_res.get("is_partial"))
            self.assertIn("BTC/USDT", self.trader.open_positions)
            # Kalan miktar yarıya inmeli
            remaining_amount = self.trader.open_positions["BTC/USDT"]["amount"]
            self.assertAlmostEqual(remaining_amount, initial_amount * 0.5, places=3)
            # Stop seviyesi başabaş (entry_price 60000.0) olmalı
            self.assertEqual(self.trader.open_positions["BTC/USDT"]["hard_stop"], 60000.0)
            self.assertEqual(self.trader.open_positions["BTC/USDT"]["sl_order_id"], "breakeven_sl_501")

            # Tam Kapatma (Final Kapanış)
            full_res = await self.trader.close_position(
                symbol="BTC/USDT",
                current_price=63000.0,
                reason="TP2_HIT",
                is_partial=False,
                slippage_pct=0.0004
            )
            self.assertIsNotNone(full_res)
            self.assertFalse(full_res.get("is_partial"))
            self.assertNotIn("BTC/USDT", self.trader.open_positions)
            # cancel_all_orders çağrıldı mı?
            self.trader.exchange.cancel_all_orders.assert_called_with("BTC/USDT:USDT")
        asyncio.run(_run())

    def test_03_circuit_breaker_percentage_normalization(self):
        """TRADE-001: %500 devre kesici çarpan hatası düzeltmesi doğrulama"""
        vault = SecurityVault()
        from datetime import datetime, timezone, timedelta
        today = datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d")

        # Senaryo A: 5.0 (kullanıcı %5 kastederek 5.0 girdi)
        # Bakiye 10.000$, İzin verilen maks kayıp %5 = -$500.00 olmalı.
        history_safe = [{"exit_time": f"{today} 08:00:00", "net_pnl": -300.0}]
        ok, msg = vault.check_daily_circuit_breaker(history_safe, balance=10000.0, max_loss_pct=5.0)
        self.assertTrue(ok, "300$ kayıp %5 eşiğinin altında olduğu için güvenli olmalı.")

        history_breach = [{"exit_time": f"{today} 08:00:00", "net_pnl": -600.0}]
        ok, msg = vault.check_daily_circuit_breaker(history_breach, balance=10000.0, max_loss_pct=5.0)
        self.assertFalse(ok, "600$ kayıp %5 limitini ($500) aştığı için devre kesici tetiklenmeli!")
        self.assertIn("GÜNLÜK DEVRE KESİCİ DEVREYE GİRDİ", msg)

        # Senaryo B: 0.05 (ondalık kesir olarak girildi)
        ok2, msg2 = vault.check_daily_circuit_breaker(history_breach, balance=10000.0, max_loss_pct=0.05)
        self.assertFalse(ok2, "0.05 ondalık değerinde de aynı şekilde devre kesici tetiklenmeli!")

    def test_04_sync_open_positions_orphan_cleanup(self):
        """ORPHAN-CLEAN: Pozisyon borsada kapandığında yetim kalan emirlerin iptal edilmesi"""
        async def _run():
            self.trader.open_positions = {
                "BTC/USDT": {
                    "id": "old_test_pos",
                    "symbol": "BTC/USDT",
                    "exchange_symbol": "BTC/USDT:USDT",
                    "side": "LONG",
                    "entry_price": 60000.0,
                    "position_value": 500.0,
                    "leverage": 5,
                    "amount": 0.008,
                    "hard_stop": 58500.0,
                    "tp1": 63000.0,
                    "sl_order_id": "sl_old_99",
                    "tp_order_id": "tp_old_99"
                }
            }
            # Binance'te hiç açık pozisyon kalmamış (SL veya TP tetiklenmiş)
            self.trader.exchange.fetch_positions = AsyncMock(return_value=[])

            await self.trader.sync_open_positions()

            # Pozisyon yerelden silinmeli ve history'ye eklenmeli
            self.assertNotIn("BTC/USDT", self.trader.open_positions)
            self.assertTrue(any(h["symbol"] == "BTC/USDT" for h in self.trader.history))
            # Borsadaki yetim SL/TP emirleri temizlenmeli
            self.trader.exchange.cancel_all_orders.assert_called_with("BTC/USDT:USDT")
        asyncio.run(_run())

if __name__ == "__main__":
    unittest.main()
