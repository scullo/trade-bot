# config.py - Trade Bot Genel Yapilandirmasi

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
LEVERAGE = 5                     # Kaldirac (5x)
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
STAGNATION_CANDLES_MEME = 4      # Yüksek beta / meme paritelerde ivme bekleme süresi: 4 mum (20 dk)
STAGNATION_CANDLES_MAJOR = 8     # Majör ve DeFi paritelerde ivme bekleme süresi: 8 mum (40 dk)

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
TELEGRAM_BOT_TOKEN = "8893395987:AAGKAzD4sUg5LwMLLWHSt5U1VRRS7JE-m9c"
TELEGRAM_CHAT_ID = "829687700"

