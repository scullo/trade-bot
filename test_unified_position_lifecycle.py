"""
VALKYRIE KUANT SISTEM TESTI: Birleşik Yaşam Döngüsü (Unified Position Lifecycle - Model 1)
Amaç: Parçalı kapanan pozisyonların (TP1 + Runner) adli deftere tek bir birleşik işlem olarak,
doğru kâr/zarar, ağırlıklı ortalama çıkış ve %100 adil Win Rate ile yazılmasını doğrular.
"""

import unittest
import os
import json
import time
import pandas as pd
import numpy as np

from paper_trader import PaperTrader
from forensic_blackbox_manager import forensic_blackbox_manager
from chart_engine_v2 import forensic_chart_engine_v2


class TestUnifiedPositionLifecycle(unittest.TestCase):

    def setUp(self):
        # İzole test paper trader başlat
        self.trader = PaperTrader(initial_balance=10000.0)
        self.trader.history = []
        self.trader.open_positions = {}

    def test_single_leg_normal_close(self):
        """Tek parça açılıp tek parça kapanan standart işlem testi."""
        pos = self.trader.open_position(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=60000.0,
            reason="Breakout Retest",
            soft_stop=59600.0,
            hard_stop=59600.0,
            tp1=60500.0,
            custom_margin=500.0,
            custom_leverage=3,
            bypass_stop_gate=True
        )
        self.assertIsNotNone(pos)
        self.assertNotIn("error", pos)
        self.assertEqual(pos["initial_margin"], 500.0)
        self.assertEqual(len(self.trader.history), 0)

        # Doğrudan tam kapanış
        rec = self.trader.close_position(
            symbol="BTC/USDT",
            exit_price=60400.0,
            close_reason="TP1 Hedefine Ulaşıldı",
            is_partial=False
        )
        self.assertIsNotNone(rec)
        self.assertEqual(len(self.trader.history), 1)
        self.assertFalse(rec.get("has_sub_legs", False))
        self.assertEqual(len(rec.get("sub_legs", [])), 0)
        self.assertEqual(rec["margin"], 500.0)
        self.assertGreater(rec["net_pnl"], 0)
        self.assertGreater(rec["roe_pct"], 0)

    def test_unified_lifecycle_tp1_then_runner_breakeven(self):
        """
        APT/USDT vakası: %50 TP1 kârla alındı, kalan %50 Breakeven stop ile kapatıldı.
        Beklenen:
        1. TP1 anında history'ye ayrı kayıt ATILMAZ (len == 0).
        2. İkinci bacak kapandığında history'de TEK BİRLEŞİK İŞLEM (len == 1) yer alır.
        3. Birleşik işlem KAZANAN (WIN) olarak mühürlenir.
        4. Net kâr iki bacağın toplamıdır (+18.67 + -11.96 = +6.71$).
        """
        initial_balance = self.trader.balance

        # 1. Pozisyon Aç
        pos = self.trader.open_position(
            symbol="APT/USDT",
            side="LONG",
            entry_price=0.8143,
            reason="Kurulum 14: Pivot Flip",
            soft_stop=0.8100,
            hard_stop=0.8100,
            tp1=0.8291,
            custom_margin=500.0,
            custom_leverage=3,
            bypass_stop_gate=True
        )
        self.assertIsNotNone(pos)
        self.assertNotIn("error", pos)
        self.assertEqual(pos["initial_margin"], 500.0)
        self.assertEqual(len(self.trader.history), 0)

        # 2. %50 TP1 Kâr Satışı
        partial_res = self.trader.close_position(
            symbol="APT/USDT",
            exit_price=0.8291,
            close_reason="🎯 TP1 Alındı (%50 Kapatıldı)",
            is_partial=True
        )
        self.assertIsNotNone(partial_res)
        self.assertTrue(partial_res.get("is_partial"))
        self.assertGreater(partial_res.get("net_pnl"), 0)

        # KRİTİK DOĞRULAMA 1: TP1 anında deftere henüz bağımsız işlem eklenmemelidir!
        self.assertEqual(len(self.trader.history), 0, "TP1 anında history'ye bağımsız işlem yazılmamalıdır!")

        # Açık pozisyon durumu
        open_pos = self.trader.open_positions.get("APT/USDT")
        self.assertIsNotNone(open_pos)
        self.assertTrue(open_pos.get("is_half_closed"))
        self.assertTrue(open_pos.get("tp1_hit"))
        self.assertEqual(len(open_pos.get("legs", [])), 1)
        self.assertEqual(open_pos["legs"][0]["type"], "TP1_PARTIAL")

        # 3. Kalan %50 Runner Parçasının Kapanışı (Hafif kayma/komisyon ile Breakeven)
        final_res = self.trader.close_position(
            symbol="APT/USDT",
            exit_price=0.8156,
            close_reason="🛡️ Breakeven Koruması Tetiklendi",
            is_partial=False
        )
        self.assertIsNotNone(final_res)

        # KRİTİK DOĞRULAMA 2: Defterde 2 ayrı kayıt değil, TEK BİRLEŞİK İŞLEM olmalıdır!
        self.assertEqual(len(self.trader.history), 1, "Defterde yalnızca 1 adet birleşik kayıt bulunmalıdır!")
        rec = self.trader.history[0]

        # Alt bacak kontrolleri
        self.assertTrue(rec.get("has_sub_legs"))
        self.assertEqual(len(rec.get("sub_legs")), 2)
        leg1 = rec["sub_legs"][0]
        leg2 = rec["sub_legs"][1]
        self.assertEqual(leg1["type"], "TP1_PARTIAL")
        self.assertEqual(leg2["type"], "RUNNER_FINAL")

        # Matematiksel toplam kontrolleri
        expected_total_pnl = round(leg1["net_pnl"] + leg2["net_pnl"], 4)
        self.assertAlmostEqual(rec["net_pnl"], expected_total_pnl, places=3)
        self.assertGreater(rec["net_pnl"], 0.0, "TP1 kârı runner kaybından büyük olduğundan toplam pozisyon KÂRDA olmalıdır!")
        self.assertGreater(rec["roe_pct"], 0.0, "Birleşik ROE pozitif olmalıdır!")
        self.assertEqual(rec["margin"], 500.0, "Toplam işlem sermayesi 500$ olarak korunmalıdır!")

        # Ağırlıklı ortalama çıkış fiyatı
        self.assertGreater(rec["exit_price"], 0.8143, "Ağırlıklı ortalama çıkış girişin üzerinde olmalıdır!")

        # Kasa bakiyesi tutarlılığı
        self.assertAlmostEqual(self.trader.balance, initial_balance + rec["net_pnl"], places=2)

    def test_forensic_outcome_tagging(self):
        """Adli karar motorunun birleşik kârlı işlemi WIN olarak etiketlemesi testi."""
        mock_unified_record = {
            "symbol": "APT/USDT",
            "side": "LONG",
            "entry_price": 0.8143,
            "exit_price": 0.8224,
            "net_pnl": 6.71,
            "roe_pct": 2.68,
            "close_reason": "🎯 TP1: +18.67$ + Breakeven Koruması: -11.96$",
            "has_sub_legs": True,
            "sub_legs": [
                {"leg_index": 1, "type": "TP1_PARTIAL", "net_pnl": 18.67, "roe_pct": 7.47, "exit_price": 0.8291},
                {"leg_index": 2, "type": "RUNNER_FINAL", "net_pnl": -11.96, "roe_pct": -2.11, "exit_price": 0.8156}
            ]
        }

        # Tetikleme kontrolü
        should_trig = forensic_blackbox_manager.should_trigger_snapshot(mock_unified_record, is_shadow=False)
        self.assertTrue(should_trig)

        # Adli otopsi sonucunda WIN etiketini doğrula
        snap = forensic_blackbox_manager.process_closed_trade_sync(
            trade_record=mock_unified_record,
            df_5m=None,
            levels={},
            is_shadow=False
        )
        self.assertIsNotNone(snap)
        self.assertEqual(snap["outcome"], "WIN", "İkinci bacakta Breakeven geçse dahi toplam kâr pozitif olduğu için WIN olmalıdır!")

    def test_composite_chart_with_sub_legs(self):
        """2 Bacaklı birleşik işlem için 1600x900 adli grafik üretim testi."""
        # Sahte 5M mum verisi üret
        dates = pd.date_range(end=pd.Timestamp.now(), periods=100, freq='5min')
        df_5m = pd.DataFrame({
            'timestamp': [int(d.timestamp() * 1000) for d in dates],
            'open': np.linspace(0.8100, 0.8250, 100),
            'high': np.linspace(0.8120, 0.8300, 100),
            'low': np.linspace(0.8080, 0.8200, 100),
            'close': np.linspace(0.8110, 0.8220, 100),
            'volume': np.random.uniform(5000, 20000, 100)
        })

        record = {
            "id": "TRD-TEST-UNIFIED",
            "symbol": "APT/USDT",
            "side": "LONG",
            "entry_price": 0.8143,
            "exit_price": 0.8224,
            "entry_time": dates[20].strftime("%Y-%m-%d %H:%M:%S"),
            "exit_time": dates[80].strftime("%Y-%m-%d %H:%M:%S"),
            "net_pnl": 6.71,
            "roe_pct": 2.68,
            "close_reason": "🎯 TP1: +18.67$ + Breakeven: -11.96$",
            "has_sub_legs": True,
            "sub_legs": [
                {
                    "leg_index": 1, "type": "TP1_PARTIAL",
                    "exit_price": 0.8291, "exit_time": dates[50].strftime("%Y-%m-%d %H:%M:%S"),
                    "net_pnl": 18.67, "roe_pct": 7.47
                },
                {
                    "leg_index": 2, "type": "RUNNER_FINAL",
                    "exit_price": 0.8156, "exit_time": dates[80].strftime("%Y-%m-%d %H:%M:%S"),
                    "net_pnl": -11.96, "roe_pct": -2.11
                }
            ]
        }

        buf = forensic_chart_engine_v2.generate_composite_snapshot(
            trade_record=record,
            df_5m=df_5m,
            levels={"camarilla": {"P": 0.8180, "R4": 0.8300, "S4": 0.8050}}
        )
        self.assertIsNotNone(buf)
        self.assertGreater(len(buf.getvalue()), 10000)


if __name__ == "__main__":
    unittest.main()
