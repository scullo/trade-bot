import time
import math
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
    # VDA-33: Asiri volatilite gunlerinde (H/L > 2) S5'in negatif fiyata dusmesini onleyen taban korumasi
    s5 = float(max(close * 0.05, close - (r5 - close)))
    
    return {
        "P": p,
        "R3": r3, "R4": r4, "R5": r5,
        "S3": s3, "S4": s4, "S5": s5
    }

def calculate_anchored_vwap(df_candles: pd.DataFrame, anchor_idx) -> float:
    if df_candles.empty:
        return 0.0

    if anchor_idx in df_candles.index:
        pos = int(df_candles.index.get_loc(anchor_idx))
    else:
        try:
            pos = int(anchor_idx)
        except Exception:
            return 0.0

    if pos < 0 or pos >= len(df_candles):
        return 0.0
        
    sub_df = df_candles.iloc[pos:].copy()
    hlc3 = (sub_df['high'] + sub_df['low'] + sub_df['close']) / 3.0
    tp_vol = hlc3 * sub_df['volume']
    
    cum_tp_vol = tp_vol.cumsum()
    cum_vol = sub_df['volume'].cumsum()
    
    valid_vol = cum_vol.iloc[-1]
    if valid_vol > 0:
        return float(cum_tp_vol.iloc[-1] / valid_vol)
    return float(hlc3.iloc[-1])

def calculate_anchored_vwap_series(df_candles: pd.DataFrame, anchor_idx) -> list:
    """Returns list of dicts: [{'time': int, 'value': float}] for Lightweight Charts plotting."""
    if df_candles.empty:
        return []

    if anchor_idx in df_candles.index:
        pos = int(df_candles.index.get_loc(anchor_idx))
    else:
        try:
            pos = int(anchor_idx)
        except Exception:
            return []

    if pos < 0 or pos >= len(df_candles):
        return []

    sub_df = df_candles.iloc[pos:].copy()
    hlc3 = (sub_df['high'] + sub_df['low'] + sub_df['close']) / 3.0
    tp_vol = hlc3 * sub_df['volume']
    cum_tp_vol = tp_vol.cumsum()
    cum_vol = sub_df['volume'].cumsum()
    
    points = []
    for i in range(len(sub_df)):
        v = cum_vol.iloc[i]
        val = (cum_tp_vol.iloc[i] / v) if v > 0 else hlc3.iloc[i]
        if 'timestamp' in sub_df.columns:
            raw_ts = sub_df['timestamp'].iloc[i]
            ts = int(raw_ts / 1000) if raw_ts > 1e11 else int(raw_ts)
        elif 'time' in sub_df.columns:
            raw_ts = sub_df['time'].iloc[i]
            ts = int(raw_ts / 1000) if raw_ts > 1e11 else int(raw_ts)
        elif isinstance(sub_df.index, pd.DatetimeIndex):
            ts = int(sub_df.index[i].timestamp())
        else:
            try:
                ts = int(sub_df.index[i])
            except Exception:
                ts = int(i)
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
        
        # VDA-29: Hacim esitliginde veya sifir hacimde POC'ye olan yakinlik ve iki yonlu dengeli genisleme saglanir
        if next_up_vol > next_dn_vol and up_idx < num_rows - 1:
            up_idx += 1
            va_accum += next_up_vol
        elif next_dn_vol > next_up_vol and dn_idx > 0:
            dn_idx -= 1
            va_accum += next_dn_vol
        elif up_idx < num_rows - 1 or dn_idx > 0:
            dist_up = (up_idx - poc_idx)
            dist_dn = (poc_idx - dn_idx)
            if dist_up < dist_dn and up_idx < num_rows - 1:
                up_idx += 1
                va_accum += next_up_vol
            elif dist_dn < dist_up and dn_idx > 0:
                dn_idx -= 1
                va_accum += next_dn_vol
            else:
                if up_idx < num_rows - 1:
                    up_idx += 1
                    va_accum += next_up_vol
                if dn_idx > 0:
                    dn_idx -= 1
                    va_accum += next_dn_vol
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

    # 1. Multi-Session test edilmemis (unmitigated) POC tespiti (50% Örtüşmeli Kayan Pencere)
    chunk_size = 144
    step_size = 72
    unmitigated_pocs = []
    total_candles = len(df)
    
    for start_i in range(0, max(1, total_candles - chunk_size), step_size):
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
                if not any(abs(p - c_poc) / max(1e-6, c_poc) < 0.001 for p in unmitigated_pocs):
                    unmitigated_pocs.append(c_poc)
        else:
            if not any(abs(p - c_poc) / max(1e-6, c_poc) < 0.001 for p in unmitigated_pocs):
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
    
    # VDA-26: Kesin yon kurali: above_* kesinlikle > current_price, below_* kesinlikle < current_price olmalidir
    raw_above_npoc = min(above_pocs) if above_pocs else (min(above_hvns) if above_hvns else (main_poc if main_poc > current_price else max_p))
    above_npoc = max(current_price * 1.003, raw_above_npoc)

    raw_below_npoc = max(below_pocs) if below_pocs else (max(below_hvns) if below_hvns else (main_poc if main_poc < current_price else min_p))
    below_npoc = min(current_price * 0.997, raw_below_npoc)

    raw_above_nvah = vah if vah > current_price else max_p
    above_nvah = max(current_price * 1.003, raw_above_nvah)

    raw_below_nval = val if val < current_price else min_p
    below_nval = min(current_price * 0.997, raw_below_nval)
    
    return {
        "above_npoc": float(above_npoc),
        "below_npoc": float(below_npoc),
        "above_nvah": float(above_nvah),
        "below_nvah": float(vah if vah < current_price else 0.0),
        "above_nval": float(val if val > current_price else 0.0),
        "below_nval": float(below_nval)
    }

def calculate_session_and_daily_levels(df_5m: pd.DataFrame, df_1d: pd.DataFrame) -> dict:
    """
    Kurumsal Seans ve Günlük Seviyeler (Auction & Session Liquidity Framework):
    - PDH (Previous Day High): Dünün en yüksek fiyatı
    - PDL (Previous Day Low): Dünün en düşük fiyatı
    - PDC (Previous Day Close): Dünün kapanış fiyatı
    - Asia High / Low: 00:00 - 08:00 UTC arasındaki Asya Seansı Zirvesi ve Dibi
    """
    res = {
        "pdh": 0.0,
        "pdl": 0.0,
        "pdc": 0.0,
        "asia_high": 0.0,
        "asia_low": 0.0
    }
    try:
        if df_1d is not None and not df_1d.empty and len(df_1d) >= 2:
            prev_row = df_1d.iloc[-2]
            res["pdh"] = float(prev_row.get('high', 0.0))
            res["pdl"] = float(prev_row.get('low', 0.0))
            res["pdc"] = float(prev_row.get('close', 0.0))
        elif df_1d is not None and not df_1d.empty:
            prev_row = df_1d.iloc[-1]
            res["pdh"] = float(prev_row.get('high', 0.0))
            res["pdl"] = float(prev_row.get('low', 0.0))
            res["pdc"] = float(prev_row.get('close', 0.0))

        if df_5m is not None and not df_5m.empty and 'timestamp' in df_5m.columns:
            ts_series = pd.to_datetime(df_5m['timestamp'], unit='ms', utc=True)
            today_utc = ts_series.iloc[-1].date()
            asia_mask = (ts_series.dt.date == today_utc) & (ts_series.dt.hour >= 0) & (ts_series.dt.hour < 8)
            asia_df = df_5m[asia_mask]
            if not asia_df.empty:
                res["asia_high"] = float(asia_df['high'].max())
                res["asia_low"] = float(asia_df['low'].min())
    except Exception:
        pass

    return res

# =========================================================================
# 5-PILLAR INSTITUTIONAL QUANT GUARDIANS (BOLTZMANN, MANDELBROT, GRIFFIN, SIMONS, THORP)
# =========================================================================

def calculate_orderbook_entropy(bids: list, asks: list, top_n: int = 20) -> dict:
    """
    1. LUDWIG BOLTZMANN — Emir Defteri Termodinamik Entropisi (Order Book Thermodynamic Entropy):
    - 20 kademe alış ve satış derinliğinin olasılık dağılımını (p_i) hesaplar.
    - S = - sum(p_i * ln(p_i))
    - Normalize Entropi S_norm = S / ln(K) -> [0.0, 1.0]
    - S_norm > 0.88: Maksimum düzensizlik / Kaotik tahta (İşlem engellenir)
    - S_norm < 0.60: Kurumsal kristalleşme / Konsantre blokaj (Yüksek güven)
    """
    try:
        sub_bids = bids[:top_n] if bids else []
        sub_asks = asks[:top_n] if asks else []

        def _entropy_of_side(side_items):
            if not side_items:
                return 1.0
            vols = np.array([float(p) * float(q) for p, q in side_items], dtype=np.float64)
            tot = np.sum(vols)
            if tot <= 0:
                return 1.0
            p_dist = vols / tot
            p_dist = p_dist[p_dist > 1e-12]
            ent = -np.sum(p_dist * np.log(p_dist))
            max_ent = np.log(len(side_items)) if len(side_items) > 1 else 1.0
            return float(np.clip(ent / max_ent, 0.0, 1.0))

        ent_bid = _entropy_of_side(sub_bids)
        ent_ask = _entropy_of_side(sub_asks)
        ent_norm = round(float((ent_bid + ent_ask) / 2.0), 3)

        # VDA-25: Entropi mantığı düzeltildi:
        # S_norm >= 0.80: Derin & Sağlıklı Likidite Dağılımı (20 kademeye eşit yayılmış kurumsal tahta)
        # S_norm < 0.40: Anormal Yoğunlaşma / Tek Duvar Riski (Spoofing ve ani kayma riski)
        return {
            "entropy_norm": ent_norm,
            "entropy_bid": round(ent_bid, 3),
            "entropy_ask": round(ent_ask, 3),
            "is_healthy_deep": ent_norm >= 0.80,
            "is_abnormal_concentration": ent_norm < 0.40,
            "is_chaotic": ent_norm < 0.40,
            "is_crystalline": ent_norm < 0.40
        }
    except Exception:
        return {
            "entropy_norm": 0.70,
            "entropy_bid": 0.70,
            "entropy_ask": 0.70,
            "is_healthy_deep": False,
            "is_abnormal_concentration": False,
            "is_chaotic": False,
            "is_crystalline": False
        }


