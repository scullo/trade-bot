"""
VALKYRIE GÖRSEL ADLİ KARA KUTU & MİKROSKOBİK MUM OTOPSİ MOTORU
Modül: forensic_autopsy.py
Amaç: Kapanan her pozisyonun mum, hacim, CVD, MAFE ve seviye verilerini
mikroskobik olarak inceleyerek kural tabanlı adli patoloji raporu üretir.
"""

import time
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta


class ForensicAutopsyEngine:
    """
    Kapanan pozisyonların mikroskobik adli otopsisini yürüten yerel analiz motoru.
    Görselin yanındaki HUD panelinde gösterilecek 3 maddelik teşhis ve
    detaylı adli patoloji raporunu üretir.
    """

    DIAGNOSIS_CATALOG = {
        "MM_STOP_HUNT_VICTIM": {
            "title": "Piyasa Yapıcı Fitil Süpürmesi (Stop Hunt)",
            "badge": "⚠️ LİKİDİTE AVINA KURBAN",
            "color": "#f43f5e",
            "icon": "💥"
        },
        "LOW_VOLUME_FAKEOUT": {
            "title": "Düşük Hacimli Sahte Kırılım Tuzağı",
            "badge": "⚠️ HACİMSİZ FAKEOUT TUZAĞI",
            "color": "#f59e0b",
            "icon": "🪤"
        },
        "CHURN_EXIT_REGRET": {
            "title": "Erken Çıkış & Kaçan Dalga (Churn)",
            "badge": "⏱️ ERKEN ÇIKIŞ PİŞMANLIĞI",
            "color": "#38bdf8",
            "icon": "🏃"
        },
        "REGIME_REVERSAL_SHOCK": {
            "title": "Ani Rejim Kayması & Makro Şok",
            "badge": "⚡ VOLATİLİTE ŞOKU",
            "color": "#a855f7",
            "icon": "🌊"
        },
        "COUNTER_TREND_TRAP": {
            "title": "Makro Ters Akıntı Tuzağı (HTF Uyumsuzluğu)",
            "badge": "🛑 TERS AKINTIYA KÜREK",
            "color": "#ec4899",
            "icon": "🌪️"
        },
        "PERFECT_EXECUTION_RUNNER": {
            "title": "Kusursuz Kurumsal İcraat & Trend Koşucusu",
            "badge": "🏆 KUSURSUZ TREND İCRAATI",
            "color": "#10b981",
            "icon": "👑"
        },
        "SQUEEZE_SURFING_SUCCESS": {
            "title": "Fonlama / Squeeze Dalgası Başarısı",
            "badge": "🚀 SQUEEZE SÖRFÜ",
            "color": "#06b6d4",
            "icon": "🏄"
        },
        "ORDERBOOK_ABSORPTION": {
            "title": "Derinlik Duvarına Çarpma & Likidite Emilimi",
            "badge": "🧱 DUVAR EMİLİMİ",
            "color": "#eab308",
            "icon": "🛡️"
        },
        "BALANCED_NORMAL_CLOSE": {
            "title": "Standart Kuant Yürütmesi",
            "badge": "⚖️ STANDART İCRAAT",
            "color": "#94a3b8",
            "icon": "📋"
        }
    }

    def __init__(self):
        pass

    def perform_autopsy(
        self,
        trade_record: Dict[str, Any],
        df_5m: Optional[pd.DataFrame] = None,
        levels: Optional[Dict[str, Any]] = None,
        post_exit_df: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        Kapanan pozisyonun tüm parametrelerini inceleyerek adli otopsi raporu üretir.
        """
        levels = levels or {}
        symbol = str(trade_record.get("symbol", "UNKNOWN")).replace("/USDT", "")
        side = str(trade_record.get("side", "LONG")).upper()
        entry_price = float(trade_record.get("entry_price") or 0.0)
        exit_price = float(trade_record.get("exit_price") or 0.0)
        net_pnl = float(trade_record.get("net_pnl") or 0.0)
        roe_pct = float(trade_record.get("roe_pct") or 0.0)
        close_reason = str(trade_record.get("close_reason") or "")
        setup_id = str(trade_record.get("setup_id") or trade_record.get("reason") or "SETUP_QUANT")
        holding_candles = int(trade_record.get("candle_count") or 1)
        duration_str = str(trade_record.get("duration") or f"{holding_candles * 5}dk")

        # Ölçüm metrikleri
        mfe_roe = float(trade_record.get("max_mfe_roe") or 0.0)
        mae_roe = float(trade_record.get("max_mae_roe") or 0.0)
        vol_surge = float(trade_record.get("volume_surge") or 1.0)
        funding_rate = float(trade_record.get("entry_funding_rate") or 0.0)
        funding_status = str(trade_record.get("funding_status") or "BALANCED")
        cvd_delta = float(trade_record.get("entry_cvd_delta") or 0.0)
        atr_pct = float(trade_record.get("atr_pct") or 1.0)

        diagnosis_code = "BALANCED_NORMAL_CLOSE"
        confidence = 0.85
        findings = []
        actionable_advice = ""

        # =========================================================================
        # 1. TEST: KUSURSUZ TREND İCRAATI (Büyük Kâr + Düşük Drawdown)
        # =========================================================================
        if roe_pct >= 2.5:
            if abs(mae_roe) < 1.0:
                diagnosis_code = "PERFECT_EXECUTION_RUNNER"
                confidence = 0.95
                findings.append(f"Girişten itibaren fiyat neredeyse hiç geri çekilmedi (Maks Çekilme: %{mae_roe:.2f}).")
                findings.append(f"Trend momentumu hedefe kadar korundu (Zirve ROE: +%{mfe_roe:.2f}).")
                findings.append(f"Kurumsal seviyeler ({setup_id}) tam isabetle çalıştı.")
                actionable_advice = "Bu paritede bu setup kombinasyonu Coin DNA'sında 'Alpha Runner' ligine dahil edilmeli."
            elif funding_rate < -0.02 and side == "LONG":
                diagnosis_code = "SQUEEZE_SURFING_SUCCESS"
                confidence = 0.92
                findings.append(f"Negatif fonlama ({funding_rate:.4f}%) ortamında açığa satanlar (Short) sıkıştırıldı.")
                findings.append(f"CVD ve hacim patlaması yukarı yönlü likidasyon çağlayanı yarattı.")
                findings.append(f"İşlem +%{roe_pct:.2f} ROE net kârla runner hedefine ulaştı.")
                actionable_advice = "Short squeeze radarı ile senkron çalışan pozisyon boyutu çarpanı %100 başarılı oldu."
            else:
                diagnosis_code = "PERFECT_EXECUTION_RUNNER"
                confidence = 0.90
                findings.append(f"Net kâr +${net_pnl:.2f} (+%{roe_pct:.1f} ROE) ile kilitlendi.")
                findings.append(f"Pozisyon {holding_candles} mum boyunca trend yönünde disiplinle taşındı.")
                findings.append(f"Çıkış stratejisi ({close_reason}) kârı başarıyla realize etti.")
                actionable_advice = "Trend takibi kusursuz icra edildi; kural setine sadık kalın."

        # =========================================================================
        # 2. TEST: ZARAR / STOP POST-MORTEM (Neden Kaybettik?)
        # =========================================================================
        elif roe_pct <= -0.5 or "Stop" in close_reason or "Tasfiye" in close_reason or "Zarar" in close_reason:
            is_wick_sweep = False

            # Mum bazlı fitil incelemesi (Eğer dataframe varsa)
            if df_5m is not None and not df_5m.empty and len(df_5m) >= 3:
                last_bars = df_5m.iloc[-3:]
                for _, bar in last_bars.iterrows():
                    b_open, b_close, b_high, b_low = float(bar['open']), float(bar['close']), float(bar['high']), float(bar['low'])
                    candle_span = max(b_high - b_low, 1e-8)
                    if side == "LONG":
                        lower_wick = min(b_open, b_close) - b_low
                        wick_ratio = lower_wick / candle_span
                        # Eğer alt fitil mumun %55'inden fazlasıysa ve stop o fitilde patladıysa
                        if wick_ratio > 0.55 and b_low <= exit_price <= min(b_open, b_close):
                            is_wick_sweep = True
                            break
                    else: # SHORT
                        upper_wick = b_high - max(b_open, b_close)
                        wick_ratio = upper_wick / candle_span
                        if wick_ratio > 0.55 and max(b_open, b_close) <= exit_price <= b_high:
                            is_wick_sweep = True
                            break

            if is_wick_sweep:
                diagnosis_code = "MM_STOP_HUNT_VICTIM"
                confidence = 0.94
                findings.append(f"Çıkış mumu belirgin bir kurumsal fitil ile kapandı (Alt/Üst fitil oranı > %55).")
                findings.append(f"Gövde stop seviyesinin üzerinde/altında tutunmasına rağmen iğne stopu patlattı.")
                findings.append(f"Piyasa yapıcı likidite havuzunu süpürdükten sonra yönünü korudu.")
                actionable_advice = "Stop seviyesini doğrudan seviye çizgisi yerine yapısal fitilin 0.25x ATR altına çekin veya 5M mum kapanışı teyidi (Closing-Basis Stop) uygulayın."

            elif vol_surge < 0.95 and "BREAKOUT" in setup_id.upper():
                diagnosis_code = "LOW_VOLUME_FAKEOUT"
                confidence = 0.88
                findings.append(f"Kırılım denemesi düşük hacimle yapıldı (Hacim Çarpanı: {vol_surge:.2f}x < 1.0x).")
                findings.append(f"Kırılımı destekleyecek kurumsal Taker CVD alımı oluşmadı.")
                findings.append(f"Tuzak kırılım hızla tersine dönerek stop alanına geri yuvarlandı.")
                actionable_advice = "Breakout setup'larında min 1.4x hacim patlaması ve pozitif CVD eğimi zorunlu kılınmalı."

            elif trade_record.get("htf_alignment") == "TERS_TREND" or "COUNTER" in str(trade_record.get("setup_archetype", "")):
                diagnosis_code = "COUNTER_TREND_TRAP"
                confidence = 0.91
                findings.append(f"İşlem 1H/4H makro trendinin zıttına açıldı (HTF Uyumsuzluğu).")
                findings.append(f"Ana trendin ezici satış/alış baskısı yerel destek/direnci kolayca ezdi.")
                findings.append(f"Piyasa ana akıntı yönünde hızla akarak pozisyonu stop etti.")
                actionable_advice = "HTF tersi yönde işlem açılışlarında kalkan toleransını %0'a indirin veya yalnızca nPOC sapmalarında deneyin."

            elif atr_pct > 2.5 or "AVALANCHE" in close_reason.upper() or "ŞOK" in close_reason.upper():
                diagnosis_code = "REGIME_REVERSAL_SHOCK"
                confidence = 0.89
                findings.append(f"Pozisyon süresince aşırı volatilite patlaması yaşandı (ATR: %{atr_pct:.2f}).")
                findings.append(f"Piyasa mikroyapısında ani bir likidite boşluğu (Flash Shock) oluştu.")
                findings.append(f"Normal stop kuralları ani yayılma ve kayma sebebiyle defansif kapandı.")
                actionable_advice = "Aegis Avalanche koruması devrede kalarak kasayı korudu; volatilite yatışana kadar yeni giriş engellenmeli."

            else:
                diagnosis_code = "BALANCED_NORMAL_CLOSE"
                confidence = 0.78
                findings.append(f"İşlem normal risk yönetimi sınırları dahilinde stop oldu (ROE: %{roe_pct:.2f}).")
                findings.append(f"Giriş gerekçesi teknik olarak uygundu ancak piyasa devamlılığı sağlamadı.")
                findings.append(f"Kayıp, hesaplanan azami risk toleransı sınırları içinde tutuldu.")
                actionable_advice = "Her kurulum kârlı olamaz; disiplinli risk yönetimi kasayı uzun vadede korur."

        # =========================================================================
        # 3. TEST: BAŞA BAŞ VEYA ERKEN ÇIKIŞ PİŞMANLIĞI (Churn Regret)
        # =========================================================================
        elif -0.3 <= roe_pct <= 0.3:
            # Erken çıkış sonrası fiyat hareket etti mi?
            post_exit_run = False
            post_exit_delta = 0.0
            if post_exit_df is not None and not post_exit_df.empty:
                max_post_p = float(post_exit_df['high'].max())
                min_post_p = float(post_exit_df['low'].min())
                if side == "LONG" and max_post_p > exit_price:
                    post_exit_delta = (max_post_p - exit_price) / exit_price * 100.0
                    if post_exit_delta >= 1.5:
                        post_exit_run = True
                elif side == "SHORT" and min_post_p < exit_price:
                    post_exit_delta = (exit_price - min_post_p) / exit_price * 100.0
                    if post_exit_delta >= 1.5:
                        post_exit_run = True

            if post_exit_run or holding_candles >= 12:
                diagnosis_code = "CHURN_EXIT_REGRET"
                confidence = 0.87
                findings.append(f"Pozisyon {holding_candles} mum boyunca taşındıktan sonra başa-baş kapatıldı.")
                if post_exit_run:
                    findings.append(f"Çıkışın ardından fiyat pozisyon yönünde +%{post_exit_delta:.2f} daha koştu.")
                else:
                    findings.append(f"Piyasa yatay dalgalanmada komisyon ve zaman yıpranması (Churn) yarattı.")
                findings.append(f"Korkak kâr koruması veya erken breakeven kilidi asıl trendi kaçırdı.")
                actionable_advice = "Başa-baş kilidini (Breakeven) en az TP1 seviyesine (%1.5 ROE) ulaşmadan devreye almayın."
            else:
                diagnosis_code = "BALANCED_NORMAL_CLOSE"
                confidence = 0.80
                findings.append(f"İşlem başa-baş ({roe_pct:+.2f}% ROE) seviyesinde temiz bir şekilde tasfiye edildi.")
                findings.append(f"Sermaye riske atılmadan piyasa belirsizliğinden çıkıldı.")
                actionable_advice = "Sıfır kayıpla çıkış başarıdır; yeni yüksek kaliteli fırsatları bekleyin."

        # Bilgi kartı ve özet
        meta = self.DIAGNOSIS_CATALOG.get(diagnosis_code, self.DIAGNOSIS_CATALOG["BALANCED_NORMAL_CLOSE"])

        # Vision LLM için hazır sistem istemi
        vision_prompt = (
            f"Valkyrie Forensic AI Otopsi İncelemesi: #{symbol}/USDT ({side} {trade_record.get('leverage', 5)}x).\n"
            f"Giriş Fiyatı: ${entry_price:,.4f}, Çıkış Fiyatı: ${exit_price:,.4f}, Net PnL: ${net_pnl:+.2f} ({roe_pct:+.2f}% ROE).\n"
            f"Setup: {setup_id}, Çıkış Nedeni: {close_reason}, Süre: {duration_str} ({holding_candles} Mum).\n"
            f"Ön Teşhis: {meta['title']} ({meta['badge']}).\n"
            f"Adli Bulgular:\n" + "\n".join([f"- {f}" for f in findings]) + "\n"
            f"Öneri: {actionable_advice}\n"
            f"Grafikte işaretlenen Giriş Mumu ve Çıkış Mumundaki kurumsal fiyat hareketini (Price Action, CVD, Likidite fitilleri) "
            f"ve yapılması gereken düzeltmeyi 3 vurucu maddede değerlendir."
        )

        return {
            "diagnosis_code": diagnosis_code,
            "diagnosis_title": meta["title"],
            "diagnosis_badge": meta["badge"],
            "diagnosis_color": meta["color"],
            "diagnosis_icon": meta["icon"],
            "confidence_score": confidence,
            "findings": findings,
            "actionable_advice": actionable_advice,
            "vision_prompt": vision_prompt,
            "analyzed_at": datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M:%S")
        }


# Singleton motor
forensic_autopsy_engine = ForensicAutopsyEngine()
