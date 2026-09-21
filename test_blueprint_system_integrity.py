"""
Valkyrie Kurumsal Alpha Master Blueprint - Sistem Bütünlüğü, Telemetri ve Otonom Sağlık Test Paketi
--------------------------------------------------------------------------------------------------
Bu test paketi; Faz 1, Faz 2, Faz 3 kuant algoritmalarının veri akışını, pozisyon telemetrisini,
Aegis Sentinel oto-onarım (auto-healing) mekanizmalarını, Excel dışa aktarımını ve sistemin
asla kilitlenmeyeceğini (non-blocking zero-freeze) kanıtlar.
"""

import unittest
import asyncio
import time
import numpy as np
import pandas as pd
from unittest.mock import MagicMock, AsyncMock, patch
from collections import deque

from paper_trader import PaperTrader
from aegis_sentinel import ValkyrieAegisSentinel


class DummyMarketData:
    """Testler için tam donanımlı mock MarketDataManager."""
    def __init__(self):
        self.all_symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
        self.current_prices = {'BTC/USDT': 65000.0, 'ETH/USDT': 3500.0, 'SOL/USDT': 140.0}
        self.levels = {
            'BTC/USDT': {
                'camarilla': {'R4': 66000.0, 'S4': 64000.0, 'R3': 65500.0, 'S3': 64500.0, 'P': 65000.0},
                'tepe_avwap': 65200.0,
                'dip_avwap': 64800.0,
                'npoc': {'price': 65100.0}
            },
            'ETH/USDT': {
                'camarilla': {'R4': 3600.0, 'S4': 3400.0, 'R3': 3550.0, 'S3': 3450.0, 'P': 3500.0},
                'tepe_avwap': 3520.0,
                'dip_avwap': 3480.0,
                'npoc': {'price': 3510.0}
            },
            'SOL/USDT': {
                'camarilla': {'R4': 145.0, 'S4': 135.0, 'R3': 142.0, 'S3': 138.0, 'P': 140.0},
                'tepe_avwap': 141.0,
                'dip_avwap': 139.0,
                'npoc': {'price': 140.5}
            }
        }
        self.deribit_gex_data = {
            'BTC': {
                'net_gex': 45000000.0,
                'gex_regime': 'POSITIVE_GAMMA_PIN',
                'is_pinning_regime': True,
                'is_explosion_regime': False,
                'pcr': 0.82
            },
            'ETH': {
                'net_gex': 12000000.0,
                'gex_regime': 'POSITIVE_GAMMA_PIN',
                'is_pinning_regime': True,
                'is_explosion_regime': False,
                'pcr': 0.88
            },
            'last_sync_ts': time.time(),
            'is_live': True
        }
        self.recent_liquidations = deque(maxlen=60)
        self.symbol_liquidations_15m = {}
        self.symbol_cvd = {
            'BTC/USDT': {'delta_60s': 120000.0, 'ratio_60s': 1.4, 'accel_60s': 450.0, 'cvd_pct': 58.0},
            'ETH/USDT': {'delta_60s': -30000.0, 'ratio_60s': 0.8, 'accel_60s': -120.0, 'cvd_pct': 46.0},
            'SOL/USDT': {'delta_60s': 15000.0, 'ratio_60s': 1.1, 'accel_60s': 30.0, 'cvd_pct': 52.0}
        }
        self.candles_5m = {s: pd.DataFrame({'close': [100.0] * 50}) for s in self.all_symbols}
        self._last_candle_scan_ts = time.time()

    def get_hawkes_avalanche(self, symbol=None):
        return {
            'branching_ratio_eta': 0.22,
            'intensity': 0.08,
            'regime': 'QUIET_FLOW',
            'is_avalanche_active': False,
            'is_avalanche_exhausted': False,
            'avalanche_side': 'NONE',
            'long_liq_usd': 0.0,
            'short_liq_usd': 0.0,
            'desc': '⚪ Durgun Tasfiye Akışı'
        }

    def get_deribit_gex_regime(self):
        return self.deribit_gex_data.get('BTC', {}).get('gex_regime', 'NEUTRAL')

    async def fetch_single_symbol(self, sym):
        pass

    async def fetch_deribit_gex_immediate(self):
        self.deribit_gex_data['last_sync_ts'] = time.time()
        self.deribit_gex_data['is_live'] = True
        return True


