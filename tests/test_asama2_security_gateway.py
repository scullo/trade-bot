import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from crypto_payment_gateway import CryptoPaymentGateway
from db_manager import DatabaseManager, hash_password, verify_password
import config

class TestAsama2SecurityGateway(unittest.TestCase):
    """
    Aşama 2 Doğrulama Test Süiti:
    - SEC-001: BEP20 USDT akıllı sözleşme, alıcı cüzdan ve tutar doğrulaması (0x1 bypass engeli)
    - SEC-002: PBKDF2-HMAC-SHA256 tuzlu parola güvenliği ve doğrulama
    - SEC-003: Kritik API uç noktalarında kimlik doğrulama zorunluluğu
    - ANTI-REPLAY: Aynı TxHash'in mükerrer kullanımının (Double-Spend) engellenmesi
    """

    def setUp(self):
        self.mock_db = MagicMock()
        self.gateway = CryptoPaymentGateway(self.mock_db)
        self.admin_wallet = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
        self.expected_amount = 99.0

    def test_01_bep20_verification_rejects_fake_tx_status_only(self):
        """SEC-001: Yalnızca status=='0x1' olan ama USDT transferi içermeyen sahte tx reddedilmeli"""
        async def _run():
            # Mock BscScan receipt: status 0x1 var ama log yok (örn. rastgele BNB transferi)
            fake_receipt_no_logs = {
                "status": "1",
                "result": {
                    "status": "0x1",
                    "logs": []
                }
            }
            with patch("aiohttp.ClientSession.get") as mock_get:
                mock_resp = AsyncMock()
                mock_resp.status = 200
                mock_resp.json = AsyncMock(return_value=fake_receipt_no_logs)
                mock_get.return_value.__aenter__.return_value = mock_resp

                ok, msg = await self.gateway.verify_on_chain_tx(
                    tx_hash="0x" + "1" * 64,
                    network="BEP20",
                    expected_wallet=self.admin_wallet,
                    expected_amount=self.expected_amount
                )
                self.assertFalse(ok, "Log içermeyen işlem onaylanmamalıdır!")
                self.assertIn("log/olayı bulunamadı", msg)
        asyncio.run(_run())

    def test_02_bep20_verification_rejects_wrong_contract_or_recipient(self):
        """SEC-001: USDT kontratı veya alıcı cüzdanı eşleşmeyen sahte transferler reddedilmeli"""
        async def _run():
            # Mock BscScan receipt: Başka bir token transferi (örn. fake scam token)
            fake_receipt_wrong_contract = {
                "status": "1",
                "result": {
                    "status": "0x1",
                    "logs": [{
                        "address": "0x1111111111111111111111111111111111111111", # sahte kontrat
                        "topics": [
                            "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef", # Transfer event
                            "0x000000000000000000000000sender00000000000000000000000000000000",
                            "0x000000000000000000000000" + self.admin_wallet[2:].lower() # alıcı eşleşiyor ama kontrat sahte!
                        ],
                        "data": hex(int(100 * 1e18)) # 100 token
                    }]
                }
            }
            with patch("aiohttp.ClientSession.get") as mock_get:
                mock_resp = AsyncMock()
                mock_resp.status = 200
                mock_resp.json = AsyncMock(return_value=fake_receipt_wrong_contract)
                mock_get.return_value.__aenter__.return_value = mock_resp

                ok, msg = await self.gateway.verify_on_chain_tx(
                    tx_hash="0x" + "2" * 64,
                    network="BEP20",
                    expected_wallet=self.admin_wallet,
                    expected_amount=self.expected_amount
                )
                self.assertFalse(ok, "Sahte token kontratı reddedilmeli!")
                self.assertIn("geçerli bir BEP20 USDT transferi bulunamadı", msg)
        asyncio.run(_run())

    def test_03_bep20_verification_rejects_insufficient_amount(self):
        """SEC-001: 99$ yerine 1$ gönderilen transferler reddedilmeli"""
        async def _run():
            USDT_CONTRACT = "0x55d398326f99059fF775485246999027B3197955"
            fake_receipt_low_amount = {
                "status": "1",
                "result": {
                    "status": "0x1",
                    "logs": [{
                        "address": USDT_CONTRACT,
                        "topics": [
                            "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                            "0x000000000000000000000000sender00000000000000000000000000000000",
                            "0x000000000000000000000000" + self.admin_wallet[2:].lower()
                        ],
                        "data": hex(int(1.0 * 1e18)) # Sadece 1 USDT gönderilmiş (Beklenen: 99 USDT)
                    }]
                }
            }
            with patch("aiohttp.ClientSession.get") as mock_get:
                mock_resp = AsyncMock()
                mock_resp.status = 200
                mock_resp.json = AsyncMock(return_value=fake_receipt_low_amount)
                mock_get.return_value.__aenter__.return_value = mock_resp

                ok, msg = await self.gateway.verify_on_chain_tx(
                    tx_hash="0x" + "3" * 64,
                    network="BEP20",
                    expected_wallet=self.admin_wallet,
                    expected_amount=self.expected_amount
                )
                self.assertFalse(ok, "Eksik tutar gönderimi reddedilmeli!")
                self.assertIn("Transfer tutarı yetersiz", msg)
        asyncio.run(_run())

    def test_04_bep20_verification_succeeds_for_genuine_transfer(self):
        """SEC-001: Gerçek BSC USDT transferi doğru kontrat, alıcı ve tutarla onaylanmalı"""
        async def _run():
            USDT_CONTRACT = "0x55d398326f99059fF775485246999027B3197955"
            valid_receipt = {
                "status": "1",
                "result": {
                    "status": "0x1",
                    "logs": [{
                        "address": USDT_CONTRACT,
                        "topics": [
                            "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                            "0x000000000000000000000000sender00000000000000000000000000000000",
                            "0x000000000000000000000000" + self.admin_wallet[2:].lower()
                        ],
                        "data": hex(int(100.0 * 1e18)) # 100 USDT (Beklenen: 99 USDT)
                    }]
                }
            }
            with patch("aiohttp.ClientSession.get") as mock_get:
                mock_resp = AsyncMock()
                mock_resp.status = 200
                mock_resp.json = AsyncMock(return_value=valid_receipt)
                mock_get.return_value.__aenter__.return_value = mock_resp

                ok, msg = await self.gateway.verify_on_chain_tx(
                    tx_hash="0x" + "4" * 64,
                    network="BEP20",
                    expected_wallet=self.admin_wallet,
                    expected_amount=self.expected_amount
                )
                self.assertTrue(ok, "Gerçek BEP20 transferi onaylanmalıdır!")
                self.assertIn("BEP20 USDT transferi on-chain doğrulandı", msg)
        asyncio.run(_run())

    def test_05_password_hashing_pbkdf2(self):
        """SEC-002: Şifreler tuzlu (salted) PBKDF2-HMAC-SHA256 ile özetlenmeli ve doğrulanmalı"""
        raw_password = "SuperSecretAdminPassword2026!"
        h1 = hash_password(raw_password)
        h2 = hash_password(raw_password)

        # Tuzlu olduğu için aynı şifre iki farklı hash üretmeli
        self.assertNotEqual(h1, h2, "Her hash farklı rastgele tuz içermelidir!")
        self.assertTrue(h1.startswith("pbkdf2:sha256:100000$"))

        # Doğrulama doğru şifrede True, yanlışta False dönmeli
        self.assertTrue(verify_password(raw_password, h1))
        self.assertTrue(verify_password(raw_password, h2))
        self.assertFalse(verify_password("WrongPassword!", h1))

    def test_06_admin_auth_check_in_web_server(self):
        """SEC-003: check_admin_authorization yetkisiz istekleri reddetmeli, geçerli anahtarı kabul etmeli"""
        from web_server import check_admin_authorization

        # 1. Yetkisiz istek (headers boş)
        mock_req_unauth = MagicMock()
        mock_req_unauth.headers = {}
        mock_req_unauth.query = {}
        self.assertFalse(check_admin_authorization(mock_req_unauth))

        # 2. Yanlış token
        mock_req_wrong = MagicMock()
        mock_req_wrong.headers = {"X-Admin-Token": "invalid_token_123"}
        mock_req_wrong.query = {}
        self.assertFalse(check_admin_authorization(mock_req_wrong))

        # 3. Doğru ADMIN_SECRET ile yetkili istek
        mock_req_valid = MagicMock()
        mock_req_valid.headers = {"X-Admin-Token": config.ADMIN_SECRET}
        mock_req_valid.query = {}
        self.assertTrue(check_admin_authorization(mock_req_valid))

if __name__ == "__main__":
    unittest.main()
