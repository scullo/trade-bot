"""
═══════════════════════════════════════════════════════════════════════════════
VALKYRIE MACRO SOURCE EVOLUTION & ELO REPUTATION ENGINE (FAZ 6A)
═══════════════════════════════════════════════════════════════════════════════
Bu modül; takip edilen tüm haber sitelerinin, Twitter hesaplarının ve resmi
kanalların geriye dönük performansını (Post-Facto Attribution) ölçerek her
kaynağa canlı bir ELO Güven Puanı (0 - 100) verir.

Temel Görevler:
1. Fiyat ve Tahta Doğrulaması (t+30s, t+5m): Haber sonrası piyasa tepkisini ölçer.
2. ELO Puanlama: Doğru ve hızlı kaynakları ödüllendirir, fitil tuzaklarına ceza keser.
3. Otonom Susturma (Auto-Pruning): ELO < 45 olan kaynakları otonom karantinaya alır.
4. Byzantine Quorum Entegrasyonu: Yüksek güvenli kaynakların oy ağırlığını artırır.
═══════════════════════════════════════════════════════════════════════════════
"""

import sys
import os
import json
import time
import re
from typing import Dict, Any, List, Optional, Tuple

REGISTRY_CACHE_FILE = os.path.join(os.path.dirname(__file__), "macro_sources_registry.json")

# Varsayılan başlangıç kaynakları ve baz puanları
INITIAL_SOURCE_SEED = {
    "TREENEWS": {
        "title": "TreeNews Fast Wire WebSocket",
        "elo_rating": 92.0,
        "type": "NEWS_WIRE",
        "domain": "CRYPTO_MACRO",
        "status": "HIGH_TRUST",
        "quorum_weight": 1.5,
        "total_news_count": 0,
        "accurate_count": 0,
        "fakeout_count": 0,
        "avg_latency_ms": 120.0,
        "pnl_impact_usd": 0.0
    },
    "SEC_EDGAR": {
        "title": "SEC EDGAR Form 8-K / S-1 Resmi RSS",
        "elo_rating": 98.0,
        "type": "REGULATORY_OFFICIAL",
        "domain": "REGULATION",
        "status": "HIGH_TRUST",
        "quorum_weight": 2.0,
        "total_news_count": 0,
        "accurate_count": 0,
        "fakeout_count": 0,
        "avg_latency_ms": 250.0,
        "pnl_impact_usd": 0.0
    },
    "FED_OFFICIAL": {
        "title": "Federal Reserve Board Press RSS",
        "elo_rating": 98.0,
        "type": "CENTRAL_BANK_OFFICIAL",
        "domain": "MONETARY_POLICY",
        "status": "HIGH_TRUST",
        "quorum_weight": 2.0,
        "total_news_count": 0,
        "accurate_count": 0,
        "fakeout_count": 0,
        "avg_latency_ms": 280.0,
        "pnl_impact_usd": 0.0
    },
    "WALTER_BLOOMBERG": {
        "title": "Walter Bloomberg Terminal Terminal Feed",
        "elo_rating": 85.0,
        "type": "NEWS_WIRE",
        "domain": "GLOBAL_MACRO",
        "status": "ACTIVE",
        "quorum_weight": 1.2,
        "total_news_count": 0,
        "accurate_count": 0,
        "fakeout_count": 0,
        "avg_latency_ms": 400.0,
        "pnl_impact_usd": 0.0
    },
    "FINANCIAL_JUICE": {
        "title": "FinancialJuice Live Real-time Audio/Wire",
        "elo_rating": 80.0,
        "type": "NEWS_WIRE",
        "domain": "GLOBAL_MACRO",
        "status": "ACTIVE",
        "quorum_weight": 1.0,
        "total_news_count": 0,
        "accurate_count": 0,
        "fakeout_count": 0,
        "avg_latency_ms": 650.0,
        "pnl_impact_usd": 0.0
    }
}

