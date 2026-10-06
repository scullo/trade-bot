# config.py - Trade Bot Genel Yapilandirmasi
import os

# 1. Takip Edilecek Coinler (Binance USDT Perpetual - Top 100 Hacimli Saf Kripto Parite)
ALL_AVAILABLE_SYMBOLS = [
    # 1 - 10 (Süper Majörler & Mega Likidite)
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "XRP/USDT",
    "ZEC/USDT",
    "ENA/USDT",
    "TRUMP/USDT",
    "DOGE/USDT",
    "BNB/USDT",
    "PEPE/USDT",
    # 11 - 20 (Yüksek Hacimli Popüler Pariteler)
    "PUMP/USDT",
    "SUI/USDT",
    "MOVR/USDT",
    "TAO/USDT",
    "ONG/USDT",
    "ADA/USDT",
    "WLD/USDT",
    "LINK/USDT",
    "UNI/USDT",
    "PENDLE/USDT",
    # 21 - 30 (DeFi & L1/L2 Trend Pariteleri)
    "NEAR/USDT",
    "W/USDT",
    "AAVE/USDT",
    "AVAX/USDT",
    "BICO/USDT",
    "VET/USDT",
    "PENGU/USDT",
    "LTC/USDT",
    "ONDO/USDT",
    "BCH/USDT",
    # 31 - 40 (Meme, Altyapı & Ekosistem)
    "EIGEN/USDT",
    "XPL/USDT",
    "FIL/USDT",
    "TRX/USDT",
    "WIF/USDT",
    "XLM/USDT",
    "INJ/USDT",
    "SHIB/USDT",
    "ASTER/USDT",
    "ZRO/USDT",
    # 41 - 50 (Katman 1 / 2 & Büyüyen Ekosistemler)
    "WLFI/USDT",
    "RUNE/USDT",
    "VIRTUAL/USDT",
    "JUP/USDT",
    "DOT/USDT",
    "STX/USDT",
    "APT/USDT",
    "FET/USDT",
    "JTO/USDT",
    "POL/USDT",
    # 51 - 60 (DeFi, Gaming & Yeni Trendler)
    "ACE/USDT",
    "EDEN/USDT",
    "ETHFI/USDT",
    "DASH/USDT",
    "OP/USDT",
    "ARB/USDT",
    "BONK/USDT",
    "ETC/USDT",
    "DYM/USDT",
    "PYTH/USDT",
    # 61 - 70 (Oracle, DEX & Kurumsal Pariteler)
    "CRV/USDT",
    "HBAR/USDT",
    "KMNO/USDT",
    "ONT/USDT",
    "ATOM/USDT",
    "ORDI/USDT",
    "ALGO/USDT",
    "ENS/USDT",
    "LDO/USDT",
    "TIA/USDT",
    # 71 - 80 (Modüler Blokzincirler & Likidite Havuzları)
    "ICP/USDT",
    "SPK/USDT",
    "BOME/USDT",
    "MANTRA/USDT",
    "HUMA/USDT",
    "KERNEL/USDT",
    "GRAM/USDT",
    "RENDER/USDT",
    "GALA/USDT",
    "SEI/USDT",
    # 81 - 90 (Meme, Web3 & Topluluk Pariteleri)
    "FLOKI/USDT",
    "TURBO/USDT",
    "PORTAL/USDT",
    "MINA/USDT",
    "COTI/USDT",
    "STRK/USDT",
    "CAKE/USDT",
    "DYDX/USDT",
    "MANA/USDT",
    "SAND/USDT",
    # 91 - 100 (Metaverse, DeFi & Klasik L1 Pariteleri)
    "GMX/USDT",
    "AXS/USDT",
    "KAVA/USDT",
    "SNX/USDT",
    "BLUR/USDT",
    "LUNC/USDT",
    "XEC/USDT",
    "NEIRO/USDT",
    "HYPE/USDT",
    "JST/USDT"
]

# Varsayilan baslangicta aktif pariteler (Tum 100 Parite Varsayilan Olarak Aktif)
DEFAULT_ACTIVE_SYMBOLS = ALL_AVAILABLE_SYMBOLS.copy()

SYMBOLS = DEFAULT_ACTIVE_SYMBOLS

# 2. Risk ve Kasa Yonetimi (Elastic Quant Portfolio & Compounding Engine)
INITIAL_BALANCE = 10000.0        # Demo baslangic bakiyesi (USDT)
LEVERAGE = 5                     # Varsayilan temel kaldirac (5x)
DEFAULT_LEVERAGE = LEVERAGE
ENABLE_DYNAMIC_LEVERAGE = True   # Akilli Dinamik Kaldirac Motoru (2x - 5x)
MIN_LEVERAGE = 2                 # Azami defansif kaldirac tabani (Asiri dalgalanma / Dead Zone kalkani)
MAX_LEVERAGE = 5                 # Azami kurumsal kaldirac tavani (Tum paritelerde azami 5x - Asiri risk onleyici)
LEVERAGE_LOW_ATR_THRESHOLD = 0.65   # Dusuk dalgalanma (BTC/ETH gibi agirbasli majorler): 5x
LEVERAGE_HIGH_ATR_THRESHOLD = 1.80  # Yuksek dalgalanma (Meme/Beta): 3x-4x'e dusurulur
LEVERAGE_EXTREME_ATR_THRESHOLD = 2.80 # Asiri dalgalanma: 2x'e sabitlenir (Sermaye zirhi)
POSITION_SIZE_USDT = 300.0       # Kurumsal dengeli baz marjin (300 USDT - 10k kasa standardi)
MAX_OPEN_POSITIONS = 8           # Esnek portfoy tavani: 5 standart, 8'e kadar esnek marjin butcesi
MAX_PORTFOLIO_MARGIN_PCT = 25.0  # Azami toplam kilitli marjin: Kasanin %25'i (10,000$ icin max 2,500$)
ELITE_SLOT_BASE = 5              # Temel kaliteli slot hedefi
ELITE_SLOT_MAX = 8               # Esnek marjin butcesi kapsaminda azami pozisyon siniri
COMMISSION_RATE = 0.0005         # %0.05 Binance vadeli islem komisyon simulasyonu
RISK_EQUITY_PCT = 0.80           # Kasa bakiyesinin %0.80'i islem basi hedef net stop riski (10k icin $80)
MIN_TP1_GAIN_PCT = 0.90          # Komisyon kalkanı: Asgari %0.90 fiyat kârı / 5x'te %4.5 ROE olmadan TP1 tetiklenemez

# 3. Strateji Parametreleri
TIMEFRAME = "5m"                 # Ana islem zaman dilimi
LOOKBACK_DAYS_AVWAP = 10         # Son 10 gunluk tepe/dip AVWAP referansi
BUFFER_RATIO = 0.25              # %25 akilli stop tampon payi
BREAKOUT_HOLD_SECONDS = 60       # Kirilim tutunma teyit suresi (60 saniye)

# 4. Trailing Stop / Kar Koruma Esikleri (Dense Tiered Trailing Engine)
TRAILING_BREAKEVEN_ROE = 2.5     # %2.5 ROE'de Tier 0 breakeven (+%0.30 komisyon korumali ve nefes payli)
TRAILING_LOCK_TIER1_ROE = 3.5    # %3.5 ROE'de Tier 1: +%2.0 ROE net kâr kilit
TRAILING_LOCK_TIER2_ROE = 5.5    # %5.5 ROE'de Tier 2: +%3.5 ROE orta dalga kilit (Giveback Kalkanı)
TRAILING_LOCK_TIER3_ROE = 8.0    # %8.0 ROE'de Tier 3: +%5.5 ROE trend kilit
TRAILING_LOCK_TIER4_ROE = 13.0   # %13.0 ROE'de Tier 4: +%9.0 ROE trend runner kilit
TRAILING_LOCK_TIER5_ROE = 18.0   # %18.0 ROE'de Tier 5: +%13.0 ROE moonbag kilit
TRAILING_LOCK_30_ROE = 13.0      # Geriye dönük uyumluluk alias
TRAILING_LOCK_50_ROE = 18.0      # Geriye dönük uyumluluk alias

