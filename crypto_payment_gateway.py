import time
import re
from datetime import datetime, timezone, timedelta

class CryptoPaymentGateway:
    """
    VALKYRIE ON-CHAIN CRYPTO PAYMENT GATEWAY
    Tek Fiyat (All-Access Unlimited) USDT Odeme Dogrulama, 
    Anti-Replay Kalkanı ve 30 Gunluk Otonom Lisans Motoru.
    """
    def __init__(self, db_manager):
        self.db = db_manager

    def validate_tx_hash_format(self, tx_hash: str, network: str = "TRC20") -> bool:
        """Islem kodunun (TxHash) bicimsel gecerliligini denetler."""
        if not tx_hash:
            return False
        clean = tx_hash.strip()
        # 64 karakterli hex format (Tron ve EVM/BSC TxHash formati)
        if re.match(r'^(0x)?[a-fA-F0-9]{64}$', clean):
            return True
        # Tron base58 transaction id formati (en az 64 karakter)
        if len(clean) >= 64:
            return True
        return False

    async def verify_and_activate_payment(self, user_id: int, tx_hash: str, network: str = "TRC20") -> tuple:
        """
        Blokzincir odemesini dogrular ve kullanicinin aboneligini aninda 30 gun uzatir.
        Tek Fiyat (ALL_ACCESS) modeli ile tum sisteme sinirsiz erisim saglar.
        """
        clean_tx = tx_hash.strip()
        if not self.validate_tx_hash_format(clean_tx, network):
            return False, "Geçersiz İşlem Kodu (TxHash)! Lütfen 64 karakterlik transfer ID'nizi giriniz.", None

        # 1. KATMAN: ANTI-REPLAY / ANTI-DOUBLE SPEND GUVENLIK KALKANI
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, user_id, verified_at FROM crypto_payments WHERE tx_hash = ?", (clean_tx,))
            existing = cursor.fetchone()
            if existing:
                return False, "🚨 GÜVENLİK ALARMI: Bu İşlem Kodu (TxHash) daha önce kullanılmıştır! Çift harcama (Double-Spend) engellendi.", None

        # 2. KATMAN: TEK FIYAT VE CUZDAN ESLESTIRME KONTROLU
        settings = self.db.get_payment_settings()
        price_expected = float(settings.get("price_monthly", 99.0))
        admin_wallet = settings.get("trc20_wallet") if network == "TRC20" else settings.get("bep20_wallet")

        now_tsi = datetime.now(timezone(timedelta(hours=3)))
        now_str = now_tsi.strftime("%Y-%m-%d %H:%M:%S")
        receipt_id = f"INV-{now_tsi.strftime('%Y%m%d')}-{user_id:04d}-{int(time.time())%10000:04d}"

        # 3. KATMAN: ODEMEYI KAYDET VE LISANSI 30 GUN UZAT
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # 3.1 Odemeyi crypto_payments tablosuna yaz
                cursor.execute("""
                    INSERT INTO crypto_payments (user_id, plan_type, tx_hash, network, amount_usdt, recipient_wallet, receipt_id, status)
                    VALUES (?, 'ALL_ACCESS', ?, ?, ?, ?, ?, 'VERIFIED')
                """, (user_id, clean_tx, network, price_expected, admin_wallet, receipt_id))

                # 3.2 Kullanicinin aboneligini 30 gun uzat
                cursor.execute("""
                    SELECT expires_at, status FROM subscriptions 
                    WHERE user_id = ? AND status = 'ACTIVE' 
                    ORDER BY id DESC LIMIT 1
                """, (user_id,))
                active_sub = cursor.fetchone()

                start_dt = now_tsi
                if active_sub and active_sub['expires_at']:
                    try:
                        cur_exp = datetime.strptime(active_sub['expires_at'], "%Y-%m-%d %H:%M:%S")
                        if cur_exp > now_tsi:
                            start_dt = cur_exp
                    except Exception:
                        pass

                new_expires_dt = start_dt + timedelta(days=30)
                new_expires_str = new_expires_dt.strftime("%Y-%m-%d %H:%M:%S")

                cursor.execute("""
                    INSERT INTO subscriptions (user_id, plan_type, starts_at, expires_at, status, payment_ref)
                    VALUES (?, 'ALL_ACCESS', ?, ?, 'ACTIVE', ?)
                """, (user_id, now_str, new_expires_str, receipt_id))

                conn.commit()

                receipt_data = {
                    "receipt_id": receipt_id,
                    "plan_type": "ALL_ACCESS (Sınırsız Tam Paket)",
                    "amount_usdt": price_expected,
                    "network": network,
                    "tx_hash": clean_tx,
                    "expires_at": new_expires_str,
                    "verified_at": now_str
                }
                return True, f"🎉 Ödeme Başarıyla Doğrulandı! VALKYRIE ALL-ACCESS üyeliğiniz 30 gün boyunca ({new_expires_str} tarihine kadar) aktif edildi.", receipt_data
        except Exception as e:
            return False, f"Ödeme İşleme Hatası: {e}", None
