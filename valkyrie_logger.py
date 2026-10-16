"""
🛡️ VALKYRIE QUANT DESK - KURUMSAL MERKEZİ LOGLAMA SİSTEMİ (CENTRAL LOGGING ENGINE)
Tüm alt modüller için yapılandırılmış, döner dosya (RotatingFileHandler) destekli,
RAM ve disk dostu merkezi loglama altyapısı.
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

LOG_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(LOG_DIR, "valkyrie.log")
LOG_LEVEL_NAME = os.environ.get("LOG_LEVEL", "INFO").upper()

LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}
DEFAULT_LEVEL = LOG_LEVEL_MAP.get(LOG_LEVEL_NAME, logging.INFO)

class ValkyrieFormatter(logging.Formatter):
    """Konsol ve dosya için yüksek okunurluklu adli formatlayıcı."""
    FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    def __init__(self):
        super().__init__(fmt=self.FORMAT, datefmt=self.DATE_FORMAT)

_ROOT_INITIALIZED = False

def get_logger(name: str = "valkyrie") -> logging.Logger:
    """Modüle özgü isimlendirilmiş kurumsal logger üretir veya mevcut olanı döndürür."""
    global _ROOT_INITIALIZED

    logger = logging.getLogger(name)
    logger.setLevel(DEFAULT_LEVEL)

    if not _ROOT_INITIALIZED:
        _ROOT_INITIALIZED = True
        root_logger = logging.getLogger()
        root_logger.setLevel(DEFAULT_LEVEL)

        formatter = ValkyrieFormatter()

        # 1. Konsol Çıktısı (StreamHandler)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(DEFAULT_LEVEL)
        console_handler.setFormatter(formatter)
        if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
            root_logger.addHandler(console_handler)

        # 2. Döner Dosya Kaydı (RotatingFileHandler - Maks 10 MB, 5 Yedek)
        try:
            file_handler = RotatingFileHandler(
                LOG_FILE,
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8"
            )
            file_handler.setLevel(DEFAULT_LEVEL)
            file_handler.setFormatter(formatter)
            if not any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers):
                root_logger.addHandler(file_handler)
        except Exception:
            pass

    return logger

# Kolay erişim için ana logger örneği
logger = get_logger("valkyrie")

def log_error_with_context(module_name: str, action: str, err: Exception, level: str = "warning"):
    """Sessizce yutulan hataları bağlam ve adli iz ile loglar."""
    mod_logger = get_logger(module_name)
    msg = f"[{action}] Hata oluştu: {type(err).__name__} - {err}"
    if level == "error":
        mod_logger.error(msg, exc_info=True)
    elif level == "debug":
        mod_logger.debug(msg)
    else:
        mod_logger.warning(msg)
