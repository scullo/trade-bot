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
import email.utils
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
import aiohttp

from macro_roles import role_registry
from macro_ai_interpreter import ai_interpreter

NEWS_HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "macro_news_history.json")
TREENEWS_API_URL = "https://news.treeofalpha.com/api/news?limit=25"
SEC_EDGAR_ATOM_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&output=atom"
FED_PRESS_RSS_URL = "https://www.federalreserve.gov/feeds/press_all.xml"

# Canlı Kripto Medya & Haber Siteleri RSS Kaynakları (24/7 Kesintisiz Akış)
CRYPTO_MEDIA_RSS_URLS = {
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "CoinTelegraph": "https://cointelegraph.com/rss",
    "Decrypt": "https://decrypt.co/feed",
    "TheBlock": "https://www.theblock.co/rss.xml"
}

# SEC Bildirimlerinde Doğrudan Kripto / Finans İlgisi Filtresi
SEC_CRYPTO_KEYWORDS = [
    "BITCOIN", "BTC", "ETH", "ETHEREUM", "CRYPTO", "DIGITAL ASSET", "ETF",
    "COINBASE", "MICROSTRATEGY", "MARA", "RIOT", "GRAYSCALE", "BLACKROCK",
    "FIDELITY", "ROBINHOOD", "CIRCLE", "BLOCKCHAIN", "MINING", "TOKEN",
    "SECURITIES AND EXCHANGE", "LITIGATION", "COMMISSIONER", "ATKINS", "PEIRCE"
]

# Kategori Anahtar Kelimeleri
CATEGORY_RULES = {
    "REGULATION": ["SEC", "ETF", "GENSLER", "LAWSUIT", "DAVA", "COMMISSION", "REGULATION", "CFTC", "DOJ", "BINANCE", "COINBASE", "RIPPLE", "XRP", "ATKINS", "COMMISSIONER"],
    "MACRO_DATA": ["CPI", "TÜFE", "INFLATION", "FOMC", "POWELL", "WARSH", "FED", "RATE CUT", "FAİZ", "NFP", "JOBS", "UNEMPLOYMENT", "PPI", "GDP", "TREASURY", "BESSENT"],
    "EXPLOIT_HACK": ["HACK", "EXPLOIT", "STOLEN", "DRAINED", "VULNERABILITY", "ATTACK", "SALDIRI", "PHISHING", "DRAIN"],
    "POLITICAL": ["TRUMP", "BIDEN", "WHITE HOUSE", "BEYAZ SARAY", "PRESIDENT", "CONGRESS", "SENATE", "ELECTION", "TARİFE", "TARIFF"],
}

# Hızlı Duygu & Etki Puanı Kütüphanesi (Genişletilmiş Kuant Sözlüğü)
BULLISH_KEYWORDS = [
    "APPROVED", "APPROVAL", "ONAYLANDI", "RATE CUT", "FAİZ İNDİRİMİ", "BEAT",
    "LOWER INFLATION", "INFLOW", "INFLOWS", "GİRİŞ", "ACQUIRE", "ACQUIRES", "RESERVE", "REZERV", "WIN", "KAZANDI",
    "STAKING", "PARTNERSHIP", "MAINNET", "UPGRADE", "ALL TIME HIGH", "ATH", "RECORD HIGH", "ACCUMULATION",
    "NET INFLOW", "SEC CLEARS", "DISMISSED", "ETF APPROVAL", "ETFS", "TREASURY BUY", "AIRDROP", "LISTING",
    "RALLY", "SURGE", "BREAKOUT", "BULLISH", "BOĞA", "GÜVERCİN", "DOVISH", "INFLOW OF", "EXPANSION", "BUYING"
]
BEARISH_KEYWORDS = [
    "SUED", "LAWSUIT", "DAVA", "REJECTED", "REJECTS", "REDDEDİLDİ", "BAN", "BANNED", "YASAK", "HIKE", "RATE HIKE",
    "FAİZ ARTIRIMI", "HACK", "HACKED", "EXPLOIT", "EXPLOITED", "OUTFLOW", "OUTFLOWS", "ÇIKIŞ", "FINE", "CEZA", "CRASH", "DUMP",
    "PHISHING", "INSOLVENT", "INSOLVENCY", "BANKRUPT", "BANKRUPTCY", "CHAPTER 11", "SEC SUES", "SUBPOENA", "PROBE",
    "INVESTIGATION", "SANCTION", "DELAYED", "NET OUTFLOW", "DOWNGRADED", "SECURITY BREACH", "BEARISH", "AYI", "ŞAHİN", "HAWKISH"
]

TRANSLATION_CACHE: Dict[str, str] = {}

