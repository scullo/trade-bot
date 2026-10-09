"""
VALKYRIE GÖRSEL ADLİ KARA KUTU & MİKROSKOBİK MUM OTOPSİ MOTORU
Modül: chart_engine_v2.py
Amaç: 1600x900 çözünürlüğünde, sol tarafında mikroskobik mum grafiği ve CVD paneli (%72),
sağ tarafında ise Bloomberg/Quant-Desk adli telemetri ve AI otopsi HUD kartını (%28)
içeren ultra-premium kompozit infografik üretir.
"""

import io
import os
import re
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.gridspec import GridSpec


def _clean_str(text: Any, max_len: int = 50) -> str:
    if text is None:
        return ""
    s = str(text).strip()
    # Strip emojis while keeping standard punctuation, Turkish characters, and UI symbols
    s = re.sub(r'[^\w\s\.,;:!\?\-\+\*/\(\)\[\]#\$%&@=<>_ıİğĞüÜşŞöÖçÇ★▲▼─│✓·|]', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s[:max_len]




def fmt_price(p: Any) -> str:
    if p is None or (isinstance(p, (int, float)) and (np.isnan(p) or p == 0)):
        return "$0.00"
    try:
        p = float(p)
    except (ValueError, TypeError):
        return "$0.00"
    abs_p = abs(p)
    if abs_p >= 1000:
        return f"${p:,.2f}"
    elif abs_p >= 10:
        return f"${p:.2f}"
    elif abs_p >= 1:
        return f"${p:.4f}"
    elif abs_p >= 0.01:
        return f"${p:.5f}"
    elif abs_p >= 0.0001:
        return f"${p:.6f}"
    else:
        return f"${p:.8f}"


class ForensicChartEngineV2:
    """
    1600x900 Ultra HD Kompozit Adli Görsel Üretim Motoru.
    Giriş ve çıkış mumunu asla kaybetmeyen dinamik zaman penceresi ve
    bağımsız adli HUD telemetri kartı içerir.
    """

    COLOR_BG = '#070b14'          # Arka plan (Ultra Dark Navy)
    COLOR_CHART_BG = '#0c1222'    # Grafik alanı
    COLOR_HUD_BG = '#090e1c'      # HUD Panel alanı
    COLOR_GRID = '#1e293b'        # İnce ızgara çizgisi
    COLOR_GREEN = '#10b981'       # Neon Yeşili (Long / Win)
    COLOR_RED = '#f43f5e'         # Neon Kırmızı (Short / Loss)
    COLOR_CYAN = '#00f2fe'        # Kuant Camgöbeği (Valkyrie Accent)
    COLOR_YELLOW = '#eab308'      # Camarilla / İkaz Sarı
    COLOR_PURPLE = '#c084fc'      # nPOC / mPOC Mor
    COLOR_ORANGE = '#fb923c'      # R4 Breakout Turuncu
    COLOR_TEXT_MUTED = '#94a3b8'  # Soluk gri metin

    def __init__(self):
        pass

    def generate_composite_snapshot(
        self,
        trade_record: Dict[str, Any],
        df_5m: pd.DataFrame,
        levels: Optional[Dict[str, Any]] = None,
        autopsy_data: Optional[Dict[str, Any]] = None
    ) -> Optional[io.BytesIO]:
        """
        1600x900 boyutunda çift panelli kompozit infografik üretir ve BytesIO buffer döndürür.
        """
        if df_5m is None or df_5m.empty or len(df_5m) < 5:
            return None

        levels = levels or {}
        autopsy = autopsy_data or {}

        symbol = str(trade_record.get("symbol", "BTC/USDT")).replace("/USDT", "")
        side = str(trade_record.get("side", "LONG")).upper()
        leverage = int(trade_record.get("leverage") or 5)
        entry_price = float(trade_record.get("entry_price") or 0.0)
        exit_price = float(trade_record.get("exit_price") or 0.0)
        net_pnl = float(trade_record.get("net_pnl") or 0.0)
        roe_pct = float(trade_record.get("roe_pct") or 0.0)
        is_profit = (net_pnl > 0) or (roe_pct > 0)
        theme_pnl_col = self.COLOR_GREEN if is_profit else (self.COLOR_RED if roe_pct < 0 else '#94a3b8')

        # Zaman damgaları
        entry_time_str = str(trade_record.get("entry_time", ""))
        exit_time_str = str(trade_record.get("exit_time", ""))
        duration_str = str(trade_record.get("duration", "Bilinmiyor"))
        close_reason = str(trade_record.get("close_reason") or "Pozisyon Kapatıldı")
        setup_id = str(trade_record.get("setup_id") or trade_record.get("reason") or "SETUP_QUANT")

        # ---------------------------------------------------------------------
        # 1. DİNAMİK ZAMAN DİLİMLEME (GİRİŞ VE ÇIKIŞ MUMUNU ASLA KAYBETMEZ)
        # ---------------------------------------------------------------------
        # DataFrame içerisinde zaman kolonunu bul
        time_col = None
        for col in ['timestamp', 'time', 'date', 'open_time']:
            if col in df_5m.columns:
                time_col = col
                break

        timestamps = df_5m[time_col].values if time_col else list(range(len(df_5m)))

        # Giriş mumunun indeksini eşleştir
        entry_ts_sec = 0.0
        if entry_time_str:
            try:
                entry_ts_sec = datetime.strptime(entry_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone(timedelta(hours=3))).timestamp()
            except Exception:
                entry_ts_sec = 0.0

        entry_idx = len(df_5m) - 15  # Varsayılan
        if entry_ts_sec > 0 and time_col:
            entry_ts_val = entry_ts_sec * 1000.0 if float(timestamps[-1]) > 1e11 else entry_ts_sec
            diffs = np.abs(np.array(timestamps, dtype=float) - entry_ts_val)
            entry_idx = int(np.argmin(diffs))

        # Çıkış mumunun indeksini eşleştir
        exit_ts_sec = 0.0
        if exit_time_str:
            try:
                exit_ts_sec = datetime.strptime(exit_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone(timedelta(hours=3))).timestamp()
            except Exception:
                exit_ts_sec = 0.0

        exit_idx = len(df_5m) - 1  # Varsayılan
        if exit_ts_sec > 0 and time_col:
            exit_ts_val = exit_ts_sec * 1000.0 if float(timestamps[-1]) > 1e11 else exit_ts_sec
            diffs_exit = np.abs(np.array(timestamps, dtype=float) - exit_ts_val)
            exit_idx = int(np.argmin(diffs_exit))
            if exit_idx < entry_idx:
                exit_idx = entry_idx + 1

        # Dilimleme penceresi formülü:
        # Başlangıç: Giriş mumu - 12 mum (İşlem öncesi piyasa yapısı)
        # Bitiş: Çıkış mumu + 8 mum (Post-exit piyasa davranışı)
        slice_start = max(0, entry_idx - 12)
        slice_end = min(len(df_5m), exit_idx + 9)
        if slice_end - slice_start < 25:
            # Görsel derinliği için en az 25 mum olsun
            slice_start = max(0, slice_end - 35)

        display_df = df_5m.iloc[slice_start:slice_end].copy().reset_index(drop=True)
        n_bars = len(display_df)

        # Yeni dilim içindeki lokal indeksler
        local_entry_idx = max(0, min(n_bars - 1, entry_idx - slice_start))
        local_exit_idx = max(0, min(n_bars - 1, exit_idx - slice_start))
        if local_exit_idx <= local_entry_idx:
            local_exit_idx = min(n_bars - 1, local_entry_idx + max(1, int(trade_record.get("candle_count", 3))))

        # ---------------------------------------------------------------------
        # 2. ŞABLON VE DÜZEN KURULUMU (1600 x 900 COMPOSITE)
        # ---------------------------------------------------------------------
        fig = plt.figure(figsize=(16.0, 9.0), dpi=140)
        fig.patch.set_facecolor(self.COLOR_BG)

        # 3 Panel GridSpec:
        # Sol: %72 (Üst: Mum Grafiği %58, Alt: CVD Paneli %14)
        # Sağ: %28 (HUD Telemetri & Otopsi Kartı)
        gs = GridSpec(nrows=2, ncols=2, width_ratios=[0.72, 0.28], height_ratios=[0.80, 0.20],
                       left=0.035, right=0.985, top=0.92, bottom=0.06, wspace=0.08, hspace=0.08)

        ax_chart = fig.add_subplot(gs[0, 0])
        ax_cvd = fig.add_subplot(gs[1, 0], sharex=ax_chart)
        ax_hud = fig.add_subplot(gs[:, 1])

        ax_chart.set_facecolor(self.COLOR_CHART_BG)
        ax_cvd.set_facecolor(self.COLOR_CHART_BG)
        ax_hud.set_facecolor(self.COLOR_HUD_BG)

        for ax in [ax_chart, ax_cvd]:
            ax.grid(True, color=self.COLOR_GRID, linestyle='--', linewidth=0.5, alpha=0.55)
            for spine in ax.spines.values():
                spine.set_color(self.COLOR_GRID)
                spine.set_linewidth(1.0)

        # ---------------------------------------------------------------------
        # 3. MİKROSKOBİK MUM GRAFİĞİ ÇİZİMİ
        # ---------------------------------------------------------------------
        width = 0.65
        for i, row in display_df.iterrows():
            o = float(row['open'])
            c = float(row['close'])
            h = float(row['high'])
            l = float(row['low'])
            col = self.COLOR_GREEN if c >= o else self.COLOR_RED

            ax_chart.plot([i, i], [l, h], color=col, linewidth=1.2, zorder=3)
            body_bottom = min(o, c)
            body_height = max(abs(c - o), (h - l) * 0.02)
            rect = patches.Rectangle((i - width/2, body_bottom), width, body_height,
                                     facecolor=col, edgecolor=col, alpha=0.95, zorder=4)
            ax_chart.add_patch(rect)

        min_y = float(display_df['low'].min())
        max_y = float(display_df['high'].max())
        y_span = max(max_y - min_y, 1e-6)

        # ---------------------------------------------------------------------
        # 4. MAFE KORİDORU (MFE / MAE GÖLGELENDİRME ALANI)
        # ---------------------------------------------------------------------
        if local_exit_idx > local_entry_idx and entry_price > 0:
            trade_sub_df = display_df.iloc[local_entry_idx:local_exit_idx + 1]
            if not trade_sub_df.empty:
                trade_high = float(trade_sub_df['high'].max())
                trade_low = float(trade_sub_df['low'].min())
                corridor_color = self.COLOR_GREEN if is_profit else self.COLOR_RED

                # Transparan MAFE bandı
                rect_mafe = patches.Rectangle(
                    (local_entry_idx - 0.4, trade_low),
                    (local_exit_idx - local_entry_idx + 0.8),
                    (trade_high - trade_low),
                    facecolor=corridor_color,
                    edgecolor=corridor_color,
                    linewidth=1.2,
                    linestyle='--',
                    alpha=0.08,
                    zorder=2
                )
                ax_chart.add_patch(rect_mafe)

                # MFE ve MAE Tepe / Dip etiketleri
                mfe_y = trade_high if side == "LONG" else trade_low
                mae_y = trade_low if side == "LONG" else trade_high
                ax_chart.plot([local_entry_idx, local_exit_idx], [mfe_y, mfe_y],
                              color='#38bdf8', linestyle=':', linewidth=1.0, alpha=0.7, zorder=3)
                ax_chart.text(local_entry_idx + 0.5, mfe_y,
                              f"▲ MFE ({fmt_price(mfe_y)})",
                              color='#38bdf8', fontsize=7.5, fontweight='bold', va='bottom', zorder=6)

        # ---------------------------------------------------------------------
        # 5. GİRİŞ VE ÇIKIŞ MUMU İŞARETÇİLERİ (NEON OK, NOKTA & ETİKETLER)
        # ---------------------------------------------------------------------
        entry_col = self.COLOR_GREEN if side == "LONG" else self.COLOR_RED

        # Giriş Mumu İşaretçisi
        if entry_price > 0:
            # 1. Dikey vurgulayıcı çizgi
            e_candle = display_df.iloc[local_entry_idx]
            ax_chart.plot([local_entry_idx, local_entry_idx],
                          [float(e_candle['low']) - y_span * 0.04, float(e_candle['high']) + y_span * 0.04],
                          color=entry_col, linestyle='--', linewidth=1.5, alpha=0.85, zorder=6)

            # 2. Parlak Beyaz/Neon Giriş Noktası
            ax_chart.scatter([local_entry_idx], [entry_price],
                             color='#ffffff', s=130, edgecolors=entry_col, linewidth=2.8, zorder=8)

            # 3. Giriş Fiyatı ve Zaman Etiketi
            e_time_disp = entry_time_str.split(" ")[-1] if " " in entry_time_str else ""
            e_lbl = f"★ {side} GİRİŞ: {fmt_price(entry_price)} ({e_time_disp})"
            tag_x = local_entry_idx - 1.5 if local_entry_idx > 5 else local_entry_idx + 1.5
            ha_align = 'right' if local_entry_idx > 5 else 'left'

            ax_chart.text(tag_x, entry_price, e_lbl,
                          color='#ffffff', fontsize=8.6, fontweight='bold', ha=ha_align, va='center',
                          bbox=dict(boxstyle='round,pad=0.35', facecolor='#090d16',
                                    edgecolor=entry_col, linewidth=1.5, alpha=0.98),
                          zorder=10)

        # Çıkış Mumu İşaretçisi
        if exit_price > 0:
            exit_col = theme_pnl_col
            exit_candle = display_df.iloc[local_exit_idx]

            # 1. Dikey vurgulayıcı çizgi
            ax_chart.plot([local_exit_idx, local_exit_idx],
                          [float(exit_candle['low']) - y_span * 0.04, float(exit_candle['high']) + y_span * 0.04],
                          color=exit_col, linestyle='--', linewidth=1.5, alpha=0.85, zorder=6)

            # 2. Çıkış Rozet Noktası
            marker_shape = 'o' if is_profit else 'X'
            ax_chart.scatter([local_exit_idx], [exit_price],
                             color='#ffffff', s=140, marker=marker_shape,
                             edgecolors=exit_col, linewidth=2.8, zorder=8)

            # 3. Çıkış Fiyatı ve ROE Rozeti
            x_lbl = f"★ ÇIKIŞ: {fmt_price(exit_price)} ({roe_pct:+.1f}% ROE)"
            tag_exit_x = local_exit_idx - 1.8 if local_exit_idx > 4 else local_exit_idx + 1.8
            ax_chart.text(tag_exit_x, exit_price, x_lbl,
                          color='#ffffff', fontsize=8.6, fontweight='bold', ha='right', va='center',
                          bbox=dict(boxstyle='round,pad=0.35', facecolor='#090d16',
                                    edgecolor=exit_col, linewidth=1.5, alpha=0.98),
                          zorder=10)

            # 4. Yörünge Bağlantı Çizgisi
            if entry_price > 0:
                ax_chart.plot([local_entry_idx, local_exit_idx], [entry_price, exit_price],
                              color=exit_col, linestyle='--', linewidth=2.0, alpha=0.9, zorder=7)

        # ---------------------------------------------------------------------
        # 6. KURUMSAL SEVİYELER & SAĞ MARJ FİYAT ETİKETLERİ
        # ---------------------------------------------------------------------
        cam = levels.get('camarilla', {})
        level_candidates = []

        def add_lvl(p, color, label, style='--', is_trade=False):
            if p and not np.isnan(p) and float(p) > 0:
                val = float(p)
                level_candidates.append({
                    'price': val, 'color': color, 'label': label,
                    'style': style, 'is_trade': is_trade
                })

        add_lvl(cam.get('R5'), self.COLOR_YELLOW, 'R5 Hedef', '--')
        add_lvl(cam.get('R4'), self.COLOR_ORANGE, 'R4 Breakout', '-')
        add_lvl(cam.get('R3'), '#f97316', 'R3 Direnç', ':')
        add_lvl(cam.get('P'), '#ffffff', 'Pivot P', '-')
        add_lvl(levels.get('mpoc'), self.COLOR_PURPLE, 'mPOC Hacim', '-')
        add_lvl(levels.get('above_npoc'), '#e2e8f0', 'Bakir nPOC', ':')
        add_lvl(cam.get('S3'), '#f97316', 'S3 Destek', ':')
        add_lvl(cam.get('S4'), self.COLOR_GREEN, 'S4 Breakdown', '-')
        add_lvl(cam.get('S5'), '#3b82f6', 'S5 Hedef', '--')
        add_lvl(levels.get('mval'), self.COLOR_CYAN, 'mVAL Taban', '--')
        add_lvl(levels.get('mvah'), self.COLOR_CYAN, 'mVAH Tavan', '--')

        planned_stop = float(trade_record.get('hard_stop') or trade_record.get('soft_stop') or trade_record.get('planned_stop') or 0.0)
        tp1_val = float(trade_record.get('tp1') or trade_record.get('tp1_target') or 0.0)
        tp2_val = float(trade_record.get('tp2') or trade_record.get('tp2_target') or 0.0)

        if planned_stop > 0:
            add_lvl(planned_stop, self.COLOR_RED, 'STOP KORUMASI', ':', is_trade=True)
        if tp1_val > 0:
            add_lvl(tp1_val, self.COLOR_GREEN, 'TP1 HEDEF', ':', is_trade=True)
        if tp2_val > 0:
            add_lvl(tp2_val, '#38bdf8', 'TP2 RUNNER', ':', is_trade=True)

        # Çizgi çakışma önleyici (Anti-collision solver)
        chart_min = min(min_y, entry_price if entry_price > 0 else min_y, exit_price if exit_price > 0 else min_y)
        chart_max = max(max_y, entry_price if entry_price > 0 else max_y, exit_price if exit_price > 0 else max_y)
        y_pad = max(chart_max - chart_min, 1e-6)
        padded_min = chart_min - y_pad * 0.10
        padded_max = chart_max + y_pad * 0.16

        visible_levels = [l for l in level_candidates if padded_min <= l['price'] <= padded_max]
        visible_levels.sort(key=lambda x: x['price'])

        for item in visible_levels:
            p_val = item['price']
            c = item['color']
            st = item['style']
            lbl = item['label']
            is_tr = item['is_trade']

            lw = 2.0 if is_tr else 1.0
            al = 0.95 if is_tr else 0.45
            ax_chart.plot([0, n_bars - 0.5], [p_val, p_val], color=c, linestyle=st, linewidth=lw, alpha=al, zorder=4)

            # Sağ marj etiketi
            font_sz = 8.0 if is_tr else 7.2
            font_wt = 'bold'
            bbox_kw = dict(boxstyle='round,pad=0.2', facecolor='#090d16', edgecolor=c, linewidth=1.2, alpha=0.95) if is_tr else None
            ax_chart.text(n_bars + 0.5, p_val, f"{lbl} ({fmt_price(p_val)})",
                          color=c, fontsize=font_sz, fontweight=font_wt, va='center', bbox=bbox_kw, zorder=6)

        ax_chart.set_ylim(padded_min, padded_max)
        ax_chart.set_xlim(-0.8, n_bars + 14)
        ax_chart.set_xticklabels([])  # X etiketlerini alt CVD paneline bırak

        # Üst Başlık Banner
        header_title = f"VALKYRIE QUANT FORENSIC BLACKBOX  │  #{symbol}/USDT (5M)  │  [{side} {leverage}x]"
        ax_chart.set_title(header_title, color='#ffffff', fontsize=11.5, fontweight='bold', pad=14, loc='left')

        # ---------------------------------------------------------------------
        # 7. ALT CVD / HACİM PANELİ (KÜMÜLATİF HACİM DELTASI)
        # ---------------------------------------------------------------------
        # Taker alım/satım veya sentetik CVD oluştur
        cvd_vals = []
        cur_cvd = 0.0
        for _, row in display_df.iterrows():
            vol = float(row.get('volume', 1000.0))
            c_close = float(row['close'])
            c_open = float(row['open'])
            c_high = float(row['high'])
            c_low = float(row['low'])
            c_span = max(c_high - c_low, 1e-8)
            # Fiyat kapanışına göre yaklaşık delta ağırlığı
            delta_ratio = (c_close - c_open) / c_span
            delta_vol = vol * delta_ratio
            cur_cvd += delta_vol
            cvd_vals.append(cur_cvd)

        cvd_series = np.array(cvd_vals)
        cvd_bars_diff = np.diff(np.insert(cvd_series, 0, cvd_series[0]))

        for i, val in enumerate(cvd_bars_diff):
            b_col = self.COLOR_GREEN if val >= 0 else self.COLOR_RED
            ax_cvd.bar(i, val, width=0.60, color=b_col, alpha=0.75, zorder=3)

        ax_cvd.axhline(0, color=self.COLOR_GRID, linestyle='-', linewidth=0.8, zorder=2)
        ax_cvd.set_ylabel("CVD Delta", color=self.COLOR_TEXT_MUTED, fontsize=8.0, fontweight='bold')
        ax_cvd.tick_params(colors=self.COLOR_TEXT_MUTED, labelsize=7.5)

        # Zaman ekseni
        step = max(1, n_bars // 6)
        xticks = list(range(0, n_bars, step))
        xlabels = []
        for idx in xticks:
            if time_col and idx < len(display_df):
                val = display_df[time_col].iloc[idx]
                try:
                    ts = float(val) / 1000.0 if float(val) > 1e11 else float(val)
                    xlabels.append(datetime.fromtimestamp(ts, tz=timezone(timedelta(hours=3))).strftime('%H:%M'))
                except Exception:
                    xlabels.append(f"M-{n_bars - idx}")
            else:
                xlabels.append(f"M-{n_bars - idx}")

        ax_cvd.set_xticks(xticks)
        ax_cvd.set_xticklabels(xlabels, color=self.COLOR_TEXT_MUTED, fontsize=8.0, fontweight='bold')

        # ---------------------------------------------------------------------
        # 8. BÖLÜM B: SAĞ ADLİ KARA KUTU HUD KARTI (%28)
        # ---------------------------------------------------------------------
        ax_hud.axis('off')
        for spine in ax_hud.spines.values():
            spine.set_color(self.COLOR_GRID)
            spine.set_linewidth(1.2)

        # HUD Arka Plan Kutusu
        hud_box = patches.FancyBboxPatch(
            (0.01, 0.01), 0.98, 0.98,
            boxstyle="round,pad=0.02,rounding_size=0.03",
            facecolor='#0b1122',
            edgecolor=self.COLOR_GRID,
            linewidth=1.5,
            zorder=1
        )
        ax_hud.add_patch(hud_box)

        # Metin yerleşim koordinatı
        y_cursor = 0.95

        # 1. Başlık ve Parite Kartı
        ax_hud.text(0.06, y_cursor, f"#{symbol}/USDT", color='#ffffff', fontsize=15.0, fontweight='bold', zorder=5)
        badge_txt = f"{side} {leverage}x"
        badge_bg = self.COLOR_GREEN if side == "LONG" else self.COLOR_RED
        ax_hud.text(0.72, y_cursor + 0.005, badge_txt, color='#000000', fontsize=9.0, fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.25', facecolor=badge_bg, edgecolor='none'), zorder=5)

        y_cursor -= 0.045
        status_txt = f"İcraat: KAPANDI │ Süre: {duration_str}"
        ax_hud.text(0.06, y_cursor, status_txt, color=self.COLOR_TEXT_MUTED, fontsize=8.2, fontweight='bold', zorder=5)

        y_cursor -= 0.070
        # 2. Net PnL ve ROE Banner Kartı
        pnl_card_bg = patches.Rectangle((0.05, y_cursor - 0.01), 0.90, 0.075,
                                        facecolor='#070c18', edgecolor=theme_pnl_col,
                                        linewidth=1.2, linestyle='-', zorder=2)
        ax_hud.add_patch(pnl_card_bg)

        pnl_sign = "+" if net_pnl > 0 else ""
        roe_sign = "+" if roe_pct > 0 else ""
        pnl_str = f"{pnl_sign}${net_pnl:,.2f}"
        roe_str = f"({roe_sign}{roe_pct:.2f}% ROE)"
        ax_hud.text(0.09, y_cursor + 0.032, "NET PnL:", color=self.COLOR_TEXT_MUTED, fontsize=8.5, fontweight='bold', zorder=5)
        ax_hud.text(0.09, y_cursor + 0.005, f"{pnl_str}  {roe_str}", color=theme_pnl_col, fontsize=12.5, fontweight='bold', zorder=5)

        y_cursor -= 0.055
        # 3. İŞLEM GEREKÇESİ & KURULUM (GİRİŞ ONAYLARI)
        ax_hud.text(0.06, y_cursor, "── GİRİŞ STRATEJİSİ & ONAYLAR ──", color=self.COLOR_CYAN, fontsize=8.2, fontweight='bold', zorder=5)

        y_cursor -= 0.038
        ax_hud.text(0.06, y_cursor, f"Setup: {_clean_str(setup_id, 32)}", color='#ffffff', fontsize=8.5, fontweight='bold', zorder=5)

        y_cursor -= 0.032
        conf_score = trade_record.get('confluence_score', '4/4')
        ax_hud.text(0.06, y_cursor, f"Onay Skoru: {conf_score} (Kurumsal Confluence)", color='#38bdf8', fontsize=8.0, fontweight='bold', zorder=5)

        # Onay maddeleri
        confluences = [
            f"[✓] Camarilla Rejim Sinyali ({trade_record.get('trend_regime', 'BOĞA')})",
            f"[✓] Stoikov Mikro Fiyat Dengeli ({fmt_price(trade_record.get('stoikov_micro_price', entry_price))})",
            f"[✓] Hacim Çarpanı: {float(trade_record.get('volume_surge', 1.0)):.2f}x",
            f"[✓] Fonlama Kalkanı: {float(trade_record.get('entry_funding_rate', 0.0)):.4f}%"
        ]
        for c_item in confluences:
            y_cursor -= 0.026
            ax_hud.text(0.08, y_cursor, c_item, color='#cbd5e1', fontsize=7.4, zorder=5)

        y_cursor -= 0.045
        # 4. ÇIKIŞ & PİYASA DAVRANIŞI
        ax_hud.text(0.06, y_cursor, "── ÇIKIŞ NEDENİ & TELEMETRİ ──", color=self.COLOR_YELLOW, fontsize=8.2, fontweight='bold', zorder=5)

        y_cursor -= 0.035
        clean_close_reason = _clean_str(close_reason, 36)
        ax_hud.text(0.06, y_cursor, f"Neden: {clean_close_reason}", color='#ffffff', fontsize=8.2, fontweight='bold', zorder=5)

        y_cursor -= 0.030
        mfe_val = float(trade_record.get('max_mfe_roe') or 0.0)
        mae_val = float(trade_record.get('max_mae_roe') or 0.0)
        mafe_text = f"MFE: +%{mfe_val:.2f}  │  MAE: %{mae_val:.2f}"
        ax_hud.text(0.06, y_cursor, mafe_text, color='#94a3b8', fontsize=7.8, fontweight='bold', zorder=5)

        y_cursor -= 0.030
        funding_fee_val = float(trade_record.get('funding_fee') or 0.0)
        fees_val = float(trade_record.get('fees') or 0.0)
        fees_text = f"Toplam Komisyon: ${fees_val:.3f} │ Fonlama: ${funding_fee_val:.3f}"
        ax_hud.text(0.06, y_cursor, fees_text, color='#94a3b8', fontsize=7.6, zorder=5)

        y_cursor -= 0.050
        # 5. AI ADLİ OTOPSİ TEŞHİSİ (PATOLOJİ)
        ax_hud.text(0.06, y_cursor, "── VALKYRIE AI OTOPSİ TEŞHİSİ ──", color='#ec4899', fontsize=8.2, fontweight='bold', zorder=5)

        y_cursor -= 0.038
        raw_badge = autopsy.get("diagnosis_badge", "[STANDART İCRAAT]")
        diag_badge = _clean_str(raw_badge, 40)
        diag_color = autopsy.get("diagnosis_color", self.COLOR_CYAN)
        ax_hud.text(0.06, y_cursor, diag_badge, color='#ffffff', fontsize=8.4, fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.25', facecolor='#1e1b4b', edgecolor=diag_color, linewidth=1.2), zorder=5)

        findings = autopsy.get("findings", ["İşlem kurumsal risk yönetimi sınırlarında kapatıldı."])
        for f in findings[:2]:  # Sığması için en kritik 2 bulgu
            y_cursor -= 0.032
            ax_hud.text(0.07, y_cursor, f"• {_clean_str(f, 44)}", color='#e2e8f0', fontsize=7.3, zorder=5)

        advice = autopsy.get("actionable_advice", "")
        if advice:
            y_cursor -= 0.038
            ax_hud.text(0.06, y_cursor, f"Tavsiye: {_clean_str(advice, 44)}", color='#38bdf8', fontsize=7.2, fontweight='bold', zorder=5)

        # Buffer'a kaydet
        buf = io.BytesIO()
        plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return buf


# Singleton motor
forensic_chart_engine_v2 = ForensicChartEngineV2()
