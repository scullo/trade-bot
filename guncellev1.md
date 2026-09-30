# VALKYRIE QUANT REFORM PROTOKOLÜ: GUNCELLEV1
# 5 Aşamalı Doğrulamalı ve Kanıt Odaklı Cerrahi Sistem Güncelleme Rehberi

**Tarih:** 2026-09-29  
**Hedef Sistem:** Valkyrie Algoritmik Ticaret Motoru (`trade-bot`)  
**Kapsam:** 38 Maddelik Büyük Kuant Denetim Kütüğü (VDA-01 ila VDA-38)  
**Çalışma İlkesi:** **"Önce Kodu Yaz $\rightarrow$ Özel Testle Kanıtla $\rightarrow$ Konsol Çıktısını Raporla $\rightarrow$ Onay Alınca Bir Sonraki Aşamaya Geç"**

---

## 🧭 GENEL MİMARİ BAĞIMLILIK VE İŞLEYİŞ KURALLARI

1. **Bağımlılık Zinciri Asla Kırılamaz:**
   - Bir aşamanın kodlaması tamamlanmadan ve doğrulama testi **%100 başarılı** olmadan sonraki aşamaya geçilemez.
   - Sıralama: **Aşama 1 (Veri & Bellek)** $\rightarrow$ **Aşama 2 (Göstergeler)** $\rightarrow$ **Aşama 3 (Setuplar & Stoplar)** $\rightarrow$ **Aşama 4 (Taksonomi & Kalibratör)** $\rightarrow$ **Aşama 5 (PaperTrader & Kasa Güvenliği)**.
2. **Sıfır Regresyon Güvencesi (Zero-Regression Rule):**
   - Her aşamanın ardından projenin mevcut omurga testi olan `test_blueprint_system_integrity.py` çalıştırılacak ve **7/7 testin eksiksiz geçtiği** tescillenecektir.
3. **Özel Kanıt Betikleri (Proof Scripts):**
   - Her aşama için bağımsız bir test dosyası (`test_phaseX_proof.py`) oluşturulacak, matematiksel ve operasyonel çıktılar konsola dökülerek doğrulanacaktır.
4. **Kullanıcı Tetikleyici Komutu:**
   - Kullanıcı *"aşama 1 i kodla"*, *"aşama 2 yi kodla"* gibi komutlar verdiğinde doğrudan ilgili aşamadaki dosyalara cerrahi müdahale yapılacak, testler çalıştırılacak ve kanıt raporu sunulacaktır.

---

## 🏛️ AŞAMA 1: Temel Veri Akışı, Bellek ve Mum Bütünlüğü (9 Madde)

> **Hedef:** Tüm göstergelerin ve seviyelerin dayandığı 5M/1D veri akışını, kline bellek tamponlarını ve WebSocket/REST dönüşümlerini kusursuzlaştırmak.

### 1. Düzeltilecek Maddeler ve Dosya Konumları:
- **[VDA-34] `main.py` (Satır 62-68):**
  - *Mevcut Durum:* `memory_and_sync_watchdog` her 60s'de `candles_5m` verisini zorla `iloc[-150:]` olarak budamakta, bu da 12.5 saat sonrasında (öğleden sonra) Asya seansını tamamen silmektedir.
  - *Düzeltme:* Bellek sınırı en az 300 muma (25 saat) çıkarılacak. Asya seansı mumları (00:00 - 08:00 UTC) gün bitimine kadar bellekte kilitlenecek.
- **[VDA-10] `market_data.py` (Satır 2098, 2340):**
  - *Mevcut Durum:* 200 mumluk sınır akşam saatlerinde Asya seansını silmektedir.
  - *Düzeltme:* Buffer boyutu 300 muma yükseltilecek.
- **[VDA-01] `market_data.py` (Satır 2275-2293):**
  - *Mevcut Durum:* 5M mum geçişinde `t_buy` ve `t_sell` borsa tarafından sıfırlandığı için kayan 60s CVD 60 saniye boyunca sıfıra düşüp kör kalmaktadır.
  - *Düzeltme:* Önceki mumun son kümülatif değeri ofset (`base_offset`) olarak eklenerek continuous (kesintisiz) 60s CVD penceresi oluşturulacak.
