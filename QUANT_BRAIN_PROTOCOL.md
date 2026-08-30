# 🧠 VALKYRIE QUANT DESK — 360° ADLİ ANALİZ PROTOKOLÜ

Bu protokol, kullanıcı yeni bir Excel raporu yüklediğinde veya `"analiz et"` dediğinde devreye giren **8 Boyutlu Kurumsal Quant Denetim Standardıdır.**

---

## 🏛️ 360 DERECE ANALİZİN 8 TEMEL BOYUTU

1. **📊 Payoff & Komisyon Vektörü:**
   * Ortalama Kazanç ($) vs Ortalama Kayıp ($) ➔ Payoff Ratio ($>1.30x$ hedefi).
   * Brüt Kâr vs Borsa Komisyonu oranı (Komisyon erozyonu teşhisi).
2. **⏱️ Temporal / Süre Vektörü (Hold Duration):**
   * İşlemlerin sürelere göre (0-15dk, 15-60dk, 1-3saat, >3saat) Win Rate dağılımı.
   * Zaman aşımı ve yatayda bayatlama analizleri.
3. **🔄 Retracement & Trajectory Vektörü (MFE vs MAE):**
   * Kâra geçip sonradan dönen işlemler (MFE > %5 ROE görüp stop olanlar).
   * 0 MFE ile anında tersine dönen sahte kırılımlar (Fakeout).
4. **🛡️ Fitil & Price Action Vektörü (`Fitil Oranı %`):**
   * Pusu setup'larında (S3, R3, nPOC) alt/üst fitil bırakma oranı vs Win Rate korelasyonu.
5. **🧬 Coin DNA & Persona Vektörü:**
   * 100 Coini 4 arketipe ayırma:
     * 👑 Altın Pusu Ustaları (Mean Reversion Queens)
     * 🚀 Trend & Runner Boğaları (Breakout Kings)
     * ⚪ Standart / Yatay Karakter
     * ⚠️ Volatil Whipsaw (Tuzakçılar)
6. **🔬 Setup & Formasyon Matrisi:**
   * 10 Setup'ın ayrı ayrı PnL, Win Rate ve komisyon yükü tablosu.
7. **📱 Anlık Canlı Açık Pozisyon Telemetrisi:**
   * Canlıdaki açık işlemlerin kâr/zarar, Breakeven kilit durumu ve risk sınırları.
8. **🎯 Reçete ve Optimizasyon Eylemleri:**
   * Matematiksel bulgulara dayalı net, uygulanabilir kural önerileri.

---

## 🚀 ÇALIŞTIRMA KOMUTU
Kullanıcı yeni bir Excel raporu sunduğunda tek bir komutla tam rapor üretilir:
```bash
python quant_brain.py
```
