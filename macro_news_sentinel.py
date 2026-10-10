"""
🦅 VALKYRIE QUANT - DÜŞÜK GECİKMELİ FLAŞ HABER VE BİRİNCİL İSTİHBARAT MOTORU (MACRO NEWS SENTINEL)
TreeNews (Tier10k), SEC EDGAR (Form 8-K) ve Federal Reserve resmi bültenlerinden
anlık beslenen, makam sahibini (Fed Başkanı, SEC Başkanı, POTUS) sınıflandıran,
yalan haber manipülasyonunu engelleyen ve dashboard'a canlı flaş haber sağlayan motor.
"""

import os
import json
import time
import asyncio
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
import aiohttp

from macro_roles import role_registry

NEWS_HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "macro_news_history.json")
TREENEWS_API_URL = "https://news.treeofalpha.com/api/news?limit=25"
SEC_EDGAR_ATOM_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&output=atom"
FED_PRESS_RSS_URL = "https://www.federalreserve.gov/feeds/press_all.xml"

# Kategori Anahtar Kelimeleri
CATEGORY_RULES = {
    "REGULATION": ["SEC", "ETF", "GENSLER", "LAWSUIT", "DAVA", "COMMISSION", "REGULATION", "CFTC", "DOJ", "BINANCE", "COINBASE", "RIPPLE", "XRP"],
    "MACRO_DATA": ["CPI", "TÜFE", "INFLATION", "FOMC", "POWELL", "FED", "RATE CUT", "FAİZ", "NFP", "JOBS", "UNEMPLOYMENT", "PPI", "GDP"],
    "EXPLOIT_HACK": ["HACK", "EXPLOIT", "STOLEN", "DRAINED", "VULNERABILITY", "ATTACK", "SALDIRI", "VULNERABILITY"],
    "POLITICAL": ["TRUMP", "BIDEN", "WHITE HOUSE", "BEYAZ SARAY", "PRESIDENT", "CONGRESS", "SENATE", "ELECTION", "TARİFE", "TARIFF"],
}

# Hızlı Duygu & Etki Puanı Kütüphanesi (Fast Sentiment Scoring)
BULLISH_KEYWORDS = ["APPROVED", "APPROVAL", "ONAYLANDI", "RATE CUT", "FAİZ İNDİRİMİ", "BEAT", "LOWER INFLATION", "INFLOW", "GİRİŞ", "ACQUIRE", "RESERVE", "REZERV", "WIN", "KAZANDI"]
BEARISH_KEYWORDS = ["SUED", "LAWSUIT", "DAVA", "REJECTED", "REDDEDİLDİ", "BAN", "YASAK", "HIKE", "FAİZ ARTIRIMI", "HACK", "EXPLOIT", "OUTFLOW", "ÇIKIŞ", "FINE", "CEZA", "CRASH", "DUMP"]