# 5. Scalp & Stagnation Zaman Sinirlari
SCALP_MAX_HOLD_CANDLES = 48      # Azami tutma: 48 mum (4 saat)
STAGNATION_CANDLES_MEME = 6      # Yüksek beta / meme paritelerde ivme bekleme süresi: 6 mum (30 dk) (4'ten 6'ya yükseltildi)
STAGNATION_CANDLES_MAJOR = 12    # Majör ve DeFi paritelerde ivme bekleme süresi: 12 mum (60 dk) (8'den 12'ye yükseltildi - Erken kapanış önleyici)

# 6. 4 Kademeli Kuant Reformu (Institutional Stop & Reclaim Engine)
ENABLE_SMART_SWING_STOP = True   # Swing High/Low + 0.5x ATR Akıllı Stop Mimarisi
SWING_LOOKBACK_CANDLES = 12      # Son 1 saatlik (12 mum) yerel tepe/dip iğne referansı
SWING_ATR_BUFFER_MULT = 0.50     # Yerel iğne arkası emniyet tamponu (0.50x ATR)
ENABLE_HMM_SWEEP_SHIELD = True   # Simons HMM Manipülasyon/Stop Avı Kalkanı
HMM_SWEEP_SHIELD_MULT = 1.35     # Manipülasyon anında 1.35x stop nefes payı
ENABLE_LONDON_SWEEP_SHIELD = True# Londra seansı sabah dip/tepe süpürme kalkanı (12:00 - 16:30 UTC+3)
LONDON_SWEEP_SHIELD_MULT = 1.25  # Londra seansı süpürme çarpanı (1.25x)
ENABLE_MAX_STOP_DIST_GATE = True  # Stop mesafesi > %0.80 olan tüm geniş stoplu işlemleri eleyen Sniper Kapısı
MAX_ENTRY_STOP_DIST_PCT = 0.80    # Azami giriş stop mesafesi tavanı (%0.80 - Sniper Seviye Dibi Filtresi)
MAX_ABSOLUTE_STOP_PCT = 1.60      # Mutlak acil felaket stop tavanı (%1.60 - Kayma ve Ani Çöküş Sermaye Zırhı)
ENABLE_FAKEOUT_RECLAIM = True   # Sahte Kırılım / Ayı-Boğa Tuzağı İntikam Modülü (Reclaim Sniper)
FAKEOUT_RECLAIM_MAX_CANDLES = 4  # İntikam takip penceresi: 4 mum (20 dakika)

# 7. Açık Pozisyon (Open Interest) & Türev Yakıt Radarı
ENABLE_OI_VELOCITY_RADAR = True
OI_EXPANSION_THRESHOLD_PCT = 1.20   # %1.20 ve üzeri ΔOI: Kurumsal yeni para girişi (Breakout onayı)
OI_SQUEEZE_EXHAUSTION_PCT = -0.80   # -%0.80 ve altı ΔOI: Short/Long Squeeze tükenişi (Sahte kırılım tuzağı)
OI_POLL_INTERVAL_SEC = 30.0         # 30 saniyede bir aday paritelerde OI taraması

# 8. Çapraz Borsa Spot Öncüsü (Coinbase Pro Spot Lead-Lag)
ENABLE_COINBASE_LEAD_LAG = True
COINBASE_LEAD_SPREAD_BPS = 8.0      # 8 bps (%0.08) spread farkı: Öncü kurumsal nakit akışı
COINBASE_TICK_WINDOW_SEC = 5.0      # 5 saniyelik mikro öncü penceresi

# 6. Veri Fetch Ayarlari
CANDLE_5M_FETCH_DAYS = 15       # 5m mum verisi icin ~15 gun (paginated, ~4300 mum)

# 7. 5 Kurumsal Omurga Parametreleri (Institutional Quantitative Pillars)
# 1. Volatiliteye Uyarlı Dinamik Kasa Riski (Inverse-ATR Dynamic Equity Risk Parity)
FIXED_DOLLAR_RISK = 80.0         # İşlem başına hedeflenen net azami stop riski tabanı (80.0 USDT)
MIN_POSITION_MARGIN = 150.0      # Asgari pozisyon marjini (Binance min notional ve komisyon kalkanı)
MAX_POSITION_MARGIN = 500.0      # Azami pozisyon marjini (A+ Balina teyitli asimetrik portföy tavanı)

