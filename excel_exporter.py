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

import os
import tempfile

HEADERS_GRANULAR = [
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
    ('CVD Taker Alım (%)', 18),
    ('Breakout İvmesi (Hız xATR)', 22),
    ('Göreceli Güç (RS vs BTC %)', 22),
    ('Ayrışma (Decoupling) Durumu', 26),
    ('Giriş Fonlama Oranı (%)', 20),
    ('Fonlama Squeeze Durumu', 24),
    ('Giriş Öncesi Tasfiye Hacmi ($)', 24),
    ('Tasfiye Teyit Durumu', 26),
    ('Giriş Mikro-CVD Alıcı Oranı (%)', 24),
    ('Mikro Agresyon & Emilim Teyidi', 28),
    ('Kayan 60s Net Delta ($)', 22),
    ('Tahta Dengesizlik (OBI %)', 22),
    ('Tahta Derinlik Oranı (Bid/Ask)', 24),
    ('Tahta Likidite Duvarı', 24),
    ('En İyi Alış/Satış Derinliği', 24),
    ('Tahta Entropisi (Boltzmann %)', 24),
    ('Fraktal Rejim (Hurst H)', 22),
    ('Gizli Likidite (Iceberg Oranı)', 24),
    ('Piyasa Fazı (Simons HMM)', 26),
    ('Bookmap Sipariş Akışı & Çapa', 28),
    ('Spot-Perp Basis (bps)', 20),
    ('Tahta Duvar Yaşı (s)', 18),
    ('Giriş Makası (Spread %)', 20),
    ('Giriş Kayması (Slippage %)', 22),
    ('BTC 60s Mikro-Hız (%)', 20),
    ('Hesaplanan Dolar Riski ($)', 22),
    ('Stoikov Drift (bps)', 20),
    ('VPIN Toksisite Skoru', 22),
    ('Kyle’s Lambda Oranı', 20),
    ('Deribit GEX Rejimi', 22),
    ('Hawkes Tasfiye Çığı (η)', 22),
    ('CVD Uyumsuzluğu (Divergence)', 28),
    ('Göreceli Hacim (RVOL Z-Score)', 24),
    ('Makro Likidite & Dominans', 26),
    ('Geometrik R-Oranı', 18)
]
headers_granular = HEADERS_GRANULAR

