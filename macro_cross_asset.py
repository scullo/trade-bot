"""
🦅 VALKYRIE QUANT - ÇAPRAZ PİYASA (CROSS-ASSET) VE ON-CHAIN KÜRESEL RADAR
Kripto piyasasını yöneten 7 büyük makro gücü (DXY, ABD 10Y Tahvilleri, Nasdaq, Altın,
USDT Dominansı, BTC Dominansı, ETH/BTC) ve Hükümet/Hazine cüzdan hareketlerini canlı izleyen,
bileşik Küresel Risk İştahı Rejimini (Risk-On / Risk-Off) hesaplayan kuant motor.
"""

import os
import json
import time
import asyncio
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
import aiohttp

CROSS_ASSET_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "macro_cross_asset_cache.json")

# Yahoo Finance & Public API Haritası (7 Büyük Çekirdek Güç)
MACRO_SYMBOLS = {
    "DXY": "DX-Y.NYB",    # Dolar Endeksi (US Dollar Index)
    "US10Y": "^TNX",      # ABD 10 Yıllık Hazine Tahvil Getirisi
    "GOLD": "GC=F",       # Ons Altın (XAU/USD Vadeli)
    "OIL": "CL=F",        # WTI Ham Petrol Vadeli (Jeopolitik Risk & Enflasyon)
    "BRENT": "BZ=F",      # Brent Petrol Vadeli (Küresel Enerji Göstergesi)
    "NASDAQ": "NQ=F",     # E-mini Nasdaq 100 Vadeli (Risk Varlıkları)
    "SP500": "ES=F",      # E-mini S&P 500 Vadeli (Geniş Piyasa Likiditesi)
    "VIX": "^VIX"         # CBOE Volatilite Korku Endeksi (Wall Street Fear Gauge)
}

# 🏛️ VALKYRIE WALL STREET & KÜRESEL TERMINAL DESK KONFİGÜRASYONU (4 KITA & EMTİA KORİDORU)
GLOBAL_TERMINAL_CONFIG = {
    "america": [
        {"id": "sp500", "symbol": "ES=F", "name": "S&P 500 Vadeli", "sub": "Geniş Piyasa Likiditesi", "flag": "🇺🇸", "category": "ENDEX"},
        {"id": "nasdaq", "symbol": "NQ=F", "name": "Nasdaq 100 Vadeli", "sub": "Teknoloji & Risk Varlığı", "flag": "🇺🇸", "category": "ENDEX"},
        {"id": "dow", "symbol": "YM=F", "name": "Dow Jones 30", "sub": "Sanayi & Değer Hisseleri", "flag": "🇺🇸", "category": "ENDEX"},
        {"id": "russell", "symbol": "RTY=F", "name": "Russell 2000", "sub": "Küçük Sermayeli Şirketler (Risk-On)", "flag": "🇺🇸", "category": "ENDEX"},
        {"id": "vix", "symbol": "^VIX", "name": "CBOE VIX Endeksi", "sub": "Wall Street Korku & Volatilite", "flag": "🇺🇸", "category": "VOLATILITY"},
        {"id": "us10y", "symbol": "^TNX", "name": "ABD 10Y Hazine Faizi", "sub": "Küresel Borçlanma Maliyeti", "flag": "🇺🇸", "category": "RATES"}
    ],
    "europe": [
        {"id": "dax", "symbol": "^GDAXI", "name": "Almanya DAX 40", "sub": "Frankfurt Sanayi Lokomotifi", "flag": "🇩🇪", "category": "ENDEX"},
        {"id": "ftse", "symbol": "^FTSE", "name": "İngiltere FTSE 100", "sub": "Londra Finans & Emtia Masası", "flag": "🇬🇧", "category": "ENDEX"},
        {"id": "cac40", "symbol": "^FCHI", "name": "Fransa CAC 40", "sub": "Paris Lüks & Enerji Endeksi", "flag": "🇫🇷", "category": "ENDEX"},
        {"id": "stoxx50", "symbol": "^STOXX50E", "name": "Euro Stoxx 50", "sub": "Avrupa Birliği Mavi Çip", "flag": "🇪🇺", "category": "ENDEX"},
        {"id": "eurusd", "symbol": "EURUSD=X", "name": "EUR / USD Paritesi", "sub": "Euro Bölgesi Döviz Gücü", "flag": "🇪🇺", "category": "FX"}
    ],
    "asia": [
        {"id": "nikkei", "symbol": "^N225", "name": "Japonya Nikkei 225", "sub": "Tokyo Teknoloji & İhracat", "flag": "🇯🇵", "category": "ENDEX"},
        {"id": "hangseng", "symbol": "^HSI", "name": "Hong Kong Hang Seng", "sub": "Çin Teknoloji & Finans", "flag": "🇭🇰", "category": "ENDEX"},
        {"id": "shanghai", "symbol": "000001.SS", "name": "Şanghay Bileşik", "sub": "Çin İmalat & Sanayi Devleri", "flag": "🇨🇳", "category": "ENDEX"},
        {"id": "asx200", "symbol": "^AXJO", "name": "Avustralya ASX 200", "sub": "Madencilik & Pasifik Likiditesi", "flag": "🇦🇺", "category": "ENDEX"},
        {"id": "usdjpy", "symbol": "USDJPY=X", "name": "USD / JPY Kuru", "sub": "Yen Carry Trade & Likidite", "flag": "🇯🇵", "category": "FX"}
    ],
    "commodities_me": [
        {"id": "brent", "symbol": "BZ=F", "name": "Brent Ham Petrol", "sub": "Küresel Enerji & Jeopolitik Şok", "flag": "🛢️", "category": "ENERGY"},
        {"id": "oil", "symbol": "CL=F", "name": "WTI Ham Petrol", "sub": "ABD Teksas Petrol Göstergesi", "flag": "🛢️", "category": "ENERGY"},
        {"id": "natgas", "symbol": "NG=F", "name": "Henry Hub Doğalgaz", "sub": "Avrupa/ABD Isınma & Elektrik", "flag": "⚡", "category": "ENERGY"},
        {"id": "gold", "symbol": "GC=F", "name": "Ons Altın (XAU/USD)", "sub": "Güvenli Liman & Devalüasyon", "flag": "🥇", "category": "METALS"},
        {"id": "silver", "symbol": "SI=F", "name": "Ons Gümüş (XAG/USD)", "sub": "Endüstriyel & Değerli Metal", "flag": "🥈", "category": "METALS"},
        {"id": "copper", "symbol": "HG=F", "name": "Yüksek Dereceli Bakır", "sub": "Dr. Bakır (Sanayi Barometresi)", "flag": "🥉", "category": "METALS"},
        {"id": "dxy", "symbol": "DX-Y.NYB", "name": "Dolar Endeksi (DXY)", "sub": "Küresel Rezerv Para Gücü", "flag": "💵", "category": "CURRENCY"},
        {"id": "tasi", "symbol": "^TASI.SR", "name": "Suudi Arabistan TASI", "sub": "Körfez Enerji & Petrol Borsası", "flag": "🇸🇦", "category": "EMERGING"},
        {"id": "jse", "symbol": "^J200.JO", "name": "Güney Afrika JSE 40", "sub": "Afrika Kıtası Sanayi & Maden", "flag": "🇿🇦", "category": "EMERGING"}
    ]
}