# 2. BTC Ani Mikro-Şok Kalkanı (BTC 60s Flush / Spike Gate)
BTC_SHOCK_60S_PCT = 0.28         # BTC 60 saniyede %0.28 ve üzeri ani hareket yaparsa şok geçidi devreye girer
BTC_SHOCK_COOLDOWN_SEC = 180.0   # Şok sonrası altcoin dondurma süresi: 3 dakika (180s)

# 3. Tahta Duvarı Yaşlanma & Sahtecilik Teyidi (Wall Aging & Spoofing Guard)
WALL_MIN_AGE_SEC = 15.0          # Duvarın gerçek emir sayılması için asgari yaşlanma süresi (15 saniye)
WALL_ANCHOR_AGE_SEC = 45.0       # Kurumsal çapa duvarı (Anchor Wall) seviyesi (45 saniye)

# 4. Spot vs Vadeli Ayrışması (Spot-Perp Basis & Divergence)
BASIS_BUBBLE_BPS = 25.0          # Vadeli prim balonu eşiği (+25 bps üstü: Boğa Tuzağı)
BASIS_ABSORPTION_BPS = -15.0     # Spot kurumsal emilim tabanı eşiği (-15 bps altı: Güçlü Sekme Teyidi)

# 5. Likidite Boşluğu ve Makas (Spread / Slippage) Koruması
MAX_ALLOWED_SPREAD_MAJORS = 0.05 # BTC, ETH, SOL için azami alış-satış makası (%0.05)
MAX_ALLOWED_SPREAD_ALTS = 0.12   # Standart altcoinler için azami makas (%0.12)
MAX_ALLOWED_SPREAD_MEME = 0.20   # Meme/Beta pariteler için azami makas (%0.20)
MAX_ENTRY_SLIPPAGE_PCT = 0.10    # Hedef lot büyüklüğünde azami kabul edilebilir kayma (%0.10)
MIN_L2_DEPTH_USD_03 = 12000.0    # Fiyatın %0.3 derinliğinde bulunması gereken asgari tahta likiditesi ($12,000)

# 8. Telegram Bildirim Ayarlari
TELEGRAM_ENABLED = True
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8893395987:AAGo285LhPhMKEfBpg3pyZAdO13sHC2y18U")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "829687700")

# 9. Geometrik Kuant & Asimetrik 2R Motoru (Valkyrie Grand Quant Engine)
ENABLE_GEOMETRIC_R_GATE = True        # R >= 1.80x Geometrik Ön-Onay Kapısı (Dün -$457 yazan 25 sıkışık işlemi eler)
MIN_PLANNED_R_RATIO = 1.80            # Asgari Planlanan R Oranı (1.80x)
ENABLE_RUNWAY_CLEARANCE = True         # Hava Koridoru (Air Pocket) Engeli Kontrolü
MIN_RUNWAY_OBSTACLE_R = 1.10          # Hedefe giden yolda ilk engel en az 1.10R uzakta olmali (1R nefes alani)
ENABLE_REGIME_DIRECTIONAL_GATE = True # Boğa rejiminde zayıf CVD'li counter-trend shortları engelle
BULL_SHORT_MIN_CVD_PCT = 52.0         # Boğada short için gereken asgari satıcı CVD üstünlüğü (%52)
ENABLE_CHANDELIER_BREATHING = True    # Erken Breakeven boğulmasını önleyen nefes payı

# 10. Meme & Yüksek Beta Sermaye Kalkanı (Meme Defensive Risk Shield)
ENABLE_MEME_DEFENSIVE_MODE = True
MEME_SYMBOLS = [
    "WIF/USDT", "PEPE/USDT", "TURBO/USDT", "FLOKI/USDT", "BONK/USDT",
    "DOGE/USDT", "SHIB/USDT", "1000PEPE/USDT", "1000FLOKI/USDT", "1000BONK/USDT",
    "MEME/USDT", "NEIRO/USDT", "POPCAT/USDT", "COTI/USDT", "ONG/USDT"
]
MEME_MAX_LEVERAGE = 3              # Meme paritelerde azami defansif kaldıraç (3x)
MEME_MAX_MARGIN = 200.0            # Meme paritelerde azami marjin ($200)
MEME_MAX_STOP_DIST_PCT = 0.70      # Meme paritelerde azami stop mesafesi (%0.70)

