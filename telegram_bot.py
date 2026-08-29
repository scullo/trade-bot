import aiohttp
import asyncio
import io
from datetime import datetime, timezone, timedelta
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from chart_generator import generate_trade_chart_image

class TelegramNotifier:
    def __init__(self, token=TELEGRAM_BOT_TOKEN, chat_id=TELEGRAM_CHAT_ID):
        self.token = token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        self.photo_url = f"https://api.telegram.org/bot{self.token}/sendPhoto"

    async def send_message(self, text: str):
        if not self.token or not self.chat_id:
            return
        try:
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML"
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, json=payload, timeout=8) as resp:
                    if resp.status != 200:
                        print(f">> Telegram Bildirim Hatasi (HTTP {resp.status})")
        except Exception as e:
            print(f">> Telegram gonderim hatasi: {e}")

    async def send_photo(self, photo_data, caption: str):
        if not self.token or not self.chat_id:
            return
        if not photo_data:
            await self.send_message(caption)
            return

        try:
            if isinstance(photo_data, bytes):
                buf = io.BytesIO(photo_data)
            elif isinstance(photo_data, io.BytesIO):
                buf = photo_data
                buf.seek(0)
            else:
                await self.send_message(caption)
                return

            data = aiohttp.FormData()
            data.add_field('chat_id', str(self.chat_id))
            data.add_field('caption', caption[:1024])
            data.add_field('parse_mode', 'HTML')
            data.add_field('photo', buf, filename='trade_chart.png', content_type='image/png')

            async with aiohttp.ClientSession() as session:
                async with session.post(self.photo_url, data=data, timeout=15) as resp:
                    if resp.status != 200:
                        err_text = await resp.text()
                        print(f">> Telegram sendPhoto Hatasi (HTTP {resp.status}): {err_text}, metin olarak iletiliyor...")
                        await self.send_message(caption)
        except Exception as e:
            print(f">> Telegram sendPhoto istisnasi: {e}, metin gonderiliyor...")
            await self.send_message(caption)

    async def notify_position_opened(self, pos: dict, free_balance: float = None, df_5m = None, levels: dict = None):
        side_emoji = "🟢 <b>LONG</b>" if pos["side"] == "LONG" else "🔴 <b>SHORT</b>"
        clean_sym = pos["symbol"].replace("/USDT", "")
        
        msg = f"""⚡ <b>YENİ POZİSYON AÇILDI</b> ⚡
━━━━━━━━━━━━━━━━━━━━━━━━
Parite: <b>#{clean_sym}/USDT</b>
Yön & Kaldıraç: {side_emoji} <b>({pos['leverage']}x)</b>
Giriş Fiyatı: <code>${pos['entry_price']:.6f}</code>
Marjin: <b>{pos.get('margin_usdt', pos.get('margin', 10.0)):.2f} USDT</b> (Hacim: {pos['position_value']:.2f} USDT)
━━━━━━━━━━━━━━━━━━━━━━━━
🛑 <b>Stop:</b> <code>${pos.get('soft_stop', pos.get('hard_stop', 0.0)):.6f}</code>
🎯 <b>TP1 Hedefi:</b> <code>${pos.get('tp1', 0.0):.6f}</code>
"""
        if pos.get("tp2"):
            msg += f"🚀 <b>TP2 Hedefi:</b> <code>${pos['tp2']:.6f}</code>\n"

        if free_balance is not None:
            msg += f"💼 <b>Kalan Serbest Kasa:</b> <b>{free_balance:.2f} USDT</b>\n"

        msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━
