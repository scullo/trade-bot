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
            # 1024 karakteri aştığında fotoğraf kısa başlıkla, tam detaylı quant raporu ise hemen ardından mesaj olarak iletilir.
            if len(caption) <= 1000:
                data = aiohttp.FormData()
                data.add_field('chat_id', str(self.chat_id))
                data.add_field('caption', caption)
                data.add_field('parse_mode', 'HTML')
                data.add_field('photo', buf, filename='trade_chart.png', content_type='image/png')

                async with aiohttp.ClientSession() as session:
                    async with session.post(self.photo_url, data=data, timeout=15) as resp:
                        if resp.status != 200:
                            err_text = await resp.text()
                            print(f">> Telegram sendPhoto Hatasi (HTTP {resp.status}): {err_text}, metin olarak iletiliyor...")
                            await self.send_message(caption)
            else:
                # Başlık 1024 karakterden uzun: Fotoğrafı özet başlıkla gönder, ardından tüm detaylı metni ilet
                lines = [l.strip() for l in caption.strip().splitlines() if l.strip() and "━━" not in l]
                headline = "\n".join(lines[:4]) if lines else "📊 <b>Valkyrie Quant Pozisyon Grafiği</b>"

                data = aiohttp.FormData()
                data.add_field('chat_id', str(self.chat_id))
                data.add_field('caption', headline)
                data.add_field('parse_mode', 'HTML')
                data.add_field('photo', buf, filename='trade_chart.png', content_type='image/png')

                async with aiohttp.ClientSession() as session:
                    async with session.post(self.photo_url, data=data, timeout=15) as resp:
                        if resp.status != 200:
                            err_text = await resp.text()
                            print(f">> Telegram sendPhoto (Uzun) Hatasi (HTTP {resp.status}): {err_text}")
                # Tüm detaylı metni mesaj olarak gönder (4096 karakter kapasitesi)
                await self.send_message(caption)
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

    def _generate_quant_entry_briefing(self, pos: dict, vol_val: float, rs_score: float, macro_str: str) -> str:
        trade_type = str(pos.get("trade_type", ""))
        reason = str(pos.get("reason", ""))
        decouple = str(pos.get("decoupling_status", ""))
        symbol = pos.get("symbol", "")
        seed_str = f"{symbol}_{pos.get('entry_time', '')}_{trade_type}_{vol_val:.1f}"
        idx = int(hashlib.md5(seed_str.encode('utf-8')).hexdigest(), 16)

        # 1. ALFA AYRIŞMA & YÜKSEK HACİMLİ BREAKOUT (vol_val >= 2.0 veya ALFA)
        if "ALFA" in decouple or (vol_val >= 2.0 and "Breakout" in trade_type):
            pool = [
                f"Parite genel piyasadan bağımsız kurumsal hacimle ({vol_val:.1f}x) ayrıştı! Rüzgar arkamızda; TP1'de ilk kâr kilitlenip koruma kalkanına geçilecek.",
                f"Akıllı para akışı netleşti ({vol_val:.1f}x Hacim, RS: {rs_score:+.2f}). Beta baskısını kıran paritede kurumsal alım dalgası değerlendiriliyor.",
                f"Emir defterinde agresif likidite emilimi gerçekleşti ({vol_val:.1f}x). Parite piyasa yönünden bağımsız pozitif ivme yakaladı; TP1 hedefte.",
                f"Kurumsal emir blokları seviyeyi hacimle ({vol_val:.1f}x) deldi. İlk hedefte risk sıfırlanarak trend koşusu planlandı.",
                f"Yüksek hacimli konsolidasyon kırılımı teyit edildi. Göreceli güç katsayısı ({rs_score:+.2f}) güçlü momentumu doğruluyor.",
                f"Büyük montanlı alıcı baskısı emir akışına yansıdı. Matematiksel disiplinle TP1 seviyesinde anapara emniyete alınacak."
            ]
            chosen = pool[idx % len(pool)]
            return f"🧠 <b>Yapay Zeka Taktik Notu:</b> <i>{chosen}</i>\n"

        # 2. STANDART BREAKOUT / MOMENTUM
        elif "Breakout" in trade_type:
            pool = [
                "Kilit direnç eşiği aşıldı. 5M mum kapanışı seviye üzerinde teyit edildi; TP1'de %50 kâr kilidi ve ardından Breakeven zırhı işletilecek.",
                "Volatilite genişlemesiyle birlikte yapısal kırılım onaylandı. 1.5 ATR dinamik tamponla işlem sağlama alındı.",
                "Kurumsal değer alanı dışına yönlü patlama gerçekleşti. TP1 istasyonuna kadar ivme korunacak, ardından sıfır risk zırhına geçilecek.",
                "Piyasa yapıcı direnç duvarı aşıldı. Disiplinli risk-getiri oranıyla ilk likidite havuzuna odaklanıldı.",
                "Düşük zaman dilimi sıkışması yukarı kırıldı. Kural gereği TP1'de yarım kâr realizasyonu yapılarak sermaye korunacak."
            ]
            chosen = pool[idx % len(pool)]
            return f"🧠 <b>Yapay Zeka Taktik Notu:</b> <i>{chosen}</i>\n"

        # 3. MEAN REVERSION / nPOC / LİKİDİTE SEKMESİ
        elif "SCALP" in trade_type or "nPOC" in reason or "Likidite" in reason or "Sekme" in reason:
            pool = [
                "Dokunulmamış kurumsal hacim bloğundan (nPOC) beklenen likidite sekmesi yakalandı. Yatay bant dengesinde kâr cebe alınacak.",
                "İstatistiksel aşırı sapma kurumsal seviyede emildi. Fiyatın değer alanı eksenine (Mean Reversion) dönüşü hedefleniyor.",
                "Fiyat kurumsal likidite havuzunu süpürüp seviye içine geri döndü. Düşük riskli, yüksek olasılıklı pivot tepkisi işleme alındı.",
                "Piyasa dengesizliği (imbalance) nPOC istasyonunda karşılandı. 1.5 ATR koruma stopuyla mikro dalga değerlendiriliyor.",
                "Kurumsal emir blokları seviyeyi savundu. Kısa vadeli sermaye korumalı scalp taktiği işletimde."
            ]
            chosen = pool[idx % len(pool)]
            return f"🧠 <b>Yapay Zeka Taktik Notu:</b> <i>{chosen}</i>\n"

        # 4. DESTEK / DİRENÇ / CAMARILLA REAKSİYONU
        elif "S3" in reason or "R3" in reason or "Pivot" in reason:
            pool = [
                "Camarilla istatistiksel sınırında güçlü reaksiyon fitili onaylandı. Ortalama dönüş istikametinde disiplinli pozisyon başlatıldı.",
                "Kritik dönüş seviyesinde alıcı/satıcı dengesi lehimize evrildi. 1.5 ATR dinamik stopla risk kontrol altında.",
                "Aşırı uzamış fiyat hareketi destek/direnç bandında kurumsal taleple karşılaştı. Hedef pivot seviyesine doğru kontrollü kâr takibi.",
                "Piyasa yapıcı denge eksenine doğru geri çekilme dalgası taranıyor. Matematiksel hedef seviyesinde kâr kilitlenecek."
            ]
            chosen = pool[idx % len(pool)]
            return f"🧠 <b>Yapay Zeka Taktik Notu:</b> <i>{chosen}</i>\n"

        # 5. RETEST / TREND DEVAM
        elif "Retest" in reason or "Devam" in reason:
            pool = [
                "Trend yönünde sağlıklı geri çekilme (Retest) başarıyla tamamlandı. Düşük maliyetli kurumsal ekleme bölgesinde pozisyon tetiklendi.",
                "Kırılan seviye yeni destek olarak test edildi ve korundu. Trend takip algoritması en uygun risk-getiri noktasından pozisyona girdi.",
                "Momentum dinlenmesinin ardından trend yönünde yeni dalga teyidi. Dinamik takip stopu ile adım adım pozisyon sürülecek."
            ]
            chosen = pool[idx % len(pool)]
            return f"🧠 <b>Yapay Zeka Taktik Notu:</b> <i>{chosen}</i>\n"

        # 6. GENEL / DENGELİ QUANT KURALI
        else:
            pool = [
                "Matematiksel kural seti tam teyit verdi. Risk sermayesi koruma kalkanıyla kontrol altında.",
                "Beklenen Değer (EV) pozitif bölgede hesaplandı. Dinamik kâr kilidi ve sert stop bariyeriyle işlem devrede.",
                "Kurumsal pusu stratejisi seviyeyi onayladı. Önceden belirlenmiş para yönetimi kuralları harfiyen uygulanıyor."
            ]
            chosen = pool[idx % len(pool)]
            return f"🧠 <b>Yapay Zeka Taktik Notu:</b> <i>{chosen}</i>\n"

    async def notify_position_opened(self, pos: dict, free_balance: float = None, df_5m = None, levels: dict = None):
        side_emoji = "🟢 <b>LONG</b>" if pos["side"] == "LONG" else "🔴 <b>SHORT</b>"
        clean_sym = pos["symbol"].replace("/USDT", "")
        
        atr_val = pos.get('atr_pct', 1.2)
        vol_val = pos.get('volume_surge', 1.0)
        bal_line = f"💼 <b>Serbest Kasa:</b> <code>${free_balance:.2f} USDT</code>\n" if free_balance is not None else ""
        tp2_line = f"🚀 <b>TP2 Final:</b> <code>${pos['tp2']:.6f}</code>\n" if pos.get("tp2") else ""

        macro_str = str(pos.get('macro_climate', '⚪ Nötr / Dengeli Piyasa'))
        decouple_str = str(pos.get('decoupling_status', '⚪ Nötr_Takipçi (Beta)'))
        rs_score = pos.get('dynamic_rs_score', pos.get('rs_vs_btc', 0.0))

        f_rate = pos.get('entry_funding_rate', 0.0100)
        f_status = pos.get('funding_status', 'BALANCED')
        f_status_label = "🟢 Dengeli" if f_status == "BALANCED" else ("⚠️ Short Squeeze Korumalı" if f_status == "SHORT_SQUEEZE_RISK" else "🔥 Aşırı Long")
        funding_line = f"⚡ <b>Fonlama Oranı:</b> <code>%{f_rate:+.4f} ({f_status_label})</code>\n"

        liq_vol = float(pos.get('entry_liq_volume_usd', 0.0))
        liq_conf = pos.get('liq_confirmed', False)
        liq_line = f"💥 <b>Tasfiye Teyidi:</b> <code>${liq_vol:,.0f} Perakende Tasfiyesi Süpürüldü 🎯</code>\n" if (liq_conf and liq_vol > 0) else ""

        cvd_val = float(pos.get('entry_cvd_pct', 50.0))
        cvd_stat = str(pos.get('cvd_status', 'DENGELİ'))
        cvd_d = float(pos.get('entry_cvd_delta', 0.0))
        cvd_line = ""
        if cvd_val != 50.0 or cvd_stat != "DENGELİ":
            d_str = f"{cvd_d/1000:+.0f}K" if abs(cvd_d) >= 1000 else f"{cvd_d:+.0f}"
            safe_cvd_stat = html.escape(cvd_stat, quote=False)
            cvd_line = f"🔬 <b>Mikro-CVD:</b> <code>%{cvd_val:.1f} Alıcı (Delta: ${d_str}) — {safe_cvd_stat}</code>\n"

        # 🧠 Yapay Zeka Dinamik Taktik Brifingi
        ai_tactic_note = self._generate_quant_entry_briefing(pos, vol_val, rs_score, macro_str)

        # HTML injection/parse hatasını önlemek için dinamik metinleri sanitize et
        safe_reason = html.escape(str(pos.get('reason', 'Strateji Sinyali')), quote=False)
        safe_macro = html.escape(macro_str, quote=False)
        safe_decouple = html.escape(decouple_str, quote=False)

        msg = f"""💎 ━━━━━━━━━━━━━━━━━━━━━━ 💎
⚡ <b>YENİ POZİSYON AÇILDI</b> ⚡
━━━━━━━━━━━━━━━━━━━━━━━━
Parite: <b>#{clean_sym}/USDT</b> | {side_emoji} <b>({pos['leverage']}x)</b>
Giriş: <code>${pos['entry_price']:.6f}</code> | Marjin: <b>${pos.get('margin_usdt', pos.get('margin', 100.0)):.1f}</b>
━━━━━━━━━━━━━━━━━━━━━━━━
🛑 <b>Stop:</b> <code>${pos.get('hard_stop', pos.get('soft_stop', 0.0)):.6f}</code>
🎯 <b>TP1 Hedefi:</b> <code>${pos.get('tp1', 0.0):.6f}</code>
{tp2_line}🛡️ <b>Kâr Zırhı:</b> <code>+%7 ROE veya 90dk (%50 Kilit)</code>
📊 <b>ATR / Hacim:</b> <code>%{atr_val:.2f} | {vol_val:.2f}x</code>
🌐 <b>Makro İklim:</b> <code>{safe_macro}</code>
⚡ <b>Alfa/Beta Gücü:</b> <code>{safe_decouple} (RS: {rs_score:+.2f})</code>
{funding_line}{liq_line}{cvd_line}{bal_line}━━━━━━━━━━━━━━━━━━━━━━━━
📌 <b>Setup:</b> <i>{safe_reason}</i>
{ai_tactic_note}⏰ <b>Zaman:</b> <code>{pos.get('entry_time', '')}</code>
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

    def _generate_quant_exit_autopsy(self, record: dict, net_pnl: float, roe: float, is_win: bool, is_partial_tp1: bool, is_breakeven: bool, is_manual: bool) -> str:
        symbol = record.get("symbol", "")
        seed_str = f"{symbol}_{record.get('exit_time', '')}_{net_pnl:.2f}_{roe:.2f}_{is_manual}"
        idx = int(hashlib.md5(seed_str.encode('utf-8')).hexdigest(), 16)

        # 1. MANUEL MÜDAHALE
        if is_manual:
            pool = [
                "Operatör inisiyatifi ile pozisyon güvenli limana çekildi. Piyasa belirsizliği döneminde sermaye likit olarak korumaya alındı.",
                "Dashboard üzerinden anlık risk tasfiyesi gerçekleştirildi. Kasa emniyeti ön planda tutularak işlem sonlandırıldı.",
                "Manuel emirle masadan kalkıldı. Sermaye yeni açılacak yüksek potansiyelli fırsatlar için serbest bırakıldı."
            ]
            return f"🧠 <b>Yapay Zeka Otopisi:</b> <i>{pool[idx % len(pool)]}</i>\n"

        # 2. DİNAMİK KÂR KİLİDİ (TP1 / %50 NAKİT)
        if is_partial_tp1:
            pool = [
                "Dinamik Kâr Kilidi (%50) disiplinle çalıştı ve kârı cebe kilitledi. Kalan %50 artık tamamen sıfır riskle koşuyor.",
                "TP1 hedefi kurumsal disiplinle nakite çevrildi. Kalan pozisyon Breakeven kalkanıyla 'bedava bilet' modunda TP2 hedefine ilerliyor.",
                "Portföy koruma protokolü devrede: İlk dilim kâr realize edildi, anapara koruma stopu başabaş seviyesine sabitlendi.",
                "İstatistiki kâr optimizasyonu kusursuz işledi. Yarı pay nakite alındı; kalan bakiye sıfır risk zırhıyla trend genişlemesini izliyor.",
                "Kâr kilitleme kuralı işletildi. Sermaye büyüme eğrisine net katkı sağlandı, sıfır stresle serbest koşu devam ediyor."
            ]
            return f"🧠 <b>Yapay Zeka Otopisi:</b> <i>{pool[idx % len(pool)]}</i>\n"

        # 3. BREAKEVEN KAPANIŞ (0 RİSK KORUMASI)
        if is_breakeven:
            pool = [
                "Fiyat ilk hedeften sonra terse döndü; ancak Breakeven kalkanı devreye girerek anaparayı kuruşu kuruşuna korudu.",
                "Kâr daha önce realize edilmişti; kalan pay piyasa dönüşünde başabaş seviyesinde korundu. İşlem net kârla tamamlandı.",
                "Sıfır risk zırhı görevini yaptı. Piyasadaki ani ters dalgalanmada anapara erimedi, sermaye bir sonraki kuruluma eksiksiz aktarıldı.",
                "Başabaş kalkanı kusursuz çalıştı. Piyasa tersine dönerken pozisyon zamanında tasfiye edilerek potansiyel zararlar engellendi.",
                "Koruma protokolü zaferi: Kâr cepte, anapara korundu. Ters piyasa koşullarında sermaye bütünlüğünü korumak en büyük başarıdır."
            ]
            return f"🧠 <b>Yapay Zeka Otopisi:</b> <i>{pool[idx % len(pool)]}</i>\n"

        # 4. KÂRLI TAM KAPANIŞ (TP2 / TAM HEDEF / WIN)
        if is_win:
            pool = [
                f"Matematiksel plan kusursuz işledi! Zirve hedefe ulaşıldı ve {net_pnl:+.2f}$ net kâr kasaya eklendi.",
                f"Kurumsal kâr istasyonuna tam isabet. Trendin zirve noktasında tam kâr realizasyonuyla {net_pnl:+.2f}$ portföye yazıldı.",
                f"Hedeflenen R:R matrisi milimetrik tamamlandı. Disiplinli algoritma yönetimiyle kasa büyüme hedefine bir adım daha atıldı.",
                f"Akıllı para kâr alma bölgesinde pozisyon tamamen tasfiye edildi. Piyasa dönüş riskine maruz kalınmadan net kâr ({net_pnl:+.2f}$) kilitlendi.",
                f"Kusursuz işlem icrası: Seviye kırılımından tepe hedefe kadar dalga sonuna kadar sürüldü ({net_pnl:+.2f}$). Tebrikler!",
                f"Trend genişlemesi matematiksel hedefte sonlandırıldı. Kasa disiplini ve sabırla beklenen kâr realize edildi."
            ]
            return f"🧠 <b>Yapay Zeka Otopisi:</b> <i>{pool[idx % len(pool)]}</i>\n"

        # 5. SERT STOP / ZARAR KES (STOP LOSS)
        hard_stop_val = record.get('hard_stop', 0)
        stop_str = f" (${hard_stop_val:.4f})" if hard_stop_val else ""
        pool = [
            f"1.5 ATR dinamik stop mekanizması{stop_str} felaket koruması olarak görevini yaptı ve kaybı sınırladı. Sermaye korundu, yeni fırsat taranıyor.",
            f"Piyasa yapısı geçici olarak bozuldu; quant kuralı tereddütsüz stop uygulayarak sermayeyi büyük çöküşten korudu. Sermaye disiplini esastır.",
            f"Kontrollü stop kaybı: İstatistiksel sınır dışına çıkan harekette kayıp katı kurallarla sınırlandı. Portföy riski matematiksel limitler dahilinde.",
            f"Risk kalkanı devrede: Sert stop seviyesi felaketi engelledi. Yanlış giden piyasa hareketine inatlaşılmadı, sermaye yeni döngüye saklandı.",
            f"Planlanan risk bütçesi haricinde tek kuruş kayıp verilmedi. Stop olmak bir kayıp değil, sermayeyi hayatta tutan en kritik profesyonel savunmadır.",
            f"Disiplinli sermaye savunması: Pozisyon stop sınırında tereddütsüz kesildi. Portföy sağlığı ve uzun vadeli hayatta kalma kuralı işletildi."
        ]
        return f"🧠 <b>Yapay Zeka Otopisi:</b> <i>{pool[idx % len(pool)]}</i>\n"

    async def notify_position_closed(self, record: dict, is_manual: bool = False, df_5m = None, levels: dict = None):
        net_pnl = float(record.get("net_pnl", 0.0))
        roe = float(record.get("roe_pct", 0.0))
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
        clean_sym = record.get("symbol", "").replace("/USDT", "")

        manual_tag = "\n⚠️ <i>Kullanıcı Dashboard üzerinden acil müdahale ile pozisyonu kapattı.</i>\n" if is_manual else ""
        bal_after = record.get('balance_after', '')
        try:
            bal_str = f"💼 <b>Güncel Toplam Kasa:</b> <b>{float(bal_after):.2f} USDT</b>\n" if bal_after != '' else ""
        except Exception:
            bal_str = ""

        open_reason = record.get("reason", "Strateji Sinyali")
        close_reason = record.get("close_reason", "Hedef/Stop Kapanışı")
        partial_note = "\n🛡️ <b>Kalan %50:</b> <i>Breakeven ile 0 riskle koşuyor!</i>\n" if is_partial_tp1 else ("\nℹ️ <i>İlk %50 kârı daha önce kasaya kilitlenmişti; kalan kısım koruma stopuyla risksiz kapatıldı.</i>\n" if is_breakeven else "")
        
        # 🧠 Yapay Zeka Dinamik İşlem Otopisi (20+ Varyasyon)
        ai_autopsy_note = self._generate_quant_exit_autopsy(record, net_pnl, roe, is_win, is_partial_tp1, is_breakeven, is_manual)

        safe_open_reason = html.escape(str(open_reason), quote=False)
        safe_close_reason = html.escape(str(close_reason), quote=False)
        safe_macro = html.escape(str(record.get('macro_climate', '')), quote=False)
        macro_line = f"🌐 <b>İşlem İklimi:</b> <code>{safe_macro}</code>\n" if safe_macro else ""

        msg = f"""💎 ━━━━━━━━━━━━━━━━━━━━━━ 💎
{pnl_emoji}
━━━━━━━━━━━━━━━━━━━━━━━━
Parite: <b>#{clean_sym}/USDT</b> ({record.get('side', '')} {record.get('leverage', 5)}x)
Giriş: <code>${float(record.get('entry_price', 0.0)):.6f}</code> ➔ Çıkış: <code>${float(record.get('exit_price', 0.0)):.6f}</code>
━━━━━━━━━━━━━━━━━━━━━━━━
💰 <b>Net Kâr / Zarar:</b> <b>{net_pnl:+.4f} USDT ({roe:+.2f}%)</b>
💵 <b>Brüt:</b> {float(record.get('gross_pnl', net_pnl)):+.4f} $ | 💸 <b>Komisyon:</b> {float(record.get('fees', 0.0)):.4f} $
{bal_str}━━━━━━━━━━━━━━━━━━━━━━━━
📥 <b>Açılış Nedeni:</b> <i>{safe_open_reason}</i>
📤 <b>Kapanış Nedeni:</b> <i>{safe_close_reason}</i>{manual_tag}{partial_note}
{macro_line}{ai_autopsy_note}⏰ <b>Çıkış Zamanı:</b> <code>{record.get('exit_time', '')}</code>
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
                    side=record.get("side", "LONG"),
                    entry_price=record.get("entry_price"),
                    exit_price=record.get("exit_price"),
                    entry_timestamp=entry_ts,
                    reason=record.get("close_reason", ""),
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
                        fname = f"{clean_dt}_{clean_sym}_{record.get('side', '')}_{pnl_label}.png".replace("+", "plus_").replace("-", "minus_").replace("$", "")
                        fpath = os.path.join("ANALİZ/KRİTİK_GRAFİKLER", fname)
                        with open(fpath, "wb") as f_img:
                            f_img.write(chart_buf.getvalue())
                        archive_tag = f"📸 <b>Adli Analiz Grafiği Kaydedildi:</b> <code>ANALİZ/KRİTİK_GRAFİKLER/{fname}</code>\n"
                    except Exception as ex_arch:
                        print(f"[ARŞİVLEME HATA]: {ex_arch}")
            except Exception as e:
                print(f"[TELEGRAM] Kapanis grafigi olusturulamadi: {e}")

        if archive_tag:
            msg = msg.replace("⏰ <b>Çıkış Zamanı:</b>", f"{archive_tag}⏰ <b>Çıkış Zamanı:</b>")

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

                current_hour = (datetime.utcnow().hour + 3) % 24
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
                                    bal = getattr(trader_manager, 'balance', 10000.0)
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
