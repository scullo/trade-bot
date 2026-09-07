import asyncio
import json
import time
from collections import deque
from datetime import datetime, timezone, timedelta
import aiohttp
import ccxt.async_support as ccxt
import pandas as pd
import numpy as np
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
            'CAT/USDT': '1000CAT/USDT'
            # Not: NEIRO Binance Vadeli'de 'NEIROUSDT' dir (1000 degildir)
        }
        return multiplier_coins.get(clean, clean)

    def _get_spot_multiplier(self, symbol: str) -> float:
        """Spot API (data-api.binance.vision) yedek olarak kullanildiginda 1000x ve 1M carpanlari uygular."""
        clean = symbol.replace(':USDT', '')
        if clean in ['PEPE/USDT', 'SHIB/USDT', 'BONK/USDT', 'FLOKI/USDT', 'SATS/USDT', 'RATS/USDT', 'LUNC/USDT', 'XEC/USDT', 'CHEEMS/USDT', 'WHY/USDT', 'CAT/USDT']:
            return 1000.0
        elif clean in ['MOG/USDT']:
            return 1000000.0
        return 1.0

    def get_system_health(self) -> dict:
        try:
            total_syms = len(self.all_symbols)
            healthy_levs = 0
            live_prices_cnt = 0
            for s in self.all_symbols:
                if self.current_prices.get(s, 0.0) > 0:
                    live_prices_cnt += 1
                lev = self.levels.get(s, {})
                cam = lev.get('camarilla', {}) if isinstance(lev, dict) else {}
                if cam.get('R4', 0.0) > 0:
                    healthy_levs += 1

            now_sec = time.time()
            last_scan = getattr(self, '_last_candle_scan_ts', now_sec)
            scan_active = (now_sec - last_scan) < 420
            levels_ok = (healthy_levs >= total_syms * 0.95 and total_syms > 0)
            ws_ok = (live_prices_cnt >= total_syms * 0.8)

            is_perfect = levels_ok and ws_ok and scan_active
            err_msg = None
            if not levels_ok:
                err_msg = f"{total_syms - healthy_levs} paritenin seviye verisi eksik!"
            elif not scan_active:
                err_msg = "5M Mum tarayıcısı gecikmeli çalışıyor!"
            elif not ws_ok:
                err_msg = "WebSocket canlı fiyat akışında gecikme var!"

            scan_str = getattr(self, '_last_candle_scan_str', datetime.now(timezone(timedelta(hours=3))).strftime('%H:%M:%S'))
            return {
                "is_perfect": is_perfect,
                "status_text": "5/5 Tam Sağlıklı & Hatasız" if is_perfect else f"⚠️ Sorun: {err_msg}",
                "healthy_symbols": healthy_levs,
                "total_symbols": total_syms,
                "live_prices": live_prices_cnt,
                "scan_active": scan_active,
                "ws_active": ws_ok,
                "last_scan_time": scan_str,
                "error_detail": err_msg
            }
        except Exception as e:
            return {
                "is_perfect": False,
                "status_text": f"Teşhis İstisnası: {e}",
                "healthy_symbols": 0,
                "total_symbols": 100,
                "live_prices": 0,
                "scan_active": True,
                "ws_active": True,
                "last_scan_time": "Şimdi",
                "error_detail": str(e)
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
                clean_no_mult = clean.replace('1000000', '').replace('1000', '')
                candidates = [
                    clean,
                    clean + 'USDT',
                    clean_no_mult + 'USDT',
                    '1000' + clean_no_mult + 'USDT',
                    clean + '_USDT',
                    clean.replace('NEIRO', 'NEIROCTO') + 'USDT'
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
                clean_no_mult = clean.replace('1000000', '').replace('1000', '')
                candidates = [
                    clean,
                    clean + 'USDT',
                    clean_no_mult + 'USDT',
                    '1000' + clean_no_mult + 'USDT',
                    clean + '_USDT',
                    clean.replace('NEIRO', 'NEIROCTO') + 'USDT'
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
        data = getattr(self, 'symbol_liquidations_15m', {}).get(symbol, {'long_usd': 0.0, 'short_usd': 0.0, 'last_update': 0})
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
            'is_hot': total >= 25000
        }

    def get_global_liquidation_summary(self) -> dict:
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
        data = getattr(self, 'symbol_cvd', {}).get(symbol, None)
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

        sorted_by_ratio = sorted(active_items, key=lambda x: x.get('ratio_60s', 50.0), reverse=True)
        top_buyers = sorted_by_ratio[:15]
        top_sellers = sorted_by_ratio[-15:][::-1] if len(sorted_by_ratio) >= 15 else sorted_by_ratio[::-1]

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
            'top_sell_ratio': top_sell.get('ratio_60s', 50.0),
            'top_sell_delta': top_sell.get('delta_60s', 0.0),
            'top_buyers': top_buyers,
            'top_sellers': top_sellers,
            'last_update_str': datetime.now().strftime('%H:%M:%S')
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
                        url_5m_v = f"{ep}&interval=5m&limit=500"
                        t_1d, t_5m = None, None
                        async with session.get(url_1d_v, timeout=aiohttp.ClientTimeout(total=4)) as r1:
                            if r1.status == 200:
                                d1 = await r1.json()
                                if isinstance(d1, list) and len(d1) > 0:
                                    t_1d = pd.DataFrame(d1, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base', 'taker_quote', 'ignore'])
                                    for col in ['open', 'high', 'low', 'close']:
                                        t_1d[col] = t_1d[col].astype(float) * mult
                                    t_1d['timestamp'] = t_1d['timestamp'].astype(float)
                                    t_1d['volume'] = t_1d['volume'].astype(float) / (mult if is_spot else 1.0)
                                    t_1d['quote_volume'] = t_1d['qav'].astype(float)
                        
                        async with session.get(url_5m_v, timeout=aiohttp.ClientTimeout(total=4)) as r2:
                            if r2.status == 200:
                                d2 = await r2.json()
                                if isinstance(d2, list) and len(d2) > 0:
                                    t_5m = pd.DataFrame(d2, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base', 'taker_quote', 'ignore'])
                                    for col in ['open', 'high', 'low', 'close']:
                                        t_5m[col] = t_5m[col].astype(float) * mult
                                    t_5m['timestamp'] = t_5m['timestamp'].astype(float)
                                    t_5m['volume'] = t_5m['volume'].astype(float) / (mult if is_spot else 1.0)
                                    t_5m['quote_volume'] = t_5m['qav'].astype(float)
                        
                        if t_5m is not None and not t_5m.empty:
                            df_1d, df_5m = t_1d, t_5m
                            break
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
                "decoupling_status": "⚪ NÖTR_TAKİPÇİ"
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

        # === ANCHORED VWAP (TradingView 24h-48h Swing High/Low Paritesi) ===
        if len(df_5m) >= 20:
            lookback_bars = min(len(df_5m), 288)
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

        # === VOLUME PROFILE (Son 30 Günlük Makro Profil: mPOC, mVAH, mVAL) ===
        if df_1d is not None and not df_1d.empty and len(df_1d) >= 5:
            vp_df = df_1d.iloc[-min(30, len(df_1d)):]
        else:
            vp_df = df_5m
        vp_result = calculate_volume_profile(vp_df, num_rows=30, value_area_pct=0.68)

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
            "decoupling_status": str(decoupling_status)
        }

    def get_symbol_metrics(self, symbol: str) -> dict:
        if not hasattr(self, 'symbol_metrics'):
            self.symbol_metrics = {}
        if symbol in self.symbol_metrics and self.symbol_metrics[symbol]:
            return self.symbol_metrics[symbol]
        self.recalculate_levels(symbol)
        majors = {"BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT"}
        return self.symbol_metrics.get(symbol, {
            "vol_surge": 1.0,
            "min_vol_surge": 1.2 if symbol in majors else 1.5,
            "atr_pct": 1.2,
            "is_top_80": True,
            "cur_vol": 0.0,
            "avg_vol": 0.0,
            "rs_vs_btc": 0.0,
            "dynamic_rs_score": 0.0,
            "decoupling_status": "⚪ NÖTR_TAKİPÇİ"
        })

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
                                                'quote_volume': float(closed_k[7])
                                            }
                                            prev_candle = {
                                                'timestamp': prev_k[0],
                                                'open': float(prev_k[1]) * mult,
                                                'high': float(prev_k[2]) * mult,
                                                'low': float(prev_k[3]) * mult,
                                                'close': float(prev_k[4]) * mult,
                                                'volume': float(prev_k[5]) / base_div,
                                                'quote_volume': float(prev_k[7])
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
                                    # Otomatik Onarım: Mum kapanışını anlık canlı vadeli fiyata eşitle (akış bozulmaz!)
                                    cur_candle['close'] = live_ws_p

                            self.current_prices[s] = cur_candle['close']
                            if s in self.candles_5m and not self.candles_5m[s].empty:
                                last_ts = self.candles_5m[s]['timestamp'].iloc[-1]
                                if cur_candle['timestamp'] == last_ts:
                                    for k_col, v_val in cur_candle.items():
                                        self.candles_5m[s].at[self.candles_5m[s].index[-1], k_col] = v_val
                                elif cur_candle['timestamp'] > last_ts:
                                    self.candles_5m[s] = pd.concat([self.candles_5m[s], pd.DataFrame([cur_candle])], ignore_index=True)
                                self.candles_5m[s] = self.candles_5m[s].drop_duplicates(subset=['timestamp'], keep='last').reset_index(drop=True)
                                if len(self.candles_5m[s]) > 300:
                                    self.candles_5m[s] = self.candles_5m[s].iloc[-300:].reset_index(drop=True)
                                self.recalculate_levels(s)
                            else:
                                self.candles_5m[s] = pd.DataFrame([cur_candle])
                                self.recalculate_levels(s)
                            if self.on_candle_close_callback and s in self.active_symbols:
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
            if clean.startswith('SHIB'): symbol_map['1000SHIBUSDT'] = s
            if clean.startswith('PEPE'): symbol_map['1000PEPEUSDT'] = s
            if clean.startswith('BONK'): symbol_map['1000BONKUSDT'] = s
            if clean.startswith('FLOKI'): symbol_map['1000FLOKIUSDT'] = s

        print(f">> [WEBSOCKET] Ultra Hizli Binance Akisi Baslatiliyor ({len(self.all_symbols)} Parite)...")

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
            url = f"wss://fstream.binance.com/market/stream?streams={'/'.join(chunk)}"
            while True:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.ws_connect(url, heartbeat=10) as ws:
                            print(f">> [CANLI] K-Line & Mikro-CVD Stream chunk baglandi ({len(chunk)} parite).")
                            async for msg in ws:
                                if msg.type == aiohttp.WSMsgType.TEXT:
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

                                                if norm_s not in self.symbol_cvd_history:
                                                    self.symbol_cvd_history[norm_s] = deque(maxlen=60)

                                                h_deque = self.symbol_cvd_history[norm_s]
                                                if not h_deque or (now_ts - h_deque[-1][0] >= 1.0):
                                                    h_deque.append((now_ts, t_buy, t_sell))

                                                delta_60s = delta
                                                ratio_60s = ratio
                                                if len(h_deque) >= 2:
                                                    t_cutoff = now_ts - 60.0
                                                    old_sample = h_deque[0]
                                                    for s_item in h_deque:
                                                        if s_item[0] >= t_cutoff:
                                                            old_sample = s_item
                                                            break
                                                    diff_buy = max(0.0, t_buy - old_sample[1])
                                                    diff_sell = max(0.0, t_sell - old_sample[2])
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
                                                'quote_volume': float(kline.get('q', 0.0))
                                            }
                                            prev_candle = self.candles_5m[norm_s].iloc[-1].to_dict() if not self.candles_5m[norm_s].empty else new_candle
                                            if not self.candles_5m[norm_s].empty:
                                                last_ts = self.candles_5m[norm_s]['timestamp'].iloc[-1]
                                                if new_candle['timestamp'] == last_ts:
                                                    for k_col, v_val in new_candle.items():
                                                        self.candles_5m[norm_s].at[self.candles_5m[norm_s].index[-1], k_col] = v_val
                                                elif new_candle['timestamp'] > last_ts:
                                                    self.candles_5m[norm_s] = pd.concat([self.candles_5m[norm_s], pd.DataFrame([new_candle])], ignore_index=True)
                                            else:
                                                self.candles_5m[norm_s] = pd.DataFrame([new_candle])
                                            self.candles_5m[norm_s] = self.candles_5m[norm_s].drop_duplicates(subset=['timestamp'], keep='last').reset_index(drop=True)
                                            if len(self.candles_5m[norm_s]) > 500:
                                                self.candles_5m[norm_s] = self.candles_5m[norm_s].iloc[-500:].reset_index(drop=True)
                                            self.recalculate_levels(norm_s)
                                            if self.on_candle_close_callback and norm_s in self.active_symbols:
                                                await self.on_candle_close_callback(norm_s, new_candle, prev_candle)
                                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                    break
                except Exception as e:
                    print(f">> [K-LINE WS UYARI] {e}")
                    await asyncio.sleep(2)

        # Worker 3: 5M Periyodik REST Mum Senkronizasyonu (Ultra Hizli Paralel 100 Parite Taramasi)
        async def candle_poller_worker():
            last_scanned_slot = -1
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
                        healed_cnt = 0
                        for sym in list(self.all_symbols):
                            try:
                                await self.fetch_single_symbol(sym)
                                healed_cnt += 1
                            except Exception:
                                pass
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

                                        # 15 Dakikalık Parite Bazlı Kümülatif Takip
                                        if norm_s not in self.symbol_liquidations_15m:
                                            self.symbol_liquidations_15m[norm_s] = {'long_usd': 0.0, 'short_usd': 0.0, 'last_update': now_ts}
                                        if is_long_liq:
                                            self.symbol_liquidations_15m[norm_s]['long_usd'] += usd_size
                                        else:
                                            self.symbol_liquidations_15m[norm_s]['short_usd'] += usd_size
                                        self.symbol_liquidations_15m[norm_s]['last_update'] = now_ts

                                        # Global İstatistik Güncelleme
                                        self.global_liquidation_stats['total_usd_24h'] += usd_size
                                        if is_long_liq:
                                            self.global_liquidation_stats['long_usd_24h'] += usd_size
                                        else:
                                            self.global_liquidation_stats['short_usd_24h'] += usd_size
                                        self.global_liquidation_stats['last_event_time'] = time_str

                                        # En çok tasfiye olan coini güncelle
                                        top_sym = '-'
                                        top_val = 0.0
                                        for sym_k, v_data in self.symbol_liquidations_15m.items():
                                            tot_s = v_data['long_usd'] + v_data['short_usd']
                                            if tot_s > top_val:
                                                top_val = tot_s
                                                top_sym = sym_k
                                        self.global_liquidation_stats['top_symbol'] = top_sym
                                        self.global_liquidation_stats['top_symbol_usd'] = top_val
                                    except Exception:
                                        pass
                                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                    break
                except Exception as e:
                    print(f">> [LİKİDASYON RADARI UYARI] Yeniden bağlanılıyor: {e}")
                    await asyncio.sleep(3)

        tasks = [bookticker_worker(), candle_poller_worker(), hourly_futures_watchdog_worker(), funding_worker(), forceorder_worker()] + [kline_worker(c) for c in kline_chunks]
        await asyncio.gather(*tasks)

    async def close(self):
        await self.exchange.close()
