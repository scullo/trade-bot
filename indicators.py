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

        return {
            "entropy_norm": ent_norm,
            "entropy_bid": round(ent_bid, 3),
            "entropy_ask": round(ent_ask, 3),
            "is_chaotic": ent_norm >= 0.88,
            "is_crystalline": ent_norm <= 0.60
        }
    except Exception:
        return {
            "entropy_norm": 0.70,
            "entropy_bid": 0.70,
            "entropy_ask": 0.70,
            "is_chaotic": False,
            "is_crystalline": False
        }


def calculate_hurst_exponent(price_series, min_lags: int = 10, max_lags: int = None) -> float:
    """
    2. BENOIT MANDELBROT — Hurst Üssü (H) ve Fraktal Rejim Dedektörü:
    - Rescaled Range (R/S) analiziyle zaman serisinin uzun dönem hafızasını ölçer.
    - H > 0.55: Kalıcı (Persistent / Trending) -> Breakout izinli.
    - H < 0.45: Ortalamaya Dönen (Anti-persistent / Mean-Reverting) -> Breakout TUZAK, Sekme oyna!
    - 0.45 <= H <= 0.55: Rastgele Yürüyüş (Brownian Motion / Gürültü).
    """
    try:
        if price_series is None or len(price_series) < 30:
            return 0.50

        ts = np.array(price_series, dtype=np.float64)
        n = len(ts)
        if max_lags is None:
            max_lags = min(n // 2, 50)
        if max_lags <= min_lags:
            max_lags = min_lags + 5

        lags = range(min_lags, max_lags)
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


def detect_iceberg_orders(executed_buy_usd: float, executed_sell_usd: float, top_bid_usd: float, top_ask_usd: float) -> dict:
    """
    3. KEN GRIFFIN — Gizli Likidite (Iceberg / Buzdağı) Radarı:
    - Son 60s gerçekleşen agresif taker hacmini tahtada görünen anlık derinliğe oranlar.
    - Ask Iceberg (Satıcı Buzdağı): executed_buy_usd / effective_ask_depth >= 3.5x
    - Bid Iceberg (Alıcı Buzdağı): executed_sell_usd / effective_bid_depth >= 3.5x
    """
    try:
        effective_ask_depth = max(2500.0, top_ask_usd * 3.0)
        effective_bid_depth = max(2500.0, top_bid_usd * 3.0)

        ask_ratio = round(min(50.0, float(executed_buy_usd / effective_ask_depth)), 2)
        bid_ratio = round(min(50.0, float(executed_sell_usd / effective_bid_depth)), 2)

        has_ask_iceberg = (ask_ratio >= 3.5 and executed_buy_usd >= 5000.0)
        has_bid_iceberg = (bid_ratio >= 3.5 and executed_sell_usd >= 5000.0)

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

        cur_vel = float(vel[-1])
        cur_acc = float(acc[-1])
        prev_acc = float(acc[-2])

        is_ex_top = False
        is_ex_bottom = False
        zero_cross = 'NONE'

        # Sıfır Geçişi Tespiti (Son 2 veri noktasında)
        if (prev_acc > 0 and cur_acc <= 0) or (len(acc) >= 3 and acc[-3] > 0 and acc[-2] <= 0):
            zero_cross = 'BULL_EXHAUSTION_TOP'
            is_ex_top = True
        elif (prev_acc < 0 and cur_acc >= 0) or (len(acc) >= 3 and acc[-3] < 0 and acc[-2] >= 0):
            zero_cross = 'BEAR_EXHAUSTION_BOTTOM'
            is_ex_bottom = True

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
            res['offense_reason'] = f'🧊 Kurumsal Alıcı Buzdağı Hücumu (${sup_lvl:.4f} Destek Arkası, {bid_ratio:.1f}x Emilim)'
            res['target_price'] = r3 if r3 > current_price else current_price * 1.015

        # 🔴 2. SHORT SNIPER HÜCUMU (Dirençte Satıcı Buzdağı Arkasına Saklanma)
        resist_levels = [lvl for lvl in [r3, above_npoc, p] if lvl > 0 and abs(current_price - lvl) / current_price <= 0.0035]
        if has_ask_iceberg and resist_levels and regime in ['REGIME_BEAR_TREND', 'REGIME_RANGING_PINGPONG']:
            res_lvl = min(resist_levels)
            res['is_sniper_sell'] = True
            res['tight_stop_dist_pct'] = 0.0022
            res['rr_multiplier'] = 1.8
            res['offense_reason'] = f'🧊 Kurumsal Satıcı Buzdağı Hücumu (${res_lvl:.4f} Direnç Arkası, {ask_ratio:.1f}x Emilim)'
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
        drift_bps = round(((micro_price - mid_price) / mid_price) * 10000.0, 2)

        bias = 'NEUTRAL'
        if drift_bps >= 1.2:
            bias = 'BULL_MICRO_DRIFT'
        elif drift_bps <= -1.2:
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
                if drift_bps > 0.5:
                    magnet_status = 'S3_MAGNET_REBOUND'
                    magnet_desc = f'🧲 Stoikov Destek Mıknatısı: Mikro-fiyat (${micro_price:.4f}, +{drift_bps} bps) yukarı çekiyor.'

            # Direnç tepki mıknatısı: Fiyat R3 yakınında ve mikro-fiyat ortalamaya (aşağı) çekiyor
            elif r3 > 0 and abs(current_price - r3) / current_price <= 0.0040:
                if drift_bps < -0.5:
                    magnet_status = 'R3_MAGNET_REJECTION'
                    magnet_desc = f'🧲 Stoikov Direnç Mıknatısı: Mikro-fiyat (${micro_price:.4f}, {drift_bps} bps) aşağı çekiyor.'

        return {
            'micro_price': round(micro_price, 6),
            'mid_price': round(mid_price, 6),
            'micro_drift_bps': drift_bps,
            'micro_bias': bias,
            'is_micro_bull': drift_bps >= 1.2,
            'is_micro_bear': drift_bps <= -1.2,
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

            # Taker alım hacmi varsa
            if 'taker_buy_volume' in row and float(row['taker_buy_volume']) > 0:
                buy_v = float(row['taker_buy_volume'])
                sell_v = max(0.0, vol - buy_v)
            else:
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

        if cur_usd_vol > 500.0:
            cur_lambda = (cur_ret / cur_usd_vol) * 1e6
        else:
            cur_lambda = mean_lambda

        lambda_ratio = round(cur_lambda / mean_lambda, 2)

        # 1. Hava Cebi Tuzağı (Fiyat %0.30'dan fazla sıçramış ama hacim sığ -> Lambda 2.5x üstü)
        is_vacuum = (lambda_ratio >= 2.5 and cur_ret >= 0.0030)

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