def translate_to_turkish(text: str) -> str:
    """
    İngilizce haber başlıklarını ve metinlerini akıcı Türkçeye çevirir.
    Google Translate gtx servisi kullanılır, önbellekleme (cache) destekler.
    """
    if not text or not str(text).strip():
        return ""
    clean_text = str(text).strip()
    if clean_text in TRANSLATION_CACHE:
        return TRANSLATION_CACHE[clean_text]

    prefix = ""
    m = re.match(r"^(\[.*?\])\s*(.*)$", clean_text)
    if m:
        prefix = m.group(1) + " "
        clean_text = m.group(2)

    try:
        import urllib.request
        import urllib.parse
        url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=tr&dt=t&q=" + urllib.parse.quote(clean_text)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=3.0) as response:
            res = json.loads(response.read().decode("utf-8"))
            translated = "".join([part[0] for part in res[0] if part[0]])
            if translated and len(translated.strip()) > 1:
                res_tr = (prefix + translated.strip()).strip()
                TRANSLATION_CACHE[str(text).strip()] = res_tr
                return res_tr
    except Exception:
        pass

    TRANSLATION_CACHE[str(text).strip()] = str(text).strip()
    return str(text).strip()

class MacroNewsSentinel:
    """Çok Kaynaklı Flaş Haber ve Birincil İstihbarat Bekçisi."""

    def __init__(self, history_file: str = NEWS_HISTORY_FILE):
        self.history_file = history_file
        self.news_items: List[Dict[str, Any]] = []
        self.seen_signatures: set = set()
        self.last_sync_ts: float = 0.0
        self.load_history()

    def load_history(self) -> None:
        """Geçmiş haber kayıtlarını yükle ve yapay zeka istihbaratını zenginleştir."""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.news_items = data.get("news", [])
                    has_upgrades = False
                    for item in self.news_items:
                        sig = self._create_signature(item.get("title", ""), item.get("source", ""))
                        self.seen_signatures.add(sig)
                        # Başlık Türkçe çevirisi yoksa ekle
                        if not item.get("title_tr"):
                            item["title_tr"] = translate_to_turkish(item.get("title", ""))
                            has_upgrades = True
                        # Yapay zeka yorumu eksikse otomatik tamamla
                        if not item.get("ai_summary") or not item.get("ai_interpretation") or item.get("speaker") == "Resmi Makam / Fed":
                            ai_data = ai_interpreter.analyze_news_ai(item)
                            item.update(ai_data)
                            item["speaker"] = ai_data.get("actual_entity", item.get("speaker", "Genel Piyasa"))
                            has_upgrades = True
                    if has_upgrades:
                        self.save_history()
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

    def _analyze_headline(self, title: str, source: str, raw_ts: float, url: str = "") -> Dict[str, Any]:
        """
        Gelen haber başlığını analiz eder:
        1. Kategori sınıflandırması (Makro, Regülasyon, Hack, Siyasi)
        2. Dinamik Yetkili tespiti (Kevin Warsh, Paul Atkins, Trump vb.)
        3. Duygu & Kripto Etki Puanı [-100, +100]
        4. Orijinal Kaynak URL'si / Arama Bağlantısı
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

        # Orijinal Haber URL'si (Doğrudan link yoksa akıllı X/Web arama linki)
        if not url:
            import urllib.parse
            clean_search = re.sub(r"\[.*?\]", "", title).strip()
            url = f"https://x.com/search?q={urllib.parse.quote(clean_search[:65])}"

        # 🇹🇷 Türkçe Başlık Çevirisi (Anlık & Önbellekli)
        title_tr = translate_to_turkish(title)

        # 🧠 Yapay Zeka Adli İstihbarat & Kuant Analiz Motoru
        temp_item = {
            "title": title.strip(),
            "title_tr": title_tr,
            "source": source,
            "sentiment_score": round(final_score, 1),
            "speaker_info": speaker_info,
            "category": category
        }
        ai_data = ai_interpreter.analyze_news_ai(temp_item)

        return {
            "title": title.strip(),
            "title_tr": title_tr,
            "source": source,
            "url": url,
            "timestamp": raw_ts,
            "time_tsi": time_str,
            "category": category,
            "sentiment_score": round(final_score, 1),
            "speaker_info": speaker_info,
            "speaker": ai_data.get("actual_entity", speaker_info.get("role_title", "Genel Piyasa")),
            "is_primary_official": is_primary_official,
            "is_verified": is_primary_official or (speaker_info.get("has_official") and speaker_info.get("market_weight", 0) >= 0.8),
            "ai_summary": ai_data.get("ai_summary", ""),
            "ai_interpretation": ai_data.get("ai_interpretation", ""),
            "market_impact": ai_data.get("market_impact", ""),
            "impact_direction": ai_data.get("impact_direction", "NEUTRAL"),
            "score_explanation": ai_data.get("score_explanation", ""),
            "strategy_action": ai_data.get("strategy_action", "")
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
                            link = item.get("link") or item.get("url") or ""

                            sig = self._create_signature(title, "TreeNews")
                            if sig not in self.seen_signatures:
                                self.seen_signatures.add(sig)
                                parsed = self._analyze_headline(title, src, raw_ts, url=link)
                                new_items.append(parsed)
        except Exception as e:
            # Sessiz ağ hatası toleransı
            pass
        return new_items

    async def fetch_crypto_media_rss(self) -> List[Dict[str, Any]]:
        """Dünyanın en büyük kripto haber sitelerinden (CoinDesk, CoinTelegraph, Decrypt, The Block) canlı RSS beslemelerini çeker."""
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        new_items = []
        try:
            async with aiohttp.ClientSession() as session:
                for site_name, rss_url in CRYPTO_MEDIA_RSS_URLS.items():
                    try:
                        async with session.get(rss_url, headers=headers, timeout=aiohttp.ClientTimeout(total=7)) as resp:
                            if resp.status == 200:
                                xml_text = await resp.text()
                                root = ET.fromstring(xml_text)
                                for item in root.findall(".//item")[:10]:
                                    title_elem = item.find("title")
                                    title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
                                    if not title:
                                        continue
                                    link_elem = item.find("link")
                                    link = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
                                    pub_elem = item.find("pubDate")
                                    raw_ts = time.time()
                                    if pub_elem is not None and pub_elem.text:
                                        try:
                                            raw_ts = email.utils.parsedate_to_datetime(pub_elem.text.strip()).timestamp()
                                        except Exception:
                                            pass

                                    sig = self._create_signature(title, site_name)
                                    if sig not in self.seen_signatures:
                                        self.seen_signatures.add(sig)
                                        parsed = self._analyze_headline(title, site_name, raw_ts, url=link)
                                        new_items.append(parsed)
                    except Exception:
                        pass
        except Exception:
            pass
        return new_items

    async def fetch_sec_edgar(self) -> List[Dict[str, Any]]:
        """SEC EDGAR RSS resmi Form 8-K akışından kurumsal bildirimleri çeker (Yalnızca Kripto/Finans odaklı)."""
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
                        for entry in root.findall("atom:entry", ns)[:15]:
                            title_elem = entry.find("atom:title", ns)
                            title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
                            if not title:
                                continue

                            # Kripto Dışı Alakasız Şirketleri Filtrele (Medikal, otomotiv vb.)
                            t_upper = title.upper()
                            is_crypto_relevant = any(kw in t_upper for kw in SEC_CRYPTO_KEYWORDS)
                            if not is_crypto_relevant:
                                continue
                            
                            link_elem = entry.find("atom:link", ns)
                            link = link_elem.attrib.get("href", "") if link_elem is not None else "https://www.sec.gov/edgar/searchedgar/companysearch"

                            updated_elem = entry.find("atom:updated", ns)
                            raw_ts = time.time()
                            if updated_elem is not None and updated_elem.text:
                                try:
                                    raw_ts = datetime.fromisoformat(updated_elem.text.replace("Z", "+00:00")).timestamp()
                                except Exception:
                                    pass

                            sig = self._create_signature(title, "SEC_EDGAR")
                            if sig not in self.seen_signatures:
                                self.seen_signatures.add(sig)
                                parsed = self._analyze_headline(f"[SEC 8-K RESMİ BİLDİRİM] {title}", "SEC_EDGAR", raw_ts, url=link)
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

                            link_elem = item.find("link")
                            link = link_elem.text.strip() if link_elem is not None and link_elem.text else "https://www.federalreserve.gov/newsevents/pressreleases.htm"

                            pub_elem = item.find("pubDate")
                            raw_ts = time.time()
                            if pub_elem is not None and pub_elem.text:
                                try:
                                    raw_ts = email.utils.parsedate_to_datetime(pub_elem.text.strip()).timestamp()
                                except Exception:
                                    pass

                            sig = self._create_signature(title, "FED_OFFICIAL")
                            if sig not in self.seen_signatures:
                                self.seen_signatures.add(sig)
                                parsed = self._analyze_headline(f"[FED RESMİ AÇIKLAMA] {title}", "FED_OFFICIAL", raw_ts, url=link)
                                new_items.append(parsed)
        except Exception:
            pass
        return new_items

    async def sync_all_sources(self) -> int:
        """Tüm kaynakları (TreeNews, CoinDesk, CoinTelegraph, Decrypt, The Block, SEC, Fed) eşzamanlı tarar."""
        t_tasks = [
            self.fetch_treenews(),
            self.fetch_crypto_media_rss(),
            self.fetch_sec_edgar(),
            self.fetch_fed_press()
        ]
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
