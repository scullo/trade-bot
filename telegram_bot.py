import html
import re
from aegis_sentinel import ValkyrieAegisSentinel
import os
import aiohttp
import asyncio
import io
import hashlib
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
                        err_text = await resp.text()
                        print(f">> Telegram Bildirim Hatasi (HTTP {resp.status}): {err_text}")
                        # HTML parse hatası durumunda HTML etiketlerini temizleyip düz metin olarak güvenli iletim
                        if "can't parse entities" in err_text.lower() or "bad request" in err_text.lower():
                            plain_text = re.sub(r'<[^>]+>', '', text)
                            payload["text"] = plain_text
                            payload.pop("parse_mode", None)
                            async with session.post(self.api_url, json=payload, timeout=8) as fb_resp:
                                if fb_resp.status == 200:
                                    print(">> Telegram Bildirimi Düz Metin (Plain Text) Fallback ile başarıyla iletildi.")
        except Exception as e:
            print(f">> Telegram gonderim hatasi: {e}")

    async def delete_webhook(self, drop_pending_updates: bool = False) -> bool:
        """Telegram Webhook'unu temizler. Webhook varken getUpdates 409 Conflict hatası verir."""
        if not self.token:
            return False
        url = f"https://api.telegram.org/bot{self.token}/deleteWebhook"
        try:
            payload = {"drop_pending_updates": bool(drop_pending_updates)}
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("ok"):
                            print(">> [TELEGRAM] Webhook basariyla kaldirildi (getUpdates aktif).")
                            return True
                    err_txt = await resp.text()
                    print(f">> [TELEGRAM WEBHOOK DELETE ERROR] (HTTP {resp.status}): {err_txt}")
                    return False
        except Exception as e:
            print(f">> [TELEGRAM WEBHOOK DELETE EXCEPTION]: {e}")
            return False

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

            # Telegram fotoğraf açıklama (caption) limiti 1024 karakterdir.
            # Caption 1000 karakterden uzun ise güvenli şekilde kısaltarak daima TEK ve kompakt mesaj olarak gönder
            safe_caption = caption
            if len(safe_caption) > 1000:
                safe_caption = safe_caption[:990] + "\n..."

            data = aiohttp.FormData()
            data.add_field('chat_id', str(self.chat_id))
            data.add_field('caption', safe_caption)
            data.add_field('parse_mode', 'HTML')
            data.add_field('photo', buf, filename='trade_chart.png', content_type='image/png')

            async with aiohttp.ClientSession() as session:
                async with session.post(self.photo_url, data=data, timeout=15) as resp:
                    if resp.status != 200:
                        err_text = await resp.text()
                        print(f">> Telegram sendPhoto Hatasi (HTTP {resp.status}): {err_text}, metin olarak iletiliyor...")
                        await self.send_message(safe_caption)
        except Exception as e:
            print(f">> Telegram sendPhoto istisnasi: {e}, metin gonderiliyor...")
            await self.send_message(caption)

    async def send_document(self, buf, filename: str, caption: str = ""):
        if not self.token or not self.chat_id:
            return
        doc_url = f"https://api.telegram.org/bot{self.token}/sendDocument"
        try:
            data = aiohttp.FormData()
            data.add_field('chat_id', str(self.chat_id))
            data.add_field('caption', caption[:1024])
            data.add_field('parse_mode', 'HTML')
            data.add_field('document', buf, filename=filename, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

            async with aiohttp.ClientSession() as session:
                async with session.post(doc_url, data=data, timeout=30) as resp:
                    if resp.status != 200:
                        err_text = await resp.text()
                        print(f">> Telegram sendDocument Hatasi (HTTP {resp.status}): {err_text}")
        except Exception as e:
            print(f">> Telegram sendDocument istisnasi: {e}")

    @staticmethod
    def _clean_signal_title(raw_reason: str) -> str:
        """Teknik ve karmaşık sinyal metnini sade, kompakt ve şık hale getirir."""
        if not raw_reason:
            return "Teknik Seviye Sinyali"
        s = str(raw_reason)
        # Köşeli parantezli karmaşık metrikleri temizle: [💥 ...] [🛡️ ...]
        s = re.sub(r'\[.*?\]', '', s).strip()
        # Hedef parantezlerini temizle: (İlk Hedef ...)
        s = re.sub(r'\(İlk Hedef.*?\)', '', s, flags=re.IGNORECASE).strip()
        # Emojileri ve özel sembolleri temizle
        s = re.sub(r'[💥🛡️🎯🔬📌⚡🕹️🔴🟢💎🚀🧠💵🛑★]', '', s).strip()
        s = re.sub(r'\s+', ' ', s).strip()
        return html.escape(s[:48] if s else "Teknik Seviye Sinyali", quote=False)

    @staticmethod
    def _fmt_price(p: float) -> str:
        """Fiyatı büyüklüğüne göre en net ve şık formatta döndürür."""
        if p is None or p == 0:
            return "$0.00"
        p = float(p)
        abs_p = abs(p)
        if abs_p >= 1000:
            return f"${p:,.2f}"
        elif abs_p >= 1:
            return f"${p:.4f}"
        elif abs_p >= 0.01:
            return f"${p:.5f}"
        elif abs_p >= 0.0001:
            return f"${p:.6f}"
        else:
            return f"${p:.8f}"

    async def notify_position_opened(self, pos: dict, free_balance: float = None, df_5m = None, levels: dict = None):
        clean_sym = pos["symbol"].replace("/USDT", "")
        side = pos.get("side", "LONG")
        lev = pos.get("leverage", 5)
        entry_p = float(pos.get("entry_price", 0.0))
        margin = float(pos.get("margin_usdt", pos.get("margin", 100.0)))
        stop_p = float(pos.get("hard_stop", pos.get("soft_stop", 0.0)))
        tp1_p = float(pos.get("tp1", 0.0))
        tp2_p = float(pos.get("tp2", 0.0)) if pos.get("tp2") else None

        # Yüzde mesafeleri
        stop_pct = abs((stop_p - entry_p) / entry_p * 100.0) if (entry_p > 0 and stop_p > 0) else 0.0
        tp1_pct = abs((tp1_p - entry_p) / entry_p * 100.0) if (entry_p > 0 and tp1_p > 0) else 0.0

        if side == "LONG":
            header = "🟢🟢🟢 <b>LONG POZİSYON AÇILDI</b> 🟢🟢🟢"
            side_tag = "🟢 <b>LONG</b>"
        else:
            header = "🔴🔴🔴 <b>SHORT POZİSYON AÇILDI</b> 🔴🔴🔴"
            side_tag = "🔴 <b>SHORT</b>"

        tp2_str = ""
        if tp2_p and tp2_p > 0:
            tp2_pct = abs((tp2_p - entry_p) / entry_p * 100.0) if entry_p > 0 else 0.0
            tp2_str = f"\n🚀 <b>TP2:</b>  <code>{self._fmt_price(tp2_p)}</code> <i>(+%{tp2_pct:.2f})</i>"

        clean_sig = self._clean_signal_title(pos.get("reason", ""))
        bal_str = f"<code>${free_balance:,.2f} USDT</code>" if free_balance is not None else "<code>Aktif</code>"
        
        t_raw = str(pos.get('entry_time', ''))
        t_disp = t_raw.split()[-1] if ' ' in t_raw else t_raw

        msg = f"""{header}
🪙 <b>#{clean_sym}/USDT</b> │ {side_tag} <b>({lev}x)</b>
━━━━━━━━━━━━━━━━━━━━
💵 <b>Giriş:</b> <code>{self._fmt_price(entry_p)}</code> │ <b>Marjin:</b> <code>${margin:.1f}</code>
🛑 <b>Stop:</b> <code>{self._fmt_price(stop_p)}</code> <i>(-%{stop_pct:.2f})</i>
🎯 <b>TP1:</b>  <code>{self._fmt_price(tp1_p)}</code> <i>(+%{tp1_pct:.2f})</i>{tp2_str}
────────────────────
⚡ <b>Sinyal:</b> <i>{clean_sig}</i>
💼 <b>Kasa:</b> {bal_str} │ ⏰ <code>{t_disp}</code>"""

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
                    soft_stop=pos.get('hard_stop', pos.get('soft_stop', 0.0)),
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

    async def notify_be_lock(self, symbol: str, side: str, entry_price: float, be_price: float, cur_profit_pct: float, leverage: int = 5):
        """Chandelier anlık tick erken Breakeven kâr kilidi tetiklendiğinde Telegram bildirimi iletir."""
        if not self.token or not self.chat_id:
            return
        clean_sym = symbol.replace("/USDT", "")
        roe_pct = cur_profit_pct * float(leverage)
        msg = f"""🛡️🛡️🛡️ <b>BREAKEVEN KÂR KİLİDİ AKTİF</b> 🛡️🛡️🛡️
🪙 <b>#{clean_sym}/USDT</b> │ <b>{side} ({leverage}x)</b>
━━━━━━━━━━━━━━━━━━━━
💵 <b>Giriş:</b> <code>{self._fmt_price(entry_price)}</code>
🔒 <b>Kilitli Stop:</b> <code>{self._fmt_price(be_price)}</code>
📈 <b>Görülen Kâr:</b> <code>+%{cur_profit_pct:.2f} (+%{roe_pct:.2f} ROE)</code>
────────────────────
🛡️ <i>Sermaye Zırhı Devrede: Pozisyon artık sıfır risk ile koşuyor!</i>"""
        await self.send_message(msg)

    async def notify_position_closed(self, record: dict, is_manual: bool = False, df_5m = None, levels: dict = None):
        net_pnl = float(record.get("net_pnl", 0.0))
        roe = float(record.get("roe_pct", 0.0))
        is_win = net_pnl > 0
        clean_sym = record.get("symbol", "").replace("/USDT", "")
        side = record.get("side", "LONG")
        lev = record.get("leverage", 5)
        side_tag = "🟢 LONG" if side == "LONG" else "🔴 SHORT"
        entry_p = float(record.get('entry_price', 0.0))
        exit_p = float(record.get('exit_price', 0.0))

        close_reason_raw = str(record.get("close_reason", ""))
        is_stop = "Stop" in close_reason_raw or "Zarar" in close_reason_raw or net_pnl < -0.20
        is_partial_tp1 = (record.get("id", "").endswith("-TP1") or "Dinamik Kâr" in close_reason_raw or "TP1" in close_reason_raw) and not is_stop
        is_breakeven = ("Breakeven" in close_reason_raw or (record.get("is_half_closed") and abs(net_pnl) < 0.8)) and not is_partial_tp1

        if is_manual:
            header = "🚨🚨🚨 <b>MANUEL KAPANIŞ</b> 🚨🚨🚨"
            pnl_line = f"🕹️ <b>NET PnL:</b> <b>{net_pnl:+.2f} USDT ({roe:+.2f}% ROE)</b>"
            reason_text = "Operatör Müdahalesi"
        elif is_partial_tp1:
            header = "🟢🟢🟢 <b>DİNAMİK KÂR KİLİTLENDİ (%50)</b> 🟢🟢🟢"
            pnl_line = f"💰 <b>NET KÂR:</b> <b>+{abs(net_pnl):.2f} USDT (+%{abs(roe):.2f} ROE)</b> 🟢"
            reason_text = "TP1 Alındı (Kalan %50 Breakeven ile koşuyor)"
        elif is_win and not is_breakeven:
            header = "🟢🟢🟢 <b>KÂRLI TAM KAPANIŞ</b> 🚀🚀🚀"
            pnl_line = f"🚀 <b>NET KÂR:</b> <b>+{abs(net_pnl):.2f} USDT (+%{abs(roe):.2f} ROE)</b> 🟢"
            reason_text = "Zirve TP2 Hedefine Ulaşıldı"
        elif is_breakeven:
            header = "🛡️🛡️🛡️ <b>BREAKEVEN KORUMASI (0 RİSK)</b> 🛡️🛡️🛡️"
            pnl_line = f"🛡️ <b>NET SONUÇ:</b> <b>{net_pnl:+.2f} USDT (%{roe:+.2f} ROE)</b> ⚪"
            reason_text = "Fiyat Girişe Döndü (Komisyon zırhı korudu)"
        else:
            header = "🔴🔴🔴 <b>STOP KORUMASI DEVREDE</b> 🔴🔴🔴"
            pnl_line = f"⚠️ <b>NET ZARAR:</b> <b>-{abs(net_pnl):.2f} USDT (-%{abs(roe):.2f} ROE)</b> 🔴"
            reason_text = "Dinamik Stop Tetiklendi (Sermaye korundu)"

        bal_after = record.get('balance_after', '')
        try:
            bal_str = f"<code>${float(bal_after):,.2f} USDT</code>" if bal_after != '' else "<code>Güncellendi</code>"
        except Exception:
            bal_str = "<code>Güncellendi</code>"

        t_raw = str(record.get('exit_time', ''))
        t_disp = t_raw.split()[-1] if ' ' in t_raw else t_raw

        msg = f"""{header}
🪙 <b>#{clean_sym}/USDT</b> │ {side_tag} <b>({lev}x)</b>
━━━━━━━━━━━━━━━━━━━━
💵 <code>{self._fmt_price(entry_p)}</code> ➔ <code>{self._fmt_price(exit_p)}</code>
{pnl_line}
─────────────────────
🎯 <b>Neden:</b> <i>{reason_text}</i>
💼 <b>Kasa:</b> {bal_str} │ ⏰ <code>{t_disp}</code>"""

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
                    side=record.get("side", "LONG"),
                    entry_price=record.get("entry_price"),
                    exit_price=record.get("exit_price"),
                    entry_timestamp=entry_ts,
                    reason=record.get("close_reason", ""),
                    is_closed=True,
                    net_pnl=net_pnl,
                    roe_pct=roe
                )

                # Otomatik Kritik Pozisyon Grafik Arşivleyicisi (Sessizce diske kaydeder, mesaja yol eklemez)
                is_critical = abs(net_pnl) >= 2.0 or abs(roe) >= 5.0 or is_manual or "Stop" in str(close_reason_raw) or "TP" in str(close_reason_raw) or "Dinamik" in str(close_reason_raw)
                if chart_buf and is_critical:
                    try:
                        os.makedirs("ANALİZ/KRİTİK_GRAFİKLER", exist_ok=True)
                        clean_dt = datetime.now().strftime("%Y%m%d_%H%M%S")
                        pnl_label = f"KÂR_{net_pnl:+.2f}USDT" if is_win else f"ZARAR_{net_pnl:+.2f}USDT"
                        fname = f"{clean_dt}_{clean_sym}_{record.get('side', '')}_{pnl_label}.png".replace("+", "plus_").replace("-", "minus_").replace("$", "")
                        fpath = os.path.join("ANALİZ/KRİTİK_GRAFİKLER", fname)
                        with open(fpath, "wb") as f_img:
                            f_img.write(chart_buf.getvalue())
                    except Exception as ex_arch:
                        print(f"[ARŞİVLEME HATA]: {ex_arch}")
            except Exception as e:
                print(f"[TELEGRAM] Kapanis grafigi olusturulamadi: {e}")

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

        # Baslangic onay mesaji gonder (Son 30 dakika icinde gonderilmisse spam yapma)
        last_boot_file = ".last_boot_sentinel"
        should_notify = True
        now_ts = time.time()
        if os.path.exists(last_boot_file):
            try:
                with open(last_boot_file, "r") as f:
                    last_ts = float(f.read().strip())
                    if now_ts - last_ts < 1800:  # 30 dakika spam kalkani
                        should_notify = False
            except Exception:
                pass

        if should_notify:
            try:
                with open(last_boot_file, "w") as f:
                    f.write(str(now_ts))
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

                current_hour = datetime.now(timezone(timedelta(hours=3))).hour
                mode = getattr(trader_manager, 'mode', 'DEMO')

                # 1) Excel raporu olustur ve Telegram uzerinden gonder (Sifir yer kaplar, %100 bulut yedek)
                try:
                    from excel_exporter import create_styled_excel_report
                    print(">> [BACKUP] Saatlik Telegram Excel yedegi hazirlaniyor...")
                    excel_buf = create_styled_excel_report(
                        history_data=trader_manager.history,
                        current_balance=trader_manager.balance,
                        initial_balance=initial_balance
                    )
                    now_str = datetime.now(timezone(timedelta(hours=3))).strftime("%d.%m.%Y_%H-%M")
                    filename = f"Valkyrie_Yedek_{now_str}.xlsx"
                    await self.send_document(excel_buf.getvalue(), filename, f"📁 <b>Saatlik Otomatik Yedek</b>\n{now_str} itibariyle tüm ticari geçmiş güvende.")
                except Exception as excel_err:
                    print(f">> [BACKUP ERROR] Excel yedegi gonderilemedi: {excel_err}")

                # 2) 6-Katmanli Valkyrie Aegis Sentinel Denetimini Calistir
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
        """Telegram üzerinden gelen /kasa, kasa veya aksa mesajlarını dinler ve anında detaylı portföy yanıtı döner."""
        if not self.token:
            return
        
        # Webhook çakışmasını engellemek için başlangıçta deleteWebhook çağırıyoruz
        await self.delete_webhook()
        
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

                                # 🛡️ YETKİ KONTROLÜ: Yalnızca yetkili chat_id komut çalıştırabilir
                                if self.chat_id and str(sender_chat_id) != str(self.chat_id):
                                    await self.send_message("⛔ <b>Yetkisiz Erişim:</b> Bu bot yalnızca sistem yöneticisine özeldir.", chat_id=sender_chat_id)
                                    continue

                                # 🕹️ 1. MANUEL POZİSYON KAPATMA KOMUTU: /kapat <SEMBOLE>
                                if text.startswith("/kapat") or text.startswith("kapat") or text.startswith("/close"):
                                    parts = raw_text.split()
                                    if len(parts) >= 2:
                                        target_sym_raw = parts[1].upper().strip()
                                        target_sym = target_sym_raw if "/" in target_sym_raw else f"{target_sym_raw.replace('USDT', '')}/USDT"
                                        open_p = getattr(trader_manager, 'open_positions', {})
                                        if target_sym in open_p:
                                            prices = getattr(market_data, 'current_prices', {}) if market_data else {}
                                            cur_price = float(prices.get(target_sym, open_p[target_sym].get("entry_price", 0.0)))
                                            close_fn = getattr(trader_manager, 'close_position', None)
                                            if close_fn:
                                                if asyncio.iscoroutinefunction(close_fn):
                                                    rec = await close_fn(target_sym, cur_price, "🕹️ Telegram Manuel Kapatma Komutu")
                                                else:
                                                    rec = close_fn(target_sym, cur_price, "🕹️ Telegram Manuel Kapatma Komutu")
                                                if rec:
                                                    await self.notify_position_closed(rec, is_manual=True)
                                                    await self.send_message(f"✅ <b>#{target_sym}</b> pozisyonu başarıyla kapatıldı! Çıkış Fiyatı: <code>${cur_price:.4f}</code>", chat_id=sender_chat_id)
                                                else:
                                                    await self.send_message(f"⚠️ <b>#{target_sym}</b> kapatılamadı.", chat_id=sender_chat_id)
                                        else:
                                            open_list = ", ".join(s.replace("/USDT", "") for s in open_p.keys()) or "Yok"
                                            await self.send_message(f"⚠️ <b>#{target_sym}</b> adında açık pozisyon bulunamadı.\nAktif Pozisyonlar: <code>{open_list}</code>", chat_id=sender_chat_id)
                                    else:
                                        await self.send_message("ℹ️ Kullanım: <code>/kapat BTC</code> veya <code>/kapat SOL/USDT</code>", chat_id=sender_chat_id)
                                    continue

                                # ℹ️ 2. YARDIM VE KOMUT LİSTESİ
                                if text in ["/yardim", "yardim", "/help", "help", "komut"]:
                                    help_msg = """🤖 <b>VALKYRIE QUANT ASİSTAN KOMUTLARI:</b>
━━━━━━━━━━━━━━━━━━━━
• <code>/kasa</code> veya <code>kasa</code>: Bakiye, büyüme oranı, win rate ve kokpit raporu
• <code>/durum</code>: Açık pozisyonlar ve anlık canlı kâr/zarar
• <code>/kapat BTC</code>: Açık pozisyonu anında piyasa fiyatından kapatır
• <code>/yardim</code>: Bu komut menüsünü gösterir"""
                                    await self.send_message(help_msg, chat_id=sender_chat_id)
                                    continue

                                is_kasa_cmd = any(w in text for w in [
                                    "kasa", "aksa", "bakiye", "durum", "start",
                                    "rapor", "pnl", "portfoy", "özet", "ozet", "pozisyon",
                                    "info",
                                    "/kasa", "/aksa", "/durum", "/bakiye", "/ozet", "/özet",
                                    "/start", "/rapor", "/pnl", "/portfoy"
                                ])
                                if is_kasa_cmd:
                                    init_bal = 10000.0
                                    bal = float(getattr(trader_manager, 'balance', init_bal))
                                    open_p = getattr(trader_manager, 'open_positions', {})
                                    hist = getattr(trader_manager, 'history', [])
                                    
                                    # Serbest / Kullanılabilir Kasa
                                    try:
                                        if hasattr(trader_manager, 'get_free_balance'):
                                            free_bal = float(trader_manager.get_free_balance())
                                        else:
                                            used = sum(float(p.get('margin', p.get('margin_usdt', 0.0))) for p in open_p.values())
                                            free_bal = max(0.0, bal - used)
                                    except Exception:
                                        used = sum(float(p.get('margin', p.get('margin_usdt', 0.0))) for p in open_p.values())
                                        free_bal = max(0.0, bal - used)

                                    # Canlı Açık PnL
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

                                    # 4 Gösterge Kartı Hesaplamaları (Cockpit Metrikleri)
                                    wins = 0
                                    losses = 0
                                    win_pnl_sum = 0.0
                                    loss_pnl_sum = 0.0
                                    total_realized_pnl = 0.0

                                    for t in hist:
                                        try:
                                            p = float(t.get('net_pnl', t.get('Net Kâr ($)', t.get('pnl', 0.0))))
                                            total_realized_pnl += p
                                            if p >= 0:
                                                wins += 1
                                                win_pnl_sum += p
                                            else:
                                                losses += 1
                                                loss_pnl_sum += abs(p)
                                        except Exception:
                                            pass

                                    # 1. Net Kâr / Zarar & Büyüme (Realize + Unrealized)
                                    total_net_pnl = total_realized_pnl + total_unrealized
                                    growth_pct = ((bal + total_unrealized - init_bal) / init_bal) * 100.0
                                    growth_badge = "BÜYÜME" if growth_pct >= 0 else "SAVUNMA"
                                    growth_word = "BÜYÜME 🚀" if growth_pct >= 0 else "KÜÇÜLME 🛡️"

                                    # 2. Kazanma Oranı (Win Rate)
                                    total_closed = wins + losses
                                    win_rate = (wins / total_closed * 100.0) if total_closed > 0 else 0.0
                                    if len(open_p) > 0:
                                        win_count_str = f"{wins} Kazanç / {losses} Kayıp ({total_closed} Kapanmış | {len(open_p)} Açık Poz)"
                                        win_sub_str = f"{len(open_p)} pozisyon sürüyor (realize bekleniyor)"
                                    else:
                                        win_count_str = f"{wins} Kazanç / {losses} Kayıp ({total_closed} Kapanmış İşlem)"
                                        win_sub_str = "Sürdürülebilir Hedef: > %50.0"

                                    # 3. Kâr Faktörü (Profit Factor)
                                    if total_closed == 0:
                                        pf_str = "—"
                                        pf_quality = "İşlem Bekleniyor"
                                        pf_note = "Her $1 Kayba: İlk işlem bekleniyor"
                                    elif loss_pnl_sum == 0 and win_pnl_sum > 0:
                                        pf_str = "∞"
                                        pf_quality = "Sıfır Kayıp / %100 Kâr 🏆"
                                        pf_note = "Kayıpsız Serüven: Tüm işlemler kârda!"
                                    else:
                                        pf_val = win_pnl_sum / loss_pnl_sum if loss_pnl_sum > 0 else 0.0
                                        pf_str = f"{pf_val:.2f}x"
                                        if pf_val >= 2.0:
                                            pf_quality = "Kurumsal Elit 🏆"
                                        elif pf_val >= 1.5:
                                            pf_quality = "Çok Güçlü 🟢"
                                        elif pf_val >= 1.2:
                                            pf_quality = "Kârlı Sistem 🟡"
                                        elif pf_val >= 1.0:
                                            pf_quality = "Başa-Baş Sınırı ⚪"
                                        else:
                                            pf_quality = "Zarar Baskısı 🔴"
                                        pf_note = f"Her $1 Kayba Karşılık: +${pf_val:.2f} Kâr (Hedef > 1.5x)"

                                    now_str = datetime.now(timezone(timedelta(hours=3))).strftime("%H:%M:%S")

                                    reply = f"""💎 ━━━━━━━━━━━━━━━━━━━━━━━━━ 💎
💼 <b>VALKYRIE QUANT — ANLIK KASA & COCKPİT RAPORU</b>
⏱️ <code>{now_str} (Canlı Piyasa Senkron)</code>
━━━━━━━━━━━━━━━━━━━━━━━━━━

🏦 <b>TOPLAM KASA BAKİYESİ</b> <code>[REZERV]</code>
💰 <b>${bal:,.2f} USDT</b>
🔹 <i>Kullanılabilir Kasa: ${free_bal:,.2f} USDT (5x)</i>
🛡️ <i>Dinamik Sermaye Koruması Aktif</i>

📊 <b>NET KÂR / ZARAR & BÜYÜME</b> <code>[{growth_badge}]</code>
💵 <b>{total_net_pnl:+.2f} $</b>
📉 <code>{growth_pct:+.2f}% {growth_word}</code>
ℹ️ <i>Realize + Açık Pozisyonlar Toplamı</i>

🎯 <b>KAZANMA ORANI (WİN RATE)</b> <code>[RADAR]</code>
📈 <b>%{win_rate:.1f}</b>
📋 <i>{win_count_str}</i>
🎯 <i>{win_sub_str}</i>

⚖️ <b>KÂR FAKTÖRÜ (PROFIT FACTOR)</b> <code>[KALKAN]</code>
⚡ <b>{pf_str} ({pf_quality})</b>
📊 <i>Brüt Kâr: +${win_pnl_sum:.2f} | Kayıp: -${loss_pnl_sum:.2f}</i>
💡 <i>{pf_note}</i>

━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 <b>AÇIK POZİSYONLAR ({len(open_p)} Adet | Canlı: {total_unrealized:+.2f}$):</b>
{top_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━
💎 ━━━━━━━━━━━━━━━━━━━━━━━━━ 💎"""
                                    await self.send_message(reply, chat_id=sender_chat_id)
                                    print(f">> [TELEGRAM ASİSTAN ANINDA YANITLANDI] -> {sender_chat_id}")
                        elif resp.status == 409:
                            err_txt = await resp.text()
                            print(f">> [TELEGRAM POLLING 409 CONFLICT]: {err_txt} -> Webhook temizleniyor...")
                            await self.delete_webhook()
                            await asyncio.sleep(2)
                        else:
                            err_txt = await resp.text()
                            print(f">> [TELEGRAM POLLING UYARI] (HTTP {resp.status}): {err_txt}")
                            await asyncio.sleep(1)
            except Exception as e:
                print(f"[TELEGRAM LISTENER ERROR]: {e}")
                await asyncio.sleep(2)
            await asyncio.sleep(0.5)
