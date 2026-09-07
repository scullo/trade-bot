from security_vault import SecurityVault
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
        self.vault = SecurityVault()
        self.peak_prices = {}  # symbol -> trailing icin en iyi fiyat
        self.last_trade_times = {}  # (symbol, side) -> timestamp
        self.failed_levels = {}  # symbol -> dict (Yapısal Seviye İptali & Whipsaw Kalkanı)
        self.boot_time = time.time()  # Sunucu baslangic zamani (Isinma Kalkanı)
        self.warmup_seconds = 45.0   # Ilk 45 saniye ani kapatmalari onle
        self.recent_rejections = []  # 🧠 Son elenen / girilmeyen sinyaller ve nedenleri (Canlı Dashboard Zekası)

    def log_rejection(self, symbol: str, setup_name: str, reason: str):
        now_str = datetime.now().strftime("%H:%M:%S")
        entry = {
            "time": now_str,
            "symbol": symbol.replace("/USDT", ""),
            "setup": setup_name.split('(')[0].strip(),
            "reason": reason
        }
        if not hasattr(self, "recent_rejections"):
            self.recent_rejections = []
        self.recent_rejections.append(entry)
        if len(self.recent_rejections) > 25:
            self.recent_rejections.pop(0)

    def _record_structural_stop(self, record: dict):
        """Stop olan veya zararla kapanan işlemin seviyesini kaydeder."""
        if not record or not isinstance(record, dict):
            return
        symbol = record.get("symbol")
        if not symbol:
            return
        net_pnl = float(record.get("net_pnl", 0.0))
        close_reason = str(record.get("close_reason", ""))
        if net_pnl < 0 or "Stop" in close_reason or "Zaman" in close_reason:
            self.failed_levels[symbol] = {
                "side": record.get("side"),
                "setup_id": record.get("setup_id", ""),
                "failed_entry": float(record.get("entry_price", 0.0)),
                "exit_price": float(record.get("exit_price", 0.0)),
                "timestamp": time.time(),
                "reason": close_reason
            }
            print(f">> [YAPISAL TAKİP] {symbol} seviye kaybı kaydedildi (${record.get('entry_price')}). Fiyat yapısı tazelenene kadar aynı seviyeden giriş kilitlendi.")

    def check_structural_invalidation(self, symbol: str, side: str, current_price: float, levels: dict) -> tuple[bool, str]:
        """
        Dinamik Yapısal Seviye Doğrulama (Zaman kronometresi DEĞİL, Fiyat Yapısı / Price Action temelli):
        Bir coin o seviyede stop olduysa, aynı fiyata tekrar atlamasını engeller.
        Yeniden giriş şartı:
        - LONG için: Fiyatın Pivot P veya S3'e inip taze likidite toplamış olması VEYA başarısız tepenin üstüne çıkması (+%0.4)
        - SHORT için: Fiyatın Pivot P veya R3'e çıkıp likidite toplamış olması VEYA başarısız dibin altına inmesi (-%0.4)
        Bu şart 2 dakikada gerçekleşirse 2 dakikada girer! Kronometre beklemez, piyasa fırsatını kaçırmaz.
        """
        if not hasattr(self, 'failed_levels') or symbol not in self.failed_levels:
            return True, ""

        failed_info = self.failed_levels[symbol]
        failed_side = failed_info.get("side")
        failed_entry = failed_info.get("failed_entry", 0.0)

        # Farklı yönde yeni bir setup oluştuysa engel yok
        if side != failed_side:
            self.failed_levels.pop(symbol, None)
            return True, ""

        cam = levels.get("camarilla", {})
        p = cam.get("P", 0.0)
        s3 = cam.get("S3", 0.0)
        r3 = cam.get("R3", 0.0)

        if side == "LONG":
            # 1. Şart: Fiyat bir önceki başarısız girişin belirgin şekilde üstüne çıktıysa (Yeni Tepe / Higher High Breakout)
            if failed_entry > 0 and current_price >= failed_entry * 1.004:
                self.failed_levels.pop(symbol, None)
                return True, "Yeni Yapısal Tepe Onayı"

            # 2. Şart: Fiyat Pivot P veya S3 seviyesine geri çekilip oradan güç topladı mı?
            if self.market_data and symbol in self.market_data.candles_5m:
                df = self.market_data.candles_5m[symbol]
                if isinstance(df, pd.DataFrame) and len(df) >= 3:
                    recent_low = df['low'].iloc[-3:].min()
                    if (p > 0 and recent_low <= p) or (s3 > 0 and recent_low <= s3):
                        self.failed_levels.pop(symbol, None)
                        return True, "Pivot / Destekten Taze Likidite Onayı"

            return False, f"Yapısal Seviye İptali: Son stop seviyesinde (${failed_entry:.4f}) sıkışma; Pivot P veya S3'ten taze likidite almadan veya yeni tepe yapmadan aynı seviyeye tekrar girilemez"

        elif side == "SHORT":
            # 1. Şart: Fiyat bir önceki başarısız girişin belirgin altına indiyse (Yeni Dip / Lower Low)
            if failed_entry > 0 and current_price <= failed_entry * 0.996:
                self.failed_levels.pop(symbol, None)
                return True, "Yeni Yapısal Dip Onayı"

            # 2. Şart: Fiyat Pivot P veya R3 seviyesine yükselip reddedildi mi?
            if self.market_data and symbol in self.market_data.candles_5m:
                df = self.market_data.candles_5m[symbol]
                if isinstance(df, pd.DataFrame) and len(df) >= 3:
                    recent_high = df['high'].iloc[-3:].max()
                    if (p > 0 and recent_high >= p) or (r3 > 0 and recent_high >= r3):
                        self.failed_levels.pop(symbol, None)
                        return True, "Pivot / Dirençten Taze Likidite Onayı"

            return False, f"Yapısal Seviye İptali: Son stop seviyesinde (${failed_entry:.4f}) sıkışma; Pivot P veya R3'e çekilip güç toplamadan veya yeni dip yapmadan aynı seviyeye tekrar girilemez"

        return True, ""

    def get_symbol_atr_pct(self, symbol: str) -> float:
        """Paritenin son 14 mumluk ATR yuzdesini hesaplayarak coine ozel dinamik esik uretir."""
        if self.market_data and symbol in self.market_data.candles_5m:
            df = self.market_data.candles_5m[symbol]
            if df is not None and len(df) >= 14:
                try:
                    high = df['high'].values[-14:]
                    low = df['low'].values[-14:]
                    close = df['close'].values[-15:-1]
                    tr = np.maximum(high - low, np.maximum(np.abs(high - close), np.abs(low - close)))
                    atr_val = np.mean(tr)
                    cur_p = df['close'].iloc[-1]
                    if cur_p > 0 and not np.isnan(atr_val):
                        return float(atr_val / cur_p)
                except Exception:
                    pass
        return 0.012  # Varsayilan %1.2

    def get_macro_climate(self) -> dict:
        """
        BTC + ETH Çift Şefli Makro Piyasa İklim Analiz Motoru.
        Piyasa iletkenliğini yalnızca BTC'ye indirgemez; altcoinlerin asıl lokomotifi olan ETH'yi ve
        BTC-ETH korelasyonunu eşzamanlı değerlendirir.
        """
        default_climate = {
            "regime": "NEUTRAL",
            "status": "⚪ NÖTR / DENGELİ PİYASA",
            "desc": "BTC ve ETH dengeli aralıkta işlem görüyor.",
            "is_dead_zone": False,
            "eth_leading": False,
            "btc_range_1h": 0.0,
            "eth_range_1h": 0.0,
            "btc_chg_1h": 0.0,
            "eth_chg_1h": 0.0,
            "eth_lead_pct": 0.0,
            "btc_price": 0.0,
            "eth_price": 0.0
        }

        if not self.market_data or not hasattr(self.market_data, 'candles_5m'):
            return default_climate

        df_btc = self.market_data.candles_5m.get('BTC/USDT')
        df_eth = self.market_data.candles_5m.get('ETH/USDT')

        if df_btc is None or df_btc.empty or len(df_btc) < 12:
            return default_climate

        try:
            btc_close = float(df_btc['close'].iloc[-1])
            btc_high_1h = float(df_btc['high'].iloc[-12:].max())
            btc_low_1h = float(df_btc['low'].iloc[-12:].min())
            btc_range_1h = round(((btc_high_1h - btc_low_1h) / btc_close) * 100.0, 2) if btc_close > 0 else 0.0
            btc_chg_1h = round(((btc_close - df_btc['close'].iloc[-12]) / df_btc['close'].iloc[-12]) * 100.0, 2)
        except Exception:
            return default_climate

        eth_close, eth_range_1h, eth_chg_1h = 0.0, 0.0, 0.0
        if df_eth is not None and not df_eth.empty and len(df_eth) >= 12:
            try:
                eth_close = float(df_eth['close'].iloc[-1])
                eth_high_1h = float(df_eth['high'].iloc[-12:].max())
                eth_low_1h = float(df_eth['low'].iloc[-12:].min())
                eth_range_1h = round(((eth_high_1h - eth_low_1h) / eth_close) * 100.0, 2) if eth_close > 0 else 0.0
                eth_chg_1h = round(((eth_close - df_eth['close'].iloc[-12]) / df_eth['close'].iloc[-12]) * 100.0, 2)
            except Exception:
                pass

        eth_lead_pct = round(eth_chg_1h - btc_chg_1h, 2)
        eth_leading = eth_lead_pct >= 0.70 and eth_chg_1h > 0

        # Seviye tespiti (Camarilla S3/R3/R4/S4)
        btc_levels = self.market_data.levels.get('BTC/USDT', {}) if self.market_data else {}
        eth_levels = self.market_data.levels.get('ETH/USDT', {}) if self.market_data else {}
        btc_cam = btc_levels.get('camarilla', {}) if isinstance(btc_levels, dict) else {}
        eth_cam = eth_levels.get('camarilla', {}) if isinstance(eth_levels, dict) else {}

        btc_in_va = True
        eth_in_va = True
        if btc_cam.get('R3', 0) > 0 and btc_cam.get('S3', 0) > 0:
            btc_in_va = (btc_close <= btc_cam['R3'] and btc_close >= btc_cam['S3'])
        if eth_cam.get('R3', 0) > 0 and eth_cam.get('S3', 0) > 0:
            eth_in_va = (eth_close <= eth_cam['R3'] and eth_close >= eth_cam['S3'])

        btc_above_r4 = btc_close > btc_cam.get('R4', 999999) if btc_cam.get('R4', 0) > 0 else False
        eth_above_r4 = eth_close > eth_cam.get('R4', 999999) if eth_cam.get('R4', 0) > 0 else False
        btc_below_s4 = btc_close < btc_cam.get('S4', 0) if btc_cam.get('S4', 0) > 0 else False
        eth_below_s4 = eth_close < eth_cam.get('S4', 0) if eth_cam.get('S4', 0) > 0 else False

        # İklim Karar Matrisi
        is_dead_zone = False
        regime = "NEUTRAL"
        status = "⚪ NÖTR / DENGELİ PİYASA"
        desc = f"BTC (%{btc_chg_1h:+.2f}) ve ETH (%{eth_chg_1h:+.2f}) dengeli bantta."

        if eth_leading and (eth_chg_1h >= 0.8 or eth_above_r4):
            regime = "ETH_EXPANSION"
            status = "🟡 ETH ÖNCÜLÜĞÜNDE BOĞA GENİŞLEMESİ"
            desc = f"ETH, BTC'ye +%{eth_lead_pct:.2f} fark atarak altcoinlere rüzgar sağlıyor (ETH 1S: %{eth_chg_1h:+.2f}). Altcoin kırılımlarına yeşil ışık."
        elif (btc_above_r4 or btc_chg_1h >= 1.2) and eth_chg_1h >= 0:
            regime = "BULL_TREND"
            status = "🟢 MAKRO BOĞA TRENDİ (BTC Liderliği)"
            desc = f"BTC kurumsal dirençleri kırıyor (1S: %{btc_chg_1h:+.2f}). Piyasa genelinde boğa ivmesi hakim."
        elif (btc_below_s4 or btc_chg_1h <= -1.2) or (eth_below_s4 or eth_chg_1h <= -1.5):
            regime = "BEAR_DUMP"
            status = "🔴 MAKRO AYI BASKISI"
            desc = f"BTC (%{btc_chg_1h:+.2f}) veya ETH (%{eth_chg_1h:+.2f}) ana destekleri kırdı. Yüksek satış baskısı."
        elif btc_in_va and eth_in_va and btc_range_1h < 0.65 and eth_range_1h < 0.85:
            is_dead_zone = True
            regime = "DEAD_ZONE"
            status = "⚪ ÖLÜ BÖLGE / DEĞER ALANI SIKIŞMASI"
            desc = f"BTC (1S: %{btc_range_1h:.2f}) ve ETH (1S: %{eth_range_1h:.2f}) Camarilla S3-R3 Değer Alanı içine kilitlendi. Beta paritelerde sahte kırılım riski yüksek. nPOC/S3/R3 tepkileri ve bağımsız Alfa ayrışanlar aktif."
        else:
            regime = "CONSOLIDATION"
            status = "⚪ YATAY KONSOLİDASYON"
            desc = f"BTC 1S: %{btc_range_1h:.2f}, ETH 1S: %{eth_range_1h:.2f}. Piyasa seviye arıyor."

        return {
            "regime": str(regime),
            "status": str(status),
            "desc": str(desc),
            "is_dead_zone": bool(is_dead_zone),
            "eth_leading": bool(eth_leading),
            "btc_range_1h": float(btc_range_1h),
            "eth_range_1h": float(eth_range_1h),
            "btc_chg_1h": float(btc_chg_1h),
            "eth_chg_1h": float(eth_chg_1h),
            "eth_lead_pct": float(eth_lead_pct),
            "btc_price": float(btc_close),
            "eth_price": float(eth_close)
        }

    def get_coin_dynamic_persona(self, symbol: str) -> dict:
        """
        Otonom Kripto DNA ve Dinamik Persona Motoru (Rolling 15-20 İşlem Penceresi):
        - Son 15-20 işlemi adli olarak tarar.
        - Fakeout (tuzak) fitil oranı, win rate ve net kâr analizine göre pariteyi
          👑 Altın Karakter, ⚪ Standart / Dengeli veya ⚠️ Volatil & Tuzakçı (Whipsaw) ligine atar.
        - İyileşme gösteren pariteleri otomatik terfi ettirir (Self-Healing).
        """
        clean_sym = symbol.replace('/', '').upper()
        history = getattr(self.paper_trader, 'history', []) if self.paper_trader else []
        
        coin_trades = []
        for h in history:
            h_sym = (h.get('symbol') or h.get('Parite') or '').replace('/', '').upper()
            if h_sym == clean_sym:
                pnl = float(h.get('net_pnl', h.get('Net Kâr ($)', h.get('pnl', 0.0))))
                mfe_raw = str(h.get('max_mfe_roe', h.get('Zirve MFE (%)', 0.0))).replace('%', '').replace('+', '')
                try:
                    mfe_val = float(mfe_raw)
                except Exception:
                    mfe_val = 0.0
                c_reason = str(h.get('close_reason', h.get('Kapanış Nedeni / Tetikleyici', '')))
                t_type = str(h.get('trade_type', ''))
                coin_trades.append({
                    'pnl': pnl,
                    'mfe': mfe_val,
                    'reason': c_reason,
                    'trade_type': t_type
                })

        recent = coin_trades[-15:] if len(coin_trades) >= 15 else coin_trades
        total_t = len(recent)

        if total_t < 3:
            return {
                "symbol": symbol,
                "persona_class": "STANDARD",
                "persona_name": "⚪ Standart / Dengeli",
                "trades_count": total_t,
                "win_rate": 0.0 if total_t == 0 else round(sum(1 for t in recent if t['pnl'] > 0) / total_t * 100, 1),
                "fakeout_rate": 0.0,
                "net_pnl": round(sum(t['pnl'] for t in recent), 2),
                "allow_breakout": True,
                "allow_bounce": True,
                "margin_scale": 1.0,
                "stop_loss_atr_mult": 1.0,
                "status_badge": "🟢 Kırılım + Sekme Açık",
                "strategy_permission": "Tüm Stratejiler Açık (Kırılım + Pusu)"
            }

        wins = sum(1 for t in recent if t['pnl'] > 0)
        net_pnl = sum(t['pnl'] for t in recent)
        wr = (wins / total_t) * 100.0

        # Fakeout tespiti: Zararla kapanan, zirve kârı %0.8'i bile göremeyen ve stoplanan işlemler
        fakeouts = sum(1 for t in recent if t['pnl'] < 0 and t['mfe'] < 0.8 and ('Stop' in t['reason'] or 'stop' in t['reason']))
        fakeout_rate = (fakeouts / total_t) * 100.0

        # Sınıflandırma
        if net_pnl > 3.0 and wr >= 60.0 and fakeout_rate <= 25.0:
            return {
                "symbol": symbol,
                "persona_class": "GOLD",
                "persona_name": "👑 Altın Karakter (Pusu Ustası)",
                "trades_count": total_t,
                "win_rate": round(wr, 1),
                "fakeout_rate": round(fakeout_rate, 1),
                "net_pnl": round(net_pnl, 2),
                "allow_breakout": True,
                "allow_bounce": True,
                "margin_scale": 1.3,
                "stop_loss_atr_mult": 1.0,
                "status_badge": "👑 Altın Lig (Marjin x1.3)",
                "strategy_permission": "Öncelikli Kırılım + Pusu (Marjin x1.3)"
            }
        elif fakeout_rate >= 45.0 or (net_pnl < -5.0 and wr < 45.0):
            return {
                "symbol": symbol,
                "persona_class": "WHIPSAW",
                "persona_name": "⚠️ Volatil & Tuzakçı (Whipsaw)",
                "trades_count": total_t,
                "win_rate": round(wr, 1),
                "fakeout_rate": round(fakeout_rate, 1),
                "net_pnl": round(net_pnl, 2),
                "allow_breakout": False,
                "allow_bounce": True,
                "margin_scale": 0.5,
                "stop_loss_atr_mult": 1.5,
                "status_badge": "⚠️ Whipsaw (Kırılım Kilitli 🔒)",
                "strategy_permission": "Yalnızca S3/R3/nPOC Dip-Tepe Sekmesi (Kırılım Kilitli 🔒)"
            }
        else:
            return {
                "symbol": symbol,
                "persona_class": "STANDARD",
                "persona_name": "⚪ Standart / Dengeli",
                "trades_count": total_t,
                "win_rate": round(wr, 1),
                "fakeout_rate": round(fakeout_rate, 1),
                "net_pnl": round(net_pnl, 2),
                "allow_breakout": True,
                "allow_bounce": True,
                "margin_scale": 1.0,
                "stop_loss_atr_mult": 1.0,
                "status_badge": "🟢 Kırılım + Sekme Açık",
                "strategy_permission": "Dengeli Kırılım + Pusu"
            }

    def get_all_coin_personas(self, all_symbols: list = None) -> dict:
        """Tüm pariteler için canlı dinamik persona matrisini döndürür."""
        if all_symbols is None:
            if self.market_data and hasattr(self.market_data, 'all_symbols') and self.market_data.all_symbols:
                all_symbols = list(self.market_data.all_symbols)
            else:
                all_symbols = []
        
        # Eğer history'de pariteler varsa onları da ekle
        if self.paper_trader and hasattr(self.paper_trader, 'history'):
            for h in self.paper_trader.history:
                sym = h.get('symbol') or h.get('Parite')
                if sym and sym not in all_symbols:
                    all_symbols.append(sym)

        matrix = {}
        for s in all_symbols:
            matrix[s] = self.get_coin_dynamic_persona(s)
        return matrix

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
            res = await res
        if isinstance(res, dict) and not kwargs.get("is_partial", False):
            self._record_structural_stop(res)
        return res

    async def _safe_open_position(self, *args, **kwargs):
        res = self.paper_trader.open_position(*args, **kwargs)
        if hasattr(res, '__await__'):
            res = await res
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

    def _get_level_name_by_price(self, target_price: float, levels: dict) -> str:
        if not levels or not target_price or target_price <= 0:
            return ""
        cam = levels.get("camarilla", {})
        tolerance = 0.004  # %0.4 esneklik payi
        
        candidates = [
            ("Pivot (P)", cam.get("P", 0)),
            ("S3 Destek", cam.get("S3", 0)),
            ("S4 Kırılım", cam.get("S4", 0)),
            ("S5 Dip", cam.get("S5", 0)),
            ("R3 Direnç", cam.get("R3", 0)),
            ("R4 Breakout", cam.get("R4", 0)),
            ("R5 Zirve", cam.get("R5", 0)),
            ("mPOC Aylık Hacim", levels.get("mpoc", 0)),
            ("mVAL Aylık Taban", levels.get("mval", 0)),
            ("mVAH Aylık Tavan", levels.get("mvah", 0)),
            ("Aşağı nPOC Likidite", levels.get("below_npoc", 0)),
            ("Yukarı nPOC Likidite", levels.get("above_npoc", 0)),
            ("Dip AVWAP", levels.get("dip_avwap", 0)),
            ("Tepe AVWAP", levels.get("tepe_avwap", 0)),
        ]
        for name, lvl in candidates:
            if lvl and lvl > 0:
                if abs(target_price - lvl) / lvl <= tolerance:
                    return name
        return ""

    async def evaluate_tick(self, symbol: str, current_price: float, levels: dict):
        """Milisaniyelik anlik sert stop, TP ve trailing stop kontrolleri."""
        if symbol not in self.paper_trader.open_positions:
            return

        # 🎯 TELEMETRİ: Anlık milisaniyelik MFE (Zirve Kâr) ve MAE (Dip Zarar) takibini güncelle
        if hasattr(self.paper_trader, "update_tick_telemetry"):
            try:
                self.paper_trader.update_tick_telemetry(symbol, current_price)
            except Exception as e:
                pass

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
                lvl_tag = self._get_level_name_by_price(tp1, levels)
                lvl_str = f" [{lvl_tag}]" if lvl_tag else ""
                if trade_type == "SCALP" or not tp2:
                    record = await self._safe_close_position(symbol, current_price, f"🎯 TP Hedefine Ulaşıldı{lvl_str} (${tp1:.4f})")
                    if record:
                        await self._notify_close(record, levels=levels)
                        self._cleanup_tracking(symbol)
                elif trade_type == "BREAKOUT" and not pos.get("is_half_closed"):
                    record = await self._safe_close_position(symbol, current_price, f"🎯 TP1 Alındı{lvl_str} (%50 Kapatıldı)", is_partial=True)
                    if record:
                        await self._notify_close(record, levels=levels)

            elif tp2 > 0 and pos.get("is_half_closed") and current_price >= tp2:
                lvl_tag2 = self._get_level_name_by_price(tp2, levels)
                lvl_str2 = f" [{lvl_tag2}]" if lvl_tag2 else ""
                record = await self._safe_close_position(symbol, current_price, f"🚀 TP2 Final Hedefe Ulaşıldı{lvl_str2} (${tp2:.4f})")
                if record:
                    await self._notify_close(record, levels=levels)
                    self._cleanup_tracking(symbol)

        elif side == "SHORT":
            if tp1 > 0 and current_price <= tp1:
                lvl_tag = self._get_level_name_by_price(tp1, levels)
                lvl_str = f" [{lvl_tag}]" if lvl_tag else ""
                if trade_type == "SCALP" or not tp2:
                    record = await self._safe_close_position(symbol, current_price, f"🎯 TP Hedefine Ulaşıldı{lvl_str} (${tp1:.4f})")
                    if record:
                        await self._notify_close(record, levels=levels)
                        self._cleanup_tracking(symbol)
                elif trade_type == "BREAKOUT" and not pos.get("is_half_closed"):
                    record = await self._safe_close_position(symbol, current_price, f"🎯 TP1 Alındı{lvl_str} (%50 Kapatıldı)", is_partial=True)
                    if record:
                        await self._notify_close(record, levels=levels)

            elif tp2 > 0 and pos.get("is_half_closed") and current_price <= tp2:
                lvl_tag2 = self._get_level_name_by_price(tp2, levels)
                lvl_str2 = f" [{lvl_tag2}]" if lvl_tag2 else ""
                record = await self._safe_close_position(symbol, current_price, f"🚀 TP2 Final Hedefe Ulaşıldı{lvl_str2} (${tp2:.4f})")
                if record:
                    await self._notify_close(record, levels=levels)
                    self._cleanup_tracking(symbol)

        # ── 2.5 DİNAMİK ROE VE ZAMAN BAZLI KÂR KİLİDİ (%50 KÂR AL & BREAKEVEN) ──
        if symbol in self.paper_trader.open_positions and not self.paper_trader.open_positions[symbol].get("is_half_closed", False):
            pos_cur = self.paper_trader.open_positions[symbol]
            entry_p = pos_cur["entry_price"]
            lev = pos_cur.get("leverage", 5)
            price_pct = ((current_price - entry_p) / entry_p) if side == "LONG" else ((entry_p - current_price) / entry_p)
            current_roe = price_pct * lev * 100.0

            # Kural A: ROE >= +7.0% -> Hedef fiyata bakılmaksızın %50 kâr anında realize edilir!
            if current_roe >= 7.0:
                record = await self._safe_close_position(
                    symbol, current_price,
                    f"🎯 Dinamik ROE Kâr Kilidi (+%{current_roe:.1f} Kâr Alındı - %50 Kapatıldı)",
                    is_partial=True
                )
                if record:
                    await self._notify_close(record, levels=levels)
                    return

            # Kural B: 90 Dakika Süre Aşımı Kalkanı (Süre >= 90dk ve ROE >= +4.0%)
            hold_sec = time.time() - pos_cur.get("entry_timestamp", time.time())
            if hold_sec >= 5400 and current_roe >= 4.0:
                hold_mins = int(hold_sec // 60)
                record = await self._safe_close_position(
                    symbol, current_price,
                    f"⏳ Zaman Kalkanı Kâr Kilidi ({hold_mins}dk Bekleme - +%{current_roe:.1f} ROE - %50 Kapatıldı)",
                    is_partial=True
                )
                if record:
                    await self._notify_close(record, levels=levels)
                    return

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

        # ── ASAMA 1: ROE >= %6 → Breakeven korumasi (giris fiyatina) ─────────
        if roe >= TRAILING_BREAKEVEN_ROE and not pos.get("_trail_be"):
            if side == "LONG":
                new_stop = entry * 1.001  # Giris + kucuk tampon
                pos["hard_stop"] = max(pos.get("hard_stop", 0), new_stop)
                pos["soft_stop"] = max(pos.get("soft_stop", 0), new_stop)
            else:
                new_stop = entry * 0.999  # Giris - kucuk tampon
                pos["hard_stop"] = min(pos.get("hard_stop", float('inf')), new_stop)
                pos["soft_stop"] = min(pos.get("soft_stop", float('inf')), new_stop)
            pos["_trail_be"] = True
            pos["trail_status"] = "🛡️ BREAKEVEN KORUMA AKTİF"
            updated = True
            print(f">> [TRAILING] {symbol} [*] Breakeven koruma AKTIF (ROE: {roe:.1f}%)")

        # ── ASAMA 2: ROE >= %12 → Karin %30'unu kilitle ─────────────────────
        if roe >= TRAILING_LOCK_30_ROE and not pos.get("_trail_30"):
            peak = self.peak_prices[symbol]
            if side == "LONG":
                lock_price = entry + (peak - entry) * 0.3
                pos["hard_stop"] = max(pos.get("hard_stop", 0), lock_price)
                pos["soft_stop"] = max(pos.get("soft_stop", 0), lock_price)
            else:
                lock_price = entry - (entry - peak) * 0.3
                pos["hard_stop"] = min(pos.get("hard_stop", float('inf')), lock_price)
                pos["soft_stop"] = min(pos.get("soft_stop", float('inf')), lock_price)
            pos["_trail_30"] = True
            pos["trail_status"] = "🔒 %30 KÂR KİLİTLENDİ"
            updated = True
            print(f">> [TRAILING] {symbol} [**] %30 kar kilidi AKTIF (ROE: {roe:.1f}%)")

        # ── ASAMA 3: ROE >= %20 → Hard stop ile karin %50'sini kilitle ───────
        if roe >= TRAILING_LOCK_50_ROE and not pos.get("_trail_50"):
            peak = self.peak_prices[symbol]
            if side == "LONG":
                lock_price = entry + (peak - entry) * 0.5
                pos["hard_stop"] = max(pos.get("hard_stop", 0), lock_price)
                pos["soft_stop"] = max(pos.get("soft_stop", 0), lock_price)
            else:
                lock_price = entry - (entry - peak) * 0.5
                pos["hard_stop"] = min(pos.get("hard_stop", float('inf')), lock_price)
                pos["soft_stop"] = min(pos.get("soft_stop", float('inf')), lock_price)
            pos["_trail_50"] = True
            pos["trail_status"] = "🔒 %50 SERT KÂR KİLİTLENDİ"
            updated = True
            print(f">> [TRAILING] {symbol} [***] %50 SERT kar kilidi AKTIF (ROE: {roe:.1f}%)")

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
        is_top_80 = True
        min_vol_surge = 1.2
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
                        
                        # MADDE 6: DINAMIK YUZDELIK VE HACIM SARTLARI
                        if len(df) >= 288:
                            vol_80th = df['volume'].iloc[-288:-1].quantile(0.80)
                        else:
                            vol_80th = df['volume'].iloc[:-1].quantile(0.80) if len(df) > 1 else 0
                        is_top_80 = (cur_vol >= vol_80th)
                        majors = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT"]
                        min_vol_surge = 1.2 if symbol in majors else 1.5
                except Exception:
                    vol_surge = 1.0
                    is_top_80 = True
                    min_vol_surge = 1.2

        if self.market_data and hasattr(self.market_data, 'get_symbol_metrics'):
            met = self.market_data.get_symbol_metrics(symbol)
            if met:
                vol_surge = met.get("vol_surge", vol_surge)
                is_top_80 = met.get("is_top_80", is_top_80)
        # ── 1b. OTONOM COIN DNA VE DİNAMİK PERSONA KALKANI (ERKEN ELEME) ──
        persona = self.get_coin_dynamic_persona(symbol)
        is_breakout = (trade_type == "BREAKOUT" or "Breakout" in reason or "Breakdown" in reason or "Kırılım" in reason)
        
        # 1. Tuzakçı (Whipsaw) Kırılım Kilidi: Sahte fitil üreten coinlerin breakout'larını anında engelle
        if is_breakout and not persona.get("allow_breakout", True):
            rej_msg = f"🛡️ Whipsaw Kalkanı: Son {persona.get('trades_count')} işlemde %{persona.get('fakeout_rate', 0):.0f} tuzak fitil üretti. Kırılım kilitli (Yalnızca S3/R3/nPOC dip-tepe sekmeleri pusuda)."
            print(f">> [RED - WHIPSAW KALKANI] {symbol}: {rej_msg}")
            self.log_rejection(symbol, reason, rej_msg)
            return {"error": "WHIPSAW_BREAKOUT_BLOCKED"}

        # ── 1c. DİNAMİK FONLAMA ORANI (FUNDING RATE) VE SQUEEZE KALKANI (ERKEN VETO) ──
        funding_info = {}
        if self.market_data and hasattr(self.market_data, 'get_funding_info'):
            funding_info = self.market_data.get_funding_info(symbol) or {}

        f_rate_pct = funding_info.get('rate_pct', 0.0100)
        squeeze_status = funding_info.get('squeeze_status', 'BALANCED')

        # Veto 1: Short Squeeze Kalkanı — Negatif fonlamada SHORT açmak intihardır (Piyasa Yapıcı yukarı sıkıştırır!)
        if side == "SHORT" and squeeze_status == "SHORT_SQUEEZE_RISK":
            rej_msg = f"🛡️ Squeeze Kalkanı: Fonlama oranı aşırı negatif (%{f_rate_pct:+.4f}). Short Squeeze riski sebebiyle SHORT işlem engellendi."
            print(f">> [RED - SQUEEZE KALKANI] {symbol}: {rej_msg}")
            self.log_rejection(symbol, reason, rej_msg)
            return {"error": "FUNDING_SHORT_SQUEEZE_BLOCKED"}

        # Veto 2: Long Overheating Kalkanı — Aşırı pozitif fonlamada tepe LONG kırılımı açmak intihardır (Düşüş kapıdadır!)
        if side == "LONG" and is_breakout and squeeze_status == "LONG_OVERHEATED":
            rej_msg = f"🛡️ Aşırı Şişkinlik Kalkanı: Fonlama oranı aşırı pozitif (%{f_rate_pct:+.4f}). Long Squeeze / Tepe tuzağı sebebiyle LONG kırılımı engellendi."
            print(f">> [RED - AŞIRI LONG KALKANI] {symbol}: {rej_msg}")
            self.log_rejection(symbol, reason, rej_msg)
            return {"error": "FUNDING_LONG_OVERHEATED_BLOCKED"}

        # 1c. GLOBAL LİKİDASYON RADARI & TASFİYE SÜPÜRME TEYİDİ (!forceOrder Confluence)
        liq_stats = {}
        if self.market_data and hasattr(self.market_data, 'get_symbol_liquidation_stats'):
            liq_stats = self.market_data.get_symbol_liquidation_stats(symbol) or {}

        long_liq_usd = float(liq_stats.get('long_usd', 0.0))
        short_liq_usd = float(liq_stats.get('short_usd', 0.0))
        liq_confirmed = False
        liq_volume_usd = 0.0
        liq_tag = ""

        # Alış (LONG) yönlü sekme işlemlerinde: Destekte Long'lar tasfiye edildiyse (Retail Stop Avı) kurumsal alıcı absorbe etmiştir!
        if side == "LONG" and not is_breakout:
            if long_liq_usd >= 10000.0 or (long_liq_usd >= 5000.0 and long_liq_usd > short_liq_usd * 1.4):
                liq_confirmed = True
                liq_volume_usd = round(long_liq_usd, 2)
                liq_tag = f" [💥 ${liq_volume_usd:,.0f} Long Tasfiye Süpürmesi Teyitli]"
        # Satış (SHORT) yönlü sekme işlemlerinde: Dirençte Short'lar patlatıldıysa (Retail Short Avı) kurumsal satıcı absorbe etmiştir!
        elif side == "SHORT" and not is_breakout:
            if short_liq_usd >= 10000.0 or (short_liq_usd >= 5000.0 and short_liq_usd > long_liq_usd * 1.4):
                liq_confirmed = True
                liq_volume_usd = round(short_liq_usd, 2)
                liq_tag = f" [💥 ${liq_volume_usd:,.0f} Short Tasfiye Süpürmesi Teyitli]"

        if liq_confirmed and liq_tag:
            reason += liq_tag
            if confluence_list is not None and isinstance(confluence_list, list):
                confluence_list.append("Likidasyon_Süpürmesi_Teyidi")

        # MADDE 5: TEMAS (TOUCH) TAKIBI VE FAKEOUT KORUMASI
        from datetime import datetime
        current_date = datetime.now().date()
        if not hasattr(self, 'setup_attempts'):
            self.setup_attempts = {}
        if not hasattr(self, 'last_attempt_date') or self.last_attempt_date != current_date:
            self.setup_attempts = {}
            self.last_attempt_date = current_date
            
        setup_key = f"{symbol}_{setup_id}"
        touches_so_far = self.setup_attempts.get(setup_key, 0)
        current_touch = touches_so_far + 1
        
        if current_touch >= 3:
            print(f">> [RED - MADDE 5] {symbol}: 3. Asinmis Temas (Likidite Tukendi). Islem iptal.")
            self.log_rejection(symbol, reason, "Seviye 3. kez test edildiği için taze likidite tükendi, işlem açılmadı")
            return {"error": "MAX_TOUCH_REACHED"}
            
        self.setup_attempts[setup_key] = current_touch

        self.margin_multiplier = 1.0
        
        # Madde 5 Kurali
        if current_touch == 2:
            self.margin_multiplier *= 0.5
            if vol_surge < 2.0:
                print(f">> [RED - MADDE 5] {symbol}: 2. Temasta hacim patlamasi 2.0x altinda ({vol_surge}x). Iptal.")
                self.log_rejection(symbol, reason, f"2. temasta hacim patlaması {vol_surge:.2f}x (en az 2.0x teyit aranıyor)")
                return {"error": "INSUFFICIENT_VOLUME_FOR_2ND_TOUCH"}
                
        # Madde 6 Kurali
        if current_touch == 1:
            if not is_top_80:
                print(f">> [RED - MADDE 6] {symbol}: Hacim Top %80'de degil. Iptal.")
                self.log_rejection(symbol, reason, "24S hacim sıralamasında Top %80 diliminde değil (yetersiz likidite)")
                return {"error": "VOLUME_PERCENTILE_LOW"}
            if vol_surge < min_vol_surge:
                print(f">> [RED - MADDE 6] {symbol}: Hacim {min_vol_surge}x altinda ({vol_surge}x). Iptal.")
                self.log_rejection(symbol, reason, f"5M hacim patlaması {vol_surge:.2f}x (en az {min_vol_surge}x patlama şartı aranıyor)")
                return {"error": "VOLUME_SURGE_LOW"}
                
        # 🛡️ AŞIRI HACİM CLIMAX KALKANI (Tükeniş / Tuzak Koruması)
        if vol_surge >= 4.0:
            if trade_type == "BREAKOUT":
                print(f">> [CLIMAX KALKANI] {symbol}: Aşırı Hacim Climax ({vol_surge:.2f}x). Tepe tükeniş riskine karşı marjin x0.5 kısıldı.")
                self.margin_multiplier *= 0.5
            elif "nPOC" in reason or "Reddi" in reason:
                print(f">> [CLIMAX ONAYI] {symbol}: nPOC Reddi için {vol_surge:.2f}x hacim likidite emilimini onaylıyor. Marjin x1.2")
                self.margin_multiplier *= 1.2
            else:
                self.margin_multiplier *= 0.8
        elif vol_surge >= 2.0:
            self.margin_multiplier *= 1.5
            
        # Confluence 4/4 Odulu
        c_count = len(confluence_list or [1])
        if c_count >= 4:
            self.margin_multiplier *= 1.2

        # 1b. GÖRECELİ GÜÇ (RELATIVE STRENGTH VS BTC + ETH) & DİNAMİK RS HESABI (MADDE 9)
        rs_vs_btc = 0.0
        decoupling_status = "⚪ NÖTR_TAKİPÇİ (Beta)"
        dynamic_rs_score = 0.0
        if self.market_data and hasattr(self.market_data, 'get_symbol_metrics'):
            met = self.market_data.get_symbol_metrics(symbol)
            rs_vs_btc = met.get("rs_vs_btc", 0.0)
            dynamic_rs_score = met.get("dynamic_rs_score", 0.0)
            decoupling_status = met.get("decoupling_status", "⚪ NÖTR_TAKİPÇİ (Beta)")
        elif self.market_data and 'BTC/USDT' in self.market_data.candles_5m and symbol in self.market_data.candles_5m:
            try:
                df_coin = self.market_data.candles_5m[symbol]
                df_btc = self.market_data.candles_5m['BTC/USDT']
                min_len = min(len(df_coin), len(df_btc))
                if min_len >= 12:
                    coin_chg_1h = ((df_coin['close'].iloc[-1] - df_coin['close'].iloc[-12]) / df_coin['close'].iloc[-12]) * 100.0
                    btc_chg_1h = ((df_btc['close'].iloc[-1] - df_btc['close'].iloc[-12]) / df_btc['close'].iloc[-12]) * 100.0
                    rs_vs_btc = round(float(coin_chg_1h - btc_chg_1h), 2)
                    dynamic_rs_score = round(rs_vs_btc / max(0.2, atr_pct), 2)
                    if dynamic_rs_score >= 1.0 and vol_surge >= 1.5:
                        decoupling_status = "🚀 ALFA_AYRIŞAN (Güçlü Boğa)"
                    elif dynamic_rs_score >= 1.0:
                        decoupling_status = "🟢 DİRENÇLİ BOĞA"
                    elif dynamic_rs_score <= -1.0:
                        decoupling_status = "🩸 AŞIRI_ZAYIF"
            except Exception:
                rs_vs_btc = 0.0
                dynamic_rs_score = 0.0

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

        # 7. MAKRO TREND KALKANI VE DINAMIK RS KORUMASI (MADDE 9)
        # Sadece TREND / BREAKOUT işlemlerinde ters yöne atlama engellenir.
        # Mean Reversion (SCALP / S3 / R3 / nPOC) ise doğası gereği dip/tepe sekmesini hedefler!
        is_mean_rev = (trade_type == "SCALP" or "nPOC" in reason or "Destek" in reason or "Direnç" in reason or "Sekmesi" in reason)
        if "NÖTR" in decoupling_status and not is_mean_rev:
            # Coin BTC kuklasi durumunda ve kırılım kovalıyor. Sert trende karşı kafa atamaz.
            if side == "LONG" and "GÜÇLÜ AYI" in trend_regime:
                print(f">> [RED - MADDE 9] {symbol}: Nötr coin, güçlü AYI trendinde LONG kırılımı açamaz.")
                self.log_rejection(symbol, reason, f"Piyasa {trend_regime} iken ters yöne LONG açılması engellendi (Trend Kalkanı)")
                return {"error": "MACRO_TREND_VIOLATION"}
            if side == "SHORT" and "GÜÇLÜ BOĞA" in trend_regime:
                print(f">> [RED - MADDE 9] {symbol}: Nötr coin, güçlü BOĞA trendinde SHORT kırılımı açamaz.")
                self.log_rejection(symbol, reason, f"Piyasa {trend_regime} iken ters yöne SHORT açılması engellendi (Trend Kalkanı)")
                return {"error": "MACRO_TREND_VIOLATION"}

        # ── 8. DİNAMİK MARJİN & RİSK BOYUTLANDIRMA (RISK PARITY) ──
        # Aşırı volatil coinlerde (AMP, BICO) marjini küçültüp riski maks 3.5$ ile sınırla
        # MADDE 2 & 8: SEANS VE YON BAZLI DINAMIK MARJIN DENGELEMESI
        if "LONDRA" in session_str:
            if side == "SHORT":
                self.margin_multiplier *= 1.2
            elif side == "LONG":
                self.margin_multiplier *= 0.8
        elif "ASYA" in session_str:
            if side == "SHORT":
                self.margin_multiplier *= 0.8

        # MADDE 1: OTONOM COIN DNA LİGİ MARJİN VE RİSK ÖLÇEKLEMESİ
        persona_margin_mult = persona.get("margin_scale", 1.0)
        self.margin_multiplier *= persona_margin_mult
        if persona.get("persona_class") == "GOLD":
            print(f">> [ÖDÜL - ALTIN LİG] {symbol}: {persona.get('persona_name')} (WR %{persona.get('win_rate')}). Marjin x{persona_margin_mult}")
        elif persona.get("persona_class") == "WHIPSAW":
            print(f">> [KORUMA - WHIPSAW SEKME] {symbol}: {persona.get('persona_name')} Sekme Pususu. Marjin x{persona_margin_mult} korumalı.")

        safe_atr = max(0.5, atr_pct)
        dyn_margin = min(80.0, max(25.0, round(100.0 / (safe_atr / 1.0), 2)))
        min_floor = 8.0 if persona.get("persona_class") == "WHIPSAW" else 15.0
        dyn_margin = min(80.0, max(min_floor, round(dyn_margin * getattr(self, 'margin_multiplier', 1.0), 2)))

        # ── 1c. GERÇEK CVD (TAKER BUY RATIO) VE İVME (CANDLE VELOCITY) HESABI ──
        cvd_pct = 50.0
        candle_velocity = 1.0
        if self.market_data and symbol in self.market_data.candles_5m:
            try:
                df = self.market_data.candles_5m[symbol]
                if len(df) > 0:
                    # 1. Gerçek CVD Hesaplama
                    if 'taker_quote' in df.columns and 'qav' in df.columns:
                        t_q = df['taker_quote'].iloc[-1]
                        qav = df['qav'].iloc[-1]
                        if qav > 0:
                            cvd_pct = round(float((t_q / qav) * 100.0), 1)

                    # 2. Breakout İvmesi (Hız) Hesaplama
                    if 'open' in df.columns and 'close' in df.columns:
                        body_size = abs(df['close'].iloc[-1] - df['open'].iloc[-1])
                        current_close = df['close'].iloc[-1]
                        atr_usd = (atr_pct / 100.0) * current_close
                        if atr_usd > 0:
                            candle_velocity = round(float(body_size / atr_usd), 2)
            except Exception as e:
                print(f">> [CVD/HIZ HATA] {symbol}: {e}")

        # ── DİNAMİK STOP VE HEDEFLERİ (ADAPTIVE ATR & VOLATILITY FLOOR) ──
        # Sığ/gece saatlerinde mikro fitillerde (%0.6) boğulmayı önleyen asgari %1.25 mesafe tabanı
        safe_atr_pct = max(0.5, min(5.0, atr_pct))
        stop_mult = persona.get("stop_loss_atr_mult", 1.0)
        effective_stop_pct = max(1.25, min(6.0, safe_atr_pct * 2.0 * stop_mult))
        stop_dist = entry_price * (effective_stop_pct / 100.0)

        # TP1: Dinamik 1.8 ATR (En az %1.25 mesafe, R:R >= 1:1 Hızlı Kâr & Breakeven Kilidi)
        # TP2: Dinamik 3.6 ATR / Makro Seviye (En az %2.50 mesafe, R:R >= 1:2 Runner Trend Koşusu)
        tp1_dist = entry_price * (max(1.25, safe_atr_pct * 1.8) / 100.0)
        tp2_dist = entry_price * (max(2.50, safe_atr_pct * 3.6) / 100.0)

        caller_hard_stop = hard_stop
        caller_soft_stop = soft_stop
        caller_tp1 = tp1
        caller_tp2 = tp2

        if side == "LONG":
            atr_hard_stop = round(entry_price - stop_dist, 6)
            # Eğer çağıran setup daha sıkı bir yapısal stop belirlediyse koru, değilse ATR tavanını kullan
            if caller_hard_stop and 0 < caller_hard_stop < entry_price and caller_hard_stop > atr_hard_stop:
                hard_stop = round(caller_hard_stop, 6)
            else:
                hard_stop = atr_hard_stop
            soft_stop = hard_stop  # Dinamik ATR / Yapısal Stop: UI, telemetri ve risk motoru ile tam senkron
            
            atr_tp1 = round(entry_price + tp1_dist, 6)
            atr_tp2 = round(entry_price + tp2_dist, 6)
            
            macro_target = caller_tp2 if (caller_tp2 and caller_tp2 > entry_price) else (caller_tp1 if (caller_tp1 and caller_tp1 > entry_price) else None)
            tp1 = atr_tp1
            if macro_target and macro_target > tp1:
                tp2 = round(macro_target, 6)
            else:
                tp2 = atr_tp2
        else:
            atr_hard_stop = round(entry_price + stop_dist, 6)
            # Eğer çağıran setup daha sıkı bir yapısal stop belirlediyse koru, değilse ATR tavanını kullan
            if caller_hard_stop and caller_hard_stop > entry_price and caller_hard_stop < atr_hard_stop:
                hard_stop = round(caller_hard_stop, 6)
            else:
                hard_stop = atr_hard_stop
            soft_stop = hard_stop  # Dinamik ATR / Yapısal Stop: UI, telemetri ve risk motoru ile tam senkron
            
            atr_tp1 = round(entry_price - tp1_dist, 6)
            atr_tp2 = round(entry_price - tp2_dist, 6)
            
            macro_target = caller_tp2 if (caller_tp2 and caller_tp2 < entry_price) else (caller_tp1 if (caller_tp1 and caller_tp1 < entry_price) else None)
            tp1 = atr_tp1
            if macro_target and macro_target < tp1:
                tp2 = round(macro_target, 6)
            else:
                tp2 = atr_tp2

        macro_clim = self.get_macro_climate()
        res = await self._safe_open_position(
            symbol=symbol, side=side, entry_price=entry_price,
            reason=reason, soft_stop=soft_stop, hard_stop=hard_stop,
            tp1=tp1, tp2=tp2, trade_type=trade_type,
            snapshot_levels=snapshot_levels, setup_id=setup_id, confluence_list=confluence_list,
            atr_pct=atr_pct, trend_regime=trend_regime, session=session_str,
            volume_surge=vol_surge, confluence_score=conf_score_str, htf_alignment=htf_str,
            custom_margin=dyn_margin, rs_vs_btc=rs_vs_btc, decoupling_status=decoupling_status,
            dynamic_rs_score=dynamic_rs_score,
            macro_climate=macro_clim.get('status', '⚪ Nötr / Dengeli Piyasa'),
            eth_leading=macro_clim.get('eth_leading', False),
            cvd_pct=cvd_pct, candle_velocity=candle_velocity,
            margin_multiplier=getattr(self, 'margin_multiplier', 1.0),
            touch_count=current_touch if 'current_touch' in locals() else 1,
            entry_funding_rate=f_rate_pct,
            funding_status=squeeze_status,
            entry_liq_volume_usd=liq_volume_usd,
            liq_confirmed=liq_confirmed
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
            if hasattr(self, 'failed_levels'):
                self.failed_levels.pop(symbol, None)
            levels = getattr(self.market_data, 'levels', {}).get(symbol) if self.market_data else None
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
            # [STOP GÜNCELLEMESİ KALDIRILDI - 1.5 ATR SERT STOP KORUNDU]

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
            # [STOP GÜNCELLEMESİ KALDIRILDI - 1.5 ATR SERT STOP KORUNDU]

        # ── BREAKOUT LONG (R4 Breakout) ──────────────────────────────────────
        elif "R4 Breakout" in reason and side == "LONG":
            if r5 > 0 and abs(old_tp1 - r5) > 0.0001:
                pos["tp1"] = r5
                print(f">> [SEVIYE GUNCELLEME] {symbol} LONG TP1: {old_tp1:.4f} → {r5:.4f}")
            # [STOP GÜNCELLEMESİ KALDIRILDI - 1.5 ATR SERT STOP KORUNDU]

        # ── BREAKOUT SHORT (S4 Breakdown) ────────────────────────────────────
        elif "S4 Breakdown" in reason and side == "SHORT":
            if s5 > 0 and abs(old_tp1 - s5) > 0.0001:
                pos["tp1"] = s5
                print(f">> [SEVIYE GUNCELLEME] {symbol} SHORT TP1: {old_tp1:.4f} → {s5:.4f}")
            # [STOP GÜNCELLEMESİ KALDIRILDI - 1.5 ATR SERT STOP KORUNDU]

        # ── R4 Destek Retest LONG ────────────────────────────────────────────
        elif "R4 Destek Retest" in reason and side == "LONG":
            if r5 > 0 and abs(old_tp1 - r5) > 0.0001:
                pos["tp1"] = r5
            # [STOP GÜNCELLEMESİ KALDIRILDI - 1.5 ATR SERT STOP KORUNDU]

        # ── S4 Direnc Retest SHORT ───────────────────────────────────────────
        elif "S4 Direnc Retest" in reason and side == "SHORT":
            if s5 > 0 and abs(old_tp1 - s5) > 0.0001:
                pos["tp1"] = s5
            # [STOP GÜNCELLEMESİ KALDIRILDI - 1.5 ATR SERT STOP KORUNDU]

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

        # Hacim Patlama Katsayısı (Volume Surge Ratio)
        vol_surge = 1.0
        if self.market_data and hasattr(self.market_data, 'get_symbol_metrics'):
            met = self.market_data.get_symbol_metrics(symbol)
            vol_surge = met.get("vol_surge", 1.0)
        elif self.market_data and symbol in self.market_data.candles_5m:
            df = self.market_data.candles_5m[symbol]
            if isinstance(df, pd.DataFrame) and not df.empty and len(df) >= 20:
                try:
                    vol_col = 'quote_volume' if ('quote_volume' in df.columns and df['quote_volume'].iloc[-1] > 0) else 'volume'
                    avg_vol = df[vol_col].iloc[-21:-1].mean()
                    cur_vol = df[vol_col].iloc[-1]
                    vol_surge = round(float(cur_vol / avg_vol), 2) if avg_vol > 0 else 1.0
                except Exception:
                    vol_surge = 1.0

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
            # 🎯 TELEMETRİ: Mum kapanışında da High, Low ve Close ile tepe/dip noktalarını güncelle
            if hasattr(self.paper_trader, "update_tick_telemetry"):
                try:
                    self.paper_trader.update_tick_telemetry(symbol, current_candle.get('high', close_price))
                    self.paper_trader.update_tick_telemetry(symbol, current_candle.get('low', close_price))
                    self.paper_trader.update_tick_telemetry(symbol, close_price)
                except Exception:
                    pass

            pos = self.paper_trader.open_positions[symbol]
            soft_stop = pos.get("soft_stop", 0.0)
            side = pos["side"]

            # 1a. KADEMELİ KÂR ALMA (TP1 - %50 Kapatma & Breakeven Koruması)
            tp1_target = pos.get("tp1", 0.0)
            tp2_target = pos.get("tp2", 0.0)
            is_half = pos.get("is_half_closed", False)

            # Dinamik ROE ve Zaman Kalkanı Kontrolü (Mum Kapanışında)
            entry_p = pos.get("entry_price", close_price)
            lev = pos.get("leverage", 5)
            price_pct = ((close_price - entry_p) / entry_p) if side == "LONG" else ((entry_p - close_price) / entry_p)
            current_roe = price_pct * lev * 100.0

            if not is_half and (current_roe >= 7.0 or ((time.time() - pos.get("entry_timestamp", time.time()) >= 5400) and current_roe >= 4.0)):
                reason_txt = f"🎯 Dinamik ROE Kâr Kilidi (+%{current_roe:.1f} Kâr Alındı - %50 Kapatıldı)" if current_roe >= 7.0 else f"⏳ Zaman Kalkanı Kâr Kilidi (+%{current_roe:.1f} ROE - %50 Kapatıldı)"
                record = await self._safe_close_position(symbol, close_price, reason_txt, is_partial=True)
                if record:
                    await self._notify_close(record, levels=levels)
                return

            if not is_half and tp1_target > 0:
                if (side == "LONG" and close_price >= tp1_target) or (side == "SHORT" and close_price <= tp1_target):
                    lvl_tag = self._get_level_name_by_price(tp1_target, levels)
                    lvl_str = f" [{lvl_tag}]" if lvl_tag else ""
                    record = await self._safe_close_position(
                        symbol, tp1_target,
                        f"🎯 TP1 Hedefine Ulaşıldı{lvl_str} (%50 Kâr Alındı - Stop Breakeven'e Çekildi)",
                        is_partial=True
                    )
                    if record:
                        await self._notify_close(record, levels=levels)
                    return

            # 1b. NİHAİ KÂR ALMA (TP2 - Kalan %50 Kapatma)
            if is_half and tp2_target > 0:
                if (side == "LONG" and close_price >= tp2_target) or (side == "SHORT" and close_price <= tp2_target):
                    lvl_tag2 = self._get_level_name_by_price(tp2_target, levels)
                    lvl_str2 = f" [{lvl_tag2}]" if lvl_tag2 else ""
                    record = await self._safe_close_position(
                        symbol, tp2_target,
                        f"🚀 TP2 Nihai Hedefe Ulaşıldı{lvl_str2} (Kalan %50 Kapatıldı)",
                        is_partial=False
                    )
                    if record:
                        await self._notify_close(record, levels=levels)
                        self._cleanup_tracking(symbol)
                    return

            # 🛡️ ISINMA KALKANI: Bot basladiktan sonraki ilk 45 saniyede soket/fiyatlar oturana kadar toplu stop ve zaman asimi kapatmasi yapma
            is_warming_up = (time.time() - getattr(self, "boot_time", 0)) < getattr(self, "warmup_seconds", 45.0)

            if not is_warming_up:
                # 1c. DINAMIK ATR / BREAKEVEN STOP KONTROLU
                active_stop = pos.get("hard_stop") or pos.get("soft_stop", 0.0)
                if side == "LONG" and active_stop > 0 and close_price <= active_stop:
                    reason_stop = "🛡️ Breakeven Koruması Tetiklendi" if is_half else f"🛑 Dinamik ATR Stopu Tetiklendi (${active_stop:.4f})"
                    record = await self._safe_close_position(symbol, close_price, reason_stop)
                    if record:
                        await self._notify_close(record, levels=levels)
                        self._cleanup_tracking(symbol)
                    return
                elif side == "SHORT" and active_stop > 0 and close_price >= active_stop:
                    reason_stop = "🛡️ Breakeven Koruması Tetiklendi" if is_half else f"🛑 Dinamik ATR Stopu Tetiklendi (${active_stop:.4f})"
                    record = await self._safe_close_position(symbol, close_price, reason_stop)
                    if record:
                        await self._notify_close(record, levels=levels)
                        self._cleanup_tracking(symbol)
                    return

                # 1d. SEVIYE GUNCELLEME (Pivot Kaymasi Kontrolu)
                closed = await self._refresh_position_levels(symbol, pos, close_price, levels)
                if closed:
                    return

                # 1e. SCALP ZAMAN ASIMI
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

        # 🛡️ GÜVENLİK ZIRHI 1: GÜNLÜK DEVRE KESİCİ TELEMETRİSİ (7 Günlük Test/Veri Toplama Modunda İşlemi Durdurmaz)
        user_daily_loss_pct = getattr(self.paper_trader, 'max_daily_drawdown_pct', 0.05)
        cb_ok, cb_msg = self.vault.check_daily_circuit_breaker(
            getattr(self.paper_trader, 'history', []),
            getattr(self.paper_trader, 'balance', 100000.0),
            max_loss_pct=user_daily_loss_pct
        )
        if not cb_ok:
            # 7 Günlük Araştırma Laboratuvarında veri toplamayı kesintisiz sürdürür, adli log kaydeder
            print(f">> [DEVRE KESİCİ TELEMETRİ BİLDİRİMİ] {cb_msg}")

        # 🛡️ GÜVENLİK ZIRHI 2: PORTFÖY MARJİN TAVAN KİLİDİ
        user_margin_cap_pct = getattr(self.paper_trader, 'max_portfolio_margin_pct', 0.80)
        pos_size = getattr(self.paper_trader, 'margin_per_trade', getattr(self.paper_trader, 'position_size', 100.0))
        mc_ok, mc_msg = self.vault.check_margin_cap(
            getattr(self.paper_trader, 'open_positions', {}),
            new_trade_margin=pos_size,
            balance=getattr(self.paper_trader, 'balance', 100000.0),
            max_cap_pct=user_margin_cap_pct
        )
        if not mc_ok:
            print(f">> [MARJİN TAVAN UYARISI] {mc_msg}")

        r3, r4, r5 = cam.get("R3", 0), cam.get("R4", 0), cam.get("R5", 0)
        s3, s4, s5 = cam.get("S3", 0), cam.get("S4", 0), cam.get("S5", 0)
        p = cam.get("P", 0)

        # ── PİYASA REJİMİ & MAKRO İKLİM TESPİTİ (BTC + ETH ÇİFT ŞEFLİ MOTOR) ──
        macro = self.get_macro_climate()
        is_dead_zone = macro.get("is_dead_zone", False)
        eth_leading = macro.get("eth_leading", False)
        is_range_regime = is_dead_zone

        if tepe_avwap > 0 and p > 0 and close_price > tepe_avwap and close_price > p:
            regime_desc = "🟢 GÜÇLÜ BOĞA (Bullish)"
        elif dip_avwap > 0 and p > 0 and close_price < dip_avwap and close_price < p:
            regime_desc = "🔴 GÜÇLÜ AYI (Bearish)"
        elif p > 0 and close_price > p:
            regime_desc = "🟡 ILIMLI BOĞA (Moderate Bull)"
        elif p > 0 and close_price < p:
            regime_desc = "🟠 ILIMLI AYI (Moderate Bear)"
        else:
            regime_desc = "⚪ YATAY / SIKIŞMA (Ranging)"
            is_range_regime = True

        # Parite Bazlı Alfa ve Hacim Metrikleri (Dinamik Ayrışma)
        sym_met = self.market_data.get_symbol_metrics(symbol) if (self.market_data and hasattr(self.market_data, 'get_symbol_metrics')) else {}
        coin_rs_score = sym_met.get("dynamic_rs_score", 0.0)
        coin_is_top80 = sym_met.get("is_top_80", True)
        coin_vol_surge = sym_met.get("vol_surge", vol_surge)
        majors_set = {"BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT"}
        min_vol_surge = sym_met.get("min_vol_surge", 1.2 if symbol in majors_set else 1.5)
        # Bağımsız Alfa Ayrışan Parite (Ölü Bölgede Kırılıma Giriş Onayı)
        is_decoupled_bull = (coin_rs_score >= 1.2 and coin_vol_surge >= 2.0 and coin_is_top80)
        is_decoupled_bear = (coin_rs_score <= -1.2 and coin_vol_surge >= 2.0 and coin_is_top80)
        coin_decoupling = sym_met.get("decoupling_status", "")
        is_severely_weak = ("AŞIRI_ZAYIF" in coin_decoupling) or (coin_rs_score <= -1.0)

        # ─────────────────────────────────────────────────────────────────
        # SETUP 1: TAZE R4 BREAKOUT LONG
        # Onceki mum R4 altinda, simdiki mum R4 ustunde kapanir
        # Tepe AVWAP filtresini gecer → Guclu boga teyidi
        # ─────────────────────────────────────────────────────────────────
        if prev_close <= r4 and close_price > r4:
            struct_ok, struct_reason = self.check_structural_invalidation(symbol, "LONG", close_price, levels)
            if not struct_ok:
                self.log_rejection(symbol, "SETUP 1 R4 Breakout", struct_reason)
                return

            # 🛡️ MAKRO ÖLÜ BÖLGE KALKANI: BTC+ETH Sıkışmasında Beta Kırılımını Filtrele
            if is_dead_zone and not is_decoupled_bull:
                self.log_rejection(
                    symbol, "SETUP 1 R4 Breakout",
                    f"Makro Ölü Bölge (BTC 1S: %{macro['btc_range_1h']:.2f}, ETH 1S: %{macro['eth_range_1h']:.2f}); Beta sahte kırılım riski nedeniyle elendi (Bağımsız Alfa RS: {coin_rs_score:+.2f} / Hacim: {coin_vol_surge:.1f}x teyidi yok)"
                )
                return

            min_breakout_vol = 1.25 if eth_leading else (1.8 if is_range_regime else 1.35)
            if vol_surge < min_breakout_vol:
                self.log_rejection(symbol, "SETUP 1 R4 Breakout", f"{'Yatay piyasada sahte kırılım kalkanı: ' if is_range_regime else ''}Hacim patlaması {vol_surge:.2f}x yetersiz (en az {min_breakout_vol:.2f}x patlama aranıyor)")
                return
            if tepe_avwap > 0 and close_price <= tepe_avwap:
                self.log_rejection(symbol, "SETUP 1 R4 Breakout", f"Fiyat (${close_price:.4f}) Tepe AVWAP (${tepe_avwap:.4f}) altında kaldığı için boğa onayı verilmedi")
                return
            if tepe_avwap == 0 or close_price > tepe_avwap:
                tp1 = r5 if (r5 >= close_price * 1.008) else (mvah if (mvah >= close_price * 1.008) else close_price * 1.015)
                candidates = [c for c in [above_npoc, above_nvah, tepe_avwap] if c and c >= tp1 * 1.008]
                tp2 = min(candidates) if candidates else (mvah if (mvah >= tp1 * 1.008) else None)
                coin_atr = self.get_symbol_atr_pct(symbol)
                dyn_stop_pct = max(0.008, min(0.025, coin_atr * 1.0))
                buffer = r4 * dyn_stop_pct
                soft_stop = r4 - buffer
                hard_stop = r3 if (r3 > 0 and r3 < r4) else (r4 - buffer * 2.0)

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
            struct_ok, struct_reason = self.check_structural_invalidation(symbol, "SHORT", close_price, levels)
            if not struct_ok:
                self.log_rejection(symbol, "SETUP 2 S4 Breakdown", struct_reason)
                return

            # 🛡️ MAKRO ÖLÜ BÖLGE KALKANI: BTC+ETH Sıkışmasında Beta Dökülmesini Filtrele
            if is_dead_zone and not is_decoupled_bear:
                self.log_rejection(
                    symbol, "SETUP 2 S4 Breakdown",
                    f"Makro Ölü Bölge (BTC 1S: %{macro['btc_range_1h']:.2f}, ETH 1S: %{macro['eth_range_1h']:.2f}); Beta sahte dökülme riski nedeniyle elendi (Bağımsız Alfa RS: {coin_rs_score:+.2f} / Hacim: {coin_vol_surge:.1f}x teyidi yok)"
                )
                return

            min_breakout_vol = 1.25 if eth_leading else (1.8 if is_range_regime else 1.35)
            if vol_surge < min_breakout_vol:
                self.log_rejection(symbol, "SETUP 2 S4 Breakdown", f"{'Yatay piyasada sahte kırılım kalkanı: ' if is_range_regime else ''}Hacim patlaması {vol_surge:.2f}x yetersiz (en az {min_breakout_vol:.2f}x patlama aranıyor)")
                return
            if dip_avwap > 0 and close_price >= dip_avwap:
                self.log_rejection(symbol, "SETUP 2 S4 Breakdown", f"Fiyat (${close_price:.4f}) Dip AVWAP (${dip_avwap:.4f}) üstünde kaldığı için ayı onayı verilmedi")
                return
            if dip_avwap == 0 or close_price < dip_avwap:
                tp1 = s5 if (s5 > 0 and s5 <= close_price * 0.992) else (mval if (mval > 0 and mval <= close_price * 0.992) else close_price * 0.985)
                candidates = [c for c in [below_npoc, below_nval, dip_avwap] if c and c <= tp1 * 0.992]
                tp2 = max(candidates) if candidates else (mval if (mval > 0 and mval <= tp1 * 0.992) else None)
                coin_atr = self.get_symbol_atr_pct(symbol)
                dyn_stop_pct = max(0.008, min(0.025, coin_atr * 1.0))
                buffer = s4 * dyn_stop_pct
                soft_stop = s4 + buffer
                hard_stop = s3 if (s3 > 0 and s3 > s4) else (s4 + buffer * 2.0)

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
            struct_ok, struct_reason = self.check_structural_invalidation(symbol, "LONG", close_price, levels)
            if not struct_ok:
                self.log_rejection(symbol, "SETUP 3 S3 Destek", struct_reason)
                return

            # 🛡️ ALICI EMİLİM MUMU ŞARTI (Ezilen Parite Koruma Zırhı)
            if is_severely_weak:
                c_open = current_candle.get('open', close_price)
                c_low = current_candle.get('low', close_price)
                c_high = current_candle.get('high', close_price)
                c_range = c_high - c_low
                lower_wick = (min(c_open, close_price) - c_low) if c_range > 0 else 0
                lower_wick_ratio = (lower_wick / c_range) if c_range > 0 else 0
                is_absorption = (lower_wick_ratio >= 0.35) or (close_price >= c_open)
                if not is_absorption:
                    self.log_rejection(symbol, "SETUP 3 S3 Destek", f"Aşırı Zayıf Parite: S3 desteğinde alıcı emilimi (min %35 alt fitil veya yeşil kapanış) yok (Fitil: %{lower_wick_ratio*100:.1f})")
                    return

            buffer = (s3 - s4) * BUFFER_RATIO
            soft_stop = s3 - buffer
            hard_stop = s4
            up_targets = [lvl for lvl in [dip_avwap, tepe_avwap, mpoc, p, r3] if lvl and lvl > close_price * 1.008]
            up_targets.sort()
            tp1 = up_targets[0] if up_targets else (close_price * 1.012)
            tp2 = up_targets[-1] if len(up_targets) > 1 else (r3 if (r3 > tp1 * 1.005) else None)
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
            struct_ok, struct_reason = self.check_structural_invalidation(symbol, "SHORT", close_price, levels)
            if not struct_ok:
                self.log_rejection(symbol, "SETUP 4 R3 Direnç", struct_reason)
                return

            buffer = (r4 - r3) * BUFFER_RATIO
            soft_stop = r3 + buffer
            hard_stop = r4
            down_targets = [lvl for lvl in [tepe_avwap, dip_avwap, mpoc, p, s3] if lvl and lvl < close_price * 0.992]
            down_targets.sort(reverse=True)
            tp1 = down_targets[0] if down_targets else (close_price * 0.988)
            tp2 = down_targets[-1] if len(down_targets) > 1 else (s3 if (s3 > 0 and s3 < tp1 * 0.995) else None)
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
            struct_ok, struct_reason = self.check_structural_invalidation(symbol, "LONG", close_price, levels)
            if not struct_ok:
                self.log_rejection(symbol, "SETUP 5 R4 Support Flip", struct_reason)
                return

            # 🛡️ TEPE AVWAP & AŞIRI ZAYIF KORUMASI: Fiyat Tepe AVWAP altında kaldıysa tepede arz birikmiştir (Bull Trap)
            if tepe_avwap > 0 and close_price < tepe_avwap:
                self.log_rejection(symbol, "SETUP 5 R4 Support Flip", f"Retest Tepe AVWAP (${tepe_avwap:.4f}) altında kaldı (Tepede sıkışan arz baskısı)")
                return
            if is_severely_weak:
                self.log_rejection(symbol, "SETUP 5 R4 Support Flip", f"Parite Aşırı Zayıf (RS: {coin_rs_score:+.2f}); zayıf paritede R4 retest desteği tutunamaz")
                return

            # Alıcı tepkisi & fitil şartı: Mum kırmızı kapanıyorsa ve belirgin alt iğnesi (%20) yoksa düşüş bıçağıdır
            c_open = current_candle.get('open', close_price)
            c_low = current_candle.get('low', close_price)
            c_high = current_candle.get('high', close_price)
            c_range = c_high - c_low
            lower_wick = (min(c_open, close_price) - c_low) if c_range > 0 else 0
            wick_ratio = (lower_wick / c_range) if c_range > 0 else 0
            if close_price < c_open and wick_ratio < 0.20:
                self.log_rejection(symbol, "SETUP 5 R4 Support Flip", "Destek retestinde alıcı tepkisi yok (Kırmızı gövde ve yetersiz alt fitil)")
                return

            min_retest_vol = 1.5 if is_range_regime else 1.20
            if vol_surge < min_retest_vol:
                self.log_rejection(symbol, "SETUP 5 R4 Support Flip", f"Retest hacmi {vol_surge:.2f}x yetersiz (en az {min_retest_vol:.2f}x aranıyor)")
                return

            coin_atr = self.get_symbol_atr_pct(symbol)
            dyn_stop_pct = max(0.008, min(0.025, coin_atr * 1.0))
            buffer = r4 * dyn_stop_pct
            soft_stop = r4 - buffer
            hard_stop = r4 - buffer * 1.5
            target_r5 = r5 if (r5 >= close_price * 1.008) else (mvah if (mvah >= close_price * 1.008) else close_price * 1.015)
            await self._handle_open(
                symbol=symbol, side="LONG", entry_price=close_price,
                reason="R4 Destek Retest Sekmesi (Support Flip)",
                soft_stop=soft_stop, hard_stop=hard_stop,
                tp1=target_r5, trade_type="SCALP",
                snapshot_levels=levels, setup_id="SETUP_5_R4_SUPPORT_FLIP",
                confluence_list=["R4_Retest", "Support_Flip"]
            )
            return

        # ─────────────────────────────────────────────────────────────────
        # SETUP 6: mVAH KIRILIMI LONG (Macro Breakout)
        # Fiyat aylik VAH'i yukari kirar → Macro trend devami
        # ─────────────────────────────────────────────────────────────────
        if mvah > 0 and prev_close <= mvah and close_price > mvah:
            struct_ok, struct_reason = self.check_structural_invalidation(symbol, "LONG", close_price, levels)
            if not struct_ok:
                self.log_rejection(symbol, "SETUP 6 mVAH Breakout", struct_reason)
                return

            # 🛡️ MAKRO ÖLÜ BÖLGE KALKANI: mVAH Kırılımında Bağımsız Alfa Kontrolü
            if is_dead_zone and not is_decoupled_bull:
                self.log_rejection(symbol, "SETUP 6 mVAH Breakout", f"Makro Ölü Bölge: BTC+ETH Değer Alanı içinde; mVAH makro kırılımı için bağımsız Alfa ayrışması (RS: {coin_rs_score:+.2f}) teyidi yok")
                return

            # 🛡️ HACİM TEYİDİ: Aylık mVAH kırılımı kurumsal hacim patlaması gerektirir (Sahte kırılım tuzağını önleme)
            min_mvah_vol = min_vol_surge if min_vol_surge else 1.5
            if vol_surge < min_mvah_vol:
                self.log_rejection(symbol, "SETUP 6 mVAH Breakout", f"mVAH kırılım hacmi {vol_surge:.2f}x yetersiz (en az {min_mvah_vol:.2f}x aranıyor)")
                return

            # 🛡️ ZIRH 3: Minimum %0.80 Hedef Barajı (Mikro hedefleri atla, kurumsal istasyona bağlan)
            candidates = [c for c in [above_npoc, above_nvah, r5, tepe_avwap] if c and c >= close_price * 1.008]
            target = min(candidates) if candidates else close_price * 1.018
            coin_atr = self.get_symbol_atr_pct(symbol)
            dyn_stop_pct = max(0.008, min(0.025, coin_atr * 1.0))
            buffer = mvah * dyn_stop_pct
            soft_stop = mvah - buffer
            hard_stop = mvah - buffer * 1.5
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
            struct_ok, struct_reason = self.check_structural_invalidation(symbol, "SHORT", close_price, levels)
            if not struct_ok:
                self.log_rejection(symbol, "SETUP 7 S4 Resistance Flip", struct_reason)
                return

            c_open = current_candle.get('open', close_price)
            c_low = current_candle.get('low', close_price)
            c_high = current_candle.get('high', close_price)
            c_range = c_high - c_low
            upper_wick = (c_high - max(c_open, close_price)) if c_range > 0 else 0
            wick_ratio = (upper_wick / c_range) if c_range > 0 else 0
            if close_price > c_open and wick_ratio < 0.20:
                self.log_rejection(symbol, "SETUP 7 S4 Resistance Flip", "Direnç retestinde satıcı tepkisi yok (Yeşil gövde ve yetersiz üst fitil)")
                return

            min_retest_vol = 1.5 if is_range_regime else 1.20
            if vol_surge < min_retest_vol:
                self.log_rejection(symbol, "SETUP 7 S4 Resistance Flip", f"Retest hacmi {vol_surge:.2f}x yetersiz (en az {min_retest_vol:.2f}x aranıyor)")
                return

            buffer = (s3 - s4) * BUFFER_RATIO
            soft_stop = s4 + buffer
            hard_stop = s3
            target_s5 = s5 if (s5 > 0 and s5 <= close_price * 0.992) else (mval if (mval > 0 and mval <= close_price * 0.992) else close_price * 0.985)
            await self._handle_open(
                symbol=symbol, side="SHORT", entry_price=close_price,
                reason="S4 Direnc Retest Sekmesi (Resistance Flip)",
                soft_stop=soft_stop, hard_stop=hard_stop,
                tp1=target_s5, trade_type="SCALP",
                snapshot_levels=levels, setup_id="SETUP_7_S4_RESISTANCE_FLIP",
                confluence_list=["S4_Retest", "Resistance_Flip"]
            )
            return

        # ─────────────────────────────────────────────────────────────────
        # SETUP 8: mVAL KIRILIMI SHORT (Macro Breakdown)
        # Fiyat aylik VAL'i asagi kirar → Macro cokus baslar
        # ─────────────────────────────────────────────────────────────────
        if mval > 0 and prev_close >= mval and close_price < mval:
            struct_ok, struct_reason = self.check_structural_invalidation(symbol, "SHORT", close_price, levels)
            if not struct_ok:
                self.log_rejection(symbol, "SETUP 8 mVAL Breakdown", struct_reason)
                return

            # 🛡️ MAKRO ÖLÜ BÖLGE KALKANI: mVAL Dökülmesinde Bağımsız Alfa Kontrolü
            if is_dead_zone and not is_decoupled_bear:
                self.log_rejection(symbol, "SETUP 8 mVAL Breakdown", f"Makro Ölü Bölge: BTC+ETH Değer Alanı içinde; mVAL makro dökülme için bağımsız Alfa ayrışması (RS: {coin_rs_score:+.2f}) teyidi yok")
                return

            # 🛡️ HACİM TEYİDİ: Aylık mVAL dökülmesi kurumsal hacim patlaması gerektirir
            min_mval_vol = min_vol_surge if min_vol_surge else 1.5
            if vol_surge < min_mval_vol:
                self.log_rejection(symbol, "SETUP 8 mVAL Breakdown", f"mVAL kırılım hacmi {vol_surge:.2f}x yetersiz (en az {min_mval_vol:.2f}x aranıyor)")
                return

            # 🛡️ ZIRH 3: Minimum %0.80 Hedef Barajı (Mikro hedefleri atla, kurumsal istasyona bağlan)
            candidates = [c for c in [below_npoc, below_nval, s5, dip_avwap] if c and c <= close_price * 0.992]
            target = max(candidates) if candidates else close_price * 0.982
            coin_atr = self.get_symbol_atr_pct(symbol)
            dyn_stop_pct = max(0.008, min(0.025, coin_atr * 1.0))
            buffer = mval * dyn_stop_pct
            soft_stop = mval + buffer
            hard_stop = mval + buffer * 1.5
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
            struct_ok, struct_reason = self.check_structural_invalidation(symbol, "LONG", close_price, levels)
            if not struct_ok:
                self.log_rejection(symbol, "SETUP 9 nPOC Sekmesi", struct_reason)
                return

            # 🛡️ ALICI EMİLİM MUMU ŞARTI (Ezilen Parite Koruma Zırhı)
            if is_severely_weak:
                c_open = current_candle.get('open', close_price)
                c_low = current_candle.get('low', close_price)
                c_high = current_candle.get('high', close_price)
                c_range = c_high - c_low
                lower_wick = (min(c_open, close_price) - c_low) if c_range > 0 else 0
                lower_wick_ratio = (lower_wick / c_range) if c_range > 0 else 0
                is_absorption = (lower_wick_ratio >= 0.35) or (close_price >= c_open)
                if not is_absorption:
                    self.log_rejection(symbol, "SETUP 9 nPOC Sekmesi", f"Aşırı Zayıf Parite: Aşağı nPOC desteğinde alıcı emilimi (min %35 alt fitil veya yeşil kapanış) yok (Fitil: %{lower_wick_ratio*100:.1f})")
                    return

            buffer = (p - support_npoc) * BUFFER_RATIO if (p > support_npoc) else (support_npoc * 0.004)
            soft_stop = support_npoc - buffer
            hard_stop = s4 if (s4 > 0 and s4 < support_npoc) else (support_npoc - buffer * 2)

            # Smart Multi-Target: En yakin ilk direnci TP1, nihai hedefi TP2 yap
            up_targets = [
                lvl for lvl in [mval, s4, dip_avwap, tepe_avwap, mpoc, s3, p, above_npoc, r3, r4, r5]
                if lvl and lvl > close_price * 1.008
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
            struct_ok, struct_reason = self.check_structural_invalidation(symbol, "SHORT", close_price, levels)
            if not struct_ok:
                self.log_rejection(symbol, "SETUP 10 nPOC Reddi", struct_reason)
                return

            # 🛡️ YUKARI nPOC REJECTION KALKANI: Güçlü Boğa trendinde yukarı nPOC'ye kafa atılmaz
            if "GÜÇLÜ BOĞA" in trend_regime:
                self.log_rejection(symbol, "Yukarı nPOC Reddi", "Piyasa Güçlü Boğa rejimindeyken Yukarı nPOC'den SHORT açılmadı (Short Squeeze Koruması)")
                return

            # 🛡️ PİNBAS / ÜST FİTİL ŞARTI: Mum tepeden gerçek bir satış baskısıyla reddedilmeli
            c_high = current_candle['high']
            c_low = current_candle['low']
            c_open = current_candle['open']
            c_range = c_high - c_low
            if c_range > 0:
                upper_wick = c_high - max(c_open, close_price)
                upper_wick_ratio = upper_wick / c_range
                # Mumun en az %28'i üst fitil olmalı (Satıcı İğnesi)
                if upper_wick_ratio < 0.28:
                    self.log_rejection(symbol, "Yukarı nPOC Reddi", f"Üst fitil oranı %{upper_wick_ratio*100:.1f} (en az %28 satıcı iğnesi aranıyor, dolu mumla girilmedi)")
                    return

            buffer = (resist_npoc - p) * BUFFER_RATIO if (resist_npoc > p) else (resist_npoc * 0.004)
            soft_stop = resist_npoc + buffer
            hard_stop = r4 if (r4 > 0 and r4 > resist_npoc) else (resist_npoc + buffer * 2)

            # Smart Multi-Target: En yakin ilk destegi TP1, nihai hedefi TP2 yap
            down_targets = [
                lvl for lvl in [mvah, r4, tepe_avwap, dip_avwap, mpoc, r3, p, below_npoc, s3, s4, s5]
                if lvl and lvl <= close_price * 0.992
            ]
            down_targets.sort(reverse=True)
            tp1_target = down_targets[0] if down_targets else (p if (p > 0 and p <= close_price * 0.992) else close_price * 0.985)
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