class SourceEvolutionEngine:
    """
    Kendi kendini eğiten ve kaynak güvenilirliğini dinamik kalibre eden kuant motoru.
    """
    def __init__(self, registry_file: str = REGISTRY_CACHE_FILE):
        self.registry_file = registry_file
        self.sources: Dict[str, Dict[str, Any]] = {}
        self.discovered_citations: Dict[str, Dict[str, Any]] = {}
        self.shadow_sandbox: Dict[str, Dict[str, Any]] = {}
        self.pending_attributions: Dict[str, Dict[str, Any]] = {} # Değerlendirme bekleyen olaylar
        self.attribution_history: List[Dict[str, Any]] = []
        self.load_registry()

    def load_registry(self) -> None:
        """Kalıcı kaynak sicilini yükler, yoksa tohum veriyi başlatır."""
        if os.path.exists(self.registry_file):
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.sources = data.get("sources", {})
                    self.discovered_citations = data.get("discovered_citations", {})
                    self.shadow_sandbox = data.get("shadow_sandbox", {})
                    self.attribution_history = data.get("attribution_history", [])[-200:]
            except Exception as e:
                print(f">> [EVOLUTION LOAD WARNING] {e}, varsayılan tohum yükleniyor.")
                self.sources = dict(INITIAL_SOURCE_SEED)
        else:
            self.sources = dict(INITIAL_SOURCE_SEED)
            self.save_registry()

    def save_registry(self) -> None:
        """Kaynak sicil kütüğünü diske kalıcı kaydeder."""
        try:
            with open(self.registry_file, "w", encoding="utf-8") as f:
                json.dump({
                    "version": "6.0.0",
                    "last_update": time.time(),
                    "sources": self.sources,
                    "discovered_citations": self.discovered_citations,
                    "shadow_sandbox": self.shadow_sandbox,
                    "attribution_history": self.attribution_history[-200:]
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f">> [EVOLUTION SAVE WARNING] {e}")

    def get_source_profile(self, source_key: str) -> Dict[str, Any]:
        """Kaynak profilini döner. Bilinmeyen bir kaynaksa dinamik olarak sicile ekler."""
        norm_key = source_key.strip().upper()
        if norm_key not in self.sources:
            # Yeni keşfedilen / gelen kaynak için nötr başlangıç profili
            self.sources[norm_key] = {
                "title": f"Kaynak: {source_key}",
                "elo_rating": 60.0, # Nötr başlangıç puanı
                "type": "CANDIDATE_FEED",
                "domain": "GENERAL",
                "status": "ACTIVE",
                "quorum_weight": 0.8,
                "total_news_count": 0,
                "accurate_count": 0,
                "fakeout_count": 0,
                "avg_latency_ms": 1000.0,
                "pnl_impact_usd": 0.0
            }
            self.save_registry()
        return self.sources[norm_key]

    def is_source_quarantined(self, source_key: str) -> Tuple[bool, str]:
        """
        Kaynağın susturulup susturulmadığını (Quarantined) denetler.
        Puanı < 45.0 olan kaynaklar veto edilir.
        """
        prof = self.get_source_profile(source_key)
        status = prof.get("status", "ACTIVE")
        elo = prof.get("elo_rating", 60.0)

        if status in ["QUARANTINED", "MUTED", "BLACKLOCKED"] or elo < 45.0:
            return True, f"🚨 KAYNAK SUSTURULDU (ELO: {elo:.1f} < 45.0): Güvenilirlik barajını aşamadı, haberler bloklandı."
        return False, "KAYNAK GÜVENLİ"

    def get_source_voting_weight(self, source_key: str) -> float:
        """Byzantine Quorum için kaynağın oy ağırlığını döner (0.0x ile 2.0x arası)."""
        is_quarantined, _ = self.is_source_quarantined(source_key)
        if is_quarantined:
            return 0.0 # Susturulan kaynağın oyu sıfırdır!

        prof = self.get_source_profile(source_key)
        elo = prof.get("elo_rating", 60.0)
        base_w = prof.get("quorum_weight", 1.0)

        # ELO bazlı dinamik katsayı
        if elo >= 90.0:
            return min(base_w * 1.3, 2.0)
        elif elo >= 75.0:
            return base_w
        elif elo >= 60.0:
            return base_w * 0.8
        else:
            return base_w * 0.5

    def register_news_event(
        self,
        source: str,
        title: str,
        initial_price: float,
        initial_cvd: float,
        sentiment_score: float,
        symbol: str = "BTC/USDT"
    ) -> str:
        """
        Yeni bir haber yayınlandığı anda başlangıç piyasa koşullarını kaydeder.
        t+30s ve t+300s sonra piyasa tepkisi incelenecektir.
        """
        norm_key = source.strip().upper()
        prof = self.get_source_profile(norm_key)
        prof["total_news_count"] = prof.get("total_news_count", 0) + 1

        event_id = f"EVT_{int(time.time() * 1000)}_{norm_key[:6]}"
        self.pending_attributions[event_id] = {
            "event_id": event_id,
            "source": norm_key,
            "title": title,
            "symbol": symbol,
            "timestamp": time.time(),
            "initial_price": float(initial_price or 0.0),
            "initial_cvd": float(initial_cvd or 0.0),
            "sentiment_score": float(sentiment_score or 0.0),
            "evaluated": False
        }
        return event_id

    def evaluate_attribution(
        self,
        event_id: str,
        price_t30: float,
        price_t300: float,
        cvd_t30: float,
        taker_buy_ratio_t30: float = 0.5,
        trade_pnl_usd: float = 0.0,
        latency_ms: float = 200.0
    ) -> Dict[str, Any]:
        """
        Haberin piyasa doğruluğunu geriye dönük hesaplar (Post-Facto Attribution).
        Formül:
        ΔELO = Yön Doğrulaması + CVD Akış Teyidi + PnL Katkısı - Gecikme Cezası - (3x Sahte Fitil Cezası)
        """
        event = self.pending_attributions.get(event_id)
        if not event:
            # Doğrudan oluşturulmuş veya simüle edilmiş denetim
            norm_key = "UNKNOWN"
            p0 = price_t30
            sent = 0.0
            title = "Manual Audit"
        else:
            norm_key = event["source"]
            p0 = event["initial_price"]
            sent = event["sentiment_score"]
            title = event["title"]
            event["evaluated"] = True

        prof = self.get_source_profile(norm_key)
        current_elo = float(prof.get("elo_rating", 60.0))

        # 1. Fiyat Değişim Yüzdesi (t+30s ve t+300s)
        pct_30 = ((price_t30 - p0) / p0 * 100.0) if p0 > 0 else 0.0
        pct_300 = ((price_t300 - p0) / p0 * 100.0) if p0 > 0 else 0.0

        # 2. Yön Uyumu (Concordance)
        is_bullish_news = sent > 15.0
        is_bearish_news = sent < -15.0
        is_neutral = not is_bullish_news and not is_bearish_news

        delta_elo = 0.0
        is_fakeout = False
        is_accurate = False

        if is_bullish_news:
            if pct_30 > 0.08 and pct_300 >= 0.05 and cvd_t30 > 0:
                # Gerçek kurumsal alım: Boğa haberi fiyata yansıdı!
                delta_elo += 3.5
                is_accurate = True
                prof["accurate_count"] = prof.get("accurate_count", 0) + 1
            elif pct_30 > 0.05 and pct_300 < -0.15:
                # Sahte fitil (Fakeout / Trap): Yukarı süpürüp çöktü!
                delta_elo -= 9.0
                is_fakeout = True
                prof["fakeout_count"] = prof.get("fakeout_count", 0) + 1
            elif pct_30 < -0.10:
                # Tamamen ters yön (Yalan haber veya kötü yorumlama)
                delta_elo -= 7.5
                is_fakeout = True
                prof["fakeout_count"] = prof.get("fakeout_count", 0) + 1

        elif is_bearish_news:
            if pct_30 < -0.08 and pct_300 <= -0.05 and cvd_t30 < 0:
                # Gerçek düşüş: Ayı haberi doğrulandı!
                delta_elo += 3.5
                is_accurate = True
                prof["accurate_count"] = prof.get("accurate_count", 0) + 1
            elif pct_30 < -0.05 and pct_300 > 0.15:
                # Sahte ayı tuzağı (Bear Trap):
                delta_elo -= 9.0
                is_fakeout = True
                prof["fakeout_count"] = prof.get("fakeout_count", 0) + 1
            elif pct_30 > 0.10:
                delta_elo -= 7.5
                is_fakeout = True
                prof["fakeout_count"] = prof.get("fakeout_count", 0) + 1
        else:
            # Nötr haber: Düşük oynaklık beklenir
            if abs(pct_30) < 0.10:
                delta_elo += 1.0

        # 3. Kasa PnL Etkisi
        if trade_pnl_usd > 0:
            delta_elo += 2.0
            prof["pnl_impact_usd"] = prof.get("pnl_impact_usd", 0.0) + trade_pnl_usd
        elif trade_pnl_usd < 0:
            delta_elo -= 2.5
            prof["pnl_impact_usd"] = prof.get("pnl_impact_usd", 0.0) + trade_pnl_usd

        # 4. Gecikme (Latency) Cezası / Ödülü
        if latency_ms < 200.0:
            delta_elo += 1.0 # Ultra-Hızlı
        elif latency_ms > 2000.0:
            delta_elo -= 2.5 # Çok Gecikmeli (>2s)

        # Yeni ELO Hesabı (0.0 ile 100.0 arasında sınırlandırılır)
        new_elo = max(0.0, min(100.0, current_elo + delta_elo))
        prof["elo_rating"] = round(new_elo, 1)

        # Durum Güncellemesi (Susturma / Terfi)
        old_status = prof.get("status", "ACTIVE")
        if new_elo < 45.0:
            prof["status"] = "QUARANTINED"
            prof["quorum_weight"] = 0.0
        elif new_elo >= 85.0:
            prof["status"] = "HIGH_TRUST"
            prof["quorum_weight"] = 1.5
        else:
            prof["status"] = "ACTIVE"
            prof["quorum_weight"] = 1.0

        audit_record = {
            "timestamp": time.time(),
            "event_id": event_id,
            "source": norm_key,
            "title": title[:60],
            "price_pct_30s": round(pct_30, 3),
            "price_pct_300s": round(pct_300, 3),
            "is_accurate": is_accurate,
            "is_fakeout": is_fakeout,
            "delta_elo": round(delta_elo, 1),
            "old_elo": round(current_elo, 1),
            "new_elo": round(new_elo, 1),
            "status": prof["status"],
            "status_changed": (old_status != prof["status"])
        }
        self.attribution_history.append(audit_record)
        self.save_registry()

        return audit_record

    def crawl_and_extract_citations(self, text: str, wire_source: str = "WIRE") -> List[Dict[str, Any]]:
        """
        Gelen haber metninden ve bültenlerden alıntı yapılan (@handle, domain, ajans)
        kaynakları NLP ile tespit eder (Citation Graph Crawler).
        3 farklı teyitli bültende atıf alan kaynakları 'Gölge Gözlem Havuzu'na (Shadow Sandbox) sevk eder.
        """
        wire_norm = wire_source.strip().upper()
        citations_found = []

        # 1. Twitter / X Handle tespiti (@handle)
        handles = re.findall(r"@([A-Za-z0-9_]{3,25})", text)
        for h in handles:
            h_upper = f"@{h.upper()}"
            if h_upper not in ["@GMAIL", "@YAHOO", "@HOTMAIL", "@TWITTER", "@X"]:
                citations_found.append({"key": h_upper, "type": "TWITTER_HANDLE", "display": f"@{h}"})

        # 2. Alan Adı / Domain Tespiti (reuters.com, wsj.com vb.)
        domains = re.findall(r"\b([a-zA-Z0-9-]{3,30}\.(?:com|org|io|net|gov|co|news|media))\b", text, re.IGNORECASE)
        for d in domains:
            d_upper = d.upper()
            if d_upper not in ["GOOGLE.COM", "TWITTER.COM", "X.COM", "T.CO", "BIT.LY"]:
                citations_found.append({"key": d_upper, "type": "DOMAIN_OUTLET", "display": d.lower()})

        # 3. İsimlendirilmiş Atıflar (via X, per Y, citing Z)
        attributed = re.findall(r"(?:via|per|citing|according to)\s+([A-Za-z0-9_]{3,20})", text, re.IGNORECASE)
        for a in attributed:
            a_clean = a.strip().upper()
            if a_clean not in ["THE", "A", "AN", "REPORTS", "SOURCES", "SOMEONE"]:
                citations_found.append({"key": f"REF_{a_clean}", "type": "NAMED_SOURCE", "display": a.strip()})

        enrolled_candidates = []
        for c in citations_found:
            ckey = c["key"]
            if ckey in self.sources:
                # Zaten asil kaynak listesinde mevcut
                continue

            if ckey not in self.discovered_citations:
                self.discovered_citations[ckey] = {
                    "entity_key": ckey,
                    "display_name": c["display"],
                    "entity_type": c["type"],
                    "citation_count": 0,
                    "citing_wires": [],
                    "first_seen": time.time(),
                    "last_seen": time.time(),
                    "sample_headlines": []
                }

            ent = self.discovered_citations[ckey]
            ent["citation_count"] += 1
            ent["last_seen"] = time.time()
            if wire_norm not in ent["citing_wires"]:
                ent["citing_wires"].append(wire_norm)
            if len(ent["sample_headlines"]) < 3:
                ent["sample_headlines"].append(text[:80])

            # OTONOM HAVUZA ALMA KURALI (DARWINIAN ADMISSION):
            # En az 3 atıf alan veya en az 2 farklı haber kaynağından referans gösterilenler
            if (ent["citation_count"] >= 3 or len(ent["citing_wires"]) >= 2) and ckey not in self.shadow_sandbox:
                self.shadow_sandbox[ckey] = {
                    "entity_key": ckey,
                    "display_name": c["display"],
                    "entity_type": c["type"],
                    "enrolled_ts": time.time(),
                    "citing_wires": list(ent["citing_wires"]),
                    "status": "SHADOW_SANDBOX",
                    "shadow_events_count": 0,
                    "shadow_accurate_count": 0,
                    "shadow_fakeout_count": 0,
                    "shadow_accuracy_pct": 0.0,
                    "is_promoted": False
                }
                enrolled_candidates.append(self.shadow_sandbox[ckey])

        if citations_found:
            self.save_registry()

        return enrolled_candidates

    def record_shadow_event(
        self,
        entity_key: str,
        event_title: str,
        is_accurate: bool,
        is_fakeout: bool = False
    ) -> Dict[str, Any]:
        """
        Gölge Havuzdaki (Shadow Sandbox) bir kaynağın haber doğruluk takibini yapar.
        Eğer doğruluk oranı >= %80 ve en az 3 olay tamamlanmışsa -> ASİL KAYNAĞA OTONOM TERFİ EDER!
        """
        norm_key = entity_key.strip().upper()
        if norm_key not in self.shadow_sandbox:
            return {"status": "NOT_IN_SHADOW_SANDBOX", "promoted": False}

        rec = self.shadow_sandbox[norm_key]
        rec["shadow_events_count"] = rec.get("shadow_events_count", 0) + 1
        if is_accurate:
            rec["shadow_accurate_count"] = rec.get("shadow_accurate_count", 0) + 1
        if is_fakeout:
            rec["shadow_fakeout_count"] = rec.get("shadow_fakeout_count", 0) + 1

        total = rec["shadow_events_count"]
        acc = rec["shadow_accurate_count"]
        rec["shadow_accuracy_pct"] = round((acc / total * 100.0) if total > 0 else 0.0, 1)

        # OTONOM TERFİ SÜZGEÇİ:
        # En az 3 olay incelenmiş ve doğruluk >= %80 ise Asil Ağa terfi eder!
        promoted = False
        if total >= 3 and rec["shadow_accuracy_pct"] >= 80.0 and not rec.get("is_promoted", False):
            promoted = True
            rec["is_promoted"] = True
            rec["status"] = "PROMOTED_TO_ACTIVE"
            rec["promoted_ts"] = time.time()

            # Asil Sicil Kütüğüne Ekle
            self.sources[norm_key] = {
                "title": f"Keşfedilen Asil Kaynak: {rec.get('display_name', norm_key)}",
                "elo_rating": 72.0,  # Terfi eden güvenilir aday için başlangıç ELO
                "type": "PROMOTED_COMMUNITY_SOURCE",
                "domain": "CRYPTO_ALPHA",
                "status": "ACTIVE",
                "quorum_weight": 1.0,
                "total_news_count": total,
                "accurate_count": acc,
                "fakeout_count": rec.get("shadow_fakeout_count", 0),
                "avg_latency_ms": 450.0,
                "pnl_impact_usd": 0.0
            }

        self.save_registry()
        return {
            "entity_key": norm_key,
            "shadow_events_count": total,
            "shadow_accuracy_pct": rec["shadow_accuracy_pct"],
            "promoted": promoted,
            "status": rec["status"]
        }

    def get_shadow_sandbox_list(self) -> List[Dict[str, Any]]:
        """Gölge Gözlem Havuzundaki (Shadow Sandbox) aday kaynakları döner."""
        return list(self.shadow_sandbox.values())

    def get_discovered_citations_leaderboard(self) -> List[Dict[str, Any]]:
        """Keşfedilen ve alıntı yapılan tüm hesapların frekans listesini döner."""
        items = list(self.discovered_citations.values())
        items.sort(key=lambda x: x.get("citation_count", 0), reverse=True)
        return items

    def get_sources_leaderboard(self) -> List[Dict[str, Any]]:
        """Tüm kaynakların ELO skor tablosunu azalan sırada döner."""
        result = []
        for k, v in self.sources.items():
            item = dict(v)
            item["source_key"] = k
            result.append(item)
        result.sort(key=lambda x: x.get("elo_rating", 0.0), reverse=True)
        return result

# Global Singleton Motor
source_evolution_engine = SourceEvolutionEngine()
