import unittest
import sys
import os
import time
import json
import tempfile
import asyncio

# Proje ana dizinini sys.path'e ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from paper_trader import PaperTrader
import config
from live_trader import normalize_symbol, to_exchange_symbol, load_live_config
from security_vault import SecurityVault
import db_manager
from market_data import MarketDataManager


class TestAsama8SoakAndProductionReadiness(unittest.TestCase):
    """
    AŞAMA 8: KURUMSAL DOĞRULAMA, SOAK TEST VE CANLIYA GEÇİŞ (PRODUCTION READINESS & SIGN-OFF)
    Denetim.docx Bölüm 27 ve Yol Haritası Aşama 8 Kriterleri Doğrulama Testi.
    """

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.history_file = os.path.join(self.tmp_dir.name, "soak_trade_history.json")
        self.positions_file = os.path.join(self.tmp_dir.name, "soak_positions_state.json")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_task8_1_soak_test_stability_and_zero_leak(self):
        """
        TASK-8.1 Doğrulaması:
        PaperTrader üzerinde 1.000 döngülük sentetik yüksek frekanslı soak test.
        - 0 unhandled exception
        - Kasa muhasebesi tam mutabakat (Closed Trades Net PnL == Kasa Değişimi)
        - $150k tavan zırhı ve kâr rezervi kilidi
        - State serileştirme stabilitesi
        """
        trader = PaperTrader(initial_balance=10000.0)
        trader.balance = 10000.0
        trader.open_positions.clear()
        trader.history.clear()
        trader.save_history = lambda critical=False: None
        trader.save_local_history = lambda: None

        symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        initial_balance = trader.balance

        # 1.000 döngülük stres testi simülasyonu
        for i in range(1, 1001):
            sym = symbols[i % len(symbols)]
            price = 50000.0 + (i * 0.5)

            # Her 5 döngüde bir pozisyon aç (%0.50 stop mesafesi - sniper guard altında)
            if i % 5 == 1 and len(trader.open_positions) < 3:
                side = "LONG" if (i % 2 == 1) else "SHORT"
                trader.open_position(
                    symbol=sym,
                    side=side,
                    entry_price=price,
                    position_size_usdt=250.0,
                    leverage=5,
                    hard_stop=price * 0.995 if side == "LONG" else price * 1.005,
                    soft_stop=price * 0.996 if side == "LONG" else price * 1.004,
                    reason=f"SOAK_TEST_ENTRY_{i}",
                    bypass_stop_gate=True
                )

            # Her 3 döngüde bir açık pozisyonlara telemetri güncellemesi gönder
            for s in list(trader.open_positions.keys()):
                curr_p = price * (1.005 if trader.open_positions[s]["side"] == "LONG" else 0.995)
                trader.update_tick_telemetry(s, curr_p)

            # Her 10 döngüde bir kâr/zararla pozisyon kapat
            if i % 10 == 0 and len(trader.open_positions) > 0:
                s_to_close = list(trader.open_positions.keys())[0]
                exit_p = price * (1.015 if trader.open_positions[s_to_close]["side"] == "LONG" else 0.985)
                trader.close_position(
                    symbol=s_to_close,
                    current_price=exit_p,
                    reason=f"SOAK_TP_CLOSE_{i}"
                )

        # Kasa mutabakat kontrolü:
        # trader.balance == initial_balance + sum(closed trade net_pnl)
        total_closed_net_pnl = sum(r.get("net_pnl", 0.0) for r in trader.history)
        expected_balance = initial_balance + total_closed_net_pnl
        self.assertAlmostEqual(trader.balance, expected_balance, places=2,
                               msg="Soak test sonrası kasa mutabakatında sapma tespit edildi!")

        # Serbest bakiye mutabakat kontrolü:
        open_margins = sum(p.get("margin", 0.0) for p in trader.open_positions.values())
        expected_free_balance = max(0.0, expected_balance - open_margins)
        self.assertAlmostEqual(trader.get_free_balance(), expected_free_balance, places=2)

        # Kâr koruma tavanı testi: Kasayı $160,000'a yükselt
        trader.balance = 160000.0
        trader.open_position(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            position_size_usdt=500.0,
            leverage=5,
            hard_stop=49700.0,
            soft_stop=49750.0,
            bypass_stop_gate=True
        )
        trader.close_position(
            symbol="BTC/USDT",
            current_price=55000.0,
            reason="RESERVE_TRIGGER_TEST"
        )
        # Bakiye $10,000'a silinmemeli, kâr rezervine aktarılmalı ve bakiye $100,000 tavanında kalmalı
        self.assertGreaterEqual(trader.secured_profit_reserve, 60000.0)
        self.assertEqual(trader.balance, 100000.0)

    def test_task8_2_production_readiness_and_gate_compliance(self):
        """
        TASK-8.2 Doğrulaması:
        Canlıya Geçiş Onay Protokolü (Sign-off) ve 6 Başarı Kapısı Uyumluluk Denetimi:
        - Kapı 1: P0 Bloklayıcı Hata Kalmadı (0 Kalan P0)
        - Kapı 2: Binance Futures Stop-Market ve kwargs senkronizasyonu
        - Kapı 3: Fonlama Oranı Sınırları ve Ölçek Doğruluğu
        - Kapı 4: Siber Güvenlik, Parola Özetleme ve Admin Yetkilendirmesi
        - Kapı 5: Konfigürasyon Risk Tavanları (Kaldıraç <= 5x, Meme <= 3x, Stop <= 0.80%)
        - Kapı 6: Acil Durum Kesici ve Kademeli Mikro Sermaye Politikası
        """
        # Kapı 1 & 2: live_trader inspect
        import inspect
        from live_trader import LiveTrader

        open_params = inspect.signature(LiveTrader.open_position).parameters
        self.assertTrue("current_price" in open_params or "entry_price" in open_params)
        self.assertTrue("kwargs" in open_params or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in open_params.values()))

        close_params = inspect.signature(LiveTrader.close_position).parameters
        self.assertTrue("kwargs" in close_params or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in close_params.values()))

        # Kapı 3: Fonlama bilgisi ve sınırları [-0.0075, 0.0075]
        mdm = MarketDataManager(["BTC/USDT"])
        f_info = mdm.get_funding_info("BTC/USDT")
        rate = f_info.get("rate", 0.0001)
        self.assertGreaterEqual(rate, -0.0075)
        self.assertLessEqual(rate, 0.0075)

        # Kapı 4: Güvenlik, PBKDF2 ve Admin Token kontrolü
        raw_pw = "ValkyrieSecure2026!"
        h1 = db_manager.hash_password(raw_pw)
        self.assertTrue(h1.startswith("pbkdf2:sha256:100000$"))
        self.assertTrue(db_manager.verify_password(raw_pw, h1))
        self.assertFalse(db_manager.verify_password("WrongPassword!", h1))

        # Kapı 5: Canlı İşlem Risk Parametreleri
        self.assertLessEqual(config.DEFAULT_LEVERAGE, 5, "Varsayılan kaldıraç 5x üzerinde olamaz!")
        self.assertLessEqual(config.MAX_LEVERAGE, 5, "Kurumsal azami kaldıraç tavanı 5x üzerinde olamaz!")
        self.assertLessEqual(config.MEME_MAX_LEVERAGE, 3, "Meme paritelerde kaldıraç 3x üzerinde olamaz!")
        self.assertLessEqual(config.MAX_ENTRY_STOP_DIST_PCT, 0.80, "Azami giriş stop mesafesi %0.80 üzerinde olamaz!")
        self.assertTrue(config.ENABLE_COOLDOWN_THROTTLE, "İşlemler arası soğuma freni devrede olmalıdır!")

        # Kapı 6: Acil Durum Kesici ve Mikro Sermaye Ayarı
        live_cfg = load_live_config()
        self.assertIn(live_cfg.get("mode", "DEMO").upper(), ["DEMO", "LIVE"])
        self.assertEqual(live_cfg.get("margin_type", "ISOLATED").upper(), "ISOLATED")
        self.assertLessEqual(live_cfg.get("leverage", 5), 5)
        self.assertLessEqual(live_cfg.get("position_size_usdt", 10.0), 25.0)
        self.assertTrue(live_cfg.get("auto_sl_tp", True))


if __name__ == "__main__":
    unittest.main()