- **[VDA-02] `market_data.py` (Satır 2083-2088):**
  - *Mevcut Durum:* Auto-heal eksik mum tamamlarken boş mumlara $O=H=L=C$ yazmakta, ATR ve volatilite geometrisini bozmaktadır.
  - *Düzeltme:* Eksik mum önceki mumun kapanışına küçük bir ATR gürültüsü eklenerek veya hacimsiz nötr doji olarak doğru geometriyle üretilecek.
- **[VDA-03] `market_data.py` (Satır 993-997):**
  - *Mevcut Durum:* 1D günlük mum çekilemediğinde 5M mumu 1D kopyalanmakta ve Camarilla pivotları %80 daralarak sahte kırılımlar tetiklemektedir.
  - *Düzeltme:* 1D fallback durumunda 5M mumu doğrudan 1D yapılmayacak; eldeki son 288 adet 5M mumunun sentetik High, Low, Close değerleri birleştirilerek gerçekçi günlük mum türetilecek.
- **[VDA-04] `market_data.py` (Satır 2620-2628):**
  - *Mevcut Durum:* Bybit USD vs Gate.io kontrat lotu birim uyuşmazlığı OI Velocity radarında sahte $\pm\%800$ patlamalara yol açmaktadır.
  - *Düzeltme:* Gate.io kontrat lotları, paritenin `multiplier` değeriyle çarpılarak USD bazına normalize edilecek.
- **[VDA-05] `market_data.py` (Satır 1716-1725):**
  - *Mevcut Durum:* Gate.io JIT L2 derinlik hesabı kontrat çarpanını unuttuğu için tahta derinliği 10,000 kat sapmaktadır.
  - *Düzeltme:* `depth_contract_multiplier` JIT L2 derinlik hesabına entegre edilecek.
- **[VDA-06] `market_data.py` (Satır 2116-2130):**
  - *Mevcut Durum:* WebSocket `symbol_map` içinde meme coin çarpanları (`1000PEPE`, `1000BONK`, `1000FLOKI`) eksik olduğundan bu veriler REST poller'a düşmektedir.
  - *Düzeltme:* Tüm 1000x ve 1M coinler haritaya eklenecek.
- **[VDA-07] `market_data.py` (Satır 2449-2455):**
  - *Mevcut Durum:* 15 dakikalık tasfiyeler asla silinmediği için kalıcı tasfiye vetosu oluşmaktadır.
  - *Düzeltme:* `time.time() - 900` saniyeden eski tasfiyeler her döngüde `deque` içinden budanacak.

### 🧪 Aşama 1 Kanıt ve Kontrol Protokolü (`test_phase1_data_memory_proof.py`):
1. **Asya Seansı Koruma Testi:** Saat 18:00 UTC simülasyonu yapılacak. 300 mumluk hafızada saat 00:00 - 08:00 UTC arasındaki en yüksek ve en düşük değerlerin kaybolmadığı doğrulanacak (`assert asia_high > 0 and asia_low > 0`).
2. **CVD Rollover Süreklilik Testi:** Mum geçişinde delta serisinin sıfıra düşmediği, bir önceki mumun son hacmini devralarak akışın sürdüğü test edilecek.
3. **Kontrat Normalizasyon Testi:** Gate.io PEPE lotu ile Bybit USD büyüklüğü kıyaslanacak; aradaki farkın <%1 olduğu kanıtlanacak.
4. **Regresyon Testi:** `python -m unittest test_blueprint_system_integrity.py` $\rightarrow$ 7/7 Geçiş!

---

## 📐 AŞAMA 2: Matematiksel Göstergeler ve Kuant Alfa Motoru (12 Madde)

> **Hedef:** Finansal matematik, bilgi teorisi ve fraktal formüllerindeki hesaplama, ölçek ve yön hatalarını gidermek.

