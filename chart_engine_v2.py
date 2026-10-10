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
import textwrap
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List

import matplotlib
matplotlib.use('Agg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import matplotlib.patches as patches
from matplotlib.gridspec import GridSpec


def _clean_str(text: Any, max_len: int = 50) -> str:
    if text is None:
        return ""
    s = str(text).strip()
    # Strip SMP emojis (> 0xFFFF) to ensure 100% font compatibility in Matplotlib
    s = "".join(c for c in s if ord(c) <= 0xFFFF)
    s = re.sub(r'[^\w\s\.,;:!\?\-\+\*/\(\)\[\]#\$%&@=<>_ıİğĞüÜşŞöÖçÇ★▲▼■●◆─│✓·|]', '', s)
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
    Giriş ve çıkış mumunu asla kaybetmeyen dinamik zaman penceresi,
    garantili Camarilla seviyeleri, kurumsal Hacim Profili (mPOC/nPOC), sürekli CVD alanı
    ve bağımsız adli HUD telemetri kartı içerir.
    """

    COLOR_BG = '#070b14'          # Dış Arka plan (Ultra Dark Navy)
    COLOR_CHART_BG = '#0a101f'    # Grafik alanı
    COLOR_HUD_BG = '#090e1c'      # HUD Panel alanı
    COLOR_GRID = '#1e293b'        # İnce ızgara çizgisi
    COLOR_GREEN = '#10b981'       # Neon Yeşili (Long / Win / Destek)
    COLOR_GREEN_BODY = '#059669'  # Zengin Zümrüt Yeşili (Boğa Mum Gövdesi)
    COLOR_RED = '#ef4444'         # Neon Kırmızı (Short / Loss / Direnç)
    COLOR_RED_BODY = '#991b1b'    # Zengin Yakut Kırmızı (Ayı Mum Gövdesi)
    COLOR_CYAN = '#00f2fe'        # Kuant Camgöbeği (Valkyrie Accent / Lazer Hattı)
    COLOR_YELLOW = '#eab308'      # Camarilla Altın / İkaz Seviyesi
    COLOR_ORANGE = '#fb923c'      # R4 Breakout Turuncu
    COLOR_PURPLE = '#c084fc'      # nPOC / mPOC Mor
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

        symbol = str(trade_record.get("symbol", "BTC/USDT")).replace("/USDT", "").replace(":USDT", "").replace("USDT", "")
        side = str(trade_record.get("side", "LONG")).upper()
        leverage = int(trade_record.get("leverage") or 5)
        entry_price = float(trade_record.get("entry_price") or 0.0)
        exit_price = float(trade_record.get("exit_price") or 0.0)
        net_pnl = float(trade_record.get("net_pnl") if trade_record.get("net_pnl") is not None else (trade_record.get("virtual_pnl_usd") or 0.0))
        roe_pct = float(trade_record.get("roe_pct") if trade_record.get("roe_pct") is not None else (trade_record.get("virtual_pnl_pct") or 0.0))

        # Mod Ayrımı: Canlı Piyasa Taraması vs Kapanmış İşlem
        is_manual = bool(
            trade_record.get("is_manual_scan")
            or trade_record.get("is_manual")
            or ("MANUAL" in str(trade_record.get("id", "")))
            or trade_record.get("close_reason") == "MANUEL_ANLIK_SNAPSHOT_KONTROLÜ"
        )

        close_reason = str(trade_record.get("close_reason") or "Pozisyon Kapatıldı")
        cr_upper = close_reason.upper()
        is_breakeven = (abs(roe_pct) <= 0.35) or ("BREAKEVEN" in cr_upper) or ("BAŞA-BAŞ" in cr_upper) or ("BAŞABAŞ" in cr_upper) or ("BE " in cr_upper) or ("BE)" in cr_upper)
        is_profit = not is_breakeven and ((net_pnl > 0) or (roe_pct > 0))
        if is_breakeven:
            theme_pnl_col = '#38bdf8'  # Kuant açık mavi (Breakeven koruma rengi)
        elif is_profit:
            theme_pnl_col = self.COLOR_GREEN
        else:
            theme_pnl_col = self.COLOR_RED

        entry_time_str = str(trade_record.get("entry_time", ""))
        exit_time_str = str(trade_record.get("exit_time", ""))
        duration_str = str(trade_record.get("duration", "Bilinmiyor"))
        setup_id = str(trade_record.get("setup_id") or trade_record.get("reason") or "SETUP_QUANT")

        # ---------------------------------------------------------------------
        # 1. ZAMAN KOLONU VE DİNAMİK DİLİMLEME (CANLI RADAR vs KAPALI İŞLEM)
        # ---------------------------------------------------------------------
        time_col = None
        for col in ['timestamp', 'time', 'date', 'open_time']:
            if col in df_5m.columns:
                time_col = col
                break

        timestamps = df_5m[time_col].values if time_col else list(range(len(df_5m)))

        if is_manual:
            # Canlı radar incelemesinde zengin geçmiş veri: Son 84 mum (7 saat)
            slice_len = min(84, len(df_5m))
            slice_start = max(0, len(df_5m) - slice_len)
            slice_end = len(df_5m)
            local_entry_idx = (slice_end - slice_start) - 1
            local_exit_idx = local_entry_idx
            entry_price = float(df_5m['close'].iloc[-1]) if entry_price <= 0 else entry_price
        else:
            # Giriş mumunun indeksini eşleştir
            entry_ts_sec = 0.0
            if entry_time_str:
                try:
                    entry_ts_sec = datetime.strptime(entry_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone(timedelta(hours=3))).timestamp()
                except Exception:
                    entry_ts_sec = 0.0

            entry_idx = len(df_5m) - 15
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

            exit_idx = len(df_5m) - 1
            if exit_ts_sec > 0 and time_col:
                exit_ts_val = exit_ts_sec * 1000.0 if float(timestamps[-1]) > 1e11 else exit_ts_sec
                diffs_exit = np.abs(np.array(timestamps, dtype=float) - exit_ts_val)
                exit_idx = int(np.argmin(diffs_exit))
                if exit_idx < entry_idx:
                    exit_idx = entry_idx + 1

            slice_start = max(0, entry_idx - 50)
            slice_end = min(len(df_5m), exit_idx + 18)
            if slice_end - slice_start < 72:
                slice_start = max(0, slice_end - 80)
                slice_end = min(len(df_5m), slice_start + 80)

            local_entry_idx = max(0, min(slice_end - slice_start - 1, entry_idx - slice_start))
            local_exit_idx = max(0, min(slice_end - slice_start - 1, exit_idx - slice_start))
            if local_exit_idx <= local_entry_idx:
                local_exit_idx = min(slice_end - slice_start - 1, local_entry_idx + max(1, int(trade_record.get("candle_count", 3))))

        # 🏛️ MODEL 1: BİRLEŞİK YAŞAM DÖNGÜSÜ (Alt-Bacak Eşleştirmesi)
        sub_legs = trade_record.get("sub_legs") or []
        local_tp1_idx = None
        tp1_exit_p = 0.0
        leg1_pnl = 0.0
        leg2_pnl = 0.0
        if not is_manual and sub_legs and len(sub_legs) >= 2:
            tp1_time_str = sub_legs[0].get("exit_time", "")
            tp1_exit_p = float(sub_legs[0].get("exit_price") or 0.0)
            leg1_pnl = float(sub_legs[0].get("net_pnl") or 0.0)
            leg2_pnl = float(sub_legs[1].get("net_pnl") or 0.0)
            tp1_ts_sec = 0.0
            if tp1_time_str:
                try:
                    tp1_ts_sec = datetime.strptime(tp1_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone(timedelta(hours=3))).timestamp()
                except Exception:
                    tp1_ts_sec = 0.0
            if tp1_ts_sec > 0 and time_col:
                tp1_ts_val = tp1_ts_sec * 1000.0 if float(timestamps[-1]) > 1e11 else tp1_ts_sec
                diffs_tp1 = np.abs(np.array(timestamps, dtype=float) - tp1_ts_val)
                tp1_idx = int(np.argmin(diffs_tp1))
                local_tp1_idx = max(0, min(slice_end - slice_start - 1, tp1_idx - slice_start))
            else:
                local_tp1_idx = int((local_entry_idx + local_exit_idx) // 2)

        display_df = df_5m.iloc[slice_start:slice_end].copy().reset_index(drop=True)
        n_bars = len(display_df)

        mpoc_val = float(levels.get('mpoc', 0.0)) if levels else 0.0
        npoc_val = float(levels.get('above_npoc', 0.0)) if levels else 0.0

        # ---------------------------------------------------------------------
        # 3. CAMARILLA SEVİYE GÜVENCESİ (FALLBACK HESAPLAMA MOTORU)
        # ---------------------------------------------------------------------
        cam = dict(levels.get('camarilla', {})) if isinstance(levels.get('camarilla'), dict) else {}
        # Eğer Camarilla eksikse son 288 mum (24 saat) üzerinden anında hesapla
        required_cam_keys = ['P', 'R3', 'R4', 'R5', 'S3', 'S4', 'S5']
        if not cam or not all(k in cam and cam[k] is not None for k in ['P', 'R3', 'R4', 'S3', 'S4']):
            sub_cam_df = df_5m.iloc[-288:] if len(df_5m) > 288 else df_5m
            ch = float(sub_cam_df['high'].max())
            cl = float(sub_cam_df['low'].min())
            cc = float(sub_cam_df['close'].iloc[-1])
            rng = max(ch - cl, 1e-6)
            fallback_cam = {
                "P": float((ch + cl + cc) / 3.0),
                "R3": float(cc + rng * 1.1 / 4.0),
                "R4": float(cc + rng * 1.1 / 2.0),
                "R5": float((ch / cl) * cc if cl > 0 else cc * 1.05),
                "S3": float(cc - rng * 1.1 / 4.0),
                "S4": float(cc - rng * 1.1 / 2.0),
                "S5": float(max(cc * 0.05, cc - ((ch / cl) * cc - cc)) if cl > 0 else cc * 0.95)
            }
            for k, v in fallback_cam.items():
                if k not in cam or cam[k] is None or np.isnan(cam[k]):
                    cam[k] = v

        # ---------------------------------------------------------------------
        # 3b. VWAP HESAPLAMA (SEANS / ROLLING VWAP + ANCHORED AVWAP)
        # ---------------------------------------------------------------------
        vol_arr = pd.to_numeric(display_df.get('volume', 1000.0), errors='coerce').fillna(1000.0).values
        high_arr = pd.to_numeric(display_df['high'], errors='coerce').values
        low_arr = pd.to_numeric(display_df['low'], errors='coerce').values
        close_arr = pd.to_numeric(display_df['close'], errors='coerce').values
        typ_arr = (high_arr + low_arr + close_arr) / 3.0

        cum_vol = np.cumsum(vol_arr)
        cum_vol[cum_vol == 0] = 1.0
        vwap_series = np.cumsum(typ_arr * vol_arr) / cum_vol
        cur_vwap = float(vwap_series[-1]) if len(vwap_series) > 0 else 0.0

        tepe_avwap = float(levels.get('tepe_avwap', 0.0)) if levels else 0.0
        dip_avwap = float(levels.get('dip_avwap', 0.0)) if levels else 0.0

        # ---------------------------------------------------------------------
        # 4. ŞABLON VE DÜZEN KURULUMU (1600 x 900 COMPOSITE)
        # ---------------------------------------------------------------------
        fig = Figure(figsize=(16.0, 9.0), dpi=100)
        canvas = FigureCanvas(fig)
        fig.patch.set_facecolor(self.COLOR_BG)

        # 3 Panel GridSpec: Sol %75 (Mum %83, CVD %17) │ Sağ %25 (HUD Telemetri)
        gs = GridSpec(nrows=2, ncols=2, width_ratios=[0.75, 0.25], height_ratios=[0.83, 0.17],
                      left=0.025, right=0.985, top=0.94, bottom=0.055, wspace=0.11, hspace=0.05)

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
        # 5. DİNAMİK Y-EKSENİ ÖLÇEKLEME (CAMARILLA & VWAP KORİDORU)
        # ---------------------------------------------------------------------
        min_y = float(display_df['low'].min())
        max_y = float(display_df['high'].max())

        scale_anchors = [min_y, max_y]
        if entry_price > 0:
            scale_anchors.append(entry_price)
        if not is_manual and exit_price > 0:
            scale_anchors.append(exit_price)
        if cur_vwap > 0:
            scale_anchors.append(cur_vwap)
        if tepe_avwap > 0 and tepe_avwap <= max_y * 1.15:
            scale_anchors.append(tepe_avwap)
        if dip_avwap > 0 and dip_avwap >= min_y * 0.85:
            scale_anchors.append(dip_avwap)

        planned_stop = float(trade_record.get('hard_stop') or trade_record.get('soft_stop') or trade_record.get('planned_stop') or 0.0)
        tp1_val = float(trade_record.get('tp1') or trade_record.get('tp1_target') or 0.0)
        if planned_stop > 0:
            scale_anchors.append(planned_stop)
        if tp1_val > 0:
            scale_anchors.append(tp1_val)

        # Camarilla R4, R3, P, S3, S4 seviyelerini Y-Eksenine dahil et
        s4_val = float(cam.get('S4', 0.0))
        r4_val = float(cam.get('R4', 0.0))
        p_val = float(cam.get('P', 0.0))
        s3_val = float(cam.get('S3', 0.0))
        r3_val = float(cam.get('R3', 0.0))

        if s4_val > 0 and s4_val >= min_y * 0.88:
            scale_anchors.append(s4_val)
        if r4_val > 0 and r4_val <= max_y * 1.12:
            scale_anchors.append(r4_val)
        if p_val > 0:
            scale_anchors.append(p_val)

        chart_min = min(scale_anchors)
        chart_max = max(scale_anchors)
        y_span = max(chart_max - chart_min, 1e-6)

        padded_min = chart_min - y_span * 0.09
        padded_max = chart_max + y_span * 0.11

        # ---------------------------------------------------------------------
        # 6. CAMARILLA TAKTİKSEL KORİDOR GÖLGELENDİRMESİ
        # ---------------------------------------------------------------------
        # S4 ile R4 Arası Taktiksel Kırılım Koridoru (Yarı şeffaf kuant mavi)
        if s4_val > 0 and r4_val > 0:
            ax_chart.axhspan(s4_val, r4_val, color='#0284c7', alpha=0.035, zorder=1)
        # S3 ile R3 Arası Konsolidasyon / Mean-Reversion Bölgesi (Yarı şeffaf altın)
        if s3_val > 0 and r3_val > 0:
            ax_chart.axhspan(s3_val, r3_val, color='#eab308', alpha=0.035, zorder=1)

        # ---------------------------------------------------------------------
        # 7. MİKROSKOBİK MUM GRAFİĞİ ÇİZİMİ (BLOOMBERG PRO AESTHETICS)
        # ---------------------------------------------------------------------
        width = 0.72
        for i, row in display_df.iterrows():
            o = float(row['open'])
            c = float(row['close'])
            h = float(row['high'])
            l = float(row['low'])

            if c >= o:
                wick_col = self.COLOR_GREEN
                body_face = self.COLOR_GREEN_BODY
                body_edge = self.COLOR_GREEN
            else:
                wick_col = self.COLOR_RED
                body_face = self.COLOR_RED_BODY
                body_edge = self.COLOR_RED

            # Fitil (Wick)
            ax_chart.plot([i, i], [l, h], color=wick_col, linewidth=1.2, zorder=3)

            # Mum Gövdesi (Body)
            body_bottom = min(o, c)
            body_height = abs(c - o)
            if body_height < 1e-8:
                # Doji Barı
                ax_chart.plot([i - width/2, i + width/2], [c, c], color='#e2e8f0', linewidth=1.5, zorder=4)
            else:
                rect = patches.Rectangle(
                    (i - width/2, body_bottom), width, body_height,
                    facecolor=body_face, edgecolor=body_edge, linewidth=0.85, alpha=0.96, zorder=4
                )
                ax_chart.add_patch(rect)

        # ---------------------------------------------------------------------
        # 7b. SEANS VWAP EĞRİSİ ÇİZİMİ
        # ---------------------------------------------------------------------
        if len(vwap_series) == n_bars and cur_vwap > 0:
            ax_chart.plot(range(n_bars), vwap_series, color='#38bdf8', linestyle='-', linewidth=1.7, alpha=0.90, label='VWAP', zorder=5)

        # ---------------------------------------------------------------------
        # 8. KURUMSAL SEVİYE ÖZET BİLGİ ROZETİ (SOL ÜST - AXES KİLİTLİ)
        # ---------------------------------------------------------------------
        institutional_tag = f"■ PIVOT (P): {fmt_price(p_val)}   ■ VWAP: {fmt_price(cur_vwap)}   ■ mPOC: {fmt_price(mpoc_val)}" if mpoc_val > 0 else f"■ PIVOT (P): {fmt_price(p_val)}   ■ VWAP: {fmt_price(cur_vwap)}"
        ax_chart.text(0.015, 0.965, institutional_tag, transform=ax_chart.transAxes,
                      color='#cbd5e1', fontsize=7.8, fontweight='bold',
                      bbox=dict(boxstyle='round,pad=0.25', facecolor='#090d16', edgecolor='#334155', linewidth=0.8, alpha=0.90),
                      zorder=18)

        # ---------------------------------------------------------------------
        # 9. GİRİŞ & ÇIKIŞ VEYA CANLI RADAR İŞARETÇİLERİ
        # ---------------------------------------------------------------------
        if is_manual:
            # =================================================================
            # CANLI PİYASA RADARI: HEDEF LAZER VE CANLI MUM İŞARETÇİSİ
            # =================================================================
            cur_market_p = entry_price

            # 1. Yatay Canlı Fiyat Lazer Rehberi
            ax_chart.axhline(cur_market_p, color=self.COLOR_CYAN, linestyle='--', linewidth=1.5, alpha=0.85, zorder=6)

            # 2. Canlı Mum Dikey Vurgu Çizgisi
            live_candle = display_df.iloc[local_entry_idx]
            ax_chart.plot([local_entry_idx, local_entry_idx],
                          [float(live_candle['low']) - y_span * 0.03, float(live_candle['high']) + y_span * 0.03],
                          color=self.COLOR_CYAN, linestyle=':', linewidth=1.8, alpha=0.95, zorder=7)

            # 3. Parlak Canlı Radar Crosshair Noktası
            ax_chart.scatter([local_entry_idx], [cur_market_p],
                             color='#ffffff', s=150, marker='o', edgecolors=self.COLOR_CYAN, linewidth=2.8, zorder=9)

            # 4. Canlı Tespit Rozeti
            radar_lbl = f"◆ CANLI PİYASA TESPİTİ: {fmt_price(cur_market_p)}"
            ax_chart.text(local_entry_idx - 1.2, cur_market_p, radar_lbl,
                          color='#ffffff', fontsize=8.8, fontweight='bold', ha='right', va='center',
                          bbox=dict(boxstyle='round,pad=0.35', facecolor='#090d16',
                                    edgecolor=self.COLOR_CYAN, linewidth=1.6, alpha=0.98),
                          zorder=11)

            # 5. Mum Üstü Vurgu Oku
            top_y = float(live_candle['high']) + y_span * 0.02
            ax_chart.text(local_entry_idx, top_y, "▲ CANLI RADAR MUMU",
                          color=self.COLOR_CYAN, fontsize=7.2, fontweight='bold', ha='center', va='bottom', zorder=10)

        else:
            # =================================================================
            # KAPALI İŞLEM: KUSURSUZ GİRİŞ, ÇIKIŞ VE MAFE İZİ (ÇAKIŞMA ÖNLEYİCİ MİMARİ)
            # =================================================================
            entry_col = self.COLOR_GREEN if side == "LONG" else self.COLOR_RED
            exit_col = theme_pnl_col

            e_candle = display_df.iloc[local_entry_idx] if (entry_price > 0 and local_entry_idx < len(display_df)) else None
            exit_candle = display_df.iloc[local_exit_idx] if (exit_price > 0 and local_exit_idx < len(display_df)) else None

            # 1. MAFE Koridoru
            if local_exit_idx > local_entry_idx and entry_price > 0:
                trade_sub_df = display_df.iloc[local_entry_idx:local_exit_idx + 1]
                if not trade_sub_df.empty:
                    trade_high = float(trade_sub_df['high'].max())
                    trade_low = float(trade_sub_df['low'].min())
                    corridor_color = theme_pnl_col

                    rect_mafe = patches.Rectangle(
                        (local_entry_idx - 0.4, trade_low),
                        (local_exit_idx - local_entry_idx + 0.8),
                        (trade_high - trade_low),
                        facecolor=corridor_color, edgecolor=corridor_color,
                        linewidth=1.2, linestyle='--', alpha=0.07, zorder=2
                    )
                    ax_chart.add_patch(rect_mafe)

                    mfe_y = trade_high if side == "LONG" else trade_low
                    ax_chart.plot([local_entry_idx, local_exit_idx], [mfe_y, mfe_y],
                                  color='#38bdf8', linestyle=':', linewidth=1.0, alpha=0.6, zorder=3)
                    ax_chart.text(local_entry_idx + 0.5, mfe_y,
                                  f"▲ MFE ({fmt_price(mfe_y)})",
                                  color='#38bdf8', fontsize=7.2, fontweight='bold', va='bottom', zorder=6)

            # 2. Dikey Zıt-Kutup Konumlandırması (Opposite-Pole Placement)
            # LONG işleminde: Giriş destekte/altta yer alır, Çıkış ise KESİNLİKLE üstte yer alır.
            # SHORT işleminde: Giriş dirençte/üstte yer alır, Çıkış ise KESİNLİKLE altta yer alır.
            # Bu geometrik kural; giriş ve çıkış fiyatları tıpatıp eşit (Breakeven) veya birbirine
            # çok yakın olsa dahi, iki etiketin yatayda veya dikeyde BİRBİRİNİ ÖRTMESİNİ İMKANSIZ KILAR!
            entry_is_bottom = (side == "LONG")

            # A. GİRİŞ İŞARETÇİSİ VE ROZETİ
            if entry_price > 0 and e_candle is not None:
                c_low = float(e_candle['low'])
                c_high = float(e_candle['high'])

                # Dikey lazer rehber çizgisi
                ax_chart.plot(
                    [local_entry_idx, local_entry_idx],
                    [c_low - y_span * 0.02, c_high + y_span * 0.02],
                    color=entry_col, linestyle='--', linewidth=1.5, alpha=0.75, zorder=6
                )
                # Giriş Fiyat Noktası (Parıldayan kurumsal halka)
                ax_chart.scatter(
                    [local_entry_idx], [entry_price],
                    color='#ffffff', s=120, marker='o', edgecolors=entry_col, linewidth=2.5, zorder=12
                )

                e_time_disp = entry_time_str.split(" ")[-1] if " " in entry_time_str else ""
                e_lbl = f"▲ LONG GİRİŞ: {fmt_price(entry_price)} ({e_time_disp})" if side == "LONG" else f"▼ SHORT GİRİŞ: {fmt_price(entry_price)} ({e_time_disp})"

                if entry_is_bottom:
                    y_entry_badge = c_low - y_span * 0.048
                    va_entry = 'top'
                    ax_chart.plot([local_entry_idx, local_entry_idx], [y_entry_badge, c_low],
                                  color=entry_col, linestyle=':', linewidth=1.2, alpha=0.8, zorder=7)
                else:
                    y_entry_badge = c_high + y_span * 0.048
                    va_entry = 'bottom'
                    ax_chart.plot([local_entry_idx, local_entry_idx], [c_high, y_entry_badge],
                                  color=entry_col, linestyle=':', linewidth=1.2, alpha=0.8, zorder=7)

                if local_entry_idx < 8:
                    tag_entry_x = max(0.5, local_entry_idx + 0.3)
                    ha_entry = 'left'
                elif local_entry_idx > n_bars - 8:
                    tag_entry_x = min(n_bars - 1.0, local_entry_idx - 0.3)
                    ha_entry = 'right'
                else:
                    tag_entry_x = local_entry_idx
                    ha_entry = 'center'

                ax_chart.text(
                    tag_entry_x, y_entry_badge, e_lbl,
                    color='#ffffff', fontsize=8.4, fontweight='bold', ha=ha_entry, va=va_entry,
                    bbox=dict(boxstyle='round,pad=0.32', facecolor='#090d16',
                              edgecolor=entry_col, linewidth=1.5, alpha=0.98),
                    zorder=15
                )

            # B. ÇIKIŞ İŞARETÇİSİ VE ROZETİ (Girişin Tam Zıt Kutusunda)
            if local_tp1_idx is not None and tp1_exit_p > 0 and len(sub_legs) >= 2:
                # 🏛️ MODEL 1: BİRLEŞİK YAŞAM DÖNGÜSÜ (2 PARÇALI ÇIKIŞ ÇİZİMİ)
                # 1. Bacak: TP1 Kâr Satışı
                tp1_candle = display_df.iloc[local_tp1_idx] if local_tp1_idx < len(display_df) else None
                if tp1_candle is not None:
                    tp1_low = float(tp1_candle['low'])
                    tp1_high = float(tp1_candle['high'])
                    ax_chart.plot(
                        [local_tp1_idx, local_tp1_idx],
                        [tp1_low - y_span * 0.02, tp1_high + y_span * 0.02],
                        color='#10b981', linestyle='--', linewidth=1.5, alpha=0.75, zorder=6
                    )
                    ax_chart.scatter(
                        [local_tp1_idx], [tp1_exit_p],
                        color='#ffffff', s=130, marker='D',
                        edgecolors='#10b981', linewidth=2.5, zorder=12
                    )
                    tp1_badge_y = tp1_high + y_span * 0.048 if entry_is_bottom else tp1_low - y_span * 0.048
                    tp1_va = 'bottom' if entry_is_bottom else 'top'
                    tp1_lbl = f"🎯 TP1 (%50): {fmt_price(tp1_exit_p)} (+${leg1_pnl:.2f})"
                    ax_chart.text(
                        local_tp1_idx, tp1_badge_y, tp1_lbl,
                        color='#ffffff', fontsize=8.0, fontweight='bold', ha='center', va=tp1_va,
                        bbox=dict(boxstyle='round,pad=0.28', facecolor='#090d16',
                                  edgecolor='#10b981', linewidth=1.5, alpha=0.98),
                        zorder=15
                    )
                    if entry_price > 0:
                        ax_chart.plot(
                            [local_entry_idx, local_tp1_idx], [entry_price, tp1_exit_p],
                            color='#10b981', linestyle='--', linewidth=1.5, alpha=0.85, zorder=8
                        )

                # 2. Bacak: Runner / Nihai Çıkış
                if exit_price > 0 and exit_candle is not None:
                    x_low = float(exit_candle['low'])
                    x_high = float(exit_candle['high'])
                    leg2_col = '#10b981' if leg2_pnl >= 0 else ('#38bdf8' if abs(leg2_pnl) < 1.0 else '#ef4444')
                    ax_chart.plot(
                        [local_exit_idx, local_exit_idx],
                        [x_low - y_span * 0.02, x_high + y_span * 0.02],
                        color=leg2_col, linestyle='--', linewidth=1.5, alpha=0.75, zorder=6
                    )
                    ax_chart.scatter(
                        [local_exit_idx], [exit_price],
                        color='#ffffff', s=130, marker='o' if leg2_pnl >= 0 else 'X',
                        edgecolors=leg2_col, linewidth=2.5, zorder=12
                    )
                    x_lbl = f"🏁 NİHAİ (%50): {fmt_price(exit_price)} (${leg2_pnl:+.2f})"
                    y_exit_badge = x_high + y_span * 0.048 if entry_is_bottom else x_low - y_span * 0.048
                    va_exit = 'bottom' if entry_is_bottom else 'top'
                    tag_exit_x = min(n_bars - 1.0, max(0.5, local_exit_idx))
                    ax_chart.text(
                        tag_exit_x, y_exit_badge, x_lbl,
                        color='#ffffff', fontsize=8.0, fontweight='bold', ha='center', va=va_exit,
                        bbox=dict(boxstyle='round,pad=0.28', facecolor='#090d16',
                                  edgecolor=leg2_col, linewidth=1.5, alpha=0.98),
                        zorder=15
                    )
                    if tp1_exit_p > 0:
                        ax_chart.plot(
                            [local_tp1_idx, local_exit_idx], [tp1_exit_p, exit_price],
                            color=leg2_col, linestyle=':', linewidth=1.5, alpha=0.85, zorder=8
                        )

            elif exit_price > 0 and exit_candle is not None:
                x_low = float(exit_candle['low'])
                x_high = float(exit_candle['high'])

                # Dikey lazer rehber çizgisi
                ax_chart.plot(
                    [local_exit_idx, local_exit_idx],
                    [x_low - y_span * 0.02, x_high + y_span * 0.02],
                    color=exit_col, linestyle='--', linewidth=1.5, alpha=0.75, zorder=6
                )
                # Çıkış Fiyat Noktası (Kârda 'o', Zararda 'X', Başa-başta 'D')
                marker_shape = 'D' if is_breakeven else ('o' if is_profit else 'X')
                ax_chart.scatter(
                    [local_exit_idx], [exit_price],
                    color='#ffffff', s=130, marker=marker_shape,
                    edgecolors=exit_col, linewidth=2.5, zorder=12
                )

                x_prefix = "▼" if entry_is_bottom else "▲"
                x_lbl = f"{x_prefix} ÇIKIŞ: {fmt_price(exit_price)} ({roe_pct:+.1f}% ROE)"

                if entry_is_bottom:
                    # Giriş altta olduğundan ÇIKIŞ KESİNLİKLE ÜSTTE yer alır
                    y_exit_badge = x_high + y_span * 0.048
                    va_exit = 'bottom'
                    ax_chart.plot([local_exit_idx, local_exit_idx], [x_high, y_exit_badge],
                                  color=exit_col, linestyle=':', linewidth=1.2, alpha=0.8, zorder=7)
                else:
                    # Giriş üstte olduğundan ÇIKIŞ KESİNLİKLE ALTTA yer alır
                    y_exit_badge = x_low - y_span * 0.048
                    va_exit = 'top'
                    ax_chart.plot([local_exit_idx, local_exit_idx], [y_exit_badge, x_low],
                                  color=exit_col, linestyle=':', linewidth=1.2, alpha=0.8, zorder=7)

                if local_exit_idx > n_bars - 8:
                    tag_exit_x = min(n_bars - 1.0, local_exit_idx - 0.3)
                    ha_exit = 'right'
                elif local_exit_idx < 8:
                    tag_exit_x = max(0.5, local_exit_idx + 0.3)
                    ha_exit = 'left'
                else:
                    tag_exit_x = local_exit_idx
                    ha_exit = 'center'

                ax_chart.text(
                    tag_exit_x, y_exit_badge, x_lbl,
                    color='#ffffff', fontsize=8.4, fontweight='bold', ha=ha_exit, va=va_exit,
                    bbox=dict(boxstyle='round,pad=0.32', facecolor='#090d16',
                              edgecolor=exit_col, linewidth=1.5, alpha=0.98),
                    zorder=15
                )

                # Yörünge Bağlantı Çizgisi (İşlem Girişinden Çıkışına Kusursuz Yol)
                if entry_price > 0:
                    ax_chart.plot(
                        [local_entry_idx, local_exit_idx], [entry_price, exit_price],
                        color=exit_col, linestyle='--', linewidth=1.8, alpha=0.85, zorder=8
                    )

        # ---------------------------------------------------------------------
        # 10. KURUMSAL SEVİYELER & SAĞ MARJ ROZETLERİ (ÇAKIŞMA ÖNLEYİCİ)
        # ---------------------------------------------------------------------
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
        add_lvl(cam.get('R3'), '#f59e0b', 'R3 Direnç', ':')
        add_lvl(cam.get('P'), '#f8fafc', 'Pivot P', '--')
        add_lvl(levels.get('mpoc'), self.COLOR_PURPLE, 'mPOC Hacim', '-')
        add_lvl(levels.get('above_npoc'), '#e2e8f0', 'Bakir nPOC', ':')
        add_lvl(cam.get('S3'), '#f59e0b', 'S3 Destek', ':')
        add_lvl(cam.get('S4'), self.COLOR_GREEN, 'S4 Breakdown', '-')
        add_lvl(cam.get('S5'), '#38bdf8', 'S5 Hedef', '--')
        add_lvl(levels.get('mval'), self.COLOR_CYAN, 'mVAL Taban', ':')
        add_lvl(levels.get('mvah'), self.COLOR_CYAN, 'mVAH Tavan', ':')

        # Kurumsal AVWAP & Seans VWAP Seviyeleri
        if cur_vwap > 0:
            add_lvl(cur_vwap, '#38bdf8', 'Seans VWAP', '--')
        if tepe_avwap > 0:
            add_lvl(tepe_avwap, self.COLOR_RED, 'Tepe AVWAP', '--')
        if dip_avwap > 0:
            add_lvl(dip_avwap, '#ffffff', 'Dip AVWAP', '--')

        if not is_manual:
            if planned_stop > 0:
                add_lvl(planned_stop, self.COLOR_RED, 'STOP KORUMASI', ':', is_trade=True)
            if tp1_val > 0:
                add_lvl(tp1_val, self.COLOR_GREEN, 'TP1 HEDEF', ':', is_trade=True)
            tp2_val = float(trade_record.get('tp2') or trade_record.get('tp2_target') or 0.0)
            if tp2_val > 0:
                add_lvl(tp2_val, '#38bdf8', 'TP2 RUNNER', ':', is_trade=True)

        visible_levels = [l for l in level_candidates if padded_min <= l['price'] <= padded_max]
        visible_levels.sort(key=lambda x: x['price'])

        # ---------------------------------------------------------------------
        # FERAH SAĞ KORİDOR & MİKRO-BİRLEŞTİRME & YAYLI ÇAKIŞMA ÖNLEYİCİ
        # ---------------------------------------------------------------------
        # 1. Mumların sağında seviye etiketleri ve göstergeler için ferah sağ koridor (%35 genişletilmiş alan)
        right_margin_bars = max(28, int(n_bars * 0.35))
        chart_x_max = n_bars + right_margin_bars

        # 2. Birbirine aşırı yakın (< %0.18) göstergeleri birleştir (İşlem STOP/TP seviyeleri ASLA birleştirilmez!)
        merged_levels = []
        for item in visible_levels:
            if not merged_levels:
                merged_levels.append(dict(item))
            else:
                prev = merged_levels[-1]
                pct_diff = abs(item['price'] - prev['price']) / max(prev['price'], 1e-6)
                if (pct_diff < 0.0018 
                    and not prev.get('is_trade') 
                    and not item.get('is_trade') 
                    and prev['label'].count('│') == 0):
                    prev['label'] = f"{prev['label']} │ {item['label']}"
                else:
                    merged_levels.append(dict(item))

        # 3. İki Yönlü Yaylı İtme (Spring Relaxation) Çakışma Önleyici Motoru
        n_lvl = len(merged_levels)
        target_y_positions = [item['price'] for item in merged_levels]
        min_label_gap = max(y_span * 0.046, 1e-6)

        for _ in range(80):
            moved = False
            for i in range(n_lvl - 1):
                gap = target_y_positions[i+1] - target_y_positions[i]
                if gap < min_label_gap:
                    push = (min_label_gap - gap) / 2.0
                    target_y_positions[i] -= push
                    target_y_positions[i+1] += push
                    moved = True
            for i in range(n_lvl):
                if target_y_positions[i] < padded_min + y_span * 0.02:
                    target_y_positions[i] = padded_min + y_span * 0.02
                elif target_y_positions[i] > padded_max - y_span * 0.02:
                    target_y_positions[i] = padded_max - y_span * 0.02
            if not moved:
                break

        # 4. Çizgileri ve Sağ Koridor Etiketlerini Çiz (Mumların Üzerine Asla Binmez)
        tag_start_x = n_bars + 2.5

        for idx_l, item in enumerate(merged_levels):
            p_val = item['price']
            lbl_y = target_y_positions[idx_l]
            c = item['color']
            st = item['style']
            lbl = item['label']
            is_tr = item.get('is_trade', False)

            lw = 1.6 if is_tr else 0.95
            al = 0.92 if is_tr else 0.42

            # A. Ana yatay seviye çizgisi (Mumlar boyunca uzanır, mum bitiminde sonlanır)
            ax_chart.plot([0, n_bars + 1.0], [p_val, p_val], color=c, linestyle=st, linewidth=lw, alpha=al, zorder=4)

            # B. Seviye çizgisinden sağdaki etikete kesikli kılavuz rehber hattı
            ax_chart.plot([n_bars + 1.0, tag_start_x - 0.4], [p_val, lbl_y], color=c, linestyle=':', linewidth=0.85, alpha=0.55, zorder=5)

            # C. Seviye Etiket Rozeti (Mumların tamamen sağında, sağa doğru genişler: ha='left')
            font_sz = 7.4 if is_tr else 6.8
            font_wt = 'bold'
            bbox_kw = dict(boxstyle='round,pad=0.25', facecolor='#090d16', edgecolor=c, linewidth=1.1, alpha=0.96)
            ax_chart.text(
                tag_start_x, lbl_y, f"{lbl}: {fmt_price(p_val)}",
                color=c, fontsize=font_sz, fontweight=font_wt, va='center', ha='left',
                bbox=bbox_kw, zorder=6
            )

        ax_chart.set_ylim(padded_min, padded_max)
        ax_chart.set_xlim(-0.8, chart_x_max)
        ax_chart.tick_params(axis='x', labelbottom=False, bottom=False)

        # =====================================================================
        # SAĞ FİYAT SKALASI (TRADINGVIEW / BINANCE STANDARDI)
        # =====================================================================
        def fmt_axis_price(val, pos=None):
            if val is None or np.isnan(val) or val <= 0:
                return ""
            if val >= 1000:
                return f"${val:,.0f}"
            elif val >= 10:
                return f"${val:.1f}"
            elif val >= 1:
                return f"${val:.2f}"
            elif val >= 0.01:
                return f"${val:.4f}"
            else:
                return f"${val:.6f}"

        ax_chart.yaxis.tick_right()
        ax_chart.yaxis.set_label_position("right")
        ax_chart.tick_params(axis='y', colors='#94a3b8', labelsize=8.0, labelcolor='#e2e8f0', length=5, width=1.1, pad=5)
        ax_chart.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(fmt_axis_price))

        # Sağ Skala Üzerinde Anlık / Kapanış Fiyat Rozeti (TradingView Stili - Sağ Skalada Hizalı)
        cur_active_price = entry_price if is_manual else exit_price
        cur_p_color = self.COLOR_CYAN if is_manual else theme_pnl_col
        if cur_active_price > 0:
            # Fiyat seviyesinde sağ skalaya kadar kesikli lazer hattı
            ax_chart.plot([n_bars + 1.0, chart_x_max - 0.5], [cur_active_price, cur_active_price],
                          color=cur_p_color, linestyle='--', linewidth=1.1, alpha=0.75, zorder=7)
            # Sağ skala üzerinde fütüristik fiyat kutusu
            ax_chart.text(
                chart_x_max - 0.2, cur_active_price, f" ▶ {fmt_price(cur_active_price)} ",
                color='#ffffff', fontsize=8.6, fontweight='bold', va='center', ha='right',
                bbox=dict(boxstyle='square,pad=0.28', facecolor=cur_p_color, edgecolor='#ffffff', linewidth=0.8),
                zorder=20
            )

        # Üst Başlık Banner
        if is_manual:
            header_title = f"VALKYRIE QUANT FORENSIC RADAR  │  #{symbol}/USDT (5M)  │  [CANLI PİYASA GÖZLEMİ & OTOPSİ]"
        else:
            header_title = f"VALKYRIE QUANT FORENSIC BLACKBOX  │  #{symbol}/USDT (5M)  │  [{side} {leverage}x]"
        ax_chart.set_title(header_title, color='#ffffff', fontsize=11.2, fontweight='bold', pad=14, loc='left')

        # ---------------------------------------------------------------------
        # 11. ALT CVD & HACİM PANELİ (SÜREKLİ ALAN GRAFİĞİ + DELTA)
        # ---------------------------------------------------------------------
        cvd_vals = []
        cur_cvd = 0.0
        for _, row in display_df.iterrows():
            vol = float(row.get('volume', 1000.0))
            c_close = float(row['close'])
            c_open = float(row['open'])
            c_high = float(row['high'])
            c_low = float(row['low'])
            c_span = max(c_high - c_low, 1e-8)
            delta_ratio = (c_close - c_open) / c_span
            delta_vol = vol * delta_ratio
            cur_cvd += delta_vol
            cvd_vals.append(cur_cvd)

        cvd_series = np.array(cvd_vals)
        cvd_bars_diff = np.diff(np.insert(cvd_series, 0, cvd_series[0]))

        # Delta Histogram Barları
        for i, val in enumerate(cvd_bars_diff):
            b_col = self.COLOR_GREEN if val >= 0 else self.COLOR_RED
            ax_cvd.bar(i, val, width=0.55, color=b_col, alpha=0.45, zorder=3)

        # Sürekli CVD Çizgisi ve Renkli Alan Doldurma (Area Fill)
        ax_cvd.plot(range(n_bars), cvd_series, color=self.COLOR_CYAN, linewidth=1.5, zorder=5)
        ax_cvd.fill_between(range(n_bars), 0, cvd_series, where=(cvd_series >= 0),
                            color=self.COLOR_GREEN, alpha=0.18, zorder=2)
        ax_cvd.fill_between(range(n_bars), 0, cvd_series, where=(cvd_series < 0),
                            color=self.COLOR_RED, alpha=0.18, zorder=2)

        ax_cvd.axhline(0, color=self.COLOR_GRID, linestyle='-', linewidth=0.8, zorder=2)
        ax_cvd.yaxis.tick_right()
        ax_cvd.yaxis.set_label_position("right")
        ax_cvd.tick_params(axis='y', colors=self.COLOR_TEXT_MUTED, labelsize=7.2, pad=4)

        # CVD Gösterge Başlık Rozeti (Sol Üst)
        cvd_ylim = ax_cvd.get_ylim()
        cvd_top_y = cvd_ylim[1] if cvd_ylim[1] != 0 else 1.0
        ax_cvd.text(0.5, cvd_top_y, "■ KÜMÜLATİF HACİM DELTASI (CVD) │ NET TAKER AKIŞI",
                    color=self.COLOR_TEXT_MUTED, fontsize=6.8, fontweight='bold', ha='left', va='top', zorder=6)

        # Alıcı / Satıcı Hakimiyeti Rozeti (CVD Paneli Sağ Üst)
        recent_delta = cvd_series[-1] - cvd_series[max(0, len(cvd_series) - 6)]
        dom_text = "ALICI BASKIN ▲" if recent_delta >= 0 else "SATICILI BASKIN ▼"
        dom_color = self.COLOR_GREEN if recent_delta >= 0 else self.COLOR_RED
        ax_cvd.text(n_bars - 1, cvd_top_y,
                    f" {dom_text} ", color=dom_color, fontsize=7.2, fontweight='bold', ha='right', va='top',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='#090d16', edgecolor=dom_color, linewidth=0.8, alpha=0.85),
                    zorder=6)

        # Zaman Ekseni
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
        # 12. BÖLÜM B: SAĞ ADLİ KARA KUTU HUD TELEMETRİ KARTI (%28)
        # ---------------------------------------------------------------------
        ax_hud.axis('off')
        for spine in ax_hud.spines.values():
            spine.set_color(self.COLOR_GRID)
            spine.set_linewidth(1.2)

        hud_box = patches.FancyBboxPatch(
            (0.01, 0.01), 0.98, 0.98,
            boxstyle="round,pad=0.02,rounding_size=0.03",
            facecolor='#0b1122', edgecolor=self.COLOR_GRID,
            linewidth=1.5, zorder=1
        )
        ax_hud.add_patch(hud_box)

        y_cursor = 0.95

        # 1. Başlık ve Parite Kartı
        ax_hud.text(0.06, y_cursor, f"#{symbol}/USDT", color='#ffffff', fontsize=15.0, fontweight='bold', zorder=5)
        if is_manual:
            badge_txt = "RADAR CANLI"
            badge_bg = self.COLOR_CYAN
            badge_fg = '#000000'
        else:
            badge_txt = f"{side} {leverage}x"
            badge_bg = self.COLOR_GREEN if side == "LONG" else self.COLOR_RED
            badge_fg = '#000000'

        ax_hud.text(0.70, y_cursor + 0.005, badge_txt, color=badge_fg, fontsize=8.8, fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.28', facecolor=badge_bg, edgecolor='none'), zorder=5)

        y_cursor -= 0.044
        if is_manual:
            status_txt = f"Mod: CANLI GÖZLEM │ Anlık: {fmt_price(entry_price)}"
        else:
            status_txt = f"İcraat: KAPANDI │ Süre: {duration_str}"
        ax_hud.text(0.06, y_cursor, status_txt, color=self.COLOR_TEXT_MUTED, fontsize=8.2, fontweight='bold', zorder=5)

        y_cursor -= 0.070
        # 2. PnL veya Canlı Piyasa Koridoru Banner Kartı
        card_border_col = self.COLOR_CYAN if is_manual else theme_pnl_col
        banner_bg = patches.Rectangle((0.05, y_cursor - 0.01), 0.90, 0.075,
                                      facecolor='#070c18', edgecolor=card_border_col,
                                      linewidth=1.2, linestyle='-', zorder=2)
        ax_hud.add_patch(banner_bg)

        if is_manual:
            # Canlı Piyasa Rejimi Bannerı
            regime_txt = "CAMARILLA DENGESİ"
            if entry_price >= r4_val and r4_val > 0:
                regime_txt = "R4 BREAKOUT / BOĞA İVMESİ"
            elif entry_price <= s4_val and s4_val > 0:
                regime_txt = "S4 BREAKDOWN / AYI BASKISI"

            ax_hud.text(0.09, y_cursor + 0.034, "CANLI PİYASA REJİMİ:", color=self.COLOR_TEXT_MUTED, fontsize=8.2, fontweight='bold', zorder=5)
            ax_hud.text(0.09, y_cursor + 0.006, regime_txt, color=self.COLOR_CYAN, fontsize=10.5, fontweight='bold', zorder=5)
        else:
            # Kapanmış İşlem PnL Bannerı
            pnl_sign = "+" if net_pnl > 0 else ""
            roe_sign = "+" if roe_pct > 0 else ""
            pnl_str = f"{pnl_sign}${net_pnl:,.2f}"
            roe_str = f"({roe_sign}{roe_pct:.2f}% ROE)"
            ax_hud.text(0.09, y_cursor + 0.032, "NET PnL & ROE:", color=self.COLOR_TEXT_MUTED, fontsize=8.5, fontweight='bold', zorder=5)
            ax_hud.text(0.09, y_cursor + 0.005, f"{pnl_str}  {roe_str}", color=theme_pnl_col, fontsize=12.2, fontweight='bold', zorder=5)

        y_cursor -= 0.055
        # 3. İŞLEM GEREKÇESİ / CANLI ONAY RADARI
        sec3_title = "── CANLI SEVİYE & ONAY RADARI ──" if is_manual else "── GİRİŞ STRATEJİSİ & ONAYLAR ──"
        ax_hud.text(0.06, y_cursor, sec3_title, color=self.COLOR_CYAN, fontsize=8.2, fontweight='bold', zorder=5)

        y_cursor -= 0.038
        setup_disp = "RADAR_MARKET_SCAN" if is_manual else _clean_str(setup_id, 32)
        ax_hud.text(0.06, y_cursor, f"Setup: {setup_disp}", color='#ffffff', fontsize=8.5, fontweight='bold', zorder=5)

        y_cursor -= 0.032
        conf_score = trade_record.get('confluence_score', '5/5' if is_manual else '4/4')
        ax_hud.text(0.06, y_cursor, f"Onay Skoru: {conf_score} (Kurumsal Confluence)", color='#38bdf8', fontsize=8.0, fontweight='bold', zorder=5)

        # Confluence Maddeleri
        raw_confs = trade_record.get('confluence_list')
        if isinstance(raw_confs, list) and len(raw_confs) > 0 and not is_manual:
            confluences = [f"[✓] {_clean_str(c, 36)}" for c in raw_confs[:4]]
        elif is_manual:
            poc_desc = f"mPOC Hacim Profili: {fmt_price(mpoc_val)}" if mpoc_val > 0 else "Stoikov Mikro Denge"
            confluences = [
                f"[✓] Camarilla Denge Seviyesi (P: {fmt_price(p_val)})",
                f"[✓] {poc_desc}",
                f"[✓] 24s Kurumsal Aralık: {fmt_price(min_y)} - {fmt_price(max_y)}",
                f"[✓] CVD Kümülatif Emir Akışı ({dom_text})"
            ]
        else:
            confluences = [
                f"[✓] Camarilla Rejim Sinyali ({trade_record.get('trend_regime', 'BOĞA')})",
                f"[✓] Stoikov Mikro Fiyat ({fmt_price(trade_record.get('stoikov_micro_price', entry_price))})",
                f"[✓] Hacim Çarpanı: {float(trade_record.get('volume_surge', 1.0)):.2f}x",
                f"[✓] Fonlama Kalkanı: {float(trade_record.get('entry_funding_rate', 0.0)):.4f}%"
            ]

        for c_item in confluences:
            y_cursor -= 0.026
            ax_hud.text(0.08, y_cursor, c_item, color='#cbd5e1', fontsize=7.4, zorder=5)

        y_cursor -= 0.045
        # 4. ÇIKIŞ / KRİTİK TETİKLEYİCİ SEVİYELER
        sec4_title = "── TETİKLEYİCİ KRİTİK SEVİYELER ──" if is_manual else "── ÇIKIŞ NEDENİ & TELEMETRİ ──"
        ax_hud.text(0.06, y_cursor, sec4_title, color=self.COLOR_YELLOW, fontsize=8.2, fontweight='bold', zorder=5)

        if is_manual:
            y_cursor -= 0.034
            ax_hud.text(0.06, y_cursor, f"• Long Tetik (R4): {fmt_price(r4_val)} (Breakout)", color='#fb923c', fontsize=8.0, fontweight='bold', zorder=5)
            y_cursor -= 0.028
            ax_hud.text(0.06, y_cursor, f"• Denge Pivot (P): {fmt_price(p_val)} (Nötr Merkez)", color='#f8fafc', fontsize=8.0, fontweight='bold', zorder=5)
            y_cursor -= 0.028
            ax_hud.text(0.06, y_cursor, f"• Short Tetik (S4): {fmt_price(s4_val)} (Breakdown)", color='#10b981', fontsize=8.0, fontweight='bold', zorder=5)
            y_cursor -= 0.028
            ax_hud.text(0.06, y_cursor, f"• Uç Hedefler: R5 {fmt_price(cam.get('R5'))} │ S5 {fmt_price(cam.get('S5'))}", color='#38bdf8', fontsize=7.6, zorder=5)
        else:
            y_cursor -= 0.035
            if sub_legs and len(sub_legs) >= 2:
                ax_hud.text(0.06, y_cursor, "🏛️ BİRLEŞİK YAŞAM DÖNGÜSÜ:", color='#38bdf8', fontsize=8.2, fontweight='bold', zorder=5)
                y_cursor -= 0.024
                ax_hud.text(0.08, y_cursor, f"• Bacak 1 (%50 TP1): {fmt_price(tp1_exit_p)} ➔ +${leg1_pnl:.2f}", color='#34d399', fontsize=7.8, fontweight='bold', zorder=5)
                y_cursor -= 0.024
                leg2_col = '#34d399' if leg2_pnl >= 0 else '#f87171'
                ax_hud.text(0.08, y_cursor, f"• Bacak 2 (%50 Runner): {fmt_price(exit_price)} ➔ ${leg2_pnl:+.2f}", color=leg2_col, fontsize=7.8, fontweight='bold', zorder=5)
            else:
                raw_cr = str(close_reason).replace("🛡️", "").replace("⏳", "").replace("💥", "").strip()
                cr_lines = textwrap.wrap(raw_cr, width=38)
                if cr_lines:
                    ax_hud.text(0.06, y_cursor, f"Neden: {cr_lines[0]}", color='#ffffff', fontsize=8.2, fontweight='bold', zorder=5)
                    if len(cr_lines) > 1:
                        y_cursor -= 0.024
                        ax_hud.text(0.12, y_cursor, cr_lines[1], color='#cbd5e1', fontsize=7.6, zorder=5)
                else:
                    ax_hud.text(0.06, y_cursor, "Neden: Standart Kapanış", color='#ffffff', fontsize=8.2, fontweight='bold', zorder=5)

            y_cursor -= 0.030
            mfe_val = float(trade_record.get('max_mfe_roe') if trade_record.get('max_mfe_roe') is not None else (trade_record.get('max_mfe_pct') or 0.0))
            mae_val = float(trade_record.get('max_mae_roe') if trade_record.get('max_mae_roe') is not None else (trade_record.get('max_mae_pct') or 0.0))
            mafe_text = f"MFE: +%{mfe_val:.2f}  │  MAE: %{mae_val:.2f}"
            ax_hud.text(0.06, y_cursor, mafe_text, color='#94a3b8', fontsize=7.8, fontweight='bold', zorder=5)

            y_cursor -= 0.030
            funding_fee_val = float(trade_record.get('funding_fee') or 0.0)
            fees_val = float(trade_record.get('fees') or 0.0)
            fees_text = f"Toplam Komisyon: ${fees_val:.3f} │ Fonlama: ${funding_fee_val:.3f}"
            ax_hud.text(0.06, y_cursor, fees_text, color='#94a3b8', fontsize=7.6, zorder=5)

        y_cursor -= 0.046
        # 5. AI ADLİ OTOPSİ / RADAR TEŞHİSİ
        sec5_title = "── VALKYRIE AI RADAR TEŞHİSİ ──" if is_manual else "── VALKYRIE AI OTOPSİ TEŞHİSİ ──"
        ax_hud.text(0.06, y_cursor, sec5_title, color='#ec4899', fontsize=8.2, fontweight='bold', zorder=5)

        y_cursor -= 0.036
        if is_manual:
            diag_badge = "[CANLI PİYASA RADARI - AKTİF İZLEME]"
            diag_color = self.COLOR_CYAN
        else:
            raw_badge = autopsy.get("diagnosis_badge", "[STANDART İCRAAT]")
            diag_badge = _clean_str(raw_badge, 40)
            diag_color = autopsy.get("diagnosis_color", self.COLOR_CYAN)

        ax_hud.text(0.06, y_cursor, diag_badge, color='#ffffff', fontsize=8.4, fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.25', facecolor='#1e1b4b', edgecolor=diag_color, linewidth=1.2), zorder=5)

        if is_manual:
            findings = [
                f"Parite kurumsal seviyeler arasında ({fmt_price(entry_price)}) seyrediyor.",
                "R4 kırılımı veya S4 altına inilmedikçe konsolidasyon geçerlidir."
            ]
            advice = "R4 üstü veya S4 altı kırılım kapanışı teyit edilmeden pozisyon açılmamalıdır."
        else:
            findings = autopsy.get("findings", ["İşlem kurumsal risk yönetimi sınırlarında kapatıldı."])
            advice = autopsy.get("actionable_advice", "")

        for f in findings[:2]:
            clean_f = _clean_str(f, 90)
            f_lines = textwrap.wrap(clean_f, width=40)
            if f_lines:
                y_cursor -= 0.026
                ax_hud.text(0.07, y_cursor, f"• {f_lines[0]}", color='#e2e8f0', fontsize=7.2, zorder=5)
                for fl in f_lines[1:2]:
                    y_cursor -= 0.022
                    ax_hud.text(0.10, y_cursor, fl, color='#cbd5e1', fontsize=7.0, zorder=5)

        if advice:
            y_cursor -= 0.032
            clean_adv = _clean_str(advice, 90)
            adv_lines = textwrap.wrap(clean_adv, width=40)
            ax_hud.text(0.06, y_cursor, f"Tavsiye: {adv_lines[0]}", color='#38bdf8', fontsize=7.2, fontweight='bold', zorder=5)
            if len(adv_lines) > 1:
                y_cursor -= 0.022
                ax_hud.text(0.12, y_cursor, adv_lines[1], color='#38bdf8', fontsize=7.0, zorder=5)

        # Buffer'a kaydet (Pure OO Canvas - Thread-Safe & Sıfır Kilitlenme)
        buf = io.BytesIO()
        try:
            canvas.print_png(buf)
            buf.seek(0)
            return buf
        finally:
            fig.clf()
            del fig
            del canvas
            import gc
            gc.collect()


# Singleton motor
forensic_chart_engine_v2 = ForensicChartEngineV2()
