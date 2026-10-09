"""
test_priority2_dual_horizon_evolution.py
=============================================================================
🦅 VALKYRIE MASTER V4.0: ÖNCELİK 2 - ÇİFT UFUKLU OTONOM KUANT EVRİMİ (SELF-HEALING)
Birim Test ve Matematiksel Doğrulama Paketi:
  - 2.1 8 Saatlik Hızlı Risk Döngüsü (Fast Risk Layer)
      * 8 saatlik seans periyodu (00:00, 08:00, 16:00 UTC)
      * Ardışık stop (consecutive stops >= 2) veya SEI < %35 durumunda marjinin 0.20x - 0.50x bandına çekilmesi
      * Zarar üreten toxic setup'ların 'muted_setups' listesine alınarak cerrahi olarak susturulması
      * Gösterge geometrisinin bozulmadığının (dokunulmadığının) ispatı
  - 2.2 48 Saatlik Yapısal Kuant Döngüsü (Slow Structural Layer)
      * wick_reversal_threshold: 48 saatlik iğne boyu ortalamasına göre kalibrasyon
      * chandelier_atr_mult: 48 saatlik gerçekleşen oynaklığa (RV / ATR) göre kalibrasyon
      * break_even_trigger_r: Kâr realizasyonu ve başabaş R seviyelerinin optimizasyonu
  - Strateji Entegrasyonu & Muted Setup Blokajı
=============================================================================
"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import os
import json
import time
import tempfile
import unittest
from unittest.mock import MagicMock, AsyncMock

from autonomous_dna_calibrator import (
    AutonomousDNACalibrator,
    FAST_RISK_CYCLE_SECONDS,
    SLOW_STRUCTURAL_CYCLE_SECONDS
)
from shadow_engine import ShadowExecutionEngine


class TestPriority2DualHorizonEvolution(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.calib_file = os.path.join(self.temp_dir, "test_coin_dna_calibrated.json")
        self.audit_file = os.path.join(self.temp_dir, "test_calibration_audit_history.json")

        self.initial_dna = {
            "SOL": {
                "scenario": "Dengeli",
                "min_confluence": 3,
                "dynamic_margin_scale": 1.0,
                "wick_reversal_threshold": 13.5,
                "fakeout_wick_threshold": 13.5,
                "chandelier_atr_mult": 2.0,
                "break_even_trigger_r": 1.0,
                "chandelier_be_threshold_pct": 0.8,
                "calibration_status": "DENGELİ",
                "muted_setups": []
            },
            "DOGE": {
                "scenario": "Dengeli",
                "min_confluence": 3,
                "dynamic_margin_scale": 1.0,
                "wick_reversal_threshold": 13.5,
                "fakeout_wick_threshold": 13.5,
                "chandelier_atr_mult": 2.0,
                "break_even_trigger_r": 1.0,
                "chandelier_be_threshold_pct": 0.8,
                "calibration_status": "DENGELİ",
                "muted_setups": []
            },
            "AVAX": {
                "scenario": "Dengeli",
                "min_confluence": 3,
                "dynamic_margin_scale": 1.0,
                "wick_reversal_threshold": 13.5,
                "fakeout_wick_threshold": 13.5,
                "chandelier_atr_mult": 2.0,
                "break_even_trigger_r": 1.0,
                "chandelier_be_threshold_pct": 0.8,
                "calibration_status": "DENGELİ",
                "muted_setups": []
            }
        }
        with open(self.calib_file, "w", encoding="utf-8") as f:
            json.dump(self.initial_dna, f)

        # Mock Shadow Engine
        self.shadow_engine = ShadowExecutionEngine()
        self.shadow_engine.completed_trades = []

        # Mock Strategy Engine
        class MockStrategy:
            def __init__(self, dna):
                self._calibrated_dna = dict(dna)
                self.calibrated_coin_dna = dict(dna)
                self.paper_trader = MagicMock()
                self.paper_trader.trades = []

        self.mock_strategy = MockStrategy(self.initial_dna)

        self.calibrator = AutonomousDNACalibrator(
            calibrated_dna_file=self.calib_file,
            audit_history_file=self.audit_file,
            shadow_engine=self.shadow_engine,
            strategy=self.mock_strategy
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_fast_risk_layer_consecutive_stops_clamps_margin_and_mutes_setup(self):
        """
        2.1 Fast Risk Layer:
        Son 8 saatte SOL paritesinde arka arkaya 2 kez STOP olan işlem gerçekleştiğinde:
        - SOL'un dynamic_margin_scale değeri 0.20x - 0.50x bandına çekilmeli (0.35x).
        - Zarar üreten SETUP_BREAKOUT kurulumu muted_setups listesine alınmalı.
        - Gösterge geometrisi (wick_reversal, chandelier_atr) bozulmamalı!
        """
        # SOL için paper trader'da 2 adet ardışık stop
        self.mock_strategy.paper_trader.trades = [
            {
                "symbol": "SOL/USDT",
                "setup": "SETUP_BREAKOUT",
                "pnl": -25.0,
                "close_reason": "🛑 Dinamik ATR Stopu Tetiklendi",
                "exit_time": time.time() - 3600
            },
            {
                "symbol": "SOL/USDT",
                "setup": "SETUP_BREAKOUT",
                "pnl": -30.0,
                "close_reason": "🛑 Sert Stop Tetiklendi",
                "exit_time": time.time() - 1800
            }
        ]

        res = self.calibrator.run_fast_risk_cycle(force=True)
        self.assertTrue(res["executed"])
        self.assertIn("SOL", res["coins_mitigated"])

        sol_dna = self.calibrator._load_current_calibrated_dna()["SOL"]

        # 1. Marjin 0.20x - 0.50x aralığında mı?
        self.assertGreaterEqual(sol_dna["dynamic_margin_scale"], 0.20)
        self.assertLessEqual(sol_dna["dynamic_margin_scale"], 0.50)
        self.assertEqual(sol_dna["dynamic_margin_scale"], 0.35)

        # 2. Toksik setup susturuldu mu?
        self.assertTrue(any("BREAKOUT" in s for s in sol_dna["muted_setups"]))

        # 3. Geometrik gösterge parametreleri ellenmedi mi?
        self.assertEqual(sol_dna["wick_reversal_threshold"], 13.5)
        self.assertEqual(sol_dna["chandelier_atr_mult"], 2.0)
        self.assertEqual(sol_dna["break_even_trigger_r"], 1.0)

        # 4. Canlı stratejiye enjekte edildi mi?
        self.assertEqual(self.mock_strategy.calibrated_coin_dna["SOL"]["dynamic_margin_scale"], 0.35)
        print("  [PASS] 2.1: Ardışık stop sonrası marjin 0.35x çekildi ve toxic setup susturuldu!")

    def test_02_fast_risk_layer_low_sei_triggers_clamp(self):
        """
        2.1 Fast Risk Layer:
        DOGE paritesinde son 8 saatte gölge motorunda SEI < %35 (Örn: 4 işlemden 1'i Hero = %25 SEI) olduğunda:
        - Marjin derhal 0.20x - 0.50x bandına çekilmeli.
        - Zarar üreten setup'lar muted_setups'a eklenmeli.
        """
        self.shadow_engine.completed_trades = [
            {
                "symbol": "DOGE/USDT",
                "setup": "SETUP 9 nPOC Sekmesi",
                "verdict": "SPOILER_SHIELD",
                "virtual_pnl_usd": -20.0,
                "exit_timestamp": time.time() - 2000
            },
            {
                "symbol": "DOGE/USDT",
                "setup": "SETUP 9 nPOC Sekmesi",
                "verdict": "SPOILER_SHIELD",
                "virtual_pnl_usd": -15.0,
                "exit_timestamp": time.time() - 1500
            },
            {
                "symbol": "DOGE/USDT",
                "setup": "SETUP 9 nPOC Sekmesi",
                "verdict": "HERO_SHIELD",
                "virtual_pnl_usd": -10.0,
                "exit_timestamp": time.time() - 1000
            },
            {
                "symbol": "DOGE/USDT",
                "setup": "SETUP 12 Trend Reversal",
                "verdict": "SPOILER_SHIELD",
                "virtual_pnl_usd": -25.0,
                "exit_timestamp": time.time() - 500
            }
        ]

        res = self.calibrator.run_fast_risk_cycle(force=True)
        self.assertTrue(res["executed"])
        self.assertIn("DOGE", res["coins_mitigated"])

        doge_dna = self.calibrator._load_current_calibrated_dna()["DOGE"]
        self.assertLessEqual(doge_dna["dynamic_margin_scale"], 0.50)
        self.assertGreaterEqual(doge_dna["dynamic_margin_scale"], 0.20)
        self.assertTrue(len(doge_dna["muted_setups"]) > 0)
        print("  [PASS] 2.1: Düşük SEI (< %35) durumunda marjin kelepçelendi ve setup susturuldu!")

    def test_03_fast_risk_layer_healthy_coin_remains_untouched(self):
        """
        2.1 Fast Risk Layer:
        AVAX paritesi sağlıklı kâr üretiyorsa ve SEI >= %35 ise hızlı risk katmanı dokunmamalıdır.
        """
        self.shadow_engine.completed_trades = [
            {
                "symbol": "AVAX/USDT",
                "setup": "SETUP_BREAKOUT",
                "verdict": "HERO_SHIELD",
                "virtual_pnl_usd": 30.0,
                "exit_timestamp": time.time() - 1000
            },
            {
                "symbol": "AVAX/USDT",
                "setup": "SETUP_BREAKOUT",
                "verdict": "HERO_SHIELD",
                "virtual_pnl_usd": 40.0,
                "exit_timestamp": time.time() - 500
            }
        ]

        res = self.calibrator.run_fast_risk_cycle(force=True)
        self.assertNotIn("AVAX", res["coins_mitigated"])
        avax_dna = self.calibrator._load_current_calibrated_dna()["AVAX"]
        self.assertEqual(avax_dna["dynamic_margin_scale"], 1.0)
        print("  [PASS] 2.1: Sağlıklı pariteye (SEI %100) hızlı risk müdahalesi yapılmadı!")

    def test_04_slow_structural_layer_calibrates_geometry_and_stops(self):
        """
        2.2 Slow Structural Layer:
        48 saatlik yapısal kuant döngüsünde:
        - Yüksek iğne ortalaması (%24) -> wick_reversal_threshold ve fakeout_wick_threshold kalibre edilir.
        - Yüksek oynaklık (ATR %0.95) -> chandelier_atr_mult 2.8x olarak ayarlanır.
        - Erken BE ve post-exit kaçan dalgalar -> break_even_trigger_r 1.6R olarak optimize edilir.
        """
        # AVAX için yüksek volatilite, yüksek fitil ve erken BE telemetrili 6 işlem
        self.shadow_engine.completed_trades = [
            {
                "symbol": "AVAX/USDT",
                "setup": "SETUP 1 Volatility Compression",
                "verdict": "SPOILER_SHIELD",
                "impact_usd": 20.0,
                "virtual_pnl_usd": 0.0,
                "max_mfe_pct": 2.2,
                "close_reason": "BREAKEVEN",
                "notional_usd": 250.0,
                "telemetry": {
                    "atr_pct": 0.95,
                    "wick_ratio_pct": 24.5
                }
            } for _ in range(6)
        ]
        self.shadow_engine.post_exit_history = [
            {
                "symbol": "AVAX/USDT",
                "trade_id": f"pe_avax_{i}",
                "verdict": "ERKEN_CIKIS_KACAN_DALGA",
                "left_on_table_pct": 2.8
            } for i in range(3)
        ]

        res = self.calibrator.run_slow_structural_cycle(force=True)
        self.assertTrue(res["executed"])
        self.assertIn("AVAX", res["approved_coins"])

        updated_dna = self.calibrator._load_current_calibrated_dna()["AVAX"]

        # 1. wick_reversal_threshold kalibre edildi mi? (avg_wick >= 18 -> max(20.0, 24.5+3.0) = 27.5)
        self.assertGreaterEqual(updated_dna["wick_reversal_threshold"], 20.0)
        self.assertEqual(updated_dna["wick_reversal_threshold"], updated_dna["fakeout_wick_threshold"])

        # 2. chandelier_atr_mult kalibre edildi mi? (avg_atr >= 0.85 -> 2.8x)
        self.assertEqual(updated_dna["chandelier_atr_mult"], 2.8)

        # 3. break_even_trigger_r optimize edildi mi? (erken BE ve post-exit -> 1.6R)
        self.assertEqual(updated_dna["break_even_trigger_r"], 1.6)

        # 4. İçsel simülasyon testi doğrulandı mı?
        self.assertTrue(updated_dna["validation_proof"]["passed"])
        print("  [PASS] 2.2: 48 Saatlik yapısal kuant döngüsü wick_reversal, chandelier_atr ve break_even_trigger_r parametrelerini başarıyla kalibre etti!")

    def test_05_strategy_engine_integration_and_muted_setup_enforcement(self):
        """
        Strateji Motoru Entegrasyon Testi:
        - get_coin_persona'nın wick_reversal_threshold, chandelier_atr_mult, break_even_trigger_r yüklediği doğrulanır.
        - Fast risk katmanında susturulan (MUTED) bir setup işleme girmek istediğinde StrategyEngine tarafından
          'MUTED_SETUP_BLOCKED' hatasıyla engellendiği kanıtlanır.
        """
        from strategy import StrategyEngine

        # StrategyEngine kurulumu
        mock_pt = MagicMock()
        mock_pt.balance = 10000.0
        mock_pt.open_positions = {}
        mock_tm = MagicMock()
        mock_tm.balance = 10000.0
        mock_tm.open_positions = {}
        mock_tm.paper_trader = mock_pt
        mock_tm.active_trader = mock_pt

        mock_md = MagicMock()
        mock_md.candles_5m = {}
        mock_md._clean_symbol = lambda s: s.replace('/', '').replace(':USDT', '')

        strategy = StrategyEngine(mock_tm, MagicMock(), market_data=mock_md)
        strategy.calibrated_coin_dna = {
            "SOL": {
                "dynamic_margin_scale": 0.35,
                "wick_reversal_threshold": 25.0,
                "fakeout_wick_threshold": 25.0,
                "chandelier_atr_mult": 2.8,
                "break_even_trigger_r": 1.6,
                "calibration_status": "DENGELİ",
                "muted_setups": ["SETUP 7 S4 Resistance Flip"]
            }
        }

        # 1. Persona doğrulaması
        persona = strategy.get_coin_persona("SOL/USDT")
        self.assertEqual(persona["dynamic_margin_scale"], 0.35)
        self.assertEqual(persona["wick_reversal_threshold"], 25.0)
        self.assertEqual(persona["chandelier_atr_mult"], 2.8)
        self.assertEqual(persona["break_even_trigger_r"], 1.6)
        self.assertIn("SETUP 7 S4 Resistance Flip", persona["muted_setups"])

        # 2. Susturulan setup'ın engellenmesi
        import asyncio
        res = asyncio.run(strategy._handle_open(
            symbol="SOL/USDT",
            side="SHORT",
            entry_price=150.0,
            reason="SETUP 7 S4 Resistance Flip Breakdown",
            soft_stop=152.0,
            hard_stop=153.0,
            tp1=145.0,
            tp2=140.0,
            trade_type="BREAKDOWN",
            snapshot_levels={},
            setup_id="SETUP_7_S4_BREAKDOWN",
            confluence_list=["S4_Breakdown", "Volume_Surge"]
        ))
        self.assertIn(res.get("error"), ["SETUP_MUTED_BY_ALPHA", "MUTED_SETUP_BLOCKED"])
        print("  [PASS] Strateji motoru kalibre persona parametrelerini okudu ve susturulan kurulumu bloke etti!")


if __name__ == "__main__":
    unittest.main()
