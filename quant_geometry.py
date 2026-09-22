"""
quant_geometry.py - Valkyrie Quant Grand Engine: Geometrik R & Ön-Onay Kapısı
=============================================================================
Bu modül, işleme girilmeden önce pozisyonun matematiksel R geometrisini (Ödül / Risk),
önündeki hava koridorunu (Air Pocket / Runway) ve makro rejim-yön uyumunu denetler.

88 işlemlik kurumsal denetimde kanıtlanan bulgu:
- R < 1.80x olan 25 işlem: -$457.75 Net Zarar (%20 Win Rate)
- R >= 1.80x olan 59 işlem: +$286.23 Net Kâr (%71.2 Win Rate)

Bu modül, sistemin sermaye erimesini engelleyen "Matematiksel Ön-Onay Geçidi"dir.
"""

from typing import Tuple, Dict, Any, Optional
import math

try:
    from config import (
        ENABLE_GEOMETRIC_R_GATE,
        MIN_PLANNED_R_RATIO,
        ENABLE_RUNWAY_CLEARANCE,
        MIN_RUNWAY_OBSTACLE_R,
        ENABLE_REGIME_DIRECTIONAL_GATE,
        BULL_SHORT_MIN_CVD_PCT,
        ENABLE_MAX_STOP_DIST_GATE,
        MAX_ENTRY_STOP_DIST_PCT,
        ENABLE_MEME_DEFENSIVE_MODE,
        MEME_SYMBOLS,
        MEME_MAX_STOP_DIST_PCT,
    )
except ImportError:
    # Güvenli varsayılan değerler (Fail-Safe Fallback)
    ENABLE_GEOMETRIC_R_GATE = True
    MIN_PLANNED_R_RATIO = 1.80
    ENABLE_RUNWAY_CLEARANCE = True
    MIN_RUNWAY_OBSTACLE_R = 1.10
    ENABLE_REGIME_DIRECTIONAL_GATE = True
    BULL_SHORT_MIN_CVD_PCT = 52.0
    ENABLE_MAX_STOP_DIST_GATE = True
    MAX_ENTRY_STOP_DIST_PCT = 0.80
    ENABLE_MEME_DEFENSIVE_MODE = True
    MEME_SYMBOLS = ["WIF/USDT", "PEPE/USDT", "TURBO/USDT", "FLOKI/USDT", "BONK/USDT", "COTI/USDT", "ONG/USDT"]
    MEME_MAX_STOP_DIST_PCT = 0.70


def calculate_geometric_r(entry_p: float, stop_p: float, tp1_p: float) -> float:
    """
    Hedef mesafesinin (TP1) risk mesafesine (Stop) oranını hesaplar.
    Formül: R = |TP1 - Entry| / |Stop - Entry|
    """
    if not entry_p or entry_p <= 0 or not stop_p or stop_p <= 0 or not tp1_p or tp1_p <= 0:
        return 0.0

    risk_dist = abs(entry_p - stop_p)
    reward_dist = abs(tp1_p - entry_p)

    if risk_dist <= 1e-9:
        return 0.0

    return round(reward_dist / risk_dist, 4)


def check_runway_clearance(
    entry_p: float,
    stop_p: float,
    target_p: float,
    levels: Optional[Dict[str, Any]],
    side: str,
    min_obstacle_r: float = 1.10
) -> Tuple[bool, str, Optional[str], float]:
    """
    Giriş ile hedef (TP1) arasında fiyatın koşusunu engelleyecek sert bir yapısal
    direnç/destek olup olmadığını (Air Pocket açıklığını) kontrol eder.
    
    Kural: Hedefe giden koridorda ilk sert engel, en az (min_obstacle_r * Stop_Mesafesi)
    kadar uzakta olmalıdır. Aksi halde işlem erken tıkanır.
    """
    if not levels or not isinstance(levels, dict) or entry_p <= 0 or stop_p <= 0:
        return True, "Seviye verisi yok, koridor kontrolü pas geçildi.", None, 0.0

    risk_dist = abs(entry_p - stop_p)
    min_free_dist = risk_dist * min_obstacle_r

    # Taranacak kritik yapısal seviyeler
    level_keys = [
        ('mVAH', levels.get('mvah')),
        ('mVAL', levels.get('mval')),
        ('mPOC', levels.get('mpoc')),
        ('Tepe AVWAP', levels.get('top_avwap')),
        ('Dip AVWAP', levels.get('bottom_avwap')),
        ('R4', levels.get('r4')),
        ('R3', levels.get('r3')),
        ('S3', levels.get('s3')),
        ('S4', levels.get('s4')),
        ('Pivot P', levels.get('pivot')),
        ('Yukarı nPOC', levels.get('up_npoc')),
        ('Aşağı nPOC', levels.get('down_npoc')),
    ]

    tolerance = 0.0015  # %0.15 giriş yakınlığı toleransı (giriş seviyesinin kendisini engel saymamak için)

    if side == "LONG":
        for name, lvl in level_keys:
            if lvl and isinstance(lvl, (int, float)) and lvl > entry_p * (1.0 + tolerance):
                dist_to_lvl = lvl - entry_p
                eff_min_r = 1.00 if name == 'mPOC' else min_obstacle_r
                min_free_dist = risk_dist * eff_min_r
                # Eğer seviye hedefin önündeyse ve min_free_dist'ten daha yakınsa koridor tıkalıdır
                if dist_to_lvl < (target_p - entry_p) and dist_to_lvl < min_free_dist:
                    obs_r = dist_to_lvl / risk_dist if risk_dist > 0 else 0
                    return False, f"Hava Koridoru Tıkalı: Önünde {name} (${lvl:.4f}) engeli var ({obs_r:.2f}R < {eff_min_r:.2f}R)", name, float(lvl)

    elif side == "SHORT":
        for name, lvl in level_keys:
            if lvl and isinstance(lvl, (int, float)) and lvl < entry_p * (1.0 - tolerance):
                dist_to_lvl = entry_p - lvl
                eff_min_r = 1.00 if name == 'mPOC' else min_obstacle_r
                min_free_dist = risk_dist * eff_min_r
                # Eğer seviye hedefin önündeyse ve min_free_dist'ten daha yakınsa koridor tıkalıdır
                if dist_to_lvl < (entry_p - target_p) and dist_to_lvl < min_free_dist:
                    obs_r = dist_to_lvl / risk_dist if risk_dist > 0 else 0
                    return False, f"Hava Koridoru Tıkalı: Önünde {name} (${lvl:.4f}) engeli var ({obs_r:.2f}R < {eff_min_r:.2f}R)", name, float(lvl)

    return True, "Hava koridoru açık.", None, 0.0


