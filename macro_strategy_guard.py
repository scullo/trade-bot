"""
🦅 VALKYRIE QUANT - STRATEJİ & TRADE SETUP MAKRO ENTEGRASYON KORUYUCUSU (PHASE 4)
Bu modül; ekonomik takvim (macro_calendar), çapraz piyasa radarı (macro_cross_asset),
haber istihbaratı (macro_news_sentinel) ve Bizans mutabakatını (macro_quorum) doğrudan
Valkyrie işlem stratejisine (strategy.py) bağlar.

Temel Fonksiyonlar:
1. Pre-Event (<15dk kala): Kârdaki pozisyonların stopunu True Net Breakeven seviyesine kilitler.
2. Pre-Event Dondurma (<5dk kala): Yeni emir açılışını kilitler.
3. Flash-Shock Kalkanı (Veri anı ilk 60s): Akut fitil ve spread sıçramalarına karşı emirleri kilitler.
4. Top 20 Likidite Filtresi: Makro volatilite anlarında düşük hacimli altcoinlerde işlem açmaz.
5. Byzantine Quorum / Anti-Spoofing: Tahta ve CVD teyidi olmayan yalan haberlerde işlemleri kilitler.
6. 8 Trade Setup ile Etkileşim Matrisi:
   - Boğa Makro Şokunda: Camarilla S3/S4 Long desteklenir, R3/R4 Short SUSTURULUR (MUTED).
     R4 Breakout Long için 1.25x marjin ve Hawkes runner (+%20 TP2) uygulanır.
   - Ayı Makro Şokunda: Camarilla S3/S4 Long SUSTURULUR (MUTED), R3/R4 Short desteklenir.
     S4 Breakdown Short için 1.25x marjin ve Hawkes runner (+%20 TP2) uygulanır.
"""

import time
import os
import json
from typing import Dict, Any, List, Optional, Tuple

from macro_calendar import calendar_manager
from macro_cross_asset import cross_asset_radar
from macro_news_sentinel import news_sentinel
from macro_quorum import news_quorum
from config import TOP_LIQUIDITY_SYMBOLS, COMMISSION_RATE

class MacroStrategyGuard:
    """Kuant Strateji Motoru ile Makro İstihbarat Arasındaki Köprü ve Karar Masası."""

    def __init__(self):
        self.calendar = calendar_manager
        self.cross_asset = cross_asset_radar
        self.news_sentinel = news_sentinel
        self.quorum = news_quorum
        self.last_be_ratchet_ts = 0.0
        self.ratchet_interval_sec = 5.0
        self.override_shock_regime: Optional[str] = None  # Testler veya acil durum simülasyonu için

        # Normalize edilmiş Top 20 Likidite Sembolleri
        self.top_liquidity_set = {
            s.replace(':USDT', '').replace('/', '').replace('USDT', '').upper()
            for s in TOP_LIQUIDITY_SYMBOLS
        }

    def set_override_regime(self, regime: Optional[str]) -> None:
        """Test senaryoları veya acil durumlar için makro rejim zorlama."""
        self.override_shock_regime = regime

    def get_active_macro_shock_regime(self) -> Dict[str, Any]:
        """
        Anlık Makro Şok Rejimini Belirler:
        - BULL_MACRO_SHOCK: Güvercin Fed/faiz kararı, düşük TÜFE veya güçlü kurumsal haber teyidi.
        - BEAR_MACRO_SHOCK: Şahin Fed kararı, yüksek TÜFE veya regülasyon baskısı / savaş şoku.
        - FLASH_SHOCK: Veri tam şu an açıklanıyor (-60s / +60s penceresi).
        - NEUTRAL_BALANCED: Olağan piyasa akışı.
        """
        if self.override_shock_regime:
            return {
                "regime": self.override_shock_regime,
                "score": 85.0 if "BULL" in self.override_shock_regime else (-85.0 if "BEAR" in self.override_shock_regime else 0.0),
                "title": f"Manuel / Kuant Rejim ({self.override_shock_regime})",
                "is_shock": self.override_shock_regime != "NEUTRAL_BALANCED"
            }

        # 1. Flash Shock Kontrolü
        is_flash, flash_ev = self.calendar.is_flash_shock_active(60.0)
        if is_flash and flash_ev:
            return {
                "regime": "FLASH_SHOCK",
                "score": 0.0,
                "title": flash_ev.get("title", "Kritik Makro Veri"),
                "is_shock": True,
                "event": flash_ev
            }

        # 2. Çapraz Piyasa Skoru & Flaş Haber Skoru
        cross_regime = self.cross_asset.get_macro_regime()
        cross_score = float(cross_regime.get("composite_score", 0.0))
        news_bias = self.news_sentinel.get_news_bias()
        news_score = float(news_bias.get("score", 0.0))

        # Ağırlıklı Bileşik Makro Şok Puanı (Çapraz Piyasa %60 + Haber İstihbaratı %40)
        composite_macro_score = (cross_score * 0.60) + (news_score * 0.40)

        if composite_macro_score >= 30.0:
            return {
                "regime": "BULL_MACRO_SHOCK",
                "score": composite_macro_score,
                "title": "🟢 KUVVETLİ BOĞA MAKRO ŞOKU (Güvercin / Risk-On)",
                "is_shock": True
            }
        elif composite_macro_score <= -30.0:
            return {
                "regime": "BEAR_MACRO_SHOCK",
                "score": composite_macro_score,
                "title": "🔴 KUVVETLİ AYI MAKRO ŞOKU (Şahin / Risk-Off)",
                "is_shock": True
            }
        else:
            return {
                "regime": "NEUTRAL_BALANCED",
                "score": composite_macro_score,
                "title": "⚪ NÖTR / DENGELİ MAKRO REJİM",
                "is_shock": False
            }

    def enforce_pre_event_defenses(self, open_positions: Dict[str, Any], paper_trader: Any = None) -> List[Dict[str, Any]]:
        """
        1. FAZ: PRE-EVENT (< 15 DAKİKA KALA) SAVUNMA KİLİDİ
        Kritik veriye (CPI, FOMC, Faiz) 15 dakikadan az kaldığında:
        - Kârdaki açık pozisyonların stop seviyesini anında "True Net Breakeven" (Giriş + Komisyon + Fonlama)
          seviyesine yükseltir (kârın silinmesini önler).
        - Zarardaki pozisyonların soft stop'unu hard stop'a çeker (kontrolsüz spread açılmasını önler).
        """
        now = time.time()
        is_imm, imm_ev = self.calendar.is_event_imminent(window_minutes=15.0)
        if not is_imm or not imm_ev or not open_positions:
            return []

        # Saniyede birden çok kez gereksiz tetiklenmeyi önle
        if now - self.last_be_ratchet_ts < self.ratchet_interval_sec:
            return []
        self.last_be_ratchet_ts = now

        secured_positions = []
        ev_title = imm_ev.get("title", "Makro Veri")
        secs_left = imm_ev.get("seconds_left", 0)
        mins_left = secs_left // 60

        fee_buffer = (float(COMMISSION_RATE) * 2.0) + 0.0002

        for sym, pos in open_positions.items():
            side = pos.get("side", "LONG")
            entry_p = float(pos.get("entry_price", 0.0))
            if entry_p <= 0:
                continue

            # Anlık kâr/zarar oranı
            cur_p = float(pos.get("current_price") or entry_p)
            cur_profit_pct = (cur_p - entry_p) / entry_p if side == "LONG" else (entry_p - cur_p) / entry_p
            acc_funding = float(pos.get("accumulated_funding_fee", 0.0))
            qty = float(pos.get("quantity", 0.0))
            funding_buffer = (acc_funding / (qty * entry_p)) if (qty > 0 and entry_p > 0) else 0.0
            total_be_buffer = fee_buffer + funding_buffer

            be_price = entry_p * (1.0 + total_be_buffer) if side == "LONG" else entry_p * (1.0 - total_be_buffer)

            # Kârdaki Pozisyon: True Net Breakeven Kilidi
            if cur_profit_pct >= 0.0020 or pos.get("is_half_closed", False):
                cur_stop = float(pos.get("hard_stop") or 0.0)
                should_tighten = (side == "LONG" and (cur_stop < be_price)) or (side == "SHORT" and (cur_stop == 0.0 or cur_stop > be_price))

                if should_tighten:
                    old_stop = cur_stop
                    pos["hard_stop"] = be_price
                    pos["soft_stop"] = be_price
                    pos["macro_be_locked"] = True
                    pos["macro_lock_reason"] = f"PRE_EVENT_BE_RATCHET ({ev_title} T-{mins_left}m)"

                    secured_positions.append({
                        "symbol": sym,
                        "side": side,
                        "action": "TIGHTEN_TO_BREAKEVEN",
                        "entry_price": entry_p,
                        "old_stop": old_stop,
                        "new_stop": be_price,
                        "profit_pct": cur_profit_pct * 100.0,
                        "event": ev_title,
                        "mins_left": mins_left
                    })
                    print(f">> [🛡️ MAKRO PRE-EVENT BE KİLİDİ] {sym} ({side}): {ev_title} verisine {mins_left} dk kaldı. Kâr korundu -> Stop ${be_price:.4f} seviyesine kilitlendi.")
            else:
                # Zarardaki / Başa Baş Yakını Pozisyon: Yumuşak stopu kaldır, sert stopa yapıştır
                if pos.get("soft_stop") != pos.get("hard_stop"):
                    pos["soft_stop"] = pos.get("hard_stop")
                    secured_positions.append({
                        "symbol": sym,
                        "side": side,
                        "action": "HARDEN_SOFT_STOP",
                        "event": ev_title,
                        "mins_left": mins_left
                    })

        if secured_positions and paper_trader and hasattr(paper_trader, "save_local_history"):
            paper_trader.save_local_history()

        return secured_positions

    def evaluate_macro_entry_permission(
        self,
        symbol: str,
        side: str,
        setup_id: str = "",
        reason: str = "",
        spread_pct: float = 0.0
    ) -> Dict[str, Any]:
        """
        YENİ POZİSYON AÇILIŞI İÇİN MERKEZİ MAKRO KAPISI (_handle_open):
        İşleme girilmeden önce şu kontrollerden geçer:
        1. Flash-Shock Kalkanı (Veri anı ilk 60s)
        2. Pre-Event Dondurma (<5 dk kala)
        3. Makro Spread Patlama Kalkanı (> %0.08)
        4. Byzantine Quorum / Sahte Pompalama Kilidi
        5. Makro Şok Altında Top 20 Likidite Filtresi
        6. 8 Trade Setup ile Etkileşim & Susturma (Muting) Matrisi
        """
        # ── 1. FLASH-SHOCK KALKANI (VERİ ANI İLK 60 SANİYE) ──
        is_flash, flash_ev = self.calendar.is_flash_shock_active(window_seconds=60.0)
        if is_flash and flash_ev:
            return {
                "allowed": False,
                "error": "BLOCK_FLASH_SHOCK_ACTIVE",
                "reason": f"⚡ Veri Anı Flash-Shock Kalkanı: '{flash_ev.get('title')}' açıklanma anında (-60s/+60s) akut fitil ve slipaj tuzağına karşı yeni emir açılışı kilitlendi."
            }

        # ── 2. PRE-EVENT DONDURMA (< 5 DAKİKA KALA) ──
        is_imm_5m, imm_ev_5m = self.calendar.is_event_imminent(window_minutes=5.0)
        if is_imm_5m and imm_ev_5m:
            rem_m = imm_ev_5m.get("seconds_left", 0) // 60
            return {
                "allowed": False,
                "error": "BLOCK_PRE_EVENT_FREEZE",
                "reason": f"🕒 Kritik Makro Olay Öncesi Kalkan: '{imm_ev_5m.get('title')}' verisine {rem_m} dk kaldı. Haber öncesi manipülasyon ve spread patlamasına karşı yeni işlem açılışı kilitlendi."
            }

        # ── 3. MAKRO SPREAD PATLAMA KALKANI (> %0.08 / 8 BPS) ──
        if spread_pct > 0.080:
            return {
                "allowed": False,
                "error": "BLOCK_SPREAD_SURGE",
                "reason": f"🛡️ Makro Spread Kalkanı: Anlık tahta spread'i %{spread_pct:.3f} > %0.080 eşiğini aştı. Likidite boşalması ve yüksek slipaj riskine karşı işlem engellendi."
            }

        # ── 4. BYZANTINE QUORUM / SAHTE POMPALAMA KİLİDİ ──
        now = time.time()
        for audit in reversed(self.quorum.audit_history[-10:]):
            if audit.get("verdict") == "SPOOFING_TRAP_NO_FLOW":
                audit_ts = audit.get("timestamp", 0)
                if (now - audit_ts) <= 30.0:  # Son 30 saniye içinde tahtasız sahte haber tuzağı varsa
                    return {
                        "allowed": False,
                        "error": "BLOCK_SPOOFING_TRAP",
                        "reason": f"🪤 Sahte Pompalama Tuzağı Kilidi: Son 30s içinde tahta ve CVD akışı olmayan manipülatif haber ({audit.get('title')}) tespit edildi; piyasa durulana kadar işlem kilitlendi."
                    }

        # ── 5. MAKRO ŞOK VE YÜKSEK VOLATİLİTE ALTINDA TOP 20 LİKİDİTE FİLTRESİ ──
        is_imm_15m, _ = self.calendar.is_event_imminent(window_minutes=15.0)
        macro_reg = self.get_active_macro_shock_regime()
        is_macro_high_vol = is_imm_15m or macro_reg.get("is_shock", False)

        clean_sym = symbol.replace(':USDT', '').replace('/', '').replace('USDT', '').upper()
        if is_macro_high_vol and clean_sym not in self.top_liquidity_set:
            return {
                "allowed": False,
                "error": "BLOCK_LOW_LIQUIDITY_MACRO",
                "reason": f"🌊 Makro Likidite Kalkanı: Yüksek makro oynaklık penceresinde düşük hacimli altcoinlerde ({symbol}) tahta boşalması riskine karşı işlem engellendi. Yalnızca Top 20 majör paritelerde işleme izin verilir."
            }

        # ── 6. 8 TRADE SETUP İLE ETKİLEŞİM & SUSTURMA (MUTING) MATRİSİ ──
        regime_code = macro_reg.get("regime", "NEUTRAL_BALANCED")
        setup_str = (str(setup_id) + " " + reason).upper()

        # AYI MAKRO ŞOKUNDA: Camarilla S3/S4 Reversal Long SUSTURULUR (MUTED)
        if regime_code == "BEAR_MACRO_SHOCK":
            if side == "LONG" and any(k in setup_str for k in ["S3_BOUNCE", "S4", "REVERSAL", "DESTEK SEKME", "S3 DESTEK"]):
                return {
                    "allowed": False,
                    "error": "MUTED_BEAR_MACRO_REVERSAL_LONG",
                    "reason": f"🔇 Setup Susturuldu (Muted): Ayı makro şokunda ({macro_reg.get('title')}) Camarilla S3/S4 Reversal Long kurulumları kurumsal satış çığı altında ezilme riskine karşı kesinlikle susturuldu."
                }

        # BOĞA MAKRO ŞOKUNDA: Camarilla R3/R4 Reversal Short SUSTURULUR (MUTED)
        if regime_code == "BULL_MACRO_SHOCK":
            if side == "SHORT" and any(k in setup_str for k in ["R3_REJECTION", "R4", "REVERSAL", "DİRENÇ RED", "R3 DİRENÇ"]):
                return {
                    "allowed": False,
                    "error": "MUTED_BULL_MACRO_REVERSAL_SHORT",
                    "reason": f"🔇 Setup Susturuldu (Muted): Boğa makro şokunda ({macro_reg.get('title')}) Camarilla R3/R4 Reversal Short kurulumları kurumsal alıcı dalgası altında ezilme riskine karşı kesinlikle susturuldu."
                }

        return {
            "allowed": True,
            "error": None,
            "reason": "Tüm makro risk, takvim ve Bizans mutabakat kontrolleri onaylandı."
        }

    def apply_macro_setup_boost(
        self,
        symbol: str,
        side: str,
        setup_id: str,
        reason: str,
        base_margin: float,
        base_tp1: float,
        base_tp2: float,
        entry_price: float
    ) -> Dict[str, Any]:
        """
        MAKRO TEŞVİK VE HAWKES RUNNER GENİŞLETMESİ (SETUP 2: RANGE BREAKOUT):
        Makro rüzgar arkadayken:
        - Boğa şokunda R4 Breakout Long: 1.25x marjin bütçesi ve +%20 TP2 hedef genişletmesi.
        - Ayı şokunda S4 Breakdown Short: 1.25x marjin bütçesi ve +%20 TP2 hedef genişletmesi.
        """
        macro_reg = self.get_active_macro_shock_regime()
        regime_code = macro_reg.get("regime", "NEUTRAL_BALANCED")
        setup_str = (str(setup_id) + " " + reason).upper()
        is_breakout = any(k in setup_str for k in ["BREAKOUT", "BREAKDOWN", "KIRILIM", "R4 ÜSTÜ", "S4 ALTI"])

        if regime_code == "BULL_MACRO_SHOCK" and side == "LONG" and is_breakout:
            boosted_margin = round(base_margin * 1.25, 2)
            tp2_dist = abs(base_tp2 - entry_price) if (base_tp2 > 0 and entry_price > 0) else 0.0
            boosted_tp2 = round(entry_price + (tp2_dist * 1.20), 4) if (tp2_dist > 0 and entry_price > 0) else base_tp2
            return {
                "boosted": True,
                "margin": boosted_margin,
                "tp1": base_tp1,
                "tp2": boosted_tp2,
                "runner_mode": True,
                "score_bonus": 15,
                "reason": "🚀 BOĞA MAKRO ŞOKU + R4 BREAKOUT: 1.25x Marjin ve Hawkes Runner modu (+%20 TP2) devrede."
            }

        if regime_code == "BEAR_MACRO_SHOCK" and side == "SHORT" and is_breakout:
            boosted_margin = round(base_margin * 1.25, 2)
            tp2_dist = abs(entry_price - base_tp2) if (base_tp2 > 0 and entry_price > 0) else 0.0
            boosted_tp2 = round(entry_price - (tp2_dist * 1.20), 4) if (tp2_dist > 0 and entry_price > 0) else base_tp2
            return {
                "boosted": True,
                "margin": boosted_margin,
                "tp1": base_tp1,
                "tp2": boosted_tp2,
                "runner_mode": True,
                "score_bonus": 15,
                "reason": "🩸 AYI MAKRO ŞOKU + S4 BREAKDOWN: 1.25x Marjin ve Hawkes Runner modu (+%20 TP2) devrede."
            }

        return {
            "boosted": False,
            "margin": base_margin,
            "tp1": base_tp1,
            "tp2": base_tp2,
            "runner_mode": False,
            "score_bonus": 0,
            "reason": "Standart kuant marjin ve hedefler uygulandı."
        }

    def get_macro_hud_telemetry(self) -> Dict[str, Any]:
        """Ana Dashboard ve 10. Sekme HUD için anlık özet telemetri."""
        next_ev = self.calendar.get_next_major_event() or {}
        cross_reg = self.cross_asset.get_macro_regime()
        news_bias = self.news_sentinel.get_news_bias()
        latest_news = self.news_sentinel.get_latest_news(limit=5)
        shock_reg = self.get_active_macro_shock_regime()

        return {
            "next_event": next_ev,
            "cross_asset_regime": cross_reg,
            "news_bias": news_bias,
            "latest_news": latest_news,
            "shock_regime": shock_reg,
            "hud_ticker_text": f"🔴 DEV OLAY: {next_ev.get('title', 'Yok')} ({next_ev.get('countdown_str', '--:--:--')}) | MAKRO NABIZ: DXY {cross_reg.get('assets', {}).get('DXY', {}).get('value', '102.2')} | USDT.D %{cross_reg.get('assets', {}).get('USDT.D', {}).get('value', '6.5')} | DURUM: {shock_reg.get('title', 'NÖTR')}"
        }

# Global Singleton Örneği
macro_guard = MacroStrategyGuard()
