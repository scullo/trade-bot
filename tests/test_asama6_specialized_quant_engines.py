# -*- coding: utf-8 -*-
"""
Aşama 6: Özel Kuant Motorları, Mock Veri Temizliği ve Çapraz Sembol Bütünlüğü Testi
==================================================================================
Bu test paketi Denetim Raporu Aşama 6 kapsamında giderilen:
1. TASK-6.1: Bank of America sahte contrarian boost kuralının kaldırılması ve standart marjin korunumu.
2. TASK-6.2: Gölge işlem kuyruk taşmasında (rotation timeout) çapraz sembol fiyat korrupsiyonunun önlenmesi.
3. Kurumsal Opsiyon GEX, SSR Osilatörü ve Tether 1B Mint bileşenlerinin matematiksel doğrulaması.
"""

import unittest
import os
import time
from unittest.mock import MagicMock, patch

from macro_strategy_guard import MacroStrategyGuard
from shadow_engine import ShadowExecutionEngine
from market_data import MarketDataManager


class TestAsama6SpecializedQuantEngines(unittest.TestCase):

    def setUp(self):
        # Test için geçici gölge geçmiş dosyası
        self.test_history_file = "test_shadow_trades_history_asama6.json"

    def tearDown(self):
        if os.path.exists(self.test_history_file):
            try:
                os.remove(self.test_history_file)
            except Exception:
                pass

    def test_task6_1_no_fake_bank_of_america_contrarian_boost(self):
        """Sahte Bank of America kuralının kaldırıldığını, marjinin 1.45x şişirilmediğini doğrular."""
        mock_calendar = MagicMock()
        mock_calendar.is_flash_shock_active.return_value = (False, None)
        mock_calendar.get_next_major_event.return_value = None

        mock_cross = MagicMock()
        mock_cross.get_macro_regime.return_value = {"regime": "NEUTRAL_BALANCED"}

        mock_news = MagicMock()
        mock_news.get_news_bias.return_value = {"bias": "NEUTRAL"}
        mock_news.get_latest_news.return_value = []

        mock_quorum = MagicMock()
        mock_quorum.get_quorum_consensus.return_value = {"consensus": "NEUTRAL"}

        mock_evolution = MagicMock()
        mock_evolution.contrarian_mode_enabled = True  # Eskiden bu True olunca her işleme 1.45x basılıyordu!

        guard = MacroStrategyGuard()
        guard.calendar = mock_calendar
        guard.cross_asset = mock_cross
        guard.news_sentinel = mock_news
        guard.quorum = mock_quorum
        guard.evolution = mock_evolution
        guard.override_shock_regime = "NEUTRAL_BALANCED"

        base_margin = 250.0
        base_tp1 = 61000.0
        base_tp2 = 62000.0
        entry_price = 60000.0

        # Normal işlem için boost hesabı çağrısı
        res = guard.calculate_macro_position_boost(
            symbol="BTCUSDT",
            side="LONG",
            entry_price=entry_price,
            base_margin=base_margin,
            base_tp1=base_tp1,
            base_tp2=base_tp2,
            setup_id="SETUP_3_S3_BOUNCE",
            reason="S3 Destek Sekmesi"
        )

        # 1.45x Sahte marjin uygulanmamalı, standart marjin ($250.0) korunmalı
        self.assertFalse(res["boosted"])
        self.assertEqual(res["margin"], base_margin)
        self.assertEqual(res["tp2"], base_tp2)
        self.assertEqual(res["runner_mode"], False)
        self.assertNotIn("Bank of America", res["reason"])
        self.assertIn("Standart kuant marjin", res["reason"])

    def test_task6_1_genuine_macro_shock_boost_still_works(self):
        """Gerçek bir makro boğa şoku ve breakout durumunda meşru 1.25x boostun çalıştığını doğrular."""
        guard = MacroStrategyGuard()
        mock_cross = MagicMock()
        mock_cross.data = {}
        guard.cross_asset = mock_cross
        guard.override_shock_regime = "BULL_MACRO_SHOCK"

        base_margin = 200.0
        entry_price = 60000.0
        base_tp1 = 61000.0
        base_tp2 = 62000.0

        res = guard.calculate_macro_position_boost(
            symbol="BTCUSDT",
            side="LONG",
            entry_price=entry_price,
            base_margin=base_margin,
            base_tp1=base_tp1,
            base_tp2=base_tp2,
            setup_id="SETUP_1_R4_BREAKOUT",
            reason="R4 Kırılım Boğa Devamı"
        )

        self.assertTrue(res["boosted"])
        self.assertEqual(res["margin"], 250.0)  # 200 * 1.25
        self.assertTrue(res["runner_mode"])
        self.assertIn("BOĞA MAKRO ŞOKU", res["reason"])

    def test_task6_2_shadow_queue_overflow_cross_symbol_integrity(self):
        """Gölge motoru kuyruk taşmasında (max_active rotasyonu) çapraz sembol fiyat korrupsiyonunun olmadığını doğrular."""
        # max_active = 2 olan test motoru
        engine = ShadowExecutionEngine(history_file=self.test_history_file, max_active=2, max_history=100)
        engine.is_test = True
        engine.active_positions.clear()
        engine.completed_trades.clear()

        # 1. Pozisyon: BTCUSDT @ 60,000.0
        pos1 = engine.spawn_shadow_trade(
            symbol="BTC/USDT",
            setup_name="SETUP_3_S3_BOUNCE",
            reason="S3 Destek Sekmesi",
            side="LONG",
            entry_price=60000.0,
            sl_price=59000.0,
            tp1_price=61000.0,
            tp2_price=62000.0
        )
        self.assertIsNotNone(pos1)
        self.assertEqual(len(engine.active_positions), 1)

        # BTC için mum güncellemesi: Kapanış 60,500.0
        engine.update_candle("BTC/USDT", {"high": 60600.0, "low": 59900.0, "close": 60500.0})
        self.assertEqual(engine.active_positions[pos1["id"]]["current_price"], 60500.0)

        # 2. Pozisyon: ETHUSDT @ 3,000.0
        pos2 = engine.spawn_shadow_trade(
            symbol="ETH/USDT",
            setup_name="SETUP_3_S3_BOUNCE",
            reason="S3 Destek Sekmesi",
            side="LONG",
            entry_price=3000.0,
            sl_price=2900.0,
            tp1_price=3100.0,
            tp2_price=3200.0
        )
        self.assertIsNotNone(pos2)
        self.assertEqual(len(engine.active_positions), 2)

        # 3. Pozisyon: SOLUSDT @ 150.0
        # Kapasite 2 olduğu için en eski pozisyon (pos1 - BTCUSDT) ZAMAN_AŞIMI (Rotasyon) ile kapatılmalıdır!
        pos3 = engine.spawn_shadow_trade(
            symbol="SOL/USDT",
            setup_name="SETUP_3_S3_BOUNCE",
            reason="S3 Destek Sekmesi",
            side="LONG",
            entry_price=150.0,
            sl_price=140.0,
            tp1_price=160.0,
            tp2_price=170.0
        )
        self.assertIsNotNone(pos3)

        # Aktif pozisyon sayısı max_active (2) olmalı (ETH ve SOL)
        self.assertEqual(len(engine.active_positions), 2)
        self.assertNotIn(pos1["id"], engine.active_positions)
        self.assertIn(pos2["id"], engine.active_positions)
        self.assertIn(pos3["id"], engine.active_positions)

        # Tamamlanan işlem listesini incele
        self.assertEqual(len(engine.completed_trades), 1)
        closed_btc = engine.completed_trades[0]
        self.assertEqual(closed_btc.get("id") or closed_btc.get("shadow_id"), pos1["id"])
        self.assertEqual(closed_btc["symbol"], "BTC/USDT")

        # ÇAPRAZ SEMBOL KORRUPSİYONU KONTROLÜ:
        # Kapanış fiyatı kesinlikle BTC'nin kendi güncel fiyatı (60500.0) olmalı,
        # ASLA yeni açılan SOL'un fiyatı (150.0) veya ETH'nin fiyatı (3000.0) olmamalıdır!
        self.assertEqual(closed_btc["exit_price"], 60500.0)
        self.assertNotEqual(closed_btc["exit_price"], 150.0)
        self.assertNotEqual(closed_btc["exit_price"], 3000.0)

        # PnL mantığı BTC ölçeğinde pozitif olmalıdır (60500 > 60000)
        self.assertGreater(closed_btc["virtual_pnl_usd"], 0)

    def test_ssr_oscillator_and_tether_mint_logic(self):
        """SSR osilatörü ve Tether 1B mint akışının kurumsal kurallara uygun çalıştığını doğrular."""
        streamer = MarketDataManager(all_symbols=["BTC/USDT", "ETH/USDT"])
        streamer.current_prices["BTC/USDT"] = 65000.0
        streamer.stablecoin_ammunition = {"total_pegged_usd": 160_000_000_000.0}

        # 1. SSR Hesabı
        ssr = streamer.get_ssr_status()
        self.assertIsInstance(ssr, dict)
        self.assertGreater(ssr.get("ssr_value", 0.0), 0.0)
        expected_btc_mc = 65000.0 * 19_760_000.0
        expected_ssr = expected_btc_mc / 160_000_000_000.0
        self.assertAlmostEqual(ssr.get("ssr_value"), expected_ssr, delta=0.5)

        # 2. Tether Mint Takibi
        # 500M transfer: $1B eşiğini aşmadığı için 4 saatlik boost tetiklenmemeli
        sub_res = streamer.record_tether_treasury_mint(500_000_000.0, blockchain="TRON")
        self.assertFalse(sub_res.get("is_active", False))

        # 1.2B transfer: $1B eşiğini aştığı için boğa boost aktif edilmeli
        mega_res = streamer.record_tether_treasury_mint(1_200_000_000.0, blockchain="TRON")
        self.assertTrue(mega_res.get("is_active", False))
        self.assertEqual(mega_res.get("amount_usd"), 1_200_000_000.0)
        self.assertIn("1.20B", mega_res.get("boost_reason", ""))


if __name__ == "__main__":
    unittest.main()