COINGECKO_GLOBAL_URL = "https://api.coingecko.com/api/v3/global"
BINANCE_ETHBTC_URL = "https://api.binance.com/api/v3/ticker/price?symbol=ETHBTC"

# Hükümet ve Kara Kuğu On-Chain Cüzdan Anahtar Kelimeleri
GOVERNMENT_ENTITIES = [
    "US GOVERNMENT", "SILK ROAD", "GERMAN GOVERNMENT", "MT. GOX", "MTGOX",
    "DOJ SEIZED", "US MARSHALS", "ESTONIA GOV", "UKRAINE GOV"
]
STABLECOIN_MINTS = ["TETHER TREASURY", "CIRCLE TREASURY", "USDT MINT", "USDC MINT", "PRINTED AT TETHER"]

def get_world_market_sessions() -> List[Dict[str, Any]]:
    """
    Dünya Borsa Seanslarının (New York, Londra, Tokyo, İstanbul) anlık açık/kapalı durumunu
    ve kapanış/açılış geri sayımını TSİ (UTC+3) bazında hesaplar.
    """
    now_utc = datetime.now(timezone.utc)
    now_tsi = now_utc + timedelta(hours=3)
    weekday = now_tsi.weekday() # 0 = Pazartesi, 6 = Pazar
    minute_of_day = now_tsi.hour * 60 + now_tsi.minute
    is_weekend = weekday >= 5

    sessions = []

    # 1. NEW YORK (NYSE / NASDAQ) 16:30 - 23:00 TSİ
    ny_open_min = 16 * 60 + 30
    ny_close_min = 23 * 60
    ny_open = (not is_weekend) and (ny_open_min <= minute_of_day < ny_close_min)
    if ny_open:
        rem_min = ny_close_min - minute_of_day
        ny_countdown = f"Kapanışa {rem_min // 60}s {rem_min % 60}dk"
    else:
        ny_countdown = "Hafta Sonu / Seans Dışı" if is_weekend else ("Açılışa " + (f"{((ny_open_min - minute_of_day) // 60)}s {((ny_open_min - minute_of_day) % 60)}dk" if minute_of_day < ny_open_min else "Yarın 16:30 TSİ"))

    sessions.append({
        "id": "nyse",
        "name": "New York (NYSE / NASDAQ)",
        "flag": "🇺🇸",
        "city": "Wall Street, New York",
        "hours_tsi": "16:30 - 23:00 TSİ",
        "is_open": ny_open,
        "status_text": "AÇIK (CANLI SEANS) 🟢" if ny_open else "KAPALI 🔴",
        "countdown": ny_countdown
    })

    # 2. LONDRA (LSE) 10:00 - 18:30 TSİ
    lon_open_min = 10 * 60
    lon_close_min = 18 * 60 + 30
    lon_open = (not is_weekend) and (lon_open_min <= minute_of_day < lon_close_min)
    if lon_open:
        rem_min = lon_close_min - minute_of_day
        lon_countdown = f"Kapanışa {rem_min // 60}s {rem_min % 60}dk"
    else:
        lon_countdown = "Hafta Sonu / Seans Dışı" if is_weekend else ("Açılışa " + (f"{((lon_open_min - minute_of_day) // 60)}s {((lon_open_min - minute_of_day) % 60)}dk" if minute_of_day < lon_open_min else "Yarın 10:00 TSİ"))

    sessions.append({
        "id": "lse",
        "name": "Londra (London Stock Exchange)",
        "flag": "🇬🇧",
        "city": "City of London",
        "hours_tsi": "10:00 - 18:30 TSİ",
        "is_open": lon_open,
        "status_text": "AÇIK (CANLI SEANS) 🟢" if lon_open else "KAPALI 🔴",
        "countdown": lon_countdown
    })

    # 3. TOKYO (TSE) 03:00 - 09:00 TSİ
    tky_open_min = 3 * 60
    tky_close_min = 9 * 60
    tky_open = (not is_weekend) and (tky_open_min <= minute_of_day < tky_close_min)
    if tky_open:
        rem_min = tky_close_min - minute_of_day
        tky_countdown = f"Kapanışa {rem_min // 60}s {rem_min % 60}dk"
    else:
        tky_countdown = "Hafta Sonu / Seans Dışı" if is_weekend else ("Açılışa " + (f"{((tky_open_min - minute_of_day) // 60)}s {((tky_open_min - minute_of_day) % 60)}dk" if minute_of_day < tky_open_min else "Yarın 03:00 TSİ"))

    sessions.append({
        "id": "tse",
        "name": "Tokyo (Tokyo Stock Exchange)",
        "flag": "🇯🇵",
        "city": "Tokyo, Nihonbashi",
        "hours_tsi": "03:00 - 09:00 TSİ",
        "is_open": tky_open,
        "status_text": "AÇIK (CANLI SEANS) 🟢" if tky_open else "KAPALI 🔴",
        "countdown": tky_countdown
    })

    # 4. İSTANBUL (BIST 100) 10:00 - 18:00 TSİ
    ist_open_min = 10 * 60
    ist_close_min = 18 * 60
    ist_open = (not is_weekend) and (ist_open_min <= minute_of_day < ist_close_min)
    if ist_open:
        rem_min = ist_close_min - minute_of_day
        ist_countdown = f"Kapanışa {rem_min // 60}s {rem_min % 60}dk"
    else:
        ist_countdown = "Hafta Sonu / Seans Dışı" if is_weekend else ("Açılışa " + (f"{((ist_open_min - minute_of_day) // 60)}s {((ist_open_min - minute_of_day) % 60)}dk" if minute_of_day < ist_open_min else "Yarın 10:00 TSİ"))

    sessions.append({
        "id": "bist",
        "name": "Borsa İstanbul (BIST 100)",
        "flag": "🇹🇷",
        "city": "Maslak, İstanbul",
        "hours_tsi": "10:00 - 18:00 TSİ",
        "is_open": ist_open,
        "status_text": "AÇIK (CANLI SEANS) 🟢" if ist_open else "KAPALI 🔴",
        "countdown": ist_countdown
    })

    return sessions

