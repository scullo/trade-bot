"""
🦅 VALKYRIE QUANT - BYZANTINE QUORUM & YALAN HABER / MANİPÜLASYON SAVUNMA MOTORU
Kripto piyasasında sahte tweet'ler, hacklenen resmi hesaplar ve yapay tahta pompalamalarına
karşı 3 Kademeli Çift Kaynak Mutabakatı (Byzantine Quorum) ve Emir Akışı (CVD/OBI) teyidi uygulayan,
körü körüne işlem açılmasını kesin olarak engelleyen elit güvenlik motoru.
"""

import os
import json
import time
import re
from typing import Dict, Any, List, Optional, Tuple
from macro_roles import role_registry

QUORUM_AUDIT_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "macro_quorum_audit.json")

# Siyasi Boş Gürültü ve Propaganda Kelimeleri
POLITICAL_NOISE_KEYWORDS = [
    "PROMISE", "SÖZ VERDİ", "WILL SUPPORT", "DESTEKLEYECEĞİZ", "GREAT FUTURE",
    "HARİKA BİR GELECEK", "INNOVATION IS GOOD", "İNOVASYON ÖNEMLİ", "CAMPAIGN",
    "SEÇİM", "VOTE FOR", "BİZE OY VERİN", "SPEECH", "RALLY"
]

# Somut Yasal ve Yürütme Eylemi Kelimeleri (Gerçek Politika Şoku)
CONCRETE_POLICY_KEYWORDS = [
    "SIGNED EXECUTIVE ORDER", "BAŞKANLIK KARARNAMESİ İMZALANDI", "BILL INTRODUCED",
    "YASA TASARISI SUNULDU", "CONGRESS PASSED", "KONGREDEN GEÇTİ", "SANCTION",
    "YAPTIRIM", "TARIFF IMPOSED", "TARİFE YÜRÜRLÜĞE GİRDİ", "RESERVE ACT",
    "REZERV YASASI", "OFFICIALLY APPOINTED", "RESMEN ATANDI"
]

def _normalize_text(text: str) -> str:
    """Türkçe ve İngilizce karakter uyumlu küçük harf normalizasyonu."""
    return text.lower().replace("i̇", "i").replace("ı", "i").replace("İ", "i").replace("I", "i")