# 11. Valkyrie Sürdürülebilir Kuant Alpha Reformları (476 İşlem Sonrası)
ENABLE_WHIPSAW_TRADING_FILTER = False     # Parite çıkarma / yasaklama KAPALI (Hiçbir coin sepetten çıkarılmaz, tüm 100 coin taranır)
PERSONA_ALLOWED_CLASSES = ["GOLD", "STANDARD", "WHIPSAW"] # Tüm parite sınıfları aktiftir; bot her coini anlık verisine göre denetler
ENABLE_DYNAMIC_COIN_AUDIT = True          # Her coinde anlık kuant ve veri süzgeci denetimi (Hacimsiz kırılım eleme, 4+ Confluence)
ENABLE_CHANDELIER_EARLY_BE_LOCK = True    # +%0.80 MFE (+%4.0 ROE) kâr gören pozisyona erken Breakeven kilidi
CHANDELIER_EARLY_BE_THRESHOLD_PCT = 0.80  # Erken BE için gereken asgari fiyat lehte hareket eşiği (%0.80)
ENABLE_ASIA_SELECTIVE_SHIELD = True       # Asya seansında (TSİ 02:00-09:00) düşük likidite tuzak filtresi
ENABLE_COOLDOWN_THROTTLE = False          # Fırsat kaçırmamak için genel soğuma KAPALI (Zararlarda zaten 45dk stop kalkanı ve 2 stop sınırı devrededir)
SYMBOL_MIN_COOLDOWN_MINUTES = 0           # Kârlı trendlerde ve A+ Elit sinyallerde anında yeniden işlem açılabilir (0 dk)

# 12. Sistem Mimarisi & Güvenlik Yapılandırması (15 Reform Paketi)
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "valkyrie-quant-2025-secure")
ENABLE_CHANDELIER_BE_NOTIFY = True        # Breakeven kilitlendiğinde Telegram anlık bildirim kalkanı
ENABLE_DAILY_CIRCUIT_BREAKER = False      # Fırsat kaçırmamak için günlük devre kesici engellemesi KAPALI (Yalnızca telemetri)
MAX_DAILY_LOSS_PCT = 0.05                 # Azami günlük referans takip eşiği (%5.0)

SECTOR_CLUSTERS = {
    "MEME": {"DOGE/USDT", "PEPE/USDT", "SHIB/USDT", "WIF/USDT", "BONK/USDT", "FLOKI/USDT", "TURBO/USDT", "BOME/USDT", "PUMP/USDT", "1000PEPE/USDT", "1000SHIB/USDT", "1000BONK/USDT", "1000FLOKI/USDT", "NEIRO/USDT"},
    "SOL_ECO": {"SOL/USDT", "JTO/USDT", "JUP/USDT", "PYTH/USDT", "RAY/USDT", "KMNO/USDT"},
    "AI_DATA": {"FET/USDT", "RENDER/USDT", "TAO/USDT", "NEAR/USDT", "VIRTUAL/USDT", "WLD/USDT"},
    "DEFI_L1": {"ETH/USDT", "AAVE/USDT", "UNI/USDT", "CRV/USDT", "PENDLE/USDT", "ENA/USDT", "LDO/USDT"}
}

TOP_LIQUIDITY_SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT", "BNB/USDT",
    "SUI/USDT", "PEPE/USDT", "AVAX/USDT", "LINK/USDT", "NEAR/USDT", "ADA/USDT",
    "LTC/USDT", "TRX/USDT", "DOT/USDT", "AAVE/USDT", "UNI/USDT", "SHIB/USDT",
    "WIF/USDT", "FET/USDT"
]

# 13. Kuantum Emir Akışı, Çığ Freni & Runner Koruma Zırhı (Mikroyapı Reformu)
ENABLE_OPPOSING_TAKER_GUARD = True      # Zıt yönlü agresif piyasa emri akışını (Taker Imbalance) engelleyen zırh
TAKER_BUY_RATIO_MIN_LONG = 42.0         # Long açılışı için asgari Taker Alıcı oranı (%42 altındaysa market satıcıları süpürüyor demektir)
TAKER_BUY_RATIO_MAX_SHORT = 58.0        # Short açılışı için azami Taker Alıcı oranı (%58 üstündeyse market alıcıları pompalıyor demektir)

ENABLE_HAWKES_AVALANCHE_BRAKE = True    # Kendi kendini besleyen tasfiye çığı freni (Hawkes branching ratio)
HAWKES_AVALANCHE_THRESHOLD_ETA = 0.50   # eta >= 0.50 olduğunda tasfiye çığı rejimine geçilir (Retest ve tuzaklara giriş engellenir)

ENABLE_DYNAMIC_RUNNER_PROFIT_LOCK = True# Anti-KMNO: TP1 sonrası koşan runner kârını garantileyen dinamik stop kilidi
RUNNER_LOCK_TIER1_MFE = 2.0             # %2.0 MFE'de stop en az +%1.0 net kâra kilitlenir
RUNNER_LOCK_TIER2_MFE = 3.5             # %3.5 MFE'de stop en az +%2.0 net kâra kilitlenir
RUNNER_LOCK_TIER3_MFE = 5.0             # %5.0 MFE'de stop en az +%3.0 net kâra kilitlenir

# 14. Apollo Kalman Durum-Uzay Filtresi & SpaceX PID Kâr Kontrolörü (AstroQuant Reformu)
ENABLE_KALMAN_PRICE_FILTER = True       # Sahte fitil kırılımlarını süzen Apollo Kalman Filtresi
KALMAN_PROCESS_NOISE_Q = 1e-4           # Süreç gürültüsü kovaryansı (Q)
KALMAN_MEASUREMENT_NOISE_R0 = 1e-2      # Baz ölçüm gürültüsü kovaryansı (R0)
KALMAN_WICK_PENALTY_MULT = 5.0          # Fitil/gövde karesi ceza çarpanı (alpha)

ENABLE_PID_PROFIT_CONTROLLER = True     # SpaceX Falcon 9 Dinamik Kâr Sürüşü & Zirve Kilidi
PID_KP = 0.50                           # Oransal kazanç (P - Kâr mesafesi)
PID_KI = 0.05                           # İntegral kazanç (I - Kârda kalma süresi enerjisi)
PID_KD = 0.35                           # Türev kazancı (D - Momentum hız değişimi)
PID_MIN_MFE_TRIGGER = 2.0               # PID'nin devreye girdiği asgari MFE eşiği (%2.0 ROE)
PID_ATR_NOISE_FLOOR_MULT = 1.5          # Gürültüde erken infazı önleyen zorunlu nefes tamponu (1.5x ATR)
PID_CAPTURE_TIER1 = 0.60                # Erken kârda (%2 - %4 ROE) yakalama oranı (%40 geniş nefes payı)
PID_CAPTURE_TIER2 = 0.70                # Orta kârda (%4 - %8 ROE) yakalama oranı (%30 nefes payı)
PID_CAPTURE_TIER3 = 0.80                # Zirve kârda (%8+ ROE) yakalama oranı (%20 nefes payı)

# 15. Ornstein-Uhlenbeck (O-U) Stokastik Süreci ile Optimal Bekleme Süresi (Half-Life & Alpha Decay)
ENABLE_OU_TIME_STOP = True                  # O-U Stokastik Yarılanma Ömrü & Dinamik Zaman Kalkanı
OU_LOOKBACK_CANDLES = 80                    # OLS regresyonu için geçmiş mum penceresi (80 mum = ~6.5 saat)
OU_MIN_HALF_LIFE_MIN = 15.0                 # Asgari yarılanma ömrü (15 dk altındaki aşırı hızlı gürültüyü sınırlar)
OU_MAX_HALF_LIFE_MIN = 180.0                # Azami yarılanma ömrü tavanı (180 dk / 3 saat)
OU_DECAY_TIER1_MULT = 1.0                   # Kademe 1: 1.0 x tau (İlk İlerleme Kontrolü)
OU_DECAY_TIER2_MULT = 1.5                   # Kademe 2: 1.5 x tau (Alfa Çürüme Uyarısı & BE Koruma Tahliyesi)
OU_DECAY_TIER3_MULT = 2.0                   # Kademe 3: 2.0 x tau (Mutlak Matematiksel Zaman Stopu)
OU_MIN_PROGRESS_RATIO = 0.35                # 1.0 tau anında hedefin en az %35'i katedilmelidir
OU_PID_IMMUNITY_ROE = 2.0                   # Pozisyon ROE >= +%2.0 ise SpaceX PID devrededir, O-U kârı ASLA kesmez

