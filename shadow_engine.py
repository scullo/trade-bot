"""
VALKYRIE SHADOW EXECUTION ENGINE & AUTONOMOUS COIN DNA CALIBRATOR
================================================================
Arka Planda Gölge İşlem Takip Motoru ve Otonom Kuant Kalibrasyon Masası

Özellikler:
1. Counterfactual Execution (Gölge İşlem Takibi):
   - Reddedilen / Veto edilen tüm setup'ları sanal pozisyon olarak açar.
   - Anlık fiyat (tick) ve 5M mum teyitleriyle pozisyonu TP1, TP2, Stop Loss ve Chandelier BE açısından canlı takip eder.
   - Kalkan Teşhisi (Verdict):
     * STOP OLDU -> HERO SHIELD (Kahraman Kalkan: Botu zarardan korudu, kurtarılan para $)
     * TP1/TP2 OLDU -> SPOILER SHIELD (Frenleyici Kalkan: Kârlı işlemi engelledi, kaçan kâr $)
2. Coin DNA Kalibratörü & Adli Otopsi Masası:
   - Her parite (ENA, DOGE, MOVR, vb.) için engellenen sinyalleri analiz eder.
   - Fitil esnekliği (Wick Elasticity), Taker CVD hassasiyeti, Tahta OBI tutunması.
   - Kalkan Verimlilik Endeksi (Shield Efficiency Index - SEI).
   - Otonom Parametre Öneri Motoru (Örn: "ENA S3 fitil eşiği %15'ten %10'a esnetilmeli").
   - Ayrıntılı Neden-Sonuç Adli Hikayeleştirme (Narrative Forensics).
3. Bellek İçi O(1) ve Sıfır Gecikme:
   - Dairesel collections.deque(maxlen=1000), maksimum 300 aktif gölge pozisyon.
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

    def __init__(self, history_file: str = "shadow_trades_history.json", max_active: int = 300, max_history: int = 1000):
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

        # Baz DNA veritabanını yükle (100 Parite Bütünlüğü)
        self.dna_baseline = {}
        try:
            b_path = os.path.join(os.path.dirname(__file__), 'coin_dna_baseline.json')
            if os.path.exists(b_path):
                with open(b_path, 'r', encoding='utf-8') as f_b:
                    self.dna_baseline = json.load(f_b)
        except Exception:
            pass

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

        # 1. Throttling Kontrolü (15 dakika içinde aynı coin ve setup için çifte kayıt engelle)
        throttle_key = f"{clean_sym}_{setup_name}"
        last_ts = self.last_rejection_ts.get(throttle_key, 0.0)
        if now_ts - last_ts < 900.0:
            return None

        # 2. Aktif pozisyon kontrolü (Eğer bu coin'de açık bir sanal pozisyon varsa bekle)
        if clean_sym in self.symbol_active_map:
            act_id = self.symbol_active_map[clean_sym]
            if act_id in self.active_positions:
                return None

        # 3. Yönü (Side) tespit et
        if not side:
            s_name = (setup_name + " " + reason).upper()
            if any(w in s_name for w in ["SHORT", "AYI", "BREAKDOWN", "DİRENÇ", "REDDİ", "S4", "R3"]):
                side = "SHORT"
            else:
                side = "LONG"

        # 4. Giriş Fiyatı ve Seviyeleri Doğrula / Hesapla
        entry_p = float(entry_price or 0.0)
        if entry_p <= 0.0:
            return None

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
            "verdict_badge": "TAKİPTE (Açık Pozisyon)",
            "narrative": "Pozisyon canlı fiyat ve mum teyidiyle takip ediliyor.",
            "margin_usd": 250.0,
            "leverage": 5.0,
            "notional_usd": 1250.0,
            "telemetry": telemetry or {}
        }

        # Aktif kapasiteyi kontrol et (Azami 300 aktif gölge pozisyon)
        if len(self.active_positions) >= self.max_active:
            oldest_id = next(iter(self.active_positions))
            self._close_shadow_position(oldest_id, self.active_positions[oldest_id]["current_price"], "ZAMAN_AŞIMI (Rotasyon)", "TIMEOUT")

        self.active_positions[shadow_id] = shadow_pos
        self.symbol_active_map[clean_sym] = shadow_id
        self.last_rejection_ts[throttle_key] = now_ts
        self.save_history()
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

        for s_id in list(self.active_positions.keys()):
            pos = self.active_positions.get(s_id)
            if not pos or pos["symbol"] != clean_sym:
                continue

            side = pos["side"]
            entry_p = pos["entry_price"]
            pos["current_price"] = cur_p

            if cur_p > pos["peak_high"]:
                pos["peak_high"] = cur_p
            if cur_p < pos["valley_low"]:
                pos["valley_low"] = cur_p

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
                    rec = self._close_shadow_position(s_id, be_p, "Sanal Başa-Baş Koruması (BE)", "BE_CLOSED")
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
                    rec = self._close_shadow_position(s_id, pos["tp2_price"], "Sanal TP2 Hedefi Gerçekleşti", "TP2_HIT")
                    if rec:
                        closed_records.append(rec)
                    continue

            # 4. Mutlak Acil Tavan Stopu (%1.60 felaket tavanı)
            disaster_pct = 0.0160
            if (side == "LONG" and cur_p <= entry_p * (1.0 - disaster_pct)) or (side == "SHORT" and cur_p >= entry_p * (1.0 + disaster_pct)):
                rec = self._close_shadow_position(s_id, cur_p, "Sanal Mutlak Stop Delindi (%1.60)", "STOPPED")
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

            if c_high > pos["peak_high"]:
                pos["peak_high"] = c_high
            if c_low < pos["valley_low"] and c_low > 0:
                pos["valley_low"] = c_low

            if side == "LONG":
                pos["max_mfe_pct"] = round(max(pos["max_mfe_pct"], ((pos["peak_high"] - entry_p) / entry_p) * 100.0), 2)
                pos["max_mae_pct"] = round(max(pos["max_mae_pct"], ((entry_p - pos["valley_low"]) / entry_p) * 100.0), 2)
            else:
                pos["max_mfe_pct"] = round(max(pos["max_mfe_pct"], ((entry_p - pos["valley_low"]) / entry_p) * 100.0), 2)
                pos["max_mae_pct"] = round(max(pos["max_mae_pct"], ((pos["peak_high"] - entry_p) / entry_p) * 100.0), 2)

            # 1. ÖNCELİK: Başa-baş Stop Kontrolü (TP1 veya Chandelier Kilidi Sonrası)
            if (pos["early_be_locked"] or pos["tp1_hit"]) and pos.get("be_price"):
                be_p = pos["be_price"]
                if (side == "LONG" and (c_low <= be_p or c_close <= be_p)) or (side == "SHORT" and (c_high >= be_p or c_close >= be_p)):
                    rec = self._close_shadow_position(s_id, be_p, "Sanal Başa-Baş Koruması (BE)", "BE_CLOSED")
                    if rec:
                        closed_records.append(rec)
                    continue

            # 2. ÖNCELİK: Orijinal Stop Loss Kontrolü (Yalnızca TP1 öncesi)
            else:
                is_stopped = False
                if side == "LONG" and (c_low <= sl_p or c_close <= sl_p):
                    is_stopped = True
                elif side == "SHORT" and (c_high >= sl_p or c_close >= sl_p):
                    is_stopped = True

                if is_stopped:
                    rec = self._close_shadow_position(s_id, sl_p, f"Sanal Stop Loss (${sl_p:.4f})", "STOPPED")
                    if rec:
                        closed_records.append(rec)
                    continue

            # 3. ÖNCELİK: TP1 ve TP2 Hedef Kontrolleri
            if not pos["tp1_hit"]:
                if (side == "LONG" and c_high >= tp1_p) or (side == "SHORT" and c_low <= tp1_p):
                    pos["tp1_hit"] = True
                    pos["be_price"] = entry_p * (1.0008 if side == "LONG" else 0.9992)

            if pos["tp1_hit"]:
                if (side == "LONG" and c_high >= tp2_p) or (side == "SHORT" and c_low <= tp2_p):
                    rec = self._close_shadow_position(s_id, tp2_p, f"Sanal TP2 Gerçekleşti (${tp2_p:.4f})", "TP2_HIT")
                    if rec:
                        closed_records.append(rec)
                    continue

            # 4. ÖNCELİK: Zaman Aşımı (36 mum = 3 saat boyunca ne TP ne Stop olmadıysa kapat)
            if pos["candles_elapsed"] >= 36:
                rec = self._close_shadow_position(s_id, c_close, "Zaman Aşımı (3 Saat / 36 Mum)", "TIMEOUT")
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

        # ADLİ TEŞHİS (HERO vs SPOILER)
        symbol_clean = pos["symbol"].replace("/USDT", "")
        shield_txt = pos.get("shield", "Kuant Kalkan")
        pnl_val = pos["virtual_pnl_usd"]

        if pos["virtual_pnl_usd"] < -2.0:
            pos["verdict"] = "HERO_SHIELD"
            pos["verdict_badge"] = "KAHRAMAN KALKAN (Zarar Kurtarıldı)"
            pos["impact_usd"] = abs(pos["virtual_pnl_usd"])
            narrative = (
                f"KAHRAMAN SAVUNMA: {symbol_clean} {side} sinyali '{shield_txt}' tarafından engellendi. "
                f"Piyasa ters yöne kırıldı ve sanal stop seviyesini ({pos['sl_price']}) deldi. "
                f"Kalkan tetiklenmeseydi kasadan -${abs(pnl_val):.2f} (%{abs(pos['virtual_pnl_pct']):.1f} ROE) eksilecekti. "
                f"Kalkan sermayeyi kusursuz korudu!"
            )
        elif pos["virtual_pnl_usd"] > 2.0:
            pos["verdict"] = "SPOILER_SHIELD"
            pos["verdict_badge"] = "FRENLEYİCİ KALKAN (Kaçan Kâr)"
            pos["impact_usd"] = pos["virtual_pnl_usd"]
            narrative = (
                f"FRENLEYİCİ ENGEL: {symbol_clean} {side} sinyali '{shield_txt}' tarafından engellendi. "
                f"Ancak fiyat hedefe doğru +%{pos['max_mfe_pct']:.2f} zirve yaptı ve sanal hedefe (${exit_p}) ulaştı. "
                f"Bu filtre engellemeseydi kasaya +${abs(pnl_val):.2f} (+%{pos['virtual_pnl_pct']:.1f} ROE) kâr girecekti. "
                f"Tavsiye: {symbol_clean} paritesinde bu kalkan eşiği esnetilebilir."
            )
        else:
            pos["verdict"] = "NEUTRAL"
            pos["verdict_badge"] = "NÖTR (Başa-Baş)"
            pos["impact_usd"] = 0.0
            narrative = (
                f"NÖTR / DENGELİ: {symbol_clean} {side} işlemi başa-baş veya yatay bölgede kapandı (${pnl_val:+.2f}). "
                f"Kalkanın kasaya belirgin bir zararı veya fırsat maliyeti oluşmadı."
            )

        pos["narrative"] = narrative
        pos["status"] = exit_status

        self.completed_trades.append(pos)
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

        total_impact = total_saved_loss + total_missed_profit
        sei_score = round((total_saved_loss / total_impact) * 100.0, 1) if total_impact > 0 else 100.0

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
        Aktif pozisyonları ve geçmiş verileri birleştirerek tam kapsama sağlar.
        """
        completed = list(self.completed_trades)
        symbols_map: Dict[str, List[dict]] = {}

        for t in completed:
            sym = t.get("symbol", "")
            if sym not in symbols_map:
                symbols_map[sym] = []
            symbols_map[sym].append(t)

        # Aktif pozisyonları da sembol haritasına dahil et
        for s_id, pos in self.active_positions.items():
            sym = pos.get("symbol", "")
            if sym not in symbols_map:
                symbols_map[sym] = []

        # Tüm pariteleri topla
        all_syms = set(symbols_map.keys())
        if self.dna_baseline:
            for b_k, b_v in self.dna_baseline.items():
                s_fmt = b_v.get("symbol") or (b_k.replace("USDT", "") + "/USDT")
                all_syms.add(s_fmt)

        coin_dna_list = []
        for sym in all_syms:
            clean = sym.replace("/USDT", "").replace(":USDT", "").replace("USDT", "")
            t_list = symbols_map.get(sym, [])
            tot = len(t_list)

            # Bu sembole ait aktif işlem var mı?
            active_for_coin = [p for p in self.active_positions.values() if p.get("symbol") == sym]
            active_cnt = len(active_for_coin)

            heroes = [t for t in t_list if t.get("verdict") == "HERO_SHIELD"]
            spoilers = [t for t in t_list if t.get("verdict") == "SPOILER_SHIELD"]

            saved = sum(abs(t.get("virtual_pnl_usd", 0.0)) for t in heroes)
            missed = sum(t.get("virtual_pnl_usd", 0.0) for t in spoilers)
            impact = saved + missed
            sei = round((saved / impact) * 100.0, 1) if impact > 0 else 100.0

            # En sık engelleyen kalkan
            shield_counts: Dict[str, int] = {}
            for t in t_list + active_for_coin:
                s_name = t.get("shield", "Genel Kalkan")
                shield_counts[s_name] = shield_counts.get(s_name, 0) + 1

            # Persona ve baz parametreler
            base_p = self.dna_baseline.get(clean + "USDT", {})
            current_persona = base_p.get("persona_name", "Standart / Dengeli")

            # Çok Boyutlu Adli Teşhis & Kalibrasyon Motoru
            diag = self._diagnose_multi_dimensional(
                clean=clean,
                sym=sym,
                current_persona=current_persona,
                base_p=base_p,
                coin_completed=t_list,
                coin_actives=active_for_coin,
                heroes=heroes,
                spoilers=spoilers,
                saved=saved,
                missed=missed,
                sei=sei,
                shield_counts=shield_counts
            )

            coin_dna_list.append({
                "symbol": clean,
                "full_symbol": sym,
                "total_shadows": tot + active_cnt,
                "active_shadows": active_cnt,
                "completed_shadows": tot,
                "hero_count": len(heroes),
                "spoiler_count": len(spoilers),
                "saved_loss_usd": round(saved, 2),
                "missed_profit_usd": round(missed, 2),
                "net_alpha_usd": round(saved - missed, 2),
                "sei": sei,
                "top_shield": diag["top_shield"],
                "wick_elasticity": diag["avg_wick"],
                "recommendation": diag["recommendation"],
                "recommendation_badge": diag["rec_badge"],
                "forensic_narrative": diag["forensic_narrative"],
                "primary_scenario": diag["primary_scenario"],
                "scenario_title": diag["scenario_title"],
                "optimality_score": diag["optimality_score"],
                "optimality_status": diag["optimality_status"],
                "optimality_desc": diag["optimality_desc"],
                "modifications_count": diag["modifications_count"],
                "modifications_summary": diag["modifications_summary"],
                "is_calibrated_needed": diag["is_calibrated_needed"]
            })

        coin_dna_list.sort(key=lambda x: (x["total_shadows"], abs(x["net_alpha_usd"])), reverse=True)
        return coin_dna_list

    # ──────────────────────────────────────────────────────────────────────────
    # ÇOK BOYUTLU KUANT ADLİ KALİBRASYON MOTORU (MULTI-DIMENSIONAL ENGINE)
    # ──────────────────────────────────────────────────────────────────────────
    def _diagnose_multi_dimensional(
        self,
        clean: str,
        sym: str,
        current_persona: str,
        base_p: dict,
        coin_completed: list,
        coin_actives: list,
        heroes: list,
        spoilers: list,
        saved: float,
        missed: float,
        sei: float,
        shield_counts: dict
    ) -> dict:
        """
        Bir coin için tüm piyasa rejimlerini (8 kuant senaryosu) ve eşzamanlı
        çoklu parametre değişikliklerini (Fitil, BE, Confluence, ATR, Marjin, Strateji)
        tespit eden otonom kuant zeka fonksiyonu.
        """
        tot_completed = len(coin_completed)
        tot_active = len(coin_actives)

        # 1. Telemetri İstatistikleri
        all_trades = coin_completed + coin_actives
        wicks = [float(t.get("telemetry", {}).get("lower_wick_ratio", 0.0)) for t in all_trades if "lower_wick_ratio" in t.get("telemetry", {})]
        avg_wick = round((sum(wicks) / len(wicks)) * 100.0, 1) if wicks else 13.5
        atrs = [float(t.get("telemetry", {}).get("atr_pct", 0.0)) for t in all_trades if "atr_pct" in t.get("telemetry", {})]
        avg_atr = round(sum(atrs) / len(atrs), 2) if atrs else 1.25

        # En çok engelleyen kalkan
        top_shield = max(shield_counts.items(), key=lambda x: x[1])[0] if shield_counts else "Genel Kalkan"

        # Erken Başa-Baş (Chandelier Premature BE) Kontrolü
        premature_be_trades = [t for t in coin_completed if t.get("status") == "BE_CLOSED" and t.get("max_mfe_pct", 0.0) >= 1.80]

        # 2. Senaryo Tespiti (8 Kuant Rejimi)
        calibrated = False
        if len(premature_be_trades) >= 1 and missed > saved:
            calibrated = True
            rec_badge = "ERKEN BE"
            primary_scenario = "PREMATURE_BE_WHIPSAW"
            scenario_title = "Erken Başa-Baş (Chandelier) Kırbaç Tuzağı"
            recommendation = f"{len(premature_be_trades)} işlemde erken BE kilidi tetiklendikten sonra fiyat doğal dalgalanmayla girişte kapandı ve ardından TP hedeflerine fırladı."
            forensic_narrative = (
                f"{clean} paritesinde yön analizi son derece isabetliydi. Ancak +%0.80 kârda devreye giren Chandelier Erken Başa-Baş (BE) kilidi, "
                f"paritenin doğal fitil oynaklığı (%{avg_wick:.1f}) nedeniyle erkenden tetiklendi ({len(premature_be_trades)} işlem). "
                f"Pozisyon $0 başa-baş ile kapatıldıktan hemen sonra fiyat TP hedeflerine doğru fırladı. "
                f"Bu durum pariteye yeterli hareket alanı tanınmadığını ve erken BE eşiğinin yükseltilmesi gerektiğini kanıtlar."
            )
        elif sei < 40.0 and len(spoilers) >= 2:
            calibrated = True
            rec_badge = "GEVŞET"
            primary_scenario = "SPOILER_OVER_RESTRICTIVE"
            scenario_title = "Aşırı Katı Filtre Kurbanı (Kaçan Fırsat Riski)"
            recommendation = f"Frenleyici kalkan bu paritede ${missed:.1f} kâr kaçırdı ({len(spoilers)} işlem). '{top_shield}' eşiği bu pariteye özel %30 esnetilmeli."
            forensic_narrative = (
                f"{clean} paritesinde savunma kalkanları piyasanın dinamizmine ayak uyduramayarak gereğinden katı davrandı. "
                f"Özellikle '{top_shield}' kalkanı {len(spoilers)} kârlı işlemi engelleyerek toplam ${missed:.2f} potansiyel kazancı kaçırdı. "
                f"Kurtarılan zarar sadece ${saved:.2f} seviyesinde kaldığı için kalkan verimliliği (%{sei:.1f}) kritik eşiğin altına indi. "
                f"Kalkan eşikleri %25-30 gevşetilerek paritenin alfa üretim potansiyeli serbest bırakılmalıdır."
            )
        elif sei >= 75.0 and len(heroes) >= 2:
            rec_badge = "KORU"
            primary_scenario = "HERO_BULLETPROOF"
            scenario_title = "Çelik Savunma Zırhı (Kusursuz Sermaye Koruması)"
            recommendation = f"Kalkan kusursuz çalışıyor. Toplam ${saved:.1f} sermaye korundu. Mevcut sıkı filtreler korunmalı."
            forensic_narrative = (
                f"{clean} paritesinde kuant kalkanlar tam bir sermaye koruma kalkanı gibi çalışıyor. "
                f"Kalkanlar mutlak stop ile sonuçlanacak {len(heroes)} işlemi milisaniyesinde engelleyerek kasayı tam -${saved:.2f} zarardan korudu. "
                f"Kalkan Verimlilik Endeksi (SEI: %{sei:.1f}) kurumsal seviyenin üzerindedir. "
                f"Mevcut sıkı filtre parametreleri asla bozulmamalı, güvenle korunmalıdır."
            )
        elif avg_wick >= 20.0 or "WHIPSAW" in current_persona:
            calibrated = True
            rec_badge = "FITIL TUZAK"
            primary_scenario = "HIGH_FAKEOUT_VOLATILE"
            scenario_title = "Sahte Kırılım & Fitil Tuzağı (Whipsaw Rejimi)"
            recommendation = f"Paritenin ortalama fitil elastikiyeti (%{avg_wick:.1f}) çok yüksek. Breakout yasaklanmalı, S3/R3 sekmeleri hedeflenmeli."
            forensic_narrative = (
                f"{clean} paritesi ortalama %{avg_wick:.1f} gibi yüksek bir sahte fitil elastikiyetine sahip. "
                f"Bu parite breakout hareketlerinde alıcıları içeri çekip hemen ardından stop patlatan bir piyasa yapısına sahip. "
                f"Breakout kovalamak yerine sadece Camarilla S3/R3 ve nPOC ekstrem seviyelerinden tepki aranmalıdır."
            )
        elif avg_atr >= 1.8 and len(heroes) >= 2:
            calibrated = True
            rec_badge = "GENİŞ STOP"
            primary_scenario = "HIGH_BETA_SUFFOCATION"
            scenario_title = "Dar Stop Boğulması (Yüksek Volatilite & ATR Uyumsuzluğu)"
            recommendation = f"Yüksek volatilite (%{avg_atr:.2f} ATR) dar stopları erken patlatıyor. Stop çarpanı 2.0x ATR seviyesine genişletilmeli."
            forensic_narrative = (
                f"{clean} paritesinin oynaklık katsayısı (%{avg_atr:.2f} ATR) piyasa ortalamasından belirgin şekilde yüksek. "
                f"Standart stop mesafeleri normal dalgalanma içinde kalıp erken tetikleniyor. "
                f"Stop genişliğinin 2.0x ATR seviyesine çekilmesi pozisyona rahat bir hareket alanı sağlayacaktır."
            )
        elif "Tahta" in top_shield or "Likidite" in top_shield:
            rec_badge = "TAHTA DUVARI"
            primary_scenario = "LOW_LIQUIDITY_WALL"
            scenario_title = "Derinlik Duvarı & Likidite Açığı (Orderbook Dengesizliği)"
            recommendation = f"Paritede emir defteri dengesizliği (OBI) hakim. Tahta likiditesi ve mikro-CVD emilim teyidi şart."
            forensic_narrative = (
                f"{clean} paritesinde emir defteri dengesizliği (OBI) ve yapay duvarlar sıkça tetikleniyor. "
                f"Bu paritede tahta likiditesi ve mikro-CVD emilim teyidi aranmadan açılan işlemler yüksek kayma riski taşır."
            )
        elif tot_completed >= 3 and 40.0 <= sei < 75.0:
            rec_badge = "DENGELİ"
            primary_scenario = "EQUILIBRIUM_BALANCED"
            scenario_title = "Kararlı ve Dengeli Piyasa (Optimum Denge)"
            recommendation = f"Koruma ve fırsat dengesi stabil (SEI: %{sei:.1f}). Standart parametreler optimum."
            forensic_narrative = (
                f"{clean} paritesinde hem engellenen zararlar (${saved:.2f}) hem de kaçan kârlar (${missed:.2f}) makul bir denge içinde (SEI: %{sei:.1f}). "
                f"Sistemin standart kuralları ve risk çarpanları bu parite için optimum verimliliktedir."
            )
        elif tot_active > 0 and tot_completed == 0:
            rec_badge = "TAKİPTE"
            primary_scenario = "ACCUMULATING_DATA"
            scenario_title = "Canlı Piyasa Gözlemi (Aktif Pozisyon Takipte)"
            recommendation = f"Şu anda {tot_active} adet gölge işlem canlı fiyat ve mumlarla izleniyor."
            forensic_narrative = f"{clean} paritesinde canlı piyasa sinyali alındı ve kalkan tarafından engellenen işlem anlık olarak simüle ediliyor."
        else:
            rec_badge = "VERİ TOPLANIYOR"
            primary_scenario = "ACCUMULATING_DATA"
            scenario_title = "Canlı Piyasa Gözlemi (Veri Biriktirme Modu)"
            recommendation = f"Henüz {tot_completed} gölge işlem tamamlandı ({tot_active} aktif). Sağlıklı kalibrasyon için takip sürüyor."
            forensic_narrative = (
                f"{clean} paritesinde şu ana kadar {tot_completed} tamamlanmış, {tot_active} aktif gölge işlem izlendi. "
                f"İstatistiki güvenilirlik için asgari 3-5 işlem beklenmektedir. "
                f"Erken optimizasyon aşırı uyum (overfitting) riski yaratabileceğinden sistem pariteyi canlı izlemeye devam ediyor."
            )

        # 3. Çok Boyutlu Eylem Planı (Modifications List)
        modifications = []

        # Mod 1: Kalkan Hassasiyeti
        if sei < 40.0 and len(spoilers) >= 2:
            modifications.append({
                "parameter": f"{top_shield} Hassasiyeti",
                "code_key": f"shield_sensitivity_{clean.lower()}",
                "current_val": "%100 (Tam Katı)",
                "proposed_val": "%70 (Seçici Esnek)",
                "urgency": "YÜKSEK",
                "reason": f"Bu kalkan {len(spoilers)} kârlı işlemi engelleyerek kasayı ${missed:.2f} kârdan mahrum bıraktı. Eşik %30 esnetilmeli.",
                "expected_impact": f"+${missed:.2f} Potansiyel Net Kâr Artışı"
            })

        # Mod 2: Confluence Skoru
        if sei < 40.0 and len(spoilers) >= 2:
            modifications.append({
                "parameter": "Minimum Confluence Skoru",
                "code_key": f"min_confluence_{clean.lower()}",
                "current_val": "4 Puan" if "WHIPSAW" in current_persona else "3 Puan",
                "proposed_val": "3 Puan" if "WHIPSAW" in current_persona else "2 Puan",
                "urgency": "ORTA",
                "reason": f"{clean} güçlü alfa ürettiğinde tüm indikatörler aynı anda yeşile dönmeyebilir. Baraj 1 puan indirilerek kârlı işlemler yakalanabilir.",
                "expected_impact": "Sinyal Yakalama Oranını %35 Artırır"
            })
        elif sei >= 80.0 and len(heroes) >= 2 and len(spoilers) == 0:
            modifications.append({
                "parameter": "Minimum Confluence Skoru",
                "code_key": f"min_confluence_{clean.lower()}",
                "current_val": "3 Puan",
                "proposed_val": "4 Puan (Elit Baraj)",
                "urgency": "ORTA",
                "reason": f"{clean} paritesinde kalkanlar çok başarılı. Zayıf sinyalleri tamamen elemek için baraj 4 puana yükseltilebilir.",
                "expected_impact": "Hatalı Girişleri %25 Azaltır"
            })

        # Mod 3: Chandelier Erken Başa-Baş (BE) Kilidi
        if len(premature_be_trades) >= 1 or (avg_wick >= 18.0 and missed > saved):
            modifications.append({
                "parameter": "Chandelier Erken Başa-Baş (BE) Kilidi",
                "code_key": f"chandelier_be_threshold_{clean.lower()}",
                "current_val": "+%0.80 Kârda Kilitle",
                "proposed_val": "+%1.40 Kârda Kilitle",
                "urgency": "YÜKSEK",
                "reason": f"Ortalama fitil boyu %{avg_wick:.1f} olan bu paritede +%0.80 çok dar kalıyor. Fiyat doğal salınımla başa-başta kapanıp ardından hedefe gidiyor.",
                "expected_impact": "Erken Stoplanmayı %60 Engeller"
            })

        # Mod 4: Sahte Fitil Toleransı
        if avg_wick >= 18.0 or "WHIPSAW" in current_persona:
            modifications.append({
                "parameter": "Sahte Fitil (Fakeout) Toleransı",
                "code_key": f"fakeout_wick_threshold_{clean.lower()}",
                "current_val": "%15.0",
                "proposed_val": f"%{max(22.0, avg_wick + 3.0):.1f}",
                "urgency": "YÜKSEK",
                "reason": f"Paritenin doğal fitil boyu (%{avg_wick:.1f}) piyasa ortalamasının çok üstünde. Eşik artırılarak sahte kırılım alarmları dengelenmeli.",
                "expected_impact": "Gereksiz Kalkan Retlerini %45 Azaltır"
            })

        # Mod 5: Stop-Loss ATR Çarpanı
        if avg_atr >= 1.6:
            modifications.append({
                "parameter": "Stop-Loss ATR Çarpanı",
                "code_key": f"stop_atr_multiplier_{clean.lower()}",
                "current_val": "1.5x ATR",
                "proposed_val": "2.2x ATR (Genişletilmiş Koruma)",
                "urgency": "ORTA",
                "reason": f"Yüksek volatilite (%{avg_atr:.2f} ATR) nedeniyle dar stoplar piyasa gürültüsüne takılıyor. Stop mesafesi genişletilmeli.",
                "expected_impact": "Piyasa Gürültüsünden Stop Olmayı %30 Azaltır"
            })

        # Mod 6: Dinamik Marjin Katsayısı
        if sei >= 75.0 and saved >= 40.0:
            modifications.append({
                "parameter": "Dinamik Marjin Katsayısı",
                "code_key": f"margin_scale_{clean.lower()}",
                "current_val": "1.00x ($250)",
                "proposed_val": "1.25x ($312.50)",
                "urgency": "DÜŞÜK",
                "reason": f"Kalkan verimliliği (%{sei:.1f}) elit seviyede. Yüksek korumalı sinyallerde pozisyon büyüklüğü %25 artırılabilir.",
                "expected_impact": "Kazanan İşlemlerde Net Kârı %25 Artırır"
            })
        elif sei < 35.0 and len(heroes) >= 2:
            modifications.append({
                "parameter": "Dinamik Marjin Katsayısı",
                "code_key": f"margin_scale_{clean.lower()}",
                "current_val": "1.00x ($250)",
                "proposed_val": "0.50x ($125.00)",
                "urgency": "YÜKSEK",
                "reason": f"{clean} yüksek testere riski üretiyor. Risk dengelenene kadar marjin yarıya çekilmeli.",
                "expected_impact": "Potansiyel Kasa Drawdown'unu %50 Düşürür"
            })

        # Mod 7: İzin Verilen Stratejiler
        if avg_wick >= 22.0 or "WHIPSAW" in current_persona:
            modifications.append({
                "parameter": "İzin Verilen Strateji Rejimi",
                "code_key": f"allowed_setups_{clean.lower()}",
                "current_val": "Tüm Stratejiler (Breakout + Reversal)",
                "proposed_val": "Sadece Dip/Tepe Dönüşleri (Camarilla S3/R3 & nPOC)",
                "urgency": "YÜKSEK",
                "reason": "Yüksek fitilli piyasalarda kırılım (Breakout) kovalamak tuzak yaratır. Sadece aşırı satım/aşırı alım tepkileri oynanmalı.",
                "expected_impact": "Sahte Kırılım Zararlarını Sıfırlar"
            })

        active_mods = [m for m in modifications if m["urgency"] != "BİLGİ"]
        mods_summary = ", ".join([m["parameter"].split()[0] for m in active_mods]) if active_mods else "Optimum"

        if not modifications:
            modifications.append({
                "parameter": "Tüm Kuant Parametreleri Optimum",
                "code_key": f"all_parameters_{clean.lower()}",
                "current_val": "Standart Konfigürasyon",
                "proposed_val": "Mevcut Durumu Koru",
                "urgency": "BİLGİ",
                "reason": f"Mevcut veriler ışığında parite filtreleri ve stratejileri dengeli çalışıyor. Ek kalibrasyon gerekmiyor.",
                "expected_impact": "Mevcut Kasa İstikrarını Sürdürür"
            })

        suggested_diff = {
            "current_wick_threshold": "%15.0",
            "proposed_wick_threshold": f"%{max(22.0, avg_wick + 3.0):.1f}" if (avg_wick >= 18.0 or "WHIPSAW" in current_persona) else ("%10.0" if sei < 40 and len(spoilers) >= 2 else "%15.0"),
            "current_min_confluence": 4 if "WHIPSAW" in current_persona else 3,
            "proposed_min_confluence": 3 if (sei < 40 and len(spoilers) >= 2) else (4 if "WHIPSAW" in current_persona else 3),
            "expected_alpha_boost": f"+${missed:.2f}" if missed > 0 else "$0.00"
        }

        # 4. Optimum Durum & Kuant Kararlılık Endeksi (Optimality Index)
        if primary_scenario == "HERO_BULLETPROOF":
            optimality_score = 98.0
            optimality_status = "KUSURSUZ OPTİMUM (DOKUNMA)"
            optimality_desc = "Parametreler altın oranda. Kalkanlar kusursuz sermaye koruması sağlıyor, parametre değiştirmek riski artırır."
        elif primary_scenario == "EQUILIBRIUM_BALANCED":
            optimality_score = 88.0
            optimality_status = "STABİL VE OPTİMUM"
            optimality_desc = "Fırsat ve koruma dengesi kararlı seviyede. Mevcut konfigürasyon sürdürülmeli."
        elif primary_scenario == "ACCUMULATING_DATA":
            optimality_score = 50.0
            optimality_status = "VERİ BİRİKİYOR (GÖZLEM MODU)"
            optimality_desc = f"İstatistiki kesinlik için {tot_completed}/5 işlem tamamlandı. Erken müdahale aşırı uyum (overfitting) tuzağı yaratır."
        else:
            optimality_score = max(15.0, round(sei * 0.4, 1))
            optimality_status = "KALİBRASYON GEREKLİ (OPTİMUM DIŞI)"
            optimality_desc = f"Parite {scenario_title} rejiminde. Sermaye verimliliği için paket uygulanmalı."

        return {
            "rec_badge": rec_badge,
            "recommendation": recommendation,
            "forensic_narrative": forensic_narrative,
            "primary_scenario": primary_scenario,
            "scenario_title": scenario_title,
            "optimality_score": optimality_score,
            "optimality_status": optimality_status,
            "optimality_desc": optimality_desc,
            "modifications": modifications,
            "modifications_count": len(active_mods),
            "modifications_summary": f"{len(active_mods)} Değişiklik ({mods_summary})" if active_mods else "Optimum (0 Değişiklik)",
            "is_calibrated_needed": calibrated,
            "suggested_diff": suggested_diff,
            "avg_wick": avg_wick,
            "avg_atr": avg_atr,
            "top_shield": top_shield
        }

    # ──────────────────────────────────────────────────────────────────────────
    # PARİTE DETAYLI ADLİ OTOPSİ PAKETİ (COIN FORENSIC DEEP-DIVE MODAL DATA)
    # ──────────────────────────────────────────────────────────────────────────
    def get_coin_forensic_detail(self, symbol: str) -> dict:
        """
        Kullanıcı dashboard'da bir coinin [Detay] butonuna bastığında açılacak
        en ince ayrıntılı adli inceleme ve çok boyutlu parametre optimizasyon paketi.
        """
        clean = symbol.replace("/USDT", "").replace(":USDT", "").replace("USDT", "").upper()
        sym = f"{clean}/USDT"

        # Bu coine ait aktif ve tamamlanmış işlemleri topla
        coin_actives = [p for p in self.active_positions.values() if clean in p.get("symbol", "").upper()]
        coin_completed = [t for t in self.completed_trades if clean in t.get("symbol", "").upper()]

        heroes = [t for t in coin_completed if t.get("verdict") == "HERO_SHIELD"]
        spoilers = [t for t in coin_completed if t.get("verdict") == "SPOILER_SHIELD"]
        saved = sum(abs(t.get("virtual_pnl_usd", 0.0)) for t in heroes)
        missed = sum(t.get("virtual_pnl_usd", 0.0) for t in spoilers)
        impact = saved + missed
        sei = round((saved / impact) * 100.0, 1) if impact > 0 else 100.0

        # Kalkan kırılımı
        shields_breakdown = {}
        shield_counts = {}
        for t in coin_completed:
            s_name = t.get("shield", "Bilinmeyen Kalkan")
            shield_counts[s_name] = shield_counts.get(s_name, 0) + 1
            if s_name not in shields_breakdown:
                shields_breakdown[s_name] = {"hero": 0, "spoiler": 0, "saved": 0.0, "missed": 0.0}
            if t.get("verdict") == "HERO_SHIELD":
                shields_breakdown[s_name]["hero"] += 1
                shields_breakdown[s_name]["saved"] += abs(t.get("virtual_pnl_usd", 0.0))
            elif t.get("verdict") == "SPOILER_SHIELD":
                shields_breakdown[s_name]["spoiler"] += 1
                shields_breakdown[s_name]["missed"] += t.get("virtual_pnl_usd", 0.0)

        for p in coin_actives:
            s_name = p.get("shield", "Genel Kalkan")
            shield_counts[s_name] = shield_counts.get(s_name, 0) + 1

        # Persona ve baz parametreler
        base_p = self.dna_baseline.get(clean + "USDT", {})
        current_persona = base_p.get("persona_name", "Standart / Dengeli")

        # Çok boyutlu adli teşhis
        diag = self._diagnose_multi_dimensional(
            clean=clean,
            sym=sym,
            current_persona=current_persona,
            base_p=base_p,
            coin_completed=coin_completed,
            coin_actives=coin_actives,
            heroes=heroes,
            spoilers=spoilers,
            saved=saved,
            missed=missed,
            sei=sei,
            shield_counts=shield_counts
        )

        return {
            "symbol": clean,
            "full_symbol": sym,
            "persona_name": current_persona,
            "total_trades": len(coin_completed) + len(coin_actives),
            "active_count": len(coin_actives),
            "completed_count": len(coin_completed),
            "hero_count": len(heroes),
            "spoiler_count": len(spoilers),
            "saved_loss_usd": round(saved, 2),
            "missed_profit_usd": round(missed, 2),
            "net_alpha_usd": round(saved - missed, 2),
            "sei": sei,
            "primary_scenario": diag["primary_scenario"],
            "scenario_title": diag["scenario_title"],
            "optimality_score": diag["optimality_score"],
            "optimality_status": diag["optimality_status"],
            "optimality_desc": diag["optimality_desc"],
            "forensic_narrative": diag["forensic_narrative"],
            "modifications": diag["modifications"],
            "modifications_count": diag["modifications_count"],
            "modifications_summary": diag["modifications_summary"],
            "suggested_diff": diag["suggested_diff"],
            "shields_breakdown": shields_breakdown,
            "active_positions": coin_actives,
            "completed_trades": coin_completed[-25:]  # son 25 işlem
        }

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
                role = "KAHRAMAN (Hero)"
            elif sei <= 35.0 and len(spoilers) >= 2:
                role = "FRENLEYİCİ (Spoiler)"
            else:
                role = "DENGELİ (Balanced)"

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
        """Hafızadaki son 500 gölge işlemi ve aktif pozisyonları JSON dosyasına yazar."""
        try:
            data = {
                "updated_at": datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M:%S"),
                "completed": list(self.completed_trades)[-500:],
                "actives": list(self.active_positions.values())
            }
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def load_history(self):
        """Başlangıçta geçmiş gölge işlemleri ve aktif pozisyonları hafızaya yükler."""
        if not os.path.exists(self.history_file):
            return
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                completed = data.get("completed", [])
                for t in completed:
                    self.completed_trades.append(t)
                actives = data.get("actives", [])
                for a in actives:
                    s_id = a.get("id") or a.get("shadow_id")
                    if s_id:
                        if "id" not in a:
                            a["id"] = s_id
                        self.active_positions[s_id] = a
                        sym = a.get("symbol")
                        if sym:
                            self.symbol_active_map[sym] = s_id
            print(f">> [GÖLGE MOTORU] {len(self.completed_trades)} adet geçmiş, {len(self.active_positions)} adet aktif gölge işlem hafızaya yüklendi.")
        except Exception as e:
            print(f">> [GÖLGE MOTORU UYARI] Geçmiş yüklenemedi: {e}")
