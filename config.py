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
ENABLE_DYNAMIC_LEVERAGE = True   # Akilli 3-Kademeli Dinamik Kaldirac Motoru (2x - 8x)
MIN_LEVERAGE = 2                 # Azami defansif kaldirac tabani (Asiri dalgalanma / Dead Zone kalkani)
MAX_LEVERAGE = 8                 # Azami kurumsal hucum kaldiraci tavani (A+ Elit Sniper teyitli)
LEVERAGE_LOW_ATR_THRESHOLD = 0.65   # Dusuk dalgalanma (BTC/ETH gibi agirbasli majorler): 7x-8x'e izin verilir
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
MAX_ABSOLUTE_STOP_PCT = 0.95      # Mutlak acil felaket stop tavanı (%0.95 - Kayma ve Ani Düşüş Sermaye Zırhı)
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
ENABLE_DAILY_CIRCUIT_BREAKER = True       # Günlük net kayıp %3'ü aştığında yeni işlem açılışını kilitle
MAX_DAILY_LOSS_PCT = 0.03                 # Azami günlük kabul edilebilir portföy kaybı (%3.0)

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


