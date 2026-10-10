"""
================================================================================
VALKYRIE MASTER AUDIT - AŞAMA 5 KANIT VE KONTROL PROTOKOLÜ
PAPER TRADER, MARJİN BÜTÜNLÜĞÜ VE KASA GÜVENLİĞİ TESTİ
(VDA-35, VDA-36, VDA-37, VDA-13)
================================================================================
"""

import sys
import os
import time
import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock
import pandas as pd

from paper_trader import PaperTrader
from strategy import StrategyEngine
from shadow_engine import ShadowExecutionEngine


def create_sample_df(base_price=100.0, count=20, is_bull=True):
    if is_bull:
        return pd.DataFrame({
            'open': [base_price - 10.0] * count,
            'high': [base_price + 0.20] * count,
            'low': [base_price - 10.20] * count,
            'close': [base_price] * count,
            'volume': [2000.0] * count,
            'taker_quote': [1500.0] * count,
            'qav': [2000.0] * count
        })
    else:
        return pd.DataFrame({
            'open': [base_price + 10.0] * count,
            'high': [base_price + 10.20] * count,
            'low': [base_price - 0.20] * count,
            'close': [base_price] * count,
            'volume': [2000.0] * count,
            'taker_quote': [500.0] * count,
            'qav': [2000.0] * count
        })


class TestPhase5PaperTraderSafetyProof(unittest.TestCase):

    def setUp(self):
        # İzole test ortamı
        test_history_file = f"test_trades_phase5_{int(time.time()*1000)}.json"
        self.history_file = os.path.join(os.path.dirname(__file__), test_history_file)
        self.trader = PaperTrader(initial_balance=10000.0, leverage=5, margin_per_trade=50.0)
        self.trader.history_file = self.history_file
        self.trader.open_positions.clear()
        self.trader.history.clear()
        self.trader.balance = 10000.0
        self.trader.is_safety_stopped = False
        self.trader.trading_halted = False

    def tearDown(self):
        if os.path.exists(self.history_file):
            try:
                os.remove(self.history_file)
            except Exception:
                pass

    def test_01_vda35_concurrency_stress_test_margin_multiplier(self):
        """
        VDA-35: Eşzamanlılık Yarış Testi (Concurrency Stress Test):
        asyncio.gather ile aynı anda 10 farklı paritede pozisyon açılır.
        Her parite farklı hacim ve oturum koşullarına sahiptir.
        Yerel marjin çarpanının (local_margin_mult) pariteler arası
        birbirini ezmediği (Race Condition olmadığı) kanıtlanır.
        """
        mock_notifier = AsyncMock()

        symbols = [f"COIN{i}/USDT" for i in range(1, 11)]

        def mock_metrics_func(sym):
            idx = int(sym.replace("COIN", "").replace("/USDT", "")) - 1
            v = 4.2 if (idx % 2 == 0) else 2.2
            return {
                "dynamic_rs_score": 0.0,
                "atr_pct": 1.5,
                "vol_surge": v,
                "min_vol_surge": 1.0,
                "is_top_80": True
            }

        mock_md = MagicMock()
        mock_md.candles_5m = {}
        mock_md.current_prices = {}
        mock_md.orderbook_depth = {}
        mock_md.levels = {}
        mock_md.open_interest_radar = {'open_interest': 1000.0, 'last_update': time.time(), 'status': 'BALANCED', 'delta_oi_pct': 0.0}
        mock_md.get_funding_info = MagicMock(return_value={'rate_pct': 0.0100, 'squeeze_status': 'BALANCED'})
        mock_md.get_orderbook_depth = MagicMock(return_value={'imbalance': 0.10, 'ratio': 1.3, 'bid_qty': 5000.0, 'ask_qty': 4000.0, 'last_update': time.time(), 'wall_side': 'BALANCED', 'wall_duration_sec': 10.0})
        mock_md.get_symbol_cvd = MagicMock(return_value={'ratio_60s': 55.0, 'delta_60s': 5000.0})
        mock_md.get_symbol_liquidation_stats = MagicMock(return_value={'long_usd': 0.0, 'short_usd': 0.0})
        mock_md.is_btc_shock_active = MagicMock(return_value=(False, 0.0, 0))
        mock_md.get_btc_velocity_60s = MagicMock(return_value=0.0)
        mock_md.get_spot_perp_basis = MagicMock(return_value={'is_available': False, 'basis_bps': 0.0, 'spot_perp_divergence': 0.0})
        mock_md.get_jit_l2_depth = AsyncMock(return_value={'depth_available': False})
        mock_md.get_symbol_metrics = MagicMock(side_effect=mock_metrics_func)

        strategy = StrategyEngine(self.trader, mock_notifier, mock_md)
        strategy.macro_oracle = None  # Birim testinde PaperTrader marjin yarışını izole test et

        captured_orders = []

        async def mock_safe_open(**kwargs):
            # Asenkron bekleme ile race condition tetiklemeyi dene (10ms context switch)
            await asyncio.sleep(0.01)
            captured_orders.append(kwargs)
            return {"orderId": 9999, "status": "FILLED", **kwargs}

        strategy._safe_open_position = mock_safe_open

        for s in symbols:
            mock_md.candles_5m[s] = create_sample_df(100.0, 20, is_bull=True)
            mock_md.current_prices[s] = 100.0

        async def run_concurrent():
            tasks = []
            for i, sym in enumerate(symbols):
                if i % 2 == 0:
                    t_type = "BREAKOUT"
                    r_text = "Direnç Kırılımı Climax Hacim"
                else:
                    t_type = "SCALP"
                    r_text = "S3 Destek Sekmesi Hacimli"

                t = strategy._handle_open(
                    symbol=sym, side="LONG", entry_price=100.0,
                    reason=r_text, soft_stop=98.5, hard_stop=98.0,
                    tp1=103.0, tp2=105.0, trade_type=t_type,
                    snapshot_levels={"camarilla": {"S3": 99.0, "R3": 101.0}},
                    setup_id="SETUP_1_R4_BREAKOUT" if t_type == "BREAKOUT" else "SETUP_3_S3_BOUNCE",
                    confluence_list=["Teyit_1", "Teyit_2", "Teyit_3"]
                )
                tasks.append(t)

            await asyncio.gather(*tasks)

        asyncio.run(run_concurrent())

        print(f"\n[EŞZAMANLILIK TESTİ] Toplam {len(captured_orders)} emir eşzamanlı işlendi.")
        self.assertEqual(len(captured_orders), 10, "10 paritenin tamamı eşzamanlı açılmalıydı.")

        for order in captured_orders:
            sym = order["symbol"]
            idx = int(sym.replace("COIN", "").replace("/USDT", "")) - 1
            mm = order.get("margin_multiplier", 1.0)
            if idx % 2 == 0:
                # Climax Breakout -> 0.5 çarpanı almalı (0.5 * 1.2 = 0.6)
                self.assertLessEqual(mm, 0.9,
                                    f"VDA-35 Yarış Hatası: {sym} Climax Breakout olmasına rağmen çarpanı {mm} (bulaşma var!)")
            else:
                # High Volume Scalp -> 1.5 çarpanı almalı (1.5 * 1.2 = 1.8)
                self.assertGreaterEqual(mm, 1.2,
                                       f"VDA-35 Yarış Hatası: {sym} Scalp olmasına rağmen çarpanı {mm} (bulaşma var!)")

        print("  [PASS] VDA-35: Eşzamanlı 10 Paritede Marjin Çarpanı Bulaşması (Race Condition) %100 Önlendi!")

    def test_02_vda36_meme_coin_multiplier_guard_on_close(self):
        """
        VDA-36: Meme Coin Multiplier Guard Kapanış Testi:
        1000PEPE/USDT vadeli işlem açılır (giriş $0.010, teminat $50).
        Kapanış fiyatı spot PEPE cinsinden ($0.000008) geldiğinde,
        Multiplier Guard bunu otomatik $0.008'e normalize etmeli ve
        kasaya sahte -%99.9 zarar yazılmasını önlemelidir.
        """
        # 1. 1000PEPE/USDT pozisyonu aç
        pos = self.trader.open_position(
            symbol="1000PEPE/USDT",
            side="LONG",
            entry_price=0.010,
            reason="Meme Kırılım Girişi",
            soft_stop=0.0095,
            hard_stop=0.0090,
            tp1=0.0110,
            tp2=0.0120,
            custom_margin=50.0,
            custom_leverage=5,
            bypass_stop_gate=True
        )
        self.assertIsNotNone(pos, "Pozisyon açılmalıydı.")
        self.assertIn("1000PEPE/USDT", self.trader.open_positions)
        initial_balance = self.trader.balance

        # 2. Hatalı spot fiyatla ($0.000008) kapatmayı dene (1000x ölçek farkı)
        # Spot $0.000008 -> Vadeli $0.0080 olmalıdır (fiyat %20 düştü, %99.9 değil!)
        closed_rec = self.trader.close_position(
            symbol="1000PEPE/USDT",
            exit_price=0.000008,
            close_reason="Stop Seviyesi Testi"
        )
        self.assertIsNotNone(closed_rec, "Kapanış kaydı üretilmeli.")

        # Doğrulamalar:
        # Exit price 0.008 olarak ölçeklenmiş olmalı
        self.assertAlmostEqual(closed_rec["exit_price"], 0.008, places=5,
                               msg="VDA-36 Hatası: Multiplier Guard exit_price'ı 1000x ile çarpmadı!")
        
        # Gross zarar: (0.008 - 0.010) * 25000 = -$50.0 olmalı (Spot fiyattaki -$249.8 değil!)
        self.assertGreater(closed_rec["gross_pnl"], -60.0,
                           f"VDA-36 Hatası: Kasaya sahte felaket zararı yazıldı! PnL: {closed_rec['gross_pnl']}")
        self.assertGreater(self.trader.balance, 9900.0,
                           f"VDA-36 Hatası: Bakiye sahte tasfiyeyle eridi! Kalan: {self.trader.balance}")

        print("  [PASS] VDA-36: Multiplier Guard 1000x Meme Kapanışında Sahte %99.9 Tasfiyeyi Engelledi!")

    def test_03_vda37_isolated_margin_liquidation_ceiling_and_slippage(self):
        """
        VDA-37: İzole Marjin Tasfiye Tavanı ve Gerçekçi Slippage Testi:
        %90 çöken bir paritede 5x kaldıraçlı işlemde brüt kayıp teminatın %450'sine
        varsa dahi, izole marjin kuralı gereği yazılan net zarar yatırılan marjini (-$50) aşamaz.
        Ayrıca slippage_pct parametresi çıkış fiyatına doğru yansıtılmalıdır.
        """
        # 1. $50 teminat, 5x kaldıraç ile pozisyon aç (Pozisyon değeri $250)
        pos = self.trader.open_position(
            symbol="CRASH/USDT",
            side="LONG",
            entry_price=100.0,
            reason="Kırılım",
            soft_stop=95.0,
            hard_stop=90.0,
            tp1=110.0,
            custom_margin=50.0,
            custom_leverage=5,
            bypass_stop_gate=True
        )
        self.assertIsNotNone(pos)
        start_bal = self.trader.balance

        # 2. Fiyat %90 çöküyor: 100 -> 10.0
        # Normalde brüt zarar: (10 - 100) * 2.5 = -$225.0
        # İzole marjin tavanı ile net zarar en fazla -$50.00 olmalı!
        closed_rec = self.trader.close_position(
            symbol="CRASH/USDT",
            exit_price=10.0,
            close_reason="Flash Crash Likidasyon",
            slippage_pct=0.005 # %0.5 slippage
        )
        self.assertIsNotNone(closed_rec)

        # Doğrulamalar:
        # a. Net zarar tam olarak -$50.00 ile sınırlanmalı
        self.assertEqual(closed_rec["net_pnl"], -50.0,
                         f"VDA-37 Hatası: İzole marjin tavanı çalışmadı! Zarar: {closed_rec['net_pnl']} > -50.0")
        self.assertEqual(closed_rec["roe_pct"], -100.0,
                         f"VDA-37 Hatası: ROE -%100 ile sınırlanmalıydı! ROE: {closed_rec['roe_pct']}")
        self.assertTrue(closed_rec.get("is_liquidated"),
                        "VDA-37 Hatası: is_liquidated bayrağı True olmalıydı.")
        self.assertIn("TASFİYESİ", closed_rec.get("close_reason", ""))

        # b. Kasa bakiyesi -$225 değil, sadece -$50 eksilmeli (10000 - 50 = 9950)
        self.assertEqual(self.trader.balance, start_bal - 50.0,
                         f"VDA-37 Hatası: Kasadan marjinden fazla para çekildi! Kasa: {self.trader.balance}")

        # c. Slippage kaydı
        self.assertEqual(closed_rec.get("exit_slippage_pct"), 0.5)

        print("  [PASS] VDA-37: İzole Marjin Tasfiye Tavanı Doğrulandı (Kayıp Marjinle Sınırlandı: -$50.00)!")

    def test_04_vda13_safe_shutdown_mode_instead_of_auto_reset(self):
        """
        VDA-13: Otomatik Bakiye Sıfırlama Devre Dışı & Güvenli Durdurma Testi:
        Bakiye $1,000 altına indiğinde botun bakiyeyi otomatik $10,000'e sıfırlayıp
        drawdown'u gizlemesi engellenmeli; sistem 'is_safety_stopped = True' moduna geçmeli
        ve yeni pozisyon açmayı reddetmelidir.
        Sıfırlama yalnızca yetkili 'reset_state()' çağrısıyla yapılabilmelidir.
        """
        # 1. Bakiyeyi yapay olarak $800'e düşür (Kritik eşik altı)
        self.trader.balance = 800.0

        # Pozisyon açmayı dene -> engellenmeli
        pos = self.trader.open_position(
            symbol="BTC/USDT", side="LONG", entry_price=65000.0,
            reason="Test", soft_stop=64000.0, hard_stop=63000.0,
            tp1=66000.0, custom_margin=50.0, custom_leverage=5,
            bypass_stop_gate=True
        )
        # Bakiye < 1000 olduğu için open_position GÜVENLİ DURDURMA vermeli
        self.assertIsInstance(pos, dict)
        self.assertEqual(pos.get("error"), "SAFETY_STOP_ACTIVE",
                         "VDA-13 Hatası: Bakiye < $1,000 iken yeni pozisyon açılması engellenmedi!")
        self.assertTrue(self.trader.is_safety_stopped)

        # 2. Bakiye asla sihirli bir şekilde 10,000'e fırlamamalı!
        self.assertEqual(self.trader.balance, 800.0,
                         "VDA-13 Hatası: Bakiye otomatik olarak sıfırlandı ve gerçek drawdown gizlendi!")

        # 3. Kapatma sırasında da bakiye < 1000 olduğunda otomatik reset yapılmamalı
        self.trader.balance = 1050.0
        self.trader.is_safety_stopped = False
        self.trader.trading_halted = False
        pos_open = self.trader.open_position(
            symbol="ETH/USDT", side="LONG", entry_price=3500.0,
            reason="Normal İşlem", soft_stop=3400.0, hard_stop=3300.0,
            tp1=3600.0, custom_margin=100.0, custom_leverage=5,
            bypass_stop_gate=True
        )
        self.assertIsNotNone(pos_open)
        self.assertNotIn("error", pos_open)

        # 100$ zarar ile kapat -> Bakiye 1050 - 100 = 950$ (< 1000$)
        rec = self.trader.close_position("ETH/USDT", exit_price=2700.0, close_reason="Stop")
        self.assertIsNotNone(rec)

        # Bakiye $950 olarak kalmalı, 10000'e sıfırlanmamalı!
        self.assertLess(self.trader.balance, 1000.0)
        self.assertEqual(round(self.trader.balance, 2), 950.0)
        self.assertTrue(self.trader.is_safety_stopped)
        self.assertIn("GÜVENLİ DURDURMA", self.trader.emergency_alert)

        # 4. Yetkili reset_state() çağrıldığında sistem normale dönmeli
        self.trader.reset_state()
        self.assertEqual(self.trader.balance, 10000.0)
        self.assertFalse(self.trader.is_safety_stopped)
        self.assertFalse(self.trader.trading_halted)

        print("  [PASS] VDA-13: Otomatik Bakiye Sıfırlama Kaldırıldı, Güvenli Durdurma Modu Doğrulandı!")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("  VALKYRIE MASTER AUDIT - AŞAMA 5 DOĞRULAMA TESTİ (VDA-35, 36, 37, 13)")
    print("="*80)
    unittest.main()