def calculate_shannon_market_entropy(df: pd.DataFrame, depth_info: dict = None, iceberg_ratio: float = 1.0, window: int = 24) -> dict:
    """
    CLAUDE SHANNON & LUDWIG BOLTZMANN — Dinamik Piyasa & Mikro-Yapı Bilgi Entropisi:
    - 5M mum akışı (Hacim Konsantrasyonu & Getiri Durum Dağılımı)
    - Tahta derinlik dengesizliği (Top-of-Book Micro-Entropy)
    - Iceberg / Emilim konsantrasyonu (Crystallization Drag)
    - Çıktı: [0.15, 0.98] aralığında dinamik normalize entropi (S_norm)
    """
    try:
        if df is None or len(df) < 10:
            return {
                "entropy_norm": 0.65,
                "entropy_vol": 0.65,
                "entropy_ret": 0.65,
                "entropy_ob": 0.65,
                "iceberg_drag": 0.0,
                "is_healthy_deep": False,
                "is_chaotic": False,
                "is_crystalline": False
            }

        sub_df = df.tail(window)
        w_len = len(sub_df)

        # 1. Hacim Konsantrasyon Entropisi (Volume Shannon Entropy)
        vol_col = 'quote_volume' if 'quote_volume' in sub_df.columns else ('volume' if 'volume' in sub_df.columns else None)
        if vol_col and vol_col in sub_df.columns:
            vols = sub_df[vol_col].astype(float).values
            tot_vol = np.sum(vols)
            if tot_vol > 1e-6 and w_len > 1:
                p_v = vols / tot_vol
                p_v = p_v[p_v > 1e-12]
                s_vol = -np.sum(p_v * np.log(p_v)) / np.log(w_len)
                s_vol = float(np.clip(s_vol, 0.0, 1.0))
            else:
                s_vol = 0.70
        else:
            s_vol = 0.70

        # 2. Getiri Durum Dağılım Entropisi (Return State Shannon Entropy)
        if 'close' in sub_df.columns and len(sub_df) >= 6:
            closes = sub_df['close'].astype(float).values
            rets = np.diff(np.log(np.maximum(closes, 1e-12)))
            std_r = np.std(rets)
            if std_r > 1e-8:
                z = (rets - np.mean(rets)) / std_r
                bins = np.histogram(z, bins=[-np.inf, -1.0, -0.3, 0.3, 1.0, np.inf])[0]
                p_r = bins / float(len(rets))
                p_r = p_r[p_r > 1e-12]
                s_ret = -np.sum(p_r * np.log(p_r)) / np.log(5.0)
                s_ret = float(np.clip(s_ret, 0.0, 1.0))
            else:
                s_ret = 0.70
        else:
            s_ret = 0.70

        # 3. Tahta Kademe Dengesizlik Entropisi (Top-of-Book Micro-Entropy)
        s_ob = 0.75
        if depth_info:
            bid_p = float(depth_info.get('bid_price', 0.0))
            bid_q = float(depth_info.get('bid_qty', 0.0))
            ask_p = float(depth_info.get('ask_price', 0.0))
            ask_q = float(depth_info.get('ask_qty', 0.0))
            b_usd = bid_p * bid_q
            a_usd = ask_p * ask_q
            tot_usd = b_usd + a_usd
            if tot_usd > 0:
                p_b = max(1e-4, min(1.0 - 1e-4, b_usd / tot_usd))
                p_a = 1.0 - p_b
                ent_binary = -(p_b * np.log(p_b) + p_a * np.log(p_a)) / np.log(2.0)
                s_ob = float(np.clip(ent_binary, 0.0, 1.0))

        # 4. Iceberg / Emilim Kristalleşme Düzeltmesi (Whale Wall Concentration)
        c_ice = 0.0
        if iceberg_ratio and iceberg_ratio > 1.0:
            c_ice = float(np.clip((iceberg_ratio - 1.0) * 0.012, 0.0, 0.18))

        # Bileşik Ağırlıklandırma: Hacim + Getiri + Tahta - Iceberg Kristalleşmesi
        composite_s = (0.45 * s_vol) + (0.35 * s_ret) + (0.20 * s_ob) - c_ice
        ent_norm = round(float(np.clip(composite_s, 0.15, 0.98)), 3)

        return {
            "entropy_norm": ent_norm,
            "entropy_vol": round(s_vol, 3),
            "entropy_ret": round(s_ret, 3),
            "entropy_ob": round(s_ob, 3),
            "iceberg_drag": round(c_ice, 3),
            "is_healthy_deep": ent_norm >= 0.80,
            "is_chaotic": ent_norm < 0.40,
            "is_crystalline": ent_norm < 0.48
        }
    except Exception:
        return {
            "entropy_norm": 0.65,
            "entropy_vol": 0.65,
            "entropy_ret": 0.65,
            "entropy_ob": 0.65,
            "iceberg_drag": 0.0,
            "is_healthy_deep": False,
            "is_chaotic": False,
            "is_crystalline": False
        }


