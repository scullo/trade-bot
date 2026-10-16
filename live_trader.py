import asyncio
import json
import os
import time
from datetime import datetime, timezone, timedelta
import ccxt.async_support as ccxt_async
from security_vault import SecurityVault
import state_store
from valkyrie_logger import get_logger

logger = get_logger("live_trader")

LIVE_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "live_config.json")
LIVE_HISTORY_PATH = os.path.join(os.path.dirname(__file__), "live_trade_history.json")
LIVE_POSITIONS_PATH = os.path.join(os.path.dirname(__file__), "live_positions_state.json")


def normalize_symbol(symbol: str) -> str:
    """
    Her türlü borsa sembol formatını (BTC/USDT:USDT, BTCUSDT, BTC/USDT)
    bot standardı olan 'BTC/USDT' biçimine dönüştürür.
    """
    if not symbol:
        return ""
    s = str(symbol).split(":")[0].strip()
    if "/" in s:
        return s
    if s.endswith("USDT"):
        base = s[:-4]
        return f"{base}/USDT"
    return s


def to_exchange_symbol(symbol: str, markets: dict = None) -> str:
    """
    Bot standardındaki 'BTC/USDT' sembolünü CCXT Binance USD-M piyasa formatına
    (örneğin 'BTC/USDT:USDT') çevirir.
    """
    norm = normalize_symbol(symbol)
    if not norm:
        return symbol
    if not markets:
        return f"{norm}:USDT"
    futures_sym = f"{norm}:USDT"
    if futures_sym in markets:
        return futures_sym
    if norm in markets:
        return norm
    for k in markets:
        if normalize_symbol(k) == norm:
            return k
    return futures_sym


def load_live_config() -> dict:
    if os.path.exists(LIVE_CONFIG_PATH):
        try:
            with open(LIVE_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"live_config.json okunamadı ({e}), varsayılan DEMO modu yüklendi.")
    return {
        "mode": "DEMO",
        "api_key": "",
        "api_secret": "",
        "leverage": 5,
        "margin_type": "ISOLATED",
        "position_size_usdt": 10.0,
        "max_open_positions": 3,
        "auto_sl_tp": True
    }


