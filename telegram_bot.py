from aegis_sentinel import ValkyrieAegisSentinel
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
        self.sentinel = ValkyrieAegisSentinel()

    async def send_message(self, text: str, chat_id: str = None):
        target_chat = chat_id or self.chat_id
        if not self.token or not target_chat:
            return
        try:
            payload = {
                "chat_id": str(target_chat),
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
        
        atr_val = pos.get('atr_pct', 1.2)
        vol_val = pos.get('volume_surge', 1.0)
        bal_line = f"💼 <b>Serbest Kasa:</b> <code>${free_balance:.2f} USDT</code>\n" if free_balance is not None else ""
        tp2_line = f"🚀 <b>TP2 Final:</b> <code>${pos['tp2']:.6f}</code>\n" if pos.get("tp2") else ""

        msg = f"""💎 ━━━━━━━━━━━━━━━━━━━━━━ 💎
⚡ <b>YENİ POZİSYON AÇILDI</b> ⚡
━━━━━━━━━━━━━━━━━━━━━━━━
Parite: <b>#{clean_sym}/USDT</b> | {side_emoji} <b>({pos['leverage']}x)</b>
Giriş: <code>${pos['entry_price']:.6f}</code> | Marjin: <b>${pos.get('margin_usdt', pos.get('margin', 100.0)):.1f}</b>
━━━━━━━━━━━━━━━━━━━━━━━━
🛑 <b>Stop:</b> <code>${pos.get('soft_stop', pos.get('hard_stop', 0.0)):.6f}</code>
🎯 <b>TP1 Hedefi:</b> <code>${pos.get('tp1', 0.0):.6f}</code>
{tp2_line}🛡️ <b>Kâr Zırhı:</b> <code>+%7 ROE veya 90dk (%50 Kilit)</code>
📊 <b>ATR / Hacim:</b> <code>%{atr_val:.2f} | {vol_val:.2f}x</code>
{bal_line}━━━━━━━━━━━━━━━━━━━━━━━━
📌 <b>Setup:</b> <i>{pos['reason']}</i>
⏰ <b>Zaman:</b> <code>{pos['entry_time']}</code>
💎 ━━━━━━━━━━━━━━━━━━━━━━ 💎"""

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
        is_partial_tp1 = record.get("id", "").endswith("-TP1") or "Dinamik" in str(record.get("close_reason", "")) or "Zaman Kalkanı" in str(record.get("close_reason", ""))
        is_breakeven = "Breakeven" in str(record.get("close_reason", "")) or (record.get("is_half_closed") and not is_win)
        if is_manual:
            pnl_emoji = "🚨 <b>MANUEL MÜDAHALE — POZİSYON KAPATILDI</b> 🚨"
        elif is_partial_tp1:
            pnl_emoji = "🎯 <b>DİNAMİK KÂR KİLİTLENDİ (%50 NAKİT ALINDI)</b> 💎"
        elif is_breakeven:
            pnl_emoji = "🛡️ <b>BREAKEVEN KORUMASI İLE KAPATILDI (0 RİSK KORUMASI)</b> 🟢"
        else:
            pnl_emoji = "🎉 <b>KÂRLI KAPANIŞ (TAM HEDEF)</b> 🟢" if is_win else "🛑 <b>ZARAR KES (STOP)</b> 🔴"
        clean_sym = record["symbol"].replace("/USDT", "")

        manual_tag = "\n⚠️ <i>Kullanıcı Dashboard üzerinden acil müdahale ile pozisyonu kapattı.</i>\n" if is_manual else ""
        bal_after = record.get('balance_after', '')
        bal_str = f"💼 <b>Güncel Toplam Kasa:</b> <b>{bal_after:.2f} USDT</b>\n" if bal_after != '' else ""

        open_reason = record.get("reason", "Strateji Sinyali")
        close_reason = record.get("close_reason", "Hedef/Stop Kapanışı")
        partial_note = "\n🛡️ <b>Kalan %50:</b> <i>Breakeven ile 0 riskle koşuyor!</i>\n" if is_partial_tp1 else ("\nℹ️ <i>İlk %50 kârı daha önce kasaya kilitlenmişti; kalan kısım koruma stopuyla risksiz kapatıldı.</i>\n" if is_breakeven else "")
        msg = f"""💎 ━━━━━━━━━━━━━━━━━━━━━━ 💎
{pnl_emoji}
━━━━━━━━━━━━━━━━━━━━━━━━
Parite: <b>#{clean_sym}/USDT</b> ({record['side']} {record['leverage']}x)
Giriş: <code>${record['entry_price']:.6f}</code> ➔ Çıkış: <code>${record['exit_price']:.6f}</code>
━━━━━━━━━━━━━━━━━━━━━━━━
💰 <b>Net Kâr / Zarar:</b> <b>{net_pnl:+.4f} USDT ({roe:+.2f}%)</b>
💵 <b>Brüt:</b> {record.get('gross_pnl', net_pnl):+.4f} $ | 💸 <b>Komisyon:</b> {record['fees']:.4f} $
{bal_str}━━━━━━━━━━━━━━━━━━━━━━━━
📥 <b>Açılış Nedeni:</b> <i>{open_reason}</i>
📤 <b>Kapanış Nedeni:</b> <i>{close_reason}</i>{manual_tag}{partial_note}
⏰ <b>Çıkış Zamanı:</b> <code>{record['exit_time']}</code>
💎 ━━━━━━━━━━━━━━━━━━━━━━ 💎"""

        chart_buf = None
        archive_tag = ""
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
                
                # Otomatik Kritik Pozisyon Grafik Arşivleyicisi
                is_critical = abs(net_pnl) >= 2.0 or abs(roe) >= 5.0 or is_manual or "Stop" in str(close_reason) or "TP" in str(close_reason) or "Dinamik" in str(close_reason)
                if chart_buf and is_critical:
                    try:
                        os.makedirs("ANALİZ/KRİTİK_GRAFİKLER", exist_ok=True)
                        clean_dt = datetime.now().strftime("%Y%m%d_%H%M%S")
                        pnl_label = f"KÂR_{net_pnl:+.2f}USDT" if is_win else f"ZARAR_{net_pnl:+.2f}USDT"
                        fname = f"{clean_dt}_{clean_sym}_{record['side']}_{pnl_label}.png".replace("+", "plus_").replace("-", "minus_").replace("$", "")
                        fpath = os.path.join("ANALİZ/KRİTİK_GRAFİKLER", fname)
                        with open(fpath, "wb") as f_img:
                            f_img.write(chart_buf.getvalue())
                        archive_tag = f"\n📸 <b>Adli Analiz Grafiği Kaydedildi:</b> <code>ANALİZ/KRİTİK_GRAFİKLER/{fname}</code>\n"
                    except Exception as ex_arch:
                        print(f"[ARŞİVLEME HATA]: {ex_arch}")
            except Exception as e:
                print(f"[TELEGRAM] Kapanis grafigi olusturulamadi: {e}")

        if archive_tag:
            msg = msg.replace("💎 ━━━━━━━━━━━━━━━━━━━━━━ 💎\n⏰", f"{archive_tag}💎 ━━━━━━━━━━━━━━━━━━━━━━ 💎\n⏰")

        if chart_buf:
            await self.send_photo(chart_buf, msg)
        else:
            await self.send_message(msg)

    @staticmethod
    def _compute_period_metrics(history: list):
        """Gecmis islemlerden Gunluk, Haftalik ve Aylik PnL ve istatistikleri hesaplar."""
        now = datetime.now()
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
                t = datetime.strptime(str(t_str).split('.')[0], "%Y-%m-%d %H:%M:%S")
            except Exception:
                try:
                    t = datetime.fromisoformat(str(t_str).replace('Z', '').split('+')[0])
                except Exception:
                    continue

            if t.tzinfo is not None:
                t = t.replace(tzinfo=None)

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

    async def start_hourly_scheduler(self, trader_manager, initial_balance=100.0, market_data=None):
        """Arka planda her saat basinda (:00) 6-Katmanli Valkyrie Aegis Sentinel denetimi yapar ve Telegram VIP raporu iletir."""
        if not self.token or not self.chat_id:
            return

        # Baslangic onay mesaji gonder
        try:
            boot_msg = f"""🛡️ <b>VALKYRIE AEGIS SENTINEL — AKTİF EDİLDİ</b>
━━━━━━━━━━━━━━━━━━━━━━━━
💰 <b>Başlangıç Kasası:</b> <code>${trader_manager.balance:,.2f} USDT</code>
📊 <b>Takip Edilen:</b> <code>100 / 100 Parite (Canlı Akış)</code>
🔬 <b>Teşhis Motoru:</b> <code>TradingView & Binance Çapraz Doğrulama Aktif</code>
⏰ <b>Başlangıç Zamanı:</b> <code>{datetime.now(timezone(timedelta(hours=3))).strftime('%Y-%m-%d %H:%M:%S')} (TSİ)</code>
━━━━━━━━━━━━━━━━━━━━━━━━
📌 <i>Her saat başı otonom sağlık denetimi, oto-onarım ve VIP yönetici raporu gönderilecektir.</i>"""
            await self.send_message(boot_msg)
        except Exception as e:
            print(f"[TELEGRAM BOOT MSG ERROR]: {e}")

        while True:
            try:
                now = datetime.now(timezone(timedelta(hours=3)))
                seconds_to_wait = (60 - now.minute - 1) * 60 + (60 - now.second) + 2
                if seconds_to_wait <= 2:
                    seconds_to_wait = 3600

                await asyncio.sleep(seconds_to_wait)

                current_hour = (datetime.utcnow().hour + 3) % 24
                mode = getattr(trader_manager, 'mode', 'DEMO')

                # 6-Katmanli Valkyrie Aegis Sentinel Denetimini Calistir
                if market_data:
                    audit_res = await self.sentinel.run_full_sentinel_audit(market_data, trader_manager, mode=mode)
                    exec_report = self.sentinel.generate_executive_telegram_report(audit_res, trader_manager, initial_balance=initial_balance)
                    await self.send_message(exec_report)
                else:
                    await self.send_hourly_report(
                        balance=trader_manager.balance,
                        initial_balance=initial_balance,
                        open_positions=trader_manager.open_positions,
                        history=trader_manager.history,
                        mode=mode
                    )

                # Sabah 08:00 ve Gece 00:00'da Günlük Yönetici Brifingi Gönder
                if current_hour in [0, 8]:
                    await self.send_daily_executive_briefing(
                        balance=trader_manager.balance,
                        initial_balance=initial_balance,
                        open_positions=trader_manager.open_positions,
                        history=trader_manager.history,
                        market_data=market_data
                    )
            except Exception as e:
                print(f"[AEGIS SENTINEL SCHEDULER HATA]: {e}")
                await asyncio.sleep(30)

    async def send_daily_executive_briefing(self, balance: float, initial_balance: float, open_positions: dict, history: list, market_data=None):
        """08:00 ve 00:00 saatlerinde Günlük Valkyrie Quant Yönetici Brifingi gönderir."""
        if not self.token or not self.chat_id:
            return
        try:
            now = datetime.now(timezone(timedelta(hours=3)))
            date_str = now.strftime("%d.%m.%Y")
            period = self._compute_period_metrics(history)
            today_pnl = period['today_pnl']
            today_trades = period['today_trades']
            growth_pct = (today_pnl / initial_balance * 100.0) if initial_balance > 0 else 0.0

            today_wins = [h for h in today_trades if float(h.get('net_pnl', 0)) >= 0]
            today_losses = [h for h in today_trades if float(h.get('net_pnl', 0)) < 0]
            today_winrate = (len(today_wins) / len(today_trades) * 100.0) if today_trades else 0.0

            best_trade = max(today_trades, key=lambda x: float(x.get('net_pnl', 0))) if today_trades else None
            if best_trade and float(best_trade.get('net_pnl', 0)) > 0:
                best_str = f"<b>#{best_trade['symbol'].replace('/USDT','')}</b> (<code>+{float(best_trade['net_pnl']):.2f} USDT</code>)"
            else:
                best_str = "<i>Henüz kârlı kapanış yok</i>"

            # En iyi setup bul
            setup_pnl = {}
            for t in today_trades:
                st = str(t.get('reason', 'Genel')).split('(')[0].strip()
                pnl = float(t.get('net_pnl', 0))
                if st not in setup_pnl:
                    setup_pnl[st] = {'pnl': 0.0, 'wins': 0, 'total': 0}
                setup_pnl[st]['pnl'] += pnl
                setup_pnl[st]['total'] += 1
                if pnl >= 0:
                    setup_pnl[st]['wins'] += 1

            if setup_pnl:
                best_st_name = max(setup_pnl.items(), key=lambda x: x[1]['pnl'])[0]
                st_data = setup_pnl[best_st_name]
                st_wr = (st_data['wins'] / st_data['total'] * 100) if st_data['total'] > 0 else 0
                best_setup_str = f"<b>{best_st_name[:24]}</b> (%{st_wr:.0f} Win)"
            else:
                best_setup_str = "<b>Camarilla & nPOC</b> (%100 Pusu)"

            msg = f"""💎 ━━━━━━━━━━━━━━━━━━━━━━━━━ 💎
🌅 <b>GÜNLÜK VALKYRIE QUANT BRİFİNGİ ({date_str})</b> 🌅
━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 <b>Günlük Net Kâr:</b> <b>{today_pnl:+.2f} USDT ({growth_pct:+.2f}%)</b>
🎯 <b>Kazanma Oranı:</b> <b>%{today_winrate:.1f}</b> ({len(today_wins)} Win / {len(today_losses)} Loss)
👑 <b>Günün Yıldızı:</b> {best_str}
🚀 <b>En İyi Setup:</b> {best_setup_str}
💼 <b>Toplam Kasa:</b> <b>${balance:,.2f} USDT</b> ({len(open_positions)} Açık Pozisyon)
━━━━━━━━━━━━━━━━━━━━━━━━━━
💎 ━━━━━━━━━━━━━━━━━━━━━━━━━ 💎"""

            await self.send_message(msg)
        except Exception as e:
            print(f"[DAILY BRIEFING ERROR]: {e}")

    async def start_command_listener(self, trader_manager, market_data=None):
        """Telegram üzerinden gelen /kasa veya kasa mesajlarını dinler ve anında detaylı portföy yanıtı döner."""
        if not self.token:
            return
        
        offset = 0
        poll_url = f"https://api.telegram.org/bot{self.token}/getUpdates"
        print(">> [TELEGRAM ASİSTAN] Şimşek Hızlı /kasa dinleyicisi devrede.")

        while True:
            try:
                params = {"timeout": 1}
                if offset > 0:
                    params["offset"] = offset

                async with aiohttp.ClientSession() as session:
                    async with session.get(poll_url, params=params, timeout=aiohttp.ClientTimeout(total=6)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            updates = data.get("result", [])
                            for u in updates:
                                offset = u["update_id"] + 1
                                msg_obj = u.get("message") or u.get("channel_post") or u.get("edited_message") or {}
                                raw_text = str(msg_obj.get("text", "")).strip()
                                text = raw_text.lower()
                                chat = msg_obj.get("chat", {})
                                sender_chat_id = str(chat.get("id", "")) or str(self.chat_id)

                                if not text:
                                    continue

                                print(f">> [TELEGRAM ASİSTAN KOMUT ALINDI]: '{raw_text}' (Chat ID: {sender_chat_id})")

                                is_kasa_cmd = any(w in text for w in ["kasa", "durum", "bakiye", "start", "help", "rapor", "pnl", "portfoy"])
                                if is_kasa_cmd:
                                    bal = getattr(trader_manager, 'balance', 100000.0)
                                    open_p = getattr(trader_manager, 'open_positions', {})
                                    hist = getattr(trader_manager, 'history', [])
                                    
                                    total_unrealized = 0.0
                                    top_movers = []
                                    prices = getattr(market_data, 'current_prices', {}) if market_data else {}
                                    
                                    for sym, pos in open_p.items():
                                        try:
                                            entry_p = float(pos.get('entry_price', 0.0))
                                            cur_p = float(prices.get(sym, entry_p))
                                            side = str(pos.get('side', 'LONG'))
                                            lev = float(pos.get('leverage', 5))
                                            margin = float(pos.get('margin_usdt', pos.get('margin', 100.0)))
                                            
                                            if entry_p > 0 and cur_p > 0:
                                                diff = (cur_p - entry_p)/entry_p if side == 'LONG' else (entry_p - cur_p)/entry_p
                                                roe = diff * lev * 100.0
                                                pnl = margin * (roe / 100.0)
                                                total_unrealized += pnl
                                                top_movers.append((sym, side, roe, pnl))
                                        except Exception as e:
                                            pass

                                    top_movers.sort(key=lambda x: x[2], reverse=True)
                                    top_str_list = []
                                    for sym, side, roe, pnl in top_movers[:5]:
                                        clean_s = sym.replace('/USDT', '')
                                        s_emoji = "🟢" if roe >= 0 else "🔴"
                                        top_str_list.append(f"• {s_emoji} <b>#{clean_s}</b> ({side}): <code>%{roe:+5.2f} ROE (${pnl:+5.2f})</code>")
                                    
                                    top_str = "\n".join(top_str_list) if top_str_list else "• <i>Açık pozisyon yok</i>"
                                    
                                    period = self._compute_period_metrics(hist)
                                    today_pnl = period['today_pnl']
                                    now_str = datetime.now(timezone(timedelta(hours=3))).strftime("%H:%M:%S")

                                    reply = f"""💎 ━━━━━━━━━━━━━━━━━━━━━━━━━ 💎
💼 <b>VALKYRIE QUANT — ANLIK KASA RAPORU ({now_str})</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 <b>Toplam Kasa Bakiyesi:</b> <b>${bal:,.2f} USDT</b>
📊 <b>Açık Pozisyon Sayısı:</b> <b>{len(open_p)} Adet</b>
⚡ <b>Anlık Canlı Kâr (Unrealized):</b> <b>{total_unrealized:+.2f} USDT</b>
💵 <b>Bugün Gerçekleşen Kâr:</b> <b>{today_pnl:+.2f} USDT</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 <b>ÖNE ÇIKAN AÇIK POZİSYONLAR:</b>
{top_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━
💎 ━━━━━━━━━━━━━━━━━━━━━━━━━ 💎"""
                                    await self.send_message(reply, chat_id=sender_chat_id)
                                    print(f">> [TELEGRAM ASİSTAN ANINDA YANITLANDI] -> {sender_chat_id}")
            except Exception as e:
                print(f"[TELEGRAM LISTENER ERROR]: {e}")
                await asyncio.sleep(2)
            await asyncio.sleep(0.5)
