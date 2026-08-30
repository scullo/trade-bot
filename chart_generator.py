import io, time, os, sys
from datetime import datetime, timezone, timedelta
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import pandas as pd

def generate_trade_chart_image(
    symbol: str,
    df_5m: pd.DataFrame,
    levels: dict = None,
    side: str = "LONG",
    entry_price: float = None,
    exit_price: float = None,
    entry_timestamp: float = None,
    soft_stop: float = None,
    tp1: float = None,
    tp2: float = None,
    avwap_high_points: list = None,
    avwap_low_points: list = None,
    trade_type: str = "SCALP",
    reason: str = "",
    is_closed: bool = False,
    net_pnl: float = None,
    roe_pct: float = None
) -> io.BytesIO:
    if df_5m is None or df_5m.empty:
        return None

    levels = levels or {}
    display_df = df_5m.iloc[-60:].copy().reset_index(drop=True)
    n_bars = len(display_df)

    # 1. Dark Theme
    fig, ax = plt.subplots(figsize=(15.0, 7.8), dpi=140)
    fig.patch.set_facecolor('#090d16')
    ax.set_facecolor('#0e1626')

    # Grid
    ax.grid(True, color='#1e293b', linestyle='--', linewidth=0.5, alpha=0.6)

    # Candlestick Drawing
    green_col = '#10b981'
    red_col = '#f43f5e'
    width = 0.65

    for i, r in display_df.iterrows():
        o = float(r['open'])
        c = float(r['close'])
        h = float(r['high'])
        l = float(r['low'])
        col = green_col if c >= o else red_col

        ax.plot([i, i], [l, h], color=col, linewidth=1.2, zorder=3)
        body_bottom = min(o, c)
        body_height = max(abs(c - o), (h - l) * 0.02)
        rect = patches.Rectangle((i - width/2, body_bottom), width, body_height, facecolor=col, edgecolor=col, zorder=4)
        ax.add_patch(rect)

    cur_p = float(display_df['close'].iloc[-1])
    min_y = float(display_df['low'].min())
    max_y = float(display_df['high'].max())

    all_prices = [min_y, max_y, cur_p]
    if entry_price and entry_price > 0: all_prices.append(entry_price)
    if exit_price and exit_price > 0: all_prices.append(exit_price)
    if soft_stop and soft_stop > 0: all_prices.append(soft_stop)
    if tp1 and tp1 > 0: all_prices.append(tp1)

    chart_min = min(all_prices)
    chart_max = max(all_prices)
    y_span = chart_max - chart_min if chart_max > chart_min else 1.0

    padded_min = chart_min - y_span * 0.14
    padded_max = chart_max + y_span * 0.24

    # Level Candidates
    cam = levels.get('camarilla', {})
    raw_levels = []

    def add_candidate(price, color, label, style='--', is_trade_level=False):
        if price and not np.isnan(price) and price > 0:
            p_val = float(price)
            if p_val >= padded_min and p_val <= padded_max:
                raw_levels.append({
                    'price': p_val,
                    'color': color,
                    'label': label,
                    'style': style,
                    'is_trade_level': is_trade_level
                })

    add_candidate(cam.get('R5'), '#f59e0b', 'R5 Hedef', '--')
    add_candidate(cam.get('R4'), '#fb923c', 'R4 Breakout', '-')
    add_candidate(levels.get('tepe_avwap'), '#f43f5e', 'Tepe AVWAP', '-')
    add_candidate(levels.get('mvah'), '#00e5ff', 'mVAH (Tavan)', '--')
    add_candidate(levels.get('above_npoc'), '#e2e8f0', 'Yukarı nPOC', ':')
    add_candidate(cam.get('R3'), '#f97316', 'R3 Direnç', ':')
    add_candidate(cam.get('P'), '#ffffff', 'Pivot P', '-')
    add_candidate(levels.get('mpoc'), '#c084fc', 'mPOC (Hacim)', '-')
    add_candidate(cam.get('S3'), '#f97316', 'S3 Destek', ':')
    add_candidate(levels.get('below_npoc'), '#e2e8f0', 'Aşağı nPOC', ':')
    add_candidate(levels.get('dip_avwap'), '#38bdf8', 'Dip AVWAP', '-')
    add_candidate(cam.get('S4'), '#10b981', 'S4 Breakdown', '-')
    add_candidate(levels.get('mval'), '#00e5ff', 'mVAL (Taban)', '--')
    add_candidate(cam.get('S5'), '#3b82f6', 'S5 Hedef', '--')

    if soft_stop and soft_stop > 0:
        add_candidate(soft_stop, '#f43f5e', 'STOP', ':', is_trade_level=True)
    if tp1 and tp1 > 0:
        add_candidate(tp1, '#10b981', 'TP1 HEDEF', ':', is_trade_level=True)

    is_actually_closed = is_closed or (exit_price is not None and exit_price > 0)
    if entry_price and entry_price > 0:
        entry_side_col = '#10b981' if side == 'LONG' else '#f43f5e'
        add_candidate(entry_price, entry_side_col, f"★ GİRİŞ ({side})", '--', is_trade_level=True)

    if is_actually_closed and exit_price and exit_price > 0:
        is_profit = (net_pnl is not None and net_pnl >= 0) or (exit_price > entry_price if side == 'LONG' else exit_price < entry_price)
        exit_side_col = '#10b981' if is_profit else '#f43f5e'
        exit_lbl = "★ KÂR ALINDI" if is_profit else "★ STOP KAPANIŞ"
        add_candidate(exit_price, exit_side_col, exit_lbl, '-.', is_trade_level=True)

    # Merge very close levels (< 0.25% difference)
    raw_levels.sort(key=lambda x: x['price'])
    filtered_levels = []
    for item in raw_levels:
        if not filtered_levels:
            filtered_levels.append(item)
        else:
            prev = filtered_levels[-1]
            pct_diff = abs(item['price'] - prev['price']) / max(prev['price'], 1e-8)
            if pct_diff < 0.0025:
                prev['label'] = f"{prev['label']} / {item['label']}"
                if item.get('is_trade_level'):
                    prev['color'] = item['color']
                    prev['is_trade_level'] = True
            else:
                filtered_levels.append(item)

    for item in filtered_levels:
        item['adjusted_y'] = item['price']

    # Anti-collision layout solver for right-hand price tags
    min_gap = y_span * 0.085
    for _ in range(50):
        for i in range(len(filtered_levels) - 1):
            cur = filtered_levels[i]
            nxt = filtered_levels[i+1]
            diff = nxt['adjusted_y'] - cur['adjusted_y']
            if diff < min_gap:
                overlap = (min_gap - diff) / 2.0
                cur['adjusted_y'] -= overlap
                nxt['adjusted_y'] += overlap

    # Render horizontal levels and non-overlapping badges
    for item in filtered_levels:
        orig_p = item['price']
        adj_y = item['adjusted_y']
        c = item['color']
        lbl = item['label']
        st = item['style']
        is_trade = item.get('is_trade_level', False)

        lw = 2.0 if is_trade else 1.0
        alpha_val = 0.95 if is_trade else 0.55

        ax.plot([-0.5, n_bars - 0.5], [orig_p, orig_p], color=c, linestyle=st, linewidth=lw, alpha=alpha_val, zorder=4)
        ax.plot([n_bars - 0.5, n_bars + 1.2], [orig_p, adj_y], color=c, linestyle=':', linewidth=0.8, alpha=0.5, zorder=5)

        font_wt = 'heavy' if is_trade else 'bold'
        font_sz = 8.5 if is_trade else 7.8
        bg_box = dict(boxstyle='round,pad=0.25', facecolor='#090d16', edgecolor=c, linewidth=1.2, alpha=0.95) if is_trade else None
        ax.text(n_bars + 1.8, adj_y, f"{lbl} (${orig_p:.4f})", color=c, fontsize=font_sz, fontweight=font_wt, va='center', bbox=bg_box, zorder=6)

    # 4. Giriş ve Çıkış Mumları Üzerinde Dikey Dotted Çizgiler ve Pinler
    if 'timestamp' in display_df.columns:
        display_timestamps = display_df['timestamp'].values
    elif 'time' in display_df.columns:
        display_timestamps = display_df['time'].values
    else:
        display_timestamps = list(range(len(display_df)))

    entry_idx = max(0, n_bars - 12) if is_actually_closed else (n_bars - 1)
    if entry_timestamp and entry_timestamp > 0:
        entry_ts_ms = entry_timestamp * 1000 if entry_timestamp < 1e11 else entry_timestamp
        best_diff = float('inf')
        for idx, ts in enumerate(display_timestamps):
            diff = abs(ts - entry_ts_ms)
            if diff < best_diff:
                best_diff = diff
                entry_idx = idx

    # Entry Marker & Dikey Noktalı Sütun Çizgisi
    if entry_price and entry_price > 0:
        entry_col = '#10b981' if side == 'LONG' else '#f43f5e'
        entry_candle = display_df.iloc[entry_idx]
        
        # 1. Mum boyunca yukarıdan aşağıya uzanan zarif noktalı çizgi
        ax.plot([entry_idx, entry_idx], [padded_min, padded_max * 0.92], color=entry_col, linestyle=':', linewidth=1.5, alpha=0.7, zorder=5)

        # 2. Mumun tepesinde/dibinde Giriş Pin Rozeti
        pin_y = float(entry_candle['high']) + y_span * 0.04 if side == 'SHORT' else float(entry_candle['low']) - y_span * 0.04
        marker = 'v' if side == 'SHORT' else '^'
        ax.scatter(entry_idx, pin_y, color=entry_col, s=260, marker=marker, edgecolors='#ffffff', linewidth=2.0, zorder=8)
        
        # 3. Giriş Noktası Etiketi (Mumun üzerinde)
        ax.text(entry_idx, pin_y + (y_span * 0.045 if side == 'SHORT' else -y_span * 0.045),
                f"GİRİŞ (${entry_price:.4f})",
                color='#ffffff', fontsize=8.2, fontweight='heavy', ha='center', va='center',
                bbox=dict(boxstyle='round,pad=0.2', facecolor=entry_col, edgecolor='#ffffff', linewidth=1.0, alpha=0.95),
                zorder=9)

    # Exit Marker & Dikey Noktalı Sütun Çizgisi
    if is_actually_closed and exit_price and exit_price > 0:
        is_profit = (net_pnl is not None and net_pnl >= 0) or (exit_price > entry_price if side == 'LONG' else exit_price < entry_price)
        exit_col = '#10b981' if is_profit else '#f43f5e'
        exit_idx = n_bars - 1
        exit_candle = display_df.iloc[exit_idx]

        # 1. Çıkış Mumu boyunca dikey noktalı çizgi
        ax.plot([exit_idx, exit_idx], [padded_min, padded_max * 0.92], color=exit_col, linestyle=':', linewidth=1.5, alpha=0.7, zorder=5)

        # 2. Çıkış X Rozeti
        pin_exit_y = float(exit_candle['high']) + y_span * 0.04 if is_profit else float(exit_candle['low']) - y_span * 0.04
        ax.scatter(exit_idx, pin_exit_y, color=exit_col, s=280, marker='X', edgecolors='#ffffff', linewidth=2.2, zorder=8)

        # 3. Çıkış Rozet Etiketi
        exit_txt = f"ÇIKIŞ (${exit_price:.4f})"
        if roe_pct is not None:
            exit_txt += f"\n{roe_pct:+.1f}%"
        ax.text(exit_idx, pin_exit_y + (y_span * 0.055 if is_profit else -y_span * 0.055),
                exit_txt,
                color='#ffffff', fontsize=8.2, fontweight='heavy', ha='center', va='center',
                bbox=dict(boxstyle='round,pad=0.2', facecolor=exit_col, edgecolor='#ffffff', linewidth=1.0, alpha=0.95),
                zorder=9)

        # 4. Giriş - Çıkış Arası Yörünge Oku ve Kutu
        if entry_price and entry_price > 0:
            fill_x = np.array([entry_idx, exit_idx, exit_idx, entry_idx])
            fill_y = np.array([entry_price, entry_price, exit_price, exit_price])
            ax.fill(fill_x, fill_y, color=exit_col, alpha=0.08, zorder=2)
            ax.annotate('', xy=(exit_idx, exit_price), xytext=(entry_idx, entry_price),
                        arrowprops=dict(arrowstyle='->,head_width=0.35,head_length=0.5', color=exit_col, linewidth=2.2, linestyle='--', alpha=0.9),
                        zorder=6)

    # 5. Zaman Eksen Formatı
    time_indices = np.linspace(0, n_bars - 1, min(7, n_bars), dtype=int)
    time_labels = []
    for idx in time_indices:
        try:
            val = display_df['timestamp'].iloc[idx] if 'timestamp' in display_df.columns else (display_df['time'].iloc[idx] if 'time' in display_df.columns else None)
            if val is not None and float(val) > 0:
                ts_sec = float(val) / 1000.0 if float(val) > 1e11 else float(val)
                time_labels.append(datetime.fromtimestamp(ts_sec, tz=timezone(timedelta(hours=3))).strftime('%H:%M'))
            else:
                time_labels.append(f"M-{n_bars - idx}")
        except Exception:
            time_labels.append(f"M-{n_bars - idx}")
    ax.set_xticks(time_indices)
    ax.set_xticklabels(time_labels, color='#94a3b8', fontsize=9, fontweight='bold')
    ax.tick_params(colors='#94a3b8', labelsize=9)
    for spine in ax.spines.values(): spine.set_color('#1e293b')

    # 6. Üst Başlık ve HUD Bilgi Paneli (Üst Üste Binmeyen Düzen)
    clean_sym = symbol.replace('/USDT', '')
    side_text = "LONG (Alış)" if side == "LONG" else "SHORT (Satış)"

    if is_actually_closed:
        pnl_str = f" | Net PnL: {net_pnl:+.2f}$ ({roe_pct:+.1f}%)" if (net_pnl is not None and roe_pct is not None) else ""
        title_str = f"VALKYRIE QUANT DESK -- #{clean_sym}/USDT (5M) | [POZİSYON KAPANDI {side_text}]{pnl_str}"
        ax.set_title(title_str, color='#ffffff', fontsize=11.0, fontweight='bold', pad=26, loc='left')

        is_profit = (net_pnl is not None and net_pnl >= 0)
        banner_border = '#10b981' if is_profit else '#f43f5e'
        banner_tag = '>> KÂRLI KAPANIŞ' if is_profit else '>> STOP / KORUMALI ÇIKIŞ'
        banner_text = f"{banner_tag}: {reason} | Giriş: ${entry_price:.4f} ➔ Çıkış: ${exit_price:.4f}"
        ax.text(0.02, 0.94, banner_text, transform=ax.transAxes,
                color='#ffffff', fontsize=9.2, fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.35', facecolor='#090d16', edgecolor=banner_border, linewidth=1.5, alpha=0.95),
                zorder=10)
    else:
        title_str = f"VALKYRIE QUANT DESK -- #{clean_sym}/USDT (5M) | [{side_text}] | Anlık: ${cur_p:.4f}"
        ax.set_title(title_str, color='#ffffff', fontsize=11.0, fontweight='bold', pad=26, loc='left')

        if reason:
            banner_text = f">> GİRİŞ NEDENİ: {reason} | Giriş Seviyesi: ${entry_price:.4f}"
            ax.text(0.02, 0.94, banner_text, transform=ax.transAxes,
                    color='#f8fafc', fontsize=9.2, fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.35', facecolor='#090d16', edgecolor='#3b82f6', linewidth=1.5, alpha=0.95),
                    zorder=10)

    ax.set_ylim(padded_min, padded_max)
    ax.set_xlim(-1, n_bars + 25)
    plt.subplots_adjust(left=0.04, right=0.98, top=0.90, bottom=0.08)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf

