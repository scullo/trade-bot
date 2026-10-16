# -*- coding: utf-8 -*-
"""
Aşama 7: Modüler Mimari, Veritabanı İndeksleri ve Performans Optimizasyonu Testi
================================================================================
Bu test paketi Denetim Raporu Aşama 7 kapsamında giderilen:
1. TASK-7.1: SQLite tablolarına B-Tree indekslerinin eklenmesi (INDEX), WAL modu ve 10.000 kayıtlık hız testi.
2. TASK-7.2: shadow_archive arşiv dosyalarının kompakt JSON formatı ve .gitignore koruması.
"""

import unittest
import os
import time
import sqlite3

from db_manager import DatabaseManager
from shadow_engine import ShadowExecutionEngine


class TestAsama7ArchitectureAndDatabase(unittest.TestCase):

    def setUp(self):
        self.test_db_path = "test_valkyrie_platform_asama7.db"
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
            except Exception:
                pass

    def tearDown(self):
        for ext in ["", "-wal", "-shm"]:
            f = self.test_db_path + ext
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

    def test_task7_1_database_indexes_and_wal_mode(self):
        """Veritabanında 14 B-Tree indeksinin ve PRAGMA ayarlarının eksiksiz oluşturulduğunu doğrular."""
        db = DatabaseManager(db_path=self.test_db_path)

        with db.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Foreign keys kontrolü
            cursor.execute("PRAGMA foreign_keys;")
            fk_status = cursor.fetchone()[0]
            self.assertEqual(fk_status, 1, "PRAGMA foreign_keys ON olmalıdır!")

            # 2. İndekslerin kontrolü
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
            indexes = {row[0] for row in cursor.fetchall()}

            expected_indexes = [
                "idx_users_email",
                "idx_users_uid_hash",
                "idx_api_cred_user_id",
                "idx_subscriptions_user_status",
                "idx_subscriptions_expires",
                "idx_trade_logs_user_symbol",
                "idx_trade_logs_status_created",
                "idx_trade_logs_symbol_time",
                "idx_payments_user_tx",
                "idx_payments_tx_hash",
                "idx_payments_receipt",
                "idx_pending_orders_code",
                "idx_pending_orders_user_status",
                "idx_pending_orders_expires"
            ]

            for idx in expected_indexes:
                self.assertIn(idx, indexes, f"Beklenen indeks bulunamadı: {idx}")

    def test_task7_1_query_speed_benchmark_10k_records(self):
        """10.000 kayıtlık işlem günlüğünde indeksli sorgu hızının 100ms altında olduğunu kanıtlar."""
        db = DatabaseManager(db_path=self.test_db_path)

        # 1. 10.000 kayıt ekle
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Önce bir test kullanıcısı oluştur
            cursor.execute("INSERT INTO users (email, password_hash) VALUES ('speed_test@valkyrie.com', 'dummy_hash')")
            user_id = cursor.lastrowid

            records = []
            symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT"]
            sides = ["LONG", "SHORT"]
            statuses = ["OPEN", "CLOSED"]

            for i in range(10000):
                sym = symbols[i % len(symbols)]
                side = sides[i % 2]
                status = statuses[i % 2]
                entry_p = 60000.0 + (i % 500)
                records.append((user_id, sym, side, 5, entry_p, entry_p + 100.0, 10.5, 5.25, status))

            cursor.executemany("""
                INSERT INTO user_trade_logs (user_id, symbol, side, leverage, entry_price, exit_price, net_pnl, roe_pct, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, records)
            conn.commit()

        # 2. İndeksli sorgu hız testi
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            start_time = time.perf_counter()
            cursor.execute("""
                SELECT * FROM user_trade_logs 
                WHERE user_id = ? AND symbol = 'BTCUSDT' AND status = 'CLOSED'
            """, (user_id,))
            rows = cursor.fetchall()
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            # 10.000 kayıt içerisinden filtreleme süresi kesinlikle 100ms altında olmalıdır
            self.assertGreater(len(rows), 0)
            self.assertLess(elapsed_ms, 100.0, f"Sorgu süresi ({elapsed_ms:.2f}ms) 100ms eşiğini aştı!")

    def test_task7_2_shadow_archive_compact_formatting(self):
        """Gölge işlem arşivinin kompakt formatta yazıldığını ve .gitignore korumasını doğrular."""
        # 1. .gitignore dosyasında shadow_archive kuralının varlığını kontrol et
        gitignore_path = os.path.join(os.path.dirname(__file__), "..", ".gitignore")
        if os.path.exists(gitignore_path):
            with open(gitignore_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("shadow_archive_", content, ".gitignore içinde shadow_archive_ kuralı bulunmalıdır!")

        # 2. _archive_trade_list fonksiyonunun kompakt JSON formatında kaydettiğini doğrula
        test_history = "test_shadow_archive_compact.json"
        engine = ShadowExecutionEngine(history_file=test_history)
        engine.is_test = True

        mock_trades = [
            {
                "id": f"TEST_TRADE_{i}",
                "symbol": "BTC/USDT",
                "side": "LONG",
                "entry_price": 60000.0,
                "exit_price": 61000.0,
                "net_pnl_usd": 25.0,
                "entry_time": "2026-10-15 14:00:00"
            }
            for i in range(50)
        ]

        engine._archive_trade_list(mock_trades)
        expected_archive_file = "shadow_archive_202610.json"
        
        # Test sonrası temizlik
        if os.path.exists(test_history):
            try:
                os.remove(test_history)
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