📌 <b>Setup Nedeni:</b> <i>{pos['reason']}</i>
⏰ <b>Zaman:</b> <code>{pos['entry_time']}</code>"""

        # Grafik Fotograf Olustur
        chart_buf = None
        if df_5m is not None and not df_5m.empty:
            try:
                chart_buf = generate_trade_chart_image(
                    symbol=pos["symbol"],
                    df_5m=df_5m,
                    levels=levels or {},
                    side=pos["side"],
                    entry_price=pos["entry_price"],
                    soft_stop=pos.get('soft_stop', pos.get('hard_stop', 0.0)),
                    tp1=pos.get('tp1', 0.0),
                    tp2=pos.get('tp2', 0.0),
                    trade_type=pos.get('trade_type', 'SCALP'),
                    reason=pos['reason']
                )
            except Exception as e:
                print(f"[TELEGRAM] Grafik olusturulamadi: {e}")

        if chart_buf:
            await self.send_photo(chart_buf, msg)
        else:
            await self.send_message(msg)

    async def notify_position_closed(self, record: dict, is_manual: bool = False, df_5m = None, levels: dict = None):
        net_pnl = record["net_pnl"]
        roe = record["roe_pct"]
        is_win = net_pnl >= 0
        if is_manual:
            pnl_emoji = "🚨 <b>MANUEL MÜDAHALE — POZİSYON KAPATILDI</b> 🚨"
        else:
            pnl_emoji = "🎉 <b>KÂRLI KAPANIŞ</b> 🟢" if is_win else "🛑 <b>ZARAR KES (STOP)</b> 🔴"
        clean_sym = record["symbol"].replace("/USDT", "")

        manual_tag = "\n⚠️ <i>Kullanıcı Dashboard üzerinden acil müdahale ile pozisyonu kapattı.</i>\n" if is_manual else ""
        bal_after = record.get('balance_after', '')
        bal_str = f"💼 <b>Güncel Toplam Kasa:</b> <b>{bal_after:.2f} USDT</b>\n" if bal_after != '' else ""

        msg = f"""{pnl_emoji}
