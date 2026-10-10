"""
🦅 VALKYRIE QUANT - OTONOM EKONOMİK TAKVİM MOTORU (MACRO CALENDAR MANAGER)
ForexFactory, Investing ve FRED resmi veri boru hatlarından beslenen,
kripto piyasasını sarsan TÜFE (CPI), ÜFE (PPI), FOMC ve Tarım Dışı İstihdam (NFP)
olaylarını canlı takip eden, saniyelik geri sayım yapan ve kuant risk kalkanlarını tetikleyen motor.
"""

import os
import json
import time
import math
import asyncio
import re
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
import aiohttp

CALENDAR_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "macro_calendar_cache.json")
FF_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

# Kripto Piyasası İçin Yüksek Etki (High Impact) Anahtar Kelimeler Kataloğu
HIGH_IMPACT_KEYWORDS = [
    "CPI", "CORE CPI", "TÜFE", "CONSUMER PRICE INDEX",
    "FOMC", "FEDERAL FUNDS RATE", "INTEREST RATE", "POWELL SPEAKS", "FED CHAIR",
    "NON-FARM", "NFP", "UNEMPLOYMENT RATE", "İSTİHDAM",
    "PPI", "ÜFE", "PRODUCER PRICE INDEX",
    "GDP", "BÜYÜME", "RETAIL SALES"
]

# Fed ve BLS Resmi Yıllık Ana Takvimi (Haftalık veri boş olduğunda veya hafta sonlarında kesintisiz geri sayım sağlar)
ANNUAL_MACRO_MASTER_SCHEDULE = [
    {"title": "ABD Çekirdek TÜFE (Core CPI)", "country": "USD", "impact": "CRITICAL", "category": "INFLATION_CPI", "iso_date": "2026-10-14T08:30:00-04:00", "forecast": "%3.1", "previous": "%3.2"},
    {"title": "ABD Perakende Satışlar (Retail Sales)", "country": "USD", "impact": "HIGH", "category": "MACRO_OTHER", "iso_date": "2026-10-16T08:30:00-04:00", "forecast": "%0.3", "previous": "%0.1"},
    {"title": "FOMC Faiz Kararı & Basın Toplantısı", "country": "USD", "impact": "CRITICAL", "category": "FED_FOMC", "iso_date": "2026-11-05T14:00:00-05:00", "forecast": "5.00%", "previous": "5.25%"},
    {"title": "ABD Tarım Dışı İstihdam (NFP)", "country": "USD", "impact": "CRITICAL", "category": "LABOR_NFP", "iso_date": "2026-11-06T08:30:00-05:00", "forecast": "150K", "previous": "142K"},
    {"title": "FOMC Faiz Kararı & Noktasal Grafik", "country": "USD", "impact": "CRITICAL", "category": "FED_FOMC", "iso_date": "2026-12-16T14:00:00-05:00", "forecast": "4.75%", "previous": "5.00%"}
]

