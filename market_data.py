import asyncio
import json
import time
from datetime import datetime
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
            'CAT/USDT': '1000CAT/USDT',
            'NEIRO/USDT': '1000NEIRO/USDT'
        }
        return multiplier_coins.get(clean, clean)

    def _get_spot_multiplier(self, symbol: str) -> float:
        clean = symbol.replace('/', '').replace(':USDT', '')
        multiplier_coins = ['1000PEPE', '1000BONK', '1000SHIB', '1000FLOKI', '1000SATS', '1000RATS', '1000LUNC', '1000XEC', '1000CHEEMS', '1000WHY', '1000CAT', '1000NEIRO', 'PEPE', 'BONK', 'SHIB', 'FLOKI', 'SATS', 'RATS', 'LUNC', 'XEC', 'CHEEMS', 'WHY', 'CAT', 'NEIRO']
        if any(k in clean for k in multiplier_coins):
            return 1000.0
        elif 'MOG' in clean:
            return 1000000.0
        return 1.0

    async def initialize(self):
        print(">> Binance Vadeli (USDT-M Futures) verileri yukleniyor...")
        print(f"   Takip Edilen Toplam Parite: {len(self.all_symbols)}")
        tasks = [self.fetch_single_symbol(s) for s in self.all_symbols]
        await asyncio.gather(*tasks)
        print(f">> [TAMAMLANDI] {len(self.all_symbols)} paritenin gosterge ve pivot seviyeleri hesaplandi.")

    async def fetch_single_symbol(self, symbol: str):
        async with self.semaphore:
            clean_sym = self._clean_symbol(symbol)
            clean_raw = clean_sym.replace('/', '').replace(':USDT', '')
            fapi_sym = clean_raw if clean_raw.endswith('USDT') else f"{clean_raw}USDT"
            raw_spot = symbol.replace('/', '').replace(':USDT', '')
            spot_clean = raw_spot.replace('1000000', '').replace('1000', '')
            spot_mult = self._get_spot_multiplier(symbol)
            now_ms = time.time() * 1000

            df_1d = None
            df_5m = None

            async with aiohttp.ClientSession() as session:
                # 1. Binance Vision (Spot with freshness check < 15 mins and correct multiplier)
                for base_sym in [spot_clean, raw_spot]:
                    try:
                        url_1d_v = f"https://data-api.binance.vision/api/v3/klines?symbol={base_sym}&interval=1d&limit=30"
                        url_5m_v = f"https://data-api.binance.vision/api/v3/klines?symbol={base_sym}&interval=5m&limit=200"
                        t_1d, t_5m = None, None
                        async with session.get(url_1d_v, timeout=aiohttp.ClientTimeout(total=2)) as r1:
                            if r1.status == 200:
                                d1 = await r1.json()
                                if isinstance(d1, list) and len(d1) > 0:
                                    t_1d = pd.DataFrame(d1, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base', 'taker_quote', 'ignore'])
                                    for col in ['open', 'high', 'low', 'close']:
                                        t_1d[col] = t_1d[col].astype(float) * spot_mult
                                    for col in ['timestamp', 'volume']:
                                        t_1d[col] = t_1d[col].astype(float)
                        
                        async with session.get(url_5m_v, timeout=aiohttp.ClientTimeout(total=2)) as r2:
                            if r2.status == 200:
                                d2 = await r2.json()
                                if isinstance(d2, list) and len(d2) > 0:
                                    t_5m = pd.DataFrame(d2, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base', 'taker_quote', 'ignore'])
                                    for col in ['open', 'high', 'low', 'close']:
                                        t_5m[col] = t_5m[col].astype(float) * spot_mult
                                    for col in ['timestamp', 'volume']:
                                        t_5m[col] = t_5m[col].astype(float)
                        
                        if t_5m is not None and not t_5m.empty:
                            if (now_ms - float(t_5m['timestamp'].iloc[-1])) <= (15 * 60 * 1000): # Fresh!
                                df_1d, df_5m = t_1d, t_5m
                                break
                    except Exception:
                        pass

                # 2. Gate.io Futures (100% unblocked, fresh 24/7 Futures for XMR, LIT, HYPE, etc.)
                if df_1d is None or df_5m is None or df_1d.empty or df_5m.empty:
                    for gate_sym in [clean_raw, spot_clean, raw_spot]:
                        try:
                            url_1d_g = f"https://api.gateio.ws/api/v4/futures/usdt/candlesticks?contract={gate_sym}_USDT&interval=1d&limit=30"
                            url_5m_g = f"https://api.gateio.ws/api/v4/futures/usdt/candlesticks?contract={gate_sym}_USDT&interval=5m&limit=200"
                            t_1d, t_5m = None, None
                            async with session.get(url_1d_g, timeout=aiohttp.ClientTimeout(total=3)) as r1:
                                if r1.status == 200:
                                    d1 = await r1.json()
                                    if isinstance(d1, list) and len(d1) > 0:
                                        rows_1d = [[float(x['t'])*1000, float(x['o']), float(x['h']), float(x['l']), float(x['c']), float(x['v'])] for x in d1]
                                        t_1d = pd.DataFrame(rows_1d, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                            
                            async with session.get(url_5m_g, timeout=aiohttp.ClientTimeout(total=3)) as r2:
                                if r2.status == 200:
                                    d2 = await r2.json()
                                    if isinstance(d2, list) and len(d2) > 0:
                                        rows_5m = [[float(x['t'])*1000, float(x['o']), float(x['h']), float(x['l']), float(x['c']), float(x['v'])] for x in d2]
                                        t_5m = pd.DataFrame(rows_5m, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                            
                            if t_5m is not None and not t_5m.empty:
                                df_1d, df_5m = t_1d, t_5m
                                break
                        except Exception:
                            pass

                # 3. Bybit Linear (Backup Futures)
                if df_1d is None or df_5m is None or df_1d.empty or df_5m.empty:
                    try:
                        url_1d_b = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={fapi_sym}&interval=D&limit=30"
                        url_5m_b = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={fapi_sym}&interval=5&limit=200"
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

            if df_1d is not None and not df_1d.empty and (df_5m is None or df_5m.empty):
                df_5m = df_1d.copy()
            if df_5m is not None and not df_5m.empty and (df_1d is None or df_1d.empty):
                df_1d = df_5m.copy()

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
            "mpoc": float(vp_result.get("POC", current_p)),
            "mvah": float(vp_result.get("VAH", current_p * 1.01)),
            "mval": float(vp_result.get("VAL", current_p * 0.99)),
            "above_npoc": float(naked_lines.get("above_npoc", current_p * 1.015)),
            "below_npoc": float(naked_lines.get("below_npoc", current_p * 0.985)),
            "above_nvah": float(naked_lines.get("above_nvah", current_p * 1.02)),
            "below_nvah": float(naked_lines.get("below_nvah", current_p * 0.98)),
            "above_nval": float(naked_lines.get("above_nval", current_p * 1.025)),
            "below_nval": float(naked_lines.get("below_nval", current_p * 0.975))
        }

    async def poll_all_candles_once(self):
        """100 Paritenin son kapanmis 5M mumlarini aninda REST uzerinden paralel tara ve stratejiye ilet."""
        sem = asyncio.Semaphore(25)
        now_ms = time.time() * 1000
        async with aiohttp.ClientSession() as session:
            async def fetch_and_eval(s):
                async with sem:
                    try:
                        clean_sym = self._clean_symbol(s)
                        clean_raw = clean_sym.replace('/', '').replace(':USDT', '')
                        fapi_sym = clean_raw if clean_raw.endswith('USDT') else f"{clean_raw}USDT"
                        raw_s = s.replace('/', '').replace(':USDT', '')
                        spot_mult = self._get_spot_multiplier(s)
                        
                        cur_candle = None
                        prev_candle = None

                        # 1. Binance Vision
                        for sym_attempt in [raw_s.replace('1000000', '').replace('1000', ''), raw_s]:
                            try:
                                url_v = f"https://data-api.binance.vision/api/v3/klines?symbol={sym_attempt}&interval=5m&limit=4"
                                async with session.get(url_v, timeout=aiohttp.ClientTimeout(total=2)) as res:
                                    if res.status == 200:
                                        kl = await res.json()
                                        if isinstance(kl, list) and len(kl) >= 2:
                                            closed_k = kl[-2]
                                            if (now_ms - float(closed_k[0])) <= (15 * 60 * 1000): # Fresh!
                                                prev_k = kl[-3] if len(kl) >= 3 else closed_k
                                                cur_candle = {
                                                    'timestamp': closed_k[0],
                                                    'open': float(closed_k[1]) * spot_mult,
                                                    'high': float(closed_k[2]) * spot_mult,
                                                    'low': float(closed_k[3]) * spot_mult,
                                                    'close': float(closed_k[4]) * spot_mult,
                                                    'volume': float(closed_k[5])
                                                }
                                                prev_candle = {
                                                    'timestamp': prev_k[0],
                                                    'open': float(prev_k[1]) * spot_mult,
                                                    'high': float(prev_k[2]) * spot_mult,
                                                    'low': float(prev_k[3]) * spot_mult,
                                                    'close': float(prev_k[4]) * spot_mult,
                                                    'volume': float(prev_k[5])
                                                }
                                                break
                            except Exception:
                                pass

                        # 2. Gate.io Futures Fallback
                        if cur_candle is None:
                            try:
                                url_g = f"https://api.gateio.ws/api/v4/futures/usdt/candlesticks?contract={clean_raw}_USDT&interval=5m&limit=4"
                                async with session.get(url_g, timeout=aiohttp.ClientTimeout(total=3)) as res:
                                    if res.status == 200:
                                        d_g = await res.json()
                                        if isinstance(d_g, list) and len(d_g) >= 2:
                                            closed_k = d_g[-2]
                                            prev_k = d_g[-3] if len(d_g) >= 3 else closed_k
                                            cur_candle = {
                                                'timestamp': float(closed_k['t']) * 1000,
                                                'open': float(closed_k['o']),
                                                'high': float(closed_k['h']),
                                                'low': float(closed_k['l']),
                                                'close': float(closed_k['c']),
                                                'volume': float(closed_k['v'])
                                            }
                                            prev_candle = {
                                                'timestamp': float(prev_k['t']) * 1000,
                                                'open': float(prev_k['o']),
                                                'high': float(prev_k['h']),
                                                'low': float(prev_k['l']),
                                                'close': float(prev_k['c']),
                                                'volume': float(prev_k['v'])
                                            }
                            except Exception:
                                pass

                        if cur_candle is not None and prev_candle is not None:
                            self.current_prices[s] = cur_candle['close']
                            if s in self.candles_5m and not self.candles_5m[s].empty:
                                last_ts = self.candles_5m[s]['timestamp'].iloc[-1]
                                if cur_candle['timestamp'] > last_ts:
                                    self.candles_5m[s] = pd.concat([self.candles_5m[s], pd.DataFrame([cur_candle])], ignore_index=True)
                                    self.recalculate_levels(s)
                            if self.on_candle_close_callback and s in self.active_symbols:
                                await self.on_candle_close_callback(s, cur_candle, prev_candle)
                    except Exception as e:
                        print(f">> [TARAMA HATA] {s}: {e}")

            await asyncio.gather(*(fetch_and_eval(s) for s in list(self.active_symbols)))

    async def start_websocket(self):
        symbol_map = {}
        for s in self.all_symbols:
            clean = self._clean_symbol(s).replace('/', '').replace(':USDT', '').upper()
            symbol_map[clean] = s
            if clean.startswith('SHIB'): symbol_map['1000SHIBUSDT'] = s
            if clean.startswith('PEPE'): symbol_map['1000PEPEUSDT'] = s
            if clean.startswith('BONK'): symbol_map['1000BONKUSDT'] = s
            if clean.startswith('FLOKI'): symbol_map['1000FLOKIUSDT'] = s

        print(f">> [WEBSOCKET] Ultra Hizli Hibrit Akis Baslatiliyor ({len(self.all_symbols)} Parite)...")

        # Worker 1: Global !bookTicker yayini (Tum coinler tek yuksek hizli sokette anlik akar)
        async def bookticker_worker():
            url = "wss://fstream.binance.com/ws/!bookTicker"
            while True:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.ws_connect(url, heartbeat=10) as ws:
                            print(">> [CANLI] Global !bookTicker Fiyat Akisi AKTIF.")
                            async for msg in ws:
                                if msg.type == aiohttp.WSMsgType.TEXT:
                                    data = json.loads(msg.data)
                                    raw_s = data.get('s', '').upper()
                                    if raw_s in symbol_map:
                                        norm_s = symbol_map[raw_s]
                                        bid = float(data.get('b', 0.0))
                                        ask = float(data.get('a', 0.0))
                                        price = (bid + ask) / 2.0 if (bid and ask) else (bid or ask)
                                        if price > 0:
                                            self.current_prices[norm_s] = price
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

        async def kline_worker(chunk):
            url = f"wss://fstream.binance.com/stream?streams={'/'.join(chunk)}"
            while True:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.ws_connect(url, heartbeat=10) as ws:
                            async for msg in ws:
                                if msg.type == aiohttp.WSMsgType.TEXT:
                                    data = json.loads(msg.data)
                                    payload = data.get('data', {})
                                    kline = payload.get('k', {})
                                    if kline.get('x', False):
                                        raw_s = payload.get('s', '').upper()
                                        if raw_s in symbol_map:
                                            norm_s = symbol_map[raw_s]
                                            new_candle = {
                                                'timestamp': kline.get('t'),
                                                'open': float(kline.get('o')),
                                                'high': float(kline.get('h')),
                                                'low': float(kline.get('l')),
                                                'close': float(kline.get('c')),
                                                'volume': float(kline.get('v'))
                                            }
                                            prev_candle = self.candles_5m[norm_s].iloc[-1].to_dict() if not self.candles_5m[norm_s].empty else new_candle
                                            self.candles_5m[norm_s] = pd.concat([self.candles_5m[norm_s], pd.DataFrame([new_candle])], ignore_index=True)
                                            self.recalculate_levels(norm_s)
                                            if self.on_candle_close_callback and norm_s in self.active_symbols:
                                                await self.on_candle_close_callback(norm_s, new_candle, prev_candle)
                                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                    break
                except Exception:
                    await asyncio.sleep(2)

        # Worker 3: 5M Periyodik REST Mum Senkronizasyonu (Ultra Hizli Paralel 100 Parite Taramasi)
        async def candle_poller_worker():
            last_scanned_slot = -1
            # Sunucu baslar baslamaz aninda ilk taramayi yap
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

        tasks = [bookticker_worker(), candle_poller_worker()] + [kline_worker(c) for c in kline_chunks]
        await asyncio.gather(*tasks)

    async def close(self):
        await self.exchange.close()
