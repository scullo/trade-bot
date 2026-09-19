# test_capital_management.py - 10.000$ Kasa Dinamik Sermaye ve Pozisyon Yönetimi Testleri
import unittest
import asyncio
from unittest.mock import MagicMock
import config
from paper_trader import PaperTrader
from strategy import StrategyEngine

class TestCapitalManagement(unittest.TestCase):
    def setUp(self):
        self.paper_trader = PaperTrader(initial_balance=10000.0, leverage=5, margin_per_trade=300.0)
        self.paper_trader.save_history = MagicMock()
        self.paper_trader.save_local_history = MagicMock()
        self.paper_trader._push_to_github = MagicMock()
        self.notifier = MagicMock()
        async def fake_notify(*args, **kwargs):
            return True
        self.notifier.notify_trade_close = fake_notify
        self.notifier.notify_trade_open = fake_notify
        self.market_data = MagicMock()
        self.strategy = StrategyEngine(self.paper_trader, self.notifier, self.market_data)
        self.strategy._notify_close = fake_notify
        self.strategy._notify_open = fake_notify

    def test_01_config_parameters(self):
        """10k Kasa için hedge-fund parametrelerinin doğruluğu"""
        self.assertEqual(config.INITIAL_BALANCE, 10000.0)
        self.assertEqual(config.POSITION_SIZE_USDT, 300.0)
        self.assertEqual(config.MAX_PORTFOLIO_MARGIN_PCT, 25.0)
        self.assertEqual(config.RISK_EQUITY_PCT, 0.80)
        self.assertEqual(config.MIN_POSITION_MARGIN, 150.0)
        self.assertEqual(config.MAX_POSITION_MARGIN, 500.0)
        self.assertEqual(config.MIN_TP1_GAIN_PCT, 0.90)

    def test_02_dynamic_slot_recycling(self):
        """Akıllı Slot Geri Kazanımı: TP1 almış ve stopu kilitli pozisyonlar 0.5 slot sayılır"""
        open_positions = {
            "BTC/USDT": {"is_half_closed": False, "margin": 300.0},
            "ETH/USDT": {"is_half_closed": False, "margin": 300.0},
            "SOL/USDT": {"is_half_closed": True, "_trail_be": True, "margin": 150.0},
            "XRP/USDT": {"is_half_closed": True, "tp1_hit": True, "margin": 150.0},
        }
        eff_slots = self.strategy.get_effective_slot_count(open_positions)
        # 1 + 1 + 0.5 + 0.5 = 3.0 efektif slot
        self.assertEqual(eff_slots, 3.0)

        # 4 aktif tam pozisyon + 4 yarı risksiz pozisyon = 4 + 2 = 6.0 slot (< 8 ELITE_SLOT_MAX)
        for i in range(4):
            open_positions[f"COIN_{i}/USDT"] = {"is_half_closed": True, "_trail_be": True, "margin": 150.0}
        self.assertEqual(self.strategy.get_effective_slot_count(open_positions), 5.0)

    def test_03_compounding_and_margin_sizing(self):
        """Kasa büyüdükçe risk ve marjinin büyümesi (Compounding)"""
        # 10k Kasada Hedef Risk
        cur_vault = 10000.0
        self.paper_trader.balance = cur_vault
        target_risk_usd_10k = max(float(config.FIXED_DOLLAR_RISK), cur_vault * (config.RISK_EQUITY_PCT / 100.0))
        self.assertAlmostEqual(target_risk_usd_10k, 80.0)

        # 15k Kasada Compounding
        cur_vault_15k = 15000.0
        self.paper_trader.balance = cur_vault_15k
        target_risk_usd_15k = max(float(config.FIXED_DOLLAR_RISK), cur_vault_15k * (config.RISK_EQUITY_PCT / 100.0))
        self.assertAlmostEqual(target_risk_usd_15k, 120.0)

        # 8k Kasada Drawdown Yumuşatma
        cur_vault_8k = 8000.0
        self.paper_trader.balance = cur_vault_8k
        target_risk_usd_8k = max(float(config.FIXED_DOLLAR_RISK), cur_vault_8k * (config.RISK_EQUITY_PCT / 100.0))
        self.assertAlmostEqual(target_risk_usd_8k, 80.0) # FIXED_DOLLAR_RISK tabanı korur

    def test_04_fallback_margin_in_paper_trader(self):
        """Paper trader fallback marjin hesabının 150$-500$ aralığında kalması"""
        self.paper_trader.balance = 10000.0
        # %1 stop mesafesi -> $80 / 0.01 = $8000 pozisyon -> $8000 / 5 = $1600 marjin -> max_cap $500 ile sınırlandırılır
        pos = self.paper_trader.open_position(
            symbol="BTC/USDT", side="LONG", entry_price=60000.0,
            reason="Test", soft_stop=59400.0, hard_stop=59400.0, tp1=61200.0
        )
        self.assertIsNotNone(pos)
        self.assertGreaterEqual(pos["margin"], 150.0)
        self.assertLessEqual(pos["margin"], 500.0)
        self.assertEqual(pos["margin"], 500.0)

    def test_05_anti_inversion_pivot_p(self):
        """_refresh_position_levels: Pivot P giriş fiyatının altındaysa pos['tp1'] asla bozulmaz"""
        pos = {
            "id": "TRD-TEST",
            "side": "LONG",
            "entry_price": 100.0,
            "tp1": 103.0,
            "reason": "İlk Hedef Pivot P",
            "confluence_list": ["Target_Pivot P"]
        }
        levels = {"camarilla": {"P": 98.0}} # P girişin altında!

        async def run_test():
            closed = await self.strategy._refresh_position_levels("TEST/USDT", pos, 100.5, levels)
            self.assertFalse(closed)
            # pos['tp1'] 98.0'e indirilmemeli, 103.0 olarak kalmalı!
            self.assertEqual(pos["tp1"], 103.0)

        asyncio.run(run_test())

    def test_06_tp1_fee_armor_min_gain(self):
        """evaluate_tick: Komisyon kalkanı - Asgari %0.90 fiyat kârı olmadan TP1 tetiklenemez"""
        pos = {
            "id": "TRD-TEST",
            "symbol": "ETH/USDT",
            "side": "LONG",
            "entry_price": 3000.0,
            "margin": 300.0,
            "leverage": 5,
            "position_value": 1500.0,
            "quantity": 0.5,
            "entry_fee": 0.75,
            "entry_time": "2026-09-19 12:00:00",
            "entry_timestamp": 0,
            "soft_stop": 2970.0,
            "hard_stop": 2970.0,
            "tp1": 3003.0, # Hatalı/çok yakın TP1 hedefi (+%0.10)
            "tp2": 3100.0,
            "is_half_closed": False
        }
        self.paper_trader.open_positions["ETH/USDT"] = pos

        async def run_test():
            # 3003.0 seviyesinde TP1 tetiklenmemeli çünkü kâr sadece %0.10 (< %0.90)
            await self.strategy.evaluate_tick("ETH/USDT", 3003.0, {})
            self.assertFalse(pos.get("is_half_closed", False))

            # 3030.0 seviyesinde (+%1.0 kâr) TP1 başarıyla tetiklenmeli!
            await self.strategy.evaluate_tick("ETH/USDT", 3030.0, {})
            self.assertTrue(pos.get("is_half_closed", False))
            self.assertIn("TRD-TEST-TP1", [h["id"] for h in self.paper_trader.history])
            tp1_rec = self.paper_trader.history[-1]
            # Net PnL komisyon sonrası kesinlikle pozitif olmalı!
            self.assertGreater(tp1_rec["net_pnl"], 5.0)

        asyncio.run(run_test())

if __name__ == '__main__':
    unittest.main()