### 1. Düzeltilecek Maddeler ve Dosya Konumları:
- **[VDA-22] `indicators.py` (Satır 348-383):**
  - *Mevcut Durum:* Hurst exponent R/S analizi ham fiyatlara ($P_t$) uygulandığı için rastgele yürüyüşte dahi $H \approx 0.95$ vermektedir (Mandelbrot kalkanı felç).
  - *Düzeltme:* R/S analizi log-getiriler ($r_t = \ln(P_t / P_{t-1})$) üzerine kurulacak. Brownian motion için $H \approx 0.50$ üretecektir.
- **[VDA-23] `indicators.py` (Satır 895-911):**
  - *Mevcut Durum:* `'taker_buy_volume'` sütun adı aranmakta, bulunamayınca kaba mum gövdesi tahminine düşmektedir.
  - *Düzeltme:* Sütun adı `'taker_base'` (veya `'taker_quote'`) olarak güncellenecek, gerçek borsa akışı bağlanacak.
- **[VDA-24] `indicators.py` (Satır 823-830):**
  - *Mevcut Durum:* Stoikov mikro-fiyat kayması için sabit $1.2\text{ bps}$ aranmakta; spread'i $0.01\text{ bps}$ olan BTC/ETH'de bu eşik imkânsız olduğu için sinyal kalıcı olarak `False` kalmaktadır.
  - *Düzeltme:* Eşik paritenin kendi ortalama spread oranına endekslenecek: `threshold = max(0.5, spread_bps * 0.40)`.
- **[VDA-25] `indicators.py` (Satır 311-325) & `strategy.py` (Satır 2931-2935):**
  - *Mevcut Durum:* 20 kademeye eşit dağılmış derin likidite $S_{\text{norm}} \ge 0.88$ verdiği için "kaotik" denilerek en kaliteli tahtalar veto edilmektedir.
  - *Düzeltme:* Entropi mantığı düzeltilecek: $S_{\text{norm}} \ge 0.80$ "Derin & Sağlıklı Likidite Dağılımı", $S_{\text{norm}} < 0.40$ "Anormal Yoğunlaşma / Tek Duvar Riski" olarak yeniden sınıflandırılacak.
- **[VDA-26] `indicators.py` (Satır 230-235):**
  - *Mevcut Durum:* Naked lines fallback mantığında `above_npoc = max_p * 0.995` fiyatın altına düşebilmekte, direnç seviyesi destek haline gelmektedir.
  - *Düzeltme:* Kesin yönsel kural: `above_npoc = max(current_price * 1.003, fallback)`, `below_npoc = min(current_price * 0.997, fallback)`.
- **[VDA-27] `indicators.py` (Satır 1131-1139):**
  - *Mevcut Durum:* Deribit Gamma Flip kümülatif strike toplamında ilk pozitif strike'ta döngüyü kırmakta, spot $65k$ iken flip $15k$ çıkmaktadır.
  - *Düzeltme:* Net GEX'in işaret değiştirdiği gerçek sıfır kesişim strike'ı enterpolasyon ile bulunacak.
- **[VDA-28] `indicators.py` (Satır 1247-1259):**
  - *Mevcut Durum:* Hawkes çığ modelinde dallanma oranı $\eta = \alpha/\beta$ formülü anlık yoğunlukla karıştırılarak yapay sayılarla çarpılmaktadır.
  - *Düzeltme:* Hawkes parametreleri teorik standarda getirilecek; eski sönmüş tasfiyelerin sahte veto üretmesi engellenecek.
- **[VDA-29] `indicators.py` (Satır 108-118):**
  - *Mevcut Durum:* Hacim profili Değer Alanı döngüsünde iki taraf da 0 hacim olduğunda sürekli yukarı genişleme asimetrisi vardır.
  - *Düzeltme:* Eşitlik durumunda POC'ye olan yakınlık gözetilecek ve iki yönlü dengeli genişleme sağlanacak.
- **[VDA-30] `indicators.py` (Satır 975-1015):**
  - *Mevcut Durum:* Kyle's Lambda henüz açılmış canlı mumun sığ hacmini geçmiş 5 dakikalık tam mumlarla kıyaslayıp sahte hava cebi tuzağı üretmektedir.
  - *Düzeltme:* Açık mumun geçen saniyesine göre hacim ekstrapolasyonu yapılacak veya sadece kapanmış barlar kıyaslanacak.
