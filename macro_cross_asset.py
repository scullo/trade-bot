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
    "NASDAQ": "NQ=F"      # E-mini Nasdaq 100 Vadeli (Risk Varlıkları)
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
            "dxy": {"price": 102.20, "chg_24h": 0.0, "status": "NEUTRAL"},
            "us10y": {"price": 5.20, "chg_24h": 0.0, "status": "NEUTRAL"},
            "nasdaq": {"price": 31000.0, "chg_24h": 0.0, "status": "NEUTRAL"},
            "gold": {"price": 4200.0, "chg_24h": 0.0, "status": "NEUTRAL"},
            "btc_d": 59.0,
            "usdt_d": 6.5,
            "eth_btc": 0.0302,
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
                    self._fetch_crypto_dominance(session),
                    self._fetch_eth_btc(session)
                ]
                dxy_r, us10y_r, gold_r, nasdaq_r, dom_r, ethbtc_r = await asyncio.gather(*tasks, return_exceptions=True)

                if isinstance(dxy_r, dict) and dxy_r:
                    self.data["dxy"] = dxy_r
                if isinstance(us10y_r, dict) and us10y_r:
                    self.data["us10y"] = us10y_r
                if isinstance(gold_r, dict) and gold_r:
                    self.data["gold"] = gold_r
                if isinstance(nasdaq_r, dict) and nasdaq_r:
                    self.data["nasdaq"] = nasdaq_r
                if isinstance(dom_r, dict) and dom_r:
                    self.data["btc_d"] = dom_r.get("btc_d", self.data.get("btc_d", 59.0))
                    self.data["usdt_d"] = dom_r.get("usdt_d", self.data.get("usdt_d", 6.5))
                if isinstance(ethbtc_r, (float, int)) and ethbtc_r > 0:
                    self.data["eth_btc"] = float(ethbtc_r)

                # Bileşik Makro Rejim & Risk İştahı Hesaplama
                self._calculate_macro_regime()
                self.data["last_sync_ts"] = now
                self.save_cache()
                print(f">> [🌐 ÇAPRAZ MAKRO RADAR] Güncellendi: DXY={self.data['dxy']['price']} | US10Y={self.data['us10y']['price']}% | USDT.D={self.data['usdt_d']}% | Rejim: {self.data['regime']} ({self.data['regime_score']:+0.1f})")
                return True

        except Exception as e:
            print(f">> [ÇAPRAZ MAKRO SENKRONİZASYON HATA] {e}")
            return False

    def _calculate_macro_regime(self) -> None:
        """
        Kripto için Bileşik Küresel Risk İştahı (Risk-On / Risk-Off) Skoru [-100, +100]:
        1. DXY (Dolar Endeksi): Düşüşteyse = +25 (Boğa), Yükselişteyse = -25 (Ayı)
        2. US10Y (10 Yıllık Faiz): Düşüşteyse = +20 (Faiz gevşemesi boğa), Yükselişteyse = -20
        3. Nasdaq: Yükselişteyse = +20 (Risk iştahı açık), Düşüşteyse = -20
        4. USDT.D (Stablecoin Dominansı): %6.5 altına geriliyorsa nakit coinlere akıyor = +20
        5. ETH/BTC: Yükselişteyse = +15 (Altseason rüzgarı)
        """
        score = 0.0

        # 1. DXY Katkısı
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

        # 2. US10Y Katkısı
        us10y_chg = float(self.data.get("us10y", {}).get("chg_24h", 0.0))
        if us10y_chg < -0.5:
            score += 20.0
        elif us10y_chg > 0.5:
            score -= 20.0

        # 3. Nasdaq Katkısı
        nq_chg = float(self.data.get("nasdaq", {}).get("chg_24h", 0.0))
        if nq_chg > 0.3:
            score += 20.0
        elif nq_chg < -0.3:
            score -= 20.0

        # 4. USDT Dominansı Katkısı
        usdt_d = float(self.data.get("usdt_d", 6.5))
        if usdt_d <= 6.2:
            score += 20.0  # Nakit az, kriptoda para var
        elif usdt_d >= 7.5:
            score -= 25.0  # Nakite kaçış rekor seviyede

        # 5. ETH/BTC Katkısı
        eth_btc = float(self.data.get("eth_btc", 0.0302))
        if eth_btc >= 0.035:
            score += 15.0
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
        regime = self.data.get("regime", "NEUTRAL")
        score = self.data.get("regime_score", 0.0)

        dxy_color = "🟢" if dxy_chg <= 0 else "🔴"
        regime_icon = "🚀" if score >= 25 else ("🛡️" if score <= -25 else "⚖️")

        hud_line = f"DXY {dxy_p:.2f} {dxy_color} | US10Y %{us10y_p:.2f} | USDT.D %{usdt_d:.1f} | BTC.D %{btc_d:.1f} | Rejim: {regime} {regime_icon}"

        return {
            "dxy": self.data.get("dxy"),
            "us10y": self.data.get("us10y"),
            "nasdaq": self.data.get("nasdaq"),
            "gold": self.data.get("gold"),
            "btc_d": btc_d,
            "usdt_d": usdt_d,
            "eth_btc": eth_btc,
            "regime": regime,
            "regime_score": score,
            "hud_line": hud_line,
            "last_sync_ts": self.data.get("last_sync_ts", 0.0)
        }

# Global Singleton Örneği
cross_asset_radar = MacroCrossAssetRadar()
