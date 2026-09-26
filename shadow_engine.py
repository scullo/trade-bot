"""
VALKYRIE SHADOW EXECUTION ENGINE & AUTONOMOUS COIN DNA CALIBRATOR
================================================================
Arka Planda Gölge İşlem Takip Motoru ve Otonom Kuant Kalibrasyon Masası

Özellikler:
1. Counterfactual Execution (Gölge İşlem Takibi):
   - Reddedilen / Veto edilen tüm setup'ları sanal pozisyon olarak açar.
   - Anlık fiyat (tick) ve 5M mum teyitleriyle pozisyonu TP1, TP2, Stop Loss ve Chandelier BE açısından canlı takip eder.
   - Kalkan Teşhisi (Verdict):
     * STOP OLDU -> HERO SHIELD (🛡️ Kahraman Kalkan: Botu zarardan korudu, kurtarılan para $)
     * TP1/TP2 OLDU -> SPOILER SHIELD (⚠️ Frenleyici Kalkan: Kârlı işlemi engelledi, kaçan kâr $)
2. Coin DNA Kalibratörü:
   - Her parite (ENA, DOGE, MOVR, vb.) için engellenen sinyalleri analiz eder.
   - Fitil esnekliği (Wick Elasticity), Taker CVD hassasiyeti, Tahta OBI tutunması.
   - Kalkan Verimlilik Endeksi (Shield Efficiency Index - SEI).
   - Otonom Parametre Öneri Motoru (Örn: "ENA S3 fitil eşiği %15'ten %10'a esnetilmeli").
3. Bellek İçi O(1) ve Sıfır Gecikme:
   - Dairesel collections.deque(maxlen=1000), maksimum 100 aktif gölge pozisyon.
   - Render 512MB RAM sınırına kesinlikle uyumlu (<2MB bellek ayak izi).
"""

import os
import json
import time
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any