- **[VDA-31] `indicators.py` (Satır 610-630):**
  - *Mevcut Durum:* CVD ivmesi mum sıfırlamasında basamak süreksizliği sebebiyle Dirac-Delta sahte ivme patlamaları üretmektedir.
  - *Düzeltme:* Sürekli kümülatif CVD serisi üzerinden sayısal türev alınacak.
- **[VDA-33] `indicators.py` (Satır 12-18):**
  - *Mevcut Durum:* Volatiliteli günlerde ($H/L > 2$) Camarilla $S_5 = 2C - R_5$ negatif fiyat üretmektedir.
  - *Düzeltme:* $S_5 = \max(close \times 0.05, 2 \times close - r5)$ taban koruması eklenecek.
- **[VDA-38] `aegis_sentinel.py` (Satır 52-55):**
  - *Mevcut Durum:* Sentinel seviye sözlüğünde `npoc` anahtarını aramakta, bulamayınca 100 paritede nPOC'u bozuk raporlamaktadır.
  - *Düzeltme:* `above_npoc` ve `below_npoc` float kontrollerine uyarlanacak.

### 🧪 Aşama 2 Kanıt ve Kontrol Protokolü (`test_phase2_indicators_proof.py`):
1. **Mandelbrot Log-Getiri Kanıtı:** 10,000 sentetik adımlı Brownian Motion serisinde Hurst değerinin $0.50 \pm 0.04$ bandında çıktığı, trendli seride $>0.55$, ortalamaya dönen seride $<0.45$ olduğu ispatlanacak.
2. **Yönsel Seviye Doğrulama Assertion:** 100 parite üzerinde sentetik döngü koşturulup `above_npoc > current_price > below_npoc` kuralının %100 sağlandığı kanıtlanacak.
3. **VPIN & Stoikov Gerçek Veri Testi:** Gerçek mum verisi verilerek VPIN'in `taker_base`'i okuduğu ve BTC'de Stoikov drift sinyalinin tetiklenebildiği gösterilecek.
4. **Regresyon Testi:** `python -m unittest test_blueprint_system_integrity.py` $\rightarrow$ 7/7 Geçiş!

---

## 🎯 AŞAMA 3: Trade Setupları, Stop Geometrisi ve Giriş Kuralları (11 Madde)

> **Hedef:** 16 işlem kurulumunun giriş, stop, kâr alma ve teyit mantıklarını kurumsal risk standartlarına kavuşturmak.

### 1. Düzeltilecek Maddeler ve Dosya Konumları:
- **[VDA-14] `strategy.py` (Satır 4190, 4365, 4505, vb.):**
  - *Mevcut Durum:* LONG işlemlerinde stop seviyesi `max(support - buffer, close * 0.9950)` ile desteğin *ÜSTÜNE* kelepçelenmekte; fiyat desteğe varmadan işlem stop olmaktadır (`SETUP 3, 5, 9, 14, 15, 16`).
  - *Düzeltme:* Kelepçe kaldırılacak. Stop mutlak suretle desteğin altında konumlanacak: `soft_stop = min(support - buffer, close * 0.9920)`.
- **[VDA-15] `strategy.py` (Satır 4270, 4420, 4610, vb.):**
  - *Mevcut Durum:* SHORT işlemlerinde stop seviyesi `min(resist + buffer, close * 1.0025)` ile direncin *ALTINA* kelepçelenmekte; fiyat dirence çarpmadan erken stop olmaktadır (`SETUP 4, 7, 10, 11, 13`).
  - *Düzeltme:* Kelepçe kaldırılacak. Stop mutlak suretle direncin üstünde konumlanacak: `soft_stop = max(resist + buffer, close * 1.0080)`.
- **[VDA-16] `strategy.py` (Satır 3773, 3865):**
  - *Mevcut Durum:* SETUP 3 ve 4 içindeki %0.25 dar stop gürültüde patlamaktadır.
  - *Düzeltme:* Dinamik ATR tabanlı en az %0.60 nefes payı tanımlanacak.
