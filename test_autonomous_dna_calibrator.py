import unittest
import os
import json
import tempfile
from autonomous_dna_calibrator import AutonomousDNACalibrator


class TestAutonomousDNACalibrator(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.calib_file = os.path.join(self.temp_dir, "test_coin_dna_calibrated.json")
        self.audit_file = os.path.join(self.temp_dir, "test_calibration_audit_history.json")

        # Örnek başlangıç DNA'sı
        initial_dna = {
            "WIF": {
                "scenario": "Dengeli",
                "min_confluence": 4,
                "chandelier_be_threshold_pct": 0.8,
                "calibration_status": "DENGELİ"
            },
            "BTC": {
                "scenario": "Dengeli",
                "min_confluence": 3,
                "chandelier_be_threshold_pct": 0.8,
                "calibration_status": "DENGELİ"
            }
        }
        with open(self.calib_file, "w", encoding="utf-8") as f:
            json.dump(initial_dna, f)

        # Mock shadow engine
        class MockShadowEngine:
            def __init__(self):
                # WIF için 6 adet spoiler işlemi (kaçan kâr > kurtarılan zarar)
                self.completed_trades = [
                    {
                        "symbol": "WIF/USDT",
                        "verdict": "SPOILER_SHIELD",
                        "impact_usd": 25.0,
                        "virtual_pnl_usd": 0.0,
                        "max_mfe_pct": 2.5,
                        "close_reason": "SPOILER",
                        "notional_usd": 250.0
                    } for _ in range(6)
                ]

        self.mock_shadow = MockShadowEngine()

        class MockStrategy:
            def __init__(self):
                self._calibrated_dna = initial_dna

        self.mock_strategy = MockStrategy()

        self.calibrator = AutonomousDNACalibrator(
            calibrated_dna_file=self.calib_file,
            audit_history_file=self.audit_file,
            shadow_engine=self.mock_shadow,
            strategy=self.mock_strategy
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_run_cycle_and_self_validation(self):
        # İlk döngüyü zorla çalıştır
        res = self.calibrator.run_cycle(force=True)
        self.assertTrue(res["executed"])
        self.assertIn("WIF", res["approved_coins"])

        # WIF'in yeni statüsü GEVŞET olmalı
        with open(self.calib_file, "r", encoding="utf-8") as f:
            updated_dna = json.load(f)

        self.assertEqual(updated_dna["WIF"]["calibration_status"], "GEVŞET")
        self.assertEqual(updated_dna["WIF"]["min_confluence"], 2)
        self.assertIn("validation_proof", updated_dna["WIF"])
        self.assertTrue(updated_dna["WIF"]["validation_proof"]["passed"])

        # Stratejiye canlı enjeksiyon doğrulandı mı?
        self.assertEqual(self.mock_strategy._calibrated_dna["WIF"]["calibration_status"], "GEVŞET")

        # Denetim defteri kaydı oluştu mu?
        self.assertEqual(len(self.calibrator.audit_history), 1)
        self.assertEqual(self.calibrator.audit_history[0]["overall_proof"], "BAŞARILI - İÇSEL MATEMATİKSEL KANIT TEYİTLİ")

    def test_dashboard_summary(self):
        summary = self.calibrator.get_dashboard_summary()
        self.assertEqual(summary["cycle_frequency_hours"], 48)
        self.assertEqual(summary["total_coins"], 2)


if __name__ == "__main__":
    unittest.main()
