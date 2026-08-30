import json
import os
import time
import base64
import threading
from datetime import datetime, timezone, timedelta
from config import INITIAL_BALANCE, LEVERAGE, POSITION_SIZE_USDT, COMMISSION_RATE

HISTORY_FILE = "trade_history.json"

# GitHub Remote Persistence Config
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "scullo/trade-bot")
GITHUB_FILE_PATH = "trade_history.json"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"

class PaperTrader:
    def __init__(self, initial_balance=INITIAL_BALANCE, leverage=LEVERAGE, margin_per_trade=POSITION_SIZE_USDT):
        self.initial_balance = float(initial_balance)
        self.balance = float(initial_balance)
        self.leverage = int(leverage)
        self.margin_per_trade = float(margin_per_trade)
        self.commission_rate = float(COMMISSION_RATE)
        self.open_positions = {}
        self.history = []
        self._github_sha = None
        self.load_history()

    def load_history(self):
        """Önce GitHub'dan yükle, başarısız olursa lokal dosyadan yükle."""
        loaded = False

        # 1. GitHub'dan yüklemeyi dene
        if GITHUB_TOKEN:
            try:
                import urllib.request
                req = urllib.request.Request(GITHUB_API_URL, headers={
                    "Authorization": f"token {GITHUB_TOKEN}",
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "TradeBot/1.0"
                })
                res = urllib.request.urlopen(req, timeout=10)
                gh_data = json.loads(res.read().decode("utf-8"))
                self._github_sha = gh_data.get("sha")
                content_b64 = gh_data.get("content", "")
                content_str = base64.b64decode(content_b64).decode("utf-8")
                data = json.loads(content_str)
                self.balance = float(data.get("balance", self.initial_balance))
                if self.balance > 150000.0 or self.balance <= 1000.0:
                    self.balance = float(self.initial_balance)
                    self.history = [h for h in self.history if abs(h.get('pnl', 0)) < 50000]
                self.open_positions = data.get("open_positions", {})
                self.history = data.get("history", [])
                loaded = True
                print(f">> [GITHUB PERSISTENCE] trade_history.json GitHub'dan yuklendi (SHA: {self._github_sha[:8]}...) Bakiye: {self.balance}")
            except Exception as e:
                print(f">> [GITHUB PERSISTENCE] GitHub'dan yuklenemedi: {e}")

        # 2. GitHub başarısız olursa lokal dosyadan yükle
        if not loaded and os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8-sig") as f:
                    data = json.load(f)
                    self.balance = float(data.get("balance", self.initial_balance))
                    if self.balance > 150000.0 or self.balance <= 1000.0:
                        self.balance = float(self.initial_balance)
                        self.history = [h for h in self.history if abs(h.get('pnl', 0)) < 50000]
                    self.open_positions = data.get("open_positions", {})
                    self.history = data.get("history", [])
                    loaded = True
                    print(f">> [LOCAL] trade_history.json lokal dosyadan yuklendi. Bakiye: {self.balance}")
            except Exception as e:
                print(f">> Gecmis yuklenirken hata: {e}")

        if not loaded:
            print(f">> [INIT] Yeni trade_history baslatiliyor. Baslangic Kasa: {self.initial_balance}")

    def save_history(self):
        """Hem lokale hem GitHub'a kaydet."""
        state = {
            "balance": round(self.balance, 4),
            "open_positions": self.open_positions,
            "history": self.history
        }

        # 1. Lokal dosyaya atomik kaydet (Bozulma Korumasi)
        try:
            tmp_file = HISTORY_FILE + ".tmp"
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            os.replace(tmp_file, HISTORY_FILE)
        except Exception as e:
            print(f">> Lokal gecmis kaydedilirken hata: {e}")

        # 2. GitHub'a kaydet (arka planda, ana threadi bloklamadan)
        if GITHUB_TOKEN:
            threading.Thread(target=self._push_to_github, args=(state,), daemon=True).start()

    def _push_to_github(self, state: dict):
        """trade_history.json dosyasini GitHub API uzerinden repo'ya kaydeder."""
        import urllib.request
        try:
            content_str = json.dumps(state, indent=2, ensure_ascii=False)
            content_b64 = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")

            # Güncel SHA'yı al (conflict olmaması için)
            if not self._github_sha:
                try:
                    req = urllib.request.Request(GITHUB_API_URL, headers={
                        "Authorization": f"token {GITHUB_TOKEN}",
                        "Accept": "application/vnd.github.v3+json",
                        "User-Agent": "TradeBot/1.0"
                    })
                    res = urllib.request.urlopen(req, timeout=10)
                    gh = json.loads(res.read().decode("utf-8"))
                    self._github_sha = gh.get("sha")
                except Exception:
                    pass

            payload = {
                "message": f"[BOT] Trade state auto-save ({datetime.now(timezone(timedelta(hours=3))).strftime('%H:%M:%S')})",
                "content": content_b64,
                "branch": "main"
            }
            if self._github_sha:
                payload["sha"] = self._github_sha

            payload_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(GITHUB_API_URL, data=payload_bytes, method="PUT", headers={
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json",
                "Content-Type": "application/json",
                "User-Agent": "TradeBot/1.0"
            })
            res = urllib.request.urlopen(req, timeout=15)
            resp_data = json.loads(res.read().decode("utf-8"))
            new_sha = resp_data.get("content", {}).get("sha", "")
            self._github_sha = new_sha
            print(f">> [GITHUB SYNC] trade_history.json kaydedildi (SHA: {new_sha[:8]}...)")
        except Exception as e:
            print(f">> [GITHUB SYNC HATA] {e}")

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

    def update_tick_telemetry(self, symbol: str, current_price: float):
        # Her fiyat hareketinde MFE (Max Kar) ve MAE (Max Zarar) derinligini anlik kaydeder ve Kademeli Izsuren Stopu yonetir
        if symbol not in self.open_positions:
            return
        pos = self.open_positions[symbol]
        side = pos["side"]
        entry = pos["entry_price"]
        lev = pos.get("leverage", 5)

        if current_price > pos.get("peak_price", entry):
            pos["peak_price"] = current_price
        if current_price < pos.get("trough_price", entry):
            pos["trough_price"] = current_price

        if side == "LONG":
            current_roe = ((current_price - entry) / entry) * lev * 100.0
            mfe_roe = ((pos["peak_price"] - entry) / entry) * lev * 100.0
            mae_roe = ((entry - pos["trough_price"]) / entry) * lev * 100.0
        else:
            current_roe = ((entry - current_price) / entry) * lev * 100.0
            mfe_roe = ((entry - pos["trough_price"]) / entry) * lev * 100.0
            mae_roe = ((pos["peak_price"] - entry) / entry) * lev * 100.0

        pos["max_mfe_roe"] = round(max(pos.get("max_mfe_roe", 0.0), mfe_roe), 2)
        pos["max_mae_roe"] = round(max(pos.get("max_mae_roe", 0.0), mae_roe), 2)

        # ── KADEMELİ İZSÜREN KÂR KİLİDİ (TIERED TRAILING PROFIT LOCK) ──
        updated_stop = False
        # Tier 3: ROE >= +15.0% -> En az +9.0% ROE kilit
        if current_roe >= 15.0 and not pos.get("_trail_15"):
            pos["_trail_15"] = True
            pos["_trail_8"] = True
            pos["trail_status"] = "🛡️ Tier 3 (%9.0 Kâr Korumalı)"
            if side == "LONG":
                lock_p = entry * (1.0 + (0.09 / lev))
                if lock_p > pos.get("soft_stop", 0):
                    pos["soft_stop"] = lock_p
                    pos["hard_stop"] = lock_p
                    updated_stop = True
            else:
                lock_p = entry * (1.0 - (0.09 / lev))
                if lock_p < pos.get("soft_stop", 999999):
                    pos["soft_stop"] = lock_p
                    pos["hard_stop"] = lock_p
                    updated_stop = True
            print(f">> [TRAILING TIER 3] {symbol} +%15 ROE Goruldu -> Stop +%9.0 Kâra Kilitlendi!")

        # Tier 2: ROE >= +8.0% -> En az +3.5% ROE kilit
        elif current_roe >= 8.0 and not pos.get("_trail_8"):
            pos["_trail_8"] = True
            pos["trail_status"] = "🛡️ Tier 2 (%3.5 Kâr Korumalı)"
            if side == "LONG":
                lock_p = entry * (1.0 + (0.035 / lev))
                if lock_p > pos.get("soft_stop", 0):
                    pos["soft_stop"] = lock_p
                    pos["hard_stop"] = lock_p
                    updated_stop = True
            else:
                lock_p = entry * (1.0 - (0.035 / lev))
                if lock_p < pos.get("soft_stop", 999999):
                    pos["soft_stop"] = lock_p
                    pos["hard_stop"] = lock_p
                    updated_stop = True
            print(f">> [TRAILING TIER 2] {symbol} +%8 ROE Goruldu -> Stop +%3.5 Kâra Kilitlendi!")

        if updated_stop:
            self.save_history()

    def open_position(self, symbol: str, side: str, entry_price: float, reason: str, soft_stop: float, hard_stop: float, tp1: float, tp2: float = None, trade_type: str = "BREAKOUT", snapshot_levels: dict = None, setup_id: str = "", confluence_list: list = None, atr_pct: float = 1.0, trend_regime: str = "YATAY", session: str = "LONDRA", volume_surge: float = 1.0, confluence_score: str = "2/4", htf_alignment: str = "TREND YÖNÜNDE", custom_margin: float = None):
        if symbol in self.open_positions:
            return None

        # Marjin ve Serbest Kasa Kontrolu (Dinamik ATR Boyutlandirma Destegi)
        margin = float(custom_margin) if custom_margin is not None else float(self.margin_per_trade)
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
        entry_time_str = datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M:%S")

        # Risk hesabi (1R degeri)
        risk_dist = abs(entry_price - soft_stop) if soft_stop else (entry_price * 0.01)
        initial_risk_usdt = round((risk_dist / entry_price) * position_value, 4)

        # Snapshot temizleme (JSON uyumlu hale getirme)
        clean_snapshot = {}
        if snapshot_levels and isinstance(snapshot_levels, dict):
            cam = snapshot_levels.get("camarilla", {})
            clean_snapshot = {
                "P": cam.get("P", 0.0), "R3": cam.get("R3", 0.0), "R4": cam.get("R4", 0.0), "R5": cam.get("R5", 0.0),
                "S3": cam.get("S3", 0.0), "S4": cam.get("S4", 0.0), "S5": cam.get("S5", 0.0),
                "tepe_avwap": snapshot_levels.get("tepe_avwap", 0.0),
                "dip_avwap": snapshot_levels.get("dip_avwap", 0.0),
                "mpoc": snapshot_levels.get("mpoc", 0.0),
                "mval": snapshot_levels.get("mval", 0.0),
                "mvah": snapshot_levels.get("mvah", 0.0),
                "above_npoc": snapshot_levels.get("above_npoc", 0.0),
                "below_npoc": snapshot_levels.get("below_npoc", 0.0)
            }

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
            "setup_id": setup_id or ("SETUP_" + trade_type),
            "confluence_count": len(confluence_list or []) or 1,
            "confluence_list": confluence_list or [reason.split('(')[0].strip()],
            "initial_risk_usdt": initial_risk_usdt,
            "snapshot_levels": clean_snapshot,
            "atr_pct": float(atr_pct),
            "trend_regime": trend_regime,
            "session": session,
            "tp1_hit": False,
            "volume_surge": float(volume_surge),
            "confluence_score": confluence_score,
            "htf_alignment": htf_alignment,
            "peak_price": float(entry_price),
            "trough_price": float(entry_price),
            "max_mfe_roe": 0.0,
            "max_mae_roe": 0.0,
            "reason": reason,
            "is_half_closed": False
        }

        self.open_positions[symbol] = pos
        self.save_history()
        print(f">> [POZISYON ACILDI] {symbol} {side} @ {entry_price} | Marjin: {margin}$ ({self.leverage}x) | Setup: {pos['setup_id']}")
        return pos

    def close_position(self, symbol: str, exit_price: float, close_reason: str, is_partial: bool = False):
        if symbol not in self.open_positions:
            return None

        pos = self.open_positions[symbol]
        side = pos["side"]
        entry_p = pos["entry_price"]
        margin = pos["margin"]
        entry_fee = pos["entry_fee"]

        if is_partial and not pos.get("is_half_closed", False):
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
            be_price = entry_p * 1.002 if side == "LONG" else entry_p * 0.998
            pos["soft_stop"] = be_price
            pos["hard_stop"] = be_price
            pos["tp1_hit"] = True
            pos["trail_status"] = "🎯 TP1 KİLİTLENDİ (%50 Alındı - Breakeven Korumalı)"

            exit_time_str = datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M:%S")
            # Duration format
            hold_sec = time.time() - pos.get("entry_timestamp", time.time())
            dur_mins = int(hold_sec // 60)
            dur_hrs = dur_mins // 60
            dur_str = f"{dur_hrs}sa {dur_mins % 60}dk" if dur_hrs > 0 else f"{dur_mins}dk"

            record = {
                "id": pos["id"] + "-TP1",
                "symbol": symbol,
                "side": side,
                "trade_type": pos.get("trade_type", "SCALP"),
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
                "duration": dur_str,
                "reason": pos.get("reason", "Strateji Sinyali"),
                "close_reason": close_reason,
                "tp1": pos.get("tp1", 0.0),
                "tp2": pos.get("tp2", 0.0),
                "soft_stop": pos.get("soft_stop", 0.0),
                "hard_stop": pos.get("hard_stop", 0.0)
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
            if self.balance > 150000.0 or self.balance < 1000.0:
                self.balance = float(self.initial_balance)
            exit_time_str = datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M:%S")

            # Duration format
            hold_sec = time.time() - pos.get("entry_timestamp", time.time())
            dur_mins = int(hold_sec // 60)
            dur_hrs = dur_mins // 60
            dur_str = f"{dur_hrs}sa {dur_mins % 60}dk" if dur_hrs > 0 else f"{dur_mins}dk"

            record = {
                "id": pos["id"],
                "symbol": symbol,
                "side": side,
                "trade_type": pos.get("trade_type", "SCALP"),
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
                "duration": dur_str,
                "reason": pos.get("reason", "Strateji Sinyali"),
                "close_reason": close_reason,
                "tp1": pos.get("tp1", 0.0),
                "tp2": pos.get("tp2", 0.0),
                "soft_stop": pos.get("soft_stop", 0.0),
                "hard_stop": pos.get("hard_stop", 0.0)
            }
            self.history.append(record)
            del self.open_positions[symbol]
            self.save_history()
            print(f">> [POZISYON KAPANDI] {symbol} Net: {net_pnl:+.2f}$ ({roe_pct:+.1f}%) | Kasa: {self.balance:.2f}$")
            return record
