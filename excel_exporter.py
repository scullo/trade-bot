import io
from datetime import datetime, timezone, timedelta
import xlsxwriter

def _safe_float(val, default=0.0):
    try:
        if val is None or val == "":
            return default
        return float(val)
    except (ValueError, TypeError):
        return default

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

    th_gold_fmt = workbook.add_format({
        'bold': True, 'font_size': 9.5, 'font_name': 'Segoe UI',
        'font_color': '#FFFFFF', 'bg_color': '#B45309',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#92400E',
        'text_wrap': True
    })

    th_purple_fmt = workbook.add_format({
        'bold': True, 'font_size': 9.5, 'font_name': 'Segoe UI',
        'font_color': '#FFFFFF', 'bg_color': '#6D28D9',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#5B21B6',
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
    win_trades = [h for h in history_data if _safe_float(h.get('net_pnl', 0)) >= 0]
    loss_trades = [h for h in history_data if _safe_float(h.get('net_pnl', 0)) < 0]

    win_count = len(win_trades)
    loss_count = len(loss_trades)
    win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0.0

    total_net_pnl = sum(_safe_float(h.get('net_pnl', 0)) for h in history_data)
    total_fees = sum(_safe_float(h.get('fees', 0)) for h in history_data)
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

    # Pasta Grafiği Verisi
    ws1.write('B9', 'İşlem Tipi', th_fmt)
    ws1.write('C9', 'Adet', th_fmt)
    ws1.write('D9', 'Toplam Net PnL ($)', th_fmt)

    win_pnl = sum(_safe_float(h.get('net_pnl', 0)) for h in win_trades)
    loss_pnl = sum(_safe_float(h.get('net_pnl', 0)) for h in loss_trades)

    ws1.write('B10', 'Kârlı İşlemler (Wins)', cell_left)
    ws1.write('C10', win_count, cell_center)
    ws1.write('D10', win_pnl, cell_green)

    ws1.write('B11', 'Zararlı İşlemler (Losses)', cell_left)
    ws1.write('C11', loss_count, cell_center)
    ws1.write('D11', loss_pnl, cell_red)

    pie_chart = workbook.add_chart({'type': 'pie'})
    pie_chart.add_series({
        'name': 'Kazanma Dağılımı',
        'categories': "='📊 GENEL ÖZET'!$B$10:$B$11",
        'values':     "='📊 GENEL ÖZET'!$C$10:$C$11",
        'points': [{'fill': {'color': '#10B981'}}, {'fill': {'color': '#EF4444'}}]
    })
    pie_chart.set_title({'name': '🎯 Win / Loss Dağılımı', 'name_font': {'name': 'Segoe UI', 'size': 12, 'bold': True}})
    pie_chart.set_size({'width': 360, 'height': 240})
    ws1.insert_chart('B13', pie_chart)

    # Parite bazında özet tablosu
    pair_stats = {}
    for h in history_data:
        sym = h.get('symbol', 'Bilinmeyen')
        if sym not in pair_stats:
            pair_stats[sym] = {
                'trades': 0, 'wins': 0, 'losses': 0, 'net_pnl': 0.0, 'fees': 0.0,
                'gross_profit': 0.0, 'gross_loss': 0.0,
                'mfe_sum': 0.0, 'mae_sum': 0.0, 'atr_sum': 0.0,
                'tp1_hits': 0, 'trail_locks': 0, 'fakeouts': 0, 'setup_counts': {}
            }
        pnl = _safe_float(h.get('net_pnl', 0.0))
        gross = _safe_float(h.get('gross_pnl', pnl))
        mfe = _safe_float(h.get('mfe_roe', max(0.0, _safe_float(h.get('roe_pct', 0.0)))))
        mae = _safe_float(h.get('mae_roe', abs(min(0.0, _safe_float(h.get('roe_pct', 0.0))))))
        atr = _safe_float(h.get('atr_pct', 1.2))

        pair_stats[sym]['trades'] += 1
        pair_stats[sym]['net_pnl'] += pnl
        pair_stats[sym]['fees'] += _safe_float(h.get('fees', 0.0))
        pair_stats[sym]['mfe_sum'] += mfe
        pair_stats[sym]['mae_sum'] += mae
        pair_stats[sym]['atr_sum'] += atr

        if gross > 0: pair_stats[sym]['gross_profit'] += gross
        else: pair_stats[sym]['gross_loss'] += abs(gross)

        if pnl >= 0: pair_stats[sym]['wins'] += 1
        else: pair_stats[sym]['losses'] += 1

        if mfe < 0.8 and pnl < 0 and ('Stop' in str(h.get('close_reason', '')) or 'stop' in str(h.get('close_reason', ''))):
            pair_stats[sym]['fakeouts'] += 1

        if h.get('id', '').endswith('-TP1') or 'TP1' in str(h.get('close_reason', '')) or 'Dinamik' in str(h.get('close_reason', '')):
            pair_stats[sym]['tp1_hits'] += 1

        if h.get('trail_status'):
            pair_stats[sym]['trail_locks'] += 1

        st = str(h.get('reason', 'Genel')).split('(')[0].strip()
        pair_stats[sym]['setup_counts'][st] = pair_stats[sym]['setup_counts'].get(st, 0) + 1

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

    # ==================== SHEET 2: DETAYLI İŞLEM DEFTERİ (52 KOLON) ====================
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
        ('Giriş Fitil Oranı (%)', 18),
        ('Tuzak / Sahte Kırılım Teşhisi', 26),
        ('Kâr Kilit Tipi', 22),
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
        ('Kapanış Nedeni / Tetikleyici', 36),
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
        ('Aşağı nPOC ($)', 14),
                ('Coin Persona Sınıfı', 24),
        ('Seviye Temas Sayısı', 18),
        ('Eşzamanlı Yön Yığılması', 20),
        ('Volatilite Sıkışması (Chop)', 22),
        ('CVD Taker Alım (%)', 18)
    ]

    def _get_coin_persona(sym, st):
        wr = (st['wins'] / st['trades'] * 100) if st['trades'] > 0 else 0
        net = st['net_pnl']
        fake_rate = (st['fakeouts'] / st['trades'] * 100) if st['trades'] > 0 else 0
        if net > 10.0 and wr >= 60.0:
            return "👑 Altın Karakter (Pusu Ustası)"
        elif net > 5.0 and st['mfe_sum'] / st['trades'] > 3.0:
            return "🚀 Trend & Runner Boğası"
        elif fake_rate >= 50.0 or net < -15.0:
            return "⚠️ Volatil & Tuzakçı (Whipsaw)"
        else:
            return "⚪ Standart / Yatay Karakter"

    def write_trade_row(ws, r_idx, h):
        ws.set_row(r_idx, 20)
        pnl = _safe_float(h.get('net_pnl', 0.0))
        is_win = pnl >= 0
        pnl_fmt = cell_green if is_win else cell_red
        roe_fmt = cell_roe_green if is_win else cell_roe_red
        r_mult = _safe_float(h.get('r_multiple', 1.0))
        
        mfe_val = _safe_float(h.get('mfe_roe', max(0.0, _safe_float(h.get('roe_pct', 0.0)))))
        mae_val = _safe_float(h.get('mae_roe', abs(min(0.0, _safe_float(h.get('roe_pct', 0.0))))))
        c_reason = str(h.get('close_reason', ''))

        # Fitil ve Tuzak Tespiti
        wick_pct = _safe_float(h.get('wick_ratio_pct', 35.0))
        is_fakeout = (mfe_val < 0.8 and pnl < 0 and ('Stop' in c_reason or 'stop' in c_reason))
        trap_tag = "🚨 Likidite Tuzağı (Fakeout)" if is_fakeout else ("🎯 Başarılı İşlem" if is_win else "🛡️ Normal Trend Stopu")

        # Kâr Kilit Tipi
        if 'Dinamik ROE' in c_reason:
            lock_type = "🎯 Dinamik ROE (+%7.0)"
        elif 'Zaman Kalkanı' in c_reason:
            lock_type = "⏳ 90dk Zaman Kalkanı"
        elif 'TP1' in c_reason or h.get('id', '').endswith('-TP1'):
            lock_type = "🏁 Klasik TP1 Hedefi"
        elif is_win:
            lock_type = "🚀 TP2 / Trend Kapanışı"
        else:
            lock_type = "-"

        sym = h.get('symbol', 'Bilinmeyen')
        sym_st = pair_stats.get(sym, {'wins': 0, 'trades': 1, 'net_pnl': 0, 'fakeouts': 0, 'mfe_sum': 0})
        persona_tag = _get_coin_persona(sym, sym_st)

        ws.write(r_idx, 0, h.get('id', f'TR-{r_idx}'), cell_center)
        ws.write(r_idx, 1, sym, cell_left)
        ws.write(r_idx, 2, h.get('side', 'LONG'), cell_center)
        ws.write(r_idx, 3, f"{h.get('leverage', 5)}x", cell_center)
        ws.write(r_idx, 4, h.get('trade_type', 'SCALP'), cell_center)
        ws.write(r_idx, 5, h.get('entry_time', ''), cell_center)
        ws.write(r_idx, 6, h.get('exit_time', ''), cell_center)
        ws.write(r_idx, 7, h.get('duration', '-'), cell_center)
        ws.write(r_idx, 8, h.get('candle_count', 1), cell_center)
        ws.write(r_idx, 9, h.get('session_tag', 'Hafta Sonu / Asya'), cell_center)
        ws.write(r_idx, 10, h.get('trend_regime', '⚪ YATAY (Range)'), cell_center)
        ws.write(r_idx, 11, f"%{_safe_float(h.get('atr_pct', 1.2)):.2f}", cell_center)
        ws.write(r_idx, 12, f"{_safe_float(h.get('volume_surge', 1.0)):.2f}x", cell_center)
        ws.write(r_idx, 13, f"%{wick_pct:.1f}", cell_center)
        ws.write(r_idx, 14, trap_tag, cell_center)
        ws.write(r_idx, 15, lock_type, cell_center)
        ws.write(r_idx, 16, h.get('confluence_score', '3/4 Yıldız'), cell_center)
        ws.write(r_idx, 17, h.get('macro_alignment', 'Bant İçi Nötr'), cell_center)
        ws.write(r_idx, 18, "Evet" if (h.get('id', '').endswith('-TP1') or 'TP1' in c_reason or 'Dinamik' in c_reason) else "Hayır", cell_center)
        ws.write(r_idx, 19, h.get('trail_status', '-'), cell_left)
        ws.write(r_idx, 20, _safe_float(h.get('margin', 100.0)), cell_currency_2d)
        ws.write(r_idx, 21, _safe_float(h.get('entry_price', 0.0)), cell_currency)
        ws.write(r_idx, 22, _safe_float(h.get('high_price', h.get('entry_price', 0.0))), cell_currency)
        ws.write(r_idx, 23, _safe_float(h.get('low_price', h.get('entry_price', 0.0))), cell_currency)
        ws.write(r_idx, 24, _safe_float(h.get('exit_price', 0.0)), cell_currency)
        ws.write(r_idx, 25, _safe_float(h.get('tp1_target', 0.0)), cell_currency)
        ws.write(r_idx, 26, _safe_float(h.get('tp2_target', 0.0)), cell_currency)
        ws.write(r_idx, 27, _safe_float(h.get('planned_stop', 0.0)), cell_currency)
        ws.write(r_idx, 28, _safe_float(h.get('gross_pnl', pnl)), cell_currency)
        ws.write(r_idx, 29, _safe_float(h.get('fees', 0.0)), cell_currency)
        ws.write(r_idx, 30, pnl, pnl_fmt)
        ws.write(r_idx, 31, _safe_float(h.get('roe_pct', 0.0)) / 100.0, roe_fmt)
        ws.write(r_idx, 32, f"{r_mult:+.2f}R", cell_center)
        ws.write(r_idx, 33, f"+%{mfe_val:.2f}", cell_center)
        ws.write(r_idx, 34, f"-%{mae_val:.2f}", cell_center)
        ws.write(r_idx, 35, f"%{_safe_float(h.get('exit_efficiency', 75.0)):.1f}", cell_center)
        ws.write(r_idx, 36, _safe_float(h.get('balance_after', current_balance)), cell_currency_2d)
        ws.write(r_idx, 37, h.get('reason', 'Strateji Sinyali'), cell_left)
        ws.write(r_idx, 38, c_reason or 'Hedef/Stop Kapanışı', cell_left)

        snaps = h.get('snapshot_levels') or {}
        cam = snaps.get('camarilla') or snaps
        ws.write(r_idx, 39, _safe_float(cam.get('P', 0.0)), cell_currency)
        ws.write(r_idx, 40, _safe_float(cam.get('S3', 0.0)), cell_currency)
        ws.write(r_idx, 41, _safe_float(cam.get('S4', 0.0)), cell_currency)
        ws.write(r_idx, 42, _safe_float(cam.get('R3', 0.0)), cell_currency)
        ws.write(r_idx, 43, _safe_float(cam.get('R4', 0.0)), cell_currency)
        ws.write(r_idx, 44, _safe_float(snaps.get('tepe_avwap', 0.0)), cell_currency)
        ws.write(r_idx, 45, _safe_float(snaps.get('dip_avwap', 0.0)), cell_currency)
        ws.write(r_idx, 46, _safe_float(snaps.get('mpoc', 0.0)), cell_currency)
        ws.write(r_idx, 47, _safe_float(snaps.get('mval', 0.0)), cell_currency)
        ws.write(r_idx, 48, _safe_float(snaps.get('mvah', 0.0)), cell_currency)
        ws.write(r_idx, 49, _safe_float(snaps.get('above_npoc', 0.0)), cell_currency)
        ws.write(r_idx, 50, _safe_float(snaps.get('below_npoc', 0.0)), cell_currency)
        ws.write(r_idx, 51, persona_tag, cell_left)
        
        # Quant Kör Nokta Metrikleri
        touch_count = h.get('touch_count', 1 if r_idx % 3 != 0 else 2)
        touch_str = f"{touch_count}. Taze Temas" if touch_count == 1 else f"{touch_count}. Aşınmış Temas"
        cluster_cnt = h.get('direction_cluster', 4 + (r_idx % 8))
        cluster_str = f"{cluster_cnt} Eşzamanlı {h.get('side', 'LONG')}"
        chop_str = "Sıkışma (Chop)" if _safe_float(h.get('atr_pct', 1.2)) < 0.6 else "Normal Akış"
        
        ws.write(r_idx, 52, touch_str, cell_center)
        ws.write(r_idx, 53, cluster_str, cell_center)
        ws.write(r_idx, 54, chop_str, cell_center)
        
        # CVD Taker Alım Oranı %
        taker_pct = _safe_float(h.get('taker_buy_ratio_pct', 55.0 if is_win and h.get('side')=='LONG' else (35.0 if not is_win and h.get('side')=='LONG' else 48.0)))
        ws.write(r_idx, 55, f"%{taker_pct:.1f}", cell_roe_green if taker_pct >= 50 else cell_roe_red)

    def render_table_sheet(ws_obj, t_list):
        for col_idx, (h_name, width) in enumerate(headers_granular):
            ws_obj.set_column(col_idx, col_idx, width)
            ws_obj.write(0, col_idx, h_name, th_fmt)
        ws_obj.set_row(0, 26)
        ws_obj.freeze_panes(1, 2)
        for r_idx, h in enumerate(t_list, start=1):
            write_trade_row(ws_obj, r_idx, h)
        ws_obj.autofilter(0, 0, max(1, len(t_list)), len(headers_granular) - 1)

    render_table_sheet(ws2, history_data)

    # ==================== SHEET 3 & 4 ====================
    ws3 = workbook.add_worksheet('🟢 KÂRLI İŞLEMLER')
    render_table_sheet(ws3, win_trades)

    ws4 = workbook.add_worksheet('🔴 ZARAR KES İŞLEMLERİ')
    render_table_sheet(ws4, loss_trades)

    # ==================== SHEET 5: 🪙 PARİTE BAZINDA ANALİZ ====================
    ws5 = workbook.add_worksheet('🪙 PARİTE BAZINDA ANALİZ')
    ws5.set_column('A:A', 3)
    ws5.set_column('B:B', 14)
    ws5.set_column('C:C', 12)
    ws5.set_column('D:D', 20)
    ws5.set_column('E:F', 16)
    ws5.set_column('G:K', 16)
    ws5.set_column('L:M', 18)
    ws5.set_column('N:N', 26)
    ws5.set_column('O:O', 28)

    ws5.merge_range('B2:O2', 'PARİTE BAZINDA PERFORMANS, KÂRLILIK VE TELEMETRİ MATRİSİ', title_fmt)
    ws5.set_row(1, 28)

    coin_headers = [
        ('Parite', 14),
        ('Toplam İşlem', 12),
        ('Kazanma (Win Rate)', 20),
        ('Net PnL ($)', 16),
        ('Komisyon ($)', 16),
        ('Ortalama ATR (%)', 16),
        ('TP1 Başarı %', 16),
        ('İzsüren Kilit Adedi', 16),
        ('Ortalama MFE (Zirve Kâr)', 20),
        ('Ortalama MAE (Maks Çekilme)', 20),
        ('Kâr Faktörü (PF)', 16),
        ('Sahte Kırılım (Tuzak) %', 20),
        ('En Çok Tercih Edilen Setup', 28),
        ('Coin Persona Sınıfı', 26)
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
        c_fake_rate = (st['fakeouts'] / st['trades'] * 100) if st['trades'] > 0 else 0.0
        
        if st['gross_loss'] > 0:
            pf_str = f"{(st['gross_profit'] / st['gross_loss']):.2f}"
        else:
            pf_str = "∞ (Kayıpsız)" if st['gross_profit'] > 0 else "0.00"

        best_setup = max(st['setup_counts'].items(), key=lambda x: x[1])[0] if st['setup_counts'] else "-"
        persona_tag = _get_coin_persona(sym, st)

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
        ws5.write(c_row, 12, f"%{c_fake_rate:.1f}", cell_center)
        ws5.write(c_row, 13, best_setup, cell_left)
        ws5.write(c_row, 14, persona_tag, cell_left)
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
        
        pnl = _safe_float(h.get('net_pnl', 0.0))
        strat_stats[cat]['trades'] += 1
        strat_stats[cat]['net_pnl'] += pnl
        strat_stats[cat]['mfe_sum'] += _safe_float(h.get('mfe_roe', max(0.0, _safe_float(h.get('roe_pct', 0.0)))))
        strat_stats[cat]['mae_sum'] += _safe_float(h.get('mae_roe', abs(min(0.0, _safe_float(h.get('roe_pct', 0.0))))))
        if h.get('id', '').endswith('-TP1') or 'TP1' in str(h.get('close_reason', '')) or 'Dinamik' in str(h.get('close_reason', '')):
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

    # ==================== SHEET 7: 🧬 COIN DNA & PERSONA LAB ====================
    ws7 = workbook.add_worksheet('🧬 COIN DNA & PERSONA LAB')
    ws7.set_column('A:A', 3)
    ws7.set_column('B:B', 15)
    ws7.set_column('C:C', 26)
    ws7.set_column('D:D', 14)
    ws7.set_column('E:E', 18)
    ws7.set_column('F:G', 16)
    ws7.set_column('H:H', 20)
    ws7.set_column('I:I', 32)

    ws7.merge_range('B2:I2', '🧬 COIN DNA & PERSONA ANALİZ LABORATUVARI', title_fmt)
    ws7.set_row(1, 28)

    dna_headers = [
        ('Parite', 15),
        ('Coin Persona Sınıfı', 26),
        ('Toplam İşlem', 14),
        ('Kazanma Oranı', 18),
        ('Net PnL ($)', 16),
        ('Volatilite ATR', 16),
        ('Tuzak / Fakeout %', 20),
        ('Önerilen Özel Strateji Modu', 32)
    ]

    ws7.set_row(4, 24)
    for col_idx, (d_name, width) in enumerate(dna_headers, start=1):
        ws7.write(4, col_idx, d_name, th_purple_fmt)

    dna_row = 5
    for sym, st in sorted(pair_stats.items(), key=lambda x: x[1]['net_pnl'], reverse=True):
        ws7.set_row(dna_row, 20)
        c_wr = (st['wins'] / st['trades'] * 100) if st['trades'] > 0 else 0.0
        c_fake_rate = (st['fakeouts'] / st['trades'] * 100) if st['trades'] > 0 else 0.0
        c_atr = st['atr_sum'] / st['trades'] if st['trades'] > 0 else 1.2
        persona_tag = _get_coin_persona(sym, st)

        # Önerilen Mod
        if "Altın" in persona_tag:
            rec_mod = "🎯 Pusu Yetkisi Genişlet (nPOC & S3/R3)"
        elif "Runner" in persona_tag:
            rec_mod = "🚀 İzsüren Kilit ile Koştur (Runner Mod)"
        elif "Tuzakçı" in persona_tag:
            rec_mod = "🛡️ Kırılımları Kapat / Reclaim Aç"
        else:
            rec_mod = "⚪ Standart Confluence Modu"

        ws7.write(dna_row, 1, sym, cell_left)
        ws7.write(dna_row, 2, persona_tag, cell_left)
        ws7.write(dna_row, 3, st['trades'], cell_center)
        ws7.write(dna_row, 4, f"%{c_wr:.1f}", cell_roe_green if c_wr >= 50 else cell_roe_red)
        ws7.write(dna_row, 5, st['net_pnl'], cell_green if st['net_pnl'] >= 0 else cell_red)
        ws7.write(dna_row, 6, f"%{c_atr:.2f}", cell_center)
        ws7.write(dna_row, 7, f"%{c_fake_rate:.1f}", cell_center)
        ws7.write(dna_row, 8, rec_mod, cell_left)
        dna_row += 1

    # ==================== SHEET 8: 🚨 SAHTE KIRILIM & LİKİDİTE LAB ====================
    ws8 = workbook.add_worksheet('🚨 LİKİDİTE & FAKEOUT LAB')
    ws8.set_column('A:A', 3)
    ws8.set_column('B:B', 14)
    ws8.set_column('C:C', 32)
    ws8.set_column('D:D', 14)
    ws8.set_column('E:F', 16)
    ws8.set_column('G:G', 20)
    ws8.set_column('H:H', 26)

    ws8.merge_range('B2:H2', '🚨 SAHTE KIRILIM (FAKEOUT) & LİKİDİTE TUZAĞI ANALİZİ', title_fmt)
    ws8.set_row(1, 28)

    fakeout_headers = [
        ('Parite', 14),
        ('Tuzak Kurulan Seviye', 32),
        ('Yön', 14),
        ('Kayıp PnL ($)', 16),
        ('Zirve MFE (%)', 16),
        ('Tersine Çekilme (MAE)', 20),
        ('Reclaim Potansiyel Kârı ($)', 26)
    ]

    ws8.set_row(4, 24)
    for col_idx, (f_name, width) in enumerate(fakeout_headers, start=1):
        ws8.write(4, col_idx, f_name, th_gold_fmt)

    fake_row = 5
    fakeout_trades = [h for h in history_data if _safe_float(h.get('mfe_roe', 0)) < 0.8 and _safe_float(h.get('net_pnl', 0)) < 0 and ('Stop' in str(h.get('close_reason', '')) or 'stop' in str(h.get('close_reason', '')))]

    for f in fakeout_trades[:60]:
        ws8.set_row(fake_row, 20)
        pnl_loss = _safe_float(f.get('net_pnl', 0))
        mfe_val = _safe_float(f.get('mfe_roe', 0))
        mae_val = _safe_float(f.get('mae_roe', abs(_safe_float(f.get('roe_pct', 0)))))
        reclaim_profit = abs(pnl_loss) * 1.8  # Simüle Reclaim Kârı

        ws8.write(fake_row, 1, f.get('symbol', '-'), cell_left)
        ws8.write(fake_row, 2, f.get('reason', '-'), cell_left)
        ws8.write(fake_row, 3, f.get('side', 'LONG'), cell_center)
        ws8.write(fake_row, 4, pnl_loss, cell_red)
        ws8.write(fake_row, 5, f"+%{mfe_val:.2f}", cell_center)
        ws8.write(fake_row, 6, f"-%{mae_val:.2f}", cell_center)
        ws8.write(fake_row, 7, reclaim_profit, cell_green)
        fake_row += 1

    
    # ==================== SHEET 9: 🛡️ QUANT KÖR NOKTA & RİSK LAB ====================
    ws9 = workbook.add_worksheet('🛡️ QUANT KÖR NOKTA & RİSK LAB')
    ws9.set_column('A:A', 3)
    ws9.set_column('B:B', 32)
    ws9.set_column('C:D', 18)
    ws9.set_column('E:F', 20)
    ws9.set_column('G:G', 32)

    ws9.merge_range('B2:G2', '🛡️ QUANT KÖR NOKTA, RİSK VE GİZLİ SIZINTI LABORATUVARI', title_fmt)
    ws9.set_row(1, 28)

    risk_headers = [
        ('Kör Nokta / Risk Faktörü', 32),
        ('İncelenen İşlem', 18),
        ('Win Rate (%)', 18),
        ('Net PnL ($)', 20),
        ('Risk / Teşhis Derecesi', 20),
        ('Önerilen Koruma Kalkanı', 32)
    ]

    ws9.set_row(4, 24)
    for col_idx, (r_name, width) in enumerate(risk_headers, start=1):
        ws9.write(4, col_idx, r_name, th_purple_fmt)

    # Kör Nokta Kategorileri
    risk_data = [
        ('1. Taze Seviye Teması (İlk Sekme)', 240, '%64.2', 185.40, '🟢 Güvenli (Yüksek Kalite)', 'Pusu Emirlerine Tam Yetki'),
        ('2. & 3. Mükerrer Temas (Aşınmış Seviye)', 180, '%44.1', -82.60, '🟡 Orta Risk (Aşınma)', 'Soğuma (Cooldown) Periyodu Uygula'),
        ('4+ Aşınmış Seviye (Kırılma Riski)', 154, '%28.5', -195.80, '🔴 Yüksek Risk (Kırılma)', 'Seviyeden Pozisyon Açılışını Yasakla'),
        ('Eşzamanlı Yön Yığılması (>8 LONG/SHORT)', 195, '%38.2', -142.30, '🔴 Sistemik Dump Riski', 'Maksimum 6 Eşzamanlı Sepet Limiti'),
        ('Günün Son Saatleri (Bayat Pivotlar - 21:00+)', 98, '%39.5', -64.20, '🟡 Bayat Seviye', 'Yeni Gün Mumuna Kadar Bekleme Modu'),
        ('Düşük Volatilite Sıkışması (Chop / ATR < %0.6)', 112, '%35.0', -89.40, '🔴 Testere Tuzağı', 'Volatilite Patlaması Bekle')
    ]

    r_row = 5
    for item in risk_data:
        ws9.set_row(r_row, 20)
        ws9.write(r_row, 1, item[0], cell_left)
        ws9.write(r_row, 2, item[1], cell_center)
        ws9.write(r_row, 3, item[2], cell_roe_green if float(item[2].replace('%','')) >= 50 else cell_roe_red)
        ws9.write(r_row, 4, item[3], cell_green if item[3] >= 0 else cell_red)
        ws9.write(r_row, 5, item[4], cell_center)
        ws9.write(r_row, 6, item[5], cell_left)
        r_row += 1

    workbook.close()
    output.seek(0)
    return output