def create_styled_excel_report(history_data: list, current_balance: float = 10000.0, initial_balance: float = 10000.0, funding_data: dict = None) -> io.BytesIO:
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
        tmp_path = tmp.name
        
    workbook = xlsxwriter.Workbook(tmp_path)

    # 🧬 3,615 Baz DNA Veritabanini Yukle (Tum 100 Parite Bütünlüğü)
    base_dna_map = {}
    try:
        dna_p = os.path.join(os.path.dirname(__file__), 'coin_dna_baseline.json')
        if os.path.exists(dna_p):
            with open(dna_p, 'r', encoding='utf-8') as f_dna:
                base_dna_map = json.load(f_dna)
    except Exception:
        pass

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

    cell_side_long = workbook.add_format({
        'font_name': 'Segoe UI', 'font_size': 9, 'bold': True,
        'font_color': '#059669', 'bg_color': '#ECFDF5',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#A7F3D0'
    })
    cell_side_short = workbook.add_format({
        'font_name': 'Segoe UI', 'font_size': 9, 'bold': True,
        'font_color': '#DC2626', 'bg_color': '#FEF2F2',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#FECACA'
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

    # Yön Analizi (LONG vs SHORT)
    long_trades = [h for h in history_data if h.get('side') == 'LONG']
    short_trades = [h for h in history_data if h.get('side') == 'SHORT']
    long_count = len(long_trades)
    short_count = len(short_trades)
    long_pnl = sum(_safe_float(h.get('net_pnl', 0)) for h in long_trades)
    short_pnl = sum(_safe_float(h.get('net_pnl', 0)) for h in short_trades)
    long_wr = (sum(1 for h in long_trades if _safe_float(h.get('net_pnl', 0)) >= 0) / long_count * 100) if long_count > 0 else 0.0
    short_wr = (sum(1 for h in short_trades if _safe_float(h.get('net_pnl', 0)) >= 0) / short_count * 100) if short_count > 0 else 0.0

    ws1.write('B27', 'Piyasa Yönü (Side)', th_fmt)
    ws1.write('C27', 'İşlem & Kazanma %', th_fmt)
    ws1.write('D27', 'Toplam Net PnL ($)', th_fmt)

    ws1.write('B28', '🟢 LONG (Boğa)', cell_left)
    ws1.write('C28', f"{long_count} İşlem (%{long_wr:.1f})", cell_center)
    ws1.write('D28', long_pnl, cell_green if long_pnl >= 0 else cell_red)

    ws1.write('B29', '🔴 SHORT (Ayı)', cell_left)
    ws1.write('C29', f"{short_count} İşlem (%{short_wr:.1f})", cell_center)
    ws1.write('D29', short_pnl, cell_green if short_pnl >= 0 else cell_red)

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
        mfe = _safe_float(h.get('max_mfe_roe', h.get('mfe_roe', max(0.0, _safe_float(h.get('roe_pct', 0.0))))))
        mae = _safe_float(h.get('max_mae_roe', h.get('mae_roe', abs(min(0.0, _safe_float(h.get('roe_pct', 0.0)))))))
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
    headers_granular = HEADERS_GRANULAR


    def _get_coin_persona(sym, st):
        clean_s = str(sym).replace('/', '').replace(':USDT', '').upper()
        if st.get('trades', 0) < 3:
            if base_dna_map and clean_s in base_dna_map:
                return base_dna_map[clean_s].get('persona_name', "⚪ Standart / Dengeli")
            return "⚪ Standart / Dengeli"
        wr = (st['wins'] / st['trades'] * 100) if st['trades'] > 0 else 0
        net = st['net_pnl']
        fake_rate = (st['fakeouts'] / st['trades'] * 100) if st['trades'] > 0 else 0
        if net > 3.0 and wr >= 60.0 and fake_rate <= 25.0:
            return "👑 Altın Karakter (Pusu Ustası)"
        elif fake_rate >= 45.0 or (net < -5.0 and wr < 45.0):
            return "⚠️ Volatil & Tuzakçı (Whipsaw)"
        else:
            return "⚪ Standart / Dengeli"

    def write_trade_row(ws, r_idx, h):
        ws.set_row(r_idx, 20)
        pnl = _safe_float(h.get('net_pnl', 0.0))
        is_win = pnl >= 0
        pnl_fmt = cell_green if is_win else cell_red
        roe_fmt = cell_roe_green if is_win else cell_roe_red
        r_mult = _safe_float(h.get('r_multiple', 1.0))
        
        mfe_val = _safe_float(h.get('max_mfe_roe'))
        if mfe_val <= 0.0:
            mfe_val = _safe_float(h.get('mfe_roe', max(0.0, _safe_float(h.get('roe_pct', 0.0)))))
        
        mae_val = _safe_float(h.get('max_mae_roe'))
        if mae_val <= 0.0:
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
        side_val = h.get('side', 'LONG')
        ws.write(r_idx, 2, side_val, cell_side_long if side_val == 'LONG' else cell_side_short)
        ws.write(r_idx, 3, f"{h.get('leverage', 5)}x", cell_center)
        ws.write(r_idx, 4, h.get('trade_type', 'SCALP'), cell_center)
        ws.write(r_idx, 5, h.get('entry_time', ''), cell_center)
        ws.write(r_idx, 6, h.get('exit_time', ''), cell_center)
        ws.write(r_idx, 7, h.get('duration', '-'), cell_center)
        ws.write(r_idx, 8, int(h.get('candle_count') or 1), cell_center)
        ws.write(r_idx, 9, h.get('session') or h.get('session_tag') or 'Hafta Sonu / Asya', cell_center)
        ws.write(r_idx, 10, h.get('trend_regime', '⚪ YATAY (Range)'), cell_center)
        ws.write(r_idx, 11, f"%{_safe_float(h.get('atr_pct', 1.2)):.2f}", cell_center)
        ws.write(r_idx, 12, f"{_safe_float(h.get('volume_surge', 1.0)):.2f}x", cell_center)
        ws.write(r_idx, 13, f"%{wick_pct:.1f}", cell_center)
        ws.write(r_idx, 14, trap_tag, cell_center)
        ws.write(r_idx, 15, lock_type, cell_center)
        ws.write(r_idx, 16, h.get('confluence_score', '3/4 Yıldız'), cell_center)
        ws.write(r_idx, 17, h.get('macro_climate') or h.get('macro_alignment', 'Bant İçi Nötr'), cell_center)
        ws.write(r_idx, 18, "Evet" if (h.get('id', '').endswith('-TP1') or 'TP1' in c_reason or 'Dinamik' in c_reason) else "Hayır", cell_center)
        ws.write(r_idx, 19, h.get('trail_status', '-'), cell_left)
        ws.write(r_idx, 20, _safe_float(h.get('margin', 100.0)), cell_currency_2d)
        ws.write(r_idx, 21, _safe_float(h.get('entry_price', 0.0)), cell_currency)
        ws.write(r_idx, 22, _safe_float(h.get('high_price', h.get('entry_price', 0.0))), cell_currency)
        ws.write(r_idx, 23, _safe_float(h.get('low_price', h.get('entry_price', 0.0))), cell_currency)
        ws.write(r_idx, 24, _safe_float(h.get('exit_price', 0.0)), cell_currency)
        ws.write(r_idx, 25, _safe_float(h.get('tp1_target') or h.get('tp1', 0.0)), cell_currency)
        ws.write(r_idx, 26, _safe_float(h.get('tp2_target') or h.get('tp2', 0.0)), cell_currency)
        ws.write(r_idx, 27, _safe_float(h.get('planned_stop') or h.get('hard_stop') or h.get('soft_stop', 0.0)), cell_currency)
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
        touch_count = h.get('touch_count', 1)
        touch_str = f"{touch_count}. Taze Temas" if touch_count == 1 else f"{touch_count}. Aşınmış Temas"
        cluster_cnt = h.get('direction_cluster', 1)
        cluster_str = f"{cluster_cnt} Eşzamanlı {h.get('side', 'LONG')}"
        chop_str = "Sıkışma (Chop)" if _safe_float(h.get('atr_pct', 1.2)) < 0.6 else "Normal Akış"
        
        ws.write(r_idx, 52, touch_str, cell_center)
        ws.write(r_idx, 53, cluster_str, cell_center)
        ws.write(r_idx, 54, chop_str, cell_center)
        
        # CVD Taker Alım Oranı % (Gerçek Veri)
        taker_pct = _safe_float(h.get('cvd_pct', 50.0))
        ws.write(r_idx, 55, f"%{taker_pct:.1f}", cell_roe_green if taker_pct >= 50 else cell_roe_red)

        # Breakout İvmesi (Candle Velocity)
        ivme = _safe_float(h.get('candle_velocity', 1.0))
        ws.write(r_idx, 56, f"{ivme:.2f}x", cell_roe_green if ivme >= 2.0 else cell_center)

        # Göreceli Güç (RS vs BTC %) & Ayrışma Durumu
        rs_val = _safe_float(h.get('rs_vs_btc', 0.0))
        ws.write(r_idx, 57, f"%{rs_val:+.2f}", cell_roe_green if rs_val >= 0 else cell_roe_red)
        ws.write(r_idx, 58, str(h.get('decoupling_status', '⚪ NÖTR_TAKİPÇİ')), cell_left)

        # Dinamik Fonlama Oranı & Squeeze Durumu
        f_rate = _safe_float(h.get('entry_funding_rate', 0.0100))
        f_stat = str(h.get('funding_status', 'BALANCED'))
        if f_stat == "BALANCED":
            f_lbl = "Dengeli"
        elif f_stat == "SHORT_SQUEEZE_RISK":
            f_lbl = "⚠️ Short Squeeze Korumalı"
        elif f_stat in ("LONG_OVERHEATED", "LONG_SQUEEZE_RISK"):
            f_lbl = "🔥 Long Squeeze / Tepe Şişkinliği"
        else:
            f_lbl = f_stat
        ws.write(r_idx, 59, f"%{f_rate:+.4f}", cell_roe_green if f_rate >= 0 else cell_roe_red)
        ws.write(r_idx, 60, f_lbl, cell_left)

        # Tasfiye Hacmi & Tasfiye Teyit Durumu
        l_vol = _safe_float(h.get('entry_liq_volume_usd', 0.0))
        l_conf = bool(h.get('liq_confirmed', False))
        l_lbl = "💥 YÜKSEK TASFİYE SÜPÜRMESİ (Teyitli)" if (l_conf and l_vol >= 10000) else ("🎯 TASFİYE TEYİTLİ" if l_conf else "STANDART / NÖTR")
        ws.write(r_idx, 61, f"${l_vol:,.2f}" if l_vol > 0 else "-", cell_currency if l_vol > 0 else cell_center)
        ws.write(r_idx, 62, l_lbl, cell_left)

        # Mikro-CVD (Kayan 60s) & Agresyon Durumu (Sütun 63, 64, 65)
        c_pct = _safe_float(h.get('entry_cvd_pct', 50.0))
        c_stat = str(h.get('cvd_status', 'DENGELİ'))
        c_delta = _safe_float(h.get('entry_cvd_delta', 0.0))
        ws.write(r_idx, 63, f"%{c_pct:.1f}", cell_roe_green if c_pct >= 50 else cell_roe_red)
        ws.write(r_idx, 64, c_stat, cell_left)
        ws.write(r_idx, 65, f"${c_delta:+,.2f}", cell_roe_green if c_delta >= 0 else cell_roe_red)

        # Order Book Imbalance (OBI) & Tahta Derinlik Duvarı (Sütun 66, 67, 68, 69)
        obi_pct = _safe_float(h.get('orderbook_imbalance', 0.0)) * 100.0
        obi_ratio = _safe_float(h.get('orderbook_ratio', 1.0))
        obi_wall = str(h.get('orderbook_wall_side', 'BALANCED'))
        wall_lbl = "🟢 GÜÇLÜ ALICI DUVARI" if obi_wall == "BID_WALL" else ("🔴 GÜÇLÜ SATICI DUVARI" if obi_wall == "ASK_WALL" else "⚪ DENGELİ TAHTA")
        b_qty = _safe_float(h.get('orderbook_bid_qty', 0.0))
        a_qty = _safe_float(h.get('orderbook_ask_qty', 0.0))
        qty_str = f"B:{b_qty:,.1f} / A:{a_qty:,.1f}" if (b_qty > 0 or a_qty > 0) else "-"

        ws.write(r_idx, 66, f"%{obi_pct:+.1f}", cell_roe_green if obi_pct >= 0 else cell_roe_red)
        ws.write(r_idx, 67, f"{obi_ratio:.2f}x", cell_roe_green if obi_ratio >= 1.0 else cell_roe_red)
        ws.write(r_idx, 68, wall_lbl, cell_left)
        ws.write(r_idx, 69, qty_str, cell_center)

        # Quant Guardian Sütunları (70, 71, 72, 73)
        ent_val = _safe_float(h.get('orderbook_entropy', 0.70)) * 100.0
        hurst_v = _safe_float(h.get('hurst_exponent', 0.50))
        ice_v = _safe_float(h.get('iceberg_ratio', 1.0))
        hmm_v = str(h.get('hmm_market_phase', 'ACCUMULATION'))
        hmm_lbl = "⚠️ MANIPULATION / SWEEP" if hmm_v == "MANIPULATION_SWEEP" else ("🚀 DIRECTIONAL EXPANSION" if hmm_v == "DIRECTIONAL_EXPANSION" else "⚪ ACCUMULATION")

        ws.write(r_idx, 70, f"%{ent_val:.1f}", cell_roe_green if ent_val <= 60 else (cell_roe_red if ent_val >= 88 else cell_center))
        ws.write(r_idx, 71, f"{hurst_v:.2f}", cell_roe_green if hurst_v >= 0.55 else (cell_roe_red if hurst_v < 0.45 else cell_center))
        ws.write(r_idx, 72, f"{ice_v:.2f}x", cell_roe_red if ice_v >= 3.5 else cell_center)
        ws.write(r_idx, 73, hmm_lbl, cell_left)

        # Bookmap Sipariş Akışı & Çapa (74)
        bm_seller = h.get('bookmap_seller_absorption', False)
        bm_buyer = h.get('bookmap_buyer_absorption', False)
        bm_anchor = h.get('is_anchor_wall', False)
        bm_dur = _safe_float(h.get('wall_duration_sec', 0.0))
        bm_str = "⚪ Normal Akış"
        if bm_buyer:
            bm_str = f"🌊 Alıcı Süngeri ({bm_dur:.0f}s)"
        elif bm_seller:
            bm_str = f"🌊 Satıcı Süngeri ({bm_dur:.0f}s)"
        elif bm_anchor:
            bm_str = f"🧱 Çapa Duvarı ({bm_dur:.0f}s)"
        ws.write(r_idx, 74, bm_str, cell_roe_green if (bm_buyer or bm_anchor) else (cell_roe_red if bm_seller else cell_center))

        # 5 Kurumsal Omurga Sütunları (75, 76, 77, 78, 79, 80)
        basis_v = _safe_float(h.get('spot_basis_bps', 0.0))
        wall_age = _safe_float(h.get('wall_age_sec', 0.0))
        spread_v = _safe_float(h.get('entry_spread_pct', 0.0))
        slip_v = _safe_float(h.get('entry_slippage_pct', 0.0))
        btc_v = _safe_float(h.get('btc_velocity_60s', 0.0))
        calc_risk = _safe_float(h.get('calculated_dollar_risk', 10.0))

        ws.write(r_idx, 75, f"{basis_v:+.1f} bps", cell_roe_green if basis_v <= -15 else (cell_roe_red if basis_v >= 25 else cell_center))
        ws.write(r_idx, 76, f"{wall_age:.1f}s", cell_roe_green if wall_age >= 45 else (cell_roe_red if wall_age < 15 else cell_center))
        ws.write(r_idx, 77, f"%{spread_v:.3f}", cell_roe_green if spread_v <= 0.08 else (cell_roe_red if spread_v >= 0.18 else cell_center))
        ws.write(r_idx, 78, f"%{slip_v:.3f}", cell_roe_green if slip_v <= 0.05 else (cell_roe_red if slip_v >= 0.10 else cell_center))
        ws.write(r_idx, 79, f"%{btc_v:+.2f}", cell_roe_green if btc_v >= 0 else cell_roe_red)
        ws.write(r_idx, 80, f"${calc_risk:.2f}", cell_currency_2d)

        # Blueprint Alpha Sütunları (81, 82, 83, 84, 85)
        stoikov_drift = _safe_float(h.get('stoikov_drift_bps', 0.0))
        vpin_sc = _safe_float(h.get('vpin_score', 0.30))
        vpin_tox = str(h.get('vpin_toxicity', 'LOW'))
        kyles_l = _safe_float(h.get('kyles_lambda_ratio', 1.0))
        gex_reg = str(h.get('deribit_gex_regime', 'NEUTRAL'))
        hwk_eta = _safe_float(h.get('hawkes_eta', 0.15))
        hwk_act = bool(h.get('is_avalanche_active', False))

        ws.write(r_idx, 81, f"{stoikov_drift:+.1f} bps", cell_roe_green if stoikov_drift > 0 else (cell_roe_red if stoikov_drift < 0 else cell_center))
        ws.write(r_idx, 82, f"{vpin_sc:.2f} ({vpin_tox})", cell_center)
        ws.write(r_idx, 83, f"{kyles_l:.2f}x", cell_center)
        ws.write(r_idx, 84, gex_reg, cell_center)
        ws.write(r_idx, 85, f"η={hwk_eta:.2f}" + (" (ÇIĞ)" if hwk_act else ""), cell_roe_red if hwk_act else cell_center)

        # 4 Gizli Kuant Silahı Sütunları (86, 87, 88, 89)
        cvd_div = str(h.get('cvd_divergence', '⚪ UYUMLU_AKIS (Normal)'))
        rvol_tag = str(h.get('rvol_tag', '⚪ SEANS_NORMU'))
        rvol_z = _safe_float(h.get('rvol_z_score', 0.0))
        macro_dom = str(h.get('macro_dominance_bias', '⚪ DENGELİ_MAKRO_AKIS'))
        planned_r_val = _safe_float(h.get('planned_r', 2.0))

        ws.write(r_idx, 86, cvd_div, cell_center)
        ws.write(r_idx, 87, f"{rvol_tag} ({rvol_z:+.1f}σ)", cell_center)
        ws.write(r_idx, 88, macro_dom, cell_center)
        ws.write(r_idx, 89, f"{planned_r_val:.2f}x", cell_roe_green if planned_r_val >= 1.8 else cell_roe_red)

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
        r = str(h.get('reason', 'Diğer Sinyaller'))
        s_id = str(h.get('setup_id', ''))
        if 'SETUP_11' in s_id or 'Resistance Flip' in r or 'Direnç Retest' in r:
            cat = 'Bearish Direnç Retest (Setup 11)'
        elif 'SETUP_12' in s_id or 'Destek Çöküşü' in r or 'Support Breakdown' in r:
            cat = 'Destek Çöküşü / Breakdown (Setup 12)'
        elif 'SETUP_13' in s_id or 'S3 Direnc' in r:
            cat = 'S3 Direnç Retesti / Ayı Devamı (Setup 13)'
        elif 'nPOC' in r:
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
        strat_stats[cat]['mfe_sum'] += _safe_float(h.get('max_mfe_roe', h.get('mfe_roe', max(0.0, _safe_float(h.get('roe_pct', 0.0))))))
        strat_stats[cat]['mae_sum'] += _safe_float(h.get('max_mae_roe', h.get('mae_roe', abs(min(0.0, _safe_float(h.get('roe_pct', 0.0)))))))
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
    # Tüm 100 Pariteyi Dahil Et (Baz DNA + Canlı İstatistikler)
    from collections import OrderedDict
    all_symbols_map = OrderedDict()
    try:
        from config import SYMBOLS
        for s in SYMBOLS:
            all_symbols_map[s] = s
    except Exception:
        pass

    if base_dna_map:
        for b_sym in base_dna_map.keys():
            # Format to BTC/USDT style if needed
            clean_display = b_sym if '/' in b_sym else (b_sym[:-4] + '/USDT' if b_sym.endswith('USDT') else b_sym)
            if clean_display not in all_symbols_map:
                all_symbols_map[clean_display] = clean_display

    for p_sym in pair_stats.keys():
        if p_sym not in all_symbols_map:
            all_symbols_map[p_sym] = p_sym

    dna_rows_data = []
    for sym_display in all_symbols_map.keys():
        clean_s = str(sym_display).replace('/', '').replace(':USDT', '').upper()
        # pair_stats eşleşmesi kontrolü
        st = pair_stats.get(sym_display)
        if not st:
            for pk, pv in pair_stats.items():
                if str(pk).replace('/', '').replace(':USDT', '').upper() == clean_s:
                    st = pv
                    break

        has_live = st is not None and st.get('trades', 0) >= 3
        base_info = base_dna_map.get(clean_s, {}) if base_dna_map else {}

        if has_live:
            t_cnt = st['trades']
            wr = (st['wins'] / t_cnt * 100) if t_cnt > 0 else 0.0
            pnl = st['net_pnl']
            fake_rate = (st['fakeouts'] / t_cnt * 100) if t_cnt > 0 else 0.0
            atr = st['atr_sum'] / t_cnt if t_cnt > 0 else 1.2
            persona_tag = _get_coin_persona(sym_display, st) + " [Canlı]"
        else:
            t_cnt = base_info.get('trades_count', 0)
            wr = float(base_info.get('win_rate', 50.0))
            pnl = float(base_info.get('net_pnl', 0.0))
            fake_rate = float(base_info.get('fakeout_rate', 25.0))
            atr = 1.45
            persona_tag = base_info.get('persona_name', "⚪ Standart / Dengeli") + " [Baz DNA]"

        if "Altın" in persona_tag or "GOLD" in persona_tag:
            rec_mod = "👑 Kırılım + Pusu Öncelikli (x1.3 Marjin)"
        elif "Tuzakçı" in persona_tag or "WHIPSAW" in persona_tag:
            rec_mod = "🛡️ Kırılım Kilitli 🔒 | Yalnızca S3/R3/nPOC Sekmesi (x0.5 Marjin)"
        elif "Süper" in persona_tag or "SUPER" in persona_tag:
            rec_mod = "🚀 Agresif Trend Takipçisi (x1.4 Marjin)"
        elif "Scalp" in persona_tag or "SCALP" in persona_tag:
            rec_mod = "⚡ Hızlı Scalp & Erken TP (x1.1 Marjin)"
        elif "Durgun" in persona_tag or "STAGNANT" in persona_tag:
            rec_mod = "⏳ Düşük Marjin & Erken Çürüme (x0.7 Marjin)"
        else:
            rec_mod = "⚪ Dengeli Kırılım + Pusu (x1.0 Marjin)"

        dna_rows_data.append({
            'sym': sym_display,
            'persona': persona_tag,
            'trades': t_cnt,
            'wr': wr,
            'pnl': pnl,
            'atr': atr,
            'fake_rate': fake_rate,
            'rec_mod': rec_mod
        })

    dna_rows_data.sort(key=lambda x: x['pnl'], reverse=True)

    for item in dna_rows_data:
        ws7.set_row(dna_row, 20)
        c_wr = item['wr']
        ws7.write(dna_row, 1, item['sym'], cell_left)
        ws7.write(dna_row, 2, item['persona'], cell_left)
        ws7.write(dna_row, 3, item['trades'], cell_center)
        ws7.write(dna_row, 4, f"%{c_wr:.1f}", cell_roe_green if c_wr >= 50 else cell_roe_red)
        ws7.write(dna_row, 5, item['pnl'], cell_green if item['pnl'] >= 0 else cell_red)
        ws7.write(dna_row, 6, f"%{item['atr']:.2f}", cell_center)
        ws7.write(dna_row, 7, f"%{item['fake_rate']:.1f}", cell_center)
        ws7.write(dna_row, 8, item['rec_mod'], cell_left)
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
    fakeout_trades = [h for h in history_data if _safe_float(h.get('max_mfe_roe', h.get('mfe_roe', 0))) < 0.8 and _safe_float(h.get('net_pnl', 0)) < 0 and ('Stop' in str(h.get('close_reason', '')) or 'stop' in str(h.get('close_reason', '')))]

    for f in fakeout_trades[:60]:
        ws8.set_row(fake_row, 20)
        pnl_loss = _safe_float(f.get('net_pnl', 0))
        mfe_val = _safe_float(f.get('max_mfe_roe', f.get('mfe_roe', 0)))
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

    # ==================== SHEET 9: ⚡ FONLAMA & SQUEEZE RADARI ====================
    if funding_data and isinstance(funding_data, dict) and len(funding_data) > 0:
        ws9 = workbook.add_worksheet('⚡ FONLAMA & SQUEEZE')
        ws9.set_column('A:A', 3)
        ws9.set_column('B:B', 15)
        ws9.set_column('C:C', 18)
        ws9.set_column('D:D', 18)
        ws9.set_column('E:E', 28)
        ws9.set_column('F:F', 26)
        ws9.set_column('G:G', 16)

        ws9.merge_range('B2:G2', '⚡ CANLI FONLAMA ORANLARI & SQUEEZE RADARI (100 PARİTE)', title_fmt)
        ws9.set_row(1, 28)

        fund_headers = [
            ('Parite', 15),
            ('8s Fonlama Oranı (%)', 18),
            ('Mark Fiyatı ($)', 18),
            ('Squeeze Riski & Durumu', 28),
            ('İzin Verilen Pozisyon Yönü', 26),
            ('Sıradaki Fonlama', 16)
        ]

        ws9.set_row(4, 24)
        for col_idx, (f_title, width) in enumerate(fund_headers, start=1):
            ws9.write(4, col_idx, f_title, th_gold_fmt)

        f_row = 5
        sorted_funds = sorted(funding_data.values(), key=lambda x: x.get('rate_pct', 0.0))
        for f_item in sorted_funds:
            ws9.set_row(f_row, 20)
            f_sym = f_item.get('symbol', '-')
            r_pct = f_item.get('rate_pct', 0.0)
            mark_p = f_item.get('mark_price', 0.0)
            sq_status = f_item.get('squeeze_status', 'BALANCED')
            dir_all = f_item.get('direction_allowed', 'ALL')
            cd_str = f_item.get('next_funding_countdown', '--:--')

            if 'SHORT_SQUEEZE' in sq_status:
                sq_label = "🚨 SHORT SQUEEZE TEHLİKESİ"
                sq_fmt = cell_red
            elif 'LONG_OVERHEATED' in sq_status:
                sq_label = "🔥 AŞIRI LONG ISINMASI"
                sq_fmt = cell_roe_red
            elif 'MODERATE_NEGATIVE' in sq_status:
                sq_label = "⚠️ Negatif Eğim (Short Ağır)"
                sq_fmt = cell_center
            elif 'MODERATE_POSITIVE' in sq_status:
                sq_label = "📈 Pozitif Eğim (Long Ağır)"
                sq_fmt = cell_center
            else:
                sq_label = "⚖️ Dengeli / Nötr"
                sq_fmt = cell_center

            if dir_all == 'LONG_ONLY':
                dir_label = "🟢 YALNIZCA LONG (Korumalı)"
            elif dir_all == 'SHORT_ONLY':
                dir_label = "🔴 YALNIZCA SHORT (Korumalı)"
            else:
                dir_label = "⚪ SERBEST (İki Yön)"

            ws9.write(f_row, 1, f_sym, cell_left)
            ws9.write(f_row, 2, f"%{r_pct:+.4f}", cell_roe_red if r_pct < -0.05 else (cell_roe_green if r_pct > 0.05 else cell_center))
            ws9.write(f_row, 3, mark_p, cell_currency)
            ws9.write(f_row, 4, sq_label, sq_fmt)
            ws9.write(f_row, 5, dir_label, cell_left)
            ws9.write(f_row, 6, cd_str, cell_center)
            f_row += 1

    
    workbook.close()
    
    with open(tmp_path, 'rb') as f:
        file_bytes = f.read()
    try:
        os.remove(tmp_path)
    except Exception:
        pass

    return io.BytesIO(file_bytes)


def create_shadow_dna_excel_report(
    shadow_summary: dict,
    coin_dna: list,
    shadow_history: list,
    shield_leaderboard: list
) -> io.BytesIO:
    """
    Valkyrie Gölge İşlem & Coin DNA Otonom Kalibrasyon Masası için 4 Sayfalı Profesyonel Excel Raporu:
    1. 📊 GÖLGE KARNESİ & SEI (Kalkan Verimlilik Endeksi, Hero vs Spoiler Karnesi)
    2. 🧬 COIN DNA & KALİBRASYON (100 Parite Canlı Fitil Esnekliği ve Parametre Önerileri)
    3. 👻 DETAYLI GÖLGE DEFTERİ (Her sanal işlemin mikroskobik tick/mum takibi)
    4. ⚙️ KOD KALİBRASYON MASASI (Kopyalanabilir Python parametre sözlüğü)
    """
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
        tmp_path = tmp.name
        
    workbook = xlsxwriter.Workbook(tmp_path)

    # ==================== ORTAK FORMATLAR ====================
    title_fmt = workbook.add_format({
        'bold': True, 'font_size': 14, 'font_name': 'Segoe UI',
        'font_color': '#FFFFFF', 'bg_color': '#0F172A',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#334155'
    })
    subtitle_fmt = workbook.add_format({
        'italic': True, 'font_size': 9, 'font_name': 'Segoe UI',
        'font_color': '#94A3B8', 'bg_color': '#0F172A',
        'align': 'center', 'valign': 'vcenter'
    })

    kpi_lbl = workbook.add_format({
        'bold': True, 'font_size': 8.5, 'font_name': 'Segoe UI',
        'font_color': '#475569', 'bg_color': '#F8FAFC',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#CBD5E1'
    })
    kpi_val_green = workbook.add_format({
        'bold': True, 'font_size': 13, 'font_name': 'Segoe UI',
        'font_color': '#059669', 'bg_color': '#ECFDF5',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#A7F3D0',
        'num_format': '$#,##0.00'
    })
    kpi_val_red = workbook.add_format({
        'bold': True, 'font_size': 13, 'font_name': 'Segoe UI',
        'font_color': '#DC2626', 'bg_color': '#FEF2F2',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#FECACA',
        'num_format': '$#,##0.00'
    })
    kpi_val_blue = workbook.add_format({
        'bold': True, 'font_size': 13, 'font_name': 'Segoe UI',
        'font_color': '#2563EB', 'bg_color': '#EFF6FF',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#BFDBFE'
    })
    kpi_val_gold = workbook.add_format({
        'bold': True, 'font_size': 13, 'font_name': 'Segoe UI',
        'font_color': '#D97706', 'bg_color': '#FFFBEB',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#FDE68A'
    })

    th_navy = workbook.add_format({
        'bold': True, 'font_size': 9, 'font_name': 'Segoe UI',
        'font_color': '#FFFFFF', 'bg_color': '#1E293B',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#475569',
        'text_wrap': True
    })
    th_gold = workbook.add_format({
        'bold': True, 'font_size': 9, 'font_name': 'Segoe UI',
        'font_color': '#FFFFFF', 'bg_color': '#854D0E',
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#CA8A04',
        'text_wrap': True
    })

    cell_c = workbook.add_format({'font_size': 9, 'font_name': 'Segoe UI', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#E2E8F0'})
    cell_l = workbook.add_format({'font_size': 9, 'font_name': 'Segoe UI', 'align': 'left', 'valign': 'vcenter', 'border': 1, 'border_color': '#E2E8F0'})
    cell_r = workbook.add_format({'font_size': 9, 'font_name': 'Segoe UI', 'align': 'right', 'valign': 'vcenter', 'border': 1, 'border_color': '#E2E8F0'})
    cell_curr = workbook.add_format({'font_size': 9, 'font_name': 'Segoe UI', 'align': 'right', 'valign': 'vcenter', 'border': 1, 'border_color': '#E2E8F0', 'num_format': '$#,##0.00'})
    cell_curr4 = workbook.add_format({'font_size': 9, 'font_name': 'Segoe UI', 'align': 'right', 'valign': 'vcenter', 'border': 1, 'border_color': '#E2E8F0', 'num_format': '$#,##0.0000'})
    cell_pnl_green = workbook.add_format({'bold': True, 'font_size': 9, 'font_name': 'Segoe UI', 'align': 'right', 'valign': 'vcenter', 'border': 1, 'border_color': '#E2E8F0', 'font_color': '#059669', 'bg_color': '#F0FDF4', 'num_format': '+$#,##0.00'})
    cell_pnl_red = workbook.add_format({'bold': True, 'font_size': 9, 'font_name': 'Segoe UI', 'align': 'right', 'valign': 'vcenter', 'border': 1, 'border_color': '#E2E8F0', 'font_color': '#DC2626', 'bg_color': '#FEF2F2', 'num_format': '-$#,##0.00'})
    cell_badge_hero = workbook.add_format({'bold': True, 'font_size': 8.5, 'font_name': 'Segoe UI', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#86EFAC', 'font_color': '#166534', 'bg_color': '#DCFCE7'})
    cell_badge_spoiler = workbook.add_format({'bold': True, 'font_size': 8.5, 'font_name': 'Segoe UI', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#FCA5A5', 'font_color': '#991B1B', 'bg_color': '#FEE2E2'})
    cell_badge_neutral = workbook.add_format({'font_size': 8.5, 'font_name': 'Segoe UI', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#CBD5E1', 'font_color': '#475569', 'bg_color': '#F1F5F9'})
    cell_badge_gold = workbook.add_format({'bold': True, 'font_size': 8.5, 'font_name': 'Segoe UI', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#FDE68A', 'font_color': '#92400E', 'bg_color': '#FEF3C7'})
    cell_code = workbook.add_format({'font_size': 9, 'font_name': 'Consolas', 'align': 'left', 'valign': 'vcenter', 'border': 1, 'border_color': '#CBD5E1', 'bg_color': '#F8FAFC'})

    # ══════════════════════════════════════════════════════════════════════
    # SAYFA 1: 📊 GÖLGE KARNESİ & SEI
    # ══════════════════════════════════════════════════════════════════════
    ws1 = workbook.add_worksheet('📊 GÖLGE KARNESİ & SEI')
    ws1.set_tab_color('#38BDF8')
    ws1.set_column('A:A', 3)
    ws1.set_column('B:B', 32)
    ws1.set_column('C:C', 14)
    ws1.set_column('D:D', 14)
    ws1.set_column('E:E', 14)
    ws1.set_column('F:F', 16)
    ws1.set_column('G:G', 16)
    ws1.set_column('H:H', 16)
    ws1.set_column('I:I', 14)
    ws1.set_column('J:J', 24)

    ws1.merge_range('B2:J2', 'VALKYRIE OTONOM GÖLGE İŞLEM & KALKAN VERİMLİLİK RAPORU (SEI AUDIT)', title_fmt)
    ws1.merge_range('B3:J3', 'Canlı Piyasa Reddedilen Sinyallerin Karşı-Olgusal (Counterfactual) Adli Analizi ve Kalkan Verimlilik Endeksi', subtitle_fmt)
    ws1.set_row(1, 28)
    ws1.set_row(2, 18)

    # KPI Kartları
    ws1.set_row(4, 18)
    ws1.set_row(5, 26)
    ws1.write('B5', 'TOPLAM GÖLGE İŞLEM', kpi_lbl)
    ws1.write('B6', f"{shadow_summary.get('total_shadow_trades', 0)} ({shadow_summary.get('active_shadow_trades', 0)} Aktif)", kpi_val_blue)

    ws1.merge_range('C5:D5', '🛡️ KURTARILAN ZARAR (HERO)', kpi_lbl)
    ws1.merge_range('C6:D6', shadow_summary.get('total_saved_loss_usd', 0.0), kpi_val_green)

    ws1.merge_range('E5:F5', '⚠️ KAÇAN FIRSAT KÂRI (SPOILER)', kpi_lbl)
    ws1.merge_range('E6:F6', shadow_summary.get('total_missed_profit_usd', 0.0), kpi_val_red)

    ws1.merge_range('G5:H5', '🎯 KALKAN VERİMLİLİĞİ (SEI)', kpi_lbl)
    ws1.merge_range('G6:H6', f"%{shadow_summary.get('shield_efficiency_index', 100.0):.1f}", kpi_val_gold)

    ws1.merge_range('I5:J5', '💎 NET KALKAN ALFASI ($)', kpi_lbl)
    net_a = shadow_summary.get('net_shield_alpha_usd', 0.0)
    ws1.merge_range('I6:J6', net_a, kpi_val_green if net_a >= 0 else kpi_val_red)

    # Kalkan Liderlik Tablosu
    ws1.set_row(7, 24)
    ws1.merge_range('B8:J8', '🛡️ GÜVENLİK KALKANLARI VE FRENLEYİCİ ENGEL KARNESİ (SHIELD AUDIT)', th_gold)
    
    headers_s1 = ['Kalkan / Filtre Adı', 'Toplam Engel', 'Kahraman (Hero)', 'Frenleyici (Spoiler)', 'Kurtarılan Zarar ($)', 'Kaçan Kâr ($)', 'Net Fayda ($)', 'SEI (%)', 'Kalkan Rolü']
    ws1.set_row(8, 22)
    for c_i, h_txt in enumerate(headers_s1, start=1):
        ws1.write(8, c_i, h_txt, th_navy)

    r_idx = 9
    for s_item in shield_leaderboard:
        ws1.set_row(r_idx, 20)
        s_name = s_item.get('shield_name', '-')
        tot_b = s_item.get('total_blocks', 0)
        h_cnt = s_item.get('hero_count', 0)
        sp_cnt = s_item.get('spoiler_count', 0)
        saved = s_item.get('saved_loss_usd', 0.0)
        missed = s_item.get('missed_profit_usd', 0.0)
        net_s = s_item.get('net_saved_usd', 0.0)
        sei = s_item.get('sei', 100.0)
        role = s_item.get('role', 'DENGELİ')

        ws1.write(r_idx, 1, s_name, cell_l)
        ws1.write(r_idx, 2, tot_b, cell_c)
        ws1.write(r_idx, 3, h_cnt, cell_c)
        ws1.write(r_idx, 4, sp_cnt, cell_c)
        ws1.write(r_idx, 5, saved, cell_curr)
        ws1.write(r_idx, 6, missed, cell_curr)
        ws1.write(r_idx, 7, net_s, cell_pnl_green if net_s >= 0 else cell_pnl_red)
        ws1.write(r_idx, 8, f"%{sei:.1f}", cell_c)
        
        badge_fmt = cell_badge_hero if 'KAHRAMAN' in role else (cell_badge_spoiler if 'FRENLEYİCİ' in role else cell_badge_neutral)
        ws1.write(r_idx, 9, role, badge_fmt)
        r_idx += 1

    # ══════════════════════════════════════════════════════════════════════
    # SAYFA 2: 🧬 COIN DNA & KALİBRASYON
    # ══════════════════════════════════════════════════════════════════════
    ws2 = workbook.add_worksheet('🧬 COIN DNA & KALİBRASYON')
    ws2.set_tab_color('#10B981')
    ws2.set_column('A:A', 3)
    ws2.set_column('B:B', 12)
    ws2.set_column('C:C', 14)
    ws2.set_column('D:D', 14)
    ws2.set_column('E:E', 14)
    ws2.set_column('F:F', 16)
    ws2.set_column('G:G', 16)
    ws2.set_column('H:H', 16)
    ws2.set_column('I:I', 14)
    ws2.set_column('J:J', 28)
    ws2.set_column('K:K', 16)
    ws2.set_column('L:L', 18)
    ws2.set_column('M:M', 36)
    ws2.set_column('N:N', 55)

    ws2.merge_range('B2:N2', '100 PARİTE CANLI PİYASA DNA\'SI VE OTONOM KALİBRASYON MASASI', title_fmt)
    ws2.merge_range('B3:N3', 'Parite Bazında Toplanan Gölge Veriler, Fitil Esnekliği, Kuant Teşhis ve Otonom Parametre Önerileri', subtitle_fmt)
    ws2.set_row(1, 28)
    ws2.set_row(2, 18)

    headers_s2 = [
        'Parite', 'Toplam Gölge', 'Aktif', 'Tamamlanan', 'Kahraman (Hero)', 'Frenleyici (Spoiler)',
        'Kurtarılan Zarar ($)', 'Kaçan Kâr ($)', 'Net Alfa ($)', 'SEI (%)', 'En Çok Engelleyen Kalkan',
        'Fitil Esnekliği (%)', 'Kalibrasyon Durumu', 'Otonom Kalibrasyon Önerisi', 'Adli Kalibrasyon Özeti'
    ]
    ws2.set_row(4, 24)
    for c_i, h_txt in enumerate(headers_s2, start=1):
        ws2.write(4, c_i, h_txt, th_navy)

    r2_idx = 5
    for c_item in coin_dna:
        ws2.set_row(r2_idx, 20)
        sym = c_item.get('symbol', '-')
        tot_s = c_item.get('total_shadows', 0)
        act_s = c_item.get('active_shadows', 0)
        cmp_s = c_item.get('completed_shadows', 0)
        h_cnt = c_item.get('hero_count', 0)
        sp_cnt = c_item.get('spoiler_count', 0)
        saved = c_item.get('saved_loss_usd', 0.0)
        missed = c_item.get('missed_profit_usd', 0.0)
        net_a = c_item.get('net_alpha_usd', 0.0)
        sei = c_item.get('sei', 100.0)
        top_s = c_item.get('top_shield', '-')
        wick = c_item.get('wick_elasticity', 12.0)
        rec_b = c_item.get('recommendation_badge', 'DENGELİ')
        rec_txt = c_item.get('recommendation', '-')
        narr_txt = c_item.get('forensic_narrative', '-')

        ws2.write(r2_idx, 1, sym, cell_c)
        ws2.write(r2_idx, 2, tot_s, cell_c)
        ws2.write(r2_idx, 3, act_s, cell_c)
        ws2.write(r2_idx, 4, cmp_s, cell_c)
        ws2.write(r2_idx, 5, h_cnt, cell_c)
        ws2.write(r2_idx, 6, sp_cnt, cell_c)
        ws2.write(r2_idx, 7, saved, cell_curr)
        ws2.write(r2_idx, 8, missed, cell_curr)
        ws2.write(r2_idx, 9, net_a, cell_pnl_green if net_a >= 0 else cell_pnl_red)
        ws2.write(r2_idx, 10, f"%{sei:.1f}", cell_c)
        ws2.write(r2_idx, 11, top_s, cell_l)
        ws2.write(r2_idx, 12, f"%{wick:.1f}", cell_c)

        badge_fmt = cell_badge_spoiler if 'GEVŞET' in rec_b else (cell_badge_hero if 'KORU' in rec_b else cell_badge_neutral)
        ws2.write(r2_idx, 13, rec_b, badge_fmt)
        ws2.write(r2_idx, 14, rec_txt, cell_l)
        ws2.write(r2_idx, 15, narr_txt, cell_l)
        r2_idx += 1

    # ══════════════════════════════════════════════════════════════════════
    # SAYFA 3: 👻 DETAYLI GÖLGE DEFTERİ
    # ══════════════════════════════════════════════════════════════════════
    ws3 = workbook.add_worksheet('👻 DETAYLI GÖLGE DEFTERİ')
    ws3.set_tab_color('#8B5CF6')
    ws3.set_column('A:A', 3)
    ws3.set_column('B:B', 18)  # ID
    ws3.set_column('C:C', 12)  # Parite
    ws3.set_column('D:D', 10)  # Yön
    ws3.set_column('E:E', 24)  # Setup
    ws3.set_column('F:F', 28)  # Kalkan
    ws3.set_column('G:G', 32)  # Ret Gerekçesi
    ws3.set_column('H:H', 48)  # Adli Teşhis & Neden-Sonuç Hikayesi
    ws3.set_column('I:I', 13)  # Giriş Fiyatı
    ws3.set_column('J:J', 13)  # Çıkış Fiyatı
    ws3.set_column('K:K', 13)  # Stop
    ws3.set_column('L:L', 13)  # TP1
    ws3.set_column('M:M', 13)  # TP2
    ws3.set_column('N:N', 12)  # MFE %
    ws3.set_column('O:O', 12)  # MAE %
    ws3.set_column('P:P', 12)  # ROE %
    ws3.set_column('Q:Q', 14)  # PnL $
    ws3.set_column('R:R', 22)  # Verdict Teşhis
    ws3.set_column('S:S', 14)  # ATR %
    ws3.set_column('T:T', 14)  # Hacim Çarpanı
    ws3.set_column('U:U', 14)  # CVD Alıcı %
    ws3.set_column('V:V', 14)  # RS Skoru
    ws3.set_column('W:W', 12)  # Süre dk
    ws3.set_column('X:X', 18)  # Giriş Zamanı
    ws3.set_column('Y:Y', 18)  # Çıkış Zamanı

    ws3.merge_range('B2:Y2', 'MİKROSKOBİK GÖLGE İŞLEM DEFTERİ (CANLI PİYASA SİMÜLASYONU)', title_fmt)
    ws3.merge_range('B3:Y3', 'Canlı Mumlarla Takip Edilerek TP1, TP2 veya Stop Akıbeti Belirlenmiş Tüm Sanal Pozisyonlar ve Adli Otopsi Raporu', subtitle_fmt)
    ws3.set_row(1, 28)
    ws3.set_row(2, 18)

    headers_s3 = [
        'Gölge ID', 'Parite', 'Yön', 'Giriş Stratejisi', 'Engelleyen Kalkan', 'Ret Gerekçesi',
        'Adli Teşhis & Neden-Sonuç Hikayesi',
        'Giriş ($)', 'Çıkış ($)', 'Stop ($)', 'Planlanan TP1 ($)', 'Planlanan TP2 ($)',
        'Zirve MFE (%)', 'Maks MAE (%)', 'ROE (%)', 'Sanal Net PnL ($)', 'Kalkan Teşhisi',
        'Volatilite ATR (%)', 'Hacim Çarpanı', 'CVD Alıcı (%)', 'RS Skoru',
        'Süre (Dk)', 'Giriş Zamanı', 'Çıkış Zamanı'
    ]
    ws3.set_row(4, 24)
    for c_i, h_txt in enumerate(headers_s3, start=1):
        ws3.write(4, c_i, h_txt, th_navy)

    r3_idx = 5
    for t_item in shadow_history:
        ws3.set_row(r3_idx, 20)
        s_id = t_item.get('id', '-')
        sym = t_item.get('symbol', '-')
        side = t_item.get('side', '-')
        setup = t_item.get('setup', '-')
        shield = t_item.get('shield', '-')
        reason = t_item.get('reason', '-')
        narr = t_item.get('narrative', reason)
        entry_p = t_item.get('entry_price', 0.0)
        exit_p = t_item.get('exit_price', 0.0)
        sl_p = t_item.get('sl_price', 0.0)
        tp1_p = t_item.get('tp1_price', 0.0)
        tp2_p = t_item.get('tp2_price', 0.0)
        mfe = t_item.get('max_mfe_pct', 0.0)
        mae = t_item.get('max_mae_pct', 0.0)
        roe = t_item.get('virtual_pnl_pct', 0.0)
        pnl = t_item.get('virtual_pnl_usd', 0.0)
        verd = t_item.get('verdict_badge', t_item.get('verdict', '-'))
        telem = t_item.get('telemetry', {}) or {}
        atr_str = f"%{telem.get('atr_pct', 0.0):.2f}" if 'atr_pct' in telem else '-'
        vol_str = f"{telem.get('vol_mult', 1.0):.2f}x" if 'vol_mult' in telem else '-'
        cvd_str = f"%{telem.get('cvd_taker_pct', 50.0):.1f}" if 'cvd_taker_pct' in telem else '-'
        rs_str = f"{telem.get('rs_score', 0.0):+.2f}" if 'rs_score' in telem else '-'
        dur = t_item.get('duration_mins', 0.0)
        in_t = t_item.get('entry_time', '-')
        out_t = t_item.get('exit_time', '-')

        ws3.write(r3_idx, 1, s_id, cell_c)
        ws3.write(r3_idx, 2, sym, cell_c)
        ws3.write(r3_idx, 3, side, cell_badge_hero if side == 'LONG' else cell_badge_spoiler)
        ws3.write(r3_idx, 4, setup, cell_l)
        ws3.write(r3_idx, 5, shield, cell_l)
        ws3.write(r3_idx, 6, reason, cell_l)
        ws3.write(r3_idx, 7, narr, cell_l)
        ws3.write(r3_idx, 8, entry_p, cell_curr4 if entry_p < 1.0 else cell_curr)
        ws3.write(r3_idx, 9, exit_p, cell_curr4 if exit_p < 1.0 else cell_curr)
        ws3.write(r3_idx, 10, sl_p, cell_curr4 if sl_p < 1.0 else cell_curr)
        ws3.write(r3_idx, 11, tp1_p, cell_curr4 if tp1_p < 1.0 else cell_curr)
        ws3.write(r3_idx, 12, tp2_p, cell_curr4 if tp2_p < 1.0 else cell_curr)
        ws3.write(r3_idx, 13, f"+%{mfe:.2f}", cell_c)
        ws3.write(r3_idx, 14, f"-%{mae:.2f}", cell_c)
        ws3.write(r3_idx, 15, f"%{roe:+.2f}", cell_pnl_green if roe >= 0 else cell_pnl_red)
        ws3.write(r3_idx, 16, pnl, cell_pnl_green if pnl >= 0 else cell_pnl_red)

        badge_fmt = cell_badge_hero if 'KAHRAMAN' in verd else (cell_badge_spoiler if 'FRENLEYİCİ' in verd else cell_badge_neutral)
        ws3.write(r3_idx, 17, verd, badge_fmt)
        ws3.write(r3_idx, 18, atr_str, cell_c)
        ws3.write(r3_idx, 19, vol_str, cell_c)
        ws3.write(r3_idx, 20, cvd_str, cell_c)
        ws3.write(r3_idx, 21, rs_str, cell_c)
        ws3.write(r3_idx, 22, dur, cell_c)
        ws3.write(r3_idx, 23, in_t, cell_c)
        ws3.write(r3_idx, 24, out_t, cell_c)
        r3_idx += 1

    # ══════════════════════════════════════════════════════════════════════
    # SAYFA 4: ⚙️ KOD KALİBRASYON MASASI
    # ══════════════════════════════════════════════════════════════════════
    ws4 = workbook.add_worksheet('⚙️ KOD KALİBRASYON MASASI')
    ws4.set_tab_color('#F59E0B')
    ws4.set_column('A:A', 3)
    ws4.set_column('B:B', 90)

    ws4.write('B2', 'OTONOM KOD KALİBRASYON VE PARAMETRE LİSTESİ', title_fmt)
    ws4.write('B3', 'Canlı Verilerle Tespit Edilen Optimum Eşik Değerleri (Doğrudan Koda Entegre Edilebilir Format)', subtitle_fmt)
    ws4.set_row(1, 28)
    ws4.set_row(2, 18)

    ws4.write('B5', '# 🧬 VALKYRIE OTONOM KALİBRE EDİLMİŞ COIN PARAMETRELERİ (CANLI PİYASA DNA)', th_gold)
    
    code_lines = [
        "# Aşağıdaki sözlük, gölge takip motorunun canlı piyasa analizlerine göre otomatik üretilmiştir.",
        "# Bu parametreler kopyalanıp strategy.py veya config.py içerisine doğrudan eklenebilir:",
        "",
        "CALIBRATED_COIN_DNA = {"
    ]

    for c in coin_dna:
        sym = c.get('symbol')
        wick = c.get('wick_elasticity', 12.0)
        sei = c.get('sei', 100.0)
        rec_b = c.get('recommendation_badge', 'DENGELİ')
        code_lines.append(f'    "{sym}": {{')
        code_lines.append(f'        "wick_threshold_pct": {wick:.1f},  # Canlı ortalama fitil esnekliği')
        code_lines.append(f'        "sei_efficiency_score": {sei:.1f},')
        code_lines.append(f'        "status": "{rec_b}",')
        code_lines.append(f'        "top_shield": "{c.get("top_shield", "")}",')
        code_lines.append(f'    }},')

    code_lines.append("}")
    code_lines.append("")
    code_lines.append(f"# Rapor Oluşturulma Zamanı: {datetime.now(timezone(timedelta(hours=3))).strftime('%Y-%m-%d %H:%M:%S')} (TSİ)")

    for line_i, c_line in enumerate(code_lines, start=6):
        ws4.set_row(line_i, 18)
        ws4.write(line_i, 1, c_line, cell_code)

    workbook.close()
    
    with open(tmp_path, 'rb') as f:
        file_bytes = f.read()
    try:
        os.remove(tmp_path)
    except Exception:
        pass

    return io.BytesIO(file_bytes)


