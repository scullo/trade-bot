import unittest
import pandas as pd
import numpy as np
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from advanced_quant_signals import (
    calculate_cvd_divergence,
    calculate_rvol_zscore,
    calculate_macro_dominance_bias
)

class TestAdvancedQuantSignals(unittest.TestCase):

    def test_calculate_cvd_divergence(self):
        # 1. Normal uyumlu akış
        df_normal = pd.DataFrame({
            'open': [100 + i for i in range(20)],
            'close': [101 + i for i in range(20)],
            'volume': [1000] * 20,
            'taker_quote': [600] * 20,
            'qav': [1000] * 20
        })
        div_type, score = calculate_cvd_divergence(df_normal, lookback=15)
        self.assertIn("UYUMLU", div_type)

        # 2. Ayı Uyumsuzluğu: Fiyat zirve yapıyor ama taker alım düşüyor
        prices = [100] * 7 + [105] * 8
        t_quote = [800] * 7 + [200] * 8  # CVD çöküyor
        df_bearish = pd.DataFrame({
            'open': prices,
            'close': prices,
            'volume': [1000] * 15,
            'taker_quote': t_quote,
            'qav': [1000] * 15
        })
        div_type, score = calculate_cvd_divergence(df_bearish, lookback=15)
        self.assertIn("AYI_UYUMSUZLUĞU", div_type)

        # 3. None veya boş veri
        self.assertEqual(calculate_cvd_divergence(None)[0], "NÖTR_VERİ_YOK")
        self.assertEqual(calculate_cvd_divergence(pd.DataFrame())[0], "NÖTR_VERİ_YOK")

    def test_calculate_rvol_zscore(self):
        # 100 mumluk standart hacim serisi
        vols = [100.0] * 99 + [500.0]  # Son mumda 5x patlama
        df = pd.DataFrame({
            'close': [100] * 100,
            'volume': vols
        })
        rvol, z, tag = calculate_rvol_zscore(df)
        self.assertGreater(rvol, 3.0)
        self.assertIn("PATLAMA", tag)

    def test_calculate_macro_dominance_bias(self):
        # BTC %2 yükseliyor, Altcoin %2 düşüyor (Vampir BTC)
        btc_df = pd.DataFrame({'close': [60000] * 11 + [61200]})
        alt_df = pd.DataFrame({'close': [100] * 11 + [98]})
        bias, rs_diff = calculate_macro_dominance_bias(btc_df, alt_df)
        self.assertIn("VAMPİR_BTC", bias)
        self.assertLess(rs_diff, -1.0)


if __name__ == '__main__':
    unittest.main()
