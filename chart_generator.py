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
    soft_stop: float = None,
    tp1: float = None,
    tp2: float = None,
    avwap_high_points: list = None,
    avwap_low_points: list = None,
    trade_type: str = "SCALP",
    reason: str = ""
) -> io.BytesIO:
    """
    Telegram icin TradingView tarzinda, yuksek cozunurluklu, indikatörlü 5M mum grafigi uretir.
    """
    if df_5m is None or df_5m.empty:
        return None

    levels = levels or {}

    # Son 70 mumu goster (Telegramda cok net ve okunakli gorunum)
    display_df = df_5m.iloc[-70:].copy().reset_index(drop=True)
    n_bars = len(display_df)

    # Dark Theme Stili
    fig, (ax_main, ax_vol) = plt.subplots(
        2, 1, figsize=(11, 6.2), dpi=120,
        gridspec_kw={'height_ratios': [4.2, 1.0], 'hspace': 0.08}
    )
    fig.patch.set_facecolor('#07090e')
    ax_main.set_facecolor('#0e121a')
    ax_vol.set_facecolor('#0e121a')

    # Grid
    ax_main.grid(True, color='#1e2638', linestyle='--', linewidth=0.5, alpha=0.7)
    ax_vol.grid(True, color='#1e2638', linestyle='--', linewidth=0.5, alpha=0.5)

    # 1. Candlestick Cizimi
    green_col = '#0ecb81'
    red_col = '#ff4757'
    width = 0.65

    for i, r in display_df.iterrows():
        o = float(r['open'])
        c = float(r['close'])
        h = float(r['high'])
        l = float(r['low'])
        col = green_col if c >= o else red_col

        # Wick
        ax_main.plot([i, i], [l, h], color=col, linewidth=1.1, zorder=3)
        # Body
        body_bottom = min(o, c)
        body_height = max(abs(c - o), (h - l) * 0.02)  # doji min height
        rect = patches.Rectangle((i - width/2, body_bottom), width, body_height, facecolor=col, edgecolor=col, zorder=4)
        ax_main.add_patch(rect)

        # Volume Bar
        vol = float(r.get('volume', 0.0))
        ax_vol.bar(i, vol, color=col, width=width, alpha=0.75, zorder=3)

    # 2. AVWAP Cizgileri
    display_timestamps = display_df['timestamp'].values
    ts_to_idx = {int(ts): idx for idx, ts in enumerate(display_timestamps)}

    if avwap_high_points:
        h_x, h_y = [], []
        for p in avwap_high_points:
            ts_ms = p['time'] * 1000
            if ts_ms in ts_to_idx:
                h_x.append(ts_to_idx[ts_ms])
                h_y.append(p['value'])
        if len(h_x) > 1:
            ax_main.plot(h_x, h_y, color='#ff4757', linewidth=2.0, label='Tepe AVWAP', zorder=5)

    if avwap_low_points:
        l_x, l_y = [], []
        for p in avwap_low_points:
            ts_ms = p['time'] * 1000
            if ts_ms in ts_to_idx:
                l_x.append(ts_to_idx[ts_ms])
                l_y.append(p['value'])
        if len(l_x) > 1:
            ax_main.plot(l_x, l_y, color='#ffffff', linewidth=2.0, label='Dip AVWAP', zorder=5)

    # 3. Kilit Fiyat Seviyeleri (Camarilla + VP)
    cam = levels.get('camarilla', {})
    cur_p = float(display_df['close'].iloc[-1])
    min_y = display_df['low'].min()
    max_y = display_df['high'].max()

    def draw_level_line(price, color, label_text, style='-.'):
        if not price or np.isnan(price) or price <= 0:
            return
        p = float(price)
        if p >= min_y * 0.95 and p <= max_y * 1.05:
            ax_main.axhline(p, color=color, linestyle=style, linewidth=1.2, alpha=0.85, zorder=4)
            ax_main.text(n_bars - 0.5, p, f" {label_text} (${p:.4f})", color=color, fontsize=8, fontweight='bold', va='center', zorder=6)

    draw_level_line(cam.get('R5'), '#fbc531', 'R5 Hedef', '--')
    draw_level_line(cam.get('R4'), '#ffa726', 'R4 Breakout', '-')
    draw_level_line(levels.get('mvah'), '#00e5ff', 'mVAH (Aylık Tavan)', '--')
    draw_level_line(cam.get('R3'), '#fb8c00', 'R3 Direnç', ':')
    draw_level_line(cam.get('P'), '#ffffff', 'Pivot P', '-')
    draw_level_line(levels.get('mpoc'), '#d500f9', 'mPOC (Aylık Hacim)', '-')
    draw_level_line(cam.get('S3'), '#fb8c00', 'S3 Destek', ':')
    draw_level_line(cam.get('S4'), '#0ecb81', 'S4 Breakdown', '-')
    draw_level_line(levels.get('mval'), '#00e5ff', 'mVAL (Aylık Taban)', '--')

    # 4. Giris & Cikis Isaretleri
    if entry_price and entry_price > 0:
        entry_col = '#0ecb81' if side == 'LONG' else '#ff4757'
        marker = '^' if side == 'LONG' else 'v'
        ax_main.axhline(entry_price, color=entry_col, linestyle='-', linewidth=1.8, alpha=0.95, zorder=6)
        ax_main.scatter(n_bars - 1, entry_price, color=entry_col, s=140, marker=marker, edgecolors='#ffffff', linewidth=1.5, zorder=7)
        ax_main.text(n_bars - 1.2, entry_price, f"GIRIS: ${entry_price:.4f} ", color='#ffffff', fontsize=9, fontweight='heavy', ha='right', va='center',
                     bbox=dict(boxstyle='round,pad=0.3', facecolor=entry_col, edgecolor='none', alpha=0.9), zorder=8)

    if exit_price and exit_price > 0:
        ax_main.scatter(n_bars - 1, exit_price, color='#fbc531', s=160, marker='X', edgecolors='#000', linewidth=1.5, zorder=7)
        ax_main.text(n_bars - 1.2, exit_price, f"CIKIS: ${exit_price:.4f} ", color='#07090e', fontsize=9, fontweight='heavy', ha='right', va='center',
                     bbox=dict(boxstyle='round,pad=0.3', facecolor='#fbc531', edgecolor='none', alpha=0.9), zorder=8)

    if soft_stop and soft_stop > 0:
        draw_level_line(soft_stop, '#ff4757', 'STOP', ':')

    if tp1 and tp1 > 0:
        draw_level_line(tp1, '#0ecb81', 'TP1', ':')

    # 5. Zaman Eksen Formatlama
    time_indices = np.linspace(0, n_bars - 1, 6, dtype=int)
    time_labels = [datetime.fromtimestamp(display_df['timestamp'].iloc[idx] / 1000).strftime('%H:%M') for idx in time_indices]
    ax_vol.set_xticks(time_indices)
    ax_vol.set_xticklabels(time_labels, color='#94a3b8', fontsize=8.5, fontweight='bold')
    ax_main.set_xticks([])

    # Fiyat Eksen Formatlama
    ax_main.tick_params(colors='#94a3b8', labelsize=8.5)
    ax_vol.tick_params(colors='#94a3b8', labelsize=7.5)
    for spine in ax_main.spines.values(): spine.set_color('#1e2638')
    for spine in ax_vol.spines.values(): spine.set_color('#1e2638')

    # 6. Baslik & Bilgi Karti
    clean_sym = symbol.replace('/USDT', '')
    title_str = f"VALKYRIE QUANT DESK -- #{clean_sym}/USDT (5M) | [{side}] | Fiyat: ${cur_p:.4f}"
    ax_main.set_title(title_str, color='#ffffff', fontsize=10.5, fontweight='bold', pad=10, loc='left', fontfamily='sans-serif')

    plt.subplots_adjust(left=0.06, right=0.92, top=0.92, bottom=0.08)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf
