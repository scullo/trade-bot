import json
import os
import time
from datetime import datetime
from config import INITIAL_BALANCE, LEVERAGE, POSITION_SIZE_USDT, COMMISSION_RATE

HISTORY_FILE = "trade_history.json"

class PaperTrader:
    def __init__(self, initial_balance=INITIAL_BALANCE, leverage=LEVERAGE, margin_per_trade=POSITION_SIZE_USDT):
        self.initial_balance = float(initial_balance)
        self.balance = float(initial_balance)
        self.leverage = int(leverage)
        self.margin_per_trade = float(margin_per_trade)
        self.commission_rate = float(COMMISSION_RATE)
        self.open_positions = {}
        self.history = []
        self.load_history()

    def load_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8-sig") as f:
                    data = json.load(f)
                    self.balance = float(data.get("balance", self.initial_balance))
                    self.open_positions = data.get("open_positions", {})
                    self.history = data.get("history", [])
            except Exception as e:
                print(f">> Gecmis yuklenirken hata: {e}")

    def save_history(self):
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "balance": round(self.balance, 4),
                    "open_positions": self.open_positions,
                    "history": self.history
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f">> Gecmis kaydedilirken hata: {e}")

    def get_free_balance(self):
        used_margin = sum(p.get("margin", 0.0) for p in self.open_positions.values())
        return max(0.0, round(self.balance - used_margin, 2))

    def update_position_levels(self, symbol: str, **kwargs):
        """Acik pozisyonun TP/Stop/flag degerlerini gunceller ve kaydeder."""
        if symbol not in self.open_positions:
            return False
        pos = self.open_positions[symbol]
        for key, value in kwargs.items():
            pos[key] = value
        self.save_history()
        return True

    def open_position(self, symbol: str, side: str, entry_price: float, reason: str, soft_stop: float, hard_stop: float, tp1: float, tp2: float = None, trade_type: str = "BREAKOUT"):
        if symbol in self.open_positions:
            return None

        # Marjin ve Serbest Kasa Kontrolu
        margin = self.margin_per_trade
        free_bal = self.get_free_balance()
        if free_bal < margin:
            print(f">> [YETERSIZ BAKIYE] Kasa: {self.balance:.2f} USDT, Serbest Kasa: {free_bal:.2f} USDT, Gereken Marjin: {margin} USDT")
            return {
                "error": "INSUFFICIENT_BALANCE",
                "required_margin": margin,
                "current_balance": free_bal
            }

        position_value = margin * self.leverage
        quantity = position_value / entry_price
        entry_fee = position_value * self.commission_rate
        entry_timestamp = time.time()
        entry_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        pos = {
            "id": f"TRD-{len(self.history) + len(self.open_positions) + 1:04d}",
            "symbol": symbol,
            "side": side.upper(),
            "entry_price": float(entry_price),
            "margin": float(margin),
            "leverage": int(self.leverage),
            "position_value": float(position_value),
            "quantity": float(quantity),
            "entry_fee": float(entry_fee),
            "entry_time": entry_time_str,
            "entry_timestamp": entry_timestamp,
            "soft_stop": float(soft_stop),
            "hard_stop": float(hard_stop),
            "tp1": float(tp1) if tp1 else 0.0,
            "tp2": float(tp2) if tp2 else 0.0,
            "trade_type": trade_type,
            "reason": reason,
            "is_half_closed": False
        }

        self.open_positions[symbol] = pos
        self.save_history()
        print(f">> [POZISYON ACILDI] {symbol} {side} @ {entry_price} | Marjin: {margin}$ ({self.leverage}x)")
        return pos

    def close_position(self, symbol: str, exit_price: float, close_reason: str, is_partial: bool = False):
        if symbol not in self.open_positions:
            return None

        pos = self.open_positions[symbol]
        side = pos["side"]
        entry_p = pos["entry_price"]
        margin = pos["margin"]
        entry_fee = pos["entry_fee"]

        if is_partial and not pos["is_half_closed"]:
            # %50 TP1 Kapatma
            closed_margin = margin * 0.5
            closed_val = pos["position_value"] * 0.5
            closed_qty = pos["quantity"] * 0.5
            exit_fee = closed_val * self.commission_rate
            portion_entry_fee = entry_fee * 0.5

            if side == "LONG":
                gross_pnl = (exit_price - entry_p) * closed_qty
            else:
                gross_pnl = (entry_p - exit_price) * closed_qty

            total_fees = portion_entry_fee + exit_fee
            net_pnl = gross_pnl - total_fees
            roe_pct = (net_pnl / closed_margin) * 100.0

            self.balance += net_pnl

            # Kalan yariya Stop'u giris seviyesine (Breakeven) cek
            pos["is_half_closed"] = True
            pos["margin"] = closed_margin
            pos["position_value"] = closed_val
            pos["quantity"] = closed_qty
            pos["entry_fee"] = entry_fee - portion_entry_fee
            pos["soft_stop"] = entry_p # Breakeven
            pos["hard_stop"] = entry_p

            exit_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            record = {
                "id": pos["id"] + "-TP1",
                "symbol": symbol,
                "side": side,
                "leverage": pos["leverage"],
                "margin": round(closed_margin, 2),
                "entry_price": round(entry_p, 8),
                "exit_price": round(exit_price, 8),
                "gross_pnl": round(gross_pnl, 4),
                "fees": round(total_fees, 4),
                "net_pnl": round(net_pnl, 4),
                "roe_pct": round(roe_pct, 2),
                "balance_after": round(self.balance, 2),
                "entry_time": pos["entry_time"],
                "exit_time": exit_time_str,
                "reason": pos["reason"],
                "close_reason": close_reason
            }
            self.history.append(record)
            self.save_history()
            print(f">> [TP1 %50 KAPATILDI] {symbol} Net: {net_pnl:+.2f}$ ({roe_pct:+.1f}%) | Kasa: {self.balance:.2f}$")
            return record

        else:
            # Tam Kapatma
            qty = pos["quantity"]
            pos_val = pos["position_value"]
            exit_fee = (qty * exit_price) * self.commission_rate
            total_fees = entry_fee + exit_fee

            if side == "LONG":
                gross_pnl = (exit_price - entry_p) * qty
            else:
                gross_pnl = (entry_p - exit_price) * qty

            net_pnl = gross_pnl - total_fees
            roe_pct = (net_pnl / margin) * 100.0

            self.balance += net_pnl
            exit_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            record = {
                "id": pos["id"],
                "symbol": symbol,
                "side": side,
                "leverage": pos["leverage"],
                "margin": round(margin, 2),
                "entry_price": round(entry_p, 8),
                "exit_price": round(exit_price, 8),
                "gross_pnl": round(gross_pnl, 4),
                "fees": round(total_fees, 4),
                "net_pnl": round(net_pnl, 4),
                "roe_pct": round(roe_pct, 2),
                "balance_after": round(self.balance, 2),
                "entry_time": pos["entry_time"],
                "exit_time": exit_time_str,
                "reason": pos["reason"],
                "close_reason": close_reason
            }
            self.history.append(record)
            del self.open_positions[symbol]
            self.save_history()
            print(f">> [POZISYON KAPANDI] {symbol} Net: {net_pnl:+.2f}$ ({roe_pct:+.1f}%) | Kasa: {self.balance:.2f}$")
            return record
