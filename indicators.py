import numpy as np
import pandas as pd

def calculate_camarilla_pivots(high: float, low: float, close: float) -> dict:
    high, low, close = float(high), float(low), float(close)
    range_hl = high - low
    if range_hl == 0:
        range_hl = 0.0001
        
    p = float((high + low + close) / 3.0)
    r5 = float((high / low) * close if low > 0 else close * 1.05)
    r4 = float(close + range_hl * 1.1 / 2.0)
    r3 = float(close + range_hl * 1.1 / 4.0)
    
    s3 = float(close - range_hl * 1.1 / 4.0)
    s4 = float(close - range_hl * 1.1 / 2.0)
    s5 = float(close - (r5 - close))
    
    return {
        "P": p,
        "R3": r3, "R4": r4, "R5": r5,
        "S3": s3, "S4": s4, "S5": s5
    }

def calculate_anchored_vwap(df_candles: pd.DataFrame, anchor_idx: int) -> float:
    if df_candles.empty or anchor_idx >= len(df_candles) or anchor_idx < 0:
        return 0.0
        
    sub_df = df_candles.iloc[anchor_idx:].copy()
    hlc3 = (sub_df['high'] + sub_df['low'] + sub_df['close']) / 3.0
    tp_vol = hlc3 * sub_df['volume']
    
    cum_tp_vol = tp_vol.cumsum()
    cum_vol = sub_df['volume'].cumsum()
    
    valid_vol = cum_vol.iloc[-1]
    if valid_vol > 0:
        return float(cum_tp_vol.iloc[-1] / valid_vol)
    return float(hlc3.iloc[-1])

def calculate_anchored_vwap_series(df_candles: pd.DataFrame, anchor_idx: int) -> list:
    """Returns list of dicts: [{'time': int, 'value': float}] for Lightweight Charts plotting."""
    if df_candles.empty or anchor_idx >= len(df_candles) or anchor_idx < 0:
        return []
    sub_df = df_candles.iloc[anchor_idx:].copy()
    hlc3 = (sub_df['high'] + sub_df['low'] + sub_df['close']) / 3.0
    tp_vol = hlc3 * sub_df['volume']
    cum_tp_vol = tp_vol.cumsum()
    cum_vol = sub_df['volume'].cumsum()
    
    points = []
    for i in range(len(sub_df)):
        v = cum_vol.iloc[i]
        val = (cum_tp_vol.iloc[i] / v) if v > 0 else hlc3.iloc[i]
        ts = int(sub_df['timestamp'].iloc[i] / 1000)
        points.append({"time": ts, "value": round(float(val), 6)})
    return points

def calculate_volume_profile(df_candles: pd.DataFrame, num_rows: int = 24, value_area_pct: float = 0.68) -> dict:
    if df_candles.empty:
        return {"POC": 0.0, "VAH": 0.0, "VAL": 0.0}
        
    minP = df_candles['low'].min()
    maxP = df_candles['high'].max()
    
    if maxP <= minP:
        return {"POC": minP, "VAH": minP, "VAL": minP}
        
    step = (maxP - minP) / num_rows
    total_vols = np.zeros(num_rows)
    
    for _, row in df_candles.iterrows():
        b_low = row['low']
        b_high = row['high']
        b_vol = row['volume']
        
        low_idx = int(np.floor((b_low - minP) / step))
        high_idx = int(np.floor((b_high - minP) / step))
        
        low_idx = max(0, min(num_rows - 1, low_idx))
        high_idx = max(0, min(num_rows - 1, high_idx))
        
        span = high_idx - low_idx + 1
        vol_per_bucket = b_vol / span if span > 0 else b_vol
        
        for k in range(low_idx, high_idx + 1):
            total_vols[k] += vol_per_bucket

    # POC
    poc_idx = np.argmax(total_vols)
    poc_price = minP + (poc_idx + 0.5) * step
    
    # Value Area
    grand_total = np.sum(total_vols)
    target_va_vol = grand_total * value_area_pct
    va_accum = total_vols[poc_idx]
    up_idx = poc_idx
    dn_idx = poc_idx
    
    for _ in range(num_rows):
        if va_accum >= target_va_vol or (up_idx >= num_rows - 1 and dn_idx <= 0):
            break
            
        next_up_vol = total_vols[up_idx + 1] if up_idx < num_rows - 1 else 0.0
        next_dn_vol = total_vols[dn_idx - 1] if dn_idx > 0 else 0.0
        
        if next_up_vol >= next_dn_vol and up_idx < num_rows - 1:
            up_idx += 1
            va_accum += next_up_vol
        elif dn_idx > 0:
            dn_idx -= 1
            va_accum += next_dn_vol
        elif up_idx < num_rows - 1:
            up_idx += 1
            va_accum += next_up_vol
        else:
            break
            
    val_price = minP + dn_idx * step
    vah_price = minP + (up_idx + 1) * step
    
    return {
        "POC": float(poc_price),
        "VAH": float(vah_price),
        "VAL": float(val_price)
    }

def get_tradingview_naked_lines(df_5m: pd.DataFrame, current_price: float) -> dict:
    """
    TradingView Hacim Profili (Volume Profile) & Naked Lines:
    1. Multi-Session (12h/24h) test edilmemis (unmitigated) POC'leri tespit eder.
    2. Fiyatın ustundeki ve altindaki en yuksek hacim dugumlerini (HVN / Naked POC) ve
       Deger Alani uclarini (Naked VAH / Naked VAL) hesaplar.
    """
    if df_5m.empty or len(df_5m) < 10:
        return {"above_npoc": 0.0, "below_npoc": 0.0, "above_nvah": 0.0, "below_nvah": 0.0, "above_nval": 0.0, "below_nval": 0.0}

    df = df_5m.copy()
    min_p = float(df['low'].min())
    max_p = float(df['high'].max())
    
    if max_p <= min_p:
        return {"above_npoc": 0.0, "below_npoc": 0.0, "above_nvah": 0.0, "below_nvah": 0.0, "above_nval": 0.0, "below_nval": 0.0}

    # 1. Multi-Session test edilmemis (unmitigated) POC tespiti
    chunk_size = 144
    unmitigated_pocs = []
    total_candles = len(df)
    
    for start_i in range(0, max(1, total_candles - chunk_size), chunk_size):
        end_i = min(total_candles, start_i + chunk_size)
        chunk = df.iloc[start_i:end_i]
        if len(chunk) < 20:
            continue
        
        c_min = chunk['low'].min()
        c_max = chunk['high'].max()
        c_bins = 30
        c_step = (c_max - c_min) / c_bins if c_max > c_min else 1.0
        c_vols = np.zeros(c_bins)
        
        for _, r in chunk.iterrows():
            idx = max(0, min(c_bins - 1, int((r['close'] - c_min) / c_step)))
            c_vols[idx] += r['volume']
            
        c_poc_idx = np.argmax(c_vols)
        c_poc = c_min + (c_poc_idx + 0.5) * c_step
        
        if end_i < total_candles:
            future = df.iloc[end_i:]
            if not ((future['low'] <= c_poc) & (future['high'] >= c_poc)).any():
                unmitigated_pocs.append(c_poc)
        else:
            unmitigated_pocs.append(c_poc)

    # 2. Genel Hacim Profili ve HVN Düğümleri
    num_bins = 50
    step = (max_p - min_p) / num_bins
    bin_vols = np.zeros(num_bins)
    
    for _, r in df.iterrows():
        idx_s = max(0, min(num_bins - 1, int((r['low'] - min_p) / step)))
        idx_e = max(0, min(num_bins - 1, int((r['high'] - min_p) / step)))
        cnt = max(1, idx_e - idx_s + 1)
        for b in range(idx_s, idx_e + 1):
            bin_vols[b] += r['volume'] / cnt
            
    bin_centers = np.array([min_p + (b + 0.5) * step for b in range(num_bins)])
    poc_idx = np.argmax(bin_vols)
    main_poc = float(bin_centers[poc_idx])
    
    tot_vol = np.sum(bin_vols)
    va_target = tot_vol * 0.68
    cur_va = bin_vols[poc_idx]
    up_i, dn_i = poc_idx, poc_idx
    
    while cur_va < va_target:
        v_up = bin_vols[up_i + 1] if up_i + 1 < num_bins else 0
        v_dn = bin_vols[dn_i - 1] if dn_i - 1 >= 0 else 0
        if v_up == 0 and v_dn == 0:
            break
        if v_up >= v_dn and up_i + 1 < num_bins:
            up_i += 1
            cur_va += v_up
        elif dn_i - 1 >= 0:
            dn_i -= 1
            cur_va += v_dn
        else:
            break
            
    vah = float(bin_centers[up_i])
    val = float(bin_centers[dn_i])
    
    hvn_peaks = []
    mean_v = np.mean(bin_vols)
    for i in range(1, num_bins - 1):
        if bin_vols[i] > bin_vols[i-1] and bin_vols[i] > bin_vols[i+1] and bin_vols[i] > mean_v * 0.7:
            hvn_peaks.append(float(bin_centers[i]))
            
    above_pocs = [p for p in unmitigated_pocs if p > current_price]
    below_pocs = [p for p in unmitigated_pocs if p < current_price]
    
    above_hvns = [p for p in hvn_peaks if p > current_price]
    below_hvns = [p for p in hvn_peaks if p < current_price]
    
    above_npoc = min(above_pocs) if above_pocs else (min(above_hvns) if above_hvns else (main_poc if main_poc > current_price else max_p * 0.995))
    below_npoc = max(below_pocs) if below_pocs else (max(below_hvns) if below_hvns else (main_poc if main_poc < current_price else min_p * 1.005))
    
    above_nvah = vah if vah > current_price else (max_p * 0.99)
    below_nval = val if val < current_price else (min_p * 1.01)
    
    return {
        "above_npoc": float(above_npoc),
        "below_npoc": float(below_npoc),
        "above_nvah": float(above_nvah),
        "below_nvah": float(vah if vah < current_price else 0.0),
        "above_nval": float(val if val > current_price else 0.0),
        "below_nval": float(below_nval)
    }
