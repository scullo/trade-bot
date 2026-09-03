# 🦅 VALKYRIE QUANT SYSTEM MANUAL (A'DAN Z'YE SİSTEM KILAVUZU)

> **DİKKAT (TÜM GELİŞTİRİCİLER VE YAPAY ZEKA ASİSTANLARI İÇİN):**
> Bu belge, Valkyrie Quant Trade Bot'un mimarisini, sunucu altyapısını, veri akışını ve operasyonel kurallarını eksiksiz olarak tanımlar. Sisteme müdahale etmeden önce bu dokümanı **MUTLAKA** okuyun.

---

## 🏛️ 1. ALTYAPI, BULUT SUNUCU VE DEPLOYMENT MİMARİSİ

### 1.1. Bot Nerede Çalışıyor?
* **Canlı Sunucu (Cloud):** Bot, **Render.com** bulut platformunda (Web Service / Background Worker) 7/24 kesintisiz çalışmaktadır.
* **Lokal Bilgisayar (Desktop):** Kullanıcının yerel bilgisayarı (`c:\Users\aucar\Desktop\trade-bot`), geliştirme, kod denetimi ve lokal analiz amacıyla kullanılır. Canlı bot lokalde DEĞİL, Render üzerinde çalışır.

### 1.2. GitHub Entegrasyonu ve Otomatik Deploy (CRITICAL ⚠️)
* **GitHub Deposu:** `https://github.com/scullo/trade-bot` (Branch: `main`)
* **Auto-Deploy Tetikleyicisi:** Render, GitHub `main` branch'ine yapılan her `git push` işleminde sunucuyu **otomatik olarak yeniden derler (re-deploy) ve yeniden başlatır (restart).**
* **ALTIN KURAL:** Kullanıcı açıkça *"Kodu GitHub'a pushla / Render'a gönder"* demediği sürece **ASLA `git push` YAPILMAZ.** Aksi halde canlıda çalışan işlemler, soket bağlantıları ve hafıza state'i kesintiye uğrar!

### 1.3. Render Kaynak Kısıtları & "Site Dönüyor" Açıklaması
* **RAM Sınırı (512 MB):** Render Free/Starter planında 512 MB RAM sınırı vardır. Bellek aşımı (OOM - Exit Code 137) olmaması için:
  * `memory_watchdog()` 60 saniyede bir `gc.collect()` çalıştırır.
  * 5M mum dizileri maksimum 300 satırda tutulur (`df.iloc[-300:]`).
  * Excel raporu üretimi `tempfile` streaming ile RAM tüketmeden diske yazılır.
* **Uyku Modu (Cold Start / Spin Down):** Render, 15 dakika boyunca web paneline trafik gelmezse konteyneri uykuya alır. Kullanıcı siteye girdiğinde sunucunun uyanması, 100 pariteyi Binance'ten belleğe alması **60-90 saniye** sürer. Bu süreçte tarayıcıda site "döner" (loading); bu bir arıza değil, Render'ın uyku mekanizmasıdır.

---

## 🔄 2. VERİ KALICILIĞI VE SENKRONİZASYON (DATA PERSISTENCE)

### 2.1. İşlem Geçmişi (`trade_history.json`)
* Canlı bot işlemleri açtıkça/kapattıkça Render sunucusunun diskine/belleğine `trade_history.json` olarak kaydeder.
* **GitHub Otomatik Senkronizasyonu (`paper_trader.py`):**
  * `GITHUB_TOKEN` ortam değişkeni tanımlı olduğunda, bot her işlem kapanışında `_push_to_github()` metodunu arka planda (ayrı thread) çalıştırarak `trade_history.json` dosyasını GitHub API üzerinden repoya yedekler.
* **Lokal Dosya Neden Eski Kalabilir?**
  * Kullanıcının bilgisayarındaki lokal `trade_history.json`, en son `git pull` yapıldığı ana aittir. Canlıdaki son işlemleri görmek için dosyayı Render panelinden indirmek veya repodan `git pull origin main` ile çekmek gerekir. Lokal dosyayı boş veya eski görmek botun çalışmadığı anlamına GELMEZ.

---

## 📡 3. BİNANCE PİYASA VERİ MOTORU (`market_data.py`)

* **Milisaniyelik Fiyat Akışı:** Binance Vadeli İşlemler `wss://fstream.binance.com/ws/!bookTicker` WebSocket kanalına bağlıdır. Tüm coinlerin bid/ask ortalaması milisaniyelik akar.
* **5M Mum Kapanış Akışı:** Pariteler 25'erli paketler (chunk) halinde `wss://fstream.binance.com/stream?streams=...` ile dinlenir.
* **Yedek REST Polling:** Herhangi bir soket kopmasında 25 eşzamanlı `asyncio.Semaphore` ile Binance Futures FAPI REST uç noktalarından son mumlar taranır.

---

## 🧠 4. İNDİKATÖR VE SEVİYE HESAPLAMA MOTORU (`indicators.py`)