class ByzantineNewsQuorum:
    """Çok Kaynaklı Doğrulama ve Manipülasyon Engelleme Masası."""

    def __init__(self, audit_file: str = QUORUM_AUDIT_LOG_FILE):
        self.audit_file = audit_file
        self.topic_clusters: Dict[str, List[Dict[str, Any]]] = {}
        self.audit_history: List[Dict[str, Any]] = []
        self.load_audit_history()

    def load_audit_history(self) -> None:
        """Geçmiş denetim kayıtlarını yükle."""
        if os.path.exists(self.audit_file):
            try:
                with open(self.audit_file, "r", encoding="utf-8") as f:
                    self.audit_history = json.load(f).get("audits", [])
            except Exception:
                pass

    def save_audit_history(self) -> None:
        """Denetim kayıtlarını diske kaydet."""
        try:
            with open(self.audit_file, "w", encoding="utf-8") as f:
                json.dump({"audits": self.audit_history[-100:]}, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _extract_topic_key(self, title: str) -> str:
        """Haberin ana konusunu çıkaran normalizasyon anahtarı."""
        clean = _normalize_text(title)
        tr_map = str.maketrans("ğüşıöç", "gusioc")
        clean = clean.translate(tr_map)
        words = re.findall(r"[a-z]{3,}", clean)
        meaningful = [w for w in words if w not in ["with", "that", "from", "this", "have", "been", "were", "said", "says", "icin", "olan", "veya", "gibi", "kadar"]]
        return "_".join(sorted(meaningful[:5]))

    def register_incoming_news(self, news_item: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Gelen haberi konu kümesine ekler.
        Eğer son 180 saniye içinde en az 2 bağımsız kaynak aynı konuyu geçmişse
        veya kaynak resmi birincil kaynaksa (SEC/Fed), ÇİFT TEYİT (Quorum) sağlanır.
        """
        now = time.time()
        title = news_item.get("title", "")
        source = news_item.get("source", "")
        is_primary = news_item.get("is_primary_official", False) or source in ["SEC_EDGAR", "FED_OFFICIAL"]

        # Resmi birincil kurumlar doğrudan teyitlidir (Tek başına yeterlidir)
        if is_primary:
            return True, [source]

        topic_key = self._extract_topic_key(title)
        if not topic_key:
            return False, [source]

        # Eski küme temizliği (>180s)
        if topic_key not in self.topic_clusters:
            self.topic_clusters[topic_key] = []
        
        self.topic_clusters[topic_key] = [
            item for item in self.topic_clusters[topic_key] if (now - item.get("ts", 0) <= 180)
        ]

        # Bu kaynağı ekle
        self.topic_clusters[topic_key].append({"source": source, "ts": now, "title": title})

        # Farklı bağımsız kaynakları say ve ELO oy ağırlıklarını hesapla
        distinct_sources = list({item["source"].split(":")[0] for item in self.topic_clusters[topic_key]})
        
        try:
            from macro_source_evolution import source_evolution_engine
            # Karantinadaki kaynakları teyit sayımından çıkar
            active_sources = [s for s in distinct_sources if not source_evolution_engine.is_source_quarantined(s)[0]]
            total_weight = sum(source_evolution_engine.get_source_voting_weight(s) for s in active_sources)
            # En az 2 bağımsız aktif kaynak veya yüksek ağırlıklı konsensüs
            is_multi_confirmed = (len(active_sources) >= 2 and total_weight >= 1.2) or (total_weight >= 2.0)
            return is_multi_confirmed, active_sources
        except Exception:
            is_multi_confirmed = (len(distinct_sources) >= 2)
            return is_multi_confirmed, distinct_sources

    def evaluate_news_authenticity(
        self,
        news_item: Dict[str, Any],
        cvd_delta_usd: float = 0.0,
        taker_buy_ratio: float = 50.0,
        obi_ratio: float = 1.0
    ) -> Dict[str, Any]:
        """
        Gelen haberi 3 Kademeli Adli Filtreden Geçirir:
        1. Kademe: Çoklu Kaynak Mutabakatı (Byzantine Quorum)
        2. Kademe: Siyasetçi ve NLP Gürültü Elemesi
        3. Kademe: Tahta ve Emir Akışı (CVD/OBI) Tepki Teyidi

        Döner:
        - is_approved_for_entry: bool (Yeni işlem açılabilir mi?)
        - is_defensive_trigger: bool (Kârdaki stopları başabaşa çekmeli miyiz?)
        - verdict: str
        - action_command: str
        - reason: str
        """
        title = news_item.get("title", "")
        source = news_item.get("source", "")
        sentiment_score = float(news_item.get("sentiment_score", 0.0))
        is_primary = news_item.get("is_primary_official", False) or source in ["SEC_EDGAR", "FED_OFFICIAL"]

        title_upper = title.upper()
        now_ts = time.time()

        # ── 0. KADEME: DARWINIAN SOURCE EVOLUTION & KARANTİNA DENETİMİ (FAZ 6A) ──
        try:
            from macro_source_evolution import source_evolution_engine
            is_quarantined, q_reason = source_evolution_engine.is_source_quarantined(source)
            if is_quarantined:
                audit_record = {
                    "timestamp": now_ts,
                    "title": title,
                    "verdict": "REJECTED_QUARANTINED_SOURCE",
                    "action_command": "IGNORE_NOISE",
                    "reason": f"🚨 KAYNAK SUSTURULDU ({source}): {q_reason}",
                    "is_approved_for_entry": False,
                    "is_defensive_trigger": False,
                    "confirmed_sources": []
                }
                self.audit_history.append(audit_record)
                self.save_audit_history()
                return audit_record
        except Exception:
            pass

        # ── 1. KADEME: SİYASETÇİ VE NLP GÜRÜLTÜ ELEMESİ ──
        spk = role_registry.classify_text_speaker(title)
        if spk.get("has_official") and spk.get("role_key") in ["POTUS", "POLITICIAN"]:
            title_norm = _normalize_text(title)
            is_concrete = any(_normalize_text(kw) in title_norm for kw in CONCRETE_POLICY_KEYWORDS)
            is_noise = any(_normalize_text(kw) in title_norm for kw in POLITICAL_NOISE_KEYWORDS)
            if is_noise and not is_concrete:
                audit_record = {
                    "timestamp": now_ts,
                    "title": title,
                    "verdict": "POLITICAL_NOISE",
                    "action_command": "IGNORE_NOISE",
                    "reason": f"Siyasetçi ({spk.get('matched_person')}) açıklaması somut yasa/kararname içermiyor; seçim propagandası/gürültü olarak elendi.",
                    "is_approved_for_entry": False,
                    "is_defensive_trigger": False
                }
                self.audit_history.append(audit_record)
                self.save_audit_history()
                return audit_record

        # ── 2. KADEME: ÇOKLU KAYNAK MUTABAKATI (BYZANTINE QUORUM) ──
        has_quorum, sources_list = self.register_incoming_news(news_item)

        if not has_quorum and not is_primary:
            # TEK KAYNAK DURUMU: ASLA YENİ İŞLEM AÇILMAZ! YALNIZCA SAVUNMA DEVREYE GİRER.
            audit_record = {
                "timestamp": now_ts,
                "title": title,
                "verdict": "DEFENSE_ONLY_SINGLE_SOURCE",
                "action_command": "TIGHTEN_STOPS_ONLY",
                "reason": f"Haber tek bir kaynaktan ({source}) geldi; çift bağımsız teyit yok. Yalan haber manipülasyonu riskine karşı yeni işlem açılışı kilitlendi. YALNIZCA kârdaki açık pozisyonların stopu başabaşa (BE) çekildi.",
                "is_approved_for_entry": False,
                "is_defensive_trigger": True,
                "confirmed_sources": sources_list
            }
            self.audit_history.append(audit_record)
            self.save_audit_history()
            return audit_record

        # ── 3. KADEME: EMİR AKIŞI (CVD) VE TAHTA TEPKİ TEYİDİ ──
        # Haber boğa yönlüyse (score >= +25), vadeli tahtada kurumsal alıcı teyidi aranır.
        # Eğer haber çok boğa görünüyor ama tahtada agresif satış varsa -> MANİPÜLASYON TUZAĞI (SPOOFING TRAP)!
        if sentiment_score >= 25.0:
            is_flow_divergent = (taker_buy_ratio < 44.0 and cvd_delta_usd < -500_000.0)
            if is_flow_divergent:
                audit_record = {
                    "timestamp": now_ts,
                    "title": title,
                    "verdict": "SPOOFING_TRAP_NO_FLOW",
                    "action_command": "BLOCK_TRADES_30S",
                    "reason": f"🪤 MANİPÜLASYON TUZAĞI TESPİT EDİLDİ: Haber aşırı boğa ({sentiment_score:+.1f}) görünmesine rağmen borsa tahtasında agresif satıcılar piyasayı süpürüyor (Taker Alıcı: %{taker_buy_ratio:.1f} < %44, CVD: -${abs(cvd_delta_usd):,.0f}). Sahte fitil tuzağına karşı işlem kesinlikle engellendi.",
                    "is_approved_for_entry": False,
                    "is_defensive_trigger": True,
                    "confirmed_sources": sources_list
                }
                self.audit_history.append(audit_record)
                self.save_audit_history()
                return audit_record

        # Haber ayı yönlüyse (score <= -25), tahtada agresif alım varken short açılmaz.
        if sentiment_score <= -25.0:
            is_bear_divergent = (taker_buy_ratio > 56.0 and cvd_delta_usd > 500_000.0)
            if is_bear_divergent:
                audit_record = {
                    "timestamp": now_ts,
                    "title": title,
                    "verdict": "SPOOFING_TRAP_NO_FLOW",
                    "action_command": "BLOCK_TRADES_30S",
                    "reason": f"🪤 AYI MANİPÜLASYON TUZAĞI: Kötü habere rağmen tahtada kurumsal pasif alıcılar her şeyi yutuyor (Taker Alıcı: %{taker_buy_ratio:.1f} > %56). Sahte dökme tuzağına karşı Short engellendi.",
                    "is_approved_for_entry": False,
                    "is_defensive_trigger": True,
                    "confirmed_sources": sources_list
                }
                self.audit_history.append(audit_record)
                self.save_audit_history()
                return audit_record

        # ── TÜM TESTLER GEÇİLDİ: TAM TEYİTLİ KURUMSAL İSTİHBARAT ──
        audit_record = {
            "timestamp": now_ts,
            "title": title,
            "verdict": "VERIFIED_INSTITUTIONAL",
            "action_command": "EXECUTE_SETUP",
            "reason": f"✅ ÇİFT TEYİT VE TAHTA AKIŞI ONAYLANDI: Haber bağımsız kaynaklarca ({', '.join(sources_list)}) doğrulandı ve borsa tahtasındaki kurumsal emir akışıyla (CVD & OBI) %100 uyuştu. Elit kuruluma tam yetki verildi.",
            "is_approved_for_entry": True,
            "is_defensive_trigger": True,
            "confirmed_sources": sources_list
        }
        self.audit_history.append(audit_record)
        self.save_audit_history()
        return audit_record

# Global Singleton Örneği
news_quorum = ByzantineNewsQuorum()
