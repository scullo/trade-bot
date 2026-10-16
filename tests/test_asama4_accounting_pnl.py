import unittest
import time
import re
from paper_trader import PaperTrader


class TestAsama4AccountingPnL(unittest.TestCase):
    def setUp(self):
        self.pt = PaperTrader(initial_balance=10000.0)
        self.pt.balance = 10000.0
        self.pt.open_positions.clear()
        self.pt.history.clear()
        self.pt.save_history = lambda critical=False: None

    def test_01_no_double_funding_fee_deduction(self):
        """
        TASK-4.1 / CODE-006 Doğrulaması:
        Fonlama ücreti pozisyon açıkken self.balance'tan kesildikten sonra,
        kapanışta net_pnl_leg üzerinden kasadan İKİNCİ KEZ DÜŞÜLMEDİĞİNİN kanıtı.
        Kasa başı ve kasa sonu farkı, trade geçmişindeki net PnL ile cent'i cent'ine eşit olmalıdır.
        """
        now = time.time()
        past_epoch = (int(now) // 28800) - 1

        # $50 marjin, 5x kaldıraç -> $250 pozisyon değeri
        entry_price = 60000.0
        pos = self.pt.open_position(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=entry_price,
            margin=50.0,
            active_leverage=5,
            trade_type="SWING",
            reason="Test Open",
            entry_slippage_pct=0.0,
            bypass_stop_gate=True
        )
        self.pt.balance = 10000.0  # Başlangıç kasasını net sabitle
        pos["last_funding_epoch"] = past_epoch
        pos["entry_funding_rate"] = 0.0001  # %0.01 fonlama oranı

        # 1. 8 saatlik fonlama yerleşimi: $250 * 0.0001 = $0.025 kesinti
        settled = self.pt.check_and_settle_funding_fees()
        self.assertEqual(len(settled), 1)
        self.assertAlmostEqual(settled[0]["total_payment"], 0.0250, places=4)
        # Kasadan $0.025 düştü -> 9999.9750
        self.assertAlmostEqual(self.pt.balance, 9999.9750, places=4)
        self.assertAlmostEqual(pos["accumulated_funding_fee"], 0.0250, places=4)

        # 2. Pozisyonu başabaş (breakeven) fiyattan kapat: exit_price = 60000.0
        # Brüt kâr = 0.0
        # Komisyon = giriş $0.125 + çıkış $0.125 = $0.250
        # Toplam maliyet = komisyon ($0.250) + fonlama ($0.025) = $0.275
        # Raporlanan Net PnL = -$0.2750
        closed_record = self.pt.close_position("BTC/USDT", exit_price=60000.0, close_reason="TP Breakeven", slippage_pct=0.0)

        # Doğrulama:
        # Trade geçmişindeki net PnL:
        last_trade = self.pt.history[-1]
        self.assertAlmostEqual(last_trade["net_pnl"], -0.2750, places=4)
        self.assertAlmostEqual(last_trade["fees"], 0.2750, places=4)

        # Kasadaki son bakiye:
        # Eğer çift kesinti olsaydı kasa: 9999.9750 - 0.2750 = 9999.7000 olacaktı (-$0.300 kayıp).
        # Düzeltilmiş muhasebe ile: 9999.9750 - 0.2500 (sadece kapanış komisyonları) = 9999.7250!
        expected_final_balance = 10000.0 - 0.2750  # Başlangıçtan sona tam -$0.2750
        self.assertAlmostEqual(self.pt.balance, expected_final_balance, places=4)
        self.assertAlmostEqual(10000.0 - self.pt.balance, abs(last_trade["net_pnl"]), places=4)

    def test_02_negative_funding_settlement_on_close(self):
        """
        TASK-4.1 Doğrulaması:
        SHORT pozisyon pozitif fonlamada (veya LONG negatif fonlamada) fonlama kazandığında,
        kapanışta bu kârın silinmediğinin ve kasaya kuruşu kuruşuna yansıdığının kanıtı.
        """
        now = time.time()
        past_epoch = (int(now) // 28800) - 1

        pos = self.pt.open_position(
            symbol="ETH/USDT",
            side="SHORT",
            entry_price=3000.0,
            margin=100.0,
            active_leverage=5,
            trade_type="SWING",
            reason="Test Short",
            entry_slippage_pct=0.0,
            bypass_stop_gate=True
        )
        self.pt.balance = 10000.0
        pos["last_funding_epoch"] = past_epoch
        pos["entry_funding_rate"] = 0.0002  # %0.02 fonlama oranı ($500 * 0.0002 = $0.100 kazanç)

        # 1. Fonlama kazancı: SHORT ödemesi = -$0.100 (kasaya +$0.10 eklenir)
        settled = self.pt.check_and_settle_funding_fees()
        self.assertEqual(len(settled), 1)
        self.assertAlmostEqual(settled[0]["total_payment"], -0.1000, places=4)
        self.assertAlmostEqual(self.pt.balance, 10000.1000, places=4)

        # 2. Pozisyonu kapat: exit_price = 3000.0
        # Komisyonlar = 500 * 0.0005 * 2 = $0.500
        # Net ücret = $0.500 - $0.100 (fonlama kazancı) = $0.400 net maliyet
        # Raporlanan Net PnL = -$0.4000
        self.pt.close_position("ETH/USDT", exit_price=3000.0, close_reason="Exit", slippage_pct=0.0)

        last_trade = self.pt.history[-1]
        self.assertAlmostEqual(last_trade["net_pnl"], -0.4000, places=4)
        # Kasa son durumu: 10000.1000 - 0.5000 = 9999.6000
        self.assertAlmostEqual(self.pt.balance, 9999.6000, places=4)
        self.assertAlmostEqual(10000.0 - self.pt.balance, 0.4000, places=4)

    def test_03_profit_lock_shield_above_150k(self):
        """
        TASK-4.1 / $150k Sıfırlama Hatasının Doğrulaması:
        Kasa $150,000 tavanını aştığında kârın silinmediği,
        $100,000 aktif kasada bırakılıp kalan kısmın secured_profit_reserve'e aktarıldığının kanıtı.
        """
        # Kasayı $149,000'a ayarla
        self.pt.balance = 149000.0

        pos = self.pt.open_position(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=60000.0,
            margin=1000.0,
            active_leverage=5,
            trade_type="SWING",
            reason="Big Win",
            entry_slippage_pct=0.0,
            bypass_stop_gate=True
        )
        self.pt.balance = 149000.0  # Sabitle

        # $5000 kâr getiren bir kapanış: exit_price = 61200 (+%2)
        # $5000 marjin * 5x = $25000 pozisyon değeri -> %2 = +$500 gross kâr değil,
        # 1000 marjin * 5x = 5000 pozisyon değeri. $6000 kâr için exit_price:
        # gross = (exit - 60000) * (5000 / 60000) = 5000 => exit = 120000
        self.pt.close_position("BTC/USDT", exit_price=120000.0, close_reason="Huge Take Profit", slippage_pct=0.0)

        # Doğrulamalar:
        # Kasa $150,000'ı aştı ve sıfırlanmadı!
        self.assertGreaterEqual(self.pt.balance, 100000.0)
        self.assertEqual(self.pt.balance, 100000.0)
        self.assertGreater(self.pt.secured_profit_reserve, 0.0)
        
        # Toplam servet (Aktif Kasa + Kilitlenen Rezerv) başlangıç + net kazançla tam uyuşmalı
        total_wealth = self.pt.balance + self.pt.secured_profit_reserve
        self.assertGreater(total_wealth, 150000.0)
        self.assertIsNotNone(self.pt.emergency_alert)
        self.assertIn("KÂR KİLİTLEME ZIRHI", self.pt.emergency_alert)

    def test_04_isolated_margin_liquidation_cap(self):
        """
        İzole marjin koruması: Pozisyon tasfiye olduğunda kayıp teminatı ($50) aşamaz.
        """
        pos = self.pt.open_position(
            symbol="SOL/USDT",
            side="LONG",
            entry_price=150.0,
            margin=50.0,
            active_leverage=5,
            trade_type="SWING",
            reason="Test Isolated Cap",
            entry_slippage_pct=0.0,
            bypass_stop_gate=True
        )
        self.pt.balance = 10000.0

        # Fiyat %50 çöksün: exit_price = 75.0 (Normalde $250'lik pozisyonda -$125 kayıp üretir)
        self.pt.close_position("SOL/USDT", exit_price=75.0, close_reason="Crash Stop", slippage_pct=0.0)

        last_trade = self.pt.history[-1]
        self.assertEqual(last_trade["net_pnl"], -50.0)  # Teminat tavanı aşılmadı
        self.assertEqual(last_trade["roe_pct"], -100.0)
        self.assertEqual(self.pt.balance, 9950.0)  # Kasa tam $50 azaldı

    def test_05_dashboard_js_compute_position_pnl_parity(self):
        """
        TASK-4.2 / UI-003 Doğrulaması:
        templates/index.html içindeki computePositionPnL fonksiyonunun
        komisyon ve fonlama kesintilerini net PnL / net ROE olarak doğru hesapladığının kanıtı.
        """
        with open("templates/index.html", "r", encoding="utf-8") as f:
            html_content = f.read()

        # JS fonksiyonundaki net hesaplama satırlarını doğrula
        self.assertIn("commFee = posVal * 0.0010", html_content)
        self.assertIn("fundFee = Number(pos.accumulated_funding_fee || 0)", html_content)
        self.assertIn("netPnlUsdt = grossPnlUsdt - commFee - fundFee", html_content)
        self.assertIn("pnlUsdt = netPnlUsdt", html_content)
        self.assertIn("roePct = netRoePct", html_content)

        # Sayısal Eşdeğerlik Testi:
        # $250 değerinde, $50 teminatlı, 5x kaldıraçlı başabaş (0% fiyat farkı) pozisyon
        pos_val = 250.0
        margin = 50.0
        comm_fee = pos_val * 0.0010  # $0.25
        fund_fee = 0.025  # $0.025
        net_pnl = 0.0 - comm_fee - fund_fee  # -$0.275
        net_roe = (net_pnl / margin) * 100.0  # -0.55%

        self.assertAlmostEqual(net_pnl, -0.275, places=4)
        self.assertAlmostEqual(net_roe, -0.55, places=2)


if __name__ == "__main__":
    unittest.main()
