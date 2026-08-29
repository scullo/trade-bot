import os
import time
import base64
import hashlib
from datetime import datetime, timezone, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

class SecurityVault:
    """
    VALKYRIE SECURITY VAULT & RISK SHIELD
    AES-256 API Sifreleme, Portfoy Marjin Tavan Kilidi,
    Gunluk Devre Kesici (Circuit Breaker) ve Binance UID Anti-Abuse Modulu.
    """
    def __init__(self, master_secret: str = "Valkyrie-Master-Quantum-Shield-2026-Quant"):
        self.salt = b"valkyrie_quant_vault_salt_2026"
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100000,
        )
        self.key = base64.urlsafe_b64encode(kdf.derive(master_secret.encode('utf-8')))
        self.cipher = Fernet(self.key)
        self._circuit_breaker_active = False
        self._circuit_breaker_date = None

    def encrypt(self, plain_text: str) -> str:
        """Metni AES-256 ile sifreler."""
        if not plain_text:
            return ""
        return self.cipher.encrypt(plain_text.encode('utf-8')).decode('utf-8')

    def decrypt(self, cipher_text: str) -> str:
        """AES-256 ile sifrelenmis metni cozer."""
        if not cipher_text:
            return ""
        try:
            return self.cipher.decrypt(cipher_text.encode('utf-8')).decode('utf-8')
        except Exception as e:
            print(f">> [VAULT DECRYPT ERROR]: {e}")
            return ""

    def hash_binance_uid(self, raw_uid: str) -> str:
        """Binance Hesap UID'sini tekillik icin SHA-256 ile ozetler (Anti-Abuse)."""
        if not raw_uid:
            return ""
        clean = str(raw_uid).strip()
        return hashlib.sha256(clean.encode('utf-8')).hexdigest()

    def check_margin_cap(self, open_positions: dict, new_trade_margin: float, balance: float, max_cap_pct: float = 0.40) -> tuple:
        """
        Kasanin toplam marjin tavan kilidini (%40) denetler.
        Eger acik islemlerin toplami kasanin %40'ini asacaksa yeni islemi engeller.
        """
        current_used_margin = 0.0
        for sym, pos in open_positions.items():
            current_used_margin += float(pos.get('margin', pos.get('margin_usdt', 100.0)))

        projected_margin = current_used_margin + new_trade_margin
        max_allowed_margin = balance * max_cap_pct

        if projected_margin > max_allowed_margin:
            current_pct = (current_used_margin / max(1.0, balance)) * 100.0
            return False, f"Marjin tavan limiti aşıldı: Kullanılan %{current_pct:.1f} / İzin Verilen %{max_cap_pct*100:.0f}"
        return True, "Marjin limiti uygun"

    def check_daily_circuit_breaker(self, history: list, balance: float, max_loss_pct: float = 0.03) -> tuple:
        """
        Gunluk Devre Kesici (Circuit Breaker):
        Gun icinde (TSİ 00:00'dan beri) gerceklesen toplam net kayip %3'u asarsa
        yeni islem acilisini o gun sonuna kadar dondurur.
        """
        now_tsi = datetime.now(timezone(timedelta(hours=3)))
        today_str = now_tsi.strftime("%Y-%m-%d")

        # 00:00'da devre kesiciyi sifirla
        if self._circuit_breaker_date != today_str:
            self._circuit_breaker_date = today_str
            self._circuit_breaker_active = False

        if self._circuit_breaker_active:
            return False, f"🚨 Günlük Devre Kesici AKTİF! (Bugünkü kayıp %{max_loss_pct*100:.0f} sınırına ulaştığı için yeni işlem açılışı 00:00'a kadar durduruldu)"

        today_pnl = 0.0
        for h in history:
            exit_time = h.get('exit_time', '')
            if exit_time and exit_time.startswith(today_str):
                today_pnl += float(h.get('net_pnl', 0.0))

        # Eger bugunku zarar kasanin %3'unu astiysa devre kesiciyi tetikle
        max_allowed_loss = -(balance * max_loss_pct)
        if today_pnl <= max_allowed_loss:
            self._circuit_breaker_active = True
            return False, f"🚨 GÜNLÜK DEVRE KESİCİ DEVREYE GİRDİ: Bugünkü Net Kayıp: ${today_pnl:.2f} (Limit: ${max_allowed_loss:.2f})"

        return True, "Devre kesici guvenli"
