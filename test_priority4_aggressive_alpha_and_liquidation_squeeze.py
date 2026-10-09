"""
🦅 VALKYRIE MASTER V4.0 - ÖNCELİK 4: AGRESİF ALFA & LİKİDASYON SQUEEZE AVI (AŞAMA 5)
Birim ve Kuant Doğrulama Test Paketi

Kapsam:
- 4.1 Global Tasfiye Isı Haritası (Liquidation Heatmap): 100 basamaklı dairesel ısı haritası ve yoğunluk dağılımı
- Setup 15: Short Squeeze Avı (> $1,000,000 Short tasfiyesi + L2 ask süpürme -> Anlık Squeeze Long)
- Setup 16: Long Cascade Dip Avı (Sert dump + Hawkes η < 0.50 + L2 alıcı bloğu -> V-dönüşü Long)
"""

import unittest
import asyncio
import time
from collections import deque
from unittest.mock import MagicMock, AsyncMock

from indicators import calculate_liquidation_heatmap
from market_data import MarketDataManager
from strategy import StrategyEngine


class TestPriority4AggressiveAlphaAndLiquidationSqueeze(unittest.TestCase):

    def setUp(self):
        self.market_data = MagicMock(spec=MarketDataManager)
        self.market_data.candles_5m = {}
        self.market_data.levels = {}
        self.market_data.symbol_metrics = {}
        self.market_data.liquidation_events_history = {}
        self.market_data.global_liquidation_events_history = deque(maxlen=100)

        self.market_data.get_symbol_metrics = lambda s: {
            "vol_surge": 1.25,
            "min_vol_surge": 1.2,
            "atr_pct": 1.2,
            "is_top_80": True,
            "dynamic_rs_score": 0.05,
            "rs_zscore": 0.2
        }
        self.market_data.get_symbol_cvd = lambda s: {"ratio_60s": 55.0, "delta_60s": 15000.0}
        self.market_data.get_symbol_netflow = lambda s: {
            "netflow_24h_usd": 0.0, "z_score": 0.0, "regime": "BALANCED_FLOW", "last_update": time.time()
        }
        self.market_data.get_smart_money_divergence = lambda s: {"coinbase_buy_ratio": 50.0}
        self.market_data.get_coinbase_lead_lag = lambda sym=None: {"direction": "NEUTRAL", "status": "BALANCED", "spread_bps": 0.0}
        self.market_data.get_orderbook_depth = lambda s: {
            'imbalance': 0.15,
            'ratio': 1.35,
            'wall_side': 'BID_SUPPORT',
            'bid_qty': 150.0,
            'ask_qty': 100.0,
            'last_update': time.time(),
            'wall_duration_sec': 15.0
        }
        self.market_data.get_jit_l2_depth = AsyncMock(return_value={
            "l2_ratio": 1.4,
            "top_ratio": 1.2,
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
        self.strategy.shadow_engine.get_coin_liquidity_tier = lambda s: {"tier": "TIER_1_MAJÖR", "tier_label": "Tier-1"}
        self.strategy.calibrated_coin_dna = {
            "SOL": {"muted_setups": [], "calibration_status": "DENGELİ", "allowed_strategy_regime": "ALL"},
            "BTC": {"muted_setups": [], "calibration_status": "DENGELİ", "allowed_strategy_regime": "ALL"}
        }

    def test_01_liquidation_heatmap_100_bins_calculation(self):
        """
        4.1 KANIT: Global Tasfiye Isı Haritası (Liquidation Heatmap)
        100 basamaklı dairesel kova dağılımı, yoğunluk yüzdesi ve tepe tasfiye kümeleri.
        """
        now = time.time()
        # 10 farklı seviyede tasfiye olayı simüle et
        events = [
            # Short Liquidations ($64,500 - $65,500 civarı)
            {'price': 65000.0, 'usd_size': 450_000.0, 'is_long_liq': False, 'timestamp': now - 20},
            {'price': 65100.0, 'usd_size': 750_000.0, 'is_long_liq': False, 'timestamp': now - 40},
            {'price': 65200.0, 'usd_size': 300_000.0, 'is_long_liq': False, 'timestamp': now - 50},
            # Long Liquidations ($63,000 - $63,800 civarı)
            {'price': 63500.0, 'usd_size': 500_000.0, 'is_long_liq': True, 'timestamp': now - 30},
            {'price': 63200.0, 'usd_size': 850_000.0, 'is_long_liq': True, 'timestamp': now - 60},
        ]

        res = calculate_liquidation_heatmap(events, current_price=64000.0, num_bins=100, lookback_sec=1800.0, current_time=now)

        # 100 kova kontrolü
        self.assertEqual(res['num_bins'], 100)
        self.assertEqual(len(res['bins']), 100)

        # Toplam ve son 120s toplamları
        self.assertEqual(res['total_short_usd'], 1_500_000.0)
        self.assertEqual(res['total_long_usd'], 1_350_000.0)
        self.assertEqual(res['total_usd'], 2_850_000.0)
        self.assertEqual(res['recent_short_liq_120s'], 1_500_000.0)
        self.assertEqual(res['recent_long_liq_120s'], 1_350_000.0)

        # Yoğunluk ve tepe kova kontrolleri
        self.assertGreater(res['max_short_cluster_usd'], 0.0)
        self.assertGreater(res['max_long_cluster_usd'], 0.0)
        self.assertGreaterEqual(res['max_short_cluster_price'], 64900.0)
        self.assertLessEqual(res['max_short_cluster_price'], 65300.0)

        # En yoğun kovanın yoğunluğu %100 olmalı
        peak_intensity = max(b['intensity_pct'] for b in res['bins'])
        self.assertEqual(peak_intensity, 100.0)

        print(f"  [PASS] 4.1: 100 Basamaklı Tasfiye Isı Haritası doğrulandı (Toplam: ${res['total_usd']/1e6:.2f}M, Tepe Short Kümesi: ${res['max_short_cluster_price']:,.0f})")

    def test_02_short_squeeze_hunt_setup15_triggers_on_large_short_liq_and_ask_sweep(self):
        """
        4.1 KANIT: Short Squeeze Avı (Setup 15)
        Son 120 saniyede > $1,000,000 Short tasfiye edildiğinde ve L2 ask süpürüldüğünde
        balina momentumuna eşlik eden anlık Squeeze Long işlemi tetiklenmelidir.
        """
        symbol = "BTC/USDT"
        now = time.time()

        # 1. > $1M Short Tasfiyesi Simülasyonu
        self.market_data.get_recent_liquidation_volume = lambda sym=None, lookback_sec=120.0: {
            'symbol': symbol,
            'long_usd': 50_000.0,
            'short_usd': 1_250_000.0,  # $1.25M Short Tasfiyesi (> $1.0M şartı sağlandı)
            'total_usd': 1_300_000.0,
            'dominant_side': 'SHORT'
        }

        # 2. L2 Satıcı Tahtası Süpürüldü (Ask Swept)
        self.market_data.get_orderbook_depth = lambda s: {
            'ratio': 1.45,  # Alıcılar baskın
            'wall_side': 'BID_SUPPORT',
            'bid_qty': 250.0,
            'ask_qty': 120.0,
            'last_update': now
        }

        current_candle = {
            'open': 64200.0,
            'high': 64800.0,
            'low': 64150.0,
            'close': 64750.0,
            'volume': 1500.0
        }
        levels = {'r3': 66500.0, 'r4': 67500.0, 'p': 64000.0, 's3': 63500.0}

        # Kurulumu tetikle
        res = asyncio.run(self.strategy.evaluate_liquidation_squeeze_setups(
            symbol=symbol,
            current_candle=current_candle,
            levels=levels
        ))

        self.assertIsNotNone(res, "Setup 15 Short Squeeze işlemi tetiklenmelidir!")
        self.assertIn("SETUP_15_SHORT_SQUEEZE_HUNT", res.get("setup_id", ""))
        self.assertEqual(res.get("side"), "LONG")
        self.assertEqual(res.get("trade_type"), "MOMENTUM")

        # Confluence kontrolleri
        c_list = res.get("confluence_list", [])
        self.assertIn("Short_Squeeze_Liquidation_Cascade", c_list)
        self.assertIn("Ask_Depth_Swept", c_list)
        self.assertIn("Whale_Squeeze_Momentum", c_list)

        print("  [PASS] 4.1: Setup 15 (Short Squeeze Avı) $1.25M Short tasfiyesi ve ask süpürmesiyle başarıyla tetiklendi!")

    def test_03_short_squeeze_hunt_bypasses_when_short_liq_below_1M(self):
        """
        4.1 KANIT: Short Squeeze Avı (Setup 15) Eşik Altında Tetiklenmeme Koruması
        Short tasfiyesi < $1,000,000 olduğunda Setup 15 devreye girmemelidir.
        """
        symbol = "BTC/USDT"
        now = time.time()

        # Sadece $400k Short Tasfiyesi (Yetersiz)
        self.market_data.get_recent_liquidation_volume = lambda sym=None, lookback_sec=120.0: {
            'symbol': symbol,
            'long_usd': 50_000.0,
            'short_usd': 400_000.0,
            'total_usd': 450_000.0,
            'dominant_side': 'SHORT'
        }
        self.market_data.get_orderbook_depth = lambda s: {
            'ratio': 1.40,
            'wall_side': 'BID_SUPPORT',
            'bid_qty': 200.0,
            'ask_qty': 100.0,
            'last_update': now
        }

        current_candle = {
            'open': 64200.0,
            'high': 64400.0,
            'low': 64150.0,
            'close': 64350.0,
            'volume': 800.0
        }

        res = asyncio.run(self.strategy.evaluate_liquidation_squeeze_setups(
            symbol=symbol,
            current_candle=current_candle,
            levels={}
        ))
        self.assertIsNone(res, "Tasfiye < $1M iken Setup 15 açılmamalıdır!")
        print("  [PASS] 4.1: Short tasfiye < $1M iken Setup 15 güvenle atlandı (False positive engellendi)!")

    def test_04_long_cascade_dip_hunt_setup16_triggers_when_hawkes_calm_and_buyer_block_seated(self):
        """
        4.1 KANIT: Long Cascade Dip Avı (Setup 16)
        Sert dump sırasında Longlar patlatıldıktan sonra Hawkes çığı sakinleştiğinde (η < 0.50)
        ve ilk L2 alıcı bloğu oturduğunda V-dönüşü Long işlemi açılmalıdır.
        """
        symbol = "SOL/USDT"
        now = time.time()

        # 1. Sert dump ve masif Long tasfiyesi ($750k Long Liq)
        self.market_data.get_recent_liquidation_volume = lambda sym=None, lookback_sec=180.0: {
            'symbol': symbol,
            'long_usd': 750_000.0,
            'short_usd': 30_000.0,
            'total_usd': 780_000.0,
            'dominant_side': 'LONG'
        }

        # 2. Hawkes Çığı Sakinleşti (η = 0.22 < 0.50)
        self.market_data.get_hawkes_avalanche = lambda s=None: {
            'branching_ratio_eta': 0.22,
            'is_avalanche_active': False,
            'is_avalanche_exhausted': True,
            'regime': 'QUIET_FLOW',
            'desc': 'Çığ Durdu'
        }

        # 3. İlk L2 Alıcı Bloğu Oturdu (L2 Bid Support Wall)
        self.market_data.get_orderbook_depth = lambda s: {
            'ratio': 1.55,
            'wall_side': 'BID_SUPPORT',
            'bid_qty': 450.0,
            'ask_qty': 220.0,
            'last_update': now
        }

        current_candle = {
            'open': 155.0,
            'high': 155.2,
            'low': 148.5,  # Sert iğne dibi
            'close': 149.8,
            'volume': 4500.0
        }
        levels = {'s3': 149.0, 'p': 154.0, 'r3': 158.0}

        res = asyncio.run(self.strategy.evaluate_liquidation_squeeze_setups(
            symbol=symbol,
            current_candle=current_candle,
            levels=levels
        ))

        self.assertIsNotNone(res, "Setup 16 Long Cascade Dip Avı tetiklenmelidir!")
        self.assertIn("SETUP_16_LONG_CASCADE_DIP_HUNT", res.get("setup_id", ""))
        self.assertEqual(res.get("side"), "LONG")
        self.assertEqual(res.get("trade_type"), "REVERSAL")

        c_list = res.get("confluence_list", [])
        self.assertIn("Long_Cascade_Exhaustion", c_list)
        self.assertIn("L2_Buyer_Block_Established", c_list)
        self.assertIn("V_Shape_Reversal", c_list)
        self.assertTrue(any("Hawkes_Eta_Calm" in c for c in c_list))

        print("  [PASS] 4.1: Setup 16 (Long Cascade Dip Avi) Hawkes sakinlesmesi (eta=0.22) ve alici blogu ile V-donusu acti!")

    def test_05_long_cascade_dip_hunt_blocks_when_hawkes_avalanche_still_active(self):
        """
        4.1 KANIT: Hawkes Cigi Aktifken (eta >= 0.50) Dusen Bicak Tutma Engeli
        Eger tasfiye cigi henuz durmamissa (zincirleme satis devam ediyorsa),
        Setup 16 dusen bicagi tutmamali ve islemi engellemelidir.
        """
        symbol = "SOL/USDT"
        now = time.time()

        self.market_data.get_recent_liquidation_volume = lambda sym=None, lookback_sec=180.0: {
            'symbol': symbol,
            'long_usd': 900_000.0,
            'short_usd': 20_000.0,
            'total_usd': 920_000.0,
            'dominant_side': 'LONG'
        }

        # Hawkes Cigi HALA SIDDETLE DEVAM EDIYOR (eta = 0.95 >= 0.50)
        self.market_data.get_hawkes_avalanche = lambda s=None: {
            'branching_ratio_eta': 0.95,
            'is_avalanche_active': True,
            'is_avalanche_exhausted': False,
            'regime': 'AVALANCHE_RUNNER_ACTIVE',
            'desc': 'Cig Devam Ediyor'
        }

        self.market_data.get_orderbook_depth = lambda s: {
            'ratio': 1.35,
            'wall_side': 'BID_SUPPORT',
            'bid_qty': 300.0,
            'ask_qty': 200.0,
            'last_update': now
        }

        current_candle = {
            'open': 155.0,
            'high': 155.2,
            'low': 147.0,
            'close': 148.0,
            'volume': 5000.0
        }

        res = asyncio.run(self.strategy.evaluate_liquidation_squeeze_setups(
            symbol=symbol,
            current_candle=current_candle,
            levels={}
        ))
        self.assertIsNone(res, "Hawkes cigi aktifken (eta >= 0.50) Setup 16 tetiklenmemeli, dusen bicak tutulmamalidir!")
        print("  [PASS] 4.1: Hawkes cigi aktifken (eta=0.95) Setup 16 tetiklenmedi (Dusen bicak engeli basarili)!")


if __name__ == '__main__':
    unittest.main()