def calculate_hurst_exponent(price_series, min_lags: int = 10, max_lags: int = None) -> float:
    """
    2. BENOIT MANDELBROT — Hurst Üssü (H) ve Fraktal Rejim Dedektörü:
    - VDA-22: R/S analizi ham fiyatlar yerine finansal log-getiriler (r_t = ln(P_t / P_{t-1})) üzerine kurulur.
    - H > 0.55: Kalıcı (Persistent / Trending) -> Breakout izinli.
    - H < 0.45: Ortalamaya Dönen (Anti-persistent / Mean-Reverting) -> Breakout TUZAK, Sekme oyna!
    - 0.45 <= H <= 0.55: Rastgele Yürüyüş (Brownian Motion / Gürültü).
    """
    try:
        if price_series is None or len(price_series) < 32:
            return 0.50

        prices = np.array(price_series, dtype=np.float64)
        prices = prices[prices > 0]
        if len(prices) < 32:
            return 0.50

        # VDA-22: Finansal ekonometri standardı: Log-getiriler (Durağan seri)
        ts = np.diff(np.log(prices))
        n = len(ts)
        if n < 30:
            return 0.50

        if max_lags is None:
            max_lags = min(n // 4, 100)
        if max_lags <= min_lags:
            max_lags = min_lags + 10

        lags = range(min_lags, max_lags, 2)
        rs_values = []

        for lag in lags:
            num_chunks = n // lag
            if num_chunks < 1:
                continue
            rs_chunk = []
            for i in range(num_chunks):
                chunk = ts[i * lag : (i + 1) * lag]
                mean_c = np.mean(chunk)
                dev = chunk - mean_c
                cum_dev = np.cumsum(dev)
                r_val = np.max(cum_dev) - np.min(cum_dev)
                s_val = np.std(chunk)
                if s_val > 1e-12:
                    rs_chunk.append(r_val / s_val)
            if rs_chunk:
                rs_values.append((lag, np.mean(rs_chunk)))

        if len(rs_values) < 3:
            return 0.50

        x = np.log([item[0] for item in rs_values])
        y = np.log([item[1] for item in rs_values])

        poly = np.polyfit(x, y, 1)
        hurst = float(np.clip(poly[0], 0.05, 0.95))
        return round(hurst, 3)
    except Exception:
        return 0.50


def detect_iceberg_orders(executed_buy_usd: float, executed_sell_usd: float, top_bid_usd: float, top_ask_usd: float, is_zone_depth: bool = False) -> dict:
    """
    3. KEN GRIFFIN — Gizli Likidite (Iceberg / Buzdağı) Radarı:
    - Son 60s gerçekleşen agresif taker hacmini tahtada görünen derinliğe oranlar.
    - Yapay 50.0x tavan bozulması giderildi: Bant likiditesi ve dinamik normalizasyon ile [1.0x - 20.0x] aralığında gerçek kurumsal emilim ölçülür.
    - Ask Iceberg (Satıcı Buzdağı): executed_buy_usd / effective_ask_depth >= 3.0x
    - Bid Iceberg (Alıcı Buzdağı): executed_sell_usd / effective_bid_depth >= 3.0x
    """
    try:
        if is_zone_depth:
            effective_ask_depth = max(3500.0, float(top_ask_usd))
            effective_bid_depth = max(3500.0, float(top_bid_usd))
        else:
            effective_ask_depth = max(5000.0, float(top_ask_usd) * 3.5)
            effective_bid_depth = max(5000.0, float(top_bid_usd) * 3.5)

        raw_ask_r = float(executed_buy_usd / effective_ask_depth)
        raw_bid_r = float(executed_sell_usd / effective_bid_depth)

        ask_ratio = round(min(20.0, raw_ask_r), 2)
        bid_ratio = round(min(20.0, raw_bid_r), 2)

        has_ask_iceberg = (ask_ratio >= 3.0 and executed_buy_usd >= 8000.0)
        has_bid_iceberg = (bid_ratio >= 3.0 and executed_sell_usd >= 8000.0)

        iceberg_side = "NONE"
        if has_ask_iceberg and ask_ratio > bid_ratio:
            iceberg_side = "ICEBERG_ASK_RESISTANCE"
        elif has_bid_iceberg and bid_ratio > ask_ratio:
            iceberg_side = "ICEBERG_BID_SUPPORT"

        return {
            "ask_iceberg_ratio": ask_ratio,
            "bid_iceberg_ratio": bid_ratio,
            "iceberg_ratio": max(ask_ratio, bid_ratio),
            "iceberg_side": iceberg_side,
            "has_seller_iceberg": has_ask_iceberg,
            "has_buyer_iceberg": has_bid_iceberg
        }
    except Exception:
        return {
            "ask_iceberg_ratio": 1.0,
            "bid_iceberg_ratio": 1.0,
            "iceberg_ratio": 1.0,
            "iceberg_side": "NONE",
            "has_seller_iceberg": False,
            "has_buyer_iceberg": False
        }


def estimate_hmm_market_phase(df_candles: pd.DataFrame, wick_ratio_pct: float = 35.0, cvd_ratio: float = 50.0, vol_surge: float = 1.0) -> dict:
    """
    4. JIM SIMONS — Gizli Markov / Piyasa Fazı Sınıflandırıcısı (Latent Market Phase Classifier):
    - 3 Gizli Durum:
      1. ACCUMULATION (Sessiz Birikim)
      2. MANIPULATION_SWEEP (Stop Avı / Likidite Süpürme Evresi - Erken kırılım tuzaktır!)
      3. DIRECTIONAL_EXPANSION (Yönlü Genişleme / Gerçek Trend Hareketi)
    """
    try:
        is_high_wick = (wick_ratio_pct >= 45.0)
        is_cvd_divergent = (cvd_ratio >= 65.0 or cvd_ratio <= 35.0)

        if is_high_wick and vol_surge >= 1.75:
            phase = "MANIPULATION_SWEEP"
            confidence = 0.85
            desc = "⚠️ Manipülasyon & Stop Avı Evresi (Yüksek Fitil + Hacim Tuzağı)"
        elif vol_surge >= 2.0 and not is_high_wick and is_cvd_divergent:
            phase = "DIRECTIONAL_EXPANSION"
            confidence = 0.80
            desc = "🚀 Yönlü Kurumsal Genişleme (Gerçek Trend Koşusu)"
        else:
            phase = "ACCUMULATION"
            confidence = 0.70
            desc = "⚪ Sessiz Akümülasyon / Denge Fazı"

        return {
            "phase": phase,
            "confidence": confidence,
            "description": desc,
            "is_manipulation": phase == "MANIPULATION_SWEEP",
            "is_expansion": phase == "DIRECTIONAL_EXPANSION"
        }
    except Exception:
        return {
            "phase": "ACCUMULATION",
            "confidence": 0.50,
            "description": "⚪ Standart Faz",
            "is_manipulation": False,
            "is_expansion": False
        }


def calculate_fractional_kelly(win_rate_pct: float, reward_risk_ratio: float = 2.0, fraction: float = 0.25) -> float:
    """
    5. ED THORP — Fraksiyonel Kelly Kriteri Dinamik Marjin Çarpanı:
    - f* = (b * p - q) / b
    - fraction = 0.25 (Çeyrek Kelly Koruması - Kripto oynaklığına karşı optimal)
    - Çıktı: 0.65x ile 1.35x arasında çarpan döndürür.
    """
    try:
        p = float(np.clip(win_rate_pct / 100.0, 0.20, 0.90))
        q = 1.0 - p
        b = max(1.0, float(reward_risk_ratio))

        full_kelly = (b * p - q) / b
        scaled_kelly = full_kelly * fraction
        mult = 1.0 + (scaled_kelly * 2.0)
        return round(float(np.clip(mult, 0.65, 1.35)), 2)
    except Exception:
        return 1.0


def detect_bookmap_absorption(
    taker_buy_usd: float,
    taker_sell_usd: float,
    top_bid_usd: float,
    top_ask_usd: float,
    price_change_pct_60s: float = 0.0,
    wall_duration_sec: float = 0.0,
    is_major: bool = False
) -> dict:
    """
    6. BOOKMAP — Mikro-Sipariş Akışı & Kurumsal Likidite Emilim (Absorption) Dedektörü:
    - Pasif Satıcı Emilimi (Ask Absorption / Boğa Tuzağı):
      Agresif alıcılar direnç kademesine hücum ederken fiyat yukarı gidemez (fiyat sıkışması).
      Pasif satıcı balina tüm alımları sünger gibi emer. Fiyat tavana çarpıp çökmek üzeredir.
    - Pasif Alıcı Emilimi (Bid Absorption / Ayı Tuzağı):
      Agresif satıcılar destek kademesine hücum ederken fiyat aşağı delinemez.
      Pasif alıcı balina tüm satışları sünger gibi emer. Fiyat tabandan patlamak üzeredir.
    - Kurumsal Çapa Duvarı (Anchor Persistence):
      Duvar süresi >= 15.0s ise gerçek çapa duvarıdır. >= 40.0s ise masif beton bloktur.
    """
    try:
        min_taker_vol = 15000.0 if is_major else 6000.0

        # Oranlar
        ask_absorption_ratio = round(float(taker_buy_usd / max(100.0, top_ask_usd)), 2)
        bid_absorption_ratio = round(float(taker_sell_usd / max(100.0, top_bid_usd)), 2)

        # Fiyat sıkışması: Son 60s'deki fiyat hareketi <= %0.08 ise fiyat o kademede çakılıdır
        is_price_stalled = abs(float(price_change_pct_60s)) <= 0.08

        # Satıcı Emilimi (Boğa Tuzağı)
        has_seller_absorption = (
            taker_buy_usd >= min_taker_vol and
            ask_absorption_ratio >= 2.5 and
            is_price_stalled
        )

        # Alıcı Emilimi (Ayı Tuzağı)
        has_buyer_absorption = (
            taker_sell_usd >= min_taker_vol and
            bid_absorption_ratio >= 2.5 and
            is_price_stalled
        )

        # Çapa Duvarı Durumu
        wall_dur = float(wall_duration_sec)
        is_anchor_wall = (wall_dur >= 15.0)
        is_iron_wall = (wall_dur >= 40.0)
        is_flash_spoof = (0.0 < wall_dur < 5.0)

        absorption_type = "NONE"
        absorption_desc = "⚪ Normal Sipariş Akışı"
        if has_seller_absorption and (ask_absorption_ratio >= bid_absorption_ratio):
            absorption_type = "ASK_ABSORPTION_BEARISH"
            absorption_desc = f"🌊 Pasif Satıcı Süngeri (Taker Alım: ${taker_buy_usd:,.0f}, {ask_absorption_ratio:.1f}x) — Boğa Tuzağı Riski"
        elif has_buyer_absorption and (bid_absorption_ratio >= ask_absorption_ratio):
            absorption_type = "BID_ABSORPTION_BULLISH"
            absorption_desc = f"🌊 Pasif Alıcı Süngeri (Taker Satım: ${taker_sell_usd:,.0f}, {bid_absorption_ratio:.1f}x) — Kurumsal Taban Güvencesi"
        elif is_iron_wall:
            absorption_desc = f"🧱 Masif Beton Çapa Duvarı ({wall_dur:.0f}s Aktif)"
        elif is_anchor_wall:
            absorption_desc = f"🧱 Kurumsal Çapa Duvarı ({wall_dur:.0f}s Aktif)"

        return {
            "has_seller_absorption": bool(has_seller_absorption),
            "has_buyer_absorption": bool(has_buyer_absorption),
            "ask_absorption_ratio": float(ask_absorption_ratio),
            "bid_absorption_ratio": float(bid_absorption_ratio),
            "is_price_stalled": bool(is_price_stalled),
            "is_anchor_wall": bool(is_anchor_wall),
            "is_iron_wall": bool(is_iron_wall),
            "is_flash_spoof": bool(is_flash_spoof),
            "wall_duration_sec": round(wall_dur, 1),
            "absorption_type": absorption_type,
            "absorption_desc": absorption_desc
        }
    except Exception:
        return {
            "has_seller_absorption": False,
            "has_buyer_absorption": False,
            "ask_absorption_ratio": 1.0,
            "bid_absorption_ratio": 1.0,
            "is_price_stalled": False,
            "is_anchor_wall": False,
            "is_iron_wall": False,
            "is_flash_spoof": False,
            "wall_duration_sec": 0.0,
            "absorption_type": "NONE",
            "absorption_desc": "⚪ Normal Sipariş Akışı"
        }


def calculate_cvd_acceleration(cvd_series, window: int = 5) -> dict:
    """
    7. CVD 1. Türev (Hız) ve 2. Türev (İvme) & Sıfır Geçişi (Zero-Crossing) Analiz Motoru:
    - Fiyat tepeye giderken ivme negatife döndüğünde: BULL_EXHAUSTION_TOP (Alıcı tükenişi, tepe dönüşü).
    - Fiyat dibe inerken ivme pozitife döndüğünde: BEAR_EXHAUSTION_BOTTOM (Satıcı tükenişi, dip dönüşü).
    """
    default_res = {
        'velocity': 0.0,
        'acceleration': 0.0,
        'zero_crossing': 'NONE',
        'is_exhaustion_top': False,
        'is_exhaustion_bottom': False,
        'momentum_regime': 'NEUTRAL'
    }
    if not cvd_series or len(cvd_series) < 4:
        return default_res

    try:
        arr = np.array(cvd_series[-max(window + 3, 10):], dtype=float)
        # 3-period EWMA kernel ile gürültü filtreleme
        if len(arr) >= 5:
            kernel = np.array([0.2, 0.3, 0.5])
            smoothed = np.convolve(arr, kernel, mode='valid')
        else:
            smoothed = arr

        vel = np.diff(smoothed)
        acc = np.diff(vel)

        if len(acc) < 2:
            return default_res

        # VDA-31: Sayısal türev basamak süreksizliklerini ve Dirac-delta sahte ivme patlamalarını filtrele
        cur_vel = float(vel[-1]) if not np.isnan(vel[-1]) else 0.0
        cur_acc = float(acc[-1]) if not np.isnan(acc[-1]) else 0.0
        prev_acc = float(acc[-2]) if not np.isnan(acc[-2]) else 0.0

        acc_std = float(np.std(acc)) if len(acc) > 2 else 0.0
        acc_median = float(np.median(acc)) if len(acc) > 2 else 0.0
        if acc_std > 0 and abs(cur_acc - acc_median) > 5.0 * acc_std:
            cur_acc = float(np.clip(cur_acc, acc_median - 3.0 * acc_std, acc_median + 3.0 * acc_std))

        is_ex_top = False
        is_ex_bottom = False
        zero_cross = 'NONE'

        # Sıfır Geçişi Tespiti (Son 4 veri noktasında)
        for i in range(len(acc) - 1, max(0, len(acc) - 4), -1):
            if acc[i-1] > 0 and acc[i] <= 0:
                zero_cross = 'BULL_EXHAUSTION_TOP'
                is_ex_top = True
                break
            elif acc[i-1] < 0 and acc[i] >= 0:
                zero_cross = 'BEAR_EXHAUSTION_BOTTOM'
                is_ex_bottom = True
                break

        if cur_vel > 0 and cur_acc > 0:
            regime = 'ACCELERATING_BUY'
        elif cur_vel > 0 and cur_acc <= 0:
            regime = 'DECELERATING_BUY'
        elif cur_vel < 0 and cur_acc < 0:
            regime = 'ACCELERATING_SELL'
        elif cur_vel < 0 and cur_acc >= 0:
            regime = 'DECELERATING_SELL'
        else:
            regime = 'NEUTRAL'

        return {
            'velocity': round(cur_vel, 2),
            'acceleration': round(cur_acc, 2),
            'zero_crossing': zero_cross,
            'is_exhaustion_top': is_ex_top,
            'is_exhaustion_bottom': is_ex_bottom,
            'momentum_regime': regime
        }
    except Exception:
        return default_res


def calculate_delta_poc(levels: dict, current_price: float, recent_candles: pd.DataFrame = None) -> dict:
    """
    8. dPOC (Delta Point of Control / Tuzaklanmış Likidite Ayak İzi):
    Seviyelerde gerçekleşen net delta birikimini ve tuzaklanmış yatırımcıları tespit eder.
    - TRAPPED_LONGS: Dirençte aşırı alım yapıldı fakat fiyat direncin altında kaldı (Boğa Tuzağı -> Short Teyidi).
    - TRAPPED_SHORTS: Destekte aşırı satım yapıldı fakat fiyat desteğin üstünde kaldı (Ayı Tuzağı -> Long Teyidi).
    """
    res = {
        'trapped_bias': 'NEUTRAL',
        'trapped_status': 'NONE',
        'trapped_desc': 'Dengeli Seviye Akışı',
        'confluence_bonus': 0.0
    }
    if not levels or current_price <= 0:
        return res

    try:
        cam = levels.get('camarilla', {})
        s3 = cam.get('S3', 0.0)
        r3 = cam.get('R3', 0.0)
        p = cam.get('P', 0.0)
        below_npoc = levels.get('below_npoc', 0.0) or 0.0
        above_npoc = levels.get('above_npoc', 0.0) or 0.0

        if recent_candles is not None and isinstance(recent_candles, pd.DataFrame) and len(recent_candles) >= 1:
            last_candle = recent_candles.iloc[-1]
            c_high = float(last_candle.get('high', current_price))
            c_low = float(last_candle.get('low', current_price))
            c_close = float(last_candle.get('close', current_price))

            # Direnç Retestinde Tuzaklanmış Boğalar (Trapped Longs at Resistance / R3 / Above nPOC)
            resist_ref = above_npoc if (above_npoc > 0 and abs(current_price - above_npoc) / current_price <= 0.006) else r3
            if resist_ref > 0 and c_high >= resist_ref and c_close < resist_ref:
                res['trapped_bias'] = 'SHORT'
                res['trapped_status'] = 'TRAPPED_LONGS'
                res['trapped_desc'] = f'🪤 Dirençte (${resist_ref:.4f}) Tuzaklanmış Boğalar (Trapped Longs)'
                res['confluence_bonus'] = 1.15
                return res

            # Destek Sekmesinde Tuzaklanmış Ayılar (Trapped Shorts at Support / S3 / Below nPOC)
            support_ref = below_npoc if (below_npoc > 0 and abs(current_price - below_npoc) / current_price <= 0.006) else s3
            if support_ref > 0 and c_low <= support_ref and c_close > support_ref:
                res['trapped_bias'] = 'LONG'
                res['trapped_status'] = 'TRAPPED_SHORTS'
                res['trapped_desc'] = f'🪤 Destekte (${support_ref:.4f}) Tuzaklanmış Ayılar (Trapped Shorts)'
                res['confluence_bonus'] = 1.15
                return res

        return res
    except Exception:
        return res


def evaluate_iceberg_offense(iceberg_data: dict, current_price: float, levels: dict, regime: str = 'REGIME_RANGING_PINGPONG') -> dict:
    """
    9. Iceberg X-Ray Hücum Sniper Motoru:
    Mevcut detect_iceberg_orders çıktısını alıp 3 boyutta (Long, Short, Yatay Ping-Pong) hücum silahına dönüştürür.
    - LONG SNIPER: Destekte alıcı buzdağı arkasına saklanarak %0.22 dar stop ile hücum.
    - SHORT SNIPER: Dirençte satıcı buzdağı arkasına saklanarak %0.22 dar stop ile hücum.
    - PING-PONG ARBITRAJ: Yatay rejimde kanal sınırları arasında çift yönlü vur-kaç.
    """
    res = {
        'is_sniper_buy': False,
        'is_sniper_sell': False,
        'is_ping_pong': False,
        'tight_stop_dist_pct': 0.0022,  # %0.22 dar kurumsal stop!
        'rr_multiplier': 1.0,
        'offense_reason': '',
        'buyer_offense_reason': '',
        'seller_offense_reason': '',
        'target_price': 0.0
    }
    if not iceberg_data or current_price <= 0:
        return res

    try:
        has_ask_iceberg = bool(iceberg_data.get('has_seller_iceberg', False))
        has_bid_iceberg = bool(iceberg_data.get('has_buyer_iceberg', False))
        ask_ratio = float(iceberg_data.get('ask_iceberg_ratio', 1.0))
        bid_ratio = float(iceberg_data.get('bid_iceberg_ratio', 1.0))

        cam = levels.get('camarilla', {}) if levels else {}
        s3 = cam.get('S3', 0.0)
        r3 = cam.get('R3', 0.0)
        below_npoc = (levels.get('below_npoc') or 0.0) if levels else 0.0
        above_npoc = (levels.get('above_npoc') or 0.0) if levels else 0.0
        p = cam.get('P', 0.0)

        # 🟢 1. LONG SNIPER HÜCUMU (Destekte Alıcı Buzdağı Arkasına Saklanma)
        support_levels = [lvl for lvl in [s3, below_npoc, p] if lvl > 0 and abs(current_price - lvl) / current_price <= 0.0035]
        if has_bid_iceberg and support_levels and regime in ['REGIME_BULL_TREND', 'REGIME_RANGING_PINGPONG']:
            sup_lvl = max(support_levels)
            res['is_sniper_buy'] = True
            res['tight_stop_dist_pct'] = 0.0022
            res['rr_multiplier'] = 1.8
            b_reason = f'🧊 Kurumsal Alıcı Buzdağı Hücumu (${sup_lvl:.4f} Destek Arkası, {bid_ratio:.1f}x Emilim)'
            res['buyer_offense_reason'] = b_reason
            res['offense_reason'] = b_reason
            res['target_price'] = r3 if r3 > current_price else current_price * 1.015

        # 🔴 2. SHORT SNIPER HÜCUMU (Dirençte Satıcı Buzdağı Arkasına Saklanma)
        resist_levels = [lvl for lvl in [r3, above_npoc, p] if lvl > 0 and abs(current_price - lvl) / current_price <= 0.0035]
        if has_ask_iceberg and resist_levels and regime in ['REGIME_BEAR_TREND', 'REGIME_RANGING_PINGPONG']:
            res_lvl = min(resist_levels)
            res['is_sniper_sell'] = True
            res['tight_stop_dist_pct'] = 0.0022
            res['rr_multiplier'] = 1.8
            s_reason = f'🧊 Kurumsal Satıcı Buzdağı Hücumu (${res_lvl:.4f} Direnç Arkası, {ask_ratio:.1f}x Emilim)'
            res['seller_offense_reason'] = s_reason
            if not res['is_sniper_buy']:
                res['offense_reason'] = s_reason
            res['target_price'] = s3 if (s3 > 0 and s3 < current_price) else current_price * 0.985

        # ⚪ 3. YATAY PİNG-PONG ARBİTRAJI
        if regime == 'REGIME_RANGING_PINGPONG' and (res['is_sniper_buy'] or res['is_sniper_sell']):
            res['is_ping_pong'] = True

        return res
    except Exception:
        return res


def calculate_stoikov_micro_price(bids: list, asks: list, current_price: float = 0.0, levels: dict = None) -> dict:
    """
    10. SASHA STOIKOV (Cornell) — Stoikov Micro-Price & Mıknatıs Modeli:
    - Çok kademeli (multi-level weighted) emir defteri ağırlıklı adil fiyatı hesaplar.
    - P_micro = P_mid + Imbalance * (Spread / 2)
    - Trendde kırılımı önden koşar (Front-run Breakout/Breakdown).
    - Yatayda kanal sınırında mıknatıs (Mean-Reversion Magnet) olarak çalışır.
    """
    res = {
        'micro_price': float(current_price),
        'mid_price': float(current_price),
        'micro_drift_bps': 0.0,
        'micro_bias': 'NEUTRAL',
        'is_micro_bull': False,
        'is_micro_bear': False,
        'magnet_status': 'NONE',
        'magnet_desc': ''
    }
    if not bids or not asks:
        return res

    try:
        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])
        if best_bid <= 0 or best_ask <= best_bid:
            return res

        spread = best_ask - best_bid
        mid_price = (best_bid + best_ask) / 2.0

        # İlk 5 kademenin azalan ağırlıklı (decay) derinlik hesabı
        weights = [1.0, 0.70, 0.50, 0.35, 0.20]
        bid_w_vol = 0.0
        ask_w_vol = 0.0

        for i in range(min(5, len(bids))):
            w = weights[i]
            p, q = bids[i]
            bid_w_vol += float(q) * w

        for i in range(min(5, len(asks))):
            w = weights[i]
            p, q = asks[i]
            ask_w_vol += float(q) * w

        tot_w_vol = bid_w_vol + ask_w_vol
        if tot_w_vol <= 0:
            imb = 0.0
        else:
            imb = (bid_w_vol - ask_w_vol) / tot_w_vol

        # Stoikov Micro-Price:
        micro_price = mid_price + (imb * (spread / 2.0))
        drift_bps = round(((micro_price - mid_price) / mid_price) * 10000.0, 4)
        spread_bps = (spread / mid_price) * 10000.0

        # VDA-24: Eşik paritenin kendi ortalama spread oranına ve emir defteri dengesizliğine (imb) endekslenir.
        # Sabit 1.2 bps BTC/ETH gibi sığ spread'li (0.01 bps) paritelerde imkansızdı.
        dyn_threshold_bps = max(0.005, spread_bps * 0.35)
        is_bull_drift = (drift_bps >= dyn_threshold_bps and imb >= 0.30) or (imb >= 0.60)
        is_bear_drift = (drift_bps <= -dyn_threshold_bps and imb <= -0.30) or (imb <= -0.60)

        bias = 'NEUTRAL'
        if is_bull_drift:
            bias = 'BULL_MICRO_DRIFT'
        elif is_bear_drift:
            bias = 'BEAR_MICRO_DRIFT'

        # Yatay Mod Mıknatıs (Mean-Reversion Magnet) Tespiti
        magnet_status = 'NONE'
        magnet_desc = ''
        if levels and current_price > 0:
            cam = levels.get('camarilla', {})
            s3 = cam.get('S3', 0.0)
            r3 = cam.get('R3', 0.0)

            # Destek sekme mıknatısı: Fiyat S3 yakınında ve mikro-fiyat ortalamaya (yukarı) çekiyor
            if s3 > 0 and abs(current_price - s3) / current_price <= 0.0040:
                if is_bull_drift:
                    magnet_status = 'S3_MAGNET_REBOUND'
                    magnet_desc = f'🧲 Stoikov Destek Mıknatısı: Mikro-fiyat (${micro_price:.4f}, +{drift_bps} bps) yukarı çekiyor.'

            # Direnç tepki mıknatısı: Fiyat R3 yakınında ve mikro-fiyat ortalamaya (aşağı) çekiyor
            elif r3 > 0 and abs(current_price - r3) / current_price <= 0.0040:
                if is_bear_drift:
                    magnet_status = 'R3_MAGNET_REJECTION'
                    magnet_desc = f'🧲 Stoikov Direnç Mıknatısı: Mikro-fiyat (${micro_price:.4f}, {drift_bps} bps) aşağı çekiyor.'

        return {
            'micro_price': round(micro_price, 6),
            'mid_price': round(mid_price, 6),
            'micro_drift_bps': drift_bps,
            'micro_bias': bias,
            'is_micro_bull': is_bull_drift,
            'is_micro_bear': is_bear_drift,
            'magnet_status': magnet_status,
            'magnet_desc': magnet_desc
        }
    except Exception:
        return res


