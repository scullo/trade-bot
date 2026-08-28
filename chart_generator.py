import io
import time
from datetime import datetime
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
    display_df = df_5m.iloc[-65:].copy().reset_index(drop=True)
    n_bars = len(display_df)

    # 1. Dark Theme
    fig, ax = plt.subplots(figsize=(13.5, 7.2), dpi=140)
    fig.patch.set_facecolor('#080d1a')
    ax.set_facecolor('#0f172a')

    # Grid
    ax.grid(True, color='#1e293b', linestyle='--', linewidth=0.6, alpha=0.7)

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

        # Wick
        ax.plot([i, i], [l, h], color=col, linewidth=1.2, zorder=3)
        # Body
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

    padded_min = chart_min - y_span * 0.10
    padded_max = chart_max + y_span * 0.18

    # 2. AVWAP Lines
    display_timestamps = display_df['timestamp'].values
    ts_to_idx = {int(ts): idx for idx, ts in enumerate(display_timestamps)}

    if avwap_high_points:
        h_x, h_y = [], []
        for p_pt in avwap_high_points:
            ts_ms = p_pt['time'] * 1000
            if ts_ms in ts_to_idx:
                h_x.append(ts_to_idx[ts_ms])
                h_y.append(p_pt['value'])
        if len(h_x) > 1:
            ax.plot(h_x, h_y, color='#f43f5e', linewidth=2.0, alpha=0.85, zorder=5)

    if avwap_low_points:
        l_x, l_y = [], []
        for p_pt in avwap_low_points:
            ts_ms = p_pt['time'] * 1000
            if ts_ms in ts_to_idx:
                l_x.append(ts_to_idx[ts_ms])
                l_y.append(p_pt['value'])
        if len(l_x) > 1:
            ax.plot(l_x, l_y, color='#38bdf8', linewidth=2.0, alpha=0.85, zorder=5)

    # 3. Smart Anti-Collision Level Selection
    cam = levels.get('camarilla', {})
    raw_levels = []

    def add_candidate(price, color, label, style='--'):
        if price and not np.isnan(price) and price > 0:
            p_val = float(price)
            if p_val >= padded_min and p_val <= padded_max:
                raw_levels.append({
                    'price': p_val,
                    'color': color,
                    'label': label,
                    'style': style
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
        add_candidate(soft_stop, '#f43f5e', 'STOP', ':')
    if tp1 and tp1 > 0:
        add_candidate(tp1, '#10b981', 'TP1 HEDEF', ':')

    # Merge very close levels (< 0.15% difference)
    raw_levels.sort(key=lambda x: x['price'])
    filtered_levels = []
    for item in raw_levels:
        if not filtered_levels:
            filtered_levels.append(item)
        else:
            prev = filtered_levels[-1]
            pct_diff = abs(item['price'] - prev['price']) / max(prev['price'], 1e-8)
            if pct_diff < 0.0015:
                prev['label'] = f"{prev['label']} / {item['label']}"
            else:
                filtered_levels.append(item)

    for item in filtered_levels:
        item['adjusted_y'] = item['price']

    # Relax vertical gap for text labels
    min_gap = y_span * 0.075
    for _ in range(30):
        for i in range(len(filtered_levels) - 1):
            cur = filtered_levels[i]
            nxt = filtered_levels[i+1]
            diff = nxt['adjusted_y'] - cur['adjusted_y']
            if diff < min_gap:
                overlap = (min_gap - diff) / 2.0
                cur['adjusted_y'] -= overlap
                nxt['adjusted_y'] += overlap

    for item in filtered_levels:
        orig_p = item['price']
        adj_y = item['adjusted_y']
        c = item['color']
        lbl = item['label']
        st = item['style']

        # Horizontal level line across candle area
        ax.plot([-0.5, n_bars - 0.5], [orig_p, orig_p], color=c, linestyle=st, linewidth=1.1, alpha=0.65, zorder=4)

        # Subtle guide line connecting level to text on right margin
        ax.plot([n_bars - 0.5, n_bars + 1.5], [orig_p, adj_y], color=c, linestyle=':', linewidth=0.8, alpha=0.5, zorder=5)

        # Right margin label with dark tag
        ax.text(n_bars + 2.0, adj_y, f"{lbl} (${orig_p:.4f})", color=c, fontsize=8.2, fontweight='bold', va='center', zorder=6)

    # 4. Entry & Exit Representation (Clean, Uncluttered, No Overlapping Badges)
    is_actually_closed = is_closed or (exit_price is not None and exit_price > 0)
    entry_idx = max(0, n_bars - 14) if is_actually_closed else (n_bars - 1)
    if entry_timestamp and entry_timestamp > 0:
        entry_ts_ms = entry_timestamp * 1000 if entry_timestamp < 1e11 else entry_timestamp
        best_diff = float('inf')
        for idx, ts in enumerate(display_timestamps):
            diff = abs(ts - entry_ts_ms)
            if diff < best_diff:
                best_diff = diff
                entry_idx = idx

    # Entry Price Line & Crisp Marker
    if entry_price and entry_price > 0:
        entry_col = '#10b981' if side == 'LONG' else '#f43f5e'
        marker = '^' if side == 'LONG' else 'v'
        
        # Horizontal entry line
        ax.plot([-0.5, n_bars - 0.5], [entry_price, entry_price], color=entry_col, linestyle='--', linewidth=1.8, alpha=0.9, zorder=6)
        
        # Sharp entry marker on candle
        ax.scatter(entry_idx, entry_price, color=entry_col, s=180, marker=marker, edgecolors='#ffffff', linewidth=1.8, zorder=8)
        
        # Entry Tag cleanly positioned on the left of the entry marker
        offset_y = -y_span * 0.05 if side == 'SHORT' else y_span * 0.05
        ax.annotate(
            f"GİRİŞ: ${entry_price:.4f} ({side})",
            xy=(entry_idx, entry_price),
            xytext=(entry_idx - 6.0, entry_price + offset_y),
            arrowprops=dict(arrowstyle='->,head_width=0.3,head_length=0.4', color=entry_col, lw=1.2),
            fontsize=8.5, fontweight='bold', color='#ffffff',
            bbox=dict(boxstyle='round,pad=0.28', facecolor=entry_col, edgecolor='#ffffff', linewidth=1.1, alpha=0.95),
            zorder=9
        )

    # Exit Price Line & Target Marker
    if is_actually_closed and exit_price and exit_price > 0:
        is_profit = (net_pnl is not None and net_pnl >= 0) or (exit_price > entry_price if side == 'LONG' else exit_price < entry_price)
        exit_col = '#10b981' if is_profit else '#f43f5e'
        exit_idx = n_bars - 1
        exit_label = f"KÂR ALINDI (${exit_price:.4f})" if is_profit else f"STOP EDİLDİ (${exit_price:.4f})"

        # Horizontal exit line
        ax.plot([-0.5, n_bars - 0.5], [exit_price, exit_price], color=exit_col, linestyle='-.', linewidth=2.0, alpha=0.9, zorder=6)
        
        # Sharp exit marker on candle
        ax.scatter(exit_idx, exit_price, color=exit_col, s=200, marker='X', edgecolors='#ffffff', linewidth=2.0, zorder=8)

        # Exit Tag cleanly positioned on the left of exit point
        offset_exit_y = y_span * 0.06 if is_profit else -y_span * 0.06
        ax.annotate(
            exit_label,
            xy=(exit_idx, exit_price),
            xytext=(exit_idx - 6.5, exit_price + offset_exit_y),
            arrowprops=dict(arrowstyle='->,head_width=0.3,head_length=0.4', color=exit_col, lw=1.2),
            fontsize=8.8, fontweight='bold', color='#ffffff',
            bbox=dict(boxstyle='round,pad=0.30', facecolor=exit_col, edgecolor='#ffffff', linewidth=1.2, alpha=0.95),
            zorder=9
        )

        # Trade Trajectory Line & Shading
        if entry_price and entry_price > 0:
            fill_x = np.array([entry_idx, exit_idx, exit_idx, entry_idx])
            fill_y = np.array([entry_price, entry_price, exit_price, exit_price])
            ax.fill(fill_x, fill_y, color=exit_col, alpha=0.08, zorder=2)

    # 5. Time and Price Axes Formatting
    time_indices = np.linspace(0, n_bars - 1, 7, dtype=int)
    time_labels = [datetime.fromtimestamp(display_df['timestamp'].iloc[idx] / 1000).strftime('%H:%M') for idx in time_indices]
    ax.set_xticks(time_indices)
    ax.set_xticklabels(time_labels, color='#94a3b8', fontsize=9, fontweight='bold')
    ax.tick_params(colors='#94a3b8', labelsize=9)
    for spine in ax.spines.values(): spine.set_color('#1e293b')

    # 6. Executive Header & Status HUD Banner
    clean_sym = symbol.replace('/USDT', '')
    side_text = "LONG (Alış)" if side == "LONG" else "SHORT (Satış)"

    if is_actually_closed:
        pnl_str = f" | Net PnL: {net_pnl:+.2f}$ ({roe_pct:+.1f}%)" if (net_pnl is not None and roe_pct is not None) else ""
        title_str = f"VALKYRIE QUANT DESK -- #{clean_sym}/USDT (5M) | [POZİSYON KAPANDI {side_text}]{pnl_str}"
        ax.set_title(title_str, color='#ffffff', fontsize=11.0, fontweight='bold', pad=24, loc='left')

        is_profit = (net_pnl is not None and net_pnl >= 0)
        banner_border = '#10b981' if is_profit else '#f43f5e'
        banner_tag = '>> KÂRLI KAPANIŞ NEDENİ' if is_profit else '>> STOP NEDENİ'
        banner_text = f"{banner_tag}: {reason}"
        ax.text(0.02, 0.94, banner_text, transform=ax.transAxes,
                color='#ffffff', fontsize=9.2, fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.40', facecolor='#0f172a', edgecolor=banner_border, linewidth=1.5, alpha=0.95),
                zorder=10)
    else:
        title_str = f"VALKYRIE QUANT DESK -- #{clean_sym}/USDT (5M) | [{side_text}] | Anlık: ${cur_p:.4f}"
        ax.set_title(title_str, color='#ffffff', fontsize=11.0, fontweight='bold', pad=24, loc='left')

        if reason:
            banner_text = f">> GİRİŞ NEDENİ: {reason}"
            ax.text(0.02, 0.94, banner_text, transform=ax.transAxes,
                    color='#f8fafc', fontsize=9.2, fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.40', facecolor='#0f172a', edgecolor='#3b82f6', linewidth=1.5, alpha=0.95),
                    zorder=10)

    ax.set_ylim(padded_min, padded_max)
    ax.set_xlim(-1, n_bars + 24)
    plt.subplots_adjust(left=0.04, right=0.98, top=0.90, bottom=0.08)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf
