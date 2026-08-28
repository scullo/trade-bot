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
    TradingView Gunluk VP ile 1:1 ayni: Her tamamlanan gunun (00:00 UTC) VP'sini cikarir,
    sonraki barlarda test edilmemis (naked) POC, VAH ve VAL seviyelerini tespit eder.
    """
    if df_5m.empty or len(df_5m) < 288:
        return {"above_npoc": 0.0, "below_npoc": 0.0, "above_nvah": 0.0, "below_nval": 0.0}

    df = df_5m.copy()
    df['dt'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df['date'] = df['dt'].dt.date
    
    unique_dates = df['date'].unique()
    # Bugun haric gecmis tamamlanmis gunler
    past_dates = unique_dates[:-1] if len(unique_dates) > 1 else unique_dates
    
    unmitigated_pocs = []
    unmitigated_vahs = []
    unmitigated_vals = []

    for d in past_dates:
        day_candles = df[df['date'] == d]
        if len(day_candles) < 50:
            continue
            
        vp = calculate_volume_profile(day_candles, num_rows=24, value_area_pct=0.68)
        poc = vp["POC"]
        vah = vp["VAH"]
        val = vp["VAL"]
        
        day_end_time = day_candles['timestamp'].iloc[-1]
        future_candles = df[df['timestamp'] > day_end_time]
        
        if future_candles.empty:
            unmitigated_pocs.append(poc)
            unmitigated_vahs.append(vah)
            unmitigated_vals.append(val)
        else:
            # POC test edildi mi?
            if not ((future_candles['low'] <= poc) & (future_candles['high'] >= poc)).any():
                unmitigated_pocs.append(poc)
            # VAH test edildi mi?
            if not ((future_candles['low'] <= vah) & (future_candles['high'] >= vah)).any():
                unmitigated_vahs.append(vah)
            # VAL test edildi mi?
            if not ((future_candles['low'] <= val) & (future_candles['high'] >= val)).any():
                unmitigated_vals.append(val)

    above_pocs = [p for p in unmitigated_pocs if p > current_price]
    below_pocs = [p for p in unmitigated_pocs if p < current_price]

    above_vahs = [v for v in unmitigated_vahs if v > current_price]
    below_vahs = [v for v in unmitigated_vahs if v < current_price]

    above_vals = [v for v in unmitigated_vals if v > current_price]
    below_vals = [v for v in unmitigated_vals if v < current_price]

    return {
        "above_npoc": min(above_pocs) if above_pocs else 0.0,
        "below_npoc": max(below_pocs) if below_pocs else 0.0,
        "above_nvah": min(above_vahs) if above_vahs else 0.0,
        "below_nvah": max(below_vahs) if below_vahs else 0.0,
        "above_nval": min(above_vals) if above_vals else 0.0,
        "below_nval": max(below_vals) if below_vals else 0.0
    }
