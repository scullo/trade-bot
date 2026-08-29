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
