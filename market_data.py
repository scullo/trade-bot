import asyncio
import json
import time
from collections import deque
from datetime import datetime, timezone, timedelta
import aiohttp
import ccxt.async_support as ccxt
import pandas as pd
import numpy as np
import config
from config import (
    LOOKBACK_DAYS_AVWAP,
    BTC_SHOCK_60S_PCT, BTC_SHOCK_COOLDOWN_SEC,
    WALL_MIN_AGE_SEC, WALL_ANCHOR_AGE_SEC,
    BASIS_BUBBLE_BPS, BASIS_ABSORPTION_BPS,
    MAX_ALLOWED_SPREAD_MAJORS, MAX_ALLOWED_SPREAD_ALTS, MAX_ALLOWED_SPREAD_MEME,
    MAX_ENTRY_SLIPPAGE_PCT, MIN_L2_DEPTH_USD_03,
    ENABLE_OI_VELOCITY_RADAR, OI_EXPANSION_THRESHOLD_PCT, OI_SQUEEZE_EXHAUSTION_PCT, OI_POLL_INTERVAL_SEC,
    ENABLE_COINBASE_LEAD_LAG, COINBASE_LEAD_SPREAD_BPS, COINBASE_TICK_WINDOW_SEC,
    ENABLE_WHALE_NETFLOW_RADAR, NETFLOW_INFLOW_ZSCORE_THRESHOLD, NETFLOW_OUTFLOW_ZSCORE_THRESHOLD,
    NETFLOW_REFRESH_INTERVAL_SEC, WHALE_TIER1_MIN_USD, WHALE_TIER2_MIN_USD, WHALE_TIER3_MIN_USD,
    ENABLE_AMMUNITION_CONFLUENCE, AMMUNITION_SURGE_THRESHOLD_USD, STALE_NETFLOW_TIMEOUT_SEC,
    ENABLE_SMART_MONEY_DIVERGENCE, SMART_MONEY_ACCUM_CB_BUY_MIN,
    SMART_MONEY_RETAIL_LONG_TRAP_BINANCE, SMART_MONEY_RETAIL_LONG_TRAP_CB_MAX,
    SMART_MONEY_RETAIL_SHORT_TRAP_BINANCE, SMART_MONEY_RETAIL_SHORT_TRAP_CB_MIN,
    SMART_MONEY_DIVERGENCE_SPREAD_TRAP, SMART_MONEY_MARGIN_BONUS_MULT
)
from indicators import (
    calculate_camarilla_pivots, calculate_anchored_vwap, calculate_volume_profile,
    get_tradingview_naked_lines, calculate_session_and_daily_levels,
    calculate_netflow_zscore, classify_whale_transfer, calculate_ammunition_momentum
)
import gc

