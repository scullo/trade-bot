import unittest
import sys
import os

# Set path so we can import local modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from quant_geometry import (
    calculate_geometric_r,
    check_runway_clearance,
    validate_pre_trade_clearance
)

class TestQuantGeometry(unittest.TestCase):

    def test_calculate_geometric_r(self):
        # Long: Entry 100, Stop 99 (Risk 1), TP1 102 (Reward 2) -> R = 2.0x
        r = calculate_geometric_r(100.0, 99.0, 102.0)
        self.assertAlmostEqual(r, 2.0, places=2)

        # Short: Entry 100, Stop 101 (Risk 1), TP1 98 (Reward 2) -> R = 2.0x
        r_short = calculate_geometric_r(100.0, 101.0, 98.0)
        self.assertAlmostEqual(r_short, 2.0, places=2)

        # Sıkışık geometri: Entry 100, Stop 99 (Risk 1), TP1 101.2 (Reward 1.2) -> R = 1.2x
        r_low = calculate_geometric_r(100.0, 99.0, 101.2)
        self.assertAlmostEqual(r_low, 1.2, places=2)

        # Hatalı/sıfır veriler
        self.assertEqual(calculate_geometric_r(0, 99.0, 102.0), 0.0)
        self.assertEqual(calculate_geometric_r(100.0, 100.0, 102.0), 0.0)

    def test_check_runway_clearance(self):
        # Long: Entry 100, Stop 99 (Risk 1), Target 103 (3R)
        # Seviye 101.0'da (Direnç) -> 1.0R mesafede, min_obstacle_r=1.40 iken engellenmeli
        levels_blocked = {'mvah': 101.0, 'r3': 105.0}
        clear, msg, obs, lvl = check_runway_clearance(100.0, 99.0, 103.0, levels_blocked, side="LONG", min_obstacle_r=1.40)
        self.assertFalse(clear)
        self.assertEqual(obs, 'mVAH')

        # Seviye 102.5'te (2.5R mesafede) -> min_obstacle_r=1.40'tan uzak, serbest olmalı
        levels_free = {'mvah': 102.5}
        clear, msg, obs, lvl = check_runway_clearance(100.0, 99.0, 103.0, levels_free, side="LONG", min_obstacle_r=1.40)
        self.assertTrue(clear)

        # Hedefin ötesindeki seviye (104.0) hedefi engellemez
        levels_beyond = {'r4': 104.0}
        clear, msg, obs, lvl = check_runway_clearance(100.0, 99.0, 103.0, levels_beyond, side="LONG", min_obstacle_r=1.40)
        self.assertTrue(clear)

    def test_validate_pre_trade_clearance(self):
        # 1. Elit 2R Long: Onaylanmalı
        ok, reason, metrics = validate_pre_trade_clearance(
            symbol="ETH/USDT",
            side="LONG",
            entry_p=2500.0,
            stop_p=2480.0,  # Risk 20
            tp1_p=2545.0,   # Reward 45 -> R = 2.25x
            market_regime="🟡 ILIMLI BOĞA (Moderate Bull)",
            cvd_taker_pct=55.0
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "OK")
        self.assertGreaterEqual(metrics["planned_r"], 1.80)

        # 2. Düşük R (1.2x): Reddedilmeli
        ok, reason, metrics = validate_pre_trade_clearance(
            symbol="BTC/USDT",
            side="LONG",
            entry_p=65000.0,
            stop_p=64500.0,  # Risk 500
            tp1_p=65600.0,   # Reward 600 -> R = 1.2x
            market_regime="🟡 ILIMLI BOĞA (Moderate Bull)"
        )
        self.assertFalse(ok)
        self.assertIn("Geometrik R Kalkanı", reason)

        # 3. Boğa Rejiminde Alıcı Akışı Varken Açılan Short: Reddedilmeli
        ok, reason, metrics = validate_pre_trade_clearance(
            symbol="SOL/USDT",
            side="SHORT",
            entry_p=140.0,
            stop_p=141.0,  # Risk 1
            tp1_p=137.5,   # Reward 2.5 -> R = 2.5x
            market_regime="🟢 GÜÇLÜ BOĞA (Bullish)",
            cvd_taker_pct=60.0  # Alıcı baskısı %60!
        )
        self.assertFalse(ok)
        self.assertIn("Boğa Rejimi Akıntı Kalkanı", reason)

        # 4. Boğa Rejiminde Güçlü Satıcı Akışı (%35 Alıcı, %65 Satıcı) ile Açılan Short: Onaylanmalı
        ok, reason, metrics = validate_pre_trade_clearance(
            symbol="SOL/USDT",
            side="SHORT",
            entry_p=140.0,
            stop_p=141.0,  # Risk 1
            tp1_p=137.5,   # Reward 2.5 -> R = 2.5x
            market_regime="🟢 GÜÇLÜ BOĞA (Bullish)",
            cvd_taker_pct=35.0  # Satıcı baskısı %65!
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "OK")


if __name__ == '__main__':
    unittest.main()
