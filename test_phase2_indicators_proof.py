# -*- coding: utf-8 -*-
"""
====================================================================
VALKYRIE QUANT REFORM - AŞAMA 2 KANIT VE DOĞRULAMA TEST PROTOKOLÜ
Hedef: Matematiksel Göstergeler ve Kuant Alfa Motoru Doğrulaması
Maddeler: VDA-22, VDA-23, VDA-24, VDA-25, VDA-26, VDA-27, VDA-28, VDA-29, VDA-30, VDA-31, VDA-33, VDA-38
====================================================================
"""

import sys
import unittest
import numpy as np
import pandas as pd

from indicators import (
    calculate_camarilla_pivots,
    calculate_volume_profile,
    get_tradingview_naked_lines,
    calculate_orderbook_entropy,
    calculate_hurst_exponent,
    calculate_cvd_acceleration,
    calculate_stoikov_micro_price,
    calculate_vpin_toxicity,
    calculate_kyles_lambda,
    calculate_deribit_gex,
    calculate_hawkes_avalanche
)
from aegis_sentinel import ValkyrieAegisSentinel

# UTF-8 stdout encoding
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


class TestPhase2IndicatorsProof(unittest.TestCase):
    """Aşama 2 cerrahi müdahalelerinin matematiksel ve operasyonel kanıt testi."""

    def setUp(self):
        print(f"\n--- [BAŞLATILIYOR] {self._testMethodName} ---")

    def test_01_vda22_hurst_exponent_log_returns(self):
        """
        [KANIT VDA-22]: Benoit Mandelbrot Hurst Üssü Log-Getiri Kanıtı.
        Rastgele Yürüyüşte (Brownian Motion) H ~ 0.50 (+-0.05),
        Güçlü Trendde H > 0.55,
        Ortalamaya Dönen Seride H < 0.45 üretildiğinin ispatı.
        (Eski sistem ham fiyat kullandığı için rastgele yürüyüşte bile H=0.95 veriyordu!)
        """
        np.random.seed(42)
        # 1. Brownian Motion (Rastgele Yürüyüş / Gürültü)
        n = 2000
        gbm_returns = np.random.normal(0.0001, 0.01, n)
        gbm_prices = 100.0 * np.exp(np.cumsum(gbm_returns))
        h_random = calculate_hurst_exponent(gbm_prices)
        print(f"  > Rastgele Yürüyüş (Brownian Motion) Hurst: {h_random:.3f} (Beklenen: 0.42 - 0.58)")
        self.assertGreaterEqual(h_random, 0.42)
        self.assertLessEqual(h_random, 0.58)

        # 2. Kalıcı / Güçlü Trend (Persistent Trend - Pozitif otokorelasyonlu AR(1) getiriler)
        rets = [0.0]
        for _ in range(n):
            rets.append(0.65 * rets[-1] + np.random.normal(0, 0.01))
        trend_prices = 100.0 * np.exp(np.cumsum(rets))
        h_trend = calculate_hurst_exponent(trend_prices)
        print(f"  > Kalıcı Trend Serisi Hurst: {h_trend:.3f} (Beklenen: > 0.60)")
        self.assertGreater(h_trend, 0.60)

        # 3. Ortalamaya Dönen (Mean-Reverting / Anti-persistent)
        mr_prices = [100.0]
        for i in range(n):
            dev = mr_prices[-1] - 100.0
            step = -0.5 * dev + np.random.normal(0, 1.0)
            mr_prices.append(mr_prices[-1] + step)
        h_mr = calculate_hurst_exponent(mr_prices)
        print(f"  > Ortalamaya Dönen Seri Hurst: {h_mr:.3f} (Beklenen: < 0.45)")
        self.assertLess(h_mr, 0.45)
        print("  [BAŞARILI] VDA-22: Log-getirili Hurst hesabı Mandelbrot kalkanını çalıştırdı.")

    def test_02_vda26_naked_lines_directional_guarantee(self):
        """
        [KANIT VDA-26]: Naked Lines Yönsel Seviye Doğrulama Assertion.
        100 sentetik senaryoda above_* seviyelerinin fiyattan daima yukarıda,
        below_* seviyelerinin daima aşağıda olduğunun matematiksel ispatı.
        """
        np.random.seed(123)
        for i in range(100):
            cur_p = float(np.random.uniform(10.0, 50000.0))
            # Fiyatın altında ve üstünde mumlar üret
            highs = [cur_p * np.random.uniform(0.98, 1.05) for _ in range(50)]
            lows = [cur_p * np.random.uniform(0.95, 1.02) for _ in range(50)]
            df = pd.DataFrame({
                'high': highs,
                'low': lows,
                'open': [l + (h - l) * 0.4 for h, l in zip(highs, lows)],
                'close': [l + (h - l) * 0.6 for h, l in zip(highs, lows)],
                'volume': [float(np.random.uniform(10, 1000)) for _ in range(50)]
            })
            res = get_tradingview_naked_lines(df, cur_p)
            above_npoc = res['above_npoc']
            below_npoc = res['below_npoc']
            above_nvah = res['above_nvah']
            below_nval = res['below_nval']

            self.assertGreater(above_npoc, cur_p, f"Senaryo {i}: above_npoc ({above_npoc}) > cur_p ({cur_p}) olmalıdır!")
            self.assertLess(below_npoc, cur_p, f"Senaryo {i}: below_npoc ({below_npoc}) < cur_p ({cur_p}) olmalıdır!")
            self.assertGreater(above_nvah, cur_p, f"Senaryo {i}: above_nvah ({above_nvah}) > cur_p ({cur_p}) olmalıdır!")
            self.assertLess(below_nval, cur_p, f"Senaryo {i}: below_nval ({below_nval}) < cur_p ({cur_p}) olmalıdır!")

        print("  > 100 sentetik parite senaryosunda above_npoc > cur_p > below_npoc %100 sağlandı.")
        print("  [BAŞARILI] VDA-26: Naked lines yönsel garanti kuralı doğrulandı.")

    def test_03_vda23_vpin_taker_base_column(self):
        """
        [KANIT VDA-23]: VPIN'in Gerçek Borsa 'taker_base' ve 'taker_quote' Sütunlarını Okuması.
        Eski sistemde 'taker_buy_volume' arandığı için mum gövdesi tahminine düşüyordu.
        """
        # Binance kline DataFrame formatı
        df_real = pd.DataFrame({
            'open': [100.0, 101.0, 102.0],
            'high': [103.0, 104.0, 105.0],
            'low': [99.0, 100.0, 101.0],
            'close': [102.0, 103.0, 104.0],
            'volume': [1000.0, 2000.0, 1500.0],
            'taker_base': [900.0, 1900.0, 1400.0], # %90-95 agresif taker alış
            'taker_quote': [90000.0, 190000.0, 140000.0]
        })

        vpin_res = calculate_vpin_toxicity(df_real)
        score = vpin_res['vpin_score']
        print(f"  > Gerçek Taker Alış (%90) ile Hesaplanan VPIN: {score:.3f} | Seviye: {vpin_res['toxicity_level']}")
        # Yüksek tek taraflı taker akışı yüksek VPIN toksisitesi üretmelidir (> 0.50)
        self.assertGreater(score, 0.50, "VPIN gerçek borsa taker_base akışını okuyup yüksek toksisite tespit etmelidir!")
        self.assertTrue(vpin_res['is_toxic_flow'])
        print("  [BAŞARILI] VDA-23: VPIN 'taker_base' sütununu başarıyla okuyor.")

    def test_04_vda24_stoikov_micro_price_threshold(self):
        """
        [KANIT VDA-24]: Stoikov Mikro-Fiyat Kayma Eşiğinin Sığ Spread'li Paritelerde (BTC/ETH) Tetiklenebilmesi.
        Eski 1.2 bps sabit eşik BTC'nin 0.01 bps spread'inde imkansızdı.
        """
        # BTC L2 Derinlik Simülasyonu: Fiyat $65,000, Spread $0.20 (0.03 bps)
        # Tahtanın %80'i Alıcı Ağırlıklı (Güçlü mikro-fiyat yukarı itmesi)
        bids = [(65000.00, 20.0), (64999.80, 15.0), (64999.60, 10.0), (64999.40, 10.0), (64999.20, 10.0)]
        asks = [(65000.20, 1.0), (65000.40, 1.0), (65000.60, 1.0), (65000.80, 1.0), (65001.00, 1.0)]

        res = calculate_stoikov_micro_price(bids, asks, current_price=65000.10)
        print(f"  > BTC Stoikov Drift: {res['micro_drift_bps']:.4f} bps | Bias: {res['micro_bias']} | is_micro_bull: {res['is_micro_bull']}")
        # Yeni dinamik kural ile BTC'deki bu güçlü alıcı baskısı artık tespit edilebilir!
        self.assertTrue(res['is_micro_bull'], "Dinamik eşik BTC'deki alıcı baskısını tespit edebilmelidir!")
        self.assertEqual(res['micro_bias'], 'BULL_MICRO_DRIFT')
        print("  [BAŞARILI] VDA-24: Stoikov mikro-fiyat eşiği sığ spread paritelerinde çalışıyor.")

    def test_05_vda25_orderbook_entropy_classification(self):
        """
        [KANIT VDA-25]: Boltzmann Entropi Mantığının Düzeltilmesi.
        20 kademeye eşit dağılmış derin kurumsal tahtanın S_norm >= 0.80 vermesi ve 'sağlıklı' sayılması.
        Tek kademeye yığılmış sahte duvarın ise S_norm < 0.40 ile anormal yoğunlaşma olarak yakalanması.
        """
        # 1. Derin ve Dengeli Tahta (20 kademeye eşit dağılmış)
        uniform_bids = [(100.0 - i * 0.1, 10.0) for i in range(20)]
        uniform_asks = [(100.1 + i * 0.1, 10.0) for i in range(20)]
        ent_uniform = calculate_orderbook_entropy(uniform_bids, uniform_asks, top_n=20)
        print(f"  > Derin & Dengeli Tahta Entropisi: {ent_uniform['entropy_norm']:.3f} (is_healthy_deep: {ent_uniform['is_healthy_deep']})")
        self.assertGreaterEqual(ent_uniform['entropy_norm'], 0.85)
        self.assertTrue(ent_uniform['is_healthy_deep'], "Dengeli tahta sağlıklı ve derin olarak sınıflandırılmalıdır!")

        # 2. Anormal Yoğunlaşma / Tek Duvar Spoofing (1. kademede %95 yığılma)
        spoof_bids = [(100.0, 1000.0)] + [(100.0 - i * 0.1, 0.5) for i in range(1, 20)]
        spoof_asks = [(100.1, 1000.0)] + [(100.1 + i * 0.1, 0.5) for i in range(1, 20)]
        ent_spoof = calculate_orderbook_entropy(spoof_bids, spoof_asks, top_n=20)
        print(f"  > Tek Duvar / Spoofing Entropisi: {ent_spoof['entropy_norm']:.3f} (is_abnormal_concentration: {ent_spoof['is_abnormal_concentration']})")
        self.assertLess(ent_spoof['entropy_norm'], 0.40)
        self.assertTrue(ent_spoof['is_abnormal_concentration'], "Tek kademe yığılması anormal yoğunlaşma olarak yakalanmalıdır!")
        print("  [BAŞARILI] VDA-25: Boltzmann entropi mantığı doğru kurumsal sınıflandırmaya kavuştu.")

    def test_06_vda27_deribit_gamma_flip_interpolation(self):
        """
        [KANIT VDA-27]: Deribit Gamma Flip Seviyesinin Enterpolasyonla Doğru Tespiti.
        Spot $65,000 iken ilk strike'a (örn. $15,000) düşmeden, sıfır kesişiminin spot civarında ($64k) bulunması.
        """
        # Sentetik opsiyon defteri: Spot $65,000
        # 50k - 60k arası Put ağırlıklı (Negatif Gamma)
        # 65k - 80k arası Call ağırlıklı (Pozitif Gamma)
        options_book = [
            {'instrument_name': 'BTC-28OCT26-40000-C', 'open_interest': 10.0, 'mark_iv': 50.0},
            {'instrument_name': 'BTC-28OCT26-55000-P', 'open_interest': 500.0, 'mark_iv': 55.0},
            {'instrument_name': 'BTC-28OCT26-60000-P', 'open_interest': 1000.0, 'mark_iv': 52.0},
            {'instrument_name': 'BTC-28OCT26-65000-C', 'open_interest': 600.0, 'mark_iv': 50.0},
            {'instrument_name': 'BTC-28OCT26-70000-C', 'open_interest': 1200.0, 'mark_iv': 53.0},
            {'instrument_name': 'BTC-28OCT26-80000-C', 'open_interest': 500.0, 'mark_iv': 60.0},
        ]

        gex_res = calculate_deribit_gex(options_book, spot_price=65000.0)
        flip_k = gex_res['gamma_flip_strike']
        print(f"  > Spot: $65,000 | Hesaplanan Gamma Flip: ${flip_k:,.2f}")
        # Flip seviyesi $40k'ya çökmemeli, 55k-70k arasında spot civarında olmalıdır
        self.assertGreater(flip_k, 55000.0, "Gamma Flip 55k üstünde spot civarında olmalıdır!")
        self.assertLess(flip_k, 75000.0, "Gamma Flip 75k altında spot civarında olmalıdır!")
        print("  [BAŞARILI] VDA-27: Deribit Gamma Flip enterpolasyonu gerçekçi sıfır kesişimini buluyor.")

    def test_07_vda28_hawkes_avalanche_branching_ratio(self):
        """
        [KANIT VDA-28]: Hawkes Çığı Dallanma Oranının (eta = alpha/beta * w) Teorik Hesabı.
        """
        # Büyük tasfiye serisi
        now_ts = 1000.0
        liq_events = [
            {'timestamp': now_ts - 20, 'usd_size': 50000.0, 'side': 'LONG'},
            {'timestamp': now_ts - 15, 'usd_size': 75000.0, 'side': 'LONG'},
            {'timestamp': now_ts - 10, 'usd_size': 120000.0, 'side': 'LONG'},
            {'timestamp': now_ts - 5,  'usd_size': 90000.0, 'side': 'LONG'},
            {'timestamp': now_ts - 1,  'usd_size': 150000.0, 'side': 'LONG'},
        ]
        res = calculate_hawkes_avalanche(liq_events, current_time=now_ts)
        eta = res['branching_ratio_eta']
        intensity = res['intensity']
        print(f"  > Hawkes Çığ Yoğunluğu: {intensity:.2f} | Dallanma Oranı (eta): {eta:.2f} | Rejim: {res['regime']}")
        self.assertGreaterEqual(eta, 0.70)
        self.assertTrue(res['is_avalanche_active'])
        self.assertEqual(res['avalanche_side'], 'LONG_LIQ_DUMP_CASCADE')
        print("  [BAŞARILI] VDA-28: Hawkes dallanma oranı teorik standartta çalışıyor.")

    def test_08_vda29_volume_profile_symmetric_va(self):
        """
        [KANIT VDA-29]: Hacim Profili Değer Alanı Dengeli Genişleme Testi.
        Eşit veya sıfır hacim durumunda yukarı doğru yapay kayma olmaksızın simetrik VAH/VAL türetimi.
        """
        # POC merkezli simetrik hacim dağılımı
        df_sym = pd.DataFrame({
            'high': [100.0 + i * 0.1 for i in range(30)],
            'low': [97.0 + i * 0.1 for i in range(30)],
            'close': [98.5 + i * 0.1 for i in range(30)],
            'volume': [100.0 for _ in range(30)]
        })
        vp = calculate_volume_profile(df_sym, num_rows=24, value_area_pct=0.70)
        poc = vp['POC']
        vah = vp['VAH']
        val = vp['VAL']
        print(f"  > Simetrik Profil: VAL: ${val:.2f} | POC: ${poc:.2f} | VAH: ${vah:.2f}")
        self.assertGreater(vah, poc)
        self.assertLess(val, poc)
        # POC Değer Alanının tam ortasında veya çok yakınında olmalıdır
        dist_up = vah - poc
        dist_dn = poc - val
        diff_skew = abs(dist_up - dist_dn) / ((dist_up + dist_dn) / 2.0)
        print(f"  > Yukarı Mesafe: ${dist_up:.2f} | Aşağı Mesafe: ${dist_dn:.2f} | Asimetri Oranı: %{diff_skew*100:.1f}")
        self.assertLess(diff_skew, 0.35, "Simetrik hacimde Değer Alanı POC etrafında dengeli olmalıdır!")
        print("  [BAŞARILI] VDA-29: Hacim profili Değer Alanı simetrisi korundu.")

    def test_09_vda30_kyles_lambda_open_candle_projection(self):
        """
        [KANIT VDA-30]: Kyle's Lambda'nın Henüz Açılmış Mumda Sahte Hava Cebi Tuzağı Üretmemesi.
        """
        # Geçmiş 20 adet 5 dakikalık tam mum (Her biri 300s, $50,000 hacim)
        df_hist = pd.DataFrame({
            'open': [100.0 for _ in range(20)],
            'high': [100.2 for _ in range(20)],
            'low': [99.8 for _ in range(20)],
            'close': [100.1 for _ in range(20)],
            'volume': [500.0 for _ in range(20)]
        })

        # Henüz 10 saniyesi geçmiş yeni canlı mum (fiyat %0.35 sıçramış ama hacim henüz sığ)
        import time
        now_ms = time.time() * 1000.0
        cur_candle = {
            'timestamp': now_ms - 10000.0, # 10 saniye önce açıldı
            'open': 100.0,
            'close': 100.35, # %0.35 artış
            'volume': 20.0
        }

        res = calculate_kyles_lambda(df_hist, current_candle=cur_candle)
        print(f"  > 10. Saniyedeki Canlı Mum Kyle's Lambda: {res['lambda_ratio']:.2f}x | is_vacuum_trap: {res['is_vacuum_trap']}")
        # 10. saniyedeki mumda sahte hava cebi tuzağı VETO EDİLMEMELİDİR
        self.assertFalse(res['is_vacuum_trap'], "Henüz açılmış 10 saniyelik mumda hava cebi tuzağı tetiklenmemelidir!")
        print("  [BAŞARILI] VDA-30: Kyle's Lambda hacim ekstrapolasyonu erken hava cebi tuzağını önledi.")

    def test_10_vda31_cvd_acceleration_numerical_stability(self):
        """
        [KANIT VDA-31]: CVD İvme Hesabında Sayısal Kararlılık ve NaN Koruması.
        """
        # Sentetik CVD deltas serisi
        cvd_series = [100.0, 150.0, 220.0, 310.0, 420.0, 500.0, 550.0, 570.0, 580.0]
        res = calculate_cvd_acceleration(cvd_series)
        print(f"  > CVD Hız: {res['velocity']:.2f} | İvme: {res['acceleration']:.2f} | Zero-Cross: {res['zero_crossing']}")
        self.assertFalse(np.isnan(res['velocity']))
        self.assertFalse(np.isnan(res['acceleration']))
        # Alıcı tükenişi (hız artışı yavaşladı, ivme negatife döndü)
        self.assertEqual(res['zero_crossing'], 'BULL_EXHAUSTION_TOP')
        self.assertTrue(res['is_exhaustion_top'])
        print("  [BAŞARILI] VDA-31: CVD ivme sayısal türevi kararlı ve tepe tükenişini yakalıyor.")

    def test_11_vda33_camarilla_s5_positive_floor(self):
        """
        [KANIT VDA-33]: Aşırı Volatilite Günlerinde (H/L > 2) Camarilla S5 Taban Koruması.
        Eski sistemde S5 = 2*Close - R5 negatif fiyat üretiyordu.
        """
        # H = 200, L = 80, C = 150 (H/L = 2.5 > 2.0)
        # R5 = (200 / 80) * 150 = 2.5 * 150 = 375
        # Eski S5 = 150 - (375 - 150) = 150 - 225 = -75.0 (NEGATİF FİYAT!)
        res = calculate_camarilla_pivots(high=200.0, low=80.0, close=150.0)
        s5 = res['S5']
        r5 = res['R5']
        print(f"  > Ekstrem Volatilite (H:200, L:80, C:150): R5: ${r5:.2f} | S5: ${s5:.2f}")
        # S5 pozitif olmalı (en az Close * 0.05 = $7.50)
        self.assertGreater(s5, 0.0, "Camarilla S5 asla negatif olamaz!")
        self.assertEqual(s5, 150.0 * 0.05)
        print("  [BAŞARILI] VDA-33: Camarilla S5 taban koruması devrede.")

    def test_12_vda38_aegis_sentinel_npoc_key(self):
        """
        [KANIT VDA-38]: Aegis Sentinel'in 'above_npoc' ve 'below_npoc' Seviyelerini %100 Tanıması.
        Eski sistemde lev.get('npoc', {}) arandığı için 100 paritede npoc 0 bildirilip hata raporlanıyordu.
        """
        import asyncio
        sentinel = ValkyrieAegisSentinel()
        # Mock MarketData
        class MockMarketData:
            def __init__(self):
                self.all_symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
                self.levels = {
                    s: {
                        'camarilla': {'R4': 105.0, 'S4': 95.0, 'P': 100.0},
                        'tepe_avwap': 102.0,
                        'dip_avwap': 98.0,
                        'above_npoc': 104.0, # VDA-38
                        'below_npoc': 96.0   # VDA-38
                    } for s in self.all_symbols
                }

        mock_md = MockMarketData()
        audit_res = asyncio.run(sentinel.audit_indicator_levels(mock_md))
        print(f"  > Aegis Sentinel Seviye Denetimi: Geçerli nPOC: {audit_res['valid_npoc']} / {audit_res['total_symbols']}")
        self.assertEqual(audit_res['valid_npoc'], 3, "Sentinel tüm paritelerdeki nPOC seviyelerini tanımalıdır!")
        self.assertTrue(audit_res['is_healthy'])
        print("  [BAŞARILI] VDA-38: Aegis Sentinel nPOC kontrolü çözüldü.")

    def test_13_shannon_market_entropy(self):
        """
        [KANIT]: Dinamik Shannon Piyasa Entropisinin Mum Akışından Hatasız Hesaplanması.
        """
        from indicators import calculate_shannon_market_entropy

        # Senaryo A: Homojen, dengeli tahta ve düzenli hacim akışı (Yüksek Entropi)
        df_uniform = pd.DataFrame({
            'close': [100.0 + (i % 2) * 0.1 for i in range(30)],
            'volume': [1000.0 for _ in range(30)],
            'quote_volume': [100000.0 for _ in range(30)]
        })
        res_uniform = calculate_shannon_market_entropy(df_uniform, {'bid_price': 100, 'bid_qty': 10, 'ask_price': 100.1, 'ask_qty': 10})
        print(f"  > Homojen Akış Entropisi: {res_uniform['entropy_norm']:.3f} (is_healthy_deep: {res_uniform['is_healthy_deep']})")
        self.assertGreaterEqual(res_uniform['entropy_norm'], 0.70)

        # Senaryo B: Tek bir mumda devasa hacim şoku ve tek duvar yoğunlaşması (Düşük Entropi / Kristalleşme)
        df_shock = pd.DataFrame({
            'close': [100.0 for _ in range(29)] + [108.0],
            'volume': [10.0 for _ in range(29)] + [10000.0],
            'quote_volume': [1000.0 for _ in range(29)] + [1080000.0]
        })
        res_shock = calculate_shannon_market_entropy(df_shock, {'bid_price': 100, 'bid_qty': 500, 'ask_price': 100.1, 'ask_qty': 5}, iceberg_ratio=15.0)
        print(f"  > Şok / Kristal Entropisi: {res_shock['entropy_norm']:.3f} (is_crystalline: {res_shock['is_crystalline']})")
        self.assertLess(res_shock['entropy_norm'], 0.60)
        print("  [BAŞARILI] Dinamik Shannon Piyasa Entropisi mum ve derinlik akışından organik hesaplanıyor.")


if __name__ == '__main__':
    unittest.main()
