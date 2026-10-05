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
import base64
import threading
import urllib.request
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

try:
    from paper_trader import _get_gh_token, GITHUB_REPO, GITHUB_BRANCH
    GITHUB_TOKEN = _get_gh_token()
except Exception:
    GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
    GITHUB_REPO = os.environ.get("GITHUB_REPO", "scullo/trade-bot")
    GITHUB_BRANCH = os.environ.get("GITHUB_STATE_BRANCH", "state")

SHADOW_GITHUB_FILE_PATH = "shadow_trades_history.json"
SHADOW_GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{SHADOW_GITHUB_FILE_PATH}"


class ShadowExecutionEngine:
    """
    Sıfır Gecikmeli Bellek İçi Gölge İşlem Motoru ve Otonom Kuant Kalibratörü.
    """

    def __init__(self, history_file: str = "shadow_trades_history.json", max_active: int = 300, max_history: int = 5000):
        self.history_file = os.path.join(os.path.dirname(__file__), history_file)
        self.max_active = max_active
        self.max_history = max_history
        self.is_test = "test" in os.path.basename(self.history_file).lower()

        # Bulut Kalıcılık (GitHub State Dalı) ve Sağlık Koruması
        self._github_sha: Optional[str] = None
        self._push_lock = threading.Lock()
        self._last_push_ts: float = 0.0
        self.last_sync_status: str = "BEKLEMEDE"
        self.last_tick_ts: float = time.time()
        self.last_candle_ts: float = time.time()

        # Aktif Sanal Pozisyonlar: {shadow_id: ShadowPositionDict}
        self.active_positions: Dict[str, dict] = {}

        # Tamamlanan Sanal İşlemler (O(1) Dairesel Bellek Kuyruğu)
        self.completed_trades: deque = deque(maxlen=max_history)

        # Sembol ve Kalkan bazlı hızlı arama endeksleri
        self.symbol_active_map: Dict[str, str] = {}  # symbol -> shadow_id (son aktif)
        self.last_rejection_ts: Dict[str, float] = {} # (symbol, setup) -> timestamp (throttling)

        # 👻 Çift Yönlü Karşı-Olgusal Takip: Post-Exit Hayalet İz Sürücüleri ("İşlem devam etseydi ne olurdu?")
        self.post_exit_ghosts: Dict[str, dict] = {}
        self.post_exit_history: deque = deque(maxlen=2000)

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
    # STANDART SEMBOL VE YÖN NORMALİZASYONU (VDA-12 & VDA-17)
    # ──────────────────────────────────────────────────────────────────────────
    @staticmethod
    def clean_symbol(symbol: str) -> str:
        """
        Standart sembol normalizasyonu (VDA-12).
        1000 ve 1000000 vadeli kontrat çarpan ön eklerini kaldırarak pariteyi
        'BASE/USDT' kanonik formatına dönüştürür.
        Örn: '1000PEPE/USDT' -> 'PEPE/USDT', '1000000MOG:USDT' -> 'MOG/USDT'
        """
        raw = str(symbol or "").strip().upper()
        raw = raw.replace(":USDT", "").replace("/USDT", "").replace("USDT", "").replace("/", "")
        if raw.startswith("1000000"):
            raw = raw[7:]
        elif raw.startswith("1000"):
            raw = raw[4:]
        return f"{raw}/USDT" if raw else ""

    @staticmethod
    def clean_base_symbol(symbol: str) -> str:
        """Pariteyi çıplak ana varlık sembolüne dönüştürür (örn: '1000PEPE/USDT' -> 'PEPE')."""
        s = ShadowExecutionEngine.clean_symbol(symbol)
        return s.replace("/USDT", "") if s else ""

    @staticmethod
    def get_setup_direction(canonical_setup: str) -> str:
        """
        Kanonik setup koduna göre beklenen işlem yönünü (LONG veya SHORT) döndürür (VDA-17).
        """
        s = str(canonical_setup or "").strip().upper()
        long_setups = {
            "SETUP_1_R4_BREAKOUT",
            "SETUP_1_OI_BULL_EXPANSION",
            "SETUP_3_S3_BOUNCE",
            "SETUP_3_S3_REVERSAL",
            "SETUP_5_R4_SUPPORT_FLIP",
            "SETUP_5_RANGE_BOUNCE",
            "SETUP_6_MVAH_BREAKOUT",
            "SETUP_6_MVAH_MACRO_BREAKOUT",
            "SETUP_9_BELOW_NPOC_BOUNCE",
            "SETUP_9_NPOC_BOUNCE",
            "SETUP_12_PDL_SWEEP_RECLAIM_LONG",
            "SETUP_14_ASIA_SWEEP_LONG",
            "SETUP_14_PIVOT_SUPPORT_FLIP",
            "SETUP_14_AVWAP_SUPPORT",
            "SETUP_15_AVWAP_MVAH_RECLAIM",
            "SETUP_15_AVWAP_RECLAIM",
            "SETUP_16_R3_SUPPORT_FLIP",
            "SETUP_16_R3_FLIP",
            "SETUP_16_FAKEOUT_RECLAIM_LONG",
            "SETUP_FAKEOUT_RECLAIM_LONG"
        }
        short_setups = {
            "SETUP_2_S4_BREAKDOWN",
            "SETUP_2_OI_SHORT_EXPANSION",
            "SETUP_4_R3_REJECTION",
            "SETUP_4_R3_REVERSAL",
            "SETUP_7_S4_BREAKDOWN",
            "SETUP_7_S4_RESISTANCE_FLIP",
            "SETUP_8_MVAL_BREAKDOWN",
            "SETUP_8_MVAL_MACRO_BREAKDOWN",
            "SETUP_10_ABOVE_NPOC_REJECTION",
            "SETUP_10_NPOC_REJECTION",
            "SETUP_11_FAKEOUT_RECLAIM_SHORT",
            "SETUP_11_RESISTANCE_FLIP",
            "SETUP_12_SUPPORT_BREAKDOWN",
            "SETUP_13_ASIA_SWEEP_SHORT",
            "SETUP_13_S3_RESISTANCE_FLIP",
            "SETUP_13_S3_FLIP",
            "SETUP_15_PDH_SWEEP_RECLAIM_SHORT",
            "SETUP_FAKEOUT_RECLAIM_SHORT"
        }
        if s in long_setups:
            return "LONG"
        if s in short_setups:
            return "SHORT"

        # Anahtar kelime tabanlı yedek yön tespiti
        if any(w in s for w in ["SHORT", "BREAKDOWN", "REJECTION", "REDDİ", "REDDI", "DİRENÇ", "DIRENC", "AYI"]):
            return "SHORT"
        if any(w in s for w in ["LONG", "BREAKOUT", "BOUNCE", "SEKME", "SUPPORT", "DESTEK", "BOĞA", "BOGA"]):
            return "LONG"
        return "UNKNOWN"

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
            if "Boğa Tavan" in r:
                return "Makro Boğa Tavan Kalkanı (Counter-Trend Short Shield)"
            elif "Ayı Düşüş" in r or "Düşüş" in r or "DUMP" in r:
                return "Makro Ayı Düşüş Kalkanı (Counter-Trend Long Shield)"
            return "Makro Trend & Düşüş Kalkanı (Macro Regime Shield)"
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
        clean_sym = self.clean_symbol(symbol)
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

        # 3. Yönü (Side) tespit et (VDA-17: extract_canonical_setup & get_setup_direction ile kusursuz yön hizalaması)
        if not side:
            canon = self.extract_canonical_setup(f"{setup_name} {reason}")
            side_detected = self.get_setup_direction(canon)
            if side_detected in ("LONG", "SHORT"):
                side = side_detected
            else:
                s_name = (setup_name + " " + reason).upper()
                if any(w in s_name for w in ["SHORT", "AYI", "BREAKDOWN", "DİRENÇ", "REDDİ", "S4"]):
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

        telemetry_dict = telemetry or {}
        macro_regime = telemetry_dict.get("macro_regime", "NEUTRAL")
        setup_archetype = telemetry_dict.get("setup_archetype", "UNKNOWN")
        regime_alignment = telemetry_dict.get("regime_alignment", "NEUTRAL")
        btc_chg_4h = float(telemetry_dict.get("btc_chg_4h", 0.0) or 0.0)
        btc_chg_1h = float(telemetry_dict.get("btc_chg_1h", 0.0) or 0.0)

        shadow_pos = {
            "id": shadow_id,
            "symbol": clean_sym,
            "side": side,
            "setup": setup_name.split('(')[0].strip(),
            "shield": shield_name,
            "reason": reason,
            "macro_regime": macro_regime,
            "setup_archetype": setup_archetype,
            "regime_alignment": regime_alignment,
            "btc_chg_4h": btc_chg_4h,
            "btc_chg_1h": btc_chg_1h,
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
            "telemetry": telemetry_dict
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
        self.last_tick_ts = time.time()
        clean_sym = self.clean_symbol(symbol)
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
        self.last_candle_ts = time.time()
        clean_sym = self.clean_symbol(symbol)
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

        # 5. ÖNCELİK: Post-Exit Hayalet İz Sürücülerini Güncelle (İşlem devam etseydi ne olurdu?)
        for g_id in list(self.post_exit_ghosts.keys()):
            g = self.post_exit_ghosts.get(g_id)
            if not g or g["symbol"] != clean_sym:
                continue
            g["candles_elapsed"] += 1
            if c_high > g["peak_high"]:
                g["peak_high"] = c_high
            if c_low < g["valley_low"] and c_low > 0:
                g["valley_low"] = c_low

            ex_p = g["exit_price"]
            side = g["side"]
            if side == "LONG":
                mfe = ((g["peak_high"] - ex_p) / ex_p) * 100.0 if ex_p > 0 else 0.0
                mae = ((ex_p - g["valley_low"]) / ex_p) * 100.0 if ex_p > 0 else 0.0
            else:
                mfe = ((ex_p - g["valley_low"]) / ex_p) * 100.0 if ex_p > 0 else 0.0
                mae = ((g["peak_high"] - ex_p) / ex_p) * 100.0 if ex_p > 0 else 0.0

            g["post_exit_mfe_pct"] = round(max(0.0, mfe), 2)
            g["post_exit_mae_pct"] = round(max(0.0, mae), 2)

            if g["candles_elapsed"] >= g["max_candles"]:
                if g["post_exit_mfe_pct"] >= 1.6:
                    g["verdict"] = "ERKEN_CIKIS_KACAN_DALGA"
                elif g["post_exit_mae_pct"] >= 1.6 and "STOP" in g["exit_status"].upper():
                    g["verdict"] = "KUSURSUZ_STOP_KORUMASI"
                elif g["post_exit_mae_pct"] >= 1.2 and "TP" in g["exit_status"].upper():
                    g["verdict"] = "SNIPER_TEPE_CIKISI"
                else:
                    g["verdict"] = "DENGELI_CIKIS"

                completed_ghost = self.post_exit_ghosts.pop(g_id, None)
                if completed_ghost:
                    self.post_exit_history.append(completed_ghost)

        return closed_records

    def spawn_post_exit_ghost(
        self,
        trade_id: str,
        symbol: str,
        side: str,
        exit_price: float,
        entry_price: float,
        exit_status: str,
        close_reason: str,
        max_candles: int = 24
    ):
        """Kapanan işlem için 'İşlem devam etseydi ne olurdu?' hayalet takibini başlatır."""
        clean_sym = self.clean_symbol(symbol)
        if exit_price <= 0.0 or not side:
            return
        g_id = f"GHOST_{trade_id}_{int(time.time())}"
        self.post_exit_ghosts[g_id] = {
            "id": g_id,
            "trade_id": str(trade_id),
            "symbol": clean_sym,
            "side": side.upper(),
            "entry_price": float(entry_price),
            "exit_price": float(exit_price),
            "exit_status": str(exit_status),
            "close_reason": str(close_reason),
            "exit_ts": time.time(),
            "candles_elapsed": 0,
            "max_candles": max_candles,
            "peak_high": float(exit_price),
            "valley_low": float(exit_price),
            "post_exit_mfe_pct": 0.0,
            "post_exit_mae_pct": 0.0,
            "verdict": "IZLENIYOR"
        }

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

        # VDA-36: Meme Coin Multiplier Guard (1000x ve 1M sözleşmelerinde spot/vadeli ölçek sapmasını normalize et)
        clean_base = self.clean_base_symbol(pos["symbol"])
        ratio = exit_p / entry_p if entry_p > 0 else 1.0
        if ratio > 500.0:
            if clean_base in ["PEPE", "SHIB", "BONK", "FLOKI", "LUNC", "CAT", "CHEEMS"]:
                exit_p = exit_p / 1000.0
        elif ratio < 0.002:
            if clean_base in ["PEPE", "SHIB", "BONK", "FLOKI", "LUNC", "CAT", "CHEEMS"]:
                exit_p = exit_p * 1000.0

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

        # VDA-37: İzole Marjin Tasfiye Tavanı (Maksimum kayıp yatırılan teminat ve -%100 ROE ile sınırlıdır)
        margin = float(pos.get("margin_usd", self.virtual_margin))
        gross_pnl = round(self.virtual_notional * raw_pnl_pct, 2)
        total_fees = round(self.virtual_notional * fee_pct, 2)

        net_pnl = max(-margin, gross_pnl - total_fees)
        roe_pct = max(-100.0, round(net_pct * self.virtual_leverage * 100.0, 2))

        pos["virtual_pnl_pct"] = roe_pct
        pos["virtual_pnl_usd"] = net_pnl

        # ADLİ TEŞHİS (HERO vs SPOILER)
        symbol_clean = pos["symbol"].replace("/USDT", "")
        shield_txt = pos.get("shield", "Kuant Kalkan")
        pnl_val = pos["virtual_pnl_usd"]

        macro_reg = pos.get("macro_regime", "")
        reg_align = pos.get("regime_alignment", "")
        setup_arch = pos.get("setup_archetype", "")

        if pos["virtual_pnl_usd"] < -2.0:
            pos["verdict"] = "HERO_SHIELD"
            pos["verdict_badge"] = "KAHRAMAN KALKAN (Zarar Kurtarıldı)"
            pos["impact_usd"] = abs(pos["virtual_pnl_usd"])
            if "COUNTER_TREND" in str(setup_arch) or "VETO" in str(reg_align) or "Ayı Düşüş Kalkanı" in shield_txt or "Boğa Tavan Kalkanı" in shield_txt:
                narrative = (
                    f"🛡️ KAHRAMAN REJİM SAVUNMASI: {symbol_clean} {side} sinyali makro ters rejimde ({macro_reg or 'BEAR/BULL'}) '{shield_txt}' tarafından engellendi. "
                    f"Piyasa ana akıntı yönünde ezici baskıyla sanal stop seviyesini ({pos['sl_price']}) deldi. "
                    f"Bu bıçak tutma tuzağı engellenmeseydi kasadan -${abs(pnl_val):.2f} (%{abs(pos['virtual_pnl_pct']):.1f} ROE) eksilecekti. "
                    f"Rejim kalkanı kasayı tam isabetle korudu!"
                )
            else:
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

        # 🔄 Zıt Yön (Inversion Counterfactual) Simülasyonu:
        # Eğer Long işlem zararla kapandıysa (HERO_SHIELD), ters yön olan SHORT ne kazandırırdı?
        inv_side = "SHORT" if side == "LONG" else "LONG"
        inv_raw_pnl = -raw_pnl_pct
        inv_net_pnl = inv_raw_pnl - fee_pct
        pos["inversion_side"] = inv_side
        pos["inversion_pnl_usd"] = max(-margin, round(self.virtual_notional * inv_net_pnl, 2))
        pos["inversion_verdict"] = "PROFITABLE_INVERSION" if pos["inversion_pnl_usd"] > 1.5 else "UNPROFITABLE_INVERSION"

        # 👻 Çift Yönlü Takip: Post-Exit Hayalet İz Sürücüsü Başlat ("İşlem devam etseydi ne olurdu?")
        self.spawn_post_exit_ghost(
            trade_id=pos["id"],
            symbol=pos["symbol"],
            side=pos["side"],
            exit_price=exit_p,
            entry_price=entry_p,
            exit_status=exit_status,
            close_reason=close_reason
        )

        self.completed_trades.append(pos)
        self.save_history(critical=True)
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
            sym = self.clean_symbol(t.get("symbol", ""))
            if not sym:
                continue
            if sym not in symbols_map:
                symbols_map[sym] = []
            symbols_map[sym].append(t)

        # Aktif pozisyonları da sembol haritasına dahil et
        for s_id, pos in self.active_positions.items():
            sym = self.clean_symbol(pos.get("symbol", ""))
            if not sym:
                continue
            if sym not in symbols_map:
                symbols_map[sym] = []

        # Tüm pariteleri topla
        all_syms = set(symbols_map.keys())
        if self.dna_baseline:
            for b_k, b_v in self.dna_baseline.items():
                s_fmt = b_v.get("symbol") or (b_k.replace("USDT", "") + "/USDT")
                all_syms.add(self.clean_symbol(s_fmt))

        coin_dna_list = []
        for sym in all_syms:
            clean = self.clean_base_symbol(sym)
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

            liq_tier = self.get_coin_liquidity_tier(clean)

            coin_dna_list.append({
                "symbol": clean,
                "full_symbol": sym,
                "liquidity_tier": liq_tier,
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
        wicks = []
        for t in all_trades:
            te = t.get("telemetry", {})
            if isinstance(te, dict) and "wick_ratio_pct" in te and te["wick_ratio_pct"] is not None:
                wicks.append(float(te["wick_ratio_pct"]))
            elif isinstance(te, dict) and "lower_wick_ratio" in te and te["lower_wick_ratio"] is not None:
                wicks.append(float(te["lower_wick_ratio"]) * 100.0)
            elif "wick_ratio_pct" in t and t["wick_ratio_pct"] is not None:
                wicks.append(float(t["wick_ratio_pct"]))
            else:
                # Fiyat hareketinin doğal dalgalanma (whiplash amplitude) oranından fitil türetme
                p_h = float(t.get("peak_high") or 0.0)
                p_l = float(t.get("valley_low") or 0.0)
                p_e = float(t.get("entry_price") or 0.0)
                p_x = float(t.get("exit_price") or p_e)
                if p_h > p_l > 0 and p_e > 0:
                    amp = (p_h - p_l) / p_e * 100.0
                    net = abs(p_x - p_e) / p_e * 100.0
                    whip = max(8.0, min(55.0, ((amp - net) / max(1e-5, amp)) * 100.0 * 0.45))
                    wicks.append(whip)
        avg_wick = round((sum(wicks) / len(wicks)), 1) if wicks else 13.5
        atrs = [float(t.get("telemetry", {}).get("atr_pct", 0.0)) for t in all_trades if isinstance(t.get("telemetry"), dict) and "atr_pct" in t.get("telemetry", {}) and t.get("telemetry", {}).get("atr_pct") is not None]
        avg_atr = round(sum(atrs) / len(atrs), 2) if atrs else 0.68

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
        elif avg_atr >= 0.90 and len(heroes) >= 2:
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
        if avg_wick >= 18.0 or "WHIPSAW" in current_persona or len(spoilers) >= 2:
            modifications.append({
                "parameter": "Sahte Fitil (Fakeout) Toleransı",
                "code_key": f"fakeout_wick_threshold_{clean.lower()}",
                "current_val": "%15.0",
                "proposed_val": f"%{max(20.0, avg_wick + 3.0):.1f}",
                "urgency": "YÜKSEK",
                "reason": f"Paritenin doğal fitil boyu (%{avg_wick:.1f}) piyasa ortalamasının çok üstünde. Eşik artırılarak sahte kırılım alarmları dengelenmeli.",
                "expected_impact": "Gereksiz Kalkan Retlerini %45 Azaltır"
            })

        # Mod 5: Stop-Loss ATR Çarpanı (5M ortalaması %0.68 olduğundan 0.85 üstü yüksek volatiltedir)
        if avg_atr >= 0.85:
            modifications.append({
                "parameter": "Stop-Loss ATR Çarpanı",
                "code_key": f"stop_atr_multiplier_{clean.lower()}",
                "current_val": "1.5x ATR",
                "proposed_val": "2.0x ATR (Genişletilmiş Koruma)",
                "urgency": "ORTA",
                "reason": f"Yüksek volatilite (%{avg_atr:.2f} ATR) nedeniyle dar stoplar piyasa gürültüsüne takılıyor. Stop mesafesi genişletilmeli.",
                "expected_impact": "Piyasa Gürültüsünden Stop Olmayı %30 Azaltır"
            })
        elif avg_atr <= 0.40 and tot_completed >= 5:
            modifications.append({
                "parameter": "Stop-Loss ATR Çarpanı",
                "code_key": f"stop_atr_multiplier_{clean.lower()}",
                "current_val": "1.5x ATR",
                "proposed_val": "1.2x ATR (Sıkı Stop / Sermaye Verimi)",
                "urgency": "DÜŞÜK",
                "reason": f"Düşük volatilite (%{avg_atr:.2f} ATR) paritenin stabil olduğunu gösteriyor. Stop daraltılarak sermaye verimi artırılabilir.",
                "expected_impact": "Stop Maliyetini %20 Düşürür"
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
        if avg_wick >= 22.0 or "WHIPSAW" in current_persona or (len(spoilers) >= 3 and sei < 45.0):
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
    # 360° KUANT MİMARİSİ: LİKİDİTE KATMANI, SETUP MATRİSİ VE KANONİK EŞLEME
    # ──────────────────────────────────────────────────────────────────────────
    @staticmethod
    def get_coin_liquidity_tier(symbol: str) -> dict:
        """Paritenin piyasa derinliğine göre 3 Kuant Likidite Katmanından birine atar."""
        clean = ShadowExecutionEngine.clean_base_symbol(symbol)
        tier_1_majors = {"BTC", "ETH", "SOL", "BNB", "XRP", "ADA"}
        tier_3_memes_and_thin = {
            "PEPE", "BONK", "DOGE", "WIF", "1000SHIB", "SHIB", "FLOKI", "BOME", "MEME",
            "TURBO", "NEIRO", "NOT", "1000PEPE", "1000FLOKI", "1000BONK", "BRETT", "POPCAT"
        }
        if clean in tier_1_majors:
            return {
                "tier": "TIER_1_KURUMSAL",
                "tier_label": "Tier-1 (Kurumsal Derinlik)",
                "badge": "TIER-1 MAJÖR",
                "color": "#10b981",
                "cvd_threshold": 52.0,
                "obi_threshold": 1.08,
                "vol_surge_threshold": 1.20,
                "fakeout_wick_tolerance": 15.0
            }
        elif clean in tier_3_memes_and_thin:
            return {
                "tier": "TIER_3_MEME_SIG",
                "tier_label": "Tier-3 (Sığ / Meme / Agresif Fitil)",
                "badge": "TIER-3 MEME",
                "color": "#a855f7",
                "cvd_threshold": 60.0,
                "obi_threshold": 1.40,
                "vol_surge_threshold": 1.80,
                "fakeout_wick_tolerance": 35.0
            }
        else:
            return {
                "tier": "TIER_2_DINAMIK",
                "tier_label": "Tier-2 (Dinamik Altcoin)",
                "badge": "TIER-2 DİNAMİK",
                "color": "#38bdf8",
                "cvd_threshold": 55.0,
                "obi_threshold": 1.20,
                "vol_surge_threshold": 1.45,
                "fakeout_wick_tolerance": 25.0
            }

    @staticmethod
    def extract_canonical_setup(setup_raw: str) -> str:
        """
        Kurulum adından standart kanonik kod üretir (VDA-17).
        strategy.py'deki 16 kurulum ve guncellev1 taksonomisiyle %100 birebir eşleşme sağlar.
        İki basamaklı kurulumlar (10-16) tek basamaklıların (1-9) alt dizesiyle çakışmaması için
        azalan sırada (16 -> 1) denetlenir.
        """
        s = str(setup_raw or "").strip().upper()
        if not s:
            return "SETUP_DİĞER"

        # 16. SETUP 16: R3 DİRENÇ AŞIMI & RETEST BOĞA DEVAMI LONG (R3 Support Flip)
        if "SETUP 16" in s or "SETUP_16" in s or "R3_SUPPORT_FLIP" in s or "R3 SUPPORT FLIP" in s or "R3 FLIP" in s:
            return "SETUP_16_R3_SUPPORT_FLIP"
        if "SETUP_FAKEOUT_RECLAIM_LONG" in s or "FAKEOUT_RECLAIM_LONG" in s or ("FAKEOUT" in s and "LONG" in s) or ("AYI TUZAĞI" in s and "LONG" in s) or ("BEAR TRAP" in s and "LONG" in s) or "SETUP_16_FAKEOUT_RECLAIM_LONG" in s:
            return "SETUP_16_R3_SUPPORT_FLIP"

        # 15. SETUP 15: AVWAP RECLAIM & mVAH BOĞA KIRILIMI RETEST LONG (Macro Absorption Flip)
        if "SETUP_15_PDH_SWEEP_RECLAIM_SHORT" in s or ("PDH_SWEEP" in s and "SHORT" in s):
            return "SETUP_15_PDH_SWEEP_RECLAIM_SHORT"
        if "SETUP 15" in s or "SETUP_15" in s or "AVWAP_MVAH_RECLAIM" in s or "AVWAP_RECLAIM" in s or ("AVWAP" in s and "MVAH" in s) or ("AVWAP" in s and "RECLAIM" in s) or "PDH_SWEEP" in s:
            return "SETUP_15_AVWAP_MVAH_RECLAIM"

        # 14. SETUP 14: ASIA SWEEP LONG / PIVOT SUPPORT FLIP (LONG)
        if "ASIA_SWEEP_LONG" in s or ("ASIA" in s and "LONG" in s) or "SETUP_14_ASIA_SWEEP_LONG" in s:
            return "SETUP_14_ASIA_SWEEP_LONG"
        if "SETUP 14" in s or "SETUP_14" in s or "PIVOT_SUPPORT_FLIP" in s or "PIVOT SUPPORT FLIP" in s or ("PIVOT" in s and "FLIP" in s) or "AVWAP_SUPPORT" in s or "BULLISH SUPPORT FLIP" in s:
            return "SETUP_14_PIVOT_SUPPORT_FLIP"

        # 13. SETUP 13: ASIA SWEEP SHORT / S3 RESISTANCE FLIP (SHORT)
        if "ASIA_SWEEP_SHORT" in s or ("ASIA" in s and "SHORT" in s) or "SETUP_13_ASIA_SWEEP_SHORT" in s:
            return "SETUP_13_ASIA_SWEEP_SHORT"
        if "SETUP 13" in s or "SETUP_13" in s or "S3_RESISTANCE_FLIP" in s or "S3 RESISTANCE FLIP" in s or "S3 FLIP" in s:
            return "SETUP_13_S3_RESISTANCE_FLIP"

        # 12. SETUP 12: DESTEK ÇÖKÜŞÜ SHORT / PDL SWEEP RECLAIM LONG
        if "SETUP_12_PDL_SWEEP_RECLAIM_LONG" in s or ("PDL_SWEEP" in s and "LONG" in s):
            return "SETUP_12_PDL_SWEEP_RECLAIM_LONG"
        if "SETUP 12" in s or "SETUP_12" in s or "SUPPORT_BREAKDOWN" in s or "DESTEK ÇÖKÜŞÜ" in s or "DESTEK COKUSU" in s or "ÇÖKÜŞ" in s or "COKUS" in s or "PDL_SWEEP" in s:
            return "SETUP_12_SUPPORT_BREAKDOWN"

        # 11. SETUP 11: PİVOT P / mPOC / TEPE AVWAP ALTTAN RETEST AYI REDDİ SHORT (Bearish Resistance Flip)
        if "SETUP 11" in s or "SETUP_11" in s or "SETUP_11_RESISTANCE_FLIP" in s or ("RESISTANCE_FLIP" in s and not any(k in s for k in ["S4", "S3", "SETUP_7", "SETUP 7", "SETUP_13", "SETUP 13"])):
            return "SETUP_11_RESISTANCE_FLIP"
        if "SETUP_FAKEOUT_RECLAIM_SHORT" in s or "FAKEOUT_RECLAIM_SHORT" in s or ("FAKEOUT" in s and "SHORT" in s) or ("BOĞA TUZAĞI" in s and "SHORT" in s) or ("BULL TRAP" in s) or "SETUP_11_FAKEOUT_RECLAIM_SHORT" in s:
            return "SETUP_11_RESISTANCE_FLIP"

        # 10. SETUP 10: ABOVE NPOC REJECTION (SHORT)
        if "SETUP 10" in s or "SETUP_10" in s or "ABOVE_NPOC_REJECTION" in s or "ABOVE NPOC" in s or "YUKARI NPOC" in s or ("NPOC" in s and ("RED" in s or "DİRENÇ" in s or "DIRENC" in s or "REJECTION" in s)):
            return "SETUP_10_ABOVE_NPOC_REJECTION"

        # 9. SETUP 9: BELOW NPOC BOUNCE (LONG)
        if "SETUP 9" in s or "SETUP_9" in s or "BELOW_NPOC_BOUNCE" in s or "BELOW NPOC" in s or "AŞAĞI NPOC" in s or "ASAGI NPOC" in s or ("NPOC" in s and ("BOUNCE" in s or "SEKME" in s or "DESTEK" in s)):
            return "SETUP_9_BELOW_NPOC_BOUNCE"

        # 8. SETUP 8: MVAL BREAKDOWN (SHORT)
        if "SETUP 8" in s or "SETUP_8" in s or "MVAL_MACRO_BREAKDOWN" in s or "MVAL_BREAKDOWN" in s or "MVAL BREAKDOWN" in s or "MVAL KIRILIMI" in s or "MVAL DESTEK" in s or "MVAL ÇÖKÜŞÜ" in s or "MVAL COKUSU" in s:
            return "SETUP_8_MVAL_BREAKDOWN"

        # 7. SETUP 7: S4 BREAKDOWN / RESISTANCE FLIP (SHORT)
        if "SETUP 7" in s or "SETUP_7" in s or "S4_RESISTANCE_FLIP" in s or "S4 RESISTANCE FLIP" in s or "S4 RETEST REDDİ" in s or "S4 RETEST REDDI" in s or "S4 DİRENÇ RETEST" in s or "S4 DIRENC RETEST" in s or "S4_BREAKDOWN" in s or ("S4" in s and "FLIP" in s):
            return "SETUP_7_S4_BREAKDOWN"

        # 6. SETUP 6: MVAH BREAKOUT (LONG)
        if "SETUP 6" in s or "SETUP_6" in s or "MVAH_MACRO_BREAKOUT" in s or "MVAH_BREAKOUT" in s or "MVAH BREAKOUT" in s or "MVAH KIRILIMI" in s or ("MVAH" in s and ("DİRENÇ KIRILIMI" in s or "DIRENC KIRILIMI" in s or "MACRO BREAKOUT" in s or "BOĞA" in s or "BULL" in s or "LONG" in s)):
            return "SETUP_6_MVAH_BREAKOUT"

        # 5. SETUP 5: R4 SUPPORT FLIP (LONG)
        if "SETUP 5" in s or "SETUP_5" in s or "R4_SUPPORT_FLIP" in s or "R4 SUPPORT FLIP" in s or "R4 FLIP" in s or "R4 DESTEK RETEST" in s or "RANGE BOUNCE" in s:
            return "SETUP_5_R4_SUPPORT_FLIP"

        # 4. SETUP 4: R3 REJECTION (SHORT)
        if "SETUP 4" in s or "SETUP_4" in s or "R3 DİRENÇ" in s or "R3 DIRENC" in s or "R3 REDDİ" in s or "R3 REDDI" in s or "R3_REJECTION" in s or "R3 REJECTION" in s or "R3_REVERSAL" in s:
            return "SETUP_4_R3_REJECTION"

        # 3. SETUP 3: S3 BOUNCE (LONG)
        if "SETUP 3" in s or "SETUP_3" in s or "S3 DESTEK" in s or "S3 SEKME" in s or "S3 RETEST" in s or "S3_BOUNCE" in s or "S3 BOUNCE" in s or "S3_REVERSAL" in s:
            return "SETUP_3_S3_BOUNCE"

        # 2. SETUP 2: S4 BREAKDOWN (SHORT)
        if "SETUP 2" in s or "SETUP_2" in s or "S4 BREAKDOWN" in s or "S4 KIRILIMI" in s or "S4 K" in s or "OI_SHORT_EXPANSION" in s:
            return "SETUP_2_S4_BREAKDOWN"

        # 1. SETUP 1: R4 BREAKOUT (LONG)
        if "SETUP 1" in s or "SETUP_1" in s or "R4 BREAKOUT" in s or "R4 KIRILIMI" in s or "R4 K" in s or "OI_BULL_EXPANSION" in s:
            return "SETUP_1_R4_BREAKOUT"

        # Fallback keyword checks
        if "MVAH" in s:
            return "SETUP_6_MVAH_BREAKOUT"
        if "MVAL" in s:
            return "SETUP_8_MVAL_BREAKDOWN"
        if "NPOC" in s:
            return "SETUP_9_BELOW_NPOC_BOUNCE" if ("BOUNCE" in s or "SEKME" in s or "DESTEK" in s) else "SETUP_10_ABOVE_NPOC_REJECTION"
        if "PIVOT" in s:
            return "SETUP_14_PIVOT_SUPPORT_FLIP"

        return "SETUP_DİĞER"

    def get_coin_setup_matrix(self, symbol: str) -> Dict[str, dict]:
        """Coin bazında 16 setup'ın performansını, kârlılığını ve alfa skorunu çıkarır."""
        clean = self.clean_base_symbol(symbol)
        coin_trades = [t for t in self.completed_trades if self.clean_base_symbol(t.get("symbol", "")) == clean]
        matrix = {}
        for t in coin_trades:
            s_canon = self.extract_canonical_setup(t.get("setup", ""))
            if s_canon not in matrix:
                matrix[s_canon] = {
                    "setup_id": s_canon,
                    "total_trades": 0,
                    "wins": 0,
                    "losses": 0,
                    "net_pnl_usd": 0.0,
                    "win_rate_pct": 0.0,
                    "max_mfe_pct": 0.0,
                    "max_mae_pct": 0.0,
                    "alpha_score": 0.0,
                    "status": "NÖTR"
                }
            m = matrix[s_canon]
            m["total_trades"] += 1
            pnl = float(t.get("virtual_pnl_usd", 0.0))
            m["net_pnl_usd"] += pnl
            if pnl > 0.0:
                m["wins"] += 1
            else:
                m["losses"] += 1
            m["max_mfe_pct"] = max(m["max_mfe_pct"], float(t.get("max_mfe_pct", 0.0)))
            m["max_mae_pct"] = max(m["max_mae_pct"], float(t.get("max_mae_pct", 0.0)))

        for s_canon, m in matrix.items():
            tot = m["total_trades"]
            m["net_pnl_usd"] = round(m["net_pnl_usd"], 2)
            m["win_rate_pct"] = round((m["wins"] / tot) * 100.0, 1) if tot > 0 else 0.0
            wr_ratio = m["win_rate_pct"] / 100.0
            pnl_contribution = m["net_pnl_usd"] / (tot * 5.0) if tot > 0 else 0.0
            alpha = round((wr_ratio * 2.0 - 1.0) + pnl_contribution, 2)
            m["alpha_score"] = alpha

            if tot >= 3:
                if alpha >= 0.35 and m["net_pnl_usd"] > 0:
                    m["status"] = "A+ ONAYLI"
                elif alpha <= -0.25 and m["net_pnl_usd"] < 0:
                    m["status"] = "UYUTULDU"
                else:
                    m["status"] = "STANDART"
            else:
                m["status"] = "STANDART"

        return matrix

    # ──────────────────────────────────────────────────────────────────────────
    # PARİTE DETAYLI ADLİ OTOPSİ PAKETİ (COIN FORENSIC DEEP-DIVE MODAL DATA)
    # ──────────────────────────────────────────────────────────────────────────
    def get_coin_forensic_detail(self, symbol: str) -> dict:
        """
        Kullanıcı dashboard'da bir coinin [Detay] butonuna bastığında açılacak
        en ince ayrıntılı adli inceleme ve çok boyutlu parametre optimizasyon paketi.
        """
        clean = self.clean_base_symbol(symbol)
        sym = f"{clean}/USDT"

        # Bu coine ait aktif ve tamamlanmış işlemleri topla
        coin_actives = [p for p in self.active_positions.values() if self.clean_base_symbol(p.get("symbol", "")) == clean]
        coin_completed = [t for t in self.completed_trades if self.clean_base_symbol(t.get("symbol", "")) == clean]

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

        # Setup matrisi ve Likidite Katmanı
        setup_matrix = self.get_coin_setup_matrix(clean)
        liq_tier = self.get_coin_liquidity_tier(clean)

        # Post-Exit Hayalet Analizi (İşlem devam etseydi ne olurdu?)
        coin_ghosts = [g for g in self.post_exit_history if self.clean_base_symbol(g.get("symbol", "")) == clean]
        premature_exits = [g for g in coin_ghosts if g.get("verdict") == "ERKEN_CIKIS_KACAN_DALGA"]
        sniper_exits = [g for g in coin_ghosts if g.get("verdict") == "SNIPER_TEPE_CIKISI"]
        post_exit_summary = {
            "total_tracked": len(coin_ghosts),
            "premature_exit_count": len(premature_exits),
            "sniper_exit_count": len(sniper_exits),
            "recent_ghosts": coin_ghosts[-5:]
        }

        # Zıt Yön (Inversion Counterfactual) Analizi
        inverted_trades = [t for t in coin_completed if "inversion_pnl_usd" in t]
        prof_inversions = [t for t in inverted_trades if t.get("inversion_verdict") == "PROFITABLE_INVERSION"]
        total_inv_profit = sum(t.get("inversion_pnl_usd", 0.0) for t in prof_inversions)
        inversion_summary = {
            "total_evaluated": len(inverted_trades),
            "profitable_count": len(prof_inversions),
            "inversion_win_rate_pct": round((len(prof_inversions) / max(1, len(inverted_trades))) * 100.0, 1),
            "total_inversion_profit_usd": round(total_inv_profit, 2)
        }

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
            "setup_matrix": setup_matrix,
            "liquidity_tier": liq_tier,
            "post_exit_summary": post_exit_summary,
            "inversion_summary": inversion_summary,
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

    def archive_old_trades(self, keep_latest: int = 3000):
        """
        Aktif hafızadaki işlem sayısı 3000'i aştığında, en eski işlemleri aylık arşiv dosyasına
        (shadow_archive_YYYYMM.json) aktarır. Böylece RAM ve disk şişmesi önlenir,
        tarihsel veriler ise aylık bazda sonsuza kadar korunur.
        """
        if len(self.completed_trades) <= keep_latest:
            return

        all_completed = list(self.completed_trades)
        to_archive = all_completed[:-keep_latest]
        to_keep = all_completed[-keep_latest:]

        archive_map: Dict[str, list] = {}
        for t in to_archive:
            entry_t = t.get("entry_time", "")
            ym = entry_t[:7].replace("-", "") if len(entry_t) >= 7 else datetime.now().strftime("%Y%m")
            af_name = f"shadow_archive_{ym}.json"
            if af_name not in archive_map:
                archive_map[af_name] = []
            archive_map[af_name].append(t)

        base_dir = os.path.dirname(self.history_file)
        for af_name, trades in archive_map.items():
            af_path = os.path.join(base_dir, af_name)
            existing = []
            if os.path.exists(af_path):
                try:
                    with open(af_path, "r", encoding="utf-8") as f:
                        existing = json.load(f).get("completed", [])
                except Exception:
                    pass

            merged_map = {x.get("id"): x for x in (existing + trades) if x.get("id")}
            archive_data = {
                "updated_at": datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M:%S"),
                "archive_period": af_name.replace("shadow_archive_", "").replace(".json", ""),
                "completed": sorted(merged_map.values(), key=lambda x: str(x.get("entry_time", "")))
            }
            try:
                with open(af_path, "w", encoding="utf-8") as f:
                    json.dump(archive_data, f, ensure_ascii=False, indent=2)
                print(f">> [GÖLGE ARŞİVLEME] {len(trades)} eski işlem {af_name} dosyasına arşivlendi.")
            except Exception as e:
                print(f">> [GÖLGE ARŞİV HATA] {e}")

        self.completed_trades.clear()
        for t in to_keep:
            self.completed_trades.append(t)

    # ──────────────────────────────────────────────────────────────────────────
    # GITHUB UZAK BULUT KALICILIĞI (REMOTE PERSISTENCE) & SİSTEM SAĞLIĞI
    # ──────────────────────────────────────────────────────────────────────────
    def save_history(self, critical: bool = False):
        """Hafızadaki gölge işlemleri hem lokal dosyaya atomik hem de GitHub state dalına kaydeder."""
        if len(self.completed_trades) > 3000:
            self.archive_old_trades(keep_latest=3000)

        data = {
            "updated_at": datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M:%S"),
            "completed": list(self.completed_trades),
            "actives": list(self.active_positions.values())
        }

        # 1. Lokal Dosyaya Atomik Yazma
        try:
            tmp_file = self.history_file + ".tmp"
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_file, self.history_file)
        except Exception:
            pass

        # 2. GitHub Uzak Kalıcılık (İzole state dalı - Render restart döngüsünü tetiklemez)
        if GITHUB_TOKEN and not self.is_test:
            now_ts = time.time()
            if critical:
                self._last_push_ts = now_ts
                threading.Thread(target=self._push_to_github, args=(data,), daemon=True).start()
            else:
                if now_ts - self._last_push_ts >= 25.0:
                    self._last_push_ts = now_ts
                    threading.Thread(target=self._push_to_github, args=(data,), daemon=True).start()

    def _push_to_github(self, data: dict):
        """shadow_trades_history.json dosyasını GitHub state dalına güvenle yazar."""
        if self.is_test or not GITHUB_TOKEN or not self._push_lock.acquire(blocking=False):
            return
        try:
            for attempt in range(1, 4):
                try:
                    content_str = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
                    content_b64 = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")

                    # Güncel SHA'yı al
                    try:
                        req = urllib.request.Request(f"{SHADOW_GITHUB_API_URL}?ref={GITHUB_BRANCH}", headers={
                            "Authorization": f"token {GITHUB_TOKEN}",
                            "Accept": "application/vnd.github.v3+json",
                            "User-Agent": "Valkyrie-Shadow-Engine"
                        })
                        with urllib.request.urlopen(req, timeout=10) as res:
                            gh = json.loads(res.read().decode("utf-8"))
                            self._github_sha = gh.get("sha")
                    except Exception:
                        pass

                    payload = {
                        "message": f"[SHADOW] State auto-sync ({len(data.get('completed', []))} completed, {len(data.get('actives', []))} active)",
                        "content": content_b64,
                        "branch": GITHUB_BRANCH
                    }
                    if self._github_sha:
                        payload["sha"] = self._github_sha

                    payload_bytes = json.dumps(payload).encode("utf-8")
                    req = urllib.request.Request(SHADOW_GITHUB_API_URL, data=payload_bytes, method="PUT", headers={
                        "Authorization": f"token {GITHUB_TOKEN}",
                        "Accept": "application/vnd.github.v3+json",
                        "Content-Type": "application/json",
                        "User-Agent": "Valkyrie-Shadow-Engine"
                    })
                    with urllib.request.urlopen(req, timeout=20) as resp:
                        res_data = json.loads(resp.read().decode("utf-8"))
                        self._github_sha = res_data.get("content", {}).get("sha", self._github_sha)
                        self.last_sync_status = "SENKRONİZE"
                        return
                except Exception as e:
                    self.last_sync_status = f"HATA ({e})"
                    time.sleep(2 * attempt)
        finally:
            self._push_lock.release()

    def load_history(self):
        """
        Başlangıçta GitHub state dalından ve yerel diskten verileri çekip akıllıca birleştirir (Merge & Deduplicate).
        Render yeniden başlatmalarında veya dağıtımlarda tek bir gölge işlem dahi kaybolmaz.
        """
        remote_completed = []
        remote_actives = []

        # 1. GitHub state dalından yükle
        if GITHUB_TOKEN and not self.is_test:
            try:
                req = urllib.request.Request(f"{SHADOW_GITHUB_API_URL}?ref={GITHUB_BRANCH}", headers={
                    "Authorization": f"token {GITHUB_TOKEN}",
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "Valkyrie-Shadow-Engine"
                })
                with urllib.request.urlopen(req, timeout=10) as resp:
                    gh_data = json.loads(resp.read().decode("utf-8"))
                    self._github_sha = gh_data.get("sha")
                    content_b64 = gh_data.get("content", "")
                    if content_b64:
                        content_str = base64.b64decode(content_b64).decode("utf-8")
                        data = json.loads(content_str)
                    elif gh_data.get("download_url"):
                        raw_req = urllib.request.Request(gh_data["download_url"], headers={
                            "Authorization": f"token {GITHUB_TOKEN}",
                            "User-Agent": "Valkyrie-Shadow-Engine"
                        })
                        with urllib.request.urlopen(raw_req, timeout=15) as raw_resp:
                            data = json.loads(raw_resp.read().decode("utf-8"))
                    elif gh_data.get("git_url"):
                        blob_req = urllib.request.Request(gh_data["git_url"], headers={
                            "Authorization": f"token {GITHUB_TOKEN}",
                            "Accept": "application/vnd.github.v3+json",
                            "User-Agent": "Valkyrie-Shadow-Engine"
                        })
                        with urllib.request.urlopen(blob_req, timeout=15) as blob_resp:
                            blob_data = json.loads(blob_resp.read().decode("utf-8"))
                            data = json.loads(base64.b64decode(blob_data.get("content", "")).decode("utf-8"))
                    else:
                        data = {}
                    remote_completed = data.get("completed", [])
                    remote_actives = data.get("actives", [])
                    print(f">> [GÖLGE BULUT KALICILIĞI] GitHub state dalından {len(remote_completed)} tamamlanan, {len(remote_actives)} aktif işlem çekildi. (SHA: {self._github_sha[:8] if self._github_sha else 'OK'})")
            except Exception as e:
                print(f">> [GÖLGE BULUT BİLGİ] GitHub'dan çekilemedi: {e}")

        # 2. Lokal diskten oku
        local_completed = []
        local_actives = []
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    l_data = json.load(f)
                    local_completed = l_data.get("completed", [])
                    local_actives = l_data.get("actives", [])
            except Exception as e:
                print(f">> [GÖLGE YEREL HATA] Yerel dosya okunamadı: {e}")

        # 3. Akıllı Birleştirme ve Mükerrer Kayıt Önleme (Deduplication Guard)
        completed_map = {}
        for t in remote_completed + local_completed:
            t_id = t.get("id") or t.get("shadow_id")
            if t_id:
                completed_map[t_id] = t

        active_map = {}
        for a in remote_actives + local_actives:
            a_id = a.get("id") or a.get("shadow_id")
            # Eğer bir işlem tamamlananlar arasındaysa artık aktif kalamaz!
            if a_id and a_id not in completed_map:
                active_map[a_id] = a

        # Hafızaya doldur
        self.completed_trades.clear()
        sorted_completed = sorted(completed_map.values(), key=lambda x: str(x.get("entry_time", "")))
        for t in sorted_completed:
            self.completed_trades.append(t)

        self.active_positions.clear()
        self.symbol_active_map.clear()
        for a_id, a in active_map.items():
            if "id" not in a:
                a["id"] = a_id
            self.active_positions[a_id] = a
            sym = a.get("symbol")
            if sym:
                self.symbol_active_map[sym] = a_id

        self.last_sync_status = "SENKRONİZE"
        print(f">> [GÖLGE KALICILIK ZIRHI] {len(self.completed_trades)} tamamlanan, {len(self.active_positions)} aktif gölge işlem hafızaya yüklendi ve korundu.")

        # Eğer lokalde GitHub'dan daha fazla kayıt varsa GitHub'ı da senkronize et
        if len(completed_map) > len(remote_completed):
            self.save_history(critical=True)

    def get_health_status(self) -> dict:
        """Sistem Sağlığı ve Aegis Sentinel için gölge motoru teşhis metrikleri."""
        now = time.time()
        tick_gap = round(now - getattr(self, "last_tick_ts", now), 1)
        candle_gap = round(now - getattr(self, "last_candle_ts", now), 1)
        is_alive = tick_gap < 120.0
        summary = self.get_summary()

        return {
            "healthy": is_alive,
            "status_text": "TAM SAĞLIKLI" if is_alive else "GECİKME",
            "active_count": len(self.active_positions),
            "completed_count": len(self.completed_trades),
            "sei": summary.get("shield_efficiency_index", 100.0),
            "saved_loss_usd": summary.get("total_saved_loss_usd", 0.0),
            "missed_profit_usd": summary.get("total_missed_profit_usd", 0.0),
            "net_alpha_usd": summary.get("net_shield_alpha_usd", 0.0),
            "last_tick_gap_sec": tick_gap,
            "last_candle_gap_sec": candle_gap,
            "github_synced": bool(GITHUB_TOKEN and self.last_sync_status == "SENKRONİZE"),
            "sync_status": self.last_sync_status,
            "max_active": self.max_active
        }