def calculate_vpin_toxicity(df_candles: pd.DataFrame, rolling_window: int = 12, recent_cvd: dict = None) -> dict:
    """
    11. EASLEY, LOPEZ DE PRADO, O'HARA — VPIN (Volume-Synchronized Probability of Toxicity):
    - Hacim bazlı toksik akış ve kurumsal içeriden bilgi (informed trader) baskısını ölçer.
    - VPIN in [0.0, 1.0]
    - TRENDDE: VPIN >= 0.50 ise kırılımın arkasında gerçek kurumsal akış var demektir (Gerçek Kırılım Teyidi).
    - YATAYDA: VPIN >= 0.55 ise KONSOLİDASYON PATLAMAK ÜZEREDİR! Sahte range scalplarını derhal veto eder.
    """
    res = {
        'vpin_score': 0.30,
        'toxicity_level': 'LOW',
        'is_toxic_flow': False,
        'is_range_veto_alert': False,
        'vpin_desc': 'Dengeli & Sakin Akış'
    }
    if df_candles is None or not isinstance(df_candles, pd.DataFrame) or len(df_candles) < 3:
        return res

    try:
        sub = df_candles.tail(min(rolling_window, len(df_candles)))
        total_v = 0.0
        abs_order_imbalance = 0.0

        for _, row in sub.iterrows():
            vol = float(row.get('volume', 0.0))
            if vol <= 0:
                continue
            total_v += vol

            # VDA-23: Binance/CCXT gercek borsa taker hacim akisi ('taker_base', 'taker_quote')
            buy_v = None
            if 'taker_base' in row and float(row['taker_base']) > 0:
                buy_v = float(row['taker_base'])
                sell_v = max(0.0, vol - buy_v)
            elif 'taker_buy_volume' in row and float(row['taker_buy_volume']) > 0:
                buy_v = float(row['taker_buy_volume'])
                sell_v = max(0.0, vol - buy_v)
            elif 'taker_quote' in row and float(row['taker_quote']) > 0 and 'quote_volume' in row and float(row.get('quote_volume', 0.0)) > 0:
                buy_ratio = float(row['taker_quote']) / float(row['quote_volume'])
                buy_v = vol * buy_ratio
                sell_v = max(0.0, vol - buy_v)

            if buy_v is None:
                o = float(row.get('open', 0.0))
                c = float(row.get('close', 0.0))
                h = float(row.get('high', 0.0))
                l = float(row.get('low', 0.0))
                rng = h - l
                if rng > 0:
                    z = (c - o) / rng
                    buy_ratio = np.clip(0.5 + (z * 0.4), 0.05, 0.95)
                else:
                    buy_ratio = 0.5
                buy_v = vol * buy_ratio
                sell_v = vol * (1.0 - buy_ratio)

            abs_order_imbalance += abs(buy_v - sell_v)

        if total_v > 0:
            raw_vpin = abs_order_imbalance / total_v
        else:
            raw_vpin = 0.30

        if recent_cvd and isinstance(recent_cvd, dict):
            ratio_60s = float(recent_cvd.get('ratio_60s', 50.0))
            micro_imb = abs(ratio_60s - 50.0) / 50.0
            vpin_score = float(np.clip((raw_vpin * 0.70) + (micro_imb * 0.30), 0.05, 0.95))
        else:
            vpin_score = float(np.clip(raw_vpin, 0.05, 0.95))

        vpin_score = round(vpin_score, 3)

        if vpin_score >= 0.55:
            tox = 'EXTREME'
            desc = f'⚠️ Aşırı Toksik Akış (VPIN: %{vpin_score*100:.1f} >= %55). Konsolidasyon patlamak üzere!'
            is_toxic = True
            is_range_veto = True
        elif vpin_score >= 0.38:
            tox = 'MODERATE'
            desc = f'⚡ Yükselen Kurumsal Toksisite (VPIN: %{vpin_score*100:.1f})'
            is_toxic = False
            is_range_veto = False
        else:
            tox = 'LOW'
            desc = f'🟢 Dengeli & Sakin Piyasa (VPIN: %{vpin_score*100:.1f})'
            is_toxic = False
            is_range_veto = False

        return {
            'vpin_score': vpin_score,
            'toxicity_level': tox,
            'is_toxic_flow': is_toxic,
            'is_range_veto_alert': is_range_veto,
            'vpin_desc': desc
        }
    except Exception:
        return res


