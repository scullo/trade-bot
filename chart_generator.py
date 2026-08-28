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
    """
    Telegram için profesyonel, seviye çakışmasız (anti-collision),
    Giriş ve Kapanış durumunu kristal netliğinde ayıran 5M mum grafiği üretir.
    """
    if df_5m is None or df_5m.empty:
        return None

    levels = levels or {}

    # Son 65 mumu göster
    display_df = df_5m.iloc[-65:].copy().reset_index(drop=True)
    n_bars = len(display_df)

    # Dark Theme
    fig, ax = plt.subplots(figsize=(12.0, 6.6), dpi=140)
    fig.patch.set_facecolor('#080b11')
    ax.set_facecolor('#0e131f')

    # Grid
    ax.grid(True, color='#1e2638', linestyle='--', linewidth=0.5, alpha=0.6)

    # 1. Candlestick Çizimi
    green_col = '#10b981'
    red_col = '#f43f5e'
    width = 0.68

    for i, r in display_df.iterrows():
        o = float(r['open'])
        c = float(r['close'])
        h = float(r['high'])
        l = float(r['low'])
        col = green_col if c >= o else red_col

        # Fitil
        ax.plot([i, i], [l, h], color=col, linewidth=1.3, zorder=3)
        # Mum Gövdesi
        body_bottom = min(o, c)
        body_height = max(abs(c - o), (h - l) * 0.02)
        rect = patches.Rectangle((i - width/2, body_bottom), width, body_height, facecolor=col, edgecolor=col, zorder=4)
        ax.add_patch(rect)

    # 2. AVWAP Çizgileri
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

    # 3. Seviyeleri Topla ve Çakışmayı Önle (Anti-Collision Algorithm)
    cam = levels.get('camarilla', {})
    cur_p = float(display_df['close'].iloc[-1])
    min_y = float(display_df['low'].min())
    max_y = float(display_df['high'].max())
    y_span = max_y - min_y if max_y > min_y else 1.0

    raw_levels = []

    def add_candidate(price, color, label, style='--'):
        if price and not np.isnan(price) and price > 0:
            p = float(price)
            if p >= min_y * 0.95 and p <= max_y * 1.05:
                raw_levels.append({
                    'price': p,
                    'color': color,
                    'label': label,
                    'style': style
                })

    add_candidate(cam.get('R5'), '#f59e0b', 'R5 Hedef', '--')
    add_candidate(cam.get('R4'), '#fb923c', 'R4 Breakout', '-')
    add_candidate(levels.get('tepe_avwap'), '#f43f5e', 'Tepe AVWAP', '-')
    add_candidate(levels.get('mvah'), '#00e5ff', 'mVAH (Tavan)', '--')
    add_candidate(levels.get('above_npoc'), '#f0f6fc', 'Yukarı nPOC', ':')
    add_candidate(cam.get('R3'), '#f97316', 'R3 Direnç', ':')
    add_candidate(cam.get('P'), '#ffffff', 'Pivot P', '-')
    add_candidate(levels.get('mpoc'), '#c084fc', 'mPOC (Hacim)', '-')
    add_candidate(cam.get('S3'), '#f97316', 'S3 Destek', ':')
    add_candidate(levels.get('below_npoc'), '#f0f6fc', 'Aşağı nPOC', ':')
    add_candidate(levels.get('dip_avwap'), '#ffffff', 'Dip AVWAP', '-')
    add_candidate(cam.get('S4'), '#10b981', 'S4 Breakdown', '-')
    add_candidate(levels.get('mval'), '#00e5ff', 'mVAL (Taban)', '--')
    add_candidate(cam.get('S5'), '#3b82f6', 'S5 Hedef', '--')

    if soft_stop and soft_stop > 0:
        add_candidate(soft_stop, '#f43f5e', 'STOP', ':')
    if tp1 and tp1 > 0:
        add_candidate(tp1, '#10b981', 'TP1 HEDEF', ':')
    if tp2 and tp2 > 0:
        add_candidate(tp2, '#06b6d4', 'TP2 HEDEF', ':')

    # Y-Çakışma Önleme Algoritması (Spring Relaxation Anti-Collision)
    raw_levels.sort(key=lambda x: x['price'])
    for item in raw_levels:
        item['adjusted_y'] = item['price']

    min_gap = y_span * 0.048  # Etiketler arası minimum dikey mesafe

    for _ in range(15):
        for i in range(len(raw_levels) - 1):
            cur = raw_levels[i]
            nxt = raw_levels[i+1]
            diff = nxt['adjusted_y'] - cur['adjusted_y']
            if diff < min_gap:
                overlap = (min_gap - diff) / 2.0
                cur['adjusted_y'] -= overlap
                nxt['adjusted_y'] += overlap

    for item in raw_levels:
        orig_p = item['price']
        adj_y = item['adjusted_y']
        c = item['color']
        lbl = item['label']
        st = item['style']

        # Ana yatay fiyat çizgisi (mumlar boyunca)
        ax.plot([-0.5, n_bars - 0.5], [orig_p, orig_p], color=c, linestyle=st, linewidth=1.2, alpha=0.75, zorder=4)

        # Eğer etiket kaydırılmışsa zarif bağlantı çizgisi çek
        ax.plot([n_bars - 0.5, n_bars + 1.2], [orig_p, adj_y], color=c, linestyle=':', linewidth=0.9, alpha=0.6, zorder=5)

        # Sağ kenar etiket metni
        ax.text(n_bars + 1.6, adj_y, f"{lbl} (${orig_p:.4f})", color=c, fontsize=8.3, fontweight='bold', va='center', zorder=6)

    # 4. GİRİŞ VE ÇIKIŞ SEVİYELERİ BİRLİKTE (KRİSTAL NETLİĞİNDE GÖSTERİM)
    is_actually_closed = is_closed or (exit_price is not None and exit_price > 0)

    # Giriş İndeksi Bul
    entry_idx = max(0, n_bars - 12) if is_actually_closed else (n_bars - 1)
    if entry_timestamp and entry_timestamp > 0:
        entry_ts_ms = entry_timestamp * 1000 if entry_timestamp < 1e11 else entry_timestamp
        best_diff = float('inf')
        for idx, ts in enumerate(display_timestamps):
            diff = abs(ts - entry_ts_ms)
            if diff < best_diff:
                best_diff = diff
                entry_idx = idx

    # 4a. GİRİŞ SEVİYESİ ÇİZGİSİ & ROZETİ
    if entry_price and entry_price > 0:
        entry_col = '#10b981' if side == 'LONG' else '#f43f5e'
        marker = '^' if side == 'LONG' else 'v'
        
        # Giriş yatay seviye çizgisi
        ax.plot([-0.5, n_bars - 0.5], [entry_price, entry_price], color=entry_col, linestyle='--', linewidth=2.0, alpha=0.9, zorder=6)
        
        # Giriş mum işaretçisi
        ax.scatter(entry_idx, entry_price, color=entry_col, s=220, marker=marker, edgecolors='#ffffff', linewidth=2.0, zorder=8)
        ax.text(entry_idx - 1.2, entry_price, f"GİRİŞ: ${entry_price:.4f} ({side})", color='#ffffff', fontsize=9.2, fontweight='heavy', ha='right', va='center',
                bbox=dict(boxstyle='round,pad=0.35', facecolor=entry_col, edgecolor='#ffffff', linewidth=1.2, alpha=0.95), zorder=9)

    # 4b. ÇIKIŞ SEVİYESİ ÇİZGİSİ & ROZETİ + TİCARET BAĞLANTI BANDI
    if is_actually_closed and exit_price and exit_price > 0:
        is_profit = (net_pnl is not None and net_pnl >= 0) or (exit_price > entry_price if side == 'LONG' else exit_price < entry_price)
        exit_col = '#10b981' if is_profit else '#f43f5e'
        exit_icon = 'KÂR ALINDI (TP)' if is_profit else 'STOP EDİLDİ'
        exit_idx = n_bars - 1

        # Çıkış yatay seviye çizgisi
        ax.plot([-0.5, n_bars - 0.5], [exit_price, exit_price], color=exit_col, linestyle='-.', linewidth=2.2, alpha=0.95, zorder=6)
        
        # Çıkış mum işaretçisi
        ax.scatter(exit_idx, exit_price, color=exit_col, s=240, marker='X', edgecolors='#ffffff', linewidth=2.2, zorder=8)
        ax.text(exit_idx - 1.2, exit_price, f"{exit_icon}: ${exit_price:.4f}", color='#ffffff', fontsize=9.5, fontweight='heavy', ha='right', va='center',
                bbox=dict(boxstyle='round,pad=0.38', facecolor=exit_col, edgecolor='#ffffff', linewidth=1.4, alpha=0.95), zorder=9)

        # GİRİŞ ➔ ÇIKIŞ YÖRÜNGE BAĞLANTISI (Trade Trajectory Line & Shading)
        if entry_price and entry_price > 0:
            ax.annotate('', xy=(exit_idx, exit_price), xytext=(entry_idx, entry_price),
                        arrowprops=dict(arrowstyle='->,head_width=0.4,head_length=0.6', color=exit_col, linewidth=2.5, linestyle='-', alpha=0.9),
                        zorder=7)
            fill_x = np.array([entry_idx, exit_idx, exit_idx, entry_idx])
            fill_y = np.array([entry_price, entry_price, exit_price, exit_price])
            ax.fill(fill_x, fill_y, color=exit_col, alpha=0.10, zorder=2)

    # 5. Zaman ve Fiyat Eksen Formatlama
    time_indices = np.linspace(0, n_bars - 1, 7, dtype=int)
    time_labels = [datetime.fromtimestamp(display_df['timestamp'].iloc[idx] / 1000).strftime('%H:%M') for idx in time_indices]
    ax.set_xticks(time_indices)
    ax.set_xticklabels(time_labels, color='#94a3b8', fontsize=9, fontweight='bold')
    ax.tick_params(colors='#94a3b8', labelsize=9)
    for spine in ax.spines.values(): spine.set_color('#1e2638')

    # 6. Başlık & GİRİŞ / KAPANIŞ ÜST BANNERI (Kusursuz Ayrım)
    clean_sym = symbol.replace('/USDT', '')
    side_text = "LONG (Alış)" if side == "LONG" else "SHORT (Satış)"

    if is_actually_closed:
        pnl_str = f" | Net: {net_pnl:+.2f}$ ({roe_pct:+.1f}%)" if (net_pnl is not None and roe_pct is not None) else ""
        title_str = f"VALKYRIE QUANT DESK -- #{clean_sym}/USDT (5M) | [POZİSYON KAPANDI {side_text}]{pnl_str}"
        ax.set_title(title_str, color='#ffffff', fontsize=10.5, fontweight='bold', pad=24, loc='left')

        # KAPANIŞ BANNERI
        is_profit = (net_pnl is not None and net_pnl >= 0)
        banner_border = '#10b981' if is_profit else '#f43f5e'
        banner_tag = '>> KÂRLI KAPANIŞ NEDENİ' if is_profit else '>> ZARAR KES / STOP NEDENİ'
        banner_text = f"{banner_tag}: {reason}"
        ax.text(0.02, 0.94, banner_text, transform=ax.transAxes,
                color='#ffffff', fontsize=9.5, fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.45', facecolor='#111827', edgecolor=banner_border, linewidth=1.5, alpha=0.95),
                zorder=10)
    else:
        title_str = f"VALKYRIE QUANT DESK -- #{clean_sym}/USDT (5M) | [{side_text}] | Anlık: ${cur_p:.4f}"
        ax.set_title(title_str, color='#ffffff', fontsize=10.5, fontweight='bold', pad=24, loc='left')

        # GİRİŞ BANNERI
        if reason:
            banner_text = f">> GİRİŞ NEDENİ: {reason}"
            ax.text(0.02, 0.94, banner_text, transform=ax.transAxes,
                    color='#f8fafc', fontsize=9.5, fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.45', facecolor='#111827', edgecolor='#3b82f6', linewidth=1.5, alpha=0.95),
                    zorder=10)

    # Sağ kenar boşluğu (Etiketler rahat okunsun)
    ax.set_xlim(-1, n_bars + 18)
    plt.subplots_adjust(left=0.05, right=0.97, top=0.90, bottom=0.08)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf
