# config.py - Trade Bot Genel Yapilandirmasi

# 1. Takip Edilecek Coinler (Binance USDT Perpetual - Top 100 Hacimli Saf Kripto Parite)
ALL_AVAILABLE_SYMBOLS = [
    # 1 - 10 (Süper Majörler & Mega Likidite)
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "XRP/USDT",
    "HYPE/USDT",
    "ZEC/USDT",
    "ENA/USDT",
    "TRUMP/USDT",
    "DOGE/USDT",
    "BTR/USDT",
    # 11 - 20 (Yüksek Hacimli Popüler Pariteler)
    "BNB/USDT",
    "PEPE/USDT",
    "PUMP/USDT",
    "SUI/USDT",
    "MOVR/USDT",
    "TAC/USDT",
    "TAO/USDT",
    "ONG/USDT",
    "ADA/USDT",
    "WLD/USDT",
    # 21 - 30 (DeFi & L1/L2 Trend Pariteleri)
    "LINK/USDT",
    "UNI/USDT",
    "PROM/USDT",
    "NEAR/USDT",
    "BEAMX/USDT",
    "AAVE/USDT",
    "MAGMA/USDT",
    "AVAX/USDT",
    "BICO/USDT",
    "VET/USDT",
    # 31 - 40 (Meme & Yüksek Volatilite)
    "PENGU/USDT",
    "LTC/USDT",
    "MUU/USDT",
    "FARTCOIN/USDT",
    "LIT/USDT",
    "ONDO/USDT",
    "XMR/USDT",
    "BCH/USDT",
    "CHIP/USDT",
    "LITE/USDT",
    # 41 - 50 (Altyapı, Yapay Zeka & Ekosistem)
    "XPL/USDT",
    "FIL/USDT",
    "TRX/USDT",
    "WIF/USDT",
    "XLM/USDT",
    "INJ/USDT",
    "BLESS/USDT",
    "SHIB/USDT",
    "ASTER/USDT",
    "AAOI/USDT",
    # 51 - 60 (Katman 1 / 2 & Büyüyen Ekosistemler)
    "ZRO/USDT",
    "WLFI/USDT",
    "RUNE/USDT",
    "VIRTUAL/USDT",
    "JUP/USDT",
    "DOT/USDT",
    "STX/USDT",
    "APT/USDT",
    "FET/USDT",
    "JTO/USDT",
    # 61 - 70 (DeFi, Gaming & Yeni Trendler)
    "POL/USDT",
    "ACE/USDT",
    "EDEN/USDT",
    "ETHFI/USDT",
    "DASH/USDT",
    "OP/USDT",
    "ARB/USDT",
    "BONK/USDT",
    "ETC/USDT",
    "PEOPLE/USDT",
    # 71 - 80 (Oracle, DEX & Kurumsal Pariteler)
    "PYTH/USDT",
    "VELVET/USDT",
    "CRV/USDT",
    "MON/USDT",
    "HBAR/USDT",
    "RIVER/USDT",
    "KMNO/USDT",
    "ONT/USDT",
    "WDC/USDT",
    "ATOM/USDT",
    # 81 - 90 (Modüler Blokzincirler & Likidite Havuzları)
    "BTW/USDT",
    "MORPHO/USDT",
    "GIGGLE/USDT",
    "MOVE/USDT",
    "LDO/USDT",
    "TIA/USDT",
    "ICP/USDT",
    "GWEI/USDT",
    "SPK/USDT",
    "BOME/USDT",
    # 91 - 100 (Yapay Zeka, Web3 & Topluluk Pariteleri)
    "MANTRA/USDT",
    "HUMA/USDT",
    "KERNEL/USDT",
    "APR/USDT",
    "GRAM/USDT",
    "MELANIA/USDT",
    "RENDER/USDT",
    "GALA/USDT",
    "SEI/USDT",
    "GPS/USDT"
]

# Varsayilan baslangicta aktif pariteler (Tum 100 Parite Varsayilan Olarak Aktif)
DEFAULT_ACTIVE_SYMBOLS = ALL_AVAILABLE_SYMBOLS.copy()

SYMBOLS = DEFAULT_ACTIVE_SYMBOLS

# 2. Risk ve Kasa Yonetimi
INITIAL_BALANCE = 100000.0       # Demo baslangic bakiyesi (USDT)
LEVERAGE = 5                  # Kaldirac (5x)
POSITION_SIZE_USDT = 100.0     # Her islemde kullanilacak marjin (10 USDT)
MAX_OPEN_POSITIONS = 100      # Tum aktif paritelerde bakiye yettigince islem acilabilmesi icin 100
COMMISSION_RATE = 0.0005      # %0.05 Binance vadeli islem komisyon simulasyonu

# 3. Strateji Parametreleri
TIMEFRAME = "5m"              # Ana islem zaman dilimi
LOOKBACK_DAYS_AVWAP = 10      # Son 10 gunluk tepe/dip AVWAP referansi
BUFFER_RATIO = 0.25           # %25 akilli stop tampon payi
BREAKOUT_HOLD_SECONDS = 60    # Kirilim tutunma teyit suresi (60 saniye)

# 4. Trailing Stop / Kar Koruma Esikleri
TRAILING_BREAKEVEN_ROE = 6.0    # %6 ROE'de soft stop -> breakeven (giris fiyatina) tasir
TRAILING_LOCK_30_ROE = 12.0     # %12 ROE'de karin %30'unu kilitleyen seviyeye tasir
TRAILING_LOCK_50_ROE = 20.0     # %20 ROE'de hard stop ile karin %50'sini kilitle

# 5. Scalp Zaman Siniri
SCALP_MAX_HOLD_CANDLES = 48     # 48 x 5dk = 4 saat (SCALP pozisyon max tutma suresi)

# 6. Veri Fetch Ayarlari
CANDLE_5M_FETCH_DAYS = 15       # 5m mum verisi icin ~15 gun (paginated, ~4300 mum)

# 7. Telegram Bildirim Ayarlari
TELEGRAM_ENABLED = True
TELEGRAM_BOT_TOKEN = "8893395987:AAGKAzD4sUg5LwMLLWHSt5U1VRRS7JE-m9c"
TELEGRAM_CHAT_ID = "829687700"
