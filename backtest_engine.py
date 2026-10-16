"""
🛡️ VALKYRIE QUANT DESK - KURUMSAL BACKTEST VE OUT-OF-SAMPLE (OOS) DOĞRULAMA MOTORU
================================================================================
Aşırı uydurma (overfitting), komisyon erimesi ve geçmiş veriye sahte uyum risklerini
matematiksel olarak tespit eden, In-Sample (%70) vs. Out-of-Sample (%30) doğrulama altyapısı.

Özellikler:
1. Gerçekçi Binance Vadeli Taker Komisyon Modeli (%0.05 giriş + %0.05 çıkış = %0.10 notional)
2. Gerçekçi Kayma (Slippage) Modeli (%0.02)
3. 5x Kaldıraç ve Risk Paritesi Modellemesi
4. Camarilla H4/L4 Kırılım & H3/L3 Ortalama Dönüş Strateji Taklidi
5. Walk-Forward / Zaman Serisi Kronolojik Ayrımı (Asla veri karıştırma / lookahead bias yok)
6. Bozulma İndeksi (Degradation Ratio): Sharpe_OOS / Sharpe_IS
7. Komisyon Tuzağı ve Aşırı Uydurma Erken Uyarı Sistemi
"""

import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import json
import math
import argparse
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Optional, Any

import numpy as np
import pandas as pd

from valkyrie_logger import get_logger

logger = get_logger("backtest_engine")


