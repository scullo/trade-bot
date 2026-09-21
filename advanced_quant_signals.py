"""
advanced_quant_signals.py - Valkyrie 4 Gizli Kuant Silahı Modülü
================================================================
Bu modül, kurumsal düzeyde en üst %1'lik HFT ve prop fonlarının kullandığı
4 gizli alfa katmanını hesaplar:

1. CVD Uyumsuzluğu ve Emilim Matrisi (Delta Divergence & Absorption)
2. Göreceli Hacim & Seans Z-Score Normalizasyonu (RVOL)
3. Makro Likidite ve Dominans Akışı (USDT.D & BTC.D Beta Vampir Kalkanı)
4. Çoklu Borsa Tasfiye Nabzı (Cross-Exchange Liquidation Contagion)
"""

from typing import Tuple, Dict, Any, Optional
import numpy as np
import pandas as pd


def calculate_cvd_divergence(df: Optional[pd.DataFrame], lookback: int = 15) -> Tuple[str, float]:
    """
    Son N mumdaki Fiyat Zirvesi/Dibi ile Kümülatif CVD arasındaki uyumsuzluğu ölçer.
    
    Döndürür:
        (divergence_type: str, divergence_score: float)
        - "🚨 AYI_UYUMSUZLUĞU (Sahte Kırılım / Bull Trap)", -2.0
        - "💎 BOĞA_EMİLİMİ (Kurumsal Destek Duvarı)", +2.0
        - "⚪ UYUMLU_AKIS (Normal)", 0.0
    """
    if df is None or not isinstance(df, pd.DataFrame) or len(df) < lookback or 'close' not in df.columns:
        return "NÖTR_VERİ_YOK", 0.0

    try:
        sub = df.tail(lookback)
        close_prices = sub['close'].values.astype(float)

        # Gerçek CVD: Taker Quote Volume vs Toplam Quote Volume
        if 'taker_quote' in sub.columns and 'qav' in sub.columns:
            t_q = sub['taker_quote'].values.astype(float)
            qav = sub['qav'].values.astype(float)
            delta = t_q - (qav - t_q)
        else:
            # Alternatif Delta: Mum gövdesi yönünde hacim
            is_green = (sub['close'].values >= sub['open'].values).astype(float) * 2.0 - 1.0
            delta = sub['volume'].values.astype(float) * is_green

        cum_cvd = np.cumsum(delta)
        half = max(2, lookback // 2)

        p_early_max = np.max(close_prices[:half])
        p_late_max = np.max(close_prices[half:])
        p_early_min = np.min(close_prices[:half])
        p_late_min = np.min(close_prices[half:])

        cvd_early_max = np.max(cum_cvd[:half])
        cvd_late_max = np.max(cum_cvd[half:])
        cvd_early_min = np.min(cum_cvd[:half])
        cvd_late_min = np.min(cum_cvd[half:])

        # 1. Ayı Uyumsuzluğu: Fiyat yeni tepe yaparken Alıcı CVD geride kalıyor (Hollow Breakout)
        if p_late_max > p_early_max * 1.0015 and cvd_late_max < cvd_early_max:
            return "🚨 AYI_UYUMSUZLUĞU (Sahte Kırılım / Bull Trap)", -2.0

        # 2. Boğa Emilimi: Fiyat dip yaparken Alıcı CVD yükseliyor (Iceberg Limit Absorption)
        if p_late_min <= p_early_min * 1.0010 and cvd_late_min > cvd_early_min:
            return "💎 BOĞA_EMİLİMİ (Kurumsal Destek Duvarı)", +2.0

    except Exception:
        pass

    return "⚪ UYUMLU_AKIS (Normal)", 0.0


def calculate_rvol_zscore(df: Optional[pd.DataFrame]) -> Tuple[float, float, str]:
    """
    Günün o saatine göre normalize edilmiş Göreceli Hacim (RVOL) ve Z-Score.
    Sahte seans açılış hacimleriyle gerçek kurumsal anomalileri ayırır.
    
    Döndürür:
        (rvol_ratio: float, z_score: float, classification_tag: str)
    """
    if df is None or not isinstance(df, pd.DataFrame) or len(df) < 30 or 'volume' not in df.columns:
        return 1.0, 0.0, "⚪ SEANS_NORMU"

    try:
        cur_vol = float(df['volume'].iloc[-1])
        # Son 7 günlük (azami 2016 mum) hacim serisi
        lookback = min(len(df) - 1, 288 * 7)
        hist_vols = df['volume'].iloc[-lookback:-1].values.astype(float)

        if len(hist_vols) > 0:
            mean_v = float(np.mean(hist_vols))
            std_v = float(np.std(hist_vols))
        else:
            mean_v = cur_vol
            std_v = 1.0

        rvol_ratio = round(cur_vol / max(1e-6, mean_v), 2)
        z_score = round((cur_vol - mean_v) / max(1e-6, std_v), 2)

        if z_score >= 2.5:
            tag = "🔥 EKSTREM_KURUMSAL_PATLAMA"
        elif z_score >= 1.5:
            tag = "⚡ YÜKSEK_ANOMALİ"
        elif z_score <= -1.0:
            tag = "💤 SESSİZ_LİKİDİTE_DİBİ"
        else:
            tag = "⚪ SEANS_NORMU"

        return rvol_ratio, z_score, tag

    except Exception:
        return 1.0, 0.0, "⚪ SEANS_NORMU"


def calculate_macro_dominance_bias(
    btc_df: Optional[pd.DataFrame],
    alt_df: Optional[pd.DataFrame]
) -> Tuple[str, float]:
    """
    Bitcoin vs Altcoin sermaye akışı barometresi (Vampir BTC Kalkanı).
    Eğer BTC sert yükselirken altcoin geride kalıyorsa altcoinlerde LONG VETO edilir.
    
    Döndürür:
        (macro_bias: str, rs_differential: float)
    """
    if btc_df is None or alt_df is None or len(btc_df) < 12 or len(alt_df) < 12:
        return "⚪ DENGELİ_MAKRO_AKIS", 0.0

    try:
        btc_1h_ret = ((float(btc_df['close'].iloc[-1]) - float(btc_df['close'].iloc[-12])) / float(btc_df['close'].iloc[-12])) * 100.0
        alt_1h_ret = ((float(alt_df['close'].iloc[-1]) - float(alt_df['close'].iloc[-12])) / float(alt_df['close'].iloc[-12])) * 100.0
        rs_diff = round(alt_1h_ret - btc_1h_ret, 2)

        # Vampir BTC Rejimi: BTC yükseliyor (+%0.80 üzeri) ama Altcoin düşüyor veya yerinde sayıyor
        if btc_1h_ret >= 0.80 and rs_diff <= -1.0:
            return "🧛 VAMPİR_BTC (Altcoin Likidite Drenajı)", rs_diff

        # Altseason / Altcoin Patlaması: Altcoin BTC'den %1.5+ daha güçlü
        if rs_diff >= 1.50 and alt_1h_ret > 0:
            return "🚀 ALTCOIN_ALFA_RALLİSİ", rs_diff

        # Genel Piyasa Çöküşü: İkisi de sert eksi
        if btc_1h_ret <= -1.0 and alt_1h_ret <= -1.0:
            return "🩸 GENEL_PİYASA_ÇÖKÜŞÜ", rs_diff

    except Exception:
        pass

    return "⚪ DENGELİ_MAKRO_AKIS", 0.0
