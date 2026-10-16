import os
import sys
import hmac
import hashlib
import unittest
import asyncio
from unittest.mock import patch, MagicMock

import config
from security_vault import SecurityVault
from db_manager import DatabaseManager, hash_password, verify_password
from crypto_payment_gateway import CryptoPaymentGateway
import paper_trader
import web_server

class TestSecurityHardening(unittest.TestCase):
    """
    Valkyrie 6 Kritik Güvenlik Açığı Denetim ve Doğrulama Test Paketi
    """

    def test_01_no_hardcoded_github_token_in_paper_trader(self):
        """Madde 1: paper_trader.py içinde parçalı/gizli GitHub token bulunmamalıdır."""
        with open("paper_trader.py", "r", encoding="utf-8") as f:
            code = f.read()

        # push scanner atlatmaya çalışan parçalanmış kod blokları kesinlikle olmamalı
        self.assertNotIn("k1 = \"github_pat_\"", code)
        self.assertNotIn("k2 =", code)
        self.assertNotIn("k3 =", code)

        # Test ortamında güvenlik gereği "" dönmeli
        self.assertEqual(paper_trader._get_gh_token(), "")

        # Canlı çalışma ortamında ortam değişkeninden token okunmalı
        with patch("paper_trader._is_test_env", return_value=False):
            with patch.dict(os.environ, {"GITHUB_TOKEN": "test_env_token_valkyrie"}):
                token = paper_trader._get_gh_token()
                self.assertEqual(token, "test_env_token_valkyrie")

    def test_02_no_hardcoded_telegram_token_in_config(self):
        """Madde 2: config.py içinde varsayılan açık bot token bulunmamalıdır."""
        with open("config.py", "r", encoding="utf-8") as f:
            code = f.read()

        # Eski sızdırılmış bot token config dosyasında sabit kalmamalı
        self.assertNotIn("8893395987:AAGo285LhPhMKEfQW5e8zWc1q", code)
        self.assertNotIn("829687700", code)

        # TELEGRAM_BOT_TOKEN os.getenv'dan okunmalı, default "" olmalı
        self.assertIn('TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")', code)

    def test_03_secure_vault_and_dynamic_admin_secret(self):
        """Madde 3: ADMIN_SECRET ve Security Vault master key/salt dinamik ve izole olmalıdır."""
        with open("config.py", "r", encoding="utf-8") as f:
            code = f.read()
        self.assertNotIn('ADMIN_SECRET = "valkyrie-quant-2025-secure"', code)

        # Dynamic admin secret test
        secret = config._get_admin_secret()
        self.assertTrue(len(secret) >= 32)

        # Security Vault dynamic key & salt test
        vault = SecurityVault()
        encrypted = vault.encrypt("binance_secret_api_key_test")
        self.assertTrue(len(encrypted) > 10)
        decrypted = vault.decrypt(encrypted)
        self.assertEqual(decrypted, "binance_secret_api_key_test")

    def test_04_pbkdf2_salted_password_hashing_and_auto_upgrade(self):
        """Madde 4: Tuzlu PBKDF2 hashleme ve eski SHA-256'dan otomatik terfi testi."""
        raw_pwd = "MySecretPassword2026!#"
        hashed = hash_password(raw_pwd)

        self.assertTrue(hashed.startswith("pbkdf2:sha256:100000$"))
        self.assertTrue(verify_password(raw_pwd, hashed))
        self.assertFalse(verify_password("WrongPassword", hashed))

        # Geriye dönük uyumluluk: Eski tuzsuz sha256 hash doğrulanabilmeli
        legacy_sha256 = hashlib.sha256(raw_pwd.encode('utf-8')).hexdigest()
        self.assertTrue(verify_password(raw_pwd, legacy_sha256))

        # Test veritabanında eski kullanıcı giriş yapınca otomatik PBKDF2'ye terfi etmeli
        test_db_path = "test_security_audit.db"
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
            except Exception:
                pass

        try:
            db = DatabaseManager(db_path=test_db_path)
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO users (email, password_hash, role) VALUES (?, ?, 'CLIENT')",
                    ("legacy_user@valkyrie.com", legacy_sha256)
                )
                conn.commit()

            # Oturum açma
            ok, msg, udata = db.authenticate_user("legacy_user@valkyrie.com", raw_pwd)
            self.assertTrue(ok)

            # Veritabanındaki hash'i kontrol et -> pbkdf2'ye terfi etmiş olmalı!
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT password_hash FROM users WHERE email = ?", ("legacy_user@valkyrie.com",))
                row = cursor.fetchone()
                self.assertTrue(row["password_hash"].startswith("pbkdf2:sha256:100000$"))
        finally:
            if os.path.exists(test_db_path):
                try:
                    os.remove(test_db_path)
                except Exception:
                    pass

    def test_05_api_session_token_and_admin_authorization(self):
        """Madde 5: Oturum token üretimi, doğrulaması ve admin yetkilendirme mantığı."""
        # Token üretimi
        token = web_server.create_session_token(user_id=42, role="ADMIN", email="admin@valkyrie.com")
        self.assertIn(".", token)

        # Token doğrulama
        payload = web_server.verify_session_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["uid"], 42)
        self.assertEqual(payload["role"], "ADMIN")

        # Geçersiz/manipüle edilmiş token reddedilmeli
        fake_token = token[:-5] + "abcde"
        self.assertIsNone(web_server.verify_session_token(fake_token))

        # Request mocking testleri
        class MockRequest:
            def __init__(self, headers=None, query=None):
                self.headers = headers or {}
                self.query = query or {}

        # 1. Başlıksız istek -> Reddedilmeli
        req_unauth = MockRequest()
        self.assertFalse(web_server.check_admin_authorization(req_unauth))

        # 2. X-Admin-Token ile geçerli ADMIN_SECRET -> Kabul edilmeli
        req_admin_secret = MockRequest(headers={"X-Admin-Token": config.ADMIN_SECRET})
        self.assertTrue(web_server.check_admin_authorization(req_admin_secret))

        # 3. Authorization: Bearer ile geçerli admin session token -> Kabul edilmeli
        req_admin_bearer = MockRequest(headers={"Authorization": f"Bearer {token}"})
        self.assertTrue(web_server.check_admin_authorization(req_admin_bearer))

        # 4. Normal kullanıcı session token'ı admin yetkisi alamaz -> Reddedilmeli
        client_token = web_server.create_session_token(user_id=99, role="USER", email="client@valkyrie.com")
        req_client_bearer = MockRequest(headers={"Authorization": f"Bearer {client_token}"})
        self.assertFalse(web_server.check_admin_authorization(req_client_bearer))

    def test_06_on_chain_payment_verification_and_protection(self):
        """Madde 6: Sahte TxHash engelleme, kullanıcı aidiyeti ve manuel onay kuyruğu."""
        test_db_path = "test_payment_gateway.db"
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
            except Exception:
                pass

        db = DatabaseManager(db_path=test_db_path)
        gateway = CryptoPaymentGateway(db)

        # 1. Geçersiz TxHash reddedilmeli
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            ok, msg, _ = loop.run_until_complete(
                gateway.verify_and_activate_payment(user_id=1, tx_hash="invalid_hash_too_short", network="TRC20")
            )
            self.assertFalse(ok)
            self.assertIn("64 karakterli", msg)

            # 2. Olmayan kullanıcı reddedilmeli
            fake_hash = "a" * 64
            ok, msg, _ = loop.run_until_complete(
                gateway.verify_and_activate_payment(user_id=99999, tx_hash=fake_hash, network="TRC20")
            )
            self.assertFalse(ok)
            self.assertTrue("kullanıcı" in msg.lower() or "id" in msg.lower())

            # 3. Geçerli kullanıcı oluştur ve on-chain başarısız olduğunda PENDING_MANUAL_REVIEW'e düşüşü test et
            db.register_user("buyer@crypto.com", "Password1234!")
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM users WHERE email = 'buyer@crypto.com'")
                user_id = cursor.fetchone()["id"]

            ok, msg, receipt = loop.run_until_complete(
                gateway.verify_and_activate_payment(user_id=user_id, tx_hash=fake_hash, network="TRC20")
            )
            # Blokzincirde doğrulanamadığı için PENDING_MANUAL_REVIEW olmalı
            self.assertFalse(ok)
            self.assertIn("inceleme kuyruğu", msg.lower())

            # 4. Admin manuel onayı testi
            ok_admin, msg_admin = gateway.admin_approve_pending_payment(fake_hash)
            self.assertTrue(ok_admin)
            self.assertIn("onaylandı", msg_admin)

            # 5. Aynı tx_hash tekrar kullanılamaz (anti-replay)
            ok_dup, msg_dup, _ = loop.run_until_complete(
                gateway.verify_and_activate_payment(user_id=user_id, tx_hash=fake_hash, network="TRC20")
            )
            self.assertFalse(ok_dup)
            self.assertIn("kullanılmıştır", msg_dup.lower())

        finally:
            loop.close()
            import gc
            gc.collect()
            if os.path.exists(test_db_path):
                try:
                    os.remove(test_db_path)
                except Exception:
                    pass

if __name__ == "__main__":
    unittest.main()
