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
    Telegram icin sadece indikatorlere ve giris nedenine odaklanmis,
    yuksek cozunurluklu 5M mum grafigi uretir (Hacim cubugu kaldirilmistir).
    """
    if df_5m is None or df_5m.empty:
        return None

    levels = levels or {}

    # Son 65 mumu goster (Indikatorler ve seviyeler cok net okunur)
    display_df = df_5m.iloc[-65:].copy().reset_index(drop=True)
    n_bars = len(display_df)

    # Dark Theme Stili (Tek ve Buyuk Grafik Alani)
    fig, ax = plt.subplots(figsize=(11.5, 6.2), dpi=130)
    fig.patch.set_facecolor('#080b11')
    ax.set_facecolor('#0e131f')

    # Grid
    ax.grid(True, color='#1e2638', linestyle='--', linewidth=0.5, alpha=0.7)

    # 1. Candlestick Cizimi
    green_col = '#10b981'
    red_col = '#f43f5e'
    width = 0.68

    for i, r in display_df.iterrows():
        o = float(r['open'])
        c = float(r['close'])
        h = float(r['high'])
        l = float(r['low'])
        col = green_col if c >= o else red_col

        # Wick
        ax.plot([i, i], [l, h], color=col, linewidth=1.3, zorder=3)
        # Body
        body_bottom = min(o, c)
        body_height = max(abs(c - o), (h - l) * 0.02)
        rect = patches.Rectangle((i - width/2, body_bottom), width, body_height, facecolor=col, edgecolor=col, zorder=4)
        ax.add_patch(rect)

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
            ax.plot(h_x, h_y, color='#f43f5e', linewidth=2.2, label='Tepe AVWAP', zorder=5)

    if avwap_low_points:
        l_x, l_y = [], []
        for p in avwap_low_points:
            ts_ms = p['time'] * 1000
            if ts_ms in ts_to_idx:
                l_x.append(ts_to_idx[ts_ms])
                l_y.append(p['value'])
        if len(l_x) > 1:
            ax.plot(l_x, l_y, color='#ffffff', linewidth=2.2, label='Dip AVWAP', zorder=5)

    # 3. Kilit Fiyat Seviyeleri (Camarilla + VP)
    cam = levels.get('camarilla', {})
    cur_p = float(display_df['close'].iloc[-1])
    min_y = display_df['low'].min()
    max_y = display_df['high'].max()

    def draw_level_line(price, color, label_text, style='-.'):
        if not price or np.isnan(price) or price <= 0:
            return
        p = float(price)
        if p >= min_y * 0.96 and p <= max_y * 1.04:
            ax.axhline(p, color=color, linestyle=style, linewidth=1.3, alpha=0.85, zorder=4)
            ax.text(n_bars - 0.5, p, f" {label_text} (${p:.4f})", color=color, fontsize=8.5, fontweight='bold', va='center', zorder=6)

    draw_level_line(cam.get('R5'), '#f59e0b', 'R5 Hedef', '--')
    draw_level_line(cam.get('R4'), '#fb923c', 'R4 Breakout', '-')
    draw_level_line(levels.get('tepe_avwap'), '#f43f5e', 'Tepe AVWAP (Direnç)', '-')
    draw_level_line(levels.get('mvah'), '#06b6d4', 'mVAH (Aylık Tavan)', '--')
    draw_level_line(cam.get('R3'), '#f97316', 'R3 Direnç', ':')
    draw_level_line(cam.get('P'), '#ffffff', 'Pivot P', '-')
    draw_level_line(levels.get('mpoc'), '#c084fc', 'mPOC (Aylık Hacim)', '-')
    draw_level_line(cam.get('S3'), '#f97316', 'S3 Destek', ':')
    draw_level_line(levels.get('dip_avwap'), '#ffffff', 'Dip AVWAP (Destek)', '-')
    draw_level_line(cam.get('S4'), '#10b981', 'S4 Breakdown', '-')
    draw_level_line(levels.get('mval'), '#06b6d4', 'mVAL (Aylık Taban)', '--')
    draw_level_line(cam.get('S5'), '#3b82f6', 'S5 Hedef', '--')

    # 4. Giris & Cikis Isaretleri
    if entry_price and entry_price > 0:
        entry_col = '#10b981' if side == 'LONG' else '#f43f5e'
        marker = '^' if side == 'LONG' else 'v'
        ax.axhline(entry_price, color=entry_col, linestyle='--', linewidth=2.0, alpha=0.95, zorder=6)
        ax.scatter(n_bars - 1, entry_price, color=entry_col, s=180, marker=marker, edgecolors='#ffffff', linewidth=1.8, zorder=7)
        ax.text(n_bars - 1.2, entry_price, f"⚡ GİRİŞ: ${entry_price:.4f} ({side}) ", color='#ffffff', fontsize=9.5, fontweight='heavy', ha='right', va='center',
                bbox=dict(boxstyle='round,pad=0.35', facecolor=entry_col, edgecolor='none', alpha=0.95), zorder=8)

    if exit_price and exit_price > 0:
        ax.scatter(n_bars - 1, exit_price, color='#f59e0b', s=200, marker='X', edgecolors='#000', linewidth=1.8, zorder=7)
        ax.text(n_bars - 1.2, exit_price, f"🏁 ÇIKIŞ: ${exit_price:.4f} ", color='#080b11', fontsize=9.5, fontweight='heavy', ha='right', va='center',
                bbox=dict(boxstyle='round,pad=0.35', facecolor='#f59e0b', edgecolor='none', alpha=0.95), zorder=8)

    if soft_stop and soft_stop > 0:
        draw_level_line(soft_stop, '#f43f5e', 'STOP', ':')

    if tp1 and tp1 > 0:
        draw_level_line(tp1, '#10b981', 'TP1 HEDEF', ':')

    if tp2 and tp2 > 0:
        draw_level_line(tp2, '#06b6d4', 'TP2 HEDEF', ':')

    # 5. Zaman Eksen Formatlama
    time_indices = np.linspace(0, n_bars - 1, 7, dtype=int)
    time_labels = [datetime.fromtimestamp(display_df['timestamp'].iloc[idx] / 1000).strftime('%H:%M') for idx in time_indices]
    ax.set_xticks(time_indices)
    ax.set_xticklabels(time_labels, color='#94a3b8', fontsize=9, fontweight='bold')

    # Fiyat Eksen Formatlama
    ax.tick_params(colors='#94a3b8', labelsize=9)
    for spine in ax.spines.values(): spine.set_color('#1e2638')

    # 6. Baslik & POZISYON ACILIS NEDENI BILGI KARTLARI
    clean_sym = symbol.replace('/USDT', '')
    side_text = "LONG (Alış)" if side == "LONG" else "SHORT (Satış)"
    title_str = f"VALKYRIE QUANT DESK -- #{clean_sym}/USDT (5M) | [{side_text}] | Anlık: ${cur_p:.4f}"
    ax.set_title(title_str, color='#ffffff', fontsize=10.5, fontweight='bold', pad=22, loc='left')

    # GİRİŞ NEDENİ BANNERI (GRAFİĞİN İÇİNDE EN ÜSTTE)
    if reason:
        reason_box_text = f"⚡ GİRİŞ NEDENİ: {reason}"
        ax.text(0.02, 0.94, reason_box_text, transform=ax.transAxes,
                color='#f8fafc', fontsize=9.5, fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.45', facecolor='#111827', edgecolor='#3b82f6', linewidth=1.3, alpha=0.95),
                zorder=10)

    plt.subplots_adjust(left=0.06, right=0.88, top=0.90, bottom=0.08)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf
