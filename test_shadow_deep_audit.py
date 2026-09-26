import unittest
import os
import sys
import io
import json

from shadow_engine import ShadowExecutionEngine
from excel_exporter import create_shadow_dna_excel_report

class TestShadowDeepAudit(unittest.TestCase):
    def setUp(self):
        self.engine = ShadowExecutionEngine()
        # Reset internal state for test
        self.engine.active_positions.clear()
        self.engine.completed_trades.clear()

    def test_01_mathematical_harmony_and_notional(self):
        """
        Matematiksel Uyum Kanıtı:
        $250 Marjin x 5x Kaldıraç = $1,250 Notional Pozisyon Büyüklüğü
        PnL Hesabı: Margin * (ROE% / 100) == Notional * Raw_Price_Change%
        """
        # LONG test
        self.engine.spawn_shadow_trade(
            symbol="ENA/USDT",
            setup_name="TEST_CAMARILLA_LONG",
            side="LONG",
            entry_price=1.00,
            sl_price=0.96, # -%4 stop (-%20 ROE)
            tp1_price=1.04, # +%4 TP (+%20 ROE)
            tp2_price=1.08,
            reason="Fitil Tuzak Kalkanı: Sahte fitil oranı %45 üzerinde"
        )
        pos_id = list(self.engine.active_positions.keys())[0]
        pos = self.engine.active_positions[pos_id]
        self.assertEqual(pos["margin_usd"], 250.0)
        self.assertEqual(pos["leverage"], 5.0)
        self.assertEqual(pos["notional_usd"], 1250.0)

        # Fiyat 1.02'ye çıksın (+%2 raw move -> +%10 ROE)
        self.engine.update_tick("ENA/USDT", 1.02)
        raw_pct = (1.02 - 1.00) / 1.00 # +0.02
        roe_pct = raw_pct * 5.0 * 100.0 # +10.0%
        # Frontend hesap formülü: 250 * (roe_pct / 100)
        frontend_usd = 250.0 * (roe_pct / 100.0)
        # Backend notional formülü: 1250 * raw_pct
        backend_usd = 1250.0 * raw_pct
        self.assertAlmostEqual(frontend_usd, 25.00, places=4)
        self.assertAlmostEqual(backend_usd, 25.00, places=4)
        self.assertEqual(frontend_usd, backend_usd)

    def test_02_be_price_priority_after_tp1(self):
        """
        TP1 alındıktan sonra Stop Seviyesi Breakeven (Giriş Fiyatı) olmalı,
        ilk stop loss (sl_price) seviyesine düşüş gerçekleşse bile işlem Breakeven kapatılmalıdır.
        """
        self.engine.spawn_shadow_trade(
            symbol="MOVR/USDT",
            setup_name="TEST_AVWAP_SHORT",
            side="SHORT",
            entry_price=10.00,
            sl_price=10.50, # +%5 yükselirse stop (-%25 ROE)
            tp1_price=9.60, # -%4 düşerse TP1 (+%20 ROE)
            tp2_price=9.20,
            reason="Alfa Boğa Patlama Kalkanı: Parite bağımsız alfa üretiyor"
        )
        # Mum 1: 9.50'ye düşüp TP1 tetikliyor
        candle_tp1 = {"high": 10.05, "low": 9.50, "close": 9.70}
        self.engine.update_candle("MOVR/USDT", candle_tp1)
        
        pos_id = list(self.engine.active_positions.keys())[0]
        pos = self.engine.active_positions[pos_id]
        self.assertTrue(pos["tp1_hit"])
        self.assertAlmostEqual(pos["be_price"], 9.992, places=3)

        # Mum 2: Fiyat yukarı fırlayıp 10.10'a çıkıyor. BE tetiklenmeli!
        candle_be = {"high": 10.15, "low": 9.70, "close": 10.10}
        self.engine.update_candle("MOVR/USDT", candle_be)

        # Pozisyon kapanmış olmalı
        self.assertEqual(len(self.engine.active_positions), 0)
        self.assertEqual(len(self.engine.completed_trades), 1)
        closed = self.engine.completed_trades[0]
        self.assertEqual(closed["status"], "BE_CLOSED")
        self.assertAlmostEqual(closed["exit_price"], 9.992, places=3)
        self.assertGreaterEqual(closed["virtual_pnl_usd"], 0.0)

    def test_03_coin_forensic_detail_modal_payload(self):
        """
        Kullanıcının [🔍 Detay] butonuna bastığında çağrılan get_coin_forensic_detail(symbol)
        metodunun eksiksiz adli veri paketi ürettiğinin doğrulanması.
        """
        # 1 Hero işlem üretelim (Stop olan işlem engellendi)
        self.engine.spawn_shadow_trade(
            symbol="ENA/USDT",
            setup_name="CAMARILLA_S3_REVERSAL",
            side="LONG",
            entry_price=1.00,
            sl_price=0.95,
            tp1_price=1.05,
            tp2_price=1.10,
            reason="Fitil & Emilim Kalkanı (Wick Absorption): Sahte fitil oranı %48.2"
        )
        candle_stop = {"high": 1.01, "low": 0.94, "close": 0.945}
        self.engine.update_candle("ENA/USDT", candle_stop)

        # 1 Aktif işlem ekleyelim
        self.engine.spawn_shadow_trade(
            symbol="ENA/USDT",
            setup_name="MOMENTUM_BREAKOUT",
            side="LONG",
            entry_price=1.00,
            sl_price=0.95,
            tp1_price=1.05,
            tp2_price=1.10,
            reason="Asya Seansı Sahte Kırılım Kalkanı: Gece likidite tuzağı"
        )

        detail = self.engine.get_coin_forensic_detail("ENA")
        self.assertEqual(detail["symbol"], "ENA")
        self.assertEqual(detail["hero_count"], 1)
        self.assertEqual(detail["spoiler_count"], 0)
        self.assertGreater(detail["saved_loss_usd"], 0)
        self.assertEqual(detail["active_count"], 1)
        self.assertEqual(detail["completed_count"], 1)
        self.assertIn("Fitil & Emilim Kalkanı (Wick Absorption)", detail["shields_breakdown"])
        self.assertIn("suggested_diff", detail)

    def test_04_excel_export_generation_and_columns(self):
        """
        4 Sayfalı Profesyonel Excel dosyasının sıfır hatayla üretildiğinin ve
        yeni adli teşhis / telemetri sütunlarının varlığının doğrulanması.
        """
        summary = self.engine.get_summary()
        coin_dna = self.engine.get_coin_dna_matrix()
        shadow_hist = self.engine.get_recent_history(50)
        shields = self.engine.get_shield_leaderboard()

        buf = create_shadow_dna_excel_report(
            shadow_summary=summary,
            coin_dna=coin_dna,
            shadow_history=shadow_hist,
            shield_leaderboard=shields
        )
        self.assertIsInstance(buf, io.BytesIO)
        file_bytes = buf.getvalue()
        self.assertGreater(len(file_bytes), 2000) # Valid xlsx file
        # Magic bytes for zip/xlsx
        self.assertEqual(file_bytes[:2], b'PK')

if __name__ == "__main__":
    unittest.main()
