"""
VALKYRIE MASTER V4.0 - ÖNCELİK 1 TEST SÜİTİ
Kasa Koruması & Sermaye Kanamasını Bitirme Matematiksel ve Kuant Kanıtı

1.1 "Bağımsız Alfa" Sızıntısının Kapatılması:
    - Gaussian Z-Score Canlı Log-Return Dağılımı (Z_RS = (R_i - μ_RS) / σ_RS)
    - Ekstrem Gauss Ayrışması (Z_RS >= +2.0σ)
    - Coinbase Prime Akıllı Para Confluence Şartı
    - Makro Ayı Tavan Marjin Kelepçesi (Max 0.50x)

1.2 Setup 9 (nPOC Altı Düşen Bıçak) L2 Absorpsiyon Kalkanı:
    - L2 Alıcı Duvarı Oranı (>= 1.40x)
    - 60 Saniyelik Mikro-CVD Dönüşü (>= %52)
    - Absorpsiyon Olmayan Düşen Bıçakların %100 Reddedilmesi
"""

import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

import unittest
from unittest.mock import MagicMock, AsyncMock
import pandas as pd
import numpy as np
import time

from market_data import MarketDataManager
from strategy import StrategyEngine


class TestPriority1CapitalPreservation(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.md = MarketDataManager(all_symbols=['BTC/USDT', 'ETH/USDT', 'SOL/USDT'])
        
        self.mock_pt = MagicMock()
        self.mock_pt.open_positions = {}
        self.mock_pt.balance = 10000.0
        self.mock_pt.initial_balance = 10000.0
        self.mock_pt.daily_pnl = 0.0
        self.mock_pt.total_pnl = 0.0
        self.mock_pt.open_position = MagicMock(return_value={"orderId": 12345, "status": "FILLED"})
        
        self.mock_notifier = AsyncMock()
        self.mock_notifier.notify_position_opened = AsyncMock()
        self.mock_notifier.notify_position_closed = AsyncMock()
        self.mock_notifier.notify_insufficient_balance = AsyncMock()

        self.strat = StrategyEngine(self.mock_pt, self.mock_notifier, self.md)
        self.strat.rejections = []
        if hasattr(self.strat, 'vault') and self.strat.vault:
            self.strat.vault.check_daily_circuit_breaker = MagicMock(return_value=(True, "OK"))
            self.strat.vault.check_margin_cap = MagicMock(return_value=(True, "OK"))

    def test_01_gaussian_zscore_universe_calculation(self):
        """1.1 KANIT: 100 paritelik evrende son 15m log-return dağılımı ve Z-Score doğrulaması."""
        np.random.seed(42)
        base_returns = np.random.normal(loc=-0.01, scale=0.005, size=100)
        
        self.md.candles_5m = {}
        for i in range(100):
            sym = f"COIN{i}/USDT"
            r = base_returns[i]
            p0 = 100.0
            p3 = p0 * np.exp(r)
            df = pd.DataFrame({
                'open': [p0, p0, p0, p3],
                'high': [p0*1.01, p0*1.01, p0*1.01, p3*1.01],
                'low': [p0*0.99, p0*0.99, p0*0.99, p3*0.99],
                'close': [p0, p0*0.998, p0*0.995, p3],
                'volume': [1000.0, 1000.0, 1000.0, 1000.0]
            })
            self.md.candles_5m[sym] = df

        # ALPHA/USDT'yi bağımsız ekstrem ralli yapan parite yap (+2.5 sigma)
        mu = np.mean(base_returns)
        sigma = np.std(base_returns)
        target_ret = mu + 2.5 * sigma
        p0 = 100.0
        p3 = p0 * np.exp(target_ret)
        self.md.candles_5m["ALPHA/USDT"] = pd.DataFrame({
            'open': [p0, p0, p0, p3],
            'high': [p0*1.01, p0*1.01, p0*1.01, p3*1.01],
            'low': [p0*0.99, p0*0.99, p0*0.99, p3*0.99],
            'close': [p0, p0, p0, p3],
            'volume': [5000.0, 5000.0, 5000.0, 5000.0]
        })

        alpha_res = self.md.get_universe_log_return_zscore("ALPHA/USDT")
        self.assertGreaterEqual(alpha_res["z_score"], 2.0, "ALPHA/USDT Z-Score >= +2.0σ olmalıdır!")
        self.assertTrue(alpha_res["is_extreme_divergence"], "Ekstrem Gauss ayrışması True olmalıdır!")

        # Normal gecikmeli coin kontrolü (COIN10)
        norm_res = self.md.get_universe_log_return_zscore("COIN10/USDT")
        self.assertLess(norm_res["z_score"], 2.0, "Normal coin Z-Score < +2.0σ olmalıdır!")
        self.assertFalse(norm_res["is_extreme_divergence"], "Normal coinde ekstrem ayrışma False olmalıdır!")

    async def test_02_macro_bear_independent_alpha_gate_blocks_lagging_coins(self):
        """1.1 KANIT: Makro Ayı altında Z_RS < +2.0 olan veya Coinbase Prime onaysız Long'ların bloke edilmesi."""
        symbol = "LAGCOIN/USDT"
        
        # Makro Ayı Rejimi: BTC 4S %-2.5 düşüşte
        macro = {"btc_chg_4h": -2.5, "btc_chg_1h": -1.2, "regime": "BEAR_DUMP", "status": "BEAR_DUMP"}
        self.strat.get_macro_climate = MagicMock(return_value=macro)
        self.strat.get_market_trend_regime = MagicMock(return_value="⚪ YATAY / SIKIŞMA (Ranging)")

        # Taze OBI derinliği (Isınma korumasını geçmesi için)
        self.md.get_orderbook_depth = MagicMock(return_value={
            "symbol": symbol, "bid_qty": 1000.0, "ask_qty": 1000.0, "ratio": 1.0,
            "wall_side": "BALANCED", "wall_duration_sec": 10.0, "last_update": time.time()
        })
        self.md.get_symbol_metrics = MagicMock(return_value={
            "vol_surge": 1.40, "atr_pct": 1.0, "dynamic_rs_score": 0.0, "rs_zscore": 0.8,
            "decoupling_status": "⚪ NÖTR_TAKİPÇİ"
        })
        self.strat.get_coin_dynamic_persona = MagicMock(return_value={"min_confluence": 3})

        # Z-Score sadece +0.8σ (Eski sistemde statik RS 0.25'ten geçerdi!)
        self.md.get_universe_log_return_zscore = MagicMock(return_value={
            "symbol": symbol, "z_score": 0.8, "is_extreme_divergence": False
        })
        self.md.get_symbol_cvd = MagicMock(return_value={"ratio_60s": 50.0})
        self.md.get_coinbase_lead_lag = MagicMock(return_value={
            "direction": "NEUTRAL", "status": "⚪ DENGELİ", "spread_bps": 0.0, "is_listed": True,
            "last_update": time.time(), "age_seconds": 5.0
        })

        # Counter-trend DIP long denemesi (SCALP dip sekmesi, 2 ortogonal confluence < min 4)
        res = await self.strat._handle_open(
            symbol=symbol, side="LONG", entry_price=10.0,
            hard_stop=9.8, soft_stop=9.85, tp1=10.3, tp2=10.5,
            trade_type="SCALP",
            reason="S3 Destek Sekmesi", setup_id="SETUP_3_S3_BOUNCE",
            confluence_list=["Destek_Bounce", "CVD_Flow"]  # Fiyat + Akış ekseni (2/4 < 4/4 makro ayı barajı)
        )

        self.assertIsInstance(res, dict)
        self.assertEqual(res.get("error"), "MACRO_BEAR_COUNTER_TREND_LONG_BLOCKED", 
                         "Makro Ayı altında bağımsız alfasız Long kesinlikle bloke edilmelidir!")

    async def test_03_macro_bear_margin_ceiling_clamp_at_050x(self):
        """1.1 KANIT: Bağımsız Alfa onaylansa bile makro ayıda marjin çarpanı ASLA 0.50x'i geçemez!"""
        symbol = "REALALPHA/USDT"
        
        macro = {"btc_chg_4h": -2.0, "btc_chg_1h": -0.9, "regime": "BEAR_DUMP", "status": "BEAR_DUMP"}
        self.strat.get_macro_climate = MagicMock(return_value=macro)
        self.strat.get_market_trend_regime = MagicMock(return_value="GÜÇLÜ AYI")

        # Taze OBI derinliği (Isınma korumasını geçmesi için)
        self.md.get_orderbook_depth = MagicMock(return_value={
            "symbol": symbol, "bid_qty": 3000.0, "ask_qty": 1000.0, "ratio": 3.0,
            "wall_side": "BID_WALL", "wall_duration_sec": 20.0, "last_update": time.time()
        })
        
        # Mükemmel Gauss Z-Score (+2.8σ) VE Coinbase Prime Smart Money Bull
        self.md.get_universe_log_return_zscore = MagicMock(return_value={
            "symbol": symbol, "z_score": 2.8, "is_extreme_divergence": True
        })
        self.md.get_symbol_cvd = MagicMock(return_value={"ratio_60s": 65.0})
        self.md.get_coinbase_lead_lag = MagicMock(return_value={
            "direction": "COINBASE_LEAD_BULL", "status": "COINBASE_LEAD_BULL", "spread_bps": 12.0, "is_listed": True,
            "last_update": time.time(), "age_seconds": 5.0
        })

        # _handle_open ile bağımsız alfanın geçip tavan marjin kelepçesi aldığını doğrula (SCALP)
        res = await self.strat._handle_open(
            symbol=symbol, side="LONG", entry_price=10.0,
            hard_stop=9.8, soft_stop=9.85, tp1=10.3, tp2=10.5,
            trade_type="SCALP",
            reason="Bağımsız Alfa Long", setup_id="SETUP_3_S3_BOUNCE",
            confluence_list=["T1", "T2", "T3", "T4"]
        )

        self.mock_pt.open_position.assert_called_once()
        open_kwargs = self.mock_pt.open_position.call_args[1]
        reason_text = open_kwargs.get("reason", "")
        self.assertIn("Makro Ayı Tavan Marjin Kelepçesi (Max 0.50x)", reason_text,
                      "Makro ayı kelepçesi loglara ve emre işlenmiş olmalıdır!")

    async def test_04_setup9_l2_absorption_shield_rejects_weak_orderbook(self):
        """1.2 KANIT: Setup 9 nPOC temasında L2 Alıcı Duvarı Oranı < 1.40x ise emir AÇILMAMALIDIR."""
        symbol = "KNIFE/USDT"
        
        levels = {
            "below_npoc": 95.0,
            "above_npoc": 105.0,
            "p": 100.0, "s3": 96.0, "s4": 94.0, "r3": 104.0, "r4": 106.0, "r5": 108.0,
            "mval": 95.5, "mpoc": 100.0
        }
        self.strat.get_macro_climate = MagicMock(return_value={"regime": "NEUTRAL", "btc_chg_1h": 0.0, "btc_chg_4h": 0.0})
        self.strat.get_market_trend_regime = MagicMock(return_value="NÖTR")
        self.strat.check_structural_invalidation = MagicMock(return_value=(True, ""))
        self.strat._handle_open = AsyncMock()

        cur_candle = {'open': 96.0, 'high': 96.2, 'low': 94.95, 'close': 95.2, 'volume': 1500.0}
        prev_candle = {'open': 96.0, 'high': 96.2, 'low': 95.1, 'close': 95.4, 'volume': 1000.0}

        # L2 Oranı Zayıf (1.10x < 1.40x) ve Mikro-CVD 53%
        self.md.get_orderbook_depth = MagicMock(return_value={
            "symbol": symbol,
            "bid_qty": 1100.0,
            "ask_qty": 1000.0,
            "ratio": 1.10, # < 1.40x YETERSİZ!
            "wall_side": "BALANCED",
            "wall_duration_sec": 10.0,
            "last_update": time.time()
        })
        self.md.get_symbol_cvd = MagicMock(return_value={"ratio_60s": 53.0})

        await self.strat.evaluate_candle_close(symbol, cur_candle, prev_candle, levels)

        self.strat._handle_open.assert_not_called()
        self.assertTrue(len(self.strat.recent_rejections) > 0, "Reddedilme kaydı oluşmalıdır.")
        rej_msg = self.strat.recent_rejections[-1].get("reason", "")
        self.assertIn("L2 Absorpsiyon Kalkanı", rej_msg, 
                      "L2 derinliği 1.40x altındaysa Setup 9 kesinlikle reddedilmelidir!")

    async def test_05_setup9_l2_absorption_shield_rejects_weak_micro_cvd(self):
        """1.2 KANIT: Setup 9 nPOC temasında 60s Mikro-CVD < %52 ise emir AÇILMAMALIDIR."""
        symbol = "BLEED/USDT"
        
        levels = {
            "below_npoc": 95.0, "above_npoc": 105.0,
            "p": 100.0, "s3": 96.0, "s4": 94.0, "r3": 104.0, "r4": 106.0, "r5": 108.0,
            "mval": 95.5, "mpoc": 100.0
        }
        self.strat.get_macro_climate = MagicMock(return_value={"regime": "NEUTRAL", "btc_chg_1h": 0.0, "btc_chg_4h": 0.0})
        self.strat.get_market_trend_regime = MagicMock(return_value="NÖTR")
        self.strat.check_structural_invalidation = MagicMock(return_value=(True, ""))
        self.strat._handle_open = AsyncMock()

        cur_candle = {'open': 96.0, 'high': 96.2, 'low': 94.95, 'close': 95.2, 'volume': 1500.0}
        prev_candle = {'open': 96.0, 'high': 96.2, 'low': 95.1, 'close': 95.4, 'volume': 1000.0}

        # L2 Oranı Güçlü (1.80x >= 1.40x) AMA Mikro-CVD Zayıf (%47.5 < %52.0)
        self.md.get_orderbook_depth = MagicMock(return_value={
            "symbol": symbol,
            "bid_qty": 1800.0,
            "ask_qty": 1000.0,
            "ratio": 1.80,
            "wall_side": "BID_WALL",
            "wall_duration_sec": 10.0,
            "last_update": time.time()
        })
        self.md.get_symbol_cvd = MagicMock(return_value={"ratio_60s": 47.5}) # < 52.0% YETERSİZ!

        await self.strat.evaluate_candle_close(symbol, cur_candle, prev_candle, levels)

        self.strat._handle_open.assert_not_called()
        self.assertTrue(len(self.strat.recent_rejections) > 0, "Reddedilme kaydı oluşmalıdır.")
        rej_msg = self.strat.recent_rejections[-1].get("reason", "")
        self.assertIn("60s Mikro-CVD Taker Alış", rej_msg, 
                      "Mikro-CVD %52 altındaysa Setup 9 düşen bıçak olarak engellenmelidir!")

    async def test_06_setup9_l2_absorption_shield_approves_when_confirmed(self):
        """1.2 KANIT: L2 Alıcı Duvarı >= 1.40x VE Mikro-CVD >= %52 olduğunda Setup 9 teyitle onaylanmalıdır."""
        symbol = "ABSORBED/USDT"
        
        levels = {
            "below_npoc": 95.0, "above_npoc": 105.0,
            "p": 100.0, "s3": 96.0, "s4": 94.0, "r3": 104.0, "r4": 106.0, "r5": 108.0,
            "mval": 97.0, "mpoc": 100.0
        }
        self.strat.get_macro_climate = MagicMock(return_value={"regime": "NEUTRAL", "btc_chg_1h": 0.0, "btc_chg_4h": 0.0})
        self.strat.get_market_trend_regime = MagicMock(return_value="NÖTR")
        self.strat.check_structural_invalidation = MagicMock(return_value=(True, ""))
        self.strat._handle_open = AsyncMock()

        # Çift mum ve alt fitil emilimi
        cur_candle = {'open': 95.1, 'high': 95.5, 'low': 94.95, 'close': 95.3, 'volume': 1500.0}
        prev_candle = {'open': 96.0, 'high': 96.2, 'low': 95.1, 'close': 95.4, 'volume': 1000.0}

        # L2 Oranı Güçlü (1.65x >= 1.40x) VE Mikro-CVD Güçlü (%56.0 >= %52.0)
        self.md.get_orderbook_depth = MagicMock(return_value={
            "symbol": symbol,
            "bid_qty": 1650.0,
            "ask_qty": 1000.0,
            "ratio": 1.65,
            "wall_side": "BID_WALL",
            "wall_duration_sec": 10.0,
            "last_update": time.time()
        })
        self.md.get_symbol_cvd = MagicMock(return_value={"ratio_60s": 56.0})

        await self.strat.evaluate_candle_close(symbol, cur_candle, prev_candle, levels)

        self.strat._handle_open.assert_called_once()
        open_kwargs = self.strat._handle_open.call_args[1]
        self.assertEqual(open_kwargs["setup_id"], "SETUP_9_BELOW_NPOC_BOUNCE")
        self.assertIn("L2_Bid_Wall_1.65x", open_kwargs["confluence_list"])
        self.assertIn("Micro_CVD_56.0pct", open_kwargs["confluence_list"])


if __name__ == '__main__':
    unittest.main()
