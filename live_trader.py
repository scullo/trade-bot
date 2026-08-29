import asyncio
import json
import os
import time
from datetime import datetime, timezone, timedelta
import ccxt.async_support as ccxt_async

LIVE_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "live_config.json")
LIVE_HISTORY_PATH = os.path.join(os.path.dirname(__file__), "live_trade_history.json")

def load_live_config() -> dict:
    if os.path.exists(LIVE_CONFIG_PATH):
        try:
            with open(LIVE_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
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

class LiveTrader:
    def __init__(self):
        self.config = load_live_config()
        self.exchange = None
        self.open_positions = {}
        self.history = self._load_history()
        self.last_balance = 0.0
        self.last_free_balance = 0.0
        self._init_exchange()

    def _init_exchange(self):
        api_key = self.config.get("api_key", "").strip()
        api_secret = self.config.get("api_secret", "").strip()
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
        else:
            self.exchange = None

    def _load_history(self) -> list:
        if os.path.exists(LIVE_HISTORY_PATH):
            try:
                with open(LIVE_HISTORY_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save_history(self):
        try:
            with open(LIVE_HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[LIVE TRADER] Gecmis kaydedilemedi: {e}")

    @property
    def balance(self) -> float:
        return self.last_balance

    def get_free_balance(self) -> float:
        return self.last_free_balance

    async def test_connection(self, api_key: str, api_secret: str) -> dict:
        """API anahtarlarini test eder, gecikme ve gercek bakiyeyi dondurur."""
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
                "message": "Binance Futures API Baglantisi Basarili!",
                "total_balance": round(total_usdt, 2),
                "free_balance": round(free_usdt, 2),
                "ping_ms": ping_ms
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Baglanti Hatasi: {str(e)}"
            }
        finally:
            if test_ex:
                await test_ex.close()

    async def update_credentials(self, api_key: str, api_secret: str, leverage: int, margin_type: str, position_size_usdt: float):
        if self.exchange:
            await self.exchange.close()

        self.config["api_key"] = api_key.strip()
        self.config["api_secret"] = api_secret.strip()
        self.config["leverage"] = int(leverage)
        self.config["margin_type"] = margin_type.upper()
        self.config["position_size_usdt"] = float(position_size_usdt)
        save_live_config(self.config)
        self._init_exchange()
        if self.exchange:
            await self.sync_balance()

    async def sync_balance(self):
        if not self.exchange:
            return
        try:
            balance_data = await self.exchange.fetch_balance()
            self.last_balance = float(balance_data.get('USDT', {}).get('total', 0.0))
            self.last_free_balance = float(balance_data.get('USDT', {}).get('free', 0.0))
        except Exception as e:
            print(f"[LIVE TRADER] Bakiye senkronizasyon hatasi: {e}")

    async def sync_open_positions(self):
        if not self.exchange:
            return
        try:
            positions = await self.exchange.fetch_positions()
            active_map = {}
            for p in positions:
                contracts = float(p.get('contracts', 0.0))
                if contracts > 0:
                    sym = p.get('symbol')
                    side = 'LONG' if p.get('side') == 'long' else 'SHORT'
                    active_map[sym] = {
                        "symbol": sym,
                        "side": side,
                        "entry_price": float(p.get('entryPrice', 0.0)),
                        "amount": contracts,
                        "leverage": int(p.get('leverage', self.config.get("leverage", 5))),
                        "position_value": float(p.get('notional', contracts * float(p.get('entryPrice', 1.0)))),
                        "unrealized_pnl": float(p.get('unrealizedPnl', 0.0)),
                        "entry_time": datetime.fromtimestamp(p.get('timestamp', int(time.time() * 1000)) / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                        "trade_type": "LIVE_POSITION"
                    }
            self.open_positions = active_map
        except Exception as e:
            print(f"[LIVE TRADER] Pozisyon senkronizasyon hatasi: {e}")

    async def open_position(self, symbol: str, side: str, current_price: float, trade_type: str, reason: str, levels_snapshot: dict = None, tp1: float = 0.0, tp2: float = 0.0, hard_stop: float = 0.0) -> dict:
        if not self.exchange:
            print("[LIVE TRADER HATA] API anahtari tanimli degil, pozisyon acilamadi.")
            return None

        clean_sym = symbol.replace(':USDT', '')
        if '/' not in clean_sym and not clean_sym.endswith('/USDT'):
            clean_sym = clean_sym + '/USDT'

        leverage = self.config.get("leverage", 5)
        margin_usdt = self.config.get("position_size_usdt", 10.0)

        try:
            try:
                await self.exchange.set_leverage(leverage, clean_sym)
            except Exception:
                pass

            try:
                await self.exchange.set_margin_mode(self.config.get("margin_type", "ISOLATED").lower(), clean_sym)
            except Exception:
                pass

            notional = margin_usdt * leverage
            amount = notional / current_price
            market = self.exchange.market(clean_sym) if self.exchange.markets else None
            if market and 'precision' in market and 'amount' in market['precision']:
                prec = market['precision']['amount']
                amount = round(amount, prec) if isinstance(prec, int) else float(self.exchange.amount_to_precision(clean_sym, amount))

            order_side = 'buy' if side == 'LONG' else 'sell'
            order = await self.exchange.create_order(
                symbol=clean_sym,
                type='market',
                side=order_side,
                amount=amount
            )
            entry_price = float(order.get('average') or order.get('price') or current_price)

            pos_data = {
                "id": str(order.get('id', int(time.time()))),
                "symbol": clean_sym,
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
                "levels_snapshot": levels_snapshot or {}
            }
            self.open_positions[clean_sym] = pos_data
            await self.sync_balance()
            return pos_data
        except Exception as e:
            print(f"[LIVE TRADER HATA] {clean_sym} {side} emri iletilemedi: {e}")
            return None

    async def close_position(self, symbol: str, current_price: float, reason: str, is_manual: bool = False) -> dict:
        if not self.exchange or symbol not in self.open_positions:
            return None

        pos = self.open_positions[symbol]
        side = pos["side"]
        amount = pos.get("amount", (pos["position_value"] / pos["entry_price"]))
        close_side = 'sell' if side == 'LONG' else 'buy'

        try:
            order = await self.exchange.create_order(
                symbol=symbol,
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
                "symbol": symbol,
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
            del self.open_positions[symbol]
            await self.sync_balance()
            return record
        except Exception as e:
            print(f"[LIVE TRADER HATA] {symbol} pozisyon kapatilamadi: {e}")
            return None
