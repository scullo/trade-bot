import unittest
import time
from shadow_engine import ShadowExecutionEngine

class TestShadowExecutionEngine(unittest.TestCase):
    def setUp(self):
        # Geçici hafıza test motoru
        self.engine = ShadowExecutionEngine(history_file="test_shadow_history.json", max_active=10, max_history=50)

    def tearDown(self):
        import os
        if os.path.exists("test_shadow_history.json"):
            try:
                os.remove("test_shadow_history.json")
            except Exception:
                pass

    def test_spawn_shadow_and_hero_verdict(self):
        # 1. Shadow pozisyon başlat (Örn: DOGE S3 sekmesi CVD kalkanına takıldı)
        pos = self.engine.spawn_shadow_trade(
            symbol="DOGE/USDT",
            setup_name="S3 Direnc Retest Sekmesi",
            reason="🛡️ Harmonik Akış Kalkanı: Taker piyasa alıcıların kontrolünde (Alıcı CVD: %60.9 > %52.0).",
            side="SHORT",
            entry_price=0.2500,
            sl_price=0.2540,
            tp1_price=0.2450,
            tp2_price=0.2400
        )
        self.assertIsNotNone(pos)
        self.assertEqual(pos["symbol"], "DOGE/USDT")
        self.assertEqual(pos["side"], "SHORT")
        self.assertEqual(pos["shield"], "Harmonik Akış Kalkanı (CVD Taker Flow)")
        self.assertEqual(len(self.engine.active_positions), 1)

        # 2. Fiyat yükseliyor ve SHORT stop oluyor (0.2545)
        candle = {"open": 0.2500, "high": 0.2545, "low": 0.2490, "close": 0.2542}
        closed = self.engine.update_candle("DOGE/USDT", candle)
        self.assertEqual(len(closed), 1)
        rec = closed[0]
        self.assertEqual(rec["status"], "STOPPED")
        self.assertEqual(rec["verdict"], "HERO_SHIELD")  # Zararı önledi!
        self.assertGreater(rec["impact_usd"], 0)
        self.assertEqual(len(self.engine.active_positions), 0)
        self.assertEqual(len(self.engine.completed_trades), 1)

    def test_spoiler_verdict(self):
        # 1. Shadow pozisyon başlat (Örn: ENA Fitil kalkanına takıldı ama kâr etti)
        pos = self.engine.spawn_shadow_trade(
            symbol="ENA/USDT",
            setup_name="SETUP 3 S3 Destek",
            reason="Fitil & Emilim Kalkanı: Alıcı fitili %14.3 < %15.0 yetersiz.",
            side="LONG",
            entry_price=0.5000,
            sl_price=0.4900,
            tp1_price=0.5100,
            tp2_price=0.5250
        )
        self.assertIsNotNone(pos)

        # 2. Fiyat TP2'ye uçtu (0.5260)
        candle = {"open": 0.5000, "high": 0.5260, "low": 0.4980, "close": 0.5240}
        closed = self.engine.update_candle("ENA/USDT", candle)
        self.assertEqual(len(closed), 1)
        rec = closed[0]
        self.assertEqual(rec["status"], "TP2_HIT")
        self.assertEqual(rec["verdict"], "SPOILER_SHIELD")  # Kârı kaçırdı!
        self.assertGreater(rec["virtual_pnl_usd"], 0)

    def test_summary_and_coin_dna(self):
        # 1 Hero ve 1 Spoiler ile summary testi
        self.test_spawn_shadow_and_hero_verdict()
        # Fake bir ENA spoiler ekle
        self.engine.spawn_shadow_trade("ENA/USDT", "S3", "Fitil", side="LONG", entry_price=1.0, sl_price=0.9, tp1_price=1.05, tp2_price=1.1)
        self.engine.update_candle("ENA/USDT", {"open": 1.0, "high": 1.15, "low": 0.99, "close": 1.12})

        summary = self.engine.get_summary()
        self.assertEqual(summary["hero_count"], 1)
        self.assertEqual(summary["spoiler_count"], 1)
        self.assertGreater(summary["total_saved_loss_usd"], 0)
        self.assertGreater(summary["total_missed_profit_usd"], 0)

        dna = self.engine.get_coin_dna_matrix()
        self.assertEqual(len(dna), 100)
        symbols = [d["symbol"] for d in dna]
        self.assertIn("DOGE", symbols)
        self.assertIn("ENA", symbols)

if __name__ == "__main__":
    unittest.main()