- **[VDA-18] `strategy.py` (Satır 2745-2755):**
  - *Mevcut Durum:* `_handle_open` içindeki `swing_stop` mantığı kurulumun hesapladığı kurumsal seviye stopunu ezmektedir.
  - *Düzeltme:* Kurulum yapısal bir seviye stopu vermişse `swing_stop` bunu ezemeyecek.
- **[VDA-19] `strategy.py` (Satır 4192-4200):**
  - *Mevcut Durum:* SETUP 5 R4 Support Flip içinde `tp2` runner hedefi tanımsızdır.
  - *Düzeltme:* TP2 hedefi `target_r5` veya `mvah * 1.015` olarak bağlanacak.
- **[VDA-20] `strategy.py` (Satır 4200):**
  - *Mevcut Durum:* Retest setuplarında sabit 2 elemanlı confluence listesi yüzünden KORU paritelerinde 3+ teyit şartı sağlanamayıp işlemler veto edilmektedir.
  - *Düzeltme:* Seviye testi, hacim onayı ve emir defteri teyitleri dinamik olarak listeye eklenecek.
- **[VDA-21] `strategy.py` (Satır 4766-4780, 5016-5030):**
  - *Mevcut Durum:* Fakeout Reclaim sniper setuplarında SHORT kurulumlara LONG etiketleri verilmiştir.
  - *Düzeltme:* SETUP 11 SHORT, SETUP 16 LONG etiketleri düzeltilecek.
- **[VDA-32] `strategy.py` (Satır 3098-3105):**
  - *Mevcut Durum:* `calculate_cvd_divergence` ve `calculate_macro_dominance_bias` sinyalleri sadece log yazmakta, filtreleme yapmamaktadır.
  - *Düzeltme:* Vampir BTC rejiminde altcoin LONG işlemleri, Ayı uyumsuzluğunda ise Breakout işlemleri kapıda veto edilecek.
- **[VDA-08] `strategy.py` (Satır 1539-1545):**
  - *Mevcut Durum:* Coinbase Lead-Lag fiyatı donduğunda tüm kırılımlar kilitlenmektedir.
  - *Düzeltme:* 60 saniyeden eski Coinbase verisinde bypass devreye girecek.
- **[VDA-09] `strategy.py` (Satır 1530):**
  - *Mevcut Durum:* Coinbase 8 bps eşiği normal USDT/USD oynamalarında sahte tetiklenmektedir.
  - *Düzeltme:* USDT/USD paritesi anlık sapmadan arındırılacak.
- **[VDA-11] `market_data.py` (Satır 1765):**
  - *Mevcut Durum:* %0.08 fiyat kayması toleransı volatil coinlerde duvar yaşını sıfırlamaktadır.
  - *Düzeltme:* Fiyat toleransı paritenin ATR'sinin %10'u olarak dinamikleştirilecek.

### 🧪 Aşama 3 Kanıt ve Kontrol Protokolü (`test_phase3_setups_geometry_proof.py`):
1. **16 Setup Geometri Matrisi Testi:** Tüm 16 kurulum sentetik fiyatlarla simüle edilecek.
   - LONG işlemlerinde: $\text{Stop} < \text{Destek} \le \text{Giriş} < \text{TP1} < \text{TP2}$
   - SHORT işlemlerinde: $\text{Stop} > \text{Direnç} \ge \text{Giriş} > \text{TP1} > \text{TP2}$
   - Tüm işlemlerde $R:R \ge 1.85$ ve $\text{Stop Mesafesi} \ge \%0.60$ olduğu doğrulanacak.
2. **Vampir BTC Veto Testi:** BTC yükselirken altcoin düşüş senaryosu verilecek; altcoin LONG işleminin kapıda veto edildiği kanıtlanacak.
3. **Regresyon Testi:** `python -m unittest test_blueprint_system_integrity.py` $\rightarrow$ 7/7 Geçiş!

---

## 🧬 AŞAMA 4: Setup Taksonomisi, Gölge Sistem ve Otonom Kalibratör Hizalaması (2 Madde)

