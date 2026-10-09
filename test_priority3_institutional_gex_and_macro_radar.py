"""
🦅 VALKYRIE V4.0: ÖNCELİK 3 - KURUMSAL İSTİHBARAT & MAKRO OPSİYON REGİME TEST PAKETİ
Matematiksel ve Kuant İspat Testleri:
1. Canlı Deribit Opsiyon Gamma Exposure (GEX) & Gamma Flip Strike Formülü İspatı (GEX = Gamma * OI * S^2 * 0.01)
2. Pozitif Gamma (+GEX / Pinning Rejimi): S3/R3 & nPOC Mean-Reversion Teşviki ve Breakout Marjin Kısma (0.50x)
3. Negatif Gamma (-GEX / Explosion Rejimi): Mean-Reversion Kurulumlarının Susturulması (MUTE) & Breakout Tam Güç
4. Gamma Flip Seviyesi Dinamik S/R Enjeksiyonu ve Seviye Uyumu
5. SSR (Stablecoin Supply Ratio) Osilatörü & 24S MA Altı Spot Alım Gücü Artışı İspatı
6. Tether Treasury Taze >= $1B Mint Radarı ve 4 Saatlik Makro Boğa İvmesi İspatı
"""

import unittest
import time
import asyncio
from unittest.mock import MagicMock, AsyncMock
import numpy as np

from indicators import calculate_deribit_gex, calculate_ssr_oscillator
from market_data import MarketDataManager
from strategy import StrategyEngine


