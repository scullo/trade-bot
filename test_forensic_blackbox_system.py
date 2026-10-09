"""
VALKYRIE GÖRSEL ADLİ KARA KUTU & MİKROSKOBİK MUM OTOPSİSİ (VFB)
Sistem Bütünlüğü ve Uçtan Uca Doğrulama Testi
"""

import os
import shutil
import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

from forensic_autopsy import forensic_autopsy_engine
from chart_engine_v2 import forensic_chart_engine_v2
from forensic_blackbox_manager import forensic_blackbox_manager


class TestForensicBlackboxSystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Sentetik 60 mumluk 5M DataFrame üret
        dates = pd.date_range('2026-10-09 10:00', periods=60, freq='5min')
        base_p = 65000.0
        closes = base_p + np.cumsum(np.random.randn(60) * 60)
        highs = closes + np.abs(np.random.randn(60) * 40)
        lows = closes - np.abs(np.random.randn(60) * 40)
        opens = (highs + lows) / 2.0
        volumes = np.random.rand(60) * 1500 + 300

        cls.df_5m = pd.DataFrame({
            'timestamp': [d.timestamp() * 1000 for d in dates],
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'volume': volumes
        })
        cls.dates = dates

    def test_01_forensic_autopsy_diagnoses(self):
        """Otopsi motorunun kural tabanlı teşhislerini doğrula."""
        # 1. Büyük Kazanç (Runner)
        rec_win = {
            "symbol": "BTC/USDT",
            "side": "LONG",
            "entry_price": 65000.0,
            "exit_price": 67000.0,
            "net_pnl": 150.0,
            "roe_pct": 15.3,
            "max_mfe_roe": 16.0,
            "max_mae_roe": -0.4,
            "candle_count": 25,
            "setup_id": "SETUP_CAMARILLA_BREAKOUT"
        }
        autopsy_win = forensic_autopsy_engine.perform_autopsy(rec_win, df_5m=self.df_5m)
        self.assertEqual(autopsy_win["diagnosis_code"], "PERFECT_EXECUTION_RUNNER")
        self.assertIn("Alpha Runner", autopsy_win["actionable_advice"])

        # 2. Hacimsiz Sahte Kırılım (Low Volume Fakeout)
        rec_fakeout = {
            "symbol": "SOL/USDT",
            "side": "LONG",
            "entry_price": 150.0,
            "exit_price": 147.0,
            "net_pnl": -35.0,
            "roe_pct": -3.5,
            "volume_surge": 0.85,
            "setup_id": "SETUP_CAMARILLA_BREAKOUT",
            "close_reason": "STOP_LOSS_TOUCH",
            "candle_count": 3
        }
        autopsy_fakeout = forensic_autopsy_engine.perform_autopsy(rec_fakeout, df_5m=self.df_5m)
        self.assertEqual(autopsy_fakeout["diagnosis_code"], "LOW_VOLUME_FAKEOUT")
        self.assertIn("Hacim", autopsy_fakeout["findings"][0])

        # 3. Standart Hedef Kâr (0.3% < ROE < 2.5%)
        rec_tp1 = {
            "symbol": "ETH/USDT",
            "side": "LONG",
            "entry_price": 2500.0,
            "exit_price": 2530.0,
            "net_pnl": 30.0,
            "roe_pct": 1.20,
            "candle_count": 8,
            "setup_id": "SETUP_CAMARILLA_BO"
        }
        autopsy_tp1 = forensic_autopsy_engine.perform_autopsy(rec_tp1, df_5m=self.df_5m)
        self.assertEqual(autopsy_tp1["diagnosis_code"], "PROFIT_TARGET_SECURED")
        self.assertGreater(len(autopsy_tp1["findings"]), 0)

        # 4. Gölge İşlem Anahtarları (virtual_pnl_usd & virtual_pnl_pct)
        rec_shadow = {
            "symbol": "DOGE/USDT",
            "side": "LONG",
            "entry_price": 0.10,
            "exit_price": 0.104,
            "virtual_pnl_usd": 12.50,
            "virtual_pnl_pct": 4.0,
            "max_mfe_pct": 4.2,
            "max_mae_pct": -0.2,
            "duration_mins": 45,
            "setup_id": "SETUP_MEME_SURGE"
        }
        autopsy_shadow = forensic_autopsy_engine.perform_autopsy(rec_shadow, df_5m=self.df_5m)
        self.assertEqual(autopsy_shadow["diagnosis_code"], "PERFECT_EXECUTION_RUNNER")
        self.assertGreater(len(autopsy_shadow["findings"]), 0)

    def test_02_chart_engine_v2_composite_generation(self):
        """1600x900 kompozit infografik üretimini test et."""
        rec = {
            "symbol": "BTC/USDT",
            "side": "LONG",
            "leverage": 5,
            "entry_price": float(self.df_5m['open'].iloc[15]),
            "exit_price": float(self.df_5m['close'].iloc[45]),
            "net_pnl": 85.40,
            "roe_pct": 8.54,
            "entry_time": self.dates[15].strftime('%Y-%m-%d %H:%M:%S'),
            "exit_time": self.dates[45].strftime('%Y-%m-%d %H:%M:%S'),
            "duration": "2sa 30dk",
            "candle_count": 30,
            "close_reason": "TP2_RUNNER_TARGET_HIT",
            "setup_id": "SETUP_CAMARILLA_BREAKOUT",
            "max_mfe_roe": 10.2,
            "max_mae_roe": -0.6
        }
        levels = {
            "camarilla": {"R5": 67000.0, "R4": 66200.0, "R3": 65500.0, "P": 65000.0, "S3": 64500.0, "S4": 63800.0},
            "mpoc": 65100.0,
            "mval": 64200.0,
            "mvah": 65800.0
        }
        autopsy = forensic_autopsy_engine.perform_autopsy(rec, df_5m=self.df_5m, levels=levels)
        buf = forensic_chart_engine_v2.generate_composite_snapshot(rec, df_5m=self.df_5m, levels=levels, autopsy_data=autopsy)

        self.assertIsNotNone(buf)
        img_bytes = buf.getvalue()
        self.assertGreater(len(img_bytes), 50000)  # > 50 KB
        self.assertEqual(img_bytes[:8], b'\x89PNG\r\n\x1a\n')  # PNG Magic header

    def test_03_blackbox_manager_lifecycle_and_pruning(self):
        """Adli yönetici kayıt, filtre, star, inceleme ve silme döngüsünü doğrula."""
        rec = {
            "id": "UNIT_TEST_ETH_001",
            "symbol": "ETH/USDT",
            "side": "SHORT",
            "leverage": 5,
            "entry_price": float(self.df_5m['open'].iloc[10]),
            "exit_price": float(self.df_5m['close'].iloc[35]),
            "net_pnl": -22.50,
            "roe_pct": -2.25,
            "entry_time": self.dates[10].strftime('%Y-%m-%d %H:%M:%S'),
            "exit_time": self.dates[35].strftime('%Y-%m-%d %H:%M:%S'),
            "duration": "2sa 05dk",
            "candle_count": 25,
            "close_reason": "STOP_LOSS_TOUCH",
            "setup_id": "SETUP_CAMARILLA_BREAKOUT"
        }

        # Senkron işleme
        snap = forensic_blackbox_manager.process_closed_trade_sync(rec, df_5m=self.df_5m, is_shadow=False)
        self.assertIsNotNone(snap)
        snap_id = snap["id"]

        # Kataloğu sorgula
        res = forensic_blackbox_manager.get_snapshots(filter_category="LOSS")
        found = any(s["id"] == snap_id for s in res["snapshots"])
        self.assertTrue(found)

        # Star toggle (Hall of Fame)
        new_star = forensic_blackbox_manager.toggle_star(snap_id)
        self.assertTrue(new_star)
        res_star = forensic_blackbox_manager.get_snapshots(filter_category="STARRED")
        self.assertTrue(any(s["id"] == snap_id for s in res_star["snapshots"]))

        # Mark reviewed (PNG silinir, JSON kalır)
        rev = forensic_blackbox_manager.mark_reviewed(snap_id)
        self.assertTrue(rev)

        # Kalıcı silme
        del_ok = forensic_blackbox_manager.delete_snapshot(snap_id)
        self.assertTrue(del_ok)
        res_after = forensic_blackbox_manager.get_snapshots()
        self.assertFalse(any(s["id"] == snap_id for s in res_after["snapshots"]))


if __name__ == '__main__':
    unittest.main()