> **Hedef:** `strategy.py`, `shadow_engine.py` ve `autonomous_dna_calibrator.py` arasındaki kurulum isimlendirmelerini ve yönlerini %100 birebir eşitlemek.

### 1. Düzeltilecek Maddeler ve Dosya Konumları:
- **[VDA-17] `shadow_engine.py` (Satır 1133-1172) & `autonomous_dna_calibrator.py` (Satır 455-465, 566-575):**
  - *Mevcut Durum:* SETUP 5 - 16 arasındaki kurulum adları ve yönleri `strategy.py` ile tamamen uyumsuzdur. S4 Breakdown SHORT kurulurken gölge motoru MVAH Breakout LONG görmekte; kalibratör birini sessize aldığında diğeri felç olmaktadır.
  - *Düzeltme:* `extract_canonical_setup` fonksiyonu `strategy.py`'deki 16 kurulumun adları ve yönleriyle birebir eşleştirilecek:
    - `SETUP_5_R4_SUPPORT_FLIP` (LONG)
    - `SETUP_6_MVAH_BREAKOUT` (LONG)
    - `SETUP_7_S4_BREAKDOWN` (SHORT)
    - `SETUP_8_MVAL_BREAKDOWN` (SHORT)
    - `SETUP_9_BELOW_NPOC_BOUNCE` (LONG)
    - `SETUP_10_ABOVE_NPOC_REJECTION` (SHORT)
    - `SETUP_11_FAKEOUT_RECLAIM_SHORT` (SHORT)
    - `SETUP_12_PDL_SWEEP_RECLAIM_LONG` (LONG)
    - `SETUP_13_ASIA_SWEEP_SHORT` (SHORT)
    - `SETUP_14_ASIA_SWEEP_LONG` (LONG)
    - `SETUP_15_PDH_SWEEP_RECLAIM_SHORT` (SHORT)
    - `SETUP_16_FAKEOUT_RECLAIM_LONG` (LONG)
- **[VDA-12] `market_data.py` (Satır 2680-2690):**
  - *Mevcut Durum:* Gölge motoruna sembol gönderilirken `1000PEPE` ile `PEPE` uyuşmazlığı vardır.
  - *Düzeltme:* Sembol normalizasyonu standartlaştırılacak.

### 🧪 Aşama 4 Kanıt ve Kontrol Protokolü (`test_phase4_taxonomy_calibrator_proof.py`):
1. **Birebir Taksonomi Eşleşme Testi (Bijective Mapping):** `strategy.py` içindeki 16 setup ID'si döngüye sokulacak; gölge motorunun ürettiği kanonik isimlerin ve yönlerin %100 örtüştüğü kanıtlanacak (`assert len(unmatched) == 0`).
2. **Sessize Alma (Muting) İzolasyon Testi:** Kalibratörün `SETUP_7_S4_BREAKDOWN` kurulumunu uyuttuğu bir senaryoda `SETUP_6_MVAH_BREAKOUT` kurulumunun açık kaldığı test edilecek.
3. **Regresyon Testi:** `python -m unittest test_blueprint_system_integrity.py` $\rightarrow$ 7/7 Geçiş!

---

## 🛡️ AŞAMA 5: Paper Trader, Marjin Bütünlüğü ve Kasa Güvenliği (4 Madde)

> **Hedef:** Tüm sinyalleri ve işlemleri paraya çeviren yürütme motorunu (PaperTrader) ve asenkron marjin yönetimini kurumsal güvenlik zırhına almak.

### 1. Düzeltilecek Maddeler ve Dosya Konumları:
- **[VDA-35] `strategy.py` (Satır 1912, 2523, 2586):**
  - *Mevcut Durum:* Asenkron `_handle_open` içinde `self.margin_multiplier` nesne özelliği kullanıldığı için eşzamanlı pozisyon açılışlarında pariteler arası marjin çarpanı bulaşması (Race Condition) yaşanmaktadır.
  - *Düzeltme:* Marjin çarpanı yerel değişken (`local_margin_mult = 1.0`) haline getirilecek; fonksiyon içinde parametre olarak taşınacak.