━━━━━━━━━━━━━━━━━━━━━━━━
Parite: <b>#{clean_sym}/USDT</b> ({record['side']} {record['leverage']}x)
Giriş: <code>${record['entry_price']:.6f}</code> ➔ Çıkış: <code>${record['exit_price']:.6f}</code>
━━━━━━━━━━━━━━━━━━━━━━━━
💰 <b>Net Kâr / Zarar:</b> <b>{net_pnl:+.4f} USDT ({roe:+.2f}%)</b>
💵 <b>Brüt Kâr:</b> {record.get('gross_pnl', net_pnl):+.4f} USDT
💸 <b>Borsa Komisyonu:</b> {record['fees']:.4f} USDT
━━━━━━━━━━━━━━━━━━━━━━━━
{bal_str}📌 <b>Kapanış Nedeni:</b> <i>{record['close_reason']}</i>{manual_tag}
⏰ <b>Çıkış Zamanı:</b> <code>{record['exit_time']}</code>"""

        chart_buf = None
        if df_5m is not None and not df_5m.empty:
            try:
                entry_ts = record.get("entry_timestamp")
                if not entry_ts and record.get("entry_time"):
                    try:
                        entry_ts = datetime.strptime(record["entry_time"], "%Y-%m-%d %H:%M:%S").timestamp()
                    except Exception:
                        entry_ts = None

                chart_buf = generate_trade_chart_image(
                    symbol=record["symbol"],
                    df_5m=df_5m,
                    levels=levels or {},
                    side=record["side"],
                    entry_price=record["entry_price"],
                    exit_price=record["exit_price"],
                    entry_timestamp=entry_ts,
                    reason=record["close_reason"],
                    is_closed=True,
                    net_pnl=net_pnl,
                    roe_pct=roe
                )
            except Exception as e:
                print(f"[TELEGRAM] Kapanis grafigi olusturulamadi: {e}")

        if chart_buf:
            await self.send_photo(chart_buf, msg)
        else:
            await self.send_message(msg)

    @staticmethod
    def _compute_period_metrics(history: list):
        """Gecmis islemlerden Gunluk, Haftalik ve Aylik PnL ve istatistikleri hesaplar."""
        now = datetime.now(timezone(timedelta(hours=3)))
        today_date = now.date()
        week_cutoff = now - timedelta(days=7)
        month_cutoff = now - timedelta(days=30)

        today_pnl = 0.0
        today_trades = []
        weekly_pnl = 0.0
        monthly_pnl = 0.0

        for h in (history or []):
            t_str = h.get('exit_time') or h.get('entry_time')
            if not t_str:
                continue
            try:
                t = datetime.strptime(t_str, "%Y-%m-%d %H:%M:%S")
            except Exception:
                try:
                    t = datetime.fromisoformat(t_str.replace('Z', ''))
                except Exception:
                    continue

            pnl = float(h.get('net_pnl', 0.0))
            if t.date() == today_date:
                today_pnl += pnl
                today_trades.append(h)
            if t >= week_cutoff:
                weekly_pnl += pnl
            if t >= month_cutoff:
                monthly_pnl += pnl

        return {
            'today_pnl': today_pnl,
            'today_trades': today_trades,
            'weekly_pnl': weekly_pnl,
            'monthly_pnl': monthly_pnl
        }

    async def send_hourly_report(self, balance: float, initial_balance: float, open_positions: dict, history: list, mode: str = "DEMO"):
        """Her saat basi otomatik portfoy, donemsel kazanc ve acik pozisyon raporu gonderir."""
        if not self.token or not self.chat_id:
            return

        total_pnl = balance - initial_balance
        growth_pct = (total_pnl / initial_balance) * 100.0 if initial_balance > 0 else 0.0

        # Donemsel Kazanc Metrikleri (Gunluk, Haftalik, Aylik)
        period = self._compute_period_metrics(history)
        today_pnl = period['today_pnl']
        weekly_pnl = period['weekly_pnl']
        monthly_pnl = period['monthly_pnl']

        # Win Rate & Komisyon
        wins = [h for h in history if h.get('net_pnl', 0.0) >= 0]
        losses = [h for h in history if h.get('net_pnl', 0.0) < 0]
        total_trades = len(history)
        win_rate = (len(wins) / total_trades * 100.0) if total_trades > 0 else 0.0
        total_fees = sum(h.get('fees', 0.0) for h in history)

        mode_badge = "🔴 <b>GERÇEK HESAP (Binance Live)</b>" if mode == "LIVE" else "🟡 <b>DEMO MODU (Paper Trading)</b>"

        # Acik Pozisyon Metni
        pos_lines = []
        if open_positions:
            for sym, pos in open_positions.items():
                clean = sym.replace('/USDT', '')
                pos_lines.append(f"• <b>#{clean}</b> ({pos['side']} {pos['leverage']}x) — Giriş: <code>${pos['entry_price']:.4f}</code>")
            pos_str = "\n".join(pos_lines)
        else:
            pos_str = "• <i>Şu an aktif açık pozisyon bulunmuyor. (100 Parite Taranıyor)</i>"

        now_str = datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M:%S")

        msg = f"""📊 <b>VALKYRIE QUANT — SAATLİK KASA & PORTFÖY RAPORU</b> 🕒
