import asyncio
import json
import logging
import threading
import time
import urllib.request
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("ValkyrieWalletListener")

class AutonomousWalletListener:
    """
    VALKYRIE 7/24 AUTONOMOUS ON-CHAIN WALLET LISTENER CRON
    Admin cüzdanlarına gelen transferleri 30 saniyede bir otonom tarar.
    Kullanıcının benzersiz kuruşlu transferini gördüğü anda kod sormadan lisansı 30 gün uzatır.
    """
    def __init__(self, db_manager, poll_interval_seconds: int = 30):
        self.db = db_manager
        self.poll_interval = poll_interval_seconds
        self.is_running = False
        self._thread = None

    def start_background_daemon(self):
        """Dinleyiciyi arka plan thread'i olarak baslatir."""
        if self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="Valkyrie-WalletListener")
        self._thread.start()
        print("[VALKYRIE WALLET LISTENER] 🛰️ Otonom Cüzdan Dinleyici 7/24 Arka Planda Başlatıldı!")

    def _run_loop(self):
        while self.is_running:
            try:
                self.check_all_pending_orders_on_chain()
            except Exception as e:
                print(f"[VALKYRIE WALLET LISTENER] ⚠️ Tarama Döngüsü Hatası: {e}")
            time.sleep(self.poll_interval)

    def check_all_pending_orders_on_chain(self):
        """Aktif bekleyen siparisleri blokzincir uzerinde tarar."""
        now_tsi = datetime.now(timezone(timedelta(hours=3))).strftime('%Y-%m-%d %H:%M:%S')
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM pending_crypto_orders 
                WHERE status = 'PENDING' AND expires_at > ?
            """, (now_tsi,))
            pending_orders = cursor.fetchall()

        if not pending_orders:
            return

        settings = self.db.get_payment_settings()
        trc20_wallet = settings.get("trc20_wallet")
        bep20_wallet = settings.get("bep20_wallet")

        for order in pending_orders:
            order_id = order['id']
            network = order['network']
            expected_amount = round(order['amount_usdt'], 2)
            target_wallet = trc20_wallet if network == "TRC20" else bep20_wallet

            # Gercek blokzincir agi taramasi
            matched_tx = self._fetch_matching_transaction(network, target_wallet, expected_amount)
            if matched_tx:
                tx_hash = matched_tx.get('tx_hash')
                print(f"[VALKYRIE WALLET LISTENER] 🎉 OTONOM TRANSFER YAKALANDI! Sipariş: {order['order_code']} | Tutar: ${expected_amount} USDT | TxHash: {tx_hash}")
                self.db.complete_pending_order_and_activate(order_id, tx_hash)

    def _fetch_matching_transaction(self, network: str, wallet_address: str, expected_amount: float) -> dict:
        """TronScan veya BSCScan API uzerinden gelen transferleri inceler."""
        if not wallet_address or "Valkyrie" in wallet_address:
            # Demo/simulasyon cuzdan adresi ise
            return None

        try:
            if network == "TRC20":
                # TronGrid / TronScan TRC20 USDT Transfer API
                url = f"https://api.trongrid.io/v1/accounts/{wallet_address}/transactions/trc20?limit=20"
                req = urllib.request.Request(url, headers={'User-Agent': 'ValkyrieQuant/1.0'})
                res = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
                data = json.loads(res)
                for tx in data.get('data', []):
                    to_addr = tx.get('to')
                    token_info = tx.get('token_info', {})
                    symbol = token_info.get('symbol', '').upper()
                    decimals = int(token_info.get('decimals', 6))
                    raw_val = float(tx.get('value', 0))
                    val_usdt = round(raw_val / (10 ** decimals), 2)
                    tx_id = tx.get('transaction_id')

                    if symbol == "USDT" and to_addr == wallet_address and abs(val_usdt - expected_amount) < 0.001:
                        return {"tx_hash": tx_id, "amount": val_usdt, "network": "TRC20"}

            elif network == "BEP20":
                # BSCScan BEP20 USDT Token Transfers API
                url = f"https://api.bscscan.com/api?module=account&action=tokentx&address={wallet_address}&page=1&offset=20&sort=desc"
                req = urllib.request.Request(url, headers={'User-Agent': 'ValkyrieQuant/1.0'})
                res = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
                data = json.loads(res)
                for tx in data.get('result', []):
                    to_addr = tx.get('to', '').lower()
                    symbol = tx.get('tokenSymbol', '').upper()
                    decimals = int(tx.get('tokenDecimal', 18))
                    raw_val = float(tx.get('value', 0))
                    val_usdt = round(raw_val / (10 ** decimals), 2)
                    tx_id = tx.get('hash')

                    if symbol == "USDT" and to_addr == wallet_address.lower() and abs(val_usdt - expected_amount) < 0.001:
                        return {"tx_hash": tx_id, "amount": val_usdt, "network": "BEP20"}

        except Exception as e:
            # Sessiz hata yakalama (ag kopmalarinda bot etkilenmez)
            pass

        return None