def calculate_kyles_lambda(df_candles: pd.DataFrame, current_candle: dict = None) -> dict:
    """
    12. ALBERT KYLE & YAKOV AMIHUD — Kyle's Lambda (İllikitlik & Fiyat Etki Oranı):
    - Birim işlem hacmi başına fiyatın ne kadar kaydığını ölçer (Lambda = |Return| / DollarVolume).
    - HAVA CEBİ TUZAĞI (Illiquidity Vacuum Trap): Eğer fiyat sert hareket etmiş ama hacim cücük kalmışsa (Lambda >= 2.5x),
      bu arkası boş sahte bir kırılımdır; asla kırılıma atlanmaz.
    - LİKİT GENİŞLEME: Düşük Lambda + Yüksek Hacim = Gerçek Kurumsal Trend.
    """
    res = {
        'lambda_ratio': 1.0,
        'is_vacuum_trap': False,
        'is_liquid_expansion': False,
        'lambda_regime': 'NORMAL',
        'desc': 'Normal Likidite Dağılımı'
    }
    if df_candles is None or not isinstance(df_candles, pd.DataFrame) or len(df_candles) < 5:
        return res

    try:
        sub = df_candles.tail(20).copy()
        lambdas = []
        for _, row in sub.iterrows():
            c = float(row.get('close', 1.0))
            o = float(row.get('open', 1.0))
            v = float(row.get('volume', 0.0))
            usd_vol = c * v
            if usd_vol > 500.0 and c > 0 and o > 0:
                ret = abs(c - o) / o
                lamb = (ret / usd_vol) * 1e6
                lambdas.append(lamb)

        if not lambdas:
            return res

        mean_lambda = float(np.mean(lambdas))
        if mean_lambda <= 0:
            mean_lambda = 1e-6

        cur_candle = current_candle or (df_candles.iloc[-1].to_dict() if len(df_candles) > 0 else {})
        cur_c = float(cur_candle.get('close', 1.0))
        cur_o = float(cur_candle.get('open', 1.0))
        cur_v = float(cur_candle.get('volume', 0.0))
        cur_usd_vol = cur_c * cur_v
        cur_ret = abs(cur_c - cur_o) / cur_o if cur_o > 0 else 0.0

        # VDA-30: Canli acik mumun gecen suresine gore hacim ekstrapolasyonu yapilir
        # Henuz acilmis (orn. 15. saniyesindeki) mumun sig hacmi 300 saniyelik gecmis barlarla
        # kiyaslanip sahte 'Hava Cebi Tuzagi' (Vacuum Trap) uretmesi engellenir.
        candle_ts = float(cur_candle.get('timestamp', 0.0))
        now_ts = time.time()
        elapsed_sec = 300.0
        if candle_ts > 1e11:  # ms timestamp
            c_sec = candle_ts / 1000.0
            diff_s = now_ts - c_sec
            if 0 < diff_s < 300.0:
                elapsed_sec = max(15.0, diff_s)

        projected_usd_vol = cur_usd_vol * (300.0 / elapsed_sec)

        if projected_usd_vol > 500.0:
            cur_lambda = (cur_ret / projected_usd_vol) * 1e6
        else:
            cur_lambda = mean_lambda

        lambda_ratio = round(cur_lambda / mean_lambda, 2)

        # 1. Hava Cebi Tuzağı (En az 60s geçmiş olmalı ve projekte edilmiş hacim sığ olmalı)
        is_vacuum = (lambda_ratio >= 2.5 and cur_ret >= 0.0030 and elapsed_sec >= 60.0)

        # 2. Likit Kurumsal Genişleme (Hacim yüksek, Lambda normal veya düşük, fiyat kaymıyor)
        is_liquid = (lambda_ratio <= 1.2 and cur_ret >= 0.0025)

        if is_vacuum:
            regime = 'ILLIQUIDITY_VACUUM_TRAP'
            desc = f'🌪️ Hava Cebi Tuzağı: İllikitlik oranı {lambda_ratio:.1f}x normal. Sığ tahtada sahte sıçrama tespiti!'
        elif is_liquid:
            regime = 'LIQUID_EXPANSION'
            desc = f'🌊 Derin Likit Genişleme: Kurumsal gerçek hacim (Lambda: {lambda_ratio:.2f}x)'
        else:
            regime = 'NORMAL'
            desc = f'⚪ Standart Tahta Likiditesi (Lambda: {lambda_ratio:.2f}x)'

        return {
            'lambda_ratio': lambda_ratio,
            'is_vacuum_trap': is_vacuum,
            'is_liquid_expansion': is_liquid,
            'lambda_regime': regime,
            'desc': desc
        }
    except Exception:
        return res