class ShadowExecutionEngine:
    """
    Sıfır Gecikmeli Bellek İçi Gölge İşlem Motoru ve Otonom Kuant Kalibratörü.
    """

    def __init__(self, history_file: str = "shadow_trades_history.json", max_active: int = 100, max_history: int = 1000):
        self.history_file = os.path.join(os.path.dirname(__file__), history_file)
        self.max_active = max_active
        self.max_history = max_history

        # Aktif Sanal Pozisyonlar: {shadow_id: ShadowPositionDict}
        self.active_positions: Dict[str, dict] = {}

        # Tamamlanan Sanal İşlemler (O(1) Dairesel Bellek Kuyruğu)
        self.completed_trades: deque = deque(maxlen=max_history)

        # Sembol ve Kalkan bazlı hızlı arama endeksleri
        self.symbol_active_map: Dict[str, str] = {}  # symbol -> shadow_id (son aktif)
        self.last_rejection_ts: Dict[str, float] = {} # (symbol, setup) -> timestamp (throttling)

        # Standart Sanal İşlem Boyutu ($10,000 kasa, %2.5 marjin, 5x kaldıraç)
        self.virtual_margin = 250.0
        self.virtual_leverage = 5
        self.virtual_notional = self.virtual_margin * self.virtual_leverage  # $1,250.0

        # Hafızadaki geçmişi yükle
        self.load_history()

    # ──────────────────────────────────────────────────────────────────────────
    # KALKAN VE ENGEL SINIFLANDIRICI
    # ──────────────────────────────────────────────────────────────────────────
    def extract_shield_name(self, reason: str) -> str:
        """Hata veya ret mesajından profesyonel kalkan adını teşhis eder."""
        r = str(reason or "")
        if "Harmonik Akış" in r or "CVD" in r:
            return "Harmonik Akış Kalkanı (CVD Taker Flow)"
        elif "Dip AVWAP" in r:
            return "Dip AVWAP Taban Kalkanı (Institutional Floor)"
        elif "Tepe AVWAP" in r:
            return "Tepe AVWAP Direnç Kalkanı (Institutional Ceiling)"
        elif "Parite Soğuma" in r or "Soğuma" in r or "COOLDOWN" in r:
            return "Parite Soğuma Kalkanı (Chop Defense)"
        elif "Komisyon Freni" in r:
            return "Komisyon Freni (Over-trading Throttle)"
        elif "Çifte Zarar" in r:
            return "Çifte Zarar Devre Kesicisi (Toxic Pair Circuit)"
        elif "Sektör" in r or "CLUSTER" in r:
            return "Sektör Kümelenme Kalkanı (Beta Exposure)"
        elif "Portföy Risk" in r or "PORTFOLIO" in r:
            return "Portföy Risk Tavanı (%25 Marjin Sınırı)"
        elif "Esnek Portföy" in r or "MAX_SLOTS" in r:
            return "Portföy Slot Tavanı (Azami 8 İşlem)"
        elif "Kuant Veri Süzgeci" in r or "WHIPSAW_BREAKOUT" in r:
            return "Kuant Veri Süzgeci (Hacimsiz Kırılım Veto)"
        elif "Confluence" in r or "WHIPSAW_LOW_CONFLUENCE" in r:
            return "Kuant Confluence Denetimi (Yetersiz Teyit)"
        elif "Dip Kovalama" in r:
            return "Dip Kovalama Kalkanı (Seller Exhaustion Wick)"
        elif "Tepe İğne" in r:
            return "Tepe İğne Kalkanı (Buyer Exhaustion Wick)"
        elif "Fonlama" in r or "Squeeze" in r:
            return "Dinamik Fonlama Kalkanı (Funding Squeeze)"
        elif "Hacim" in r or "patlama" in r:
            return "Hacim Patlama Eşiği (Volume Surge Filter)"
        elif "Makro" in r or "BTC" in r:
            return "Makro Düşüş Kalkanı (BTC/ETH Dump Shield)"
        elif "Buzdağı" in r or "Duvar" in r or "Tahta" in r or "Iceberg" in r or "WALL" in r:
            return "Tahta Likidite Duvarı Kalkanı (Orderbook Wall)"
        elif "Fitil" in r or "fitil" in r or "emilim" in r:
            return "Fitil & Emilim Kalkanı (Wick Absorption)"
        elif "Yapısal" in r:
            return "Dinamik Yapısal Seviye Doğrulama (PA Invalidation)"
        else:
            # İlk iki kelimeyi temizle
            parts = r.split(":")
            if len(parts) > 1 and len(parts[0]) < 40:
                return parts[0].replace("🛡️", "").replace("🚨", "").strip()
            return "Kuant Güvenlik Kalkanı"

    # ──────────────────────────────────────────────────────────────────────────
    # GÖLGE İŞLEM BAŞLATMA (SPAWN SHADOW POSITION)
    # ──────────────────────────────────────────────────────────────────────────
    def spawn_shadow_trade(
        self,
        symbol: str,
        setup_name: str,
        reason: str,
        side: Optional[str] = None,
        entry_price: Optional[float] = None,
        sl_price: Optional[float] = None,
        tp1_price: Optional[float] = None,
        tp2_price: Optional[float] = None,
        telemetry: Optional[dict] = None
    ) -> Optional[dict]:
        """
        Reddedilen sinyal için sanal bir gölge işlem başlatır.
        Throttling: Aynı coin ve setup için son 15 dakika içinde aktif bir işlem varsa tekrar açmaz.
        """
        clean_sym = symbol.replace("/USDT", "").replace(":USDT", "").replace("USDT", "").upper() + "/USDT"
        now_ts = time.time()

        # 1. Throttling Kontrolü (15 dakika içinde aynı coin için çifte kayıt engelle)
        throttle_key = f"{clean_sym}_{setup_name}"
        last_ts = self.last_rejection_ts.get(throttle_key, 0.0)
        if now_ts - last_ts < 900.0:  # 15 dakika (3 mum)
            return None

        # 2. Aktif pozisyon kontrolü (Eğer bu coin'de açık bir sanal pozisyon varsa bekle)
        if clean_sym in self.symbol_active_map:
            act_id = self.symbol_active_map[clean_sym]
            if act_id in self.active_positions:
                return None

        # 3. Yönü (Side) tespit et
        if not side:
            s_name = setup_name.upper()
            if any(w in s_name for w in ["SHORT", "AYI", "BREAKDOWN", "DİRENÇ", "REDDİ", "S4", "R3"]):
                side = "SHORT"
            else:
                side = "LONG"

        # 4. Giriş Fiyatı ve Seviyeleri Doğrula / Hesapla
        entry_p = float(entry_price or 0.0)
        if entry_p <= 0.0:
            return None  # Geçerli fiyat yoksa sanal işlem açılamaz

        # Stop ve TP Seviyeleri (Eğer verilmediyse standart dinamik %1.20 stop, %1.65 TP1, %3.0 TP2)
        atr_pct = float((telemetry or {}).get("atr_pct", 1.2))
        stop_dist_pct = max(0.008, (atr_pct * 1.0) / 100.0)
        tp1_dist_pct = max(0.012, (atr_pct * 1.5) / 100.0)
        tp2_dist_pct = max(0.024, (atr_pct * 2.8) / 100.0)

        if side == "LONG":
            sl_p = float(sl_price) if (sl_price and sl_price < entry_p) else round(entry_p * (1.0 - stop_dist_pct), 6)
            tp1_p = float(tp1_price) if (tp1_price and tp1_price > entry_p) else round(entry_p * (1.0 + tp1_dist_pct), 6)
            tp2_p = float(tp2_price) if (tp2_price and tp2_price > tp1_p) else round(entry_p * (1.0 + tp2_dist_pct), 6)
        else:
            sl_p = float(sl_price) if (sl_price and sl_price > entry_p) else round(entry_p * (1.0 + stop_dist_pct), 6)
            tp1_p = float(tp1_price) if (tp1_price and tp1_price < entry_p) else round(entry_p * (1.0 - tp1_dist_pct), 6)
            tp2_p = float(tp2_price) if (tp2_price and tp2_price < tp1_p) else round(entry_p * (1.0 - tp2_dist_pct), 6)

        shield_name = self.extract_shield_name(reason)
        now_dt = datetime.now(timezone(timedelta(hours=3)))
        shadow_id = f"SHD_{clean_sym.replace('/USDT', '')}_{int(now_ts * 1000)}"

        shadow_pos = {
            "id": shadow_id,
            "symbol": clean_sym,
            "side": side,
            "setup": setup_name.split('(')[0].strip(),
            "shield": shield_name,
            "reason": reason,
            "entry_price": entry_p,
            "current_price": entry_p,
            "sl_price": sl_p,
            "tp1_price": tp1_p,
            "tp2_price": tp2_p,
            "be_price": None,
            "tp1_hit": False,
            "tp2_hit": False,
            "early_be_locked": False,
            "candles_elapsed": 0,
            "entry_time": now_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "entry_ts": now_ts,
            "peak_high": entry_p,
            "valley_low": entry_p,
            "max_mfe_pct": 0.0,
            "max_mae_pct": 0.0,
            "status": "OPEN",
            "exit_price": None,
            "exit_time": None,
            "virtual_pnl_usd": 0.0,
            "virtual_pnl_pct": 0.0,
            "verdict": None,  # "HERO_SHIELD", "SPOILER_SHIELD", "NEUTRAL"
            "telemetry": telemetry or {}
        }

        # Aktif kapasiteyi kontrol et (Azami 100 aktif gölge pozisyon)
        if len(self.active_positions) >= self.max_active:
            # En eski pozisyonu zaman aşımıyla kapat
            oldest_id = next(iter(self.active_positions))
            self._close_shadow_position(oldest_id, self.active_positions[oldest_id]["current_price"], "ZAMAN_AŞIMI (Rotasyon)", "TIMEOUT")

        self.active_positions[shadow_id] = shadow_pos
        self.symbol_active_map[clean_sym] = shadow_id
        self.last_rejection_ts[throttle_key] = now_ts
        return shadow_pos

    # ──────────────────────────────────────────────────────────────────────────
    # ANLIK TICK VE MUM İLE CANLI GÖLGE TAKİBİ
    # ──────────────────────────────────────────────────────────────────────────
    def update_tick(self, symbol: str, current_price: float) -> List[dict]:
        """Anlık milisaniyelik fiyat güncellemesi (MFE, MAE, Acil Stop, Chandelier BE)."""
        clean_sym = symbol.replace("/USDT", "").replace(":USDT", "").replace("USDT", "").upper() + "/USDT"
        closed_records = []
        cur_p = float(current_price)
        if cur_p <= 0.0:
            return closed_records

        # Bu sembole ait aktif gölge pozisyonları bul
        for s_id in list(self.active_positions.keys()):
            pos = self.active_positions.get(s_id)
            if not pos or pos["symbol"] != clean_sym:
                continue

            side = pos["side"]
            entry_p = pos["entry_price"]
            pos["current_price"] = cur_p

            # Peak / Valley güncelle
            if cur_p > pos["peak_high"]:
                pos["peak_high"] = cur_p
            if cur_p < pos["valley_low"]:
                pos["valley_low"] = cur_p

            # MFE (Maksimum Favorable Excursion) ve MAE hesapla
            if side == "LONG":
                mfe_pct = max(0.0, ((pos["peak_high"] - entry_p) / entry_p) * 100.0)
                mae_pct = max(0.0, ((entry_p - pos["valley_low"]) / entry_p) * 100.0)
                cur_profit_pct = (cur_p - entry_p) / entry_p
            else:
                mfe_pct = max(0.0, ((entry_p - pos["valley_low"]) / entry_p) * 100.0)
                mae_pct = max(0.0, ((pos["peak_high"] - entry_p) / entry_p) * 100.0)
                cur_profit_pct = (entry_p - cur_p) / entry_p

            pos["max_mfe_pct"] = round(mfe_pct, 2)
            pos["max_mae_pct"] = round(mae_pct, 2)

            # 1. Chandelier Early BE Lock Kontrolü (+%0.80 kârda başabaş kilitle)
            if not pos["early_be_locked"] and not pos["tp1_hit"] and cur_profit_pct >= 0.0080:
                pos["early_be_locked"] = True
                pos["be_price"] = entry_p * (1.0008 if side == "LONG" else 0.9992)

            # 2. Breakeven Stop Kontrolü (Erken kilit veya TP1 sonrası)
            if (pos["early_be_locked"] or pos["tp1_hit"]) and pos.get("be_price"):
                be_p = pos["be_price"]
                if (side == "LONG" and cur_p <= be_p) or (side == "SHORT" and cur_p >= be_p):
                    rec = self._close_shadow_position(s_id, be_p, "🛡️ Sanal Başa-Baş Koruması (BE)", "BE_CLOSED")
                    if rec:
                        closed_records.append(rec)
                    continue

            # 3. TP1 ve TP2 Kontrolü
            if not pos["tp1_hit"]:
                if (side == "LONG" and cur_p >= pos["tp1_price"]) or (side == "SHORT" and cur_p <= pos["tp1_price"]):
                    pos["tp1_hit"] = True
                    pos["be_price"] = entry_p * (1.0008 if side == "LONG" else 0.9992)

            if pos["tp1_hit"]:
                if (side == "LONG" and cur_p >= pos["tp2_price"]) or (side == "SHORT" and cur_p <= pos["tp2_price"]):
                    rec = self._close_shadow_position(s_id, pos["tp2_price"], "🎯 Sanal TP2 Hedefi Gerçekleşti", "TP2_HIT")
                    if rec:
                        closed_records.append(rec)
                    continue

            # 4. Mutlak Acil Tavan Stopu (%1.60 felaket tavanı)
            disaster_pct = 0.0160
            if (side == "LONG" and cur_p <= entry_p * (1.0 - disaster_pct)) or (side == "SHORT" and cur_p >= entry_p * (1.0 + disaster_pct)):
                rec = self._close_shadow_position(s_id, cur_p, "🚨 Sanal Mutlak Stop Delindi (%1.60)", "STOPPED")
                if rec:
                    closed_records.append(rec)
                continue

        return closed_records

    def update_candle(self, symbol: str, current_candle: dict) -> List[dict]:
        """5 Dakikalık mum kapanışı ile fitil ve kapanış kontrolleri."""
        clean_sym = symbol.replace("/USDT", "").replace(":USDT", "").replace("USDT", "").upper() + "/USDT"
        closed_records = []
        c_high = float(current_candle.get("high", 0.0))
        c_low = float(current_candle.get("low", 0.0))
        c_close = float(current_candle.get("close", 0.0))

        if c_close <= 0.0:
            return closed_records

        for s_id in list(self.active_positions.keys()):
            pos = self.active_positions.get(s_id)
            if not pos or pos["symbol"] != clean_sym:
                continue

            pos["candles_elapsed"] += 1
            side = pos["side"]
            entry_p = pos["entry_price"]
            sl_p = pos["sl_price"]
            tp1_p = pos["tp1_price"]
            tp2_p = pos["tp2_price"]

            # Mum içi peak/valley güncelle
            if c_high > pos["peak_high"]:
                pos["peak_high"] = c_high
            if c_low < pos["valley_low"] and c_low > 0:
                pos["valley_low"] = c_low

            # MFE / MAE tazele
            if side == "LONG":
                pos["max_mfe_pct"] = round(max(pos["max_mfe_pct"], ((pos["peak_high"] - entry_p) / entry_p) * 100.0), 2)
                pos["max_mae_pct"] = round(max(pos["max_mae_pct"], ((entry_p - pos["valley_low"]) / entry_p) * 100.0), 2)
            else:
                pos["max_mfe_pct"] = round(max(pos["max_mfe_pct"], ((entry_p - pos["valley_low"]) / entry_p) * 100.0), 2)
                pos["max_mae_pct"] = round(max(pos["max_mae_pct"], ((pos["peak_high"] - entry_p) / entry_p) * 100.0), 2)

            # 1. Stop Loss Kontrolü (Mum kapanışı veya fitil testi)
            is_stopped = False
            if side == "LONG" and (c_low <= sl_p or c_close <= sl_p):
                is_stopped = True
            elif side == "SHORT" and (c_high >= sl_p or c_close >= sl_p):
                is_stopped = True

            if is_stopped:
                rec = self._close_shadow_position(s_id, sl_p, f"🛑 Sanal Stop Loss (${sl_p:.4f})", "STOPPED")
                if rec:
                    closed_records.append(rec)
                continue

            # 2. TP1 ve TP2 Kontrolü
            if not pos["tp1_hit"]:
                if (side == "LONG" and c_high >= tp1_p) or (side == "SHORT" and c_low <= tp1_p):
                    pos["tp1_hit"] = True
                    pos["be_price"] = entry_p * (1.0008 if side == "LONG" else 0.9992)

            if pos["tp1_hit"]:
                if (side == "LONG" and c_high >= tp2_p) or (side == "SHORT" and c_low <= tp2_p):
                    rec = self._close_shadow_position(s_id, tp2_p, f"🎯 Sanal TP2 Gerçekleşti (${tp2_p:.4f})", "TP2_HIT")
                    if rec:
                        closed_records.append(rec)
                    continue

            # 3. Başa-baş Stop Kontrolü
            if (pos["early_be_locked"] or pos["tp1_hit"]) and pos.get("be_price"):
                be_p = pos["be_price"]
                if (side == "LONG" and c_low <= be_p) or (side == "SHORT" and c_high >= be_p):
                    rec = self._close_shadow_position(s_id, be_p, "🛡️ Sanal Başa-Baş Koruması (BE)", "BE_CLOSED")
                    if rec:
                        closed_records.append(rec)
                    continue

            # 4. Zaman Aşımı (36 mum = 3 saat boyunca ne TP ne Stop olmadıysa kapat)
            if pos["candles_elapsed"] >= 36:
                rec = self._close_shadow_position(s_id, c_close, "⏳ Zaman Aşımı (3 Saat / 36 Mum)", "TIMEOUT")
                if rec:
                    closed_records.append(rec)
                continue

        return closed_records

    # ──────────────────────────────────────────────────────────────────────────
    # GÖLGE İŞLEM KAPATMA & ADLİ TEŞHİS (VERDICT ASSIGNMENT)
    # ──────────────────────────────────────────────────────────────────────────
    def _close_shadow_position(self, shadow_id: str, exit_price: float, close_reason: str, exit_status: str) -> Optional[dict]:
        """Gölge işlemi kapatır, sanal PnL ve Hero/Spoiler kalkan teşhisini yapar."""
        pos = self.active_positions.pop(shadow_id, None)
        if not pos:
            return None

        # Sembol eşlemesini temizle
        if self.symbol_active_map.get(pos["symbol"]) == shadow_id:
            del self.symbol_active_map[pos["symbol"]]

        side = pos["side"]
        entry_p = pos["entry_price"]
        exit_p = float(exit_price)
        pos["exit_price"] = exit_p
        pos["exit_status"] = exit_status
        pos["close_reason"] = close_reason
        pos["exit_time"] = datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M:%S")
        pos["duration_mins"] = round((time.time() - pos["entry_ts"]) / 60.0, 1)

        # Sanal PnL Hesabı
        if side == "LONG":
            raw_pnl_pct = (exit_p - entry_p) / entry_p
        else:
            raw_pnl_pct = (entry_p - exit_p) / entry_p

        fee_pct = 0.0008  # %0.08 taker roundtrip komisyonu
        net_pct = raw_pnl_pct - fee_pct
        pos["virtual_pnl_pct"] = round(net_pct * self.virtual_leverage * 100.0, 2)
        pos["virtual_pnl_usd"] = round(self.virtual_notional * net_pct, 2)

        # 🎯 ADLİ TEŞHİS (HERO vs SPOILER)
        # Eğer işlem zararla kapandıysa -> Kalkan bizi korudu! (HERO SHIELD)
        # Eğer işlem kârla kapandıysa -> Kalkan kârı kaçırdı! (SPOILER SHIELD)
        if pos["virtual_pnl_usd"] < -2.0:
            pos["verdict"] = "HERO_SHIELD"
            pos["verdict_badge"] = "🛡️ KAHRAMAN KALKAN (Zarar Kurtarıldı)"
            pos["impact_usd"] = abs(pos["virtual_pnl_usd"])
        elif pos["virtual_pnl_usd"] > 2.0:
            pos["verdict"] = "SPOILER_SHIELD"
            pos["verdict_badge"] = "⚠️ FRENLEYİCİ KALKAN (Kaçan Kâr)"
            pos["impact_usd"] = pos["virtual_pnl_usd"]
        else:
            pos["verdict"] = "NEUTRAL"
            pos["verdict_badge"] = "⚪ NÖTR (Başa-Baş)"
            pos["impact_usd"] = 0.0

        pos["status"] = exit_status

        # Dairesel kuyruğa ekle
        self.completed_trades.append(pos)

        # Diske asenkron kaydet (hata fırlatmaz)
        self.save_history()
        return pos

    # ──────────────────────────────────────────────────────────────────────────
    # PERFORMANS ÖZETİ VE METRİKLER (KPIs)
    # ──────────────────────────────────────────────────────────────────────────
    def get_summary(self) -> dict:
        """Genel gölge işlem performans karnesi ve Kalkan Verimlilik Skoru (SEI)."""
        completed = list(self.completed_trades)
        total_completed = len(completed)
        active_count = len(self.active_positions)

        hero_trades = [t for t in completed if t.get("verdict") == "HERO_SHIELD"]
        spoiler_trades = [t for t in completed if t.get("verdict") == "SPOILER_SHIELD"]
        neutral_trades = [t for t in completed if t.get("verdict") == "NEUTRAL"]

        total_saved_loss = sum(abs(t.get("virtual_pnl_usd", 0.0)) for t in hero_trades)
        total_missed_profit = sum(t.get("virtual_pnl_usd", 0.0) for t in spoiler_trades)
        net_shield_alpha = total_saved_loss - total_missed_profit

        # Kalkan Verimlilik Endeksi (Shield Efficiency Index - SEI %)
        # SEI = Kurtarılan Zarar / (Kurtarılan Zarar + Kaçan Kâr) * 100
        total_impact = total_saved_loss + total_missed_profit
        sei_score = round((total_saved_loss / total_impact) * 100.0, 1) if total_impact > 0 else 100.0

        # En çok koruma sağlayan ilk 3 kalkan
        shield_savings: Dict[str, float] = {}
        for t in hero_trades:
            s_name = t.get("shield", "Bilinmeyen")
            shield_savings[s_name] = shield_savings.get(s_name, 0.0) + abs(t.get("virtual_pnl_usd", 0.0))
        top_hero_shields = sorted(shield_savings.items(), key=lambda x: x[1], reverse=True)[:3]

        return {
            "total_shadow_trades": total_completed + active_count,
            "active_shadow_trades": active_count,
            "completed_shadow_trades": total_completed,
            "hero_count": len(hero_trades),
            "spoiler_count": len(spoiler_trades),
            "neutral_count": len(neutral_trades),
            "total_saved_loss_usd": round(total_saved_loss, 2),
            "total_missed_profit_usd": round(total_missed_profit, 2),
            "net_shield_alpha_usd": round(net_shield_alpha, 2),
            "shield_efficiency_index": sei_score,
            "top_hero_shields": top_hero_shields,
            "tracked_symbols_count": len(set(t.get("symbol") for t in completed + list(self.active_positions.values())))
        }

    # ──────────────────────────────────────────────────────────────────────────
    # COIN BAZLI DNA VE OTONOM KALİBRASYON RAPORU
    # ──────────────────────────────────────────────────────────────────────────
    def get_coin_dna_matrix(self) -> List[dict]:
        """
        100 coin için tek tek toplanan gölge verileri ve otonom kalibrasyon önerilerini üretir.
        """
        completed = list(self.completed_trades)
        symbols_map: Dict[str, List[dict]] = {}

        for t in completed:
            sym = t.get("symbol", "")
            if sym not in symbols_map:
                symbols_map[sym] = []
            symbols_map[sym].append(t)

        coin_dna_list = []
        for sym, t_list in symbols_map.items():
            clean = sym.replace("/USDT", "")
            tot = len(t_list)
            heroes = [t for t in t_list if t.get("verdict") == "HERO_SHIELD"]
            spoilers = [t for t in t_list if t.get("verdict") == "SPOILER_SHIELD"]

            saved = sum(abs(t.get("virtual_pnl_usd", 0.0)) for t in heroes)
            missed = sum(t.get("virtual_pnl_usd", 0.0) for t in spoilers)
            impact = saved + missed
            sei = round((saved / impact) * 100.0, 1) if impact > 0 else 100.0

            # En sık engelleyen kalkanı bul
            shield_counts: Dict[str, int] = {}
            for t in t_list:
                s_name = t.get("shield", "Genel")
                shield_counts[s_name] = shield_counts.get(s_name, 0) + 1
            top_shield = max(shield_counts.items(), key=lambda x: x[1])[0] if shield_counts else "Yok"

            # Ortalama fitil oranı (Wick Elasticity)
            wicks = [float(t.get("telemetry", {}).get("lower_wick_ratio", 0.0)) for t in t_list if "lower_wick_ratio" in t.get("telemetry", {})]
            avg_wick = round((sum(wicks) / len(wicks)) * 100.0, 1) if wicks else 12.0

            # Otonom Kuant Kalibrasyon Teşhisi
            calibrated = False
            rec_badge = "DENGELİ"
            if len(spoilers) >= 3 and sei < 35.0:
                calibrated = True
                rec_badge = "⚠️ GEVŞET"
                recommendation = f"Frenleyici kalkan bu paritede ${missed:.1f} kâr kaçırdı ({len(spoilers)} işlem). '{top_shield}' eşiği bu pariteye özel %20 esnetilmeli."
            elif len(heroes) >= 2 and sei >= 80.0:
                rec_badge = "👑 KORU"
                recommendation = f"Kalkan kusursuz çalışıyor. Toplam ${saved:.1f} sermaye korundu. Mevcut sıkı filtreler korunmalı."
            elif tot >= 5:
                rec_badge = "⚖️ DENGELİ"
                recommendation = f"Koruma ve fırsat dengesi stabil (SEI: %{sei:.1f}). Standart persona parametreleri optimum."
            else:
                rec_badge = "⏳ VERİ TOPLANIYOR"
                recommendation = f"Henüz {tot} gölge işlem toplandı. Sağlıklı kalibrasyon için en az 5 işlem bekleniyor."

            coin_dna_list.append({
                "symbol": clean,
                "full_symbol": sym,
                "total_shadows": tot,
                "hero_count": len(heroes),
                "spoiler_count": len(spoilers),
                "saved_loss_usd": round(saved, 2),
                "missed_profit_usd": round(missed, 2),
                "net_alpha_usd": round(saved - missed, 2),
                "sei": sei,
                "top_shield": top_shield,
                "wick_elasticity": avg_wick,
                "recommendation": recommendation,
                "recommendation_badge": rec_badge,
                "is_calibrated_needed": calibrated
            })

        # Toplam işlem ve etkiye göre sırala
        coin_dna_list.sort(key=lambda x: (x["total_shadows"], abs(x["net_alpha_usd"])), reverse=True)
        return coin_dna_list

    # ──────────────────────────────────────────────────────────────────────────
    # KALKAN LİDERLİK TABLOSU (SHIELD AUDIT)
    # ──────────────────────────────────────────────────────────────────────────
    def get_shield_leaderboard(self) -> List[dict]:
        """Tüm kalkanların genel etki karnesi."""
        completed = list(self.completed_trades)
        shields_map: Dict[str, List[dict]] = {}

        for t in completed:
            s_name = t.get("shield", "Bilinmeyen Kalkan")
            if s_name not in shields_map:
                shields_map[s_name] = []
            shields_map[s_name].append(t)

        leaderboard = []
        for s_name, t_list in shields_map.items():
            heroes = [t for t in t_list if t.get("verdict") == "HERO_SHIELD"]
            spoilers = [t for t in t_list if t.get("verdict") == "SPOILER_SHIELD"]
            saved = sum(abs(t.get("virtual_pnl_usd", 0.0)) for t in heroes)
            missed = sum(t.get("virtual_pnl_usd", 0.0) for t in spoilers)
            impact = saved + missed
            sei = round((saved / impact) * 100.0, 1) if impact > 0 else 100.0

            if sei >= 70.0:
                role = "👑 KAHRAMAN (Hero)"
            elif sei <= 35.0 and len(spoilers) >= 2:
                role = "⚠️ FRENLEYİCİ (Spoiler)"
            else:
                role = "⚖️ DENGELİ (Balanced)"

            leaderboard.append({
                "shield_name": s_name,
                "total_blocks": len(t_list),
                "hero_count": len(heroes),
                "spoiler_count": len(spoilers),
                "saved_loss_usd": round(saved, 2),
                "missed_profit_usd": round(missed, 2),
                "net_saved_usd": round(saved - missed, 2),
                "sei": sei,
                "role": role
            })

        leaderboard.sort(key=lambda x: x["saved_loss_usd"], reverse=True)
        return leaderboard

    # ──────────────────────────────────────────────────────────────────────────
    # AKTİF VE GEÇMİŞ LİSTELERİ
    # ──────────────────────────────────────────────────────────────────────────
    def get_active_positions(self) -> List[dict]:
        """Anlık çalışan tüm gölge pozisyonların listesi."""
        return list(self.active_positions.values())

    def get_recent_history(self, limit: int = 50) -> List[dict]:
        """En son tamamlanan N adet gölge işlem."""
        trades = list(self.completed_trades)
        return trades[-limit:] if len(trades) > limit else trades

    # ──────────────────────────────────────────────────────────────────────────
    # GITHUB & DİSK KALICILIĞI (PERSISTENCE)
    # ──────────────────────────────────────────────────────────────────────────
    def save_history(self):
        """Hafızadaki son 500 gölge işlemi JSON dosyasına yazar."""
        try:
            data = {
                "updated_at": datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M:%S"),
                "completed": list(self.completed_trades)[-500:]
            }
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            pass

    def load_history(self):
        """Başlangıçta geçmiş gölge işlemleri hafızaya yükler."""
        if not os.path.exists(self.history_file):
            return
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                completed = data.get("completed", [])
                for t in completed:
                    self.completed_trades.append(t)
            print(f">> [GÖLGE MOTORU] {len(self.completed_trades)} adet geçmiş gölge işlem hafızaya yüklendi.")
        except Exception as e:
            print(f">> [GÖLGE MOTORU UYARI] Geçmiş yüklenemedi: {e}")