━━━━━━━━━━━━━━━━━━━━━━━━
💰 <b>Güncel Toplam Kasa:</b> <b>${balance:,.2f} USDT</b>
📈 <b>Toplam Net Kâr:</b> <b>{total_pnl:+.2f} USDT ({growth_pct:+.2f}%)</b>
🎯 <b>Ticaret Modu:</b> {mode_badge}
━━━━━━━━━━━━━━━━━━━━━━━━
📅 <b>DÖNEMSEL KAZANÇ PERFORMANSI:</b>
• 💵 <b>Günlük Kazanç (Bugün):</b> <b>{today_pnl:+.2f} USDT</b>
• 📆 <b>Haftalık Kazanç (7 Gün):</b> <b>{weekly_pnl:+.2f} USDT</b>
• 🗓️ <b>Aylık Kazanç (30 Gün):</b> <b>{monthly_pnl:+.2f} USDT</b>
━━━━━━━━━━━━━━━━━━━━━━━━
⚡ <b>AÇIK POZİSYONLAR ({len(open_positions)} / 3):</b>
{pos_str}
━━━━━━━━━━━━━━━━━━━━━━━━
📜 <b>İŞLEM GEÇMİŞİ ÖZETİ:</b>
• Toplam Tamamlanan: <b>{total_trades} İşlem</b>
• Kazanma Oranı (Win Rate): <b>%{win_rate:.1f}</b> ({len(wins)} Kâr / {len(losses)} Zarar)
• Ödenen Toplam Komisyon: <b>${total_fees:.4f} USDT</b>
━━━━━━━━━━━━━━━━━━━━━━━━
⏰ <b>Rapor Zamanı:</b> <code>{now_str}</code>"""

        await self.send_message(msg)

    async def send_midnight_summary(self, balance: float, initial_balance: float, open_positions: dict, history: list, mode: str = "DEMO"):
        """Her gece saat 00:00'da gunluk kapanis ve genel performans ozetini gonderir."""
        if not self.token or not self.chat_id:
            return

        total_pnl = balance - initial_balance
        growth_pct = (total_pnl / initial_balance) * 100.0 if initial_balance > 0 else 0.0

        period = self._compute_period_metrics(history)
        today_pnl = period['today_pnl']
        today_trades = period['today_trades']
        weekly_pnl = period['weekly_pnl']
        monthly_pnl = period['monthly_pnl']

        today_wins = [h for h in today_trades if h.get('net_pnl', 0.0) >= 0]
        today_losses = [h for h in today_trades if h.get('net_pnl', 0.0) < 0]
        today_winrate = (len(today_wins) / len(today_trades) * 100.0) if today_trades else 0.0
        today_fees = sum(h.get('fees', 0.0) for h in today_trades)

        best_trade = max(today_trades, key=lambda x: x.get('net_pnl', 0.0)) if today_trades else None
        if best_trade:
            best_str = f"<b>#{best_trade['symbol'].replace('/USDT','')}</b> ({best_trade['net_pnl']:+.2f} USDT)"
        else:
            best_str = "<i>Bugün tamamlanan işlem yok</i>"

        mode_badge = "🔴 <b>GERÇEK HESAP (Binance Live)</b>" if mode == "LIVE" else "🟡 <b>DEMO MODU (Paper Trading)</b>"

        pos_lines = []
        if open_positions:
            for sym, pos in open_positions.items():
                clean = sym.replace('/USDT', '')
                pos_lines.append(f"• <b>#{clean}</b> ({pos['side']} {pos['leverage']}x) — Giriş: <code>${pos['entry_price']:.4f}</code>")
            pos_str = "\n".join(pos_lines)
        else:
            pos_str = "• <i>Açık pozisyon devretmedi. 100 paritede gece pusu devam ediyor.</i>"

        now_str = datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d 00:00:00")

        msg = f"""🌕 <b>VALKYRIE QUANT — GÜNLÜK KAPANIŞ & PERFORMANS RAPORU (00:00)</b> 🌙
━━━━━━━━━━━━━━━━━━━━━━━━
💰 <b>Günün Kapanış Kasası:</b> <b>${balance:,.2f} USDT</b>
🎯 <b>Ticaret Modu:</b> {mode_badge}
━━━━━━━━━━━━━━━━━━━━━━━━
📊 <b>GÜNÜN İŞLEM & KÂR/ZARAR ÖZETİ:</b>
• 💵 <b>Bugünkü Net Kazanç:</b> <b>{today_pnl:+.2f} USDT</b>
• 🎯 <b>Günlük Win Rate:</b> <b>%{today_winrate:.1f}</b> ({len(today_wins)} Kâr / {len(today_losses)} Zarar)
• 🏆 <b>Günün En Başarılı İşlemi:</b> {best_str}
• 🔢 <b>Bugün Kapanan İşlem:</b> <b>{len(today_trades)} Adet</b>
• 💸 <b>Günün Ödenen Komisyonu:</b> <b>${today_fees:.4f} USDT</b>
━━━━━━━━━━━━━━━━━━━━━━━━
📅 <b>KÜMÜLATİF DÖNEMSEL PERFORMANS:</b>
• 📆 <b>Haftalık Kazanç (Son 7 Gün):</b> <b>{weekly_pnl:+.2f} USDT</b>
• 🗓️ <b>Aylık Kazanç (Son 30 Gün):</b> <b>{monthly_pnl:+.2f} USDT</b>
• 📈 <b>Başlangıçtan Beri Toplam Kâr:</b> <b>{total_pnl:+.2f} USDT ({growth_pct:+.2f}%)</b>
━━━━━━━━━━━━━━━━━━━━━━━━
⚡ <b>DEVREDEN AÇIK POZİSYONLAR ({len(open_positions)} / 3):</b>
{pos_str}
━━━━━━━━━━━━━━━━━━━━━━━━
⏰ <b>Kapanış Zamanı:</b> <code>{now_str}</code>"""

        await self.send_message(msg)

    async def start_hourly_scheduler(self, trader_manager, initial_balance=100.0):
        """Arka planda her saat basinda (:00) saatlik rapor, her gece 00:00'da ise ozel gunluk kapanis ozeti gonderir."""
        if not self.token or not self.chat_id:
            return

        # Baslangic onay mesaji gonder
        try:
            boot_msg = f"""🚀 <b>VALKYRIE QUANT DESK — AKTİF EDİLDİ</b>
━━━━━━━━━━━━━━━━━━━━━━━━
💰 <b>Başlangıç Kasası:</b> <code>${trader_manager.balance:,.2f} USDT</code>
📊 <b>Taranan Parite:</b> <code>100 / 100 Canlı Akış</code>
⏰ <b>Başlangıç Zamanı:</b> <code>{datetime.now(timezone(timedelta(hours=3))).strftime('%Y-%m-%d %H:%M:%S')}</code>
━━━━━━━━━━━━━━━━━━━━━━━━
📌 <i>5 Dakikalık mum kapanışları ve saatlik raporlama döngüsü başlatıldı.</i>"""
            await self.send_message(boot_msg)
        except Exception as e:
            print(f"[TELEGRAM BOOT MSG ERROR]: {e}")

        while True:
            try:
                now = datetime.now(timezone(timedelta(hours=3)))
                # Bir sonraki tam saat basina (:00:02) kalan saniyeyi hesapla
                seconds_to_wait = (60 - now.minute - 1) * 60 + (60 - now.second) + 2
                if seconds_to_wait <= 2:
                    seconds_to_wait = 3600

                await asyncio.sleep(seconds_to_wait)

                # Turkiye saati (UTC+3) hesabi
                current_hour = (datetime.utcnow().hour + 3) % 24

                # Eger saat 00:00 ise ozel Gece Kapanis Raporu gonder, aksi takdirde normal Saatlik Rapor gonder
                if current_hour == 0:
                    await self.send_midnight_summary(
                        balance=trader_manager.balance,
                        initial_balance=initial_balance,
                        open_positions=trader_manager.open_positions,
                        history=trader_manager.history,
                        mode=getattr(trader_manager, 'mode', 'DEMO')
                    )
                else:
                    await self.send_hourly_report(
                        balance=trader_manager.balance,
                        initial_balance=initial_balance,
                        open_positions=trader_manager.open_positions,
                        history=trader_manager.history,
                        mode=getattr(trader_manager, 'mode', 'DEMO')
                    )
            except Exception as e:
                print(f"[HOURLY/MIDNIGHT REPORT SCHEDULER HATA]: {e}")
                await asyncio.sleep(30)