def calculate_deribit_gex(options_book: list, spot_price: float = None) -> dict:
    """
    13. DERIBIT GEX (GAMMA EXPOSURE) & OPSİYON REJİM HAKEMİ
    - Deribit kurumsal BTC/ETH opsiyon tahtasından Call ve Put GEX hesaplar.
    - Black-Scholes Gamma:
        d1 = [ln(S/K) + (0.5 * sigma^2 * tau)] / (sigma * sqrt(tau))
        Gamma = exp(-0.5 * d1^2) / (S * sigma * sqrt(2*pi*tau))
    - GEX ($ per 1% price move):
        Call GEX = +Gamma * S^2 * OI * 0.01
        Put GEX  = -Gamma * S^2 * OI * 0.01
        Net GEX  = Sum(Call GEX) - Sum(Put GEX)
    - Rejimler:
        * Net GEX > 0: POSITIVE_GAMMA_PIN (Volatilite Sönümleyici / Yatay Mıknatıs)
        * Net GEX < 0: NEGATIVE_GAMMA_EXPLOSION (Volatilite Hızlandırıcı / Trend Kırılımı)
    """
    res = {
        'net_gex': 0.0,
        'call_gex': 0.0,
        'put_gex': 0.0,
        'put_call_ratio': 1.0,
        'gex_regime': 'NEUTRAL',
        'is_pinning_regime': False,
        'is_explosion_regime': False,
        'gamma_flip_strike': 0.0,
        'desc': '⚪ Nötr Gamma Rejimi'
    }
    if not options_book or not isinstance(options_book, list):
        return res

    try:
        from datetime import datetime, timezone
        now_time = datetime.now(timezone.utc)

        # 1. Spot fiyat tespiti
        if not spot_price or spot_price <= 0:
            underlying_prices = [float(item.get('underlying_price', 0)) for item in options_book if item.get('underlying_price')]
            spot_price = float(np.median(underlying_prices)) if underlying_prices else 0.0

        if spot_price <= 0:
            return res

        calls_gex = 0.0
        puts_gex = 0.0
        total_call_oi = 0.0
        total_put_oi = 0.0
        strikes_gex = {}

        for item in options_book:
            name = item.get('instrument_name', '')
            parts = name.split('-')
            if len(parts) < 4:
                continue

            strike = float(parts[2])
            opt_type = parts[3].upper()
            oi = float(item.get('open_interest', 0.0))
            if oi <= 0:
                continue

            iv_pct = float(item.get('mark_iv', 50.0))
            sigma = max(0.10, iv_pct / 100.0)

            # Vadeye kalan süre (yıl)
            expiry_str = parts[1]
            try:
                expiry_dt = datetime.strptime(expiry_str, '%d%b%y').replace(tzinfo=timezone.utc)
                diff_sec = (expiry_dt - now_time).total_seconds()
                tau = max(1.0 / 365.25, diff_sec / (365.25 * 86400.0))
            except Exception:
                tau = 30.0 / 365.25

            # Black-Scholes d1 ve Gamma
            denom = sigma * np.sqrt(tau)
            if denom <= 0:
                continue
            d1 = (np.log(spot_price / strike) + 0.5 * (sigma ** 2) * tau) / denom
            gamma = (np.exp(-0.5 * (d1 ** 2)) / (spot_price * denom * np.sqrt(2.0 * np.pi)))

            # GEX (USD / %1 fiyat hareketi)
            dollar_gamma = gamma * (spot_price ** 2) * oi * 0.01

            if strike not in strikes_gex:
                strikes_gex[strike] = 0.0

            if opt_type == 'C':
                calls_gex += dollar_gamma
                total_call_oi += oi
                strikes_gex[strike] += dollar_gamma
            elif opt_type == 'P':
                puts_gex += dollar_gamma
                total_put_oi += oi
                strikes_gex[strike] -= dollar_gamma

        net_gex = calls_gex - puts_gex
        pcr = round(total_put_oi / total_call_oi, 3) if total_call_oi > 0 else 1.0

        # VDA-27: Gamma Flip Seviyesi (Net Gamma'nın sıfırı kestiği gerçek kullanım fiyatı)
        sorted_strikes = sorted(strikes_gex.items(), key=lambda x: x[0])
        flip_strike = spot_price
        zero_crossings = []

        # 1. Kümülatif Gamma sıfır kesişim adayları
        cum_gex = 0.0
        cum_series = []
        for st, g_val in sorted_strikes:
            cum_gex += g_val
            cum_series.append((st, cum_gex))

        for i in range(len(cum_series) - 1):
            st1, c1 = cum_series[i]
            st2, c2 = cum_series[i + 1]
            if (c1 <= 0 and c2 > 0) or (c1 >= 0 and c2 < 0):
                interp_st = st1 + (0.0 - c1) / (c2 - c1) * (st2 - st1)
                zero_crossings.append(interp_st)

        # 2. Strike-bazlı Net Gamma sıfır kesişim adayları
        for i in range(len(sorted_strikes) - 1):
            st1, g1 = sorted_strikes[i]
            st2, g2 = sorted_strikes[i + 1]
            if (g1 <= 0 and g2 > 0) or (g1 >= 0 and g2 < 0):
                interp_st = st1 + (0.0 - g1) / (g2 - g1) * (st2 - st1)
                zero_crossings.append(interp_st)

        if zero_crossings:
            # Spot fiyata en yakın gerçekçi sıfır kesişim noktasını seç
            flip_strike = min(zero_crossings, key=lambda s: abs(s - spot_price))
            flip_strike = round(float(flip_strike), 2)

        tot_abs = (calls_gex + puts_gex)
        rel_bias = net_gex / tot_abs if tot_abs > 0 else 0.0

        if rel_bias > 0.05:
            regime = 'POSITIVE_GAMMA_PIN'
            is_pinning = True
            is_exploding = False
            desc = f"🟩 Pozitif GEX (+${net_gex/1e6:.1f}M, PCR: {pcr:.2f}): Volatilite sönümlü, piyasa yapıcılar yatay mıknatıs modunda (S3/R3 & nPOC Scalp Desteklenir)."
        elif rel_bias < -0.05:
            regime = 'NEGATIVE_GAMMA_EXPLOSION'
            is_pinning = False
            is_exploding = True
            desc = f"🟥 Negatif GEX (-${abs(net_gex)/1e6:.1f}M, PCR: {pcr:.2f}): Volatilite hızlandırıcı, kurumsal delta-hedge trend kırılımını besliyor (Breakout Teşvik Edilir)."
        else:
            regime = 'NEUTRAL_GAMMA'
            is_pinning = False
            is_exploding = False
            desc = f"⚪ Dengeli Gamma ($0.0M, PCR: {pcr:.2f}): Normal piyasa dengesi."

        return {
            'net_gex': round(net_gex, 2),
            'call_gex': round(calls_gex, 2),
            'put_gex': round(puts_gex, 2),
            'put_call_ratio': pcr,
            'gex_regime': regime,
            'is_pinning_regime': is_pinning,
            'is_explosion_regime': is_exploding,
            'gamma_flip_strike': float(flip_strike),
            'desc': desc
        }
    except Exception as e:
        res['desc'] = f'⚪ GEX Hesaplama İstisnası: {e}'
        return res


def calculate_hawkes_avalanche(
    liquidations: list,
    current_time: float = None,
    alpha: float = 0.85,
    beta: float = 0.12,
    lookback_sec: float = 120.0
) -> dict:
    """
    14. HAWKES KENDİ KENDİNİ BESLEYEN TASFİYE ÇIĞI (SELF-EXCITING LIQUIDATION AVALANCHE)
    - Finansal mikro-yapıda kaldıraç tasfiyelerinin zincirleme patlamasını modeller.
    - Yoğunluk Fonksiyonu:
        lambda(t) = mu + sum_{t_i < t} alpha * w_i * exp(-beta * (t - t_i))
    - Dallanma Oranı (Branching Ratio) eta = alpha / beta:
        * eta >= 0.80 -> AVALANCHE_RUNNER_ACTIVE: Tasfiye çığı devam ediyor, TP2'de çıkma, kârı sür!
        * eta < 0.40  -> AVALANCHE_EXHAUSTED: Çığ durdu, tasfiye yakıtı tükendi, tepe fitilde kârı kilitle.
        * eta < 0.30  -> QUIET_FLOW: Çığ yok, standart scalp.
    """
    res = {
        'branching_ratio_eta': 0.15,
        'intensity': 0.05,
        'regime': 'QUIET_FLOW',
        'is_avalanche_active': False,
        'is_avalanche_exhausted': False,
        'avalanche_side': 'NONE',
        'long_liq_usd': 0.0,
        'short_liq_usd': 0.0,
        'desc': '⚪ Durgun Tasfiye Akışı'
    }
    if not liquidations:
        return res

    try:
        now_ts = float(current_time if current_time is not None else time.time())
        cutoff = now_ts - lookback_sec

        valid_events = []
        long_usd = 0.0
        short_usd = 0.0

        for item in liquidations:
            if isinstance(item, dict):
                t = float(item.get('timestamp', 0.0))
                usd = float(item.get('usd_size', 1000.0))
                side = item.get('side', 'LONG')
            elif isinstance(item, (int, float)):
                t = float(item)
                usd = 1000.0
                side = 'LONG'
            else:
                continue

            if t >= cutoff and t <= now_ts:
                valid_events.append((t, usd, side))
                if side == 'LONG':
                    long_usd += usd
                else:
                    short_usd += usd

        cnt = len(valid_events)
        if cnt == 0:
            return res

        mu = 0.05
        decay_sum = 0.0
        weights = []

        for t, usd, _ in valid_events:
            dt = max(0.0, now_ts - t)
            w = float(np.clip(np.sqrt(usd / 10000.0), 0.5, 3.0))
            weights.append(w)
            decay_sum += alpha * w * np.exp(-beta * dt)

        cur_intensity = mu + decay_sum

        # VDA-28: Hawkes dallanma orani (Branching Ratio) teorik standardi:
        # eta = (alpha / beta) * mean_weight (anlik yogunluk ile yapay carpim kaldirildi)
        mean_w = float(np.mean(weights)) if weights else 1.0
        base_eta = (alpha / (beta * 10.0))
        eta = float(np.clip(base_eta * mean_w, 0.05, 1.45))

        if long_usd >= short_usd * 1.5 and long_usd > 5000.0:
            av_side = 'LONG_LIQ_DUMP_CASCADE'
        elif short_usd >= long_usd * 1.5 and short_usd > 5000.0:
            av_side = 'SHORT_SQUEEZE_PUMP_CASCADE'
        elif cnt >= 3:
            av_side = 'DUAL_VOLATILITY_BURST'
        else:
            av_side = 'NONE'

        is_active = (eta >= 0.75 and cur_intensity >= 0.30)
        is_exhausted = (not is_active and cnt >= 4 and cur_intensity <= 0.15)

        if is_active:
            regime = 'AVALANCHE_RUNNER_ACTIVE'
            desc = f"⚡ Hawkes Tasfiye Çığı Aktif (eta={eta:.2f}, Yoğunluk={cur_intensity:.2f}): Zincirleme tasfiyeler trendi besliyor ({av_side}). TP2 sonrası kârı sür!"
        elif is_exhausted:
            regime = 'AVALANCHE_EXHAUSTED'
            desc = f"🛑 Hawkes Çığı Sönümlendi (eta={eta:.2f}): Tasfiye yakıtı tükendi. Dönüş fitilinde acil kâr kilitle!"
        else:
            regime = 'QUIET_FLOW'
            desc = f"⚪ Standart Tasfiye Akışı (eta={eta:.2f}, Yoğunluk={cur_intensity:.2f})"

        return {
            'branching_ratio_eta': round(eta, 2),
            'intensity': round(cur_intensity, 3),
            'regime': regime,
            'is_avalanche_active': is_active,
            'is_avalanche_exhausted': is_exhausted,
            'avalanche_side': av_side,
            'long_liq_usd': round(long_usd, 2),
            'short_liq_usd': round(short_usd, 2),
            'desc': desc
        }
    except Exception as e:
        res['desc'] = f'⚪ Hawkes Hesaplama İstisnası: {e}'
        return res