class TestBlueprintSystemIntegrity(unittest.TestCase):

    def setUp(self):
        # İzole test paper trader başlat
        self.trader = PaperTrader(initial_balance=10000.0, leverage=5, margin_per_trade=300.0)
        self.trader.save_history = MagicMock()
        self.trader.save_local_history = MagicMock()
        self.trader._push_to_github = MagicMock()
        self.trader.balance = 10000.0
        self.trader.open_positions = {}
        self.trader.history = []
        self.market_data = DummyMarketData()
        self.sentinel = ValkyrieAegisSentinel()

    def test_01_blueprint_telemetry_in_open_and_close_positions(self):
        """1. Pozisyon açılış ve kapanışında 11 Blueprint telemetri alanının tam akışı."""
        pos = self.trader.open_position(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=65000.0,
            soft_stop=64200.0,
            hard_stop=64000.0,
            tp1=65800.0,
            tp2=66800.0,
            leverage=5,
            reason="SETUP_1_R4_BREAKOUT",
            calculated_dollar_risk=80.0,
            # Faz 1, 2, 3 Blueprint Telemetrisi:
            stoikov_micro_price=65040.0,
            stoikov_drift_bps=6.15,
            vpin_score=0.42,
            vpin_toxicity="LOW",
            kyles_lambda_ratio=0.85,
            deribit_gex_regime="POSITIVE_GAMMA_PIN",
            deribit_net_gex=45000000.0,
            hawkes_eta=0.22,
            is_avalanche_active=False,
            cvd_accel_60s=450.0,
            tri_modal_regime="DIRECTIONAL_EXPANSION"
        )
        self.assertIsNotNone(pos, "Pozisyon başarıyla açılmalı")
        self.assertEqual(pos['stoikov_drift_bps'], 6.15)
        self.assertEqual(pos['deribit_gex_regime'], "POSITIVE_GAMMA_PIN")
        self.assertEqual(pos['tri_modal_regime'], "DIRECTIONAL_EXPANSION")
        self.assertEqual(pos['hawkes_eta'], 0.22)

        # TP1 Kapanışı Testi
        tp1_res = self.trader.close_position("BTC/USDT", exit_price=65800.0, close_reason="TP1_HALF_TAKE_PROFIT", is_partial=True)
        self.assertTrue(tp1_res)
        self.assertEqual(len(self.trader.history), 1)
        h_tp1 = self.trader.history[0]
        self.assertEqual(h_tp1['stoikov_drift_bps'], 6.15)
        self.assertEqual(h_tp1['deribit_gex_regime'], "POSITIVE_GAMMA_PIN")
        self.assertEqual(h_tp1['hawkes_eta'], 0.22)
        self.assertEqual(h_tp1['tri_modal_regime'], "DIRECTIONAL_EXPANSION")

        # Full Close Kapanışı Testi
        full_res = self.trader.close_position("BTC/USDT", exit_price=66500.0, close_reason="TP2_RUNNER_FULL_CLOSE")
        self.assertTrue(full_res)
        self.assertEqual(len(self.trader.history), 2)
        h_full = self.trader.history[1]
        self.assertEqual(h_full['stoikov_drift_bps'], 6.15)
        self.assertEqual(h_full['vpin_toxicity'], "LOW")
        self.assertEqual(h_full['kyles_lambda_ratio'], 0.85)
        self.assertEqual(h_full['cvd_accel_60s'], 450.0)

    def test_02_aegis_sentinel_blueprint_audit_healthy(self):
        """2. Aegis Sentinel Blueprint sensör denetimi tam sağlıklı senaryo."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            audit = loop.run_until_complete(self.sentinel.audit_alpha_blueprint_sensors(self.market_data))
            self.assertTrue(audit['is_healthy'])
            self.assertTrue(audit['deribit_gex']['is_fresh'])
            self.assertEqual(audit['deribit_gex']['regime'], "POSITIVE_GAMMA_PIN")
            self.assertEqual(audit['hawkes_avalanche']['eta'], 0.22)
            self.assertEqual(audit['cvd_integrity']['nan_anomalies'], 0)
        finally:
            loop.close()

    def test_03_aegis_sentinel_auto_healing_stale_deribit_and_nan_cvd(self):
        """3. Aegis Sentinel Auto-Healing: Bayat Deribit verisi ve CVD NaN otomatik onarımı."""
        # 1. Bayat Deribit simülasyonu (25 dakika önce güncellenmiş)
        self.market_data.deribit_gex_data['last_sync_ts'] = time.time() - 1500

        # 2. NaN CVD anomalisi simülasyonu
        self.market_data.symbol_cvd['BTC/USDT']['accel_60s'] = float('nan')
        self.market_data.symbol_cvd['ETH/USDT']['delta_60s'] = float('inf')

        # 3. 2 saatten eski tasfiye kaydı simülasyonu
        self.market_data.symbol_liquidations_15m['STALE/USDT'] = {
            'long_usd': 50000.0,
            'short_usd': 0.0,
            'last_update': time.time() - 7200
        }

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Denetimi çalıştır
            findings = loop.run_until_complete(self.sentinel.audit_alpha_blueprint_sensors(self.market_data))
            self.assertFalse(findings['is_healthy'], "Bayat Deribit ve NaN CVD nedeniyle sağlıksız olarak işaretlenmeli")
            self.assertFalse(findings['deribit_gex']['is_fresh'])
            self.assertEqual(findings['cvd_integrity']['nan_anomalies'], 2)

            # Auto-healing çalıştır
            audit_dict = {"blueprint": findings}
            actions = loop.run_until_complete(self.sentinel.apply_auto_healing(self.market_data, self.trader, audit_dict))

            # Onarımları doğrula
            self.assertTrue(any("Deribit GEX bayatlığı" in a for a in actions), "Deribit onarım görevi başlatılmalı")
            self.assertTrue(any("bayat tasfiye kaydı bellekten tahliye edildi" in a for a in actions), "RAM koruması eski pariteyi silmeli")
            self.assertTrue(any("CVD NaN/Inf değeri 0.0 ile onarıldı" in a for a in actions), "NaN CVD 0.0'a eşitlenmeli")

            # RAM temizliğini doğrula
            self.assertNotIn('STALE/USDT', self.market_data.symbol_liquidations_15m)

            # CVD NaN temizliğini doğrula
            self.assertEqual(self.market_data.symbol_cvd['BTC/USDT']['accel_60s'], 0.0)
            self.assertEqual(self.market_data.symbol_cvd['ETH/USDT']['delta_60s'], 0.0)
        finally:
            loop.close()

    def test_04_full_sentinel_audit_and_telegram_report(self):
        """4. 6-Katmanlı Sentinel denetimi ve Telegram kurumsal rapor formatı testi."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            full_audit = loop.run_until_complete(self.sentinel.run_full_sentinel_audit(self.market_data, self.trader))
            self.assertIn('blueprint', full_audit)
            self.assertTrue(full_audit['is_all_perfect'])
            self.assertEqual(full_audit['status_text'], "KUSURSUZ (CANLI İŞLEME HAZIR)")

            # Telegram Raporunu Oluştur
            report_msg = self.sentinel.generate_executive_telegram_report(full_audit, self.trader)
            self.assertIn("KURUMSAL ALPHA RADARI", report_msg)
            self.assertIn("Deribit GEX Black-Scholes", report_msg)
            self.assertIn("Hawkes Tasfiye Çığı", report_msg)
            self.assertIn("POSITIVE_GAMMA_PIN", report_msg)
        finally:
            loop.close()

    def test_05_excel_exporter_blueprint_columns(self):
        """5. Excel dışa aktarım motoruna 5 yeni Blueprint kolonunun entegrasyonu."""
        from excel_exporter import HEADERS_GRANULAR, create_styled_excel_report
        header_names = [h[0] for h in HEADERS_GRANULAR]

        self.assertIn('Stoikov Drift (bps)', header_names)
        self.assertIn('VPIN Toksisite Skoru', header_names)
        self.assertIn('Kyle’s Lambda Oranı', header_names)
        self.assertIn('Deribit GEX Rejimi', header_names)
        self.assertIn('Hawkes Tasfiye Çığı (η)', header_names)
        self.assertIn('CVD Uyumsuzluğu (Divergence)', header_names)
        self.assertIn('Göreceli Hacim (RVOL Z-Score)', header_names)
        self.assertIn('Makro Likidite & Dominans', header_names)
        self.assertIn('Geometrik R-Oranı', header_names)
        self.assertEqual(len(HEADERS_GRANULAR), 90, "Toplam sütun sayısı 90 olmalı")

        # Gerçek bir rapor oluşturma testi
        dummy_trade = {
            'symbol': 'BTC/USDT',
            'side': 'LONG',
            'trade_type': 'SCALP',
            'leverage': 5,
            'margin': 300.0,
            'entry_price': 65000.0,
            'exit_price': 66000.0,
            'gross_pnl': 50.0,
            'fees': 1.5,
            'net_pnl': 48.5,
            'roe_pct': 16.16,
            'balance_after': 10048.5,
            'entry_time': '2026-09-19 12:00:00',
            'exit_time': '2026-09-19 12:25:00',
            'duration': '25 dk',
            'reason': 'SETUP_1_R4_BREAKOUT',
            'close_reason': 'TP1_HALF_TAKE_PROFIT',
            'stoikov_drift_bps': 4.5,
            'vpin_score': 0.35,
            'vpin_toxicity': 'LOW',
            'kyles_lambda_ratio': 0.95,
            'deribit_gex_regime': 'POSITIVE_GAMMA_PIN',
            'hawkes_eta': 0.18,
            'is_avalanche_active': False
        }
        report_buffer = create_styled_excel_report([dummy_trade], current_balance=10048.5, initial_balance=10000.0)
        self.assertIsNotNone(report_buffer)
        self.assertGreater(len(report_buffer.getvalue()), 1000, "Oluşturulan Excel dosyası geçerli olmalı")

    def test_06_zero_lock_api_resilience_and_safe_fallback(self):
        """6. Sıfır kilitlenme (Zero-Lock): Harici API çökse dahi sistemin kesintisiz devamı."""
        # Deribit API tamamen çökse veya network timeouts yaşansa dahi fetch_deribit_gex_immediate asenkron ve crash-proof olmalı
        from market_data import MarketDataManager
        md = MarketDataManager(['BTC/USDT', 'ETH/USDT'])

        # Sahte başarısız Deribit isteği simülasyonu
        with patch('aiohttp.ClientSession.get', side_effect=Exception("Connection Timeout")):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                res = loop.run_until_complete(md.fetch_deribit_gex_immediate())
                self.assertFalse(res, "Harici hata durumunda False dönmeli, asla crash olmamalı")
                regime = md.get_deribit_gex_regime()
                self.assertEqual(regime, "NEUTRAL", "Harici API yokken sistem güvenli NÖTR rejimde kalmalı")
            finally:
                loop.close()


if __name__ == '__main__':
    unittest.main()
