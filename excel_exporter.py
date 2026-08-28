import io
import datetime
import xlsxwriter

def create_styled_excel_report(history_data: list, current_balance: float = 100.0, initial_balance: float = 100.0) -> io.BytesIO:
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})

    # ==================== RENK PALETI & FORMATLAR ====================
    # Başlıklar
    title_fmt = workbook.add_format({
        'bold': True, 'font_size': 16, 'font_name': 'Segoe UI',
        'font_color': '#FFFFFF', 'bg_color': '#0F172A',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#334155'
    })
    subtitle_fmt = workbook.add_format({
        'italic': True, 'font_size': 10, 'font_name': 'Segoe UI',
        'font_color': '#94A3B8', 'bg_color': '#0F172A',
        'align': 'center', 'valign': 'vcenter'
    })

    # KPI Kart Formatları
    kpi_card_lbl = workbook.add_format({
        'bold': True, 'font_size': 9.5, 'font_name': 'Segoe UI',
        'font_color': '#475569', 'bg_color': '#F1F5F9',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#CBD5E1'
    })
    kpi_card_val_green = workbook.add_format({
        'bold': True, 'font_size': 14, 'font_name': 'Segoe UI',
        'font_color': '#059669', 'bg_color': '#ECFDF5',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#A7F3D0',
        'num_format': '$#,##0.00'
    })
    kpi_card_val_red = workbook.add_format({
        'bold': True, 'font_size': 14, 'font_name': 'Segoe UI',
        'font_color': '#DC2626', 'bg_color': '#FEF2F2',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#FECACA',
        'num_format': '$#,##0.00'
    })
    kpi_card_val_blue = workbook.add_format({
        'bold': True, 'font_size': 14, 'font_name': 'Segoe UI',
        'font_color': '#2563EB', 'bg_color': '#EFF6FF',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#BFDBFE',
        'num_format': '$#,##0.00'
    })
    kpi_card_val_blue_text = workbook.add_format({
        'bold': True, 'font_size': 13, 'font_name': 'Segoe UI',
        'font_color': '#2563EB', 'bg_color': '#EFF6FF',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#BFDBFE'
    })
    kpi_card_val_purple = workbook.add_format({
        'bold': True, 'font_size': 14, 'font_name': 'Segoe UI',
        'font_color': '#7C3AED', 'bg_color': '#F5F3FF',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#DDD6FE',
        'num_format': '$#,##0.0000'
    })

    # Tablo Başlığı
    th_fmt = workbook.add_format({
        'bold': True, 'font_size': 10, 'font_name': 'Segoe UI',
        'font_color': '#FFFFFF', 'bg_color': '#1E293B',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#475569',
        'text_wrap': True
    })

    # Veri Hücreleri
    cell_center = workbook.add_format({'font_name': 'Segoe UI', 'font_size': 9.5, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#E2E8F0'})
    cell_left = workbook.add_format({'font_name': 'Segoe UI', 'font_size': 9.5, 'align': 'left', 'valign': 'vcenter', 'border': 1, 'border_color': '#E2E8F0'})
    cell_currency = workbook.add_format({'font_name': 'Segoe UI', 'font_size': 9.5, 'align': 'right', 'valign': 'vcenter', 'border': 1, 'border_color': '#E2E8F0', 'num_format': '$#,##0.0000'})
    cell_currency_2d = workbook.add_format({'font_name': 'Segoe UI', 'font_size': 9.5, 'align': 'right', 'valign': 'vcenter', 'border': 1, 'border_color': '#E2E8F0', 'num_format': '$#,##0.00'})
    
    cell_green = workbook.add_format({
        'font_name': 'Segoe UI', 'font_size': 9.5, 'bold': True,
        'font_color': '#059669', 'bg_color': '#F0FDF4',
        'align': 'right', 'valign': 'vcenter', 'border': 1, 'border_color': '#BBF7D0',
        'num_format': '+$#,##0.0000;-$#,##0.0000;$0.00'
    })
    cell_red = workbook.add_format({
        'font_name': 'Segoe UI', 'font_size': 9.5, 'bold': True,
        'font_color': '#DC2626', 'bg_color': '#FEF2F2',
        'align': 'right', 'valign': 'vcenter', 'border': 1, 'border_color': '#FECACA',
        'num_format': '+$#,##0.0000;-$#,##0.0000;$0.00'
    })
    cell_roe_green = workbook.add_format({
        'font_name': 'Segoe UI', 'font_size': 9.5, 'bold': True,
        'font_color': '#059669', 'bg_color': '#F0FDF4',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#BBF7D0',
        'num_format': '+0.00%;-0.00%;0.00%'
    })
    cell_roe_red = workbook.add_format({
        'font_name': 'Segoe UI', 'font_size': 9.5, 'bold': True,
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
    win_rate = (win_count / total_trades * 100.0) if total_trades > 0 else 0.0

    total_gross_profit = sum(h.get('gross_pnl', 0) for h in win_trades)
    total_gross_loss = sum(h.get('gross_pnl', 0) for h in loss_trades)
    total_fees = sum(h.get('fees', 0) for h in history_data)
    total_net_pnl = sum(h.get('net_pnl', 0) for h in history_data)
    growth_pct = ((current_balance - initial_balance) / initial_balance * 100.0) if initial_balance > 0 else 0.0

    # ==================== SHEET 1: DASHBOARD & GRAFIKLER ====================
    ws1 = workbook.add_worksheet('📊 ÖZET & GRAFİKLER')
    ws1.hide_gridlines(2)

    # Banner
    ws1.merge_range('B2:K2', 'VALKYRIE QUANT DESK — PERFORMANS & TİCARET RAPORU', title_fmt)
    ws1.merge_range('B3:K3', f'Rapor Tarihi: {datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")} | Algoritmik Vadeli İşlem Defteri', subtitle_fmt)
    ws1.set_row(1, 32)
    ws1.set_row(2, 20)

    # Genişletilmiş Kolon Genişlikleri (Yazı Taşmalarını Engeller)
    ws1.set_column('A:A', 3)
    ws1.set_column('B:B', 24) # Net PnL
    ws1.set_column('C:C', 26) # Win Rate
    ws1.set_column('D:D', 22) # Toplam Islem
    ws1.set_column('E:E', 24) # Komisyon
    ws1.set_column('F:F', 24) # Toplam Kasa
    ws1.set_column('G:G', 22) # Portfoy Buyumesi
    ws1.set_column('H:H', 20) # Parite Net PnL
    ws1.set_column('I:I', 20) # Parite Komisyon
    ws1.set_column('J:K', 15)

    # KPI Kartları (Satır 5-7)
    ws1.write('B5', 'TOPLAM NET KÂR / ZARAR', kpi_card_lbl)
    ws1.write('B6', total_net_pnl, kpi_card_val_green if total_net_pnl >= 0 else kpi_card_val_red)

    ws1.write('C5', 'KAZANMA ORANI (WIN RATE)', kpi_card_lbl)
    ws1.write('C6', f"{win_rate:.1f}% ({win_count}K / {loss_count}Z)", kpi_card_val_blue_text)

    ws1.write('D5', 'TOPLAM İŞLEM SAYISI', kpi_card_lbl)
    ws1.write('D6', f"{total_trades} İşlem", kpi_card_val_blue_text)

    ws1.write('E5', 'ÖDENEN BORSA KOMİSYONU', kpi_card_lbl)
    ws1.write('E6', total_fees, kpi_card_val_purple)

    ws1.write('F5', 'GÜNCEL TOPLAM KASA', kpi_card_lbl)
    ws1.write('F6', current_balance, kpi_card_val_blue)

    ws1.write('G5', 'PORTFÖY BÜYÜMESİ', kpi_card_lbl)
    ws1.write('G6', f"{growth_pct:+.2f}%", kpi_card_val_green if growth_pct >= 0 else kpi_card_val_red)

    ws1.set_row(4, 20)
    ws1.set_row(5, 28)

    # Pasta Grafiği İçin Veri Tablosu (Satır 9-12)
    ws1.write('B9', 'İşlem Tipi', th_fmt)
    ws1.write('C9', 'Adet', th_fmt)
    ws1.write('D9', 'Toplam Net PnL ($)', th_fmt)

    ws1.write('B10', 'Kârlı İşlemler (Wins)', cell_left)
    ws1.write('C10', win_count, cell_center)
    ws1.write('D10', sum(h.get('net_pnl', 0) for h in win_trades), cell_green)

    ws1.write('B11', 'Zararlı İşlemler (Losses)', cell_left)
    ws1.write('C11', loss_count, cell_center)
    ws1.write('D11', sum(h.get('net_pnl', 0) for h in loss_trades), cell_red)

    # 1. PASTA GRAFİĞİ: KÂR / ZARAR DAĞILIMI
    pie_chart = workbook.add_chart({'type': 'doughnut'})
    pie_chart.add_series({
        'name': 'İşlem Dağılımı',
        'categories': "='📊 ÖZET & GRAFİKLER'!$B$10:$B$11",
        'values':     "='📊 ÖZET & GRAFİKLER'!$C$10:$C$11",
        'points': [
            {'fill': {'color': '#10B981'}}, # Canlı Yeşil
            {'fill': {'color': '#EF4444'}}, # Canlı Kırmızı
        ],
        'data_labels': {'percentage': True, 'font': {'name': 'Segoe UI', 'size': 11, 'bold': True}}
    })
    pie_chart.set_title({'name': '🎯 Kârlı vs Zararlı İşlem Dağılımı', 'name_font': {'name': 'Segoe UI', 'size': 12, 'bold': True}})
    pie_chart.set_style(10)
    pie_chart.set_hole_size(45)
    pie_chart.set_size({'width': 440, 'height': 280})
    ws1.insert_chart('B14', pie_chart)

    # 2. KOLON GRAFİĞİ: PARİTE BAZINDA PERFORMANS & KOMİSYON
    pair_stats = {}
    for h in history_data:
        sym = h.get('symbol', 'Bilinmeyen')
        if sym not in pair_stats:
            pair_stats[sym] = {'trades': 0, 'net_pnl': 0.0, 'fees': 0.0}
        pair_stats[sym]['trades'] += 1
        pair_stats[sym]['net_pnl'] += h.get('net_pnl', 0.0)
        pair_stats[sym]['fees'] += h.get('fees', 0.0)

    # Parite Tablosu (Satır 9, Kolon F-I)
    ws1.write('F9', 'Parite', th_fmt)
    ws1.write('G9', 'İşlem Sayısı', th_fmt)
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
            'categories': f"='📊 ÖZET & GRAFİKLER'!$F$10:$F${row_idx}",
            'values':     f"='📊 ÖZET & GRAFİKLER'!$H$10:$H${row_idx}",
            'fill': {'color': '#3B82F6'}
        })
        bar_chart.set_title({'name': '📈 Parite Bazında Net Kâr / Zarar ($)', 'name_font': {'name': 'Segoe UI', 'size': 12, 'bold': True}})
        bar_chart.set_y_axis({'name': 'Net PnL ($)'})
        bar_chart.set_size({'width': 520, 'height': 280})
        ws1.insert_chart('F14', bar_chart)

    # ==================== SHEET 2: TÜM İŞLEMLER DEFTERİ ====================
    ws2 = workbook.add_worksheet('📜 TÜM İŞLEMLER')
    ws2.set_row(0, 28)

    headers = [
        ("İşlem ID", 14), ("Parite", 12), ("Yön", 10), ("Kaldıraç", 10),
        ("Giriş Zamanı", 18), ("Çıkış Zamanı", 18), ("Marjin ($)", 12),
        ("Giriş Fiyatı", 14), ("Çıkış Fiyatı", 14), ("Brüt Kâr ($)", 14),
        ("Komisyon ($)", 14), ("Net Kâr ($)", 14), ("ROE (%)", 12),
        ("Bakiye ($)", 14), ("Setup Stratejisi", 28), ("Çıkış Nedeni", 30)
    ]

    for col_idx, (h_name, width) in enumerate(headers):
        ws2.write(0, col_idx, h_name, th_fmt)
        ws2.set_column(col_idx, col_idx, width)

    for r_idx, h in enumerate(history_data, start=1):
        ws2.set_row(r_idx, 22)
        is_win = h.get('net_pnl', 0) >= 0
        pnl_fmt = cell_green if is_win else cell_red
        roe_fmt = cell_roe_green if is_win else cell_roe_red

        ws2.write(r_idx, 0, h.get('id', ''), cell_center)
        ws2.write(r_idx, 1, h.get('symbol', ''), cell_center)
        ws2.write(r_idx, 2, h.get('side', ''), cell_center)
        ws2.write(r_idx, 3, f"{h.get('leverage', 5)}x", cell_center)
        ws2.write(r_idx, 4, h.get('entry_time', ''), cell_center)
        ws2.write(r_idx, 5, h.get('exit_time', ''), cell_center)
        ws2.write(r_idx, 6, h.get('margin', 0.0), cell_currency_2d)
        ws2.write(r_idx, 7, h.get('entry_price', 0.0), cell_currency)
        ws2.write(r_idx, 8, h.get('exit_price', 0.0), cell_currency)
        ws2.write(r_idx, 9, h.get('gross_pnl', 0.0), pnl_fmt)
        ws2.write(r_idx, 10, h.get('fees', 0.0), cell_currency)
        ws2.write(r_idx, 11, h.get('net_pnl', 0.0), pnl_fmt)
        ws2.write(r_idx, 12, (h.get('roe_pct', 0.0) / 100.0), roe_fmt)
        ws2.write(r_idx, 13, h.get('balance_after', current_balance), cell_currency_2d)
        ws2.write(r_idx, 14, h.get('reason', ''), cell_left)
        ws2.write(r_idx, 15, h.get('close_reason', ''), cell_left)

    # ==================== SHEET 3: KÂRLI İŞLEMLER (WINS) ====================
    ws3 = workbook.add_worksheet('🟢 KÂRLI İŞLEMLER')
    ws3.set_row(0, 28)
    for col_idx, (h_name, width) in enumerate(headers):
        ws3.write(0, col_idx, h_name, th_fmt)
        ws3.set_column(col_idx, col_idx, width)

    for r_idx, h in enumerate(win_trades, start=1):
        ws3.set_row(r_idx, 22)
        ws3.write(r_idx, 0, h.get('id', ''), cell_center)
        ws3.write(r_idx, 1, h.get('symbol', ''), cell_center)
        ws3.write(r_idx, 2, h.get('side', ''), cell_center)
        ws3.write(r_idx, 3, f"{h.get('leverage', 5)}x", cell_center)
        ws3.write(r_idx, 4, h.get('entry_time', ''), cell_center)
        ws3.write(r_idx, 5, h.get('exit_time', ''), cell_center)
        ws3.write(r_idx, 6, h.get('margin', 0.0), cell_currency_2d)
        ws3.write(r_idx, 7, h.get('entry_price', 0.0), cell_currency)
        ws3.write(r_idx, 8, h.get('exit_price', 0.0), cell_currency)
        ws3.write(r_idx, 9, h.get('gross_pnl', 0.0), cell_green)
        ws3.write(r_idx, 10, h.get('fees', 0.0), cell_currency)
        ws3.write(r_idx, 11, h.get('net_pnl', 0.0), cell_green)
        ws3.write(r_idx, 12, (h.get('roe_pct', 0.0) / 100.0), cell_roe_green)
        ws3.write(r_idx, 13, h.get('balance_after', current_balance), cell_currency_2d)
        ws3.write(r_idx, 14, h.get('reason', ''), cell_left)
        ws3.write(r_idx, 15, h.get('close_reason', ''), cell_left)

    # ==================== SHEET 4: ZARARLI İŞLEMLER (LOSSES) ====================
    ws4 = workbook.add_worksheet('🔴 ZARAR KES İŞLEMLERİ')
    ws4.set_row(0, 28)
    for col_idx, (h_name, width) in enumerate(headers):
        ws4.write(0, col_idx, h_name, th_fmt)
        ws4.set_column(col_idx, col_idx, width)

    for r_idx, h in enumerate(loss_trades, start=1):
        ws4.set_row(r_idx, 22)
        ws4.write(r_idx, 0, h.get('id', ''), cell_center)
        ws4.write(r_idx, 1, h.get('symbol', ''), cell_center)
        ws4.write(r_idx, 2, h.get('side', ''), cell_center)
        ws4.write(r_idx, 3, f"{h.get('leverage', 5)}x", cell_center)
        ws4.write(r_idx, 4, h.get('entry_time', ''), cell_center)
        ws4.write(r_idx, 5, h.get('exit_time', ''), cell_center)
        ws4.write(r_idx, 6, h.get('margin', 0.0), cell_currency_2d)
        ws4.write(r_idx, 7, h.get('entry_price', 0.0), cell_currency)
        ws4.write(r_idx, 8, h.get('exit_price', 0.0), cell_currency)
        ws4.write(r_idx, 9, h.get('gross_pnl', 0.0), cell_red)
        ws4.write(r_idx, 10, h.get('fees', 0.0), cell_currency)
        ws4.write(r_idx, 11, h.get('net_pnl', 0.0), cell_red)
        ws4.write(r_idx, 12, (h.get('roe_pct', 0.0) / 100.0), cell_roe_red)
        ws4.write(r_idx, 13, h.get('balance_after', current_balance), cell_currency_2d)
        ws4.write(r_idx, 14, h.get('reason', ''), cell_left)
        ws4.write(r_idx, 15, h.get('close_reason', ''), cell_left)

    workbook.close()
    output.seek(0)
    return output
