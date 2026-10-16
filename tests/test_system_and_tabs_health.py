import unittest
import asyncio
import os
import sys
import json
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

# Proje ana dizinini sys.path'e ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from market_data import MarketDataManager
from paper_trader import PaperTrader
from live_trader import LiveTrader
from trader_manager import TraderManager
from telegram_bot import TelegramNotifier
from strategy import StrategyEngine
import web_server


class TestSystemAndTabsHealth(AioHTTPTestCase):
    """
    Sistemin, Sekmelerin ve REST API Uç Noktalarının Sağlık ve Doğruluk Denetimi.
    Tüm dashboard sekmelerinin veri sağlayan backend servisleriyle kusursuz çalıştığını test eder.
    """

    async def get_application(self):
        # Test için MarketData ve bileşenler
        symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        self.market_data = MarketDataManager(all_symbols=symbols, active_symbols=symbols)
        self.paper_trader = PaperTrader(initial_balance=10000.0)
        self.paper_trader.balance = 10000.0
        self.paper_trader.secured_profit_reserve = 0.0
        self.paper_trader.open_positions.clear()
        self.paper_trader.history.clear()
        self.paper_trader.save_history = lambda critical=False: None
        self.paper_trader.save_local_history = lambda: None

        self.live_trader = LiveTrader()
        self.trader_manager = TraderManager(self.paper_trader, self.live_trader)
        self.trader_manager.mode = "DEMO"
        self.notifier = TelegramNotifier()
        self.strategy = StrategyEngine(self.trader_manager, self.notifier, market_data=self.market_data)

        # web_server app oluşturucu
        app = web.Application()
        web_server.market_data = self.market_data
        web_server.trader_manager = self.trader_manager
        web_server.notifier = self.notifier
        web_server.live_trader = self.live_trader
        web_server.strategy = self.strategy

        # web_server route kayıtlarını yap (arkaplan daemon'ları başlatmadan)
        await web_server.start_server(
            self.market_data,
            self.trader_manager,
            self.notifier,
            live_trader=self.live_trader,
            strategy=self.strategy,
            app=app,
            start_listener=False
        )
        return app

    @unittest_run_loop
    async def test_01_health_and_ping(self):
        """Health ve ping kontrolü"""
        resp = await self.client.request("GET", "/health")
        self.assertEqual(resp.status, 200)
        text = await resp.text()
        self.assertEqual(text, "OK")

        resp2 = await self.client.request("GET", "/ping")
        self.assertEqual(resp2.status, 200)
        text2 = await resp2.text()
        self.assertEqual(text2, "OK")

    @unittest_run_loop
    async def test_02_index_html_rendered_with_all_tabs(self):
        """Dashboard HTML sayfası ve tüm 18 sekmenin DOM elemanlarının varlığı"""
        resp = await self.client.request("GET", "/")
        self.assertEqual(resp.status, 200)
        html = await resp.text()

        # 18 Sekme buton ve ID kontrolü
        tab_ids = [
            "tab-btn-cockpit",
            "tab-btn-positions",
            "tab-btn-radar",
            "tab-btn-ledger",
            "tab-btn-forensic",
            "tab-btn-persona",
            "tab-btn-shadow",
            "tab-btn-evolution",
            "tab-btn-funding",
            "tab-btn-cvd",
            "tab-btn-whale",
            "tab-btn-institutional",
            "tab-btn-health",
            "tab-btn-admin",
            "tab-btn-macro",
            "tab-btn-wallstreet",
            "tab-btn-institutional-ratings",
            "tab-btn-macro_evolution"
        ]
        for tid in tab_ids:
            self.assertIn(tid, html, f"Dashboard sekme butonu '{tid}' HTML içinde bulunamadı!")

    @unittest_run_loop
    async def test_03_api_data_clean_wallet_state(self):
        """Sekmeler: Cockpit, Positions, Ledger -> /api/data sıfırlanmış kasa durumu kontrolü"""
        resp = await self.client.request("GET", "/api/data")
        self.assertEqual(resp.status, 200)
        data = await resp.json()

        # Sıfırlanmış kasa doğrulama
        self.assertAlmostEqual(data.get("balance", 0.0), 10000.0, places=2)
        self.assertEqual(len(data.get("open_positions", {})), 0, "Açık pozisyonlar boş olmalıdır!")
        self.assertEqual(len(data.get("history", [])), 0, "İşlem defteri geçmişi boş olmalıdır!")

    @unittest_run_loop
    async def test_04_api_specialized_engine_tabs(self):
        """Sekmeler: Shadow, DNA Evolution, Macro Oracle, Wall Street, Institutional Intel"""
        # Shadow masası sekmesi
        resp_shadow = await self.client.request("GET", "/api/shadow_data")
        self.assertEqual(resp_shadow.status, 200)

        # DNA evrim sekmesi
        resp_dna = await self.client.request("GET", "/api/quant_evolution_data")
        self.assertEqual(resp_dna.status, 200)

        # Makro Kehanet sekmesi
        resp_macro = await self.client.request("GET", "/api/macro_oracle")
        self.assertEqual(resp_macro.status, 200)

        # Wall Street terminali sekmesi
        resp_ws = await self.client.request("GET", "/api/wallstreet_terminal")
        self.assertEqual(resp_ws.status, 200)

        # Kurumsal istihbarat sekmesi
        resp_inst = await self.client.request("GET", "/api/institutional_intel")
        self.assertEqual(resp_inst.status, 200)

        # Sistem sağlığı sekmesi
        resp_health = await self.client.request("GET", "/api/institutional_health")
        self.assertEqual(resp_health.status, 200)

        # Makro ELO kaynak evrimi sekmesi
        resp_mevo = await self.client.request("GET", "/api/macro_evolution")
        self.assertEqual(resp_mevo.status, 200)

    @unittest_run_loop
    async def test_05_api_live_status(self):
        """Sekmeler: Canlı işlem modu ve konfigürasyon durumu kontrolü"""
        resp = await self.client.request("GET", "/api/live/status")
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertEqual(data.get("status"), "ok")
        self.assertIn("mode", data)
        self.assertIn("margin_type", data)
        self.assertIn("leverage", data)


if __name__ == "__main__":
    unittest.main()
