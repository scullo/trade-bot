import io
from datetime import datetime, timezone, timedelta
import xlsxwriter

def create_styled_excel_report(history_data: list, current_balance: float = 100000.0, initial_balance: float = 100000.0) -> io.BytesIO:
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})

    # ==================== FORMATLAR ====================
    title_fmt = workbook.add_format({
        'bold': True, 'font_size': 15, 'font_name': 'Segoe UI',
        'font_color': '#FFFFFF', 'bg_color': '#0F172A',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#334155'
    })
    subtitle_fmt = workbook.add_format({
        'italic': True, 'font_size': 9.5, 'font_name': 'Segoe UI',
        'font_color': '#94A3B8', 'bg_color': '#0F172A',
        'align': 'center', 'valign': 'vcenter'
    })

    kpi_card_lbl = workbook.add_format({
        'bold': True, 'font_size': 9, 'font_name': 'Segoe UI',
        'font_color': '#475569', 'bg_color': '#F1F5F9',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#CBD5E1'
    })
    kpi_card_val_green = workbook.add_format({
        'bold': True, 'font_size': 13, 'font_name': 'Segoe UI',
        'font_color': '#059669', 'bg_color': '#ECFDF5',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#A7F3D0',
        'num_format': '$#,##0.00'
    })
    kpi_card_val_red = workbook.add_format({
        'bold': True, 'font_size': 13, 'font_name': 'Segoe UI',
        'font_color': '#DC2626', 'bg_color': '#FEF2F2',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#FECACA',
        'num_format': '$#,##0.00'
    })
    kpi_card_val_blue = workbook.add_format({
        'bold': True, 'font_size': 13, 'font_name': 'Segoe UI',
        'font_color': '#2563EB', 'bg_color': '#EFF6FF',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#BFDBFE',
        'num_format': '$#,##0.00'
    })
    kpi_card_val_blue_text = workbook.add_format({
        'bold': True, 'font_size': 12, 'font_name': 'Segoe UI',
        'font_color': '#2563EB', 'bg_color': '#EFF6FF',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#BFDBFE'
    })
    kpi_card_val_purple = workbook.add_format({
        'bold': True, 'font_size': 13, 'font_name': 'Segoe UI',
        'font_color': '#7C3AED', 'bg_color': '#F5F3FF',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#DDD6FE',
        'num_format': '$#,##0.0000'
    })

    th_fmt = workbook.add_format({
        'bold': True, 'font_size': 9.5, 'font_name': 'Segoe UI',
        'font_color': '#FFFFFF', 'bg_color': '#1E293B',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#475569',
        'text_wrap': True
    })

    cell_center = workbook.add_format({'font_name': 'Segoe UI', 'font_size': 9, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#E2E8F0'})
    cell_left = workbook.add_format({'font_name': 'Segoe UI', 'font_size': 9, 'align': 'left', 'valign': 'vcenter', 'border': 1, 'border_color': '#E2E8F0'})
    cell_currency = workbook.add_format({'font_name': 'Segoe UI', 'font_size': 9, 'align': 'right', 'valign': 'vcenter', 'border': 1, 'border_color': '#E2E8F0', 'num_format': '$#,##0.0000'})
    cell_currency_2d = workbook.add_format({'font_name': 'Segoe UI', 'font_size': 9, 'align': 'right', 'valign': 'vcenter', 'border': 1, 'border_color': '#E2E8F0', 'num_format': '$#,##0.00'})
    
    cell_green = workbook.add_format({
        'font_name': 'Segoe UI', 'font_size': 9, 'bold': True,
        'font_color': '#059669', 'bg_color': '#F0FDF4',
        'align': 'right', 'valign': 'vcenter', 'border': 1, 'border_color': '#BBF7D0',
        'num_format': '+$#,##0.0000;-$#,##0.0000;$0.00'
    })
    cell_red = workbook.add_format({
        'font_name': 'Segoe UI', 'font_size': 9, 'bold': True,
        'font_color': '#DC2626', 'bg_color': '#FEF2F2',
        'align': 'right', 'valign': 'vcenter', 'border': 1, 'border_color': '#FECACA',
        'num_format': '+$#,##0.0000;-$#,##0.0000;$0.00'
    })
    cell_roe_green = workbook.add_format({
        'font_name': 'Segoe UI', 'font_size': 9, 'bold': True,
        'font_color': '#059669', 'bg_color': '#F0FDF4',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#BBF7D0',
        'num_format': '+0.00%;-0.00%;0.00%'
    })
    cell_roe_red = workbook.add_format({
        'font_name': 'Segoe UI', 'font_size': 9, 'bold': True,
        'font_color': '#DC2626', 'bg_color': '#FEF2F2',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#FECACA',
        'num_format': '+0.00%;-0.00%;0.00%'
    })

    # ==================== HESAPLAMALAR ====================
    total_trades = len(history_data)
    win_trades = [h for h in history_data if h.get('net_pnl', 0) >= 0]
    loss_trades = [h for h in history_data if h.get('net_pnl', 0) < 0]

    win_count = len(win_trades)
    loss_count = len(loss_trades)
    win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0.0

    total_net_pnl = sum(h.get('net_pnl', 0) for h in history_data)
    total_fees = sum(h.get('fees', 0) for h in history_data)
    growth_pct = ((current_balance - initial_balance) / initial_balance * 100) if initial_balance > 0 else 0.0

    # ==================== SHEET 1: ÖZET & GRAFİKLER ====================
    ws1 = workbook.add_worksheet('📊 GENEL ÖZET')
    ws1.set_column('A:A', 3)
    ws1.set_column('B:D', 24)
    ws1.set_column('E:E', 4)
    ws1.set_column('F:I', 20)

    ws1.merge_range('B2:I2', 'VALKYRIE QUANT DESK — PERFORMANS & STRATEJİ RAPORU', title_fmt)
    ws1.merge_range('B3:I3', f"Oluşturulma Tarihi: {datetime.now(timezone(timedelta(hours=3))).strftime('%d.%m.%Y %H:%M:%S')}  |  Toplam İşlem: {total_trades}  |  Kazanma Oranı: %{win_rate:.1f}", subtitle_fmt)
    ws1.set_row(1, 30)
    ws1.set_row(2, 18)

    ws1.write('B5', 'TOPLAM KASA', kpi_card_lbl)
    ws1.write('B6', current_balance, kpi_card_val_blue)

    ws1.write('C5', 'NET KÂR / ZARAR', kpi_card_lbl)
    ws1.write('C6', total_net_pnl, kpi_card_val_green if total_net_pnl >= 0 else kpi_card_val_red)

    ws1.write('D5', 'KAZANMA ORANI (WIN RATE)', kpi_card_lbl)
    ws1.write('D6', f"%{win_rate:.1f} ({win_count}K / {loss_count}Z)", kpi_card_val_blue_text)

    ws1.write('F5', 'ÖDENEN KOMİSYON', kpi_card_lbl)
    ws1.write('F6', total_fees, kpi_card_val_purple)

    ws1.write('G5', 'KASA BÜYÜMESİ', kpi_card_lbl)
    ws1.write('G6', f"{growth_pct:+.2f}%", kpi_card_val_green if growth_pct >= 0 else kpi_card_val_red)

    ws1.set_row(4, 20)
    ws1.set_row(5, 26)

    # Pasta Grafiği İçin Veri Tablosu
    ws1.write('B9', 'İşlem Tipi', th_fmt)
    ws1.write('C9', 'Adet', th_fmt)
    ws1.write('D9', 'Toplam Net PnL ($)', th_fmt)

    ws1.write('B10', 'Kârlı İşlemler (Wins)', cell_left)
    ws1.write('C10', win_count, cell_center)
    ws1.write('D10', sum(h.get('net_pnl', 0) for h in win_trades), cell_green)

    ws1.write('B11', 'Zararlı İşlemler (Losses)', cell_left)
    ws1.write('C11', loss_count, cell_center)
    ws1.write('D11', sum(h.get('net_pnl', 0) for h in loss_trades), cell_red)

    pie_chart = workbook.add_chart({'type': 'doughnut'})
    pie_chart.add_series({
        'name': 'Kazanma / Kaybetme Oranı',
        'categories': "='📊 GENEL ÖZET'!$B$10:$B$11",
        'values':     "='📊 GENEL ÖZET'!$C$10:$C$11",
        'points': [
            {'fill': {'color': '#10B981'}},
            {'fill': {'color': '#EF4444'}},
        ]
    })
    pie_chart.set_title({'name': '🎯 Kâr / Zarar Dağılımı', 'name_font': {'name': 'Segoe UI', 'size': 12, 'bold': True}})
    pie_chart.set_size({'width': 440, 'height': 280})
    ws1.insert_chart('B14', pie_chart)

    # Parite Bazında PnL Tablosu & Bar Grafik
    pair_stats = {}
    for h in history_data:
        sym = h.get('symbol', 'Bilinmeyen')
        if sym not in pair_stats:
            pair_stats[sym] = {
                'trades': 0, 'wins': 0, 'losses': 0,
                'net_pnl': 0.0, 'gross_profit': 0.0, 'gross_loss': 0.0,
                'fees': 0.0, 'mfe_sum': 0.0, 'mae_sum': 0.0,
                'tp1_hits': 0, 'trail_locks': 0, 'atr_sum': 0.0,
                'setup_counts': {}
            }
        pnl = h.get('net_pnl', 0.0)
        pair_stats[sym]['trades'] += 1
        pair_stats[sym]['net_pnl'] += pnl
        pair_stats[sym]['fees'] += h.get('fees', 0.0)
        pair_stats[sym]['mfe_sum'] += h.get('mfe_roe', max(0, h.get('roe_pct', 0)))
        pair_stats[sym]['mae_sum'] += h.get('mae_roe', abs(min(0, h.get('roe_pct', 0))))
        pair_stats[sym]['atr_sum'] += h.get('atr_pct', 1.2)

        if h.get('id', '').endswith('-TP1') or 'TP1' in str(h.get('close_reason', '')):
            pair_stats[sym]['tp1_hits'] += 1
        if 'Tier' in str(h.get('trail_status', '')) or 'Breakeven' in str(h.get('close_reason', '')):
            pair_stats[sym]['trail_locks'] += 1

        if pnl >= 0:
            pair_stats[sym]['wins'] += 1
            pair_stats[sym]['gross_profit'] += pnl
        else:
            pair_stats[sym]['losses'] += 1
            pair_stats[sym]['gross_loss'] += abs(pnl)

        st_name = h.get('reason', 'Sinyal').split('(')[0].strip()
        pair_stats[sym]['setup_counts'][st_name] = pair_stats[sym]['setup_counts'].get(st_name, 0) + 1

    ws1.write('F9', 'Parite', th_fmt)
    ws1.write('G9', 'İşlem', th_fmt)
    ws1.write('H9', 'Net PnL ($)', th_fmt)
    ws1.write('I9', 'Komisyon ($)', th_fmt)

    row_idx = 9
    for sym, st in pair_stats.items():
        ws1.write(row_idx, 5, sym, cell_left)
        ws1.write(row_idx, 6, st['trades'], cell_center)
        ws1.write(row_idx, 7, st['net_pnl'], cell_green if st['net_pnl'] >= 0 else cell_red)
        ws1.write(row_idx, 8, st['fees'], cell_currency)
        row_idx += 1

    if pair_stats:
        bar_chart = workbook.add_chart({'type': 'column'})
        bar_chart.add_series({
            'name': 'Net PnL ($)',
            'categories': f"='📊 GENEL ÖZET'!$F$10:$F${row_idx}",
            'values':     f"='📊 GENEL ÖZET'!$H$10:$H${row_idx}",
            'fill': {'color': '#3B82F6'}
        })
        bar_chart.set_title({'name': '📈 Parite Bazında Net Kâr / Zarar ($)', 'name_font': {'name': 'Segoe UI', 'size': 12, 'bold': True}})
        bar_chart.set_y_axis({'name': 'Net PnL ($)'})
        bar_chart.set_size({'width': 520, 'height': 280})
        ws1.insert_chart('F14', bar_chart)

    # ==================== SHEET 2: DETAYLI İŞLEM DEFTERİ (48 KOLON) ====================
    ws2 = workbook.add_worksheet('📜 DETAYLI İŞLEM DEFTERİ')
    headers_granular = [
        ('İşlem ID', 12),
        ('Parite', 12),
        ('Yön', 8),
        ('Kaldıraç', 9),
        ('İşlem Tipi', 18),
        ('Giriş Zamanı', 17),
        ('Çıkış Zamanı', 17),
        ('Süre', 11),
        ('Mum Sayısı', 10),
        ('Piyasa Seansı', 18),
        ('Trend Rejimi', 22),
        ('Volatilite ATR (%)', 15),
        ('Hacim Patlaması', 15),
        ('Confluence Skoru', 18),
        ('Makro Uyum (1H/4H)', 24),
        ('TP1 Alındı mı?', 18),
        ('İzsüren Kâr Kilidi', 22),
        ('Dinamik Marjin ($)', 14),
        ('Giriş Fiyatı ($)', 14),
        ('Zirve Fiyat ($)', 14),
        ('Dip Fiyat ($)', 14),
        ('Çıkış Fiyatı ($)', 14),
        ('Planlanan TP1 ($)', 15),
        ('Planlanan TP2 ($)', 15),
        ('Planlanan Stop ($)', 15),
        ('Brüt Kâr ($)', 13),
        ('Komisyon ($)', 13),
        ('Net Kâr ($)', 13),
        ('ROE (%)', 11),
        ('1R Katı', 10),
        ('Zirve MFE (%)', 13),
        ('Maks MAE (%)', 13),
        ('Çıkış Verimliliği (%)', 16),
        ('Kasa ($)', 13),
        ('Giriş Stratejisi / Formasyon', 38),
        ('Kapanış Nedeni / Tetikleyici', 32),
        ('Giriş Pivot P ($)', 14),
        ('Giriş S3 ($)', 13),
        ('Giriş S4 ($)', 13),
        ('Giriş R3 ($)', 13),
        ('Giriş R4 ($)', 13),
        ('Tepe AVWAP ($)', 14),
        ('Dip AVWAP ($)', 14),
        ('mPOC ($)', 13),
        ('mVAL ($)', 13),
        ('mVAH ($)', 13),
        ('Yukarı nPOC ($)', 14),
        ('Aşağı nPOC ($)', 14)
    ]

    def write_trade_row(ws, r_idx, h):
        ws.set_row(r_idx, 20)
        is_win = h.get('net_pnl', 0) >= 0
        pnl_fmt = cell_green if is_win else cell_red
        roe_fmt = cell_roe_green if is_win else cell_roe_red
        r_mult = h.get('realized_r', round(h.get('roe_pct', 0) / 2, 1) if is_win else -1.0)
        mfe = h.get('mfe_roe', max(0, h.get('roe_pct', 0)))
        mae = h.get('mae_roe', abs(min(0, h.get('roe_pct', 0))))
        eff = h.get('exit_efficiency_pct', round((h.get('roe_pct', 0) / mfe) * 100, 1) if (mfe > 0 and is_win) else (0.0 if not is_win else 100.0))
        snaps = h.get('snapshot_levels', {})

        trade_type_label = "TP1 %50 KISMİ KÂR" if h.get('id', '').endswith('-TP1') else ("TP2 NİHAİ KAPANIŞ" if "TP2" in str(h.get('close_reason', '')) else "TAM POZİSYON")
        tp1_status = "EVET (%50 Kilitlendi)" if (h.get('id', '').endswith('-TP1') or h.get('tp1_hit')) else "HAYIR"
        trailing_status = h.get('trail_status') or ("Breakeven" if "Breakeven" in str(h.get('close_reason', '')) else "-")

        ws.write(r_idx, 0, h.get('id', ''), cell_center)
        ws.write(r_idx, 1, h.get('symbol', ''), cell_center)
        ws.write(r_idx, 2, h.get('side', ''), cell_center)
        ws.write(r_idx, 3, f"{h.get('leverage', 5)}x", cell_center)
        ws.write(r_idx, 4, trade_type_label, cell_center)
        ws.write(r_idx, 5, h.get('entry_time', ''), cell_center)
        ws.write(r_idx, 6, h.get('exit_time', ''), cell_center)
        ws.write(r_idx, 7, h.get('duration', '5M Mum'), cell_center)
        ws.write(r_idx, 8, h.get('candles_held', 1), cell_center)
        ws.write(r_idx, 9, h.get('session', 'LONDRA'), cell_center)
        ws.write(r_idx, 10, h.get('trend_regime', 'YATAY'), cell_center)
        ws.write(r_idx, 11, f"%{h.get('atr_pct', 1.2):.2f}", cell_center)
        ws.write(r_idx, 12, f"{h.get('volume_surge', 1.0):.1f}x", cell_center)
        ws.write(r_idx, 13, h.get('confluence_score', '2/4'), cell_center)
        ws.write(r_idx, 14, h.get('htf_alignment', 'NÖTR'), cell_center)
        ws.write(r_idx, 15, tp1_status, cell_center)
        ws.write(r_idx, 16, trailing_status, cell_center)
        ws.write(r_idx, 17, h.get('margin', 0.0), cell_currency_2d)
        ws.write(r_idx, 18, h.get('entry_price', 0.0), cell_currency)
        ws.write(r_idx, 19, h.get('peak_price', h.get('entry_price', 0.0)), cell_currency)
        ws.write(r_idx, 20, h.get('trough_price', h.get('entry_price', 0.0)), cell_currency)
        ws.write(r_idx, 21, h.get('exit_price', 0.0), cell_currency)
        ws.write(r_idx, 22, h.get('tp1', 0.0) or "-", cell_currency if h.get('tp1') else cell_center)
        ws.write(r_idx, 23, h.get('tp2', 0.0) or "-", cell_currency if h.get('tp2') else cell_center)
        ws.write(r_idx, 24, h.get('soft_stop', 0.0) or "-", cell_currency if h.get('soft_stop') else cell_center)
        ws.write(r_idx, 25, h.get('gross_pnl', h.get('net_pnl', 0.0) + h.get('fees', 0.0)), cell_currency)
        ws.write(r_idx, 26, h.get('fees', 0.0), cell_currency)
        ws.write(r_idx, 27, h.get('net_pnl', 0.0), pnl_fmt)
        ws.write(r_idx, 28, (h.get('roe_pct', 0.0) / 100.0), roe_fmt)
        ws.write(r_idx, 29, f"{r_mult:+.1f}R", cell_center)
        ws.write(r_idx, 30, f"+%{mfe:.1f}", cell_center)
        ws.write(r_idx, 31, f"-%{mae:.1f}", cell_center)
        ws.write(r_idx, 32, f"%{eff:.1f}", cell_center)
        ws.write(r_idx, 33, h.get('balance_after', current_balance), cell_currency_2d)
        ws.write(r_idx, 34, h.get('reason', 'Strateji Sinyali'), cell_left)
        ws.write(r_idx, 35, h.get('close_reason', 'Kapanış'), cell_left)
        ws.write(r_idx, 36, snaps.get('P', 0.0) or "-", cell_currency if snaps.get('P') else cell_center)
        ws.write(r_idx, 37, snaps.get('S3', 0.0) or "-", cell_currency if snaps.get('S3') else cell_center)
        ws.write(r_idx, 38, snaps.get('S4', 0.0) or "-", cell_currency if snaps.get('S4') else cell_center)
        ws.write(r_idx, 39, snaps.get('R3', 0.0) or "-", cell_currency if snaps.get('R3') else cell_center)
        ws.write(r_idx, 40, snaps.get('R4', 0.0) or "-", cell_currency if snaps.get('R4') else cell_center)
        ws.write(r_idx, 41, snaps.get('tepe_avwap', 0.0) or "-", cell_currency if snaps.get('tepe_avwap') else cell_center)
        ws.write(r_idx, 42, snaps.get('dip_avwap', 0.0) or "-", cell_currency if snaps.get('dip_avwap') else cell_center)
        ws.write(r_idx, 43, snaps.get('mpoc', 0.0) or "-", cell_currency if snaps.get('mpoc') else cell_center)
        ws.write(r_idx, 44, snaps.get('mval', 0.0) or "-", cell_currency if snaps.get('mval') else cell_center)
        ws.write(r_idx, 45, snaps.get('mvah', 0.0) or "-", cell_currency if snaps.get('mvah') else cell_center)
        ws.write(r_idx, 46, snaps.get('above_npoc', 0.0) or "-", cell_currency if snaps.get('above_npoc') else cell_center)
        ws.write(r_idx, 47, snaps.get('below_npoc', 0.0) or "-", cell_currency if snaps.get('below_npoc') else cell_center)

    ws2.set_row(0, 26)
    for col_idx, (h_name, width) in enumerate(headers_granular):
        ws2.write(0, col_idx, h_name, th_fmt)
        ws2.set_column(col_idx, col_idx, width)

    for r_idx, h in enumerate(reversed(history_data), start=1):
        write_trade_row(ws2, r_idx, h)

    # ==================== SHEET 3: KÂRLI İŞLEMLER ====================
    ws3 = workbook.add_worksheet('🟢 KÂRLI İŞLEMLER')
    ws3.set_row(0, 26)
    for col_idx, (h_name, width) in enumerate(headers_granular):
        ws3.write(0, col_idx, h_name, th_fmt)
        ws3.set_column(col_idx, col_idx, width)

    for r_idx, h in enumerate(reversed(win_trades), start=1):
        write_trade_row(ws3, r_idx, h)

    # ==================== SHEET 4: ZARAR KES İŞLEMLERİ ====================
    ws4 = workbook.add_worksheet('🔴 ZARAR KES İŞLEMLERİ')
    ws4.set_row(0, 26)
    for col_idx, (h_name, width) in enumerate(headers_granular):
        ws4.write(0, col_idx, h_name, th_fmt)
        ws4.set_column(col_idx, col_idx, width)

    for r_idx, h in enumerate(reversed(loss_trades), start=1):
        write_trade_row(ws4, r_idx, h)

    # ==================== SHEET 5: 🪙 PARİTE BAZINDA ADLİ ANALİZ ====================
    ws5 = workbook.add_worksheet('🪙 PARİTE BAZINDA ANALİZ')
    ws5.set_column('A:A', 3)
    ws5.set_column('B:B', 16)
    ws5.set_column('C:L', 15)
    ws5.set_column('M:M', 32)

    ws5.merge_range('B2:M2', 'PARİTE BAZINDA PERFORMANS, KÂRLILIK VE TELEMETRİ MATRİSİ', title_fmt)
    ws5.set_row(1, 28)

    coin_headers = [
        ('Parite', 16),
        ('Toplam İşlem', 13),
        ('Kazanma (Win Rate)', 18),
        ('Net PnL ($)', 16),
        ('Komisyon ($)', 14),
        ('Ortalama ATR (%)', 16),
        ('TP1 Başarı %', 15),
        ('İzsüren Kilit', 15),
        ('Ortalama MFE (Zirve Kâr)', 22),
        ('Ortalama MAE (Maks Çekilme)', 22),
        ('Kâr Faktörü (PF)', 15),
        ('En Çok Tercih Edilen Setup', 32)
    ]

    ws5.set_row(4, 24)
    for col_idx, (c_name, width) in enumerate(coin_headers, start=1):
        ws5.write(4, col_idx, c_name, th_fmt)

    c_row = 5
    for sym, st in sorted(pair_stats.items(), key=lambda x: x[1]['net_pnl'], reverse=True):
        ws5.set_row(c_row, 20)
        c_wr = (st['wins'] / st['trades'] * 100) if st['trades'] > 0 else 0.0
        c_avg_mfe = st['mfe_sum'] / st['trades'] if st['trades'] > 0 else 0.0
        c_avg_mae = st['mae_sum'] / st['trades'] if st['trades'] > 0 else 0.0
        c_avg_atr = st['atr_sum'] / st['trades'] if st['trades'] > 0 else 1.2
        c_tp1_rate = (st['tp1_hits'] / st['trades'] * 100) if st['trades'] > 0 else 0.0
        
        # Gerçek Kâr Faktörü (PF) = Brüt Kâr / Brüt Zarar
        if st['gross_loss'] > 0:
            pf_str = f"{(st['gross_profit'] / st['gross_loss']):.2f}"
        else:
            pf_str = "∞ (Kayıpsız)" if st['gross_profit'] > 0 else "0.00"

        # En çok açılan setup
        best_setup = max(st['setup_counts'].items(), key=lambda x: x[1])[0] if st['setup_counts'] else "-"

        ws5.write(c_row, 1, sym, cell_left)
        ws5.write(c_row, 2, st['trades'], cell_center)
        ws5.write(c_row, 3, f"%{c_wr:.1f} ({st['wins']}K / {st['losses']}Z)", cell_roe_green if c_wr >= 50 else cell_roe_red)
        ws5.write(c_row, 4, st['net_pnl'], cell_green if st['net_pnl'] >= 0 else cell_red)
        ws5.write(c_row, 5, st['fees'], cell_currency)
        ws5.write(c_row, 6, f"%{c_avg_atr:.2f}", cell_center)
        ws5.write(c_row, 7, f"%{c_tp1_rate:.1f}", cell_center)
        ws5.write(c_row, 8, st['trail_locks'], cell_center)
        ws5.write(c_row, 9, f"+%{c_avg_mfe:.2f} ROE", cell_center)
        ws5.write(c_row, 10, f"-%{c_avg_mae:.2f} ROE", cell_center)
        ws5.write(c_row, 11, pf_str, cell_center)
        ws5.write(c_row, 12, best_setup, cell_left)
        c_row += 1

    # ==================== SHEET 6: 🔬 STRATEJİ & QUANT LABORATUVARI ====================
    ws6 = workbook.add_worksheet('🔬 QUANT & STRATEJİ LAB')
    ws6.set_column('A:A', 3)
    ws6.set_column('B:B', 34)
    ws6.set_column('C:H', 18)

    ws6.merge_range('B2:H2', 'QUANT LABORATUVARI: STRATEJİ & FORMASYON OPTİMİZASYON MATRİSİ', title_fmt)
    ws6.set_row(1, 28)

    strat_stats = {}
    for h in history_data:
        r = h.get('reason', 'Diğer Sinyaller')
        if 'nPOC' in r:
            cat = 'nPOC Likidite Sekmesi / Reddi'
        elif 'mVAL' in r or 'mVAH' in r:
            cat = 'mVAL / mVAH Makro Kırılımı'
        elif 'S3' in r or 'R3' in r:
            cat = 'Camarilla S3 / R3 Destek/Direnç'
        elif 'S4' in r or 'R4' in r:
            cat = 'Camarilla S4 / R4 Breakout/down'
        else:
            cat = 'Diğer Seviye Formasyonları'

        if cat not in strat_stats:
            strat_stats[cat] = {'trades': 0, 'wins': 0, 'losses': 0, 'net_pnl': 0.0, 'mfe_sum': 0.0, 'mae_sum': 0.0, 'tp1_hits': 0}
        
        pnl = h.get('net_pnl', 0.0)
        strat_stats[cat]['trades'] += 1
        strat_stats[cat]['net_pnl'] += pnl
        strat_stats[cat]['mfe_sum'] += h.get('mfe_roe', max(0, h.get('roe_pct', 0)))
        strat_stats[cat]['mae_sum'] += h.get('mae_roe', abs(min(0, h.get('roe_pct', 0))))
        if h.get('id', '').endswith('-TP1') or 'TP1' in str(h.get('close_reason', '')):
            strat_stats[cat]['tp1_hits'] += 1

        if pnl >= 0: strat_stats[cat]['wins'] += 1
        else: strat_stats[cat]['losses'] += 1

    strat_headers = [
        ('Strateji / Setup Adı', 34),
        ('İşlem Sayısı', 14),
        ('Win Rate (%)', 16),
        ('Toplam Net PnL ($)', 18),
        ('TP1 Başarı Adedi', 16),
        ('Ortalama MFE (Zirve Kâr)', 22),
        ('Ortalama MAE (Çekilme)', 22)
    ]

    ws6.set_row(4, 24)
    for col_idx, (s_name, width) in enumerate(strat_headers, start=1):
        ws6.write(4, col_idx, s_name, th_fmt)

    s_row = 5
    for s_name, st in sorted(strat_stats.items(), key=lambda x: x[1]['net_pnl'], reverse=True):
        ws6.set_row(s_row, 20)
        s_wr = (st['wins'] / st['trades'] * 100) if st['trades'] > 0 else 0.0
        s_mfe = st['mfe_sum'] / st['trades'] if st['trades'] > 0 else 0.0
        s_mae = st['mae_sum'] / st['trades'] if st['trades'] > 0 else 0.0

        ws6.write(s_row, 1, s_name, cell_left)
        ws6.write(s_row, 2, st['trades'], cell_center)
        ws6.write(s_row, 3, f"%{s_wr:.1f}", cell_roe_green if s_wr >= 50 else cell_roe_red)
        ws6.write(s_row, 4, st['net_pnl'], cell_green if st['net_pnl'] >= 0 else cell_red)
        ws6.write(s_row, 5, st['tp1_hits'], cell_center)
        ws6.write(s_row, 6, f"+%{s_mfe:.2f} ROE", cell_center)
        ws6.write(s_row, 7, f"-%{s_mae:.2f} ROE", cell_center)
        s_row += 1

    workbook.close()
    output.seek(0)
    return output
