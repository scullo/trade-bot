# -*- coding: utf-8 -*-
"""
Aşama 5: İndikatörler, Hawkes Çığı ve Sinyal Çakışması Doğrulama Testi
======================================================================
Bu test paketi Denetim Raporu Aşama 5 kapsamında giderilen:
1. STRAT-001: SETUP 15 / SETUP 16 ID çakışması ve SETUP 17 (AVWAP MVAH Reclaim),
   SETUP 18 (R3 Support Flip) bağımsız kanonik isimlendirmesi.
2. STRAT-002: Hawkes Tasfiye Çığı Freni (η >= 0.50) eksik return hatasının düzeltilmesi.
3. IND-001: Naked POC ve VAH/VAL seviyelerinde %0.3 yapay clamp bozulmasının kaldırılması.
"""

import unittest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch

from indicators import get_tradingview_naked_lines
from shadow_engine import ShadowExecutionEngine
from strategy import StrategyEngine


class TestAsama5IndicatorsAndSetups(unittest.TestCase):

    def test_task5_1_setup_id_collision_resolution(self):
        """SETUP 15, 16, 17, 18 kurulumlarının bağımsız ve çakışmasız kanonik kodlara dönüştüğünü doğrular."""
        # 1. SETUP 15: Short Squeeze
        canon_15 = ShadowExecutionEngine.extract_canonical_setup("SETUP_15_SHORT_SQUEEZE_HUNT")
        self.assertEqual(canon_15, "SETUP_15_SHORT_SQUEEZE_HUNT")

        canon_15_alt = ShadowExecutionEngine.extract_canonical_setup("SHORT SQUEEZE AVI")
        self.assertEqual(canon_15_alt, "SETUP_15_SHORT_SQUEEZE_HUNT")

        # 2. SETUP 16: Long Cascade Dip
        canon_16 = ShadowExecutionEngine.extract_canonical_setup("SETUP_16_LONG_CASCADE_DIP_HUNT")
        self.assertEqual(canon_16, "SETUP_16_LONG_CASCADE_DIP_HUNT")

        canon_16_alt = ShadowExecutionEngine.extract_canonical_setup("LONG CASCADE DIP")
        self.assertEqual(canon_16_alt, "SETUP_16_LONG_CASCADE_DIP_HUNT")

        # 3. SETUP 17: AVWAP MVAH Reclaim
        canon_17 = ShadowExecutionEngine.extract_canonical_setup("SETUP_17_AVWAP_MVAH_RECLAIM")
        self.assertEqual(canon_17, "SETUP_17_AVWAP_MVAH_RECLAIM")

        canon_17_alias = ShadowExecutionEngine.extract_canonical_setup("AVWAP_MVAH_RECLAIM")
        self.assertEqual(canon_17_alias, "SETUP_17_AVWAP_MVAH_RECLAIM")

        # 4. SETUP 18: R3 Support Flip
        canon_18 = ShadowExecutionEngine.extract_canonical_setup("SETUP_18_R3_SUPPORT_FLIP")
        self.assertEqual(canon_18, "SETUP_18_R3_SUPPORT_FLIP")

        canon_18_alias = ShadowExecutionEngine.extract_canonical_setup("R3_SUPPORT_FLIP")
        self.assertEqual(canon_18_alias, "SETUP_18_R3_SUPPORT_FLIP")

        # 5. Tüm bu kurulumlar get_setup_direction ile doğru yönleri döndürmeli
        self.assertEqual(ShadowExecutionEngine.get_setup_direction("SETUP_15_SHORT_SQUEEZE_HUNT"), "LONG")
        self.assertEqual(ShadowExecutionEngine.get_setup_direction("SETUP_16_LONG_CASCADE_DIP_HUNT"), "LONG")
        self.assertEqual(ShadowExecutionEngine.get_setup_direction("SETUP_17_AVWAP_MVAH_RECLAIM"), "LONG")
        self.assertEqual(ShadowExecutionEngine.get_setup_direction("SETUP_18_R3_SUPPORT_FLIP"), "LONG")

    def test_task5_2_hawkes_avalanche_brake_blocks_trade(self):
        """Hawkes eta >= 0.50 olduğunda _handle_open'ın işlemi derhal bloke ettiğini doğrular."""
        import asyncio
        mock_market_data = MagicMock()
        mock_market_data.candles_5m = {}
        mock_market_data.orderbook_depth = {}
        mock_market_data.get_orderbook_depth.return_value = {"ratio": 1.5}
        mock_market_data.get_symbol_cvd.return_value = {"ratio_60s": 50.0, "delta_60s": 0.0}
        
        # hawkes_eta = 0.65 (Tasfiye çığı aktif)
        mock_market_data.get_symbol_metrics.return_value = {
            "hawkes_eta": 0.65,
            "dynamic_rs_score": 0.0
        }

        mock_paper_trader = MagicMock()
        mock_paper_trader.open_positions = {}
        mock_paper_trader.balance = 10000.0
        engine = StrategyEngine(paper_trader=mock_paper_trader, notifier=MagicMock(), market_data=mock_market_data)
        engine.macro_oracle = None

        levels = {
            "r3": 65000.0, "s3": 63000.0, "pivot": 64000.0,
            "above_npoc": 65500.0, "below_npoc": 62500.0
        }

        # _handle_open çağrısı
        res = asyncio.run(engine._handle_open(
            symbol="BTCUSDT",
            side="LONG",
            entry_price=64000.0,
            reason="Test Signal",
            soft_stop=63000.0,
            hard_stop=62500.0,
            tp1=65000.0,
            tp2=66000.0,
            trade_type="BOUNCE",
            snapshot_levels=levels,
            setup_id="SETUP_17_AVWAP_MVAH_RECLAIM"
        ))

        # Hawkes freni tetiklenmeli ve HAWKES_AVALANCHE_BRAKE_BLOCKED dönmeli
        self.assertIsInstance(res, dict)
        self.assertEqual(res.get("error"), "HAWKES_AVALANCHE_BRAKE_BLOCKED")
        self.assertIn("Tasfiye Çığı Freni", res.get("message", ""))

    def test_task5_2_hawkes_calm_market_passes_brake(self):
        """Hawkes eta < 0.50 olduğunda Hawkes freninin engellemediğini doğrular."""
        import asyncio
        mock_market_data = MagicMock()
        mock_market_data.candles_5m = {}
        mock_market_data.orderbook_depth = {}
        mock_market_data.get_orderbook_depth.return_value = {"ratio": 1.5}
        mock_market_data.get_symbol_cvd.return_value = {"ratio_60s": 50.0, "delta_60s": 0.0}
        
        # hawkes_eta = 0.20 (Sakin mikroyapı)
        mock_market_data.get_symbol_metrics.return_value = {
            "hawkes_eta": 0.20,
            "dynamic_rs_score": 0.0
        }

        mock_paper_trader = MagicMock()
        mock_paper_trader.open_positions = {}
        mock_paper_trader.balance = 10000.0
        engine = StrategyEngine(paper_trader=mock_paper_trader, notifier=MagicMock(), market_data=mock_market_data)
        engine.macro_oracle = None

        levels = {
            "r3": 65000.0, "s3": 63000.0, "pivot": 64000.0,
            "above_npoc": 65500.0, "below_npoc": 62500.0
        }

        res = asyncio.run(engine._handle_open(
            symbol="BTCUSDT",
            side="LONG",
            entry_price=64000.0,
            reason="Test Signal",
            soft_stop=63000.0,
            hard_stop=62500.0,
            tp1=65000.0,
            tp2=66000.0,
            trade_type="BOUNCE",
            snapshot_levels=levels,
            setup_id="SETUP_17_AVWAP_MVAH_RECLAIM"
        ))

        # Hawkes freni hatası dönmemeli
        if isinstance(res, dict):
            self.assertNotEqual(res.get("error"), "HAWKES_AVALANCHE_BRAKE_BLOCKED")

    def test_task5_3_volume_profile_npoc_genuine_levels(self):
        """Volume Profile nPOC ve NVAH/NVAL hesaplamasında yapay %0.3 clamp olmadığını doğrular."""
        # Sentetik 5m dataframe oluştur (fiyat 100 etrafında)
        n = 50
        dates = pd.date_range("2026-01-01", periods=n, freq="5min")
        
        # Fiyat aralığı 98 ile 102 arasında
        prices = np.linspace(98.0, 102.0, n)
        volumes = np.ones(n) * 100.0
        
        # 100.10 seviyesine yüksek hacim kümesi yerleştir (Sadece %0.1 yukarıda)
        # Eski %0.3 clamp kodu bunu 100.30'a zorluyordu!
        prices[25] = 100.10
        volumes[25] = 50000.0

        # 99.90 seviyesine yüksek hacim kümesi yerleştir (Sadece %0.1 aşağıda)
        # Eski %0.3 clamp kodu bunu 99.70'e zorluyordu!
        prices[24] = 99.90
        volumes[24] = 45000.0

        df_5m = pd.DataFrame({
            "timestamp": dates,
            "open": prices,
            "high": prices + 0.05,
            "low": prices - 0.05,
            "close": prices,
            "volume": volumes
        })

        current_price = 100.00
        res = get_tradingview_naked_lines(df_5m, current_price=current_price)

        above_npoc = res["above_npoc"]
        below_npoc = res["below_npoc"]

        # Yön kuralı korunmalı
        self.assertGreater(above_npoc, current_price)
        self.assertLess(below_npoc, current_price)

        # Yapay %0.3 bozulma olmamalı:
        # Eğer %0.3 clamp devam etseydi above_npoc en az 100.30, below_npoc en fazla 99.70 olurdu.
        # Gerçek hacim kümesi 100.10 ve 99.90 olduğu için seviyeler bu civarda olmalıdır.
        self.assertLess(above_npoc, 100.25, f"above_npoc ({above_npoc}) yapay %0.3 clamp ile şişirilmiş!")
        self.assertGreater(below_npoc, 99.75, f"below_npoc ({below_npoc}) yapay %0.3 clamp ile bastırılmış!")


if __name__ == "__main__":
    unittest.main()