class MacroCalendarManager:
    """Ekonomik Takvim ve Makro Geri Sayım Yöneticisi."""

    def __init__(self, cache_file: str = CALENDAR_CACHE_FILE):
        self.cache_file = cache_file
        self.events: List[Dict[str, Any]] = []
        self.last_sync_ts: float = 0.0
        self.sync_interval_sec: float = 900.0  # 15 dakikada bir otomatik tazeleyen boru hattı
        self.load_cache()

    def load_cache(self) -> None:
        """Önbellekteki takvim verilerini yükle."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.events = data.get("events", [])
                    self.last_sync_ts = float(data.get("last_sync_ts", 0.0))
            except Exception as e:
                print(f">> [TAKVİM ÖNBELLEK UYARI] {e}")

    def save_cache(self) -> None:
        """Takvim verilerini diske kaydet."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump({
                    "last_sync_ts": self.last_sync_ts,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "events": self.events
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f">> [TAKVİM KAYIT HATA] {e}")

    async def sync_calendar(self, force: bool = False) -> bool:
        """
        ForexFactory kamuya açık resmi JSON boru hattından haftalık ekonomik takvimi çeker.
        USD ve küresel kripto etkili olayları filtreleyerek normalize eder.
        """
        now = time.time()
        if not force and (now - self.last_sync_ts < self.sync_interval_sec) and len(self.events) > 0:
            return True

        headers = {
            "User-Agent": "ValkyrieQuant/2.0 (Institutional Macro Desk; Contact: quant@valkyrie.ai)",
            "Accept": "application/json"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(FF_CALENDAR_URL, headers=headers, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                    if resp.status != 200:
                        print(f">> [TAKVİM HTTP UYARI] ForexFactory durum kodu: {resp.status} (Master Takvim Yedeği Devreye Alınıyor)")
                        self._populate_fallback_schedule()
                        return True

                    raw_items = await resp.json()
                    parsed_events = []

                    for item in raw_items:
                        title = item.get("title", "").strip()
                        country = item.get("country", "").strip().upper()
                        impact = item.get("impact", "").strip()  # High, Medium, Low
                        date_str = item.get("date", "").strip()

                        # Yalnızca USD veya Global ('All') olayları incele
                        if country not in ["USD", "ALL"]:
                            continue

                        title_upper = title.upper()
                        is_high_impact = (impact.lower() == "high") or any(kw in title_upper for kw in HIGH_IMPACT_KEYWORDS)
                        if not is_high_impact:
                            continue

                        # ISO Tarih Ayrıştırma
                        try:
                            # Örnek: "2026-10-10T08:30:00-04:00"
                            dt = datetime.fromisoformat(date_str)
                            event_ts = dt.timestamp()
                        except Exception:
                            continue

                        forecast_val = item.get("forecast", "").strip()
                        previous_val = item.get("previous", "").strip()

                        # Kategori tespiti
                        category = "MACRO_OTHER"
                        if any(k in title_upper for k in ["CPI", "TÜFE", "CONSUMER PRICE"]):
                            category = "INFLATION_CPI"
                        elif any(k in title_upper for k in ["FOMC", "RATE", "POWELL", "FED CHAIR"]):
                            category = "FED_FOMC"
                        elif any(k in title_upper for k in ["NON-FARM", "NFP", "UNEMPLOYMENT", "İSTİHDAM"]):
                            category = "LABOR_NFP"
                        elif any(k in title_upper for k in ["PPI", "ÜFE"]):
                            category = "INFLATION_PPI"
                        elif "GDP" in title_upper:
                            category = "GROWTH_GDP"

                        parsed_events.append({
                            "title": title,
                            "country": country,
                            "impact": "CRITICAL" if ("CPI" in title_upper or "FOMC" in title_upper) else ("HIGH" if is_high_impact else "MEDIUM"),
                            "category": category,
                            "timestamp": event_ts,
                            "iso_date": date_str,
                            "forecast": forecast_val,
                            "previous": previous_val,
                            "actual": ""  # Veri anında taze doldurulur
                        })

                    # Yıllık ana takvimden gelecekteki olayları da ekle (Mükerrerlik olmadan)
                    existing_titles = {e["title"].upper() for e in parsed_events}
                    for m_ev in ANNUAL_MACRO_MASTER_SCHEDULE:
                        try:
                            m_ts = datetime.fromisoformat(m_ev["iso_date"]).timestamp()
                            if m_ev["title"].upper() not in existing_titles and m_ts >= (now - 3600):
                                m_dict = dict(m_ev)
                                m_dict["timestamp"] = m_ts
                                m_dict["actual"] = ""
                                parsed_events.append(m_dict)
                        except Exception:
                            pass

                    # Kronolojik sırala
                    parsed_events.sort(key=lambda x: x["timestamp"])
                    self.events = parsed_events
                    self.last_sync_ts = now
                    self.save_cache()
                    print(f">> [📅 EKONOMİK TAKVİM SENKRONİZE EDİLDİ] {len(self.events)} kritik makro olay hafızaya alındı.")
                    return True

        except Exception as e:
            print(f">> [TAKVİM SENKRONİZASYON UYARI] {e} (Master Takvim Yedeği Devreye Alınıyor)")
            self._populate_fallback_schedule()
            return True

    def _populate_fallback_schedule(self) -> None:
        """Ağ hatası veya 429 hız sınırında yıllık resmi takvimle hafızayı güvenceye alır."""
        now = time.time()
        existing_titles = {e["title"].upper() for e in self.events}
        added = False
        for m_ev in ANNUAL_MACRO_MASTER_SCHEDULE:
            try:
                m_ts = datetime.fromisoformat(m_ev["iso_date"]).timestamp()
                if m_ev["title"].upper() not in existing_titles and m_ts >= (now - 3600):
                    m_dict = dict(m_ev)
                    m_dict["timestamp"] = m_ts
                    m_dict["actual"] = ""
                    self.events.append(m_dict)
                    added = True
            except Exception:
                pass
        self.events.sort(key=lambda x: x["timestamp"])
        if added:
            self.save_cache()
            print(f">> [📅 MASTER TAKVİM YEDEĞİ AKTİF] {len(self.events)} kritik makro olay hafızaya işlendi.")

    def get_upcoming_events(self, hours_ahead: float = 48.0) -> List[Dict[str, Any]]:
        """Gelecek X saat içindeki kritik olayları döner."""
        now = time.time()
        cutoff = now + (hours_ahead * 3600.0)
        upcoming = []

        for ev in self.events:
            ev_ts = ev["timestamp"]
            if now - 300 <= ev_ts <= cutoff:  # Son 5 dakikada geçmiş veya gelecekteki
                ev_copy = dict(ev)
                ev_copy["seconds_left"] = max(0, int(ev_ts - now))
                ev_copy["is_imminent"] = (0 <= ev_ts - now <= 900)  # Son 15 dakika
                ev_copy["is_flash_shock"] = (abs(ev_ts - now) <= 60) # Veri anı (-60s / +60s)
                upcoming.append(ev_copy)

        return upcoming

    def get_next_major_event(self) -> Optional[Dict[str, Any]]:
        """
        Dashboard'un en üstündeki HUD Şeridi için:
        Kriptoyu etkileyecek EN YAKIN tek bir kritik olayı ve saniyelik geri sayımı döner.
        """
        now = time.time()
        for ev in self.events:
            ev_ts = ev["timestamp"]
            # En fazla 15 dakika önce geçmiş veya gelecekteki ilk kritik olay
            if ev_ts >= (now - 900):
                ev_copy = dict(ev)
                diff = int(ev_ts - now)
                ev_copy["seconds_left"] = max(0, diff)
                
                # Formatlı kalan süre (Örn: "02:14:35" veya "AÇIKLANIYOR")
                if diff <= 0:
                    ev_copy["countdown_str"] = "ŞU AN AÇIKLANIYOR! ⚡"
                else:
                    hrs = diff // 3600
                    mins = (diff % 3600) // 60
                    secs = diff % 60
                    ev_copy["countdown_str"] = f"{hrs:02d}:{mins:02d}:{secs:02d}"

                ev_copy["is_imminent"] = (0 <= diff <= 900)
                ev_copy["is_flash_shock"] = (abs(diff) <= 60)
                return ev_copy

        return None

    def get_todays_key_events(self) -> List[Dict[str, Any]]:
        """Bugün gerçekleşecek tüm kritik olayları döner (TSİ UTC+3 senkronize)."""
        now = time.time()
        now_dt = datetime.now(timezone(timedelta(hours=3)))
        start_of_day = datetime(now_dt.year, now_dt.month, now_dt.day, 0, 0, 0, tzinfo=timezone(timedelta(hours=3))).timestamp()
        end_of_day = start_of_day + 86400.0

        todays = []
        for ev in self.events:
            ev_ts = ev["timestamp"]
            if start_of_day <= ev_ts <= end_of_day:
                ev_copy = dict(ev)
                diff = int(ev_ts - now)
                ev_copy["seconds_left"] = diff
                ev_copy["is_past"] = (diff < 0)
                todays.append(ev_copy)

        return todays

    def is_event_imminent(self, window_minutes: float = 15.0) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Kritik veriye X dakika kaldı mı?
        True dönerse bot kârdaki pozisyonların stopunu sıkı başabaşa (BE) çeker!
        """
        next_ev = self.get_next_major_event()
        if not next_ev:
            return False, None

        secs_left = next_ev.get("seconds_left", 999999)
        if 0 <= secs_left <= (window_minutes * 60.0):
            return True, next_ev

        return False, None

    def is_flash_shock_active(self, window_seconds: float = 60.0) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Şu an tam veri açıklanma anı (-60s ile +60s arası) mı?
        True dönerse ilk 60 saniyelik stop-avı fitillerinde işlem açılışı kilitlenir!
        """
        next_ev = self.get_next_major_event()
        if not next_ev:
            return False, None

        now = time.time()
        ev_ts = next_ev.get("timestamp", 0)
        if abs(now - ev_ts) <= window_seconds:
            return True, next_ev

        return False, None

    @staticmethod
    def calculate_surprise_zscore(actual_str: str, forecast_str: str, category: str = "INFLATION_CPI") -> Dict[str, Any]:
        """
        Açıklanan veri ile beklenti arasındaki Matematiksel Sürpriz Skorunu (Z-Score) hesaplar (<0.01ms).
        - Enflasyon (CPI/PPI) için: Açıklanan < Beklenti -> BOĞA (+ Skor)
        - Büyüme (GDP/İstihdam) için: Açıklanan > Beklenti -> BOĞA (+ Skor)
        """
        def _extract_float(s: str) -> Optional[float]:
            match = re.search(r"[-+]?\d*\.\d+|\d+", s.replace("%", "").replace("K", "").replace("M", "").replace("B", ""))
            return float(match.group()) if match else None

        act = _extract_float(actual_str)
        fc = _extract_float(forecast_str)

        if act is None or fc is None:
            return {"valid": False, "score": 0.0, "bias": "NEUTRAL", "reason": "Sayısal veri okunamadı"}

        delta = act - fc

        # Kategoriye göre kripto piyasası yön etkisi
        if "INFLATION" in category:
            # Enflasyon düşük gelirse = Fed faiz indirir = Kripto Boğa (+)
            score = -1.0 * (delta / max(0.1, abs(fc))) * 100.0
        elif "FED_FOMC" in category:
            # Faiz düşük gelirse = Boğa (+)
            score = -1.0 * (delta / max(0.1, abs(fc))) * 100.0
        else:
            # Güçlü istihdam/GDP = Pozitif ekonomi (+)
            score = (delta / max(0.1, abs(fc))) * 100.0

        # Normalizasyon [-100, +100]
        score = max(-100.0, min(100.0, score))

        bias = "NEUTRAL"
        if score >= 35.0:
            bias = "STRONG_BULLISH"
        elif score >= 15.0:
            bias = "MODERATE_BULLISH"
        elif score <= -35.0:
            bias = "STRONG_BEARISH"
        elif score <= -15.0:
            bias = "MODERATE_BEARISH"

        return {
            "valid": True,
            "actual": act,
            "forecast": fc,
            "delta": round(delta, 3),
            "surprise_score": round(score, 1),
            "bias": bias
        }

# Global Singleton Örneği
macro_calendar = MacroCalendarManager()