class ValkyrieBacktestEngine:
    def __init__(
        self,
        symbol: str = "BTC/USDT",
        initial_balance: float = 10000.0,
        leverage: int = 5,
        position_margin: float = 100.0,
        commission_rate: float = 0.0005,  # 0.05% per leg (Binance Futures VIP0 taker)
        slippage_rate: float = 0.0002,    # 0.02% per leg
        oos_ratio: float = 0.30,          # %30 Out-of-Sample test penceresi
        enable_camarilla_breakout: bool = True,
        enable_mean_reversion: bool = True
    ):
        self.symbol = symbol
        self.initial_balance = float(initial_balance)
        self.leverage = int(leverage)
        self.position_margin = float(position_margin)
        self.commission_rate = float(commission_rate)
        self.slippage_rate = float(slippage_rate)
        self.oos_ratio = float(oos_ratio)
        self.enable_camarilla_breakout = enable_camarilla_breakout
        self.enable_mean_reversion = enable_mean_reversion

    @staticmethod
    def generate_synthetic_klines(days: int = 60, interval_minutes: int = 5, seed: int = 42) -> pd.DataFrame:
        """
        Borsaya bağlanılamadığı veya çevrimdışı testlerde kullanılmak üzere
        volatilite kümelenmesi (GARCH-benzeri) ve trend sıçramaları içeren
        gerçekçi 5 dakikalık mum veri seti üretir.
        """
        np.random.seed(seed)
        total_bars = int((days * 24 * 60) / interval_minutes)
        now_ts = int(datetime.now(timezone.utc).timestamp())
        start_ts = now_ts - (total_bars * interval_minutes * 60)

        # Başlangıç fiyatı $65,000 (BTC ölçeği)
        p = 65000.0
        prices = [p]
        vols = [0.002]  # Bar volatilitesi

        for _ in range(1, total_bars):
            # Volatilite kümelenmesi
            last_vol = vols[-1]
            new_vol = max(0.0008, min(0.008, 0.92 * last_vol + 0.08 * np.random.exponential(0.002)))
            vols.append(new_vol)
            
            # Rejim kayması ve sıçrama (jump diffusion)
            jump = 0.0
            if np.random.rand() < 0.005:  # %0.5 ihtimalle haber/tasfiye şoku
                jump = np.random.normal(0, new_vol * 4)

            ret = np.random.normal(0.00002, new_vol) + jump
            p = max(100.0, p * math.exp(ret))
            prices.append(p)

        timestamps = [start_ts + (i * interval_minutes * 60) for i in range(total_bars)]
        
        opens, highs, lows, closes, volumes = [], [], [], [], []
        for i, center_p in enumerate(prices):
            bar_vol = vols[i]
            o = center_p * (1.0 + np.random.normal(0, bar_vol * 0.3))
            c = center_p * (1.0 + np.random.normal(0, bar_vol * 0.3))
            h = max(o, c) * (1.0 + abs(np.random.normal(0, bar_vol * 0.5)))
            l = min(o, c) * (1.0 - abs(np.random.normal(0, bar_vol * 0.5)))
            v = float(np.random.gamma(shape=3.0, scale=15.0) * (center_p * 0.01))

            opens.append(o)
            highs.append(h)
            lows.append(l)
            closes.append(c)
            volumes.append(v)

        df = pd.DataFrame({
            'timestamp': timestamps,
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'volume': volumes
        })
        return df

    @staticmethod
    def fetch_binance_klines(symbol: str = "BTC/USDT", timeframe: str = "5m", limit: int = 1500) -> Optional[pd.DataFrame]:
        """Binance vadeli borsasından gerçek geçmiş mum verilerini çeker."""
        try:
            import ccxt
            exchange = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'future'}})
            raw_klines = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            if raw_klines and len(raw_klines) > 50:
                df = pd.DataFrame(raw_klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = df[col].astype(float)
                df['timestamp'] = df['timestamp'].astype(int) // 1000
                logger.info(f"Binance'ten {len(df)} adet gerçek {timeframe} mumu indirildi ({symbol}).")
                return df
        except Exception as e:
            logger.warning(f"Binance geçmiş veri indirme hatası: {e}. Sentetik veri üretimine geçiliyor...")
        return None

    @staticmethod
    def calculate_indicators(df: pd.DataFrame, camarilla_lookback: int = 72) -> pd.DataFrame:
        """Backtest mumları için ATR, RVOL, EMA ve Camarilla seviyelerini hesaplar."""
        df = df.copy()
        
        # 1. 14 Periyotluk ATR
        tr1 = df['high'] - df['low']
        tr2 = (df['high'] - df['close'].shift(1)).abs()
        tr3 = (df['low'] - df['close'].shift(1)).abs()
        df['tr'] = np.maximum(tr1, np.maximum(tr2, tr3))
        df['atr_14'] = df['tr'].rolling(window=14, min_periods=1).mean()
        df['atr_pct'] = df['atr_14'] / df['close']

        # 2. RVOL (Relative Volume - 20 periyotluk hacim ortalamasına oran)
        vol_ma = df['volume'].rolling(window=20, min_periods=1).mean()
        df['rvol'] = df['volume'] / np.maximum(1.0, vol_ma)

        # 3. EMA 20 & EMA 50 Trend Filtresi
        df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()

        # 4. Dinamik Seans / İntraday Camarilla Seviyeleri (1 mum ötelenmiş)
        lb = max(12, int(camarilla_lookback))
        roll_h = df['high'].shift(1).rolling(window=lb, min_periods=12).max()
        roll_l = df['low'].shift(1).rolling(window=lb, min_periods=12).min()
        roll_c = df['close'].shift(1)
        rng = roll_h - roll_l
        rng = np.where(rng <= 0, 0.001, rng)

        df['cam_p'] = (roll_h + roll_l + roll_c) / 3.0
        df['cam_r3'] = roll_c + rng * 1.1 / 4.0
        df['cam_r4'] = roll_c + rng * 1.1 / 2.0
        df['cam_s3'] = roll_c - rng * 1.1 / 4.0
        df['cam_s4'] = roll_c - rng * 1.1 / 2.0

        return df

    def run_simulation(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Verilen OHLCV verisi üzerinde In-Sample ve Out-of-Sample simülasyonunu çalıştırır.
        """
        df_ind = self.calculate_indicators(df)
        total_len = len(df_ind)
        if total_len < 100:
            raise ValueError(f"Yetersiz mum verisi: {total_len} (En az 100 mum gerekli)")

        # Zaman serisini böl (Asla shuffle yapılmaz)
        oos_count = int(total_len * self.oos_ratio)
        is_count = total_len - oos_count

        df_is = df_ind.iloc[:is_count].copy().reset_index(drop=True)
        df_oos = df_ind.iloc[is_count:].copy().reset_index(drop=True)

        logger.info(f"Backtest Başlatıldı: Toplam Mum={total_len}, IS Mum={len(df_is)}, OOS Mum={len(df_oos)}")

        is_results = self._simulate_segment(df_is, segment_name="IN_SAMPLE")
        oos_results = self._simulate_segment(df_oos, segment_name="OUT_OF_SAMPLE")

        # Bozulma ve Aşırı Uydurma Metrikleri
        sharpe_is = is_results.get("sharpe_ratio", 0.0)
        sharpe_oos = oos_results.get("sharpe_ratio", 0.0)
        
        # Bozulma İndeksi (Degradation Index)
        if sharpe_is > 0:
            degradation = max(0.0, sharpe_oos) / max(0.01, sharpe_is)
        else:
            degradation = 1.0 if sharpe_oos >= 0 else 0.0

        # Durum sınıflandırması
        if degradation >= 0.70 and oos_results.get("net_pnl", 0) > 0:
            health_status = "ROBUST_EDGE"
            health_label = "SAĞLAM VE DAYANIKLI (ROBUST)"
        elif degradation >= 0.40 and oos_results.get("net_pnl", 0) > 0:
            health_status = "MODERATE_DECAY"
            health_label = "KABUL EDİLEBİLİR ERİME (MODERATE DECAY)"
        else:
            health_status = "OVERFITTED_DANGER"
            health_label = "AŞIRI UYDURULMUŞ / TEHLİKELİ (OVERFITTED)"

        total_net_pnl = is_results.get("net_pnl", 0) + oos_results.get("net_pnl", 0)
        total_fees = is_results.get("total_commission", 0) + oos_results.get("total_commission", 0)
        
        fee_trap = total_fees > abs(total_net_pnl) and total_net_pnl <= 0

        summary = {
            "symbol": self.symbol,
            "total_bars": total_len,
            "is_bars": len(df_is),
            "oos_bars": len(df_oos),
            "initial_balance": self.initial_balance,
            "leverage": self.leverage,
            "commission_rate_pct": self.commission_rate * 100.0,
            "slippage_rate_pct": self.slippage_rate * 100.0,
            "in_sample": is_results,
            "out_of_sample": oos_results,
            "combined": {
                "total_trades": is_results.get("total_trades", 0) + oos_results.get("total_trades", 0),
                "total_net_pnl": round(total_net_pnl, 2),
                "total_commission_paid": round(total_fees, 2),
                "degradation_index": round(degradation, 3),
                "health_status": health_status,
                "health_label": health_label,
                "fee_trap_detected": fee_trap
            }
        }

        return summary

    def _simulate_segment(self, df: pd.DataFrame, segment_name: str) -> Dict[str, Any]:
        """Tek bir zaman dilimi (IS veya OOS) üzerinde bar-by-bar emir eşleşmesi."""
        balance = self.initial_balance
        open_pos: Optional[Dict[str, Any]] = None
        closed_trades: List[Dict[str, Any]] = []

        # Minimum ısınma süresi (24 mum)
        for i in range(24, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i - 1]
            cur_price = float(row['close'])
            high = float(row['high'])
            low = float(row['low'])

            # 1. Açık Pozisyon Yönetimi (SL / TP1 / TP2 kontrolü)
            if open_pos is not None:
                side = open_pos['side']
                entry_p = open_pos['entry_price']
                sl = open_pos['sl']
                tp1 = open_pos['tp1']
                tp2 = open_pos['tp2']
                notional = open_pos['notional']
                pos_margin = open_pos['margin']

                is_closed = False
                exit_price = cur_price
                exit_reason = ""

                if side == "LONG":
                    # Stop Tetiklenmesi
                    if low <= sl:
                        exit_price = sl * (1.0 - self.slippage_rate)
                        exit_reason = "STOP_LOSS"
                        is_closed = True
                    # TP2 (Tam Kapanış)
                    elif tp2 and high >= tp2:
                        exit_price = tp2 * (1.0 - self.slippage_rate)
                        exit_reason = "TAKE_PROFIT_2"
                        is_closed = True
                    # TP1 (Kısmi Kapanış / BE çekme)
                    elif tp1 and high >= tp1 and not open_pos.get('tp1_hit', False):
                        open_pos['tp1_hit'] = True
                        open_pos['sl'] = entry_p  # Breakeven stop'a çek
                        # %50 kâr realizasyonu
                        part_notional = notional * 0.5
                        pnl_tp1 = (tp1 - entry_p) / entry_p * part_notional
                        fee_tp1 = part_notional * self.commission_rate
                        open_pos['realized_partial_pnl'] = pnl_tp1 - fee_tp1
                        open_pos['notional'] = notional * 0.5
                        balance += (pnl_tp1 - fee_tp1)

                elif side == "SHORT":
                    if high >= sl:
                        exit_price = sl * (1.0 + self.slippage_rate)
                        exit_reason = "STOP_LOSS"
                        is_closed = True
                    elif tp2 and low <= tp2:
                        exit_price = tp2 * (1.0 + self.slippage_rate)
                        exit_reason = "TAKE_PROFIT_2"
                        is_closed = True
                    elif tp1 and low <= tp1 and not open_pos.get('tp1_hit', False):
                        open_pos['tp1_hit'] = True
                        open_pos['sl'] = entry_p
                        part_notional = notional * 0.5
                        pnl_tp1 = (entry_p - tp1) / entry_p * part_notional
                        fee_tp1 = part_notional * self.commission_rate
                        open_pos['realized_partial_pnl'] = pnl_tp1 - fee_tp1
                        open_pos['notional'] = notional * 0.5
                        balance += (pnl_tp1 - fee_tp1)

                if is_closed:
                    # Kalan pozisyonu kapat
                    rem_notional = open_pos['notional']
                    if side == "LONG":
                        gross_pnl = ((exit_price - entry_p) / entry_p) * rem_notional
                    else:
                        gross_pnl = ((entry_p - exit_price) / entry_p) * rem_notional

                    exit_commission = rem_notional * self.commission_rate
                    total_comm = open_pos['entry_commission'] + exit_commission
                    net_trade_pnl = gross_pnl + open_pos.get('realized_partial_pnl', 0.0) - exit_commission
                    
                    balance += (gross_pnl - exit_commission)

                    closed_trades.append({
                        "side": side,
                        "entry_price": entry_p,
                        "exit_price": exit_price,
                        "exit_reason": exit_reason,
                        "gross_pnl": gross_pnl,
                        "net_pnl": net_trade_pnl,
                        "commission": total_comm,
                        "bars_held": i - open_pos['entry_bar']
                    })
                    open_pos = None

            # 2. Yeni Giriş Sinyali Taraması (Yalnızca açık pozisyon yokken)
            if open_pos is None:
                atr = float(row['atr_14'])
                atr_p = float(row['atr_pct'])
                rvol = float(row['rvol'])
                cam_r4 = float(row['cam_r4'])
                cam_s4 = float(row['cam_s4'])
                cam_r3 = float(row['cam_r3'])
                cam_s3 = float(row['cam_s3'])
                prev_c = float(prev_row['close'])

                # Sinyal 1: Camarilla H4 Breakout LONG
                if self.enable_camarilla_breakout and prev_c < cam_r4 and cur_price >= cam_r4 and rvol >= 1.2:
                    entry_p = cur_price * (1.0 + self.slippage_rate)
                    sl = max(entry_p * 0.98, cam_r3)
                    tp1 = entry_p + (entry_p - sl) * 1.5
                    tp2 = entry_p + (entry_p - sl) * 3.0
                    notional = self.position_margin * self.leverage
                    entry_comm = notional * self.commission_rate
                    balance -= entry_comm

                    open_pos = {
                        "side": "LONG",
                        "entry_price": entry_p,
                        "sl": sl,
                        "tp1": tp1,
                        "tp2": tp2,
                        "margin": self.position_margin,
                        "notional": notional,
                        "entry_commission": entry_comm,
                        "entry_bar": i,
                        "tp1_hit": False,
                        "realized_partial_pnl": 0.0
                    }

                # Sinyal 2: Camarilla L4 Breakdown SHORT
                elif self.enable_camarilla_breakout and prev_c > cam_s4 and cur_price <= cam_s4 and rvol >= 1.2:
                    entry_p = cur_price * (1.0 - self.slippage_rate)
                    sl = min(entry_p * 1.02, cam_s3)
                    tp1 = entry_p - (sl - entry_p) * 1.5
                    tp2 = entry_p - (sl - entry_p) * 3.0
                    notional = self.position_margin * self.leverage
                    entry_comm = notional * self.commission_rate
                    balance -= entry_comm

                    open_pos = {
                        "side": "SHORT",
                        "entry_price": entry_p,
                        "sl": sl,
                        "tp1": tp1,
                        "tp2": tp2,
                        "margin": self.position_margin,
                        "notional": notional,
                        "entry_commission": entry_comm,
                        "entry_bar": i,
                        "tp1_hit": False,
                        "realized_partial_pnl": 0.0
                    }

                # Sinyal 3: Mean Reversion L3 Bounce LONG
                elif self.enable_mean_reversion and low <= cam_s3 and cur_price > cam_s3 and rvol < 2.5:
                    entry_p = cur_price * (1.0 + self.slippage_rate)
                    sl = cam_s4
                    tp1 = entry_p + (entry_p - sl) * 1.5
                    tp2 = float(row['cam_p'])
                    notional = self.position_margin * self.leverage
                    entry_comm = notional * self.commission_rate
                    balance -= entry_comm

                    open_pos = {
                        "side": "LONG",
                        "entry_price": entry_p,
                        "sl": sl,
                        "tp1": tp1,
                        "tp2": tp2,
                        "margin": self.position_margin,
                        "notional": notional,
                        "entry_commission": entry_comm,
                        "entry_bar": i,
                        "tp1_hit": False,
                        "realized_partial_pnl": 0.0
                    }

                # Sinyal 4: Mean Reversion H3 Reject SHORT
                elif self.enable_mean_reversion and high >= cam_r3 and cur_price < cam_r3 and rvol < 2.5:
                    entry_p = cur_price * (1.0 - self.slippage_rate)
                    sl = cam_r4
                    tp1 = entry_p - (sl - entry_p) * 1.5
                    tp2 = float(row['cam_p'])
                    notional = self.position_margin * self.leverage
                    entry_comm = notional * self.commission_rate
                    balance -= entry_comm

                    open_pos = {
                        "side": "SHORT",
                        "entry_price": entry_p,
                        "sl": sl,
                        "tp1": tp1,
                        "tp2": tp2,
                        "margin": self.position_margin,
                        "notional": notional,
                        "entry_commission": entry_comm,
                        "entry_bar": i,
                        "tp1_hit": False,
                        "realized_partial_pnl": 0.0
                    }

        # İstatistiksel Hesaplamalar
        tot_trades = len(closed_trades)
        if tot_trades == 0:
            return {
                "segment": segment_name,
                "total_trades": 0,
                "win_rate_pct": 0.0,
                "net_pnl": 0.0,
                "profit_factor": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown_pct": 0.0,
                "total_commission": 0.0
            }

        wins = [t for t in closed_trades if t['net_pnl'] > 0]
        losses = [t for t in closed_trades if t['net_pnl'] <= 0]
        win_rate = (len(wins) / tot_trades) * 100.0

        gross_wins = sum(t['net_pnl'] for t in wins)
        gross_losses = abs(sum(t['net_pnl'] for t in losses))
        profit_factor = (gross_wins / max(0.001, gross_losses)) if gross_losses > 0 else 99.0

        net_pnl = sum(t['net_pnl'] for t in closed_trades)
        total_comm = sum(t['commission'] for t in closed_trades)

        # Drawdown Hesaplaması
        equity_curve = [self.initial_balance]
        c_bal = self.initial_balance
        for t in closed_trades:
            c_bal += t['net_pnl']
            equity_curve.append(c_bal)

        eq_series = pd.Series(equity_curve)
        peak = eq_series.cummax()
        dd = (eq_series - peak) / peak
        max_dd_pct = abs(float(dd.min())) * 100.0

        # Sharpe Oranı (İşlem getirileri bazında)
        returns = [t['net_pnl'] / self.position_margin for t in closed_trades]
        mean_ret = np.mean(returns)
        std_ret = np.std(returns)
        if std_ret > 0:
            # Yıllıklandırma çarpanı (yaklaşık 500 işlem/yıl kabulü)
            sharpe = (mean_ret / std_ret) * math.sqrt(min(500, tot_trades * 4))
        else:
            sharpe = 0.0

        return {
            "segment": segment_name,
            "total_trades": tot_trades,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate_pct": round(win_rate, 2),
            "gross_profit": round(gross_wins, 2),
            "gross_loss": round(gross_losses, 2),
            "net_pnl": round(net_pnl, 2),
            "net_pnl_pct": round((net_pnl / self.initial_balance) * 100.0, 2),
            "total_commission": round(total_comm, 2),
            "profit_factor": round(profit_factor, 2),
            "sharpe_ratio": round(sharpe, 2),
            "max_drawdown_pct": round(max_dd_pct, 2),
            "avg_trade_pnl": round(net_pnl / tot_trades, 2)
        }

    def print_ascii_report(self, results: Dict[str, Any]):
        """Terminal için kurumsal karşılaştırma tablosu yazdırır."""
        is_r = results['in_sample']
        oos_r = results['out_of_sample']
        comb = results['combined']

        print("\n" + "=" * 88)
        print(f"🛡️  VALKYRIE QUANT DESK - IN-SAMPLE VS OUT-OF-SAMPLE DOĞRULAMA MOTORU")
        print(f"   Parite: {results['symbol']} | Kaldıraç: {results['leverage']}x | Taker Fee: %{results['commission_rate_pct']:.2f}")
        print("=" * 88)
        print(f"{'Metrik':<30} | {'In-Sample (%70)':<22} | {'Out-of-Sample (%30)':<22} | {'Değerlendirme'}")
        print("-" * 88)
        print(f"{'Toplam İşlem Sayısı':<30} | {is_r.get('total_trades', 0):<22} | {oos_r.get('total_trades', 0):<22} | Toplam: {comb.get('total_trades', 0)}")
        print(f"{'Kazanma Oranı (Win Rate)':<30} | %{is_r.get('win_rate_pct', 0.0):<21.2f} | %{oos_r.get('win_rate_pct', 0.0):<21.2f} | Fark: %{oos_r.get('win_rate_pct', 0) - is_r.get('win_rate_pct', 0):+.2f}")
        print(f"{'Net Kâr / Zarar ($)':<30} | ${is_r.get('net_pnl', 0.0):<21.2f} | ${oos_r.get('net_pnl', 0.0):<21.2f} | Toplam: ${comb.get('total_net_pnl', 0.0):+.2f}")
        print(f"{'Ödenen Borsa Komisyonu':<30} | ${is_r.get('total_commission', 0.0):<21.2f} | ${oos_r.get('total_commission', 0.0):<21.2f} | Toplam: ${comb.get('total_commission_paid', 0.0):.2f}")
        print(f"{'Kâr Faktörü (Profit Factor)':<30} | {is_r.get('profit_factor', 0.0):<22.2f} | {oos_r.get('profit_factor', 0.0):<22.2f} | Eşik: >1.25")
        print(f"{'Sharpe Oranı':<30} | {is_r.get('sharpe_ratio', 0.0):<22.2f} | {oos_r.get('sharpe_ratio', 0.0):<22.2f} | Bozulma: {comb.get('degradation_index', 0.0):.2f}")
        print(f"{'Maksimum Düşüş (Max DD)':<30} | %{is_r.get('max_drawdown_pct', 0.0):<21.2f} | %{oos_r.get('max_drawdown_pct', 0.0):<21.2f} | Risk Sınırı: <%10")
        print("=" * 88)
        print(f"📊 SONUÇ VE TEŞHİS: {comb.get('health_label')}")
        if comb.get('fee_trap_detected'):
            print("⚠️ [KOMİSYON TUZAĞI TESPİT EDİLDİ]: Ödenen komisyon brüt kârı aşıyor. Taker emri yerine maker/limit kullanılmalı!")
        if comb.get('health_status') == "OVERFITTED_DANGER":
            print("❌ [AŞIRI UYDURMA UYARISI]: Strateji Out-of-Sample veride çöktü. Parametreler geçmiş veriye aşırı uydurulmuş!")
        else:
            print("✅ [DOĞRULAMA BAŞARILI]: Strateji Out-of-Sample veride istatistiksel üstünlüğünü koruyor.")
        print("=" * 88 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Valkyrie Quant Desk - In-Sample / Out-of-Sample Backtest Engine")
    parser.add_argument("--symbol", type=str, default="BTC/USDT", help="İşlem yapılacak parite")
    parser.add_argument("--days", type=int, default=60, help="Test edilecek gün sayısı")
    parser.add_argument("--leverage", type=int, default=5, help="Kaldıraç çarpanı (varsayılan: 5x)")
    parser.add_argument("--margin", type=float, default=100.0, help="İşlem başına margin (USD)")
    parser.add_argument("--oos-ratio", type=float, default=0.30, help="Out-of-sample oranı (varsayılan: 0.30)")
    parser.add_argument("--lookback", type=int, default=72, help="Camarilla seans mum sayısı (varsayılan: 72 = 6 saat)")
    parser.add_argument("--fetch-binance", action="store_true", help="Binance Vadeli borsasından canlı veri çek")
    parser.add_argument("--export", type=str, default="backtest_results.json", help="Raporun kaydedileceği JSON dosya yolu")
    args = parser.parse_args()

    engine = ValkyrieBacktestEngine(
        symbol=args.symbol,
        leverage=args.leverage,
        position_margin=args.margin,
        oos_ratio=args.oos_ratio
    )

    df = None
    if args.fetch_binance:
        df = engine.fetch_binance_klines(symbol=args.symbol, timeframe="5m", limit=1500)
    
    if df is None or df.empty:
        df = engine.generate_synthetic_klines(days=args.days)

    results = engine.run_simulation(df)
    engine.print_ascii_report(results)

    if args.export:
        with open(args.export, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f">> [RAPOR KAYDEDİLDİ]: {args.export}")


if __name__ == "__main__":
    main()