# =====================================================================
# 14. ASTROQUANT: APOLLO KALMAN DURUM-UZAY FİLTRESİ (STATE-SPACE FILTER)
# =====================================================================
def calculate_kalman_state(
    prices,
    wick_ratios=None,
    q: float = 1e-4,
    r0: float = 1e-2,
    wick_penalty_mult: float = 5.0
) -> dict:
    """
    NASA Apollo Durum-Uzay (State-Space) Filtresi.
    Ham piyasa fiyatindaki fitil ve likidasyon avi gurultusunu (measurement noise)
    dinamik olarak ayiklar ve gercek piyasa durumunu (equilibrium state) hesaplar.
    
    Ölçüm Kovaryansı: R_t = R0 * (1.0 + wick_penalty_mult * wick_ratio^2)
    Gürültülü fitillerde R_t büyür -> Kalman fiyata inanmaz, çizgisi bükülmez.
    Hacimli gerçek kırılımlarda R_t küçülür -> Kalman tam gaz fiyata yapışır.
    """
    if prices is None or len(prices) == 0:
        return {
            'clean_price': 0.0,
            'state_variance': 0.0,
            'z_score': 0.0,
            'noise_dampening_pct': 0.0,
            'raw_price': 0.0
        }
        
    prices = np.asarray(prices, dtype=float)
    n = len(prices)
    if n == 1:
        return {
            'clean_price': float(prices[0]),
            'state_variance': 1.0,
            'z_score': 0.0,
            'noise_dampening_pct': 0.0,
            'raw_price': float(prices[0])
        }
        
    if wick_ratios is None or len(wick_ratios) != n:
        wick_ratios = np.zeros(n, dtype=float)
    else:
        wick_ratios = np.asarray(wick_ratios, dtype=float)
        
    x = float(prices[0])
    p = 1.0
    
    for t in range(n):
        # Tahmin (Predict)
        x_pred = x
        p_pred = p + q
        
        # Dinamik Ölçüm Gürültüsü (Update with Dynamic Wick Noise)
        w_rat = max(0.0, min(5.0, float(wick_ratios[t])))
        r_t = r0 * (1.0 + wick_penalty_mult * (w_rat ** 2))
        
        # Kalman Kazancı (Kalman Gain)
        k_t = p_pred / (p_pred + r_t) if (p_pred + r_t) > 0 else 0.5
        
        # Durum Güncellemesi (State Update)
        x = x_pred + k_t * (float(prices[t]) - x_pred)
        p = (1.0 - k_t) * p_pred
        
    raw_cur = float(prices[-1])
    clean_p = float(x)
    std_p = math.sqrt(max(1e-8, p))
    z_score = float((raw_cur - clean_p) / std_p) if std_p > 0 else 0.0
    
    # Gürültü Sönümleme Oranı (%)
    diff_raw = abs(raw_cur - prices[-2]) if n >= 2 else 0.0
    diff_clean = abs(clean_p - prices[-2]) if n >= 2 else 0.0
    damp_pct = round(max(0.0, (1.0 - (diff_clean / diff_raw)) * 100.0), 1) if diff_raw > 1e-8 else 0.0
    
    return {
        'clean_price': round(clean_p, 6),
        'state_variance': round(float(p), 6),
        'z_score': round(z_score, 2),
        'noise_dampening_pct': damp_pct,
        'raw_price': raw_cur
    }


# =====================================================================
# 15. ASTROQUANT: SPACEX FALCON 9 PID KÂR VE STOP KONTROLÖRÜ
# =====================================================================
def calculate_pid_stop_level(
    entry_price: float,
    current_price: float,
    side: str,
    peak_mfe_roe: float,
    mfe_series: list = None,
    atr_pct: float = 0.50,
    leverage: int = 5,
    kp: float = 0.50,
    ki: float = 0.05,
    kd: float = 0.35,
    min_mfe_trigger: float = 2.0,
    noise_floor_atr_mult: float = 1.5
) -> dict:
    """
    SpaceX Falcon 9 Uçuş Kontrol Dinamik Kâr Sürücüsü (PID Controller).
    Açık pozisyon kârdayken (MFE >= 2.0% ROE) stopu roket hassasiyetinde arkasından çeker.
    
    3 KATMANLI GÜVENLİK KALKANI:
    1. D > 0 (Momentum canlı): Roket koşarken stop gevşek tutulur (büyük trend kaçmaz).
    2. D <= 0 (Momentum tükendi): Tepe fitilinde stop anında zirvenin %60 - %80'ine basamaklanır.
    3. Noise Floor (1.5x ATR): Stop fiyata asla 1.5x ATR'den daha yakın yapılamaz (gürültüde erken infaz önlenir).
    """
    side = str(side).upper()
    entry_p = float(entry_price)
    cur_p = float(current_price)
    peak_mfe = float(max(0.0, peak_mfe_roe))
    lev = int(leverage) if leverage > 0 else 5
    
    if entry_p <= 0 or cur_p <= 0:
        return {'is_engaged': False, 'proposed_stop': 0.0, 'reason': 'Geçersiz fiyat'}
        
    # Anlık ROE (%)
    cur_roe = ((cur_p - entry_p) / entry_p * 100.0 * lev) if side == 'LONG' else ((entry_p - cur_p) / entry_p * 100.0 * lev)
    
    # PID Henüz Devreye Girmedi (Kâr eşiği < %2.0 ROE)
    if peak_mfe < min_mfe_trigger:
        return {
            'is_engaged': False,
            'proposed_stop': 0.0,
            'cur_roe': round(cur_roe, 2),
            'peak_mfe': round(peak_mfe, 2),
            'reason': f'MFE (%{peak_mfe:.1f}) eşiğin (<%{min_mfe_trigger:.1f}) altında'
        }
        
    # MFE Geçmişi ve Türev Hesabı
    series = [float(x) for x in (mfe_series or []) if x is not None]
    if not series or series[-1] != peak_mfe:
        series.append(peak_mfe)
        
    # P: Anlık Hata (Zirveye olan mesafe)
    err = peak_mfe - cur_roe
    
    # I: Kârda Biriken Enerji (Kümülatif toplam)
    integral = sum(series[-10:]) * 0.1
    
    # D: Momentum İvmesi (Son 2-3 okuma arasındaki değişim)
    if len(series) >= 2:
        deriv = series[-1] - series[-2]
    else:
        deriv = 0.0
        
    # PID Kontrol Çıktısı (Uçuş Stabilizasyonu)
    u_control = (kp * err) + (ki * integral) + (kd * deriv)
    
    # Kademeli Asimetrik Kilit Oranı
    if peak_mfe >= 8.0:
        base_capture = 0.80  # Zirve koşusu: %80 kilit
    elif peak_mfe >= 4.0:
        base_capture = 0.70  # Orta koşu: %70 kilit
    else:
        base_capture = 0.60  # Erken kâr: %60 kilit (geniş nefes alanı)
        
    # Türev Kalkanı: Eğer ivme halen pozitifse (D > 0), nefes payı aç (%10 gevşet)
    # Eğer ivme durduysa (D <= 0), kârı sıkı kilitle (+%5 sıkılaştır)
    if deriv > 0.05:
        target_capture = max(0.50, base_capture - 0.10)
        mode = "🚀 İvme Canlı (Pozisyon Koşuyor - Geniş Nefes)"
    else:
        target_capture = min(0.85, base_capture + 0.05)
        mode = "🛑 İvme Tükendi (Zirve Kilidi Aktif)"
        
    # Hedef Kilit ROE
    target_locked_roe = peak_mfe * target_capture
    
    # Fiyat karşılığı
    price_pct_gain = (target_locked_roe / lev) / 100.0
    if side == 'LONG':
        raw_stop = entry_p * (1.0 + price_pct_gain)
    else:
        raw_stop = entry_p * (1.0 - price_pct_gain)
        
    # ── GÜRÜLTÜ TABANI (NOISE FLOOR) KALKANI ──
    # Stop mesafesi anlık fiyata 1.5x ATR'den daha yakın olamaz!
    atr_val = (atr_pct / 100.0) if atr_pct > 0 else 0.0050
    noise_buffer = entry_p * atr_val * noise_floor_atr_mult
    
    if side == 'LONG':
        # Long için stop, anlık fiyatın (cur_p - noise_buffer) üstüne geçemez (fiyata yapışamaz)
        safe_stop = min(raw_stop, cur_p - noise_buffer)
        # Ama girişin üstünde kalmalı
        final_stop = max(entry_p * 1.0010, safe_stop)
    else:
        # Short için stop, anlık fiyatın (cur_p + noise_buffer) altına inemez
        safe_stop = max(raw_stop, cur_p + noise_buffer)
        final_stop = min(entry_p * 0.9990, safe_stop)
        
    return {
        'is_engaged': True,
        'proposed_stop': round(final_stop, 6),
        'locked_roe': round(target_locked_roe, 2),
        'peak_mfe': round(peak_mfe, 2),
        'cur_roe': round(cur_roe, 2),
        'capture_ratio': round(target_capture, 2),
        'derivative': round(deriv, 3),
        'mode': mode,
        'noise_floor_applied': bool(safe_stop != raw_stop)
    }


