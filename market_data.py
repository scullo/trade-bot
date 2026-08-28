import asyncio
import json
import time
import aiohttp
import ccxt.async_support as ccxt
import pandas as pd
from config import LOOKBACK_DAYS_AVWAP
from indicators import calculate_camarilla_pivots, calculate_anchored_vwap, calculate_volume_profile, get_tradingview_naked_lines

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
        self.current_prices = {s: 0.0 for s in all_symbols}
        self.on_tick_callback = None
        self.on_candle_close_callback = None

    async def initialize(self):
        print(">> Binance Vadeli (USDT-M Futures) verileri yukleniyor...")
        print(f"   Takip Edilen Toplam Parite: {len(self.all_symbols)}")
        tasks = [self.fetch_single_symbol(s) for s in self.all_symbols]
        await asyncio.gather(*tasks)
        print(f">> [TAMAMLANDI] {len(self.all_symbols)} paritenin gosterge ve pivot seviyeleri hesaplandi.")

    def _clean_symbol(self, symbol: str) -> str:
        """Binance USDT-M Futures icin sembol donusumu."""
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
            'CAT/USDT': '1000CAT/USDT',
            'NEIRO/USDT': '1000NEIRO/USDT'
        }
        return multiplier_coins.get(clean, clean)

    async def fetch_single_symbol(self, symbol: str):
        async with self.semaphore:
            clean_sym = self._clean_symbol(symbol)
            clean_raw = clean_sym.replace('/', '').replace(':USDT', '')
            raw_spot = symbol.replace('/', '').replace(':USDT', '')
            spot_clean = raw_spot.replace('1000000', '').replace('1000', '')

            mult = 1.0
            if '1000PEPE' in clean_raw or '1000BONK' in clean_raw or '1000SHIB' in clean_raw or '1000FLOKI' in clean_raw or '1000SATS' in clean_raw or '1000RATS' in clean_raw or '1000LUNC' in clean_raw or '1000XEC' in clean_raw or '1000CHEEMS' in clean_raw or '1000WHY' in clean_raw or '1000CAT' in clean_raw or '1000NEIRO' in clean_raw:
                mult = 1000.0
            elif '1000000MOG' in clean_raw:
                mult = 1000000.0

            df_1d = None
            df_5m = None
            applied_mult = 1.0

            async with aiohttp.ClientSession() as session:
                # 1. Binance Vision (Global unblocked for Spot/Major pairs)
                vision_urls = [
                    (f"https://data-api.binance.vision/api/v3/klines?symbol={raw_spot}", 1.0),
                    (f"https://data-api.binance.vision/api/v3/klines?symbol={spot_clean}", mult)
                ]
                for base_url, m_val in vision_urls:
                    try:
                        url_1d = f"{base_url}&interval=1d&limit=30"
                        url_5m = f"{base_url}&interval=5m&limit=500"
                        async with session.get(url_1d, timeout=aiohttp.ClientTimeout(total=3)) as r1:
                            if r1.status == 200:
                                d1 = await r1.json()
                                if isinstance(d1, list) and len(d1) > 0:
                                    df_1d = pd.DataFrame(d1, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base', 'taker_quote', 'ignore'])
                                    for col in ['timestamp', 'open', 'high', 'low', 'close', 'volume']:
                                        df_1d[col] = df_1d[col].astype(float)
                        
                        async with session.get(url_5m, timeout=aiohttp.ClientTimeout(total=3)) as r2:
                            if r2.status == 200:
                                d2 = await r2.json()
                                if isinstance(d2, list) and len(d2) > 0:
                                    df_5m = pd.DataFrame(d2, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base', 'taker_quote', 'ignore'])
                                    for col in ['timestamp', 'open', 'high', 'low', 'close', 'volume']:
                                        df_5m[col] = df_5m[col].astype(float)
                        
                        if df_1d is not None and df_5m is not None and not df_1d.empty and not df_5m.empty:
                            applied_mult = m_val
                            break
                    except Exception:
                        continue

                # 2. Bybit Linear Futures (Global unblocked for all futures-exclusive coins like APR, MAGMA, FARTCOIN, HYPE)
                if df_1d is None or df_5m is None or df_1d.empty or df_5m.empty:
                    try:
                        bybit_sym = clean_raw
                        url_1d_b = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={bybit_sym}&interval=D&limit=30"
                        url_5m_b = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={bybit_sym}&interval=5&limit=200"
                        
                        async with session.get(url_1d_b, timeout=aiohttp.ClientTimeout(total=3)) as r1:
                            if r1.status == 200:
                                res1 = await r1.json()
                                l1 = res1.get('result', {}).get('list', [])
                                if l1:
                                    rows_1d = [[float(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])] for x in reversed(l1)]
                                    df_1d = pd.DataFrame(rows_1d, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                        
                        async with session.get(url_5m_b, timeout=aiohttp.ClientTimeout(total=3)) as r2:
                            if r2.status == 200:
                                res2 = await r2.json()
                                l2 = res2.get('result', {}).get('list', [])
                                if l2:
                                    rows_5m = [[float(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])] for x in reversed(l2)]
                                    df_5m = pd.DataFrame(rows_5m, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    except Exception:
                        pass

                # 3. Direct Binance Futures fallback
                if df_1d is None or df_5m is None or df_1d.empty or df_5m.empty:
                    try:
                        url_1d = f"https://fapi.binance.com/fapi/v1/klines?symbol={clean_raw}&interval=1d&limit=30"
                        url_5m = f"https://fapi.binance.com/fapi/v1/klines?symbol={clean_raw}&interval=5m&limit=500"
                        async with session.get(url_1d, timeout=aiohttp.ClientTimeout(total=3)) as r1:
                            if r1.status == 200:
                                d1 = await r1.json()
                                if isinstance(d1, list) and len(d1) > 0:
                                    df_1d = pd.DataFrame(d1, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base', 'taker_quote', 'ignore'])
                                    for col in ['timestamp', 'open', 'high', 'low', 'close', 'volume']:
                                        df_1d[col] = df_1d[col].astype(float)
                        async with session.get(url_5m, timeout=aiohttp.ClientTimeout(total=3)) as r2:
                            if r2.status == 200:
                                d2 = await r2.json()
                                if isinstance(d2, list) and len(d2) > 0:
                                    df_5m = pd.DataFrame(d2, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base', 'taker_quote', 'ignore'])
                                    for col in ['timestamp', 'open', 'high', 'low', 'close', 'volume']:
                                        df_5m[col] = df_5m[col].astype(float)
                    except Exception:
                        pass

            if df_1d is not None and df_5m is not None and not df_1d.empty and not df_5m.empty:
                if applied_mult != 1.0:
                    for col in ['open', 'high', 'low', 'close']:
                        df_1d[col] = df_1d[col] * applied_mult
                        df_5m[col] = df_5m[col] * applied_mult
                self.candles_1d[symbol] = df_1d
                self.candles_5m[symbol] = df_5m
                self.current_prices[symbol] = float(df_5m['close'].iloc[-1])
                self.recalculate_levels(symbol)
                status = "AKTIF" if symbol in self.active_symbols else "HAZIR"
                print(f"   [{status}] {symbol} seviyeleri esitlendi. Fiyat: {self.current_prices[symbol]}")
            else:
                cur_p = self.current_prices.get(symbol, 0.0)
                if cur_p > 0:
                    import time as tm
                    h = cur_p * 1.03
                    l = cur_p * 0.97
                    c = cur_p
                    df_dummy = pd.DataFrame([{
                        'timestamp': tm.time() * 1000,
                        'open': cur_p * 0.99,
                        'high': h,
                        'low': l,
                        'close': c,
                        'volume': 1000.0
                    }])
                    self.candles_5m[symbol] = df_dummy
                    self.recalculate_levels(symbol)
                    status = "AKTIF" if symbol in self.active_symbols else "HAZIR"
                    print(f"   [{status}] {symbol} anlik fiyat ile esitlendi. Fiyat: {cur_p}")

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

    def _ensure_instant_levels(self, symbol: str, price: float):
        if price <= 0:
            return
        df_5m = self.candles_5m.get(symbol, pd.DataFrame())
        if df_5m.empty:
            import time as tm
            ts = tm.time() * 1000
            rows = []
            for i in range(50):
                drift = (i - 25) * 0.0003 * price
                rows.append({
                    'timestamp': ts - (50 - i) * 300000,
                    'open': price * 0.995 + drift,
                    'high': price * 1.015 + drift,
                    'low': price * 0.985 + drift,
                    'close': price + drift,
                    'volume': 1000.0
                })
            df_5m = pd.DataFrame(rows)
            self.candles_5m[symbol] = df_5m

        self.recalculate_levels(symbol)

    def recalculate_levels(self, symbol):
        df_1d = self.candles_1d.get(symbol, pd.DataFrame())
        df_5m = self.candles_5m.get(symbol, pd.DataFrame())
        if df_5m.empty:
            return

        # === CAMARILLA PIVOT ===
        if not df_1d.empty:
            prev_day = df_1d.iloc[-2] if len(df_1d) >= 2 else df_1d.iloc[-1]
            camarilla = calculate_camarilla_pivots(prev_day['high'], prev_day['low'], prev_day['close'])
        else:
            camarilla = calculate_camarilla_pivots(df_5m['high'].max(), df_5m['low'].min(), df_5m['close'].iloc[-1])

        # === ANCHORED VWAP ===
        if not df_1d.empty:
            lookback_count = min(LOOKBACK_DAYS_AVWAP, len(df_1d))
            lookback_days = df_1d.iloc[-lookback_count:]
            max_high_idx = lookback_days['high'].idxmax()
            min_low_idx = lookback_days['low'].idxmin()

            tepe_time = lookback_days.loc[max_high_idx, 'timestamp']
            dip_time = lookback_days.loc[min_low_idx, 'timestamp']

            earliest_5m_ts = df_5m['timestamp'].iloc[0]

            if tepe_time >= earliest_5m_ts:
                tepe_idx_5m = (df_5m['timestamp'] - tepe_time).abs().idxmin()
                tepe_avwap = float(calculate_anchored_vwap(df_5m, tepe_idx_5m))
            else:
                tepe_avwap = float(calculate_anchored_vwap(df_5m, 0))

            if dip_time >= earliest_5m_ts:
                dip_idx_5m = (df_5m['timestamp'] - dip_time).abs().idxmin()
                dip_avwap = float(calculate_anchored_vwap(df_5m, dip_idx_5m))
            else:
                dip_avwap = float(calculate_anchored_vwap(df_5m, 0))
        else:
            high_idx = df_5m['high'].idxmax()
            low_idx = df_5m['low'].idxmin()
            tepe_avwap = float(calculate_anchored_vwap(df_5m, high_idx))
            dip_avwap = float(calculate_anchored_vwap(df_5m, low_idx))

        # === VOLUME PROFILE ===
        vp_result = calculate_volume_profile(df_5m, num_rows=30, value_area_pct=0.68)

        # === NAKED LINES ===
        current_p = self.current_prices.get(symbol, float(df_5m['close'].iloc[-1]))
        naked_lines = get_tradingview_naked_lines(df_5m, current_p)

        self.levels[symbol] = {
            "camarilla": camarilla,
            "tepe_avwap": float(tepe_avwap),
            "dip_avwap": float(dip_avwap),
            "mpoc": float(vp_result.get("POC", 0.0)),
            "mvah": float(vp_result.get("VAH", 0.0)),
            "mval": float(vp_result.get("VAL", 0.0)),
            "above_npoc": float(naked_lines.get("above_npoc", 0.0)),
            "below_npoc": float(naked_lines.get("below_npoc", 0.0)),
            "above_nvah": float(naked_lines.get("above_nvah", 0.0)),
            "below_nvah": float(naked_lines.get("below_nvah", 0.0)),
            "above_nval": float(naked_lines.get("above_nval", 0.0)),
            "below_nval": float(naked_lines.get("below_nval", 0.0))
        }

    async def start_websocket(self):
        streams = []
        for s in self.all_symbols:
            clean_full = self._clean_symbol(s)
            clean_stream = clean_full.replace('/', '').lower().replace(':usdt', '')
            streams.append(f"{clean_stream}@bookTicker")
            streams.append(f"{clean_stream}@kline_5m")

        stream_url = f"wss://fstream.binance.com/stream?streams={'/'.join(streams)}"
        print(f">> Canli Binance Futures WebSocket baslatiliyor ({len(self.all_symbols)} Parite Stream)...")

        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(stream_url, heartbeat=10) as ws:
                        print(">> [CANLI] Binance Global WebSocket AKTIF - Fiyatlar anlik akiyor.")
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                data = json.loads(msg.data)
                                stream_name = data.get('stream', '').lower()
                                payload = data.get('data', {})

                                if '@bookticker' in stream_name:
                                    symbol_raw = payload.get('s', '').upper()
                                    for s in self.all_symbols:
                                        clean_match = self._clean_symbol(s).replace('/', '').replace(':USDT', '').upper()
                                        if clean_match == symbol_raw or s.replace('/', '').replace(':USDT', '').upper() == symbol_raw:
                                            bid = float(payload.get('b', 0.0))
                                            ask = float(payload.get('a', 0.0))
                                            price = (bid + ask) / 2.0 if (bid and ask) else (bid or ask)
                                            if price > 0:
                                                self.current_prices[s] = price
                                                if self.on_tick_callback:
                                                    await self.on_tick_callback(s, price)

                                elif '@kline' in stream_name:
                                    kline = payload.get('k', {})
                                    if kline.get('x', False):
                                        symbol_raw = payload.get('s', '').upper()
                                        for s in self.all_symbols:
                                            clean_match = self._clean_symbol(s).replace('/', '').replace(':USDT', '').upper()
                                            if clean_match == symbol_raw or s.replace('/', '').replace(':USDT', '').upper() == symbol_raw:
                                                new_candle = {
                                                    'timestamp': kline.get('t'),
                                                    'open': float(kline.get('o')),
                                                    'high': float(kline.get('h')),
                                                    'low': float(kline.get('l')),
                                                    'close': float(kline.get('c')),
                                                    'volume': float(kline.get('v'))
                                                }
                                                prev_candle = self.candles_5m[s].iloc[-1].to_dict() if not self.candles_5m[s].empty else new_candle
                                                self.candles_5m[s] = pd.concat([self.candles_5m[s], pd.DataFrame([new_candle])], ignore_index=True)
                                                self.recalculate_levels(s)
                                                if self.on_candle_close_callback and s in self.active_symbols:
                                                    await self.on_candle_close_callback(s, new_candle, prev_candle)
                            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                break
            except Exception as e:
                print(f">> [UYARI] WebSocket baglantisi yenileniyor: {e}")
                await asyncio.sleep(2)

    async def close(self):
        await self.exchange.close()
