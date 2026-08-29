import time
import datetime
from datetime import datetime
import pandas as pd
import numpy as np
from config import (
    BUFFER_RATIO, MAX_OPEN_POSITIONS,
    TRAILING_BREAKEVEN_ROE, TRAILING_LOCK_30_ROE, TRAILING_LOCK_50_ROE,
    SCALP_MAX_HOLD_CANDLES
)

class StrategyEngine:
    def __init__(self, paper_trader, notifier, market_data=None):
        self.market_data = market_data
        self.paper_trader = paper_trader
        self.notifier = notifier
        self.peak_prices = {}  # symbol -> trailing icin en iyi fiyat

    async def _notify_open(self, pos: dict, levels: dict = None):
        if not self.notifier:
            return
        symbol = pos.get("symbol", "")
        df_5m = self.market_data.candles_5m.get(symbol) if self.market_data else None
        await self.notifier.notify_position_opened(
            pos=pos,
            free_balance=self.paper_trader.get_free_balance(),
            df_5m=df_5m,
            levels=levels
        )

    async def _notify_close(self, record: dict, is_manual: bool = False, levels: dict = None):
        if not self.notifier or not record:
            return
        symbol = record.get("symbol", "")
        df_5m = self.market_data.candles_5m.get(symbol) if self.market_data else None
        await self.notifier.notify_position_closed(
            record=record,
            is_manual=is_manual,
            df_5m=df_5m,
            levels=levels
        )


    async def _safe_close_position(self, *args, **kwargs):
        res = self.paper_trader.close_position(*args, **kwargs)
        if hasattr(res, '__await__'):
            return await res
        return res

    async def _safe_open_position(self, *args, **kwargs):
        res = self.paper_trader.open_position(*args, **kwargs)
        if hasattr(res, '__await__'):
            return await res
        return res

    # =========================================================================
    # TICK SEVIYESI: Sert Stop + TP + Trailing Stop (Her fiyat guncellenmesinde)
    # =========================================================================
    def check_engine_health(self) -> dict:
        """Strateji motorunun tum formul ve degiskenlerini anlik test eder (Hata tespiti)."""
        try:
            test_levels = {
                'camarilla': {'P': 100.0, 'R3': 102.0, 'R4': 105.0, 'R5': 110.0, 'S3': 98.0, 'S4': 95.0, 'S5': 90.0},
                'tepe_avwap': 103.0, 'dip_avwap': 97.0, 'mpoc': 99.5, 'mvah': 104.0, 'mval': 96.0,
                'above_npoc': 106.0, 'below_npoc': 94.0
            }
            cam = test_levels['camarilla']
            p = cam.get('P', 0.0)
            r3, r4, r5 = cam.get('R3', 0.0), cam.get('R4', 0.0), cam.get('R5', 0.0)
            s3, s4, s5 = cam.get('S3', 0.0), cam.get('S4', 0.0), cam.get('S5', 0.0)
            tepe_av = test_levels['tepe_avwap']
            dip_av = test_levels['dip_avwap']
            mpoc = test_levels['mpoc']
            up_targets = [lvl for lvl in [dip_av, tepe_av, mpoc, p] if lvl and lvl > 98.5 * 1.004]
            return {"healthy": True, "error": None}
        except Exception as e:
            return {"healthy": False, "error": f"Strateji Değişken Hatası: {str(e)}"}

    async def evaluate_tick(self, symbol: str, current_price: float, levels: dict):
        """Milisaniyelik anlik sert stop, TP ve trailing stop kontrolleri."""
        if symbol not in self.paper_trader.open_positions:
            return

        pos = self.paper_trader.open_positions[symbol]
        side = pos["side"]
        trade_type = pos.get("trade_type")
        tp1 = pos.get("tp1") or 0.0
        tp2 = pos.get("tp2") or 0.0
        hard_stop = pos.get("hard_stop") or 0.0

        # ── 1. SERT STOP KONTROLU (Felaket Korumasi — Aninda Kapat) ──────────
        if side == "LONG" and hard_stop > 0 and current_price <= hard_stop:
            record = await self._safe_close_position(symbol, current_price, f"Sert Stop Tetiklendi (${hard_stop:.4f})")
            if record:
                await self._notify_close(record, levels=levels)
                self._cleanup_tracking(symbol)
            return

        elif side == "SHORT" and hard_stop > 0 and current_price >= hard_stop:
            record = await self._safe_close_position(symbol, current_price, f"Sert Stop Tetiklendi (${hard_stop:.4f})")
            if record:
                await self._notify_close(record, levels=levels)
                self._cleanup_tracking(symbol)
            return

        # ── 2. TAKE-PROFIT (KAR ALMA) KONTROLU ──────────────────────────────
        if side == "LONG":
            if tp1 > 0 and current_price >= tp1:
                if trade_type == "SCALP" or not tp2:
                    record = await self._safe_close_position(symbol, current_price, f"TP Hedefine Ulasildi (${tp1:.4f})")
                    if record:
                        await self._notify_close(record, levels=levels)
                        self._cleanup_tracking(symbol)
                elif trade_type == "BREAKOUT" and not pos.get("is_half_closed"):
                    record = await self._safe_close_position(symbol, current_price, f"TP1 Alindi (%50 Kapatildi)", is_partial=True)
                    if record:
                        await self._notify_close(record, levels=levels)

            elif tp2 > 0 and pos.get("is_half_closed") and current_price >= tp2:
                record = await self._safe_close_position(symbol, current_price, f"TP2 Final Hedefe Ulasildi (${tp2:.4f})")
                if record:
                    await self._notify_close(record, levels=levels)
                    self._cleanup_tracking(symbol)

        elif side == "SHORT":
            if tp1 > 0 and current_price <= tp1:
                if trade_type == "SCALP" or not tp2:
                    record = await self._safe_close_position(symbol, current_price, f"TP Hedefine Ulasildi (${tp1:.4f})")
                    if record:
                        await self._notify_close(record, levels=levels)
                        self._cleanup_tracking(symbol)
                elif trade_type == "BREAKOUT" and not pos.get("is_half_closed"):
                    record = await self._safe_close_position(symbol, current_price, f"TP1 Alindi (%50 Kapatildi)", is_partial=True)
                    if record:
                        await self._notify_close(record, levels=levels)

            elif tp2 > 0 and pos.get("is_half_closed") and current_price <= tp2:
                record = await self._safe_close_position(symbol, current_price, f"TP2 Final Hedefe Ulasildi (${tp2:.4f})")
                if record:
                    await self._notify_close(record, levels=levels)
                    self._cleanup_tracking(symbol)

        # ── 3. TRAILING STOP (KAR KORUMA MEKANIZMASI) ────────────────────────
        if symbol in self.paper_trader.open_positions:
            self._apply_trailing_stop(symbol, self.paper_trader.open_positions[symbol], current_price)

    # =========================================================================
    # TRAILING STOP — ROE esiklerine gore stop seviyelerini sikilastirir
    # =========================================================================
    def _apply_trailing_stop(self, symbol: str, pos: dict, current_price: float):
        side = pos["side"]
        entry = pos["entry_price"]
        margin = pos["margin"]
        leverage = pos["leverage"]

        # ROE hesapla
        if side == "LONG":
            price_pct = ((current_price - entry) / entry) * 100.0
        else:
            price_pct = ((entry - current_price) / entry) * 100.0
        roe = price_pct * leverage

        if roe <= 0:
            return  # Zarardayken trailing yapma

        # Peak fiyat takibi (trailing mesafe hesabi icin)
        if symbol not in self.peak_prices:
            self.peak_prices[symbol] = current_price
        if side == "LONG" and current_price > self.peak_prices[symbol]:
            self.peak_prices[symbol] = current_price
        elif side == "SHORT" and current_price < self.peak_prices[symbol]:
            self.peak_prices[symbol] = current_price

        updated = False

        # ── ASAMA 1: ROE >= %6 → Soft stop breakeven'e (giris fiyatina) ─────
        if roe >= TRAILING_BREAKEVEN_ROE and not pos.get("_trail_be"):
            if side == "LONG":
                new_stop = entry * 1.001  # Giris + kucuk tampon
                if new_stop > pos["soft_stop"]:
                    pos["soft_stop"] = new_stop
            else:
                new_stop = entry * 0.999  # Giris - kucuk tampon
                if new_stop < pos["soft_stop"]:
                    pos["soft_stop"] = new_stop
            pos["_trail_be"] = True
            updated = True
            print(f">> [TRAILING] {symbol} ★ Breakeven koruma AKTIF (ROE: {roe:.1f}%)")

        # ── ASAMA 2: ROE >= %12 → Karin %30'unu kilitle ─────────────────────
        if roe >= TRAILING_LOCK_30_ROE and not pos.get("_trail_30"):
            peak = self.peak_prices[symbol]
            if side == "LONG":
                lock_price = entry + (peak - entry) * 0.3
                pos["soft_stop"] = max(pos["soft_stop"], lock_price)
            else:
                lock_price = entry - (entry - peak) * 0.3
                pos["soft_stop"] = min(pos["soft_stop"], lock_price)
            pos["_trail_30"] = True
            updated = True
            print(f">> [TRAILING] {symbol} ★★ %30 kar kilidi AKTIF (ROE: {roe:.1f}%)")

        # ── ASAMA 3: ROE >= %20 → Hard stop ile karin %50'sini kilitle ───────
        if roe >= TRAILING_LOCK_50_ROE and not pos.get("_trail_50"):
            peak = self.peak_prices[symbol]
            if side == "LONG":
                lock_price = entry + (peak - entry) * 0.5
                pos["hard_stop"] = max(pos["hard_stop"], lock_price)
                pos["soft_stop"] = max(pos["soft_stop"], lock_price)
            else:
                lock_price = entry - (entry - peak) * 0.5
                pos["hard_stop"] = min(pos["hard_stop"], lock_price)
                pos["soft_stop"] = min(pos["soft_stop"], lock_price)
            pos["_trail_50"] = True
            updated = True
            print(f">> [TRAILING] {symbol} ★★★ %50 SERT kar kilidi AKTIF (ROE: {roe:.1f}%)")

        if updated:
            self.paper_trader.save_history()

    def _cleanup_tracking(self, symbol: str):
        """Pozisyon kapandiginda tracking verilerini temizle."""
        self.peak_prices.pop(symbol, None)

    # =========================================================================
    # POZISYON ACMA YARDIMCISI
    # =========================================================================
    async def _handle_open(self, symbol: str, side: str, entry_price: float, reason: str, soft_stop: float, hard_stop: float, tp1: float, tp2: float = None, trade_type: str = "BREAKOUT", snapshot_levels: dict = None, setup_id: str = "", confluence_list: list = None):
        # ── 1. ATR / VOLATILITE HESABI ──
        atr_pct = 1.2
        vol_surge = 1.0
        if self.market_data and symbol in self.market_data.candles_5m:
            df = self.market_data.candles_5m[symbol]
            if isinstance(df, pd.DataFrame) and not df.empty and len(df) >= 14:
                try:
                    high = df['high']
                    low = df['low']
                    close = df['close']
                    tr1 = high - low
                    tr2 = (high - close.shift()).abs()
                    tr3 = (low - close.shift()).abs()
                    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                    atr = tr.rolling(14).mean().iloc[-1]
                    atr_pct = round((atr / close.iloc[-1]) * 100.0, 2)
                except Exception:
                    atr_pct = 1.2

                try:
                    if len(df) >= 20:
                        avg_vol = df['volume'].iloc[-21:-1].mean()
                        cur_vol = df['volume'].iloc[-1]
                        vol_surge = round(float(cur_vol / avg_vol), 2) if avg_vol > 0 else 1.0
                except Exception:
                    vol_surge = 1.0

        # ── 2. TREND REJIMI HESABI ──
        snaps = snapshot_levels or {}
        tepe_av = snaps.get('tepe_avwap', 0.0)
        dip_av = snaps.get('dip_avwap', 0.0)
        p_val = snaps.get('camarilla', {}).get('P', 0.0) if 'camarilla' in snaps else snaps.get('P', 0.0)
        
        if tepe_av > 0 and p_val > 0 and entry_price > tepe_av and entry_price > p_val:
            trend_regime = "🟢 GÜÇLÜ BOĞA (Bullish)"
        elif dip_av > 0 and p_val > 0 and entry_price < dip_av and entry_price < p_val:
            trend_regime = "🔴 GÜÇLÜ AYI (Bearish)"
        elif p_val > 0 and entry_price > p_val:
            trend_regime = "🟡 ILIMLI BOĞA (Moderate Bull)"
        elif p_val > 0 and entry_price < p_val:
            trend_regime = "🟠 ILIMLI AYI (Moderate Bear)"
        else:
            trend_regime = "⚪ YATAY / SIKIŞMA (Ranging)"

        # ── 3. SEANS HESABI ──
        h_hour = datetime.now().hour
        if 0 <= h_hour < 9:
            session_str = "🌏 ASYA (Tokyo/Singapur)"
        elif 9 <= h_hour < 16:
            session_str = "🏛️ LONDRA (Avrupa)"
        else:
            session_str = "🗽 NEW YORK (ABD)"

        # ── 4. HACIM PATLAMA KATSAYISI (Volume Surge Ratio) ──
        # Zaten yukarida df_5m'den guvenle hesaplandi (varsayilan 1.0x)

        # ── 5. CONFLUENCE (ÇAKIŞMA) SKORU ──
        c_count = min(4, max(1, len(confluence_list or [1])))
        conf_labels = {1: "1/4 (Tekil Teyit)", 2: "2/4 (Çift Teyit)", 3: "3/4 (Güçlü Confluence)", 4: "4/4 (Maksimum Kurumsal Teyit)"}
        conf_score_str = conf_labels.get(c_count, f"{c_count}/4")

        # ── 6. ÜST ZAMAN DİLİMİ (HTF) MAKRO UYUMU ──
        mpoc_val = snaps.get('mpoc', 0.0)
        if side == "LONG":
            if mpoc_val > 0 and entry_price > mpoc_val and (tepe_av == 0 or entry_price > tepe_av):
                htf_str = "🟢 TREND YÖNÜNDE (1H Boğa Uyumu)"
            elif mpoc_val > 0 and entry_price < mpoc_val:
                htf_str = "🟡 DİP TEPKİSİ (Mean Reversion)"
            else:
                htf_str = "⚪ NÖTR MAKRO"
        else:
            if mpoc_val > 0 and entry_price < mpoc_val and (dip_av == 0 or entry_price < dip_av):
                htf_str = "🔴 TREND YÖNÜNDE (1H Ayı Uyumu)"
            elif mpoc_val > 0 and entry_price > mpoc_val:
                htf_str = "🟠 TEPE REDDİ (Mean Reversion)"
            else:
                htf_str = "⚪ NÖTR MAKRO"

        # ── 7. MAKRO TREND KALKANI (COUNTER-TREND SHIELD) ──
        # Güçlü Boğa Trendinde zayıf SHORT'ları ve Güçlü Ayı Trendinde zayıf LONG'ları engelle
        if trend_regime == "🟢 GÜÇLÜ BOĞA (Bullish)" and side == "SHORT" and c_count < 3 and vol_surge < 2.0:
            print(f">> [MAKRO TREND KALKANI] {symbol} Güçlü Boğa Trendinde Karşı SHORT Reddedildi (Confluence: {c_count}/4, Surge: {vol_surge}x)")
            return
        if trend_regime == "🔴 GÜÇLÜ AYI (Bearish)" and side == "LONG" and c_count < 3 and vol_surge < 2.0:
            print(f">> [MAKRO TREND KALKANI] {symbol} Güçlü Ayı Trendinde Karşı LONG Reddedildi (Confluence: {c_count}/4, Surge: {vol_surge}x)")
            return

        # ── 8. DİNAMİK MARJİN & RİSK BOYUTLANDIRMA (RISK PARITY) ──
        # Aşırı volatil coinlerde (AMP, BICO) marjini küçültüp riski maks 3.5$ ile sınırla
        safe_atr = max(0.5, atr_pct)
        dyn_margin = min(100.0, max(20.0, round(3.5 / (safe_atr * 0.02 * 5.0) * 100.0 / 3.5, 2)))
        dyn_margin = min(100.0, max(25.0, round(100.0 / (safe_atr / 1.0), 2)))

        res = await self._safe_open_position(
            symbol=symbol, side=side, entry_price=entry_price,
            reason=reason, soft_stop=soft_stop, hard_stop=hard_stop,
            tp1=tp1, tp2=tp2, trade_type=trade_type,
            snapshot_levels=snapshot_levels, setup_id=setup_id, confluence_list=confluence_list,
            atr_pct=atr_pct, trend_regime=trend_regime, session=session_str,
            volume_surge=vol_surge, confluence_score=conf_score_str, htf_alignment=htf_str,
            custom_margin=dyn_margin
        )
        if isinstance(res, dict) and res.get("error") == "INSUFFICIENT_BALANCE":
            await self.notifier.notify_insufficient_balance(
                symbol=symbol,
                side=side,
                reason=reason,
                required_margin=res["required_margin"],
                current_balance=res["current_balance"]
            )
            return
        elif res:
            levels = self.market_data.levels.get(symbol) if self.market_data else None
            await self._notify_open(res, levels=levels)

    # =========================================================================
    # SEVIYE GUNCELLEME — Gun degisiminde acik pozisyon TP/Stop guncelleme
    # =========================================================================
    async def _refresh_position_levels(self, symbol: str, pos: dict, close_price: float, levels: dict) -> bool:
        """
        Camarilla seviyeleri gun degisiminde guncellendiginde,
        acik pozisyonun TP1/TP2/Stop degerlerini yeni seviyelere gore gunceller.
        Eger hedef coktan asilmissa pozisyonu kapatir.
        Returns True if position was closed.
        """
        cam = levels.get("camarilla", {})
        p = cam.get("P", 0)
        r3, r4, r5 = cam.get("R3", 0), cam.get("R4", 0), cam.get("R5", 0)
        s3, s4, s5 = cam.get("S3", 0), cam.get("S4", 0), cam.get("S5", 0)

        side = pos["side"]
        reason = pos.get("reason", "")
        old_tp1 = pos.get("tp1", 0)
        entry = pos["entry_price"]

        # Trailing aktifse stop seviyelerini zayiflatma
        trail_active = pos.get("_trail_be", False)

        # ── SCALP SHORT (R3 Direnc Tepkisi → hedef Pivot P) ─────────────────
        if "R3 Direnc" in reason and side == "SHORT":
            if p > 0 and abs(old_tp1 - p) > 0.0001:
                if close_price <= p:
                    # Fiyat yeni Pivot'un altinda → hedef coktan asildi → kapat
                    record = await self._safe_close_position(
                        symbol, close_price,
                        f"Pivot Kayma — Hedef Asildi (Yeni P: ${p:.4f}, Eski TP: ${old_tp1:.4f})")
                    if record:
                        await self._notify_close(record, levels=levels)
                        self._cleanup_tracking(symbol)
                    return True
                else:
                    # Yeni hedefe guncelle
                    pos["tp1"] = p
                    print(f">> [SEVIYE GUNCELLEME] {symbol} SHORT TP1: {old_tp1:.4f} → {p:.4f}")
            # Stop guncelle (trailing yoksa)
            if r3 > 0 and r4 > 0 and not trail_active:
                pos["soft_stop"] = r3 + (r4 - r3) * BUFFER_RATIO
                pos["hard_stop"] = r4

        # ── SCALP LONG (S3 Destek Sekmesi → hedef Pivot P) ──────────────────
        elif "S3 Destek" in reason and side == "LONG":
            if p > 0 and abs(old_tp1 - p) > 0.0001:
                if close_price >= p:
                    record = await self._safe_close_position(
                        symbol, close_price,
                        f"Pivot Kayma — Hedef Asildi (Yeni P: ${p:.4f}, Eski TP: ${old_tp1:.4f})")
                    if record:
                        await self._notify_close(record, levels=levels)
                        self._cleanup_tracking(symbol)
                    return True
                else:
                    pos["tp1"] = p
                    print(f">> [SEVIYE GUNCELLEME] {symbol} LONG TP1: {old_tp1:.4f} → {p:.4f}")
            if s3 > 0 and s4 > 0 and not trail_active:
                pos["soft_stop"] = s3 - (s3 - s4) * BUFFER_RATIO
                pos["hard_stop"] = s4

        # ── BREAKOUT LONG (R4 Breakout) ──────────────────────────────────────
        elif "R4 Breakout" in reason and side == "LONG":
            if r5 > 0 and abs(old_tp1 - r5) > 0.0001:
                pos["tp1"] = r5
                print(f">> [SEVIYE GUNCELLEME] {symbol} LONG TP1: {old_tp1:.4f} → {r5:.4f}")
            if r4 > 0 and r3 > 0 and not trail_active:
                pos["soft_stop"] = r4 - (r4 - r3) * BUFFER_RATIO
                pos["hard_stop"] = r3

        # ── BREAKOUT SHORT (S4 Breakdown) ────────────────────────────────────
        elif "S4 Breakdown" in reason and side == "SHORT":
            if s5 > 0 and abs(old_tp1 - s5) > 0.0001:
                pos["tp1"] = s5
                print(f">> [SEVIYE GUNCELLEME] {symbol} SHORT TP1: {old_tp1:.4f} → {s5:.4f}")
            if s4 > 0 and s3 > 0 and not trail_active:
                pos["soft_stop"] = s4 + (s3 - s4) * BUFFER_RATIO
                pos["hard_stop"] = s3

        # ── R4 Destek Retest LONG ────────────────────────────────────────────
        elif "R4 Destek Retest" in reason and side == "LONG":
            if r5 > 0 and abs(old_tp1 - r5) > 0.0001:
                pos["tp1"] = r5
            if r4 > 0 and r3 > 0 and not trail_active:
                pos["soft_stop"] = r4 - (r4 - r3) * BUFFER_RATIO
                pos["hard_stop"] = r3

        # ── S4 Direnc Retest SHORT ───────────────────────────────────────────
        elif "S4 Direnc Retest" in reason and side == "SHORT":
            if s5 > 0 and abs(old_tp1 - s5) > 0.0001:
                pos["tp1"] = s5
            if s4 > 0 and s3 > 0 and not trail_active:
                pos["soft_stop"] = s4 + (s3 - s4) * BUFFER_RATIO
                pos["hard_stop"] = s3

        # ── nPOC SCALP POZISYONLAR (Hedef Pivot P) ─────────────────────────
        elif "nPOC" in reason or "Likidite" in reason:
            if p > 0 and abs(old_tp1 - p) > 0.0001:
                if (side == "SHORT" and close_price <= p) or (side == "LONG" and close_price >= p):
                    record = await self._safe_close_position(
                        symbol, close_price,
                        f"Pivot Kayma — Hedef Asildi (Yeni P: ${p:.4f}, Eski TP: ${old_tp1:.4f})")
                    if record:
                        await self._notify_close(record, levels=levels)
                        self._cleanup_tracking(symbol)
                    return True
                else:
                    pos["tp1"] = p
                    print(f">> [SEVIYE GUNCELLEME] {symbol} nPOC {side} TP1: {old_tp1:.4f} → {p:.4f}")

        # ── mVAH / mVAL Macro pozisyonlar ───────────────────────────────────
        # Bu pozisyonlarin hedefleri nPOC/nVAH bazli, Camarilla'ya bagli degil
        # Guncelleme gerekmez

        self.paper_trader.save_history()
        return False

    # =========================================================================
    # MUM KAPANISI: Yumusak Stop + Seviye Guncelleme + Zaman Asimi + Yeni Giris
    # =========================================================================
    async def evaluate_candle_close(self, symbol: str, current_candle: dict, prev_candle: dict, levels: dict):
        """5 Dakikalik mum kapandiginda tum kontroller."""
        close_price = current_candle['close']
        prev_close = prev_candle['close'] if prev_candle else close_price

        cam = levels.get("camarilla", {})
        p = cam.get("P", 0.0)
        r3 = cam.get("R3", 0.0)
        r4 = cam.get("R4", 0.0)
        r5 = cam.get("R5", 0.0)
        s3 = cam.get("S3", 0.0)
        s4 = cam.get("S4", 0.0)
        s5 = cam.get("S5", 0.0)
        tepe_avwap = levels.get("tepe_avwap") or 0.0
        dip_avwap = levels.get("dip_avwap") or 0.0
        mvah = levels.get("mvah") or 0.0
        mval = levels.get("mval") or 0.0
        mpoc = levels.get("mpoc") or 0.0
        above_npoc = levels.get("above_npoc") or 0.0
        below_npoc = levels.get("below_npoc") or 0.0
        above_nvah = levels.get("above_nvah") or 0.0
        below_nval = levels.get("below_nval") or 0.0

        # ═══════════════════════════════════════════════════════════════════
        # BOLUM 1: ACIK POZISYON YONETIMI
        # ═══════════════════════════════════════════════════════════════════
        if symbol in self.paper_trader.open_positions:
            pos = self.paper_trader.open_positions[symbol]
            soft_stop = pos.get("soft_stop", 0.0)
            side = pos["side"]

            # 1a. KADEMELİ KÂR ALMA (TP1 - %50 Kapatma & Breakeven Koruması)
            tp1_target = pos.get("tp1", 0.0)
            tp2_target = pos.get("tp2", 0.0)
            is_half = pos.get("is_half_closed", False)

            if not is_half and tp1_target > 0:
                if (side == "LONG" and close_price >= tp1_target) or (side == "SHORT" and close_price <= tp1_target):
                    record = await self._safe_close_position(
                        symbol, tp1_target,
                        f"🎯 TP1 Hedefine Ulaşıldı (%50 Kâr Alındı - Stop Breakeven'e Çekildi)",
                        is_partial=True
                    )
                    if record:
                        await self._notify_close(record, levels=levels)
                    return

            # 1b. NİHAİ KÂR ALMA (TP2 - Kalan %50 Kapatma)
            if is_half and tp2_target > 0:
                if (side == "LONG" and close_price >= tp2_target) or (side == "SHORT" and close_price <= tp2_target):
                    record = await self._safe_close_position(
                        symbol, tp2_target,
                        f"🚀 TP2 Nihai Hedefe Ulaşıldı (Kalan %50 Kapatıldı)",
                        is_partial=False
                    )
                    if record:
                        await self._notify_close(record, levels=levels)
                        self._cleanup_tracking(symbol)
                    return

            # 1c. YUMUSAK STOP KONTROL (Breakeven veya Koruma Stopu)
            if side == "LONG" and close_price < soft_stop:
                reason_stop = "🛡️ Breakeven Koruması Tetiklendi" if is_half else "Yumusak Stop (Mum Seviye Altinda Kapandi)"
                record = await self._safe_close_position(symbol, close_price, reason_stop)
                if record:
                    await self._notify_close(record, levels=levels)
                    self._cleanup_tracking(symbol)
                return
            elif side == "SHORT" and close_price > soft_stop:
                reason_stop = "🛡️ Breakeven Koruması Tetiklendi" if is_half else "Yumusak Stop (Mum Seviye Ustunde Kapandi)"
                record = await self._safe_close_position(symbol, close_price, reason_stop)
                if record:
                    await self._notify_close(record, levels=levels)
                    self._cleanup_tracking(symbol)
                return

            # 1b. SEVIYE GUNCELLEME (Pivot Kaymasi Kontrolu)
            closed = await self._refresh_position_levels(symbol, pos, close_price, levels)
            if closed:
                return

            # 1c. SCALP ZAMAN ASIMI
            if pos.get("trade_type") == "SCALP":
                hold_seconds = time.time() - pos.get("entry_timestamp", 0)
                max_seconds = SCALP_MAX_HOLD_CANDLES * 300  # candle sayisi x 5dk
                if hold_seconds > max_seconds:
                    hours = hold_seconds / 3600.0
                    record = await self._safe_close_position(
                        symbol, close_price,
                        f"Scalp Zaman Asimi ({hours:.1f} saat)")
                    if record:
                        await self._notify_close(record, levels=levels)
                        self._cleanup_tracking(symbol)
            return

        # ═══════════════════════════════════════════════════════════════════
        # BOLUM 2: YENI POZISYON GIRIS KONTROLLERI (8 SETUP)
        # ═══════════════════════════════════════════════════════════════════
        if len(self.paper_trader.open_positions) >= MAX_OPEN_POSITIONS:
            return

        r3, r4, r5 = cam.get("R3", 0), cam.get("R4", 0), cam.get("R5", 0)
        s3, s4, s5 = cam.get("S3", 0), cam.get("S4", 0), cam.get("S5", 0)
        p = cam.get("P", 0)

        # ─────────────────────────────────────────────────────────────────
        # SETUP 1: TAZE R4 BREAKOUT LONG
        # Onceki mum R4 altinda, simdiki mum R4 ustunde kapanir
        # Tepe AVWAP filtresini gecer → Guclu boga teyidi
        # ─────────────────────────────────────────────────────────────────
        if prev_close <= r4 and close_price > r4:
            if tepe_avwap == 0 or close_price > tepe_avwap:
                tp1 = r5 if r5 > close_price else (mvah if mvah > close_price else close_price * 1.01)
                # nPOC veya nVAH hedefi
                candidates = [c for c in [above_npoc, above_nvah] if c and c > tp1]
                tp2 = min(candidates) if candidates else (mvah if mvah > tp1 else None)
                buffer = (r4 - r3) * BUFFER_RATIO
                soft_stop = r4 - buffer
                hard_stop = r3

                await self._handle_open(
                    symbol=symbol, side="LONG", entry_price=close_price,
                    reason="Taze R4 Breakout + Tepe AVWAP Ustu Onay",
                    soft_stop=soft_stop, hard_stop=hard_stop,
                    tp1=tp1, tp2=tp2, trade_type="BREAKOUT",
                    snapshot_levels=levels, setup_id="SETUP_1_R4_BREAKOUT",
                    confluence_list=["R4_Breakout", "Tepe_AVWAP_Ustu"]
                )
                return

        # ─────────────────────────────────────────────────────────────────
        # SETUP 2: TAZE S4 BREAKDOWN SHORT
        # Onceki mum S4 ustunde, simdiki mum S4 altinda kapanir
        # Dip AVWAP filtresini gecer → Guclu ayi teyidi
        # ─────────────────────────────────────────────────────────────────
        if prev_close >= s4 and close_price < s4:
            if dip_avwap == 0 or close_price < dip_avwap:
                tp1 = s5 if s5 < close_price else (mval if (mval > 0 and mval < close_price) else close_price * 0.99)
                candidates = [c for c in [below_npoc, below_nval] if c and c < tp1]
                tp2 = max(candidates) if candidates else (mval if (mval > 0 and mval < tp1) else None)
                buffer = (s3 - s4) * BUFFER_RATIO
                soft_stop = s4 + buffer
                hard_stop = s3

                await self._handle_open(
                    symbol=symbol, side="SHORT", entry_price=close_price,
                    reason="Taze S4 Breakdown + Dip AVWAP Alti Onay",
                    soft_stop=soft_stop, hard_stop=hard_stop,
                    tp1=tp1, tp2=tp2, trade_type="BREAKOUT",
                    snapshot_levels=levels, setup_id="SETUP_2_S4_BREAKDOWN",
                    confluence_list=["S4_Breakdown", "Dip_AVWAP_Alti"]
                )
                return

        # ─────────────────────────────────────────────────────────────────
        # SETUP 3: S3 DESTEK TEPKISI LONG (Scalp — Kademeli Kilit Hedef)
        # Mum S3'e dokunur ama ustunde kapatir, Pivot P altinda
        # ─────────────────────────────────────────────────────────────────
        if current_candle['low'] <= s3 and close_price > s3 and close_price < p:
            buffer = (s3 - s4) * BUFFER_RATIO
            soft_stop = s3 - buffer
            hard_stop = s4
            up_targets = [lvl for lvl in [dip_avwap, tepe_avwap, mpoc, p] if lvl and lvl > close_price * 1.004]
            up_targets.sort()
            tp1 = up_targets[0] if up_targets else p
            tp2 = p if p > tp1 else (mpoc if mpoc > tp1 else None)
            target_name = "AVWAP" if (tp1 in [dip_avwap, tepe_avwap]) else ("mPOC" if tp1 == mpoc else "Pivot P")
            await self._handle_open(
                symbol=symbol, side="LONG", entry_price=close_price,
                reason=f"S3 Destek Sekmesi (İlk Hedef {target_name}: ${tp1:.4f})",
                soft_stop=soft_stop, hard_stop=hard_stop,
                tp1=tp1, tp2=tp2, trade_type="SCALP",
                snapshot_levels=levels, setup_id="SETUP_3_S3_BOUNCE",
                confluence_list=["S3_Support", f"Target_{target_name}"]
            )
            return

        # ─────────────────────────────────────────────────────────────────
        # SETUP 4: R3 DIRENC TEPKISI SHORT (Scalp — Kademeli Kilit Hedef)
        # Mum R3'e dokunur ama altinda kapatir, Pivot P ustunde
        # ─────────────────────────────────────────────────────────────────
        if current_candle['high'] >= r3 and close_price < r3 and close_price > p:
            buffer = (r4 - r3) * BUFFER_RATIO
            soft_stop = r3 + buffer
            hard_stop = r4
            down_targets = [lvl for lvl in [tepe_avwap, dip_avwap, mpoc, p] if lvl and lvl < close_price * 0.996]
            down_targets.sort(reverse=True)
            tp1 = down_targets[0] if down_targets else p
            tp2 = p if p < tp1 else (mpoc if (mpoc > 0 and mpoc < tp1) else None)
            target_name = "AVWAP" if (tp1 in [tepe_avwap, dip_avwap]) else ("mPOC" if tp1 == mpoc else "Pivot P")
            await self._handle_open(
                symbol=symbol, side="SHORT", entry_price=close_price,
                reason=f"R3 Direnc Tepkisi (İlk Hedef {target_name}: ${tp1:.4f})",
                soft_stop=soft_stop, hard_stop=hard_stop,
                tp1=tp1, tp2=tp2, trade_type="SCALP",
                snapshot_levels=levels, setup_id="SETUP_4_R3_REJECTION",
                confluence_list=["R3_Resistance", f"Target_{target_name}"]
            )
            return

        # ─────────────────────────────────────────────────────────────────
        # SETUP 5: R4-R5 DESTEK RETEST LONG (Support Flip)
        # R4 ustunde olan fiyat R4'e geri cekilerek fitil birakir, ustunde kapanir
        # ─────────────────────────────────────────────────────────────────
        if prev_close > r4 and current_candle['low'] <= r4 and close_price > r4 and close_price < r5:
            buffer = (r4 - r3) * BUFFER_RATIO
            soft_stop = r4 - buffer
            hard_stop = r3
            await self._handle_open(
                symbol=symbol, side="LONG", entry_price=close_price,
                reason="R4 Destek Retest Sekmesi (Support Flip)",
                soft_stop=soft_stop, hard_stop=hard_stop,
                tp1=r5, trade_type="SCALP",
                snapshot_levels=levels, setup_id="SETUP_5_R4_SUPPORT_FLIP",
                confluence_list=["R4_Retest", "Support_Flip"]
            )
            return

        # ─────────────────────────────────────────────────────────────────
        # SETUP 6: mVAH KIRILIMI LONG (Macro Breakout)
        # Fiyat aylik VAH'i yukari kirar → Macro trend devami
        # ─────────────────────────────────────────────────────────────────
        if mvah > 0 and prev_close <= mvah and close_price > mvah:
            candidates = [c for c in [above_npoc, above_nvah] if c and c > close_price]
            target = min(candidates) if candidates else close_price * 1.02
            buffer = (r4 - r3) * BUFFER_RATIO if (r4 > r3) else (close_price * 0.005)
            soft_stop = mvah - buffer
            hard_stop = r5 if r5 > 0 else (mvah - buffer * 2)
            await self._handle_open(
                symbol=symbol, side="LONG", entry_price=close_price,
                reason="mVAH Aylik Direnc Kirilimi (Macro Breakout)",
                soft_stop=soft_stop, hard_stop=hard_stop,
                tp1=target, trade_type="BREAKOUT",
                snapshot_levels=levels, setup_id="SETUP_6_MVAH_MACRO_BREAKOUT",
                confluence_list=["mVAH_Breakout", "Volume_Profile_Expansion"]
            )
            return

        # ─────────────────────────────────────────────────────────────────
        # SETUP 7: S4-S5 DIRENC RETEST SHORT (Resistance Flip) [YENİ]
        # S4 altinda olan fiyat S4'e yukselip reddedilir, altinda kapanir
        # ─────────────────────────────────────────────────────────────────
        if prev_close < s4 and current_candle['high'] >= s4 and close_price < s4 and close_price > s5:
            buffer = (s3 - s4) * BUFFER_RATIO
            soft_stop = s4 + buffer
            hard_stop = s3
            await self._handle_open(
                symbol=symbol, side="SHORT", entry_price=close_price,
                reason="S4 Direnc Retest Sekmesi (Resistance Flip)",
                soft_stop=soft_stop, hard_stop=hard_stop,
                tp1=s5, trade_type="SCALP",
                snapshot_levels=levels, setup_id="SETUP_7_S4_RESISTANCE_FLIP",
                confluence_list=["S4_Retest", "Resistance_Flip"]
            )
            return

        # ─────────────────────────────────────────────────────────────────
        # SETUP 8: mVAL KIRILIMI SHORT (Macro Breakdown)
        # Fiyat aylik VAL'i asagi kirar → Macro cokus baslar
        # ─────────────────────────────────────────────────────────────────
        if mval > 0 and prev_close >= mval and close_price < mval:
            candidates = [c for c in [below_npoc, below_nval] if c and c < close_price]
            target = max(candidates) if candidates else close_price * 0.98
            buffer = (s3 - s4) * BUFFER_RATIO if (s3 > s4) else (close_price * 0.005)
            soft_stop = mval + buffer
            hard_stop = s5 if s5 > 0 else (mval + buffer * 2)
            await self._handle_open(
                symbol=symbol, side="SHORT", entry_price=close_price,
                reason="mVAL Aylik Destek Kirilimi (Macro Breakdown)",
                soft_stop=soft_stop, hard_stop=hard_stop,
                tp1=target, trade_type="BREAKOUT",
                snapshot_levels=levels, setup_id="SETUP_8_MVAL_MACRO_BREAKDOWN",
                confluence_list=["mVAL_Breakdown", "Volume_Profile_Collapse"]
            )
            return

        # ─────────────────────────────────────────────────────────────────
        # SETUP 9: AŞAĞI nPOC / nVAL LİKİDİTE SÜPÜRMESİ LONG (Smart Multi-Target)
        # Fiyat önceki günlerin dokunulmamış POC/VAL seviyesine inip fitil bırakır ve üstünde kapatır
        # ─────────────────────────────────────────────────────────────────
        support_npoc = below_npoc if (below_npoc and below_npoc > 0) else below_nval
        if support_npoc and support_npoc > 0 and current_candle['low'] <= support_npoc and close_price > support_npoc and close_price < p:
            buffer = (p - support_npoc) * BUFFER_RATIO if (p > support_npoc) else (support_npoc * 0.004)
            soft_stop = support_npoc - buffer
            hard_stop = s4 if (s4 > 0 and s4 < support_npoc) else (support_npoc - buffer * 2)

            # Smart Multi-Target: En yakin ilk direnci TP1, nihai hedefi TP2 yap
            up_targets = [
                lvl for lvl in [mval, s4, dip_avwap, tepe_avwap, mpoc, s3, p, above_npoc, r3, r4, r5]
                if lvl and lvl > close_price * 1.004
            ]
            up_targets.sort()
            tp1_target = up_targets[0] if up_targets else (p if p > close_price else close_price * 1.01)
            tp2_target = up_targets[-1] if len(up_targets) > 1 else (p if p > tp1_target else None)

            target_name = "mVAL" if tp1_target == mval else ("S4" if tp1_target == s4 else ("AVWAP" if (tp1_target in [dip_avwap, tepe_avwap]) else ("mPOC" if tp1_target == mpoc else ("S3" if tp1_target == s3 else "Pivot P"))))
            reason_text = f"Aşağı nPOC (${support_npoc:.4f}) Sekmesi (İlk Hedef {target_name}: ${tp1_target:.4f})"

            await self._handle_open(
                symbol=symbol, side="LONG", entry_price=close_price,
                reason=reason_text,
                soft_stop=soft_stop, hard_stop=hard_stop,
                tp1=tp1_target, tp2=tp2_target, trade_type="SCALP",
                snapshot_levels=levels, setup_id="SETUP_9_BELOW_NPOC_BOUNCE",
                confluence_list=["nPOC_Sweep", f"Target_{target_name}"]
            )
            return

        # ─────────────────────────────────────────────────────────────────
        # SETUP 10: YUKARI nPOC / nVAH LİKİDİTE REDDİ SHORT (Smart Multi-Target)
        # Fiyat önceki günlerin dokunulmamış POC/VAH seviyesine iğne atıp altında kapatır
        # ─────────────────────────────────────────────────────────────────
        resist_npoc = above_npoc if (above_npoc and above_npoc > 0) else above_nvah
        if resist_npoc and resist_npoc > 0 and current_candle['high'] >= resist_npoc and close_price < resist_npoc and close_price > p:
            buffer = (resist_npoc - p) * BUFFER_RATIO if (resist_npoc > p) else (resist_npoc * 0.004)
            soft_stop = resist_npoc + buffer
            hard_stop = r4 if (r4 > 0 and r4 > resist_npoc) else (resist_npoc + buffer * 2)

            # Smart Multi-Target: En yakin ilk destegi TP1, nihai hedefi TP2 yap
            down_targets = [
                lvl for lvl in [mvah, r4, tepe_avwap, dip_avwap, mpoc, r3, p, below_npoc, s3, s4, s5]
                if lvl and lvl < close_price * 0.996
            ]
            down_targets.sort(reverse=True)
            tp1_target = down_targets[0] if down_targets else (p if p < close_price else close_price * 0.99)
            tp2_target = down_targets[-1] if len(down_targets) > 1 else (p if p < tp1_target else None)

            target_name = "mVAH" if tp1_target == mvah else ("R4" if tp1_target == r4 else ("AVWAP" if (tp1_target in [tepe_avwap, dip_avwap]) else ("mPOC" if tp1_target == mpoc else ("R3" if tp1_target == r3 else "Pivot P"))))
            reason_text = f"Yukarı nPOC (${resist_npoc:.4f}) Reddi (İlk Hedef {target_name}: ${tp1_target:.4f})"

            await self._handle_open(
                symbol=symbol, side="SHORT", entry_price=close_price,
                reason=reason_text,
                soft_stop=soft_stop, hard_stop=hard_stop,
                tp1=tp1_target, tp2=tp2_target, trade_type="SCALP",
                snapshot_levels=levels, setup_id="SETUP_10_ABOVE_NPOC_REJECTION",
                confluence_list=["nPOC_Rejection", f"Target_{target_name}"]
            )
            return