def validate_pre_trade_clearance(
    symbol: str,
    side: str,
    entry_p: float,
    stop_p: float,
    tp1_p: float,
    tp2_p: Optional[float] = None,
    levels: Optional[Dict[str, Any]] = None,
    cvd_taker_pct: Optional[float] = None,
    market_regime: Optional[str] = None,
    hurst_h: Optional[float] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    İşleme giriş anında tüm kurumsal kuant şartlarını tek noktada denetleyen Baş Kapı (Master Gate).
    
    Döndürür:
        (is_approved: bool, reason: str, metrics: dict)
    """
    planned_r = calculate_geometric_r(entry_p, stop_p, tp1_p)
    metrics = {
        "symbol": symbol,
        "side": side,
        "entry_p": entry_p,
        "stop_p": stop_p,
        "tp1_p": tp1_p,
        "planned_r": planned_r,
        "market_regime": market_regime or "UNKNOWN",
        "cvd_taker_pct": cvd_taker_pct or 50.0,
    }

    # ── 0. STOP MESAFESİ SNIPER KONTROLÜ (HARD GATE) ─────────────────────────
    # Stop mesafesi %0.80'den (Meme paritelerde %0.70'den) geniş olan işlemler yapısal seviye dibi değildir.
    # Bu işlemler tüm piyasa rejimlerinde (yatay, boğa, asya) kasanın erimesine yol açtığı için derhal elenir.
    if ENABLE_MAX_STOP_DIST_GATE:
        if entry_p > 0 and stop_p > 0:
            stop_dist_pct = abs(entry_p - stop_p) / entry_p * 100.0
            is_meme = ENABLE_MEME_DEFENSIVE_MODE and (
                symbol in MEME_SYMBOLS or any(m in symbol for m in ["WIF", "PEPE", "TURBO", "FLOKI", "BONK", "COTI", "ONG", "POPCAT", "NEIRO"])
            )
            max_allowed_stop = float(MEME_MAX_STOP_DIST_PCT if is_meme else MAX_ENTRY_STOP_DIST_PCT)
            metrics["stop_dist_pct"] = round(stop_dist_pct, 3)
            metrics["max_allowed_stop_pct"] = max_allowed_stop
            
            if stop_dist_pct > max_allowed_stop:
                type_str = "Meme Parite Kalkanı" if is_meme else "Sniper Stop Kalkanı"
                rej_msg = (
                    f"🎯 {type_str}: Stop mesafesi (%{stop_dist_pct:.2f}) azami "
                    f"sınırın (%{max_allowed_stop:.2f}) üstünde. Sadece dar stoplu "
                    f"seviye dibi sniper kurulumlara izin verilir."
                )
                return False, rej_msg, metrics

    # ── 1. GEOMETRİK R KONTROLÜ (HARD GATE) ──────────────────────────────────
    if ENABLE_GEOMETRIC_R_GATE:
        min_r = float(MIN_PLANNED_R_RATIO)
        if planned_r < min_r:
            rej_msg = (
                f"🛡️ Geometrik R Kalkanı: Planlanan R ({planned_r:.2f}x) asgari hedef "
                f"oranın ({min_r:.2f}x) altında. Sıkışık geometri elendi."
            )
            return False, rej_msg, metrics

    # ── 2. HAVA KORİDORU / AIR POCKET AÇIKLIK TESTİ ───────────────────────────
    if ENABLE_RUNWAY_CLEARANCE and levels:
        min_obs_r = float(MIN_RUNWAY_OBSTACLE_R)
        clear, runway_msg, obs_name, obs_lvl = check_runway_clearance(
            entry_p=entry_p,
            stop_p=stop_p,
            target_p=tp1_p,
            levels=levels,
            side=side,
            min_obstacle_r=min_obs_r
        )
        metrics["runway_clear"] = clear
        metrics["runway_obstacle"] = obs_name
        metrics["runway_obstacle_lvl"] = obs_lvl
        if not clear:
            rej_msg = f"🛡️ {runway_msg}"
            return False, rej_msg, metrics

    # ── 3. MAKRO BOĞA REJİMİ COUNTER-TREND SHORT KALKANI ─────────────────────
    if ENABLE_REGIME_DIRECTIONAL_GATE and side == "SHORT" and market_regime:
        regime_upper = str(market_regime).upper()
        is_bull_regime = ("GÜÇLÜ BOĞA" in regime_upper) or ("ILIMLI BOĞA" in regime_upper) or ("BULL" in regime_upper)
        
        if is_bull_regime:
            cvd_val = float(cvd_taker_pct or 50.0)
            min_short_cvd = float(BULL_SHORT_MIN_CVD_PCT)
            
            # Boğa piyasasında Taker Alıcı oranı %50'nin üzerindeyse, satıcı üstünlüğü yok demektir.
            # Short açabilmek için satıcı CVD üstünlüğü (yani alıcı CVD'nin düşük olması: CVD <= 100 - min_short_cvd)
            # veya mikro akışta güçlü teyit aranır.
            # Not: Eğer cvd_taker_pct Alıcı oranını ifade ediyorsa (Örn: %52 Alıcı), satıcı oranı %48'dir.
            # Satıcı akışının üstün olması için Taker Alıcı CVD <= (100 - min_short_cvd) veya doğrudan satıcı CVD >= min_short_cvd gerekir.
            buyer_cvd_pct = cvd_val if cvd_val <= 100.0 else cvd_val / 100.0
            
            # Eğer piyasada hala alıcı baskısı yüksekse (>%48 Alıcı), boğada short ezilir:
            if buyer_cvd_pct > (100.0 - min_short_cvd):
                rej_msg = (
                    f"🛡️ Boğa Rejimi Akıntı Kalkanı: Piyasa {market_regime} iken "
                    f"alıcı taker akışı (%{buyer_cvd_pct:.1f}) baskın. "
                    f"Satıcı CVD teyitsiz counter-trend SHORT engellendi."
                )
                return False, rej_msg, metrics

    return True, "OK", metrics