def calculate_ornstein_uhlenbeck_params(prices, anchor_price=None, dt_minutes=5.0, min_half_life=15.0, max_half_life=180.0):
    """
    Ornstein-Uhlenbeck (O-U) Stokastik Süreci ile Ortalama Dönüş Hızı (theta)
    ve Matematiksel Yarılanma Ömrü (Half-Life - tau) Hesabı.
    
    dX_t = theta * (mu - X_t) dt + sigma * dW_t
    
    Euler-Maruyama & AR(1) OLS Çözümü:
    X_t = a + b * X_{t-1} + e_t
    b = exp(-theta * dt) => theta = -ln(b) / dt
    tau (half-life) = ln(2) / theta
    """
    default_res = {
        'is_valid': False,
        'is_mean_reverting': True,
        'theta': 0.0231,              # ~30 dk yarılanma varsayılanı
        'half_life_min': 30.0,
        'half_life_candles': 6.0,
        'equilibrium_mu': float(anchor_price or (prices[-1] if prices else 0.0)),
        'r_squared': 0.50,
        'sigma': 0.005,
        'regime': 'MODERATE_MEAN_REVERTING'
    }
    
    if prices is None or len(prices) < 20:
        return default_res
        
    try:
        arr = np.array(prices, dtype=float)
        # NaN / Inf temizliği
        arr = arr[np.isfinite(arr)]
        if len(arr) < 20:
            return default_res
            
        cur_p = arr[-1]
        mu = float(anchor_price) if (anchor_price is not None and anchor_price > 0) else float(np.mean(arr))
        
        # Sapma serisi: Log-sapma oransal olarak ölçek bağımsızdır
        # X_t = ln(P_t / mu)
        if mu <= 0:
            return default_res
            
        series = np.log(arr / mu)
        
        # OLS AR(1): y = series[1:], x = series[:-1]
        x = series[:-1]
        y = series[1:]
        
        var_x = np.var(x)
        if var_x < 1e-12:
            return default_res
            
        cov_xy = np.cov(x, y)[0, 1]
        b = cov_xy / var_x
        a = np.mean(y) - b * np.mean(x)
        
        # R-kare hesabı
        residuals = y - (a + b * x)
        ss_res = np.sum(residuals ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r2 = max(0.0, min(1.0, 1.0 - (ss_res / max(1e-12, ss_tot))))
        
        # Difüzyon gürültüsü sigma (yıllıklandırılmamış, mum bazlı)
        sigma = float(np.std(residuals))
        
        # b katsayısı analizi
        if b >= 0.9999 or b <= 0.0:
            # Seri ortalamaya dönmüyor (Random Walk veya Güçlü Trend patlaması)
            return {
                'is_valid': True,
                'is_mean_reverting': False,
                'theta': 0.001,
                'half_life_min': float(max_half_life),
                'half_life_candles': float(max_half_life / dt_minutes),
                'equilibrium_mu': mu,
                'r_squared': round(float(r2), 3),
                'sigma': round(sigma, 5),
                'regime': 'TRENDING_DIVERGENT'
            }
            
        # Normal Mean-Reversion durumu:
        # theta = -ln(b) / dt
        theta = -np.log(b) / float(dt_minutes)
        if theta <= 1e-6:
            theta = 1e-6
            
        # tau = ln(2) / theta
        tau_min = np.log(2.0) / theta
        
        # Dinamik sınırlama (min_half_life - max_half_life aralığı)
        clamped_tau = max(float(min_half_life), min(float(max_half_life), float(tau_min)))
        tau_candles = clamped_tau / float(dt_minutes)
        
        # Rejim sınıflaması
        if clamped_tau <= 25.0:
            regime = 'STRONG_MEAN_REVERTING'
        elif clamped_tau <= 50.0:
            regime = 'MODERATE_MEAN_REVERTING'
        elif clamped_tau <= 100.0:
            regime = 'SLOW_MEAN_REVERTING'
        else:
            regime = 'EXTENDED_MEAN_REVERTING'
            
        return {
            'is_valid': True,
            'is_mean_reverting': True,
            'theta': round(float(theta), 5),
            'half_life_min': round(clamped_tau, 1),
            'half_life_candles': round(tau_candles, 1),
            'equilibrium_mu': round(mu, 6),
            'r_squared': round(float(r2), 3),
            'sigma': round(sigma, 5),
            'regime': regime
        }
    except Exception as e:
        return default_res


# ═════════════════════════════════════════════════════════════════════════════
# 16. BORSA NET GİRİŞ/ÇIKIŞ AKIŞI (NETFLOW) VE ON-CHAIN BALİNA METRİKLERİ
# ═════════════════════════════════════════════════════════════════════════════

def calculate_netflow_zscore(flow_history: list, current_flow: float) -> dict:
    """
    Borsa Net Akışı (Netflow = Inflow - Outflow) için İstatistiksel Z-Skor Hesabı.
    Z = (X - mu) / sigma
    
    Z >= +2.0: Borsa Giriş Patlaması (DUMP UYARISI / Mal Boşaltma)
    Z <= -2.0: Borsa Çıkış Patlaması (ARZ ŞOKU / Soğuk Cüzdan Akümülasyonu)
    """
    default_res = {
        'z_score': 0.0,
        'mean_flow': float(current_flow),
        'std_flow': 0.0,
        'regime': 'BALANCED_FLOW',
        'is_dump_risk': False,
        'is_accumulation': False,
        'is_anomaly': False
    }
    if not flow_history or len(flow_history) < 3:
        return default_res

    try:
        arr = np.array(flow_history, dtype=float)
        arr = arr[np.isfinite(arr)]
        if len(arr) < 3:
            return default_res

        mu = float(np.mean(arr))
        sigma = float(np.std(arr))
        # Kuant Gürültü Tabanı (Finansal Varyans Regülarizasyonu):
        # Kripto piyasasında mikro-akış gürültüsünün ($1k - $50k) sahte Z-skor patlaması yaratmasını önlemek için
        # asgari standart sapma tabanı $100,000 USD olarak uygulanır.
        min_sigma = max(100_000.0, sigma)

        z = (float(current_flow) - mu) / min_sigma
        z_clamped = max(-5.0, min(5.0, z))

        # Gerçek kurumsal balina tehdidi için hem Z-skoru (>= 2.0σ) hem de asgari $250,000 net akış şarttır.
        # $10,000 veya $7,000 gibi mikro akışlar asla dump riski veya short squeeze olarak etiketlenemez.
        has_whale_economic_size = abs(float(current_flow)) >= 250_000.0

        if z_clamped >= 2.0 and has_whale_economic_size:
            regime = 'INFLOW_SURGE_DUMP_RISK'
            dump_risk = True
            accum = False
            anomaly = True
        elif z_clamped <= -2.0 and has_whale_economic_size:
            regime = 'OUTFLOW_SURGE_ACCUMULATION'
            dump_risk = False
            accum = True
            anomaly = True
        elif z_clamped >= 1.0 or (z_clamped >= 0.5 and float(current_flow) >= 100_000.0):
            regime = 'MILD_INFLOW'
            dump_risk = False
            accum = False
            anomaly = False
        elif z_clamped <= -1.0 or (z_clamped <= -0.5 and float(current_flow) <= -100_000.0):
            regime = 'MILD_OUTFLOW'
            dump_risk = False
            accum = False
            anomaly = False
        else:
            regime = 'BALANCED_FLOW'
            dump_risk = False
            accum = False
            anomaly = False

        return {
            'z_score': round(float(z_clamped), 2),
            'mean_flow': round(mu, 2),
            'std_flow': round(sigma, 2),
            'regime': regime,
            'is_dump_risk': dump_risk,
            'is_accumulation': accum,
            'is_anomaly': anomaly
        }
    except Exception:
        return default_res


def classify_whale_transfer(
    symbol: str,
    amount_usd: float,
    volume_24h_usd: float = 0.0,
    tier: str = 'TIER_2',
    transfer_type: str = 'WALLET_TO_EXCHANGE',
    source: str = None
) -> dict:
    """
    On-Chain Balina Transferini veya Binance WebSocket aggTrade Blok Emirlerini
    Parite Kademesi (Tier-1, 2, 3) ve 24s Hacme Göre Sınıflandırır.
    
    Blok Emirler (aggTrade):
      Tier-1 (BTC, ETH, SOL, BNB): >= $1,000,000
      Tier-2 (Standart Altcoin):   >= $250,000
      Tier-3 (Meme & Düşük Liq):  >= $100,000

    On-Chain Mempool Transferler:
      Tier-1: >= $1,000,000
      Tier-2: >= $500,000
      Tier-3: >= $250,000

    Genel On-Chain Transferler:
      Tier-1: >= $5,000,000
      Tier-2: >= $2,000,000
      Tier-3: >= $500,000
    """
    tier_upper = str(tier).upper()
    t_type = str(transfer_type).upper()
    is_block = any(k in t_type for k in ['AGGTRADE', 'BLOCK', 'MARKET']) or (source == 'BINANCE_AGGTRADE')
    is_mempool = any(k in t_type for k in ['MEMPOOL', 'ONCHAIN']) or (source == 'ONCHAIN_MEMPOOL')

    if is_block:
        if '1' in tier_upper:
            tier_thresh = 1_000_000.0
        elif '3' in tier_upper:
            tier_thresh = 100_000.0
        else:
            tier_thresh = 250_000.0
    elif is_mempool:
        if '1' in tier_upper:
            tier_thresh = 1_000_000.0
        elif '3' in tier_upper:
            tier_thresh = 250_000.0
        else:
            tier_thresh = 500_000.0
    else:
        if '1' in tier_upper:
            tier_thresh = 5_000_000.0
        elif '3' in tier_upper:
            tier_thresh = 500_000.0
        else:
            tier_thresh = 2_000_000.0

    amt = float(amount_usd or 0.0)
    vol = float(volume_24h_usd or 0.0)
    vol_ratio = (amt / vol * 100.0) if vol > 0 else 0.0

    min_abs_thresh = 100_000.0 if is_block else 200_000.0
    is_whale = (amt >= tier_thresh) or (vol_ratio >= 2.0 and amt >= min_abs_thresh)

    severity = 'NORMAL'
    if is_whale:
        if amt >= tier_thresh * 3.0 or vol_ratio >= 5.0:
            severity = 'EXTREME'
        elif amt >= tier_thresh * 1.5 or vol_ratio >= 3.0:
            severity = 'HIGH'
        else:
            severity = 'MODERATE'

    # Transfer / Blok Emir yönü niyeti
    if 'WALLET_TO_EXCHANGE' in t_type or 'TO_EXCHANGE' in t_type or (is_block and ('SELL' in t_type or 'DUMP' in t_type)):
        intent = 'AGGRESSIVE_MARKET_DUMP' if is_block else ('DUMP_PREPARATION' if is_whale else 'DEPOSIT')
        is_dump_risk = is_whale
        is_bull_ammo = False
    elif 'EXCHANGE_TO_WALLET' in t_type or 'TO_WALLET' in t_type or (is_block and ('BUY' in t_type or 'PUMP' in t_type)):
        intent = 'AGGRESSIVE_MARKET_BUY' if is_block else ('COLD_STORAGE_ACCUMULATION' if is_whale else 'WITHDRAWAL')
        is_dump_risk = False
        is_bull_ammo = is_whale
    elif 'TREASURY' in t_type or 'STABLE' in t_type or 'MINT' in t_type:
        intent = 'FRESH_AMMUNITION_MINT'
        is_dump_risk = False
        is_bull_ammo = True
    else:
        intent = 'INTERNAL_TRANSFER'
        is_dump_risk = False
        is_bull_ammo = False

    return {
        'symbol': symbol,
        'amount_usd': round(amt, 2),
        'is_whale': is_whale,
        'severity': severity,
        'intent': intent,
        'vol_ratio_pct': round(vol_ratio, 2),
        'is_dump_risk': is_dump_risk,
        'is_bull_ammo': is_bull_ammo
    }


def calculate_ammunition_momentum(stablecoin_history: list) -> dict:
    """
    Borsalara Stabil Kripto (USDT/USDC) Rezerv Akış Momentumunu ve Boğa Yakıtını Hesaplarlar.
    Pozitif akış: Balinalar taze alım gücü (Cephane) yığıyor demektir.
    """
    default_res = {
        'bias': 'NEUTRAL',
        'delta_24h_usd': 0.0,
        'delta_pct': 0.0,
        'momentum_score': 0.0,
        'is_bullish_fuel': False
    }
    if not stablecoin_history or len(stablecoin_history) < 2:
        return default_res

    try:
        cur = float(stablecoin_history[-1])
        # Günlük zaman serisinde son 24 saatlik değişim: son gün ile bir önceki gün farkı
        prev_24h = float(stablecoin_history[-2]) if len(stablecoin_history) >= 2 else float(stablecoin_history[0])
        delta = cur - prev_24h
        pct = (delta / prev_24h * 100.0) if prev_24h > 0 else 0.0

        # 14 günlük makro akış trendi
        base_14d = float(stablecoin_history[0]) if len(stablecoin_history) >= 2 else prev_24h
        macro_delta_14d = cur - base_14d
        macro_pct_14d = (macro_delta_14d / base_14d * 100.0) if base_14d > 0 else 0.0

        # Son 24 saatte borsa rezervlerine >= $50M stabil para girdiyse boğa yakıtıdır
        if delta >= 50_000_000.0 or pct >= 0.15:
            bias = 'BULLISH_FUEL'
            is_fuel = True
            score = min(1.0, max(0.2, delta / 200_000_000.0))
        elif delta <= -50_000_000.0 or pct <= -0.15:
            bias = 'CAPITAL_DRAIN'
            is_fuel = False
            score = max(-1.0, min(-0.2, delta / 200_000_000.0))
        else:
            bias = 'NEUTRAL'
            is_fuel = False
            score = round(delta / 200_000_000.0, 3)

        return {
            'bias': bias,
            'delta_24h_usd': round(delta, 2),
            'delta_pct': round(pct, 3),
            'macro_pct_14d': round(macro_pct_14d, 3),
            'momentum_score': round(score, 3),
            'is_bullish_fuel': is_fuel
        }
    except Exception:
        return default_res