Bot, kurumsal seviyede 4 ana analitik katman hesaplar:
1. **Camarilla Pivots:** 1D UTC 00:00 mumuna göre R3, R4, R5 (Dirençler/Hedefler) ve S3, S4, S5 (Destekler/Hedefler) + P (Ana Pivot).
2. **Anchored VWAP (AVWAP):** Son 10 günlük en yüksek swing tepe ve en düşük swing dip noktalarından çıpalanmış hacim ağırlıklı ortalama fiyat.
3. **TradingView Volume Profile & Naked POC:** 144 mumluk (12 saat) dilimlerde henüz fiyatın geri test etmediği (unmitigated) en yoğun hacim seviyeleri (nPOC, nVAH, nVAL).
4. **Gerçek CVD & Kırılım İvmesi (Yeni Eklendi):**
   * **CVD (Taker Buy Ratio):** Binance `taker_quote` / `qav` oranıyla hesaplanan net alıcı/satıcı baskısı yüzdesi (%0 - %100).
   * **Kırılım İvmesi (Candle Velocity):** Kırılım mum gövdesi / ATR USD oranı ($x$ kat hız).

---

## 🛡️ 5. STRATEJİ VE İŞLEM YÜRÜTME MOTORU (`strategy.py`)

### 5.1. Setup Türleri (10 Temel Formasyon)
* Mean-Reversion (Pusu): S3 Destek Sekmesi, R3 Direnç Tepkisi, nPOC Sekmeleri.
* Trend-Following (Kırılım): R4 Breakout (Long), S4 Breakdown (Short), R4 Destek Retest.

### 5.2. İkili Koruma Kalkanı (Sert Stop vs. Yumuşak Stop)
* **Sert Stop (Hard Stop):** `evaluate_tick()` fonksiyonunda milisaniyelik fiyatla anında kontrol edilir. Ani çöküş/pump anında beklemeden pozisyonu keser.
* **Yumuşak Stop (Soft Stop):** `evaluate_candle_close()` fonksiyonunda sadece **5 dakikalık mum kapanışı** seviyenin ötesinde gerçekleşirse devreye girer. Sahte iğnelerden (wick-hunting) korur.

### 5.3. Kâr Alma (Take-Profit)
* **TP1 (%50 Kapatma):** Hedefe ulaşıldığında pozisyonun %50'si nakde döner, kalan yarının stopu anında **Giriş Seviyesine (Breakeven)** çekilir.
* **TP2 (Nihai Hedef):** Kalan %50 nihai seviyede kapatılır veya trailing ile sürülür.

---

## 💼 6. İŞLEM MODLARI VE GÜVENLİK KASASI

1. **Paper Trading (`paper_trader.py`):**
   * 100.000$ sanal kasa, 5x kaldıraç, %0.05 Binance vadeli komisyon simülasyonu.
   * Telemetri ve strateji doğrulama için 7/24 veri toplar.
2. **Live Trading (`live_trader.py`):**
   * Gerçek Binance Vadeli İşlemler hesabı (CCXT Async).
   * **Güvenlik Kasası (`security_vault.py`):** API anahtarları `live_config.json` içinde **AES-256 (enc:...)** şifreli olarak saklanır.
   * **Kaldıraç Emniyet Kilidi:** Binance API'sinden kaldıraç veya marjin modu ayarlanamazsa işlem GÜVENLİ İPTAL edilir, asla kontrolsüz emir gönderilmez.
3. **Yönetici Katmanı (`trader_manager.py`):**
   * Gelen emirleri kullanıcının seçtiği moda (DEMO veya LIVE) yönlendirir.

---

## 🚑 7. KENDİ KENDİNİ ONARMA VE NÖBETÇİ (`aegis_sentinel.py`)

* **Gelişmiş Denetim:** 100 paritedeki indikatör seviyelerinin sıfır olup olmadığını, donmuş soketleri ve açık pozisyonların mantıksal risk tutarlılığını 7/24 tarar.
* **Otomatik İyileştirme (Auto-Healing):** Sapma tespit ettiği anda sessizce ilgili paritenin verilerini REST üzerinden tazeler ve seviyeleri TradingView ile birebir eşitler.

---

## 📊 8. RAPORLAMA VE EXCEL MOTORU (`excel_exporter.py`)

* Tek tıkla veya Telegram üzerinden 8 Sayfalı Kurumsal Excel Raporu üretir:
  1. *Genel Özet & KPI Kartları*
  2. *Tüm İşlemler Ledger*
  3. *Kazananlar & Kaybedenler Ayrımı*
  4. *Strateji & Setup Matrisi*
  5. *Coin DNA Laboratuvarı*
  6. *Fakeout & Tuzak Laboratuvarı*
  7. *Ayrışma & Göreceli Güç (RS / CVD)*
  8. *Saat & Seans Dağılımı*

---

## ⚠️ 9. GELİŞTİRİCİLER İÇİN KATI PROTOKOL KURALLARI

1. **Render'a push yapmadan önce kullanıcıdan teyit al.**
2. **Kullanıcı 'veriler doğru mu' dediğinde önce verinin kaynağını (Render mı lokal mi) sorgula; lokal eski diye canlı durdu sanma.**
3. **Hafta sonuna kadar strateji filtrelerini (Short kalkanı vb.) kapalı tutarak saf/filtresiz veri toplamaya izin ver.**
4. **Kodda asla sessizce yutulan `except: pass` blokları bırakma; kritik yerleri güvenli iptalle sonlandır.**