def save_live_config(cfg: dict):
    with open(LIVE_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    try:
        state_store.backup_file(LIVE_CONFIG_PATH)
    except Exception as e:
        logger.debug(f"live_config.json yedeklenirken: {e}")


def load_positions_state() -> dict:
    if os.path.exists(LIVE_POSITIONS_PATH):
        try:
            with open(LIVE_POSITIONS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return {normalize_symbol(k): v for k, v in data.items()}
        except Exception as e:
            logger.warning(f"live_positions_state.json okunamadı: {e}")
    return {}


def save_positions_state(positions: dict):
    try:
        clean_data = {}
        for k, v in positions.items():
            clean_data[normalize_symbol(k)] = v
        with open(LIVE_POSITIONS_PATH, "w", encoding="utf-8") as f:
            json.dump(clean_data, f, indent=2, ensure_ascii=False)
        state_store.backup_file(LIVE_POSITIONS_PATH)
    except Exception as e:
        print(f"[LIVE TRADER] Pozisyon meta verisi kaydedilemedi: {e}")


class LiveTrader:
    def __init__(self):
        self.vault = SecurityVault()
        self.config = load_live_config()
        self.exchange = None
        self.open_positions = load_positions_state()
        self.history = self._load_history()
        self.last_balance = 0.0
        self.last_free_balance = 0.0
        self._markets_loaded = False
        self._init_exchange()

    def _init_exchange(self):
        enc_key = self.config.get("api_key", "").strip()
        enc_secret = self.config.get("api_secret", "").strip()

        api_key = self.vault.decrypt(enc_key[4:]) if enc_key.startswith("enc:") else enc_key
        api_secret = self.vault.decrypt(enc_secret[4:]) if enc_secret.startswith("enc:") else enc_secret

        if api_key and api_secret:
            self.exchange = ccxt_async.binanceusdm({
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future',
                    'adjustForTimeDifference': True
                }
            })
            self._markets_loaded = False
        else:
            self.exchange = None
            self._markets_loaded = False

    def _load_history(self) -> list:
        if os.path.exists(LIVE_HISTORY_PATH):
            try:
                with open(LIVE_HISTORY_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"live_trade_history.json yüklenirken hata: {e}")
        return []

    def _save_history(self):
        try:
            with open(LIVE_HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
            state_store.backup_file(LIVE_HISTORY_PATH, critical=True)
        except Exception as e:
            print(f"[LIVE TRADER] Geçmiş kaydedilemedi: {e}")

    def save_history(self):
        self._save_history()

    def save_local_history(self):
        self._save_history()

    def _save_positions_state(self):
        save_positions_state(self.open_positions)

    @property
    def balance(self) -> float:
        return self.last_balance

    def get_free_balance(self) -> float:
        return self.last_free_balance

    async def initialize(self):
        """
        Bot açılışında ya da LIVE moda geçişte Binance piyasa hassasiyetlerini (load_markets),
        güncel cüzdan bakiyesini ve açık borsa pozisyonlarını yükler.
        """
        if not self.exchange:
            self._init_exchange()
        if not self.exchange:
            print(">> [LIVE TRADER] API anahtarları tanımlı değil; canlı borsa bağlantısı beklemede.")
            return

        try:
            print(">> [LIVE TRADER] Binance piyasa verileri (load_markets) yükleniyor...")
            await self.exchange.load_markets()
            self._markets_loaded = True
            print(f">> [LIVE TRADER] {len(self.exchange.markets)} parite hassasiyet ve limitleri başarıyla yüklendi.")
        except Exception as e:
            print(f">> [LIVE TRADER HATA] load_markets başarısız oldu: {e}")

        await self.sync_balance()
        await self.sync_open_positions()

    async def test_connection(self, api_key: str, api_secret: str) -> dict:
        """API anahtarlarını test eder, gecikme ve gerçek bakiyeyi döndürür."""
        test_ex = None
        try:
            t0 = time.time()
            test_ex = ccxt_async.binanceusdm({
                'apiKey': api_key.strip(),
                'secret': api_secret.strip(),
                'enableRateLimit': True,
                'options': {'defaultType': 'future', 'adjustForTimeDifference': True}
            })
            balance_data = await test_ex.fetch_balance()
            ping_ms = int((time.time() - t0) * 1000)

            total_usdt = float(balance_data.get('USDT', {}).get('total', 0.0))
            free_usdt = float(balance_data.get('USDT', {}).get('free', 0.0))

            return {
                "status": "ok",
                "message": "Binance Futures API Bağlantısı Başarılı!",
                "total_balance": round(total_usdt, 2),
                "free_balance": round(free_usdt, 2),
                "ping_ms": ping_ms
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Bağlantı Hatası: {str(e)}"
            }
        finally:
            if test_ex:
                await test_ex.close()

    async def update_credentials(self, api_key: str, api_secret: str, leverage: int, margin_type: str, position_size_usdt: float, auto_sl_tp: bool = None):
        if self.exchange:
            await self.exchange.close()

        clean_key = api_key.strip()
        clean_secret = api_secret.strip()

        if clean_key and not clean_key.startswith("enc:"):
            self.config["api_key"] = "enc:" + self.vault.encrypt(clean_key)

        if clean_secret and not clean_secret.startswith("enc:"):
            self.config["api_secret"] = "enc:" + self.vault.encrypt(clean_secret)

        self.config["leverage"] = int(leverage)
        self.config["margin_type"] = margin_type.upper()
        self.config["position_size_usdt"] = float(position_size_usdt)
        if auto_sl_tp is not None:
            self.config["auto_sl_tp"] = bool(auto_sl_tp)

        save_live_config(self.config)
        self._init_exchange()
        if self.exchange:
            await self.initialize()

    async def sync_balance(self):
        if not self.exchange:
            return
        try:
            balance_data = await self.exchange.fetch_balance()
            self.last_balance = float(balance_data.get('USDT', {}).get('total', 0.0))
            self.last_free_balance = float(balance_data.get('USDT', {}).get('free', 0.0))
        except Exception as e:
            print(f"[LIVE TRADER] Bakiye senkronizasyon hatası: {e}")

    async def sync_open_positions(self):
        """
        Binance Futures üzerindeki gerçek açık pozisyonları sorgular.
        Diskteki meta verilerle (TP, SL, sinyal geçmişi) birleştirir;
        Borsada kapanmış pozisyonları tespit edip yerel durumu günceller.
        """
        if not self.exchange:
            return
        try:
            positions = await self.exchange.fetch_positions()
            active_map = {}
            for p in positions:
                contracts = float(p.get('contracts', 0.0))
                if contracts > 0:
                    raw_sym = p.get('symbol')
                    norm_sym = normalize_symbol(raw_sym)
                    side = 'LONG' if p.get('side') == 'long' else 'SHORT'
                    entry_p = float(p.get('entryPrice', 0.0))
                    lev = int(p.get('leverage', self.config.get("leverage", 5)))
                    notional = float(p.get('notional', contracts * entry_p))
                    upnl = float(p.get('unrealizedPnl', 0.0))

                    old_meta = self.open_positions.get(norm_sym, {})
                    entry_time = old_meta.get("entry_time")
                    if not entry_time:
                        raw_ts = p.get('timestamp')
                        entry_time = datetime.fromtimestamp(raw_ts / 1000).strftime('%Y-%m-%d %H:%M:%S') if raw_ts else datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M:%S")

                    pos_entry = {
                        "id": old_meta.get("id", str(int(time.time()))),
                        "symbol": norm_sym,
                        "exchange_symbol": raw_sym,
                        "side": side,
                        "entry_price": entry_p,
                        "amount": contracts,
                        "leverage": lev,
                        "position_value": abs(notional),
                        "unrealized_pnl": upnl,
                        "entry_time": entry_time,
                        "trade_type": old_meta.get("trade_type", "LIVE_POSITION"),
                        "reason": old_meta.get("reason", "BINANCE_SYNC"),
                        "margin_usdt": old_meta.get("margin_usdt", round(abs(notional) / max(1, lev), 2)),
                        "tp1": old_meta.get("tp1", 0.0),
                        "tp2": old_meta.get("tp2", 0.0),
                        "hard_stop": old_meta.get("hard_stop", 0.0),
                        "soft_stop": old_meta.get("soft_stop", old_meta.get("hard_stop", 0.0)),
                        "sl_order_id": old_meta.get("sl_order_id"),
                        "tp_order_id": old_meta.get("tp_order_id"),
                        "levels_snapshot": old_meta.get("levels_snapshot", {}),
                        "trail_status": old_meta.get("trail_status", "🟢 CANLI AKTİF")
                    }
                    active_map[norm_sym] = pos_entry

            # Eğer yerelde olup Binance'te artık bulunmayan pozisyon varsa (borsada SL/TP patlamış)
            for old_sym, old_pos in list(self.open_positions.items()):
                if old_sym not in active_map:
                    print(f">> [LIVE TRADER BİLGİ] {old_sym} pozisyonu borsada sonlanmış (SL/TP tetiklendi veya manuel kapatıldı).")
                    exit_price = old_pos.get("hard_stop") or old_pos.get("entry_price")
                    side = old_pos.get("side", "LONG")
                    entry_price = old_pos.get("entry_price", exit_price)
                    price_diff = (exit_price - entry_price) if side == 'LONG' else (entry_price - exit_price)
                    pos_val = old_pos.get("position_value", 0.0)
                    gross = pos_val * (price_diff / entry_price) if entry_price > 0 else 0.0
                    fees = pos_val * 0.001
                    net = gross - fees
                    roe = (price_diff / entry_price) * old_pos.get("leverage", 5) * 100.0 if entry_price > 0 else 0.0

                    closed_rec = {
                        "id": old_pos.get("id", str(int(time.time()))),
                        "symbol": old_sym,
                        "side": side,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "leverage": old_pos.get("leverage", 5),
                        "position_value": pos_val,
                        "fees": round(fees, 4),
                        "net_pnl": round(net, 4),
                        "roe_pct": round(roe, 2),
                        "reason": "EXCHANGE_TRIGGERED_CLOSE",
                        "entry_time": old_pos.get("entry_time", ""),
                        "exit_time": datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M:%S"),
                        "is_live": True
                    }
                    self.history.append(closed_rec)
                    self._save_history()

            self.open_positions = active_map
            self._save_positions_state()
        except Exception as e:
            print(f"[LIVE TRADER] Pozisyon senkronizasyon hatası: {e}")

    async def open_position(self, symbol: str, side: str, current_price: float, trade_type: str, reason: str, levels_snapshot: dict = None, tp1: float = 0.0, tp2: float = 0.0, hard_stop: float = 0.0, custom_margin: float = None, custom_leverage: int = None, **kwargs) -> dict:
        if not self.exchange:
            print("[LIVE TRADER HATA] API anahtarı tanımlı değil, pozisyon açılamadı.")
            return None

        norm_sym = normalize_symbol(symbol)
        if not self._markets_loaded or not self.exchange.markets:
            try:
                await self.exchange.load_markets()
                self._markets_loaded = True
            except Exception as e:
                print(f"[LIVE TRADER] load_markets uyarısı: {e}")

        ex_sym = to_exchange_symbol(norm_sym, self.exchange.markets)
        leverage = int(custom_leverage) if custom_leverage is not None and int(custom_leverage) > 0 else self.config.get("leverage", 5)
        margin_usdt = float(custom_margin) if custom_margin is not None else self.config.get("position_size_usdt", 10.0)

        try:
            # 1. Kaldıraç ayarla
            try:
                await self.exchange.set_leverage(leverage, ex_sym)
            except Exception as e:
                if "-2128" not in str(e):
                    print(f">> [GÜVENLİK İPTALİ] {ex_sym} Kaldıraç ayarlanamadı! Hata: {e}. İşlem iptal edildi.")
                    return None

            # 2. Marjin modu ayarla
            try:
                await self.exchange.set_margin_mode(self.config.get("margin_type", "ISOLATED").lower(), ex_sym)
            except Exception as e:
                if "-4046" not in str(e):
                    print(f">> [GÜVENLİK İPTALİ] {ex_sym} Marjin tipi ayarlanamadı! Hata: {e}. İşlem iptal edildi.")
                    return None

            # 3. Miktar ve hassasiyet hesabı
            notional = margin_usdt * leverage
            amount = notional / current_price
            if self.exchange.markets and ex_sym in self.exchange.markets:
                try:
                    amount = float(self.exchange.amount_to_precision(ex_sym, amount))
                except Exception:
                    market = self.exchange.market(ex_sym)
                    prec = market.get('precision', {}).get('amount')
                    if isinstance(prec, int):
                        amount = round(amount, prec)

            # 4. Ana piyasa emrini gönder
            order_side = 'buy' if side == 'LONG' else 'sell'
            close_side = 'sell' if side == 'LONG' else 'buy'
            order = await self.exchange.create_order(
                symbol=ex_sym,
                type='market',
                side=order_side,
                amount=amount
            )
            entry_price = float(order.get('average') or order.get('price') or current_price)

            sl_order_id = None
            tp_order_id = None

            # 5. Otomatik Borsa Stop-Loss & Take-Profit (auto_sl_tp)
            if self.config.get("auto_sl_tp", True):
                # A. Stop-Loss Girişi (Borsa STOP_MARKET)
                if hard_stop and hard_stop > 0:
                    try:
                        formatted_stop = float(self.exchange.price_to_precision(ex_sym, hard_stop))
                        sl_order = await self.exchange.create_order(
                            symbol=ex_sym,
                            type='STOP_MARKET',
                            side=close_side,
                            amount=amount,
                            params={'stopPrice': formatted_stop, 'reduceOnly': True}
                        )
                        sl_order_id = str(sl_order.get('id', ''))
                        print(f">> [LIVE TRADER] {ex_sym} Borsa Stop-Loss emri girildi: {formatted_stop} (ID: {sl_order_id})")
                    except Exception as e:
                        print(f">> [LIVE TRADER UYARI] {ex_sym} Borsa Stop-Loss emri iletilemedi: {e}")

                # B. Take-Profit Girişi (Borsa TAKE_PROFIT_MARKET)
                target_tp = tp1 if (tp1 and tp1 > 0) else (tp2 if (tp2 and tp2 > 0) else 0.0)
                if target_tp and target_tp > 0:
                    try:
                        formatted_tp = float(self.exchange.price_to_precision(ex_sym, target_tp))
                        tp_order = await self.exchange.create_order(
                            symbol=ex_sym,
                            type='TAKE_PROFIT_MARKET',
                            side=close_side,
                            amount=amount,
                            params={'stopPrice': formatted_tp, 'reduceOnly': True}
                        )
                        tp_order_id = str(tp_order.get('id', ''))
                        print(f">> [LIVE TRADER] {ex_sym} Borsa Kâr-Al emri girildi: {formatted_tp} (ID: {tp_order_id})")
                    except Exception as e:
                        print(f">> [LIVE TRADER UYARI] {ex_sym} Borsa Kâr-Al emri iletilemedi: {e}")

            pos_data = {
                "id": str(order.get('id', int(time.time()))),
                "symbol": norm_sym,
                "exchange_symbol": ex_sym,
                "side": side,
                "entry_price": entry_price,
                "margin_usdt": margin_usdt,
                "leverage": leverage,
                "position_value": entry_price * amount,
                "amount": amount,
                "entry_time": datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M:%S"),
                "trade_type": trade_type,
                "reason": reason,
                "tp1": tp1,
                "tp2": tp2,
                "hard_stop": hard_stop,
                "soft_stop": hard_stop,
                "sl_order_id": sl_order_id,
                "tp_order_id": tp_order_id,
                "levels_snapshot": levels_snapshot or {},
                "trail_status": "🟢 CANLI AKTİF"
            }
            self.open_positions[norm_sym] = pos_data
            self._save_positions_state()
            await self.sync_balance()
            return pos_data
        except Exception as e:
            print(f"[LIVE TRADER HATA] {ex_sym} {side} emri iletilemedi: {e}")
            return None

    async def update_position_stop(self, symbol: str, new_stop: float) -> bool:
        """
        İzsüren stop veya breakeven tetiklendiğinde borsa stop emrini günceller.
        """
        norm_sym = normalize_symbol(symbol)
        if norm_sym not in self.open_positions or not self.exchange:
            return False

        pos = self.open_positions[norm_sym]
        pos["hard_stop"] = new_stop
        pos["soft_stop"] = new_stop
        self._save_positions_state()

        if self.config.get("auto_sl_tp", True):
            ex_sym = pos.get("exchange_symbol") or to_exchange_symbol(norm_sym, self.exchange.markets)
            close_side = 'sell' if pos["side"] == 'LONG' else 'buy'
            try:
                old_sl = pos.get("sl_order_id")
                if old_sl:
                    try:
                        await self.exchange.cancel_order(old_sl, ex_sym)
                    except Exception as e:
                        logger.debug(f"Eski stop emri iptal edilirken (tetiklenmiş veya kapatılmış olabilir): {e}")
                formatted_stop = float(self.exchange.price_to_precision(ex_sym, new_stop))
                amount = float(self.exchange.amount_to_precision(ex_sym, pos["amount"]))
                new_sl = await self.exchange.create_order(
                    symbol=ex_sym,
                    type='STOP_MARKET',
                    side=close_side,
                    amount=amount,
                    params={'stopPrice': formatted_stop, 'reduceOnly': True}
                )
                pos["sl_order_id"] = str(new_sl.get("id", ""))
                self._save_positions_state()
                print(f">> [LIVE TRADER] {norm_sym} Borsa Stop-Loss güncellendi -> {formatted_stop} (ID: {pos['sl_order_id']})")
                return True
            except Exception as e:
                print(f">> [LIVE TRADER UYARI] {norm_sym} Stop-Loss borsa güncellemesi başarısız: {e}")
        return False

    async def close_position(self, symbol: str, current_price: float, reason: str, is_manual: bool = False) -> dict:
        norm_sym = normalize_symbol(symbol)
        if not self.exchange or norm_sym not in self.open_positions:
            return None

        pos = self.open_positions[norm_sym]
        ex_sym = pos.get("exchange_symbol") or to_exchange_symbol(norm_sym, self.exchange.markets)
        side = pos["side"]
        amount = pos.get("amount", (pos["position_value"] / pos["entry_price"]))
        close_side = 'sell' if side == 'LONG' else 'buy'

        # 1. Borsadaki açık kalan tüm şartlı Stop ve Kâr-al emirlerini temizle
        try:
            await self.exchange.cancel_all_orders(ex_sym)
            print(f">> [LIVE TRADER] {ex_sym} bekleyen tüm SL/TP emirleri borsadan iptal edildi.")
        except Exception as e:
            if "-2011" not in str(e):
                print(f">> [LIVE TRADER UYARI] {ex_sym} açık emirler iptal edilirken: {e}")

        # 2. Pozisyonu piyasadan kapat
        try:
            order = await self.exchange.create_order(
                symbol=ex_sym,
                type='market',
                side=close_side,
                amount=amount,
                params={'reduceOnly': True}
            )
            exit_price = float(order.get('average') or order.get('price') or current_price)

            price_diff = (exit_price - pos['entry_price']) if side == 'LONG' else (pos['entry_price'] - exit_price)
            gross_pnl = pos['position_value'] * (price_diff / pos['entry_price'])
            fees = (pos['position_value'] + (exit_price * amount)) * 0.0005
            net_pnl = gross_pnl - fees
            roe_pct = (price_diff / pos['entry_price']) * pos['leverage'] * 100

            record = {
                "id": str(order.get('id', int(time.time()))),
                "symbol": norm_sym,
                "exchange_symbol": ex_sym,
                "side": side,
                "entry_price": pos['entry_price'],
                "exit_price": exit_price,
                "leverage": pos['leverage'],
                "position_value": pos['position_value'],
                "fees": round(fees, 4),
                "net_pnl": round(net_pnl, 4),
                "roe_pct": round(roe_pct, 2),
                "reason": reason,
                "entry_time": pos['entry_time'],
                "exit_time": datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M:%S"),
                "is_live": True
            }

            self.history.append(record)
            self._save_history()
            del self.open_positions[norm_sym]
            self._save_positions_state()
            await self.sync_balance()
            return record
        except Exception as e:
            print(f"[LIVE TRADER HATA] {norm_sym} pozisyon kapatılamadı: {e}")
            return None

    def update_tick_telemetry(self, symbol: str, current_price: float, **kwargs):
        norm_sym = normalize_symbol(symbol)
        if norm_sym not in self.open_positions:
            return

        pos = self.open_positions[norm_sym]
        entry = pos.get("entry_price", current_price)
        lev = pos.get("leverage", 5)
        side = pos.get("side", "LONG")

        if current_price > pos.get("peak_price", entry):
            pos["peak_price"] = current_price
        if current_price < pos.get("trough_price", entry):
            pos["trough_price"] = current_price

        if side == "LONG":
            current_roe = round(((current_price - entry) / entry) * lev * 100.0, 4)
        else:
            current_roe = round(((entry - current_price) / entry) * lev * 100.0, 4)

        updated_stop = False
        new_stop_price = None

        # Tier 5: ROE >= +18.0% -> En az +13.0% ROE kilit
        if current_roe >= 18.0 and not pos.get("_trail_18"):
            pos["_trail_18"] = True
            pos["trail_status"] = "🛡️ Tier 5 (%13.0 Kâr Korumalı)"
            new_stop_price = round(entry * (1.0 + (0.13 / lev)), 8) if side == "LONG" else round(entry * (1.0 - (0.13 / lev)), 8)
            updated_stop = True

        # Tier 4: ROE >= +12.0% -> En az +8.0% ROE kilit
        elif current_roe >= 12.0 and not pos.get("_trail_12"):
            pos["_trail_12"] = True
            pos["trail_status"] = "🛡️ Tier 4 (%8.0 Kâr Korumalı)"
            new_stop_price = round(entry * (1.0 + (0.08 / lev)), 8) if side == "LONG" else round(entry * (1.0 - (0.08 / lev)), 8)
            updated_stop = True

        # Tier 3: ROE >= +7.0% -> En az +4.5% ROE kilit
        elif current_roe >= 7.0 and not pos.get("_trail_7"):
            pos["_trail_7"] = True
            pos["trail_status"] = "🛡️ Tier 3 (%4.5 Kâr Korumalı)"
            new_stop_price = round(entry * (1.0 + (0.045 / lev)), 8) if side == "LONG" else round(entry * (1.0 - (0.045 / lev)), 8)
            updated_stop = True

        # Tier 2: ROE >= +4.5% -> En az +2.8% ROE kilit
        elif current_roe >= 4.5 and not pos.get("_trail_45"):
            pos["_trail_45"] = True
            pos["trail_status"] = "🛡️ Tier 2 (%2.8 Kâr Korumalı)"
            new_stop_price = round(entry * (1.0 + (0.028 / lev)), 8) if side == "LONG" else round(entry * (1.0 - (0.028 / lev)), 8)
            updated_stop = True

        # Tier 1: ROE >= +3.5% -> En az +2.0% ROE kilit
        elif current_roe >= 3.5 and not pos.get("_trail_35"):
            pos["_trail_35"] = True
            pos["trail_status"] = "🛡️ Tier 1 (%2.0 Kâr Korumalı)"
            new_stop_price = round(entry * (1.0 + (0.020 / lev)), 8) if side == "LONG" else round(entry * (1.0 - (0.020 / lev)), 8)
            updated_stop = True

        # Tier 0 (Erken Breakeven): ROE >= +2.50%
        elif current_roe >= 2.50 and not pos.get("_trail_be"):
            pos["_trail_be"] = True
            pos["trail_status"] = "🛡️ TIER 0 BREAKEVEN KORUMA AKTİF"
            new_stop_price = round(entry * 1.0030, 8) if side == "LONG" else round(entry * 0.9970, 8)
            updated_stop = True

        if updated_stop and new_stop_price:
            pos["hard_stop"] = new_stop_price
            pos["soft_stop"] = new_stop_price
            self._save_positions_state()
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.update_position_stop(norm_sym, new_stop_price))
            except Exception as e:
                logger.warning(f"Stop güncelleme asenkron görevi başlatılamadı: {e}")

    def update_position_levels(self, symbol: str, **kwargs):
        norm_sym = normalize_symbol(symbol)
        if norm_sym in self.open_positions:
            self.open_positions[norm_sym].update(kwargs)
            self._save_positions_state()
