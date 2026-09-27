import unittest
import os
import json
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from strategy import StrategyEngine

class TestCalibratedDNAIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.strategy = StrategyEngine(None, None)

    def test_01_calibrated_dna_loaded(self):
        """100 paritelik kalibrasyon sözlüğünün eksiksiz yüklendiğini doğrula."""
        self.assertTrue(hasattr(self.strategy, 'calibrated_coin_dna'))
        self.assertEqual(len(self.strategy.calibrated_coin_dna), 100)

    def test_02_gevset_and_koru_identification(self):
        """GEVŞET ve KORU liglerinin doğru pariteler için True döndürdüğünü doğrula."""
        gevset_samples = ['SEI/USDT', 'ALGO/USDT', 'ORDI/USDT', 'VET/USDT', 'OP/USDT', 'WIF/USDT', 'TURBO/USDT', 'ACE/USDT']
        for sym in gevset_samples:
            self.assertTrue(self.strategy.is_gevset_coin(sym), f"{sym} should be identified as GEVŞET")
            self.assertFalse(self.strategy.is_koru_coin(sym), f"{sym} should NOT be identified as KORU")

        koru_samples = ['PYTH/USDT', 'RUNE/USDT', 'DASH/USDT', 'POL/USDT', 'COTI/USDT', 'ARB/USDT']
        for sym in koru_samples:
            self.assertTrue(self.strategy.is_koru_coin(sym), f"{sym} should be identified as KORU")
            self.assertFalse(self.strategy.is_gevset_coin(sym), f"{sym} should NOT be identified as GEVŞET")

    def test_03_persona_dna_enrichment(self):
        """get_coin_dynamic_persona fonksiyonunun kalibre edilmiş DNA değerlerini doğru enjekte ettiğini doğrula."""
        # GEVŞET Paritesi Testi
        p_sei = self.strategy.get_coin_dynamic_persona('SEI/USDT')
        self.assertEqual(p_sei.get('calibration_status'), 'GEVŞET')
        self.assertEqual(p_sei.get('min_confluence'), 2)
        self.assertEqual(p_sei.get('dynamic_margin_scale'), 0.5)
        self.assertEqual(p_sei.get('persona_class'), 'GEVSET_OPPORTUNITY')

        # KORU Paritesi Testi
        p_rune = self.strategy.get_coin_dynamic_persona('RUNE/USDT')
        self.assertEqual(p_rune.get('calibration_status'), 'KORU')
        self.assertEqual(p_rune.get('min_confluence'), 3)
        self.assertEqual(p_rune.get('dynamic_margin_scale'), 1.25)

        # DENGELİ Paritesi Testi
        p_btc = self.strategy.get_coin_dynamic_persona('BTC/USDT')
        self.assertEqual(p_btc.get('calibration_status'), 'DENGELİ')
        self.assertEqual(p_btc.get('min_confluence'), 3)
        self.assertEqual(p_btc.get('dynamic_margin_scale'), 1.0)

if __name__ == '__main__':
    unittest.main()