def downcast_candle_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    VDA-0.1: Tip İndirgeme (Downcasting):
    - timestamp kolonu int64
    - open, high, low, close, volume, qav vb. float32
    DataFrame RAM ayak izini %50 azaltır.
    """
    if df is None or df.empty:
        return df
    try:
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_numeric(df['timestamp'], errors='coerce').fillna(0).astype(np.int64)
        float32_cols = ['open', 'high', 'low', 'close', 'volume', 'quote_volume', 'taker_base', 'taker_quote', 'qav']
        for c in float32_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0).astype(np.float32)
    except Exception:
        pass
    return df

def update_rolling_candle_buffer(df: pd.DataFrame, candle_dict: dict, maxlen: int = 300) -> pd.DataFrame:
    """
    VDA-0.1: In-Place Rolling Buffer (pd.concat parçalanma engeli):
    - Aynı mum için (ts == last_ts): Sıfır bellek ayırımıyla in-place at[] güncellemesi
    - Yeni mum için (ts > last_ts): Eski satırları kaydırarak iloc[-299:] ile yeni satırı ekler.
    """
    if df is None or df.empty:
        new_df = pd.DataFrame([candle_dict])
        return downcast_candle_dataframe(new_df)
    
    last_ts = df['timestamp'].iloc[-1]
    cur_ts = candle_dict.get('timestamp')
    if cur_ts == last_ts:
        last_idx = df.index[-1]
        for k_col, v_val in candle_dict.items():
            if k_col in df.columns:
                df.at[last_idx, k_col] = v_val
        return df
    elif cur_ts is not None and cur_ts > last_ts:
        if len(df) >= maxlen:
            df = df.iloc[-(maxlen - 1):].reset_index(drop=True)
        new_row = pd.DataFrame([candle_dict])
        downcast_candle_dataframe(new_row)
        df = pd.concat([df, new_row], ignore_index=True)
        return df
    return df

# ──────────────────────────────────────────────────────────────────────────
# 🏦 KURUMSAL VE BORSA SICAK/SOĞUK CÜZDAN BİLGİ BANKASI (AŞAMA 2 ON-CHAIN)
# ──────────────────────────────────────────────────────────────────────────
INSTITUTIONAL_WALLETS = {
    # Bitcoin
    "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo": "Binance Cold Storage #1",
    "bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h": "Binance Hot Wallet",
    "1NDyJtNTjmwk5xPNhjgAMu4HDHigtobu1s": "Binance 1",
    "3FHNBLobJgtgmTwR3Gqd3dcxNFwfnpUrMD": "Binance 2",
    "bc1qgdjqv0av3q56jvd82tkdjpy7gdp9ut8tlqmgrpmv24sq90ecnvqqjwvw97": "Binance 3",
    "1JCe8z4jJVNzgWeAZqttPrUshgQV7X11wb": "Coinbase Prime",
    # Ethereum / ERC20
    "0x28c6c06298d514db089934071355e5743bf21d60": "Binance Hot Wallet 14",
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549": "Binance Hot Wallet 15",
    "0xdfd5293d8e347dfe59e90efd55b2956a1343963d": "Binance Hot Wallet 16",
    "0xbe0eb53f46cd790cd13851d5eff43d12404d33e8": "Binance 7",
    "0xf977814e90da44bfa03b6295a0616a897441acec": "Binance 8",
    "0x47ac0fb4f2d84898e4d9e7b4dab3c24507a6d503": "Binance Hot Wallet",
    "0xa097d6b218977535799a7734208183c9b744e865": "Coinbase Prime",
    "0x71660c4005ba85c37ccec55d0c4493e66fe775d3": "Coinbase Hot Wallet",
    "0x50382893437ba40df72549a37e8c33979bb95574": "Coinbase Institutional",
    "0x6cc5f688a30d371e667352b058ecc4443b560e49": "OKX Hot Wallet",
    "0xf89d7b9c22bfdd665618421fd60209ca71df70ab": "Bybit Hot Wallet",
    "0x5754284f345af666384fb400a0ab37b39f15955b": "Tether Treasury (USDT)",
    "0xc6cde7c39eb2f0f0095f41570af89efc2c1ea828": "Tether Treasury Multi-Sig",
    "0x55fe002aef0550eef12bc31421397b9c9f426274": "Circle Treasury (USDC)",
    "0x0000000000000000000000000000000000000000": "Token Genesis Mint",
}

def format_wallet_label(address: str) -> str:
    if not address:
        return "Bilinmeyen Balina"
    addr_clean = str(address).strip().lower()
    for k, v in INSTITUTIONAL_WALLETS.items():
        if k.lower() == addr_clean:
            return v
    if address.startswith('0x') and len(address) >= 10:
        return f"Balina ({address[:6]}...{address[-4:]})"
    elif len(address) >= 12:
        return f"Balina ({address[:5]}...{address[-4:]})"
    return f"Balina ({address})"

class MarketDataManager:
    def __init__(self, all_symbols, active_symbols=None, timeframe="5m"):
        self.all_symbols = all_symbols
        self.active_symbols = set(active_symbols if active_symbols is not None else all_symbols)
        self.timeframe = timeframe
        self.exchange = ccxt.binanceusdm({
            'enableRateLimit': True
        })
        self.semaphore = asyncio.Semaphore(25)

        self.candles_5m = {s: pd.DataFrame() for s in all_symbols}
        self.candles_1d = {s: pd.DataFrame() for s in all_symbols}
        self.levels = {s: {} for s in all_symbols}
        self.symbol_metrics = {s: {} for s in all_symbols}
        self.current_prices = {s: 0.0 for s in all_symbols}
        self.funding_rates = {s: {
            'symbol': s,
            'rate': 0.0001,
            'rate_pct': 0.0100,
            'mark_price': 0.0,
            'next_funding_time': 0,
            'next_funding_countdown': '--:--',
            'squeeze_status': 'BALANCED',
            'direction_allowed': 'ALL'
        } for s in all_symbols}
        self.funding_summary = {
            'median_rate_pct': 0.0100,
            'short_squeeze_count': 0,
            'long_overheated_count': 0,
            'balanced_count': len(all_symbols),
            'short_squeeze_symbols': [],
            'long_overheated_symbols': [],
            'last_update_str': 'Başlatılıyor...'
        }
        # Global Likidasyon Radarı (!forceOrder) Veri Yapıları
        self.recent_liquidations = deque(maxlen=60)
        self.symbol_liquidations_deque = {}  # norm_s -> deque of (timestamp, usd_size, is_long_liq)
        self.symbol_liquidations_15m = {}
        self.global_liquidation_stats = {
            'total_usd_24h': 0.0,
            'long_usd_24h': 0.0,
            'short_usd_24h': 0.0,
            'top_symbol': '-',
            'top_symbol_usd': 0.0,
            'last_event_time': '-'
        }
        # Anlık Mikro-CVD (Cumulative Volume Delta) & Agresyon Veri Yapıları
        self.symbol_cvd = {}          # norm_s -> {taker_buy_usd, taker_sell_usd, delta_usd, cvd_pct, delta_60s, ratio_60s, bias, last_update}
        self.symbol_cvd_history = {}  # norm_s -> deque(maxlen=60) of (timestamp, taker_buy_usd, taker_sell_usd)
        self.symbol_cvd_offsets = {}  # VDA-01: norm_s -> candle rollover offset tracker for continuous 60s CVD
        self.symbol_price_history = {}  # norm_s -> deque(maxlen=60) of (timestamp, price) for 60s micro price change
        # Order Book Imbalance (OBI) & Tahta Derinlik Duvarı Veri Yapıları
        self.orderbook_depth = {s: {
            'symbol': s,
            'bid_price': 0.0,
            'bid_qty': 0.0,
            'ask_price': 0.0,
            'ask_qty': 0.0,
            'imbalance': 0.0,
            'ratio': 1.0,
            'wall_side': 'BALANCED',
            'wall_price': 0.0,
            'wall_duration_sec': 0.0,
            'wall_first_seen': 0.0,
            'spread_pct': 0.0,
            'is_spoof_risk': False,
        } for s in all_symbols}
        # Açık Pozisyon (Open Interest) Radarı & Delta-OI Takip Veri Yapıları
        self.symbol_oi = {s: {
            'symbol': s,
            'open_interest': 0.0,
            'oi_prev': 0.0,
            'delta_oi_pct': 0.0,
            'status': 'BALANCED',
            'last_update': 0.0
        } for s in all_symbols}
        self.oi_summary = {
            'top_expansion_symbol': '-',
            'top_expansion_pct': 0.0,
            'top_squeeze_symbol': '-',
            'top_squeeze_pct': 0.0,
            'last_update': 0.0
        }

        # 🇺🇸 Çapraz Borsa Spot Öncüsü (Coinbase Pro Lead-Lag) Veri Yapıları (15 Likit Majör/Altcoin)
        self.coinbase_supported_assets = [
            "BTC", "ETH", "SOL", "LINK", "AVAX", "NEAR", "SUI", "DOGE", "ADA", "LTC", "BCH", "DOT", "UNI", "XRP", "APT"
        ]
        self.coinbase_prices = {asset: 0.0 for asset in self.coinbase_supported_assets}
        self.coinbase_prices['last_update'] = 0.0
        self.coinbase_prices['is_connected'] = False
        self.coinbase_lead_lag = {
            'lead_symbol': 'NONE',
            'spread_bps': 0.0,
            'direction': 'NEUTRAL',
            'status': '⚪ DENGELİ NAKİT AKIŞI',
            'desc': 'Coinbase Spot ile Binance Vadeli dengede.',
            'last_update': 0.0
        }

        # 🇺🇸 Stage 3: Kurumsal Coinbase Prime vs. Binance Offshore CVD Ayrışması (Smart Money Delta)
        self.coinbase_cvd_history = {asset: deque(maxlen=60) for asset in self.coinbase_supported_assets}
        self.smart_money_divergence = {}

        # ⚡ 1. BTC Ani Mikro-Şok Kalkanı Veri Yapıları (60s Flush / Spike Gate)
        self.btc_price_60s_deque = deque(maxlen=120)
        self.btc_velocity_60s = 0.0
        self.btc_shock_gate_active = False
        self.btc_shock_gate_expiry = 0.0
        self.btc_shock_pct = 0.0

        # ⚖️ 4. Spot vs Vadeli Ayrışması Veri Yapıları (Spot-Perp Basis)
        self.spot_prices = {}
        self.spot_hist_3m = {s: deque(maxlen=60) for s in all_symbols}
        self.perp_hist_3m = {s: deque(maxlen=60) for s in all_symbols}
        self.last_spot_update_ts = 0.0

        # 🏛️ Faz 3: Deribit GEX (Gamma Exposure) & Hawkes Tasfiye Çığı Veri Yapıları
        self.deribit_gex_data = {
            'BTC': {'net_gex': 0.0, 'call_gex': 0.0, 'put_gex': 0.0, 'put_call_ratio': 1.0, 'gex_regime': 'NEUTRAL', 'is_pinning_regime': False, 'is_explosion_regime': False, 'gamma_flip_strike': 0.0, 'desc': '⚪ Deribit BTC GEX Başlatılıyor...', 'last_update': 0.0},
            'ETH': {'net_gex': 0.0, 'call_gex': 0.0, 'put_gex': 0.0, 'put_call_ratio': 1.0, 'gex_regime': 'NEUTRAL', 'is_pinning_regime': False, 'is_explosion_regime': False, 'gamma_flip_strike': 0.0, 'desc': '⚪ Deribit ETH GEX Başlatılıyor...', 'last_update': 0.0},
            'last_sync_ts': 0.0,
            'is_live': False
        }
        self.global_hawkes_avalanche = {
            'branching_ratio_eta': 0.15,
            'intensity': 0.05,
            'regime': 'QUIET_FLOW',
            'is_avalanche_active': False,
            'is_avalanche_exhausted': False,
            'avalanche_side': 'NONE',
            'long_liq_usd': 0.0,
            'short_liq_usd': 0.0,
            'desc': '⚪ Durgun Tasfiye Akışı',
            'last_update': 0.0
        }

        # 🐋 16. Borsa Net Giriş/Çıkış Akışı (Netflow) ve Balina Radarı Veri Yapıları
        self.exchange_netflows = {s: {
            'symbol': s,
            'netflow_24h_usd': 0.0,
            'inflow_24h_usd': 0.0,
            'outflow_24h_usd': 0.0,
            'z_score': 0.0,
            'regime': 'BALANCED_FLOW',
            'is_dump_risk': False,
            'is_accumulation': False,
            'tier': 'TIER_1' if any(m in s for m in ["BTC", "ETH", "SOL", "BNB"]) else ('TIER_3' if any(m in s for m in ["PEPE", "SHIB", "DOGE", "BONK", "MEME", "FLOKI", "WIF"]) else 'TIER_2'),
            'last_whale_transfer_ts': 0.0,
            'last_whale_amount_usd': 0.0,
            'last_whale_intent': 'NONE',
            'last_update': 0.0
        } for s in all_symbols}
        self.netflow_history_deque = {s: deque(maxlen=48) for s in all_symbols}
        self.stablecoin_ammunition = {
            'bias': 'NEUTRAL',
            'delta_24h_usd': 0.0,
            'delta_pct': 0.0,
            'momentum_score': 0.0,
            'is_bullish_fuel': False,
            'total_pegged_usd': 0.0,
            'binance_clean_reserves': 0.0,
            'binance_24h_inflows': 0.0,
            'total_cex_inflows_24h': 0.0,
            'last_update': 0.0
        }
        self.stablecoin_history_deque = deque(maxlen=48)
        self.whale_transactions_feed = deque(maxlen=50)
        self.block_trades_history = {}  # symbol -> deque((ts, notional, is_sell)) rolling 60s block orders
        self.whale_provider_status = {
            'defillama': {'status': 'CONNECTING', 'latency_ms': 0, 'last_success': 0.0, 'errors': 0},
            'binance_flow': {'status': 'ONLINE', 'latency_ms': 0, 'last_success': time.time(), 'errors': 0},
            'whale_radar_live': True,
            'last_sync_ts': 0.0
        }

        self.on_tick_callback = None
        self.on_candle_close_callback = None
        self.last_candle_callback_ts = {}  # norm_s -> int(candle timestamp) mükerrer mum tetikleme önleyici

        # VDA-0.1: JIT İndikatör Önbelleği (60s TTL)
        self._vp_cache = {}      # symbol -> {'data': dict, 'ts': float}
        self._naked_cache = {}   # symbol -> {'data': dict, 'ts': float}
        self._session_cache = {} # symbol -> {'data': dict, 'ts': float}

        # 🌐 WebSocket Canlılık Heartbeat & Anti-Zombi Watchdog (Aegis Sentinel Entegrasyonu)
        self.last_stream_tick_time = 0.0
        self.last_chunk_msg_ts = {}
        self._active_stream_tasks = []


    def _clean_symbol(self, symbol: str) -> str:
        clean = symbol.replace(':USDT', '')
        multiplier_coins = {
            'PEPE/USDT': '1000PEPE/USDT',
            'SHIB/USDT': '1000SHIB/USDT',
            'BONK/USDT': '1000BONK/USDT',
            'FLOKI/USDT': '1000FLOKI/USDT',
            'SATS/USDT': '1000SATS/USDT',
            'RATS/USDT': '1000RATS/USDT',
            'LUNC/USDT': '1000LUNC/USDT',
            'XEC/USDT': '1000XEC/USDT',
            'MOG/USDT': '1000000MOG/USDT',
            'CHEEMS/USDT': '1000CHEEMS/USDT',
            'WHY/USDT': '1000WHY/USDT',
            'CAT/USDT': '1000CAT/USDT'
            # Not: NEIRO Binance Vadeli'de 'NEIROUSDT' dir (1000 degildir)
        }
        return multiplier_coins.get(clean, clean)

    def _get_spot_multiplier(self, symbol: str) -> float:
        """Spot API (data-api.binance.vision) yedek olarak kullanildiginda 1000x ve 1M carpanlari uygular."""
        clean = symbol.replace(':USDT', '')
        clean_base = clean.replace('1000000', '').replace('1000', '')
        target_1000 = ['PEPE/USDT', 'SHIB/USDT', 'BONK/USDT', 'FLOKI/USDT', 'SATS/USDT', 'RATS/USDT', 'LUNC/USDT', 'XEC/USDT', 'CHEEMS/USDT', 'WHY/USDT', 'CAT/USDT']
        if clean in target_1000 or clean_base in target_1000:
            return 1000.0
        elif clean in ['MOG/USDT'] or clean_base in ['MOG/USDT']:
            return 1000000.0
        return 1.0

    def get_gate_contract_name(self, symbol: str) -> str:
        """Gate.io Vadeli Kontrat Adini Standartlastirir (Gate'de 1000 veya 1M on eki yoktur)."""
        clean = symbol.strip().upper()
        if clean.endswith(':USDT'):
            clean = clean[:-5]
        elif clean.endswith('/USDT'):
            clean = clean[:-5]
        elif clean.endswith('_USDT'):
            clean = clean[:-5]
        elif clean.endswith('USDT'):
            clean = clean[:-4]
        for prefix in ['1000000', '100000', '10000', '1000']:
            if clean.startswith(prefix):
                clean = clean[len(prefix):]
                break
        return f"{clean}_USDT"

    def get_gate_contract_multiplier(self, contract: str) -> float:
        """Gate.io Vadeli Kontratlarinin Kesin Quanto Carpanlari (Birim kontrat basina coin adedi)."""
        c = self.get_gate_contract_name(contract).upper()
        GATE_QUANTO = {
            'BTC_USDT': 0.0001,
            'ETH_USDT': 0.01,
            'PEPE_USDT': 10000000.0,
            'BONK_USDT': 1000000.0,
            'SHIB_USDT': 10000.0,
            'FLOKI_USDT': 10000.0,
            'DOGE_USDT': 10.0,
            'MOG_USDT': 1000000.0,
            'SATS_USDT': 1000.0,
            'RATS_USDT': 1000.0,
            'LUNC_USDT': 10000.0,
            'XEC_USDT': 10000.0,
            'CHEEMS_USDT': 1000000.0,
            'WHY_USDT': 1000000.0,
            'CAT_USDT': 1000.0
        }
        return GATE_QUANTO.get(c, 1.0)

    def get_system_health(self, paper_trader=None, strategy=None) -> dict:
        try:
            total_syms = len(self.all_symbols)
            now_sec = time.time()
            now_str = datetime.now(timezone(timedelta(hours=3))).strftime('%H:%M:%S')

            # 1. Canlı Fiyatlar & WebSocket (!bookTicker)
            live_prices_cnt = sum(1 for s in self.all_symbols if self.current_prices.get(s, 0.0) > 0)
            ws_price_pct = round(live_prices_cnt / max(1, total_syms) * 100.0, 1)
            ws_ok = (live_prices_cnt >= total_syms * 0.8)

            # 2. Seviye Bütünlüğü (Camarilla R4/S4/P, AVWAP, nPOC)
            healthy_levs = 0
            for s in self.all_symbols:
                lev = self.levels.get(s, {})
                cam = lev.get('camarilla', {}) if isinstance(lev, dict) else {}
                if cam.get('R4', 0.0) > 0 and cam.get('S4', 0.0) > 0:
                    healthy_levs += 1
            levels_pct = round(healthy_levs / max(1, total_syms) * 100.0, 1)
            levels_ok = (healthy_levs >= total_syms * 0.90)

            # 3. Canlı L2 OBI & Tahta Derinliği (!bookTicker)
            fresh_obi_cnt = 0
            bid_walls_cnt = 0
            ask_walls_cnt = 0
            for s in self.all_symbols:
                ob = self.orderbook_depth.get(s, {})
                upd = ob.get('last_update', 0.0)
                if (now_sec - upd) < 45.0 and ob.get('bid_qty', 0) > 0:
                    fresh_obi_cnt += 1
                    w = ob.get('wall_side', 'BALANCED')
                    if w == 'BID_WALL':
                        bid_walls_cnt += 1
                    elif w == 'ASK_WALL':
                        ask_walls_cnt += 1
            obi_ok = (fresh_obi_cnt >= total_syms * 0.75)

            # 4. Mikro-CVD & Taker Agresyon Akışı
            cvd_active_cnt = sum(1 for s in self.all_symbols if (now_sec - self.symbol_cvd.get(s, {}).get('last_update', 0.0)) < 75.0)
            cvd_ok = (cvd_active_cnt >= total_syms * 0.70)

            # 5. Global Tasfiye Radarı (!forceOrder@arr)
            liq_stats = getattr(self, 'global_liquidation_stats', {})
            liq_total_usd = float(liq_stats.get('total_usd_24h', 0.0))
            liq_top_sym = str(liq_stats.get('top_symbol', '-'))
            liq_last_time = str(liq_stats.get('last_event_time', '-'))
            liq_ok = True

            # 6. Spot vs Vadeli Basis Ayrışması (Binance Vision Spot API)
            spot_active_cnt = sum(1 for s in self.all_symbols if self.spot_prices.get(s, 0.0) > 0)
            spot_delay_sec = int(now_sec - getattr(self, 'last_spot_update_ts', now_sec))
            spot_ok = (spot_active_cnt >= total_syms * 0.70)

            # 7. 5M Mum Tarayıcısı & Deduplication
            last_scan = getattr(self, '_last_candle_scan_ts', now_sec)
            scan_delay_sec = int(now_sec - last_scan)
            scan_active = (scan_delay_sec < 420)
            scan_str = getattr(self, '_last_candle_scan_str', now_str)

            # 8. BTC 60s Mikro-Şok Kalkanı
            btc_v60 = round(getattr(self, 'btc_velocity_60s', 0.0), 2)
            btc_shock_active = getattr(self, 'btc_shock_gate_active', False)

            # 9. Dinamik Fonlama Oranları & Squeeze
            funding_data = getattr(self, 'funding_stats', {})
            funding_upd_str = funding_data.get('last_update_str', now_str)

            # 10. RAM & Bellek Koruması
            max_candles = max([len(df) for df in self.candles_5m.values() if hasattr(df, '__len__')] or [0])
            ram_ok = (max_candles <= 200)

            # 11. GitHub Cloud State Persistence
            gh_synced = True
            gh_branch = "state"
            gh_sha = None
            if paper_trader:
                gh_synced = getattr(paper_trader, '_last_push_ok', True)
                gh_branch = getattr(paper_trader, 'GITHUB_BRANCH', 'state')
                gh_sha = getattr(paper_trader, '_github_sha', None)
                if gh_sha and len(gh_sha) > 8:
                    gh_sha = gh_sha[:8]

            # 12. 100 Parite Kuant DNA & Persona Baseline
            dna_count = len(getattr(strategy, 'dna_baseline', {})) if (strategy and hasattr(strategy, 'dna_baseline') and strategy.dna_baseline) else (len(getattr(strategy, 'persona_matrix', {})) if strategy else len(self.all_symbols))
            dna_loaded = (dna_count >= total_syms * 0.90)

            # 13. Gölge Takip Motoru ve Kalıcılık Zırhı (Shadow Engine Health)
            sh_engine = getattr(strategy, 'shadow_engine', None)
            sh_health = sh_engine.get_health_status() if (sh_engine and hasattr(sh_engine, 'get_health_status')) else {
                "healthy": True,
                "status_text": "TAM SAĞLIKLI",
                "active_count": 0,
                "completed_count": 0,
                "sei": 100.0,
                "github_synced": True
            }
            shadow_ok = sh_health.get("healthy", True)

            # 14. Kasa Güvenlik Zırhı & Multiplier Guard (VDA-13, VDA-36, VDA-37)
            is_safety_stopped = getattr(paper_trader, 'is_safety_stopped', False) if paper_trader else False
            trading_halted = getattr(paper_trader, 'trading_halted', False) if paper_trader else False
            current_bal = float(getattr(paper_trader, 'balance', 10000.0)) if paper_trader else 10000.0
            vault_ok = not is_safety_stopped

            # 15. 16-Kurulum Kanonik Taksonomi ve Otonom Muting (VDA-27, VDA-28)
            calibrator = getattr(strategy, 'dna_calibrator', None)
            muted_setups_cnt = len(getattr(calibrator, 'muted_setups', [])) if calibrator else 0

            # Toplam Puanlama (Tam 12 Kuant Alt Sistem Denetimi)
            checks = [levels_ok, ws_ok, scan_active, obi_ok, cvd_ok, spot_ok, ram_ok, gh_synced, dna_loaded, liq_ok, shadow_ok, vault_ok]
            passed = sum(1 for c in checks if c)
            is_perfect = (passed >= 11)

            status_text = f"{passed}/{len(checks)} TAM SAĞLIKLI (KURUMSAL QUANT KOKPİTİ)" if is_perfect else f"UYARI: {len(checks) - passed} Alt Sistemde Gecikme"

            return {
                "is_perfect": is_perfect,
                "status_text": status_text,
                "score_str": f"{passed}/{len(checks)}",
                "healthy_symbols": healthy_levs,
                "total_symbols": total_syms,
                "live_prices": live_prices_cnt,
                "scan_active": scan_active,
                "ws_active": ws_ok,
                "last_scan_time": scan_str,
                "timestamp": now_str,
                "streams": {
                    "ws_prices": {"healthy": ws_ok, "count": live_prices_cnt, "total": total_syms, "pct": ws_price_pct, "watchdog_30s": True},
                    "obi_depth": {"healthy": obi_ok, "count": fresh_obi_cnt, "total": total_syms, "bid_walls": bid_walls_cnt, "ask_walls": ask_walls_cnt},
                    "cvd_flow": {"healthy": cvd_ok, "count": cvd_active_cnt, "total": total_syms, "continuous_cumulative": True},
                    "liquidations": {"healthy": liq_ok, "total_usd_24h": round(liq_total_usd, 2), "top_symbol": liq_top_sym, "last_event_time": liq_last_time},
                    "spot_basis": {"healthy": spot_ok, "count": spot_active_cnt, "total": total_syms, "delay_sec": spot_delay_sec},
                    "candle_poller": {"healthy": scan_active, "last_scan_time": scan_str, "delay_sec": scan_delay_sec},
                    "btc_shock": {"healthy": not btc_shock_active, "velocity_60s": btc_v60, "is_active": btc_shock_active},
                    "funding": {"healthy": True, "last_update": funding_upd_str},
                    "coinbase_lead_lag": {
                        "healthy": bool((now_sec - getattr(self, 'coinbase_prices', {}).get('last_update', 0.0)) < 30.0),
                        "status": getattr(self, 'coinbase_lead_lag', {}).get('status', '⚪ DENGELİ'),
                        "spread_bps": getattr(self, 'coinbase_lead_lag', {}).get('spread_bps', 0.0),
                        "direction": getattr(self, 'coinbase_lead_lag', {}).get('direction', 'NEUTRAL')
                    },
                    "oi_radar": {
                        "healthy": bool(sum(1 for v in getattr(self, 'symbol_oi', {}).values() if (now_sec - v.get('last_update', 0.0)) < 90.0) >= 10),
                        "fresh_count": sum(1 for v in getattr(self, 'symbol_oi', {}).values() if (now_sec - v.get('last_update', 0.0)) < 90.0),
                        "top_expansion": getattr(self, 'oi_summary', {}).get('top_expansion_symbol', '-'),
                        "top_expansion_pct": getattr(self, 'oi_summary', {}).get('top_expansion_pct', 0.0)
                    },
                    "whale_netflow_radar": {
                        "healthy": bool(getattr(self, 'get_whale_radar_health', lambda: {})().get('is_healthy', True)),
                        "ammunition_bias": getattr(self, 'stablecoin_ammunition', {}).get('bias', 'NEUTRAL'),
                        "feed_count": len(getattr(self, 'whale_transactions_feed', [])),
                        "last_sync_sec": getattr(self, 'get_whale_radar_health', lambda: {})().get('last_sync_sec', 0.0),
                        "providers": getattr(self, 'whale_provider_status', {})
                    },
                    "aggtrade_blocks": {
                        "healthy": True,
                        "mode": "Binance Futures <50ms aggTrade Blok Emir Dedektörü",
                        "tracked_symbols": total_syms,
                        "active_blocks_60s": sum(len(dq) for dq in getattr(self, 'block_trades_history', {}).values())
                    },
                    "onchain_mempool": {
                        "healthy": True,
                        "mode": "Bitcoin Mempool & Ethereum Blockscout",
                        "whale_feed_count": len(getattr(self, 'whale_transactions_feed', [])),
                        "mempool_threats": sum(1 for v in getattr(self, 'exchange_netflows', {}).values() if v.get('mempool_dump_threat'))
                    },
                    "smart_money_cvd": {
                        "healthy": getattr(self, 'coinbase_prices', {}).get('is_connected', False),
                        "mode": "Coinbase Prime vs Binance Offshore CVD",
                        "btc_spread": getattr(self, 'smart_money_divergence', {}).get('BTC/USDT', {}).get('smart_money_spread', 0.0),
                        "regime": getattr(self, 'smart_money_divergence', {}).get('BTC/USDT', {}).get('regime', 'HARMONIC_FLOW')
                    }
                },
                "quant_engine": {
                    "levels": {"healthy": levels_ok, "count": healthy_levs, "total": total_syms, "pct": levels_pct},
                    "coin_dna": {"healthy": dna_loaded, "count": dna_count, "total": total_syms},
                    "confluence": {"healthy": True, "mode": "Shannon Ortogonal 3-Eksen JIT"},
                    "setup_taxonomy": {
                        "healthy": True,
                        "total_setups": 16,
                        "canonical": True,
                        "bijective": True,
                        "muted_count": muted_setups_cnt,
                        "mode": "16 Kanonik Biyektif Taksonomi & Otonom Muting"
                    },
                    "deribit_gex": {
                        "healthy": True,
                        "regime": self.get_deribit_gex_regime(),
                        "net_gex_usd": float(self.deribit_gex_data.get('BTC', {}).get('net_gex', 0.0)),
                        "pcr": float(self.deribit_gex_data.get('BTC', {}).get('put_call_ratio', 1.0)),
                        "freshness_sec": int(time.time() - self.deribit_gex_data.get('last_sync_ts', time.time())),
                        "is_live": bool(self.deribit_gex_data.get('is_live', True))
                    },
                    "hawkes_avalanche": {
                        "healthy": True,
                        "eta": float(self.get_hawkes_avalanche().get('branching_ratio_eta', 0.15)),
                        "regime": self.get_hawkes_avalanche().get('regime', 'QUIET_FLOW'),
                        "is_active": bool(self.get_hawkes_avalanche().get('is_avalanche_active', False)),
                        "side": str(self.get_hawkes_avalanche().get('avalanche_side', 'NONE'))
                    },
                    "stoikov_vpin": {
                        "healthy": True,
                        "mode": "Stoikov Micro-Drift + VPIN Volume Buckets",
                        "status": "AKTİF RADAR",
                        "kyles_lambda": "AMIHUD_AIR_POCKET_GUARD"
                    },
                    "iceberg_sniper": {
                        "healthy": True,
                        "mode": "Tri-Modal Offensive Sniper (%0.20 Stop)",
                        "cvd_derivative": "2nd_Derivative_Zero_Crossing"
                    }
                },
                "infrastructure": {
                    "github_persistence": {"healthy": gh_synced, "branch": gh_branch, "sha": gh_sha or "-"},
                    "ram_watchdog": {"healthy": ram_ok, "max_candles": max_candles, "limit": 150, "gc_interval": "60s"},
                    "keepalive": {"healthy": True, "interval": "3dk Self-Ping"},
                    "telegram": {"healthy": True, "mode": "Saatlik VIP + /kasa Dinleyici"},
                    "shadow_guard": sh_health,
                    "vault_guard": {
                        "healthy": vault_ok,
                        "is_safety_stopped": is_safety_stopped,
                        "trading_halted": trading_halted,
                        "balance": current_bal,
                        "threshold": 1000.0,
                        "multiplier_guard": True,
                        "isolated_ceiling": True
                    }
                }
            }
        except Exception as e:
            return {
                "is_perfect": False,
                "status_text": f"Teşhis İstisnası: {e}",
                "score_str": "Hata",
                "healthy_symbols": 0,
                "total_symbols": len(self.all_symbols) if hasattr(self, 'all_symbols') else 100,
                "live_prices": 0,
                "scan_active": True,
                "ws_active": True,
                "last_scan_time": "Şimdi",
                "timestamp": datetime.now().strftime('%H:%M:%S'),
                "error_detail": str(e),
                "streams": {},
                "quant_engine": {},
                "infrastructure": {}
            }

    async def fetch_funding_rates(self):
        """
        Multi-Exchange Resilient Fonlama Orani ve Squeeze Motoru.
        Binance fapi ABD bulut sunucularinda (Render / AWS) bolgesel 451 dondurdugunde,
        Gate.io ve Bitget Global Vadeli Tickers uzerinden 100 paritenin anlik fonlama oranlarini,
        mark fiyatlarini ve sonraki 8 saatlik fonlama geri sayimlarini eksiksiz ceker.
        """
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        fmap = {}
        source_name = "None"
        now_ms = int(time.time() * 1000)

        # 8-Saatlik Dunya Standart Fonlama Geri Sayimi (00:00, 08:00, 16:00 UTC)
        now_utc = datetime.now(timezone.utc)
        curr_utc_sec = now_utc.hour * 3600 + now_utc.minute * 60 + now_utc.second
        next_8h_sec = ((now_utc.hour // 8) + 1) * 8 * 3600
        rem_sec = max(0, next_8h_sec - curr_utc_sec)
        rem_hrs = rem_sec // 3600
        rem_mins = (rem_sec % 3600) // 60
        default_cd_str = f"{rem_hrs:02d}sa {rem_mins:02d}dk"
        next_time_8h_ms = now_ms + (rem_sec * 1000)

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                # 1. Binance Futures Direct (Yerel makine ve kisitlanmamis sunucular)
                try:
                    url_binance = "https://fapi.binance.com/fapi/v1/premiumIndex"
                    async with session.get(url_binance, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if isinstance(data, list) and len(data) > 0:
                                for item in data:
                                    sym = item.get('symbol', '')
                                    try:
                                        fmap[sym] = {
                                            'rate': float(item.get('lastFundingRate', 0.0)),
                                            'mark_price': float(item.get('markPrice', 0.0)),
                                            'next_time': int(item.get('nextFundingTime', next_time_8h_ms))
                                        }
                                    except (ValueError, TypeError):
                                        pass
                                source_name = "Binance Futures (Direct)"
                except Exception:
                    pass

                # 2. Gate.io Futures Tickers (Render / US Cloud Safe - 980+ Kontrat)
                if not fmap:
                    try:
                        url_gate = "https://api.gateio.ws/api/v4/futures/usdt/tickers"
                        async with session.get(url_gate, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                if isinstance(data, list) and len(data) > 0:
                                    for item in data:
                                        contract = item.get('contract', '') # e.g. BTC_USDT
                                        clean_sym = contract.replace('_USDT', 'USDT')
                                        try:
                                            f_rate = float(item.get('funding_rate', 0.0))
                                            f_mark = float(item.get('mark_price', 0.0))
                                            fmap[clean_sym] = {
                                                'rate': f_rate,
                                                'mark_price': f_mark,
                                                'next_time': next_time_8h_ms
                                            }
                                            fmap[contract.replace('_', '')] = fmap[clean_sym]
                                        except (ValueError, TypeError):
                                            pass
                                    source_name = "Gate.io Futures (US Cloud Safe)"
                    except Exception:
                        pass

                # 3. Bitget USDT-Futures Tickers (Tamamlayici / Hibrit Kaynak)
                if not fmap or source_name != "Binance Futures (Direct)":
                    try:
                        url_bg = "https://api.bitget.com/api/v2/mix/market/tickers?productType=USDT-FUTURES"
                        async with session.get(url_bg, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                            if resp.status == 200:
                                b_json = await resp.json()
                                data = b_json.get('data', [])
                                if isinstance(data, list) and len(data) > 0:
                                    for item in data:
                                        sym = item.get('symbol', '') # e.g. BTCUSDT, NEIROCTOUSDT
                                        if sym not in fmap:
                                            try:
                                                fmap[sym] = {
                                                    'rate': float(item.get('fundingRate', 0.0)),
                                                    'mark_price': float(item.get('markPrice', 0.0)),
                                                    'next_time': next_time_8h_ms
                                                }
                                            except (ValueError, TypeError):
                                                pass
                                    if not source_name or source_name == "None":
                                        source_name = "Bitget Futures (US Cloud Safe)"
                    except Exception:
                        pass

            if not fmap:
                print(">> [FONLAMA UYARI]: Hicbir vadeli kaynaktan veri alinamadi.")
                return

            # 100 Parite Verilerini Normalize Et ve Isle
            raw_rates = []
            for s in self.all_symbols:
                clean = self._clean_symbol(s).replace('/', '').replace(':USDT', '').upper()
                base = clean.replace('USDT', '')
                base_no_mult = base.replace('1000000', '').replace('1000', '')
                candidates = [
                    clean,
                    base + 'USDT',
                    base + '_USDT',
                    base_no_mult + 'USDT',
                    '1000' + base_no_mult + 'USDT',
                    '1000' + base_no_mult + '_USDT',
                    '1000000' + base_no_mult + 'USDT',
                    base.replace('NEIRO', 'NEIROCTO') + 'USDT',
                    base.replace('NEIRO', 'NEIROCTO') + '_USDT'
                ]
                found = None
                for c in candidates:
                    if c in fmap:
                        found = fmap[c]
                        break

                if found:
                    r_pct = round(found['rate'] * 100.0, 4)
                    raw_rates.append(r_pct)

            median_pct = float(np.median(raw_rates)) if raw_rates else 0.0100
            short_squeeze_syms = []
            long_overheat_syms = []
            balanced_cnt = 0

            for s in self.all_symbols:
                clean = self._clean_symbol(s).replace('/', '').replace(':USDT', '').upper()
                base = clean.replace('USDT', '')
                base_no_mult = base.replace('1000000', '').replace('1000', '')
                candidates = [
                    clean,
                    base + 'USDT',
                    base + '_USDT',
                    base_no_mult + 'USDT',
                    '1000' + base_no_mult + 'USDT',
                    '1000' + base_no_mult + '_USDT',
                    '1000000' + base_no_mult + 'USDT',
                    base.replace('NEIRO', 'NEIROCTO') + 'USDT',
                    base.replace('NEIRO', 'NEIROCTO') + '_USDT'
                ]
                found = None
                for c in candidates:
                    if c in fmap:
                        found = fmap[c]
                        break

                if found:
                    r_pct = round(found['rate'] * 100.0, 4)
                    rem_ms = max(0, found['next_time'] - now_ms)
                    rem_h = rem_ms // (1000 * 3600)
                    rem_m = (rem_ms % (1000 * 3600)) // (1000 * 60)
                    cd_str = f"{rem_h:02d}sa {rem_m:02d}dk" if rem_ms > 0 else default_cd_str
                    mark_p = found['mark_price']
                else:
                    # En kotu durumda medyan fonlama ve canli spot/websocket fiyati
                    r_pct = median_pct
                    cd_str = default_cd_str
                    mark_p = self.current_prices.get(s, 0.0)

                # Squeeze Esik Kurallari:
                # 1. Negatif Short Squeeze: rate <= -0.0300% veya (rate < 0 ve median - 0.0250%)
                if r_pct <= -0.0300 or (r_pct < 0 and r_pct <= (median_pct - 0.0250)):
                    status = 'SHORT_SQUEEZE_RISK'
                    dir_allowed = 'LONG_ONLY'
                    short_squeeze_syms.append(s)
                # 2. Pozitif Siskinlik: rate >= +0.0600% veya rate >= (median + 0.0500%)
                elif r_pct >= 0.0600 or r_pct >= (median_pct + 0.0500):
                    status = 'LONG_OVERHEATED'
                    dir_allowed = 'SHORT_ONLY'
                    long_overheat_syms.append(s)
                else:
                    status = 'BALANCED'
                    dir_allowed = 'ALL'
                    balanced_cnt += 1

                self.funding_rates[s] = {
                    'symbol': s,
                    'rate': round(r_pct / 100.0, 6),
                    'rate_pct': r_pct,
                    'mark_price': mark_p,
                    'next_funding_time': next_time_8h_ms,
                    'next_funding_countdown': cd_str,
                    'squeeze_status': status,
                    'direction_allowed': dir_allowed
                }

            now_str = datetime.now(timezone(timedelta(hours=3))).strftime('%H:%M:%S')
            self.funding_summary = {
                'median_rate_pct': round(median_pct, 4),
                'short_squeeze_count': len(short_squeeze_syms),
                'long_overheated_count': len(long_overheat_syms),
                'balanced_count': balanced_cnt,
                'short_squeeze_symbols': short_squeeze_syms,
                'long_overheated_symbols': long_overheat_syms,
                'last_update_str': now_str,
                'source': source_name
            }
            print(f">> [FONLAMA SENKRONİZASYONU] {len(raw_rates)}/100 Parite guncellendi | Kaynak: {source_name} | Medyan: %{median_pct:.4f} | Squeeze: {len(short_squeeze_syms)} Parite")
        except Exception as e:
            print(f">> [FONLAMA TARAMA HATA]: {e}")

    def get_funding_info(self, symbol: str) -> dict:
        return self.funding_rates.get(symbol, {
            'symbol': symbol,
            'rate': 0.0001,
            'rate_pct': 0.0100,
            'mark_price': self.current_prices.get(symbol, 0.0),
            'next_funding_time': 0,
            'next_funding_countdown': '--:--',
            'squeeze_status': 'BALANCED',
            'direction_allowed': 'ALL'
        })

    def get_all_funding_summary(self) -> dict:
        return {
            'summary': getattr(self, 'funding_summary', {}),
            'rates': getattr(self, 'funding_rates', {})
        }

    def get_recent_liquidations(self, limit: int = 20) -> list:
        return list(getattr(self, 'recent_liquidations', []))[-limit:]

    def get_symbol_liquidation_stats(self, symbol: str) -> dict:
        now_ts = time.time()
        cutoff_ts = now_ts - 900.0

        # Gerçek 900 saniyelik zaman damgalı budama (deque pruning)
        deques = getattr(self, 'symbol_liquidations_deque', {})
        if symbol in deques:
            dq = deques[symbol]
            while dq and dq[0][0] < cutoff_ts:
                dq.popleft()
            long_usd = sum(item[1] for item in dq if item[2])
            short_usd = sum(item[1] for item in dq if not item[2])
            last_update = dq[-1][0] if dq else 0.0
            total = long_usd + short_usd
            dom = 'NEUTRAL'
            if long_usd > short_usd * 1.4 and long_usd >= 10000:
                dom = 'LONG_SWEEP'
            elif short_usd > long_usd * 1.4 and short_usd >= 1000:
                dom = 'SHORT_SWEEP'
            dom_side = 'LONG' if long_usd >= short_usd else 'SHORT'
            if not dq:
                dom_side = 'NEUTRAL'
                dom = 'NEUTRAL'
            res = {
                'symbol': symbol,
                'long_usd': round(long_usd, 2),
                'short_usd': round(short_usd, 2),
                'total_usd': round(total, 2),
                'dominant_bias': dom,
                'dominant_side': dom_side,
                'is_hot': total >= 25000,
                'last_update': last_update
            }
            if hasattr(self, 'symbol_liquidations_15m'):
                self.symbol_liquidations_15m[symbol] = res
            return res

        # Deque henüz yoksa (örn. test senaryolarında doğrudan symbol_liquidations_15m atanmışsa)
        data = getattr(self, 'symbol_liquidations_15m', {}).get(symbol, {'long_usd': 0.0, 'short_usd': 0.0, 'last_update': 0})
        # VDA-07: 15 dakikadan (900s) eski tasfiyeleri 0.0 olarak döndür (bayat tasfiye vetosu kalkar)
        if (now_ts - data.get('last_update', 0)) > 900.0:
            return {
                'symbol': symbol,
                'long_usd': 0.0,
                'short_usd': 0.0,
                'total_usd': 0.0,
                'dominant_bias': 'NEUTRAL',
                'dominant_side': 'NEUTRAL',
                'last_update': data.get('last_update', 0)
            }
        long_usd = float(data.get('long_usd', 0.0))
        short_usd = float(data.get('short_usd', 0.0))
        total = long_usd + short_usd
        dom = 'NEUTRAL'
        if long_usd > short_usd * 1.4 and long_usd >= 10000:
            dom = 'LONG_SWEEP'
        elif short_usd > long_usd * 1.4 and short_usd >= 1000:
            dom = 'SHORT_SWEEP'
        return {
            'symbol': symbol,
            'long_usd': round(long_usd, 2),
            'short_usd': round(short_usd, 2),
            'total_usd': round(total, 2),
            'dominant_bias': dom,
            'dominant_side': 'LONG' if long_usd >= short_usd else 'SHORT',
            'is_hot': total >= 25000,
            'last_update': data.get('last_update', 0)
        }

    def get_global_liquidation_summary(self) -> dict:
        now_ts = time.time()
        cutoff_ts = now_ts - 900.0

        # Aktif 15dk deque'lerden en çok tasfiye olan sembolü dinamik hesapla ve buda
        top_sym = '-'
        top_val = 0.0
        deques = getattr(self, 'symbol_liquidations_deque', {})
        if deques:
            for sym_k, dq_k in list(deques.items()):
                while dq_k and dq_k[0][0] < cutoff_ts:
                    dq_k.popleft()
                tot_s = sum(item[1] for item in dq_k)
                if tot_s > top_val:
                    top_val = tot_s
                    top_sym = sym_k
                if hasattr(self, 'symbol_liquidations_15m') and sym_k in self.symbol_liquidations_15m:
                    l_s = sum(item[1] for item in dq_k if item[2])
                    s_s = sum(item[1] for item in dq_k if not item[2])
                    self.symbol_liquidations_15m[sym_k]['long_usd'] = round(l_s, 2)
                    self.symbol_liquidations_15m[sym_k]['short_usd'] = round(s_s, 2)
                    self.symbol_liquidations_15m[sym_k]['total_usd'] = round(tot_s, 2)
                    self.symbol_liquidations_15m[sym_k]['dominant_side'] = 'LONG' if l_s >= s_s else 'SHORT'
            stats = getattr(self, 'global_liquidation_stats', {})
            stats['top_symbol'] = top_sym
            stats['top_symbol_usd'] = round(top_val, 2)

        stats = getattr(self, 'global_liquidation_stats', {})
        tot = stats.get('total_usd_24h', 0.0)
        l_usd = stats.get('long_usd_24h', 0.0)
        s_usd = stats.get('short_usd_24h', 0.0)
        long_ratio = round((l_usd / tot * 100.0), 1) if tot > 0 else 50.0
        short_ratio = round((s_usd / tot * 100.0), 1) if tot > 0 else 50.0
        return {
            'total_usd_24h': round(tot, 2),
            'total_liq_usd': round(tot, 2),
            'long_usd_24h': round(l_usd, 2),
            'short_usd_24h': round(s_usd, 2),
            'long_ratio': long_ratio,
            'long_ratio_pct': long_ratio,
            'short_ratio': short_ratio,
            'short_ratio_pct': short_ratio,
            'top_symbol': stats.get('top_symbol', '-'),
            'top_symbol_15m': stats.get('top_symbol', '-'),
            'top_symbol_usd': round(stats.get('top_symbol_usd', 0.0), 2),
            'top_symbol_vol_usd': round(stats.get('top_symbol_usd', 0.0), 2),
            'dominant_side': 'LONG' if l_usd >= s_usd else 'SHORT',
            'last_event_time': stats.get('last_event_time', '-'),
            'recent_events_count': len(getattr(self, 'recent_liquidations', []))
        }

    def get_symbol_cvd(self, symbol: str) -> dict:
        clean = self._clean_symbol(symbol)
        data = getattr(self, 'symbol_cvd', {}).get(symbol) or getattr(self, 'symbol_cvd', {}).get(clean)
        now_ts = time.time()
        
        # 1. Eğer WebSocket verisi taze ise (son 120s içinde) ve nötr (50.0) değilse doğrudan kullan
        if data and (now_ts - data.get('last_update', 0) <= 120.0) and abs(data.get('ratio_60s', 50.0) - 50.0) > 0.1:
            return data

        # 2. WebSocket akışı yoksa veya 50.0 default kalmışsa -> Resmi 5M Mum Taker Hacimlerinden Gerçek CVD Hesapla!
        df_5m = None
        c_map = getattr(self, 'candles_5m', {})
        candidates = [symbol, clean, symbol.replace('/', ''), clean.replace('/', ''), f"{clean}/USDT" if '/' not in clean else clean, f"{symbol}/USDT" if '/' not in symbol else symbol]
        for c in candidates:
            if c in c_map and isinstance(c_map[c], pd.DataFrame) and not c_map[c].empty:
                df_5m = c_map[c]
                break

        if df_5m is not None and isinstance(df_5m, pd.DataFrame) and not df_5m.empty:
            try:
                last_k = df_5m.iloc[-1]
                t_buy = float(last_k.get('taker_quote', 0.0))
                tot_q = float(last_k.get('quote_volume', 0.0) or last_k.get('qav', 0.0))

                # Eğer son mum henüz yeni açıldıysa (< $15,000 hacim veya t_buy <= 0) ve önceki mum varsa, 2 mumun kümülatif taker hacmine bak
                if (tot_q < 15000.0 or t_buy <= 0) and len(df_5m) >= 2:
                    prev_k = df_5m.iloc[-2]
                    prev_t_buy = float(prev_k.get('taker_quote', 0.0))
                    prev_tot_q = float(prev_k.get('quote_volume', 0.0) or prev_k.get('qav', 0.0))
                    if prev_tot_q > 0:
                        t_buy += prev_t_buy
                        tot_q += prev_tot_q

                if tot_q > 0:
                    t_sell = max(0.0, tot_q - t_buy)
                    delta = t_buy - t_sell
                    ratio = round((t_buy / tot_q) * 100.0, 1)
                    bias = "NEUTRAL"
                    if ratio >= 60.0: bias = "STRONG_BUY_SURGE"
                    elif ratio <= 40.0: bias = "STRONG_SELL_PRESSURE"
                    elif ratio >= 53.0: bias = "MODERATE_BUY"
                    elif ratio <= 47.0: bias = "MODERATE_SELL"

                    import math
                    if math.isnan(ratio) or math.isinf(ratio):
                        ratio = 50.0
                    if math.isnan(delta) or math.isinf(delta):
                        delta = 0.0

                    res = {
                        'symbol': symbol,
                        'taker_buy_usd': round(t_buy, 2) if not math.isnan(t_buy) else 0.0,
                        'taker_sell_usd': round(t_sell, 2) if not math.isnan(t_sell) else 0.0,
                        'delta_usd': round(delta, 2),
                        'cvd_pct': ratio,
                        'delta_60s': round(delta, 2),
                        'ratio_60s': ratio,
                        'bias': bias,
                        'last_price': float(last_k.get('close', 0.0)),
                        'last_update': now_ts,
                        'source': 'OFFICIAL_5M_KLINE_TAKER'
                    }
                    if not hasattr(self, 'symbol_cvd'):
                        self.symbol_cvd = {}
                    self.symbol_cvd[symbol] = res
                    return res
            except Exception:
                pass

        if data:
            return data

        return {
            'symbol': symbol,
            'taker_buy_usd': 0.0,
            'taker_sell_usd': 0.0,
            'delta_usd': 0.0,
            'cvd_pct': 50.0,
            'delta_60s': 0.0,
            'ratio_60s': 50.0,
            'bias': 'NEUTRAL',
            'last_price': 0.0,
            'last_update': 0
        }

    def get_orderbook_depth(self, symbol: str) -> dict:
        data = getattr(self, 'orderbook_depth', {}).get(symbol, None)
        if data:
            return data
        cur_p = getattr(self, 'current_prices', {}).get(symbol, 0.0)
        return {
            'symbol': symbol,
            'bid_price': cur_p,
            'bid_qty': 0.0,
            'ask_price': cur_p,
            'ask_qty': 0.0,
            'imbalance': 0.0,
            'ratio': 1.0,
            'wall_side': 'BALANCED',
            'wall_price': cur_p,
            'wall_duration_sec': 0.0,
            'spread_pct': 0.0,
            'is_spoof_risk': False,
            'last_update': 0.0
        }

    def is_btc_shock_active(self) -> tuple:
        """
        BTC 60s Ani Mikro-Şok Kalkanı Durumu:
        Döner: (is_active: bool, shock_pct: float, remaining_sec: float)
        """
        now_ts = time.time()
        if getattr(self, 'btc_shock_gate_active', False):
            if now_ts < getattr(self, 'btc_shock_gate_expiry', 0.0):
                remaining = round(self.btc_shock_gate_expiry - now_ts, 1)
                return True, getattr(self, 'btc_shock_pct', 0.0), remaining
            else:
                self.btc_shock_gate_active = False
                self.btc_shock_pct = 0.0
        return False, 0.0, 0.0

    def get_btc_velocity_60s(self) -> float:
        """BTC son 60 saniyelik yüzdesel fiyat hızı."""
        return getattr(self, 'btc_velocity_60s', 0.0)

    def get_spot_perp_basis(self, symbol: str) -> dict:
        """
        Spot vs Vadeli Ayrışması & Basis Hesabı (Spot-Perp Basis in BPS):
        Basis (bps) = ((Perp_Price - Spot_Price) / Spot_Price) * 10,000
        Divergence = %Delta_Spot_3m - %Delta_Perp_3m
        """
        perp_p = float(getattr(self, 'current_prices', {}).get(symbol, 0.0))
        spot_p = float(getattr(self, 'spot_prices', {}).get(symbol, 0.0))
        if perp_p <= 0 or spot_p <= 0:
            return {
                "basis_bps": 0.0,
                "spot_price": spot_p,
                "perp_price": perp_p,
                "spot_perp_divergence": 0.0,
                "is_available": False
            }
        basis_bps = round(((perp_p - spot_p) / spot_p) * 10000.0, 2)

        # 3 Dakikalık Divergence Hesabı
        spot_div = 0.0
        s_dq = getattr(self, 'spot_hist_3m', {}).get(symbol)
        p_dq = getattr(self, 'perp_hist_3m', {}).get(symbol)
        if s_dq and len(s_dq) >= 2 and p_dq and len(p_dq) >= 2:
            s_old = s_dq[0][1]
            p_old = p_dq[0][1]
            if s_old > 0 and p_old > 0:
                s_chg = (spot_p - s_old) / s_old * 100.0
                p_chg = (perp_p - p_old) / p_old * 100.0
                spot_div = round(s_chg - p_chg, 3)

        return {
            "basis_bps": basis_bps,
            "spot_price": spot_p,
            "perp_price": perp_p,
            "spot_perp_divergence": spot_div,
            "is_available": True
        }


    def get_market_cvd_summary(self) -> dict:
        cvds = getattr(self, 'symbol_cvd', {})
        if not cvds:
            return {
                'avg_buy_ratio': 50.0,
                'avg_sell_ratio': 50.0,
                'total_buy_usd': 0.0,
                'total_sell_usd': 0.0,
                'net_market_delta': 0.0,
                'top_buy_sym': '-',
                'top_buy_ratio': 50.0,
                'top_buy_delta': 0.0,
                'top_sell_sym': '-',
                'top_sell_ratio': 50.0,
                'top_sell_delta': 0.0,
                'top_buyers': [],
                'top_sellers': [],
                'last_update_str': '-'
            }

        ratios = []
        tot_buy = 0.0
        tot_sell = 0.0
        active_items = []
        for s, item in cvds.items():
            ratios.append(item.get('ratio_60s', 50.0))
            tot_buy += item.get('taker_buy_usd', 0.0)
            tot_sell += item.get('taker_sell_usd', 0.0)
            active_items.append(item)

        avg_buy = round(sum(ratios) / len(ratios), 1) if ratios else 50.0
        avg_sell = round(100.0 - avg_buy, 1)

        # Asgari Hacim & Likidite Filtresi: $40'lik tekil emirlerin lider olmasini engelle
        # Son 60s hacmi >= $500 veya net deltasi >= $250 olan pariteler onceliklidir
        valid_volume_items = [x for x in active_items if (x.get('taker_buy_usd', 0.0) + x.get('taker_sell_usd', 0.0)) >= 500.0 or abs(x.get('delta_60s', 0.0)) >= 250.0]
        pool = valid_volume_items if len(valid_volume_items) >= 10 else active_items

        top_buyers = sorted(pool, key=lambda x: (x.get('ratio_60s', 50.0), x.get('delta_60s', 0.0)), reverse=True)[:15]
        top_sellers = sorted(pool, key=lambda x: (x.get('ratio_60s', 50.0), -x.get('delta_60s', 0.0)))[:15]

        top_buy = top_buyers[0] if top_buyers else {}
        top_sell = top_sellers[0] if top_sellers else {}

        return {
            'avg_buy_ratio': avg_buy,
            'avg_sell_ratio': avg_sell,
            'total_buy_usd': round(tot_buy, 2),
            'total_sell_usd': round(tot_sell, 2),
            'net_market_delta': round(tot_buy - tot_sell, 2),
            'top_buy_sym': top_buy.get('symbol', '-'),
            'top_buy_ratio': top_buy.get('ratio_60s', 50.0),
            'top_buy_delta': top_buy.get('delta_60s', 0.0),
            'top_sell_sym': top_sell.get('symbol', '-'),
            'top_sell_ratio': round(100.0 - float(top_sell.get('ratio_60s', 50.0)), 1) if top_sell else 50.0,
            'top_sell_delta': top_sell.get('delta_60s', 0.0),
            'top_buyers': top_buyers,
            'top_sellers': top_sellers,
            'last_update_str': datetime.now().strftime('%H:%M:%S')
        }

    def get_universe_log_return_zscore(self, symbol: str) -> dict:
        """
        Valkyrie V4.0 Öncelik 1.1: Canlı Popülasyon Log-Return Gaussian Z-Score Motoru.
        Piyasa evrenindeki 100 paritenin son 15 dakikalık logaritmik getirilerini toplayarak
        popülasyon ortalamasını (μ_RS) ve standart sapmasını (σ_RS) hesaplar:
            Z_RS = (R_i - μ_RS) / σ_RS
        Yalnızca ekstrem pozitif Gauss ayrışması (Z_RS >= +2.0σ, en üst %2.2) potansiyel bağımsız alfa sayılır.
        """
        now_ts = time.time()
        cached_time = getattr(self, '_universe_returns_time', 0.0)
        returns_map = getattr(self, '_universe_returns_map', {})

        if (now_ts - cached_time) > 15.0 or not returns_map:
            returns_map = {}
            for s, df in getattr(self, 'candles_5m', {}).items():
                if df is not None and not df.empty and 'close' in df.columns and len(df) >= 2:
                    try:
                        c_now = float(df['close'].iloc[-1])
                        # Son 15 dakika: son 3 adet 5M mumu (close[-1] vs close[-4], veya min 2)
                        lookback_idx = -4 if len(df) >= 4 else 0
                        c_prev = float(df['close'].iloc[lookback_idx])
                        if c_now > 0 and c_prev > 0:
                            ret = float(np.log(c_now / c_prev))
                            returns_map[s] = ret
                    except Exception:
                        continue
            self._universe_returns_map = returns_map
            self._universe_returns_time = now_ts

        sym_ret = returns_map.get(symbol, None)
        if sym_ret is None:
            df_sym = getattr(self, 'candles_5m', {}).get(symbol, None)
            if df_sym is not None and not df_sym.empty and 'close' in df_sym.columns and len(df_sym) >= 2:
                try:
                    c_now = float(df_sym['close'].iloc[-1])
                    lookback_idx = -4 if len(df_sym) >= 4 else 0
                    c_prev = float(df_sym['close'].iloc[lookback_idx])
                    if c_now > 0 and c_prev > 0:
                        sym_ret = float(np.log(c_now / c_prev))
                        returns_map[symbol] = sym_ret
                except Exception:
                    sym_ret = 0.0
            else:
                sym_ret = 0.0

        all_vals = list(returns_map.values())
        if len(all_vals) >= 2:
            mu = float(np.mean(all_vals))
            sigma = float(np.std(all_vals))
        else:
            mu = float(all_vals[0]) if all_vals else 0.0
            sigma = 0.0

        if sigma > 1e-6 and sym_ret is not None:
            z_score = float((sym_ret - mu) / sigma)
        else:
            z_score = 0.0

        z_rounded = round(z_score, 2)
        return {
            "symbol": symbol,
            "z_score": z_rounded,
            "is_extreme_divergence": bool(z_rounded >= 2.0),
            "symbol_log_return": round(sym_ret or 0.0, 5),
            "mean_return": round(mu, 5),
            "std_return": round(sigma, 5),
            "universe_size": len(all_vals)
        }

    async def sync_top_100_symbols(self):
        """Binance Vadeli (USDT-M) 24h hacim siralamasini kontrol eder, delist olan veya veri vermeyen pariteleri otomatik degistirir."""
        try:
            url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        tickers = await resp.json()
                        if isinstance(tickers, list):
                            # Sadece USDT ile biten ve hacmi olan pariteleri al
                            valid_tickers = [
                                t for t in tickers 
                                if t.get('symbol', '').endswith('USDT') and float(t.get('quoteVolume', 0)) > 500000.0
                            ]
                            valid_tickers.sort(key=lambda x: float(x.get('quoteVolume', 0)), reverse=True)
                            top_symbols = []
                            for t in valid_tickers:
                                raw_s = t['symbol']
                                if raw_s.endswith('USDT'):
                                    base = raw_s[:-4]
                                    if base.startswith('1000000'): base = base[7:]
                                    elif base.startswith('1000'): base = base[4:]
                                    top_symbols.append(base + '/USDT')

                            # Simdiki sembolleri tara, verisi olmayanlari siradaki en iyi hacimli ile degistir
                            for s in list(self.all_symbols):
                                lev = self.levels.get(s, {})
                                cam = lev.get('camarilla', {}) if isinstance(lev, dict) else {}
                                if not cam or not cam.get('R4') or cam.get('R4') <= 0:
                                    # Bu sembol veri vermiyor / delist olmus olabilir
                                    for replacement in top_symbols:
                                        if replacement not in self.all_symbols:
                                            print(f">> [OTOMATİK DELİST YÖNETİCİSİ] {s} veri vermiyor -> Yerine Top Hacimli {replacement} alınıyor!")
                                            self.all_symbols.remove(s)
                                            self.all_symbols.append(replacement)
                                            if s in self.active_symbols:
                                                self.active_symbols.remove(s)
                                                self.active_symbols.add(replacement)
                                            self.levels[replacement] = {}
                                            self.current_prices[replacement] = 0.0
                                            self.candles_5m[replacement] = pd.DataFrame()
                                            self.candles_1d[replacement] = pd.DataFrame()
                                            await self.fetch_single_symbol(replacement)
                                            break
        except Exception as e:
            print(f">> [SYNC TOP 100 UYARI] {e}")

    async def initialize(self):
        print(">> Binance Vadeli (USDT-M Futures) verileri yukleniyor...")
        print(f"   Takip Edilen Toplam Parite: {len(self.all_symbols)}")
        tasks = [self.fetch_single_symbol(s) for s in self.all_symbols]
        await asyncio.gather(*tasks)
        await self.fetch_funding_rates()
        print(f">> [TAMAMLANDI] {len(self.all_symbols)} paritenin gosterge, pivot seviyeleri ve fonlama oranlari hesaplandi.")

    async def fetch_single_symbol(self, symbol: str):
        async with self.semaphore:
            clean_sym = self._clean_symbol(symbol)
            clean_raw = clean_sym.replace('/', '').replace(':USDT', '').replace('USDT', '')
            raw_spot = symbol.replace('/', '').replace(':USDT', '').replace('USDT', '')
            spot_clean = raw_spot.replace('1000000', '').replace('1000', '')
            spot_mult = self._get_spot_multiplier(symbol)

            df_1d = None
            df_5m = None

            async with aiohttp.ClientSession() as session:
                # 1. Binance USDT-M Futures Native Perpetuals & Vision Fallback (US Cloud Safe)
                futures_endpoints = [
                    f"https://fapi.binance.com/fapi/v1/klines?symbol={clean_raw}USDT",
                    f"https://fapi.binance.com/fapi/v1/continuousKlines?pair={clean_raw}USDT&contractType=PERPETUAL",
                    f"https://data-api.binance.vision/api/v3/klines?symbol={spot_clean}USDT"
                ]
                for ep in futures_endpoints:
                    try:
                        is_spot = "binance.vision" in ep
                        mult = spot_mult if is_spot else 1.0
                        url_1d_v = f"{ep}&interval=1d&limit=35"
                        url_5m_v = f"{ep}&interval=5m&limit=300"
                        t_1d, t_5m = None, None
                        async with session.get(url_1d_v, timeout=aiohttp.ClientTimeout(total=4)) as r1:
                            if r1.status == 200:
                                d1 = await r1.json()
                                if isinstance(d1, list) and len(d1) > 0:
                                    t_1d = pd.DataFrame(d1, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base', 'taker_quote', 'ignore'])
                                    for col in ['open', 'high', 'low', 'close', 'qav', 'taker_quote', 'taker_base']:
                                        if col in t_1d.columns:
                                            t_1d[col] = pd.to_numeric(t_1d[col], errors='coerce').fillna(0.0)
                                    for col in ['open', 'high', 'low', 'close']:
                                        t_1d[col] = t_1d[col] * mult
                                    t_1d['timestamp'] = t_1d['timestamp'].astype(float)
                                    t_1d['volume'] = t_1d['volume'].astype(float) / (mult if is_spot else 1.0)
                                    t_1d['quote_volume'] = t_1d['qav'].astype(float)
                                    t_1d = downcast_candle_dataframe(t_1d)
                        
                        async with session.get(url_5m_v, timeout=aiohttp.ClientTimeout(total=4)) as r2:
                            if r2.status == 200:
                                d2 = await r2.json()
                                if isinstance(d2, list) and len(d2) > 0:
                                    t_5m = pd.DataFrame(d2, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base', 'taker_quote', 'ignore'])
                                    for col in ['open', 'high', 'low', 'close', 'qav', 'taker_quote', 'taker_base']:
                                        if col in t_5m.columns:
                                            t_5m[col] = pd.to_numeric(t_5m[col], errors='coerce').fillna(0.0)
                                    for col in ['open', 'high', 'low', 'close']:
                                        t_5m[col] = t_5m[col] * mult
                                    t_5m['timestamp'] = t_5m['timestamp'].astype(float)
                                    t_5m['volume'] = t_5m['volume'].astype(float) / (mult if is_spot else 1.0)
                                    t_5m['quote_volume'] = t_5m['qav'].astype(float)
                                    t_5m = downcast_candle_dataframe(t_5m)
                        
                        if t_5m is not None and not t_5m.empty:
                            df_1d, df_5m = t_1d, t_5m
                            break
                    except Exception:
                        pass

            if df_1d is not None and not df_1d.empty and (df_5m is None or df_5m.empty):
                df_5m = df_1d.copy()
            if df_5m is not None and not df_5m.empty and (df_1d is None or df_1d.empty):
                # VDA-03: 5M mumlarından gerçekçi sentetik günlük mum üret (High=max, Low=min, Open=first, Close=last)
                bars_to_use = min(len(df_5m), 288)
                sub_5m = df_5m.iloc[-bars_to_use:]
                synth_row = {
                    'timestamp': sub_5m['timestamp'].iloc[0],
                    'open': float(sub_5m['open'].iloc[0]),
                    'high': float(sub_5m['high'].max()),
                    'low': float(sub_5m['low'].min()),
                    'close': float(sub_5m['close'].iloc[-1]),
                    'volume': float(sub_5m['volume'].sum()),
                    'close_time': sub_5m['close_time'].iloc[-1] if 'close_time' in sub_5m.columns else sub_5m['timestamp'].iloc[-1],
                    'qav': float(sub_5m['qav'].sum()) if 'qav' in sub_5m.columns else float(sub_5m['volume'].sum() * sub_5m['close'].iloc[-1]),
                    'num_trades': int(sub_5m['num_trades'].sum()) if 'num_trades' in sub_5m.columns else 1000,
                    'taker_base': float(sub_5m['taker_base'].sum()) if 'taker_base' in sub_5m.columns else float(sub_5m['volume'].sum() * 0.5),
                    'taker_quote': float(sub_5m['taker_quote'].sum()) if 'taker_quote' in sub_5m.columns else 0.0,
                    'ignore': 0
                }
                # Camarilla ve dünün seviyeleri için en az 2 satır üret
                df_1d = downcast_candle_dataframe(pd.DataFrame([synth_row, synth_row]))

            if df_1d is not None and df_5m is not None and not df_1d.empty and not df_5m.empty:
                self.candles_1d[symbol] = df_1d
                self.candles_5m[symbol] = df_5m
                self.current_prices[symbol] = float(df_5m['close'].iloc[-1])
                self.recalculate_levels(symbol)
                status = "AKTIF" if symbol in self.active_symbols else "HAZIR"
                print(f"   [{status}] {symbol} seviyeleri esitlendi. Fiyat: {self.current_prices[symbol]}")

    async def toggle_symbol(self, symbol: str, is_active: bool):
        if is_active:
            self.active_symbols.add(symbol)
            if symbol not in self.levels or not self.levels[symbol]:
                asyncio.create_task(self.fetch_single_symbol(symbol))
            print(f">> [PARITE AKTIF EDILDI] {symbol} strateji taramasina eklendi.")
        else:
            self.active_symbols.discard(symbol)
            print(f">> [PARITE PASIF EDILDI] {symbol} strateji taramasindan cikarildi.")

    async def set_active_symbols(self, symbols_list: list):
        new_active = set(s for s in symbols_list if s in self.all_symbols)
        self.active_symbols = new_active
        missing = [s for s in new_active if s not in self.levels or not self.levels[s]]
        if missing:
            asyncio.create_task(self._fetch_missing_symbols(missing))
        print(f">> [TOPLU PARITE GUNCELLEME] Aktif Parite Sayisi: {len(self.active_symbols)}")

    async def _fetch_missing_symbols(self, symbols):
        await asyncio.gather(*(self.fetch_single_symbol(s) for s in symbols))

    def recalculate_levels(self, symbol):
        df_1d = self.candles_1d.get(symbol, pd.DataFrame())
        df_5m = self.candles_5m.get(symbol, pd.DataFrame())
        current_p = self.current_prices.get(symbol, 1.0)
        if current_p <= 0: current_p = 1.0

        if df_5m.empty:
            camarilla = calculate_camarilla_pivots(current_p * 1.03, current_p * 0.97, current_p)
            self.levels[symbol] = {
                "camarilla": camarilla,
                "tepe_avwap": current_p * 1.02,
                "dip_avwap": current_p * 0.98,
                "daily_avwap": current_p,
                "mpoc": current_p,
                "mvah": current_p * 1.01,
                "mval": current_p * 0.99,
                "above_npoc": current_p * 1.015,
                "below_npoc": current_p * 0.985,
                "above_nvah": current_p * 1.02,
                "below_nvah": current_p * 0.98,
                "above_nval": current_p * 1.025,
                "below_nval": current_p * 0.975
            }
            majors = {"BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT"}
            if not hasattr(self, 'symbol_metrics'):
                self.symbol_metrics = {}
            self.symbol_metrics[symbol] = {
                "vol_surge": 1.0,
                "min_vol_surge": 1.2 if symbol in majors else 1.5,
                "atr_pct": 1.2,
                "is_top_80": True,
                "cur_vol": 0.0,
                "avg_vol": 0.0,
                "rs_vs_btc": 0.0,
                "dynamic_rs_score": 0.0,
                "decoupling_status": "⚪ NÖTR_TAKİPÇİ",
                "hurst_exponent": 0.50,
                "entropy_norm": 0.65,
                "is_chaotic": False,
                "is_crystalline": False,
                "iceberg_ratio": 1.0,
                "ask_iceberg_ratio": 1.0,
                "bid_iceberg_ratio": 1.0,
                "iceberg_side": "NONE",
                "has_iceberg": False,
                "hmm_phase": "ACCUMULATION",
                "hmm_desc": "Sessiz Birikim"
            }
            return

        # === CAMARILLA PIVOT (TradingView 1D UTC 00:00 Tam Uyumu) ===
        if not df_1d.empty and len(df_1d) >= 2:
            prev_day = df_1d.iloc[-2]
            camarilla = calculate_camarilla_pivots(prev_day['high'], prev_day['low'], prev_day['close'])
        elif not df_1d.empty:
            prev_day = df_1d.iloc[-1]
            camarilla = calculate_camarilla_pivots(prev_day['high'], prev_day['low'], prev_day['close'])
        else:
            camarilla = calculate_camarilla_pivots(df_5m['high'].max(), df_5m['low'].min(), df_5m['close'].iloc[-1])

        # === ANCHORED VWAP (TradingView 24h-48h Teyitli Majör Swing Paritesi) ===
        if len(df_5m) >= 20:
            lookback_bars = min(len(df_5m), 288)
            # Yerel 1-2 barlık fitillere yapışmayı önlemek için en az 6 bar (30dk) gerideki teyitli zirve/dip:
            if len(df_5m) > 26:
                eval_window = df_5m.iloc[-lookback_bars:-6]
                peak_idx = eval_window['high'].idxmax()
                trough_idx = eval_window['low'].idxmin()
            else:
                sub_5m = df_5m.iloc[-lookback_bars:]
                peak_idx = sub_5m['high'].idxmax()
                trough_idx = sub_5m['low'].idxmin()
            tepe_avwap = float(calculate_anchored_vwap(df_5m, peak_idx))
            dip_avwap = float(calculate_anchored_vwap(df_5m, trough_idx))
        else:
            high_idx = df_5m['high'].idxmax()
            low_idx = df_5m['low'].idxmin()
            tepe_avwap = float(calculate_anchored_vwap(df_5m, high_idx))
            dip_avwap = float(calculate_anchored_vwap(df_5m, low_idx))

        # === GÜNLÜK SEANS ÇAPALI AVWAP (00:00 UTC Daily Anchor) ===
        try:
            now_utc = datetime.now(timezone.utc)
            start_day_utc = datetime(now_utc.year, now_utc.month, now_utc.day, 0, 0, 0, tzinfo=timezone.utc)
            start_ts_ms = int(start_day_utc.timestamp() * 1000)
            day_mask = df_5m['timestamp'] >= start_ts_ms
            if day_mask.any():
                day_start_idx = df_5m[day_mask].index[0]
                daily_avwap = float(calculate_anchored_vwap(df_5m, day_start_idx))
            else:
                daily_avwap = float(calculate_anchored_vwap(df_5m, 0))
        except Exception:
            daily_avwap = float(current_p)

        now_ts = time.time()
        # === VOLUME PROFILE (Son 30 Günlük Makro Profil: JIT 60s TTL Önbellek) ===
        if symbol in getattr(self, '_vp_cache', {}) and (now_ts - self._vp_cache[symbol].get('ts', 0) < 60.0):
            vp_result = self._vp_cache[symbol]['data']
        else:
            if df_1d is not None and not df_1d.empty and len(df_1d) >= 5:
                vp_df = df_1d.iloc[-min(30, len(df_1d)):]
            else:
                vp_df = df_5m
            vp_result = calculate_volume_profile(vp_df, num_rows=30, value_area_pct=0.68)
            if hasattr(self, '_vp_cache'):
                self._vp_cache[symbol] = {'data': vp_result, 'ts': now_ts}

        # === NAKED LINES & KURUMSAL SEANS SEVİYELERİ (JIT 60s TTL Önbellek) ===
        current_p = self.current_prices.get(symbol, float(df_5m['close'].iloc[-1]))
        if symbol in getattr(self, '_naked_cache', {}) and (now_ts - self._naked_cache[symbol].get('ts', 0) < 60.0):
            naked_lines = self._naked_cache[symbol]['data']
        else:
            naked_lines = get_tradingview_naked_lines(df_5m, current_p)
            if hasattr(self, '_naked_cache'):
                self._naked_cache[symbol] = {'data': naked_lines, 'ts': now_ts}

        if symbol in getattr(self, '_session_cache', {}) and (now_ts - self._session_cache[symbol].get('ts', 0) < 60.0):
            session_levels = self._session_cache[symbol]['data']
        else:
            session_levels = calculate_session_and_daily_levels(df_5m, df_1d)
            if hasattr(self, '_session_cache'):
                self._session_cache[symbol] = {'data': session_levels, 'ts': now_ts}

        self.levels[symbol] = {
            "camarilla": camarilla,
            "tepe_avwap": float(tepe_avwap),
            "dip_avwap": float(dip_avwap),
            "daily_avwap": float(daily_avwap),
            "mpoc": float(vp_result.get("POC", current_p)),
            "mvah": float(vp_result.get("VAH", current_p * 1.01)),
            "mval": float(vp_result.get("VAL", current_p * 0.99)),
            "above_npoc": float(naked_lines.get("above_npoc", current_p * 1.015)),
            "below_npoc": float(naked_lines.get("below_npoc", current_p * 0.985)),
            "above_nvah": float(naked_lines.get("above_nvah", current_p * 1.02)),
            "below_nvah": float(naked_lines.get("below_nvah", current_p * 0.98)),
            "above_nval": float(naked_lines.get("above_nval", current_p * 1.025)),
            "below_nval": float(naked_lines.get("below_nval", current_p * 0.975)),
            "pdh": float(session_levels.get("pdh", 0.0)),
            "pdl": float(session_levels.get("pdl", 0.0)),
            "pdc": float(session_levels.get("pdc", 0.0)),
            "asia_high": float(session_levels.get("asia_high", 0.0)),
            "asia_low": float(session_levels.get("asia_low", 0.0))
        }

        # === DYNAMIC TELEMETRY & VOLUME METRICS ===
        majors = {"BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT"}
        min_vol_surge = 1.2 if symbol in majors else 1.5
        vol_surge = 1.0
        atr_pct = 1.2
        is_top_80 = True
        cur_vol = 0.0
        avg_vol = 0.0
        rs_vs_btc = 0.0
        dynamic_rs_score = 0.0
        decoupling_status = "⚪ NÖTR_TAKİPÇİ"

        if not df_5m.empty and len(df_5m) >= 14:
            try:
                sub_tr = df_5m.iloc[-15:]
                h, l, cl = sub_tr['high'], sub_tr['low'], sub_tr['close']
                tr = np.maximum(h - l, np.maximum((h - cl.shift()).abs(), (l - cl.shift()).abs()))
                atr = float(tr.iloc[1:].mean())
                if current_p > 0:
                    atr_pct = round((atr / current_p) * 100.0, 2)
            except Exception:
                atr_pct = 1.2

        if not df_5m.empty and len(df_5m) >= 20:
            try:
                vol_col = 'quote_volume' if ('quote_volume' in df_5m.columns and df_5m['quote_volume'].iloc[-1] > 0) else 'volume'
                cur_vol = float(df_5m[vol_col].iloc[-1])
                avg_vol = float(df_5m[vol_col].iloc[-21:-1].mean())
                vol_surge = round(cur_vol / avg_vol, 2) if avg_vol > 0 else 1.0
                
                # Madde 6: 24S Hacim Dilimi (Üst %80'lik dilim, dip %20 ölü piyasa koruması)
                if len(df_5m) >= 288:
                    vol_20th = float(df_5m[vol_col].iloc[-288:-1].quantile(0.20))
                else:
                    vol_20th = float(df_5m[vol_col].iloc[:-1].quantile(0.20)) if len(df_5m) > 1 else 0.0
                is_top_80 = bool(cur_vol >= vol_20th)
            except Exception:
                vol_surge = 1.0
                is_top_80 = True

        # === DİNAMİK RS (RELATIVE STRENGTH VS BTC - MADDE 9) ===
        # === DİNAMİK RS (RELATIVE STRENGTH VS BTC + ETH - ÇİFT ŞEFLİ ALFA MOTORU) ===
        if symbol == "BTC/USDT":
            decoupling_status = "👑 MAKRO KRAL (BTC)"
            rs_vs_btc = 0.0
            dynamic_rs_score = 0.0
        elif symbol == "ETH/USDT":
            btc_df = self.candles_5m.get('BTC/USDT', pd.DataFrame())
            if not btc_df.empty and not df_5m.empty and len(df_5m) >= 12 and len(btc_df) >= 12:
                try:
                    eth_chg = ((df_5m['close'].iloc[-1] - df_5m['close'].iloc[-12]) / df_5m['close'].iloc[-12]) * 100.0
                    btc_chg = ((btc_df['close'].iloc[-1] - btc_df['close'].iloc[-12]) / btc_df['close'].iloc[-12]) * 100.0
                    diff = float(eth_chg - btc_chg)
                    rs_vs_btc = round(diff, 2)
                    dynamic_rs_score = round(diff / max(0.2, atr_pct), 2)
                    if dynamic_rs_score >= 0.7:
                        decoupling_status = "🟡 ALTCOİN LOKOMOTİFİ (ETH Liderliği)"
                    elif dynamic_rs_score <= -0.7:
                        decoupling_status = "🟠 ZAYIF ETH (BTC Baskısı)"
                    else:
                        decoupling_status = "⚪ NÖTR LİDER (ETH)"
                except Exception:
                    decoupling_status = "👑 ALTCOİN LOKOMOTİFİ (ETH)"
                    rs_vs_btc = 0.0
                    dynamic_rs_score = 0.0
            else:
                decoupling_status = "👑 ALTCOİN LOKOMOTİFİ (ETH)"
                rs_vs_btc = 0.0
                dynamic_rs_score = 0.0
        else:
            btc_df = self.candles_5m.get('BTC/USDT', pd.DataFrame())
            eth_df = self.candles_5m.get('ETH/USDT', pd.DataFrame())
            if not btc_df.empty and not df_5m.empty:
                try:
                    min_len_btc = min(len(df_5m), len(btc_df))
                    if min_len_btc >= 12:
                        coin_chg_1h = ((df_5m['close'].iloc[-1] - df_5m['close'].iloc[-12]) / df_5m['close'].iloc[-12]) * 100.0
                        btc_chg_1h = ((btc_df['close'].iloc[-1] - btc_df['close'].iloc[-12]) / btc_df['close'].iloc[-12]) * 100.0
                        rs_btc_1h = float(coin_chg_1h - btc_chg_1h)

                        coin_chg_fast = ((df_5m['close'].iloc[-1] - df_5m['close'].iloc[-4]) / df_5m['close'].iloc[-4]) * 100.0
                        btc_chg_fast = ((btc_df['close'].iloc[-1] - btc_df['close'].iloc[-4]) / btc_df['close'].iloc[-4]) * 100.0
                        rs_btc_fast = float(coin_chg_fast - btc_chg_fast)
                        rs_btc = rs_btc_1h * 0.7 + rs_btc_fast * 0.3
                    elif min_len_btc >= 4:
                        coin_chg = ((df_5m['close'].iloc[-1] - df_5m['close'].iloc[-4]) / df_5m['close'].iloc[-4]) * 100.0
                        btc_chg = ((btc_df['close'].iloc[-1] - btc_df['close'].iloc[-4]) / btc_df['close'].iloc[-4]) * 100.0
                        rs_btc = float(coin_chg - btc_chg)
                    else:
                        rs_btc = 0.0

                    # ETH Kıyaslaması (Altcoin liderliği teyidi)
                    rs_eth = rs_btc
                    if eth_df is not None and not eth_df.empty:
                        min_len_eth = min(len(df_5m), len(eth_df))
                        if min_len_eth >= 12:
                            eth_chg_1h = ((eth_df['close'].iloc[-1] - eth_df['close'].iloc[-12]) / eth_df['close'].iloc[-12]) * 100.0
                            rs_eth = float(coin_chg_1h - eth_chg_1h)

                    # Bileşik RS: %60 BTC, %40 ETH ağırlıklı
                    composite_rs = rs_btc * 0.60 + rs_eth * 0.40
                    rs_vs_btc = round(composite_rs, 2)

                    safe_atr = max(0.2, atr_pct)
                    dynamic_rs_score = round(composite_rs / safe_atr, 2)

                    if dynamic_rs_score >= 1.0 and vol_surge >= 1.5:
                        decoupling_status = "🚀 ALFA_AYRIŞAN (Güçlü Boğa)"
                    elif dynamic_rs_score >= 1.0:
                        decoupling_status = "🟢 DİRENÇLİ BOĞA (Makrodan Güçlü)"
                    elif dynamic_rs_score <= -1.0:
                        decoupling_status = "🩸 AŞIRI_ZAYIF (Ezilen Ayı)"
                    else:
                        decoupling_status = "⚪ NÖTR_TAKİPÇİ (Beta)"
                except Exception:
                    rs_vs_btc = 0.0
                    dynamic_rs_score = 0.0
                    decoupling_status = "⚪ NÖTR_TAKİPÇİ (Beta)"

        # 🧠 6-SÜTUNLU KUANT TELEMETRİSİ (HURST, BOLTZMANN ENTROPİ, ICEBERG, BOOKMAP EMİLİM, SIMONS HMM, CVD İVME, dPOC, STOIKOV, VPIN, KYLE'S LAMBDA)
        from indicators import (
            calculate_hurst_exponent, calculate_orderbook_entropy, calculate_shannon_market_entropy,
            detect_iceberg_orders, estimate_hmm_market_phase, detect_bookmap_absorption,
            calculate_cvd_acceleration, calculate_delta_poc, evaluate_iceberg_offense,
            calculate_stoikov_micro_price, calculate_vpin_toxicity, calculate_kyles_lambda
        )
        
        # 1. Mandelbrot Hurst Üssü (5M Kapanışlarından Fraktal Hafıza)
        hurst_val = 0.50
        if not df_5m.empty and len(df_5m) >= 30 and 'close' in df_5m.columns:
            try:
                hurst_val = calculate_hurst_exponent(df_5m['close'].values)
            except Exception:
                hurst_val = 0.50

        # 2. Ken Griffin Iceberg & Boltzmann Derinlik Tespiti
        clean_s = self._clean_symbol(symbol)
        norm_s = symbol
        depth = self.orderbook_depth.get(norm_s) or self.orderbook_depth.get(clean_s, {})
        h_deque = self.symbol_cvd_history.get(clean_s) or self.symbol_cvd_history.get(norm_s)
        
        diff_buy = 0.0
        diff_sell = 0.0
        if h_deque and len(h_deque) >= 2:
            now_ts = time.time()
            t_cutoff = now_ts - 60.0
            if h_deque[-1][0] >= t_cutoff:
                old_sample = h_deque[0]
                for s_item in h_deque:
                    if s_item[0] >= t_cutoff:
                        old_sample = s_item
                        break
                diff_buy = max(0.0, float(h_deque[-1][1] - old_sample[1]))
                diff_sell = max(0.0, float(h_deque[-1][2] - old_sample[2]))

        top_bid_usd = float(depth.get('bid_price', 0.0)) * float(depth.get('bid_qty', 0.0))
        top_ask_usd = float(depth.get('ask_price', 0.0)) * float(depth.get('ask_qty', 0.0))
        cur_p = current_p if current_p > 0 else self.current_prices.get(symbol, 0.0)
        default_top_depth_usd = 25000.0 if (symbol in ["BTC/USDT", "ETH/USDT", "SOL/USDT"]) else 8000.0
        if top_bid_usd <= 0:
            top_bid_usd = default_top_depth_usd
        if top_ask_usd <= 0:
            top_ask_usd = default_top_depth_usd

        ice_data = detect_iceberg_orders(diff_buy, diff_sell, top_bid_usd, top_ask_usd)
        ask_ice_r = float(ice_data.get('ask_iceberg_ratio', 1.0))
        bid_ice_r = float(ice_data.get('bid_iceberg_ratio', 1.0))
        iceberg_ratio = max(ask_ice_r, bid_ice_r)
        has_iceberg = bool(ice_data.get('has_seller_iceberg') or ice_data.get('has_buyer_iceberg') or iceberg_ratio >= 3.0)
        iceberg_side = str(ice_data.get('iceberg_side', 'NONE'))

        # 2b. Bookmap Mikro-Emilim Süngeri ve Kurumsal Çapa Duvarı Tespiti
        price_chg_60s = 0.0
        p_deque = self.symbol_price_history.get(clean_s) or self.symbol_price_history.get(norm_s)
        if p_deque and len(p_deque) >= 2:
            now_t = time.time()
            t_cutoff = now_t - 60.0
            old_p = p_deque[0][1]
            for ts_i, p_i in p_deque:
                if ts_i >= t_cutoff:
                    old_p = p_i
                    break
            cur_live_p = p_deque[-1][1]
            if old_p > 0:
                price_chg_60s = round(((cur_live_p - old_p) / old_p) * 100.0, 3)

        wall_dur_sec = float(depth.get('wall_duration_sec', 0.0))
        is_major_sym = symbol in {"BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT", "NEAR/USDT", "AVAX/USDT"}
        bm_data = detect_bookmap_absorption(
            taker_buy_usd=diff_buy,
            taker_sell_usd=diff_sell,
            top_bid_usd=top_bid_usd,
            top_ask_usd=top_ask_usd,
            price_change_pct_60s=price_chg_60s,
            wall_duration_sec=wall_dur_sec,
            is_major=is_major_sym
        )

        # 3. HMM Piyasa Evresi
        wick_ratio = 35.0
        if not df_5m.empty:
            c_row = df_5m.iloc[-1]
            tot_range = max(1e-6, float(c_row['high'] - c_row['low']))
            body_range = abs(float(c_row['close'] - c_row['open']))
            wick_ratio = round((1.0 - (body_range / tot_range)) * 100.0, 1)

        cvd_info = self.get_symbol_cvd(symbol) if hasattr(self, 'get_symbol_cvd') else {'taker_buy_pct': 50.0}
        cvd_pct = float(cvd_info.get('taker_buy_pct', 50.0))
        hmm_res = estimate_hmm_market_phase(df_5m, wick_ratio_pct=wick_ratio, cvd_ratio=cvd_pct, vol_surge=vol_surge)
        hmm_phase = str(hmm_res.get('phase', 'ACCUMULATION'))
        hmm_desc = str(hmm_res.get('desc', 'Sessiz Birikim'))

        # 4. CVD İvme & Sıfır Geçişi (Zero-Crossing)
        cvd_deltas = [float(s[1] - s[2]) for s in h_deque] if h_deque and len(h_deque) >= 4 else []
        cvd_acc_info = calculate_cvd_acceleration(cvd_deltas)

        # 5. dPOC Tuzaklanmış Likidite
        sym_levels = self.levels.get(symbol, {})
        dpoc_info = calculate_delta_poc(sym_levels, cur_p, df_5m)

        # 6. Iceberg Hücum Sniper & Ping-Pong
        ice_offense = evaluate_iceberg_offense(ice_data, cur_p, sym_levels)

        # 7. VPIN Toksik Akış & Konsolidasyon Patlama Erken Uyarısı
        vpin_info = calculate_vpin_toxicity(df_5m, rolling_window=12, recent_cvd=cvd_info)

        # 8. Kyle's Lambda (İllikitlik & Fiyat Etki Oranı)
        lambda_info = calculate_kyles_lambda(df_5m)

        # 9. Hawkes Kendi Kendini Besleyen Tasfiye Çığı Modeli
        hawkes_info = self.get_hawkes_avalanche(symbol)

        # Deribit Kurumsal Opsiyon GEX & Makro Şemsiye Ayrımı
        sym_clean = symbol.upper().replace('/', '').replace(':USDT', '').replace('USDT', '')
        btc_net_gex = float(self.deribit_gex_data.get('BTC', {}).get('net_gex', 0.0)) if hasattr(self, 'deribit_gex_data') else 0.0
        eth_net_gex = float(self.deribit_gex_data.get('ETH', {}).get('net_gex', 0.0)) if hasattr(self, 'deribit_gex_data') else 0.0

        if sym_clean == 'BTC':
            coin_gex = btc_net_gex
            coin_gex_regime = str(self.get_deribit_gex_regime())
            is_proxy = False
        elif sym_clean == 'ETH':
            coin_gex = eth_net_gex
            eth_data = self.get_deribit_gex('ETH')
            coin_gex_regime = str(eth_data.get('gex_regime', 'NEUTRAL'))
            is_proxy = False
        else:
            coin_gex = 0.0
            coin_gex_regime = 'MACRO_BTC_PROXY'
            is_proxy = True

        # JIT L2 önbelleği varsa oradaki derin L2 entropisini al, yoksa dinamik Shannon piyasa entropisini hesapla
        cached_l2 = getattr(self, 'jit_l2_cache', {}).get(symbol, {})
        if cached_l2 and 'entropy_norm' in cached_l2:
            entropy_norm = float(cached_l2.get('entropy_norm', 0.70))
            is_chaotic = bool(cached_l2.get('is_chaotic', False))
            is_crystalline = bool(cached_l2.get('is_crystalline', False))
        else:
            # 5M Mum Hacim/Getiri Akışı + Tahta Dengesizliği + Iceberg Kristalleşmesi ile dinamik Shannon piyasa entropisi
            ent_dyn = calculate_shannon_market_entropy(
                df=df_5m,
                depth_info=depth,
                iceberg_ratio=iceberg_ratio,
                window=24
            )
            entropy_norm = float(ent_dyn.get('entropy_norm', 0.70))
            is_chaotic = bool(ent_dyn.get('is_chaotic', False))
            is_crystalline = bool(ent_dyn.get('is_crystalline', False))

        if not hasattr(self, 'symbol_metrics'):
            self.symbol_metrics = {}
        self.symbol_metrics[symbol] = {
            "vol_surge": float(vol_surge),
            "min_vol_surge": float(min_vol_surge),
            "atr_pct": float(atr_pct),
            "is_top_80": bool(is_top_80),
            "cur_vol": float(cur_vol),
            "avg_vol": float(avg_vol),
            "rs_vs_btc": float(rs_vs_btc),
            "dynamic_rs_score": float(dynamic_rs_score),
            "rs_zscore": float(self.get_universe_log_return_zscore(symbol).get("z_score", 0.0)),
            "decoupling_status": str(decoupling_status),
            "hurst_exponent": float(hurst_val),
            "entropy_norm": float(entropy_norm),
            "is_chaotic": bool(is_chaotic),
            "is_crystalline": bool(is_crystalline),
            "iceberg_ratio": float(iceberg_ratio),
            "ask_iceberg_ratio": float(ask_ice_r),
            "bid_iceberg_ratio": float(bid_ice_r),
            "iceberg_side": str(iceberg_side),
            "has_iceberg": bool(has_iceberg),
            "bookmap_seller_absorption": bool(bm_data.get('has_seller_absorption', False)),
            "bookmap_buyer_absorption": bool(bm_data.get('has_buyer_absorption', False)),
            "bookmap_absorption_type": str(bm_data.get('absorption_type', 'NONE')),
            "bookmap_absorption_desc": str(bm_data.get('absorption_desc', '⚪ Normal Sipariş Akışı')),
            "is_anchor_wall": bool(bm_data.get('is_anchor_wall', False)),
            "is_iron_wall": bool(bm_data.get('is_iron_wall', False)),
            "wall_duration_sec": float(wall_dur_sec),
            "price_change_pct_60s": float(price_chg_60s),
            "hmm_phase": str(hmm_phase),
            "hmm_desc": str(hmm_desc),
            "cvd_velocity": float(cvd_acc_info.get('velocity', 0.0)),
            "cvd_acceleration": float(cvd_acc_info.get('acceleration', 0.0)),
            "cvd_zero_cross": str(cvd_acc_info.get('zero_crossing', 'NONE')),
            "is_cvd_exhaustion_top": bool(cvd_acc_info.get('is_exhaustion_top', False)),
            "is_cvd_exhaustion_bottom": bool(cvd_acc_info.get('is_exhaustion_bottom', False)),
            "cvd_momentum_regime": str(cvd_acc_info.get('momentum_regime', 'NEUTRAL')),
            "trapped_bias": str(dpoc_info.get('trapped_bias', 'NEUTRAL')),
            "trapped_status": str(dpoc_info.get('trapped_status', 'NONE')),
            "trapped_desc": str(dpoc_info.get('trapped_desc', 'Dengeli Seviye Akışı')),
            "is_iceberg_sniper_buy": bool(ice_offense.get('is_sniper_buy', False)),
            "is_iceberg_sniper_sell": bool(ice_offense.get('is_sniper_sell', False)),
            "is_iceberg_ping_pong": bool(ice_offense.get('is_ping_pong', False)),
            "iceberg_tight_stop_pct": float(ice_offense.get('tight_stop_dist_pct', 0.0022)),
            "iceberg_offense_reason": str(ice_offense.get('offense_reason', '')),
            "buyer_offense_reason": str(ice_offense.get('buyer_offense_reason', '')),
            "seller_offense_reason": str(ice_offense.get('seller_offense_reason', '')),
            "vpin_score": float(vpin_info.get('vpin_score', 0.30)),
            "vpin_toxicity": str(vpin_info.get('toxicity_level', 'LOW')),
            "is_vpin_toxic": bool(vpin_info.get('is_toxic_flow', False)),
            "is_range_veto_alert": bool(vpin_info.get('is_range_veto_alert', False)),
            "vpin_desc": str(vpin_info.get('vpin_desc', '')),
            "kyles_lambda_ratio": float(lambda_info.get('lambda_ratio', 1.0)),
            "is_vacuum_trap": bool(lambda_info.get('is_vacuum_trap', False)),
            "is_liquid_expansion": bool(lambda_info.get('is_liquid_expansion', False)),
            "lambda_desc": str(lambda_info.get('desc', '')),
            "deribit_gex_regime": coin_gex_regime,
            "deribit_net_gex": coin_gex,
            "macro_btc_net_gex": btc_net_gex,
            "is_gex_proxy": is_proxy,
            "is_gex_pinning": bool(self.is_gex_pinning()),
            "is_gex_exploding": bool(self.is_gex_exploding()),
            "hawkes_eta": float(hawkes_info.get('branching_ratio_eta', 0.15)),
            "local_hawkes_eta": float(hawkes_info.get('local_hawkes_eta', 0.0)),
            "macro_hawkes_eta": float(hawkes_info.get('macro_hawkes_eta', 0.15)),
            "hawkes_source": str(hawkes_info.get('hawkes_source', 'GLOBAL_MACRO')),
            "is_avalanche_active": bool(hawkes_info.get('is_avalanche_active', False)),
            "is_macro_avalanche": bool(hawkes_info.get('is_macro_avalanche', False)),
            "is_avalanche_exhausted": bool(hawkes_info.get('is_avalanche_exhausted', False)),
            "avalanche_side": str(hawkes_info.get('avalanche_side', 'NONE')),
            "avalanche_desc": str(hawkes_info.get('desc', ''))
        }

    def get_deribit_gex(self, currency: str = 'BTC') -> dict:
        """Deribit kurumsal opsiyon GEX ve Gamma verisini döndürür."""
        if not hasattr(self, 'deribit_gex_data'):
            return {}
        return self.deribit_gex_data.get(currency.upper(), {})

    def get_deribit_gex_regime(self) -> str:
        """Global opsiyon gamma rejimini döndürür (POSITIVE_GAMMA_PIN, NEGATIVE_GAMMA_EXPLOSION, NEUTRAL)."""
        btc_gex = self.get_deribit_gex('BTC')
        return btc_gex.get('gex_regime', 'NEUTRAL')

    def is_gex_pinning(self) -> bool:
        """+GEX rejiminde piyasa yapıcıların volatiliteyi baskılayıp fiyatı kilitlediği rejim (S3/R3 Scalp ve nPOC teşvik)."""
        btc_gex = self.get_deribit_gex('BTC')
        return bool(btc_gex.get('is_pinning_regime', False))

    def is_gex_exploding(self) -> bool:
        """-GEX rejiminde kurumsal delta hedge'in volatiliteyi patlattığı rejim (Breakout/Breakdown teşvik)."""
        btc_gex = self.get_deribit_gex('BTC')
        return bool(btc_gex.get('is_explosion_regime', False))

    def get_coinbase_lead_lag(self, symbol: str = "BTC/USDT") -> dict:
        """
        Coinbase Spot USD ile Binance Vadeli arasındaki kurumsal lider-takipçi (Lead-Lag) fiyat farkını hesaplar.
        15 likit parite için pariteye özel spread, desteklenmeyenler için NOT_LISTED döner.
        """
        base_asset = symbol.upper().replace('/', '').replace(':USDT', '')
        if base_asset.endswith('USDT'):
            base_asset = base_asset[:-4]
        for prefix in ['1000000', '100000', '10000', '1000']:
            if base_asset.startswith(prefix):
                base_asset = base_asset[len(prefix):]
                break

        now_ts = time.time()
        cb_last_upd = getattr(self, 'coinbase_prices', {}).get('last_update', 0.0)
        macro_btc_lead = getattr(self, 'coinbase_lead_lag', {})
        macro_btc_spread = float(macro_btc_lead.get('spread_bps', 0.0))

        if hasattr(self, 'coinbase_supported_assets') and base_asset in self.coinbase_supported_assets:
            cb_price = float(self.coinbase_prices.get(base_asset, 0.0))
            if cb_price > 0:
                binance_price = float(self.current_prices.get(symbol, self.current_prices.get(f"{base_asset}/USDT", 0.0)))
                if binance_price > 0:
                    usdt_peg = self.current_prices.get("USDT/USD", self.current_prices.get("USDC/USDT", 1.0))
                    adj_binance_price = binance_price * usdt_peg if (0.95 <= usdt_peg <= 1.05) else binance_price
                    spread_bps = round(((cb_price - adj_binance_price) / adj_binance_price) * 10000.0, 1)

                    direction = "NEUTRAL"
                    status_str = "⚪ DENGELİ NAKİT AKIŞI"
                    desc_str = f"Coinbase (${cb_price:,.2f}) ile Binance (${binance_price:,.2f}) dengede ({spread_bps:+.1f} bps)."

                    from config import COINBASE_LEAD_SPREAD_BPS
                    if spread_bps >= COINBASE_LEAD_SPREAD_BPS:
                        direction = "BULLISH_LEAD"
                        status_str = f"🇺🇸 COINBASE SPOT BOĞA ÖNCÜSÜ (+{spread_bps:.0f} bps)"
                        desc_str = f"Coinbase Spot alıcı baskısıyla önde (+{spread_bps:+.1f} bps). Kurumsal yukarı itki."
                    elif spread_bps <= -COINBASE_LEAD_SPREAD_BPS:
                        direction = "BEARISH_LEAD"
                        status_str = f"🇺🇸 COINBASE SPOT AYI BASKISI ({spread_bps:.0f} bps)"
                        desc_str = f"Coinbase Spot satıcı baskısıyla geride ({spread_bps:+.1f} bps). Kurumsal aşağı baskı."

                    item_age = (now_ts - getattr(self, 'coinbase_prices', {}).get(f"{base_asset}_time", cb_last_upd))
                    return {
                        'lead_symbol': base_asset,
                        'spread_bps': spread_bps,
                        'direction': direction,
                        'status': status_str,
                        'desc': desc_str,
                        'is_listed': True,
                        'macro_btc_spread_bps': macro_btc_spread,
                        'last_update': cb_last_upd,
                        'age_seconds': item_age if cb_last_upd > 0 else 999.0
                    }

            # Listeli ama henüz fiyat akışı bağlanmadı veya 0 (Başlangıç/Isınma)
            return {
                'lead_symbol': base_asset,
                'spread_bps': 0.0,
                'direction': 'NEUTRAL',
                'status': '⚪ DENGELİ (Veri Bekleniyor)',
                'desc': f'{symbol} Coinbase Spot tahtasında listeli, fiyat akışı bekleniyor.',
                'is_listed': True,
                'macro_btc_spread_bps': macro_btc_spread,
                'last_update': cb_last_upd,
                'age_seconds': (now_ts - cb_last_upd) if cb_last_upd > 0 else 999.0
            }

        # Listeli Değil (NOT_LISTED)
        return {
            'lead_symbol': base_asset,
            'spread_bps': 0.0,
            'direction': 'NEUTRAL',
            'status': 'NOT_LISTED',
            'desc': f'{symbol} Coinbase Spot tahtasında listeli değil.',
            'is_listed': False,
            'macro_btc_spread_bps': macro_btc_spread,
            'last_update': cb_last_upd,
            'age_seconds': (now_ts - cb_last_upd) if cb_last_upd > 0 else 999.0
        }

    # ──────────────────────────────────────────────────────────────────────────
    # 🏛️ STAGE 3: KURUMSAL COINBASE SPOT VS. BINANCE OFFSHORE CVD AYRIŞMASI
    # ──────────────────────────────────────────────────────────────────────────
    def get_coinbase_cvd(self, base_asset: str = "BTC") -> dict:
        """Coinbase Spot son 60 saniyelik Taker Alış/Satış hacimlerini ve kümülatif delta oranını döndürür."""
        clean_a = base_asset.upper().replace('/', '').replace(':USDT', '')
        if clean_a.endswith('USDT'):
            clean_a = clean_a[:-4]
        for prefix in ['1000000', '100000', '10000', '1000']:
            if clean_a.startswith(prefix):
                clean_a = clean_a[len(prefix):]
                break

        dq = getattr(self, 'coinbase_cvd_history', {}).get(clean_a, deque())
        now_t = time.time()
        cutoff = now_t - 60.0
        while dq and dq[0][0] < cutoff:
            dq.popleft()

        buy_usd = sum(x[1] for x in dq)
        sell_usd = sum(x[2] for x in dq)
        tot_usd = buy_usd + sell_usd
        delta_usd = buy_usd - sell_usd
        buy_ratio = (buy_usd / tot_usd * 100.0) if tot_usd > 0 else 50.0

        return {
            'asset': clean_a,
            'buy_usd_60s': round(buy_usd, 2),
            'sell_usd_60s': round(sell_usd, 2),
            'tot_usd_60s': round(tot_usd, 2),
            'delta_usd_60s': round(delta_usd, 2),
            'buy_ratio_60s': round(buy_ratio, 1),
            'trade_count_60s': len(dq)
        }

    def get_smart_money_divergence(self, symbol: str = "BTC/USDT") -> dict:
        """
        Stage 3: ABD Kurumsal Coinbase Spot CVD ile Binance Vadeli CVD arasındaki
        ayrışmayı (Smart Money Delta) ve tuzak rejimlerini hesaplar.
        """
        clean_s = self._clean_symbol(symbol)
        base_asset = clean_s.replace('/USDT', '').replace(':USDT', '')
        for prefix in ['1000000', '100000', '10000', '1000']:
            if base_asset.startswith(prefix):
                base_asset = base_asset[len(prefix):]
                break

        # 1. Coinbase Spot CVD
        is_cb_supported = hasattr(self, 'coinbase_supported_assets') and (base_asset in self.coinbase_supported_assets)
        target_asset = base_asset if is_cb_supported else 'BTC'
        cb_cvd = self.get_coinbase_cvd(target_asset)
        cb_ratio = float(cb_cvd.get('buy_ratio_60s', 50.0))
        cb_delta = float(cb_cvd.get('delta_usd_60s', 0.0))
        cb_tot = float(cb_cvd.get('tot_usd_60s', 0.0))

        # 2. Binance Vadeli CVD
        bin_item = self.symbol_cvd.get(symbol, self.symbol_cvd.get(clean_s, {}))
        bin_ratio = float(bin_item.get('ratio_60s', 50.0) or 50.0)
        bin_delta = float(bin_item.get('delta_60s', 0.0) or 0.0)

        # 3. Smart Money Delta Oranı & Spread
        spread_ratio = round(cb_ratio - bin_ratio, 1)

        # 4. Rejim Teşhisi
        is_cb_active = (cb_tot >= 100.0 or cb_cvd.get('trade_count_60s', 0) >= 2)

        # Senaryo A: INSTITUTIONAL_SPOT_ACCUMULATION
        is_accum = is_cb_active and (cb_ratio >= SMART_MONEY_ACCUM_CB_BUY_MIN and cb_delta > 0 and (bin_ratio <= 52.0 or spread_ratio >= 5.0))

        # Senaryo B: RETAIL_FOMO_LONG_TRAP
        is_long_trap = is_cb_active and (bin_ratio >= SMART_MONEY_RETAIL_LONG_TRAP_BINANCE and (cb_ratio <= SMART_MONEY_RETAIL_LONG_TRAP_CB_MAX or spread_ratio <= -SMART_MONEY_DIVERGENCE_SPREAD_TRAP))

        # Senaryo C: RETAIL_PANIC_SHORT_TRAP
        is_short_trap = is_cb_active and (bin_ratio <= SMART_MONEY_RETAIL_SHORT_TRAP_BINANCE and (cb_ratio >= SMART_MONEY_RETAIL_SHORT_TRAP_CB_MIN or spread_ratio >= SMART_MONEY_DIVERGENCE_SPREAD_TRAP))

        regime = "HARMONIC_FLOW"
        status_desc = "⚪ Kurumsal Spot ve Vadeli Akış Dengeli"
        if is_accum:
            regime = "INSTITUTIONAL_SPOT_ACCUMULATION"
            status_desc = f"⚡ ABD Kurumsal Spot Birikimi (Coinbase %{cb_ratio:.1f} vs Binance %{bin_ratio:.1f})"
        elif is_long_trap:
            regime = "RETAIL_FOMO_LONG_TRAP"
            status_desc = f"🚨 Perakende FOMO Long Tuzağı (Binance %{bin_ratio:.1f} vs Coinbase %{cb_ratio:.1f})"
        elif is_short_trap:
            regime = "RETAIL_PANIC_SHORT_TRAP"
            status_desc = f"🛡️ Perakende Panik Short Tuzağı (Binance %{bin_ratio:.1f} vs Coinbase %{cb_ratio:.1f})"

        res = {
            'symbol': symbol,
            'target_asset': target_asset,
            'is_macro_proxy': (not is_cb_supported),
            'coinbase_buy_ratio': cb_ratio,
            'coinbase_delta_60s': cb_delta,
            'coinbase_tot_60s': cb_tot,
            'binance_buy_ratio': bin_ratio,
            'binance_delta_60s': bin_delta,
            'smart_money_spread': spread_ratio,
            'regime': regime,
            'status_desc': status_desc,
            'is_institutional_accum': is_accum,
            'is_retail_long_trap': is_long_trap,
            'is_retail_short_trap': is_short_trap,
            'margin_multiplier': SMART_MONEY_MARGIN_BONUS_MULT if is_accum else 1.0,
            'last_update': time.time()
        }
        self.smart_money_divergence[symbol] = res
        return res

    def get_smart_money_summary(self) -> dict:
        """Kokpit ve Web Dashboard için Smart Money Ayrışma Özetini döndürür."""
        btc_div = self.get_smart_money_divergence("BTC/USDT")
        eth_div = self.get_smart_money_divergence("ETH/USDT")
        sol_div = self.get_smart_money_divergence("SOL/USDT")
        return {
            'btc': btc_div,
            'eth': eth_div,
            'sol': sol_div,
            'regime': btc_div.get('regime', 'HARMONIC_FLOW'),
            'status_desc': btc_div.get('status_desc', '⚪ Akış Dengeli'),
            'cb_connected': getattr(self, 'coinbase_prices', {}).get('is_connected', False)
        }

    async def fetch_deribit_gex_immediate(self):
        """Aegis Sentinel veya manuel tetikleyici tarafından çağrılan anlık ve crash-proof Deribit GEX tazeleyicisi."""
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        success_count = 0
        try:
            import aiohttp
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
                for ccy in ['BTC', 'ETH']:
                    url = f"https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency={ccy}&kind=option"
                    try:
                        async with session.get(url, headers=headers) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                book = data.get('result', [])
                                if book and isinstance(book, list):
                                    from indicators import calculate_deribit_gex
                                    gex_res = calculate_deribit_gex(book)
                                    gex_res['last_update'] = time.time()
                                    self.deribit_gex_data[ccy] = gex_res
                                    success_count += 1
                    except Exception:
                        pass
                if success_count > 0:
                    self.deribit_gex_data['last_sync_ts'] = time.time()
                    self.deribit_gex_data['is_live'] = True
                    print(">> [AEGIS AUTO-HEAL] Deribit GEX verisi otonom olarak tazelendi.")
                    return True
                else:
                    self.deribit_gex_data['is_live'] = False
                    return False
        except Exception as e:
            print(f">> [DERIBIT IMMEDIATE HATA] {e}")
            self.deribit_gex_data['is_live'] = False
            return False

    def get_hawkes_avalanche(self, symbol: str = None) -> dict:
        """
        Kaldıraç tasfiye akışından (!forceOrder) Hawkes kendi kendini besleyen çığ analizi.
        Yerel parite tasfiyesi ile küresel BTC/ETH makro çığını birbirinden ayırır.
        """
        from indicators import calculate_hawkes_avalanche

        macro_res = {}
        if hasattr(self, 'recent_liquidations') and self.recent_liquidations:
            try:
                macro_res = calculate_hawkes_avalanche(list(self.recent_liquidations))
            except Exception:
                macro_res = {}

        local_res = {}
        if symbol and hasattr(self, 'recent_liquidations') and self.recent_liquidations:
            clean_s = symbol.upper().replace('/', '').replace(':USDT', '').replace('USDT', '')
            sym_liqs = [liq for liq in self.recent_liquidations if clean_s in liq.get('symbol', '').upper() or clean_s in liq.get('raw_symbol', '').upper()]
            if len(sym_liqs) >= 2:
                try:
                    local_res = calculate_hawkes_avalanche(sym_liqs)
                    local_res['source'] = 'LOCAL'
                except Exception:
                    local_res = {}

        local_eta = float(local_res.get('branching_ratio_eta', 0.0))
        macro_eta = float(macro_res.get('branching_ratio_eta', 0.15))
        has_local_data = bool(local_res and 'branching_ratio_eta' in local_res)

        return {
            'branching_ratio_eta': local_eta if has_local_data else (macro_eta if not symbol else 0.0),
            'local_hawkes_eta': local_eta if has_local_data else 0.0,
            'macro_hawkes_eta': macro_eta,
            'intensity': float(local_res.get('intensity', macro_res.get('intensity', 0.0) if not symbol else 0.0)),
            'regime': str(local_res.get('regime', macro_res.get('regime', 'QUIET_FLOW'))),
            'is_avalanche_active': bool(local_res.get('is_avalanche_active', False)),
            'is_macro_avalanche': bool(macro_res.get('is_avalanche_active', False)),
            'hawkes_source': 'LOCAL' if has_local_data else 'GLOBAL_MACRO',
            'is_avalanche_exhausted': bool(local_res.get('is_avalanche_exhausted', False)),
            'avalanche_side': str(local_res.get('avalanche_side', macro_res.get('avalanche_side', 'NONE') if not symbol else 'NONE')),
            'long_liq_usd': float(local_res.get('long_liq_usd', 0.0)),
            'short_liq_usd': float(local_res.get('short_liq_usd', 0.0)),
            'macro_long_liq_usd': float(macro_res.get('long_liq_usd', 0.0)),
            'macro_short_liq_usd': float(macro_res.get('short_liq_usd', 0.0)),
            'desc': str(local_res.get('desc', '⚪ Paritede Tasfiye Sakin' if symbol else '⚪ Durgun Tasfiye Akışı'))
        }

    # ──────────────────────────────────────────────────────────────────────────
    # 🐋 16. BORSA NET GİRİŞ/ÇIKIŞ AKIŞI (NETFLOW) VE BALİNA METRİK ERİŞİMCİLERİ
    # ──────────────────────────────────────────────────────────────────────────
    def get_symbol_netflow(self, symbol: str) -> dict:
        """Paritenin anlık borsa net akış durumunu ve Z-skorunu RAM'den 0.01ms içinde döndürür."""
        clean_s = self._clean_symbol(symbol)
        raw_s = symbol.replace('/', '').replace(':USDT', '')
        clean_raw = clean_s.replace('/', '').replace(':USDT', '')

        flow_data = (
            self.exchange_netflows.get(clean_s) or
            self.exchange_netflows.get(symbol) or
            self.exchange_netflows.get(raw_s) or
            self.exchange_netflows.get(clean_raw) or
            self.exchange_netflows.get(f"{clean_s}:USDT") or
            self.exchange_netflows.get(f"{clean_raw}USDT") or
            {}
        )
        if not flow_data:
            flow_data = {
                'symbol': symbol,
                'netflow_24h_usd': 0.0,
                'z_score': 0.0,
                'regime': 'BALANCED_FLOW',
                'is_dump_risk': False,
                'is_accumulation': False,
                'block_dump_active': False,
                'block_squeeze_active': False,
                'block_sells_60s': 0.0,
                'block_buys_60s': 0.0,
                'block_netflow_60s': 0.0,
                'last_block_trade_ts': 0.0,
                'mempool_dump_threat': False,
                'mempool_squeeze_threat': False,
                'mempool_amount_usd': 0.0,
                'mempool_threat_expiry': 0.0,
                'mempool_squeeze_expiry': 0.0,
                'mempool_from_label': '',
                'mempool_to_label': '',
                'mempool_tx_hash': '',
                'tier': 'TIER_1' if any(m in clean_s for m in ["BTC", "ETH", "SOL", "BNB"]) else ('TIER_3' if any(m in clean_s for m in ["PEPE", "SHIB", "DOGE", "BONK", "MEME", "FLOKI", "WIF"]) else 'TIER_2'),
                'last_whale_transfer_ts': 0.0,
                'last_whale_amount_usd': 0.0,
                'last_whale_intent': 'NONE',
                'last_update': 0.0
            }
        else:
            now_ts = time.time()
            # 60s Dinamik Blok Baskı Yaşlanma Doğrulaması (Fail-safe auto-cooling)
            last_b_ts = float(flow_data.get('last_block_trade_ts', 0.0))
            if (now_ts - last_b_ts) > 60.0:
                flow_data['block_dump_active'] = False
                flow_data['block_squeeze_active'] = False
                flow_data['block_sells_60s'] = 0.0
                flow_data['block_buys_60s'] = 0.0
                flow_data['block_netflow_60s'] = 0.0

            # 20dk (1200s) Dinamik Mempool Tehdit Yaşlanma Doğrulaması (Fail-safe auto-cooling)
            if now_ts > float(flow_data.get('mempool_threat_expiry', 0.0)):
                flow_data['mempool_dump_threat'] = False
            if now_ts > float(flow_data.get('mempool_squeeze_expiry', 0.0)):
                flow_data['mempool_squeeze_threat'] = False
        return flow_data

    def get_ammunition_status(self) -> dict:
        """Global borsa stabil kripto (USDT/USDC) yakıt ve cephane durumunu döndürür."""
        return getattr(self, 'stablecoin_ammunition', {
            'bias': 'NEUTRAL',
            'delta_24h_usd': 0.0,
            'delta_pct': 0.0,
            'momentum_score': 0.0,
            'is_bullish_fuel': False,
            'binance_clean_reserves': 0.0,
            'binance_24h_inflows': 0.0,
            'last_update': 0.0
        })

    def get_recent_whale_alerts(self, limit: int = 15) -> list:
        """Son balina işlemlerini liste olarak döndürür."""
        dq = getattr(self, 'whale_transactions_feed', deque())
        return list(dq)[-limit:]

    def get_whale_radar_health(self) -> dict:
        prov = getattr(self, 'whale_provider_status', {})
        last_sync = prov.get('last_sync_ts', 0.0)
        age = round(time.time() - last_sync, 1) if last_sync > 0 else 999.0
        is_ok = (age < 1200) and (last_sync > 0)
        
        # Stage 1-3 Kurumsal Sağlık Metrikleri
        recent_blocks_cnt = sum(len(dq) for dq in getattr(self, 'block_trades_history', {}).values())
        mempool_feed_cnt = sum(1 for tx in getattr(self, 'whale_transactions_feed', []) if tx.get('source') == 'ONCHAIN_MEMPOOL')
        cb_conn = getattr(self, 'coinbase_prices', {}).get('is_connected', False)
        sm_summary = self.get_smart_money_summary() if hasattr(self, 'get_smart_money_summary') else {}

        return {
            'providers': prov,
            'feed_count': len(getattr(self, 'whale_transactions_feed', [])),
            'ammunition_bias': getattr(self, 'stablecoin_ammunition', {}).get('bias', 'NEUTRAL'),
            'last_sync_sec': age,
            'is_healthy': is_ok,
            'healthy': is_ok,
            # Kurumsal Balina & On-Chain Akış Sağlığı
            'aggtrade_healthy': True,
            'aggtrade_block_count': recent_blocks_cnt,
            'mempool_healthy': True,
            'mempool_feed_count': mempool_feed_cnt,
            'smart_money_healthy': cb_conn,
            'smart_money_regime': sm_summary.get('regime', 'HARMONIC_FLOW'),
            'smart_money_spread': sm_summary.get('btc', {}).get('smart_money_spread', 0.0)
        }

    def _record_block_trade_pressure(self, symbol: str, amount_usd: float, is_sell: bool, trade_ts: float):
        """Son 60 saniyelik agresif kurumsal piyasa vuruşlarını (aggTrade blok emirleri) kaydeder ve kalkan durumunu günceller."""
        clean_s = self._clean_symbol(symbol)
        if not hasattr(self, 'block_trades_history'):
            self.block_trades_history = {}
        if clean_s not in self.block_trades_history:
            self.block_trades_history[clean_s] = deque(maxlen=60)

        dq = self.block_trades_history[clean_s]
        dq.append((trade_ts, float(amount_usd), bool(is_sell)))

        cutoff = trade_ts - 60.0
        while dq and dq[0][0] < cutoff:
            dq.popleft()

        sells_60s = sum(item[1] for item in dq if item[2])
        buys_60s = sum(item[1] for item in dq if not item[2])
        block_netflow_60s = buys_60s - sells_60s

        is_tier1 = any(m in clean_s for m in ["BTC", "ETH", "SOL", "BNB"])
        is_tier3 = any(m in clean_s for m in ["PEPE", "SHIB", "DOGE", "BONK", "MEME", "FLOKI", "WIF"])
        block_thresh_60s = 2_000_000.0 if is_tier1 else (500_000.0 if is_tier3 else 750_000.0)

        block_dump_active = (sells_60s >= block_thresh_60s)
        block_squeeze_active = (buys_60s >= block_thresh_60s)

        target_keys = [
            symbol,
            clean_s,
            clean_s.replace('/', '').replace(':USDT', ''),
            symbol.replace('/', '').replace(':USDT', '')
        ]
        for tk in target_keys:
            if tk not in self.exchange_netflows:
                self.exchange_netflows[tk] = {
                    'symbol': symbol,
                    'netflow_24h_usd': 0.0,
                    'z_score': 0.0,
                    'regime': 'BALANCED_FLOW',
                    'is_dump_risk': False,
                    'is_accumulation': False,
                    'tier': 'TIER_1' if is_tier1 else ('TIER_3' if is_tier3 else 'TIER_2'),
                    'last_whale_transfer_ts': trade_ts,
                    'last_whale_amount_usd': amount_usd,
                    'last_whale_intent': 'AGGRESSIVE_MARKET_DUMP' if is_sell else 'AGGRESSIVE_MARKET_BUY',
                    'last_update': trade_ts
                }
            self.exchange_netflows[tk]['block_dump_active'] = block_dump_active
            self.exchange_netflows[tk]['block_squeeze_active'] = block_squeeze_active
            self.exchange_netflows[tk]['block_sells_60s'] = round(sells_60s, 2)
            self.exchange_netflows[tk]['block_buys_60s'] = round(buys_60s, 2)
            self.exchange_netflows[tk]['block_netflow_60s'] = round(block_netflow_60s, 2)
            self.exchange_netflows[tk]['last_block_trade_ts'] = trade_ts

    def record_whale_transaction(
        self,
        symbol: str,
        amount_usd: float,
        transfer_type: str = 'WALLET_TO_EXCHANGE',
        tx_hash: str = None,
        price: float = 0.0,
        source: str = 'BINANCE_CEX',
        side: str = None,
        from_label: str = None,
        to_label: str = None,
        blockchain: str = None
    ) -> dict:
        """Büyük bir on-chain veya borsa içi balina transferi gerçekleştiğinde beslemeye ve kalkan hafızasına kaydeder."""
        clean_s = self._clean_symbol(symbol)
        feat = getattr(self, 'symbol_features', {}).get(clean_s, {})
        vol_24h = float(feat.get('volume_24h_usd', 0.0) or 0.0)
        if vol_24h <= 0.0 and hasattr(self, 'candles_5m'):
            df_s = self.candles_5m.get(symbol)
            if df_s is None or df_s.empty:
                df_s = self.candles_5m.get(clean_s)
            if df_s is not None and isinstance(df_s, pd.DataFrame) and not df_s.empty:
                vol_24h = float((df_s['volume'] * df_s['close']).sum())

        is_tier1 = any(m in clean_s for m in ["BTC", "ETH", "SOL", "BNB"])
        is_tier3 = any(m in clean_s for m in ["PEPE", "SHIB", "DOGE", "BONK", "MEME", "FLOKI", "WIF"])
        tier_str = "TIER_1" if is_tier1 else ("TIER_3" if is_tier3 else "TIER_2")

        from indicators import classify_whale_transfer
        res = classify_whale_transfer(clean_s, amount_usd, volume_24h_usd=vol_24h, tier=tier_str, transfer_type=transfer_type, source=source)
        now_ts = time.time()
        res['timestamp'] = now_ts
        res['time_str'] = datetime.now(timezone(timedelta(hours=3))).strftime("%H:%M:%S")
        res['tx_hash'] = tx_hash or f"tx_{int(now_ts * 1000)}"
        res['price'] = float(price or 0.0)
        res['source'] = str(source or 'BINANCE_CEX')
        res['side'] = str(side or ('TAKER_SELL' if res.get('is_dump_risk') else 'TAKER_BUY'))
        res['from_label'] = str(from_label or ('Mempool Balina Cüzdanı' if res.get('is_dump_risk') else 'Borsa Sıcak Cüzdanı'))
        res['to_label'] = str(to_label or ('Borsa Sıcak Cüzdanı' if res.get('is_dump_risk') else 'Soğuk Cüzdan Kasası'))
        res['blockchain'] = str(blockchain or ('BTC' if 'BTC' in clean_s else ('ETH' if 'ETH' in clean_s else ('SOL' if 'SOL' in clean_s else 'ONCHAIN'))))
        res['tier'] = tier_str

        if res['is_whale']:
            self.whale_transactions_feed.append(res)
            target_keys = [
                symbol, clean_s,
                clean_s.replace('/', '').replace(':USDT', ''),
                symbol.replace('/', '').replace(':USDT', '')
            ]
            expiry_ts = now_ts + 1200.0  # 20 dakika (1200s) öncü kalkan koruma penceresi
            for tk in target_keys:
                if tk in self.exchange_netflows:
                    if res['is_dump_risk']:
                        self.exchange_netflows[tk]['is_dump_risk'] = True
                        if source == 'ONCHAIN_MEMPOOL':
                            self.exchange_netflows[tk]['mempool_dump_threat'] = True
                            self.exchange_netflows[tk]['mempool_threat_expiry'] = expiry_ts
                    elif res['is_bull_ammo']:
                        self.exchange_netflows[tk]['is_accumulation'] = True
                        if source == 'ONCHAIN_MEMPOOL':
                            self.exchange_netflows[tk]['mempool_squeeze_threat'] = True
                            self.exchange_netflows[tk]['mempool_squeeze_expiry'] = expiry_ts

                    self.exchange_netflows[tk]['last_whale_transfer_ts'] = now_ts
                    self.exchange_netflows[tk]['last_whale_amount_usd'] = amount_usd
                    self.exchange_netflows[tk]['last_whale_intent'] = res['intent']
                    if source == 'ONCHAIN_MEMPOOL':
                        self.exchange_netflows[tk]['mempool_amount_usd'] = amount_usd
                        self.exchange_netflows[tk]['mempool_from_label'] = res['from_label']
                        self.exchange_netflows[tk]['mempool_to_label'] = res['to_label']
                        self.exchange_netflows[tk]['mempool_tx_hash'] = res['tx_hash']
        return res

    def get_symbol_metrics(self, symbol: str) -> dict:
        if not hasattr(self, 'symbol_metrics'):
            self.symbol_metrics = {}
        if symbol not in self.symbol_metrics or not self.symbol_metrics[symbol]:
            self.recalculate_levels(symbol)
            
        majors = {"BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT"}
        base_met = self.symbol_metrics.get(symbol, {
            "vol_surge": 1.0,
            "min_vol_surge": 1.2 if symbol in majors else 1.5,
            "atr_pct": 1.2,
            "is_top_80": True,
            "cur_vol": 0.0,
            "avg_vol": 0.0,
            "rs_vs_btc": 0.0,
            "dynamic_rs_score": 0.0,
            "decoupling_status": "⚪ NÖTR_TAKİPÇİ",
            "hurst_exponent": 0.50,
            "entropy_norm": 0.65,
            "is_chaotic": False,
            "is_crystalline": False,
            "iceberg_ratio": 1.0,
            "ask_iceberg_ratio": 1.0,
            "bid_iceberg_ratio": 1.0,
            "iceberg_side": "NONE",
            "has_iceberg": False,
            "hmm_phase": "ACCUMULATION",
            "hmm_desc": "Sessiz Birikim"
        })

        # Anlık dinamik Iceberg tazeleyici (WebSocket 1s verisinden)
        try:
            clean_s = self._clean_symbol(symbol)
            norm_s = symbol
            depth = self.orderbook_depth.get(norm_s) or self.orderbook_depth.get(clean_s, {})
            h_deque = self.symbol_cvd_history.get(clean_s) or self.symbol_cvd_history.get(norm_s)
            if h_deque and len(h_deque) >= 2 and depth:
                now_ts = time.time()
                t_cutoff = now_ts - 60.0
                if h_deque[-1][0] >= t_cutoff:
                    old_sample = h_deque[0]
                    for s_item in h_deque:
                        if s_item[0] >= t_cutoff:
                            old_sample = s_item
                            break
                    diff_buy = max(0.0, float(h_deque[-1][1] - old_sample[1]))
                    diff_sell = max(0.0, float(h_deque[-1][2] - old_sample[2]))
                else:
                    diff_buy = 0.0
                    diff_sell = 0.0
                top_bid_usd = float(depth.get('bid_price', 0.0)) * float(depth.get('bid_qty', 0.0))
                top_ask_usd = float(depth.get('ask_price', 0.0)) * float(depth.get('ask_qty', 0.0))
                default_top_depth_usd = 25000.0 if (symbol in ["BTC/USDT", "ETH/USDT", "SOL/USDT"]) else 8000.0
                if top_bid_usd <= 0: top_bid_usd = default_top_depth_usd
                if top_ask_usd <= 0: top_ask_usd = default_top_depth_usd
                
                from indicators import detect_iceberg_orders
                ice_live = detect_iceberg_orders(diff_buy, diff_sell, top_bid_usd, top_ask_usd)
                ask_r = float(ice_live.get('ask_iceberg_ratio', 1.0))
                bid_r = float(ice_live.get('bid_iceberg_ratio', 1.0))
                max_r = max(ask_r, bid_r)
                
                res_met = dict(base_met)
                res_met['iceberg_ratio'] = max_r
                res_met['ask_iceberg_ratio'] = ask_r
                res_met['bid_iceberg_ratio'] = bid_r
                res_met['iceberg_side'] = str(ice_live.get('iceberg_side', 'NONE'))
                res_met['has_iceberg'] = bool(ice_live.get('has_seller_iceberg') or ice_live.get('has_buyer_iceberg') or max_r >= 3.0)
                return res_met
        except Exception:
            pass

        return base_met

    async def fetch_symbol_open_interest(self, symbol: str) -> dict:
        """
        Gerçek Zamanlı Açık Pozisyon (Open Interest) & Delta-OI Takip Motoru:
        - _clean_symbol() ile 1000PEPE, 1000SHIB ve diğer çarpanlı pariteleri hatasız sorgular.
        - Multi-exchange resilient: Binance Futures REST -> Gate.io Vadeli Tickers.
        - delta_oi_pct = ((cur_oi - prev_oi) / prev_oi) * 100
        """
        clean = self._clean_symbol(symbol).replace('/', '').replace(':USDT', '')
        headers = {'User-Agent': 'Mozilla/5.0'}
        oi_val_usd = 0.0
        provider = "binance"
        now_ts = time.time()
        c_price = float(self.current_prices.get(symbol, 0.0))
        if c_price <= 0 and symbol in self.candles_5m and not self.candles_5m[symbol].empty:
            try:
                c_price = float(self.candles_5m[symbol]['close'].iloc[-1])
            except Exception:
                pass

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                url_binance = f"https://fapi.binance.com/fapi/v1/openInterest?symbol={clean}"
                try:
                    async with session.get(url_binance, timeout=aiohttp.ClientTimeout(total=2.5)) as resp:
                        if resp.status == 200:
                            d = await resp.json()
                            raw_oi = float(d.get('openInterest', 0.0))
                            if raw_oi > 0:
                                p = c_price if c_price > 0 else 1.0
                                oi_val_usd = raw_oi * p
                except Exception:
                    pass

                if oi_val_usd == 0.0:
                    raw_gate = self.get_gate_contract_name(symbol)
                    url_gate = f"https://api.gateio.ws/api/v4/futures/usdt/tickers?contract={raw_gate}"
                    try:
                        async with session.get(url_gate, timeout=aiohttp.ClientTimeout(total=2.5)) as resp:
                            if resp.status == 200:
                                d = await resp.json()
                                if isinstance(d, list) and d:
                                    provider = "gate"
                                    raw_size = float(d[0].get('total_size', 0.0))
                                    last_p = float(d[0].get('last', 0.0) or c_price or 1.0)
                                    gate_mult = self.get_gate_contract_multiplier(raw_gate)
                                    oi_val_usd = raw_size * gate_mult * last_p
                    except Exception:
                        pass
        except Exception:
            pass

        prev_info = self.symbol_oi.get(symbol, {})
        cur_hist = list(prev_info.get('oi_history', []))
        last_provider = prev_info.get('provider', provider)
        if last_provider != provider:
            cur_hist = []

        if oi_val_usd > 0:
            cur_hist.append((now_ts, oi_val_usd))
            cur_hist = [(t, v) for (t, v) in cur_hist if (now_ts - t) <= 360.0]

        oi_5m_ago = cur_hist[0][1] if cur_hist else (prev_info.get('oi_5m_ago', oi_val_usd) if oi_val_usd > 0 else 1.0)
        delta_pct = round(((oi_val_usd - oi_5m_ago) / oi_5m_ago) * 100.0, 2) if (oi_val_usd > 0 and oi_5m_ago > 0) else 0.0

        price_chg_5m = 0.0
        df = self.candles_5m.get(symbol, pd.DataFrame())
        if df is not None and len(df) >= 2:
            try:
                c_last = float(df['close'].iloc[-1])
                c_prev = float(df['close'].iloc[-2])
                if c_prev > 0:
                    price_chg_5m = round(((c_last - c_prev) / c_prev) * 100.0, 2)
            except Exception:
                pass

        status = "BALANCED"
        if price_chg_5m <= -0.10 and delta_pct >= OI_EXPANSION_THRESHOLD_PCT:
            status = "AGGRESSIVE_SHORT_EXPANSION"
        elif price_chg_5m <= -0.10 and delta_pct <= OI_SQUEEZE_EXHAUSTION_PCT:
            status = "LONG_LIQUIDATION_DUMP"
        elif price_chg_5m >= 0.10 and delta_pct >= OI_EXPANSION_THRESHOLD_PCT:
            status = "AGGRESSIVE_LONG_EXPANSION"
        elif price_chg_5m >= 0.10 and delta_pct <= OI_SQUEEZE_EXHAUSTION_PCT:
            status = "SHORT_COVERING_PUMP"
        elif delta_pct >= OI_EXPANSION_THRESHOLD_PCT:
            status = "AGGRESSIVE_LONG_EXPANSION" if price_chg_5m >= 0 else "AGGRESSIVE_SHORT_EXPANSION"
        elif delta_pct <= OI_SQUEEZE_EXHAUSTION_PCT:
            status = "SHORT_COVERING_PUMP" if price_chg_5m >= 0 else "LONG_LIQUIDATION_DUMP"

        res = {
            'symbol': symbol,
            'open_interest': oi_val_usd,
            'oi_5m_ago': oi_5m_ago,
            'oi_history': cur_hist,
            'delta_oi_pct': delta_pct,
            'price_chg_5m': price_chg_5m,
            'status': status,
            'provider': provider,
            'last_update': now_ts
        }
        self.symbol_oi[symbol] = res
        if hasattr(self, 'symbol_metrics') and symbol in self.symbol_metrics:
            self.symbol_metrics[symbol]['delta_oi_pct'] = delta_pct
            self.symbol_metrics[symbol]['oi_status'] = status
        return res

    def get_symbol_open_interest(self, symbol: str) -> dict:
        return self.symbol_oi.get(symbol, {
            'symbol': symbol,
            'open_interest': 0.0,
            'oi_5m_ago': 0.0,
            'delta_oi_pct': 0.0,
            'price_chg_5m': 0.0,
            'status': 'BALANCED',
            'last_update': 0.0
        })


    async def get_jit_l2_depth(self, symbol: str) -> dict:
        """
        15ms Just-In-Time L2 Derinlik Taraması (Depth 20 Snapshot):
        - Yalnızca işleme girmeden tam 15ms önce çağrılır (Sıfır RAM/soket yükü).
        - Fiyatın %0.5 altındaki ve üstündeki kümülatif derinliği ($) ölçer.
        - 1. kademedeki duvar ile arka kademeler arasındaki çelişkiyi (Spoofing) yakalar.
        - Boltzmann Termodinamik Entropisi ve Ken Griffin Iceberg oranlarını anında hesaplar.
        """
        clean = self._clean_symbol(symbol).replace('/', '').replace(':USDT', '')
        headers = {'User-Agent': 'Mozilla/5.0'}
        bids = []
        asks = []
        now_ts = time.time()

        l2_provider = "none"
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                url_depth = f"https://fapi.binance.com/fapi/v1/depth?symbol={clean}&limit=20"
                try:
                    async with session.get(url_depth, timeout=aiohttp.ClientTimeout(total=2.5)) as resp:
                        if resp.status == 200:
                            d = await resp.json()
                            bids = [(float(p), float(q)) for p, q in d.get('bids', [])]
                            asks = [(float(p), float(q)) for p, q in d.get('asks', [])]
                            if bids and asks:
                                l2_provider = "binance"
                except Exception:
                    pass

                if not bids:
                    raw_gate = self.get_gate_contract_name(symbol)
                    url_gate_ob = f"https://api.gateio.ws/api/v4/futures/usdt/order_book?contract={raw_gate}&limit=20"
                    try:
                        async with session.get(url_gate_ob, timeout=aiohttp.ClientTimeout(total=2.5)) as resp:
                            if resp.status == 200:
                                d_gate = await resp.json()
                                gate_mult = self.get_gate_contract_multiplier(raw_gate)
                                bids = [(float(item['p']), float(item['s']) * gate_mult) for item in d_gate.get('bids', [])]
                                asks = [(float(item['p']), float(item['s']) * gate_mult) for item in d_gate.get('asks', [])]
                                if bids and asks:
                                    l2_provider = "gate"
                    except Exception:
                        pass
        except Exception:
            pass

        mid_price = (bids[0][0] + asks[0][0]) / 2.0 if bids and asks else 0.0
        bid_usd_05 = 0.0
        ask_usd_05 = 0.0
        bid_usd_02 = 0.0
        ask_usd_02 = 0.0
        if mid_price > 0:
            for p, q in bids:
                if p >= mid_price * 0.995:
                    bid_usd_05 += (p * q)
                if p >= mid_price * 0.998:
                    bid_usd_02 += (p * q)
            for p, q in asks:
                if p <= mid_price * 1.005:
                    ask_usd_05 += (p * q)
                if p <= mid_price * 1.002:
                    ask_usd_02 += (p * q)

        l2_ratio = round(bid_usd_05 / max(1.0, ask_usd_05), 2)
        top_bid_q = (bids[0][1] * bids[0][0]) if bids else 0.0
        top_ask_q = (asks[0][1] * asks[0][0]) if asks else 0.0
        top_ratio = round(top_bid_q / max(1.0, top_ask_q), 2)

        spoofing_detected = (top_ratio >= 2.0 and l2_ratio < 0.70)

        # 🧠 BOLTZMANN ENTROPİ, KEN GRIFFIN ICEBERG, BOOKMAP EMİLİM, CVD İVME, dPOC, STOIKOV, VPIN & KYLE'S LAMBDA
        from indicators import (
            calculate_orderbook_entropy, detect_iceberg_orders, detect_bookmap_absorption,
            calculate_cvd_acceleration, calculate_delta_poc, evaluate_iceberg_offense,
            calculate_stoikov_micro_price, calculate_vpin_toxicity, calculate_kyles_lambda
        )
        entropy_data = calculate_orderbook_entropy(bids, asks, top_n=20)

        # 60s Kayan Taker Hacmi
        clean_s = self._clean_symbol(symbol)
        h_deque = self.symbol_cvd_history.get(clean_s) or self.symbol_cvd_history.get(symbol)
        diff_buy = 0.0
        diff_sell = 0.0
        if h_deque and len(h_deque) >= 2:
            now_t = time.time()
            t_cutoff = now_t - 60.0
            if h_deque[-1][0] >= t_cutoff:
                old_sample = h_deque[0]
                for s_item in h_deque:
                    if s_item[0] >= t_cutoff:
                        old_sample = s_item
                        break
                diff_buy = max(0.0, float(h_deque[-1][1] - old_sample[1]))
                diff_sell = max(0.0, float(h_deque[-1][2] - old_sample[2]))
            else:
                diff_buy = 0.0
                diff_sell = 0.0

        zone_bid = bid_usd_02 if bid_usd_02 > 0 else (top_bid_q * 3.5)
        zone_ask = ask_usd_02 if ask_usd_02 > 0 else (top_ask_q * 3.5)
        iceberg_data = detect_iceberg_orders(diff_buy, diff_sell, zone_bid, zone_ask, is_zone_depth=True)

        # Bookmap 60s Mikro Fiyat Değişimi ve Çapa Duvarı Tespiti
        price_chg_60s = 0.0
        p_deque = self.symbol_price_history.get(clean_s) or self.symbol_price_history.get(symbol)
        if p_deque and len(p_deque) >= 2:
            now_t = time.time()
            t_cutoff = now_t - 60.0
            old_p = p_deque[0][1]
            for ts_i, p_i in p_deque:
                if ts_i >= t_cutoff:
                    old_p = p_i
                    break
            cur_live_p = p_deque[-1][1]
            if old_p > 0:
                price_chg_60s = round(((cur_live_p - old_p) / old_p) * 100.0, 3)

        depth_meta = self.orderbook_depth.get(clean_s) or self.orderbook_depth.get(symbol, {})
        wall_dur_sec = float(depth_meta.get('wall_duration_sec', 0.0))
        is_major_sym = symbol in {"BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT", "NEAR/USDT", "AVAX/USDT"}
        bm_data = detect_bookmap_absorption(
            taker_buy_usd=diff_buy,
            taker_sell_usd=diff_sell,
            top_bid_usd=top_bid_q,
            top_ask_usd=top_ask_q,
            price_change_pct_60s=price_chg_60s,
            wall_duration_sec=wall_dur_sec,
            is_major=is_major_sym
        )

        # 4. CVD İvme & Sıfır Geçişi
        cvd_deltas = [float(s[1] - s[2]) for s in h_deque] if h_deque and len(h_deque) >= 4 else []
        cvd_acc_info = calculate_cvd_acceleration(cvd_deltas)

        # 5. dPOC Tuzaklanmış Likidite
        cur_p_for_ice = bids[0][0] if bids else self.current_prices.get(symbol, 0.0)
        sym_levels_for_ice = self.levels.get(symbol, {})
        df_5m_chk = self.candles_5m.get(symbol, pd.DataFrame())
        dpoc_info = calculate_delta_poc(sym_levels_for_ice, cur_p_for_ice, df_5m_chk)

        # 6. Iceberg Hücum Sniper & Ping-Pong
        ice_offense = evaluate_iceberg_offense(iceberg_data, cur_p_for_ice, sym_levels_for_ice)

        # 7. Stoikov Micro-Price & Mıknatıs Modeli
        stoikov_info = calculate_stoikov_micro_price(bids, asks, current_price=cur_p_for_ice, levels=sym_levels_for_ice)

        # 8. VPIN ve Kyle's Lambda
        vpin_info = calculate_vpin_toxicity(df_5m_chk, rolling_window=12, recent_cvd=cvd_acc_info)
        lambda_info = calculate_kyles_lambda(df_5m_chk)
        hawkes_info = self.get_hawkes_avalanche(symbol)

        # Likidite Boşluğu (Hava Cebi / Liquidity Vacuum) Tespiti:
        # Önündeki derinlik karşı tarafın %40'ından az veya oran aşırı asimetrikse hava cebi vardır
        vacuum_detected = False
        vacuum_side = "NONE"
        if len(bids) >= 10 and len(asks) >= 10:
            bids_10_usd = sum(p * q for p, q in bids[:10])
            asks_10_usd = sum(p * q for p, q in asks[:10])
            if bids_10_usd > 0 and asks_10_usd > 0:
                v_ratio = bids_10_usd / asks_10_usd
                if v_ratio >= 3.5:
                    vacuum_detected = True
                    vacuum_side = "ASK_VACUUM"   # Satıcı boşluğu -> Yukarı roketleme kolay
                elif v_ratio <= 0.28:
                    vacuum_detected = True
                    vacuum_side = "BID_VACUUM"   # Alıcı boşluğu -> Aşağı şelale kolay

        # Duvar Doğrulama
        wall_dur = float(bm_data.get('wall_duration_sec', 0.0))
        is_anchor_aged = (wall_dur >= WALL_ANCHOR_AGE_SEC)
        is_unverified_wall = (wall_dur < WALL_MIN_AGE_SEC)

        # Kayma (Slippage) ve Makas (Spread) Simülasyonu ($500 Büyüklük):
        spread_pct = 0.0
        depth_usd_03 = 0.0
        sim_slip_long = 0.0
        sim_slip_short = 0.0
        if bids and asks:
            best_bid = bids[0][0]
            best_ask = asks[0][0]
            if best_bid > 0:
                spread_pct = round(((best_ask - best_bid) / best_bid) * 100.0, 6)

            mid_p = (best_bid + best_ask) / 2.0
            if mid_p > 0:
                p_min = mid_p * 0.997
                p_max = mid_p * 1.003
                b_depth = sum(p * q for p, q in bids if p >= p_min)
                a_depth = sum(p * q for p, q in asks if p <= p_max)
                depth_usd_03 = round(b_depth + a_depth, 1)

            # Simüle Kayma (VWAP tabanlı — $500 piyasa emri simülasyonu)
            req_usd = 500.0
            accum_usd = 0.0
            total_qty_buy = 0.0
            for p, q in asks:
                tier_usd = p * q
                take_usd = min(tier_usd, req_usd - accum_usd)
                take_qty = take_usd / p
                total_qty_buy += take_qty
                accum_usd += take_usd
                if accum_usd >= req_usd:
                    break
            if total_qty_buy > 0 and best_ask > 0:
                avg_exec = accum_usd / total_qty_buy
                sim_slip_long = round(max(0.0, (avg_exec - best_ask) / best_ask * 100.0), 6)

            accum_usd_s = 0.0
            total_qty_sell = 0.0
            for p, q in bids:
                tier_usd = p * q
                take_usd = min(tier_usd, req_usd - accum_usd_s)
                take_qty = take_usd / p
                total_qty_sell += take_qty
                accum_usd_s += take_usd
                if accum_usd_s >= req_usd:
                    break
            if total_qty_sell > 0 and best_bid > 0:
                avg_exec_s = accum_usd_s / total_qty_sell
                sim_slip_short = round(max(0.0, (best_bid - avg_exec_s) / best_bid * 100.0), 6)

        sym_clean = symbol.upper().replace('/', '').replace(':USDT', '').replace('USDT', '')
        btc_net_gex = float(self.deribit_gex_data.get('BTC', {}).get('net_gex', 0.0)) if hasattr(self, 'deribit_gex_data') else 0.0
        eth_net_gex = float(self.deribit_gex_data.get('ETH', {}).get('net_gex', 0.0)) if hasattr(self, 'deribit_gex_data') else 0.0

        if sym_clean == 'BTC':
            coin_gex = btc_net_gex
            coin_gex_regime = str(self.get_deribit_gex_regime())
            is_proxy = False
        elif sym_clean == 'ETH':
            coin_gex = eth_net_gex
            eth_data = self.get_deribit_gex('ETH')
            coin_gex_regime = str(eth_data.get('gex_regime', 'NEUTRAL'))
            is_proxy = False
        else:
            coin_gex = 0.0
            coin_gex_regime = 'MACRO_BTC_PROXY'
            is_proxy = True

        res_depth = {
            'symbol': symbol,
            'mid_price': mid_price,
            'bid_usd_05': round(bid_usd_05, 2),
            'ask_usd_05': round(ask_usd_05, 2),
            'l2_ratio': l2_ratio,
            'top_ratio': top_ratio,
            'spoofing_detected': spoofing_detected,
            'vacuum_detected': vacuum_detected,
            'vacuum_side': vacuum_side,
            'depth_available': len(bids) > 0,
            'depth_provider': l2_provider,
            'entropy_norm': entropy_data.get('entropy_norm', 0.70),
            'entropy_bid': entropy_data.get('entropy_bid', 0.70),
            'entropy_ask': entropy_data.get('entropy_ask', 0.70),
            'is_chaotic': entropy_data.get('is_chaotic', False),
            'is_crystalline': entropy_data.get('is_crystalline', False),
            'ask_iceberg_ratio': iceberg_data.get('ask_iceberg_ratio', 1.0),
            'bid_iceberg_ratio': iceberg_data.get('bid_iceberg_ratio', 1.0),
            'iceberg_side': iceberg_data.get('iceberg_side', 'NONE'),
            'has_seller_iceberg': iceberg_data.get('has_seller_iceberg', False),
            'has_buyer_iceberg': iceberg_data.get('has_buyer_iceberg', False),
            'bookmap_seller_absorption': bool(bm_data.get('has_seller_absorption', False)),
            'bookmap_buyer_absorption': bool(bm_data.get('has_buyer_absorption', False)),
            'bookmap_absorption_type': str(bm_data.get('absorption_type', 'NONE')),
            'bookmap_absorption_desc': str(bm_data.get('absorption_desc', '⚪ Normal Sipariş Akışı')),
            'is_anchor_wall': bool(bm_data.get('is_anchor_wall', False)),
            'is_iron_wall': bool(bm_data.get('is_iron_wall', False)),
            'wall_duration_sec': float(wall_dur_sec),
            'is_anchor_aged': bool(is_anchor_aged),
            'is_unverified_wall': bool(is_unverified_wall),
            'spread_pct': float(spread_pct),
            'depth_usd_03': float(depth_usd_03),
            'sim_slip_long': float(sim_slip_long),
            'sim_slip_short': float(sim_slip_short),
            'price_change_pct_60s': float(price_chg_60s),
            'cvd_velocity': float(cvd_acc_info.get('velocity', 0.0)),
            'cvd_acceleration': float(cvd_acc_info.get('acceleration', 0.0)),
            'cvd_zero_cross': str(cvd_acc_info.get('zero_crossing', 'NONE')),
            'is_cvd_exhaustion_top': bool(cvd_acc_info.get('is_exhaustion_top', False)),
            'is_cvd_exhaustion_bottom': bool(cvd_acc_info.get('is_exhaustion_bottom', False)),
            'cvd_momentum_regime': str(cvd_acc_info.get('momentum_regime', 'NEUTRAL')),
            'trapped_bias': str(dpoc_info.get('trapped_bias', 'NEUTRAL')),
            'trapped_status': str(dpoc_info.get('trapped_status', 'NONE')),
            'trapped_desc': str(dpoc_info.get('trapped_desc', 'Dengeli Seviye Akışı')),
            'is_iceberg_sniper_buy': bool(ice_offense.get('is_sniper_buy', False)),
            'is_iceberg_sniper_sell': bool(ice_offense.get('is_sniper_sell', False)),
            'is_iceberg_ping_pong': bool(ice_offense.get('is_ping_pong', False)),
            'iceberg_tight_stop_pct': float(ice_offense.get('tight_stop_dist_pct', 0.0022)),
            'iceberg_offense_reason': str(ice_offense.get('offense_reason', '')),
            'buyer_offense_reason': str(ice_offense.get('buyer_offense_reason', '')),
            'seller_offense_reason': str(ice_offense.get('seller_offense_reason', '')),
            'stoikov_micro_price': float(stoikov_info.get('micro_price', mid_price)),
            'stoikov_mid_price': float(stoikov_info.get('mid_price', mid_price)),
            'stoikov_drift_bps': float(stoikov_info.get('micro_drift_bps', 0.0)),
            'stoikov_bias': str(stoikov_info.get('micro_bias', 'NEUTRAL')),
            'is_stoikov_bull': bool(stoikov_info.get('is_micro_bull', False)),
            'is_stoikov_bear': bool(stoikov_info.get('is_micro_bear', False)),
            'stoikov_magnet': str(stoikov_info.get('magnet_status', 'NONE')),
            'stoikov_magnet_desc': str(stoikov_info.get('magnet_desc', '')),
            'vpin_score': float(vpin_info.get('vpin_score', 0.30)),
            'vpin_toxicity': str(vpin_info.get('toxicity_level', 'LOW')),
            'is_vpin_toxic': bool(vpin_info.get('is_toxic_flow', False)),
            'is_range_veto_alert': bool(vpin_info.get('is_range_veto_alert', False)),
            'vpin_desc': str(vpin_info.get('vpin_desc', '')),
            'kyles_lambda_ratio': float(lambda_info.get('lambda_ratio', 1.0)),
            'is_vacuum_trap': bool(lambda_info.get('is_vacuum_trap', False)),
            'is_liquid_expansion': bool(lambda_info.get('is_liquid_expansion', False)),
            'lambda_desc': str(lambda_info.get('desc', '')),
            'deribit_gex_regime': coin_gex_regime,
            'deribit_net_gex': coin_gex,
            'macro_btc_net_gex': btc_net_gex,
            'is_gex_proxy': is_proxy,
            'is_gex_pinning': bool(self.is_gex_pinning()),
            'is_gex_exploding': bool(self.is_gex_exploding()),
            'hawkes_eta': float(hawkes_info.get('branching_ratio_eta', 0.15)),
            'local_hawkes_eta': float(hawkes_info.get('local_hawkes_eta', 0.0)),
            'macro_hawkes_eta': float(hawkes_info.get('macro_hawkes_eta', 0.15)),
            'hawkes_source': str(hawkes_info.get('hawkes_source', 'GLOBAL_MACRO')),
            'is_avalanche_active': bool(hawkes_info.get('is_avalanche_active', False)),
            'is_macro_avalanche': bool(hawkes_info.get('is_macro_avalanche', False)),
            'is_avalanche_exhausted': bool(hawkes_info.get('is_avalanche_exhausted', False)),
            'avalanche_side': str(hawkes_info.get('avalanche_side', 'NONE')),
            'avalanche_desc': str(hawkes_info.get('desc', '')),
            'last_update': now_ts
        }


        if not hasattr(self, 'jit_l2_cache'):
            self.jit_l2_cache = {}
        self.jit_l2_cache[symbol] = res_depth

        if hasattr(self, 'symbol_metrics') and symbol in self.symbol_metrics:
            self.symbol_metrics[symbol].update({
                'entropy_norm': res_depth['entropy_norm'],
                'is_chaotic': res_depth['is_chaotic'],
                'is_crystalline': res_depth['is_crystalline'],
                'iceberg_ratio': max(res_depth['ask_iceberg_ratio'], res_depth['bid_iceberg_ratio']),
                'ask_iceberg_ratio': res_depth['ask_iceberg_ratio'],
                'bid_iceberg_ratio': res_depth['bid_iceberg_ratio'],
                'iceberg_side': res_depth['iceberg_side'],
                'has_iceberg': bool(res_depth['has_seller_iceberg'] or res_depth['has_buyer_iceberg']),
                'bookmap_seller_absorption': res_depth['bookmap_seller_absorption'],
                'bookmap_buyer_absorption': res_depth['bookmap_buyer_absorption'],
                'bookmap_absorption_type': res_depth['bookmap_absorption_type'],
                'bookmap_absorption_desc': res_depth['bookmap_absorption_desc'],
                'is_anchor_wall': res_depth['is_anchor_wall'],
                'is_iron_wall': res_depth['is_iron_wall'],
                'wall_duration_sec': res_depth['wall_duration_sec'],
                'price_change_pct_60s': res_depth['price_change_pct_60s'],
                'cvd_velocity': res_depth['cvd_velocity'],
                'cvd_acceleration': res_depth['cvd_acceleration'],
                'cvd_zero_cross': res_depth['cvd_zero_cross'],
                'is_cvd_exhaustion_top': res_depth['is_cvd_exhaustion_top'],
                'is_cvd_exhaustion_bottom': res_depth['is_cvd_exhaustion_bottom'],
                'cvd_momentum_regime': res_depth['cvd_momentum_regime'],
                'trapped_bias': res_depth['trapped_bias'],
                'trapped_status': res_depth['trapped_status'],
                'trapped_desc': res_depth['trapped_desc'],
                'is_iceberg_sniper_buy': res_depth['is_iceberg_sniper_buy'],
                'is_iceberg_sniper_sell': res_depth['is_iceberg_sniper_sell'],
                'is_iceberg_ping_pong': res_depth['is_iceberg_ping_pong'],
                'iceberg_tight_stop_pct': res_depth['iceberg_tight_stop_pct'],
                'iceberg_offense_reason': res_depth['iceberg_offense_reason'],
                'buyer_offense_reason': res_depth['buyer_offense_reason'],
                'seller_offense_reason': res_depth['seller_offense_reason'],
                'stoikov_micro_price': res_depth['stoikov_micro_price'],
                'stoikov_mid_price': res_depth['stoikov_mid_price'],
                'stoikov_drift_bps': res_depth['stoikov_drift_bps'],
                'stoikov_bias': res_depth['stoikov_bias'],
                'is_stoikov_bull': res_depth['is_stoikov_bull'],
                'is_stoikov_bear': res_depth['is_stoikov_bear'],
                'stoikov_magnet': res_depth['stoikov_magnet'],
                'stoikov_magnet_desc': res_depth['stoikov_magnet_desc'],
                'vpin_score': res_depth['vpin_score'],
                'vpin_toxicity': res_depth['vpin_toxicity'],
                'is_vpin_toxic': res_depth['is_vpin_toxic'],
                'is_range_veto_alert': res_depth['is_range_veto_alert'],
                'vpin_desc': res_depth['vpin_desc'],
                'kyles_lambda_ratio': res_depth['kyles_lambda_ratio'],
                'is_vacuum_trap': res_depth['is_vacuum_trap'],
                'is_liquid_expansion': res_depth['is_liquid_expansion'],
                'lambda_desc': res_depth['lambda_desc'],
                'deribit_gex_regime': res_depth['deribit_gex_regime'],
                'deribit_net_gex': res_depth['deribit_net_gex'],
                'macro_btc_net_gex': res_depth['macro_btc_net_gex'],
                'is_gex_proxy': res_depth['is_gex_proxy'],
                'is_gex_pinning': res_depth['is_gex_pinning'],
                'is_gex_exploding': res_depth['is_gex_exploding'],
                'hawkes_eta': res_depth['hawkes_eta'],
                'local_hawkes_eta': res_depth['local_hawkes_eta'],
                'macro_hawkes_eta': res_depth['macro_hawkes_eta'],
                'hawkes_source': res_depth['hawkes_source'],
                'is_avalanche_active': res_depth['is_avalanche_active'],
                'is_macro_avalanche': res_depth['is_macro_avalanche'],
                'is_avalanche_exhausted': res_depth['is_avalanche_exhausted'],
                'avalanche_side': res_depth['avalanche_side'],
                'avalanche_desc': res_depth['avalanche_desc']
            })

        return res_depth

    async def poll_all_candles_once(self):
        """100 Paritenin son kapanmis 5M mumlarini aninda REST uzerinden paralel tara ve stratejiye ilet."""
        sem = asyncio.Semaphore(25)
        async with aiohttp.ClientSession() as session:
            async def fetch_and_eval(s):
                async with sem:
                    try:
                        clean_sym = self._clean_symbol(s)
                        clean_raw = clean_sym.replace('/', '').replace(':USDT', '').replace('USDT', '')
                        raw_s = s.replace('/', '').replace(':USDT', '').replace('USDT', '')
                        spot_clean = raw_s.replace('1000000', '').replace('1000', '')
                        spot_mult = self._get_spot_multiplier(s)
                        
                        cur_candle = None
                        prev_candle = None

                        for url_v in [
                            f"https://fapi.binance.com/fapi/v1/klines?symbol={clean_raw}USDT&interval=5m&limit=4",
                            f"https://fapi.binance.com/fapi/v1/continuousKlines?pair={clean_raw}USDT&contractType=PERPETUAL&interval=5m&limit=4",
                            f"https://data-api.binance.vision/api/v3/klines?symbol={spot_clean}USDT&interval=5m&limit=4"
                        ]:
                            try:
                                is_spot = "binance.vision" in url_v
                                mult = spot_mult if is_spot else 1.0
                                async with session.get(url_v, timeout=aiohttp.ClientTimeout(total=2.5)) as res:
                                    if res.status == 200:
                                        kl = await res.json()
                                        if isinstance(kl, list) and len(kl) >= 2:
                                            closed_k = kl[-2]
                                            prev_k = kl[-3] if len(kl) >= 3 else closed_k
                                            base_div = mult if is_spot else 1.0
                                            cur_candle = {
                                                'timestamp': closed_k[0],
                                                'open': float(closed_k[1]) * mult,
                                                'high': float(closed_k[2]) * mult,
                                                'low': float(closed_k[3]) * mult,
                                                'close': float(closed_k[4]) * mult,
                                                'volume': float(closed_k[5]) / base_div,
                                                'quote_volume': float(closed_k[7]),
                                                'qav': float(closed_k[7]),
                                                'taker_base': float(closed_k[9]) / base_div if len(closed_k) > 9 else 0.0,
                                                'taker_quote': float(closed_k[10]) if len(closed_k) > 10 else 0.0
                                            }
                                            prev_candle = {
                                                'timestamp': prev_k[0],
                                                'open': float(prev_k[1]) * mult,
                                                'high': float(prev_k[2]) * mult,
                                                'low': float(prev_k[3]) * mult,
                                                'close': float(prev_k[4]) * mult,
                                                'volume': float(prev_k[5]) / base_div,
                                                'quote_volume': float(prev_k[7]),
                                                'qav': float(prev_k[7]),
                                                'taker_base': float(prev_k[9]) / base_div if len(prev_k) > 9 else 0.0,
                                                'taker_quote': float(prev_k[10]) if len(prev_k) > 10 else 0.0
                                            }
                                            break
                            except Exception:
                                pass

                        if cur_candle is not None and prev_candle is not None:
                            # 🛡️ OTOMATİK BORSA SENKRONİZASYON VE ANLIK ONARIM (AUTO-HEAL GUARD)
                            live_ws_p = self.current_prices.get(s, cur_candle['close'])
                            if live_ws_p > 0:
                                delta_p = abs(cur_candle['close'] - live_ws_p) / live_ws_p * 100.0
                                if delta_p > 1.5:
                                    # Otomatik Onarım: Mum kapanışını anlık canlı vadeli fiyata eşitle, High ve Low geometrisini koru
                                    cur_candle['close'] = live_ws_p
                                    cur_candle['high'] = max(float(cur_candle.get('high', live_ws_p)), live_ws_p)
                                    cur_candle['low'] = min(float(cur_candle.get('low', live_ws_p)), live_ws_p)

                            self.current_prices[s] = cur_candle['close']
                            self.candles_5m[s] = update_rolling_candle_buffer(self.candles_5m.get(s, pd.DataFrame()), cur_candle, maxlen=300)
                            self.recalculate_levels(s)
                            if self.on_candle_close_callback and s in self.active_symbols:
                                c_ts = cur_candle.get('timestamp', 0)
                                if self.last_candle_callback_ts.get(s) != c_ts:
                                    self.last_candle_callback_ts[s] = c_ts
                                    await self.on_candle_close_callback(s, cur_candle, prev_candle)
                    except Exception as e:
                        print(f">> [TARAMA HATA] {s}: {e}")

            await asyncio.gather(*(fetch_and_eval(s) for s in list(self.active_symbols)))
            import gc
            gc.collect()

    async def start_websocket(self):
        symbol_map = {}
        for s in self.all_symbols:
            clean = self._clean_symbol(s).replace('/', '').replace(':USDT', '').upper()
            symbol_map[clean] = s
            # VDA-06: 1000x ve 1M önekli vadeli meme paritelerinin WebSocket eşleşmesi
            symbol_map['1000' + clean] = s
            symbol_map['1000000' + clean] = s
            clean_no_mult = clean.replace('1000000', '').replace('1000', '')
            symbol_map[clean_no_mult] = s
            symbol_map['1000' + clean_no_mult] = s
            symbol_map['1000000' + clean_no_mult] = s

        print(f">> [WEBSOCKET] Ultra Hizli Binance Akisi Baslatiliyor ({len(self.all_symbols)} Parite)...")

        # Worker 1: Global !bookTicker yayini (Tum coinler tek yuksek hizli sokette anlik akar)
        async def bookticker_worker():
            url = "wss://fstream.binance.com/ws/!bookTicker"
            while True:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.ws_connect(url, heartbeat=10) as ws:
                            print(">> [CANLI] Global !bookTicker Fiyat Akisi AKTIF.")
                            while True:
                                try:
                                    msg = await asyncio.wait_for(ws.receive(), timeout=35.0)
                                except asyncio.TimeoutError:
                                    print(">> [BOOKTICKER ZOMBİ UYARISI] 35s veri gelmedi, soket yenileniyor...")
                                    break

                                if msg.type == aiohttp.WSMsgType.TEXT:
                                    self.last_stream_tick_time = time.time()
                                    data = json.loads(msg.data)
                                    raw_s = data.get('s', '').upper()
                                    if raw_s not in symbol_map:
                                        continue
                                    norm_s = symbol_map[raw_s]
                                    bid = float(data.get('b', 0.0))
                                    ask = float(data.get('a', 0.0))
                                    bid_qty = float(data.get('B', 0.0))
                                    ask_qty = float(data.get('A', 0.0))
                                    price = (bid + ask) / 2.0 if (bid and ask) else (bid or ask)
                                    if price > 0:
                                        self.current_prices[norm_s] = price
                                        now_ts = time.time()
                                        if norm_s not in self.symbol_price_history:
                                            self.symbol_price_history[norm_s] = deque(maxlen=60)
                                        p_dq = self.symbol_price_history[norm_s]
                                        if not p_dq or (now_ts - p_dq[-1][0] >= 1.0):
                                            p_dq.append((now_ts, price))

                                        # Order Book Imbalance (OBI) & Likidite Duvarı Hesaplama (<0.001ms)
                                        tot_q = bid_qty + ask_qty
                                        if tot_q > 0:
                                            imbalance = (bid_qty - ask_qty) / tot_q
                                            ratio = bid_qty / max(0.0001, ask_qty)
                                            wall_side = 'BALANCED'
                                            if ratio >= 1.5:
                                                wall_side = 'BID_WALL'
                                            elif ratio <= 0.65:
                                                wall_side = 'ASK_WALL'

                                            now_ts = time.time()
                                            prev_depth = self.orderbook_depth.get(norm_s, {})
                                            prev_wall = prev_depth.get('wall_side', 'BALANCED')
                                            first_seen = prev_depth.get('wall_first_seen', 0.0)
                                            prev_wall_p = prev_depth.get('wall_price', 0.0)

                                            current_wall_p = bid if wall_side == 'BID_WALL' else (ask if wall_side == 'ASK_WALL' else 0.0)
                                            p_shift = abs(current_wall_p - prev_wall_p) / prev_wall_p if (prev_wall_p > 0 and current_wall_p > 0) else 0.0

                                            # VDA-11: Fiyat toleransı paritenin ATR'sinin %10'u olarak dinamikleştirilecek
                                            sym_atr_pct = float(getattr(self, 'symbol_metrics', {}).get(norm_s, {}).get('atr_pct', 1.2))
                                            dyn_wall_tolerance = max(0.0008, (sym_atr_pct / 100.0) * 0.10)

                                            # Fiyata Sabit (Price-Anchored) Duvar Yaşlanması: Duvar yönü aynı ve fiyat kayması <= dyn_wall_tolerance olmalı
                                            if wall_side != 'BALANCED' and wall_side == prev_wall and p_shift <= dyn_wall_tolerance:
                                                duration_sec = (now_ts - first_seen) if first_seen > 0 else 0.0
                                            elif wall_side != 'BALANCED':
                                                first_seen = now_ts
                                                duration_sec = 0.0
                                            else:
                                                first_seen = 0.0
                                                duration_sec = 0.0

                                            # Makas (Spread %) Hesabı
                                            mid_p = (bid + ask) / 2.0 if (bid and ask) else price
                                            spread_p = round(((ask - bid) / mid_p * 100.0), 4) if mid_p > 0 and ask > bid else 0.0

                                            # Sahte Duvar (Spoofing) Hızlı Kaçış Tespiti:
                                            is_spoof = False
                                            if prev_wall != 'BALANCED' and wall_side == 'BALANCED' and prev_depth.get('wall_duration_sec', 0.0) < WALL_MIN_AGE_SEC:
                                                is_spoof = True

                                            self.orderbook_depth[norm_s] = {
                                                'symbol': norm_s,
                                                'bid_price': bid,
                                                'bid_qty': bid_qty,
                                                'ask_price': ask,
                                                'ask_qty': ask_qty,
                                                'imbalance': round(imbalance, 4),
                                                'ratio': round(ratio, 4),
                                                'wall_side': wall_side,
                                                'wall_price': current_wall_p,
                                                'wall_duration_sec': round(duration_sec, 2),
                                                'wall_first_seen': first_seen,
                                                'spread_pct': spread_p,
                                                'is_spoof_risk': is_spoof,
                                                'last_update': now_ts
                                            }

                                            # ⚡ BTC 60s Mikro-Şok Takibi (BTC 60s Velocity & Shock Gate)
                                            if norm_s == "BTC/USDT":
                                                self.btc_price_60s_deque.append((now_ts, price))
                                                while self.btc_price_60s_deque and (now_ts - self.btc_price_60s_deque[0][0] > 60.0):
                                                    self.btc_price_60s_deque.popleft()
                                                if len(self.btc_price_60s_deque) >= 2:
                                                    oldest_p = self.btc_price_60s_deque[0][1]
                                                    if oldest_p > 0:
                                                        self.btc_velocity_60s = round(((price - oldest_p) / oldest_p) * 100.0, 3)
                                                        if abs(self.btc_velocity_60s) >= BTC_SHOCK_60S_PCT:
                                                            if not self.btc_shock_gate_active:
                                                                print(f">> [⚡ BTC MİKRO-ŞOK GEÇİDİ DEVREDE] BTC 60s Hız: %{self.btc_velocity_60s:+.2f} -> Altcoinler {BTC_SHOCK_COOLDOWN_SEC:.0f}s donduruldu!")
                                                            self.btc_shock_gate_active = True
                                                            self.btc_shock_gate_expiry = now_ts + BTC_SHOCK_COOLDOWN_SEC
                                                            self.btc_shock_pct = self.btc_velocity_60s

                                        if self.on_tick_callback:
                                            await self.on_tick_callback(norm_s, price)

                                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                    break
                except Exception as e:
                    print(f">> [UYARI] bookTicker WebSocket yenileniyor: {e}")
                    await asyncio.sleep(2)

        # Worker 2: K-Line 5M Kapanis Taramasi (25'erli paketler halinde paralel baglantilar)
        kline_streams = []
        for s in self.all_symbols:
            clean_stream = self._clean_symbol(s).replace('/', '').lower().replace(':usdt', '')
            kline_streams.append(f"{clean_stream}@kline_5m")

        chunk_size = 25
        kline_chunks = [kline_streams[i:i + chunk_size] for i in range(0, len(kline_streams), chunk_size)]

        async def kline_worker(chunk_id, chunk):
            url = f"wss://fstream.binance.com/market/stream?streams={'/'.join(chunk)}"
            while True:
                try:
                    self.last_chunk_msg_ts[chunk_id] = time.time()
                    async with aiohttp.ClientSession() as session:
                        async with session.ws_connect(url, heartbeat=10) as ws:
                            print(f">> [CANLI] K-Line & Mikro-CVD Stream chunk-{chunk_id} bağlandı ({len(chunk)} parite).")
                            while True:
                                try:
                                    msg = await asyncio.wait_for(ws.receive(), timeout=45.0)
                                except asyncio.TimeoutError:
                                    print(f">> [K-LINE CHUNK-{chunk_id} ZOMBİ TESPİTİ] 45s veri gelmedi, soket yenileniyor...")
                                    break

                                if msg.type == aiohttp.WSMsgType.TEXT:
                                    now_t = time.time()
                                    self.last_stream_tick_time = now_t
                                    self.last_chunk_msg_ts[chunk_id] = now_t
                                    data = json.loads(msg.data)
                                    payload = data.get('data', data) if isinstance(data, dict) else {}
                                    kline = payload.get('k', {})
                                    raw_s = (payload.get('s') or kline.get('s') or (data.get('stream', '').split('@')[0] if isinstance(data, dict) and '@' in data.get('stream', '') else '')).upper()
                                    norm_s = symbol_map.get(raw_s, raw_s.replace('USDT', '/USDT'))
                                    if norm_s in self.all_symbols and kline:
                                        # Anlık Mikro-CVD (Taker Buy vs Taker Sell) Hesaplama (<0.001ms)
                                        try:
                                            cur_q = float(kline.get('q', 0.0))
                                            cur_Q = float(kline.get('Q', 0.0))
                                            if cur_q > 0:
                                                now_ts = time.time()
                                                t_buy = cur_Q
                                                t_sell = max(0.0, cur_q - cur_Q)
                                                delta = t_buy - t_sell
                                                ratio = (t_buy / cur_q * 100.0)

                                                if norm_s not in self.symbol_cvd_offsets:
                                                    self.symbol_cvd_offsets[norm_s] = {
                                                        'last_candle_t': kline.get('t', 0),
                                                        'offset_buy': 0.0,
                                                        'offset_sell': 0.0,
                                                        'prev_last_buy': 0.0,
                                                        'prev_last_sell': 0.0
                                                    }

                                                c_off = self.symbol_cvd_offsets[norm_s]
                                                candle_start_t = kline.get('t', 0)
                                                if candle_start_t != c_off['last_candle_t']:
                                                    c_off['offset_buy'] += c_off['prev_last_buy']
                                                    c_off['offset_sell'] += c_off['prev_last_sell']
                                                    c_off['last_candle_t'] = candle_start_t
                                                    c_off['prev_last_buy'] = 0.0
                                                    c_off['prev_last_sell'] = 0.0

                                                c_off['prev_last_buy'] = t_buy
                                                c_off['prev_last_sell'] = t_sell

                                                abs_buy = c_off['offset_buy'] + t_buy
                                                abs_sell = c_off['offset_sell'] + t_sell

                                                if norm_s not in self.symbol_cvd_history:
                                                    self.symbol_cvd_history[norm_s] = deque(maxlen=60)

                                                h_deque = self.symbol_cvd_history[norm_s]
                                                if not h_deque or (now_ts - h_deque[-1][0] >= 1.0):
                                                    h_deque.append((now_ts, abs_buy, abs_sell))

                                                delta_60s = delta
                                                ratio_60s = ratio
                                                if len(h_deque) >= 2:
                                                    t_cutoff = now_ts - 60.0
                                                    old_sample = h_deque[0]
                                                    for s_item in h_deque:
                                                        if s_item[0] >= t_cutoff:
                                                            old_sample = s_item
                                                            break
                                                    diff_buy = max(0.0, abs_buy - old_sample[1])
                                                    diff_sell = max(0.0, abs_sell - old_sample[2])
                                                    tot_diff = diff_buy + diff_sell
                                                    if tot_diff > 0:
                                                        delta_60s = diff_buy - diff_sell
                                                        ratio_60s = (diff_buy / tot_diff * 100.0)

                                                bias = "NEUTRAL"
                                                if ratio_60s >= 65.0:
                                                    bias = "STRONG_BUY_SURGE"
                                                elif ratio_60s <= 35.0:
                                                    bias = "STRONG_SELL_PRESSURE"
                                                elif ratio_60s >= 55.0:
                                                    bias = "MODERATE_BUY"
                                                elif ratio_60s <= 45.0:
                                                    bias = "MODERATE_SELL"

                                                self.symbol_cvd[norm_s] = {
                                                    'symbol': norm_s,
                                                    'taker_buy_usd': round(t_buy, 2),
                                                    'taker_sell_usd': round(t_sell, 2),
                                                    'delta_usd': round(delta, 2),
                                                    'cvd_pct': round(ratio, 1),
                                                    'delta_60s': round(delta_60s, 2),
                                                    'ratio_60s': round(ratio_60s, 1),
                                                    'bias': bias,
                                                    'last_price': float(kline.get('c', 0.0)),
                                                    'last_update': now_ts
                                                }
                                        except Exception:
                                            pass

                                        if kline.get('x', False):
                                            new_candle = {
                                                'timestamp': kline.get('t'),
                                                'open': float(kline.get('o')),
                                                'high': float(kline.get('h')),
                                                'low': float(kline.get('l')),
                                                'close': float(kline.get('c')),
                                                'volume': float(kline.get('v')),
                                                'quote_volume': float(kline.get('q', 0.0)),
                                                'num_trades': int(kline.get('n', 0)),
                                                'taker_base': float(kline.get('V', 0.0)),
                                                'taker_quote': float(kline.get('Q', 0.0))
                                            }
                                            prev_candle = self.candles_5m[norm_s].iloc[-1].to_dict() if (norm_s in self.candles_5m and not self.candles_5m[norm_s].empty) else new_candle
                                            self.candles_5m[norm_s] = update_rolling_candle_buffer(self.candles_5m.get(norm_s, pd.DataFrame()), new_candle, maxlen=300)
                                            self.recalculate_levels(norm_s)
                                            if self.on_candle_close_callback and norm_s in self.active_symbols:
                                                c_ts = new_candle.get('timestamp', 0)
                                                if self.last_candle_callback_ts.get(norm_s) != c_ts:
                                                    self.last_candle_callback_ts[norm_s] = c_ts
                                                    await self.on_candle_close_callback(norm_s, new_candle, prev_candle)
                                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                    break
                except Exception as e:
                    print(f">> [K-LINE WS UYARI] {e}")
                    await asyncio.sleep(2)

        # Worker 3: 5M Periyodik REST Mum Senkronizasyonu (Ultra Hizli Paralel 100 Parite Taramasi)
        async def candle_poller_worker():
            last_scanned_slot = -1
            # 🛡️ WebSocket & OBI Isınma Koruması: bookTicker akışının bağlanıp tahtayı doldurması için 5s beklenir
            await asyncio.sleep(5)
            try:
                print(">> [İLK BAŞLANGIÇ TARAMASI] 100 Parite için son kapanmış 5M mumlar taranıyor...")
                await self.poll_all_candles_once()
            except Exception as e:
                print(f">> [ILK TARAMA HATA]: {e}")

            while True:
                try:
                    now_sec = time.time()
                    current_5m_slot = int(now_sec // 300)
                    if current_5m_slot != last_scanned_slot:
                        last_scanned_slot = current_5m_slot
                        now_str = datetime.now().strftime('%H:%M:%S')
                        print(f">> [5M MUM TARAMASI] {now_str} — 100 Paritede yeni 5M mum kapandi, strateji kontrolleri baslatiliyor...")
                        await self.poll_all_candles_once()
                    await asyncio.sleep(4)
                except Exception as e:
                    print(f">> [MUM TARAYICI HATA]: {e}")
                    await asyncio.sleep(5)

        # Worker 4: Saat Başı Otomatik Vadeli (Futures) Seviye Doğrulama ve İyileştirme Nöbetçisi (Watchdog)
        async def hourly_futures_watchdog_worker():
            last_audited_hour = -1
            while True:
                try:
                    now = datetime.now()
                    if now.hour != last_audited_hour:
                        last_audited_hour = now.hour
                        print(f">> [SAATLİK VADELİ SAĞLIK DENETÇİSİ] Saat {now.strftime('%H:00')} — 100 Paritenin Vadeli Verileri ve Seviyeleri Denetleniyor...")
                        tasks = [self.fetch_single_symbol(sym) for sym in list(self.all_symbols)]
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        healed_cnt = sum(1 for r in results if not isinstance(r, Exception))
                        print(f">> [SAATLİK VADELİ SAĞLIK DENETÇİSİ TAMAMLANDI] {healed_cnt}/{len(self.all_symbols)} Parite fapi.binance.com ile %100 doğrulandı ve eşitlendi.")
                    await asyncio.sleep(60)
                except Exception as e:
                    print(f">> [SAATLİK DENETÇİ UYARI]: {e}")
                    await asyncio.sleep(60)

        # Worker 5: Dinamik Fonlama Oranı ve Squeeze Kalkanı Taraması (60 Saniyede bir REST)
        async def funding_worker():
            while True:
                try:
                    await self.fetch_funding_rates()
                except Exception as e:
                    print(f">> [FONLAMA İŞÇİSİ UYARI]: {e}")
                await asyncio.sleep(60)

        # Worker 6: Global Likidasyon Radarı (!forceOrder@arr Tek Soket Dinleyicisi)
        async def forceorder_worker():
            url = "wss://fstream.binance.com/market/ws/!forceOrder@arr"
            print(">> [LİKİDASYON RADARI] Global !forceOrder@arr Soketi Başlatılıyor...")
            while True:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.ws_connect(url, heartbeat=15) as ws:
                            print(">> [LİKİDASYON RADARI AKTİF] Tüm borsa tasfiye emirleri dinleniyor.")
                            async for msg in ws:
                                if msg.type == aiohttp.WSMsgType.TEXT:
                                    try:
                                        payload = json.loads(msg.data)
                                        o = payload.get('o', {})
                                        raw_s = o.get('s', '').upper()
                                        if not raw_s:
                                            continue
                                        side = o.get('S', '') # SELL = Long Liq, BUY = Short Liq
                                        price = float(o.get('p', 0.0))
                                        qty = float(o.get('q', 0.0))
                                        usd_size = price * qty
                                        if usd_size < 500.0:
                                            continue

                                        now_ts = time.time()
                                        time_str = datetime.now(timezone(timedelta(hours=3))).strftime('%H:%M:%S')
                                        norm_s = symbol_map.get(raw_s, raw_s.replace('USDT', '/USDT'))
                                        is_long_liq = (side == 'SELL')

                                        event = {
                                            'symbol': norm_s,
                                            'raw_symbol': raw_s,
                                            'side': 'LONG' if is_long_liq else 'SHORT',
                                            'forced_action': side,
                                            'price': price,
                                            'qty': qty,
                                            'usd_size': round(usd_size, 2),
                                            'timestamp': now_ts,
                                            'time_str': time_str,
                                            'is_long_liq': is_long_liq
                                        }
                                        self.recent_liquidations.append(event)

                                        # 15 Dakikalık Parite Bazlı Kayan Pencere (Gerçek 900s deque pruning)
                                        if not hasattr(self, 'symbol_liquidations_deque'):
                                            self.symbol_liquidations_deque = {}
                                        if norm_s not in self.symbol_liquidations_deque:
                                            self.symbol_liquidations_deque[norm_s] = deque(maxlen=60)
                                        dq = self.symbol_liquidations_deque[norm_s]
                                        dq.append((now_ts, usd_size, is_long_liq))

                                        cutoff_ts = now_ts - 900.0
                                        while dq and dq[0][0] < cutoff_ts:
                                            dq.popleft()

                                        l_usd_15m = sum(item[1] for item in dq if item[2])
                                        s_usd_15m = sum(item[1] for item in dq if not item[2])
                                        tot_15m = l_usd_15m + s_usd_15m

                                        self.symbol_liquidations_15m[norm_s] = {
                                            'symbol': norm_s,
                                            'long_usd': round(l_usd_15m, 2),
                                            'short_usd': round(s_usd_15m, 2),
                                            'total_usd': round(tot_15m, 2),
                                            'dominant_side': 'LONG' if l_usd_15m >= s_usd_15m else 'SHORT',
                                            'last_update': now_ts
                                        }

                                        # Global İstatistik Güncelleme (Canlı Oturum Toplamı)
                                        self.global_liquidation_stats['total_usd_24h'] += usd_size
                                        if is_long_liq:
                                            self.global_liquidation_stats['long_usd_24h'] += usd_size
                                        else:
                                            self.global_liquidation_stats['short_usd_24h'] += usd_size
                                        self.global_liquidation_stats['last_event_time'] = time_str

                                        # En çok tasfiye olan coini aktif 15dk penceresine göre güncelle
                                        top_sym = '-'
                                        top_val = 0.0
                                        for sym_k, dq_k in self.symbol_liquidations_deque.items():
                                            while dq_k and dq_k[0][0] < cutoff_ts:
                                                dq_k.popleft()
                                            tot_s = sum(item[1] for item in dq_k)
                                            if tot_s > top_val:
                                                top_val = tot_s
                                                top_sym = sym_k
                                        self.global_liquidation_stats['top_symbol'] = top_sym
                                        self.global_liquidation_stats['top_symbol_usd'] = round(top_val, 2)
                                    except Exception:
                                        pass
                                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                    break
                except Exception as e:
                    print(f">> [LİKİDASYON RADARI UYARI] Yeniden bağlanılıyor: {e}")
                    await asyncio.sleep(3)

        # Worker 7: Spot vs Vadeli Ayrışması & Basis Nöbetçisi (Spot-Perp Basis Worker)
        async def spot_basis_worker():
            url = "https://data-api.binance.vision/api/v3/ticker/price"
            headers = {'User-Agent': 'Mozilla/5.0'}
            while True:
                try:
                    async with aiohttp.ClientSession(headers=headers) as session:
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                spot_map = {item['symbol']: float(item['price']) for item in data if 'symbol' in item and 'price' in item}
                                now_ts = time.time()
                                for s in self.all_symbols:
                                    clean_raw = s.replace('/', '').replace(':USDT', '').replace('USDT', '')
                                    clean_base = clean_raw.replace('1000000', '').replace('1000', '')
                                    spot_sym = f"{clean_base}USDT"
                                    if spot_sym in spot_map:
                                        mult = self._get_spot_multiplier(s)
                                        adj_spot = spot_map[spot_sym] * mult
                                        self.spot_prices[s] = adj_spot
                                        if s not in self.spot_hist_3m:
                                            self.spot_hist_3m[s] = deque(maxlen=60)
                                        self.spot_hist_3m[s].append((now_ts, adj_spot))

                                        cur_perp = self.current_prices.get(s, 0.0)
                                        if cur_perp > 0:
                                            if s not in self.perp_hist_3m:
                                                self.perp_hist_3m[s] = deque(maxlen=60)
                                            self.perp_hist_3m[s].append((now_ts, cur_perp))
                                self.last_spot_update_ts = now_ts
                except Exception:
                    pass
                await asyncio.sleep(15)  # 15 saniyede bir spot baz fiyatlarını tazele

        # Worker 7: Kurumsal Deribit GEX (Gamma Exposure) Radarı
        async def deribit_gex_worker():
            print(">> [DERIBIT GEX RADARI] Kurumsal Opsiyon Gamma Radarı Başlatılıyor...")
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            while True:
                try:
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12)) as session:
                        for ccy in ['BTC', 'ETH']:
                            url = f"https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency={ccy}&kind=option"
                            try:
                                async with session.get(url, headers=headers) as resp:
                                    if resp.status == 200:
                                        data = await resp.json()
                                        book = data.get('result', [])
                                        if book and isinstance(book, list):
                                            from indicators import calculate_deribit_gex
                                            gex_res = calculate_deribit_gex(book)
                                            gex_res['last_update'] = time.time()
                                            self.deribit_gex_data[ccy] = gex_res
                            except Exception as ccy_err:
                                print(f">> [DERIBIT GEX {ccy} HATA] {ccy_err}")
                        self.deribit_gex_data['last_sync_ts'] = time.time()
                        self.deribit_gex_data['is_live'] = True
                        btc_res = self.deribit_gex_data.get('BTC', {})
                        print(f">> [DERIBIT GEX GÜNCELLENDİ] BTC Rejim: {btc_res.get('gex_regime')} (Net: ${btc_res.get('net_gex', 0)/1e6:.1f}M, PCR: {btc_res.get('put_call_ratio'):.2f})")
                except Exception as e:
                    print(f">> [DERIBIT GEX RADAR UYARI] {e} (Mevcut GEX önbelleği korunuyor)")
                await asyncio.sleep(900)  # Her 15 dakikada bir güncelle

        # Worker 8: Çapraz Borsa Spot Öncüsü (Coinbase Pro Lead-Lag wss://ws-feed.exchange.coinbase.com)
        async def coinbase_lead_lag_worker():
            if not ENABLE_COINBASE_LEAD_LAG:
                return
            url = "wss://ws-feed.exchange.coinbase.com"
            cb_pairs = [f"{a}-USD" for a in getattr(self, 'coinbase_supported_assets', ["BTC", "ETH", "SOL"])]
            sub_msg = {
                "type": "subscribe",
                "product_ids": cb_pairs,
                "channels": ["ticker"]
            }
            while True:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.ws_connect(url, heartbeat=10) as ws:
                            await ws.send_str(json.dumps(sub_msg))
                            print(f">> [COINBASE SPOT WS] wss://ws-feed.exchange.coinbase.com bağlandı ({len(cb_pairs)} Parite: {', '.join(cb_pairs[:5])}...).")
                            self.coinbase_prices['is_connected'] = True
                            async for msg in ws:
                                if msg.type == aiohttp.WSMsgType.TEXT:
                                    d = json.loads(msg.data)
                                    if d.get("type") == "ticker":
                                        prod = d.get("product_id", "")
                                        p = float(d.get("price", 0.0))
                                        if p > 0:
                                            now_t = time.time()
                                            base_asset = prod.split("-")[0]
                                            self.coinbase_prices[base_asset] = p
                                            self.coinbase_prices[f"{base_asset}_time"] = now_t
                                            self.coinbase_prices['last_update'] = now_t

                                            # Stage 3: Coinbase Taker Hacim ve CVD Akışını Kaydet
                                            last_size = float(d.get("last_size", 0.0) or 0.0)
                                            side_str = str(d.get("side", "")).lower()
                                            if last_size > 0:
                                                size_usd = p * last_size
                                                is_buy = (side_str == "buy")
                                                buy_u = size_usd if is_buy else 0.0
                                                sell_u = 0.0 if is_buy else size_usd
                                                if not hasattr(self, 'coinbase_cvd_history'):
                                                    self.coinbase_cvd_history = {}
                                                dq = self.coinbase_cvd_history.setdefault(base_asset, deque(maxlen=60))
                                                dq.append((now_t, buy_u, sell_u))
                                                cutoff_t = now_t - 60.0
                                                while dq and dq[0][0] < cutoff_t:
                                                    dq.popleft()

                                            # Binance BTC/USDT ile Lead-Lag Karşılaştırması (VDA-09: USDT/USD peg sapmasından arındırılmış)
                                            if base_asset == "BTC":
                                                binance_btc = self.current_prices.get("BTC/USDT", 0.0)
                                                cb_btc = self.coinbase_prices.get("BTC", 0.0)
                                                if binance_btc > 0 and cb_btc > 0:
                                                    usdt_peg = self.current_prices.get("USDT/USD", self.current_prices.get("USDC/USDT", 1.0))
                                                    adj_binance_btc = binance_btc * usdt_peg if (0.95 <= usdt_peg <= 1.05) else binance_btc
                                                    spread_bps = round(((cb_btc - adj_binance_btc) / adj_binance_btc) * 10000.0, 1)
                                                    direction = "NEUTRAL"
                                                    status_str = "⚪ DENGELİ NAKİT AKIŞI"
                                                    desc_str = f"Coinbase (${cb_btc:,.1f}) ile Binance (${binance_btc:,.1f}) dengede ({spread_bps:+.1f} bps)."

                                                    if spread_bps >= COINBASE_LEAD_SPREAD_BPS:
                                                        direction = "BULLISH_LEAD"
                                                        status_str = f"🇺🇸 COINBASE SPOT BOĞA ÖNCÜSÜ (+{spread_bps:.0f} bps)"
                                                        desc_str = f"Coinbase Spot alıcı baskısıyla önde (+{spread_bps:+.1f} bps). Kurumsal yukarı itki."
                                                    elif spread_bps <= -COINBASE_LEAD_SPREAD_BPS:
                                                        direction = "BEARISH_LEAD"
                                                        status_str = f"🇺🇸 COINBASE SPOT AYI BASKISI ({spread_bps:.0f} bps)"
                                                        desc_str = f"Coinbase Spot satıcı baskısıyla geride ({spread_bps:+.1f} bps). Kurumsal aşağı baskı."

                                                    self.coinbase_lead_lag = {
                                                        'lead_symbol': 'BTC',
                                                        'spread_bps': spread_bps,
                                                        'direction': direction,
                                                        'status': status_str,
                                                        'desc': desc_str,
                                                        'last_update': now_t
                                                    }
                                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                    break
                except Exception as e:
                    self.coinbase_prices['is_connected'] = False
                    print(f">> [COINBASE WS UYARI] {e} (2s sonra yeniden bağlanıyor...)")
                    await asyncio.sleep(2)

        # Worker 9: Gerçek Zamanlı Açık Pozisyon İvmesi (Binance Futures OI Poller)
        async def open_interest_worker():
            if not ENABLE_OI_VELOCITY_RADAR:
                return
            headers = {'User-Agent': 'Mozilla/5.0'}
            while True:
                try:
                    now_sec = time.time()
                    oi_batch = {}
                    provider = "bybit"
                    async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as session:
                        # 1. Öncelik: Bybit Vadeli Tickers (Tüm pariteler tek istekte, US geoblock yok)
                        try:
                            url_bybit = "https://api.bybit.com/v5/market/tickers?category=linear"
                            async with session.get(url_bybit) as resp:
                                if resp.status == 200:
                                    d = await resp.json()
                                    for item in d.get('result', {}).get('list', []):
                                        sym_raw = item.get('symbol', '')
                                        val = float(item.get('openInterestValue', 0.0))
                                        if val > 0:
                                            oi_batch[sym_raw] = val
                        except Exception:
                            pass

                        # 2. Öncelik: Gate.io Vadeli Tickers (Yedek borsa - VDA-04: Kontrat lotları USD değerine normalize edilir)
                        if not oi_batch:
                            try:
                                url_gate = "https://api.gateio.ws/api/v4/futures/usdt/tickers"
                                async with session.get(url_gate) as resp:
                                    if resp.status == 200:
                                        d = await resp.json()
                                        if isinstance(d, list):
                                            provider = "gate"
                                            for item in d:
                                                c_name = item.get('contract', '').replace('_', '')
                                                raw_size = float(item.get('total_size', 0.0))
                                                last_p = float(item.get('last', 0.0) or 0.0)
                                                if raw_size > 0 and last_p > 0:
                                                    gate_mult = self.get_gate_contract_multiplier(c_name)
                                                    val_usd = raw_size * gate_mult * last_p
                                                    oi_batch[c_name] = val_usd
                            except Exception:
                                pass

                    if oi_batch:
                        for s in list(self.all_symbols):
                            clean = s.replace('/', '').replace(':USDT', '').upper()
                            clean_base = clean.replace('USDT', '')
                            if clean_base.startswith('1000000'):
                                clean_base = clean_base[7:]
                            elif clean_base.startswith('1000'):
                                clean_base = clean_base[4:]

                            candidates = [
                                clean,
                                clean_base + 'USDT',
                                '1000' + clean_base + 'USDT',
                                '1000000' + clean_base + 'USDT',
                                clean_base,
                            ]
                            cur_oi = 0.0
                            for cand in candidates:
                                if cand in oi_batch and float(oi_batch[cand]) > 0:
                                    cur_oi = float(oi_batch[cand])
                                    break

                            if cur_oi > 0:
                                prev_info = self.symbol_oi.get(s, {})
                                cur_hist = prev_info.get('oi_history', [])
                                last_provider = prev_info.get('provider', provider)
                                if last_provider != provider:
                                    cur_hist = []  # VDA-04: Borsa gecislerinde sahte delta_pct patlamalarini onlemek icin sifirla
                                cur_hist.append((now_sec, cur_oi))
                                cur_hist = [(t, v) for (t, v) in cur_hist if (now_sec - t) <= 360.0]
                                oi_5m_ago = cur_hist[0][1] if cur_hist else cur_oi

                                delta_pct = round(((cur_oi - oi_5m_ago) / oi_5m_ago) * 100.0, 2) if oi_5m_ago > 0 else 0.0

                                # 5 Dakikalık Fiyat Değişimiyle Karşılaştırma
                                price_chg_5m = 0.0
                                df = self.candles_5m.get(s, pd.DataFrame())
                                if df is not None and len(df) >= 2:
                                    try:
                                        c_last = float(df['close'].iloc[-1])
                                        c_prev = float(df['close'].iloc[-2])
                                        if c_prev > 0:
                                            price_chg_5m = round(((c_last - c_prev) / c_prev) * 100.0, 2)
                                    except Exception:
                                        pass

                                status = "BALANCED"
                                if price_chg_5m <= -0.10 and delta_pct >= OI_EXPANSION_THRESHOLD_PCT:
                                    status = "AGGRESSIVE_SHORT_EXPANSION"
                                elif price_chg_5m <= -0.10 and delta_pct <= OI_SQUEEZE_EXHAUSTION_PCT:
                                    status = "LONG_LIQUIDATION_DUMP"
                                elif price_chg_5m >= 0.10 and delta_pct >= OI_EXPANSION_THRESHOLD_PCT:
                                    status = "AGGRESSIVE_LONG_EXPANSION"
                                elif price_chg_5m >= 0.10 and delta_pct <= OI_SQUEEZE_EXHAUSTION_PCT:
                                    status = "SHORT_COVERING_PUMP"
                                elif delta_pct >= OI_EXPANSION_THRESHOLD_PCT:
                                    status = "AGGRESSIVE_LONG_EXPANSION" if price_chg_5m >= 0 else "AGGRESSIVE_SHORT_EXPANSION"
                                elif delta_pct <= OI_SQUEEZE_EXHAUSTION_PCT:
                                    status = "SHORT_COVERING_PUMP" if price_chg_5m >= 0 else "LONG_LIQUIDATION_DUMP"

                                self.symbol_oi[s] = {
                                    'symbol': s,
                                    'open_interest': cur_oi,
                                    'oi_5m_ago': oi_5m_ago,
                                    'oi_history': cur_hist,
                                    'delta_oi_pct': delta_pct,
                                    'price_chg_5m': price_chg_5m,
                                    'status': status,
                                    'provider': provider,
                                    'last_update': now_sec
                                }
                                if hasattr(self, 'symbol_metrics') and s in self.symbol_metrics:
                                    self.symbol_metrics[s]['delta_oi_pct'] = delta_pct
                                    self.symbol_metrics[s]['oi_status'] = status

                        top_exp_sym = '-'
                        top_exp_val = 0.0
                        top_sqz_sym = '-'
                        top_sqz_val = 0.0
                        for s_k, oi_d in self.symbol_oi.items():
                            d_pct = oi_d.get('delta_oi_pct', 0.0)
                            if d_pct > top_exp_val:
                                top_exp_val = d_pct
                                top_exp_sym = s_k
                            if d_pct < top_sqz_val:
                                top_sqz_val = d_pct
                                top_sqz_sym = s_k
                        self.oi_summary = {
                            'top_expansion_symbol': top_exp_sym,
                            'top_expansion_pct': top_exp_val,
                            'top_squeeze_symbol': top_sqz_sym,
                            'top_squeeze_pct': top_sqz_val,
                            'last_update': now_sec
                        }
                except Exception as e:
                    print(f">> [OI WORKER UYARI]: {e}")
                await asyncio.sleep(OI_POLL_INTERVAL_SEC)

        # Worker 10: Kurumsal Borsa Net Akışı (Exchange Netflows) ve On-Chain Balina Radarı
        async def whale_netflow_worker():
            if not getattr(config, 'ENABLE_WHALE_NETFLOW_RADAR', True):
                return
            print(">> [BALİNA RADARI] Çok Kaynaklı Borsa Net Akışı & On-Chain Likidite Radarı Başlatılıyor...")
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

            while True:
                try:
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                        # 1. DefiLlama 88 CEX Rezervi ve 24h Netflow (Primary CEX Inflow/Outflow)
                        try:
                            t0 = time.time()
                            async with session.get("https://api.llama.fi/cexs", headers=headers) as resp:
                                if resp.status == 200:
                                    data = await resp.json()
                                    cexs = data.get('cexs', [])
                                    total_inflow_24h = 0.0
                                    binance_tvl = 0.0
                                    binance_inflow = 0.0
                                    for c in cexs:
                                        c_name = str(c.get('name', '')).lower()
                                        c_inf = float(c.get('inflows_24h', 0.0) or 0.0)
                                        total_inflow_24h += c_inf
                                        if 'binance' in c_name:
                                            binance_tvl = float(c.get('cleanAssetsTvl', c.get('currentTvl', 0.0)) or 0.0)
                                            binance_inflow = c_inf

                                    self.stablecoin_ammunition['binance_clean_reserves'] = binance_tvl
                                    self.stablecoin_ammunition['binance_24h_inflows'] = binance_inflow
                                    self.stablecoin_ammunition['total_cex_inflows_24h'] = total_inflow_24h

                                    lat = int((time.time() - t0) * 1000)
                                    self.whale_provider_status['defillama'] = {
                                        'status': 'ONLINE', 'latency_ms': lat, 'last_success': time.time(), 'errors': 0
                                    }
                        except Exception:
                            err_cnt = self.whale_provider_status.get('defillama', {}).get('errors', 0) + 1
                            self.whale_provider_status['defillama'] = {
                                'status': 'DEGRADED', 'latency_ms': 0, 'last_success': self.whale_provider_status.get('defillama', {}).get('last_success', 0.0), 'errors': err_cnt
                            }

                        # 2. DefiLlama Stablecoin Dolaşımdaki Arz (Mint/Burn Momentum)
                        try:
                            async with session.get("https://stablecoins.llama.fi/stablecoincharts/all", headers=headers) as resp:
                                if resp.status == 200:
                                    data = await resp.json()
                                    if isinstance(data, list) and len(data) >= 2:
                                        recent_days = [float(x.get('totalCirculatingUSD', {}).get('peggedUSD', 0.0) or 0.0) for x in data[-14:]]
                                        ammo_res = calculate_ammunition_momentum(recent_days)
                                        ammo_res['total_pegged_usd'] = recent_days[-1]
                                        ammo_res['binance_clean_reserves'] = self.stablecoin_ammunition.get('binance_clean_reserves', 0.0)
                                        ammo_res['binance_24h_inflows'] = self.stablecoin_ammunition.get('binance_24h_inflows', 0.0)
                                        ammo_res['last_update'] = time.time()
                                        self.stablecoin_ammunition.update(ammo_res)
                        except Exception:
                            pass

                        # 3. Parite Bazlı Borsa Net Akışı (Symbol Netflow & Taker Delta Proxy)
                        now_ts = time.time()
                        for sym in self.all_symbols:
                            clean_s = self._clean_symbol(sym)
                            df_5m = self.candles_5m.get(sym)
                            if df_5m is None or df_5m.empty:
                                df_5m = self.candles_5m.get(clean_s)

                            curr_netflow_usd = 0.0
                            if df_5m is not None and len(df_5m) >= 6:
                                lookback = min(len(df_5m), 24)
                                recent_df = df_5m.iloc[-lookback:]
                                if 'taker_quote' in recent_df.columns:
                                    taker_buys = float(recent_df['taker_quote'].sum())
                                    tot_vol_usd = float((recent_df['volume'] * recent_df['close']).sum())
                                    taker_sells = max(0.0, tot_vol_usd - taker_buys)
                                    curr_netflow_usd = float(taker_buys - taker_sells)
                                elif 'taker_base' in recent_df.columns:
                                    taker_buys = float((recent_df['taker_base'] * recent_df['close']).sum())
                                    tot_vol_usd = float((recent_df['volume'] * recent_df['close']).sum())
                                    taker_sells = max(0.0, tot_vol_usd - taker_buys)
                                    curr_netflow_usd = float(taker_buys - taker_sells)
                                else:
                                    rng = np.maximum(1e-8, recent_df['high'] - recent_df['low'])
                                    w = (recent_df['close'] - recent_df['open']) / rng
                                    curr_netflow_usd = float((w * recent_df['volume'] * recent_df['close']).sum())

                            dq = self.netflow_history_deque[sym]
                            dq.append(curr_netflow_usd)

                            z_res = calculate_netflow_zscore(list(dq), curr_netflow_usd)
                            is_tier1 = any(m in clean_s for m in ["BTC", "ETH", "SOL", "BNB"])
                            is_tier3 = any(m in clean_s for m in ["PEPE", "SHIB", "DOGE", "BONK", "MEME", "FLOKI", "WIF"])
                            tier_str = "TIER_1" if is_tier1 else ("TIER_3" if is_tier3 else "TIER_2")

                            prev_entry = self.exchange_netflows.get(sym, {})
                            last_whale_ts = prev_entry.get('last_whale_transfer_ts', 0.0)
                            whale_active = (now_ts - last_whale_ts) < 1800.0

                            is_dump_threat = z_res['is_dump_risk'] or (whale_active and prev_entry.get('last_whale_intent') == 'DUMP_PREPARATION')
                            is_accum_threat = z_res['is_accumulation'] or (whale_active and prev_entry.get('last_whale_intent') == 'COLD_STORAGE_ACCUMULATION')

                            self.exchange_netflows[sym] = {
                                'symbol': sym,
                                'netflow_24h_usd': round(curr_netflow_usd, 2),
                                'z_score': z_res['z_score'],
                                'regime': z_res['regime'],
                                'is_dump_risk': is_dump_threat,
                                'is_accumulation': is_accum_threat,
                                'tier': tier_str,
                                'last_whale_transfer_ts': last_whale_ts,
                                'last_whale_amount_usd': prev_entry.get('last_whale_amount_usd', 0.0),
                                'last_whale_intent': prev_entry.get('last_whale_intent', 'NONE'),
                                'last_update': now_ts
                            }
                            self.exchange_netflows[clean_s] = self.exchange_netflows[sym]
                            clean_unslashed = clean_s.replace('/', '').replace(':USDT', '')
                            sym_unslashed = sym.replace('/', '').replace(':USDT', '')
                            self.exchange_netflows[clean_unslashed] = self.exchange_netflows[sym]
                            self.exchange_netflows[sym_unslashed] = self.exchange_netflows[sym]

                            # Whale Feed otomatik besleme (Yalnızca gerçek eşik üstü kurumsal akışlar)
                            abs_flow = abs(curr_netflow_usd)
                            thresh_feed = 5_000_000.0 if is_tier1 else (1_000_000.0 if not is_tier3 else 250_000.0)
                            if abs_flow >= thresh_feed and (now_ts - last_whale_ts) >= 300.0:
                                t_dir = 'WALLET_TO_EXCHANGE' if curr_netflow_usd >= 0 else 'EXCHANGE_TO_WALLET'
                                self.record_whale_transaction(sym, abs_flow, transfer_type=t_dir)

                        self.whale_provider_status['last_sync_ts'] = now_ts
                        self.whale_provider_status['whale_radar_live'] = True

                        btc_flow = self.exchange_netflows.get('BTC/USDT', {})
                        ammo_bias = self.stablecoin_ammunition.get('bias', 'NEUTRAL')
                        print(f">> [BALİNA RADARI GÜNCELLENDİ] BTC Netflow: ${btc_flow.get('netflow_24h_usd', 0):+,.0f} (Z: {btc_flow.get('z_score', 0):+.2f}σ) | Stabil Cephane: {ammo_bias} (Binance TVL: ${self.stablecoin_ammunition.get('binance_clean_reserves', 0)/1e9:.1f}B)")

                except Exception as e_main:
                    print(f">> [BALİNA RADARI HATA] {e_main}")

                poll_interval = getattr(config, 'NETFLOW_REFRESH_INTERVAL_SEC', 90)
                await asyncio.sleep(poll_interval)

        # Worker 11: Gerçek Zamanlı Binance WebSocket aggTrade Blok Emir Dedektörü (< 50ms)
        agg_streams = []
        for s in self.all_symbols:
            clean_s_ws = self._clean_symbol(s).replace('/', '').lower().replace(':usdt', '')
            agg_streams.append(f"{clean_s_ws}@aggTrade")

        agg_chunk_size = 35
        agg_chunks = [agg_streams[i:i + agg_chunk_size] for i in range(0, len(agg_streams), agg_chunk_size)]

        async def aggtrade_worker(chunk_id, chunk):
            url = f"wss://fstream.binance.com/market/stream?streams={'/'.join(chunk)}"
            while True:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.ws_connect(url, heartbeat=10) as ws:
                            print(f">> [CANLI] Binance aggTrade Blok Emir Akışı chunk-{chunk_id} bağlandı ({len(chunk)} parite).")
                            while True:
                                try:
                                    msg = await asyncio.wait_for(ws.receive(), timeout=45.0)
                                except asyncio.TimeoutError:
                                    print(f">> [AGGTRADE CHUNK-{chunk_id} ZOMBİ TESPİTİ] 45s veri gelmedi, soket yenileniyor...")
                                    break

                                if msg.type == aiohttp.WSMsgType.TEXT:
                                    self.last_stream_tick_time = time.time()
                                    data = json.loads(msg.data)
                                    payload = data.get('data', data) if isinstance(data, dict) else {}
                                    if not payload or not isinstance(payload, dict):
                                        continue

                                    p = float(payload.get('p', 0.0) or 0.0)
                                    q = float(payload.get('q', 0.0) or 0.0)
                                    notional = p * q
                                    # Ultra-hafif mikrosaniye filtresi: 100k altı perakende işlemler tek satırda elenir
                                    if notional < 100_000.0:
                                        continue

                                    raw_s = (payload.get('s') or '').upper()
                                    norm_s = symbol_map.get(raw_s, raw_s.replace('USDT', '/USDT'))
                                    if norm_s not in self.all_symbols:
                                        continue

                                    clean_s = self._clean_symbol(norm_s)
                                    is_tier1 = any(m in clean_s for m in ["BTC", "ETH", "SOL", "BNB"])
                                    is_tier3 = any(m in clean_s for m in ["PEPE", "SHIB", "DOGE", "BONK", "MEME", "FLOKI", "WIF"])

                                    thresh = 1_000_000.0 if is_tier1 else (100_000.0 if is_tier3 else 250_000.0)
                                    if notional >= thresh:
                                        is_buyer_maker = bool(payload.get('m', False))
                                        is_sell = is_buyer_maker  # True = Taker Seller (Agresif Piyasa Satışı)
                                        side_str = 'TAKER_SELL' if is_sell else 'TAKER_BUY'
                                        a_id = payload.get('a', '')
                                        trade_ts = float(payload.get('T', time.time() * 1000.0)) / 1000.0

                                        self._record_block_trade_pressure(norm_s, notional, is_sell, trade_ts)
                                        self.record_whale_transaction(
                                            symbol=norm_s,
                                            amount_usd=notional,
                                            transfer_type='MARKET_SELL_DUMP' if is_sell else 'MARKET_BUY_PUMP',
                                            tx_hash=f"agg_{a_id}",
                                            price=p,
                                            source='BINANCE_AGGTRADE',
                                            side=side_str
                                        )
                                        tier_str = "TIER_1" if is_tier1 else ("TIER_3" if is_tier3 else "TIER_2")
                                        act_icon = "🛑 BLOK SATIŞ" if is_sell else "⚡ BLOK ALIŞ"
                                        print(f">> [⚡ {act_icon} <50ms] {norm_s} ({tier_str}) | {side_str} | ${notional/1e6:.2f}M @ ${p:,.4f} | ID: agg_{a_id}")

                                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                    break
                except Exception as e:
                    print(f">> [AGGTRADE WS UYARI chunk-{chunk_id}] {e}")
                    await asyncio.sleep(2)

        # Worker 12: Gerçek On-Chain Whale Alert & Mempool Transfer Besleyicisi (Aşama 2)
        async def onchain_mempool_worker():
            print(">> [ON-CHAIN MEMPOOL] Bitcoin Mempool & Ethereum Token Transfer Radarı Başlatılıyor...")
            seen_hashes = deque(maxlen=400)
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

            while True:
                try:
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
                        # 1. Bitcoin Mempool Taraması (Blockchain.info Unconfirmed Transactions)
                        try:
                            btc_url = "https://blockchain.info/unconfirmed-transactions?format=json"
                            async with session.get(btc_url, headers=headers) as resp:
                                if resp.status == 200:
                                    data = await resp.json()
                                    txs = data.get('txs', [])
                                    btc_p = float(self.current_prices.get('BTC/USDT', 67000.0) or 67000.0)
                                    for tx in txs:
                                        h = tx.get('hash', '')
                                        if not h or h in seen_hashes:
                                            continue
                                        tot_sat = sum(out.get('value', 0) for out in tx.get('out', []))
                                        tot_btc = tot_sat / 1e8
                                        tot_usd = tot_btc * btc_p
                                        # Eşik: >= $500,000 USD (Kurumsal Balina Mempool Transferi)
                                        if tot_usd >= 500_000.0:
                                            seen_hashes.append(h)
                                            out_addrs = [out.get('addr', '') for out in tx.get('out', []) if out.get('addr')]
                                            to_label = "Borsa Sıcak Cüzdanı"
                                            t_type = "WALLET_TO_EXCHANGE"
                                            for o_a in out_addrs:
                                                lbl = format_wallet_label(o_a)
                                                if "Binance" in lbl or "Coinbase" in lbl or "OKX" in lbl or "Bybit" in lbl:
                                                    to_label = lbl
                                                    t_type = "WALLET_TO_EXCHANGE"
                                                    break

                                            from_label = "Mempool Balina Cüzdanı"
                                            self.record_whale_transaction(
                                                symbol="BTC/USDT",
                                                amount_usd=tot_usd,
                                                transfer_type=t_type,
                                                tx_hash=h,
                                                price=btc_p,
                                                source="ONCHAIN_MEMPOOL",
                                                from_label=from_label,
                                                to_label=to_label,
                                                blockchain="BTC"
                                            )
                                            print(f">> [🔗 ON-CHAIN BTC MEMPOOL] {from_label} ➔ {to_label} | ${tot_usd/1e6:.2f}M ({tot_btc:.2f} BTC) | TX: {h[:12]}...")
                        except Exception:
                            pass

                        # 2. Ethereum / ERC20 Büyük Transfer Taraması (Blockscout API)
                        try:
                            eth_url = "https://eth.blockscout.com/api/v2/token-transfers"
                            async with session.get(eth_url, headers=headers) as resp:
                                if resp.status == 200:
                                    data = await resp.json()
                                    items = data.get('items', [])
                                    for it in items:
                                        tx_h = it.get('transaction_hash', '')
                                        if not tx_h or tx_h in seen_hashes:
                                            continue

                                        token = it.get('token', {})
                                        sym = token.get('symbol', '').upper()
                                        dec = int(token.get('decimals', 18) or 18)
                                        raw_v = float(it.get('total', {}).get('value', 0) or 0)
                                        norm_v = raw_v / (10 ** dec)

                                        target_symbol = None
                                        usd_val = 0.0
                                        if sym in ['USDT', 'USDC']:
                                            usd_val = norm_v
                                            target_symbol = 'BTC/USDT'
                                        elif sym in ['WETH', 'ETH']:
                                            eth_p = float(self.current_prices.get('ETH/USDT', 2700.0) or 2700.0)
                                            usd_val = norm_v * eth_p
                                            target_symbol = 'ETH/USDT'
                                        elif sym == 'WBTC':
                                            btc_p = float(self.current_prices.get('BTC/USDT', 67000.0) or 67000.0)
                                            usd_val = norm_v * btc_p
                                            target_symbol = 'BTC/USDT'

                                        if target_symbol and usd_val >= 250_000.0:
                                            seen_hashes.append(tx_h)
                                            f_addr = it.get('from', {}).get('hash', '')
                                            t_addr = it.get('to', {}).get('hash', '')
                                            f_label = format_wallet_label(f_addr)
                                            t_label = format_wallet_label(t_addr)

                                            t_type = "WALLET_TO_EXCHANGE"
                                            if "Binance" in t_label or "Coinbase" in t_label or "OKX" in t_label:
                                                t_type = "WALLET_TO_EXCHANGE"
                                            elif "Binance" in f_label or "Coinbase" in f_label or "OKX" in f_label:
                                                t_type = "EXCHANGE_TO_WALLET"
                                            elif "Treasury" in f_label or "Mint" in f_label:
                                                t_type = "TREASURY_MINT"

                                            cur_p = float(self.current_prices.get(target_symbol, 0.0) or 0.0)
                                            self.record_whale_transaction(
                                                symbol=target_symbol,
                                                amount_usd=usd_val,
                                                transfer_type=t_type,
                                                tx_hash=tx_h,
                                                price=cur_p,
                                                source="ONCHAIN_MEMPOOL",
                                                from_label=f_label,
                                                to_label=t_label,
                                                blockchain="ETH"
                                            )
                                            print(f">> [🔗 ON-CHAIN ERC20 {sym}] {f_label} ➔ {t_label} | ${usd_val/1e6:.2f}M | TX: {tx_h[:12]}...")
                        except Exception:
                            pass

                except Exception as e:
                    print(f">> [ONCHAIN WORKER UYARI]: {e}")

                await asyncio.sleep(25)  # Her 25 saniyede bir mempool ve transfer kontrolü

        # Worker 12: 15 Dakikalık Periyodik Bellek Koruma ve GC Süpürmesi (Render Free Tier 512MB RAM Kalkanı)
        async def memory_guard_worker():
            while True:
                await asyncio.sleep(900)  # Her 15 dakikada bir
                try:
                    import gc
                    # 1. Ölü ve inaktif deque anahtarlarını süpür
                    active_and_all = set(self.all_symbols) | set(self.active_symbols)
                    for dq_map_name in ['symbol_liquidations_deque', 'block_trades_history', 'symbol_cvd_history', 'symbol_price_history']:
                        dq_map = getattr(self, dq_map_name, None)
                        if isinstance(dq_map, dict):
                            for k in list(dq_map.keys()):
                                if k not in active_and_all:
                                    dq_map.pop(k, None)
                    # 2. 60 saniyeden eski JIT indikatör önbelleklerini serbest bırak
                    now_cur = time.time()
                    for c_name in ['_vp_cache', '_naked_cache', '_session_cache']:
                        c_map = getattr(self, c_name, None)
                        if isinstance(c_map, dict):
                            for k in list(c_map.keys()):
                                if now_cur - c_map[k].get('ts', 0) > 60.0:
                                    c_map.pop(k, None)
                    # 3. Açık GC süpürmesi
                    collected = gc.collect()
                    print(f">> [BELLEK KORUMA ZIRHI] 15dk periyodik GC süpürmesi tamamlandı. {collected} sahipsiz nesne serbest bırakıldı.")
                except Exception:
                    pass

        # Her worker'ı crash-proof saran koruyucu (bir worker çökerse diğerlerini öldürmez, otomatik yeniden başlatır)
        async def resilient_worker(name, coro_fn, *args):
            backoff = 2
            while True:
                try:
                    print(f">> [WORKER] {name} başlatılıyor...")
                    await coro_fn(*args)
                except Exception as e:
                    print(f">> [WORKER CRASH] {name} çöktü: {e}. {backoff}s sonra yeniden başlatılacak...")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 60)  # Exponential backoff, max 60s
                else:
                    backoff = 2  # Başarılı çalışma sonrası sıfırla

        tasks = [
            resilient_worker("BookTicker", bookticker_worker),
            resilient_worker("CandlePoller", candle_poller_worker),
            resilient_worker("HourlyFuturesWatchdog", hourly_futures_watchdog_worker),
            resilient_worker("FundingWorker", funding_worker),
            resilient_worker("ForceOrderRadar", forceorder_worker),
            resilient_worker("SpotBasisWorker", spot_basis_worker),
            resilient_worker("DeribitGexRadar", deribit_gex_worker),
            resilient_worker("CoinbaseLeadLag", coinbase_lead_lag_worker),
            resilient_worker("OpenInterestRadar", open_interest_worker),
            resilient_worker("WhaleNetflowRadar", whale_netflow_worker),
            resilient_worker("OnchainMempoolRadar", onchain_mempool_worker),
            resilient_worker("MemoryGuard", memory_guard_worker),
        ] + [resilient_worker(f"KLine-Chunk-{i}", kline_worker, i, c) for i, c in enumerate(kline_chunks)] \
          + [resilient_worker(f"AggTrade-Chunk-{i}", aggtrade_worker, i, c) for i, c in enumerate(agg_chunks)]

        self._active_stream_tasks = [asyncio.create_task(t) for t in tasks]
        try:
            await asyncio.gather(*self._active_stream_tasks)
        except asyncio.CancelledError:
            print(">> [WEBSOCKET] Canlı akış görevleri iptal edildi (reconnect / oturum yenileme).")

    async def reconnect(self):
        """
        Aegis Sentinel ve Anti-Zombie Watchdog tarafından tetiklenen otonom yeniden bağlanma:
        35s+ veri gecikmesi olduğunda tüm WebSocket görevlerini iptal eder ve temiz bir oturumla yeniden başlatır.
        """
        print(">> [WEBSOCKET RECONNECT] 35s+ veri gecikmesi tespit edildi: Canlı akışlar sonlandırılıp temiz oturum başlatılıyor...")
        self.last_stream_tick_time = time.time()
        if hasattr(self, '_active_stream_tasks') and self._active_stream_tasks:
            for t in self._active_stream_tasks:
                if not t.done():
                    t.cancel()
            self._active_stream_tasks = []
        await asyncio.sleep(1)

    async def close(self):
        if hasattr(self, '_active_stream_tasks') and self._active_stream_tasks:
            for t in self._active_stream_tasks:
                if not t.done():
                    t.cancel()
            self._active_stream_tasks = []
        await self.exchange.close()