# 16. Borsa Net Giriş/Çıkış Akışı (Exchange Netflows) ve On-Chain Balina Radarı (Whale Ammunition)
ENABLE_WHALE_NETFLOW_RADAR = True            # Borsa Net Akışları ve Balina Giriş/Çıkış Radarı
NETFLOW_INFLOW_ZSCORE_THRESHOLD = 2.0        # Borsa net girişi (Inflow) 24s ortalamasından +2.0 sigma saparsa VETO
NETFLOW_OUTFLOW_ZSCORE_THRESHOLD = -2.0      # Borsa net çıkışı (Outflow) 24s ortalamasından -2.0 sigma saparsa SHORT VETO / ARZ ŞOKU
NETFLOW_LOOKBACK_HOURS = 24                  # Net akış hareketli ortalaması için geçmiş pencere (saat)
NETFLOW_REFRESH_INTERVAL_SEC = 90            # Çoklu kaynak arka plan sorgu sıklığı (sn)

# Dinamik Likidite Kademeleri Balina Transfer Eşikleri ($ USD)
WHALE_TIER1_MIN_USD = 10_000_000.0           # Tier-1 Majörler (BTC, ETH, SOL, BNB) tek işlem balina eşiği ($10M)
WHALE_TIER2_MIN_USD = 2_000_000.0            # Tier-2 Standart Altcoinler tek işlem balina eşiği ($2M)
WHALE_TIER3_MIN_USD = 500_000.0              # Tier-3 Meme & Düşük Likidite tek işlem balina eşiği ($500K)
WHALE_VOL_RATIO_THRESHOLD_PCT = 2.0          # İşlem büyüklüğü paritenin 24s hacminin %2.0'sini aşarsa doğrudan DUMP uyarısı

# Stabil Kripto Cephane & Confluence Parametreleri
ENABLE_AMMUNITION_CONFLUENCE = True          # Borsa taze USDT/USDC girişini LONG confluence (+1 skor) olarak ödüllendir
AMMUNITION_SURGE_THRESHOLD_USD = 50_000_000.0# Borsalara son 1-4 saatte >= $50M taze stabil kripto girişi = Boğa Cephanesi
STALE_NETFLOW_TIMEOUT_SEC = 1200             # 20 dakikadan eski verilerde sinyali engelleme (Fail-safe passthrough)

# 17. Kurumsal Coinbase Prime vs. Binance Offshore CVD Ayrışması (Stage 3: Smart Money Delta)
ENABLE_SMART_MONEY_DIVERGENCE = True           # ABD Kurumsal Spot vs. Offshore Vadeli CVD Ayrışma Kalkanı
SMART_MONEY_ACCUM_CB_BUY_MIN = 53.0           # Kurumsal Spot Birikim için Coinbase asgari Alıcı oranı (%53.0)
SMART_MONEY_RETAIL_LONG_TRAP_BINANCE = 60.0    # Perakende Long Tuzağı: Binance Futures alıcı oranı >= %60.0
SMART_MONEY_RETAIL_LONG_TRAP_CB_MAX = 46.0     # Perakende Long Tuzağı: Coinbase Spot alıcı oranı <= %46.0
SMART_MONEY_RETAIL_SHORT_TRAP_BINANCE = 40.0   # Perakende Short Tuzağı: Binance Futures alıcı oranı <= %40.0
SMART_MONEY_RETAIL_SHORT_TRAP_CB_MIN = 53.0    # Perakende Short Tuzağı: Coinbase Spot alıcı oranı >= %53.0
SMART_MONEY_DIVERGENCE_SPREAD_TRAP = 12.0      # Binance ile Coinbase arasındaki kritik ayrışma spread eşiği (%12.0)
SMART_MONEY_MARGIN_BONUS_MULT = 1.25           # Kurumsal birikim teyitli Long'larda asimetrik marjin çarpanı (x1.25)



