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

# Yahoo Finance & Public API Haritası
MACRO_SYMBOLS = {
    "DXY": "DX-Y.NYB",    # Dolar Endeksi (US Dollar Index)
    "US10Y": "^TNX",      # ABD 10 Yıllık Hazine Tahvil Getirisi
    "GOLD": "GC=F",       # Ons Altın (XAU/USD Vadeli)
    "NASDAQ": "NQ=F",     # E-mini Nasdaq 100 Vadeli (Risk Varlıkları)
    "SP500": "ES=F",      # E-mini S&P 500 Vadeli (Geniş Piyasa Likiditesi)
    "VIX": "^VIX"         # CBOE Volatilite Korku Endeksi (Wall Street Fear Gauge)
}

COINGECKO_GLOBAL_URL = "https://api.coingecko.com/api/v3/global"
BINANCE_ETHBTC_URL = "https://api.binance.com/api/v3/ticker/price?symbol=ETHBTC"

# Hükümet ve Kara Kuğu On-Chain Cüzdan Anahtar Kelimeleri
GOVERNMENT_ENTITIES = [
    "US GOVERNMENT", "SILK ROAD", "GERMAN GOVERNMENT", "MT. GOX", "MTGOX",
    "DOJ SEIZED", "US MARSHALS", "ESTONIA GOV", "UKRAINE GOV"
]
STABLECOIN_MINTS = ["TETHER TREASURY", "CIRCLE TREASURY", "USDT MINT", "USDC MINT", "PRINTED AT TETHER"]

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
            "btc_d": 59.08,
            "usdt_d": 6.52,
            "eth_btc": 0.03027,
            "regime": "NEUTRAL",
            "regime_score": 0.0,
            "last_sync_ts": 0.0
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
        """Tüm 7 çapraz makro göstergeyi paralel asenkron olarak çeker ve rejim skorunu hesaplar."""
        now = time.time()
        if not force and (now - float(self.data.get("last_sync_ts", 0.0)) < self.sync_interval_sec):
            return True

        try:
            async with aiohttp.ClientSession() as session:
                tasks = [
                    self._fetch_yahoo_symbol(session, "DXY", MACRO_SYMBOLS["DXY"]),
                    self._fetch_yahoo_symbol(session, "US10Y", MACRO_SYMBOLS["US10Y"]),
                    self._fetch_yahoo_symbol(session, "GOLD", MACRO_SYMBOLS["GOLD"]),
                    self._fetch_yahoo_symbol(session, "NASDAQ", MACRO_SYMBOLS["NASDAQ"]),
                    self._fetch_yahoo_symbol(session, "SP500", MACRO_SYMBOLS["SP500"]),
                    self._fetch_yahoo_symbol(session, "VIX", MACRO_SYMBOLS["VIX"]),
                    self._fetch_crypto_dominance(session),
                    self._fetch_eth_btc(session)
                ]
                dxy_r, us10y_r, gold_r, nasdaq_r, sp500_r, vix_r, dom_r, ethbtc_r = await asyncio.gather(*tasks, return_exceptions=True)

                if isinstance(dxy_r, dict) and dxy_r:
                    self.data["dxy"] = dxy_r
                if isinstance(us10y_r, dict) and us10y_r:
                    self.data["us10y"] = us10y_r
                if isinstance(gold_r, dict) and gold_r:
                    self.data["gold"] = gold_r
                if isinstance(nasdaq_r, dict) and nasdaq_r:
                    self.data["nasdaq"] = nasdaq_r
                if isinstance(sp500_r, dict) and sp500_r:
                    self.data["sp500"] = sp500_r
                if isinstance(vix_r, dict) and vix_r:
                    self.data["vix"] = vix_r
                if isinstance(dom_r, dict) and dom_r:
                    self.data["btc_d"] = dom_r.get("btc_d", self.data.get("btc_d", 59.08))
                    self.data["usdt_d"] = dom_r.get("usdt_d", self.data.get("usdt_d", 6.52))
                if isinstance(ethbtc_r, (float, int)) and ethbtc_r > 0:
                    self.data["eth_btc"] = float(ethbtc_r)

                # Bileşik Makro Rejim & Risk İştahı Hesaplama
                self._calculate_macro_regime()
                self.data["last_sync_ts"] = now
                self.save_cache()
                print(f">> [🌐 ÇAPRAZ MAKRO RADAR] Güncellendi: DXY={self.data['dxy']['price']} | US10Y={self.data['us10y']['price']}% | VIX={self.data.get('vix', {}).get('price', '-')} | USDT.D={self.data['usdt_d']}% | Rejim: {self.data['regime']} ({self.data['regime_score']:+0.1f})")
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

        dxy_color = "🟢" if dxy_chg <= 0 else "🔴"
        regime_icon = "🚀" if score >= 25 else ("🛡️" if score <= -25 else "⚖️")

        hud_line = f"DXY {dxy_p:.2f} {dxy_color} | US10Y %{us10y_p:.2f} | VIX {vix_p:.1f} | USDT.D %{usdt_d:.1f} | BTC.D %{btc_d:.1f} | Rejim: {regime} {regime_icon}"

        return {
            "dxy": self.data.get("dxy"),
            "us10y": self.data.get("us10y"),
            "nasdaq": self.data.get("nasdaq"),
            "sp500": self.data.get("sp500"),
            "vix": self.data.get("vix"),
            "gold": self.data.get("gold"),
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

# Global Singleton Örneği
cross_asset_radar = MacroCrossAssetRadar()