class MacroNewsSentinel:
    """Çok Kaynaklı Flaş Haber ve Birincil İstihbarat Bekçisi."""

    def __init__(self, history_file: str = NEWS_HISTORY_FILE):
        self.history_file = history_file
        self.news_items: List[Dict[str, Any]] = []
        self.seen_signatures: set = set()
        self.last_sync_ts: float = 0.0
        self.load_history()

    def load_history(self) -> None:
        """Geçmiş haber kayıtlarını yükle."""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.news_items = data.get("news", [])
                    for item in self.news_items:
                        sig = self._create_signature(item.get("title", ""), item.get("source", ""))
                        self.seen_signatures.add(sig)
            except Exception as e:
                print(f">> [HABER GEÇMİŞİ OKUMA UYARI] {e}")

    def save_history(self) -> None:
        """Haber kayıtlarını diske kaydet (Son 100 haber tutulur)."""
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump({
                    "last_sync_ts": self.last_sync_ts,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "news": self.news_items[-100:]
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f">> [HABER GEÇMİŞİ KAYIT HATA] {e}")

    def _create_signature(self, title: str, source: str) -> str:
        """Haber mükerrerliğini önleyen temiz imza üretir."""
        clean = re.sub(r"[^a-zA-Z0-9]", "", title.lower())[:60]
        return f"{source}:{clean}"

    def _analyze_headline(self, title: str, source: str, raw_ts: float) -> Dict[str, Any]:
        """
        Gelen haber başlığını analiz eder:
        1. Kategori sınıflandırması (Makro, Regülasyon, Hack, Siyasi)
        2. Dinamik Yetkili tespiti (Powell, Gensler, Trump)
        3. Duygu & Kripto Etki Puanı [-100, +100]
        """
        title_upper = title.upper()
        
        # 1. Kategori Tespiti
        category = "GENERAL_CRYPTO"
        for cat, kw_list in CATEGORY_RULES.items():
            if any(kw in title_upper for kw in kw_list):
                category = cat
                break

        # 2. Dinamik Makam ve Konuşmacı Sınıflandırması & Otomatik Liderlik Değişimi (Faz 6C)
        try:
            role_registry.detect_leadership_changes(title)
        except Exception:
            pass
        speaker_info = role_registry.classify_text_speaker(title)

        # 3. Kripto Etki Puanı (Hızlı Kuant Skorlama)
        score = 0.0
        for b in BULLISH_KEYWORDS:
            if b in title_upper:
                score += 35.0
        for b in BEARISH_KEYWORDS:
            if b in title_upper:
                score -= 40.0

        # Eğer makam sahibi konuştuysa ağırlığı çarpanla artır
        if speaker_info.get("has_official", False):
            weight = speaker_info.get("market_weight", 1.0)
            score = score * (1.0 + weight)

        # Normalizasyon [-100, +100]
        final_score = max(-100.0, min(100.0, score))

        # Saat formatı (TSİ UTC+3)
        ev_dt = datetime.fromtimestamp(raw_ts, tz=timezone(timedelta(hours=3)))
        time_str = ev_dt.strftime("%H:%M:%S")

        is_primary_official = source in ["SEC_EDGAR", "FED_OFFICIAL"]

        # Faz 6B: Alıntı Grafiği ve Otomatik Kaynak Keşfi (Citation Graph Crawler)
        try:
            from macro_source_evolution import source_evolution_engine
            source_evolution_engine.crawl_and_extract_citations(title, source)
        except Exception:
            pass

        return {
            "title": title.strip(),
            "source": source,
            "timestamp": raw_ts,
            "time_tsi": time_str,
            "category": category,
            "sentiment_score": round(final_score, 1),
            "speaker_info": speaker_info,
            "is_primary_official": is_primary_official,
            "is_verified": is_primary_official or (speaker_info.get("has_official") and speaker_info.get("market_weight", 0) >= 0.8)
        }

    async def fetch_treenews(self) -> List[Dict[str, Any]]:
        """TreeNews resmi API'sinden en taze flaş haberleri çeker (<100ms)."""
        headers = {"User-Agent": "Mozilla/5.0"}
        new_items = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(TREENEWS_API_URL, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for item in data:
                            title = item.get("title", "").strip()
                            if not title:
                                continue
                            raw_ms = item.get("time", int(time.time() * 1000))
                            raw_ts = raw_ms / 1000.0 if raw_ms > 1e11 else float(raw_ms)
                            src = f"TreeNews:{item.get('source', 'wire')}"

                            sig = self._create_signature(title, "TreeNews")
                            if sig not in self.seen_signatures:
                                self.seen_signatures.add(sig)
                                parsed = self._analyze_headline(title, src, raw_ts)
                                new_items.append(parsed)
        except Exception as e:
            # Sessiz ağ hatası toleransı
            pass
        return new_items

    async def fetch_sec_edgar(self) -> List[Dict[str, Any]]:
        """SEC EDGAR RSS resmi Form 8-K akışından kurumsal bildirimleri çeker."""
        headers = {"User-Agent": "ValkyrieQuant/2.0 (quant_desk@valkyrie.ai)"}
        new_items = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(SEC_EDGAR_ATOM_URL, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        xml_text = await resp.text()
                        root = ET.fromstring(xml_text)
                        # Atom namespace
                        ns = {"atom": "http://www.w3.org/2005/Atom"}
                        for entry in root.findall("atom:entry", ns)[:10]:
                            title_elem = entry.find("atom:title", ns)
                            title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
                            if not title:
                                continue
                            
                            sig = self._create_signature(title, "SEC_EDGAR")
                            if sig not in self.seen_signatures:
                                self.seen_signatures.add(sig)
                                parsed = self._analyze_headline(f"[SEC 8-K RESMİ BİLDİRİM] {title}", "SEC_EDGAR", time.time())
                                new_items.append(parsed)
        except Exception:
            pass
        return new_items

    async def fetch_fed_press(self) -> List[Dict[str, Any]]:
        """Federal Reserve resmi web sitesinden en son basın bültenlerini çeker."""
        headers = {"User-Agent": "Mozilla/5.0"}
        new_items = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(FED_PRESS_RSS_URL, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        xml_text = await resp.text()
                        root = ET.fromstring(xml_text)
                        for item in root.findall(".//item")[:8]:
                            title_elem = item.find("title")
                            title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
                            if not title:
                                continue

                            sig = self._create_signature(title, "FED_OFFICIAL")
                            if sig not in self.seen_signatures:
                                self.seen_signatures.add(sig)
                                parsed = self._analyze_headline(f"[FED RESMİ AÇIKLAMA] {title}", "FED_OFFICIAL", time.time())
                                new_items.append(parsed)
        except Exception:
            pass
        return new_items

    async def sync_all_sources(self) -> int:
        """Tüm kaynakları eşzamanlı olarak tarar ve hafızayı günceller."""
        t_tasks = [self.fetch_treenews(), self.fetch_sec_edgar(), self.fetch_fed_press()]
        results = await asyncio.gather(*t_tasks, return_exceptions=True)

        added_count = 0
        for res in results:
            if isinstance(res, list) and res:
                for item in res:
                    self.news_items.append(item)
                    added_count += 1

        if added_count > 0:
            # Kronolojik sırala ve diske kaydet
            self.news_items.sort(key=lambda x: x["timestamp"])
            self.news_items = self.news_items[-100:]  # Son 100 haber
            self.last_sync_ts = time.time()
            self.save_history()
            print(f">> [⚡ FLAŞ İSTİHBARAT] {added_count} taze haber/bildirim hafızaya işlendi.")

        return added_count

    def get_latest_news(self, limit: int = 15) -> List[Dict[str, Any]]:
        """En güncel haberleri döner (Yeni haber en başta)."""
        return list(reversed(self.news_items))[:limit]

    def get_flash_breaking_alert(self) -> Optional[Dict[str, Any]]:
        """
        Dashboard'un en üstündeki HUD Şeridi için:
        Son 1 saat içindeki EN ETKİLİ tek bir son dakika haberini döner.
        """
        now = time.time()
        # Son 1 saatteki kritik haberleri tara
        recent_candidates = [n for n in self.news_items if (now - n.get("timestamp", 0) <= 3600)]
        if not recent_candidates:
            # Eğer son 1 saatte flaş yoksa, hafızadaki en son teyitli haberi ver
            if self.news_items:
                return self.news_items[-1]
            return None

        # En yüksek etki skoruna veya resmi makam ağırlığına göre seç
        recent_candidates.sort(
            key=lambda x: abs(float(x.get("sentiment_score", 0.0))) + (50.0 if x.get("is_primary_official") else 0.0),
            reverse=True
        )
        return recent_candidates[0]

    def get_news_bias(self) -> Dict[str, Any]:
        """Son haberlerin kümülatif duygu ve yönelimini hesaplar."""
        recent = self.news_items[-20:] if self.news_items else []
        if not recent:
            return {"bias": "NEUTRAL", "score": 0.0, "bullish_count": 0, "bearish_count": 0}

        scores = [float(n.get("sentiment_score", 0.0)) for n in recent]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        bull_cnt = sum(1 for s in scores if s > 15.0)
        bear_cnt = sum(1 for s in scores if s < -15.0)

        bias = "NEUTRAL"
        if avg_score >= 20.0:
            bias = "BULLISH"
        elif avg_score <= -20.0:
            bias = "BEARISH"

        return {
            "bias": bias,
            "score": round(avg_score, 1),
            "bullish_count": bull_cnt,
            "bearish_count": bear_cnt
        }

# Global Singleton Örneği
macro_news = MacroNewsSentinel()
news_sentinel = macro_news
