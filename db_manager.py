import time
import sqlite3
import os
import hashlib
from datetime import datetime, timezone, timedelta
from security_vault import SecurityVault

DB_PATH = os.path.join(os.path.dirname(__file__), 'valkyrie_platform.db')

class DatabaseManager:
    """
    VALKYRIE MULTI-TENANT DATABASE MANAGER
    Cok kullanicili uye yonetimi, AES-256 Binance API kasasi,
    24 Saatlik VIP Deneme (1-Day Trial) ve Binance UID Suistimal Engelleme Motoru.
    """
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.vault = SecurityVault()
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Veritabani tablolarini ve indekslerini olusturur."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. KULLANICILAR TABLOSU (Anti-Abuse UID Tekilligi ile)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    telegram_chat_id TEXT,
                    binance_uid_hash TEXT UNIQUE,
                    role TEXT DEFAULT 'USER',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 2. SIFRELI BINANCE API KASASI (AES-256)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS api_credentials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE NOT NULL,
                    encrypted_api_key TEXT NOT NULL,
                    encrypted_api_secret TEXT NOT NULL,
                    is_valid INTEGER DEFAULT 0,
                    futures_balance REAL DEFAULT 0.0,
                    verified_at DATETIME,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)

            # 3. ABONELIKLER & 24 SAAT DENEME TABLOSU
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    plan_type TEXT NOT NULL,
                    starts_at DATETIME NOT NULL,
                    expires_at DATETIME NOT NULL,
                    status TEXT DEFAULT 'ACTIVE',
                    payment_ref TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)

            # 4. KULLANICI ISLEM GUNLUGU (MULTI-TENANT TRADE LOGS)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_trade_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    leverage INTEGER DEFAULT 5,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    net_pnl REAL DEFAULT 0.0,
                    roe_pct REAL DEFAULT 0.0,
                    status TEXT DEFAULT 'OPEN',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)

            # 5. KRIPTO ODEMELERI & BLOKZINCIR ISLEM KAYITLARI (ANTI-REPLAY)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS crypto_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    plan_type TEXT NOT NULL,
                    tx_hash TEXT UNIQUE NOT NULL,
                    network TEXT NOT NULL,
                    amount_usdt REAL NOT NULL,
                    recipient_wallet TEXT NOT NULL,
                    receipt_id TEXT UNIQUE NOT NULL,
                    status TEXT DEFAULT 'VERIFIED',
                    verified_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)

            # 6. SISTEM GENEL AYARLARI (ADMIN CUZDANLARI & FIYATLANDIRMA)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 7. OTONOM CUZDAN DINLEYICI ICIN BEKLEYEN SIPARISLER (UNIQUE CENT MATCHING)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pending_crypto_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    order_code TEXT UNIQUE NOT NULL,
                    amount_usdt REAL NOT NULL,
                    network TEXT NOT NULL,
                    target_wallet TEXT NOT NULL,
                    status TEXT DEFAULT 'PENDING',
                    tx_hash TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            conn.commit()

    def check_binance_uid_trial_eligibility(self, raw_binance_uid: str) -> tuple:
        """
        ANTI-ABUSE KONTROLU (1. Kalkan):
        Bu Binance Hesap UID'si daha once 24 saatlik denemeyi kullandi mi?
        """
        if not raw_binance_uid:
            return True, "UID belirtilmedi"
        uid_hash = self.vault.hash_binance_uid(raw_binance_uid)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, email FROM users WHERE binance_uid_hash = ?", (uid_hash,))
            row = cursor.fetchone()
            if row:
                return False, f"Bu Binance hesabı daha önce ({row['email']}) ile 24 saatlik ücretsiz denemeyi kullandı. Lütfen ücretli bir paket seçiniz."
            return True, "Binance hesabı deneme için uygun"

    def register_user(self, email: str, password_raw: str, telegram_chat_id: str = None, raw_binance_uid: str = None) -> tuple:
        """Yeni kullanici kaydeder ve 24 Saatlik VIP Denemeyi baslatir."""
        clean_email = email.strip().lower()
        pwd_hash = hashlib.sha256(password_raw.encode('utf-8')).hexdigest()
        uid_hash = self.vault.hash_binance_uid(raw_binance_uid) if raw_binance_uid else None

        if uid_hash:
            eligible, msg = self.check_binance_uid_trial_eligibility(raw_binance_uid)
            if not eligible:
                return False, msg, None

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO users (email, password_hash, telegram_chat_id, binance_uid_hash)
                    VALUES (?, ?, ?, ?)
                """, (clean_email, pwd_hash, telegram_chat_id, uid_hash))
                user_id = cursor.lastrowid

                # Otomatik 24 Saatlik VIP Deneme Baslat
                now_tsi = datetime.now(timezone(timedelta(hours=3)))
                expires_tsi = now_tsi + timedelta(hours=24)
                cursor.execute("""
                    INSERT INTO subscriptions (user_id, plan_type, starts_at, expires_at, status)
                    VALUES (?, '24H_TRIAL', ?, ?, 'ACTIVE')
                """, (user_id, now_tsi.strftime('%Y-%m-%d %H:%M:%S'), expires_tsi.strftime('%Y-%m-%d %H:%M:%S')))

                conn.commit()
                return True, "Kullanıcı başarıyla kaydedildi ve 24 Saatlik VIP Deneme tanımlandı!", user_id
        except sqlite3.IntegrityError:
            return False, "Bu e-posta adresi veya Binance hesabı sistemde zaten kayıtlı!", None
        except Exception as e:
            return False, f"Kayıt Hatası: {e}", None

    def save_api_credentials(self, user_id: int, api_key_raw: str, api_secret_raw: str, balance: float = 0.0) -> bool:
        """Binance API anahtarlarini AES-256 ile sifreleyerek guvenle saklar."""
        enc_key = self.vault.encrypt(api_key_raw.strip())
        enc_secret = self.vault.encrypt(api_secret_raw.strip())
        now_str = datetime.now(timezone(timedelta(hours=3))).strftime('%Y-%m-%d %H:%M:%S')

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO api_credentials (user_id, encrypted_api_key, encrypted_api_secret, is_valid, futures_balance, verified_at)
                VALUES (?, ?, ?, 1, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    encrypted_api_key=excluded.encrypted_api_key,
                    encrypted_api_secret=excluded.encrypted_api_secret,
                    is_valid=1,
                    futures_balance=excluded.futures_balance,
                    verified_at=excluded.verified_at
            """, (user_id, enc_key, enc_secret, balance, now_str))
            conn.commit()
            return True

    def get_decrypted_credentials(self, user_id: int) -> dict:
        """Kullanicinin API anahtarlarini cozer ve bellekte kullanilmak uzere dondurur."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT encrypted_api_key, encrypted_api_secret, is_valid, futures_balance FROM api_credentials WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if not row or not row['is_valid']:
                return None
            return {
                "api_key": self.vault.decrypt(row['encrypted_api_key']),
                "api_secret": self.vault.decrypt(row['encrypted_api_secret']),
                "futures_balance": row['futures_balance']
            }

    def get_active_subscribers_for_dispatch(self) -> list:
        """Sinyal aninda emir iletilecek aktif lisansli musterileri dondurur."""
        now_str = datetime.now(timezone(timedelta(hours=3))).strftime('%Y-%m-%d %H:%M:%S')
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.id as user_id, u.email, u.telegram_chat_id, s.plan_type, s.expires_at,
                       c.encrypted_api_key, c.encrypted_api_secret, c.futures_balance
                FROM subscriptions s
                JOIN users u ON s.user_id = u.id
                JOIN api_credentials c ON u.id = c.user_id
                WHERE s.status = 'ACTIVE' AND s.expires_at >= ? AND c.is_valid = 1
            """, (now_str,))
            rows = cursor.fetchall()
            subscribers = []
            for r in rows:
                subscribers.append({
                    "user_id": r['user_id'],
                    "email": r['email'],
                    "telegram_chat_id": r['telegram_chat_id'],
                    "plan_type": r['plan_type'],
                    "api_key": self.vault.decrypt(r['encrypted_api_key']),
                    "api_secret": self.vault.decrypt(r['encrypted_api_secret']),
                    "futures_balance": r['futures_balance']
                })
            return subscribers


    def seed_admin_account(self, email: str = "admin@valkyriequant.com", password_raw: str = "AdminValkyrie2026!"):
        """Sistem ilk baslatildiginda Master Admin hesabini otomatik olusturur."""
        clean_email = email.strip().lower()
        pwd_hash = hashlib.sha256(password_raw.encode('utf-8')).hexdigest()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE email = ?", (clean_email,))
            row = cursor.fetchone()
            if not row:
                cursor.execute("""
                    INSERT INTO users (email, password_hash, role, telegram_chat_id)
                    VALUES (?, ?, 'ADMIN', '829687700')
                """, (clean_email, pwd_hash))
                user_id = cursor.lastrowid
                now_tsi = datetime.now(timezone(timedelta(hours=3)))
                expires_tsi = now_tsi + timedelta(days=3650)
                cursor.execute("""
                    INSERT INTO subscriptions (user_id, plan_type, starts_at, expires_at, status)
                    VALUES (?, 'VIP', ?, ?, 'ACTIVE')
                """, (user_id, now_tsi.strftime('%Y-%m-%d %H:%M:%S'), expires_tsi.strftime('%Y-%m-%d %H:%M:%S')))
                conn.commit()
                print(">> [MASTER ADMIN] admin@valkyriequant.com hesabi basariyla olusturuldu!")

    def authenticate_user(self, email: str, password_raw: str) -> tuple:
        """Kullanici girisini dogrular ve oturum bilgilerini dondurur."""
        clean_email = email.strip().lower()
        pwd_hash = hashlib.sha256(password_raw.encode('utf-8')).hexdigest()
        now_str = datetime.now(timezone(timedelta(hours=3))).strftime('%Y-%m-%d %H:%M:%S')

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.id, u.email, u.role, u.telegram_chat_id, u.created_at,
                       s.plan_type, s.expires_at, s.status as sub_status
                FROM users u
                LEFT JOIN subscriptions s ON u.id = s.user_id
                WHERE u.email = ? AND u.password_hash = ?
                ORDER BY s.id DESC LIMIT 1
            """, (clean_email, pwd_hash))
            row = cursor.fetchone()
            if not row:
                return False, "E-posta veya şifre hatalı!", None

            # 24 Saatlik deneme kalan suresi
            expires_at_str = row['expires_at']
            is_active = False
            remaining_seconds = 0
            if expires_at_str:
                try:
                    exp_dt = datetime.strptime(expires_at_str, '%Y-%m-%d %H:%M:%S')
                    now_dt = datetime.strptime(now_str, '%Y-%m-%d %H:%M:%S')
                    remaining_seconds = max(0, int((exp_dt - now_dt).total_seconds()))
                    is_active = (remaining_seconds > 0) and (row['sub_status'] == 'ACTIVE')
                except Exception:
                    pass

            user_data = {
                "id": row['id'],
                "email": row['email'],
                "role": row['role'],
                "telegram_chat_id": row['telegram_chat_id'],
                "plan_type": row['plan_type'] or '24H_TRIAL',
                "is_subscription_active": is_active,
                "remaining_seconds": remaining_seconds,
                "expires_at": expires_at_str
            }
            return True, "Giriş başarılı!", user_data

    def get_admin_dashboard_metrics(self) -> dict:
        """Master Admin icin toplam AUM, abone sayilari ve kullanici tablosunu derler."""
        now_str = datetime.now(timezone(timedelta(hours=3))).strftime('%Y-%m-%d %H:%M:%S')
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Kullanici ve abonelik listesi
            cursor.execute("""
                SELECT u.id, u.email, u.role, u.telegram_chat_id, u.created_at,
                       s.plan_type, s.expires_at, s.status as sub_status,
                       c.futures_balance, c.is_valid as api_valid
                FROM users u
                LEFT JOIN subscriptions s ON u.id = s.user_id
                LEFT JOIN api_credentials c ON u.id = c.user_id
                GROUP BY u.id
                ORDER BY u.id DESC
            """)
            users = []
            total_aum = 0.0
            trial_count = 0
            pro_count = 0
            vip_count = 0

            for r in cursor.fetchall():
                bal = float(r['futures_balance'] or 0.0)
                total_aum += bal
                plan = r['plan_type'] or '24H_TRIAL'
                if plan == '24H_TRIAL': trial_count += 1
                elif plan == 'PRO': pro_count += 1
                elif plan == 'VIP': vip_count += 1

                users.append({
                    "id": r['id'],
                    "email": r['email'],
                    "role": r['role'],
                    "plan": plan,
                    "expires_at": r['expires_at'],
                    "sub_status": r['sub_status'],
                    "balance": bal,
                    "api_valid": bool(r['api_valid']),
                    "created_at": r['created_at']
                })

            return {
                "total_users": len(users),
                "total_aum": total_aum,
                "trial_count": trial_count,
                "pro_count": pro_count,
                "vip_count": vip_count,
                "users_list": users
            }


    def get_payment_settings(self) -> dict:
        """Admin tarafindan belirlenen resmi USDT cuzdanlarini ve tek fiyatini dondurur."""
        default_settings = {
            "trc20_wallet": "TXvK7w7ValkyrieQuantProTRC20DepositVault99",
            "bep20_wallet": "0x71C836393791B339243764835261821039818299",
            "price_monthly": 99.0
        }
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM system_settings")
            for row in cursor.fetchall():
                k = row['key']
                v = row['value']
                if k in ("price_monthly", "price_pro", "price_vip"):
                    default_settings["price_monthly"] = float(v)
                else:
                    default_settings[k] = v
        return default_settings

    def save_payment_settings(self, trc20_wallet: str, bep20_wallet: str, price_monthly: float = 99.0) -> bool:
        """Admin panelinden girilen USDT cuzdanlarini ve tek aylik fiyatini kaydeder."""
        now_str = datetime.now(timezone(timedelta(hours=3))).strftime('%Y-%m-%d %H:%M:%S')
        settings_map = {
            "trc20_wallet": trc20_wallet.strip(),
            "bep20_wallet": bep20_wallet.strip(),
            "price_monthly": str(float(price_monthly))
        }
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for k, v in settings_map.items():
                cursor.execute("""
                    INSERT INTO system_settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """, (k, v, now_str))
            conn.commit()
            return True

    def create_pending_crypto_order(self, user_id: int, network: str = "TRC20") -> dict:
        """
        Kullanici icin benzersiz kuruslu (Unique Cent) 20 dakikalik otonom siparis olusturur.
        Ornek: 99.04 USDT veya 99.17 USDT.
        """
        import random
        settings = self.get_payment_settings()
        base_price = float(settings.get("price_monthly", 99.0))
        target_wallet = settings.get("trc20_wallet") if network == "TRC20" else settings.get("bep20_wallet")

        now_tsi = datetime.now(timezone(timedelta(hours=3)))
        expires_tsi = now_tsi + timedelta(minutes=20)
        now_str = now_tsi.strftime('%Y-%m-%d %H:%M:%S')
        expires_str = expires_tsi.strftime('%Y-%m-%d %H:%M:%S')

        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Son 20 dakikada aktif olan diger kuruslari bul (cakismayi onle)
            cursor.execute("""
                SELECT amount_usdt FROM pending_crypto_orders 
                WHERE status = 'PENDING' AND expires_at > ?
            """, (now_str,))
            active_amounts = {round(row['amount_usdt'], 2) for row in cursor.fetchall()}

            # 0.01 ile 0.99 arasinda bos bir kurus sec
            cent_offset = 0.00
            for _ in range(100):
                cand = round(random.randint(1, 99) * 0.01, 2)
                candidate_price = round(base_price + cand, 2)
                if candidate_price not in active_amounts:
                    cent_offset = cand
                    break
            
            final_price = round(base_price + cent_offset, 2)
            order_code = f"ORD-{now_tsi.strftime('%Y%m%d%H%M')}-{user_id:04d}-{random.randint(1000, 9999)}"

            cursor.execute("""
                INSERT INTO pending_crypto_orders (user_id, order_code, amount_usdt, network, target_wallet, status, expires_at)
                VALUES (?, ?, ?, ?, ?, 'PENDING', ?)
            """, (user_id, order_code, final_price, network, target_wallet, expires_str))
            
            order_id = cursor.lastrowid
            conn.commit()

            return {
                "order_id": order_id,
                "order_code": order_code,
                "amount_usdt": final_price,
                "base_price": base_price,
                "cent_tag": cent_offset,
                "network": network,
                "target_wallet": target_wallet,
                "expires_at": expires_str,
                "expires_in_seconds": 1200
            }

    def get_pending_order_status(self, order_code: str) -> dict:
        """Siparisin blokzincir onay durumunu sorgular."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.*, u.email 
                FROM pending_crypto_orders p
                JOIN users u ON p.user_id = u.id
                WHERE p.order_code = ?
            """, (order_code,))
            row = cursor.fetchone()
            if not row:
                return {"found": False, "status": "NOT_FOUND"}

            now_tsi = datetime.now(timezone(timedelta(hours=3))).strftime('%Y-%m-%d %H:%M:%S')
            is_expired = (row['expires_at'] < now_tsi and row['status'] == 'PENDING')
            status = "EXPIRED" if is_expired else row['status']

            # Eger tamamlandiysa makbuz detaylarini dondur
            receipt = None
            if row['status'] == 'COMPLETED':
                cursor.execute("SELECT * FROM crypto_payments WHERE tx_hash = ?", (row['tx_hash'],))
                pmt = cursor.fetchone()
                if pmt:
                    receipt = {
                        "receipt_id": pmt['receipt_id'],
                        "tx_hash": pmt['tx_hash'],
                        "amount_usdt": pmt['amount_usdt'],
                        "network": pmt['network'],
                        "verified_at": pmt['verified_at']
                    }

            return {
                "found": True,
                "order_id": row['id'],
                "order_code": row['order_code'],
                "user_id": row['user_id'],
                "email": row['email'],
                "amount_usdt": row['amount_usdt'],
                "network": row['network'],
                "target_wallet": row['target_wallet'],
                "status": status,
                "tx_hash": row['tx_hash'],
                "receipt": receipt
            }

    def complete_pending_order_and_activate(self, order_id: int, tx_hash: str) -> bool:
        """Cuzdan dinleyicisi transferi yakaladiginda siparisi onaylar ve lisansi acar."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pending_crypto_orders WHERE id = ? AND status = 'PENDING'", (order_id,))
            order = cursor.fetchone()
            if not order:
                return False

            user_id = order['user_id']
            network = order['network']
            amount = order['amount_usdt']
            target_wallet = order['target_wallet']

            now_tsi = datetime.now(timezone(timedelta(hours=3)))
            now_str = now_tsi.strftime('%Y-%m-%d %H:%M:%S')
            receipt_id = f"INV-{now_tsi.strftime('%Y%m%d')}-{user_id:04d}-{int(time.time())%10000:04d}"

            # 1. crypto_payments tablosuna ekle
            cursor.execute("""
                INSERT OR IGNORE INTO crypto_payments (user_id, plan_type, tx_hash, network, amount_usdt, recipient_wallet, receipt_id, status)
                VALUES (?, 'ALL_ACCESS', ?, ?, ?, ?, ?, 'VERIFIED')
            """, (user_id, tx_hash, network, amount, target_wallet, receipt_id))

            # 2. subscriptions tablosunda 30 gun uzat
            cursor.execute("""
                SELECT expires_at FROM subscriptions 
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

            # 3. pending_crypto_orders durumunu COMPLETED yap
            cursor.execute("""
                UPDATE pending_crypto_orders 
                SET status = 'COMPLETED', tx_hash = ? 
                WHERE id = ?
            """, (tx_hash, order_id))

            conn.commit()
            return True