class TestPriority3InstitutionalGexAndMacroRadar(unittest.TestCase):

    def setUp(self):
        self.market_data = MagicMock(spec=MarketDataManager)
        self.market_data._clean_symbol = lambda s: s.replace('/', '').replace(':USDT', '')
        self.market_data.candles_5m = {}
        self.market_data.current_prices = {"BTC/USDT": 65000.0, "SOL/USDT": 150.0}
        self.market_data.levels = {}
        self.market_data.symbol_metrics = {}
        self.market_data.get_symbol_metrics = lambda s: {
            "vol_surge": 1.2,
            "min_vol_surge": 1.2,
            "atr_pct": 1.2,
            "is_top_80": True,
            "dynamic_rs_score": 0.0,
            "rs_zscore": 0.0
        }
        self.market_data.get_symbol_cvd = lambda s: {"ratio_60s": 55.0}
        self.market_data.get_symbol_netflow = lambda s: {"netflow_24h_usd": 0.0, "z_score": 0.0, "regime": "BALANCED_FLOW", "last_update": time.time()}
        self.market_data.get_smart_money_divergence = lambda s: {"coinbase_buy_ratio": 50.0}
        self.market_data.get_coinbase_lead_lag = lambda sym=None: {"direction": "NEUTRAL", "status": "BALANCED", "spread_bps": 0.0}
        self.market_data.get_orderbook_depth = lambda s: {
            'imbalance': 0.1,
            'ratio': 1.25,
            'wall_side': 'BID_SUPPORT',
            'bid_qty': 100.0,
            'ask_qty': 80.0,
            'last_update': time.time(),
            'wall_duration_sec': 10.0
        }
        self.market_data.get_jit_l2_depth = AsyncMock(return_value={
            "l2_ratio": 1.5,
            "top_ratio": 1.0,
            "depth_available": True,
            "deribit_gex_regime": "NEUTRAL",
            "deribit_net_gex": 0.0
        })

        # Mock Paper Trader & Manager
        self.mock_pt = MagicMock()
        self.mock_pt.balance = 10000.0
        self.mock_pt.open_positions = {}
        def mock_open_fn(*args, **kwargs):
            pos_dict = dict(kwargs)
            sym = kwargs.get("symbol") or (args[0] if len(args) > 0 else "UNKNOWN")
            pos_dict["symbol"] = sym
            self.mock_pt.open_positions[sym] = pos_dict
            return pos_dict
        self.mock_pt.open_position = MagicMock(side_effect=mock_open_fn)
        self.mock_pt.paper_trader = self.mock_pt
        self.mock_pt.active_trader = self.mock_pt

        self.mock_notifier = MagicMock()
        self.mock_notifier.notify_position_opened = AsyncMock()

        self.strategy = StrategyEngine(self.mock_pt, self.mock_notifier, market_data=self.market_data)
        self.strategy.boot_time = time.time() - 100.0
        self.strategy.warmup_seconds = 0.0
        self.strategy.shadow_engine = MagicMock()
        self.strategy.shadow_engine.get_coin_setup_matrix = lambda s: {}
        self.strategy.shadow_engine.get_coin_liquidity_tier = lambda s: {"tier": "TIER_2_DINAMIK", "tier_label": "Tier-2"}
        self.strategy.calibrated_coin_dna = {
            "SOL": {"muted_setups": [], "calibration_status": "DENGELİ", "allowed_strategy_regime": "ALL"},
            "BTC": {"muted_setups": [], "calibration_status": "DENGELİ", "allowed_strategy_regime": "ALL"}
        }
        self.strategy.dna_baseline = {}

    def test_01_deribit_gex_formula_and_gamma_flip_calculation(self):
        """
        3.1 Canlı Deribit Opsiyon GEX & Gamma Flip Formül Doğrulaması:
        GEX_Strike = Gamma * OI * S^2 * 0.01
        Net Gamma'nın sıfırı kestiği pivot seviyesinin doğru enterpole edildiği kanıtlanır.
        """
        spot = 65000.0
        options_book = [
            # Call: 60,000 Strike, OI=100, Gamma=0.00002
            {
                'instrument_name': 'BTC-28OCT26-60000-C',
                'underlying_price': spot,
                'open_interest': 100.0,
                'gamma': 0.00002,
                'mark_iv': 55.0
            },
            # Call: 70,000 Strike, OI=150, Gamma=0.000025
            {
                'instrument_name': 'BTC-28OCT26-70000-C',
                'underlying_price': spot,
                'open_interest': 150.0,
                'gamma': 0.000025,
                'mark_iv': 55.0
            },
            # Put: 62,000 Strike, OI=120, Gamma=0.000022
            {
                'instrument_name': 'BTC-28OCT26-62000-P',
                'underlying_price': spot,
                'open_interest': 120.0,
                'gamma': 0.000022,
                'mark_iv': 55.0
            },
            # Put: 68,000 Strike, OI=80, Gamma=0.000018
            {
                'instrument_name': 'BTC-28OCT26-68000-P',
                'underlying_price': spot,
                'open_interest': 80.0,
                'gamma': 0.000018,
                'mark_iv': 55.0
            }
        ]

        res = calculate_deribit_gex(options_book, spot_price=spot)
        self.assertGreater(res['call_gex'], 0.0)
        self.assertGreater(res['put_gex'], 0.0)
        self.assertIn(res['gex_regime'], ['POSITIVE_GAMMA_PIN', 'NEGATIVE_GAMMA_EXPLOSION', 'NEUTRAL_GAMMA'])
        self.assertGreater(res['gamma_flip_strike'], 55000.0)
        self.assertLess(res['gamma_flip_strike'], 75000.0)
        print(f"  [PASS] 3.1: GEX Formülü doğrulandı: Net GEX=${res['net_gex']/1e6:.2f}M, Flip=${res['gamma_flip_strike']:,.0f}, Rejim={res['gex_regime']}")

    def test_02_positive_gex_pinning_regime_boosts_mean_reversion_and_clamps_breakout(self):
        """
        3.1 Pozitif Gamma (+GEX / Pinning Rejimi):
        Piyasa yapıcılar volatiliteyi baskılarken:
        - S3/R3 & nPOC Mean-Reversion işlemlerine 'Deribit_+GEX_Pinning_Support' teyidi verilmeli.
        - Breakout (Kırılım) işlemlerinin marjini %50 kısılmalı (0.50x kelepçesi).
        """
        self.market_data.get_deribit_gex_regime = lambda: "POSITIVE_GAMMA_PIN"
        self.market_data.deribit_gex_data = {
            "BTC": {
                "net_gex": 45_000_000.0,
                "gex_regime": "POSITIVE_GAMMA_PIN",
                "gamma_flip_strike": 64500.0
            }
        }
        self.market_data.levels = {
            "SOL/USDT": {"gamma_flip": 148.5, "camarilla": {"S3": 149.0, "R3": 151.0, "P": 150.0}}
        }

        # 1. Mean-Reversion (SETUP_9_BELOW_NPOC_BOUNCE) İşlemi
        c_list_mr = []
        res_mr = asyncio.run(self.strategy._handle_open(
            symbol="SOL/USDT",
            side="LONG",
            entry_price=149.2,
            reason="SETUP 9 nPOC Sekmesi Alış",
            soft_stop=147.5,
            hard_stop=147.0,
            tp1=153.0,
            tp2=155.0,
            trade_type="SCALP",
            snapshot_levels={"gamma_flip": 148.5},
            setup_id="SETUP_9_BELOW_NPOC_BOUNCE",
            confluence_list=c_list_mr
        ))
        self.assertIn("Deribit_+GEX_Pinning_Support", c_list_mr)
        self.assertIn("Above_Gamma_Flip_Bullish_Zone", c_list_mr)

        # 2. Breakout (SETUP_1_R4_BREAKOUT) İşlemi -> Marjin Kısılmalı
        c_list_bo = []
        res_bo = asyncio.run(self.strategy._handle_open(
            symbol="SOL/USDT",
            side="LONG",
            entry_price=152.0,
            reason="SETUP 1 R4 Breakout",
            soft_stop=149.5,
            hard_stop=149.0,
            tp1=156.0,
            tp2=160.0,
            trade_type="BREAKOUT",
            snapshot_levels={"gamma_flip": 148.5},
            setup_id="SETUP_1_R4_BREAKOUT",
            confluence_list=c_list_bo
        ))
        # Açılan pozisyonun marjininin %50 kısıldığı doğrulanır
        opened_pos = list(self.mock_pt.open_positions.values())
        self.assertTrue(len(opened_pos) > 0)
        latest_pos = opened_pos[-1]
        self.assertLessEqual(latest_pos.get("margin_multiplier", 1.0), 0.50)
        print("  [PASS] 3.1: +GEX Pinning modunda nPOC sekesi ödüllendirildi ve Breakout marjini 0.50x kelepçelendi!")

    def test_03_negative_gex_explosion_regime_mutes_mean_reversion_and_powers_breakout(self):
        """
        3.1 Negatif Gamma (-GEX / Explosion Rejimi):
        Piyasa yapıcılar delta-hedge ile fiyatı hızlandırırken:
        - Mean-Reversion (S3/R3 & nPOC) işlemleri SUSTURULMALI (GEX_EXPLOSION_MEAN_REVERSION_MUTED hatasıyla engellenmeli).
        - Breakout işlemleri 'Deribit_-GEX_Volatility_Explosion' teyidi alarak tam güçle onaylanmalı.
        """
        self.market_data.get_deribit_gex_regime = lambda: "NEGATIVE_GAMMA_EXPLOSION"
        self.market_data.deribit_gex_data = {
            "BTC": {
                "net_gex": -55_000_000.0,
                "gex_regime": "NEGATIVE_GAMMA_EXPLOSION",
                "gamma_flip_strike": 66200.0
            }
        }
        self.market_data.levels = {
            "SOL/USDT": {"gamma_flip": 152.0, "camarilla": {"S3": 149.0, "R3": 151.0, "P": 150.0}}
        }

        # 1. Mean-Reversion İşlemi Engellenmeli (MUTE)
        res_mr = asyncio.run(self.strategy._handle_open(
            symbol="SOL/USDT",
            side="LONG",
            entry_price=149.2,
            reason="SETUP 9 nPOC Sekmesi Alış",
            soft_stop=147.5,
            hard_stop=147.0,
            tp1=153.0,
            tp2=155.0,
            trade_type="SCALP",
            snapshot_levels={"gamma_flip": 152.0},
            setup_id="SETUP_9_BELOW_NPOC_BOUNCE",
            confluence_list=[]
        ))
        self.assertEqual(res_mr.get("error"), "GEX_EXPLOSION_MEAN_REVERSION_MUTED")

        # 2. Breakout İşlemi Tam Güçle Onaylanmalı
        c_list_bo = []
        res_bo = asyncio.run(self.strategy._handle_open(
            symbol="SOL/USDT",
            side="LONG",
            entry_price=153.0,
            reason="SETUP 1 R4 Breakout Hacimli",
            soft_stop=150.0,
            hard_stop=149.5,
            tp1=160.0,
            tp2=165.0,
            trade_type="BREAKOUT",
            snapshot_levels={"gamma_flip": 152.0},
            setup_id="SETUP_1_R4_BREAKOUT",
            confluence_list=c_list_bo
        ))
        self.assertIn("Deribit_-GEX_Volatility_Explosion", c_list_bo)
        print("  [PASS] 3.1: -GEX Patlama modunda nPOC Mean-Reversion susturuldu ve Breakout tam güçle onaylandı!")

    def test_04_ssr_oscillator_detects_spot_purchasing_power_and_awards_confluence(self):
        """
        3.2 SSR (Stablecoin Supply Ratio) Osilatörü:
        SSR = BTC Market Cap / Stablecoin Market Cap
        SSR, 24 saatlik MA altına indiğinde spot alım gücü artışı 'SSR_Bullish_Purchasing_Power' confluence'ı sağlamalıdır.
        """
        # Test: BTC Cap $1,200B, Stablecoin Cap $180B -> SSR = 6.67
        # Tarihsel 24 saatlik ortalama = 7.50
        # SSR (6.67) < MA24 (7.50) -> Boğa alım gücü artışı!
        btc_mc = 1_200_000_000_000.0
        stable_mc = 180_000_000_000.0
        hist_ssr = [7.6, 7.5, 7.4, 7.5, 7.6]

        ssr_res = calculate_ssr_oscillator(btc_mc, stable_mc, hist_ssr)
        self.assertTrue(ssr_res['is_bullish_purchasing_power'])
        self.assertEqual(ssr_res['status'], "BULLISH_PURCHASING_POWER")
        self.assertLess(ssr_res['ssr'], ssr_res['ssr_ma24'])

        # Strategy Engine Entegrasyon Testi
        self.market_data.get_ammunition_status = lambda: {
            "bias": "BULLISH_FUEL",
            "ssr": ssr_res,
            "tether_mint": {"is_active": False}
        }
        c_list = []
        res = asyncio.run(self.strategy._handle_open(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=65000.0,
            reason="SETUP 1 R4 Breakout",
            soft_stop=64000.0,
            hard_stop=63500.0,
            tp1=68000.0,
            tp2=70000.0,
            trade_type="BREAKOUT",
            snapshot_levels={},
            setup_id="SETUP_1_R4_BREAKOUT",
            confluence_list=c_list
        ))
        self.assertIn("SSR_Bullish_Purchasing_Power", c_list)
        print("  [PASS] 3.2: SSR 24S MA altına indiğinde spot alım gücü başarıyla tespit edildi ve Long işlemine teyit eklendi!")

    def test_05_tether_treasury_1b_mint_triggers_4h_bull_surge(self):
        """
        3.2 Tether Mint Takibi:
        Tether Treasury taze >= $1 Milyar USDT bastığında:
        - 4 saatlik makro boğa ivmesi aktif edilmeli (is_active: True).
        - Strateji motorunda Long işlemlerine 'Tether_Treasury_$1B_Mint_Surge' confluence'ı enjekte edilmelidir.
        """
        # 1. MarketData üzerinde taze $1B Tether Mint kaydı
        real_md = MarketDataManager.__new__(MarketDataManager)
        real_md.all_symbols = ["BTC/USDT"]
        real_md.whale_transactions_feed = []
        real_md.tether_mint_status = {
            'is_active': False,
            'amount_usd': 0.0,
            'blockchain': 'NONE',
            'mint_ts': 0.0,
            'expires_ts': 0.0
        }
        real_md.record_whale_transaction = MagicMock()
        real_md.candles_5m = {}
        real_md._clean_symbol = lambda s: s

        mint_res = MarketDataManager.record_tether_treasury_mint(real_md, amount_usd=1_000_000_000.0, blockchain="TRON")
        self.assertTrue(mint_res['is_active'])
        self.assertEqual(mint_res['blockchain'], "TRON")
        self.assertEqual(mint_res['amount_usd'], 1_000_000_000.0)
        self.assertGreater(mint_res['remaining_sec'], 14000.0)  # ~4 saat (14400s)

        # 2. Strategy Engine Entegrasyonu
        self.market_data.get_ammunition_status = lambda: {
            "bias": "BULLISH_FUEL",
            "ssr": {"is_bullish_purchasing_power": False},
            "tether_mint": mint_res
        }
        c_list = []
        res = asyncio.run(self.strategy._handle_open(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=65000.0,
            reason="SETUP 1 R4 Breakout",
            soft_stop=64000.0,
            hard_stop=63500.0,
            tp1=68000.0,
            tp2=70000.0,
            trade_type="BREAKOUT",
            snapshot_levels={},
            setup_id="SETUP_1_R4_BREAKOUT",
            confluence_list=c_list
        ))
        self.assertIn("Tether_Treasury_$1B_Mint_Surge", c_list)
        print("  [PASS] 3.2: Tether Treasury $1B taze mint 4 saatlik makro boğa ivmesini başarıyla başlattı ve stratejiye aktardı!")


if __name__ == "__main__":
    unittest.main()