- **[VDA-36] `paper_trader.py` (Satır 603-750):**
  - *Mevcut Durum:* `close_position` içinde Multiplier Guard bulunmamaktadır. `1000PEPE` ($0.008$) spot `PEPE` ($0.000008$) fiyatıyla kapatıldığında kasaya sahte %99.9 zarar yazılmaktadır.
  - *Düzeltme:* `update_tick_telemetry` içindeki Multiplier Guard mantığı `close_position` fonksiyonuna da eklenecek.
- **[VDA-37] `paper_trader.py` (Satır 625, 745):**
  - *Mevcut Durum:* İzole marjin tasfiye (Liquidation Engine) mekanizması yoktur. Fiyat çöktüğünde pozisyon marjinden fazla zarar yazabilmektedir.
  - *Düzeltme:* İzole marjin tasfiye tavanı eklenecek: Kayıp pozisyona yatırılan marjini aşamaz (`net_pnl = max(-margin, gross_pnl - fees)`). Gerçekçi slippage modeli entegre edilecek.
- **[VDA-13] `paper_trader.py` (Satır 753-757):**
  - *Mevcut Durum:* Bakiye $1,000 altına indiğinde otomatik $10,000'e sıfırlanarak gerçek drawdown gizlenmektedir.
  - *Düzeltme:* Kasa sıfırlaması sadece yetkili API isteğiyle yapılabilecek; sistem otomatik sıfırlama yerine güvenli durdurma moduna geçecek.

### 🧪 Aşama 5 Kanıt ve Kontrol Protokolü (`test_phase5_papertrader_safety_proof.py`):
1. **Eşzamanlılık Yarış Testi (Concurrency Stress Test):** `asyncio.gather` ile aynı milisaniyede 10 paritede pozisyon açılacak; marjin çarpanlarının birbirini ezmediği ispatlanacak.
2. **Meme Coin 1000x Kapanış Testi:** `1000PEPE` işlemi spot $0.000008$ fiyatıyla kapatılacak; Multiplier Guard'ın devreye girip kasayı sahte tasfiyeden koruduğu kanıtlanacak.
3. **Tasfiye Tavan Testi:** %90 çöken bir coin simüle edilecek; yazılan zararın pozisyon teminatını (örneğin $50$) aşamadığı test edilecek.
4. **Büyük Final Bütünlük Testi:** Tüm test kütüphanesi (`test_blueprint_system_integrity.py`, `test_capital_management.py`, vb.) çalıştırılacak ve **sıfır hata ile %100 yeşil** raporlanacak.

---

## 📋 KULLANICI YÖNETİM VE TETİKLEME DİZİNİ

Kullanıcı süreci başlatmak için şu komutları verecektir:

| Kullanıcı Komutu | Sistemin Yapacağı İşlem |
| :--- | :--- |
| **"aşama 1 i kodla"** | Aşama 1'deki 9 maddeyi kodlar, `test_phase1_data_memory_proof.py` çalıştırır, kanıtları ve `test_blueprint_system_integrity.py` sonucunu sunar. |
| **"aşama 2 yi kodla"** | Aşama 2'deki 12 maddeyi kodlar, `test_phase2_indicators_proof.py` çalıştırır, matematiksel kanıtları sunar. |
| **"aşama 3 ü kodla"** | Aşama 3'teki 11 maddeyi kodlar, `test_phase3_setups_geometry_proof.py` çalıştırır, 16 setup geometrisini kanıtlar. |
| **"aşama 4 ü kodla"** | Aşama 4'teki 2 maddeyi kodlar, `test_phase4_taxonomy_calibrator_proof.py` çalıştırır, birebir taksonomi örtüşmesini kanıtlar. |
| **"aşama 5 i kodla"** | Aşama 5'teki 4 maddeyi kodlar, `test_phase5_papertrader_safety_proof.py` çalıştırır, nihai kasa güvenliğini ve tam sistem testini tesciller. |

*Bu doküman, sistem üzerinde yapılacak tüm geliştirmelerin bağlayıcı anayasasıdır.*