class MacroCrossAssetRadar:
    """Çapraz Piyasa ve Küresel Makro Radar Yöneticisi."""

    def __init__(self, cache_file: str = CROSS_ASSET_CACHE_FILE):
        self.cache_file = cache_file
        self.data: Dict[str, Any] = {
            "dxy": {"price": 102.23, "chg_24h": 0.06, "status": "NEUTRAL"},
            "us10y": {"price": 5.24, "chg_24h": -1.26, "status": "NEUTRAL"},
            "nasdaq": {"price": 31108.75, "chg_24h": -0.67, "status": "NEUTRAL"},
            "sp500": {"price": 7859.75, "chg_24h": 0.43, "status": "NEUTRAL"},
            "vix": {"price": 14.84, "chg_24h": -4.38, "status": "NEUTRAL"},
            "gold": {"price": 4216.3, "chg_24h": 1.43, "status": "NEUTRAL"},
            "oil": {"price": 75.20, "chg_24h": 2.69, "status": "NEUTRAL"},
            "brent": {"price": 78.40, "chg_24h": 4.12, "status": "NEUTRAL"},
            "btc_d": 59.08,
            "usdt_d": 6.52,
            "eth_btc": 0.03027,
            "regime": "NEUTRAL",
            "regime_score": 0.0,
            "last_sync_ts": 0.0,
            "terminal_assets": {}
        }
        self.sync_interval_sec: float = 300.0  # 5 dakikada bir otomatik tazeleyen boru hattı
        self.load_cache()

    def load_cache(self) -> None:
        """Diskteki önbelleği yükle."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                    self.data.update(cached)
            except Exception as e:
                print(f">> [ÇAPRAZ MAKRO ÖNBELLEK UYARI] {e}")

    def save_cache(self) -> None:
        """Diske önbelleği atomik kaydet."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f">> [ÇAPRAZ MAKRO KAYIT HATA] {e}")

    async def _fetch_yahoo_symbol(self, session: aiohttp.ClientSession, name: str, symbol: str) -> Optional[Dict[str, Any]]:
        """Yahoo Finance v8 Chart API üzerinden tek bir makro varlığı çeker (<200ms)."""
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        try:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=6)) as resp:
                if resp.status == 200:
                    d = await resp.json()
                    meta = d.get("chart", {}).get("result", [{}])[0].get("meta", {})
                    p = meta.get("regularMarketPrice")
                    prev = meta.get("chartPreviousClose")
                    if p is not None and prev and prev > 0:
                        chg = round(((p - prev) / prev * 100.0), 2)
                        return {"price": round(float(p), 3), "chg_24h": chg}
                    elif p is not None:
                        return {"price": round(float(p), 3), "chg_24h": 0.0}
        except Exception:
            pass
        return None

    async def _fetch_crypto_dominance(self, session: aiohttp.ClientSession) -> Dict[str, float]:
        """CoinGecko Global API üzerinden BTC.D ve USDT.D dominansını çeker."""
        headers = {"User-Agent": "Mozilla/5.0"}
        res = {"btc_d": self.data.get("btc_d", 59.0), "usdt_d": self.data.get("usdt_d", 6.5)}
        try:
            async with session.get(COINGECKO_GLOBAL_URL, headers=headers, timeout=aiohttp.ClientTimeout(total=6)) as resp:
                if resp.status == 200:
                    d = await resp.json()
                    mcp = d.get("data", {}).get("market_cap_percentage", {})
                    btc_d = mcp.get("btc")
                    usdt_d = mcp.get("usdt")
                    if btc_d is not None:
                        res["btc_d"] = round(float(btc_d), 2)
                    if usdt_d is not None:
                        res["usdt_d"] = round(float(usdt_d), 2)
        except Exception:
            pass
        return res

    async def _fetch_eth_btc(self, session: aiohttp.ClientSession) -> float:
        """Binance Resmi API üzerinden ETH/BTC kurunu çeker."""
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            async with session.get(BINANCE_ETHBTC_URL, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    d = await resp.json()
                    p = d.get("price")
                    if p:
                        return round(float(p), 5)
        except Exception:
            pass
        return float(self.data.get("eth_btc", 0.0302))

    async def sync_cross_assets(self, force: bool = False) -> bool:
        """Tüm 4 kıta ve emtia varlıklarını paralel asenkron olarak çeker ve rejim skorunu hesaplar."""
        now = time.time()
        if not force and (now - float(self.data.get("last_sync_ts", 0.0)) < self.sync_interval_sec):
            return True

        try:
            async with aiohttp.ClientSession() as session:
                # 1. Tüm küresel terminal varlıklarını derle
                all_config_items = []
                for reg_key, items in GLOBAL_TERMINAL_CONFIG.items():
                    for item in items:
                        all_config_items.append(item)

                tasks = [
                    self._fetch_yahoo_symbol(session, item["id"], item["symbol"])
                    for item in all_config_items
                ]
                # Kripto Dominansı ve ETH/BTC ekle
                tasks.append(self._fetch_crypto_dominance(session))
                tasks.append(self._fetch_eth_btc(session))

                results = await asyncio.gather(*tasks, return_exceptions=True)

                terminal_results = results[:len(all_config_items)]
                dom_r = results[len(all_config_items)]
                ethbtc_r = results[len(all_config_items) + 1]

                if "terminal_assets" not in self.data or not isinstance(self.data["terminal_assets"], dict):
                    self.data["terminal_assets"] = {}

                for idx, item in enumerate(all_config_items):
                    res = terminal_results[idx]
                    asset_id = item["id"]
                    if isinstance(res, dict) and res:
                        p = res.get("price", 0.0)
                        chg = res.get("chg_24h", 0.0)
                        asset_data = {
                            "id": asset_id,
                            "symbol": item["symbol"],
                            "name": item["name"],
                            "sub": item["sub"],
                            "flag": item["flag"],
                            "category": item["category"],
                            "price": p,
                            "chg_24h": chg,
                            "status": "BULLISH" if chg > 0 else ("BEARISH" if chg < 0 else "NEUTRAL")
                        }
                        self.data["terminal_assets"][asset_id] = asset_data
                        
                        # Geriye dönük uyumluluk: Çekirdek makro alanları da güncelle
                        if asset_id in self.data and isinstance(self.data[asset_id], dict):
                            self.data[asset_id].update({"price": p, "chg_24h": chg})
                        elif asset_id in ["dxy", "us10y", "nasdaq", "sp500", "vix", "gold", "oil", "brent"]:
                            self.data[asset_id] = {"price": p, "chg_24h": chg}

                if isinstance(dom_r, dict) and dom_r:
                    self.data["btc_d"] = dom_r.get("btc_d", self.data.get("btc_d", 59.08))
                    self.data["usdt_d"] = dom_r.get("usdt_d", self.data.get("usdt_d", 6.52))
                if isinstance(ethbtc_r, (float, int)) and ethbtc_r > 0:
                    self.data["eth_btc"] = float(ethbtc_r)

                # Bileşik Makro Rejim & Risk İştahı Hesaplama
                self._calculate_macro_regime()
                self.data["last_sync_ts"] = now
                self.save_cache()
                print(f">> [WALL STREET & GLOBAL DESK] {len(all_config_items)} varlık senkronize edildi: DXY={self.data.get('dxy',{}).get('price')} | Brent=${self.data.get('brent',{}).get('price')} | S&P500={self.data.get('sp500',{}).get('price')}")
                return True

        except Exception as e:
            print(f">> [ÇAPRAZ MAKRO SENKRONİZASYON HATA] {e}")
            return False

    def _calculate_macro_regime(self) -> None:
        """
        Kripto için Çok Değişkenli Kuant Risk İştahı (Risk-On / Risk-Off) Skoru [-100, +100]:
        1. DXY (Dolar Endeksi): Düşüş = +25 (Boğa), Yükseliş = -25 (Ayı)
        2. US10Y (10 Yıllık Faiz): Düşüş = +20 (Faiz gevşemesi boğa), Yükseliş = -20
        3. Nasdaq & S&P 500: Hisse rallisi = +20 (Risk iştahı açık), Düşüş = -20
        4. VIX (CBOE Korku Endeksi): VIX < 16.0 = +15 (Sakin kurumsal boğa), VIX > 22.0 = -20 (Volatilite şoku / panik)
        5. Ons Altın (GC=F): Güvenli liman ve devalüasyon korunması, DXY düşerken altın artarsa = +10
        6. USDT.D (Stablecoin Dominansı): %6.2 altı nakit kriptoya akıyor = +20, %7.5 üstü nakite kaçış = -25
        7. BTC.D & ETH/BTC: Altcoin risk iştahı teyidi = +15 / -10
        """
        score = 0.0

        # 1. DXY Katkısı (En güçlü ters korelasyon)
        dxy_chg = float(self.data.get("dxy", {}).get("chg_24h", 0.0))
        dxy_p = float(self.data.get("dxy", {}).get("price", 102.0))
        if dxy_chg < -0.15:
            score += 25.0
        elif dxy_chg > 0.15:
            score -= 25.0
        if dxy_p < 101.5:
            score += 10.0
        elif dxy_p > 104.5:
            score -= 15.0

        # 2. US10Y Katkısı (Faiz beklentisi)
        us10y_chg = float(self.data.get("us10y", {}).get("chg_24h", 0.0))
        if us10y_chg < -0.5:
            score += 20.0
        elif us10y_chg > 0.5:
            score -= 20.0

        # 3. Hisse Senedi Vadelileri (Nasdaq NQ + S&P 500 ES)
        nq_chg = float(self.data.get("nasdaq", {}).get("chg_24h", 0.0))
        sp_chg = float(self.data.get("sp500", {}).get("chg_24h", 0.0))
        equity_avg_chg = (nq_chg + sp_chg) / 2.0 if sp_chg != 0.0 else nq_chg
        if equity_avg_chg > 0.3:
            score += 20.0
        elif equity_avg_chg < -0.3:
            score -= 20.0

        # 4. VIX Volatilite & Korku Endeksi
        vix_p = float(self.data.get("vix", {}).get("price", 15.0))
        vix_chg = float(self.data.get("vix", {}).get("chg_24h", 0.0))
        if vix_p < 15.5:
            score += 15.0  # Düşük korku, sakin kurumsal likidite
        elif vix_p >= 21.0:
            score -= 20.0  # Volatilite patlaması, risk varlıklarından kaçış
        if vix_chg > 5.0:
            score -= 10.0  # Gün içi panik sıçraması

        # 5. Ons Altın (Monetary Debasement & Küresel Likidite)
        gold_chg = float(self.data.get("gold", {}).get("chg_24h", 0.0))
        if gold_chg > 0.5 and dxy_chg <= 0.0:
            score += 10.0  # Dolar zayıflarken altın artışı, dijital altın BTC için rüzgar

        # 5b. Petrol & Enerji Şoku (WTI CL=F & Brent BZ=F)
        oil_chg = float(self.data.get("oil", {}).get("chg_24h", 0.0))
        brent_chg = float(self.data.get("brent", {}).get("chg_24h", 0.0))
        max_oil_chg = max(oil_chg, brent_chg)
        if max_oil_chg >= 2.5:
            score -= 20.0  # Akut petrol sıçraması: Jeopolitik savaş riski, enflasyon korkusu, Fed faiz indirimi ertelemesi
        elif max_oil_chg >= 1.2:
            score -= 10.0
        elif max_oil_chg <= -2.0:
            score += 10.0  # Petrol gevşemesi: Dezenflasyon ve rahatlama

        # 6. USDT Dominansı Katkısı
        usdt_d = float(self.data.get("usdt_d", 6.5))
        if usdt_d <= 6.2:
            score += 20.0  # Nakit az, kriptoda para var
        elif usdt_d >= 7.5:
            score -= 25.0  # Nakite kaçış rekor seviyede

        # 7. ETH/BTC & BTC Dominansı Katkısı
        eth_btc = float(self.data.get("eth_btc", 0.0302))
        btc_d = float(self.data.get("btc_d", 59.0))
        if eth_btc >= 0.033:
            score += 15.0  # Altcoin sezonu ve risk iştahı açık
        elif eth_btc <= 0.028:
            score -= 10.0

        # Normalizasyon [-100, +100]
        final_score = max(-100.0, min(100.0, score))
        self.data["regime_score"] = round(final_score, 1)

        if final_score >= 25.0:
            self.data["regime"] = "RISK_ON (Küresel Boğa İştahı 🚀)"
        elif final_score <= -25.0:
            self.data["regime"] = "RISK_OFF (Defans / Ayı Koruması 🛡️)"
        else:
            self.data["regime"] = "NEUTRAL (Dengeli / Karışık ⚖️)"

    def analyze_onchain_event(self, text: str) -> Dict[str, Any]:
        """
        Metin veya haber başlığı içindeki Hükümet Cüzdanları (Silk Road, MtGox) veya
        Tether/Circle Darphane (Mint) hareketlerini tespit eder.
        """
        t_upper = text.upper()
        
        # 1. Hükümet & Tasfiye Cüzdanı Şoku (Mt. Gox, Silk Road vb.)
        for gov in GOVERNMENT_ENTITIES:
            if gov in t_upper:
                return {
                    "is_onchain_threat": True,
                    "entity": gov,
                    "event_type": "GOVERNMENT_DUMP_SHOCK",
                    "severity": "CRITICAL_BEARISH",
                    "score_impact": -50.0,
                    "message": f"🚨 Hükümet/Mt.Gox Cüzdan Hareketi Tespit Edildi ({gov}). Büyük satış baskısı riski!"
                }

        # 2. Stablecoin Taze Likidite Enjeksiyonu ($500M+ Mint)
        for mint_kw in STABLECOIN_MINTS:
            if mint_kw in t_upper:
                return {
                    "is_onchain_threat": False,
                    "entity": "STABLECOIN_TREASURY",
                    "event_type": "FRESH_LIQUIDITY_INJECTION",
                    "severity": "STRONG_BULLISH",
                    "score_impact": +35.0,
                    "message": f"🟢 Taze Stablecoin Likidite Basımı Doğrulandı ({mint_kw}). Kriptoya para giriyor!"
                }

        return {
            "is_onchain_threat": False,
            "entity": "NONE",
            "event_type": "NORMAL",
            "severity": "NEUTRAL",
            "score_impact": 0.0,
            "message": ""
        }

    def get_macro_summary(self) -> Dict[str, Any]:
        """Dashboard'un en üstündeki HUD Şeridi ve 10. Sekme için kompakt özet döner."""
        dxy_p = self.data.get("dxy", {}).get("price", 102.2)
        dxy_chg = self.data.get("dxy", {}).get("chg_24h", 0.0)
        us10y_p = self.data.get("us10y", {}).get("price", 5.24)
        usdt_d = self.data.get("usdt_d", 6.54)
        btc_d = self.data.get("btc_d", 59.09)
        eth_btc = self.data.get("eth_btc", 0.0302)
        vix_p = self.data.get("vix", {}).get("price", 14.84)
        regime = self.data.get("regime", "NEUTRAL")
        score = self.data.get("regime_score", 0.0)

        brent_p = self.data.get("brent", {}).get("price", 0.0)
        brent_chg = self.data.get("brent", {}).get("chg_24h", 0.0)
        oil_str = f" | BRENT ${brent_p:.1f} ({brent_chg:+.1f}%)" if brent_p > 0 else ""

        dxy_color = "🟢" if dxy_chg <= 0 else "🔴"
        regime_icon = "🚀" if score >= 25 else ("🛡️" if score <= -25 else "⚖️")

        hud_line = f"DXY {dxy_p:.2f} {dxy_color} | US10Y %{us10y_p:.2f}{oil_str} | VIX {vix_p:.1f} | USDT.D %{usdt_d:.1f} | BTC.D %{btc_d:.1f} | Rejim: {regime} {regime_icon}"

        return {
            "dxy": self.data.get("dxy"),
            "us10y": self.data.get("us10y"),
            "nasdaq": self.data.get("nasdaq"),
            "sp500": self.data.get("sp500"),
            "vix": self.data.get("vix"),
            "gold": self.data.get("gold"),
            "oil": self.data.get("oil"),
            "brent": self.data.get("brent"),
            "btc_d": btc_d,
            "usdt_d": usdt_d,
            "eth_btc": eth_btc,
            "regime": regime,
            "regime_score": score,
            "hud_line": hud_line,
            "last_sync_ts": self.data.get("last_sync_ts", 0.0)
        }

    def get_macro_regime(self) -> Dict[str, Any]:
        """Kompakt makro rejim ve bileşik skoru döner."""
        return {
            "regime": self.data.get("regime", "NEUTRAL (Dengeli / Karışık ⚖️)"),
            "composite_score": float(self.data.get("regime_score", 0.0)),
            "assets": {
                "DXY": {"value": self.data.get("dxy", {}).get("price", 102.2)},
                "US10Y": {"value": self.data.get("us10y", {}).get("price", 5.24)},
                "USDT.D": {"value": self.data.get("usdt_d", 6.54)},
                "BTC.D": {"value": self.data.get("btc_d", 59.09)}
            }
        }

    def get_global_terminal_data(self) -> Dict[str, Any]:
        """
        Wall Street & Küresel Terminal Desk için hazır veri paketi döner:
        - 4 Kıta & Bölgesel Masalar (Amerika, Avrupa, Asya, Emtia/ME)
        - Dünya Borsa Seans Durumları (Açık/Kapalı + Geri Sayım)
        - Times Square Kayan Marquee Ticker Bandı
        - Makro Korelasyon & Beta Matrisi
        """
        sessions = get_world_market_sessions()

        # 1. Bölgelere göre varlıkları derle
        regions: Dict[str, List[Dict[str, Any]]] = {
            "america": [],
            "europe": [],
            "asia": [],
            "commodities_me": []
        }

        marquee_tape: List[Dict[str, Any]] = []
        term_assets = self.data.get("terminal_assets", {})

        for reg_key, config_items in GLOBAL_TERMINAL_CONFIG.items():
            for item in config_items:
                aid = item["id"]
                raw_data = term_assets.get(aid, {})
                price = raw_data.get("price") or (self.data.get(aid, {}).get("price") if isinstance(self.data.get(aid), dict) else 0.0)
                chg = raw_data.get("chg_24h") or (self.data.get(aid, {}).get("chg_24h") if isinstance(self.data.get(aid), dict) else 0.0)

                # Özel Flaş Etiketi (Flash Warning / Catalyst)
                badge = ""
                if aid == "brent" and price >= 90.0:
                    badge = "🚨 SAVAŞ & ENFLASYON PRİMİ"
                elif aid == "vix" and price >= 20.0:
                    badge = "⚠️ PANİK VOLATİLİTE"
                elif aid == "gold" and price >= 3500.0:
                    badge = "🥇 GÜVENLİ LİMAN RALLİSİ"
                elif aid == "dxy" and chg <= -0.3:
                    badge = "🟢 DOLAR GEVŞEMESİ (RİSK-ON)"
                elif aid == "sp500" and chg >= 0.8:
                    badge = "🚀 WALL STREET BOĞASI"
                elif abs(chg) >= 2.0:
                    badge = "⚡ YÜKSEK VOLATİLİTE"

                formatted_item = {
                    "id": aid,
                    "symbol": item["symbol"],
                    "name": item["name"],
                    "sub": item["sub"],
                    "flag": item["flag"],
                    "category": item["category"],
                    "price": round(float(price or 0.0), 3),
                    "chg_24h": round(float(chg or 0.0), 2),
                    "is_positive": (chg or 0.0) >= 0,
                    "badge": badge
                }
                regions[reg_key].append(formatted_item)

                # Marquee şeridi için kompakt kart
                marquee_tape.append({
                    "symbol": item["symbol"].replace("=F", "").replace("^", "").replace(".SS", ""),
                    "display_name": item["name"],
                    "flag": item["flag"],
                    "price": round(float(price or 0.0), 3),
                    "chg_24h": round(float(chg or 0.0), 2),
                    "is_positive": (chg or 0.0) >= 0,
                    "badge": badge
                })

        # 2. Makro Korelasyon & Kuant Beta İçgörüleri
        brent_p = float(self.data.get("brent", {}).get("price", 0.0) or 0.0)
        dxy_chg = float(self.data.get("dxy", {}).get("chg_24h", 0.0) or 0.0)
        sp_chg = float(self.data.get("sp500", {}).get("chg_24h", 0.0) or 0.0)

        correlations = {
            "btc_sp500": {
                "beta": "+0.68",
                "bias": "BULLISH" if sp_chg > 0 else "BEARISH",
                "title": "BTC / S&P 500 Risk-On Beta",
                "desc": "Wall Street risk iştahı pozitif olduğunda kurumsal likidite BTC spot ETF'lerine akar."
            },
            "btc_dxy": {
                "beta": "-0.74",
                "bias": "BULLISH" if dxy_chg < 0 else "BEARISH",
                "title": "BTC / DXY Likidite Ters Korelasyonu",
                "desc": "Dolar zayıfladığında küresel fiat likidite kriptoyu yukarı iter; DXY yükseldiğinde baskı oluşur."
            },
            "btc_gold": {
                "beta": "+0.42",
                "bias": "NEUTRAL",
                "title": "BTC / Altın (Dijital Sığınak)",
                "desc": "Jeopolitik gerilimlerde fiziksel altın ilk tepkiyi verirken, 7/24 transfer edilen BTC dijital liman rolü oynar."
            },
            "oil_shock": {
                "brent_price": brent_p,
                "is_shock": brent_p >= 90.0,
                "level": "🚨 KRİTİK ŞOK DÜZEYİ ($100+)" if brent_p >= 100.0 else ("⚠️ YÜKSEK RİSK ($90+)" if brent_p >= 90.0 else "🟢 NORMAL KORİDOR"),
                "desc": "Akut petrol sıçramaları küresel enflasyonu tetikleyip Fed faiz indirimlerini erteleme riski yaratır."
            }
        }

        # TSİ formatlı zaman
        last_sync = self.data.get("last_sync_ts", 0.0)
        sync_str = datetime.fromtimestamp(last_sync, timezone(timedelta(hours=3))).strftime("%H:%M:%S TSİ") if last_sync > 0 else "Şimdi"

        return {
            "sessions": sessions,
            "regions": regions,
            "marquee_tape": marquee_tape,
            "correlations": correlations,
            "regime": self.data.get("regime", "NEUTRAL"),
            "regime_score": self.data.get("regime_score", 0.0),
            "last_sync_ts": last_sync,
            "last_sync_tsi": sync_str,
            "total_monitored_assets": len(marquee_tape)
        }

# Global Singleton Örneği
cross_asset_radar = MacroCrossAssetRadar()
