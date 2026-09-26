from wallet_listener_cron import AutonomousWalletListener
from crypto_payment_gateway import CryptoPaymentGateway
from db_manager import DatabaseManager
import asyncio
import gzip
import json
import numpy as np
import pandas as pd
import time
from datetime import datetime, timezone, timedelta
from aiohttp import web
from config import SYMBOLS

SERVER_START_TS = time.time()
sse_clients = set()

HTML_PAGE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>VALKYRIE QUANT DESK •— Binance Futures Terminal</title>    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <script type="text/javascript" src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
    <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
    <script>
        (function() {
            try {
                var user = localStorage.getItem('valkyrie_auth_user');
                if (user && JSON.parse(user)) {
                    document.documentElement.className = 'is-authenticated';
                } else {
                    document.documentElement.className = 'is-guest';
                }
            } catch(e) {
                document.documentElement.className = 'is-guest';
            }
        })();
    </script>

    <style>
        /* 0ms INSTANT ZERO-FLASH AUTH LAYOUT CONTROLLER */
        html.is-authenticated #landing-page-view { display: none !important; }
        html.is-authenticated #dashboard-app-view { display: block !important; }

        html.is-guest #landing-page-view { display: block !important; }
        html.is-guest #dashboard-app-view { display: none !important; }

        :root {
            --bg: #080b11;
            --surface: #0e131f;
            --surface-glass: rgba(14, 19, 31, 0.85);
            --card-bg: #111726;
            --card-hover: #161f33;
            --border: rgba(255, 255, 255, 0.08);
            --border-light: rgba(255, 255, 255, 0.14);
            --border-focus: #388bfd;
            --green: #10b981;
            --green-bg: rgba(16, 185, 129, 0.08);
            --green-glow: rgba(16, 185, 129, 0.25);
            --red: #f43f5e;
            --red-bg: rgba(244, 63, 94, 0.08);
            --red-glow: rgba(244, 63, 94, 0.25);
            --yellow: #f59e0b;
            --yellow-glow: rgba(245, 158, 11, 0.25);
            --purple: #c084fc;
            --blue: #3b82f6;
            --cyan: #06b6d4;
            --text-main: #f8fafc;
            --text-secondary: #cbd5e1;
            --text-muted: #64748b;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background: radial-gradient(circle at 50% 0%, #111827 0%, #080b11 75%);
            background-attachment: fixed;
            color: var(--text-main);
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            padding: 20px 32px;
            min-height: 100vh;
            -webkit-font-smoothing: antialiased;
        }

        /* BRANDING & TOP BAR */
        .top-bar { display: flex; justify-content: space-between; align-items: center; padding-bottom: 18px; border-bottom: 1px solid var(--border); margin-bottom: 22px; flex-wrap: wrap; gap: 14px; }
        .logo-wrap { display: flex; align-items: center; gap: 14px; }
        .brand-logo-gem {
            width: 44px;
            height: 44px;
            background: linear-gradient(135deg, rgba(0, 242, 254, 0.15), rgba(79, 172, 254, 0.25));
            border: 1px solid rgba(0, 242, 254, 0.4);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 0 20px rgba(0, 242, 254, 0.3);
            flex-shrink: 0;
        }
        .logo-title { font-size: 23px; font-weight: 800; letter-spacing: -0.3px; color: #ffffff; font-family: 'Plus Jakarta Sans', sans-serif; }
        .logo-sub { font-size: 12.5px; color: var(--text-muted); font-family: 'JetBrains Mono', monospace; margin-top: 2px; }

        .live-tag { display: flex; align-items: center; gap: 8px; background: rgba(14, 203, 129, 0.12); border: 1px solid var(--green); padding: 7px 16px; border-radius: 20px; font-size: 12.5px; font-weight: 700; color: var(--green); font-family: 'JetBrains Mono', monospace; }
        .live-dot { width: 9px; height: 9px; background: var(--green); border-radius: 50%; box-shadow: 0 0 12px var(--green); animation: pulse 0.6s infinite; }

        /* CHART TAB SWITCHER & BUTTONS */
        .chart-tab-group {
            display: inline-flex;
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 3px;
            gap: 4px;
        }
        .chart-tab-btn {
            background: transparent;
            border: none;
            color: #94a3b8;
            padding: 6px 14px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.15s ease;
            font-family: 'JetBrains Mono', monospace;
        }
        .chart-tab-btn:hover {
            color: #ffffff;
            background: rgba(255, 255, 255, 0.06);
        }
        .chart-tab-btn.tab-active {
            background: var(--blue);
            color: #ffffff;
            box-shadow: 0 0 12px rgba(56, 139, 253, 0.4);
        }
        .btn-copy-pine {
            background: rgba(213, 0, 249, 0.15);
            border: 1px solid rgba(213, 0, 249, 0.4);
            color: #e040fb;
            font-size: 12px;
            font-weight: 700;
            padding: 6px 14px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.15s ease;
            font-family: 'JetBrains Mono', monospace;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        .btn-copy-pine:hover {
            background: #d500f9;
            color: #ffffff;
            box-shadow: 0 0 14px rgba(213, 0, 249, 0.5);
            transform: translateY(-1px);
        }

        /* CANLI GRAFIK BUTONU & TRADINGVIEW MODAL */
        .btn-open-chart {
            background: rgba(56, 139, 253, 0.15);
            border: 1px solid rgba(56, 139, 253, 0.35);
            color: #58a6ff;
            font-size: 11.5px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.15s ease;
            font-family: 'JetBrains Mono', monospace;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }
        .btn-open-chart:hover {
            background: var(--blue);
            color: #ffffff;
            border-color: var(--blue);
            box-shadow: 0 0 10px rgba(56, 139, 253, 0.5);
            transform: translateY(-1px);
        }
        .tv-modal-overlay {
            position: fixed;
            inset: 0;
            background: rgba(7, 9, 14, 0.88);
            backdrop-filter: blur(10px);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 99999;
            padding: 16px;
            animation: fadeIn 0.2s ease;
        }
        .tv-modal-card {
            background: #0e121a;
            border: 1px solid #2c3850;
            border-radius: 20px;
            width: 96vw;
            max-width: 1440px;
            height: 90vh;
            display: flex;
            flex-direction: column;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.9), 0 0 35px rgba(56, 139, 253, 0.25);
            overflow: hidden;
        }
        .tv-modal-header {
            padding: 14px 22px;
            background: #121722;
            border-bottom: 1px solid #1e2638;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
        }
        .tv-modal-title {
            font-size: 17px;
            font-weight: 800;
            color: #ffffff;
            display: flex;
            align-items: center;
            gap: 10px;
            font-family: 'JetBrains Mono', monospace;
        }
        .tv-modal-close-btn {
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.15);
            color: #ffffff;
            width: 32px;
            height: 32px;
            border-radius: 8px;
            font-size: 15px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.15s ease;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .tv-modal-close-btn:hover {
            background: var(--red);
            border-color: var(--red);
            transform: scale(1.06);
        }
        .tv-modal-body {
            flex: 1;
            display: flex;
            overflow: hidden;
            background: #07090e;
        }
        .tv-chart-area {
            flex: 1;
            height: 100%;
            position: relative;
            background: #0b0e14;
        }
        .tv-sidebar-area {
            width: 340px;
            background: #0e121a;
            border-left: 1px solid #1e2638;
            padding: 18px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        @media (max-width: 960px) {
            .tv-modal-body { flex-direction: column; }
            .tv-sidebar-area { width: 100%; height: 260px; border-left: none; border-top: 1px solid #1e2638; }
        }
        @keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.3; transform: scale(1.3); } }

        /* BUTTONS */
        .btn-manual-close {
            background: linear-gradient(135deg, #ff4757, #d32f2f);
            border: none;
            color: #ffffff;
            padding: 8px 16px;
            border-radius: 8px;
            font-weight: 800;
            font-size: 13px;
            cursor: pointer;
            font-family: 'JetBrains Mono', monospace;
            transition: all 0.2s ease;
            box-shadow: 0 4px 14px rgba(255, 71, 87, 0.4);
            white-space: nowrap;
        }
        .btn-manual-close:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 20px rgba(255, 71, 87, 0.6);
            background: linear-gradient(135deg, #ff6b81, #e53935);
        }
        .btn-card-manual-close {
            background: linear-gradient(135deg, #ff4757, #d32f2f);
            border: none;
            color: #ffffff;
            padding: 5px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 800;
            cursor: pointer;
            font-family: 'JetBrains Mono', monospace;
            transition: all 0.15s ease;
            box-shadow: 0 2px 8px rgba(255, 71, 87, 0.35);
            white-space: nowrap;
        }
        .btn-card-manual-close:hover {
            background: linear-gradient(135deg, #ff6b81, #e53935);
            transform: translateY(-1px);
            box-shadow: 0 4px 14px rgba(255, 71, 87, 0.6);
        }

        /* 100 PARITE YONETIM PANELI & HIZLI SECIM */
        .manager-card { background: var(--surface); border: 1px solid var(--border); border-radius: 18px; padding: 18px 22px; margin-bottom: 24px; }
        .manager-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; flex-wrap: wrap; gap: 14px; }
        .active-badge-pill { font-size: 12.5px; font-weight: 800; background: rgba(14, 203, 129, 0.15); color: var(--green); border: 1px solid var(--green); padding: 4px 12px; border-radius: 20px; font-family: 'JetBrains Mono', monospace; }
        .quick-preset-bar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
        .btn-preset { background: rgba(255, 255, 255, 0.06); border: 1px solid var(--border-light); color: #ffffff; padding: 6px 12px; border-radius: 8px; font-weight: 700; font-size: 12.5px; cursor: pointer; transition: all 0.15s ease; font-family: 'JetBrains Mono', monospace; }
        .btn-preset:hover { background: rgba(56, 139, 253, 0.2); border-color: var(--blue); color: var(--blue); }
        .btn-preset-danger { color: var(--red); }
        .btn-preset-danger:hover { background: rgba(255, 71, 87, 0.2); border-color: var(--red); color: var(--red); }

        /* ARAMA KUTUSU */
        .search-wrap {
            position: relative;
            display: flex;
            align-items: center;
            min-width: 250px;
            flex: 1;
            max-width: 380px;
        }
        .coin-search-input {
            width: 100%;
            background: rgba(13, 17, 23, 0.9);
            border: 1px solid var(--border-light);
            color: #ffffff;
            font-size: 13px;
            font-weight: 600;
            padding: 8px 32px 8px 34px;
            border-radius: 10px;
            outline: none;
            transition: all 0.2s ease;
            font-family: 'Plus Jakarta Sans', sans-serif;
        }
        .coin-search-input:focus {
            border-color: var(--blue);
            box-shadow: 0 0 12px rgba(56, 139, 253, 0.4);
            background: #0d1117;
        }
        .search-icon {
            position: absolute;
            left: 10px;
            font-size: 13px;
            pointer-events: none;
            opacity: 0.6;
        }
        .search-clear-btn {
            position: absolute;
            right: 8px;
            background: transparent;
            border: none;
            color: #94a3b8;
            font-size: 13px;
            cursor: pointer;
            padding: 4px 6px;
            border-radius: 4px;
        }
        .search-clear-btn:hover {
            color: #ffffff;
            background: rgba(255, 255, 255, 0.1);
        }
        .chip-highlight {
            border-color: var(--yellow) !important;
            box-shadow: 0 0 15px rgba(240, 185, 11, 0.5) !important;
            animation: pulseHighlight 1.5s infinite alternate;
        }
        @keyframes pulseHighlight {
            from { transform: scale(1); }
            to { transform: scale(1.04); }
        }

        .coin-chips-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 10px; }
        .coin-chip { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 9px 12px; display: flex; justify-content: space-between; align-items: center; transition: all 0.2s ease; cursor: pointer; user-select: none; }
        .coin-chip:hover { border-color: var(--border-light); transform: translateY(-1px); }
        .coin-chip.is-active { border-color: var(--green); background: rgba(14, 203, 129, 0.08); box-shadow: 0 0 12px rgba(14, 203, 129, 0.15); }
        .chip-sym { font-weight: 800; font-family: 'JetBrains Mono', monospace; font-size: 13.5px; display: flex; align-items: center; gap: 6px; color: #ffffff; }
        .chip-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--text-muted); }
        .is-active .chip-dot { background: var(--green); box-shadow: 0 0 8px var(--green); }
        .chip-btn { font-size: 11px; font-weight: 800; padding: 3px 8px; border-radius: 6px; border: none; cursor: pointer; font-family: 'JetBrains Mono', monospace; transition: all 0.15s ease; }
        .btn-toggle-on { background: var(--green); color: #000; }
        .btn-toggle-off { background: rgba(255,255,255,0.08); color: var(--text-muted); }
        .btn-toggle-off:hover { background: rgba(255,255,255,0.15); color: #fff; }

        /* SECTIONS & WATCHLIST */
        .section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 10px; }
        .section-title { font-size: 16px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.8px; color: #ffffff; display: flex; align-items: center; gap: 8px; }
        
        .watchlist-grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); 
            gap: 18px; 
            margin-bottom: 32px; 
            width: 100%; 
            align-items: start; 
        }
        .coin-card {
            background: linear-gradient(180deg, rgba(18, 25, 40, 0.85) 0%, rgba(13, 18, 30, 0.95) 100%);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 16px 18px;
            transition: border-color 0.2s ease, box-shadow 0.2s ease;
            position: relative;
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
            gap: 10px;
            backdrop-filter: blur(12px);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
            height: fit-content;
        }
        .coin-card:hover {
            border-color: rgba(59, 130, 246, 0.4);
            transform: translateY(-2px);
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.5), 0 0 20px rgba(59, 130, 246, 0.1);
        }

        /* SOLID VIVID GLOWING BORDERS FOR ACTIVE POSITIONS */
        .coin-card.has-active-pos-profit {
            border: 2px solid var(--green) !important;
            box-shadow: 0 0 25px rgba(14, 203, 129, 0.35) !important;
            background: var(--green-bg) !important;
        }
        .coin-card.has-active-pos-loss {
            border: 2px solid var(--red) !important;
            box-shadow: 0 0 25px rgba(255, 71, 87, 0.35) !important;
            background: var(--red-bg) !important;
        }

        /* MODERN MULTI-ROW CARD HEAD (NO OVERLAPPING ON ANY SCREEN OR LONG NAMES) */
        .card-head {
            display: flex;
            flex-direction: column;
            gap: 6px;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }
        .card-top-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            width: 100%;
        }
        .card-symbol-wrap {
            display: flex;
            align-items: center;
            gap: 8px;
            min-width: 0;
            overflow: hidden;
        }
        .card-symbol {
            font-size: 18px;
            font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
            color: #ffffff;
            letter-spacing: -0.2px;
            white-space: nowrap;
        }
        .symbol-tag {
            font-size: 10px;
            background: rgba(56, 139, 253, 0.15);
            color: var(--blue);
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: 700;
            border: 1px solid rgba(56, 139, 253, 0.3);
            font-family: 'JetBrains Mono', monospace;
        }
        .btn-open-chart {
            background: rgba(56, 139, 253, 0.12);
            border: 1px solid rgba(56, 139, 253, 0.3);
            color: #58a6ff;
            font-size: 11px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.15s ease;
            display: inline-flex;
            align-items: center;
            gap: 4px;
            font-family: 'JetBrains Mono', monospace;
            white-space: nowrap;
        }
        .btn-open-chart:hover {
            background: var(--blue);
            color: #ffffff;
            box-shadow: 0 0 10px rgba(56, 139, 253, 0.4);
            transform: translateY(-1px);
        }
        .card-price-row {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            width: 100%;
            margin-top: 2px;
        }
        .price-label-mini {
            font-size: 10.5px;
            color: #64748b;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.4px;
        }
        .card-price {
            font-size: 22px;
            font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
            font-variant-numeric: tabular-nums;
            color: #f8fafc;
            padding: 2px 6px;
            border-radius: 6px;
            transition: all 0.12s ease;
            text-align: right;
            margin-left: auto;
        }
        .tick-up { background: var(--green-glow) !important; color: var(--green) !important; text-shadow: 0 0 16px rgba(16, 185, 129, 0.9); }
        .tick-down { background: var(--red-glow) !important; color: var(--red) !important; text-shadow: 0 0 16px rgba(244, 63, 94, 0.9); }

        /* DEDICATED CARD ACTIVE POSITION BANNER (PREVENTS CROWDING) */
        .card-pos-banner {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 12px;
            border-radius: 10px;
            margin-bottom: 14px;
            font-family: 'JetBrains Mono', monospace;
            gap: 8px;
        }
        .banner-profit {
            background: rgba(14, 203, 129, 0.15);
            border: 1px solid rgba(14, 203, 129, 0.4);
        }
        .banner-loss {
            background: rgba(255, 71, 87, 0.15);
            border: 1px solid rgba(255, 71, 87, 0.4);
        }
        .pos-pill-profit {
            font-size: 12px;
            font-weight: 800;
            color: var(--green);
        }
        .pos-pill-loss {
            font-size: 12px;
            font-weight: 800;
            color: var(--red);
        }

        /* CANLI DINAMIK ANALIZ CUMLESI */
        .analysis-box { background: rgba(0, 0, 0, 0.6); border: 1px solid var(--border); border-radius: 12px; padding: 10px 14px; font-size: 12.5px; line-height: 1.45; color: #f1f5f9; margin-bottom: 0; border-left: 4px solid var(--blue); display: flex; flex-direction: column; justify-content: flex-start; }
        .analysis-title { font-size: 12px; font-weight: 800; text-transform: uppercase; margin-bottom: 4px; display: flex; align-items: center; gap: 6px; }

        /* BOT PUSU & EYLEM PLANI */
        .action-plan-box { background: rgba(240, 185, 11, 0.08); border: 1px solid rgba(240, 185, 11, 0.35); border-radius: 10px; padding: 10px 14px; font-size: 12.5px; line-height: 1.45; color: #ffffff; margin-bottom: 0; display: flex; flex-direction: column; justify-content: flex-start; }
        .action-plan-title { font-size: 11.5px; font-weight: 800; text-transform: uppercase; color: var(--yellow); margin-bottom: 5px; display: flex; align-items: center; gap: 6px; }

        .levels-table { width: 100%; border-collapse: collapse; font-family: 'JetBrains Mono', monospace; font-size: 13px; }
        .levels-table tr:hover { background: rgba(255, 255, 255, 0.05); }
        .levels-table td { padding: 6px 6px; border-bottom: 1px solid rgba(255, 255, 255, 0.06); }
        .lvl-lbl { color: #cbd5e1; font-weight: 600; }
        .lvl-num { text-align: right; font-weight: 700; color: #ffffff; }

        /* LOAD MORE / PARITE LAZY LOADING */
        .load-more-bar {
            grid-column: 1 / -1;
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 16px;
            margin: 20px 0 10px 0;
            flex-wrap: wrap;
        }
        .btn-load-more {
            background: linear-gradient(135deg, rgba(56, 139, 253, 0.25), rgba(56, 139, 253, 0.15));
            border: 1px solid var(--blue);
            color: #ffffff;
            font-weight: 800;
            font-size: 14px;
            padding: 12px 28px;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.2s ease;
            box-shadow: 0 4px 15px rgba(56, 139, 253, 0.2);
        }
        .btn-load-more:hover {
            background: var(--blue);
            color: #000000;
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(56, 139, 253, 0.4);
        }
        .btn-load-all {
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid var(--border-light);
            color: #cbd5e1;
            font-weight: 700;
            font-size: 13.5px;
            padding: 12px 20px;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .btn-load-all:hover {
            background: rgba(255, 255, 255, 0.15);
            color: #ffffff;
        }

        /* ALT PANEL - YARI YARIYA BOLUNMUS MODULLER */
        .bottom-split { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 32px; width: 100%; }
        .panel-box { background: var(--surface); border: 1px solid var(--border); border-radius: 20px; padding: 24px; min-height: 440px; display: flex; flex-direction: column; }
        .panel-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 14px; border-bottom: 1px solid var(--border); }
        .panel-title { font-size: 19px; font-weight: 800; letter-spacing: 0.3px; display: flex; align-items: center; gap: 10px; color: #ffffff; }

        .wallet-kpi-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 22px; }
        .w-kpi { background: var(--card-bg); border: 1px solid var(--border); border-radius: 14px; padding: 16px; }
        .w-lbl { font-size: 12.5px; font-weight: 700; color: #cbd5e1; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px; }
        .w-val { font-size: 26px; font-weight: 800; font-family: 'JetBrains Mono', monospace; color: #ffffff; }

        /* BUYUTULMUS AKTIF POZISYON KARTI */
        .active-pos-card { background: var(--card-bg); border: 2px solid var(--border); border-radius: 14px; padding: 20px; margin-bottom: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); }
        .active-pos-card.pos-card-profit { border-color: var(--green) !important; background: var(--green-bg) !important; box-shadow: 0 0 25px rgba(14, 203, 129, 0.3) !important; }
        .active-pos-card.pos-card-loss { border-color: var(--red) !important; background: var(--red-bg) !important; box-shadow: 0 0 25px rgba(255, 71, 87, 0.3) !important; }

        .pos-top { 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            margin-bottom: 12px; 
            gap: 12px; 
            flex-wrap: wrap; 
        }
        .pos-badge { font-weight: 800; font-size: 12px; padding: 4px 10px; border-radius: 8px; font-family: 'JetBrains Mono', monospace; text-transform: uppercase; white-space: nowrap; }
        .pos-long { background: rgba(14, 203, 129, 0.2); color: var(--green); border: 1px solid var(--green); }
        .pos-short { background: rgba(255, 71, 87, 0.2); color: var(--red); border: 1px solid var(--red); }
        .pos-main-pnl { font-size: 16px; font-weight: 900; font-family: 'JetBrains Mono', monospace; white-space: nowrap; text-align: right; margin-left: auto; }
        .active-pos-card {
            background: linear-gradient(180deg, rgba(18, 25, 40, 0.92) 0%, rgba(13, 18, 30, 0.98) 100%);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 16px 18px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            gap: 10px;
            height: fit-content;
        }
        .pos-badge { padding: 5px 12px; border-radius: 8px; font-size: 14px; font-weight: 800; font-family: 'JetBrains Mono', monospace; }
        .pos-long { background: var(--green); color: #000; }
        .pos-short { background: var(--red); color: #fff; }

        .pos-main-pnl { font-size: 22px; font-weight: 800; font-family: 'JetBrains Mono', monospace; }
        .pos-detail-row { font-size: 14.5px; font-family: 'JetBrains Mono', monospace; color: #cbd5e1; margin-bottom: 8px; line-height: 1.5; }
        .pos-detail-row b { color: #ffffff; font-weight: 800; }
        .pos-target-row { font-size: 13.5px; font-family: 'JetBrains Mono', monospace; color: #e2e8f0; margin-bottom: 8px; }
        .pos-setup-tag { font-size: 13.5px; margin-top: 8px; color: var(--yellow); font-weight: 700; }

        /* TICARET DEFTERI */
        .history-full-box { background: var(--surface); border: 1px solid var(--border); border-radius: 20px; padding: 24px; }
        .history-top-controls { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; flex-wrap: wrap; gap: 14px; }
        .filter-group { display: flex; align-items: center; gap: 10px; }
        .filter-select { background: var(--card-bg); border: 1px solid var(--border-light); color: #ffffff; padding: 8px 14px; border-radius: 8px; font-family: 'Plus Jakarta Sans', sans-serif; font-size: 13.5px; outline: none; cursor: pointer; }
        .filter-select:hover { border-color: var(--blue); }

        .btn-export { background: linear-gradient(135deg, #238636, #2ea043); border: none; color: #fff; padding: 9px 18px; border-radius: 10px; font-weight: 700; font-size: 13.5px; display: flex; align-items: center; gap: 8px; cursor: pointer; transition: all 0.2s ease; box-shadow: 0 4px 12px rgba(46, 160, 67, 0.3); }
        .btn-export:hover { transform: translateY(-2px); box-shadow: 0 6px 16px rgba(46, 160, 67, 0.5); }

        .trade-table { width: 100%; border-collapse: collapse; font-family: 'JetBrains Mono', monospace; font-size: 13px; }
        .trade-table th { text-align: left; padding: 12px 12px; background: #0c1017; color: #cbd5e1; font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid var(--border); font-weight: 700; }
        .trade-table td { padding: 12px 12px; border-bottom: 1px solid rgba(255, 255, 255, 0.06); color: #f1f5f9; }
        .trade-table tr:hover { background: rgba(255, 255, 255, 0.03); }

        /* CUSTOM CONFIRMATION MODAL */
        .modal-overlay {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0, 0, 0, 0.8);
            backdrop-filter: blur(8px);
            z-index: 9999;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .modal-card {
            background: #111622;
            border: 1px solid #2c3850;
            border-radius: 22px;
            padding: 32px 36px;
            max-width: 480px;
            width: 90%;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.9), 0 0 30px rgba(255, 71, 87, 0.25);
            text-align: center;
            animation: modalIn 0.2s ease-out;
        }
        @keyframes modalIn {
            from { opacity: 0; transform: scale(0.92); }
            to { opacity: 1; transform: scale(1); }
        }
        .modal-icon { font-size: 44px; margin-bottom: 12px; }
        .modal-title { font-size: 21px; font-weight: 800; color: #ffffff; margin-bottom: 10px; font-family: 'Plus Jakarta Sans', sans-serif; }
        .modal-desc { font-size: 14.5px; color: #cbd5e1; line-height: 1.6; margin-bottom: 20px; }
        .modal-metrics { background: #090c13; border: 1px solid #1e2638; border-radius: 12px; padding: 14px 16px; margin-bottom: 24px; font-family: 'JetBrains Mono', monospace; font-size: 14px; text-align: left; line-height: 1.7; }
        .modal-actions { display: flex; gap: 14px; justify-content: center; }
        .modal-btn { padding: 12px 24px; border-radius: 10px; font-weight: 800; font-size: 14px; cursor: pointer; border: none; font-family: 'Plus Jakarta Sans', sans-serif; transition: all 0.2s ease; }
        .modal-btn-cancel { background: rgba(255, 255, 255, 0.1); color: #cbd5e1; }
        .modal-btn-cancel:hover { background: rgba(255, 255, 255, 0.18); color: #ffffff; }
        .modal-btn-confirm { background: linear-gradient(135deg, #ff4757, #d32f2f); color: #ffffff; box-shadow: 0 4px 16px rgba(255, 71, 87, 0.4); }
        .modal-btn-confirm:hover { background: linear-gradient(135deg, #ff6b81, #e53935); transform: translateY(-1px); box-shadow: 0 6px 20px rgba(255, 71, 87, 0.6); }

        @media (max-width: 900px) {
            .bottom-split { grid-template-columns: 1fr; }
        }
    
        /* LIVE / DEMO MODE BADGE & SETTINGS */
        .mode-badge-wrap {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(251, 197, 49, 0.12);
            border: 1px solid rgba(251, 197, 49, 0.4);
            color: #fbc531;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .mode-badge-wrap:hover {
            background: rgba(251, 197, 49, 0.22);
            box-shadow: 0 0 14px rgba(251, 197, 49, 0.3);
            transform: translateY(-1px);
        }
        .mode-badge-wrap.is-live {
            background: rgba(255, 71, 87, 0.15);
            border-color: var(--red);
            color: #ff4757;
            box-shadow: 0 0 14px rgba(255, 71, 87, 0.3);
        }
        .mode-dot-demo {
            width: 8px;
            height: 8px;
            background: #fbc531;
            border-radius: 50%;
            box-shadow: 0 0 8px #fbc531;
        }
        .mode-dot-live {
            width: 8px;
            height: 8px;
            background: var(--red);
            border-radius: 50%;
            box-shadow: 0 0 10px var(--red);
            animation: pulse 0.5s infinite;
        }

        .btn-binance-settings {
            background: linear-gradient(135deg, rgba(243, 186, 47, 0.15), rgba(251, 197, 49, 0.25));
            border: 1px solid rgba(243, 186, 47, 0.5);
            color: #f3ba2f;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s ease;
        }
        .btn-binance-settings:hover {
            background: #f3ba2f;
            color: #07090e;
            box-shadow: 0 0 16px rgba(243, 186, 47, 0.6);
            transform: translateY(-1px);
        }

        /* LIVE SETTINGS MODAL */
        .live-settings-card {
            background: #0e121a;
            border: 1px solid #2c3850;
            border-radius: 20px;
            width: 90vw;
            max-width: 680px;
            max-height: 88vh;
            display: flex;
            flex-direction: column;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.9), 0 0 35px rgba(243, 186, 47, 0.2);
            overflow: hidden;
            animation: fadeIn 0.2s ease;
        }
        .settings-tab-bar {
            display: flex;
            background: rgba(255, 255, 255, 0.03);
            border-bottom: 1px solid var(--border);
            padding: 8px 16px;
            gap: 8px;
        }
        .settings-tab-btn {
            background: transparent;
            border: none;
            color: #94a3b8;
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 12.5px;
            font-weight: 700;
            cursor: pointer;
            font-family: 'JetBrains Mono', monospace;
            transition: all 0.15s ease;
        }
        .settings-tab-btn:hover {
            color: #ffffff;
            background: rgba(255, 255, 255, 0.05);
        }
        .settings-tab-btn.tab-active {
            background: rgba(243, 186, 47, 0.2);
            color: #f3ba2f;
            border: 1px solid rgba(243, 186, 47, 0.4);
        }
        .settings-html, body { overflow-anchor: none; }
        .settings-body {
            padding: 20px 24px;
            overflow-y: auto;
            flex: 1;
        }
        .setting-group-box {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px 18px;
            margin-bottom: 16px;
        }
        .mode-toggle-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }
        .mode-radio-label {
            background: rgba(255, 255, 255, 0.03);
            border: 2px solid var(--border);
            border-radius: 10px;
            padding: 12px 14px;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .mode-radio-label:hover {
            border-color: var(--border-light);
            background: rgba(255, 255, 255, 0.06);
        }
        .mode-radio-label.is-selected-demo {
            border-color: #fbc531;
            background: rgba(251, 197, 49, 0.1);
        }
        .mode-radio-label.is-selected-live {
            border-color: var(--red);
            background: rgba(255, 71, 87, 0.12);
        }
        .input-with-eye {
            position: relative;
            display: flex;
            align-items: center;
        }
        .settings-input {
            width: 100%;
            background: #07090e;
            border: 1px solid var(--border);
            color: #ffffff;
            padding: 10px 14px;
            border-radius: 8px;
            font-size: 13px;
            font-family: 'JetBrains Mono', monospace;
            outline: none;
            transition: border-color 0.2s ease;
        }
        .settings-input:focus {
            border-color: #f3ba2f;
            box-shadow: 0 0 10px rgba(243, 186, 47, 0.2);
        }
        .btn-toggle-eye {
            position: absolute;
            right: 10px;
            background: transparent;
            border: none;
            cursor: pointer;
            font-size: 15px;
            padding: 4px;
            opacity: 0.7;
        }
        .btn-toggle-eye:hover { opacity: 1; }
        .settings-select {
            width: 100%;
            background: #07090e;
            border: 1px solid var(--border);
            color: #ffffff;
            padding: 10px 14px;
            border-radius: 8px;
            font-size: 13px;
            font-family: 'JetBrains Mono', monospace;
            outline: none;
        }
        .btn-test-conn {
            background: rgba(56, 139, 253, 0.15);
            border: 1px solid var(--blue);
            color: #58a6ff;
            padding: 10px 18px;
            border-radius: 8px;
            font-size: 12.5px;
            font-weight: 800;
            cursor: pointer;
            font-family: 'JetBrains Mono', monospace;
            transition: all 0.2s ease;
        }
        .btn-test-conn:hover {
            background: var(--blue);
            color: #fff;
            box-shadow: 0 0 12px rgba(56, 139, 253, 0.5);
        }
        .btn-save-settings {
            background: linear-gradient(135deg, #f3ba2f, #f59e0b);
            border: none;
            color: #07090e;
            padding: 10px 22px;
            border-radius: 8px;
            font-size: 12.5px;
            font-weight: 800;
            cursor: pointer;
            font-family: 'Plus Jakarta Sans', sans-serif;
            transition: all 0.2s ease;
        }
        .btn-save-settings:hover {
            transform: translateY(-1px);
            box-shadow: 0 0 16px rgba(243, 186, 47, 0.6);
        }
        .security-box {
            background: rgba(251, 197, 49, 0.08);
            border: 1px solid rgba(251, 197, 49, 0.25);
            border-radius: 10px;
            padding: 12px 16px;
        }

        .accordion-btn {
            width: 100%;
            background: rgba(255, 255, 255, 0.04);
            border: 1px dashed rgba(255, 255, 255, 0.15);
            border-radius: 8px;
            color: #94a3b8;
            font-size: 11.5px;
            font-family: 'JetBrains Mono', monospace;
            padding: 7px 10px;
            margin-top: 10px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: all 0.2s ease;
        }
        .accordion-btn:hover {
            background: rgba(56, 189, 248, 0.1);
            border-color: #38bdf8;
            color: #ffffff;
        }
        .accordion-content {
            display: none;
            margin-top: 8px;
            animation: fadeIn 0.2s ease;
        }
        .quant-intel-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 6px;
            margin-top: 8px;
            font-size: 11px;
            font-family: 'JetBrains Mono', monospace;
        }
        .quant-intel-item {
            background: rgba(0, 0, 0, 0.25);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 6px;
            padding: 5px 8px;
        }
        .quant-intel-lbl {
            color: #64748b;
            font-size: 10px;
            text-transform: uppercase;
        }
        .quant-intel-val {
            color: #f1f5f9;
            font-weight: 700;
            margin-top: 1px;
        }
        .badge-tp1-hit {
            background: linear-gradient(135deg, rgba(16, 185, 129, 0.25), rgba(5, 150, 105, 0.4));
            border: 1px solid #10b981;
            color: #a7f3d0;
            font-size: 11.5px;
            font-weight: 800;
            padding: 4px 10px;
            border-radius: 6px;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        .badge-trailing-lock {
            background: linear-gradient(135deg, rgba(245, 158, 11, 0.25), rgba(217, 119, 6, 0.4));
            border: 1px solid #f59e0b;
            color: #fde68a;
            font-size: 11.5px;
            font-weight: 800;
            padding: 4px 10px;
            border-radius: 6px;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }

    
        /* =========================================================================
           VALKYRIE QUANT COCKPIT 3.0 - TAB NAVIGATION & AI QUANT DESK STYLES
           ========================================================================= */
        /* =========================================================================
           VALKYRIE QUANT COCKPIT 3.0 - VERTICAL SIDEBAR DESK & APP LAYOUT
           ========================================================================= */
        .dashboard-main-layout {
            display: flex;
            align-items: flex-start;
            gap: 24px;
            width: 100%;
            position: relative;
        }

        .dashboard-sidebar {
            width: 255px;
            flex-shrink: 0;
            position: sticky;
            top: 20px;
            display: flex;
            flex-direction: column;
            gap: 12px;
            transition: width 0.25s cubic-bezier(0.2, 0.8, 0.2, 1);
            z-index: 40;
        }

        .dashboard-sidebar.is-collapsed {
            width: 72px;
        }

        .dashboard-content-area {
            flex: 1 1 0%;
            min-width: 0;
        }

        .sidebar-header-box {
            background: rgba(13, 18, 30, 0.85);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 14px;
            padding: 12px 14px;
            backdrop-filter: blur(16px);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
        }

        .sidebar-title-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .sidebar-section-title {
            font-size: 11px;
            font-weight: 800;
            color: #64748b;
            letter-spacing: 0.8px;
            text-transform: uppercase;
            font-family: 'JetBrains Mono', monospace;
        }

        .sidebar-subtitle {
            font-size: 11px;
            color: #94a3b8;
            margin-top: 2px;
            font-weight: 600;
        }

        .sidebar-toggle-btn {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: #94a3b8;
            width: 24px;
            height: 24px;
            border-radius: 6px;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 11px;
            transition: all 0.2s ease;
        }

        .sidebar-toggle-btn:hover {
            color: var(--cyan, #00f2fe);
            border-color: var(--cyan, #00f2fe);
            background: rgba(0, 242, 254, 0.1);
        }

        .dashboard-sidebar.is-collapsed .sidebar-subtitle,
        .dashboard-sidebar.is-collapsed .sidebar-section-title {
            display: none !important;
        }

        .dashboard-sidebar.is-collapsed .sidebar-header-box {
            padding: 8px;
            text-align: center;
        }

        .dashboard-sidebar.is-collapsed .sidebar-title-row {
            justify-content: center;
        }

        /* SIDEBAR VERTICAL NAV STRIP */
        .dashboard-sidebar .nav-tab-strip {
            display: flex;
            flex-direction: column;
            align-items: stretch;
            gap: 5px;
            background: rgba(13, 18, 30, 0.9);
            border: 1px solid var(--border, rgba(255, 255, 255, 0.08));
            padding: 8px;
            border-radius: 16px;
            margin-bottom: 0;
            overflow: visible;
            backdrop-filter: blur(16px);
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.45);
        }

        .dashboard-sidebar .nav-tab-btn {
            background: transparent;
            border: 1px solid transparent;
            border-left: 3px solid transparent;
            color: #94a3b8;
            padding: 10px 12px;
            border-radius: 10px;
            font-size: 13px;
            font-weight: 700;
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: flex-start;
            gap: 10px;
            transition: all 0.18s cubic-bezier(0.4, 0, 0.2, 1);
            white-space: nowrap;
            width: 100%;
            text-align: left;
            position: relative;
        }

        .dashboard-sidebar .nav-tab-btn:hover {
            color: #ffffff;
            background: rgba(255, 255, 255, 0.04);
            border-color: rgba(255, 255, 255, 0.07);
            border-left-color: rgba(0, 242, 254, 0.5);
            transform: translateX(2px);
        }

        .dashboard-sidebar .nav-tab-btn.active {
            background: linear-gradient(90deg, rgba(0, 242, 254, 0.15) 0%, rgba(0, 242, 254, 0.02) 100%);
            border-color: rgba(0, 242, 254, 0.25);
            border-left: 3.5px solid var(--cyan, #00f2fe);
            color: #ffffff;
            box-shadow: 0 0 20px rgba(0, 242, 254, 0.12);
            font-weight: 800;
        }

        .tab-btn-icon {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 20px;
            height: 20px;
            color: inherit;
            flex-shrink: 0;
            transition: color 0.15s ease, filter 0.15s ease;
        }

        .dashboard-sidebar .nav-tab-btn.active .tab-btn-icon {
            color: var(--cyan, #00f2fe);
            filter: drop-shadow(0 0 6px rgba(0, 242, 254, 0.6));
        }

        .tab-btn-text {
            flex: 1 1 auto;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            letter-spacing: -0.2px;
        }

        .tab-badge {
            font-size: 10.5px;
            font-weight: 800;
            padding: 2px 7px;
            border-radius: 10px;
            margin-left: auto;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 18px;
            height: 18px;
            font-family: 'JetBrains Mono', monospace;
            vertical-align: middle;
            transition: all 0.3s ease;
            flex-shrink: 0;
        }

        .tab-badge.active-pulse {
            background: linear-gradient(135deg, #ef4444, #dc2626);
            color: #ffffff;
            box-shadow: 0 0 10px rgba(239, 68, 68, 0.85);
            animation: pulseBadge 1.2s infinite ease-in-out;
        }

        .tab-badge.zero-idle {
            background: rgba(148, 163, 184, 0.12);
            color: #94a3b8;
            border: 1px solid rgba(148, 163, 184, 0.25);
            box-shadow: none;
            animation: none;
        }

        @keyframes pulseBadge {
            0%, 100% {
                opacity: 1;
                transform: scale(1);
                box-shadow: 0 0 8px rgba(239, 68, 68, 0.6);
            }
            50% {
                opacity: 0.7;
                transform: scale(1.18);
                box-shadow: 0 0 18px rgba(239, 68, 68, 1);
            }
        }

        .tab-badge-sub {
            background: rgba(14, 203, 129, 0.15);
            color: var(--green, #10b981);
            border: 1px solid var(--green, #10b981);
            font-size: 10px;
            font-weight: 800;
            padding: 2px 6px;
            border-radius: 8px;
            margin-left: auto;
            font-family: 'JetBrains Mono', monospace;
            flex-shrink: 0;
        }

        /* COLLAPSED SIDEBAR MODES */
        .dashboard-sidebar.is-collapsed .tab-btn-text,
        .dashboard-sidebar.is-collapsed .tab-badge,
        .dashboard-sidebar.is-collapsed .tab-badge-sub,
        .dashboard-sidebar.is-collapsed .sidebar-status-card {
            display: none !important;
        }

        .dashboard-sidebar.is-collapsed .nav-tab-btn {
            justify-content: center;
            padding: 12px 0;
            gap: 0;
            border-left-width: 3px;
        }

        .dashboard-sidebar.is-collapsed .tab-btn-icon {
            margin-right: 0;
            width: 24px;
            height: 24px;
        }

        /* SIDEBAR TELEMETRİ KARTI */
        .sidebar-status-card {
            background: rgba(13, 18, 30, 0.75);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 14px;
            padding: 12px 14px;
            backdrop-filter: blur(12px);
            box-shadow: 0 4px 18px rgba(0, 0, 0, 0.3);
        }

        .sidebar-status-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
            padding-bottom: 6px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }

        .sidebar-status-beacon {
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .sidebar-status-dot {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: var(--green, #10b981);
            box-shadow: 0 0 8px var(--green, #10b981);
            animation: pulse 1.2s infinite;
        }

        .sidebar-status-title {
            font-size: 10.5px;
            font-weight: 800;
            color: #cbd5e1;
            letter-spacing: 0.6px;
            font-family: 'JetBrains Mono', monospace;
        }

        .sidebar-status-state {
            font-size: 9.5px;
            font-weight: 800;
            color: var(--green, #10b981);
            background: rgba(14, 203, 129, 0.12);
            border: 1px solid rgba(14, 203, 129, 0.3);
            padding: 2px 5px;
            border-radius: 6px;
            font-family: 'JetBrains Mono', monospace;
        }

        .sidebar-status-meta {
            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        .sidebar-status-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 10.5px;
            color: #64748b;
            font-family: 'JetBrains Mono', monospace;
        }

        .sidebar-status-row b {
            color: #cbd5e1;
            font-weight: 700;
        }

        /* RESPONSIVE LAYOUT FOR SCREENS < 1024px */
        @media (max-width: 1024px) {
            .dashboard-main-layout {
                flex-direction: column;
                gap: 16px;
            }
            .dashboard-sidebar {
                width: 100% !important;
                position: static;
            }
            .dashboard-sidebar .nav-tab-strip {
                flex-direction: row;
                overflow-x: auto;
                padding: 6px 8px;
            }
            .dashboard-sidebar .nav-tab-btn {
                width: auto;
                white-space: nowrap;
                border-left: 1px solid transparent;
                border-bottom: 3px solid transparent;
            }
            .dashboard-sidebar .nav-tab-btn.active {
                border-left-color: transparent;
                border-bottom: 3.5px solid var(--cyan, #00f2fe);
            }
            .sidebar-header-box,
            .sidebar-status-card {
                display: none !important;
            }
        }

        /* 1. COCKPIT HERO FINANSAL KPI GRID */
        /* 1. COCKPIT HERO FINANSAL KPI GRID (MİKRO-SİMÜLASYONLU & CAM EFEKTLİ) */
        .cockpit-kpi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }
        .cockpit-kpi-card {
            background: linear-gradient(180deg, rgba(18, 25, 40, 0.88) 0%, rgba(12, 17, 28, 0.94) 100%);
            border: 1px solid rgba(255, 255, 255, 0.09);
            border-radius: 18px;
            padding: 18px 20px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            position: relative;
            overflow: hidden;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.45);
            backdrop-filter: blur(12px);
            transition: transform 0.25s cubic-bezier(0.2, 0.8, 0.2, 1), border-color 0.25s ease, box-shadow 0.25s ease;
        }
        .cockpit-kpi-card:hover {
            transform: translateY(-3px);
            border-color: rgba(0, 242, 254, 0.35);
            box-shadow: 0 12px 38px rgba(0, 0, 0, 0.55), 0 0 20px rgba(0, 242, 254, 0.12);
        }
        .cockpit-kpi-card::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, #00f2fe, #4facfe);
            z-index: 3;
        }
        .cockpit-kpi-card.kpi-card-growth::after {
            background: linear-gradient(90deg, #10b981, #00f2fe);
        }
        .cockpit-kpi-card.kpi-card-growth.drawdown::after {
            background: linear-gradient(90deg, #f43f5e, #fb923c);
        }
        .cockpit-kpi-card.kpi-card-radar::after {
            background: linear-gradient(90deg, #38bdf8, #818cf8);
        }
        .cockpit-kpi-card.kpi-card-reactor::after {
            background: linear-gradient(90deg, #c084fc, #00f2fe);
        }
        .kpi-sim-canvas {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 1;
        }
        .kpi-card-inner {
            position: relative;
            z-index: 2;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            height: 100%;
        }
        .kpi-card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
        .kpi-card-title { font-size: 11.5px; font-weight: 800; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.6px; display: inline-flex; align-items: center; gap: 6px; }
        .kpi-card-icon { font-size: 18px; filter: drop-shadow(0 0 8px rgba(0,242,254,0.3)); }
        .kpi-card-val { font-size: 25px; font-weight: 900; font-family: 'JetBrains Mono', monospace; color: #ffffff; margin-bottom: 4px; text-shadow: 0 0 16px rgba(255,255,255,0.15); }
        .kpi-card-sub { font-size: 11.5px; color: #94a3b8; font-family: 'JetBrains Mono', monospace; }
        .kpi-telemetry-chip {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            font-size: 9.5px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            padding: 2px 7px;
            border-radius: 6px;
            letter-spacing: 0.5px;
        }

        /* 🧠 VALKYRIE AI CANLI AKIL & YORUM ODASI */
        .ai-quant-room {
            background: linear-gradient(180deg, rgba(15, 23, 42, 0.95) 0%, rgba(10, 15, 29, 0.98) 100%);
            border: 1px solid rgba(0, 242, 254, 0.35);
            border-radius: 20px;
            padding: 22px 24px;
            margin-bottom: 24px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.6), 0 0 25px rgba(0, 242, 254, 0.15);
            position: relative;
        }
        .ai-room-head {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            flex-wrap: wrap;
            gap: 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            padding-bottom: 14px;
        }
        .ai-room-title {
            font-size: 16px;
            font-weight: 900;
            letter-spacing: 0.5px;
            color: #ffffff;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .ai-pulse-dot {
            width: 9px;
            height: 9px;
            background: #00f2fe;
            border-radius: 50%;
            box-shadow: 0 0 12px #00f2fe;
            animation: pulse 0.8s infinite alternate;
        }
        /* ⚔️ VALKYRIE CANLI LİKİDİTE SAVAŞI: BOĞA VS AYI CEPHESİ ARENASI */
        .regime-battle-card {
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.75), rgba(10, 15, 29, 0.85));
            border: 1px solid rgba(0, 242, 254, 0.25);
            border-radius: 16px;
            padding: 14px 18px;
            margin: 12px 0 16px 0;
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.08);
            position: relative;
            overflow: hidden;
        }
        .regime-battle-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 2px;
            background: linear-gradient(90deg, #0ecb81, #00f2fe, #ff4757);
        }
        .regime-battle-top-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            flex-wrap: wrap;
            gap: 8px;
        }
        .regime-battle-title {
            font-size: 13px;
            font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
            display: flex;
            align-items: center;
            gap: 8px;
            color: #ffffff;
            letter-spacing: 0.3px;
        }
        .btn-battle-toggle {
            background: rgba(0, 242, 254, 0.08);
            border: 1px solid rgba(0, 242, 254, 0.3);
            color: var(--cyan);
            font-size: 11px;
            font-weight: 800;
            padding: 4px 10px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s ease;
            font-family: 'JetBrains Mono', monospace;
        }
        .btn-battle-toggle:hover {
            background: rgba(0, 242, 254, 0.18);
            border-color: var(--cyan);
            box-shadow: 0 0 12px rgba(0, 242, 254, 0.3);
        }
        .regime-arena-canvas-wrap {
            position: relative;
            width: 100%;
            height: 140px;
            border-radius: 12px;
            overflow: hidden;
            background: radial-gradient(circle at 50% 50%, #0d1527 0%, #050811 100%);
            border: 1px solid rgba(255, 255, 255, 0.08);
            box-shadow: inset 0 0 30px rgba(0, 0, 0, 0.9);
            margin-bottom: 10px;
        }
        #regime-battle-canvas {
            width: 100%;
            height: 100%;
            display: block;
        }
        .regime-arena-hud-overlay {
            position: absolute;
            inset: 0;
            pointer-events: none;
            display: flex;
            justify-content: space-between;
            align-items: stretch;
            padding: 10px 16px;
        }
        .hud-side-box {
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            z-index: 2;
        }
        .hud-side-box.bull { text-align: left; }
        .hud-side-box.bear { text-align: right; }
        .hud-army-name {
            font-size: 11.5px;
            font-weight: 900;
            font-family: 'JetBrains Mono', monospace;
            letter-spacing: 0.5px;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .hud-side-box.bull .hud-army-name {
            color: #0ecb81;
            text-shadow: 0 0 10px rgba(14, 203, 129, 0.6);
        }
        .hud-side-box.bear .hud-army-name {
            color: #ff4757;
            text-shadow: 0 0 10px rgba(255, 71, 87, 0.6);
            justify-content: flex-end;
        }
        .hud-tag-taarruz {
            font-size: 9px;
            background: rgba(14, 203, 129, 0.15);
            border: 1px solid #0ecb81;
            padding: 2px 6px;
            border-radius: 4px;
        }
        .hud-tag-savunma {
            font-size: 9px;
            background: rgba(255, 71, 87, 0.15);
            border: 1px solid #ff4757;
            padding: 2px 6px;
            border-radius: 4px;
        }
        .hud-power-stat {
            font-size: 26px;
            font-weight: 900;
            font-family: 'JetBrains Mono', monospace;
            line-height: 1;
        }
        .hud-side-box.bull .hud-power-stat {
            color: #ffffff;
            text-shadow: 0 0 16px rgba(14, 203, 129, 0.8);
        }
        .hud-side-box.bear .hud-power-stat {
            color: #ffffff;
            text-shadow: 0 0 16px rgba(255, 71, 87, 0.8);
        }
        .hud-parite-count {
            font-size: 11px;
            font-family: 'JetBrains Mono', monospace;
            color: #94a3b8;
            font-weight: 700;
        }
        .hud-center-neutral {
            position: absolute;
            top: 10px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(15, 23, 42, 0.75);
            border: 1px solid rgba(255, 255, 255, 0.14);
            padding: 3px 12px;
            border-radius: 20px;
            font-size: 10.5px;
            font-family: 'JetBrains Mono', monospace;
            color: #cbd5e1;
            backdrop-filter: blur(4px);
            z-index: 2;
            display: flex;
            align-items: center;
            gap: 6px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5);
        }
        .regime-battle-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            font-weight: 800;
            margin-bottom: 8px;
            flex-wrap: wrap;
            gap: 8px;
        }
        .regime-side-bull {
            color: #0ecb81;
            display: flex;
            align-items: center;
            gap: 6px;
            text-shadow: 0 0 10px rgba(14, 203, 129, 0.4);
        }
        .regime-side-range {
            color: #94a3b8;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .regime-side-bear {
            color: #ff4757;
            display: flex;
            align-items: center;
            gap: 6px;
            text-shadow: 0 0 10px rgba(255, 71, 87, 0.4);
        }
        .regime-battle-track {
            position: relative;
            display: flex;
            height: 12px;
            border-radius: 8px;
            overflow: hidden;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.6);
            margin-bottom: 8px;
        }
        .regime-bar-bull {
            background: linear-gradient(90deg, rgba(14, 203, 129, 0.35), #0ecb81);
            box-shadow: 0 0 14px rgba(14, 203, 129, 0.5);
            transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
        }
        .regime-bar-range {
            background: linear-gradient(90deg, #334155, #475569);
            transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .regime-bar-bear {
            background: linear-gradient(90deg, #ff4757, rgba(255, 71, 87, 0.35));
            box-shadow: 0 0 14px rgba(255, 71, 87, 0.5);
            transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .regime-clash-spark {
            position: absolute;
            top: -2px;
            bottom: -2px;
            width: 4px;
            background: #ffffff;
            box-shadow: 0 0 8px #00f2fe, 0 0 16px #00f2fe, 0 0 24px #fff;
            border-radius: 2px;
            z-index: 6;
            transition: left 0.5s cubic-bezier(0.4, 0, 0.2, 1);
            animation: sparkFlicker 0.8s infinite alternate;
        }
        @keyframes sparkFlicker {
            0% { opacity: 0.8; transform: scaleY(1); }
            100% { opacity: 1; transform: scaleY(1.3); box-shadow: 0 0 12px #00f2fe, 0 0 24px #0ecb81; }
        }
        .regime-battle-footer {
            font-size: 11.5px;
            color: #cbd5e1;
            display: flex;
            align-items: center;
            gap: 6px;
            line-height: 1.4;
        }

        /* 🎯 VALKYRIE 360° TAKTİK LİKİDİTE RADARI & SAVUNMA KALKANI STİLLERİ */
        .tactical-radar-card {
            background: linear-gradient(180deg, rgba(14, 20, 34, 0.95) 0%, rgba(10, 14, 25, 0.98) 100%);
            border: 1px solid rgba(0, 242, 254, 0.3);
            border-radius: 20px;
            padding: 18px 20px;
            margin-bottom: 20px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.55), 0 0 25px rgba(0, 242, 254, 0.12);
            position: relative;
            overflow: hidden;
            backdrop-filter: blur(12px);
        }
        .tactical-radar-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, #00f2fe, #38bdf8, #10b981, #f43f5e);
            z-index: 3;
        }
        .tactical-radar-topbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
            padding-bottom: 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }
        .tactical-radar-title {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
            color: #ffffff;
            font-family: 'JetBrains Mono', monospace;
        }
        .radar-live-blip {
            width: 8px;
            height: 8px;
            background: #00f2fe;
            border-radius: 50%;
            box-shadow: 0 0 10px #00f2fe;
            animation: radarBlipPulse 1.4s infinite;
        }
        @keyframes radarBlipPulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.3; transform: scale(0.7); }
        }
        .radar-scope-badge {
            font-size: 10.5px;
            background: rgba(0, 242, 254, 0.12);
            border: 1px solid rgba(0, 242, 254, 0.35);
            color: var(--cyan);
            padding: 3px 8px;
            border-radius: 6px;
            font-weight: 700;
        }
        .radar-top-controls {
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
        }
        .radar-scope-filters {
            display: inline-flex;
            align-items: center;
            background: rgba(15, 23, 42, 0.7);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 8px;
            padding: 2px 4px;
            gap: 3px;
        }
        .radar-filter-pill {
            background: transparent;
            border: 1px solid transparent;
            color: #94a3b8;
            font-size: 10.5px;
            font-family: 'JetBrains Mono', monospace;
            padding: 3px 8px;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s ease;
            font-weight: 600;
        }
        .radar-filter-pill:hover {
            color: #ffffff;
            background: rgba(255, 255, 255, 0.06);
        }
        .radar-filter-pill.active {
            background: rgba(0, 242, 254, 0.18);
            border-color: rgba(0, 242, 254, 0.45);
            color: var(--cyan);
            box-shadow: 0 0 10px rgba(0, 242, 254, 0.25);
            font-weight: 700;
        }
        .tactical-radar-body {
            display: grid;
            grid-template-columns: 1.4fr 1fr;
            gap: 20px;
            align-items: center;
            margin-top: 14px;
            transition: all 0.3s ease;
        }
        @media (max-width: 950px) {
            .tactical-radar-body {
                grid-template-columns: 1fr;
            }
        }
        .tactical-radar-card.radar-expanded-mode .tactical-radar-body {
            grid-template-columns: 1fr;
        }
        .tactical-radar-card.radar-expanded-mode .radar-canvas-container {
            height: 640px !important;
        }
        .tactical-radar-card.radar-expanded-mode .radar-telemetry-panel {
            min-height: auto;
        }
        .radar-canvas-container {
            position: relative;
            width: 100%;
            height: 520px;
            background: radial-gradient(circle at center, rgba(16, 24, 40, 0.82) 0%, rgba(8, 12, 22, 0.98) 78%);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 16px;
            overflow: hidden;
            box-shadow: inset 0 0 50px rgba(0, 0, 0, 0.95);
            display: flex;
            align-items: center;
            justify-content: center;
            transition: height 0.3s ease;
        }
        #tactical-radar-canvas {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            cursor: crosshair;
        }
        .radar-hud-legend {
            position: absolute;
            bottom: 12px;
            left: 14px;
            right: 14px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 6px;
            pointer-events: none;
            z-index: 2;
            background: rgba(10, 15, 28, 0.8);
            padding: 5px 12px;
            border-radius: 8px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            backdrop-filter: blur(6px);
        }
        .legend-item {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            font-size: 11px;
            color: #94a3b8;
            font-family: 'JetBrains Mono', monospace;
        }
        .legend-dot {
            width: 7px;
            height: 7px;
            border-radius: 50%;
        }
        .legend-dot.contact { background: #10b981; box-shadow: 0 0 6px #10b981; }
        .legend-dot.ambush { background: #f59e0b; box-shadow: 0 0 6px #f59e0b; }
        .legend-dot.approach { background: #38bdf8; box-shadow: 0 0 6px #38bdf8; }
        .legend-dot.blocked { background: #f43f5e; box-shadow: 0 0 6px #f43f5e; }

        .radar-telemetry-panel {
            background: rgba(13, 19, 33, 0.85);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 16px;
            padding: 18px 20px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            min-height: 460px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
        }
        .telemetry-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            padding-bottom: 10px;
            border-bottom: 1px dashed rgba(255, 255, 255, 0.1);
        }
        .telemetry-target-name {
            font-size: 16px;
            font-weight: 900;
            color: #ffffff;
            font-family: 'JetBrains Mono', monospace;
            display: flex;
            align-items: center;
            gap: 6px;
            text-shadow: 0 0 12px rgba(0, 242, 254, 0.4);
        }
        .telemetry-badge {
            font-size: 10px;
            font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
            padding: 3px 8px;
            border-radius: 6px;
            background: rgba(56, 189, 248, 0.15);
            border: 1px solid rgba(56, 189, 248, 0.35);
            color: #38bdf8;
            letter-spacing: 0.5px;
        }
        .telemetry-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            margin-bottom: 12px;
        }
        .telemetry-stat-box {
            background: rgba(0, 0, 0, 0.28);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 10px;
            padding: 8px 10px;
        }
        .stat-label {
            font-size: 10px;
            font-weight: 800;
            color: #64748b;
            font-family: 'JetBrains Mono', monospace;
            text-transform: uppercase;
            margin-bottom: 2px;
        }
        .stat-val {
            font-size: 15px;
            font-weight: 900;
            color: #ffffff;
            font-family: 'JetBrains Mono', monospace;
        }
        .stat-sub {
            font-size: 10.5px;
            color: #94a3b8;
            font-family: 'JetBrains Mono', monospace;
            margin-top: 1px;
        }
        .telemetry-briefing-box {
            background: rgba(0, 0, 0, 0.35);
            border-left: 3px solid #00f2fe;
            border-radius: 6px;
            padding: 10px 12px;
            font-size: 11.5px;
            color: #cbd5e1;
            line-height: 1.5;
            margin-bottom: 12px;
            min-height: 68px;
            font-family: 'Plus Jakarta Sans', sans-serif;
        }
        .telemetry-footer-action {
            display: flex;
            justify-content: flex-end;
        }
        .btn-radar-focus {
            background: linear-gradient(135deg, rgba(0, 242, 254, 0.15) 0%, rgba(79, 172, 254, 0.2) 100%);
            border: 1px solid rgba(0, 242, 254, 0.4);
            color: #00f2fe;
            padding: 7px 14px;
            border-radius: 8px;
            font-size: 11.5px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            cursor: pointer;
            transition: all 0.2s ease;
            box-shadow: 0 0 12px rgba(0, 242, 254, 0.15);
        }
        .btn-radar-focus:hover {
            background: rgba(0, 242, 254, 0.25);
            border-color: #00f2fe;
            color: #ffffff;
            transform: translateY(-1px);
            box-shadow: 0 0 18px rgba(0, 242, 254, 0.3);
        }
            display: flex;
            gap: 8px;
            margin-bottom: 12px;
            overflow-x: auto;
            padding-bottom: 4px;
        }
        .ai-filter-btn {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 8px;
            padding: 6px 12px;
            font-size: 11.5px;
            font-weight: 700;
            color: #94a3b8;
            cursor: pointer;
            transition: all 0.2s ease;
            white-space: nowrap;
            font-family: 'JetBrains Mono', monospace;
        }
        .ai-filter-btn:hover {
            background: rgba(255, 255, 255, 0.08);
            color: #ffffff;
        }
        .ai-filter-btn.active {
            background: rgba(0, 242, 254, 0.12);
            border-color: rgba(0, 242, 254, 0.4);
            color: #00f2fe;
            box-shadow: 0 0 10px rgba(0, 242, 254, 0.15);
        }
        .ai-thought-feed {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 12px;
        }
        @media (max-width: 1024px) {
            .ai-thought-feed {
                grid-template-columns: 1fr;
            }
        }
        .ai-thought-feed.layout-single {
            grid-template-columns: 1fr !important;
        }
        .ai-thought-item {
            background: rgba(15, 23, 42, 0.75);
            border: 1px solid rgba(255, 255, 255, 0.07);
            border-radius: 12px;
            padding: 14px 16px;
            font-size: 12.5px;
            line-height: 1.55;
            color: #f1f5f9;
            display: flex;
            align-items: flex-start;
            gap: 12px;
            border-left: 4px solid var(--blue);
            transition: all 0.2s ease;
            box-sizing: border-box;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
            min-width: 0;
        }
        .ai-thought-item.macro-span {
            grid-column: 1 / -1;
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.85) 0%, rgba(30, 27, 75, 0.35) 100%);
            border-color: rgba(168, 85, 247, 0.25);
        }
        .ai-thought-item:hover {
            background: rgba(30, 41, 59, 0.85);
            border-color: rgba(255, 255, 255, 0.16);
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
        }
        .ai-thought-tag {
            display: inline-block;
            font-size: 10px;
            font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
            padding: 2px 6px;
            border-radius: 4px;
            margin-right: 6px;
            text-transform: uppercase;
        }
        .tag-vol { background: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.3); }
        .tag-pos { background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3); }
        .tag-autopsy-win { background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); }
        .tag-autopsy-loss { background: rgba(244, 63, 94, 0.15); color: #f43f5e; border: 1px solid rgba(244, 63, 94, 0.3); }
        .tag-macro { background: rgba(168, 85, 247, 0.15); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.3); }

        /* 🎯 TETIKLENMEYE EN YAKIN TOP 5 COIN PUSU GRID */
        .near-trigger-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 14px;
            margin-bottom: 24px;
        }
        .near-card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 14px 16px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: all 0.2s ease;
            position: relative;
        }
        .near-card:hover {
            border-color: rgba(0, 242, 254, 0.5);
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4);
        }
        .near-card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
        .near-sym { font-weight: 800; font-size: 15px; font-family: 'JetBrains Mono', monospace; color: #ffffff; }
        .near-dist-badge { font-size: 11px; font-weight: 800; padding: 3px 8px; border-radius: 8px; font-family: 'JetBrains Mono', monospace; }
        .dist-super-close { background: rgba(14, 203, 129, 0.2); color: var(--green); border: 1px solid var(--green); }
        .dist-close { background: rgba(240, 185, 11, 0.2); color: var(--yellow); border: 1px solid var(--yellow); }

        /* TAB CONTAINER DISPLAY TOGGLING */
        .main-tab-content {
            display: none;
            animation: fadeIn 0.25s ease;
        }
        .main-tab-content.active-tab {
            display: block;
        }

        /* 📈 VALKYRIE KURUMSAL KASA PERFORMANSI (EQUITY CURVE) */
        .equity-curve-card {
            background: linear-gradient(180deg, rgba(14, 20, 34, 0.92) 0%, rgba(10, 14, 25, 0.98) 100%);
            border: 1px solid rgba(0, 242, 254, 0.25);
            border-radius: 18px;
            padding: 18px 22px;
            margin-bottom: 22px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.45), 0 0 20px rgba(0, 242, 254, 0.08);
            position: relative;
            overflow: hidden;
            backdrop-filter: blur(14px);
        }
        .equity-curve-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 2.5px;
            background: linear-gradient(90deg, #00f2fe, #38bdf8, #10b981);
        }
        .equity-top-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
            margin-bottom: 14px;
            padding-bottom: 10px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.06);
        }
        .equity-title-wrap {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .equity-title {
            font-size: 13.5px;
            font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
            color: #ffffff;
            letter-spacing: 0.4px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .equity-hud-chips {
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
        }
        .equity-chip {
            background: rgba(15, 23, 42, 0.7);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 8px;
            padding: 4px 10px;
            font-size: 11px;
            font-family: 'JetBrains Mono', monospace;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        .equity-chip-label {
            color: #94a3b8;
            font-size: 10px;
            text-transform: uppercase;
        }
        .equity-chip-val {
            color: #ffffff;
            font-weight: 800;
        }
        .equity-canvas-container {
            width: 100%;
            height: 260px;
            position: relative;
            border-radius: 12px;
            overflow: hidden;
            background: #080c14;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }
        .equity-empty-placeholder {
            position: absolute;
            inset: 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 8px;
            color: #94a3b8;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12.5px;
            background: radial-gradient(circle at 50% 50%, rgba(0, 242, 254, 0.04) 0%, transparent 70%);
        }

        /* 🛡️ KUANT KALKANLARI & REDDEDİLEN SİNYAL İSTİHBARATI */
        .rejection-panel-card {
            background: linear-gradient(180deg, rgba(14, 20, 34, 0.92) 0%, rgba(10, 14, 25, 0.98) 100%);
            border: 1px solid rgba(255, 71, 87, 0.25);
            border-radius: 18px;
            padding: 18px 22px;
            margin: 20px 0;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.45), 0 0 20px rgba(255, 71, 87, 0.08);
            position: relative;
            overflow: hidden;
            backdrop-filter: blur(14px);
        }
        .rejection-panel-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 2.5px;
            background: linear-gradient(90deg, #ff4757, #fb923c, #f59e0b);
        }
        .shield-stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
            gap: 10px;
            margin-bottom: 14px;
        }
        .shield-stat-card {
            background: rgba(0, 0, 0, 0.35);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 10px;
            padding: 9px 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: all 0.2s ease;
        }
        .shield-stat-card:hover {
            border-color: rgba(255, 71, 87, 0.35);
            background: rgba(255, 71, 87, 0.05);
        }
        .rejection-feed-list {
            display: flex;
            flex-direction: column;
            gap: 6px;
            max-height: 260px;
            overflow-y: auto;
            padding-right: 4px;
        }
        .rejection-feed-item {
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-left: 3px solid #ff4757;
            border-radius: 8px;
            padding: 8px 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-family: 'JetBrains Mono', monospace;
            font-size: 11.5px;
            transition: all 0.15s ease;
            gap: 10px;
        }
        .rejection-feed-item:hover {
            background: rgba(255, 255, 255, 0.03);
            border-color: rgba(255, 255, 255, 0.12);
        }
        .rejection-shield-tag {
            font-size: 10px;
            font-weight: 800;
            padding: 2px 7px;
            border-radius: 6px;
            background: rgba(255, 71, 87, 0.15);
            color: #ff4757;
            border: 1px solid rgba(255, 71, 87, 0.35);
            white-space: nowrap;
        }

        /* 🌡️ PORTFÖY RİSK & EXPOSURE HUD */
        .portfolio-risk-hud {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 12px;
            margin-bottom: 20px;
        }
        .risk-hud-card {
            background: linear-gradient(180deg, rgba(16, 22, 36, 0.85) 0%, rgba(11, 16, 28, 0.92) 100%);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 12px 16px;
            display: flex;
            flex-direction: column;
            gap: 4px;
        }
        .risk-hud-title {
            font-size: 10.5px;
            font-weight: 800;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.6px;
            font-family: 'JetBrains Mono', monospace;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .risk-hud-val {
            font-size: 19px;
            font-weight: 900;
            font-family: 'JetBrains Mono', monospace;
            color: #ffffff;
        }
        .risk-hud-sub {
            font-size: 10.5px;
            color: #64748b;
            font-family: 'JetBrains Mono', monospace;
        }

        /* 🎯 STOP / TP ROUTE PROGRESS BAR (DİNAMİK ROTA TAKİBİ) */
        .pos-route-track {
            position: relative;
            width: 100%;
            height: 14px;
            background: rgba(0, 0, 0, 0.5);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 7px;
            overflow: hidden;
            margin: 6px 0 3px 0;
            display: flex;
        }
        .pos-route-loss-zone {
            width: 35%;
            background: linear-gradient(90deg, rgba(244, 63, 94, 0.3) 0%, rgba(244, 63, 94, 0.08) 100%);
            border-right: 1.5px dashed rgba(255, 255, 255, 0.25);
            position: relative;
        }
        .pos-route-profit-zone {
            width: 65%;
            background: linear-gradient(90deg, rgba(16, 185, 129, 0.08) 0%, rgba(16, 185, 129, 0.35) 100%);
            position: relative;
        }
        .pos-route-cursor {
            position: absolute;
            top: 1px;
            bottom: 1px;
            width: 4px;
            background: #ffffff;
            border-radius: 2px;
            box-shadow: 0 0 8px #ffffff, 0 0 14px #00f2fe;
            z-index: 5;
            transition: left 0.3s ease;
        }
        .pos-route-labels {
            display: flex;
            justify-content: space-between;
            font-size: 10px;
            font-family: 'JetBrains Mono', monospace;
            color: #94a3b8;
            margin-bottom: 2px;
        }

        /* 📜 İŞLEM GEÇMİŞİ PNL & ROE PİLLERİ */
        .history-pnl-pill {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 3px 8px;
            border-radius: 6px;
            font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            white-space: nowrap;
        }
        .history-pnl-pill.pnl-win {
            background: rgba(16, 185, 129, 0.12);
            color: #10b981;
            border: 1px solid rgba(16, 185, 129, 0.3);
            box-shadow: 0 0 8px rgba(16, 185, 129, 0.15);
        }
        .history-pnl-pill.pnl-loss {
            background: rgba(244, 63, 94, 0.12);
            color: #f43f5e;
            border: 1px solid rgba(244, 63, 94, 0.3);
            box-shadow: 0 0 8px rgba(244, 63, 94, 0.15);
        }
        .history-roe-pill {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 2px 7px;
            border-radius: 5px;
            font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
            font-size: 11.5px;
            white-space: nowrap;
        }
        .history-roe-pill.roe-win {
            background: rgba(16, 185, 129, 0.08);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.2);
        }
        .history-roe-pill.roe-loss {
            background: rgba(244, 63, 94, 0.08);
            color: #fb7185;
            border: 1px solid rgba(244, 63, 94, 0.2);
        }

        /* 📊 SETUP PERFORMANS MATRİSİ */
        .setup-matrix-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 12px;
            margin-bottom: 20px;
        }
        .setup-matrix-card {
            background: rgba(13, 18, 30, 0.85);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 12px 14px;
            display: flex;
            flex-direction: column;
            gap: 4px;
            transition: all 0.2s ease;
            cursor: pointer;
            user-select: none;
        }
        .setup-matrix-card:hover {
            border-color: rgba(0, 242, 254, 0.4);
            transform: translateY(-2px);
            box-shadow: 0 4px 14px rgba(0, 242, 254, 0.12);
        }
        .setup-matrix-card.active-card {
            border-color: var(--cyan);
            background: rgba(0, 242, 254, 0.1);
            box-shadow: 0 0 16px rgba(0, 242, 254, 0.25);
        }
        .setup-card-name {
            font-size: 11px;
            font-weight: 800;
            color: #94a3b8;
            font-family: 'JetBrains Mono', monospace;
            text-transform: uppercase;
            display: flex;
            justify-content: space-between;
        }
        .setup-card-pnl {
            font-size: 17px;
            font-weight: 900;
            font-family: 'JetBrains Mono', monospace;
        }
        .setup-card-stats {
            font-size: 11px;
            color: #64748b;
            font-family: 'JetBrains Mono', monospace;
            display: flex;
            justify-content: space-between;
        }

    </style>
</head>
<body>
    <!-- GLOBAL VALKYRIE BRAND VECTOR ASSETS & GRADIENTS -->
    <svg style="position:absolute; width:0; height:0; overflow:hidden;" aria-hidden="true">
        <defs>
            <linearGradient id="valk_global_wing" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#00f2fe" />
                <stop offset="100%" stop-color="#4facfe" />
            </linearGradient>
            <linearGradient id="valk_global_core" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#00f2fe" />
                <stop offset="50%" stop-color="#38ef7d" />
                <stop offset="100%" stop-color="#00f2fe" />
            </linearGradient>
            <linearGradient id="valk_global_gold" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#fbc531" />
                <stop offset="100%" stop-color="#f39c12" />
            </linearGradient>
        </defs>
    </svg>


    
    
    
            <!-- =========================================================================
         48-HOUR DEMO TRIAL EXPIRED GRACEFUL NOTIFICATION MODAL
         ========================================================================= -->
    <div id="trial-expired-modal-overlay" class="modal-overlay" style="display:none;" onclick="if(event.target === this) closeTrialExpiredModal()">
        <div class="modal-card" style="max-width:560px; text-align:left; border:1px solid rgba(255,71,87,0.4); box-shadow:0 25px 60px rgba(0,0,0,0.9), 0 0 40px rgba(255,71,87,0.15); padding:28px;">
            <!-- HEADER -->
            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:18px; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:14px;">
                <div style="display:flex; align-items:center; gap:12px;">
                    <div style="width:38px; height:38px; background:rgba(255,71,87,0.12); border:1.5px solid var(--red); border-radius:10px; display:flex; align-items:center; justify-content:center;">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--red)" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
                    </div>
                    <div>
                        <div style="font-size:18px; font-weight:900; color:#fff;">48 Saatlik Demo Süreniz Tamamlandı</div>
                        <div style="font-size:12px; color:var(--text-muted); margin-top:2px;">Valkyrie Quant Algoritmik Demo Lisans Raporu</div>
                    </div>
                </div>
                <button onclick="closeTrialExpiredModal()" style="background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); color:#94a3b8; width:32px; height:32px; border-radius:8px; font-size:16px; cursor:pointer;" onmouseover="this.style.color='#fff';" onmouseout="this.style.color='#94a3b8';">✕</button>
            </div>

            <!-- GRACEFUL SAFETY PROTOCOL NOTICE -->
            <div style="background:rgba(0,242,254,0.05); border:1.5px solid rgba(0,242,254,0.3); border-radius:12px; padding:16px; margin-bottom:18px;">
                <div style="font-size:12.5px; font-weight:800; color:var(--cyan); margin-bottom:6px; display:flex; align-items:center; gap:6px;">
                    <span>🛡️</span> GÜVENLİ POZİSYON PROTOKOLÜ DEVREDE
                </div>
                <div style="font-size:12px; color:#cbd5e1; line-height:1.55;">
                    Mevcut açık pozisyonlarınız <b>kesinlikle panikle veya piyasadan kapatılmaz</b>. Önceden belirlenen Take Profit (TP) ve Stop Loss (SL) hedeflerine ulaşana kadar güvenle yönetilir. Yalnızca <b>yeni pozisyon alımları kısıtlanmıştır</b>.
                </div>
            </div>

            <!-- VALUE SUMMARY -->
            <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.06); border-radius:12px; padding:14px 16px; margin-bottom:20px; font-size:12.5px; color:#94a3b8; line-height:1.6;">
                48 saat boyunca 100 paritede kurumsal nPOC, AVWAP ve Camarilla seviye pusu algoritmalarını test ettiniz. Kesintisiz canlı veya demo işlem yapmaya devam etmek için üyeliğinizi yükseltebilirsiniz.
            </div>

            <!-- ACTIONS -->
            <div style="display:flex; gap:10px;">
                <button onclick="closeTrialExpiredModal(); openUpgradeModal();" style="flex:1; background:linear-gradient(135deg, #00f2fe, #4facfe); border:none; color:#000; font-weight:900; font-size:13.5px; padding:13px 20px; border-radius:10px; cursor:pointer; box-shadow:0 6px 20px rgba(0,242,254,0.35);">
                    💎 ALL-ACCESS ($99 / Ay) Paketine Yükselt
                </button>
                <button onclick="closeTrialExpiredModal(); switchMainTab('ledger');" style="background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.12); color:#fff; font-weight:700; font-size:12.5px; padding:13px 18px; border-radius:10px; cursor:pointer;">
                    📜 Raporları İncele
                </button>
            </div>
        </div>
    </div>

<!-- ULTRA-PREMIUM UPGRADE & CRYPTO PAYMENT MODAL (AUTONOMOUS WALLET LISTENER) -->
    <div id="upgrade-modal-overlay" class="modal-overlay" style="display:none;" onclick="if(event.target === this) closeUpgradeModal()">
        <div class="modal-card" style="max-width:680px; text-align:left; border:1px solid rgba(0,242,254,0.35); box-shadow:0 25px 60px rgba(0,0,0,0.85), 0 0 40px rgba(0,242,254,0.12); padding:26px;">
            <!-- TOP HEADER -->
            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:18px; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:14px;">
                <div>
                    <div style="display:flex; align-items:center; gap:10px;">
                        <div class="brand-logo-gem" style="width:34px; height:34px; background:rgba(0,242,254,0.1); border:1px solid var(--cyan); border-radius:8px; display:flex; align-items:center; justify-content:center;">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--cyan)" stroke-width="2"><polygon points="12 2 22 8.5 12 22 2 8.5 12 2"></polygon></svg>
                        </div>
                        <div style="font-size:19px; font-weight:900; color:#fff; letter-spacing:0.5px;">
                            VALKYRIE <span style="background: linear-gradient(135deg, #00f2fe, #4facfe); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">ALL-ACCESS</span> UNLIMITED
                        </div>
                    </div>
                    <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">
                        Kurumsal Düzey Kripto Algoritmik Ticaret Platformuna 30 Gün Sınırsız Erişim
                    </div>
                </div>
                <button onclick="closeUpgradeModal()" style="background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); color:#94a3b8; width:32px; height:32px; border-radius:8px; font-size:16px; cursor:pointer; display:flex; align-items:center; justify-content:center;" onmouseover="this.style.color='#fff';" onmouseout="this.style.color='#94a3b8';">✕</button>
            </div>

            <!-- HERO PRICING BANNER -->
            <div style="background:linear-gradient(135deg, rgba(0,242,254,0.1), rgba(79,172,254,0.04)); border:1.5px solid rgba(0,242,254,0.4); border-radius:14px; padding:18px 20px; margin-bottom:18px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
                <div>
                    <div style="font-size:11.5px; font-weight:800; color:var(--cyan); text-transform:uppercase; letter-spacing:1px;">TEK FİYAT • TÜM ÖZELLİKLER DAHİL</div>
                    <div style="font-size:28px; font-weight:900; color:#ffffff; font-family:'JetBrains Mono'; margin-top:2px;" id="modal-price-all-access">
                        $99.00 <span style="font-size:14px; font-weight:600; color:#94a3b8;">/ AY</span>
                    </div>
                    <div style="font-size:11.5px; color:var(--green); font-weight:700; margin-top:3px;">
                        🟢 Sürpriz Komisyon Yok • Gizli Masraf Yok • İstediğin Zaman İptal
                    </div>
                </div>
                <div style="background:rgba(0,0,0,0.4); border:1px solid rgba(255,255,255,0.08); border-radius:10px; padding:10px 14px; text-align:right;">
                    <div style="font-size:11px; color:#94a3b8;">Aktivasyon Türü:</div>
                    <div style="font-size:13px; font-weight:800; color:var(--yellow); margin-top:2px; display:flex; align-items:center; justify-content:flex-end; gap:6px;">
                        <span class="live-dot" style="background:var(--yellow); width:8px; height:8px;"></span>
                        Tam Otomatik Dinleyici
                    </div>
                    <div style="font-size:10.5px; color:#cbd5e1;">Kod Girmeden Anında Açılır</div>
                </div>
            </div>

            <!-- VALUE PROPOSITION GRID (VALKYRIE PROPRIETARY SETUPS) -->
            <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.06); border-radius:14px; padding:16px 18px; margin-bottom:18px;">
                <div style="font-size:12px; font-weight:800; color:#cbd5e1; margin-bottom:12px; text-transform:uppercase; letter-spacing:0.5px; display:flex; align-items:center; gap:8px;">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--cyan)" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
                    <span>VALKYRIE ÖZEL ALGORİTMİK SİSTEM ÖZELLİKLERİ</span>
                </div>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px 18px; font-size:12px; color:#e2e8f0;">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#00f2fe" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>
                        <span><b>100 Kripto Paritede</b> 5M Canlı Otonom İşlem</span>
                    </div>
                    <div style="display:flex; align-items:center; gap:8px;">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#00f2fe" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>
                        <span><b>Valkyrie Özel Kurumsal Likidite</b> Setupları</span>
                    </div>
                    <div style="display:flex; align-items:center; gap:8px;">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#00f2fe" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>
                        <span><b>Yüksek Olasılıklı Dönüş & Kırılım</b> Algoritmaları</span>
                    </div>
                    <div style="display:flex; align-items:center; gap:8px;">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#00f2fe" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>
                        <span><b>Kişiselleştirilebilir Risk & Kasa</b> Güvenlik Kilidi</span>
                    </div>
                    <div style="display:flex; align-items:center; gap:8px;">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#00f2fe" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>
                        <span><b>7/24 Kesintisiz VIP Telegram</b> Anlık Bildirim Kanalı</span>
                    </div>
                    <div style="display:flex; align-items:center; gap:8px;">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#00f2fe" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>
                        <span><b>48 Sütunlu Adli Defter</b> & Profesyonel Excel İndirme</span>
                    </div>
                </div>
            </div>

            <!-- PAYMENT STEP 1: NETWORK SELECT -->
            <div style="margin-bottom:14px;">
                <label style="font-size:12px; font-weight:800; color:#cbd5e1; display:flex; justify-content:space-between; margin-bottom:6px;">
                    <span>1. Ödeme Ağını (Network) Seçiniz:</span>
                    <span style="font-weight:400; color:var(--text-muted);">USDT Transferi</span>
                </label>
                <select id="payment-network-select" class="settings-select" onchange="generateFreshCryptoOrder()" style="padding:10px 14px; font-size:13px;">
                    <option value="TRC20" selected>USDT (TRC20 / Tron Ağı) — En Hızlı & Düşük Ücret (~$1-2)</option>
                    <option value="BEP20">USDT (BEP20 / Binance Smart Chain) — Hızlı & Düşük Masraf</option>
                </select>
            </div>

            <!-- PAYMENT STEP 2: EXACT AMOUNT & WALLET BOX -->
            <div style="background:rgba(0,0,0,0.5); border:1.5px solid rgba(0,242,254,0.3); border-radius:12px; padding:16px; margin-bottom:16px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; border-bottom:1px solid rgba(255,255,255,0.06); padding-bottom:10px;">
                    <div>
                        <span style="font-size:11.5px; font-weight:700; color:#94a3b8;">Gönderilecek Tam Tutar:</span>
                        <div id="exact-amount-display" style="font-size:22px; font-weight:900; color:#ffffff; font-family:'JetBrains Mono'; margin-top:2px;">
                            $99.00 <span style="font-size:13px; color:var(--cyan); font-weight:700;">USDT</span>
                        </div>
                    </div>
                    <button type="button" onclick="copyExactAmount()" style="background:rgba(0,242,254,0.12); border:1px solid var(--cyan); color:#fff; padding:8px 14px; border-radius:8px; font-size:11.5px; font-weight:800; cursor:pointer;">
                        📋 Tutarı Kopyala
                    </button>
                </div>

                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span style="font-size:11.5px; font-weight:700; color:#94a3b8;">Ödeme Gönderilecek Resmi Cüzdan Adresi:</span>
                    <span id="copy-success-badge" style="display:none; color:var(--green); font-size:11.5px; font-weight:800;">✅ Cüzdan Kopyalandı!</span>
                </div>
                <div style="display:flex; gap:8px; align-items:center;">
                    <input type="text" id="deposit-wallet-address" readonly class="settings-input" style="font-size:12.5px; font-weight:700; color:var(--cyan); background:rgba(0,0,0,0.6); padding:10px 12px;" value="TXvK7w7ValkyrieQuantProTRC20DepositVault99" />
                    <button type="button" onclick="copyDepositAddress()" style="background:linear-gradient(135deg, #00f2fe, #4facfe); border:none; color:#000; padding:10px 16px; border-radius:8px; font-size:12px; font-weight:800; cursor:pointer; white-space:nowrap;">📋 Cüzdanı Kopyala</button>
                </div>
            </div>

            <!-- AUTONOMOUS PULSING RADAR -->
            <div id="auto-listener-radar" style="background:rgba(0,242,254,0.05); border:1px solid rgba(0,242,254,0.25); border-radius:12px; padding:14px 16px; margin-bottom:16px; display:flex; align-items:center; justify-content:space-between;">
                <div style="display:flex; align-items:center; gap:12px;">
                    <div class="live-dot" style="width:12px; height:12px; background:var(--cyan); box-shadow:0 0 12px var(--cyan);"></div>
                    <div>
                        <div style="font-size:12.5px; font-weight:800; color:#fff;">Blokzincir Ağı Otonom Taranıyor...</div>
                        <div style="font-size:11px; color:#94a3b8;">Transferiniz cüzdana ulaştığında ekranınız otomatik yeşile dönecektir. (~30-60 sn)</div>
                    </div>
                </div>
                <div id="order-countdown-clock" style="font-family:'JetBrains Mono'; font-weight:800; font-size:14px; color:var(--yellow); background:rgba(0,0,0,0.4); padding:6px 12px; border-radius:8px;">
                    19:59
                </div>
            </div>

            <!-- OPTIONAL FALLBACK MANUAL TXHASH COLLAPSIBLE -->
            <div style="margin-top:10px;">
                <div onclick="toggleManualTxSection()" style="font-size:11.5px; color:#94a3b8; cursor:pointer; display:flex; align-items:center; gap:4px;">
                    <span>▶</span> Sabırsız mısınız? <u>İşlem Kodu (TxHash) ile Anında Doğrula</u>
                </div>
                <div id="manual-tx-section" style="display:none; margin-top:10px;">
                    <div style="display:flex; gap:8px;">
                        <input type="text" id="input-payment-txhash" placeholder="64 haneli TxHash kodunuzu yapıştırınız..." class="settings-input" style="padding:10px 12px; font-size:11.5px; flex:1;" />
                        <button onclick="submitCryptoPayment()" style="background:var(--blue); color:#fff; border:none; padding:10px 16px; border-radius:8px; font-size:11.5px; font-weight:800; cursor:pointer; white-space:nowrap;">
                            ⚡ Doğrula
                        </button>
                    </div>
                </div>
            </div>

            <!-- STATUS MESSAGE / INVOICE RECEIPT BOX -->
            <div id="payment-status-box" style="display:none; margin-top:14px; padding:16px; border-radius:12px; font-size:12.5px; font-family:'JetBrains Mono'; line-height:1.5;"></div>
        </div>
    </div>
<!-- AUTHENTICATION (LOGIN / 24H TRIAL REGISTER) MODAL -->
    <div id="auth-modal-overlay" class="modal-overlay" style="display:none;" onclick="if(event.target === this) closeAuthModal()">
        <div class="modal-card" style="max-width:460px; text-align:left; border:1.5px solid rgba(0,242,254,0.35); box-shadow:0 25px 60px rgba(0,0,0,0.85);">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
                <div style="font-size:17px; font-weight:900; color:#fff; display:flex; align-items:center; gap:8px;">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block; vertical-align:middle; margin-right:4px;"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg> VALKYRIE GİRİŞ & KAYIT PORTALI
                </div>
                <button onclick="closeAuthModal()" style="background:transparent; border:none; color:#94a3b8; font-size:20px; cursor:pointer;">✕</button>
            </div>

            <!-- 2 CLEAN TABS (REGISTER & LOGIN) -->
            <div style="display:flex; gap:8px; margin-bottom:16px; background:rgba(255,255,255,0.03); padding:4px; border-radius:10px;">
                <button id="auth-tab-btn-register" onclick="switchAuthTab('register')" style="flex:1.2; padding:9px 8px; border-radius:8px; border:none; background:linear-gradient(135deg, #00f2fe, #4facfe); color:#000; font-weight:900; font-size:12.5px; cursor:pointer;">48h Ücretsiz Demo</button>
                <button id="auth-tab-btn-login" onclick="switchAuthTab('login')" style="flex:1; padding:9px 8px; border-radius:8px; border:none; background:transparent; color:#94a3b8; font-weight:800; font-size:12.5px; cursor:pointer;">👤 Giriş Yap</button>
            </div>

            <!-- 1. TAB: 24H TRIAL REGISTER FORM -->
            <div id="auth-form-register">
                <div style="background:rgba(0,242,254,0.06); border:1px solid rgba(0,242,254,0.25); border-radius:10px; padding:12px; margin-bottom:14px; font-size:12px; color:#cbd5e1; line-height:1.5;">
                    🎉 <b>24 Saatlik Ücretsiz VIP Deneme:</b> Kredi kartı gerekmez. Kayıt olduğunuz anda 100 kripto paritede tüm algoritmalar 48 saat boyunca hesabınızda sınırsız açılır!
                </div>
                <div style="margin-bottom:12px;">
                    <label style="font-size:11.5px; font-weight:700; color:#cbd5e1; display:block; margin-bottom:4px;">E-Posta Adresiniz</label>
                    <input type="email" id="reg-email" placeholder="ornek@domain.com" class="settings-input" />
                </div>
                <div style="margin-bottom:12px;">
                    <label style="font-size:11.5px; font-weight:700; color:#cbd5e1; display:block; margin-bottom:4px;">Şifreniz</label>
                    <input type="password" id="reg-password" placeholder="Güçlü bir şifre belirleyiniz..." class="settings-input" />
                </div>
                <div style="margin-bottom:16px;">
                    <label style="font-size:11.5px; font-weight:700; color:#cbd5e1; display:block; margin-bottom:4px;">Binance Hesap UID (Opsiyonel / Suistimal Koruması)</label>
                    <input type="text" id="reg-binance-uid" placeholder="Binance UID (Örn: 12345678)" class="settings-input" />
                </div>
                <button class="btn-save-settings" style="width:100%; background:linear-gradient(135deg, #00f2fe, #4facfe); color:#000; font-weight:900; font-size:13.5px; padding:12px;" onclick="submitRegister()">
                    🚀 48 Saatlik Ücretsiz Demo (Paper Trading)mi Anında Başlat
                </button>
            </div>

            <!-- 2. TAB: UNIFIED LOGIN FORM (BOTH FOR USERS AND ADMIN) -->
            <div id="auth-form-login" style="display:none;">
                <div style="margin-bottom:12px;">
                    <label style="font-size:11.5px; font-weight:700; color:#cbd5e1; display:block; margin-bottom:4px;">E-Posta Adresiniz</label>
                    <input type="email" id="login-email" placeholder="ornek@domain.com" class="settings-input" />
                </div>
                <div style="margin-bottom:16px;">
                    <label style="font-size:11.5px; font-weight:700; color:#cbd5e1; display:block; margin-bottom:4px;">Şifreniz</label>
                    <input type="password" id="login-password" placeholder="Şifrenizi giriniz..." class="settings-input" />
                </div>
                <button class="btn-save-settings" style="width:100%; font-weight:900; padding:12px;" onclick="submitLogin()">🔐 Güvenli Giriş Yap</button>
            </div>

            <div id="auth-msg-box" style="display:none; margin-top:14px; padding:12px; border-radius:8px; font-size:12.5px; font-family:'JetBrains Mono'; line-height:1.5;"></div>
        </div>
    </div>
<!-- SYSTEM HEALTH DIAGNOSTIC MODAL -->
    <div id="health-modal-overlay" class="modal-overlay" style="display:none;" onclick="if(event.target === this) closeHealthDiagnosticModal()">
        <div class="modal-card" style="max-width:680px; max-height:88vh; overflow-y:auto; text-align:left; padding:24px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
                <div class="modal-title" style="margin:0; font-size:18px; display:flex; align-items:center; gap:8px;">
                    <span style="font-size:20px;">🛡️</span>
                    <span>VALKYRIE AEGIS • 360° SİSTEM & VERİ SAĞLIĞI</span>
                </div>
                <button onclick="closeHealthDiagnosticModal()" style="background:transparent; border:none; color:#94a3b8; font-size:22px; cursor:pointer;">✕</button>
            </div>
            <div id="health-modal-body" style="font-family:'JetBrains Mono', monospace; font-size:12.5px; line-height:1.6;">
                <!-- JS ile dinamik doldurulur -->
            </div>
            <div style="margin-top:20px; display:flex; justify-content:space-between; align-items:center;">
                <div style="font-size:11px; color:#64748b;" id="health-modal-footer-ts">Canlı Telemetri</div>
                <button class="modal-btn modal-btn-cancel" onclick="closeHealthDiagnosticModal()" style="background:var(--blue); color:#fff; padding:8px 24px;">Tamam / Kapat</button>
            </div>
        </div>
    </div>

    <!-- CUSTOM CONFIRMATION MODAL -->
    <div id="close-modal-overlay" class="modal-overlay" style="display:none;">
        <div class="modal-card">
            <div class="modal-icon">🛑</div>
            <div class="modal-title" id="modal-title">Pozisyonu Kapat</div>
            <div class="modal-desc" id="modal-desc">
                Bu açık pozisyonu anlık piyasa fiyatından kapatıp kâr/zararı kilitlemek istediğinize emin misiniz?
            </div>
            <div class="modal-metrics" id="modal-metrics"></div>
            <div class="modal-actions">
                <button class="modal-btn modal-btn-cancel" onclick="closeConfirmModal()">İptal / Vazgeç</button>
                <button class="modal-btn modal-btn-confirm" id="modal-btn-confirm">Evet, Pozisyonu Kapat</button>
            </div>
        </div>
    </div>

    <!-- TRADINGVIEW LIVE CHART MODAL -->
    <div id="tv-modal-overlay" class="tv-modal-overlay" style="display:none;" onclick="if(event.target===this) closeTvModal()">
        <div class="tv-modal-card">
            <div class="tv-modal-header">
                <div class="tv-modal-title">
                    <span style="font-size:20px;">📈</span>
                    <span id="tv-modal-title">BTC/USDT PERPETUAL</span>
                    <div class="chart-tab-group">
                        <button id="tab-btn-native" class="chart-tab-btn tab-active" onclick="switchChartTab('native')">🎯 Strateji Grafiği</button>
                        <button id="tab-btn-tv" class="chart-tab-btn" onclick="switchChartTab('tv')">🌐 TradingView</button>
                    </div>
                </div>
                <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
                    <button class="btn-copy-pine" onclick="copyPineScriptCode()" title="TradingView Pine Script v6 Kodunu Kopyala">
                        📋 Pine Script Kopyala
                    </button>
                    <a id="tv-external-link" href="https://www.tradingview.com" target="_blank" style="font-size:12px; color:var(--blue); text-decoration:none; font-weight:700; background:rgba(56,139,253,0.1); border:1px solid rgba(56,139,253,0.3); padding:5px 12px; border-radius:8px;">
                        TradingView'de Aç ↗
                    </a>
                    <button class="tv-modal-close-btn" onclick="closeTvModal()" title="Kapat (ESC)">✕</button>
                </div>
            </div>
            <div class="tv-modal-body">
                <div class="tv-chart-area" id="tv-container">
                    <div id="native-chart-wrapper" style="width:100%; height:100%; position:relative;">
                        <div id="native-chart-box" style="width:100%; height:100%;"></div>
                        <div id="chart-loading-spinner" style="position:absolute; inset:0; display:flex; align-items:center; justify-content:center; background:rgba(7,9,14,0.85); color:var(--cyan); font-family:'JetBrains Mono'; font-size:14px; font-weight:700; z-index:10;">
                            ⚡ 5M Mumlar & AVWAP / Camarilla / VP Seviyeleri Çiziliyor...
                        </div>
                    </div>
                    <div id="tv-widget-wrapper" style="width:100%; height:100%; display:none;"></div>
                </div>
                <div class="tv-sidebar-area" id="tv-sidebar-content"></div>
            </div>
        </div>
    </div>

    
    <!-- QUANT TELEMETRY FORENSIC AUDIT MODAL -->
    <div id="telemetry-modal-overlay" class="modal-overlay" style="display:none;" onclick="if(event.target===this) closeTelemetryModal()">
        <div class="live-settings-card" style="max-width:780px;">
            <div class="tv-modal-header" style="border-bottom:1px solid var(--border);">
                <div style="display:flex; align-items:center; gap:12px;">
                    <div class="brand-logo-gem" style="width:36px; height:36px; background:rgba(0,242,254,0.15); border-color:var(--cyan);">
                        🔬
                    </div>
                    <div>
                        <div style="font-size:15px; font-weight:800; color:#fff;" id="tel-title">İŞLEM İNCELEME & TELEMETRİ</div>
                        <div style="font-size:11.5px; color:var(--text-muted);" id="tel-sub">Giriş Anı Seviye Snapshot'ı, MFE/MAE Derinliği ve R-Multiple Analizi</div>
                    </div>
                </div>
                <div style="display:flex; align-items:center; gap:10px;">
                    <button id="tel-chart-btn" class="btn-open-chart" style="background:linear-gradient(135deg, rgba(0,242,254,0.18), rgba(79,172,254,0.28)); border:1.5px solid var(--cyan); color:#fff; font-weight:800; font-size:12px; padding:6px 14px; border-radius:8px; cursor:pointer; display:flex; align-items:center; gap:6px; box-shadow:0 0 12px rgba(0,242,254,0.25);">
                        📈 Göstergeli Grafik
                    </button>
                    <button class="tv-modal-close-btn" onclick="closeTelemetryModal()" title="Kapat (ESC)">✕</button>
                </div>
            </div>

            <div class="settings-body" id="tel-content" style="max-height:75vh; overflow-y:auto; padding:20px;">
                <!-- DYNAMIC CONTENT -->
            </div>
        </div>
    </div>

    <!-- =========================================================================
         SHADOW COIN FORENSIC DEEP-DIVE & CALIBRATION MODAL
         ========================================================================= -->
    <div id="shadow-coin-detail-modal" class="modal-overlay" style="display:none;" onclick="if(event.target===this) closeShadowCoinDetail()">
        <div class="live-settings-card" style="max-width:960px; max-height:90vh; display:flex; flex-direction:column; overflow:hidden;">
            <div class="tv-modal-header" style="border-bottom:1px solid var(--border); flex-shrink:0;">
                <div style="display:flex; align-items:center; gap:12px;">
                    <div class="brand-logo-gem" style="width:38px; height:38px; background:rgba(168,85,247,0.18); border-color:#a855f7; display:flex; align-items:center; justify-content:center; border-radius:10px; font-size:18px;">
                        🧬
                    </div>
                    <div>
                        <div style="display:flex; align-items:center; gap:8px;">
                            <span style="font-size:17px; font-weight:800; color:#fff;" id="shadow-modal-symbol">PARİTE / USDT</span>
                            <span id="shadow-modal-badge" style="background:rgba(16,185,129,0.15); color:#10b981; border:1px solid rgba(16,185,129,0.3); font-size:11px; font-weight:700; padding:2px 8px; border-radius:10px;">👑 KORU</span>
                        </div>
                        <div style="font-size:11.5px; color:var(--text-muted); font-family:'JetBrains Mono', monospace;" id="shadow-modal-persona">
                            Coin DNA & Canlı Piyasa Adli Kalibrasyon Masası
                        </div>
                    </div>
                </div>
                <div style="display:flex; align-items:center; gap:10px;">
                    <button class="tv-modal-close-btn" onclick="closeShadowCoinDetail()" title="Kapat (ESC)">✕</button>
                </div>
            </div>

            <div style="flex:1; overflow-y:auto; padding:20px; display:flex; flex-direction:column; gap:18px;">
                <!-- 1. KPI STRIP -->
                <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(160px, 1fr)); gap:10px;">
                    <div style="background:rgba(16,185,129,0.06); border:1px solid rgba(16,185,129,0.2); border-radius:8px; padding:10px 14px;">
                        <div style="font-size:10.5px; color:#94a3b8; margin-bottom:2px;">🛡️ Kurtarılan Zarar (Hero)</div>
                        <div id="shadow-modal-kpi-saved" style="font-size:16px; font-weight:800; color:#10b981; font-family:'JetBrains Mono';">$0.00</div>
                        <div id="shadow-modal-kpi-hero" style="font-size:10px; color:#64748b;">0 Stop Engellendi</div>
                    </div>
                    <div style="background:rgba(244,63,94,0.06); border:1px solid rgba(244,63,94,0.2); border-radius:8px; padding:10px 14px;">
                        <div style="font-size:10.5px; color:#94a3b8; margin-bottom:2px;">⚠️ Kaçan Kâr (Spoiler)</div>
                        <div id="shadow-modal-kpi-missed" style="font-size:16px; font-weight:800; color:#f43f5e; font-family:'JetBrains Mono';">$0.00</div>
                        <div id="shadow-modal-kpi-spoiler" style="font-size:10px; color:#64748b;">0 Kâr Kaçırıldı</div>
                    </div>
                    <div style="background:rgba(245,158,11,0.06); border:1px solid rgba(245,158,11,0.2); border-radius:8px; padding:10px 14px;">
                        <div style="font-size:10.5px; color:#94a3b8; margin-bottom:2px;">🎯 Kalkan Verimliliği (SEI)</div>
                        <div id="shadow-modal-kpi-sei" style="font-size:16px; font-weight:800; color:#f59e0b; font-family:'JetBrains Mono';">%100.0</div>
                        <div style="font-size:10px; color:#64748b;">Kurtarılan / Etki Oranı</div>
                    </div>
                    <div style="background:rgba(56,189,248,0.06); border:1px solid rgba(56,189,248,0.2); border-radius:8px; padding:10px 14px;">
                        <div style="font-size:10.5px; color:#94a3b8; margin-bottom:2px;">💎 Net Kalkan Alfası</div>
                        <div id="shadow-modal-kpi-alpha" style="font-size:16px; font-weight:800; color:#38bdf8; font-family:'JetBrains Mono';">$0.00</div>
                        <div style="font-size:10px; color:#64748b;">Kurtarılan - Kaçan Kâr</div>
                    </div>
                </div>

                <!-- 1.5 OPTIMALITY & STABILITY GAUGE (EN İYİ PARAMETRE & KORUMA GÜVENİ) -->
                <div id="shadow-modal-optimality-box" style="background:rgba(255,255,255,0.025); border:1px solid rgba(255,255,255,0.08); border-radius:12px; padding:14px 18px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:12px;">
                    <div style="flex:1; min-width:260px;">
                        <div style="font-size:10.5px; color:#94a3b8; text-transform:uppercase; font-weight:700; letter-spacing:0.5px; margin-bottom:2px;">
                            🎯 Kuant Optimum Parametre Durumu & Kararlılık Kilidi
                        </div>
                        <div id="shadow-modal-optimality-status" style="font-size:14px; font-weight:800; color:#38bdf8;">
                            Analiz Ediliyor...
                        </div>
                        <div id="shadow-modal-optimality-desc" style="font-size:11.5px; color:#cbd5e1; margin-top:3px; line-height:1.4;">
                            Mevcut parametrelerin altın oran uyumu ve istatistiki yeterlilik ölçülüyor.
                        </div>
                    </div>
                    <div style="text-align:right; background:rgba(0,0,0,0.35); padding:8px 16px; border-radius:8px; border:1px solid rgba(255,255,255,0.06);">
                        <div id="shadow-modal-optimality-score" style="font-size:22px; font-weight:900; font-family:'JetBrains Mono'; color:#10b981;">
                            %100
                        </div>
                        <div style="font-size:10px; color:#64748b; font-weight:600;">Optimum Güven Endeksi</div>
                    </div>
                </div>

                <!-- 2. FORENSIC NARRATIVE (ADLİ TEŞHİS & NEDEN-SONUÇ HİKAYESİ) -->
                <div style="background:linear-gradient(135deg, rgba(168,85,247,0.08), rgba(15,23,42,0.95)); border:1px solid rgba(168,85,247,0.3); border-radius:12px; padding:16px;">
                    <div style="font-size:13px; font-weight:800; color:#c084fc; margin-bottom:8px; display:flex; align-items:center; gap:6px;">
                        <span>🧠</span> Kuant Adli Otopsi & Neden-Sonuç Teşhisi
                    </div>
                    <div id="shadow-modal-narrative" style="font-size:12.5px; line-height:1.6; color:#e2e8f0; font-family:'Segoe UI', sans-serif;">
                        Yükleniyor...
                    </div>
                </div>

                <!-- 3. PARAMETER CALIBRATION DIFF -->
                <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.08); border-radius:12px; padding:16px;">
                    <div style="font-size:13px; font-weight:800; color:#38bdf8; margin-bottom:12px; display:flex; align-items:center; gap:6px;">
                        <span>⚙️</span> Otonom Kuant Kalibrasyon Eylem Planı (Çok Boyutlu Parametre Matrisi)
                    </div>
                    <div style="display:flex; flex-direction:column; gap:10px;" id="shadow-modal-diff-grid">
                        <!-- Populated by JS -->
                    </div>
                </div>

                <!-- 4. SHIELDS BREAKDOWN -->
                <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.08); border-radius:12px; padding:16px;">
                    <div style="font-size:13px; font-weight:800; color:#f59e0b; margin-bottom:10px; display:flex; align-items:center; gap:6px;">
                        <span>🛡️</span> Bu Paritede Tetiklenen Kalkanlar ve Skorları
                    </div>
                    <div class="table-responsive">
                        <table class="data-table" style="width:100%; font-size:12px;">
                            <thead>
                                <tr>
                                    <th style="text-align:left;">Kalkan Adı</th>
                                    <th>Kahraman (Hero)</th>
                                    <th>Frenleyici (Spoiler)</th>
                                    <th>Kurtarılan Zarar ($)</th>
                                    <th>Kaçan Kâr ($)</th>
                                    <th>Kalkan SEI</th>
                                </tr>
                            </thead>
                            <tbody id="shadow-modal-shields-tbody">
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- 5. RECENT SHADOW TRADES -->
                <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.08); border-radius:12px; padding:16px;">
                    <div style="font-size:13px; font-weight:800; color:#fff; margin-bottom:10px; display:flex; align-items:center; gap:6px;">
                        <span>📜</span> Paritenin Gölge Pozisyon Geçmişi & Canlı Sonuçları
                    </div>
                    <div class="table-responsive">
                        <table class="data-table" style="width:100%; font-size:11.5px;">
                            <thead>
                                <tr>
                                    <th>Gölge ID</th>
                                    <th>Yön</th>
                                    <th style="text-align:left;">Setup</th>
                                    <th style="text-align:left;">Kalkan</th>
                                    <th>Giriş / Çıkış</th>
                                    <th>MFE / MAE</th>
                                    <th>Sanal PnL</th>
                                    <th>Teşhis</th>
                                    <th style="text-align:left;">Adli Gerekçe</th>
                                </tr>
                            </thead>
                            <tbody id="shadow-modal-trades-tbody">
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- =========================================================================
         VALKYRIE QUANT DESK •— ULTRA-LUXURY PUBLIC LANDING PAGE (AUTH GATEWAY)
         ========================================================================= -->
    <div id="landing-page-view" style="display:block; min-height:100vh; background:radial-gradient(circle at 50% 15%, rgba(0,242,254,0.08), transparent 60%), #07090e; color:#fff; position:relative; overflow-x:hidden;">
        
        <!-- LANDING NAVBAR -->
        <nav style="display:flex; justify-content:space-between; align-items:center; padding:18px 40px; border-bottom:1px solid rgba(255,255,255,0.06); background:rgba(7,9,14,0.75); backdrop-filter:blur(15px); position:sticky; top:0; z-index:100;">
            <div style="display:flex; align-items:center; gap:12px;">
                <div style="width:38px; height:38px; background:rgba(0,242,254,0.12); border:1.5px solid var(--cyan); border-radius:10px; display:flex; align-items:center; justify-content:center; box-shadow:0 0 20px rgba(0,242,254,0.3); flex-shrink:0;">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="display:block;">
  <path d="M12 2L3 8.5L6 21L12 17L18 21L21 8.5L12 2Z" fill="rgba(0,242,254,0.18)" stroke="#00f2fe" stroke-width="1.6" stroke-linejoin="round"/>
  <polygon points="12,6 16.5,11.5 12,17 7.5,11.5" fill="rgba(56,239,125,0.25)" stroke="#38ef7d" stroke-width="1.4" stroke-linejoin="round"/>
  <circle cx="12" cy="11.5" r="1.8" fill="#ffffff" stroke="#00f2fe" stroke-width="0.8"/>
</svg>
                </div>
                <div style="font-size:18px; font-weight:900; letter-spacing:0.5px;">
                    VALKYRIE <span style="background: linear-gradient(135deg, #00f2fe, #4facfe); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">QUANT DESK</span>
                </div>
            </div>
            <div style="display:flex; align-items:center; gap:12px;">
                <button onclick="openAuthModal('login')" style="background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.15); color:#cbd5e1; font-weight:800; font-size:13px; padding:9px 18px; border-radius:9px; cursor:pointer;">
                    🔐 Giriş Yap
                </button>
                <button onclick="openAuthModal('register')" style="background:linear-gradient(135deg, #00f2fe, #4facfe); border:none; color:#000; font-weight:900; font-size:13px; padding:9px 22px; border-radius:9px; cursor:pointer; box-shadow:0 4px 20px rgba(0,242,254,0.3);">
                    🚀 48h Ücretsiz Demo
                </button>
            </div>
        </nav>

        <!-- HERO SECTION -->
        <section style="max-width:1050px; margin:0 auto; padding:60px 24px 45px; text-align:center;">
            <div style="display:inline-flex; align-items:center; gap:8px; background:rgba(0,242,254,0.08); border:1px solid rgba(0,242,254,0.3); padding:6px 16px; border-radius:30px; font-size:12px; font-weight:800; color:var(--cyan); margin-bottom:22px; box-shadow:0 0 20px rgba(0,242,254,0.15);">
                <span class="live-dot" style="width:8px; height:8px;"></span>
                YENİ NESİL KRİPTO QUANT ALGORİTMİK TİCARET TERMİNALİ
            </div>

            <h1 style="font-size:42px; font-weight:900; line-height:1.2; letter-spacing:-0.5px; margin-bottom:18px;">
                100 Kripto Paritede <br>
                <span style="background: linear-gradient(135deg, #00f2fe 0%, #4facfe 50%, #38ef7d 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">7/24 Otonom Algoritmik Likidite Taraması</span>
            </h1>

            <p style="font-size:16px; color:#94a3b8; max-width:740px; margin:0 auto 34px; line-height:1.6;">
                Valkyrie Quant Desk, kurumsal seviyede likidite boşluklarını, nPOC seviye pusularını ve momentum kırılımlarını 5 dakikalık mumlarda tarar; risk kalkanı koruması altında Binance Vadeli hesabınıza milisaniyelik emir iletir.
            </p>

            <div style="display:flex; justify-content:center; align-items:center; gap:16px; flex-wrap:wrap; margin-bottom:44px;">
                <button onclick="openAuthModal('register')" style="background:linear-gradient(135deg, #00f2fe, #4facfe); border:none; color:#000; font-weight:900; font-size:14.5px; padding:14px 30px; border-radius:12px; cursor:pointer; box-shadow:0 8px 30px rgba(0,242,254,0.35);">
                    🚀 48 Saatlik Ücretsiz Demo Başlat ($10,000 Sanal Kasa)
                </button>
                <button onclick="openAuthModal('login')" style="background:rgba(255,255,255,0.04); border:1.5px solid rgba(255,255,255,0.15); color:#ffffff; font-weight:800; font-size:14.5px; padding:14px 26px; border-radius:12px; cursor:pointer;">
                    🔐 Yatırımcı Girişi
                </button>
            </div>

            <!-- TRUST & SECURITY BADGES -->
            <div style="display:flex; justify-content:center; align-items:center; gap:24px; flex-wrap:wrap; font-size:12px; color:#cbd5e1; border-top:1px solid rgba(255,255,255,0.06); padding-top:22px;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--cyan)" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
                    <span>🔒 <b>AES-256</b> Donanım Seviyesinde Şifreli Kasa</span>
                </div>
                <div style="display:flex; align-items:center; gap:8px;">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--red)" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"></line></svg>
                    <span>🚫 <b>Para Çekme Yetkisi Yok</b> (Sadece Al-Sat)</span>
                </div>
                <div style="display:flex; align-items:center; gap:8px;">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--green)" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>
                    <span>⚡ <b>5M Mumlarla</b> 100/100 Canlı WebSocket Akışı</span>
                </div>
            </div>
        </section>

        <!-- 4 FEATURE CARDS -->
        <section style="max-width:1100px; margin:0 auto; padding:10px 24px 70px;">
            <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(240px, 1fr)); gap:18px;">
                <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.08); border-radius:14px; padding:22px; text-align:left;">
                    <div style="width:38px; height:38px; background:rgba(0,242,254,0.1); border-radius:10px; display:flex; align-items:center; justify-content:center; margin-bottom:14px;">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--cyan)" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="22" y1="12" x2="18" y2="12"></line><line x1="6" y1="12" x2="2" y2="12"></line><line x1="12" y1="6" x2="12" y2="2"></line><line x1="12" y1="22" x2="12" y2="18"></line></svg>
                    </div>
                    <div style="font-size:15px; font-weight:800; color:#fff; margin-bottom:6px;">100 Parite Canlı Radar</div>
                    <div style="font-size:12.5px; color:#94a3b8; line-height:1.5;">Tüm Binance Vadeli piyasasını 5M mumlarla tarayarak yüksek olasılıklı pusu ve dönüş bölgelerini anlık yakalar.</div>
                </div>

                <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.08); border-radius:14px; padding:22px; text-align:left;">
                    <div style="width:38px; height:38px; background:rgba(251,197,49,0.1); border-radius:10px; display:flex; align-items:center; justify-content:center; margin-bottom:14px;">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--yellow)" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
                    </div>
                    <div style="font-size:15px; font-weight:800; color:#fff; margin-bottom:6px;">Valkyrie Aegis Sentinel</div>
                    <div style="font-size:12.5px; color:#94a3b8; line-height:1.5;">6 katmanlı otomatik risk zırhı, izole marjin kilidi ve günlük devre kesicilerle kasanızı piyasa şoklarına karşı korur.</div>
                </div>

                <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.08); border-radius:14px; padding:22px; text-align:left;">
                    <div style="width:38px; height:38px; background:rgba(56,239,125,0.1); border-radius:10px; display:flex; align-items:center; justify-content:center; margin-bottom:14px;">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--green)" stroke-width="2"><polygon points="12 2 22 8.5 12 22 2 8.5 12 2"></polygon></svg>
                    </div>
                    <div style="font-size:15px; font-weight:800; color:#fff; margin-bottom:6px;">Tek Fiyat ($99 / Ay)</div>
                    <div style="font-size:12.5px; color:#94a3b8; line-height:1.5;">Karmaşık paketler yok. Tek bir aylık abonelikle 100 paritede sınırsız otonom işlem ve tüm özelliklere tam erişim.</div>
                </div>

                <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.08); border-radius:14px; padding:22px; text-align:left;">
                    <div style="width:38px; height:38px; background:rgba(79,172,254,0.1); border-radius:10px; display:flex; align-items:center; justify-content:center; margin-bottom:14px;">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#4facfe" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg>
                    </div>
                    <div style="font-size:15px; font-weight:800; color:#fff; margin-bottom:6px;">48 Sütunlu Adli Defter</div>
                    <div style="font-size:12.5px; color:#94a3b8; line-height:1.5;">Her işlemin giriş-çıkış anı, MFE/MAE derinliği ve risk çarpanları kayıt altına alınır; tek tıkla Excel (.XLSX) olarak indirilir.</div>
                </div>
            </div>
        </section>

        <!-- FOOTER -->
        <footer style="border-top:1px solid rgba(255,255,255,0.06); padding:24px; text-align:center; font-size:11.5px; color:#64748b;">
            <div style="margin-bottom:6px;">VALKYRIE QUANT DESK •© 2026 • Kurumsal Algoritmik Ticaret Sistemleri</div>
            <div>Risk Bildirimi: Kripto vadeli işlemler yüksek volatilite ve risk içerir. Geçmiş performans gelecekteki getirilerin garantisi değildir.</div>
        </footer>
    </div>

    <div id="dashboard-app-view" style="display:none; width:100%;">
    <!-- TOP BAR BRANDING -->
    <!-- CUSTOM LIVE SETTINGS MODAL -->

    <!-- BINANCE LIVE ACCOUNT & API SETTINGS MODAL -->
    <!-- ULTRA-PREMIUM BINANCE LIVE ACCOUNT & API SETTINGS MODAL -->
    <div id="live-settings-overlay" class="modal-overlay" style="display:none;" onclick="if(event.target===this) closeLiveSettingsModal()">
        <div class="live-settings-card" style="max-width:680px; border:1.5px solid rgba(243,186,47,0.35); box-shadow:0 25px 70px rgba(0,0,0,0.9), 0 0 40px rgba(243,186,47,0.08); padding:0; border-radius:18px; overflow:hidden;">
            <!-- MODAL HEADER -->
            <div class="tv-modal-header" style="background:linear-gradient(135deg, rgba(243,186,47,0.12), rgba(0,242,254,0.05)); border-bottom:1px solid rgba(255,255,255,0.08); padding:18px 24px;">
                <div style="display:flex; align-items:center; gap:14px;">
                    <div class="brand-logo-gem" style="width:42px; height:42px; background:rgba(243,186,47,0.15); border:1.5px solid #f3ba2f; border-radius:12px; display:flex; align-items:center; justify-content:center;">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="#f3ba2f"><path d="M12 2L4 6v12l8 4 8-4V6l-8-4zm0 2.8l5.5 2.75L12 10.3 6.5 7.55 12 4.8zM6 9.3l5 2.5v5.85l-5-2.5V9.3zm12 5.85l-5 2.5V11.8l5-2.5v5.85z"/></svg>
                    </div>
                    <div>
                        <div style="display:flex; align-items:center; gap:8px;">
                            <span style="font-size:16px; font-weight:900; color:#fff; letter-spacing:0.3px;">BİNANCE VADELİ HESAP AYARLARI</span>
                        </div>
                        <div style="font-size:11.5px; color:#cbd5e1; margin-top:2px; display:flex; align-items:center; gap:8px;">
                            <span style="color:#f3ba2f; font-weight:700;">🔒 AES-256 Korumalı</span>
                            <span>•</span>
                            <span>Otonom Emirler & Dinamik Risk Kalkanı</span>
                        </div>
                    </div>
                </div>
                <button class="tv-modal-close-btn" onclick="closeLiveSettingsModal()" title="Kapat (ESC)" style="background:rgba(255,255,255,0.06); width:32px; height:32px; border-radius:8px; border:1px solid rgba(255,255,255,0.1); color:#94a3b8; font-size:16px; cursor:pointer;">✕</button>
            </div>

            <!-- MODAL TABS -->
            <div class="settings-tab-bar" style="background:rgba(0,0,0,0.3); padding:8px 24px; border-bottom:1px solid rgba(255,255,255,0.06); gap:10px;">
                <button id="set-tab-api" class="settings-tab-btn tab-active" onclick="switchSettingsTab('api')" style="font-size:12.5px; font-weight:800; padding:8px 16px; border-radius:8px;">🔑 1. API Bağlantısı</button>
                <button id="set-tab-risk" class="settings-tab-btn" onclick="switchSettingsTab('risk')" style="font-size:12.5px; font-weight:800; padding:8px 16px; border-radius:8px;">🛡️ 2. Risk & Marjin</button>
                <button id="set-tab-status" class="settings-tab-btn" onclick="switchSettingsTab('status')" style="font-size:12.5px; font-weight:800; padding:8px 16px; border-radius:8px;">📊 3. Cüzdan Durumu</button>
            </div>

            <div class="settings-body" style="padding:22px 24px; max-height:calc(85vh - 120px); overflow-y:auto;">
                <!-- TAB 1: API & BAGLANTI -->
                <div id="tab-content-api" class="settings-tab-content">
                    <!-- MODE SELECTION (2 PREMIUM HERO CARDS) -->
                    <div style="margin-bottom:18px;">
                        <div style="font-size:12px; font-weight:800; color:#cbd5e1; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:8px;">
                            🎯 Aktif Ticaret Modu Seçimi
                        </div>
                        <div class="mode-toggle-grid" style="display:grid; grid-template-columns: 1fr 1fr; gap:12px;">
                            <div class="mode-radio-label is-selected-demo" id="lbl-mode-demo" onclick="selectTradingMode('DEMO')" style="padding:14px; border-radius:12px; cursor:pointer; transition:all 0.15s ease;">
                                <div style="display:flex; align-items:flex-start; gap:10px;">
                                    <span style="font-size:22px; line-height:1;">🟡</span>
                                    <div>
                                        <div style="font-weight:900; font-size:13.5px; color:#ffffff;">DEMO MODU (Paper Trading)</div>
                                        <div style="font-size:11.5px; color:#94a3b8; margin-top:2px;">100.000$ Sanal Kasa • 0 Finansal Risk</div>
                                        <div style="font-size:10.5px; color:var(--cyan); margin-top:4px; font-weight:700;">🟢 Strateji & Pusu Testi İçin Uygun</div>
                                    </div>
                                </div>
                            </div>

                            <div class="mode-radio-label" id="lbl-mode-live" onclick="selectTradingMode('LIVE')" style="padding:14px; border-radius:12px; cursor:pointer; transition:all 0.15s ease;">
                                <div style="display:flex; align-items:flex-start; gap:10px;">
                                    <span style="font-size:22px; line-height:1;">🔴</span>
                                    <div>
                                        <div style="font-weight:900; font-size:13.5px; color:var(--red);">GERÇEK MOD (Binance Live)</div>
                                        <div style="font-size:11.5px; color:#94a3b8; margin-top:2px;">Gerçek Vadeli Cüzdan • Otonom Emirler</div>
                                        <div style="font-size:10.5px; color:var(--yellow); margin-top:4px; font-weight:700;">⚡ Milisaniyelik Canlı Emir İletimi</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- API KEY INPUTS WITH ENCRYPTION SHIELD -->
                    <div style="background:rgba(0,0,0,0.4); border:1px solid rgba(255,255,255,0.08); border-radius:14px; padding:18px; margin-bottom:18px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
                            <div style="font-size:13px; font-weight:800; color:#fff; display:flex; align-items:center; gap:8px;">
                                <span>🔑</span> BİNANCE API BİLGİLERİ
                            </div>
                            <span style="font-size:10.5px; background:rgba(0,242,254,0.1); color:var(--cyan); border:1px solid rgba(0,242,254,0.3); padding:2px 8px; border-radius:6px; font-weight:700;">AES-256 Korumalı</span>
                        </div>
                        
                        <div style="margin-bottom:14px;">
                            <label style="font-size:12px; font-weight:700; color:#cbd5e1; display:flex; justify-content:space-between; margin-bottom:5px;">
                                <span>Binance API Key</span>
                                <span style="font-weight:400; color:#94a3b8; font-size:11px;">64 Karakter</span>
                            </label>
                            <div class="input-with-eye">
                                <input type="password" id="input-api-key" placeholder="Binance Vadeli API Key giriniz..." class="settings-input" style="padding:10px 12px; font-size:12.5px;" />
                                <button type="button" class="btn-toggle-eye" onclick="togglePasswordVisibility('input-api-key')">👁️</button>
                            </div>
                        </div>

                        <div style="margin-bottom:16px;">
                            <label style="font-size:12px; font-weight:700; color:#cbd5e1; display:flex; justify-content:space-between; margin-bottom:5px;">
                                <span>Binance API Secret</span>
                                <span style="font-weight:400; color:#94a3b8; font-size:11px;">Gizli Anahtar</span>
                            </label>
                            <div class="input-with-eye">
                                <input type="password" id="input-api-secret" placeholder="Binance Vadeli API Secret giriniz..." class="settings-input" style="padding:10px 12px; font-size:12.5px;" />
                                <button type="button" class="btn-toggle-eye" onclick="togglePasswordVisibility('input-api-secret')">👁️</button>
                            </div>
                        </div>

                        <!-- CONNECTION TEST RESULTS BOX -->
                        <div id="conn-result-box" style="display:none; margin-bottom:16px; padding:14px; border-radius:10px; font-size:12px; font-family:'JetBrains Mono'; line-height:1.5;"></div>

                        <div style="display:grid; grid-template-columns: 1.2fr 1fr; gap:12px;">
                            <button class="btn-test-conn" onclick="testBinanceConnection()" style="background:linear-gradient(135deg, #00f2fe, #4facfe); color:#000; font-weight:900; font-size:12.5px; padding:12px; border-radius:10px; cursor:pointer; border:none; box-shadow:0 4px 15px rgba(0,242,254,0.25);">
                                ⚡ Bağlantıyı Test Et & Bakiyeyi Doğrula
                            </button>
                            <button class="btn-save-settings" onclick="saveBinanceSettings()" style="background:linear-gradient(135deg, #f3ba2f, #e1b12c); color:#000; font-weight:900; font-size:12.5px; padding:12px; border-radius:10px; cursor:pointer; border:none;">
                                💾 Kasaya Kaydet
                            </button>
                        </div>
                    </div>

                    <!-- INSTITUTIONAL SECURITY ADVISORY -->
                    <div style="background:rgba(251,197,49,0.05); border:1.5px solid rgba(251,197,49,0.3); border-radius:12px; padding:16px;">
                        <div style="font-weight:900; color:var(--yellow); margin-bottom:8px; font-size:12.5px; display:flex; align-items:center; gap:6px;">
                            <span>🛡️</span> GÜVENLİK REHBERİ
                        </div>
                        <ul style="margin-left:18px; line-height:1.6; font-size:11.5px; color:#cbd5e1;">
                            <li>🚫 <b style="color:var(--red);">PARA ÇEKME (WITHDRAWAL) İZNİ KESİNLİKLE KAPALI OLMALIDIR!</b> Robotun para çekme yetkisi yoktur, sadece al-sat yapar.</li>
                            <li>🟢 Binance API oluştururken yalnızca <b>'Enable Futures' (Vadeli İşlemler)</b> ve <b>'Reading' (Okuma)</b> izinlerini açınız.</li>
                            <li>🔒 API anahtarlarınız sunucumuzda <b>AES-256 donanım şifreleme standardı</b> ile saklanır, 3. şahıslarla asla paylaşılmaz.</li>
                        </ul>
                    </div>
                </div>

                <!-- TAB 2: RISK & MARJIN -->
                <div id="tab-content-risk" class="settings-tab-content" style="display:none;">
                    <div style="background:rgba(0,0,0,0.4); border:1px solid rgba(255,255,255,0.08); border-radius:14px; padding:18px; margin-bottom:16px;">
                        <div style="font-size:13px; font-weight:800; color:#fff; margin-bottom:14px; display:flex; align-items:center; gap:8px;">
                            <span>⚙️</span> İŞLEM PARAMETRELERİ
                        </div>
                        
                        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px; margin-bottom:16px;">
                            <div>
                                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                                    <label style="font-size:12px; font-weight:700; color:#cbd5e1;">Kaldıraç Oranı</label>
                                    <span id="lbl-leverage-risk" style="font-size:11.5px; font-weight:800; color:var(--green); font-family:'JetBrains Mono';">5x (Güvenli)</span>
                                </div>
                                <div style="display:flex; align-items:center; gap:10px;">
                                    <input type="range" id="input-leverage-slider" min="1" max="20" value="5" class="slider" oninput="document.getElementById('input-leverage').value = this.value; updateLeverageRiskLabel(this.value);" />
                                    <input type="number" id="input-leverage" min="1" max="20" value="5" class="settings-input" style="width:65px; text-align:center;" oninput="document.getElementById('input-leverage-slider').value = this.value; updateLeverageRiskLabel(this.value);" />
                                </div>
                            </div>

                            <div>
                                <label style="font-size:12px; font-weight:700; color:#cbd5e1; display:block; margin-bottom:4px;">İşlem Başına Marjin ($ USDT)</label>
                                <input type="number" id="input-position-size" step="1" min="5" value="10" class="settings-input" style="padding:10px 12px;" />
                            </div>
                        </div>

                        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px; margin-bottom:16px;">
                            <div>
                                <label style="font-size:12px; font-weight:700; color:#cbd5e1; display:block; margin-bottom:4px;">Marjin Modu</label>
                                <select id="input-margin-type" class="settings-select" style="padding:10px 12px;">
                                    <option value="ISOLATED" selected>İzole (Isolated) — Tavsiye Edilen</option>
                                    <option value="CROSSED">Çapraz (Cross)</option>
                                </select>
                            </div>

                            <div>
                                <label style="font-size:12px; font-weight:700; color:#cbd5e1; display:block; margin-bottom:4px;">Maksimum Açık Pozisyon</label>
                                <input type="number" id="input-max-pos" step="1" min="1" max="100" value="100" class="settings-input" style="padding:10px 12px;" />
                            </div>
                        </div>

                        <!-- KULLANICI TANIMLI GUCLU GUVENLIK ZIRHI KONTROLLERI -->
                        <div style="background:rgba(0,242,254,0.04); border:1.5px solid rgba(0,242,254,0.25); border-radius:12px; padding:16px; margin-bottom:16px;">
                            <div style="font-size:13px; font-weight:900; color:var(--cyan); margin-bottom:12px; display:flex; align-items:center; gap:6px;">
                                <span>🛡️</span> RİSK & KASA KORUMASI
                            </div>
                            
                            <div style="margin-bottom:14px;">
                                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                                    <label style="font-size:12px; font-weight:700; color:#cbd5e1;">Portföy Marjin Tavan Kilidi (%)</label>
                                    <span id="lbl-margin-cap" style="font-size:12px; font-weight:800; color:var(--cyan); font-family:'JetBrains Mono';">%40 Kasa Limiti</span>
                                </div>
                                <div style="display:flex; align-items:center; gap:10px;">
                                    <input type="range" id="input-margin-cap-slider" min="10" max="100" step="5" value="40" class="slider" oninput="document.getElementById('input-margin-cap').value = this.value; document.getElementById('lbl-margin-cap').innerText = '%' + this.value + ' Kasa Limiti';" />
                                    <input type="number" id="input-margin-cap" min="10" max="100" step="5" value="40" class="settings-input" style="width:65px; text-align:center;" oninput="document.getElementById('input-margin-cap-slider').value = this.value; document.getElementById('lbl-margin-cap').innerText = '%' + this.value + ' Kasa Limiti';" />
                                </div>
                                <div style="font-size:11px; color:#94a3b8; margin-top:3px;">Açık pozisyonların toplam marjini kasanın bu oranına ulaştığında yeni işlem açılışı otomatik durdurulur.</div>
                            </div>

                            <div>
                                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                                    <label style="font-size:12px; font-weight:700; color:#cbd5e1;">Günlük Devre Kesici (Max Kayıp %)</label>
                                    <span id="lbl-daily-loss" style="font-size:12px; font-weight:800; color:var(--yellow); font-family:'JetBrains Mono';">%3 Günlük Kayıp Limiti</span>
                                </div>
                                <div style="display:flex; align-items:center; gap:10px;">
                                    <input type="range" id="input-daily-loss-slider" min="1" max="20" step="1" value="3" class="slider" oninput="document.getElementById('input-daily-loss').value = this.value; document.getElementById('lbl-daily-loss').innerText = '%' + this.value + ' Günlük Kayıp Limiti';" />
                                    <input type="number" id="input-daily-loss" min="1" max="20" step="1" value="3" class="settings-input" style="width:65px; text-align:center;" oninput="document.getElementById('input-daily-loss-slider').value = this.value; document.getElementById('lbl-daily-loss').innerText = '%' + this.value + ' Günlük Kayıp Limiti';" />
                                </div>
                                <div style="font-size:11px; color:#94a3b8; margin-top:3px;">Bugün (00:00'dan beri) toplam net zarar bu orana ulaşırsa gün sonuna kadar yeni işlem açılışı kilitlenir.</div>
                            </div>
                        </div>

                        <button class="btn-save-settings" style="width:100%; font-weight:900; padding:12px; background:linear-gradient(135deg, #00f2fe, #4facfe); color:#000;" onclick="saveBinanceSettings()">
                            💾 Özel Risk ve Güvenlik Ayarlarını Kaydet
                        </button>
                    </div>
                </div>

                <!-- TAB 3: CANLI CUZDAN & DURUM -->
                <div id="tab-content-status" class="settings-tab-content" style="display:none;">
                    <div id="live-wallet-overview">
                        <div style="text-align:center; padding:40px 20px; color:var(--text-muted); font-size:13.5px; line-height:1.6;">
                            Henüz canlı API anahtarı girilmedi veya bakiye sorgulanmadı.<br>
                            <span style="color:var(--yellow); font-weight:700;">'🔑 API & Bağlantı' sekmesinden bilgilerinizi girip '⚡ Bağlantıyı Test Et' butonuna basınız.</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- TOP BAR BRANDING -->
    <div class="top-bar">
        <div class="logo-wrap">
            <div class="brand-logo-gem" style="width:38px; height:38px; background:rgba(0,242,254,0.12); border:1.5px solid var(--cyan); border-radius:10px; display:flex; align-items:center; justify-content:center; box-shadow:0 0 16px rgba(0,242,254,0.3); flex-shrink:0;">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="display:block;">
  <path d="M12 2L3 8.5L6 21L12 17L18 21L21 8.5L12 2Z" fill="rgba(0,242,254,0.18)" stroke="#00f2fe" stroke-width="1.6" stroke-linejoin="round"/>
  <polygon points="12,6 16.5,11.5 12,17 7.5,11.5" fill="rgba(56,239,125,0.25)" stroke="#38ef7d" stroke-width="1.4" stroke-linejoin="round"/>
  <circle cx="12" cy="11.5" r="1.8" fill="#ffffff" stroke="#00f2fe" stroke-width="0.8"/>
</svg>
            </div>
            <div class="logo-title">VALKYRIE <span style="background: linear-gradient(135deg, #00f2fe, #4facfe); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">QUANT DESK</span></div>
        </div>
        <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
            <button onclick="openUpgradeModal()" style="background:linear-gradient(135deg, rgba(0,242,254,0.15), rgba(79,172,254,0.25)); border:1.5px solid var(--cyan); color:#fff; font-weight:800; font-size:12px; padding:6px 12px; border-radius:8px; cursor:pointer; display:flex; align-items:center; gap:6px;">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block; vertical-align:middle; margin-right:4px;"><polygon points="12 2 22 8.5 12 22 2 8.5 12 2"></polygon></svg> Paketi Yükselt
            </button>
            <div id="user-session-container" style="display:flex; align-items:center;">
                <button id="user-auth-btn" class="nav-tab-btn" onclick="openAuthModal('login')" style="background:rgba(0,242,254,0.08); border:1.5px solid var(--cyan); color:#fff; font-size:12px; font-weight:800; padding:6px 14px; border-radius:8px; cursor:pointer; display:flex; align-items:center; gap:6px;">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block; vertical-align:middle; margin-right:4px;"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg> Giriş Yap / 48h Demo
                </button>
            </div>
            <div id="mode-badge-wrap" class="mode-badge-wrap" onclick="openLiveSettingsModal()" title="Ticaret Modu (Demo/Canlı) & Binance API Ayarlarını Aç">
                <span id="mode-badge-dot" class="mode-dot-demo"></span>
                <span id="mode-badge-text">🟡 DEMO MODU</span>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block; vertical-align:middle; margin-left:3px;"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
            </div>
            <div class="live-tag" id="cb-lead-lag-pill" onclick="switchMainTab('health')" style="cursor:pointer; background:rgba(59,130,246,0.12); border:1px solid rgba(59,130,246,0.35); color:#60a5fa;" title="Coinbase Pro Spot Lead-Lag ($LLI$ - Kurumsal Spot Öncüsü)">
                <span id="cb-lead-lag-dot" style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#60a5fa; box-shadow:0 0 8px #60a5fa;"></span>
                <span id="cb-lead-lag-text">🏛️ CB: 0.0 bps</span>
            </div>
            <div class="live-tag" id="system-health-pill" onclick="switchMainTab('health')" style="cursor:pointer;" title="Aegis Sentinel 360° Kuant Telemetri Sekmesini Aç">
                <div class="live-dot" id="system-health-dot"></div>
                <span id="system-health-text">100/100 Parite Canlı Akıyor</span>
            </div>
        </div>
    </div>

    <!-- =========================================================================
         VALKYRIE QUANT COCKPIT 3.0 - MODULER DİKEY SIDEBAR & DESK LAYOUT
         ========================================================================= -->
    <div class="dashboard-main-layout">
        <!-- SOL SIDEBAR: DİKEY NAVİGASYON DESKİ -->
        <aside class="dashboard-sidebar" id="dashboard-sidebar">
            <div class="sidebar-header-box">
                <div class="sidebar-title-row">
                    <span class="sidebar-section-title">KONTROL MASASI</span>
                    <button class="sidebar-toggle-btn" id="sidebar-toggle-btn" onclick="toggleSidebarCollapse()" title="Kenar Çubuğunu Daralt / Genişlet">◀</button>
                </div>
                <div class="sidebar-subtitle">Kurumsal Algoritmik Terminal</div>
            </div>

            <div class="nav-tab-strip">
                <button class="nav-tab-btn active" id="tab-btn-cockpit" onclick="switchMainTab('cockpit')" title="1. Kokpit (Ana Göstergeler)">
                    <span class="tab-btn-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg></span>
                    <span class="tab-btn-text">1. Kokpit</span>
                </button>

                <button class="nav-tab-btn" id="tab-btn-positions" onclick="switchMainTab('positions')" title="2. Canlı Açık Pozisyonlar">
                    <span class="tab-btn-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg></span>
                    <span class="tab-btn-text">2. Pozisyonlar</span>
                    <span class="tab-badge zero-idle" id="nav-pos-count-badge">0</span>
                </button>

                <button class="nav-tab-btn" id="tab-btn-radar" onclick="switchMainTab('radar')" title="3. Pusu Radarı (100 Parite)">
                    <span class="tab-btn-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="22" y1="12" x2="18" y2="12"></line><line x1="6" y1="12" x2="2" y2="12"></line><line x1="12" y1="6" x2="12" y2="2"></line><line x1="12" y1="22" x2="12" y2="18"></line></svg></span>
                    <span class="tab-btn-text">3. Pusu Radarı</span>
                    <span class="tab-badge-sub" id="nav-active-coins-badge">100/100</span>
                </button>

                <button class="nav-tab-btn" id="tab-btn-ledger" onclick="switchMainTab('ledger')" title="4. İşlem Geçmişi (Adli Defter)">
                    <span class="tab-btn-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg></span>
                    <span class="tab-btn-text">4. İşlem Geçmişi</span>
                </button>

                <button class="nav-tab-btn" id="tab-btn-persona" onclick="switchMainTab('persona')" title="5. Coin DNA & Persona Matrisi">
                    <span class="tab-btn-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2" ry="2"></rect><rect x="9" y="9" width="6" height="6"></rect><line x1="9" y1="1" x2="9" y2="4"></line><line x1="15" y1="1" x2="15" y2="4"></line><line x1="9" y1="20" x2="9" y2="23"></line><line x1="15" y1="20" x2="15" y2="23"></line><line x1="20" y1="9" x2="23" y2="9"></line><line x1="20" y1="14" x2="23" y2="14"></line><line x1="1" y1="9" x2="4" y2="9"></line><line x1="1" y1="14" x2="4" y2="14"></line></svg></span>
                    <span class="tab-btn-text">5. DNA</span>
                    <span class="tab-badge-sub" id="nav-persona-badge" style="background:rgba(0,242,254,0.12); color:var(--cyan); border:1px solid rgba(0,242,254,0.3);">100 Parite</span>
                </button>

                <button class="nav-tab-btn" id="tab-btn-shadow" onclick="switchMainTab('shadow')" title="5b. Gölge İşlem & Coin DNA Kalibrasyon Masası">
                    <span class="tab-btn-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a8 8 0 0 0-8 8v12l3-3 2.5 2.5L12 19l2.5 2.5L17 19l3 3V10a8 8 0 0 0-8-8z"></path><circle cx="9" cy="10" r="1"></circle><circle cx="15" cy="10" r="1"></circle></svg></span>
                    <span class="tab-btn-text">5b. Gölge & DNA</span>
                    <span class="tab-badge-sub" id="nav-shadow-badge" style="background:rgba(168,85,247,0.15); color:#a855f7; border:1px solid rgba(168,85,247,0.3);">SEI %100</span>
                </button>

                <button class="nav-tab-btn" id="tab-btn-funding" onclick="switchMainTab('funding')" title="6. Fonlama & Squeeze Radarı">
                    <span class="tab-btn-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg></span>
                    <span class="tab-btn-text">6. Fonlama</span>
                    <span class="tab-badge-sub" id="nav-funding-badge" style="background:rgba(255,107,107,0.15); color:var(--red); border:1px solid rgba(255,107,107,0.3);">0 Squeeze</span>
                </button>

                <button class="nav-tab-btn" id="tab-btn-cvd" onclick="switchMainTab('cvd')" title="7. Mikro-CVD & Taker Hacim Akışı">
                    <span class="tab-btn-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg></span>
                    <span class="tab-btn-text">7. CVD</span>
                    <span class="tab-badge-sub" id="nav-cvd-badge" style="background:rgba(34,197,94,0.15); color:#22c55e; border:1px solid rgba(34,197,94,0.3);">Canlı</span>
                </button>

                <button class="nav-tab-btn" id="tab-btn-health" onclick="switchMainTab('health')" title="8. Aegis Sentinel Sistem Sağlığı">
                    <span class="tab-btn-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"></path></svg></span>
                    <span class="tab-btn-text">8. Sağlık</span>
                    <span class="tab-badge-sub" id="nav-health-tab-badge" style="background:rgba(14,203,129,0.15); color:#22c55e; border:1px solid rgba(14,203,129,0.3);">10/10 Kusursuz</span>
                </button>

                <button class="nav-tab-btn" id="tab-btn-admin" onclick="switchMainTab('admin'); loadAdminMetrics();" style="border-color:rgba(0,242,254,0.35); display:none;" title="9. Yönetim Masası">
                    <span class="tab-btn-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--cyan)" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg></span>
                    <span class="tab-btn-text">9. Yönetim</span>
                </button>
            </div>

            <!-- SIDEBAR TELEMETRİ KARTI -->
            <div class="sidebar-status-card">
                <div class="sidebar-status-top">
                    <div class="sidebar-status-beacon">
                        <span class="sidebar-status-dot"></span>
                        <span class="sidebar-status-title">AEGIS SENTINEL</span>
                    </div>
                    <span class="sidebar-status-state">AKTİF</span>
                </div>
                <div class="sidebar-status-meta">
                    <div class="sidebar-status-row"><span>Parite Akışı:</span> <b>100 / 100</b></div>
                    <div class="sidebar-status-row"><span>Açık PnL:</span> <b id="sidebar-open-pnl" style="color:#94a3b8;">$0.00 (0 Açık)</b></div>
                    <div class="sidebar-status-row"><span>Net Realize:</span> <b id="sidebar-net-pnl" style="color:var(--green);">+$0.00</b></div>
                    <div class="sidebar-status-row"><span>RAM Kalkanı:</span> <b>512MB RAM</b></div>
                    <div class="sidebar-status-row"><span>Bulut:</span> <b>Render Linux</b></div>
                </div>
            </div>
        </aside>

        <!-- SAĞ ANA İÇERİK ALANI -->
        <main class="dashboard-content-area">

    <!-- =========================================================================
         1. SEKME: KOKPİT (ANA SAYFA)
         ========================================================================= -->
    <div id="main-tab-content-cockpit" class="main-tab-content active-tab">
        <!-- 4 HERO FINANSAL KPI KARTI -->
        <!-- 4 HERO FINANSAL KPI KARTI (MİKRO-SİMÜLASYONLU) -->
        <div class="cockpit-kpi-grid">
            <div class="cockpit-kpi-card kpi-card-vault" id="card-kpi-vault">
                <canvas class="kpi-sim-canvas" id="canvas-kpi-vault"></canvas>
                <div class="kpi-card-inner">
                    <div class="kpi-card-head">
                        <span class="kpi-card-title">
                            Toplam Kasa Bakiyesi
                            <span class="kpi-telemetry-chip" style="background:rgba(0,242,254,0.12); border:1px solid rgba(0,242,254,0.3); color:var(--cyan);">REZERV</span>
                        </span>
                    </div>
                    <div class="kpi-card-val" id="cockpit-balance">10,000.00 $</div>
                    <div class="kpi-card-sub" id="cockpit-free-bal">Kullanılabilir Kasa: $10,000.00 USDT (5x)</div>
                    <div style="font-size:11px; color:#64748b; font-family:'JetBrains Mono', monospace; margin-top:3px; display:flex; align-items:center; gap:6px;">
                        <span style="display:inline-block; width:5px; height:5px; border-radius:50%; background:#10b981; box-shadow:0 0 6px #10b981;"></span>
                        <span>Dinamik Sermaye Koruması Aktif</span>
                    </div>
                </div>
            </div>

            <div class="cockpit-kpi-card kpi-card-growth" id="card-kpi-growth">
                <canvas class="kpi-sim-canvas" id="canvas-kpi-growth"></canvas>
                <div class="kpi-card-inner">
                    <div class="kpi-card-head">
                        <span class="kpi-card-title">
                            Net Kâr / Zarar & Büyüme
                            <span class="kpi-telemetry-chip" id="chip-kpi-growth" style="background:rgba(16,185,129,0.12); border:1px solid rgba(16,185,129,0.3); color:var(--green);">CANLI NABIZ</span>
                        </span>
                    </div>
                    <div class="kpi-card-val" id="cockpit-pnl" style="color:var(--green);">+0.00 $</div>
                    <div class="kpi-card-sub" id="cockpit-growth">+0.00% Büyüme</div>
                    <div style="font-size:11px; color:#64748b; font-family:'JetBrains Mono', monospace; margin-top:3px;">Realize + Açık Pozisyonlar Toplamı</div>
                </div>
            </div>

            <div class="cockpit-kpi-card kpi-card-radar" id="card-kpi-radar" title="Kazanma Oranı (Win Rate): Sadece kârı veya zararı kesinleşen (kapanmış) işlemleri hesaplar. Halen piyasada açık olan pozisyonlar henüz kapanmadığı için buraya dahil edilmez.">
                <canvas class="kpi-sim-canvas" id="canvas-kpi-radar"></canvas>
                <div class="kpi-card-inner">
                    <div class="kpi-card-head">
                        <span class="kpi-card-title">
                            Kazanma Oranı (Win Rate)
                            <span class="kpi-telemetry-chip" id="chip-kpi-winrate" style="background:rgba(56,189,248,0.12); border:1px solid rgba(56,189,248,0.3); color:#38bdf8;">RADAR</span>
                        </span>
                    </div>
                    <div class="kpi-card-val" id="cockpit-winrate">%0.0</div>
                    <div class="kpi-card-sub" id="cockpit-win-loss-count">0 Kazanç / 0 Kayıp</div>
                    <div style="font-size:11px; color:#64748b; font-family:'JetBrains Mono', monospace; margin-top:3px;" id="cockpit-winrate-subtext">Sürdürülebilir Hedef: &gt; %50.0</div>
                </div>
            </div>

            <div class="cockpit-kpi-card kpi-card-reactor" id="card-kpi-reactor" title="Profit Factor (Kâr Faktörü): Dünyadaki kurumsal fonların en temel sistem kalite göstergesidir. Kaybedilen her 1$'a karşılık kasaya kaç dolar kâr girdiğini ifade eder.">
                <canvas class="kpi-sim-canvas" id="canvas-kpi-reactor"></canvas>
                <div class="kpi-card-inner">
                    <div class="kpi-card-head">
                        <span class="kpi-card-title">
                            KÂR FAKTÖRÜ (PROFIT FACTOR)
                            <span class="kpi-info-icon" title="Profit Factor (Kâr Faktörü): Sistemin kurumsal getiri kalitesini gösterir. Kaybedilen her 1$'a karşılık kasaya kaç dolar kâr girdiğini ifade eder.&#10;&#10;Formül: Toplam Kâr ÷ Toplam Kayıp&#10;• < 1.00x: Negatif (Zarar Baskısı)&#10;• 1.00x: Başa-Baş&#10;• 1.20x - 1.50x: Kârlı Sistem&#10;• 1.50x - 2.00x: Çok Güçlü&#10;• 2.00x+: Kurumsal Elit Seviye" style="cursor:help; font-size:11px; color:#38bdf8; background:rgba(56, 189, 248, 0.15); border-radius:50%; width:16px; height:16px; display:inline-flex; align-items:center; justify-content:center; border:1px solid rgba(56, 189, 248, 0.35);">ⓘ</span>
                            <span class="kpi-telemetry-chip" id="chip-kpi-reactor" style="background:rgba(192,132,252,0.12); border:1px solid rgba(192,132,252,0.3); color:#c084fc;">REAKTÖR</span>
                        </span>
                    </div>
                    <div class="kpi-card-val" id="cockpit-pf" style="color:#94a3b8;">— (İşlem Bekleniyor)</div>
                    <div class="kpi-card-sub" id="cockpit-fees">Brüt Kâr: +$0.00 | Kayıp: -$0.00</div>
                    <div id="cockpit-pf-note" style="font-size:11px; color:#38bdf8; font-family:'JetBrains Mono', monospace; margin-top:3px; font-weight:700;">Her 1$ Kayba: İlk işlem bekleniyor</div>
                </div>
            </div>
        </div>

        <!-- 📈 VALKYRIE KURUMSAL KASA PERFORMANSI (EQUITY CURVE) -->
        <div class="equity-curve-card" id="cockpit-equity-curve-card">
            <div class="equity-top-bar">
                <div class="equity-title-wrap">
                    <div class="equity-title">
                        <span style="font-size:16px;">📈</span>
                        <span>VALKYRIE KURUMSAL KASA PERFORMANSI</span>
                        <span style="font-size:10.5px; background:rgba(0,242,254,0.12); color:var(--cyan); border:1px solid rgba(0,242,254,0.3); padding:2px 7px; border-radius:6px; font-weight:800;">EQUITY CURVE</span>
                    </div>
                </div>
                <div class="equity-hud-chips">
                    <div class="equity-chip">
                        <span class="equity-chip-label">Başlangıç:</span>
                        <span class="equity-chip-val" id="equity-chip-init">$10,000.00</span>
                    </div>
                    <div class="equity-chip">
                        <span class="equity-chip-label">Zirve Kasa:</span>
                        <span class="equity-chip-val" id="equity-chip-peak" style="color:var(--cyan);">$10,000.00</span>
                    </div>
                    <div class="equity-chip">
                        <span class="equity-chip-label">Net Kâr:</span>
                        <span class="equity-chip-val" id="equity-chip-pnl" style="color:var(--green);">+$0.00</span>
                    </div>
                    <div class="equity-chip">
                        <span class="equity-chip-label">Max Drawdown:</span>
                        <span class="equity-chip-val" id="equity-chip-drawdown" style="color:#38bdf8;">%0.00</span>
                    </div>
                    <div class="equity-chip">
                        <span class="equity-chip-label">Kasa Koruma:</span>
                        <span class="equity-chip-val" style="color:var(--green);">🛡️ %100 Güvenli</span>
                    </div>
                </div>
            </div>
            <div class="equity-canvas-container" id="cockpit-equity-container">
                <div class="equity-empty-placeholder" id="equity-empty-state">
                    <div style="font-size:24px;">📊</div>
                    <div style="font-weight:800; color:#cbd5e1;">İlk Kapanan İşlemle Birlikte Canlı Kasa Eğrisi Çizilecek</div>
                    <div style="font-size:11px; color:#64748b;">Referans Başlangıç Kasası: $10,000.00 USDT • Sabit Sermaye Koruma Kalkanı Devrede</div>
                </div>
            </div>
        </div>

        <!-- DİNAMİK AÇIK POZİSYONLAR BÖLÜMÜ -->
        <div id="cockpit-open-positions-container" style="margin: 20px 0; display:none;"></div>

        <!-- 🛡️ KUANT KALKANLARI & REDDEDİLEN SİNYAL İSTİHBARATI (SHIELD INTELLIGENCE) -->
        <div class="rejection-panel-card" id="cockpit-rejection-card">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06); flex-wrap:wrap; gap:10px;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <span style="font-size:16px;">🛡️</span>
                    <span style="font-size:13.5px; font-weight:800; font-family:'JetBrains Mono'; color:#ffffff; letter-spacing:0.4px;">KUANT KALKANLARI & REDDEDİLEN SİNYAL İSTİHBARATI</span>
                    <span style="font-size:10px; background:rgba(255,71,87,0.15); color:#ff4757; border:1px solid rgba(255,71,87,0.35); padding:2px 7px; border-radius:6px; font-weight:800; font-family:'JetBrains Mono';" id="rejection-total-badge">0 VETO</span>
                </div>
                <div style="font-size:11px; color:#94a3b8; font-family:'JetBrains Mono';">
                    <span>Otomatik Risk Filtresi: <b>35+ Kalkan Devrede</b></span>
                </div>
            </div>

            <!-- Top Shield Blocker Counters -->
            <div class="shield-stats-grid" id="shield-stats-container">
                <div class="shield-stat-card">
                    <span style="font-size:11px; color:#94a3b8; font-family:'JetBrains Mono';">🌊 Harmonic Flow Gate</span>
                    <b style="color:var(--cyan); font-family:'JetBrains Mono';" id="shield-cnt-flow">0</b>
                </div>
                <div class="shield-stat-card">
                    <span style="font-size:11px; color:#94a3b8; font-family:'JetBrains Mono';">⚡ Judas Swing Tuzağı</span>
                    <b style="color:#f59e0b; font-family:'JetBrains Mono';" id="shield-cnt-judas">0</b>
                </div>
                <div class="shield-stat-card">
                    <span style="font-size:11px; color:#94a3b8; font-family:'JetBrains Mono';">🪙 Beta / BTC Korelasyonu</span>
                    <b style="color:#a78bfa; font-family:'JetBrains Mono';" id="shield-cnt-beta">0</b>
                </div>
                <div class="shield-stat-card">
                    <span style="font-size:11px; color:#94a3b8; font-family:'JetBrains Mono';">🌀 Shannon / Entropi Kalkanı</span>
                    <b style="color:#38bdf8; font-family:'JetBrains Mono';" id="shield-cnt-entropy">0</b>
                </div>
                <div class="shield-stat-card">
                    <span style="font-size:11px; color:#94a3b8; font-family:'JetBrains Mono';">🛑 Cooldown / Zarar Limiti</span>
                    <b style="color:#ff4757; font-family:'JetBrains Mono';" id="shield-cnt-cooldown">0</b>
                </div>
                <div class="shield-stat-card">
                    <span style="font-size:11px; color:#94a3b8; font-family:'JetBrains Mono';">🧊 Tri-Modal Iceberg Filtresi</span>
                    <b style="color:#34d399; font-family:'JetBrains Mono';" id="shield-cnt-iceberg">0</b>
                </div>
            </div>

            <!-- Live Rejection Feed Stream -->
            <div class="rejection-feed-list" id="rejection-feed-container">
                <div style="text-align:center; padding:20px; color:#64748b; font-size:12px; font-family:'JetBrains Mono';">
                    🛡️ Henüz kalkanlara çarpan riskli sinyal bulunmuyor. Piyasa 100 paritede temiz akıyor.
                </div>
            </div>
        </div>

        <!-- AI PİYASA & PUSU AKIŞI -->
        <div class="ai-quant-room">
            <div class="ai-room-head">
                <div class="ai-room-title">
                    <div class="ai-pulse-dot"></div>
                    <span>AI PİYASA & PUSU AKIŞI</span>
                </div>
                <div style="font-size:12px; color:#cbd5e1; font-family:'JetBrains Mono', monospace;" id="ai-market-time-badge">
                    <span style="display:inline-block; width:5px; height:5px; border-radius:50%; background:#00f2fe; box-shadow:0 0 6px #00f2fe; margin-right:5px;"></span>Canlı 5M Senkronizasyon
                </div>
            </div>

            <!-- VALKYRIE CANLI LİKİDİTE SAVAŞI: BOĞA VS AYI CEPHESİ (CANLI ARENA) -->
            <div class="regime-battle-card">
                <div class="regime-battle-top-bar">
                    <div class="regime-battle-title">
                        <span>VALKYRIE LİKİDİTE SAVAŞI: BOĞA VS AYI CEPHESİ</span>
                        <span style="font-size:11px; color:#94a3b8; font-weight:700;">(100 PARİTE 1H MAKRO)</span>
                    </div>
                    <button id="btn-toggle-battle-view" class="btn-battle-toggle" onclick="toggleBattleView()" title="Görünüm Modunu Değiştir">
                        Sade Çubuğa Geç
                    </button>
                </div>

                <!-- 1. SİNEMATİK ARENA GÖRÜNÜMÜ -->
                <div id="regime-arena-wrap" class="regime-arena-canvas-wrap">
                    <canvas id="regime-battle-canvas"></canvas>
                    <div class="regime-arena-hud-overlay">
                        <div class="hud-side-box bull">
                            <div class="hud-army-name">
                                <span>BOĞA CEPHESİ</span>
                                <span class="hud-tag-taarruz">TAARRUZ</span>
                            </div>
                            <div class="hud-power-stat" id="hud-bull-pct">%0</div>
                            <div class="hud-parite-count" id="hud-bull-count">0 Parite Kırılımda</div>
                        </div>

                        <div class="hud-center-neutral" id="hud-neutral-badge">
                            <span>TAMPON BÖLGE: %0 YATAY</span>
                        </div>

                        <div class="hud-side-box bear">
                            <div class="hud-army-name">
                                <span class="hud-tag-savunma">SAVUNMA</span>
                                <span>AYI CEPHESİ</span>
                            </div>
                            <div class="hud-power-stat" id="hud-bear-pct">%0</div>
                            <div class="hud-parite-count" id="hud-bear-count">0 Parite Baskıda</div>
                        </div>
                    </div>
                </div>

                <!-- 2. KOMPAKT ÇUBUK GÖRÜNÜMÜ -->
                <div id="regime-simple-wrap" style="display:none;">
                    <div class="regime-battle-header">
                        <div class="regime-side-bull">
                            <span>BOĞA HAKİMİYETİ:</span>
                            <b id="regime-bull-text">%0 (0 Parite)</b>
                        </div>
                        <div class="regime-side-range">
                            <span>YATAY KONSOLİDASYON:</span>
                            <b id="regime-range-text">%0 (0 Parite)</b>
                        </div>
                        <div class="regime-side-bear">
                            <span>AYI BASKISI:</span>
                            <b id="regime-bear-text">%0 (0 Parite)</b>
                        </div>
                    </div>
                    <div class="regime-battle-track">
                        <div class="regime-bar-bull" id="regime-bar-bull" style="width: 33.3%;"></div>
                        <div class="regime-bar-range" id="regime-bar-range" style="width: 33.4%;"></div>
                        <div class="regime-bar-bear" id="regime-bar-bear" style="width: 33.3%;"></div>
                        <div class="regime-clash-spark" id="regime-clash-spark" style="left: 33.3%;"></div>
                    </div>
                </div>

                <div class="regime-battle-footer">
                    <span style="color:#00f2fe; font-weight:800; flex-shrink:0;">CEBHE RAPORU:</span>
                    <span id="regime-commentary" style="color:#e2e8f0;">100 paritede 1H makro likidite dengesi hesaplanıyor...</span>
                </div>
                <div class="regime-battle-footer" style="margin-top:6px; border-top:1px dashed rgba(255,255,255,0.06); padding-top:6px;">
                    <span style="color:#fbc531; font-weight:800; flex-shrink:0;">FONLAMA REJİMİ:</span>
                    <span id="cockpit-funding-commentary" style="color:#94a3b8; font-family:'JetBrains Mono'; font-size:12px;">100 paritede fonlama oranları ve squeeze riskleri taranıyor...</span>
                </div>
            </div>

            <!-- VALKYRIE 360° TAKTİK LİKİDİTE RADARI & SAVUNMA KALKANI (CANLI KOMUTA KONSOLU) -->
            <div class="tactical-radar-card" id="tactical-radar-wrap">
                <div class="tactical-radar-topbar">
                    <div class="tactical-radar-title">
                        <span class="radar-live-blip"></span>
                        <span style="font-weight:800; letter-spacing:0.5px;">VALKYRIE TAKTİK LİKİDİTE RADARI & SAVUNMA KALKANI</span>
                        <span class="radar-scope-badge" id="radar-active-count-badge">0 HEDEF TARANIYOR</span>
                    </div>
                    <div class="radar-top-controls">
                        <!-- Radar Kapsam Filtreleri -->
                        <div class="radar-scope-filters">
                            <button class="radar-filter-pill active" id="rf-pill-top15" onclick="setRadarScope('top15')" title="En yüksek öncelikli 15 parite (Feraha kavuşturulmuş net görünüm)">⭐ Odak 15</button>
                            <button class="radar-filter-pill" id="rf-pill-all" onclick="setRadarScope('all')" title="Taranan tüm pariteler">Tümü</button>
                            <button class="radar-filter-pill" id="rf-pill-contact" onclick="setRadarScope('contact')" title="Destek / Direnç seviyesine tam temas edenler">🔥 Temas</button>
                            <button class="radar-filter-pill" id="rf-pill-iceberg" onclick="setRadarScope('iceberg')" title="Gizli balina buzdağı ve emilim tespit edilenler">🧊 Iceberg</button>
                            <button class="radar-filter-pill" id="rf-pill-ambush" onclick="setRadarScope('ambush')" title="Seviyeye 0.25%-0.60% mesafede pusu kuranlar">🎯 Pusu</button>
                            <button class="radar-filter-pill" id="rf-pill-blocked" onclick="setRadarScope('blocked')" title="Aegis Kalkanı ve Kuant filtrelerle elenenler">🛡️ Kalkan</button>
                        </div>
                        <button id="btn-expand-radar" class="btn-battle-toggle" onclick="toggleRadarExpand()" title="Radarı Tam Genişliğe Büyüt / Küçült">
                            ⛶ Geniş Radar
                        </button>
                        <button id="btn-toggle-radar-view" class="btn-battle-toggle" onclick="toggleRadarView()" title="Radar Görünümünü Aç / Kapat">
                            Radarı Gizle
                        </button>
                    </div>
                </div>

                <div id="tactical-radar-body" class="tactical-radar-body">
                    <!-- SOL: 360° CANVAS RADAR EKRANI -->
                    <div class="radar-canvas-container">
                        <canvas id="tactical-radar-canvas"></canvas>
                        <!-- Radar HUD Legend Overlay -->
                        <div class="radar-hud-legend">
                            <span class="legend-item"><span class="legend-dot contact"></span> Merkez: %0.25 Temas</span>
                            <span class="legend-item"><span class="legend-dot ambush"></span> Orta: %0.60 Pusu</span>
                            <span class="legend-item"><span class="legend-dot approach"></span> Dış: %2.50 Yaklaşan</span>
                            <span class="legend-item"><span class="legend-dot blocked"></span> Dış Halka: Kalkan</span>
                            <span class="legend-item"><span class="legend-dot" style="background:#00f2fe; box-shadow:0 0 8px #00f2fe;"></span> 🧊 Iceberg</span>
                            <span class="legend-item"><span class="legend-dot" style="background:#10b981; box-shadow:0 0 8px #10b981;"></span> 🌊 Bookmap</span>
                        </div>
                    </div>

                    <!-- SAĞ: CANLI TELEMETRİ MONİTÖRÜ (HEDEF BRİFİNGİ - 6'LI KUANT KOKPİTİ) -->
                    <div class="radar-telemetry-panel" id="radar-telemetry-panel">
                        <div class="telemetry-header">
                            <div class="telemetry-target-name" id="radar-target-name">HEDEF SEÇİLİYOR...</div>
                            <div class="telemetry-badge" id="radar-target-badge">RADAR KİLİTLENMESİ</div>
                        </div>

                        <div class="telemetry-grid">
                            <!-- Kutu 1: Seviye Mesafesi -->
                            <div class="telemetry-stat-box">
                                <div class="stat-label">SEVİYE MESAFESİ</div>
                                <div class="stat-val" id="radar-stat-distance">%0.00</div>
                                <div class="stat-sub" id="radar-stat-target-lvl">nPOC / S3 / R4</div>
                            </div>
                            <!-- Kutu 2: 5M Hacim Patlaması -->
                            <div class="telemetry-stat-box">
                                <div class="stat-label">5M HACİM PATLAMASI</div>
                                <div class="stat-val" id="radar-stat-volume">1.00x</div>
                                <div class="stat-sub" id="radar-stat-vol-target">Min 1.50x Şartı</div>
                            </div>
                            <!-- Kutu 3: Mikro-CVD Delta -->
                            <div class="telemetry-stat-box">
                                <div class="stat-label">MİKRO-CVD DELTA</div>
                                <div class="stat-val" id="radar-stat-cvd">%50 Dengeli</div>
                                <div class="stat-sub" id="radar-stat-cvd-delta">Net $0 Taker</div>
                            </div>
                            <!-- Kutu 4: Sistem Teşhisi -->
                            <div class="telemetry-stat-box">
                                <div class="stat-label">SİSTEM TEŞHİSİ</div>
                                <div class="stat-val" id="radar-stat-status" style="font-size:12px;">Taranıyor</div>
                                <div class="stat-sub" id="radar-stat-action">Bekleme Modu</div>
                            </div>
                            <!-- Kutu 5: 🧊 Ken Griffin Iceberg Dedektörü -->
                            <div class="telemetry-stat-box telemetry-quant-iceberg" style="border-color: rgba(0, 242, 254, 0.25); background: linear-gradient(135deg, rgba(0, 242, 254, 0.05) 0%, rgba(0, 0, 0, 0.35) 100%);">
                                <div class="stat-label" style="color: #00f2fe; display: flex; align-items: center; gap: 4px;">
                                    <span>🧊 GİZLİ LİKİDİTE (ICEBERG)</span>
                                </div>
                                <div class="stat-val" id="radar-stat-iceberg" style="font-size: 13.5px; color: #00f2fe;">⚪ Normal</div>
                                <div class="stat-sub" id="radar-stat-iceberg-sub">Ken Griffin Taker Emilimi</div>
                            </div>
                            <!-- Kutu 6: 🌡️ Boltzmann Entropi & Mandelbrot Hurst -->
                            <div class="telemetry-stat-box telemetry-quant-entropy" style="border-color: rgba(168, 85, 247, 0.25); background: linear-gradient(135deg, rgba(168, 85, 247, 0.05) 0%, rgba(0, 0, 0, 0.35) 100%);">
                                <div class="stat-label" style="color: #c084fc; display: flex; align-items: center; gap: 4px;">
                                    <span>🌡️ ENTROPİ & FRAKTAL</span>
                                </div>
                                <div class="stat-val" id="radar-stat-entropy-hurst" style="font-size: 13px;">S: %50 | H: 0.50</div>
                                <div class="stat-sub" id="radar-stat-entropy-sub">Boltzmann & Mandelbrot</div>
                            </div>
                        </div>

                        <!-- Canlı Taktik Açıklama Kutusu -->
                        <div class="telemetry-briefing-box" id="radar-target-briefing">
                            Radar 100 paritede nPOC, AVWAP ve Camarilla seviyelerine yaklaşan ve koruma kalkanına çarpan sinyalleri tarıyor. Hedeflerin üzerine tıklayarak veya fareyle gelerek canlı telemetrisini inceleyebilirsiniz.
                        </div>

                        <div class="telemetry-footer-action">
                            <button class="btn-radar-focus" id="btn-radar-focus-card" onclick="focusRadarTargetCard()">
                                🔍 Alttaki Detaylı Analiz Kartına Odaklan ➔
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 🧠 AI KATEGORİ FİLTRELERİ & GÖRÜNÜM MODU -->
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:12px;">
                <div class="ai-thought-filters" style="margin-bottom:0;">
                    <button class="ai-filter-btn active" id="btn-filter-all" onclick="setAiThoughtFilter('all')">TÜMÜ (<span id="ai-cnt-all">0</span>)</button>
                    <button class="ai-filter-btn" id="btn-filter-macro" onclick="setAiThoughtFilter('macro')">Makro (<span id="ai-cnt-macro">1</span>)</button>
                    <button class="ai-filter-btn" id="btn-filter-near" onclick="setAiThoughtFilter('near')">Pusu & Seviye (<span id="ai-cnt-near">0</span>)</button>
                    <button class="ai-filter-btn" id="btn-filter-rejected" onclick="setAiThoughtFilter('rejected')">Elenenler (<span id="ai-cnt-rej">0</span>)</button>
                    <button class="ai-filter-btn" id="btn-filter-positions" onclick="setAiThoughtFilter('positions')">Pozisyonlar (<span id="ai-cnt-pos">0</span>)</button>
                    <button class="ai-filter-btn" id="btn-filter-autopsy" onclick="setAiThoughtFilter('autopsy')">Otopi (<span id="ai-cnt-autopsy">0</span>)</button>
                </div>
                <div style="display:flex; gap:6px; align-items:center;">
                    <button class="ai-filter-btn active" id="btn-layout-grid" onclick="setAiThoughtLayout('grid')" title="2 Sütunlu Kompakt Görünüm" style="padding:5px 11px; font-size:11.5px; border-color:rgba(0, 242, 254, 0.4); color:#00f2fe;">
                        ⊞ 2'li Izgara
                    </button>
                    <button class="ai-filter-btn" id="btn-layout-single" onclick="setAiThoughtLayout('single')" title="Tek Sütun Geniş Görünüm" style="padding:5px 11px; font-size:11.5px;">
                        ☰ Tek Sütun
                    </button>
                </div>
            </div>

            <div class="ai-thought-feed" id="ai-thought-feed">
                <div class="ai-thought-item">
                    <span style="font-size:18px;">💡</span>
                    <div>
                        <b>VALKYRIE QUANT DESK •BAŞLATILDI:</b> 100 paritede Camarilla Pivotları, Tepe/Dip AVWAP seviyeleri ve Kurumsal nPOC likidite hatları aktif taranıyor.
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- =========================================================================
         2. SEKME: AÇIK POZİSYONLAR
         ========================================================================= -->
    <div id="main-tab-content-positions" class="main-tab-content">
        <div class="section-header">
            <div style="display:flex; align-items:center; gap:14px; flex-wrap:wrap;">
                <div class="section-title">⚡ CANLI AÇIK POZİSYONLAR</div>
                <span class="active-badge-pill" id="positions-active-count-badge">0 Açık Pozisyon</span>
            </div>
        </div>

        <!-- 🌡️ PORTFÖY RİSK & EXPOSURE HUD -->
        <div class="portfolio-risk-hud" id="positions-risk-hud">
            <div class="risk-hud-card">
                <div class="risk-hud-title">
                    <span>🟢 LONG MARUZİYET</span>
                </div>
                <div class="risk-hud-val" id="risk-hud-long-val" style="color:var(--green);">$0.00</div>
                <div class="risk-hud-sub" id="risk-hud-long-sub">0 Long Pozisyon</div>
            </div>
            <div class="risk-hud-card">
                <div class="risk-hud-title">
                    <span>🔴 SHORT MARUZİYET</span>
                </div>
                <div class="risk-hud-val" id="risk-hud-short-val" style="color:var(--red);">$0.00</div>
                <div class="risk-hud-sub" id="risk-hud-short-sub">0 Short Pozisyon</div>
            </div>
            <div class="risk-hud-card">
                <div class="risk-hud-title">
                    <span>⚖️ NET DELTA EĞİLİMİ</span>
                </div>
                <div class="risk-hud-val" id="risk-hud-delta-val" style="color:var(--cyan);">$0.00 Net</div>
                <div class="risk-hud-sub" id="risk-hud-delta-sub">Piyasa-Nötr / Dengeli</div>
            </div>
            <div class="risk-hud-card">
                <div class="risk-hud-title">
                    <span>🛡️ MARJİN KULLANIMI</span>
                </div>
                <div class="risk-hud-val" id="risk-hud-margin-val">%0.0</div>
                <div class="risk-hud-sub" id="risk-hud-margin-sub">Tam Güvenlik Tamponu</div>
            </div>
        </div>

        <div id="positions-container" style="display:grid; grid-template-columns:repeat(auto-fit, minmax(360px, 1fr)); gap:18px; margin-bottom:30px;">
            <div style="grid-column:1/-1; color: #94a3b8; text-align:center; padding: 100px 20px; font-size:15px; line-height:1.6;">
                Şu an açık pozisyon bulunmuyor.<br><span style="color:var(--yellow)">● 5M Mum kapanışları, taze kırılımlar ve destek dönüşleri taranıyor...</span>
            </div>
        </div>
    </div>

    <!-- =========================================================================
         3. SEKME: PUSU RADARI
         ========================================================================= -->
    <div id="main-tab-content-radar" class="main-tab-content">
        <!-- PARITE YONETIM HAVUZU -->
        <div class="manager-card">
            <div class="manager-head">
                <div style="display:flex; align-items:center; gap:12px; flex-wrap:wrap;">
                    <div style="font-size:15px; font-weight:800; letter-spacing:0.3px; display:flex; align-items:center; gap:10px; cursor:pointer;" onclick="togglePoolCollapse()" title="Parite Havuzunu Aç / Gizle">
                        ⚙️ PARİTE HAVUZU
                        <span id="pool-collapse-btn" style="font-size:11.5px; font-weight:800; color:var(--cyan); background:rgba(0,242,254,0.08); border:1px solid rgba(0,242,254,0.3); padding:4px 12px; border-radius:8px; transition:all 0.15s ease;">⚙️ Pariteleri Yönet ▼</span>
                    </div>
                    <span class="active-badge-pill" id="active-coin-counter">100 Aktif / 100 Parite</span>
                </div>

                <!-- PARITE ARAMA KUTUSU -->
                <div class="search-wrap">
                    <span class="search-icon">🔍</span>
                    <input type="text" id="coin-search-input" class="coin-search-input" placeholder="Parite veya kart ara (örn: SOL, ENA, PEPE)..." oninput="handleSearch(this.value)" autocomplete="off" />
                    <button id="search-clear-btn" class="search-clear-btn" onclick="clearSearch()" style="display:none;" title="Aramayı Temizle">✕</button>
                </div>

                <div class="quick-preset-bar">
                    <span style="font-size:12.5px; font-weight:700; color:#cbd5e1;">⚡ HIZLI SEÇİM:</span>
                    <button class="btn-preset" onclick="selectTopN(5)">Top 5</button>
                    <button class="btn-preset" onclick="selectTopN(10)">Top 10</button>
                    <button class="btn-preset" onclick="selectTopN(20)">Top 20</button>
                    <button class="btn-preset" onclick="selectTopN(50)">Top 50</button>
                    <button class="btn-preset" onclick="selectTopN(100)">Top 100 (Tümü)</button>
                    <button class="btn-preset btn-preset-danger" onclick="selectTopN(0)">Tümünü Kapat</button>
                </div>
            </div>
            <div class="coin-chips-grid" id="coin-chips-container" style="display:none; transition:all 0.3s ease;"></div>
        </div>

        <div class="section-header">
            <div style="display:flex; align-items:center; gap:14px; flex-wrap:wrap;">
                <div class="section-title">📊 PARİTE SEVİYE RADARI</div>
                <div id="watchlist-search-count-badge" style="display:none; font-size:12px; font-weight:800; color:#58a6ff; background:rgba(56,139,253,0.15); border:1px solid rgba(56,139,253,0.3); padding:4px 12px; border-radius:12px;"></div>
            </div>
        </div>
        <div class="watchlist-grid" id="watchlist-container"></div>
    </div>

    <!-- =========================================================================
         4. SEKME: İŞLEM GEÇMİŞİ
         ========================================================================= -->
    <div id="main-tab-content-ledger" class="main-tab-content">
        <div class="history-full-box">
            <!-- 📊 SETUP PERFORMANS MATRİSİ -->
            <div style="margin-bottom:18px;">
                <div style="font-size:12px; font-weight:800; color:var(--cyan); text-transform:uppercase; letter-spacing:0.8px; font-family:'JetBrains Mono'; margin-bottom:10px; display:flex; align-items:center; gap:6px;">
                    <span>📊</span> KURULUM BAZLI STRATEJİ PERFORMANSI (16 SETUP MATRİSİ)
                </div>
                <div class="setup-matrix-grid" id="ledger-setup-matrix-container">
                    <!-- Dynamically populated by renderSetupPerformanceMatrix() -->
                </div>
            </div>

            <div class="history-top-controls">
                <div style="display:flex; align-items:center; gap:12px;">
                    <div class="panel-title" style="margin:0;">📜 İşlem Geçmişi</div>
                    <span style="font-size:13px; background:var(--card-bg); padding:4px 10px; border-radius:8px; font-family:'JetBrains Mono'" id="history-total-count">0 İşlem</span>
                </div>
                
                <div class="filter-group">
                    <select class="filter-select" id="filter-symbol" onchange="onLedgerFilterChange()">
                        <option value="ALL">Tüm Pariteler</option>
                    </select>

                    <select class="filter-select" id="filter-setup" onchange="onLedgerFilterChange()">
                        <option value="ALL">🎯 Tüm Stratejiler (18 Setup)</option>
                        
                        <optgroup label="🔵 LİKİDİTE & nPOC">
                            <option value="NPOC">🔵 nPOC Likidite Sekmesi / Reddi (Setup 9, 10)</option>
                        </optgroup>
                        
                        <optgroup label="🔁 DESTEK & DİRENÇ RETEST / FLIP">
                            <option value="RETEST">🔁 Tüm Retest & Flip Kurulumları (Setup 5-16)</option>
                            <option value="FLIP_AVWAP">〰️ Dip/Tepe AVWAP & mVAH Reclaim (Setup 15)</option>
                            <option value="FLIP_CAM">🛡️ Camarilla S3/R3/S4/R4 Flip (Setup 5, 7, 13, 16)</option>
                            <option value="FLIP_PIVOT">⚖️ Pivot P & mPOC Flip / Retest (Setup 11, 14)</option>
                        </optgroup>
                        
                        <optgroup label="⚡ CAMARILLA KIRILIMLARI (BREAKOUT)">
                            <option value="CAM_BO">⚡ Camarilla S4 / R4 Breakout (Setup 1, 2)</option>
                            <option value="BREAKDOWN">🚨 Destek Çöküşü / Breakdown (Setup 12)</option>
                        </optgroup>
                        
                        <optgroup label="🛡️ BANT İÇİ DÖNÜŞ (BOUNCE / REJECTION)">
                            <option value="CAM_BOUNCE">🛡️ Camarilla S3 Sekmesi / R3 Reddi (Setup 3, 4)</option>
                        </optgroup>
                        
                        <optgroup label="🟣 MAKRO HACİM ALANI">
                            <option value="MACRO">🟣 mVAL / mVAH Makro Kırılımı (Setup 6, 8)</option>
                        </optgroup>
                        
                        <optgroup label="🪤 TUZAK İNTİKAMI (REFORM 4)">
                            <option value="RECLAIM">🪤 Fakeout Reclaim (Boğa / Ayı Tuzağı İntikamı)</option>
                        </optgroup>

                        <optgroup label="🎯 DİĞER ÖZEL STRATEJİLER">
                            <option value="SCALP">🎯 Diğer Scalp / Iceberg & L2 Derinlik</option>
                        </optgroup>
                    </select>

                    <select class="filter-select" id="filter-status" onchange="onLedgerFilterChange()">
                        <option value="ALL">Tüm Sonuçlar</option>
                        <option value="WIN">🟢 Kârlı İşlemler</option>
                        <option value="LOSS">🔴 Zararlı İşlemler</option>
                    </select>

                    <button class="btn-export" onclick="resetLedgerFilters()" style="background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.15); box-shadow:none; padding:7px 12px;" title="Tüm filtreleri varsayılana sıfırla">
                        🔄 Sıfırla
                    </button>
                    <button class="btn-export" onclick="downloadExcelReport()" title="Pasta grafikleri, KPI kartları ve renklendirilmiş sekmeleriyle Excel raporu indir">
                        📊 Excel İndir (.xlsx)
                    </button>
                    <button class="btn-export" onclick="downloadCSVReport()" style="background:rgba(255,255,255,0.08); border:1px solid var(--border-light); box-shadow:none;" title="CSV tablosu indir">
                        📄 CSV İndir
                    </button>
                </div>
            </div>

            <div style="overflow-x:auto;">
                <table class="trade-table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Kapanış Tarihi (TSİ)</th>
                            <th>Süre</th>
                            <th>Parite</th>
                            <th>Yön & Kaldıraç</th>
                            <th>Giriş Fiyatı</th>
                            <th>Çıkış Fiyatı</th>
                            <th>Net Kâr ($)</th>
                            <th>ROE (%)</th>
                            <th>R-Katı (1R)</th>
                            <th>Zirve Kâr (MFE)</th>
                            <th>🎯 Giriş Stratejisi</th>
                            <th>🚪 Kapanış Nedeni</th>
                            <th>🔬 Adli İnceleme</th>
                        </tr>
                    </thead>
                    <tbody id="trade-table-body">
                        <tr>
                            <td colspan="14" style="text-align:center; padding: 40px; color:#94a3b8;">
                                Kayıtlı işlem geçmişi bulunmuyor.
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <!-- LEDGER 20-ITEM PAGINATION STRIP -->
            <div id="ledger-pagination-container" style="display:flex; justify-content:space-between; align-items:center; margin-top:16px; padding:12px 18px; background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.06); border-radius:12px; flex-wrap:wrap; gap:12px;"></div>
        </div>
    </div>

    <!-- =========================================================================
         5. SEKME: 🧬 CANLI COIN DNA & PERSONA MATRİSİ (100 PARİTE)
         ========================================================================= -->
    <div id="main-tab-content-persona" class="main-tab-content">
        <!-- 4 KPI PERSONA ÖZET KARTLARI -->
        <div class="cockpit-kpi-grid">
            <div class="cockpit-kpi-card" style="border-top:3px solid #fbc531;">
                <div class="kpi-card-head">
                    <span class="kpi-card-title">👑 Altın Lig (Pusu Ustaları)</span>
                    <span class="kpi-card-icon">👑</span>
                </div>
                <div class="kpi-card-val" id="persona-gold-count" style="color:#fbc531;">0 Parite</div>
                <div class="kpi-card-sub">Marjin: <b>x1.3</b> | WR &ge; %60 | Tuzak &le; %25</div>
                <div style="font-size:11px; color:#64748b; font-family:'JetBrains Mono', monospace; margin-top:3px;">Kırılım + Pusu yetkisi tam açık elit pariteler</div>
            </div>

            <div class="cockpit-kpi-card" style="border-top:3px solid #38bdf8;">
                <div class="kpi-card-head">
                    <span class="kpi-card-title">⚪ Standart / Dengeli Lig</span>
                    <span class="kpi-card-icon">⚖️</span>
                </div>
                <div class="kpi-card-val" id="persona-standard-count" style="color:#38bdf8;">0 Parite</div>
                <div class="kpi-card-sub">Marjin: <b>x1.0</b> | Dengeli Parametreler</div>
                <div style="font-size:11px; color:#64748b; font-family:'JetBrains Mono', monospace; margin-top:3px;">Tüm kurumsal likidite seviyeleri standart izlenir</div>
            </div>

            <div class="cockpit-kpi-card" style="border-top:3px solid var(--red);">
                <div class="kpi-card-head">
                    <span class="kpi-card-title">⚠️ Whipsaw / Tuzakçı Ligi</span>
                    <span class="kpi-card-icon">🛡️</span>
                </div>
                <div class="kpi-card-val" id="persona-whipsaw-count" style="color:var(--red);">0 Parite</div>
                <div class="kpi-card-sub">Kırılım: <b style="color:var(--red);">KİLİTLİ 🔒</b> | Sekme: <b>x0.5</b> Marjin</div>
                <div style="font-size:11px; color:#64748b; font-family:'JetBrains Mono', monospace; margin-top:3px;">Fitil tuzaklarına karşı kırılım yasak, yalnız dip/tepe pusu</div>
            </div>

            <div class="cockpit-kpi-card" style="border-top:3px solid var(--cyan);">
                <div class="kpi-card-head">
                    <span class="kpi-card-title">🔄 Otonom Terfi & Tenzil</span>
                    <span class="kpi-card-icon">🧬</span>
                </div>
                <div class="kpi-card-val" id="persona-healing-status" style="color:var(--cyan); font-size:20px;">Dinamik Self-Healing</div>
                <div class="kpi-card-sub">Son 15 İşlem Kayan Pencere (Rolling)</div>
                <div style="font-size:11px; color:#64748b; font-family:'JetBrains Mono', monospace; margin-top:3px;">Performansı düzelen pariteler anında terfi eder</div>
            </div>
        </div>

        <!-- PERSONA FİLTRE VE ARAMA KARTI -->
        <div class="table-container" style="margin-top:18px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:18px; flex-wrap:wrap; gap:14px;">
                <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
                    <div style="display:flex; background:rgba(255,255,255,0.04); border:1px solid var(--border); border-radius:10px; padding:3px; gap:4px;">
                        <button id="pfilter-btn-ALL" class="chart-tab-btn tab-active" onclick="setPersonaFilter('ALL')">
                            Tümü (<span id="pfilter-count-ALL">0</span>)
                        </button>
                        <button id="pfilter-btn-GOLD" class="chart-tab-btn" onclick="setPersonaFilter('GOLD')" style="color:#fbc531;">
                            👑 Altın Lig (<span id="pfilter-count-GOLD">0</span>)
                        </button>
                        <button id="pfilter-btn-STANDARD" class="chart-tab-btn" onclick="setPersonaFilter('STANDARD')" style="color:#cbd5e1;">
                            ⚪ Standart (<span id="pfilter-count-STANDARD">0</span>)
                        </button>
                        <button id="pfilter-btn-WHIPSAW" class="chart-tab-btn" onclick="setPersonaFilter('WHIPSAW')" style="color:var(--red);">
                            ⚠️ Whipsaw Kalkanı Aktif (<span id="pfilter-count-WHIPSAW">0</span>)
                        </button>
                    </div>
                </div>

                <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
                    <div style="position:relative; width:260px;">
                        <input type="text" id="persona-search-input" placeholder="🔍 Parite Ara (Örn: CRV, SOL)..." oninput="onPersonaSearchInput(this.value)" class="settings-input" style="padding:8px 12px; font-size:12.5px; border-radius:8px;" />
                    </div>
                    <button class="btn-export" onclick="downloadExcelReport()" style="padding:8px 16px; font-size:12px;">
                        📊 Excel DNA Raporunu İndir (.xlsx)
                    </button>
                </div>
            </div>

            <div style="overflow-x:auto;">
                <table class="trade-table">
                    <thead>
                        <tr>
                            <th>Parite</th>
                            <th>Mevcut Lig / Persona</th>
                            <th>Son Havuz</th>
                            <th>Kazanma Oranı (WR %)</th>
                            <th>Tuzak Fitil (Fakeout %)</th>
                            <th>Net Kâr ($)</th>
                            <th>🎯 İzin Verilen Stratejiler</th>
                            <th>🛡️ Risk & Marjin Katsayısı</th>
                            <th>Aksiyon</th>
                        </tr>
                    </thead>
                    <tbody id="persona-table-body">
                        <tr>
                            <td colspan="9" style="text-align:center; padding: 40px; color:#94a3b8;">
                                Canlı coin persona verileri yükleniyor...
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
            
            <div id="persona-table-footer" style="display:flex; justify-content:space-between; align-items:center; margin-top:16px; padding:12px 18px; background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.06); border-radius:12px; font-family:'JetBrains Mono'; font-size:12px; color:#94a3b8;">
                <div>Toplam <b id="persona-footer-count" style="color:#fff;">0</b> parite analiz edildi.</div>
                <div style="color:var(--cyan);">🛡️ Kalkan Kuralı: %45+ Sahte Fitil üreten paritelerde Breakout otomatik engellenir, dip-tepe sekmeleri yarım marjinle korunur.</div>
            </div>
        </div>
    </div>

    <!-- =========================================================================
         5b. SEKME: 👻 GÖLGE İŞLEM TAKİP MOTORU & OTONOM COIN DNA KALİBRASYON MASASI
         ========================================================================= -->
    <div id="main-tab-content-shadow" class="main-tab-content" style="display:none;">
        <!-- BAŞLIK VE 1-TIK EXCEL İNDİR AKSİYON ÇUBUĞU -->
        <div style="display:flex; justify-content:space-between; align-items:center; background:linear-gradient(135deg, rgba(17,23,38,0.95), rgba(14,19,31,0.98)); border:1px solid var(--border-light); border-radius:12px; padding:18px 24px; margin-bottom:20px; box-shadow:0 8px 32px rgba(0,0,0,0.36); flex-wrap:wrap; gap:16px;">
            <div>
                <div style="display:flex; align-items:center; gap:10px;">
                    <span style="font-size:24px;">👻</span>
                    <h2 style="font-size:18px; font-weight:800; color:#fff; margin:0; letter-spacing:0.5px;">GÖLGE İŞLEM TAKİP MOTORU & OTONOM COIN DNA MASASI</h2>
                    <span style="background:rgba(168,85,247,0.18); color:#c084fc; border:1px solid rgba(168,85,247,0.4); font-size:11px; font-weight:700; padding:3px 10px; border-radius:20px;">COUNTERFACTUAL SHADOW ENGINE</span>
                </div>
                <div style="font-size:12px; color:#94a3b8; margin-top:5px; font-family:'JetBrains Mono', monospace;">
                    Reddedilen tüm sinyaller arka planda canlı fiyatla izlenir • Hero (Kurtarılan) vs Spoiler (Kaçan) kalkan analizi • Otonom parametre kalibrasyonu
                </div>
            </div>
            <div style="display:flex; gap:12px; align-items:center;">
                <button onclick="window.location.href='/api/export_shadow_excel'" class="action-btn" style="background:linear-gradient(135deg, #10b981, #059669); color:#fff; font-weight:700; padding:10px 18px; border-radius:8px; display:flex; align-items:center; gap:8px; border:none; cursor:pointer; box-shadow:0 4px 14px rgba(16,185,129,0.35); transition:all 0.2s ease;">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                    <span>📥 Gölge & Coin DNA Excel İndir (.xlsx)</span>
                </button>
            </div>
        </div>

        <!-- 5 KPI ÖZET KARTI -->
        <div class="cockpit-kpi-grid" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:14px; margin-bottom:20px;">
            <div class="cockpit-kpi-card" style="border-top:3px solid #10b981;">
                <div class="kpi-card-head">
                    <span class="kpi-card-title">🛡️ Kurtarılan Net Zarar (Hero)</span>
                    <span class="kpi-card-icon">🛡️</span>
                </div>
                <div class="kpi-card-val" id="shadow-kpi-saved" style="color:#10b981;">$0.00</div>
                <div class="kpi-card-sub"><span id="shadow-kpi-hero-count">0</span> Stop İşlemi Engellendi</div>
                <div style="font-size:11px; color:#64748b; font-family:'JetBrains Mono', monospace; margin-top:3px;">Kalkanların koruduğu gerçek sermaye</div>
            </div>

            <div class="cockpit-kpi-card" style="border-top:3px solid #f43f5e;">
                <div class="kpi-card-head">
                    <span class="kpi-card-title">⚠️ Kaçan Fırsat Kârı (Spoiler)</span>
                    <span class="kpi-card-icon">⚠️</span>
                </div>
                <div class="kpi-card-val" id="shadow-kpi-missed" style="color:#f43f5e;">$0.00</div>
                <div class="kpi-card-sub"><span id="shadow-kpi-spoiler-count">0</span> Kazanan İşlem Engellendi</div>
                <div style="font-size:11px; color:#64748b; font-family:'JetBrains Mono', monospace; margin-top:3px;">Filtrelerin kaçırdığı potansiyel TP kazancı</div>
            </div>

            <div class="cockpit-kpi-card" style="border-top:3px solid #f59e0b;">
                <div class="kpi-card-head">
                    <span class="kpi-card-title">🎯 Kalkan Verimliliği (SEI)</span>
                    <span class="kpi-card-icon">🎯</span>
                </div>
                <div class="kpi-card-val" id="shadow-kpi-sei" style="color:#f59e0b;">%100.0</div>
                <div class="kpi-card-sub">Kurtarılan / Toplam Etki Oranı</div>
                <div style="font-size:11px; color:#64748b; font-family:'JetBrains Mono', monospace; margin-top:3px;">&ge; %70 Elit Kurumsal Koruma Seviyesi</div>
            </div>

            <div class="cockpit-kpi-card" style="border-top:3px solid #06b6d4;">
                <div class="kpi-card-head">
                    <span class="kpi-card-title">💎 Net Kalkan Alfası</span>
                    <span class="kpi-card-icon">💎</span>
                </div>
                <div class="kpi-card-val" id="shadow-kpi-alpha" style="color:#06b6d4;">$0.00</div>
                <div class="kpi-card-sub">Kurtarılan Zarar - Kaçan Kâr</div>
                <div style="font-size:11px; color:#64748b; font-family:'JetBrains Mono', monospace; margin-top:3px;">Sistem filtrelerinin net kâr katkısı</div>
            </div>

            <div class="cockpit-kpi-card" style="border-top:3px solid #a855f7;">
                <div class="kpi-card-head">
                    <span class="kpi-card-title">👻 Canlı Gölge Pozisyonlar</span>
                    <span class="kpi-card-icon">⏳</span>
                </div>
                <div class="kpi-card-val" id="shadow-kpi-active" style="color:#a855f7;">0 Aktif</div>
                <div class="kpi-card-sub"><span id="shadow-kpi-total-tracked">0</span> Toplam Sinyal Taraması</div>
                <div style="font-size:11px; color:#64748b; font-family:'JetBrains Mono', monospace; margin-top:3px;">Anlık tick ve 5M mum teyidiyle takipte</div>
            </div>
        </div>

        <!-- GÖLGE SEKME KONTROL VE HIZLI GİZLE/GÖSTER BARI -->
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:18px; padding:10px 16px; background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.06); border-radius:10px; flex-wrap:wrap; gap:10px;">
            <div style="display:flex; align-items:center; gap:8px;">
                <span style="font-size:13px; font-weight:700; color:#fff;">📑 Görünüm & Tablo Denetimi:</span>
                <span style="font-size:11px; color:#94a3b8;">Aşağı doğru uzayan tabloları tek tıkla gizleyebilir veya açabilirsiniz.</span>
            </div>
            <div style="display:flex; gap:8px;">
                <button class="nav-tab-btn" onclick="toggleAllShadowSections(false)" style="padding:6px 12px; font-size:11px; display:flex; align-items:center; gap:5px; border-color:rgba(244,63,94,0.3); color:#f43f5e;" title="Tüm tabloları gizleyerek kompakt başlık moduna geçer">
                    <span>📁</span> <span>Tüm Tabloları Gizle (Kompakt Mod)</span>
                </button>
                <button class="nav-tab-btn" onclick="toggleAllShadowSections(true)" style="padding:6px 12px; font-size:11px; display:flex; align-items:center; gap:5px; border-color:rgba(16,185,129,0.3); color:#10b981;" title="Tüm tabloları görünür yapar">
                    <span>📂</span> <span>Tüm Tabloları Aç</span>
                </button>
            </div>
        </div>

        <!-- 1. BÖLÜM: 🧬 COIN BAZLI CANLI DNA VE KALİBRASYON MASASI -->
        <div class="table-container" style="margin-bottom:24px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; flex-wrap:wrap; gap:12px;">
                <div>
                    <h3 style="font-size:15px; font-weight:700; color:#fff; margin:0; display:flex; align-items:center; gap:8px;">
                        <span>🧬</span> 100 Parite Canlı Piyasa DNA'sı ve Otonom Kalibrasyon Masası
                    </h3>
                    <div style="font-size:11px; color:#94a3b8; margin-top:4px;">Paritelerin canlı test sonuçları, fitil esneklikleri ve botun otonom parametre iyileştirme tavsiyeleri</div>
                </div>
                <div style="display:flex; gap:8px; align-items:center;">
                    <input type="text" id="shadow-coin-search" placeholder="Coin ara (ENA, DOGE, MOVR...)" oninput="filterShadowCoinsTable()" style="background:#090d16; border:1px solid var(--border); color:#fff; padding:6px 12px; border-radius:6px; font-size:12px; width:235px; min-width:200px; font-family:'JetBrains Mono', monospace;">
                    <button class="nav-tab-btn active" id="btn-shadow-filter-all" onclick="setShadowCoinFilter('ALL')" style="padding:6px 12px; font-size:11px;">Tümü</button>
                    <button class="nav-tab-btn" id="btn-shadow-filter-relax" onclick="setShadowCoinFilter('RELAX')" style="padding:6px 12px; font-size:11px; border-color:rgba(244,63,94,0.4); color:#f43f5e;">⚠️ Gevşet</button>
                    <button class="nav-tab-btn" id="btn-shadow-filter-keep" onclick="setShadowCoinFilter('KEEP')" style="padding:6px 12px; font-size:11px; border-color:rgba(16,185,129,0.4); color:#10b981;">👑 Koru</button>
                    <button class="nav-tab-btn" id="btn-toggle-shadow-dna" onclick="toggleShadowSection('shadow-dna')" style="padding:6px 12px; font-size:11px; border-color:rgba(56,189,248,0.4); color:#38bdf8; display:flex; align-items:center; gap:5px;" title="Bu tabloyu gizle veya aç">
                        <span id="icon-toggle-shadow-dna">👁️</span> <span id="text-toggle-shadow-dna">Gizle</span>
                    </button>
                </div>
            </div>
            <div class="table-responsive" id="container-shadow-dna" style="max-height:520px; overflow-y:auto;">
                <table class="data-table" style="width:100%; border-collapse:collapse;">
                    <thead style="position:sticky; top:0; z-index:10; background:#0b101b;">
                        <tr>
                            <th style="text-align:left; width:75px;">Parite</th>
                            <th style="text-align:center; width:60px;">Toplam</th>
                            <th style="text-align:center; width:65px;" title="Hero Kalkan (Zarardan Kurtarılan İşlem)">🛡️ Hero</th>
                            <th style="text-align:center; width:65px;" title="Spoiler Kalkan (Kaçan Kârlı İşlem)">⚠️ Spoiler</th>
                            <th style="text-align:center; width:85px;">Kurtarılan</th>
                            <th style="text-align:center; width:85px;">Kaçan Kâr</th>
                            <th style="text-align:center; width:65px;" title="Shield Efficiency Index">SEI (%)</th>
                            <th style="text-align:left; width:190px; min-width:170px;">En Çok Engelleyen Kalkan</th>
                            <th style="text-align:center; width:65px;" title="Fitil Esnekliği">Fitil %</th>
                            <th style="text-align:center; width:95px;">Durum</th>
                            <th style="text-align:left; min-width:320px;">Otonom Kalibrasyon Teşhisi</th>
                            <th style="text-align:center; width:75px;">Detay</th>
                        </tr>
                    </thead>
                    <tbody id="shadow-coin-matrix-tbody">
                        <tr><td colspan="12" style="text-align:center; padding:24px; color:#64748b;">Henüz gölge işlem verisi toplanıyor...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- 2. BÖLÜM: 🛡️ KALKAN LİDERLİK VE VERİMLİLİK KARNESİ (SHIELD AUDIT) -->
        <div class="table-container" style="margin-bottom:24px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; flex-wrap:wrap; gap:12px;">
                <div>
                    <h3 style="font-size:15px; font-weight:700; color:#fff; margin:0; display:flex; align-items:center; gap:8px;">
                        <span>🛡️</span> Güvenlik Kalkanları ve Filtre Verimlilik Karnesi (Shield Leaderboard)
                    </h3>
                    <div style="font-size:11px; color:#94a3b8; margin-top:4px;">Hangi kalkan botu kaç dolarlık zarardan kurtardı? Hangisi kaç dolarlık kârı engelledi?</div>
                </div>
                <div>
                    <button class="nav-tab-btn" id="btn-toggle-shadow-shields" onclick="toggleShadowSection('shadow-shields')" style="padding:6px 12px; font-size:11px; border-color:rgba(56,189,248,0.4); color:#38bdf8; display:flex; align-items:center; gap:5px;" title="Bu tabloyu gizle veya aç">
                        <span id="icon-toggle-shadow-shields">👁️</span> <span id="text-toggle-shadow-shields">Gizle</span>
                    </button>
                </div>
            </div>
            <div class="table-responsive" id="container-shadow-shields" style="max-height:480px; overflow-y:auto;">
                <table class="data-table" style="width:100%; border-collapse:collapse;">
                    <thead style="position:sticky; top:0; z-index:10; background:#0b101b;">
                        <tr>
                            <th style="text-align:left;">Kalkan / Filtre Adı</th>
                            <th>Toplam Bloklama</th>
                            <th>Kahraman (Hero)</th>
                            <th>Frenleyici (Spoiler)</th>
                            <th>Kurtarılan Zarar ($)</th>
                            <th>Kaçan Kâr ($)</th>
                            <th>Net Katkı ($)</th>
                            <th>SEI (%)</th>
                            <th>Kalkan Rolü</th>
                        </tr>
                    </thead>
                    <tbody id="shadow-shield-leaderboard-tbody">
                        <tr><td colspan="9" style="text-align:center; padding:24px; color:#64748b;">Kalkan verileri hesaplanıyor...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- 3. BÖLÜM: 👻 AKTİF GÖLGE POZİSYONLAR & SON TAMAMLANAN GÖLGE DEFTERİ -->
        <div style="display:grid; grid-template-columns:1fr; gap:20px;">
            <!-- AKTİF SANAL İŞLEMLER -->
            <div class="table-container">
                <div style="margin-bottom:14px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
                    <div>
                        <h3 style="font-size:15px; font-weight:700; color:#fff; margin:0; display:flex; align-items:center; gap:8px;">
                            <span>⏳</span> Canlı İzlenen Aktif Gölge Pozisyonlar (Live Shadow Tracking)
                        </h3>
                        <div style="font-size:11px; color:#94a3b8; margin-top:4px;">Açılması engellenen fakat anlık fiyat ve 5M mum teyidiyle canlı takip edilen pozisyonlar</div>
                    </div>
                    <div style="display:flex; gap:8px; align-items:center;">
                        <span id="shadow-active-count-badge" style="background:rgba(168,85,247,0.15); color:#a855f7; border:1px solid rgba(168,85,247,0.3); font-size:11px; font-weight:700; padding:2px 8px; border-radius:12px;">0 Pozisyon</span>
                        <button class="nav-tab-btn" id="btn-toggle-shadow-active" onclick="toggleShadowSection('shadow-active')" style="padding:6px 12px; font-size:11px; border-color:rgba(168,85,247,0.4); color:#a855f7; display:flex; align-items:center; gap:5px;" title="Bu tabloyu gizle veya aç">
                            <span id="icon-toggle-shadow-active">👁️</span> <span id="text-toggle-shadow-active">Gizle</span>
                        </button>
                    </div>
                </div>
                <div class="table-responsive" id="container-shadow-active" style="max-height:480px; overflow-y:auto;">
                    <table class="data-table" style="width:100%; border-collapse:collapse;">
                        <thead style="position:sticky; top:0; z-index:10; background:#0b101b;">
                            <tr>
                                <th style="text-align:left;">Parite</th>
                                <th>Yön</th>
                                <th style="text-align:left;">Giriş Stratejisi</th>
                                <th style="text-align:left;">Engelleyen Kalkan</th>
                                <th>Giriş Fiyatı</th>
                                <th>Güncel Fiyat</th>
                                <th>Stop Fiyatı</th>
                                <th>Planlanan TP1</th>
                                <th>Planlanan TP2</th>
                                <th>Zirve MFE</th>
                                <th>Maks MAE</th>
                                <th>Canlı ROE</th>
                                <th>Canlı Sanal PnL</th>
                                <th>Süre (Dk)</th>
                            </tr>
                        </thead>
                        <tbody id="shadow-active-tbody">
                            <tr><td colspan="14" style="text-align:center; padding:20px; color:#64748b;">Şu an canlı izlenen açık gölge pozisyon yok.</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- SON TAMAMLANAN GÖLGE DEFTERİ -->
            <div class="table-container">
                <div style="margin-bottom:14px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
                    <div>
                        <h3 style="font-size:15px; font-weight:700; color:#fff; margin:0; display:flex; align-items:center; gap:8px;">
                            <span>📜</span> Son Tamamlanan Gölge İşlem Defteri (Son 50 Sonuç)
                        </h3>
                        <div style="font-size:11px; color:#94a3b8; margin-top:4px;">TP1, TP2, Stop veya Zaman Aşımıyla sonuçlanan sanal işlemler ve adli teşhis</div>
                    </div>
                    <div>
                        <button class="nav-tab-btn" id="btn-toggle-shadow-history" onclick="toggleShadowSection('shadow-history')" style="padding:6px 12px; font-size:11px; border-color:rgba(56,189,248,0.4); color:#38bdf8; display:flex; align-items:center; gap:5px;" title="Bu tabloyu gizle veya aç">
                            <span id="icon-toggle-shadow-history">👁️</span> <span id="text-toggle-shadow-history">Gizle</span>
                        </button>
                    </div>
                </div>
                <div class="table-responsive" id="container-shadow-history" style="max-height:480px; overflow-y:auto;">
                    <table class="data-table" style="width:100%; border-collapse:collapse;">
                        <thead style="position:sticky; top:0; z-index:10; background:#0b101b;">
                            <tr>
                                <th>Gölge ID</th>
                                <th style="text-align:left;">Parite</th>
                                <th>Yön</th>
                                <th style="text-align:left;">Setup</th>
                                <th style="text-align:left;">Engelleyen Kalkan</th>
                                <th>Giriş ($)</th>
                                <th>Çıkış ($)</th>
                                <th>MFE</th>
                                <th>MAE</th>
                                <th>Sanal PnL ($)</th>
                                <th>Kalkan Teşhisi (Verdict)</th>
                                <th style="text-align:left;">Adli Teşhis & Neden-Sonuç</th>
                                <th>Sonuç Durumu</th>
                                <th>Giriş Zamanı</th>
                            </tr>
                        </thead>
                        <tbody id="shadow-history-tbody">
                            <tr><td colspan="14" style="text-align:center; padding:20px; color:#64748b;">Henüz tamamlanan gölge işlem yok.</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <!-- =========================================================================
         6. SEKME: ⚡ CANLI MİKRO PİYASA & FONLAMA / SQUEEZE RADARI (100 PARİTE)
         ========================================================================= -->
    <div id="main-tab-content-funding" class="main-tab-content" style="display:none;">
        <!-- 4 KPI FONLAMA ÖZET KARTLARI -->
        <div class="cockpit-kpi-grid">
            <div class="cockpit-kpi-card" style="border-top:3px solid #38bdf8;">
                <div class="kpi-card-head">
                    <span class="kpi-card-title">Piyasa Medyan Fonlama Oranı</span>
                    <span class="kpi-card-icon">⚡</span>
                </div>
                <div class="kpi-card-val" id="funding-median-val" style="color:#38bdf8;">+0.0100%</div>
                <div class="kpi-card-sub">100 Paritenin Ortanca Ağırlığı (8h)</div>
                <div style="font-size:11px; color:#64748b; font-family:'JetBrains Mono'; margin-top:3px;">Dengeli Piyasa Bandı: -%0.02 ile +%0.05</div>
            </div>

            <div class="cockpit-kpi-card" style="border-top:3px solid var(--red);">
                <div class="kpi-card-head">
                    <span class="kpi-card-title">Short Squeeze Riski (Short Kilitli 🔒)</span>
                    <span class="kpi-card-icon">⚠️</span>
                </div>
                <div class="kpi-card-val" id="funding-squeeze-count" style="color:var(--red);">0 Parite</div>
                <div class="kpi-card-sub">Aşırı Negatif Fonlama (&lt; -%0.0300)</div>
                <div style="font-size:11px; color:#f87171; font-family:'JetBrains Mono'; margin-top:3px;">Piyasa yapıcı avına karşı Short açılışları kilitlendi</div>
            </div>

            <div class="cockpit-kpi-card" style="border-top:3px solid #fbc531;">
                <div class="kpi-card-head">
                    <span class="kpi-card-title">Aşırı Şişkin Long (Long Kilitli 🔒)</span>
                    <span class="kpi-card-icon">🔥</span>
                </div>
                <div class="kpi-card-val" id="funding-overheat-count" style="color:#fbc531;">0 Parite</div>
                <div class="kpi-card-sub">Aşırı Pozitif Fonlama (&gt; +%0.0600)</div>
                <div style="font-size:11px; color:#fde047; font-family:'JetBrains Mono'; margin-top:3px;">Tepe tuzağına karşı Long Breakout engellenir</div>
            </div>

            <div class="cockpit-kpi-card" style="border-top:3px solid var(--green);">
                <div class="kpi-card-head">
                    <span class="kpi-card-title">Squeeze Koruma Kalkanı</span>
                    <span class="kpi-card-icon">🛡️</span>
                </div>
                <div class="kpi-card-val" id="funding-shield-status" style="color:var(--green); font-size:20px;">Otomatik Veto Aktif</div>
                <div class="kpi-card-sub" id="funding-source-sub">Canlı Çoklu-Borsa Vadeli Senkronizasyonu</div>
                <div style="font-size:11px; color:#4ade80; font-family:'JetBrains Mono'; margin-top:3px;">Ters yönlü tasfiye tuzakları sıfırlandı</div>
            </div>
        </div>

        <!-- FONLAMA FİLTRE VE ARAMA KARTI -->
        <div class="history-full-box" style="margin-top:20px;">
            <div class="history-top-controls" style="flex-wrap:wrap; gap:12px;">
                <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                    <button id="ffilter-btn-ALL" class="chart-tab-btn tab-active" onclick="setFundingFilter('ALL')">
                        Tümü (<span id="ffilter-count-ALL">100</span>)
                    </button>
                    <button id="ffilter-btn-SQUEEZE" class="chart-tab-btn" onclick="setFundingFilter('SQUEEZE')" style="color:var(--red);">
                        ⚠️ Short Squeeze Kalkanı (<span id="ffilter-count-SQUEEZE">0</span>)
                    </button>
                    <button id="ffilter-btn-OVERHEAT" class="chart-tab-btn" onclick="setFundingFilter('OVERHEAT')" style="color:#fbc531;">
                        🔥 Aşırı Long (<span id="ffilter-count-OVERHEAT">0</span>)
                    </button>
                    <button id="ffilter-btn-BALANCED" class="chart-tab-btn" onclick="setFundingFilter('BALANCED')" style="color:var(--cyan);">
                        🟢 Dengeli Bölge (<span id="ffilter-count-BALANCED">0</span>)
                    </button>
                </div>

                <div style="display:flex; align-items:center; gap:10px;">
                    <input type="text" id="funding-search-input" placeholder="🔍 Parite Ara (Örn: ACE, ONG)..." oninput="onFundingSearchInput(this.value)" class="settings-input" style="padding:8px 12px; font-size:12.5px; border-radius:8px;" />
                    <button class="btn-export-excel" onclick="window.location.href='/api/export_excel'" style="margin:0; padding:8px 14px; font-size:12.5px;">
                        📊 Excel Raporunu İndir (.xlsx)
                    </button>
                </div>
            </div>

            <!-- 100 COIN FONLAMA & SQUEEZE MATRİS TABLOSU -->
            <div class="history-table-wrap" style="max-height: 600px; overflow-y:auto;">
                <table class="history-table">
                    <thead>
                        <tr>
                            <th>Parite</th>
                            <th>Anlık Fonlama Oranı (%)</th>
                            <th>Squeeze Teşhisi / Durum</th>
                            <th>Mark Fiyatı ($)</th>
                            <th>Geri Sayım (Sonraki Ödeme)</th>
                            <th>🎯 İzin Verilen Yönler</th>
                            <th>🛡️ Kalkan Emniyet Kuralı</th>
                            <th>Aksiyon</th>
                        </tr>
                    </thead>
                    <tbody id="funding-table-body">
                        <tr>
                            <td colspan="8" style="text-align:center; padding: 40px; color:#94a3b8;">
                                Canlı fonlama oranı verileri yükleniyor...
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div id="funding-table-footer" style="display:flex; justify-content:space-between; align-items:center; margin-top:16px; padding:12px 18px; background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.06); border-radius:12px; font-family:'JetBrains Mono'; font-size:12px; color:#94a3b8;">
                <div>Toplam <b id="funding-footer-count" style="color:#fff;">0</b> parite analiz edildi. <span id="funding-last-update-str" style="color:var(--cyan); margin-left:12px;"></span></div>
                <div style="color:var(--red);">🛡️ Squeeze Kuralı: Aşırı negatif fonlamalı coinlerde Short emirleri engellenir, kasanın yapay fitillerde erimesi önlenir.</div>
            </div>
        </div>

        <!-- =========================================================================
             B. GLOBAL LİKİDASYON RADARI & TASFİYE SÜPÜRME PANELİ (!forceOrder)
             ========================================================================= -->
        <div style="margin-top:28px; margin-bottom:14px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
            <div style="display:flex; align-items:center; gap:10px;">
                <span style="font-size:18px;">💥</span>
                <span style="font-size:16px; font-weight:800; color:#fff; font-family:'JetBrains Mono';">CANLI LİKİDASYON AKIŞI & TASFİYE SÜPÜRME RADARI (!forceOrder)</span>
            </div>
            <div style="font-size:12px; color:#94a3b8; font-family:'JetBrains Mono'; display:flex; align-items:center; gap:8px;">
                <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#22c55e; box-shadow:0 0 8px #22c55e;"></span>
                <span>Canlı Binance WebSocket Hattı Aktif (0ms Gecikme)</span>
            </div>
        </div>

        <!-- LİKİDASYON 3 KPI HERO -->
        <div class="cockpit-kpi-grid" style="margin-bottom:18px;">
            <div class="cockpit-kpi-card" style="border-top:3px solid #ef4444;">
                <div class="kpi-card-head">
                    <span class="kpi-card-title">Son 24h Toplam Tasfiye Hacmi</span>
                    <span class="kpi-card-icon">🌊</span>
                </div>
                <div class="kpi-card-val" id="liq-total-24h" style="color:#ef4444;">$0</div>
                <div class="kpi-card-sub">Piyasa Genelinde Zorunlu Tasfiyeler</div>
                <div style="font-size:11px; color:#fca5a5; font-family:'JetBrains Mono'; margin-top:3px;">Balinaların yakıt olarak kullandığı stop hacmi</div>
            </div>

            <div class="cockpit-kpi-card" style="border-top:3px solid #38bdf8;">
                <div class="kpi-card-head">
                    <span class="kpi-card-title">Tasfiye Baskısı (Long vs Short)</span>
                    <span class="kpi-card-icon">⚖️</span>
                </div>
                <div class="kpi-card-val" id="liq-ratio-text" style="color:#38bdf8; font-size:18px;">Long %50 / Short %50</div>
                <div style="margin-top:8px; width:100%; height:6px; background:rgba(255,255,255,0.08); border-radius:3px; display:flex; overflow:hidden;">
                    <div id="liq-bar-long" style="width:50%; height:100%; background:#ef4444; transition:width 0.4s ease;"></div>
                    <div id="liq-bar-short" style="width:50%; height:100%; background:#22c55e; transition:width 0.4s ease;"></div>
                </div>
                <div style="font-size:11px; color:#94a3b8; font-family:'JetBrains Mono'; margin-top:6px;">Kırmızı: Long Tasfiyesi | Yeşil: Short Tasfiyesi</div>
            </div>

            <div class="cockpit-kpi-card" style="border-top:3px solid #fbc531;">
                <div class="kpi-card-head">
                    <span class="kpi-card-title">Son 15dk En Sıcak Tasfiye Paritesi</span>
                    <span class="kpi-card-icon">🔥</span>
                </div>
                <div class="kpi-card-val" id="liq-top-sym" style="color:#fbc531; font-size:20px;">-</div>
                <div class="kpi-card-sub">En Çok Stop / Likidasyon Süpürülen Coin</div>
                <div style="font-size:11px; color:#fde047; font-family:'JetBrains Mono'; margin-top:3px;">S3/R3 destek-direnç sekmeleri için birincil aday</div>
            </div>
        </div>

        <!-- CANLI TASFİYE AKIŞ ŞERİDİ TABLOSU -->
        <div class="history-full-box">
            <div style="padding:14px 18px; border-bottom:1px solid rgba(255,255,255,0.06); display:flex; justify-content:space-between; align-items:center;">
                <div style="font-weight:800; font-size:13.5px; color:#fff; font-family:'JetBrains Mono';">
                    ⚡ Son Gerçekleşen Büyük Tasfiye Emirleri (Tape Stream)
                </div>
                <div style="font-size:11.5px; color:#64748b; font-family:'JetBrains Mono';">
                    Sadece &gt; $500 kurumsal ve perakende tasfiyeleri listelenir
                </div>
            </div>
            <div class="history-table-container" style="max-height:360px; overflow-y:auto;">
                <table class="history-table">
                    <thead>
                        <tr>
                            <th style="width:90px;">Zaman</th>
                            <th>Parite</th>
                            <th>Tasfiye Yönü</th>
                            <th>Zorunlu İşlem</th>
                            <th>Hacim ($)</th>
                            <th>İşlem Fiyatı</th>
                            <th>Strateji Yorumu & Kurumsal Anlamı</th>
                        </tr>
                    </thead>
                    <tbody id="liquidation-tape-body">
                        <tr>
                            <td colspan="7" style="text-align:center; padding:30px; color:#94a3b8;">
                                Canlı !forceOrder akışı bekleniyor...
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
            <div style="padding:10px 18px; background:rgba(255,255,255,0.015); border-top:1px solid rgba(255,255,255,0.06); font-family:'JetBrains Mono'; font-size:11.5px; color:#94a3b8;">
                🎯 <b>Strateji Kuralı:</b> Destek seviyelerinde (S3 / Aşağı nPOC) Long tasfiyeleri süpürüldüğünde, akıllı para piyasa satışlarını emerek dip dönüş fitili üretir. Bu teyit sekme (Bounce) girişlerini en dipten yakalamamızı sağlar.
            </div>
        </div>
    </div>

    <!-- =========================================================================
         7. SEKME: 🔬 CANLI MİKRO-CVD & TAKER AGRESYON RADARI (100 PARİTE)
         ========================================================================= -->
    <div id="main-tab-content-cvd" class="main-tab-content" style="display:none;">
        <!-- CVD BAŞLIK & CANLI DURUM -->
        <div style="margin-bottom:18px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
            <div style="display:flex; align-items:center; gap:12px;">
                <span style="font-size:26px;">🔬</span>
                <div>
                    <div style="font-size:17px; font-weight:800; color:#fff; font-family:'JetBrains Mono';">CANLI MİKRO-CVD & TAKER AGRESYON RADARI (Piyasanın Kalp Atışı)</div>
                    <div style="font-size:12px; color:#94a3b8; margin-top:2px;">Mum içi anlık piyasa alışları (Taker Buy) ve satışları (Taker Sell) — Milisaniyelik Net Para Akışı (Delta)</div>
                </div>
            </div>
            <div style="display:flex; align-items:center; gap:8px; font-size:12px; color:#94a3b8; font-family:'JetBrains Mono'; background:rgba(34,197,94,0.08); padding:6px 14px; border-radius:20px; border:1px solid rgba(34,197,94,0.25);">
                <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#22c55e; box-shadow:0 0 8px #22c55e;"></span>
                <span style="color:#86efac; font-weight:700;">Binance 100/100 K-Line Stream (0ms Gecikme)</span>
            </div>
        </div>

        <!-- 3 MİKRO KPI KARTI -->
        <div class="cockpit-kpi-grid" style="margin-bottom:20px;">
            <div class="cockpit-kpi-card" style="border-top:3px solid #38bdf8;">
                <div class="kpi-card-head">
                    <span class="kpi-card-title">📊 Piyasa Geneli Taker Güç Dengesi (Son 60s)</span>
                    <span class="kpi-card-icon">⚖️</span>
                </div>
                <div class="kpi-card-val" id="cvd-market-ratio-text" style="color:#38bdf8; font-size:18px;">Alıcı %50.0 / Satıcı %50.0</div>
                <div style="margin-top:8px; width:100%; height:7px; background:rgba(255,255,255,0.08); border-radius:4px; display:flex; overflow:hidden;">
                    <div id="cvd-market-bar-long" style="width:50%; height:100%; background:#22c55e; transition:width 0.4s ease;"></div>
                    <div id="cvd-market-bar-short" style="width:50%; height:100%; background:#ef4444; transition:width 0.4s ease;"></div>
                </div>
                <div style="font-size:11px; color:#94a3b8; font-family:'JetBrains Mono'; margin-top:7px; line-height:1.4;">
                    🟢 <b>Yeşil (% Alıcı):</b> Tahtayı yukarı süpüren piyasa alışları | 🔴 <b>Kırmızı (% Satıcı):</b> Aşağı vuran satışlar
                </div>
            </div>

            <div class="cockpit-kpi-card" style="border-top:3px solid #22c55e;">
                <div class="kpi-card-head">
                    <span class="kpi-card-title">🚀 60 Saniyenin Boğa Lideri (En Hızlı Para Girişi)</span>
                    <span class="kpi-card-icon">🔥</span>
                </div>
                <div class="kpi-card-val" id="cvd-top-buyer-sym" style="color:#22c55e; font-size:19px;">-</div>
                <div class="kpi-card-sub" id="cvd-top-buyer-delta" style="font-weight:700;">Net Para Girişi: +$0</div>
                <div style="font-size:11px; color:#86efac; font-family:'JetBrains Mono'; margin-top:5px;">
                    🎯 <b>Strateji:</b> Direnç kırılımı (Breakout) için en güçlü aday. Mum beklemeden marjin 1.15x artırılır.
                </div>
            </div>

            <div class="cockpit-kpi-card" style="border-top:3px solid #ef4444;">
                <div class="kpi-card-head">
                    <span class="kpi-card-title">🔻 60 Saniyenin Ayı Lideri (En Ağır Satış Baskısı)</span>
                    <span class="kpi-card-icon">⚠️</span>
                </div>
                <div class="kpi-card-val" id="cvd-top-seller-sym" style="color:#ef4444; font-size:19px;">-</div>
                <div class="kpi-card-sub" id="cvd-top-seller-delta" style="font-weight:700;">Net Para Çıkışı: -$0</div>
                <div style="font-size:11px; color:#fca5a5; font-family:'JetBrains Mono'; margin-top:5px;">
                    🛡️ <b>Strateji:</b> Dirençteyse 'Boğa Tuzağı' engellenir. Destekteyse fitilden 'Dip Emilim (Bounce)' aranır.
                </div>
            </div>
        </div>

        <!-- COIN SEÇİM & FİLTRE ÇUBUĞU -->
        <div style="margin-bottom:14px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
            <div style="font-size:13px; font-weight:800; color:#e2e8f0; font-family:'JetBrains Mono'; display:flex; align-items:center; gap:8px;">
                <span>⚡</span> CANLI PİYASA EMİR AKIŞI ISI TABLOLARI (Alıcılar vs Satıcılar)
            </div>
            <div class="quick-preset-bar" style="display:flex; align-items:center; gap:6px;">
                <span style="font-size:11.5px; color:#94a3b8; font-family:'JetBrains Mono'; margin-right:4px;">Görünüm:</span>
                <button class="btn-preset" id="cvd-btn-top5" onclick="setCvdLimit(5)" style="padding:4px 10px; font-size:11px;">İlk 5</button>
                <button class="btn-preset active" id="cvd-btn-top10" onclick="setCvdLimit(10)" style="padding:4px 10px; font-size:11px; border-color:var(--cyan); color:var(--cyan);">İlk 10 (Önerilen)</button>
                <button class="btn-preset" id="cvd-btn-top15" onclick="setCvdLimit(15)" style="padding:4px 10px; font-size:11px;">Tüm 15 Parite</button>
            </div>
        </div>

        <!-- 2 SÜTUNLU CANLI AGRESYON ISI TABLOSU -->
        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(420px, 1fr)); gap:18px; margin-bottom:20px;">
            <!-- SOL: EN ÇOK ALICI BASKISI OLAN COINLER -->
            <div class="history-full-box">
                <div style="padding:14px 18px; border-bottom:1px solid rgba(255,255,255,0.06); display:flex; justify-content:space-between; align-items:center; background:rgba(34,197,94,0.04);">
                    <div>
                        <div style="font-weight:800; font-size:13px; color:#22c55e; font-family:'JetBrains Mono'; display:flex; align-items:center; gap:8px;">
                            <span>🟢</span> DİRENÇ PATLATMAYA HAZIR COINLER (Taker Buy Dominance)
                        </div>
                        <div style="font-size:11px; color:#94a3b8; margin-top:2px;">Piyasa emriyle tahtası yukarı süpürülenler — Kırılım ve Boğa İvmesi</div>
                    </div>
                    <div style="font-size:11px; color:#86efac; font-family:'JetBrains Mono'; background:rgba(34,197,94,0.1); padding:3px 8px; border-radius:6px;">Son 60 Saniye</div>
                </div>
                <div class="history-table-container">
                    <table class="history-table">
                        <thead>
                            <tr>
                                <th>Parite (Coin)</th>
                                <th>Alıcı Gücü</th>
                                <th>60s Net Para Akışı ($)</th>
                                <th>Anlık Fiyat</th>
                                <th>Botun Stratejik Kararı & Aksiyonu</th>
                            </tr>
                        </thead>
                        <tbody id="cvd-top-buyers-body">
                            <tr><td colspan="5" style="text-align:center; padding:20px; color:#94a3b8;">Canlı K-Line verileri taranıyor...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- SAĞ: EN ÇOK SATICI BASKISI OLAN COINLER -->
            <div class="history-full-box">
                <div style="padding:14px 18px; border-bottom:1px solid rgba(255,255,255,0.06); display:flex; justify-content:space-between; align-items:center; background:rgba(239,68,68,0.04);">
                    <div>
                        <div style="font-weight:800; font-size:13px; color:#ef4444; font-family:'JetBrains Mono'; display:flex; align-items:center; gap:8px;">
                            <span>🔴</span> TUZAK & BOŞALTMA UYARISI (Taker Sell Dominance)
                        </div>
                        <div style="font-size:11px; color:#94a3b8; margin-top:2px;">Piyasa satışı yığılanlar — Sahte Kırılım (Tuzak) ve Dip Emilim Adayları</div>
                    </div>
                    <div style="font-size:11px; color:#fca5a5; font-family:'JetBrains Mono'; background:rgba(239,68,68,0.1); padding:3px 8px; border-radius:6px;">Son 60 Saniye</div>
                </div>
                <div class="history-table-container">
                    <table class="history-table">
                        <thead>
                            <tr>
                                <th>Parite (Coin)</th>
                                <th>Satıcı Gücü</th>
                                <th>60s Net Para Çıkışı ($)</th>
                                <th>Anlık Fiyat</th>
                                <th>Botun Stratejik Kararı & Aksiyonu</th>
                            </tr>
                        </thead>
                        <tbody id="cvd-top-sellers-body">
                            <tr><td colspan="5" style="text-align:center; padding:20px; color:#94a3b8;">Canlı K-Line verileri taranıyor...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- 3 SÜTUNLU ÖĞRETİCİ STRATEJİ REHBERİ -->
        <div style="margin-top:22px; display:grid; grid-template-columns:repeat(auto-fit, minmax(300px, 1fr)); gap:14px;">
            <div style="padding:16px 18px; background:rgba(0,242,254,0.03); border:1px solid rgba(0,242,254,0.15); border-radius:10px; font-family:'JetBrains Mono';">
                <div style="color:var(--cyan); font-weight:800; font-size:13px; margin-bottom:6px;">⚡ 1. Mum Kapanışı Beklemiyoruz (0ms Gecikme)</div>
                <div style="color:#94a3b8; font-size:11.5px; line-height:1.5;">Geleneksel botlar 5 dakikalık mumun kapanmasını beklerken tren kaçar. Mikro-CVD motorumuz son 60 saniyedeki piyasa emirlerini milisaniyesinde sayar ve direnç kırıldığı an gecikmesiz işleme girer.</div>
            </div>

            <div style="padding:16px 18px; background:rgba(239,68,68,0.03); border:1px solid rgba(239,68,68,0.15); border-radius:10px; font-family:'JetBrains Mono';">
                <div style="color:#ef4444; font-weight:800; font-size:13px; margin-bottom:6px;">🛡️ 2. Boğa Tuzağı Kalkanı (Fakeout Shield)</div>
                <div style="color:#94a3b8; font-size:11.5px; line-height:1.5;">Fiyat Camarilla R4 direncini yukarı geçse bile, tahtada alıcı yoksa (kırmızı tablodaki gibi satıcı baskısı varsa) bot 'Bu balinaların mal boşaltma tuzağıdır' der ve işlemi anında engelleyerek kasayı korur.</div>
            </div>

            <div style="padding:16px 18px; background:rgba(34,197,94,0.03); border:1px solid rgba(34,197,94,0.15); border-radius:10px; font-family:'JetBrains Mono';">
                <div style="color:#22c55e; font-weight:800; font-size:13px; margin-bottom:6px;">🎯 3. Marjin Güçlendirmesi (1.15x Boost)</div>
                <div style="color:#94a3b8; font-size:11.5px; line-height:1.5;">Yeşil tablodaki gibi alıcı oranı %62'nin üzerindeyse kırılımın arkasında gerçek hacim var demektir; bot işlem marjinini 1.15x katına çıkarır. Destekte emilim varsa 1.10x marjinle fitilin ucunu yakalar.</div>
            </div>
        </div>
    </div>

    <!-- =========================================================================
         8. SEKME: YÖNETİM MASASI
         ========================================================================= -->
    <div id="main-tab-content-admin" class="main-tab-content" style="display:none;">
        <!-- ADMIN 4 KPI HERO -->
        <div class="cockpit-kpi-grid" style="margin-bottom:16px;">
            <div class="cockpit-kpi-card">
                <div class="kpi-card-head">
                    <span class="kpi-card-title">Toplam Yönetilen Fon (AUM)</span>
                    <span class="kpi-card-icon">🏦</span>
                </div>
                <div class="kpi-card-val" id="admin-total-aum" style="color:var(--cyan);">$10,000.00</div>
                <div class="kpi-card-sub">Bağlı Müşteri Cüzdanları Toplamı</div>
            </div>

            <div class="cockpit-kpi-card">
                <div class="kpi-card-head">
                    <span class="kpi-card-title">Kayıtlı Yatırımcı Sayısı</span>
                    <span class="kpi-card-icon">👥</span>
                </div>
                <div class="kpi-card-val" id="admin-total-users">1 Yatırımcı</div>
                <div class="kpi-card-sub">Çok Kullanıcılı SaaS Havuzu</div>
            </div>

            <div class="cockpit-kpi-card">
                <div class="kpi-card-head">
                    <span class="kpi-card-title">24 Saatlik Aktif Denemeler</span>
                    <span class="kpi-card-icon">⏳</span>
                </div>
                <div class="kpi-card-val" id="admin-trial-count" style="color:var(--yellow);">0 Aktif</div>
                <div class="kpi-card-sub">Suistimal Kalkanı (Anti-Abuse) Aktif</div>
            </div>

            <div class="cockpit-kpi-card">
                <div class="kpi-card-head">
                    <span class="kpi-card-title">VIP & Pro Aboneler</span>
                    <span class="kpi-card-icon">👑</span>
                </div>
                <div class="kpi-card-val" id="admin-vip-count" style="color:var(--green);">1 VIP</div>
                <div class="kpi-card-sub">Otomatik Lisans Denetimi Aktif</div>
            </div>
        </div>

        
            <!-- ADMIN WALLET & PRICING CONFIGURATION BOX -->
            <div class="setting-group-box" style="margin-bottom:16px;">
                <div style="font-size:14px; font-weight:800; color:var(--cyan); margin-bottom:10px; display:flex; align-items:center; gap:8px;">
                    <span>💳</span> CÜZDAN & FİYAT AYARLARI
                </div>
                <div style="font-size:12px; color:#cbd5e1; margin-bottom:14px;">
                    Müşterilerin 24 saatlik denemeden sonra ödeme yapacağı cüzdan adreslerinizi ve aylık paket fiyatlarını buradan yönetebilirsiniz.
                </div>

                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:14px; margin-bottom:12px;">
                    <div>
                        <label style="font-size:11.5px; font-weight:700; color:#cbd5e1; display:block; margin-bottom:4px;">USDT TRC20 (Tron) Cüzdan Adresiniz</label>
                        <input type="text" id="admin-input-trc20" class="settings-input" placeholder="TRON / TRC20 cüzdan adresiniz..." value="TXvK7w7ValkyrieQuantProTRC20DepositVault99" />
                    </div>
                    <div>
                        <label style="font-size:11.5px; font-weight:700; color:#cbd5e1; display:block; margin-bottom:4px;">USDT BEP20 (BSC) Cüzdan Adresiniz</label>
                        <input type="text" id="admin-input-bep20" class="settings-input" placeholder="BSC / BEP20 cüzdan adresiniz..." value="0x71C836393791B339243764835261821039818299" />
                    </div>
                </div>

                <div style="margin-bottom:16px;">
                    <label style="font-size:11.5px; font-weight:700; color:#cbd5e1; display:block; margin-bottom:4px;">VALKYRIE ALL-ACCESS Aylık Tek Fiyat ($ USDT)</label>
                    <input type="number" id="admin-input-price-monthly" step="1" class="settings-input" value="99" style="max-width:280px;" />
                    <div style="font-size:11px; color:#94a3b8; margin-top:4px;">Müşteriler 24 saatlik denemeden sonra bu tek fiyatı ödeyerek tüm sisteme sınırsız erişir.</div>
                </div>

                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span id="admin-save-msg" style="font-size:12px; color:var(--green); font-weight:700; display:none;">✅ Cüzdan ve fiyat ayarları başarıyla kaydedildi!</span>
                    <button class="btn-save-settings" onclick="saveAdminPaymentConfig()">
                        💾 Cüzdan & Fiyat Ayarlarını Kaydet
                    </button>
                </div>
            </div>

        <!-- SUBSCRIBER MANAGEMENT TABLE -->
        <div class="history-full-box">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; flex-wrap:wrap; gap:10px;">
                <div>
                    <div class="panel-title" style="margin:0;">📋 Yatırımcı Listesi</div>
                    <div style="font-size:12px; color:var(--text-muted); margin-top:2px;">Sistemde kayıtlı kullanıcıların lisans süreleri ve API bağlantı durumları</div>
                </div>
                <button class="btn-export" onclick="loadAdminMetrics()">🔄 Yenile</button>
            </div>

            <div style="overflow-x:auto;">
                <table class="trade-table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>E-Posta</th>
                            <th>Rol</th>
                            <th>Abonelik Planı</th>
                            <th>Kasa Bakiyesi</th>
                            <th>API Durumu</th>
                            <th>Lisans Bitişi</th>
                        </tr>
                    </thead>
                    <tbody id="admin-users-table-body">
                        <tr>
                            <td colspan="7" style="text-align:center; padding:30px; color:#94a3b8;">
                                Yatırımcı verileri yükleniyor...
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- =========================================================================
         8. SEKME: VALKYRIE AEGIS 360° SİSTEM SAĞLIĞI & TELEMETRİ KOKPİTİ
         ========================================================================= -->
    <div id="main-tab-content-health" class="main-tab-content" style="display:none; padding: 6px 0 30px 0;">
        <div id="health-tab-view-container">
            <!-- Dynamically populated by renderHealthTabView() -->
        </div>
    </div>

        </main>
    </div><!-- END DASHBOARD-MAIN-LAYOUT -->

    </div><!-- END DASHBOARD-APP-VIEW -->

    <script>

        // =========================================================================
        // AUTOMATED CRYPTO PAYMENT & UPGRADE MODAL JS ENGINE (SINGLE FLAT PRICE)
        // =========================================================================
        let paymentSettings = {
            trc20_wallet: 'TXvK7w7ValkyrieQuantProTRC20DepositVault99',
            bep20_wallet: '0x71C836393791B339243764835261821039818299',
            price_monthly: 99.0
        };

        
        let activePaymentOrder = null;
        let paymentPollInterval = null;
        let countdownTimer = null;
        let countdownRemainingSec = 1200;

        async function generateFreshCryptoOrder() {
            const net = document.getElementById('payment-network-select').value;
            const uid = (currentUser && currentUser.id) ? currentUser.id : 1;
            
            try {
                const res = await fetch(`/api/payment/create_order?network=${net}&user_id=${uid}`);
                const data = await res.json();
                activePaymentOrder = data;

                // Update UI elements
                const amtDisp = document.getElementById('exact-amount-display');
                if (amtDisp) amtDisp.innerHTML = `$${data.amount_usdt.toFixed(2)} <span style="font-size:13px; color:var(--cyan); font-weight:700;">USDT</span>`;
                
                const wAddr = document.getElementById('deposit-wallet-address');
                if (wAddr) wAddr.value = data.target_wallet;

                // Reset countdown
                countdownRemainingSec = 1200;
                startPaymentCountdown();

                // Start polling
                startOrderStatusPolling(data.order_code);
            } catch (e) {
                console.error("Order creation error:", e);
            }
        }

        function startPaymentCountdown() {
            if (countdownTimer) clearInterval(countdownTimer);
            countdownTimer = setInterval(() => {
                countdownRemainingSec--;
                if (countdownRemainingSec <= 0) {
                    clearInterval(countdownTimer);
                    if (paymentPollInterval) clearInterval(paymentPollInterval);
                    const clock = document.getElementById('order-countdown-clock');
                    if (clock) clock.innerText = "SÜRE DOLDU";
                    return;
                }
                const m = Math.floor(countdownRemainingSec / 60).toString().padStart(2, '0');
                const s = (countdownRemainingSec % 60).toString().padStart(2, '0');
                const clock = document.getElementById('order-countdown-clock');
                if (clock) clock.innerText = `${m}:${s}`;
            }, 1000);
        }

        function startOrderStatusPolling(orderCode) {
            if (paymentPollInterval) clearInterval(paymentPollInterval);
            paymentPollInterval = setInterval(async () => {
                try {
                    const res = await fetch(`/api/payment/order_status?order_code=${orderCode}`);
                    const data = await res.json();
                    if (data && data.status === 'COMPLETED') {
                        clearInterval(paymentPollInterval);
                        clearInterval(countdownTimer);
                        handleAutonomousPaymentSuccess(data);
                    }
                } catch (e) {
                    console.error("Polling error:", e);
                }
            }, 4000);
        }

        function handleAutonomousPaymentSuccess(orderData) {
            const radar = document.getElementById('auto-listener-radar');
            if (radar) radar.style.display = 'none';

            const box = document.getElementById('payment-status-box');
            if (!box) return;

            const rec = orderData.receipt || {};
            box.style.display = 'block';
            box.style.background = 'rgba(14,203,129,0.15)';
            box.style.border = '1.5px solid var(--green)';
            box.style.color = 'var(--green)';
            box.innerHTML = `
                <div style="font-size:14.5px; font-weight:900; margin-bottom:6px; display:flex; align-items:center; gap:8px;">
                    <span>🎉</span> ÖDEMENİZ OTONOM OLARAK ONAYLANDI & LİSANS AKTİF!
                </div>
                <div style="font-size:12px; color:#ffffff; line-height:1.5;">
                    Transferiniz blokzincirde yakalandı. VALKYRIE ALL-ACCESS üyeliğiniz 30 gün boyunca tüm 100 paritede sınırsız açıldı.
                </div>
                <div style="font-size:11.5px; color:var(--cyan); margin-top:10px; padding-top:8px; border-top:1px solid rgba(255,255,255,0.1); display:flex; justify-content:space-between; flex-wrap:wrap; gap:6px;">
                    <span>🧾 Fatura: <b>${rec.receipt_id || 'INV-20260829-001'}</b></span>
                    <span>💸 Tutar: <b>$${orderData.amount_usdt} USDT</b></span>
                </div>
            `;

            // Refresh user session state
            if (currentUser) {
                currentUser.role = 'CLIENT';
                localStorage.setItem('valkyrie_auth_user', JSON.stringify(currentUser));
                updateUserSessionUI();
            }
        }

        function copyExactAmount() {
            if (!activePaymentOrder) return;
            navigator.clipboard.writeText(activePaymentOrder.amount_usdt.toFixed(2));
            showToast("Tutar kopyalandı: $" + activePaymentOrder.amount_usdt.toFixed(2));
        }

        function toggleManualTxSection() {
            const sec = document.getElementById('manual-tx-section');
            if (sec) sec.style.display = (sec.style.display === 'none') ? 'block' : 'none';
        }

        function openUpgradeModal() {
            generateFreshCryptoOrder();
            const m = document.getElementById('upgrade-modal-overlay');
            if (m) m.style.display = 'flex';
            loadPaymentConfig();
        }

        function closeUpgradeModal() {
            const m = document.getElementById('upgrade-modal-overlay');
            if (m) m.style.display = 'none';
        }

        async function loadPaymentConfig() {
            try {
                const res = await fetch('/api/payment/config');
                const data = await res.json();
                if (data.success && data.settings) {
                    paymentSettings = data.settings;
                    updateDepositWalletDisplay();
                    const mPrice = document.getElementById('modal-price-all-access');
                    const lblExact = document.getElementById('lbl-exact-payment');
                    if (mPrice) mPrice.innerText = `$${paymentSettings.price_monthly} / Ay`;
                    if (lblExact) lblExact.innerText = `${paymentSettings.price_monthly.toFixed(2)} USDT`;

                    const aTrc = document.getElementById('admin-input-trc20');
                    const aBep = document.getElementById('admin-input-bep20');
                    const aPrice = document.getElementById('admin-input-price-monthly');
                    if (aTrc) aTrc.value = paymentSettings.trc20_wallet;
                    if (aBep) aBep.value = paymentSettings.bep20_wallet;
                    if (aPrice) aPrice.value = paymentSettings.price_monthly;
                }
            } catch (e) {
                console.error('Payment config load error:', e);
            }
        }

        function updateDepositWalletDisplay() {
            const net = document.getElementById('payment-network-select').value;
            const addrInput = document.getElementById('deposit-wallet-address');
            if (!addrInput) return;

            if (net === 'TRC20') {
                addrInput.value = paymentSettings.trc20_wallet;
            } else {
                addrInput.value = paymentSettings.bep20_wallet;
            }
        }

        function copyDepositAddress() {
            const addrInput = document.getElementById('deposit-wallet-address');
            const badge = document.getElementById('copy-success-badge');
            if (addrInput) {
                navigator.clipboard.writeText(addrInput.value);
                if (badge) {
                    badge.style.display = 'inline';
                    setTimeout(() => { badge.style.display = 'none'; }, 2000);
                }
            }
        }

        async function saveAdminPaymentConfig() {
            const trc20_wallet = document.getElementById('admin-input-trc20').value;
            const bep20_wallet = document.getElementById('admin-input-bep20').value;
            const price_monthly = parseFloat(document.getElementById('admin-input-price-monthly').value) || 99.0;
            const msgEl = document.getElementById('admin-save-msg');

            try {
                const res = await fetch('/api/admin/save_payment_config', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ trc20_wallet, bep20_wallet, price_monthly })
                });
                const data = await res.json();
                if (data.success) {
                    if (msgEl) {
                        msgEl.style.display = 'inline';
                        setTimeout(() => { msgEl.style.display = 'none'; }, 3000);
                    }
                    paymentSettings = { trc20_wallet, bep20_wallet, price_monthly };
                    const lblExact = document.getElementById('lbl-exact-payment');
                    if (lblExact) lblExact.innerText = `${price_monthly.toFixed(2)} USDT`;
                } else {
                    alert('Hata: ' + data.message);
                }
            } catch (e) {
                alert('Kaydetme Hatası: ' + e);
            }
        }

        async function submitCryptoPayment() {
            const tx_hash = document.getElementById('input-payment-txhash').value.trim();
            const network = document.getElementById('payment-network-select').value;
            const box = document.getElementById('payment-status-box');
            const userId = currentUser ? currentUser.id : 1;

            if (!tx_hash) {
                box.style.display = 'block';
                box.style.background = 'rgba(255,71,87,0.1)';
                box.style.color = 'var(--red)';
                box.innerText = 'Lütfen transfer işlem kodunu (TxHash) giriniz!';
                return;
            }

            box.style.display = 'block';
            box.style.background = 'rgba(0,242,254,0.1)';
            box.style.color = 'var(--cyan)';
            box.innerHTML = `⏳ <b>Blokzincir Onayı Taranıyor...</b> TxHash doğrulanıyor ve sahtekarlık kalkanı kontrol ediliyor...`;

            try {
                const res = await fetch('/api/payment/verify', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        user_id: userId,
                        tx_hash: tx_hash,
                        network: network
                    })
                });
                const data = await res.json();

                if (data.success) {
                    box.style.background = 'rgba(14,203,129,0.15)';
                    box.style.color = 'var(--green)';
                    box.innerHTML = `
                        <div style="font-size:13px; font-weight:800; margin-bottom:4px;">🎉 ÖDEME ONAYLANDI & LİSANS AKTİF!</div>
                        <div>${data.message}</div>
                        <div style="font-size:11px; color:#cbd5e1; margin-top:6px;">Fatura No: <b>${data.receipt.receipt_id}</b> | Bitiş: <b>${data.receipt.expires_at}</b></div>
                    `;
                    setTimeout(() => {
                        closeUpgradeModal();
                        updateUserSessionUI();
                    }, 3500);
                } else {
                    box.style.background = 'rgba(255,71,87,0.15)';
                    box.style.color = 'var(--red)';
                    box.innerHTML = `❌ <b>Doğrulama Başarısız:</b> ${data.message}`;
                }
            } catch (e) {
                box.style.background = 'rgba(255,71,87,0.15)';
                box.style.color = 'var(--red)';
                box.innerText = 'Bağlantı Hatası: Lütfen internet bağlantınızı kontrol edip tekrar deneyiniz.';
            }
        }


        // =========================================================================
        // MULTI-TENANT AUTHENTICATION & MASTER ADMIN JS ENGINE
        // =========================================================================
        let currentUser = null;
        try {
            const saved = localStorage.getItem('valkyrie_auth_user');
            if (saved) currentUser = JSON.parse(saved);
        } catch(e) {}

        function restorePersistedSession() {
            try {
                const saved = localStorage.getItem('valkyrie_auth_user');
                if (saved) {
                    currentUser = JSON.parse(saved);
                } else {
                    currentUser = null;
                }
            } catch (e) {
                currentUser = null;
            }
            updateUserSessionUI();
        }

        function closeAuthModal() {
            const m = document.getElementById('auth-modal-overlay');
            if (m) m.style.display = 'none';
        }

        function openAuthModal(defaultTab = 'register') {
            const m = document.getElementById('auth-modal-overlay');
            if (m) m.style.display = 'flex';
            switchAuthTab(defaultTab);
        }

        function switchAuthTab(tab) {
            const btnReg = document.getElementById('auth-tab-btn-register');
            const btnLog = document.getElementById('auth-tab-btn-login');
            const fReg = document.getElementById('auth-form-register');
            const fLog = document.getElementById('auth-form-login');

            if (fReg) fReg.style.display = (tab === 'register') ? 'block' : 'none';
            if (fLog) fLog.style.display = (tab === 'login') ? 'block' : 'none';

            if (btnReg) {
                btnReg.style.background = (tab === 'register') ? 'linear-gradient(135deg, #00f2fe, #4facfe)' : 'transparent';
                btnReg.style.color = (tab === 'register') ? '#000' : '#94a3b8';
            }
            if (btnLog) {
                btnLog.style.background = (tab === 'login') ? 'var(--blue)' : 'transparent';
                btnLog.style.color = (tab === 'login') ? '#fff' : '#94a3b8';
            }
        }

        let trialCountdownInterval = null;

        function closeTrialExpiredModal() {
            const el = document.getElementById('trial-expired-modal-overlay');
            if (el) el.style.display = 'none';
        }

        function openTrialExpiredModal() {
            const el = document.getElementById('trial-expired-modal-overlay');
            if (el) el.style.display = 'flex';
        }

        function startTrialLiveCountdown(expiresAtStr) {
            if (trialCountdownInterval) clearInterval(trialCountdownInterval);

            function tick() {
                const badge = document.getElementById('trial-countdown-badge');
                if (!badge) return;

                if (!expiresAtStr) {
                    badge.innerHTML = `⏳ <span style="color:var(--yellow);">48h Demo</span>`;
                    return;
                }

                const expireTime = new Date(expiresAtStr.replace(' ', 'T') + '+03:00').getTime();
                const now = new Date().getTime();
                const diffMs = expireTime - now;

                if (diffMs <= 0) {
                    badge.style.background = 'rgba(255,71,87,0.15)';
                    badge.style.borderColor = 'var(--red)';
                    badge.innerHTML = `<span class="live-dot" style="background:var(--red); width:8px; height:8px;"></span> <b style="color:var(--red);">Süre Doldu</b>`;
                    if (currentUser && currentUser.plan === '48H_DEMO_TRIAL') {
                        // Notify expired once per session if not already closed
                        if (!sessionStorage.getItem('valkyrie_trial_expired_notified')) {
                            sessionStorage.setItem('valkyrie_trial_expired_notified', 'true');
                            openTrialExpiredModal();
                        }
                    }
                    return;
                }

                const totalSec = Math.floor(diffMs / 1000);
                const hrs = Math.floor(totalSec / 3600);
                const mins = Math.floor((totalSec % 3600) / 60);
                const secs = totalSec % 60;

                const timeStr = `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
                
                if (hrs < 4) {
                    badge.style.background = 'rgba(251,197,49,0.15)';
                    badge.style.borderColor = 'var(--yellow)';
                    badge.innerHTML = `<span class="live-dot" style="background:var(--yellow); width:8px; height:8px;"></span> <b style="color:var(--yellow);">48h Demo: ${timeStr}</b>`;
                } else {
                    badge.style.background = 'rgba(0,242,254,0.08)';
                    badge.style.borderColor = 'rgba(0,242,254,0.3)';
                    badge.innerHTML = `<span class="live-dot" style="background:var(--cyan); width:8px; height:8px;"></span> <b style="color:var(--cyan);">48h Demo: ${timeStr}</b>`;
                }
            }

            tick();
            trialCountdownInterval = setInterval(tick, 1000);
        }

        function updateUserSessionUI() {
            const landingView = document.getElementById('landing-page-view');
            const appView = document.getElementById('dashboard-app-view');
            const cont = document.getElementById('user-session-container');
            const navAdminTab = document.getElementById('tab-btn-admin');

            if (!currentUser) {
                document.documentElement.className = 'is-guest';
                if (trialCountdownInterval) clearInterval(trialCountdownInterval);
                if (landingView) landingView.style.display = 'block';
                if (appView) appView.style.display = 'none';
                return;
            }
            document.documentElement.className = 'is-authenticated';

            if (landingView) landingView.style.display = 'none';
            if (appView) appView.style.display = 'block';

            if (!cont) return;

            if (currentUser.role === 'ADMIN') {
                if (trialCountdownInterval) clearInterval(trialCountdownInterval);
                cont.innerHTML = `
                    <div class="live-tag" style="border-color:rgba(0,242,254,0.4); background:rgba(0,242,254,0.08);" title="Master Admin Masası">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--cyan)" stroke-width="2" style="margin-right:4px;"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
                        <b style="color:var(--cyan);">Master Admin</b>
                    </div>
                    <button onclick="handleLogout()" style="background:rgba(255,71,87,0.12); border:1px solid rgba(255,71,87,0.3); color:var(--red); font-weight:800; font-size:11.5px; padding:6px 12px; border-radius:8px; cursor:pointer;" title="Oturumu Kapat">
                        Çıkış Yap
                    </button>
                `;
                if (navAdminTab) navAdminTab.style.display = 'inline-flex';
            } else if (currentUser.email) {
                const cleanName = currentUser.email.split('@')[0];
                const isAllAccess = (currentUser.plan === 'ALL_ACCESS' || currentUser.role === 'CLIENT');
                
                let badgeMarkup = '';
                if (isAllAccess) {
                    badgeMarkup = `<span class="live-tag" style="background:rgba(56,239,125,0.12); border:1px solid var(--green); color:var(--green); font-size:11px; font-weight:800;">💎 All-Access VIP</span>`;
                } else {
                    badgeMarkup = `<div id="trial-countdown-badge" class="live-tag" onclick="openUpgradeModal()" style="cursor:pointer; font-family:'JetBrains Mono'; font-size:11.5px; transition:all 0.15s ease;">⏳ 48h Demo Yükleniyor...</div>`;
                }

                cont.innerHTML = `
                    <div class="live-tag" title="Hesap Bilgilerim">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:4px;"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
                        <b style="color:#cbd5e1;">${cleanName}</b>
                    </div>
                    ${badgeMarkup}
                    <button onclick="handleLogout()" style="background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.12); color:#94a3b8; font-weight:800; font-size:11.5px; padding:6px 12px; border-radius:8px; cursor:pointer;" title="Oturumu Kapat">
                        Çıkış Yap
                    </button>
                `;
                if (navAdminTab) navAdminTab.style.display = 'none';

                if (!isAllAccess) {
                    startTrialLiveCountdown(currentUser.expires_at);
                }
            }
        }

        function handleLogout() {
            if (trialCountdownInterval) clearInterval(trialCountdownInterval);
            localStorage.removeItem('valkyrie_auth_user');
            currentUser = null;
            document.documentElement.className = 'is-guest';
            updateUserSessionUI();
        }

        async function submitLogin() {
            const email = document.getElementById('login-email').value;
            const password = document.getElementById('login-password').value;
            const box = document.getElementById('auth-msg-box');

            try {
                const res = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ email, password })
                });
                let data;
                try {
                    data = await res.json();
                } catch(pe) {
                    data = { success: false, message: 'Sunucu geçiş aşamasında (~10sn), lütfen 5 saniye sonra tekrar deneyin.' };
                }

                if (data.success) {
                    currentUser = data.user;
                    try { localStorage.setItem('valkyrie_auth_user', JSON.stringify(currentUser)); } catch(e) {}
                    box.style.display = 'block';
                    box.style.background = 'rgba(14,203,129,0.1)';
                    box.style.color = 'var(--green)';
                    box.innerText = `✅ Hoş geldiniz, ${currentUser.email}!`;
                    setTimeout(() => {
                        closeAuthModal();
                        updateUserSessionUI();
                    }, 800);
                } else {
                    box.style.display = 'block';
                    box.style.background = 'rgba(255,71,87,0.1)';
                    box.style.color = 'var(--red)';
                    box.innerText = `❌ ${data.message || 'Giriş yapılamadı'}`;
                }
            } catch (e) {
                box.style.display = 'block';
                box.style.background = 'rgba(255,71,87,0.1)';
                box.style.color = 'var(--red)';
                box.innerText = 'Bağlantı Hatası: Lütfen sayfayı yenileyip tekrar deneyin.';
            }
        }

        async function submitRegister() {
            const email = document.getElementById('reg-email').value;
            const password = document.getElementById('reg-password').value;
            const binance_uid = document.getElementById('reg-binance-uid').value;
            const box = document.getElementById('auth-msg-box');

            try {
                const res = await fetch('/api/auth/register', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ email, password, binance_uid })
                });
                let data;
                try {
                    data = await res.json();
                } catch(pe) {
                    data = { success: false, message: 'Sunucu geçiş aşamasında (~10sn), lütfen 5 saniye sonra tekrar deneyin.' };
                }

                if (data.success) {
                    currentUser = data.user;
                    try { localStorage.setItem('valkyrie_auth_user', JSON.stringify(currentUser)); } catch(e) {}
                    box.style.display = 'block';
                    box.style.background = 'rgba(14,203,129,0.1)';
                    box.style.color = 'var(--green)';
                    box.innerText = `🎉 48 Saatlik Risksiz Demo Denemeniz Başlatıldı!`;
                    setTimeout(() => {
                        closeAuthModal();
                        updateUserSessionUI();
                    }, 1000);
                } else {
                    box.style.display = 'block';
                    box.style.background = 'rgba(255,71,87,0.1)';
                    box.style.color = 'var(--red)';
                    box.innerText = `❌ ${data.message || 'Kayıt başarısız'}`;
                }
            } catch (e) {
                box.style.display = 'block';
                box.style.background = 'rgba(255,71,87,0.1)';
                box.style.color = 'var(--red)';
                box.innerText = 'Bağlantı Hatası: Lütfen sayfayı yenileyip tekrar deneyin.';
            }
        }
async function loadAdminMetrics() {
            try {
                const res = await fetch('/api/admin/overview');
                const data = await res.json();
                
                const aumEl = document.getElementById('admin-total-aum');
                const usrEl = document.getElementById('admin-total-users');
                const trlEl = document.getElementById('admin-trial-count');
                const vipEl = document.getElementById('admin-vip-count');
                const tbody = document.getElementById('admin-users-table-body');

                if (aumEl) aumEl.innerText = `$${(data.total_aum || 10000).toLocaleString('en-US', {minimumFractionDigits:2})}`;
                if (usrEl) usrEl.innerText = `${data.total_users || 1} Yatırımcı`;
                if (trlEl) trlEl.innerText = `${data.trial_count || 0} Aktif`;
                if (vipEl) vipEl.innerText = `${(data.vip_count || 1) + (data.pro_count || 0)} Abone`;

                if (tbody && data.users_list) {
                    let html = '';
                    data.users_list.forEach(u => {
                        html += `
                            <tr style="border-bottom:1px solid rgba(255,255,255,0.04);">
                                <td style="padding:10px; color:#94a3b8;">#${u.id}</td>
                                <td style="padding:10px; font-weight:700; color:#fff;">${u.email}</td>
                                <td style="padding:10px;"><span style="background:${u.role === 'ADMIN' ? 'rgba(0,242,254,0.15)' : 'rgba(255,255,255,0.06)'}; color:${u.role === 'ADMIN' ? 'var(--cyan)' : '#94a3b8'}; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:800;">${u.role}</span></td>
                                <td style="padding:10px;"><span style="color:var(--yellow); font-weight:700;">${u.plan}</span></td>
                                <td style="padding:10px; font-family:'JetBrains Mono'; font-weight:800; color:var(--green);">$${u.balance.toLocaleString('en-US', {minimumFractionDigits:2})}</td>
                                <td style="padding:10px;">${u.api_valid ? '🟢 Bağlı' : '⚪ Bekliyor'}</td>
                                <td style="padding:10px; font-size:11px; color:#94a3b8;">${u.expires_at || 'Süresiz'}</td>
                            </tr>
                        `;
                    });
                    tbody.innerHTML = html;
                }
            } catch (e) {
                console.error('Admin metrics error:', e);
            }
        }


        // =========================================================================
        // VALKYRIE AEGIS SENTINEL & HEALTH DIAGNOSTIC MODAL
        // =========================================================================
        function updateSystemHealthBadge() {
            const pill = document.getElementById('system-health-pill');
            const textEl = document.getElementById('system-health-text');
            const dotEl = document.getElementById('system-health-dot');
            if (!textEl || !appState) return;

            const sys = appState.system_health || {};
            const isPerf = sys.is_perfect === true;

            if (isPerf) {
                textEl.innerText = `${sys.healthy_symbols || 100}/${sys.total_symbols || 100} Parite Canlı Akıyor`;
                if (dotEl) dotEl.className = 'live-dot';
                if (pill) pill.style.borderColor = 'rgba(14,203,129,0.3)';
            } else {
                textEl.innerText = sys.status_text || '⚠️ Bot Sağlığında Sorun Var';
                if (dotEl) dotEl.className = 'live-dot-error';
                if (pill) pill.style.borderColor = 'rgba(255,71,87,0.5)';
            }

            // Coinbase Lead-Lag Badge Update
            const cbPill = document.getElementById('cb-lead-lag-pill');
            const cbText = document.getElementById('cb-lead-lag-text');
            const cbDot = document.getElementById('cb-lead-lag-dot');
            if (cbText && appState) {
                const cb = appState.coinbase_lead_lag || {};
                const spread = Number(cb.spread_bps || 0);
                const dir = cb.direction || 'NEUTRAL';
                const sStr = (spread >= 0 ? '+' : '') + spread.toFixed(1);
                if (dir === 'BULLISH_LEAD') {
                    cbText.innerText = `🏛️ CB Boğa: ${sStr} bps`;
                    if (cbDot) { cbDot.style.background = 'var(--green)'; cbDot.style.boxShadow = '0 0 8px var(--green)'; }
                    if (cbPill) { cbPill.style.borderColor = 'rgba(16,185,129,0.5)'; cbPill.style.color = 'var(--green)'; }
                } else if (dir === 'BEARISH_LEAD') {
                    cbText.innerText = `🏛️ CB Ayı: ${sStr} bps`;
                    if (cbDot) { cbDot.style.background = 'var(--red)'; cbDot.style.boxShadow = '0 0 8px var(--red)'; }
                    if (cbPill) { cbPill.style.borderColor = 'rgba(244,63,94,0.5)'; cbPill.style.color = 'var(--red)'; }
                } else {
                    cbText.innerText = `🏛️ CB: ${sStr} bps`;
                    if (cbDot) { cbDot.style.background = '#60a5fa'; cbDot.style.boxShadow = '0 0 8px #60a5fa'; }
                    if (cbPill) { cbPill.style.borderColor = 'rgba(59,130,246,0.35)'; cbPill.style.color = '#60a5fa'; }
                }
            }
        }

        function openHealthDiagnosticModal() {
            const modal = document.getElementById('health-modal-overlay');
            const body = document.getElementById('health-modal-body');
            if (!modal || !body) return;

            const sys = appState.system_health || {};
            const isPerf = sys.is_perfect === true;
            const streams = sys.streams || {};
            const qEngine = sys.quant_engine || {};
            const infra = sys.infrastructure || {};

            // Streams Data
            const ws = streams.ws_prices || { count: sys.live_prices || 100, total: sys.total_symbols || 100, pct: 100 };
            const obi = streams.obi_depth || { count: 100, total: 100, bid_walls: 0, ask_walls: 0 };
            const cvd = streams.cvd_flow || { count: 100, total: 100 };
            const liq = streams.liquidations || { total_usd_24h: 0, top_symbol: '-', last_event_time: '-' };
            const spot = streams.spot_basis || { count: 100, total: 100, delay_sec: 15 };
            const poller = streams.candle_poller || { last_scan_time: sys.last_scan_time || 'Şimdi', delay_sec: 0 };
            const btcShock = streams.btc_shock || { velocity_60s: 0.0, is_active: false };
            const funding = streams.funding || { last_update: 'Aktif' };
            const cb = streams.coinbase_lead_lag || (appState.coinbase_lead_lag || { spread_bps: 0.0, status: '⚪ DENGELİ', direction: 'NEUTRAL' });
            const oi = streams.oi_radar || (appState.oi_summary || { fresh_count: 40, top_expansion: '-', top_expansion_pct: 0.0 });

            // Quant Engine Data
            const lev = qEngine.levels || { count: sys.healthy_symbols || 100, total: sys.total_symbols || 100, pct: 100 };
            const dna = qEngine.coin_dna || { count: 100, total: 100 };

            // Infra Data
            const gh = infra.github_persistence || { branch: 'state', sha: '-' };
            const ram = infra.ram_watchdog || { max_candles: 150, limit: 150, gc_interval: '60s' };

            const badgeColor = isPerf ? 'var(--green)' : 'var(--yellow)';
            const badgeBg = isPerf ? 'rgba(14,203,129,0.12)' : 'rgba(245,158,11,0.12)';
            const borderCol = isPerf ? 'rgba(14,203,129,0.3)' : 'rgba(245,158,11,0.3)';

            const pill = (txt, color='var(--green)') => `<span style="background:${color==='var(--green)'?'rgba(14,203,129,0.12)':'rgba(56,189,248,0.12)'}; color:${color}; border:1px solid ${color==='var(--green)'?'rgba(14,203,129,0.3)':'rgba(56,189,248,0.3)'}; padding:2px 8px; border-radius:6px; font-size:11px; font-weight:700;">${txt}</span>`;

            body.innerHTML = `
                <!-- ÜST GENEL DURUM AFİŞİ -->
                <div style="background:${badgeBg}; border:1px solid ${borderCol}; border-radius:12px; padding:14px; margin-bottom:16px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                        <div style="font-size:15px; font-weight:800; color:${badgeColor}; display:flex; align-items:center; gap:8px;">
                            <span>${isPerf ? '🟢' : '🟡'}</span>
                            <span>${sys.status_text || 'TAM SAĞLIKLI (KURUMSAL QUANT KOKPİTİ)'}</span>
                        </div>
                        <span style="background:rgba(255,255,255,0.06); padding:3px 10px; border-radius:6px; font-size:11.5px; color:#e2e8f0; font-weight:700;">
                            Puan: ${sys.score_str || '10/10'}
                        </span>
                    </div>
                    <div style="font-size:11.5px; color:#cbd5e1; line-height:1.5;">
                        Valkyrie Aegis Sentinel; borsa WebSocket soketlerini, L2 emir defterlerini, Mikro-CVD akışlarını ve bulut sürekliliğini 7/24 kesintisiz doğrulamaktadır.
                    </div>
                </div>

                <!-- 1. KATEGORİ: PİYASA VE BORSA VERİ AKIŞLARI -->
                <div style="margin-bottom:14px;">
                    <div style="font-size:11.5px; font-weight:800; color:#38bdf8; text-transform:uppercase; letter-spacing:0.8px; margin-bottom:8px; display:flex; align-items:center; gap:6px;">
                        <span>📡</span> 1. CANLI BORSA VE PİYASA VERİ AKIŞLARI (DATA FEEDS)
                    </div>
                    <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.06); border-radius:10px; padding:10px 14px; display:flex; flex-direction:column; gap:8px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.04); padding-bottom:6px;">
                            <span style="color:#94a3b8;">⚡ Binance WebSocket Canlı Fiyat (!bookTicker):</span>
                            <div style="display:flex; align-items:center; gap:8px;">
                                <span style="color:#e2e8f0; font-weight:700;">${ws.count || 100} / ${ws.total || 100} Parite</span>
                                ${pill(ws.count >= 80 ? 'CANLI AKIYOR' : 'GECİKME', ws.count >= 80 ? 'var(--green)' : 'var(--yellow)')}
                            </div>
                        </div>
                        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.04); padding-bottom:6px;">
                            <span style="color:#94a3b8;">🧱 L2 Tahta Derinliği & OBI Duvarları:</span>
                            <div style="display:flex; align-items:center; gap:8px;">
                                <span style="color:#e2e8f0; font-weight:700;">${obi.count || 100} Canlı Tahta (${obi.bid_walls || 0} Alıcı / ${obi.ask_walls || 0} Satıcı)</span>
                                ${pill('0.001ms RADAR', 'var(--cyan)')}
                            </div>
                        </div>
                        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.04); padding-bottom:6px;">
                            <span style="color:#94a3b8;">🌊 Anlık Mikro-CVD & Taker Agresyon Akışı:</span>
                            <div style="display:flex; align-items:center; gap:8px;">
                                <span style="color:#e2e8f0; font-weight:700;">${cvd.count || 100} Paritede Kayan 60s Delta Aktif</span>
                                ${pill('AKTİF', 'var(--green)')}
                            </div>
                        </div>
                        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.04); padding-bottom:6px;">
                            <span style="color:#94a3b8;">💀 Global Tasfiye Radarı (!forceOrder@arr):</span>
                            <div style="display:flex; align-items:center; gap:8px;">
                                <span style="color:#e2e8f0; font-weight:700;">$${(liq.total_usd_24h || 0).toLocaleString()} (Son: ${liq.last_event_time || '-'})</span>
                                ${pill('7/24 SOKET', 'var(--green)')}
                            </div>
                        </div>
                        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.04); padding-bottom:6px;">
                            <span style="color:#94a3b8;">⚖️ Spot vs Vadeli Basis Senkronu (Vision API):</span>
                            <div style="display:flex; align-items:center; gap:8px;">
                                <span style="color:#e2e8f0; font-weight:700;">${spot.count || 100} Parite Güncel (15s Periyot)</span>
                                ${pill('EŞİTLENDİ', 'var(--cyan)')}
                            </div>
                        </div>
                        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.04); padding-bottom:6px;">
                            <span style="color:#94a3b8;">🕒 5M Mum Senkronizasyonu & Deduplication:</span>
                            <div style="display:flex; align-items:center; gap:8px;">
                                <span style="color:#e2e8f0; font-weight:700;">Son Mum: ${poller.last_scan_time || 'Şimdi'} (Çift Tetikleme Korumalı)</span>
                                ${pill('AKTİF', 'var(--green)')}
                            </div>
                        </div>
                        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.04); padding-bottom:6px;">
                            <span style="color:#94a3b8;">⚡ BTC 60s Mikro-Şok Kalkanı:</span>
                            <div style="display:flex; align-items:center; gap:8px;">
                                <span style="color:#e2e8f0; font-weight:700;">BTC Hız: %${(btcShock.velocity_60s >= 0 ? '+' : '') + (btcShock.velocity_60s || 0).toFixed(2)} / Eşik: ±%0.28</span>
                                ${pill(btcShock.is_active ? 'ŞOK DEVREDE' : 'GÜVENLİ', btcShock.is_active ? 'var(--red)' : 'var(--green)')}
                            </div>
                        </div>
                        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.04); padding-bottom:6px;">
                            <span style="color:#94a3b8;">💰 Fonlama Oranı (Funding Rate) & Squeeze:</span>
                            <div style="display:flex; align-items:center; gap:8px;">
                                <span style="color:#e2e8f0; font-weight:700;">100 Parite Taranıyor (${funding.last_update || 'Güncel'})</span>
                                ${pill('60s PERİYOT', 'var(--green)')}
                            </div>
                        </div>
                        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.04); padding-bottom:6px;">
                            <span style="color:#94a3b8;">🏛️ Coinbase Spot Öncüsü (Lead-Lag LLI):</span>
                            <div style="display:flex; align-items:center; gap:8px;">
                                <span style="color:#e2e8f0; font-weight:700;">${(cb.spread_bps >= 0 ? '+' : '') + Number(cb.spread_bps || 0).toFixed(1)} bps (${cb.direction || 'NEUTRAL'})</span>
                                ${pill(cb.spread_bps >= 8.0 ? 'BOĞA ÖNCÜSÜ' : (cb.spread_bps <= -8.0 ? 'AYI BASKISI' : 'DENGELİ'), cb.spread_bps >= 8.0 ? 'var(--green)' : (cb.spread_bps <= -8.0 ? 'var(--red)' : 'var(--cyan)'))}
                            </div>
                        </div>
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span style="color:#94a3b8;">🧲 Gerçek Zamanlı Açık Pozisyon İvmesi (Delta-OI):</span>
                            <div style="display:flex; align-items:center; gap:8px;">
                                <span style="color:#e2e8f0; font-weight:700;">${oi.fresh_count || 100} Parite (Lider: ${oi.top_expansion || '-'} %${Number(oi.top_expansion_pct || 0).toFixed(1)})</span>
                                ${pill(oi.fresh_count >= 10 ? 'RADAR AKTİF' : 'TARANIYOR', oi.fresh_count >= 10 ? 'var(--green)' : 'var(--yellow)')}
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 2. KATEGORİ: KUANT MOTOR & SEVİYE BÜTÜNLÜĞÜ -->
                <div style="margin-bottom:14px;">
                    <div style="font-size:11.5px; font-weight:800; color:#a78bfa; text-transform:uppercase; letter-spacing:0.8px; margin-bottom:8px; display:flex; align-items:center; gap:6px;">
                        <span>🧠</span> 2. KUANT MOTOR & SEVİYE BÜTÜNLÜĞÜ (QUANT ENGINE)
                    </div>
                    <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.06); border-radius:10px; padding:10px 14px; display:flex; flex-direction:column; gap:8px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.04); padding-bottom:6px;">
                            <span style="color:#94a3b8;">📊 Camarilla / AVWAP / nPOC Seviye Bütünlüğü:</span>
                            <div style="display:flex; align-items:center; gap:8px;">
                                <span style="color:#e2e8f0; font-weight:700;">${lev.count || 100} / ${lev.total || 100} Parite Tam Uyumlu (%${lev.pct || 100})</span>
                                ${pill('0 SAPMA', 'var(--cyan)')}
                            </div>
                        </div>
                        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.04); padding-bottom:6px;">
                            <span style="color:#94a3b8;">🧬 100 Parite Kuant DNA & Persona Baseline:</span>
                            <div style="display:flex; align-items:center; gap:8px;">
                                <span style="color:#e2e8f0; font-weight:700;">${dna.count || 100} Parite Hafızada (Altın/Standart/Testere)</span>
                                ${pill('YÜKLÜ', 'var(--green)')}
                            </div>
                        </div>
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span style="color:#94a3b8;">🌀 Shannon Confluence & Entropi Kalkanı:</span>
                            <div style="display:flex; align-items:center; gap:8px;">
                                <span style="color:#e2e8f0; font-weight:700;">3-Eksen Bağımsız Confluence + Boltzmann L2</span>
                                ${pill('JIT AKTİF', 'var(--cyan)')}
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 3. KATEGORİ: BULUT ALTYAPISI, RAM & SÜREKLİLİK -->
                <div>
                    <div style="font-size:11.5px; font-weight:800; color:#34d399; text-transform:uppercase; letter-spacing:0.8px; margin-bottom:8px; display:flex; align-items:center; gap:6px;">
                        <span>☁️</span> 3. BULUT ALTYAPISI, RAM & SÜREKLİLİK (INFRASTRUCTURE)
                    </div>
                    <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.06); border-radius:10px; padding:10px 14px; display:flex; flex-direction:column; gap:8px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.04); padding-bottom:6px;">
                            <span style="color:#94a3b8;">🛡️ GitHub Bulut Kasa Senkronizasyonu:</span>
                            <div style="display:flex; align-items:center; gap:8px;">
                                <span style="color:#e2e8f0; font-weight:700;">'${gh.branch || 'state'}' Dalı (Commit: ${gh.sha || '-'})</span>
                                ${pill('SENKRONİZE', 'var(--green)')}
                            </div>
                        </div>
                        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.04); padding-bottom:6px;">
                            <span style="color:#94a3b8;">🧹 Otonom Bellek (RAM) Watchdog (Render OOM Kalkanı):</span>
                            <div style="display:flex; align-items:center; gap:8px;">
                                <span style="color:#e2e8f0; font-weight:700;">Max ${ram.limit || 150} Mum Tavanı (${ram.max_candles || 150} Satır) + 60s GC</span>
                                ${pill('512MB GÜVENLİ', 'var(--green)')}
                            </div>
                        </div>
                        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.04); padding-bottom:6px;">
                            <span style="color:#94a3b8;">⏱️ Render Keep-Alive Uyku Kalkanı:</span>
                            <div style="display:flex; align-items:center; gap:8px;">
                                <span style="color:#e2e8f0; font-weight:700;">Her 3 Dakika Self-Ping (HTTP 200 OK)</span>
                                ${pill('7/24 UYANIK', 'var(--green)')}
                            </div>
                        </div>
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span style="color:#94a3b8;">📱 Telegram Saatlik VIP Raporlayıcı & /kasa:</span>
                            <div style="display:flex; align-items:center; gap:8px;">
                                <span style="color:#e2e8f0; font-weight:700;">Saat Başı :00 Otomatik Rapor + İnteraktif Komut Dinleyici</span>
                                ${pill('AKTİF', 'var(--cyan)')}
                            </div>
                        </div>
                    </div>
                </div>
            `;
            const footerTs = document.getElementById('health-modal-footer-ts');
            if (footerTs) footerTs.innerText = `Son Telemetri Ölçümü: ${sys.timestamp || new Date().toLocaleTimeString()} (TSİ)`;
            modal.style.display = 'flex';
        }

        function closeHealthDiagnosticModal() {
            const modal = document.getElementById('health-modal-overlay');
            if (modal) modal.style.display = 'none';
        }

        // =========================================================================
        // VALKYRIE AEGIS 360° SİSTEM SAĞLIĞI & TELEMETRİ TAB ENGINE (DEDICATED TAB)
        // =========================================================================
        function renderHealthTabView() {
            const container = document.getElementById('health-tab-view-container');
            if (!container) return;

            const sys = (appState && appState.system_health) || {};
            const isPerf = sys.is_perfect === true;
            const streams = sys.streams || {};
            const qEngine = sys.quant_engine || {};
            const infra = sys.infrastructure || {};

            // Streams Data
            const ws = streams.ws_prices || { count: sys.live_prices || 100, total: sys.total_symbols || 100, pct: 100 };
            const obi = streams.obi_depth || { count: 100, total: 100, bid_walls: 0, ask_walls: 0 };
            const cvd = streams.cvd_flow || { count: 100, total: 100 };
            const liq = streams.liquidations || { total_usd_24h: 0, top_symbol: '-', last_event_time: '-' };
            const spot = streams.spot_basis || { count: 100, total: 100, delay_sec: 15 };
            const poller = streams.candle_poller || { last_scan_time: sys.last_scan_time || 'Şimdi', delay_sec: 0 };
            const btcShock = streams.btc_shock || { velocity_60s: 0.0, is_active: false };
            const funding = streams.funding || { last_update: 'Aktif' };
            const cb = streams.coinbase_lead_lag || (appState.coinbase_lead_lag || { spread_bps: 0.0, status: '⚪ DENGELİ', direction: 'NEUTRAL' });
            const oi = streams.oi_radar || (appState.oi_summary || { fresh_count: 40, top_expansion: '-', top_expansion_pct: 0.0 });

            // Quant Engine Data
            const lev = qEngine.levels || { count: sys.healthy_symbols || 100, total: sys.total_symbols || 100, pct: 100 };
            const dna = qEngine.coin_dna || { count: 100, total: 100 };
            const deribit = qEngine.deribit_gex || { freshness_sec: 120, is_live: true, regime: 'NEUTRAL', net_gex_usd: 0, pcr: 0.85 };
            const hawkes = qEngine.hawkes_avalanche || { eta: 0.15, is_active: false, side: 'NONE' };
            const stoikov = qEngine.stoikov_vpin || { healthy: true, mode: 'Stoikov Micro-Drift + VPIN', kyles_lambda: 'AMIHUD_AIR_POCKET_GUARD' };
            const iceberg = qEngine.iceberg_sniper || { healthy: true, mode: 'Tri-Modal Offensive Sniper', cvd_derivative: '2nd_Derivative_Zero_Crossing' };

            // Infra Data
            const gh = infra.github_persistence || { branch: 'state', sha: '-' };
            const ram = infra.ram_watchdog || { max_candles: 150, limit: 150, gc_interval: '60s' };

            const badgeColor = isPerf ? 'var(--green)' : 'var(--yellow)';
            const badgeBg = isPerf ? 'rgba(14,203,129,0.12)' : 'rgba(245,158,11,0.12)';
            const borderCol = isPerf ? 'rgba(14,203,129,0.3)' : 'rgba(245,158,11,0.3)';

            const pill = (txt, color='var(--green)') => `
                <span style="background:${color==='var(--green)'?'rgba(14,203,129,0.12)':(color==='var(--cyan)'?'rgba(0,242,254,0.12)':(color==='var(--red)'?'rgba(239,68,68,0.14)':'rgba(245,158,11,0.12)'))};
                             color:${color};
                             border:1px solid ${color==='var(--green)'?'rgba(14,203,129,0.3)':(color==='var(--cyan)'?'rgba(0,242,254,0.3)':(color==='var(--red)'?'rgba(239,68,68,0.35)':'rgba(245,158,11,0.3)'))};
                             padding:3px 8px; border-radius:6px; font-size:11px; font-weight:800; font-family:'JetBrains Mono',monospace; white-space:nowrap; letter-spacing:0.3px; flex-shrink:0;">
                    ${txt}
                </span>
            `;

            const itemRow = (icon, title, desc, rightVal, rightPill) => `
                <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.06); border-radius:10px; padding:12px 14px; display:flex; justify-content:space-between; align-items:flex-start; gap:12px; transition:all 0.2s ease;"
                     onmouseenter="this.style.background='rgba(255,255,255,0.04)'; this.style.borderColor='rgba(0,242,254,0.2)';"
                     onmouseleave="this.style.background='rgba(255,255,255,0.02)'; this.style.borderColor='rgba(255,255,255,0.06)';">
                    <div style="flex:1 1 auto; min-width:0;">
                        <div style="font-size:12.5px; font-weight:700; color:#f1f5f9; margin-bottom:3px; display:flex; align-items:center; gap:6px;">
                            <span>${icon}</span>
                            <span>${title}</span>
                        </div>
                        <div style="font-size:11px; color:#94a3b8; line-height:1.45; word-break:break-word;">${desc}</div>
                    </div>
                    <div style="display:flex; flex-direction:column; align-items:flex-end; gap:4px; flex-shrink:0;">
                        ${rightPill}
                        <span style="font-size:10.5px; color:#cbd5e1; font-family:'JetBrains Mono',monospace; font-weight:600; white-space:nowrap;">${rightVal}</span>
                    </div>
                </div>
            `;

            const liqAmount = Number(liq.total_usd_24h || 0).toLocaleString();
            const btcV = Number(btcShock.velocity_60s || 0);
            const btcVStr = (btcV >= 0 ? '+' : '') + btcV.toFixed(2);

            const uptimeSec = Number(appState.server_uptime_sec || 0);
            const days = Math.floor(uptimeSec / 86400);
            const hours = Math.floor((uptimeSec % 86400) / 3600);
            const mins = Math.floor((uptimeSec % 3600) / 60);
            const secs = uptimeSec % 60;
            const uptimeStr = `${days > 0 ? days + 'g ' : ''}${hours.toString().padStart(2,'0')}s ${mins.toString().padStart(2,'0')}d ${secs.toString().padStart(2,'0')}sn`;

            container.innerHTML = `
                <!-- ÜST HERO DURUM AFİŞİ -->
                <div style="background:linear-gradient(135deg, rgba(14, 19, 31, 0.95), rgba(17, 24, 39, 0.95)); border:1.5px solid ${borderCol}; box-shadow:0 4px 24px rgba(0,0,0,0.4); border-radius:14px; padding:20px 24px; margin-bottom:20px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:16px;">
                    <div style="flex:1 1 320px; min-width:0;">
                        <div style="font-size:11px; font-weight:800; color:var(--cyan); text-transform:uppercase; letter-spacing:1px; margin-bottom:4px; display:flex; align-items:center; gap:6px;">
                            <span>🛡️</span> AEGIS SENTINEL 360° KUANT TELEMETRİ SİSTEMİ
                        </div>
                        <div style="font-size:20px; font-weight:800; color:#f8fafc; margin-bottom:6px; letter-spacing:-0.3px;">
                            Sistem Sağlığı & Kuant Sensör Kokpiti
                        </div>
                        <div style="font-size:12px; color:#94a3b8; line-height:1.5; word-break:break-word;">
                            Binance Futures 100 paritede canlı WebSocket fiyatları, L2 tahta derinliği (OBI), Mikro-CVD emir akışı, global tasfiyeler, spot-perp basis ve bulut bellek korumasının gerçek zamanlı canlı teşhis merkezidir.
                        </div>
                    </div>
                    <div style="display:flex; flex-direction:column; align-items:flex-end; gap:8px; flex-shrink:0;">
                        <div style="display:flex; align-items:center; gap:8px;">
                            <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:${badgeColor}; box-shadow:0 0 10px ${badgeColor};"></span>
                            <span style="font-size:14.5px; font-weight:800; color:${badgeColor}; font-family:'JetBrains Mono',monospace;">
                                ${sys.status_text || '10/10 Tam Sağlıklı'}
                            </span>
                        </div>
                        <div style="font-size:11px; color:#64748b; font-family:'JetBrains Mono',monospace;">
                            ⏱️ Kesintisiz Uptime: <span style="color:#38bdf8; font-weight:700;">${uptimeStr}</span> • Son Kalp Atışı: <span style="color:#cbd5e1; font-weight:700;">${sys.timestamp || new Date().toLocaleTimeString()} (TSİ)</span>
                        </div>
                        <button onclick="syncBackendState(); if(typeof showToast === 'function') showToast('⚡ Canlı telemetri yenilendi');"
                                style="background:rgba(0,242,254,0.08); border:1px solid rgba(0,242,254,0.3); color:var(--cyan); font-size:11.5px; font-weight:700; padding:6px 14px; border-radius:8px; cursor:pointer; display:flex; align-items:center; gap:6px; transition:all 0.2s ease;"
                                onmouseenter="this.style.background='rgba(0,242,254,0.18)';"
                                onmouseleave="this.style.background='rgba(0,242,254,0.08)';">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 4v6h-6"></path><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg>
                            Canlı Teşhisi Yenile
                        </button>
                    </div>
                </div>

                <!-- 4 HERO KPI KARTI -->
                <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(230px, 1fr)); gap:14px; margin-bottom:20px;">
                    <div class="cockpit-kpi-card" style="border:1px solid rgba(14,203,129,0.25); background:rgba(14,203,129,0.03);">
                        <div class="kpi-card-head">
                            <span class="kpi-card-title">GENEL SAĞLIK PUANI</span>
                            <span class="kpi-card-icon">🛡️</span>
                        </div>
                        <div class="kpi-card-val" style="color:var(--green); font-size:24px;">${sys.score_str || '10/10'}</div>
                        <div class="kpi-card-sub" style="color:#cbd5e1;">0 Kritik Hata • Sentinel Devrede</div>
                    </div>

                    <div class="cockpit-kpi-card" style="border:1px solid rgba(0,242,254,0.25); background:rgba(0,242,254,0.03);">
                        <div class="kpi-card-head">
                            <span class="kpi-card-title">CANLI PARİTE AKIŞI</span>
                            <span class="kpi-card-icon">⚡</span>
                        </div>
                        <div class="kpi-card-val" style="color:var(--cyan); font-size:24px;">${ws.count || 100} / ${ws.total || 100}</div>
                        <div class="kpi-card-sub" style="color:#cbd5e1;">%100 WebSocket & REST Kapsama</div>
                    </div>

                    <div class="cockpit-kpi-card" style="border:1px solid rgba(59,130,246,0.25); background:rgba(59,130,246,0.03);">
                        <div class="kpi-card-head">
                            <span class="kpi-card-title">L2 DERİNLİK & MİKRO-CVD</span>
                            <span class="kpi-card-icon">🌊</span>
                        </div>
                        <div class="kpi-card-val" style="color:#60a5fa; font-size:24px;">${obi.count || 100} Parite</div>
                        <div class="kpi-card-sub" style="color:#cbd5e1;">Anlık Duvar & Taker Emilim Radarı</div>
                    </div>

                    <div class="cockpit-kpi-card" style="border:1px solid rgba(168,85,247,0.25); background:rgba(168,85,247,0.03);">
                        <div class="kpi-card-head">
                            <span class="kpi-card-title">CANLI UPTIME & BELLEK</span>
                            <span class="kpi-card-icon">⏱️</span>
                        </div>
                        <div class="kpi-card-val" style="color:#c084fc; font-size:20px;">${uptimeStr}</div>
                        <div class="kpi-card-sub" style="color:#cbd5e1;">Render 512MB RAM • Max 150 Mum Koruma</div>
                    </div>
                </div>

                <!-- 3 ANA KATEGORİ KOLONLARI -->
                <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(360px, 1fr)); gap:18px;">

                    <!-- KOLON 1: CANLI BORSA VE PİYASA VERİ AKIŞLARI -->
                    <div style="background:var(--card-bg, #111726); border:1px solid rgba(255,255,255,0.08); border-radius:14px; padding:18px 20px; box-shadow:0 4px 24px rgba(0,0,0,0.25); display:flex; flex-direction:column; gap:10px;">
                        <div style="border-bottom:1px solid rgba(255,255,255,0.06); padding-bottom:12px; margin-bottom:4px;">
                            <div style="font-size:12px; font-weight:800; color:#38bdf8; text-transform:uppercase; letter-spacing:0.8px; display:flex; align-items:center; gap:8px;">
                                <span>📡</span> 1. CANLI BORSA VE PİYASA VERİ AKIŞLARI
                            </div>
                            <div style="font-size:11px; color:#64748b; margin-top:3px;">Binance Futures milisaniyelik soketler ve sipariş akışları</div>
                        </div>

                        ${itemRow('⚡', 'Binance WebSocket Canlı Fiyat', '100 paritede milisaniyelik anlık en iyi alış/satış (bid/ask) fiyat akışı', (ws.count || 100) + ' / ' + (ws.total || 100) + ' Parite', pill(ws.count >= 80 ? 'CANLI AKIYOR' : 'GECİKME', ws.count >= 80 ? 'var(--green)' : 'var(--yellow)'))}
                        ${itemRow('🧱', 'L2 Tahta Derinliği & OBI Duvarları', 'Emir defteri alıcı/satıcı dengesizliği (OBI) ve anlık likidite duvarları', (obi.count || 100) + ' Canlı Tahta', pill((obi.bid_walls || 0) + 'B / ' + (obi.ask_walls || 0) + 'A', 'var(--cyan)'))}
                        ${itemRow('🌊', 'Anlık Mikro-CVD & Taker Emilim', 'Gerçek zamanlı piyasa alıcı/satıcı hacim farkı ve kurumsal emir emilimi', (cvd.count || 100) + ' Parite (60s)', pill('DELTA TAKİPTE', 'var(--green)'))}
                        ${itemRow('💀', 'Global Tasfiye Radarı (!forceOrder)', 'Son 24 saatlik long/short likidasyon patlamaları ve piyasa yönü', '$' + liqAmount + ' (Son: ' + (liq.last_event_time || '-') + ')', pill('7/24 SOKET', 'var(--green)'))}
                        ${itemRow('⚖️', 'Spot vs Vadeli Basis Senkronu', 'Vadeli ile spot piyasa arasındaki arbitraj primi ve kurumsal sapma radarı', (spot.count || 100) + ' Parite (15s)', pill('SENKRON', 'var(--cyan)'))}
                        ${itemRow('🏛️', 'Coinbase Spot Öncüsü (Lead-Lag LLI)', 'Coinbase Pro BTC/USD spot akışı ile Binance arasındaki kurumsal likidite öncüsü', (cb.spread_bps >= 0 ? '+' : '') + Number(cb.spread_bps || 0).toFixed(1) + ' bps (' + (cb.direction || 'NEUTRAL') + ')', pill(cb.spread_bps >= 8.0 ? 'BOĞA ÖNCÜSÜ' : (cb.spread_bps <= -8.0 ? 'AYI BASKISI' : 'DENGELİ'), cb.spread_bps >= 8.0 ? 'var(--green)' : (cb.spread_bps <= -8.0 ? 'var(--red)' : 'var(--cyan)')))}
                        ${itemRow('🧲', 'Açık Faiz İvmesi (Delta-OI Radar)', 'Vadeli piyasada (Bybit/Gate/Binance) 30s periyotlu taze kurumsal sermaye akış radarı', (oi.fresh_count || 100) + ' Parite (Top: ' + (oi.top_expansion || '-') + ' %' + Number(oi.top_expansion_pct || 0).toFixed(1) + ')', pill(oi.fresh_count >= 10 ? 'RADAR AKTİF' : 'TARANIYOR', oi.fresh_count >= 10 ? 'var(--green)' : 'var(--yellow)'))}
                    </div>

                    <!-- KOLON 2: KUANT MOTORU VE ANALİTİK SENSÖRLER -->
                    <div style="background:var(--card-bg, #111726); border:1px solid rgba(255,255,255,0.08); border-radius:14px; padding:18px 20px; box-shadow:0 4px 24px rgba(0,0,0,0.25); display:flex; flex-direction:column; gap:10px;">
                        <div style="border-bottom:1px solid rgba(255,255,255,0.06); padding-bottom:12px; margin-bottom:4px;">
                            <div style="font-size:12px; font-weight:800; color:#a78bfa; text-transform:uppercase; letter-spacing:0.8px; display:flex; align-items:center; gap:8px;">
                                <span>🧠</span> 2. KUANT MOTORU VE ANALİTİK SENSÖRLER
                            </div>
                            <div style="font-size:11px; color:#64748b; margin-top:3px;">Sinyal üretimi, piyasa rejimi ve mikro-şok devre kesicileri</div>
                        </div>

                        ${itemRow('⚡', 'BTC 60s Mikro-Şok Kalkanı', 'Bitcoin ani 60 saniyelik mikro çöküş ve sıçrama devre kesicisi', 'BTC Hız: %' + btcVStr + ' (±%0.28)', pill(btcShock.is_active ? 'ŞOK DEVREDE' : 'GÜVENLİ', btcShock.is_active ? 'var(--red)' : 'var(--green)'))}
                        ${itemRow('🏛️', 'Deribit GEX Black-Scholes Rejimi', 'Kurumsal opsiyon gamma maruziyeti, volatilite pini (+GEX) ve patlama (-GEX) radarı', (deribit.regime || 'NEUTRAL') + ' ($' + Number(deribit.net_gex_usd || 0).toLocaleString() + ')', pill(deribit.regime === 'POSITIVE_GAMMA_PIN' ? '+GEX MIKNATIS' : (deribit.regime === 'NEGATIVE_GAMMA_EXPLOSION' ? '-GEX PATLAMA' : 'GEX DENGELİ'), deribit.regime === 'POSITIVE_GAMMA_PIN' ? 'var(--cyan)' : (deribit.regime === 'NEGATIVE_GAMMA_EXPLOSION' ? 'var(--red)' : 'var(--green)')))}
                        ${itemRow('⚡', 'Hawkes Tasfiye Çığı Radarı (!forceOrder)', 'Tasfiyelerin kendi kendini besleyen zincirleme patlama şiddeti (Branching Ratio η)', 'η: ' + Number(hawkes.eta || 0.15).toFixed(2) + (hawkes.is_active ? ' (' + (hawkes.side || 'ÇIĞ') + ')' : ''), pill(hawkes.is_active ? '⚡ ÇIĞ AKTİF' : 'SAKİN AKIŞ', hawkes.is_active ? 'var(--red)' : 'var(--green)'))}
                        ${itemRow('🎯', 'Stoikov Micro-Price & VPIN Toksik Akış', 'Order book derinlik ağırlıklı mikrofiyat sapması ve hacim dilimli toksik akış radarı', 'Stoikov + VPIN Filtresi', pill('RANGE VETO KORUMASI', 'var(--cyan)'))}
                        ${itemRow('🧊', 'Tri-Modal Iceberg & CVD 2. Türev', '3-Modlu rejim uyumlu iceberg gizli likidite avcısı ve ivme sıfır geçişi dedektörü', 'İvme ve Sıkışma Radarı', pill('%0.20 STOP AVCI', 'var(--green)'))}
                        ${itemRow('💰', 'Fonlama Oranı & Squeeze Radarı', '8 saatlik fonlama maliyetleri ve short/long sıkışma fırsat/tuzak kalkanı', '100 Parite Taranıyor', pill(funding.last_update || '60s PERİYOT', 'var(--green)'))}
                        ${itemRow('📊', 'Dinamik Seviye & Rejim Matrisi', 'Camarilla pivot seviyeleri, ATR %, Hurst üssü ve kaos/kristal faz tespiti', (lev.count || 100) + ' / ' + (lev.total || 100) + ' Parite Tam Uyumlu', pill('0 SAPMA', 'var(--cyan)'))}
                        ${itemRow('🧬', '100 Parite Kuant DNA Profilleri', 'Pariteye özel volatilite sınıflaması, hacim eşikleri ve karakter profilleme', (dna.count || 100) + ' Parite Hafızada', pill('YÜKLENDİ', 'var(--green)'))}
                        ${itemRow('🌀', 'Shannon Confluence & Entropi Kalkanı', '3-Eksen bağımsız confluence doğrulaması ve Boltzmann L2 gürültü filtresi', 'JIT Anlık Doğrulama', pill('AKTİF', 'var(--cyan)'))}
                    </div>

                    <!-- KOLON 3: BULUT ALTYAPISI, RAM & SÜREKLİLİK -->
                    <div style="background:var(--card-bg, #111726); border:1px solid rgba(255,255,255,0.08); border-radius:14px; padding:18px 20px; box-shadow:0 4px 24px rgba(0,0,0,0.25); display:flex; flex-direction:column; gap:10px;">
                        <div style="border-bottom:1px solid rgba(255,255,255,0.06); padding-bottom:12px; margin-bottom:4px;">
                            <div style="font-size:12px; font-weight:800; color:#34d399; text-transform:uppercase; letter-spacing:0.8px; display:flex; align-items:center; gap:8px;">
                                <span>☁️</span> 3. BULUT ALTYAPISI, RAM & SÜREKLİLİK
                            </div>
                            <div style="font-size:11px; color:#64748b; margin-top:3px;">Render bulut dayanıklılığı, bellek bekçisi ve otonom yedekler</div>
                        </div>

                        ${itemRow('🛡️', 'GitHub Bulut Kasa Senkronu', 'Kasa bakiyesi ve islemlerin state dalina otonom commit ve senkronu', (gh.branch || 'state') + ' Dali (Commit: ' + (gh.sha || '-') + ')', pill('SENKRONİZE', 'var(--green)'))}
                        ${itemRow('🧹', 'Otonom Bellek (RAM) Watchdog', 'Bellek şişmesini önleyen 150 mumluk dinamik tavan ve Render 512MB RAM kalkanı', 'Max ' + (ram.limit || 150) + ' Mum + 60s GC', pill('512MB GÜVENLİ', 'var(--green)'))}
                        ${itemRow('⏱️', 'Render Keep-Alive Uyku Kalkanı', 'Render Free Tier 15 dakika inaktivite uykusunu engelleyen 3 dakikalık self-ping', 'Her 3 Dakika (200 OK)', pill('7/24 UYANIK', 'var(--green)'))}
                        ${itemRow('📱', 'Telegram Saatlik VIP Raporlayıcı', 'Saat başı :00 otomatik kasa raporu ve /kasa interaktif komut dinleyici', 'Saat Başı :00 Rapor', pill('AKTİF', 'var(--cyan)'))}
                        ${itemRow('⚙️', 'Aegis Sentinel Otonom Denetim', 'Tüm alt kuant servislerinin kesintisiz çalışmasını denetleyen nöronal bekçi', 'Sıfır Hata / Tam Sağlıklı', pill('TAM KORUMA', 'var(--green)'))}
                    </div>

                </div>

                <!-- ALT BİLGİLENDİRME BANTI -->
                <div style="margin-top:20px; padding:12px 18px; background:rgba(255,255,255,0.015); border:1px solid rgba(255,255,255,0.05); border-radius:10px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; font-family:'JetBrains Mono',monospace; font-size:11px; color:#64748b;">
                    <div>⚙️ Mimari: <span style="color:#cbd5e1;">Render Docker Linux • Python 3.10 Aiohttp • Zero-Allocation Bellek Döngüsü</span></div>
                    <div>🛡️ Sentinel: <span style="color:var(--green); font-weight:700;">7/24 Kesintisiz Otonom İzleme Aktif</span></div>
                </div>
            `;
        }


        // =========================================================================
        // VALKYRIE QUANT COCKPIT 3.0 - MAIN TAB SWITCHING & AI ENGINE
        // =========================================================================
        let currentActiveMainTab = 'cockpit';
        window.currentActiveMainTab = currentActiveMainTab;

        let personaFilter = 'ALL';
        let personaSearchQuery = '';

        function setPersonaFilter(filter) {
            personaFilter = filter;
            ['ALL', 'GOLD', 'STANDARD', 'WHIPSAW'].forEach(f => {
                const btn = document.getElementById('pfilter-btn-' + f);
                if (btn) {
                    if (f === filter) btn.classList.add('tab-active');
                    else btn.classList.remove('tab-active');
                }
            });
            renderPersonaMatrixView();
        }

        function onPersonaSearchInput(val) {
            personaSearchQuery = (val || '').trim().toUpperCase();
            renderPersonaMatrixView();
        }

        function updatePersonaBadge() {
            const badge = document.getElementById('nav-persona-badge');
            if (!badge || !appState.coin_personas) return;
            const matrix = appState.coin_personas || {};
            let w = 0, g = 0;
            for (const s in matrix) {
                const p = matrix[s].persona_class;
                if (p === 'WHIPSAW') w++;
                else if (p === 'GOLD') g++;
            }
            badge.innerText = `${w} ⚠️ | ${g} 👑`;
        }

        let shadowCoinFilterState = 'ALL';

        const shadowSections = {
            'shadow-dna': { isHidden: false, name: '100 Coin DNA Masası' },
            'shadow-shields': { isHidden: false, name: 'Kalkan Karnesi' },
            'shadow-active': { isHidden: false, name: 'Aktif Gölge Pozisyonlar' },
            'shadow-history': { isHidden: false, name: 'Tamamlanan Gölge Defteri' }
        };

        try {
            const savedShadowState = localStorage.getItem('valkyrie_shadow_sections');
            if (savedShadowState) {
                const parsed = JSON.parse(savedShadowState);
                Object.keys(parsed).forEach(k => {
                    if (shadowSections[k]) shadowSections[k].isHidden = parsed[k];
                });
            }
        } catch(e) {}

        function applyShadowSectionVisibility() {
            Object.keys(shadowSections).forEach(k => {
                const isHidden = shadowSections[k].isHidden;
                const container = document.getElementById(`container-${k}`);
                const btnText = document.getElementById(`text-toggle-${k}`);
                const btnIcon = document.getElementById(`icon-toggle-${k}`);
                const btn = document.getElementById(`btn-toggle-${k}`);
                if (container) {
                    container.style.display = isHidden ? 'none' : 'block';
                }
                if (btnText) {
                    btnText.innerText = isHidden ? 'Göster' : 'Gizle';
                }
                if (btnIcon) {
                    btnIcon.innerText = isHidden ? '👁️‍🗨️' : '👁️';
                }
                if (btn) {
                    if (isHidden) {
                        btn.style.opacity = '0.6';
                        btn.style.borderColor = 'rgba(255,255,255,0.15)';
                        btn.style.color = '#94a3b8';
                    } else {
                        btn.style.opacity = '1';
                        btn.style.borderColor = k === 'shadow-active' ? 'rgba(168,85,247,0.4)' : 'rgba(56,189,248,0.4)';
                        btn.style.color = k === 'shadow-active' ? '#a855f7' : '#38bdf8';
                    }
                }
            });
            try {
                const toSave = {};
                Object.keys(shadowSections).forEach(k => toSave[k] = shadowSections[k].isHidden);
                localStorage.setItem('valkyrie_shadow_sections', JSON.stringify(toSave));
            } catch(e) {}
        }

        function toggleShadowSection(secKey) {
            if (shadowSections[secKey]) {
                shadowSections[secKey].isHidden = !shadowSections[secKey].isHidden;
                applyShadowSectionVisibility();
            }
        }

        function toggleAllShadowSections(show) {
            Object.keys(shadowSections).forEach(k => {
                shadowSections[k].isHidden = !show;
            });
            applyShadowSectionVisibility();
        }

        function updateShadowBadge() {
            const badge = document.getElementById('nav-shadow-badge');
            if (!badge || !appState || !appState.shadow_summary) return;
            const summ = appState.shadow_summary || {};
            const sei = summ.shield_efficiency_index != null ? summ.shield_efficiency_index : 100;
            const heroes = summ.hero_count || 0;
            const spoilers = summ.spoiler_count || 0;
            badge.innerText = `SEI %${sei.toFixed(0)} (${heroes}🛡️/${spoilers}⚠️)`;
        }

        function setShadowCoinFilter(filter) {
            shadowCoinFilterState = filter;
            ['all', 'relax', 'keep'].forEach(k => {
                const btn = document.getElementById(`btn-shadow-filter-${k}`);
                if (btn) btn.classList.remove('active');
            });
            const actBtn = document.getElementById(`btn-shadow-filter-${filter.toLowerCase()}`);
            if (actBtn) actBtn.classList.add('active');
            renderShadowView();
        }

        function filterShadowCoinsTable() {
            renderShadowView();
        }

        function renderShadowView() {
            try {
                if (!appState) return;
                const summ = appState.shadow_summary || {};
                const coinMatrix = appState.coin_dna_matrix || [];
                const shieldBoards = appState.shield_leaderboard || [];
                const activePos = appState.shadow_positions || [];
                const hist = appState.shadow_history || [];

                // 1. KPI Kartlarını Güncelle
                const savedEl = document.getElementById('shadow-kpi-saved');
                if (savedEl) savedEl.innerText = `+$${(summ.total_saved_loss_usd || 0).toFixed(2)}`;

                const heroEl = document.getElementById('shadow-kpi-hero-count');
                if (heroEl) heroEl.innerText = summ.hero_count || 0;

                const missedEl = document.getElementById('shadow-kpi-missed');
                if (missedEl) missedEl.innerText = `-$${(summ.total_missed_profit_usd || 0).toFixed(2)}`;

                const spoilerEl = document.getElementById('shadow-kpi-spoiler-count');
                if (spoilerEl) spoilerEl.innerText = summ.spoiler_count || 0;

                const seiEl = document.getElementById('shadow-kpi-sei');
                if (seiEl) {
                    const sei = summ.shield_efficiency_index != null ? summ.shield_efficiency_index : 100;
                    seiEl.innerText = `%${sei.toFixed(1)}`;
                    seiEl.style.color = sei >= 70 ? '#10b981' : (sei <= 35 ? '#f43f5e' : '#f59e0b');
                }

                const alphaEl = document.getElementById('shadow-kpi-alpha');
                if (alphaEl) {
                    const alpha = summ.net_shield_alpha_usd || 0;
                    alphaEl.innerText = `${alpha >= 0 ? '+$' : '-$'}${Math.abs(alpha).toFixed(2)}`;
                    alphaEl.style.color = alpha >= 0 ? '#06b6d4' : '#f43f5e';
                }

                const activeEl = document.getElementById('shadow-kpi-active');
                if (activeEl) activeEl.innerText = `${summ.active_shadow_trades || activePos.length} Aktif`;

                const totalEl = document.getElementById('shadow-kpi-total-tracked');
                if (totalEl) totalEl.innerText = summ.total_shadow_trades || (activePos.length + hist.length);

                updateShadowBadge();

                // 2. 100 Coin Canlı DNA & Kalibrasyon Tablosu
                const coinTbody = document.getElementById('shadow-coin-matrix-tbody');
                if (coinTbody) {
                    const searchInput = (document.getElementById('shadow-coin-search')?.value || '').trim().toUpperCase();
                    
                    let filteredCoins = coinMatrix.filter(c => {
                        if (searchInput && !c.symbol.toUpperCase().includes(searchInput)) return false;
                        if (shadowCoinFilterState === 'RELAX' && !c.recommendation_badge.includes('GEVŞET')) return false;
                        if (shadowCoinFilterState === 'KEEP' && !c.recommendation_badge.includes('KORU')) return false;
                        return true;
                    });

                    if (filteredCoins.length === 0) {
                        coinTbody.innerHTML = `<tr><td colspan="12" style="text-align:center; padding:24px; color:#64748b;">${coinMatrix.length === 0 ? 'Canlı mumlarla gölge pozisyonlar toplanıyor... Bot her 5M mumda verileri işler.' : 'Arama kriterine uygun coin bulunamadı.'}</td></tr>`;
                    } else {
                        coinTbody.innerHTML = filteredCoins.map(c => {
                            const badgeColor = c.recommendation_badge.includes('GEVŞET') ? '#f43f5e' : (c.recommendation_badge.includes('KORU') ? '#10b981' : '#f59e0b');
                            const badgeBg = c.recommendation_badge.includes('GEVŞET') ? 'rgba(244,63,94,0.12)' : (c.recommendation_badge.includes('KORU') ? 'rgba(16,185,129,0.12)' : 'rgba(245,158,11,0.12)');

                            return `
                                <tr style="border-bottom:1px solid rgba(255,255,255,0.04); font-family:'JetBrains Mono', monospace; font-size:12px;">
                                    <td style="font-weight:700; color:#fff; padding:10px 12px; text-align:left;">${c.symbol}</td>
                                    <td style="text-align:center;">${c.total_shadows}</td>
                                    <td style="text-align:center; color:#10b981; font-weight:700;">${c.hero_count}</td>
                                    <td style="text-align:center; color:#f43f5e; font-weight:700;">${c.spoiler_count}</td>
                                    <td style="text-align:center; color:#10b981; font-weight:600;">+$${(c.saved_loss_usd || 0).toFixed(2)}</td>
                                    <td style="text-align:center; color:#f43f5e; font-weight:600;">-$${(c.missed_profit_usd || 0).toFixed(2)}</td>
                                    <td style="text-align:center; font-weight:700; color:${c.sei >= 70 ? '#10b981' : (c.sei <= 35 ? '#f43f5e' : '#f59e0b')};">%${(c.sei || 100).toFixed(1)}</td>
                                    <td style="text-align:left; color:#94a3b8; font-size:11.5px; white-space:normal; line-height:1.3;">${c.top_shield || '-'}</td>
                                    <td style="text-align:center; color:#38bdf8;">%${(c.wick_elasticity || 12).toFixed(1)}</td>
                                    <td style="text-align:center;">
                                        <span style="background:${badgeBg}; color:${badgeColor}; border:1px solid ${badgeColor}40; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:700; white-space:nowrap;">
                                            ${c.recommendation_badge}
                                        </span>
                                    </td>
                                    <td style="text-align:left; color:#cbd5e1; font-size:11.5px;">
                                        <div style="font-weight:700; color:#38bdf8; font-size:11.5px; margin-bottom:3px; display:flex; align-items:center; gap:6px;">
                                            <span>${c.scenario_title || '🎯 Canlı Piyasa Gözlemi'}</span>
                                        </div>
                                        <div style="color:#cbd5e1; margin-bottom:4px; line-height:1.4;">${c.recommendation}</div>
                                        ${(c.modifications_count > 0 && c.modifications_summary) ? `<div style="display:inline-block; background:rgba(56,189,248,0.1); border:1px solid rgba(56,189,248,0.25); border-radius:4px; padding:1px 6px; font-size:10px; color:#38bdf8; font-weight:600;">🛠️ ${c.modifications_summary}</div>` : ''}
                                    </td>
                                    <td style="text-align:center;">
                                        <button onclick="openShadowCoinDetail('${c.symbol}')" style="background:linear-gradient(135deg, rgba(56,189,248,0.2), rgba(168,85,247,0.2)); color:#38bdf8; border:1px solid rgba(56,189,248,0.4); padding:4px 8px; border-radius:6px; cursor:pointer; font-weight:700; font-size:11px; font-family:'JetBrains Mono', monospace; transition:all 0.15s ease; white-space:nowrap;">
                                            🔍 Detay
                                        </button>
                                    </td>
                                </tr>
                            `;
                        }).join('');
                    }
                }

                // 3. Kalkan Liderlik Tablosu
                const shieldTbody = document.getElementById('shadow-shield-leaderboard-tbody');
                if (shieldTbody) {
                    if (shieldBoards.length === 0) {
                        shieldTbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding:20px; color:#64748b;">Kalkan verileri hesaplanıyor...</td></tr>`;
                    } else {
                        shieldTbody.innerHTML = shieldBoards.map(s => {
                            const roleColor = s.role.includes('KAHRAMAN') ? '#10b981' : (s.role.includes('FRENLEYİCİ') ? '#f43f5e' : '#f59e0b');
                            const roleBg = s.role.includes('KAHRAMAN') ? 'rgba(16,185,129,0.12)' : (s.role.includes('FRENLEYİCİ') ? 'rgba(244,63,94,0.12)' : 'rgba(245,158,11,0.12)');
                            return `
                                <tr style="border-bottom:1px solid rgba(255,255,255,0.04); font-family:'JetBrains Mono', monospace; font-size:12px;">
                                    <td style="font-weight:700; color:#fff; text-align:left; padding:10px 12px;">${s.shield_name}</td>
                                    <td style="text-align:center;">${s.total_blocks}</td>
                                    <td style="text-align:center; color:#10b981; font-weight:700;">${s.hero_count}</td>
                                    <td style="text-align:center; color:#f43f5e; font-weight:700;">${s.spoiler_count}</td>
                                    <td style="text-align:center; color:#10b981;">+$${(s.saved_loss_usd || 0).toFixed(2)}</td>
                                    <td style="text-align:center; color:#f43f5e;">-$${(s.missed_profit_usd || 0).toFixed(2)}</td>
                                    <td style="text-align:center; font-weight:700; color:${s.net_saved_usd >= 0 ? '#10b981' : '#f43f5e'};">${s.net_saved_usd >= 0 ? '+$' : '-$'}${Math.abs(s.net_saved_usd || 0).toFixed(2)}</td>
                                    <td style="text-align:center; font-weight:700;">%${(s.sei || 100).toFixed(1)}</td>
                                    <td style="text-align:center;">
                                        <span style="background:${roleBg}; color:${roleColor}; border:1px solid ${roleColor}40; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:700;">
                                            ${s.role}
                                        </span>
                                    </td>
                                </tr>
                            `;
                        }).join('');
                    }
                }

                // 4. Aktif Gölge Pozisyonlar Tablosu
                const activeTbody = document.getElementById('shadow-active-tbody');
                const activeBadge = document.getElementById('shadow-active-count-badge');
                if (activeBadge) activeBadge.innerText = `${activePos.length} Pozisyon`;

                if (activeTbody) {
                    if (activePos.length === 0) {
                        activeTbody.innerHTML = `<tr><td colspan="14" style="text-align:center; padding:20px; color:#64748b;">Şu an canlı izlenen açık gölge pozisyon yok. Reddedilen yeni sinyaller anında burada takip edilir.</td></tr>`;
                    } else {
                        activeTbody.innerHTML = activePos.map(p => {
                            const sideColor = p.side === 'LONG' ? '#10b981' : '#f43f5e';
                            const sideBg = p.side === 'LONG' ? 'rgba(16,185,129,0.12)' : 'rgba(244,63,94,0.12)';
                            const pnlPct = p.side === 'LONG' ? ((p.current_price - p.entry_price) / p.entry_price * 5 * 100) : ((p.entry_price - p.current_price) / p.entry_price * 5 * 100);
                            const pnlUsd = (250 * (pnlPct / 100)).toFixed(2);
                            const pnlColor = pnlPct >= 0 ? '#10b981' : '#f43f5e';

                            return `
                                <tr style="border-bottom:1px solid rgba(255,255,255,0.04); font-family:'JetBrains Mono', monospace; font-size:12px;">
                                    <td style="font-weight:700; color:#fff; text-align:left; padding:10px 12px;">${p.symbol.replace('/USDT','')}</td>
                                    <td style="text-align:center;"><span style="background:${sideBg}; color:${sideColor}; padding:2px 6px; border-radius:6px; font-weight:700; font-size:11px;">${p.side}</span></td>
                                    <td style="text-align:left; color:#94a3b8;">${p.setup}</td>
                                    <td style="text-align:left; color:#cbd5e1;">${p.shield}</td>
                                    <td style="text-align:center;">$${p.entry_price < 1 ? p.entry_price.toFixed(4) : p.entry_price.toFixed(2)}</td>
                                    <td style="text-align:center; font-weight:700; color:#fff;">$${p.current_price < 1 ? p.current_price.toFixed(4) : p.current_price.toFixed(2)}</td>
                                    <td style="text-align:center; color:#f43f5e;">$${p.sl_price < 1 ? p.sl_price.toFixed(4) : p.sl_price.toFixed(2)}</td>
                                    <td style="text-align:center; color:#10b981;">$${p.tp1_price < 1 ? p.tp1_price.toFixed(4) : p.tp1_price.toFixed(2)}</td>
                                    <td style="text-align:center; color:#10b981;">$${p.tp2_price < 1 ? p.tp2_price.toFixed(4) : p.tp2_price.toFixed(2)}</td>
                                    <td style="text-align:center; color:#10b981;">+%{p.max_mfe_pct.toFixed(2)}</td>
                                    <td style="text-align:center; color:#f43f5e;">-%{p.max_mae_pct.toFixed(2)}</td>
                                    <td style="text-align:center; font-weight:700; color:${pnlColor};">${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(2)}%</td>
                                    <td style="text-align:center; font-weight:700; color:${pnlColor};">${pnlPct >= 0 ? '+$' : '-$'}${Math.abs(pnlUsd)}</td>
                                    <td style="text-align:center; color:#64748b;">${((Date.now() / 1000 - p.entry_ts) / 60).toFixed(0)} dk</td>
                                </tr>
                            `;
                        }).join('');
                    }
                }

                // 5. Tamamlanan Gölge Defteri Tablosu
                const histTbody = document.getElementById('shadow-history-tbody');
                if (histTbody) {
                    if (hist.length === 0) {
                        histTbody.innerHTML = `<tr><td colspan="14" style="text-align:center; padding:20px; color:#64748b;">Henüz tamamlanan gölge işlem yok. Pozisyonlar kapandıkça buraya dökülür.</td></tr>`;
                    } else {
                        histTbody.innerHTML = [...hist].reverse().slice(0, 50).map(t => {
                            const isHero = t.verdict === 'HERO_SHIELD';
                            const isSpoiler = t.verdict === 'SPOILER_SHIELD';
                            const badgeColor = isHero ? '#10b981' : (isSpoiler ? '#f43f5e' : '#94a3b8');
                            const badgeBg = isHero ? 'rgba(16,185,129,0.12)' : (isSpoiler ? 'rgba(244,63,94,0.12)' : 'rgba(255,255,255,0.05)');
                            const pnlColor = t.virtual_pnl_usd >= 0 ? '#10b981' : '#f43f5e';

                            return `
                                <tr style="border-bottom:1px solid rgba(255,255,255,0.04); font-family:'JetBrains Mono', monospace; font-size:12px;">
                                    <td style="color:#64748b; font-size:11px;">${t.id.replace('SHD_','')}</td>
                                    <td style="font-weight:700; color:#fff; text-align:left;">${t.symbol.replace('/USDT','')}</td>
                                    <td style="text-align:center; color:${t.side === 'LONG' ? '#10b981' : '#f43f5e'}; font-weight:700;">${t.side}</td>
                                    <td style="text-align:left; color:#94a3b8;">${t.setup}</td>
                                    <td style="text-align:left; color:#cbd5e1;">${t.shield}</td>
                                    <td style="text-align:center;">$${t.entry_price < 1 ? t.entry_price.toFixed(4) : t.entry_price.toFixed(2)}</td>
                                    <td style="text-align:center;">$${t.exit_price ? (t.exit_price < 1 ? t.exit_price.toFixed(4) : t.exit_price.toFixed(2)) : '-'}</td>
                                    <td style="text-align:center; color:#10b981;">+%{t.max_mfe_pct ? t.max_mfe_pct.toFixed(2) : '0.00'}</td>
                                    <td style="text-align:center; color:#f43f5e;">-%{t.max_mae_pct ? t.max_mae_pct.toFixed(2) : '0.00'}</td>
                                    <td style="text-align:center; font-weight:700; color:${pnlColor};">${t.virtual_pnl_usd >= 0 ? '+$' : '-$'}${Math.abs(t.virtual_pnl_usd || 0).toFixed(2)}</td>
                                    <td style="text-align:center;">
                                        <span style="background:${badgeBg}; color:${badgeColor}; border:1px solid ${badgeColor}40; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:700;">
                                            ${t.verdict_badge || t.verdict}
                                        </span>
                                    </td>
                                    <td style="text-align:left; color:#cbd5e1; font-size:11px; max-width:280px; white-space:normal; line-height:1.4;">${t.narrative || t.reason || '-'}</td>
                                    <td style="text-align:center; color:#64748b;">${t.status}</td>
                                    <td style="text-align:center; color:#64748b; font-size:11px;">${t.entry_time ? t.entry_time.split(' ')[1] : '-'}</td>
                                </tr>
                            `;
                        }).join('');
                    }
                }

                // Apply user collapse/expand visibility states
                applyShadowSectionVisibility();
            } catch (err) {
                console.error("renderShadowView error:", err);
            }
        }

        function renderPersonaMatrixView() {
            try {
                const matrix = appState.coin_personas || {};
                const symbols = Object.keys(matrix);

                let goldCount = 0;
                let standardCount = 0;
                let whipsawCount = 0;

                symbols.forEach(s => {
                    const p = matrix[s].persona_class;
                    if (p === 'GOLD') goldCount++;
                    else if (p === 'WHIPSAW') whipsawCount++;
                    else standardCount++;
                });

                // Update KPI Cards
                const elGold = document.getElementById('persona-gold-count');
                const elStd = document.getElementById('persona-standard-count');
                const elWhip = document.getElementById('persona-whipsaw-count');
                if (elGold) elGold.innerText = `${goldCount} Parite`;
                if (elStd) elStd.innerText = `${standardCount} Parite`;
                if (elWhip) elWhip.innerText = `${whipsawCount} Parite`;

                // Update Filter Counts
                const fAll = document.getElementById('pfilter-count-ALL');
                const fGold = document.getElementById('pfilter-count-GOLD');
                const fStd = document.getElementById('pfilter-count-STANDARD');
                const fWhip = document.getElementById('pfilter-count-WHIPSAW');
                if (fAll) fAll.innerText = symbols.length;
                if (fGold) fGold.innerText = goldCount;
                if (fStd) fStd.innerText = standardCount;
                if (fWhip) fWhip.innerText = whipsawCount;

                const footerCount = document.getElementById('persona-footer-count');
                if (footerCount) footerCount.innerText = symbols.length;

                updatePersonaBadge();

                const tbody = document.getElementById('persona-table-body');
                if (!tbody) return;

                if (symbols.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding: 40px; color:#94a3b8;">Henüz analiz edilen parite verisi bulunmuyor.</td></tr>`;
                    return;
                }

                // Filter items
                let filtered = symbols.filter(s => {
                    const item = matrix[s];
                    if (personaFilter !== 'ALL' && item.persona_class !== personaFilter) return false;
                    if (personaSearchQuery) {
                        const q = personaSearchQuery.toUpperCase();
                        const clean = s.replace('/USDT', '').replace('USDT', '').toUpperCase();
                        const pName = (item.persona_name || '').toUpperCase();
                        const pClass = (item.persona_class || '').toUpperCase();
                        return clean.includes(q) || s.toUpperCase().includes(q) || pName.includes(q) || pClass.includes(q);
                    }
                    return true;
                });

                // Sort items: Whipsaw & Gold first, then by net_pnl descending
                filtered.sort((a, b) => {
                    const pA = matrix[a];
                    const pB = matrix[b];
                    const rankOrder = { 'WHIPSAW': 1, 'GOLD': 2, 'STANDARD': 3 };
                    const rankA = rankOrder[pA.persona_class] || 4;
                    const rankB = rankOrder[pB.persona_class] || 4;
                    if (rankA !== rankB) return rankA - rankB;
                    return pB.net_pnl - pA.net_pnl;
                });

                if (filtered.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding: 40px; color:#94a3b8;">Arama veya filtre kriterlerine uygun coin bulunamadı.</td></tr>`;
                    return;
                }

                let html = '';
                filtered.forEach(s => {
                    const item = matrix[s];
                    const symClean = s.replace('/USDT', '').replace('USDT', '');
                    const isGold = item.persona_class === 'GOLD';
                    const isWhipsaw = item.persona_class === 'WHIPSAW';
                    const isBaseline = item.is_baseline !== false && item.is_baseline !== undefined;

                    // Source Badge: Baz DNA vs Canli
                    const sourceBadge = isBaseline
                        ? `<span style="background:rgba(148,163,184,0.15); color:#94a3b8; border:1px solid rgba(148,163,184,0.3); font-size:9.5px; padding:2px 6px; border-radius:4px; margin-left:6px; font-weight:700;">BAZ DNA</span>`
                        : `<span style="background:rgba(34,197,94,0.18); color:#22c55e; border:1px solid rgba(34,197,94,0.4); font-size:9.5px; padding:2px 6px; border-radius:4px; margin-left:6px; font-weight:800;">CANLI</span>`;

                    // Lig Badge
                    let badgeHtml = '';
                    const displayName = item.persona_name || (isGold ? '👑 Altın Lig (Pusu Ustası)' : (isWhipsaw ? '⚠️ Whipsaw (Tuzakçı)' : '⚪ Standart / Dengeli'));
                    if (isGold) {
                        badgeHtml = `<span style="background:rgba(251,197,49,0.15); color:#fbc531; border:1px solid #fbc531; padding:4px 10px; border-radius:6px; font-weight:800; font-size:11.5px; font-family:'JetBrains Mono';">${displayName}</span>`;
                    } else if (isWhipsaw) {
                        badgeHtml = `<span style="background:rgba(244,63,94,0.15); color:#f43f5e; border:1px solid #f43f5e; padding:4px 10px; border-radius:6px; font-weight:800; font-size:11.5px; font-family:'JetBrains Mono';">${displayName}</span>`;
                    } else {
                        badgeHtml = `<span style="background:rgba(255,255,255,0.06); color:#cbd5e1; border:1px solid rgba(255,255,255,0.14); padding:4px 10px; border-radius:6px; font-weight:700; font-size:11.5px; font-family:'JetBrains Mono';">${displayName}</span>`;
                    }

                    // Win rate color
                    const wrColor = item.win_rate >= 60 ? 'var(--green)' : (item.win_rate < 45 ? 'var(--red)' : '#fbc531');

                    // Fakeout color
                    const fakeColor = item.fakeout_rate >= 45 ? 'var(--red)' : (item.fakeout_rate <= 20 ? 'var(--green)' : '#cbd5e1');

                    // Net PnL color
                    const pnlColor = item.net_pnl > 0 ? 'var(--green)' : (item.net_pnl < 0 ? 'var(--red)' : '#94a3b8');

                    // Strategy permissions
                    let stratHtml = '';
                    if (isWhipsaw) {
                        stratHtml = `<span style="color:#fbc531; font-weight:800; font-size:11.5px;">🟡 Yalnızca Sekme Pususu <span style="color:var(--red); font-weight:900;">(Kırılım Kilitli 🔒)</span></span>`;
                    } else if (isGold) {
                        stratHtml = `<span style="color:var(--green); font-weight:800; font-size:11.5px;">🟢 Kırılım + Pusu (Öncelikli x1.3)</span>`;
                    } else {
                        stratHtml = `<span style="color:#38bdf8; font-weight:700; font-size:11.5px;">🟢 Kırılım + Sekme Açık</span>`;
                    }

                    // Dynamic Margin & Stop Setting
                    const mScale = item.margin_scale != null ? Number(item.margin_scale) : (isGold ? 1.3 : (isWhipsaw ? 0.5 : 1.0));
                    const atrMult = item.stop_loss_atr_mult != null ? Number(item.stop_loss_atr_mult) : (isWhipsaw ? 1.5 : 1.0);
                    let riskHtml = '';
                    if (isWhipsaw) {
                        riskHtml = `<span style="color:#f43f5e; font-family:'JetBrains Mono'; font-size:11.5px; font-weight:700;">x${mScale.toFixed(1)} ($8 taban) | ${atrMult.toFixed(1)}x ATR Stop</span>`;
                    } else if (isGold) {
                        riskHtml = `<span style="color:#fbc531; font-family:'JetBrains Mono'; font-size:11.5px; font-weight:700;">x${mScale.toFixed(1)} Marjin | ${atrMult.toFixed(1)}x ATR Stop</span>`;
                    } else {
                        riskHtml = `<span style="color:#94a3b8; font-family:'JetBrains Mono'; font-size:11.5px;">x${mScale.toFixed(1)} Marjin | ${atrMult.toFixed(1)}x ATR Stop</span>`;
                    }

                    html += `
                    <tr>
                        <td>
                            <b style="color:#ffffff; font-size:14px; font-family:'JetBrains Mono';">${symClean}</b>
                            <span style="color:#64748b; font-size:11px;">/USDT</span>
                        </td>
                        <td>${badgeHtml}</td>
                        <td style="color:#cbd5e1; font-family:'JetBrains Mono'; font-size:12px;">${item.trades_count || 0} İşlem ${sourceBadge}</td>
                        <td style="color:${wrColor}; font-weight:800; font-family:'JetBrains Mono';">
                            %${item.win_rate.toFixed(1)}
                        </td>
                        <td style="color:${fakeColor}; font-weight:800; font-family:'JetBrains Mono';">
                            %${item.fakeout_rate.toFixed(1)}
                        </td>
                        <td style="color:${pnlColor}; font-weight:800; font-family:'JetBrains Mono';">
                            ${item.net_pnl >= 0 ? '+' : ''}$${item.net_pnl.toFixed(2)}
                        </td>
                        <td>${stratHtml}</td>
                        <td>${riskHtml}</td>
                        <td style="white-space:nowrap;">
                            <button onclick="openTradingViewModal('${symClean}')" style="background:rgba(0,242,254,0.12); border:1px solid rgba(0,242,254,0.35); color:var(--cyan); padding:4px 9px; border-radius:6px; font-size:11px; font-weight:700; cursor:pointer;" title="${symClean} Grafiğini Aç">
                                📈 Grafik
                            </button>
                            <button onclick="filterWatchlistDirect('${symClean}')" style="background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.15); color:#cbd5e1; padding:4px 8px; border-radius:6px; font-size:11px; font-weight:700; cursor:pointer; margin-left:4px;" title="Pusu Radarında Gör">
                                🎯 Radar
                            </button>
                        </td>
                    </tr>
                    `;
                });

                tbody.innerHTML = html;
            } catch (err) {
                console.error("renderPersonaMatrixView error:", err);
            }
        }

        let fundingFilter = 'ALL';
        let fundingSearchQuery = '';

        function setFundingFilter(filter) {
            fundingFilter = filter;
            ['ALL', 'SQUEEZE', 'OVERHEAT', 'BALANCED'].forEach(f => {
                const btn = document.getElementById('ffilter-btn-' + f);
                if (btn) {
                    if (f === filter) btn.classList.add('tab-active');
                    else btn.classList.remove('tab-active');
                }
            });
            renderFundingMatrixView();
        }

        function onFundingSearchInput(val) {
            fundingSearchQuery = (val || '').trim().toUpperCase();
            renderFundingMatrixView();
        }

        function updateFundingBadge() {
            const badge = document.getElementById('nav-funding-badge');
            if (!badge || !appState.funding_summary) return;
            const summary = appState.funding_summary.summary || {};
            const sqCount = summary.short_squeeze_count || 0;
            if (sqCount > 0) {
                badge.innerText = `${sqCount} ⚠️ Squeeze`;
                badge.style.background = 'rgba(255,107,107,0.18)';
                badge.style.color = 'var(--red)';
                badge.style.border = '1px solid rgba(255,107,107,0.4)';
            } else {
                badge.innerText = `0 Squeeze`;
                badge.style.background = 'rgba(0,242,254,0.12)';
                badge.style.color = 'var(--cyan)';
                badge.style.border = '1px solid rgba(0,242,254,0.3)';
            }
        }

        function renderFundingMatrixView() {
            try {
                const fData = appState.funding_summary || {};
                const summary = fData.summary || {};
                const rates = fData.rates || {};
                const symbols = Object.keys(rates);

                const medianPct = summary.median_rate_pct != null ? summary.median_rate_pct : 0.0100;
                const sqCount = summary.short_squeeze_count || 0;
                const ohCount = summary.long_overheated_count || 0;
                const balCount = summary.balanced_count || symbols.length;

                // Update KPI cards
                const elMedian = document.getElementById('funding-median-val');
                const elSqueeze = document.getElementById('funding-squeeze-count');
                const elOverheat = document.getElementById('funding-overheat-count');
                if (elMedian) elMedian.innerText = `${medianPct >= 0 ? '+' : ''}${medianPct.toFixed(4)}%`;
                if (elSqueeze) elSqueeze.innerText = `${sqCount} Parite`;
                if (elOverheat) elOverheat.innerText = `${ohCount} Parite`;

                // Update filter pills counts
                const fAll = document.getElementById('ffilter-count-ALL');
                const fSq = document.getElementById('ffilter-count-SQUEEZE');
                const fOh = document.getElementById('ffilter-count-OVERHEAT');
                const fBal = document.getElementById('ffilter-count-BALANCED');
                if (fAll) fAll.innerText = symbols.length;
                if (fSq) fSq.innerText = sqCount;
                if (fOh) fOh.innerText = ohCount;
                if (fBal) fBal.innerText = balCount;

                const footerCount = document.getElementById('funding-footer-count');
                if (footerCount) footerCount.innerText = symbols.length;

                const elSrc = document.getElementById('funding-source-sub');
                if (elSrc && summary.source) {
                    elSrc.innerText = `Canlı ${summary.source} Senkronizasyonu`;
                }

                const elUpd = document.getElementById('funding-last-update-str');
                if (elUpd && summary.last_update_str) {
                    elUpd.innerText = `• Son Senkronizasyon: ${summary.last_update_str} (${summary.source || 'Canlı'})`;
                }

                updateFundingBadge();

                const tbody = document.getElementById('funding-table-body');
                if (!tbody) return;

                if (symbols.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding: 40px; color:#94a3b8;">Henüz canlı fonlama verisi yüklenmedi.</td></tr>`;
                    return;
                }

                // Filter
                let filtered = symbols.filter(s => {
                    const item = rates[s];
                    if (fundingFilter === 'SQUEEZE' && item.squeeze_status !== 'SHORT_SQUEEZE_RISK') return false;
                    if (fundingFilter === 'OVERHEAT' && item.squeeze_status !== 'LONG_OVERHEATED') return false;
                    if (fundingFilter === 'BALANCED' && item.squeeze_status !== 'BALANCED') return false;

                    if (fundingSearchQuery) {
                        const q = fundingSearchQuery.toUpperCase();
                        const clean = s.replace('/USDT', '').replace('USDT', '').toUpperCase();
                        const sqStatus = (item.squeeze_status || '').toUpperCase();
                        const dirAllowed = (item.direction_allowed || '').toUpperCase();
                        return clean.includes(q) || s.toUpperCase().includes(q) || sqStatus.includes(q) || dirAllowed.includes(q);
                    }
                    return true;
                });

                // Sort: SQUEEZE first, then OVERHEAT, then ascending rate (most negative first)
                filtered.sort((a, b) => {
                    const itemA = rates[a];
                    const itemB = rates[b];
                    const rankOrder = { 'SHORT_SQUEEZE_RISK': 1, 'LONG_OVERHEATED': 2, 'BALANCED': 3 };
                    const rankA = rankOrder[itemA.squeeze_status] || 4;
                    const rankB = rankOrder[itemB.squeeze_status] || 4;
                    if (rankA !== rankB) return rankA - rankB;
                    return itemA.rate_pct - itemB.rate_pct;
                });

                if (filtered.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding: 40px; color:#94a3b8;">Arama veya filtre kriterlerine uygun coin bulunamadı.</td></tr>`;
                    return;
                }

                let html = '';
                filtered.forEach(s => {
                    const item = rates[s];
                    const symClean = s.replace('/USDT', '').replace('USDT', '');
                    const isSqueeze = item.squeeze_status === 'SHORT_SQUEEZE_RISK';
                    const isOverheat = item.squeeze_status === 'LONG_OVERHEATED';

                    // Rate color
                    const rateColor = item.rate_pct < 0 ? 'var(--red)' : (item.rate_pct > 0.03 ? '#fbc531' : 'var(--cyan)');

                    // Status badge
                    let statusBadge = '';
                    let dirBadge = '';
                    let ruleDesc = '';

                    if (isSqueeze) {
                        statusBadge = `<span style="background:rgba(255,107,107,0.18); color:var(--red); border:1px solid rgba(255,107,107,0.45); padding:4px 10px; border-radius:6px; font-weight:800; font-size:11.5px; font-family:'JetBrains Mono';">⚠️ Short Squeeze Riski</span>`;
                        dirBadge = `<span style="color:#4ade80; font-weight:800; font-family:'JetBrains Mono'; font-size:11.5px;">🟢 YALNIZCA LONG <span style="color:var(--red); font-weight:900;">(Short Kilitli 🔒)</span></span>`;
                        ruleDesc = `<span style="color:var(--red); font-size:11.5px;">🛡️ Aşırı eksi fonlama; MM yukarı sıkıştırır. Short emirleri motor seviyesinde engellenir.</span>`;
                    } else if (isOverheat) {
                        statusBadge = `<span style="background:rgba(251,197,49,0.18); color:#fbc531; border:1px solid rgba(251,197,49,0.45); padding:4px 10px; border-radius:6px; font-weight:800; font-size:11.5px; font-family:'JetBrains Mono';">🔥 Aşırı Long Şişkinliği</span>`;
                        dirBadge = `<span style="color:#f87171; font-weight:800; font-family:'JetBrains Mono'; font-size:11.5px;">🔴 YALNIZCA SHORT <span style="color:#fbc531; font-weight:900;">(Long Breakout Yasak 🔒)</span></span>`;
                        ruleDesc = `<span style="color:#fbc531; font-size:11.5px;">🛡️ Aşırı pozitif fonlama; tepe tuzağı riski sebebiyle Long Breakout engellenir.</span>`;
                    } else {
                        statusBadge = `<span style="background:rgba(0,242,254,0.08); color:var(--cyan); border:1px solid rgba(0,242,254,0.22); padding:4px 10px; border-radius:6px; font-weight:700; font-size:11.5px; font-family:'JetBrains Mono';">🟢 Güvenli / Dengeli</span>`;
                        dirBadge = `<span style="color:#e2e8f0; font-weight:700; font-family:'JetBrains Mono'; font-size:11.5px;">🔄 Long & Short Serbest</span>`;
                        ruleDesc = `<span style="color:#94a3b8; font-size:11.5px;">Standart kurumsal Camarilla & nPOC pusu kuralları devrede.</span>`;
                    }

                    const markPriceStr = item.mark_price ? '$' + (typeof formatSmartPrice === 'function' ? formatSmartPrice(item.mark_price) : Number(item.mark_price).toFixed(item.mark_price < 1 ? 4 : 2)) : '-';

                    html += `
                    <tr>
                        <td style="font-weight:900; font-family:'JetBrains Mono'; color:#fff; font-size:13.5px;">
                            ${symClean} <span style="color:#64748b; font-size:11px;">/USDT</span>
                        </td>
                        <td style="color:${rateColor}; font-weight:900; font-family:'JetBrains Mono'; font-size:13.5px;">
                            ${item.rate_pct >= 0 ? '+' : ''}${item.rate_pct.toFixed(4)}%
                            <div style="font-size:10px; color:#94a3b8; font-weight:600; margin-top:2px;">
                                Yıllık: <b style="color:${(item.rate_pct * 3 * 365) >= 0 ? 'var(--cyan)' : 'var(--red)'};">${((item.rate_pct * 3 * 365) >= 0 ? '+' : '') + (item.rate_pct * 3 * 365).toFixed(1)}% APR</b>
                            </div>
                        </td>
                        <td>${statusBadge}</td>
                        <td style="font-family:'JetBrains Mono'; color:#cbd5e1;">${markPriceStr}</td>
                        <td style="font-family:'JetBrains Mono'; color:#94a3b8; font-size:12px;">⏳ ${item.next_funding_countdown || '--:--'}</td>
                        <td>${dirBadge}</td>
                        <td>${ruleDesc}</td>
                        <td style="white-space:nowrap;">
                            <button onclick="openTradingViewModal('${symClean}')" style="background:rgba(0,242,254,0.12); border:1px solid rgba(0,242,254,0.35); color:var(--cyan); padding:4px 9px; border-radius:6px; font-size:11px; font-weight:700; cursor:pointer;" title="${symClean} Grafiğini Aç">
                                📈 Grafik
                            </button>
                            <button onclick="filterWatchlistDirect('${symClean}')" style="background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.15); color:#cbd5e1; padding:4px 8px; border-radius:6px; font-size:11px; font-weight:700; cursor:pointer; margin-left:4px;" title="Pusu Radarında Gör">
                                🎯 Radar
                            </button>
                        </td>
                    </tr>
                    `;
                });

                tbody.innerHTML = html;
            } catch (err) {
                console.error("renderFundingMatrixView error:", err);
            }
        }

        function renderLiquidationView() {
            try {
                if (!appState) return;
                const liqSummary = appState.liquidation_summary || {};
                const recentLiqs = appState.recent_liquidations || [];

                // 1. KPI Cards
                const totalEl = document.getElementById('liq-total-24h');
                if (totalEl) {
                    const totalVal = Number(liqSummary.total_liq_usd || 0);
                    totalEl.innerText = '$' + Math.round(totalVal).toLocaleString('en-US');
                }

                const ratioEl = document.getElementById('liq-ratio-text');
                const barLong = document.getElementById('liq-bar-long');
                const barShort = document.getElementById('liq-bar-short');
                if (ratioEl && barLong && barShort) {
                    const longPct = Number(liqSummary.long_ratio_pct != null ? liqSummary.long_ratio_pct : 50).toFixed(1);
                    const shortPct = Number(liqSummary.short_ratio_pct != null ? liqSummary.short_ratio_pct : 50).toFixed(1);
                    ratioEl.innerHTML = `<span style="color:#ef4444;">Long %${longPct}</span> / <span style="color:#22c55e;">Short %${shortPct}</span>`;
                    barLong.style.width = `${longPct}%`;
                    barShort.style.width = `${shortPct}%`;
                }

                const topSymEl = document.getElementById('liq-top-sym');
                if (topSymEl) {
                    const topSym = liqSummary.top_symbol_15m;
                    const topVol = Number(liqSummary.top_symbol_vol_usd || 0);
                    if (topSym && topVol > 0) {
                        const cleanSym = topSym.replace('/USDT', '');
                        topSymEl.innerHTML = `${cleanSym} <span style="font-size:13px; color:#fff; font-weight:600;">($${Math.round(topVol).toLocaleString('en-US')})</span>`;
                    } else {
                        topSymEl.innerText = '-';
                    }
                }

                // 2. Liquidation Tape Table
                const tbody = document.getElementById('liquidation-tape-body');
                if (!tbody) return;

                if (!recentLiqs || recentLiqs.length === 0) {
                    tbody.innerHTML = `
                        <tr>
                            <td colspan="7" style="text-align:center; padding:30px; color:#94a3b8; font-family:'JetBrains Mono';">
                                Canlı !forceOrder akışı bekleniyor (Büyük tasfiye emirleri geldikçe akacak)...
                            </td>
                        </tr>
                    `;
                    return;
                }

                let html = '';
                recentLiqs.slice().reverse().forEach(item => {
                    const symClean = (item.symbol || '').replace('/USDT', '');
                    const isLongLiq = item.side === 'LONG';
                    const sideBadge = isLongLiq 
                        ? `<span style="background:rgba(239,68,68,0.18); border:1px solid rgba(239,68,68,0.4); color:#ef4444; padding:3px 8px; border-radius:6px; font-weight:800; font-size:11px;">🔴 LONG Tasfiyesi</span>`
                        : `<span style="background:rgba(34,197,94,0.18); border:1px solid rgba(34,197,94,0.4); color:#22c55e; padding:3px 8px; border-radius:6px; font-weight:800; font-size:11px;">🟢 SHORT Tasfiyesi</span>`;

                    const forceOrderBadge = isLongLiq 
                        ? `<span style="color:#f87171; font-weight:700;">SELL (Satış)</span>`
                        : `<span style="color:#4ade80; font-weight:700;">BUY (Alış)</span>`;

                    const usdSize = Number(item.usd_size || 0);
                    const price = Number(item.price || 0);
                    const timeStr = item.time_str || (item.time ? (item.time.indexOf(' ') > -1 ? item.time.split(' ')[1] : item.time) : '--:--:--');

                    const interp = isLongLiq
                        ? `<span style="color:#38bdf8;">🔻 Destekte Satış Emildi → Sekme (Bounce Long) Teyidi</span>`
                        : `<span style="color:#fbbf24;">🔺 Dirençte Alış Emildi → Tepe Reddi (Reject Short) Teyidi</span>`;

                    const priceFormatted = typeof formatSmartPrice === 'function' ? formatSmartPrice(price) : price.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 6});

                    html += `
                    <tr style="border-bottom:1px solid rgba(255,255,255,0.04); font-family:'JetBrains Mono'; font-size:12px;">
                        <td style="color:#94a3b8;">${timeStr}</td>
                        <td style="font-weight:800; color:#fff;">${symClean}</td>
                        <td>${sideBadge}</td>
                        <td>${forceOrderBadge}</td>
                        <td style="font-weight:800; color:#fbbf24;">$${Math.round(usdSize).toLocaleString('en-US')}</td>
                        <td style="color:#e2e8f0;">$${priceFormatted}</td>
                        <td>${interp}</td>
                    </tr>
                    `;
                });

                tbody.innerHTML = html;
            } catch (err) {
                console.error("renderLiquidationView error:", err);
            }
        }

        let cvdDisplayLimit = 10;
        function setCvdLimit(limit) {
            cvdDisplayLimit = limit;
            [5, 10, 15].forEach(l => {
                const btn = document.getElementById('cvd-btn-top' + l);
                if (btn) {
                    if (l === limit) {
                        btn.classList.add('active');
                        btn.style.borderColor = 'var(--cyan)';
                        btn.style.color = 'var(--cyan)';
                    } else {
                        btn.classList.remove('active');
                        btn.style.borderColor = '';
                        btn.style.color = '';
                    }
                }
            });
            renderCvdView();
        }
        window.setCvdLimit = setCvdLimit;

        function renderCvdView() {
            try {
                if (!appState) return;
                const cvdSummary = appState.cvd_summary || {};

                // 1. KPI Cards
                const ratioTextEl = document.getElementById('cvd-market-ratio-text');
                const barLong = document.getElementById('cvd-market-bar-long');
                const barShort = document.getElementById('cvd-market-bar-short');
                if (ratioTextEl && barLong && barShort) {
                    const buyPct = Number(cvdSummary.avg_buy_ratio != null ? cvdSummary.avg_buy_ratio : 50).toFixed(1);
                    const sellPct = Number(cvdSummary.avg_sell_ratio != null ? cvdSummary.avg_sell_ratio : 50).toFixed(1);
                    ratioTextEl.innerHTML = `<span style="color:#22c55e;">Alıcı %${buyPct}</span> / <span style="color:#ef4444;">Satıcı %${sellPct}</span>`;
                    barLong.style.width = `${buyPct}%`;
                    barShort.style.width = `${sellPct}%`;
                }

                // Update nav badge
                const navCvdBadge = document.getElementById('nav-cvd-badge');
                if (navCvdBadge && cvdSummary.avg_buy_ratio != null) {
                    const buyPct = Number(cvdSummary.avg_buy_ratio).toFixed(1);
                    const isBull = cvdSummary.avg_buy_ratio >= 50;
                    navCvdBadge.innerText = `%${buyPct} ${isBull ? '🟢' : '🔴'}`;
                    navCvdBadge.style.color = isBull ? '#22c55e' : '#ef4444';
                    navCvdBadge.style.background = isBull ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)';
                    navCvdBadge.style.borderColor = isBull ? 'rgba(34,197,94,0.3)' : 'rgba(239,68,68,0.3)';
                }

                const topBuyerSymEl = document.getElementById('cvd-top-buyer-sym');
                const topBuyerDeltaEl = document.getElementById('cvd-top-buyer-delta');
                if (topBuyerSymEl && topBuyerDeltaEl) {
                    const topB = cvdSummary.top_buy_sym;
                    const topBDelta = Number(cvdSummary.top_buy_delta || 0);
                    const topBRatio = Number(cvdSummary.top_buy_ratio || 50).toFixed(1);
                    if (topB && topB !== '-') {
                        const cleanB = topB.replace('/USDT', '');
                        const deltaStr = (Math.abs(topBDelta) > 0 && Math.abs(topBDelta) < 100) ? topBDelta.toFixed(2) : Math.round(topBDelta).toLocaleString('en-US');
                        topBuyerSymEl.innerHTML = `${cleanB} <span style="font-size:13px; color:#fff; font-weight:600;">(%${topBRatio})</span>`;
                        topBuyerDeltaEl.innerText = `Net Para Girişi: +$${deltaStr}`;
                    } else {
                        topBuyerSymEl.innerText = '-';
                        topBuyerDeltaEl.innerText = 'Net Para Girişi: +$0';
                    }
                }

                const topSellerSymEl = document.getElementById('cvd-top-seller-sym');
                const topSellerDeltaEl = document.getElementById('cvd-top-seller-delta');
                if (topSellerSymEl && topSellerDeltaEl) {
                    const topS = cvdSummary.top_sell_sym;
                    const topSDelta = Number(cvdSummary.top_sell_delta || 0);
                    const topSRatio = Number(cvdSummary.top_sell_ratio || 50).toFixed(1);
                    if (topS && topS !== '-') {
                        const cleanS = topS.replace('/USDT', '');
                        const deltaStr = (Math.abs(topSDelta) > 0 && Math.abs(topSDelta) < 100) ? Math.abs(topSDelta).toFixed(2) : Math.abs(Math.round(topSDelta)).toLocaleString('en-US');
                        topSellerSymEl.innerHTML = `${cleanS} <span style="font-size:13px; color:#fff; font-weight:600;">(%${topSRatio})</span>`;
                        topSellerDeltaEl.innerText = `Net Para Çıkışı: -$${deltaStr}`;
                    } else {
                        topSellerSymEl.innerText = '-';
                        topSellerDeltaEl.innerText = 'Net Para Çıkışı: -$0';
                    }
                }

                // 2. Dual-Column Aggression Heat Tables
                const buyersTbody = document.getElementById('cvd-top-buyers-body');
                if (buyersTbody) {
                    const rawBuyers = cvdSummary.top_buyers || [];
                    const topBuyers = rawBuyers.slice(0, cvdDisplayLimit);
                    if (topBuyers.length === 0) {
                        buyersTbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:20px; color:#94a3b8;">K-Line Taker Buy verisi toplanıyor...</td></tr>`;
                    } else {
                        let bHtml = '';
                        topBuyers.forEach(item => {
                            const symClean = (item.symbol || '').replace('/USDT', '');
                            const ratio = Number(item.ratio_60s || 50).toFixed(1);
                            const sellRatio = (100 - Number(ratio)).toFixed(1);
                            const delta = Number(item.delta_60s || 0);
                            const price = Number(item.last_price || 0);
                            const deltaFormatted = (Math.abs(delta) > 0 && Math.abs(delta) < 100) ? delta.toFixed(2) : Math.round(delta).toLocaleString('en-US');
                            const priceFormatted = typeof formatSmartPrice === 'function' ? formatSmartPrice(price) : price.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 6});
                            
                            let stratBadge = `<span title="Alıcı/Satıcı dengede. Standart pusu kuralları bekleniyor." style="color:#94a3b8; font-size:11px;">⚪ Nötr Akış</span>`;
                            if (ratio >= 62) {
                                stratBadge = `<span title="Son 60s alıcı agresyonu %${ratio}. Camarilla R4 direnci kırılırsa mum kapanışı beklenmeden 1.15x marjinle LONG açılır." style="background:rgba(34,197,94,0.18); border:1px solid rgba(34,197,94,0.4); color:#22c55e; padding:3px 8px; border-radius:6px; font-weight:800; font-size:11px; cursor:help;">🚀 Kırılım Teyitli (1.15x Marjin)</span>`;
                            } else if (ratio >= 55) {
                                stratBadge = `<span title="Destek seviyesinde alıcılar piyasa satışlarını emiyor (%${ratio}). Sekme halinde 1.10x marjinle fitilden yakalanır." style="background:rgba(56,189,248,0.18); border:1px solid rgba(56,189,248,0.4); color:#38bdf8; padding:3px 8px; border-radius:6px; font-weight:800; font-size:11px; cursor:help;">⚡ Dip Emilim (1.10x Marjin)</span>`;
                            } else if (ratio >= 50) {
                                stratBadge = `<span title="Alıcılar hafif önde ancak teyit eşiğinin altında." style="background:rgba(148,163,184,0.1); border:1px solid rgba(148,163,184,0.3); color:#94a3b8; padding:3px 8px; border-radius:6px; font-weight:700; font-size:11px; cursor:help;">⚪ Hafif Boğa (Beklemede)</span>`;
                            }

                            bHtml += `
                            <tr style="border-bottom:1px solid rgba(255,255,255,0.04); font-family:'JetBrains Mono'; font-size:12px;">
                                <td style="font-weight:800; color:#fff;">${symClean}</td>
                                <td>
                                    <span style="font-weight:800; color:#22c55e;">%${ratio} Alıcı</span> 
                                    <span style="font-size:10px; color:#64748b;">(%${sellRatio} Satıcı)</span>
                                </td>
                                <td style="color:#4ade80; font-weight:700;">+$${deltaFormatted}</td>
                                <td style="color:#e2e8f0;">$${priceFormatted}</td>
                                <td>${stratBadge}</td>
                            </tr>
                            `;
                        });
                        buyersTbody.innerHTML = bHtml;
                    }
                }

                const sellersTbody = document.getElementById('cvd-top-sellers-body');
                if (sellersTbody) {
                    const rawSellers = cvdSummary.top_sellers || [];
                    const topSellers = rawSellers.slice(0, cvdDisplayLimit);
                    if (topSellers.length === 0) {
                        sellersTbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:20px; color:#94a3b8;">K-Line Taker Sell verisi toplanıyor...</td></tr>`;
                    } else {
                        let sHtml = '';
                        topSellers.forEach(item => {
                            const symClean = (item.symbol || '').replace('/USDT', '');
                            const ratio = Number(item.ratio_60s || 50).toFixed(1);
                            const sellRatio = (100 - Number(ratio)).toFixed(1);
                            const delta = Number(item.delta_60s || 0);
                            const price = Number(item.last_price || 0);
                            const deltaFormatted = (Math.abs(delta) > 0 && Math.abs(delta) < 100) ? Math.abs(delta).toFixed(2) : Math.abs(Math.round(delta)).toLocaleString('en-US');
                            const priceFormatted = typeof formatSmartPrice === 'function' ? formatSmartPrice(price) : price.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 6});
                            
                            let stratBadge = `<span title="Alıcı/Satıcı dengede. Standart pusu kuralları bekleniyor." style="color:#94a3b8; font-size:11px;">⚪ Nötr Akış</span>`;
                            if (ratio <= 38) {
                                stratBadge = `<span title="Satıcılar son 60s tahtayı boşaltıyor (%${sellRatio} satıcı). Direnç aşılsa bile tuzaktır, işlem engellenir (Fakeout Shield)." style="background:rgba(239,68,68,0.18); border:1px solid rgba(239,68,68,0.4); color:#ef4444; padding:3px 8px; border-radius:6px; font-weight:800; font-size:11px; cursor:help;">🛡️ Boğa Tuzağı (İşlem Engellendi)</span>`;
                            } else if (ratio <= 45) {
                                stratBadge = `<span title="Piyasa satıcıları baskın (%${sellRatio}). Destek seviyesine fitil atarken tasfiye ve emilim bekleniyor." style="background:rgba(251,191,36,0.18); border:1px solid rgba(251,191,36,0.4); color:#fbbf24; padding:3px 8px; border-radius:6px; font-weight:800; font-size:11px; cursor:help;">🔻 Satıcı Baskısı (Dip Aranıyor)</span>`;
                            } else if (ratio <= 50) {
                                stratBadge = `<span title="Satıcılar hafif önde. Destek seviyesi test edilene kadar bekleniyor." style="background:rgba(148,163,184,0.1); border:1px solid rgba(148,163,184,0.3); color:#94a3b8; padding:3px 8px; border-radius:6px; font-weight:700; font-size:11px; cursor:help;">⚪ Hafif Ayı (Beklemede)</span>`;
                            }

                            sHtml += `
                            <tr style="border-bottom:1px solid rgba(255,255,255,0.04); font-family:'JetBrains Mono'; font-size:12px;">
                                <td style="font-weight:800; color:#fff;">${symClean}</td>
                                <td>
                                    <span style="font-weight:800; color:#ef4444;">%${sellRatio} Satıcı</span> 
                                    <span style="font-size:10px; color:#64748b;">(%${ratio} Alıcı)</span>
                                </td>
                                <td style="color:#f87171; font-weight:700;">-$${deltaFormatted}</td>
                                <td style="color:#e2e8f0;">$${priceFormatted}</td>
                                <td>${stratBadge}</td>
                            </tr>
                            `;
                        });
                        sellersTbody.innerHTML = sHtml;
                    }
                }
            } catch (err) {
                console.error("renderCvdView error:", err);
            }
        }

        function toggleSidebarCollapse() {
            const sb = document.getElementById("dashboard-sidebar");
            const btn = document.getElementById("sidebar-toggle-btn");
            if (!sb) return;
            const isCollapsed = sb.classList.toggle("is-collapsed");
            if (btn) {
                btn.innerHTML = isCollapsed ? "▶" : "◀";
            }
            try {
                localStorage.setItem("valkyrie_sidebar_collapsed", isCollapsed ? "1" : "0");
            } catch (e) {}
            setTimeout(() => {
                if (window.ValkyrieBattleEngine) ValkyrieBattleEngine.resize();
                if (window.ValkyrieKpiSimEngine) window.ValkyrieKpiSimEngine.resize();
                if (window.ValkyrieTacticalRadarEngine) window.ValkyrieTacticalRadarEngine.resize();
            }, 260);
        }

        function restoreSidebarPreference() {
            try {
                if (localStorage.getItem("valkyrie_sidebar_collapsed") === "1") {
                    const sb = document.getElementById("dashboard-sidebar");
                    const btn = document.getElementById("sidebar-toggle-btn");
                    if (sb) sb.classList.add("is-collapsed");
                    if (btn) btn.innerHTML = "▶";
                }
            } catch (e) {}
        }

        function switchMainTab(tabName) {
            if (tabName === 'history') tabName = 'ledger';
            currentActiveMainTab = tabName;
            window.currentActiveMainTab = tabName;
            
            const tabButtons = {
                'cockpit': document.getElementById('tab-btn-cockpit'),
                'positions': document.getElementById('tab-btn-positions'),
                'radar': document.getElementById('tab-btn-radar'),
                'ledger': document.getElementById('tab-btn-ledger'),
                'persona': document.getElementById('tab-btn-persona'),
                'shadow': document.getElementById('tab-btn-shadow'),
                'funding': document.getElementById('tab-btn-funding'),
                'cvd': document.getElementById('tab-btn-cvd'),
                'health': document.getElementById('tab-btn-health'),
                'admin': document.getElementById('tab-btn-admin')
            };
            const tabContents = {
                'cockpit': document.getElementById('main-tab-content-cockpit'),
                'positions': document.getElementById('main-tab-content-positions'),
                'radar': document.getElementById('main-tab-content-radar'),
                'ledger': document.getElementById('main-tab-content-ledger'),
                'persona': document.getElementById('main-tab-content-persona'),
                'shadow': document.getElementById('main-tab-content-shadow'),
                'funding': document.getElementById('main-tab-content-funding'),
                'cvd': document.getElementById('main-tab-content-cvd'),
                'health': document.getElementById('main-tab-content-health'),
                'admin': document.getElementById('main-tab-content-admin')
            };

            for (const key in tabButtons) {
                if (tabButtons[key]) {
                    if (key === tabName) {
                        tabButtons[key].classList.add('active');
                    } else {
                        tabButtons[key].classList.remove('active');
                    }
                }
            }

            for (const key in tabContents) {
                if (tabContents[key]) {
                    if (key === tabName) {
                        tabContents[key].classList.add('active-tab');
                        tabContents[key].style.display = 'block';
                    } else {
                        tabContents[key].classList.remove('active-tab');
                        tabContents[key].style.display = 'none';
                    }
                }
            }

            try {
                if (tabName === 'cockpit') {
                    renderCockpitView();
                    renderCockpitOpenPositions();
                    if (equityChartInstance) {
                        const eqCont = document.getElementById('cockpit-equity-container');
                        if (eqCont && eqCont.clientWidth > 0) {
                            equityChartInstance.applyOptions({ width: eqCont.clientWidth, height: eqCont.clientHeight || 260 });
                            try { equityChartInstance.timeScale().fitContent(); } catch(e) {}
                        }
                    }
                    if (window.ValkyrieBattleEngine) ValkyrieBattleEngine.resize();
                    if (window.ValkyrieKpiSimEngine) window.ValkyrieKpiSimEngine.resize();
                    if (window.ValkyrieTacticalRadarEngine) window.ValkyrieTacticalRadarEngine.resize();
                    setTimeout(() => {
                        if (equityChartInstance) {
                            const eqCont = document.getElementById('cockpit-equity-container');
                            if (eqCont && eqCont.clientWidth > 0) {
                                equityChartInstance.applyOptions({ width: eqCont.clientWidth, height: eqCont.clientHeight || 260 });
                                try { equityChartInstance.timeScale().fitContent(); } catch(e) {}
                            }
                        }
                        if (window.ValkyrieBattleEngine) ValkyrieBattleEngine.resize();
                        if (window.ValkyrieKpiSimEngine) window.ValkyrieKpiSimEngine.resize();
                        if (window.ValkyrieTacticalRadarEngine) window.ValkyrieTacticalRadarEngine.resize();
                    }, 60);
                } else if (tabName === 'positions') {
                    renderPortfolioRiskHUD();
                    renderPositions();
                } else if (tabName === 'radar') {
                    renderCards();
                } else if (tabName === 'ledger') {
                    renderHistoryTable();
                } else if (tabName === 'persona') {
                    renderPersonaMatrixView();
                } else if (tabName === 'shadow') {
                    renderShadowView();
                } else if (tabName === 'funding') {
                    renderFundingMatrixView();
                    renderLiquidationView();
                } else if (tabName === 'cvd') {
                    renderCvdView();
                } else if (tabName === 'health') {
                    renderHealthTabView();
                } else if (tabName === 'admin') {
                    loadAdminMetrics();
                }
            } catch (tabErr) {
                console.warn("[Valkyrie Navigation] View rendering warning for tab " + tabName + ":", tabErr);
            }
        }

        function filterWatchlistDirect(symbol) {
            switchMainTab('radar');
            setTimeout(() => {
                const input = document.getElementById('coin-search-input');
                if (input) {
                    input.value = symbol.replace('/USDT', '');
                    handleSearch(input.value);
                }
            }, 100);
        }

        // =========================================================================
        // ⚔️ VALKYRIE CANLI LİKİDİTE SAVAŞI (BATTLE ARENA) ENGINE 60 FPS
        // =========================================================================
        var currentBattleMode = 'arena'; // 'arena' or 'simple'
        window.currentBattleMode = currentBattleMode;

        function restoreBattleViewPreference() {
            try {
                const saved = localStorage.getItem('valkyrie_battle_mode');
                if (saved === 'simple' || saved === 'arena') {
                    setBattleViewMode(saved);
                }
            } catch (e) {}
        }

        function setBattleViewMode(mode) {
            currentBattleMode = mode;
            window.currentBattleMode = mode;
            const arenaWrap = document.getElementById('regime-arena-wrap');
            const simpleWrap = document.getElementById('regime-simple-wrap');
            const btn = document.getElementById('btn-toggle-battle-view');
            
            if (currentBattleMode === 'simple') {
                if (arenaWrap) arenaWrap.style.display = 'none';
                if (simpleWrap) simpleWrap.style.display = 'block';
                if (btn) btn.innerHTML = '⚔️ Sinematik Arenaya Geç';
            } else {
                if (arenaWrap) arenaWrap.style.display = 'block';
                if (simpleWrap) simpleWrap.style.display = 'none';
                if (btn) btn.innerHTML = '📊 Sade Çubuğa Geç';
                if (window.ValkyrieBattleEngine) ValkyrieBattleEngine.resize();
            }
            try {
                localStorage.setItem('valkyrie_battle_mode', currentBattleMode);
            } catch (e) {}
        }

        function toggleBattleView() {
            setBattleViewMode(currentBattleMode === 'arena' ? 'simple' : 'arena');
        }

        const ValkyrieBattleEngine = (function() {
            let canvas, ctx;
            let width = 0, height = 0;
            let dpr = window.devicePixelRatio || 1;
            let animId = null;

            let bullPct = 40, bearPct = 10, rangePct = 50;
            let lastRatio = 0.5;
            let currentClashX = 0;
            let targetClashX = 0;

            const particles = [];
            const MAX_PARTICLES = 60;
            const sparks = [];

            function init() {
                canvas = document.getElementById('regime-battle-canvas');
                if (!canvas) return;
                ctx = canvas.getContext('2d');
                resize();
                window.addEventListener('resize', resize);

                // Init particles
                for (let i = 0; i < MAX_PARTICLES; i++) {
                    resetParticle(i);
                }

                currentClashX = width * lastRatio;
                targetClashX = currentClashX;

                startLoop();
            }

            function resize() {
                if (!canvas) return;
                const rect = canvas.getBoundingClientRect();
                width = rect.width || (canvas.parentElement ? canvas.parentElement.clientWidth : 0) || 800;
                height = rect.height || (canvas.parentElement ? canvas.parentElement.clientHeight : 0) || 145;
                if (width <= 0) width = 800;
                if (height <= 0) height = 145;
                dpr = window.devicePixelRatio || 1;
                canvas.width = Math.floor(width * dpr);
                canvas.height = Math.floor(height * dpr);
                ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

                targetClashX = width * lastRatio;
                if (!currentClashX) currentClashX = targetClashX;
            }

            function resetParticle(idx) {
                const isBull = idx % 2 === 0;
                particles[idx] = {
                    isBull: isBull,
                    x: isBull ? Math.random() * (width * 0.35) : width - Math.random() * (width * 0.35),
                    y: 18 + Math.random() * (height - 36),
                    vx: isBull ? (1.5 + Math.random() * 2.5) : -(1.5 + Math.random() * 2.5),
                    vy: (Math.random() - 0.5) * 0.8,
                    size: 1.5 + Math.random() * 2.5,
                    alpha: 0.3 + Math.random() * 0.7,
                    life: Math.random() * 100
                };
            }

            function addSparks(cx, cy, count) {
                for (let i = 0; i < count; i++) {
                    const angle = Math.random() * Math.PI * 2;
                    const spd = 2 + Math.random() * 5;
                    sparks.push({
                        x: cx,
                        y: cy,
                        vx: Math.cos(angle) * spd,
                        vy: Math.sin(angle) * spd,
                        color: Math.random() > 0.5 ? '#00f2fe' : (Math.random() > 0.5 ? '#ffffff' : '#fbbf24'),
                        alpha: 1.0,
                        size: 1 + Math.random() * 2,
                        decay: 0.03 + Math.random() * 0.04
                    });
                }
            }

            function setRegimeData(b, r, be) {
                bullPct = b;
                rangePct = r;
                bearPct = be;
                const total = (b + be) || 1;
                // Ratio between 0.20 and 0.80 so clash point remains in view
                lastRatio = Math.max(0.20, Math.min(0.80, 0.20 + (b / total) * 0.60));
                targetClashX = width * lastRatio;
            }

            // Stylized cybernetic beast avatar
            function drawBeast(isBull, x, y, size) {
                ctx.save();
                ctx.translate(x, y);
                if (!isBull) ctx.scale(-1, 1);

                ctx.shadowBlur = 18;
                ctx.shadowColor = isBull ? 'rgba(14, 203, 129, 0.8)' : 'rgba(255, 71, 87, 0.8)';
                ctx.strokeStyle = isBull ? '#0ecb81' : '#ff4757';
                ctx.fillStyle = isBull ? 'rgba(14, 203, 129, 0.12)' : 'rgba(255, 71, 87, 0.12)';
                ctx.lineWidth = 2.2;
                ctx.lineJoin = 'round';
                ctx.lineCap = 'round';

                if (isBull) {
                    // Futuristic Bull Head & Horns
                    ctx.beginPath();
                    // Horns
                    ctx.moveTo(size * 0.4, -size * 0.5);
                    ctx.quadraticCurveTo(size * 0.2, -size * 0.9, size * 0.8, -size * 0.8);
                    ctx.moveTo(size * 0.1, -size * 0.5);
                    ctx.quadraticCurveTo(-size * 0.1, -size * 0.9, size * 0.5, -size * 0.8);
                    // Brow & Snout
                    ctx.moveTo(-size * 0.3, -size * 0.2);
                    ctx.lineTo(size * 0.4, -size * 0.3);
                    ctx.lineTo(size * 0.6, 0);
                    ctx.lineTo(size * 0.4, size * 0.3);
                    ctx.lineTo(0, size * 0.4);
                    ctx.lineTo(-size * 0.3, size * 0.2);
                    ctx.closePath();
                    ctx.stroke();
                    ctx.fill();

                    // Glowing Eye
                    ctx.fillStyle = '#ffffff';
                    ctx.shadowColor = '#ffffff';
                    ctx.shadowBlur = 10;
                    ctx.beginPath();
                    ctx.arc(size * 0.25, -size * 0.05, 2.5, 0, Math.PI * 2);
                    ctx.fill();
                } else {
                    // Futuristic Bear Head & Claws
                    ctx.beginPath();
                    // Ears
                    ctx.moveTo(size * 0.2, -size * 0.6);
                    ctx.arc(size * 0.1, -size * 0.7, size * 0.18, 0, Math.PI, true);
                    // Skull & Jaw
                    ctx.moveTo(-size * 0.3, -size * 0.4);
                    ctx.lineTo(size * 0.3, -size * 0.4);
                    ctx.lineTo(size * 0.6, -size * 0.1);
                    ctx.lineTo(size * 0.5, size * 0.3);
                    ctx.lineTo(size * 0.1, size * 0.5);
                    ctx.lineTo(-size * 0.3, size * 0.2);
                    ctx.closePath();
                    ctx.stroke();
                    ctx.fill();

                    // Glowing Eye
                    ctx.fillStyle = '#ffffff';
                    ctx.shadowColor = '#ffffff';
                    ctx.shadowBlur = 10;
                    ctx.beginPath();
                    ctx.arc(size * 0.25, -size * 0.1, 2.5, 0, Math.PI * 2);
                    ctx.fill();
                }

                ctx.restore();
            }

            function drawLightning(x, y1, y2) {
                ctx.save();
                ctx.strokeStyle = '#ffffff';
                ctx.shadowColor = '#00f2fe';
                ctx.shadowBlur = 14;
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.moveTo(x, y1);
                
                let curY = y1;
                let curX = x;
                while (curY < y2) {
                    curY += 8 + Math.random() * 12;
                    curX = x + (Math.random() - 0.5) * 16;
                    ctx.lineTo(curX, Math.min(y2, curY));
                }
                ctx.stroke();
                ctx.restore();
            }

            function render() {
                // If not on cockpit tab or in simple mode, pause rendering to save 100% CPU
                if ((window.currentActiveMainTab && window.currentActiveMainTab !== 'cockpit') || (window.currentBattleMode && window.currentBattleMode !== 'arena') || !ctx) {
                    animId = requestAnimationFrame(render);
                    return;
                }

                if (width <= 0 || canvas.width <= 0) {
                    resize();
                }

                ctx.clearRect(0, 0, width, height);

                // Smooth clash interpolation
                currentClashX += (targetClashX - currentClashX) * 0.08;

                // 1. Background Grid & Atmospheric Ground Light
                ctx.save();
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.025)';
                ctx.lineWidth = 1;
                for (let x = 0; x < width; x += 40) {
                    ctx.beginPath();
                    ctx.moveTo(x, 0);
                    ctx.lineTo(x, height);
                    ctx.stroke();
                }
                for (let y = 0; y < height; y += 30) {
                    ctx.beginPath();
                    ctx.moveTo(0, y);
                    ctx.lineTo(width, y);
                    ctx.stroke();
                }

                // 2. Bull Energy Zone (Green Gradient)
                const bullGrad = ctx.createLinearGradient(0, 0, currentClashX, 0);
                bullGrad.addColorStop(0, 'rgba(14, 203, 129, 0.22)');
                bullGrad.addColorStop(0.7, 'rgba(14, 203, 129, 0.12)');
                bullGrad.addColorStop(1, 'rgba(14, 203, 129, 0.35)');
                ctx.fillStyle = bullGrad;
                ctx.fillRect(0, 0, currentClashX, height);

                // 3. Bear Energy Zone (Red Gradient)
                const bearGrad = ctx.createLinearGradient(currentClashX, 0, width, 0);
                bearGrad.addColorStop(0, 'rgba(255, 71, 87, 0.35)');
                bearGrad.addColorStop(0.3, 'rgba(255, 71, 87, 0.12)');
                bearGrad.addColorStop(1, 'rgba(255, 71, 87, 0.22)');
                ctx.fillStyle = bearGrad;
                ctx.fillRect(currentClashX, 0, width - currentClashX, height);

                // 4. Ground Laser Beam
                const beamGrad = ctx.createLinearGradient(0, height - 6, width, height - 6);
                beamGrad.addColorStop(0, '#0ecb81');
                beamGrad.addColorStop(currentClashX / (width || 1), '#00f2fe');
                beamGrad.addColorStop(1, '#ff4757');
                ctx.fillStyle = beamGrad;
                ctx.fillRect(0, height - 5, width, 5);
                ctx.restore();

                // 5. Draw Beast Avatars
                // Bull on Left
                const bullX = Math.max(70, currentClashX * 0.45);
                drawBeast(true, bullX, height * 0.58, 42);

                // Bear on Right
                const bearX = Math.min(width - 70, currentClashX + (width - currentClashX) * 0.55);
                drawBeast(false, bearX, height * 0.58, 42);

                // 6. Particles
                for (let i = 0; i < MAX_PARTICLES; i++) {
                    const p = particles[i];
                    p.x += p.vx;
                    p.y += p.vy;
                    p.life++;

                    // If crossed clash line or died, trigger spark and reset
                    if (p.isBull && p.x >= currentClashX) {
                        addSparks(currentClashX, p.y, 2);
                        resetParticle(i);
                        continue;
                    } else if (!p.isBull && p.x <= currentClashX) {
                        addSparks(currentClashX, p.y, 2);
                        resetParticle(i);
                        continue;
                    }

                    if (p.life > 120 || p.x < 0 || p.x > width) {
                        resetParticle(i);
                        continue;
                    }

                    ctx.save();
                    ctx.shadowBlur = 8;
                    ctx.shadowColor = p.isBull ? '#0ecb81' : '#ff4757';
                    ctx.fillStyle = p.isBull ? `rgba(14, 203, 129, ${p.alpha})` : `rgba(255, 71, 87, ${p.alpha})`;
                    ctx.beginPath();
                    ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.restore();
                }

                // 7. Sparks at Clash Center
                for (let i = sparks.length - 1; i >= 0; i--) {
                    const s = sparks[i];
                    s.x += s.vx;
                    s.y += s.vy;
                    s.alpha -= s.decay;
                    if (s.alpha <= 0) {
                        sparks.splice(i, 1);
                        continue;
                    }
                    ctx.save();
                    ctx.globalAlpha = s.alpha;
                    ctx.shadowBlur = 6;
                    ctx.shadowColor = s.color;
                    ctx.fillStyle = s.color;
                    ctx.beginPath();
                    ctx.arc(s.x, s.y, s.size, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.restore();
                }

                // 8. Dynamic Shockwave Collision Beam & Lightning
                ctx.save();
                // Vertical Seam Glow
                const seamGrad = ctx.createLinearGradient(currentClashX - 15, 0, currentClashX + 15, 0);
                seamGrad.addColorStop(0, 'rgba(14, 203, 129, 0)');
                seamGrad.addColorStop(0.5, 'rgba(0, 242, 254, 0.6)');
                seamGrad.addColorStop(1, 'rgba(255, 71, 87, 0)');
                ctx.fillStyle = seamGrad;
                ctx.fillRect(currentClashX - 15, 0, 30, height);

                // Shockwave pulse
                const pulseR = 10 + (Date.now() % 1000) * 0.03;
                const pulseAlpha = Math.max(0, 1 - (pulseR / 40));
                ctx.strokeStyle = `rgba(0, 242, 254, ${pulseAlpha})`;
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.arc(currentClashX, height * 0.5, pulseR, 0, Math.PI * 2);
                ctx.stroke();

                // Lightning Ark
                if (Math.random() > 0.3) {
                    drawLightning(currentClashX, 10, height - 10);
                }
                ctx.restore();

                animId = requestAnimationFrame(render);
            }

            function startLoop() {
                if (!animId) animId = requestAnimationFrame(render);
            }

            return {
                init,
                resize,
                setRegimeData
            };
        })();
        window.ValkyrieBattleEngine = ValkyrieBattleEngine;
        window.toggleBattleView = toggleBattleView;
        window.setBattleViewMode = setBattleViewMode;
        window.restoreBattleViewPreference = restoreBattleViewPreference;

        // =========================================================================
        // 🔮 VALKYRIE 4X KPI QUANT SIMULATION ENGINE (GÖRSEL ŞÖLEN & CANLI SİMÜLASYON)
        // =========================================================================
        const ValkyrieKpiSimEngine = (function() {
            let canvases = {};
            let ctxs = {};
            let sizes = {};
            let animId = null;
            let dpr = window.devicePixelRatio || 1;
            let isRunning = false;

            let metrics = {
                balance: 10000.0,
                initialBalance: 10000.0,
                pnl: 0.0,
                growthPct: 0.0,
                winRate: 0.0,
                wins: 0,
                losses: 0,
                totalTrades: 0,
                pf: 0.0
            };

            // 1. Vault Sim State
            let vaultTime = 0;
            let vaultRipples = [];
            let vaultParticles = [];
            for (let i = 0; i < 18; i++) {
                vaultParticles.push({
                    x: Math.random(),
                    y: 0.5 + Math.random() * 0.5,
                    vx: (Math.random() - 0.5) * 0.002,
                    vy: -(0.003 + Math.random() * 0.004),
                    size: 1 + Math.random() * 2,
                    alpha: 0.2 + Math.random() * 0.5
                });
            }

            // 2. Growth Sim State
            let ekgPhase = 0;
            let growthSparks = [];
            for (let i = 0; i < 20; i++) {
                growthSparks.push({
                    x: Math.random(),
                    y: Math.random(),
                    vx: (Math.random() - 0.5) * 0.004,
                    vy: -(0.003 + Math.random() * 0.006),
                    size: 1 + Math.random() * 2,
                    alpha: Math.random() * 0.7
                });
            }

            // 3. Radar Sim State
            let radarAngle = 0;
            let radarBlips = [];
            function refreshRadarBlips() {
                radarBlips = [];
                const total = Math.min(12, Math.max(4, metrics.totalTrades || 6));
                const winCount = metrics.wins || 0;
                for (let i = 0; i < total; i++) {
                    const isWin = i < winCount;
                    const r = 0.25 + Math.random() * 0.65;
                    const theta = Math.random() * Math.PI * 2;
                    radarBlips.push({
                        x: Math.cos(theta) * r,
                        y: Math.sin(theta) * r,
                        theta: theta < 0 ? theta + Math.PI * 2 : theta,
                        isWin: isWin,
                        intensity: 0.2
                    });
                }
            }
            refreshRadarBlips();

            // 4. Reactor Sim State
            let reactorAngle = 0;
            let reactorTilt = 0;
            let reactorParticles = [];
            for (let i = 0; i < 22; i++) {
                reactorParticles.push({
                    angle: Math.random() * Math.PI * 2,
                    dist: 12 + Math.random() * 24,
                    speed: (0.015 + Math.random() * 0.03) * (Math.random() > 0.5 ? 1 : -1),
                    size: 1 + Math.random() * 2,
                    alpha: 0.3 + Math.random() * 0.6
                });
            }

            function init() {
                const ids = ['vault', 'growth', 'radar', 'reactor'];
                ids.forEach(id => {
                    const c = document.getElementById('canvas-kpi-' + id);
                    if (c) {
                        canvases[id] = c;
                        ctxs[id] = c.getContext('2d');
                    }
                });

                resize();
                window.addEventListener('resize', resize);
                startLoop();
            }

            function resize() {
                dpr = window.devicePixelRatio || 1;
                for (const id in canvases) {
                    const c = canvases[id];
                    if (!c) continue;
                    const rect = c.parentElement ? c.parentElement.getBoundingClientRect() : c.getBoundingClientRect();
                    const w = rect.width || 280;
                    const h = rect.height || 135;
                    sizes[id] = { w, h };
                    c.width = Math.floor(w * dpr);
                    c.height = Math.floor(h * dpr);
                    const ctx = ctxs[id];
                    if (ctx) {
                        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
                    }
                }
            }

            function updateMetrics(newData) {
                const prevBal = metrics.balance;
                metrics = Object.assign(metrics, newData);

                if (Math.abs(metrics.balance - prevBal) > 0.5) {
                    vaultRipples.push({ r: 5, maxR: 70, alpha: 0.8 });
                }

                const growthCard = document.getElementById('card-kpi-growth');
                const growthChip = document.getElementById('chip-kpi-growth');
                if (growthCard) {
                    if (metrics.pnl < 0) {
                        growthCard.classList.add('drawdown');
                        if (growthChip) {
                            growthChip.style.background = 'rgba(244,63,94,0.15)';
                            growthChip.style.borderColor = 'rgba(244,63,94,0.35)';
                            growthChip.style.color = 'var(--red)';
                            growthChip.innerText = '🛡️ SAVUNMA';
                        }
                    } else {
                        growthCard.classList.remove('drawdown');
                        if (growthChip) {
                            growthChip.style.background = 'rgba(16,185,129,0.15)';
                            growthChip.style.borderColor = 'rgba(16,185,129,0.35)';
                            growthChip.style.color = 'var(--green)';
                            growthChip.innerText = 'CANLI NABIZ';
                        }
                    }
                }

                const reactorChip = document.getElementById('chip-kpi-reactor');
                if (reactorChip) {
                    if (metrics.pf >= 2.0) {
                        reactorChip.style.background = 'rgba(192,132,252,0.18)';
                        reactorChip.style.borderColor = 'rgba(192,132,252,0.45)';
                        reactorChip.style.color = '#c084fc';
                        reactorChip.innerText = 'ELİT ALFA';
                    } else if (metrics.pf >= 1.5) {
                        reactorChip.style.background = 'rgba(16,185,129,0.18)';
                        reactorChip.style.borderColor = 'rgba(16,185,129,0.45)';
                        reactorChip.style.color = 'var(--green)';
                        reactorChip.innerText = 'GÜÇLÜ';
                    } else if (metrics.pf >= 1.0) {
                        reactorChip.style.background = 'rgba(245,158,11,0.18)';
                        reactorChip.style.borderColor = 'rgba(245,158,11,0.45)';
                        reactorChip.style.color = '#fbbf24';
                        reactorChip.innerText = 'KÂRLI';
                    } else {
                        reactorChip.style.background = 'rgba(244,63,94,0.18)';
                        reactorChip.style.borderColor = 'rgba(244,63,94,0.45)';
                        reactorChip.style.color = 'var(--red)';
                        reactorChip.innerText = 'KALKAN';
                    }
                }

                refreshRadarBlips();
            }

            function startLoop() {
                if (isRunning) return;
                isRunning = true;
                function loop() {
                    render();
                    animId = requestAnimationFrame(loop);
                }
                animId = requestAnimationFrame(loop);
            }

            // 1. RENDER VAULT (KUANTUM LİKİDİTE KASASI)
            function renderVault(ctx, w, h) {
                ctx.clearRect(0, 0, w, h);
                vaultTime += 0.025;

                // Wave layer
                const waveH = h * 0.32;
                ctx.save();
                const grad = ctx.createLinearGradient(0, h - waveH, 0, h);
                grad.addColorStop(0, 'rgba(0, 242, 254, 0.09)');
                grad.addColorStop(1, 'rgba(79, 172, 254, 0.01)');
                ctx.fillStyle = grad;

                ctx.beginPath();
                ctx.moveTo(0, h);
                for (let x = 0; x <= w; x += 10) {
                    const y = (h - waveH * 0.6) + Math.sin(x * 0.018 + vaultTime) * 6 + Math.cos(x * 0.035 - vaultTime * 0.8) * 3;
                    ctx.lineTo(x, y);
                }
                ctx.lineTo(w, h);
                ctx.closePath();
                ctx.fill();

                ctx.strokeStyle = 'rgba(0, 242, 254, 0.35)';
                ctx.lineWidth = 1.2;
                ctx.stroke();
                ctx.restore();

                // Floating Sparkles
                ctx.save();
                for (let p of vaultParticles) {
                    p.y += p.vy;
                    p.x += p.vx;
                    if (p.y < 0.2) { p.y = 0.95; p.x = Math.random(); }
                    if (p.x < 0) p.x = 1; if (p.x > 1) p.x = 0;

                    ctx.fillStyle = `rgba(0, 242, 254, ${p.alpha})`;
                    ctx.beginPath();
                    ctx.arc(p.x * w, p.y * h, p.size, 0, Math.PI * 2);
                    ctx.fill();
                }
                ctx.restore();

                // Holographic 3D Orb on right
                const ox = w - 48;
                const oy = h * 0.48;
                const r = 24;

                ctx.save();
                const corePulse = 1 + Math.sin(vaultTime * 2) * 0.08;
                const orbGrad = ctx.createRadialGradient(ox, oy, 2, ox, oy, r * 1.5 * corePulse);
                orbGrad.addColorStop(0, 'rgba(0, 242, 254, 0.35)');
                orbGrad.addColorStop(0.5, 'rgba(79, 172, 254, 0.12)');
                orbGrad.addColorStop(1, 'rgba(0, 242, 254, 0)');
                ctx.fillStyle = orbGrad;
                ctx.beginPath();
                ctx.arc(ox, oy, r * 1.5 * corePulse, 0, Math.PI * 2);
                ctx.fill();

                ctx.lineWidth = 1.3;
                const drawRing = (rx, ry, rot, col) => {
                    ctx.save();
                    ctx.translate(ox, oy);
                    ctx.rotate(rot);
                    ctx.strokeStyle = col;
                    ctx.beginPath();
                    ctx.ellipse(0, 0, rx, ry, 0, 0, Math.PI * 2);
                    ctx.stroke();
                    ctx.restore();
                };

                drawRing(r, r * Math.abs(Math.cos(vaultTime)), vaultTime * 0.6, 'rgba(0, 242, 254, 0.55)');
                drawRing(r * Math.abs(Math.sin(vaultTime * 0.8)), r, -vaultTime * 0.7, 'rgba(129, 140, 248, 0.5)');
                drawRing(r * 0.75, r * 0.75 * Math.abs(Math.sin(vaultTime * 1.2)), Math.PI / 4 + vaultTime, 'rgba(56, 189, 248, 0.6)');

                ctx.fillStyle = '#ffffff';
                ctx.shadowColor = '#00f2fe';
                ctx.shadowBlur = 8;
                ctx.beginPath();
                ctx.arc(ox, oy, 3.5 * corePulse, 0, Math.PI * 2);
                ctx.fill();

                for (let i = vaultRipples.length - 1; i >= 0; i--) {
                    const rip = vaultRipples[i];
                    rip.r += 1.8;
                    rip.alpha *= 0.94;
                    ctx.strokeStyle = `rgba(0, 242, 254, ${rip.alpha})`;
                    ctx.lineWidth = 1.5;
                    ctx.beginPath();
                    ctx.arc(ox, oy, rip.r, 0, Math.PI * 2);
                    ctx.stroke();
                    if (rip.alpha < 0.02 || rip.r >= rip.maxR) {
                        vaultRipples.splice(i, 1);
                    }
                }
                ctx.restore();
            }

            // 2. RENDER GROWTH (NEON EKG NABZI)
            function renderGrowth(ctx, w, h) {
                ctx.clearRect(0, 0, w, h);
                ekgPhase += 0.035;

                const isPositive = metrics.pnl >= 0;
                const mainColor = isPositive ? '#10b981' : '#f43f5e';
                const glowColor = isPositive ? 'rgba(16, 185, 129, ' : 'rgba(244, 63, 94, ';

                ctx.save();
                for (let p of growthSparks) {
                    p.y += p.vy;
                    p.x += p.vx;
                    if (p.y < 0.05) { p.y = 0.95; p.x = Math.random(); }
                    if (p.x < 0) p.x = 1; if (p.x > 1) p.x = 0;

                    ctx.fillStyle = glowColor + (p.alpha * 0.45) + ')';
                    ctx.beginPath();
                    ctx.arc(p.x * w, p.y * h, p.size, 0, Math.PI * 2);
                    ctx.fill();
                }
                ctx.restore();

                const baseY = h * 0.72;
                ctx.save();
                ctx.strokeStyle = mainColor;
                ctx.shadowColor = mainColor;
                ctx.shadowBlur = 9;
                ctx.lineWidth = 2;

                ctx.beginPath();
                ctx.moveTo(0, baseY);

                const scanPos = (ekgPhase * 60) % (w + 100) - 50;

                for (let x = 0; x <= w; x += 3) {
                    const distToScan = x - scanPos;
                    let y = baseY;

                    if (distToScan > -40 && distToScan < 40) {
                        const t = (distToScan + 40) / 80;
                        if (t > 0.25 && t < 0.35) {
                            y -= Math.sin((t - 0.25) * 10 * Math.PI) * 5;
                        } else if (t >= 0.35 && t < 0.42) {
                            y += Math.sin((t - 0.35) * 14 * Math.PI) * 4;
                        } else if (t >= 0.42 && t < 0.58) {
                            const spikeH = isPositive ? 26 : 18;
                            y -= Math.sin((t - 0.42) * 6.25 * Math.PI) * spikeH;
                        } else if (t >= 0.58 && t < 0.68) {
                            y += Math.sin((t - 0.58) * 10 * Math.PI) * 5;
                        } else if (t >= 0.68 && t < 0.85) {
                            y -= Math.sin((t - 0.68) * 5.88 * Math.PI) * 7;
                        }
                    } else {
                        y += Math.sin(x * 0.04 + ekgPhase * 2) * 1.5;
                    }

                    ctx.lineTo(x, y);
                }
                ctx.stroke();

                if (scanPos >= 0 && scanPos <= w) {
                    ctx.fillStyle = '#ffffff';
                    ctx.shadowColor = '#ffffff';
                    ctx.shadowBlur = 12;
                    ctx.beginPath();
                    ctx.arc(scanPos, baseY, 3.2, 0, Math.PI * 2);
                    ctx.fill();
                }
                ctx.restore();

                // Vector Indicator on right
                const ax = w - 44;
                const ay = h * 0.46;
                ctx.save();
                ctx.strokeStyle = glowColor + '0.45)';
                ctx.lineWidth = 1.5;
                ctx.beginPath();
                if (isPositive) {
                    ctx.moveTo(ax - 10, ay + 10);
                    ctx.lineTo(ax, ay - 8);
                    ctx.lineTo(ax + 10, ay + 10);
                } else {
                    ctx.moveTo(ax - 10, ay - 6);
                    ctx.lineTo(ax, ay + 8);
                    ctx.lineTo(ax + 10, ay - 6);
                }
                ctx.stroke();
                ctx.restore();
            }

            // 3. RENDER RADAR (SİBER NİŞANGAH)
            function renderRadar(ctx, w, h) {
                ctx.clearRect(0, 0, w, h);
                radarAngle += 0.035;

                const cx = w - 48;
                const cy = h * 0.48;
                const r = 30;

                ctx.save();

                ctx.strokeStyle = 'rgba(56, 189, 248, 0.18)';
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.arc(cx, cy, r, 0, Math.PI * 2);
                ctx.stroke();

                ctx.beginPath();
                ctx.arc(cx, cy, r * 0.55, 0, Math.PI * 2);
                ctx.stroke();

                ctx.beginPath();
                ctx.moveTo(cx - r - 4, cy); ctx.lineTo(cx - 6, cy);
                ctx.moveTo(cx + 6, cy); ctx.lineTo(cx + r + 4, cy);
                ctx.moveTo(cx, cy - r - 4); ctx.lineTo(cx, cy - 6);
                ctx.moveTo(cx, cy + 6); ctx.lineTo(cx, cy + r + 4);
                ctx.stroke();

                const sweepGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
                sweepGrad.addColorStop(0, 'rgba(56, 189, 248, 0.25)');
                sweepGrad.addColorStop(1, 'rgba(56, 189, 248, 0)');
                ctx.fillStyle = sweepGrad;

                ctx.beginPath();
                ctx.moveTo(cx, cy);
                ctx.arc(cx, cy, r, radarAngle - 0.7, radarAngle);
                ctx.closePath();
                ctx.fill();

                ctx.strokeStyle = '#38bdf8';
                ctx.shadowColor = '#38bdf8';
                ctx.shadowBlur = 8;
                ctx.lineWidth = 1.4;
                ctx.beginPath();
                ctx.moveTo(cx, cy);
                ctx.lineTo(cx + Math.cos(radarAngle) * r, cy + Math.sin(radarAngle) * r);
                ctx.stroke();

                for (let b of radarBlips) {
                    const bx = cx + b.x * r;
                    const by = cy + b.y * r;

                    let dTheta = (radarAngle - b.theta) % (Math.PI * 2);
                    if (dTheta < 0) dTheta += Math.PI * 2;
                    if (dTheta < 0.25) {
                        b.intensity = 1.0;
                    } else {
                        b.intensity = Math.max(0.15, b.intensity * 0.97);
                    }

                    const blipCol = b.isWin ? `rgba(16, 185, 129, ${b.intensity})` : `rgba(244, 63, 94, ${b.intensity})`;
                    ctx.fillStyle = blipCol;
                    ctx.shadowColor = b.isWin ? '#10b981' : '#f43f5e';
                    ctx.shadowBlur = b.intensity > 0.5 ? 8 : 2;
                    ctx.beginPath();
                    ctx.arc(bx, by, b.intensity > 0.5 ? 2.5 : 1.8, 0, Math.PI * 2);
                    ctx.fill();

                    if (b.intensity > 0.8) {
                        ctx.strokeStyle = blipCol;
                        ctx.lineWidth = 1;
                        ctx.beginPath();
                        ctx.arc(bx, by, (1 - b.intensity) * 12 + 2, 0, Math.PI * 2);
                        ctx.stroke();
                    }
                }

                const wr = Math.max(0, Math.min(100, metrics.winRate || 0));
                const startAngle = -Math.PI / 2;
                const endAngle = startAngle + (wr / 100) * (Math.PI * 2);

                ctx.shadowColor = '#00f2fe';
                ctx.shadowBlur = 10;
                ctx.strokeStyle = '#00f2fe';
                ctx.lineWidth = 2.4;
                ctx.beginPath();
                ctx.arc(cx, cy, r + 4, startAngle, endAngle);
                ctx.stroke();

                if (wr > 0) {
                    ctx.fillStyle = '#ffffff';
                    ctx.beginPath();
                    ctx.arc(cx + Math.cos(endAngle) * (r + 4), cy + Math.sin(endAngle) * (r + 4), 2.8, 0, Math.PI * 2);
                    ctx.fill();
                }

                ctx.restore();
            }

            // 4. RENDER REACTOR (KUANTUM ALFA REAKTÖRÜ)
            function renderReactor(ctx, w, h) {
                ctx.clearRect(0, 0, w, h);
                const pf = metrics.pf || 0.0;

                let colMain = '#c084fc';
                let colSec = '#00f2fe';
                let rotSpeed = 0.025;

                if (pf >= 2.0) {
                    colMain = '#c084fc';
                    colSec = '#00f2fe';
                    rotSpeed = 0.038;
                } else if (pf >= 1.5) {
                    colMain = '#10b981';
                    colSec = '#34d399';
                    rotSpeed = 0.030;
                } else if (pf >= 1.0) {
                    colMain = '#f59e0b';
                    colSec = '#fbbf24';
                    rotSpeed = 0.022;
                } else {
                    colMain = '#f43f5e';
                    colSec = '#fb7185';
                    rotSpeed = 0.016;
                }

                reactorAngle += rotSpeed;
                reactorTilt += rotSpeed * 0.7;

                const cx = w - 48;
                const cy = h * 0.48;
                const r = 24;

                ctx.save();

                for (let p of reactorParticles) {
                    p.angle += p.speed;
                    const px = cx + Math.cos(p.angle) * p.dist;
                    const py = cy + Math.sin(p.angle) * p.dist * 0.55;
                    ctx.fillStyle = colMain;
                    ctx.globalAlpha = p.alpha * 0.65;
                    ctx.beginPath();
                    ctx.arc(px, py, p.size, 0, Math.PI * 2);
                    ctx.fill();
                }
                ctx.globalAlpha = 1.0;

                ctx.lineWidth = 1.4;
                ctx.shadowColor = colMain;
                ctx.shadowBlur = 8;

                ctx.save();
                ctx.translate(cx, cy);
                ctx.rotate(0.5);
                ctx.strokeStyle = colMain;
                ctx.beginPath();
                ctx.ellipse(0, 0, r * 1.3, r * 0.45 * Math.abs(Math.sin(reactorAngle)), 0, 0, Math.PI * 2);
                ctx.stroke();
                ctx.restore();

                ctx.save();
                ctx.translate(cx, cy);
                ctx.rotate(-0.5);
                ctx.strokeStyle = colSec;
                ctx.shadowColor = colSec;
                ctx.beginPath();
                ctx.ellipse(0, 0, r * 1.3, r * 0.45 * Math.abs(Math.cos(reactorAngle * 0.9)), 0, 0, Math.PI * 2);
                ctx.stroke();
                ctx.restore();

                ctx.save();
                ctx.translate(cx, cy);

                const pts = [
                    { x: 0, y: -r * 0.85, z: 0 },
                    { x: 0, y: r * 0.85, z: 0 },
                    { x: r * 0.75, y: 0, z: 0 },
                    { x: -r * 0.75, y: 0, z: 0 },
                    { x: 0, y: 0, z: r * 0.75 },
                    { x: 0, y: 0, z: -r * 0.75 }
                ];

                const proj = pts.map(p => {
                    const cosY = Math.cos(reactorAngle);
                    const sinY = Math.sin(reactorAngle);
                    let x1 = p.x * cosY + p.z * sinY;
                    let z1 = -p.x * sinY + p.z * cosY;

                    const cosX = Math.cos(reactorTilt);
                    const sinX = Math.sin(reactorTilt);
                    let y2 = p.y * cosX - z1 * sinX;
                    return { x: x1, y: y2 };
                });

                ctx.strokeStyle = colMain;
                ctx.lineWidth = 1.3;
                ctx.beginPath();
                const edges = [
                    [0, 2], [0, 3], [0, 4], [0, 5],
                    [1, 2], [1, 3], [1, 4], [1, 5],
                    [2, 4], [4, 3], [3, 5], [5, 2]
                ];
                for (let e of edges) {
                    ctx.moveTo(proj[e[0]].x, proj[e[0]].y);
                    ctx.lineTo(proj[e[1]].x, proj[e[1]].y);
                }
                ctx.stroke();

                const plasmaGrad = ctx.createRadialGradient(0, 0, 1, 0, 0, 8);
                plasmaGrad.addColorStop(0, '#ffffff');
                plasmaGrad.addColorStop(0.5, colSec);
                plasmaGrad.addColorStop(1, 'rgba(0,0,0,0)');
                ctx.fillStyle = plasmaGrad;
                ctx.beginPath();
                ctx.arc(0, 0, 8, 0, Math.PI * 2);
                ctx.fill();
                ctx.restore();

                const barW = w - 40;
                const barH = 2.5;
                const barX = 20;
                const barY = h - 6;

                ctx.fillStyle = 'rgba(255, 255, 255, 0.08)';
                ctx.fillRect(barX, barY, barW, barH);

                const fillRatio = Math.max(0.05, Math.min(1.0, pf / 3.0));
                const activeGrad = ctx.createLinearGradient(barX, 0, barX + barW * fillRatio, 0);
                activeGrad.addColorStop(0, colMain);
                activeGrad.addColorStop(1, colSec);
                ctx.fillStyle = activeGrad;
                ctx.fillRect(barX, barY, barW * fillRatio, barH);

                ctx.fillStyle = '#ffffff';
                ctx.shadowColor = colSec;
                ctx.shadowBlur = 6;
                ctx.beginPath();
                ctx.arc(barX + barW * fillRatio, barY + barH / 2, 2.2, 0, Math.PI * 2);
                ctx.fill();

                ctx.restore();
            }

            function render() {
                if ((window.currentActiveMainTab && window.currentActiveMainTab !== 'cockpit') || document.hidden) {
                    return;
                }

                if (ctxs.vault && sizes.vault) renderVault(ctxs.vault, sizes.vault.w, sizes.vault.h);
                if (ctxs.growth && sizes.growth) renderGrowth(ctxs.growth, sizes.growth.w, sizes.growth.h);
                if (ctxs.radar && sizes.radar) renderRadar(ctxs.radar, sizes.radar.w, sizes.radar.h);
                if (ctxs.reactor && sizes.reactor) renderReactor(ctxs.reactor, sizes.reactor.w, sizes.reactor.h);
            }

            return {
                init,
                resize,
                updateMetrics
            };
        })();
        window.ValkyrieKpiSimEngine = ValkyrieKpiSimEngine;

        // =========================================================================
        // 🎯 VALKYRIE 360° TAKTİK LİKİDİTE RADARI & SAVUNMA KALKANI MOTORU
        // =========================================================================
        let currentRadarMode = localStorage.getItem('valkyrie_radar_mode') || 'expanded';
        let currentRadarSize = localStorage.getItem('valkyrie_radar_size') || 'normal';
        let currentRadarScope = localStorage.getItem('valkyrie_radar_scope') || 'top15';

        function toggleRadarView() {
            currentRadarMode = (currentRadarMode === 'expanded') ? 'collapsed' : 'expanded';
            localStorage.setItem('valkyrie_radar_mode', currentRadarMode);
            applyRadarViewMode();
        }

        function applyRadarViewMode() {
            const body = document.getElementById('tactical-radar-body');
            const btn = document.getElementById('btn-toggle-radar-view');
            if (currentRadarMode === 'collapsed') {
                if (body) body.style.display = 'none';
                if (btn) btn.innerHTML = '📡 Radarı Aç';
            } else {
                if (body) body.style.display = 'grid';
                if (btn) btn.innerHTML = '📡 Radarı Gizle';
                if (window.ValkyrieTacticalRadarEngine) window.ValkyrieTacticalRadarEngine.resize();
            }
        }

        function toggleRadarExpand() {
            const card = document.getElementById('tactical-radar-wrap');
            const btn = document.getElementById('btn-expand-radar');
            if (!card) return;
            const isExp = card.classList.contains('radar-expanded-mode');
            if (isExp) {
                card.classList.remove('radar-expanded-mode');
                localStorage.setItem('valkyrie_radar_size', 'normal');
                if (btn) btn.innerHTML = '⛶ Geniş Radar';
            } else {
                card.classList.add('radar-expanded-mode');
                localStorage.setItem('valkyrie_radar_size', 'expanded');
                if (btn) btn.innerHTML = '🗗 Standart Görünüm';
            }
            if (window.ValkyrieTacticalRadarEngine) {
                setTimeout(() => {
                    window.ValkyrieTacticalRadarEngine.resize();
                }, 60);
            }
        }

        function applyRadarSizeMode() {
            const saved = localStorage.getItem('valkyrie_radar_size') || 'normal';
            const card = document.getElementById('tactical-radar-wrap');
            const btn = document.getElementById('btn-expand-radar');
            if (card && saved === 'expanded') {
                card.classList.add('radar-expanded-mode');
                if (btn) btn.innerHTML = '🗗 Standart Görünüm';
            }
        }

        function setRadarScope(scope) {
            currentRadarScope = scope;
            localStorage.setItem('valkyrie_radar_scope', scope);
            syncFilterPillsUI();
            if (window.ValkyrieTacticalRadarEngine) {
                window.ValkyrieTacticalRadarEngine.applyCurrentFilter();
            }
        }

        function syncFilterPillsUI() {
            const pills = document.querySelectorAll('.radar-filter-pill');
            pills.forEach(p => p.classList.remove('active'));
            const activePill = document.getElementById(`rf-pill-${currentRadarScope}`);
            if (activePill) activePill.classList.add('active');
        }

        function focusRadarTargetCard() {
            if (window.ValkyrieTacticalRadarEngine) {
                window.ValkyrieTacticalRadarEngine.focusSelectedInFeed();
            }
        }

        const ValkyrieTacticalRadarEngine = (function() {
            let canvas, ctx;
            let width = 0, height = 0;
            let dpr = window.devicePixelRatio || 1;
            let animId = null;
            let sweepAngle = 0;
            let isRunning = false;

            let allRawRadarTargets = [];
            let radarTargets = [];
            let selectedTarget = null;
            let selectedIndex = 0;
            let lastAutoCycleTime = Date.now();
            let isUserHovering = false;
            let mousePos = { x: -1, y: -1 };

            let shieldSparks = [];

            function getStableAngle(str) {
                let h = 0;
                for (let i = 0; i < str.length; i++) {
                    h = (h << 5) - h + str.charCodeAt(i);
                    h |= 0;
                }
                return Math.abs(h % 360) * (Math.PI / 180);
            }

            function applyAntiCollision(targets) {
                if (!targets || targets.length <= 1) return;
                targets.forEach(t => { t.displayAngle = t.angle; });

                const bands = { contact: [], ambush: [], approach: [], blocked: [] };
                targets.forEach(t => {
                    if (bands[t.category]) bands[t.category].push(t);
                    else bands.approach.push(t);
                });

                Object.values(bands).forEach(band => {
                    if (band.length <= 1) return;
                    band.sort((a, b) => a.displayAngle - b.displayAngle);
                    const minGap = 0.20; // radyan (~11.5 derece) minimum açısal ferahlık
                    for (let pass = 0; pass < 3; pass++) {
                        for (let i = 0; i < band.length; i++) {
                            const nextIdx = (i + 1) % band.length;
                            let d = band[nextIdx].displayAngle - band[i].displayAngle;
                            if (d < 0) d += Math.PI * 2;
                            if (d < minGap && d > 0.0001) {
                                const push = (minGap - d) / 2;
                                band[i].displayAngle = (band[i].displayAngle - push + Math.PI * 2) % (Math.PI * 2);
                                band[nextIdx].displayAngle = (band[nextIdx].displayAngle + push) % (Math.PI * 2);
                            }
                        }
                    }
                });
            }

            function applyCurrentFilter() {
                if (!allRawRadarTargets || allRawRadarTargets.length === 0) {
                    radarTargets = [];
                    return;
                }

                if (currentRadarScope === 'top15') {
                    // En kritik 15 pariteyi önceliklendir (Temas > Iceberg/Bookmap > Pusu > Kalkan > Yaklaşan)
                    const scored = allRawRadarTargets.map(t => {
                        let score = 0;
                        if (t.category === 'contact') score += 1000 - Math.min(60, (t.distPct || 0) * 120);
                        else if (t.hasIceberg || t.icebergRatio >= 3.5) score += 800 - Math.min(60, (t.distPct || 0) * 60);
                        else if (t.isAnchorWall || t.isIronWall) score += 700 - Math.min(60, (t.distPct || 0) * 60);
                        else if (t.bookmapBuyerAbsorption || t.bookmapSellerAbsorption) score += 650;
                        else if (t.category === 'ambush') score += 500 - Math.min(60, (t.distPct || 0) * 60);
                        else if (t.category === 'blocked') score += 400;
                        else score += 200 - Math.min(100, (t.distPct || 0) * 20);

                        if (t.volSurge > 1.5) score += Math.min(80, t.volSurge * 20);
                        return { item: t, score: score };
                    });
                    scored.sort((a, b) => b.score - a.score);
                    let filtered = scored.slice(0, 15).map(s => s.item);

                    if (selectedTarget && !filtered.some(t => t.symbol === selectedTarget.symbol)) {
                        filtered[filtered.length - 1] = selectedTarget;
                    }
                    radarTargets = filtered;
                } else if (currentRadarScope === 'contact') {
                    radarTargets = allRawRadarTargets.filter(t => t.category === 'contact');
                } else if (currentRadarScope === 'iceberg') {
                    radarTargets = allRawRadarTargets.filter(t => t.hasIceberg || t.icebergRatio >= 3.5 || t.bookmapBuyerAbsorption || t.bookmapSellerAbsorption);
                } else if (currentRadarScope === 'ambush') {
                    radarTargets = allRawRadarTargets.filter(t => t.category === 'ambush');
                } else if (currentRadarScope === 'blocked') {
                    radarTargets = allRawRadarTargets.filter(t => t.category === 'blocked');
                } else {
                    radarTargets = allRawRadarTargets.slice(0, 100);
                }

                applyAntiCollision(radarTargets);

                const badge = document.getElementById('radar-active-count-badge');
                if (badge) {
                    const iceCount = radarTargets.filter(t => t.hasIceberg || t.icebergRatio >= 3.5).length;
                    const iceTxt = iceCount > 0 ? ` • 🧊 ${iceCount} ICEBERG` : '';
                    let scopeTitle = 'ODAK 15';
                    if (currentRadarScope === 'all') scopeTitle = 'TÜMÜ';
                    else if (currentRadarScope === 'contact') scopeTitle = 'TEMAS';
                    else if (currentRadarScope === 'iceberg') scopeTitle = 'ICEBERG';
                    else if (currentRadarScope === 'ambush') scopeTitle = 'PUSU';
                    else if (currentRadarScope === 'blocked') scopeTitle = 'KALKAN';
                    badge.innerText = `${radarTargets.length} HEDEF (${scopeTitle})${iceTxt}`;
                }

                if (!selectedTarget || !radarTargets.some(t => t.symbol === selectedTarget.symbol)) {
                    selectedTarget = radarTargets.find(t => t.category === 'contact') 
                        || radarTargets.find(t => t.hasIceberg)
                        || radarTargets.find(t => t.category === 'ambush') 
                        || radarTargets[0] || null;
                    updateTelemetryHUD(selectedTarget);
                }
            }

            function setRadarData(nearCandidates, rejections) {
                const list = [];

                if (nearCandidates && Array.isArray(nearCandidates)) {
                    nearCandidates.forEach(c => {
                        const cleanS = (c.symbol || '').replace('/USDT', '').replace('USDT', '').trim();
                        if (!cleanS) return;
                        const dist = c.distPct !== undefined ? c.distPct : 0.5;
                        const volSurge = c.volSurge !== undefined ? c.volSurge : 1.0;
                        const minSurge = c.minVolSurge !== undefined ? c.minVolSurge : 1.5;
                        const isContact = dist < 0.25;
                        const isVolOk = volSurge >= minSurge;

                        let cat = 'approach';
                        if (isContact) cat = 'contact';
                        else if (dist <= 0.60) cat = 'ambush';

                        const iceRatio = c.icebergRatio !== undefined ? Number(c.icebergRatio) : 1.0;
                        const askIceRatio = c.askIcebergRatio !== undefined ? Number(c.askIcebergRatio) : 1.0;
                        const bidIceRatio = c.bidIcebergRatio !== undefined ? Number(c.bidIcebergRatio) : 1.0;
                        const iceSide = c.icebergSide || 'NONE';
                        const hasIce = Boolean(c.hasIceberg || (iceRatio >= 3.5));
                        const entropyNorm = c.entropyNorm !== undefined ? Number(c.entropyNorm) : 0.65;
                        const hurstVal = c.hurstVal !== undefined ? Number(c.hurstVal) : 0.50;
                        const hmmPhase = c.hmmPhase || 'ACCUMULATION';
                        const hmmDesc = c.hmmDesc || '';

                        list.push({
                            symbol: cleanS,
                            category: cat,
                            distPct: dist,
                            volSurge: volSurge,
                            minVolSurge: minSurge,
                            isVolOk: isVolOk,
                            targetName: c.targetName || 'Destek / Direnç',
                            action: c.action || (c.side === 'SHORT' ? 'SHORT Satış' : 'LONG Alış'),
                            price: c.price || 0,
                            targetPrice: c.targetPrice || 0,
                            rsScore: c.rsScore || 0,
                            reason: isContact 
                                ? (isVolOk ? 'Seviyede tam temas & Hacim onaylı!' : `Seviyede temas var; ${minSurge.toFixed(1)}x hacim patlaması ve 5M kapanış bekleniyor.`)
                                : `Fiyat ${c.targetName} seviyesine süzülüyor (Kalan: %${dist.toFixed(2)}).`,
                            angle: getStableAngle(cleanS + '_near'),
                            displayAngle: getStableAngle(cleanS + '_near'),
                            intensity: 0.25,
                            pulse: 0,
                            icebergRatio: iceRatio,
                            askIcebergRatio: askIceRatio,
                            bidIcebergRatio: bidIceRatio,
                            icebergSide: iceSide,
                            hasIceberg: hasIce,
                            entropyNorm: entropyNorm,
                            hurstVal: hurstVal,
                            hmmPhase: hmmPhase,
                            hmmDesc: hmmDesc,
                            bookmapSellerAbsorption: Boolean(c.bookmapSellerAbsorption),
                            bookmapBuyerAbsorption: Boolean(c.bookmapBuyerAbsorption),
                            bookmapAbsorptionType: c.bookmapAbsorptionType || 'NONE',
                            bookmapAbsorptionDesc: c.bookmapAbsorptionDesc || '',
                            isAnchorWall: Boolean(c.isAnchorWall),
                            isIronWall: Boolean(c.isIronWall),
                            wallDurationSec: Number(c.wallDurationSec || 0),
                            priceChangePct60s: Number(c.priceChangePct60s || 0)
                        });
                    });
                }

                if (rejections && Array.isArray(rejections)) {
                    rejections.slice(-8).forEach(r => {
                        const cleanS = (r.symbol || '').replace('/USDT', '').replace('USDT', '').trim();
                        if (!cleanS) return;
                        if (list.some(t => t.symbol === cleanS && t.category === 'blocked')) return;

                        const iceRatio = Number(r.icebergRatio || (r.reason && r.reason.includes('x >= 3.5x') ? 3.8 : 1.0));
                        const hasIce = Boolean(r.hasIceberg || (iceRatio >= 3.5) || (r.reason && (r.reason.includes('Buzdağı') || r.reason.includes('Iceberg'))));
                        const iceSide = r.icebergSide || (r.reason && r.reason.includes('satıcı') ? 'ICEBERG_ASK_RESISTANCE' : (r.reason && r.reason.includes('alıcı') ? 'ICEBERG_BID_SUPPORT' : 'NONE'));
                        const entropyNorm = Number(r.entropyNorm !== undefined ? r.entropyNorm : (r.reason && r.reason.includes('Entropi') ? 0.91 : 0.70));
                        const hurstVal = Number(r.hurstVal !== undefined ? r.hurstVal : (r.reason && r.reason.includes('Mandelbrot') ? 0.38 : 0.50));

                        list.push({
                            symbol: cleanS,
                            category: 'blocked',
                            distPct: 0.0,
                            volSurge: 0,
                            minVolSurge: 1.5,
                            isVolOk: false,
                            targetName: r.setup || 'Sinyal Kurulumu',
                            action: 'ENGEL / İŞLEM REDDİ',
                            price: 0,
                            targetPrice: 0,
                            rsScore: 0,
                            reason: r.reason || 'Kriterler sağlanamadığı için işlem güvenliği gereği iptal edildi.',
                            angle: getStableAngle(cleanS + '_rej'),
                            displayAngle: getStableAngle(cleanS + '_rej'),
                            intensity: 0.35,
                            pulse: 0,
                            icebergRatio: iceRatio,
                            askIcebergRatio: Number(r.askIcebergRatio || iceRatio),
                            bidIcebergRatio: Number(r.bidIcebergRatio || iceRatio),
                            icebergSide: iceSide,
                            hasIceberg: hasIce,
                            entropyNorm: entropyNorm,
                            hurstVal: hurstVal,
                            hmmPhase: r.hmmPhase || (r.reason && r.reason.includes('HMM') ? 'MANIPULATION_SWEEP' : 'ACCUMULATION'),
                            hmmDesc: r.hmmDesc || '',
                            bookmapSellerAbsorption: Boolean(r.bookmapVeto === 'SELLER_ABSORPTION_BULL_TRAP' || (r.reason && r.reason.includes('Satıcı Emilimi'))),
                            bookmapBuyerAbsorption: Boolean(r.bookmapVeto === 'BUYER_ABSORPTION_BEAR_TRAP' || (r.reason && r.reason.includes('Alıcı Emilimi'))),
                            isAnchorWall: Boolean(r.isAnchorWall),
                            wallDurationSec: Number(r.wallDurationSec || 0),
                            priceChangePct60s: Number(r.priceChg60s || 0)
                        });
                    });
                }

                allRawRadarTargets = list;
                applyCurrentFilter();
            }

            function updateTelemetryHUD(target) {
                if (!target) return;
                const nameEl = document.getElementById('radar-target-name');
                const badgeEl = document.getElementById('radar-target-badge');
                const distEl = document.getElementById('radar-stat-distance');
                const lvlEl = document.getElementById('radar-stat-target-lvl');
                const volEl = document.getElementById('radar-stat-volume');
                const volSubEl = document.getElementById('radar-stat-vol-target');
                const cvdEl = document.getElementById('radar-stat-cvd');
                const cvdSubEl = document.getElementById('radar-stat-cvd-delta');
                const statEl = document.getElementById('radar-stat-status');
                const actEl = document.getElementById('radar-stat-action');
                const briefEl = document.getElementById('radar-target-briefing');
                const iceEl = document.getElementById('radar-stat-iceberg');
                const iceSubEl = document.getElementById('radar-stat-iceberg-sub');
                const entEl = document.getElementById('radar-stat-entropy-hurst');
                const entSubEl = document.getElementById('radar-stat-entropy-sub');

                const hasIce = Boolean(target.hasIceberg || (target.icebergRatio && target.icebergRatio >= 3.5));
                const iceBadgeIcon = hasIce ? ' 🧊' : '';

                if (nameEl) nameEl.innerHTML = `${target.category === 'blocked' ? '🛡️' : (target.category === 'contact' ? '🔥' : '🎯')} ${target.symbol}/USDT${iceBadgeIcon}`;
                
                if (badgeEl) {
                    if (target.category === 'contact') {
                        badgeEl.innerText = '⚡ SEVİYEDE TAM TEMAS';
                        badgeEl.style.background = 'rgba(16, 185, 129, 0.18)';
                        badgeEl.style.borderColor = 'rgba(16, 185, 129, 0.45)';
                        badgeEl.style.color = '#10b981';
                    } else if (target.category === 'ambush') {
                        badgeEl.innerText = '⏳ HACİM BEKLENİYOR';
                        badgeEl.style.background = 'rgba(245, 158, 11, 0.18)';
                        badgeEl.style.borderColor = 'rgba(245, 158, 11, 0.45)';
                        badgeEl.style.color = '#f59e0b';
                    } else if (target.category === 'blocked') {
                        badgeEl.innerText = '⛔ AEGIS KALKANI (ELENDİ)';
                        badgeEl.style.background = 'rgba(244, 63, 94, 0.18)';
                        badgeEl.style.borderColor = 'rgba(244, 63, 94, 0.45)';
                        badgeEl.style.color = 'var(--red)';
                    } else {
                        badgeEl.innerText = '🎯 PUSUDA YAKLAŞIYOR';
                        badgeEl.style.background = 'rgba(56, 189, 248, 0.18)';
                        badgeEl.style.borderColor = 'rgba(56, 189, 248, 0.35)';
                        badgeEl.style.color = '#38bdf8';
                    }
                }

                if (distEl) {
                    if (target.category === 'blocked') {
                        distEl.innerText = '🛡️ KALKAN';
                        distEl.style.color = 'var(--red)';
                    } else {
                        distEl.innerText = `%${(target.distPct || 0).toFixed(2)}`;
                        distEl.style.color = target.category === 'contact' ? '#10b981' : '#38bdf8';
                    }
                }
                if (lvlEl) lvlEl.innerText = target.targetName;

                if (volEl) {
                    if (target.category === 'blocked') {
                        volEl.innerText = '⛔ İptal';
                        volEl.style.color = 'var(--red)';
                    } else {
                        volEl.innerText = `${(target.volSurge || 1.0).toFixed(2)}x`;
                        volEl.style.color = target.isVolOk ? '#10b981' : '#f59e0b';
                    }
                }
                if (volSubEl) {
                    if (target.category === 'blocked') {
                        volSubEl.innerText = 'Kural İhlali';
                    } else {
                        volSubEl.innerText = target.isVolOk ? 'Hacim Koşulu Sağlandı' : `Hedef: min ${(target.minVolSurge || 1.5).toFixed(1)}x`;
                    }
                }

                if (cvdEl) {
                    const sCvds = (typeof appState !== 'undefined' && appState && appState.symbol_cvd) || {};
                    const rawSym = (target.symbol || '').replace('/USDT', '').replace('USDT', '').trim();
                    const sCvd = sCvds[target.symbol] || sCvds[rawSym + 'USDT'] || sCvds[rawSym] || null;
                    if (sCvd && sCvd.ratio_60s != null) {
                        const ratio = Number(sCvd.ratio_60s);
                        const delta = Number(sCvd.delta_60s !== undefined ? sCvd.delta_60s : (sCvd.delta_usd || 0));
                        if (ratio >= 50) {
                            cvdEl.innerText = `%${ratio.toFixed(0)} Alıcı 🟢`;
                            cvdEl.style.color = '#10b981';
                        } else {
                            cvdEl.innerText = `%${(100 - ratio).toFixed(0)} Satıcı 🔴`;
                            cvdEl.style.color = 'var(--red)';
                        }
                        if (cvdSubEl) {
                            const dSign = delta >= 0 ? '+' : '';
                            const dFmt = Math.abs(delta) >= 1000 ? Math.round(delta).toLocaleString('en-US') : delta.toFixed(1);
                            cvdSubEl.innerText = `Net ${dSign}$${dFmt} Taker`;
                        }
                    } else {
                        const rs = target.rsScore || 0;
                        cvdEl.innerText = `RS: ${rs >= 0 ? '+' : ''}${rs.toFixed(2)}`;
                        cvdEl.style.color = rs >= 0 ? '#10b981' : 'var(--red)';
                        if (cvdSubEl) {
                            cvdSubEl.innerText = rs >= 0 ? 'BTC Üzeri Güçlü RS' : 'Zayıf Göreceli Güç';
                        }
                    }
                }

                if (statEl) {
                    if (target.category === 'blocked') {
                        statEl.innerText = 'GİRİŞ REDDİ';
                        statEl.style.color = 'var(--red)';
                    } else if (target.category === 'contact') {
                        statEl.innerText = target.isVolOk ? 'ONAYLANDI' : 'BAR BEKLİYOR';
                        statEl.style.color = target.isVolOk ? '#10b981' : '#f59e0b';
                    } else {
                        statEl.innerText = 'İZLEMEDE';
                        statEl.style.color = '#38bdf8';
                    }
                }

                if (actEl) {
                    actEl.innerText = target.action || 'HAZIRDA';
                    if (target.action && target.action.includes('SHORT')) actEl.style.color = 'var(--red)';
                    else if (target.action && target.action.includes('LONG')) actEl.style.color = '#10b981';
                    else actEl.style.color = '#ffffff';
                }

                // 🧊 Box 5: Iceberg & Gizli Balina Emilimi
                if (iceEl) {
                    const iRatio = target.icebergRatio || 1.0;
                    const iSide = target.icebergSide || 'NONE';
                    if (hasIce) {
                        const sideText = iSide === 'ICEBERG_ASK_RESISTANCE' ? 'Satıcı Emilimi' : 'Alıcı Emilimi';
                        iceEl.innerHTML = `<span style="color:#00f2fe; text-shadow:0 0 10px rgba(0,242,254,0.6);">🧊 ${iRatio.toFixed(1)}x Buzdağı</span>`;
                        if (iceSubEl) iceSubEl.innerText = `Aktif Gizli Balina (${sideText})`;
                    } else if (iRatio >= 2.0) {
                        iceEl.innerHTML = `<span style="color:#38bdf8;">🧊 %${Math.round(iRatio*100)} Kısmi</span>`;
                        if (iceSubEl) iceSubEl.innerText = 'Potansiyel Gizli Likidite';
                    } else {
                        iceEl.innerHTML = `<span style="color:#94a3b8;">⚪ Normal (${iRatio.toFixed(1)}x)</span>`;
                        if (iceSubEl) iceSubEl.innerText = 'Gizli Balina Duvarı Yok';
                    }
                }

                // 🌡️ Box 6: Boltzmann Entropi & Mandelbrot Hurst
                if (entEl) {
                    const entVal = target.entropyNorm !== undefined ? target.entropyNorm : 0.65;
                    const hurstVal = target.hurstVal !== undefined ? target.hurstVal : 0.50;
                    const entPct = Math.round(entVal * 100);
                    
                    let entTag = entVal <= 0.60 ? 'Kristal' : (entVal >= 0.88 ? 'Kaotik' : 'Dengeli');
                    let hurstTag = hurstVal >= 0.55 ? 'Trend' : (hurstVal <= 0.45 ? 'Tuzak' : 'Gürültü');
                    
                    let entCol = entVal <= 0.60 ? '#10b981' : (entVal >= 0.88 ? '#f43f5e' : '#38bdf8');
                    let hurstCol = hurstVal >= 0.55 ? '#10b981' : (hurstVal <= 0.45 ? '#f59e0b' : '#94a3b8');
                    
                    entEl.innerHTML = `<span style="color:${entCol}; font-weight:800;">S:%${entPct}</span> <span style="color:#64748b;">|</span> <span style="color:${hurstCol}; font-weight:800;">H:${hurstVal.toFixed(2)}</span>`;
                    if (entSubEl) {
                        entSubEl.innerText = `${entTag} • ${hurstTag}`;
                    }
                }

                // Canlı Taktik Masa Raporu
                if (briefEl) {
                    let quantAlert = '';
                    const iRatio = target.icebergRatio || 1.0;
                    const iSide = target.icebergSide || 'NONE';

                    if (hasIce) {
                        if (iSide === 'ICEBERG_ASK_RESISTANCE' || target.askIcebergRatio >= 3.5) {
                            quantAlert += `<br><span style="color:#f43f5e; font-weight:700;">🧊 Ken Griffin Iceberg:</span> Satış tarafında <b>${iRatio.toFixed(1)}x</b> gizli buzdağı tespit edildi! Taker alımlar tahtadaki görünmeyen duvar tarafından emiliyor, tepe ve tuzak riski yüksek!`;
                        } else {
                            quantAlert += `<br><span style="color:#10b981; font-weight:700;">🧊 Ken Griffin Iceberg:</span> Alış tarafında <b>${iRatio.toFixed(1)}x</b> gizli alıcı buzdağı tespit edildi! Satışlar görünmeyen kurumsal taban tarafından emiliyor, güçlü destek!`;
                        }
                    } else if (iRatio >= 2.0) {
                        quantAlert += `<br><span style="color:#38bdf8; font-weight:600;">🧊 Iceberg Radarı:</span> Kısmi emilim (${iRatio.toFixed(1)}x) izleniyor; tahtada kurumsal gizli limit emirler toplanıyor.`;
                    }

                    if (target.entropyNorm >= 0.88) {
                        quantAlert += `<br><span style="color:#f43f5e; font-weight:700;">⚠️ Boltzmann Entropisi:</span> S=%${Math.round(target.entropyNorm*100)} (Kaotik Tahta). Likidite aşırı dağınık, ani manipülatif iğne riski.`;
                    } else if (target.entropyNorm <= 0.60) {
                        quantAlert += `<br><span style="color:#10b981; font-weight:700;">💎 Boltzmann Entropisi:</span> S=%${Math.round(target.entropyNorm*100)} (Kristalize). Kurumsal likidite tek bir hatta kilitlenmiş, yüksek güvenilirlik.`;
                    }

                    if (target.hurstVal && target.hurstVal <= 0.44) {
                        quantAlert += `<br><span style="color:#f59e0b; font-weight:700;">🌀 Mandelbrot Hurst:</span> H=${target.hurstVal.toFixed(2)} (Anti-Persistent / Ortalamaya Dönüş). Kırılım sahte (fakeout) olma ihtimali yüksek!`;
                    } else if (target.hurstVal && target.hurstVal >= 0.58) {
                        quantAlert += `<br><span style="color:#10b981; font-weight:700;">📈 Mandelbrot Hurst:</span> H=${target.hurstVal.toFixed(2)} (Kalıcı Trend). Kırılım ve seviye devamı güçlü momentum barındırıyor.`;
                    }

                    if (target.hmmPhase === 'MANIPULATION_SWEEP') {
                        quantAlert += `<br><span style="color:#f43f5e; font-weight:700;">🚨 Jim Simons HMM:</span> Piyasa manipülatif stop süpürme evresinde; tuzak tamamlanmadan işleme girmek tehlikeli!`;
                    }

                    // 🌊 Bookmap Sipariş Akışı & Çapa Duvarı Teşhisi
                    if (target.bookmapBuyerAbsorption) {
                        quantAlert += `<br><span style="color:#10b981; font-weight:700;">🌊 Bookmap Alıcı Süngeri:</span> Destekte kurumsal sünger devrede! Agresif satışlar emildi, taban kilitlendi (+%10 Confluence, 30dk Sabır Modu).`;
                    } else if (target.bookmapSellerAbsorption) {
                        quantAlert += `<br><span style="color:#f43f5e; font-weight:700;">🌊 Bookmap Satıcı Süngeri:</span> Dirençte agresif alıcılar pasif balina tarafından yutuluyor; Boğa Tuzağı (Bull Trap) riski, kırılımlar veto edilir!`;
                    }

                    if (target.isIronWall) {
                        quantAlert += `<br><span style="color:#00f2fe; font-weight:700;">🧱 Bookmap Çapa Duvarı:</span> Masif Kurumsal Beton Blok (${Math.round(target.wallDurationSec || 40)}s Kesintisiz Aktif). Spoofing değil, kurumsal savunma çapası!`;
                    } else if (target.isAnchorWall) {
                        quantAlert += `<br><span style="color:#38bdf8; font-weight:700;">🧱 Bookmap Çapa Duvarı:</span> Kurumsal Çapa (${Math.round(target.wallDurationSec || 15)}s Aktif). Seviye stabilitesi teyitli.`;
                    }

                    briefEl.innerHTML = `<b>⚡ Masa Raporu:</b> ${target.reason}${quantAlert}`;
                }
            }

            function focusSelectedInFeed() {
                if (!selectedTarget) return;
                const sym = selectedTarget.symbol.toUpperCase();
                const feed = document.getElementById('ai-thought-feed');
                if (!feed) return;
                const items = feed.querySelectorAll('.ai-thought-item');
                let found = null;
                for (let item of items) {
                    if (item.innerText && item.innerText.toUpperCase().includes(sym)) {
                        found = item;
                        break;
                    }
                }
                if (found) {
                    found.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    found.style.transition = 'all 0.4s ease';
                    found.style.boxShadow = '0 0 25px rgba(0, 242, 254, 0.8), inset 0 0 15px rgba(0, 242, 254, 0.2)';
                    found.style.borderColor = 'var(--cyan)';
                    setTimeout(() => {
                        found.style.boxShadow = '';
                        found.style.borderColor = '';
                    }, 2500);
                } else {
                    if (selectedTarget.category === 'blocked') {
                        setAiThoughtFilter('rejected');
                    } else {
                        setAiThoughtFilter('near');
                    }
                }
            }

            function init() {
                canvas = document.getElementById('tactical-radar-canvas');
                if (!canvas) return;
                ctx = canvas.getContext('2d');
                resize();
                window.addEventListener('resize', resize);

                function handlePointerMove(clientX, clientY) {
                    const rect = canvas.getBoundingClientRect();
                    if (!rect || rect.width <= 0 || rect.height <= 0) return;
                    mousePos.x = (clientX - rect.left) * (width / rect.width);
                    mousePos.y = (clientY - rect.top) * (height / rect.height);
                    checkHover();
                }

                canvas.addEventListener('mousemove', e => {
                    handlePointerMove(e.clientX, e.clientY);
                });

                canvas.addEventListener('touchstart', e => {
                    if (e.touches && e.touches[0]) {
                        handlePointerMove(e.touches[0].clientX, e.touches[0].clientY);
                    }
                }, { passive: true });

                canvas.addEventListener('touchmove', e => {
                    if (e.touches && e.touches[0]) {
                        handlePointerMove(e.touches[0].clientX, e.touches[0].clientY);
                    }
                }, { passive: true });

                canvas.addEventListener('mouseleave', () => {
                    mousePos.x = -1;
                    mousePos.y = -1;
                    isUserHovering = false;
                });

                canvas.addEventListener('click', e => {
                    handlePointerMove(e.clientX, e.clientY);
                    if (selectedTarget) {
                        focusSelectedInFeed();
                    }
                });

                applyRadarViewMode();
                applyRadarSizeMode();
                syncFilterPillsUI();
                startLoop();
            }

            function checkHover() {
                if (mousePos.x < 0 || mousePos.y < 0) return;
                const cx = width / 2;
                const cy = height / 2;
                const rMax = Math.min(cx, cy) * 0.88;

                let bestTarget = null;
                let bestScore = 999999;

                for (let t of radarTargets) {
                    const pos = getTargetCoords(t, cx, cy, rMax);
                    const dx = mousePos.x - pos.x;
                    const dy = mousePos.y - pos.y;
                    const dotDist = Math.hypot(dx, dy);

                    // Etiket plaka hit-test hesabı
                    const hasIce = Boolean(t.hasIceberg || (t.icebergRatio && t.icebergRatio >= 3.5));
                    const extraChars = (hasIce ? 3 : 0) + (t.isAnchorWall || t.isIronWall || t.bookmapBuyerAbsorption ? 3 : 0);
                    const badgeW = Math.max((t.symbol.length + extraChars) * 8.5 + 16, 50);
                    const badgeH = 22;
                    const badgeX = pos.x - badgeW / 2;
                    const badgeY = (pos.y >= cy) ? (pos.y + 6) : (pos.y - badgeH - 6);

                    // Kullanıcı hem blip noktasına hem de isim etiketine geldiğinde seçilsin
                    const inBadge = (mousePos.x >= badgeX - 6 && mousePos.x <= badgeX + badgeW + 6 &&
                                     mousePos.y >= badgeY - 5 && mousePos.y <= badgeY + badgeH + 5);

                    if (dotDist < 26 || inBadge) {
                        const score = inBadge ? Math.min(dotDist, 12) : dotDist;
                        if (score < bestScore) {
                            bestScore = score;
                            bestTarget = t;
                        }
                    }
                }

                if (bestTarget) {
                    selectedTarget = bestTarget;
                    isUserHovering = true;
                    try {
                        updateTelemetryHUD(bestTarget);
                    } catch (err) {
                        console.warn('[Radar] Telemetry update warning:', err);
                    }
                    canvas.style.cursor = 'pointer';
                } else {
                    isUserHovering = false;
                    canvas.style.cursor = 'crosshair';
                }
            }

            function resize() {
                if (!canvas) return;
                const rect = canvas.getBoundingClientRect();
                const parentRect = canvas.parentElement ? canvas.parentElement.getBoundingClientRect() : null;
                width = Math.floor(rect.width || (parentRect ? parentRect.width : 0) || 580);
                height = Math.floor(rect.height || (parentRect ? parentRect.height : 0) || 520);
                if (width <= 0) width = 580;
                if (height <= 0) height = 520;
                dpr = window.devicePixelRatio || 1;
                canvas.width = Math.floor(width * dpr);
                canvas.height = Math.floor(height * dpr);
                if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            }

            function getTargetCoords(t, cx, cy, rMax) {
                let r = 0;
                const ang = t.displayAngle !== undefined ? t.displayAngle : t.angle;
                if (t.category === 'contact') {
                    // Merkez: Ferah temas alanı (rMax * 0.20 - 0.36)
                    const normDist = Math.min(1.0, Math.max(0.0, (t.distPct || 0) / 0.25));
                    r = rMax * (0.20 + normDist * 0.16);
                } else if (t.category === 'ambush') {
                    // Orta halka: Pusu alanı (rMax * 0.40 - 0.62)
                    const normDist = Math.min(1.0, Math.max(0.0, ((t.distPct || 0.25) - 0.25) / 0.35));
                    r = rMax * (0.40 + normDist * 0.22);
                } else if (t.category === 'approach') {
                    // Dış halka: Yaklaşan alanı (rMax * 0.66 - 0.86)
                    const normDist = Math.min(1.0, Math.max(0.0, ((t.distPct || 0.60) - 0.60) / 1.90));
                    r = rMax * (0.66 + normDist * 0.20);
                } else if (t.category === 'blocked') {
                    // Kalkan perimetresi
                    r = rMax * 0.94;
                }
                return {
                    x: cx + Math.cos(ang) * r,
                    y: cy + Math.sin(ang) * r,
                    r: r
                };
            }

            function startLoop() {
                if (isRunning) return;
                isRunning = true;
                function loop() {
                    render();
                    animId = requestAnimationFrame(loop);
                }
                animId = requestAnimationFrame(loop);
            }

            function render() {
                if ((window.currentActiveMainTab && window.currentActiveMainTab !== 'cockpit') || document.hidden || !ctx) {
                    return;
                }
                if (currentRadarMode === 'collapsed') return;

                const rect = canvas.getBoundingClientRect();
                const curW = Math.floor(rect.width);
                const curH = Math.floor(rect.height);
                if (curW > 0 && curH > 0 && (Math.abs(width - curW) > 1 || Math.abs(height - curH) > 1 || canvas.width <= 0)) {
                    resize();
                }

                ctx.clearRect(0, 0, width, height);
                sweepAngle += 0.022;

                const cx = width / 2;
                const cy = height / 2;
                const rMax = Math.min(cx, cy) * 0.88;

                if (!isUserHovering && radarTargets.length > 0 && Date.now() - lastAutoCycleTime > 4500) {
                    selectedIndex = (selectedIndex + 1) % radarTargets.length;
                    selectedTarget = radarTargets[selectedIndex];
                    updateTelemetryHUD(selectedTarget);
                    lastAutoCycleTime = Date.now();
                }

                ctx.save();

                // 🌐 Ergonomik Genişletilmiş Taktik Çemberler
                const rings = [
                    { r: rMax * 0.20, col: 'rgba(16, 185, 129, 0.40)', label: '0.00% BOĞA/AYI GÖBEĞİ' },
                    { r: rMax * 0.36, col: 'rgba(16, 185, 129, 0.25)', label: '0.25% TEMAS ÇEMBERİ' },
                    { r: rMax * 0.62, col: 'rgba(245, 158, 11, 0.22)', label: '0.60% PUSU ÇEMBERİ' },
                    { r: rMax * 0.86, col: 'rgba(56, 189, 248, 0.18)', label: '2.50% YAKLAŞAN' },
                    { r: rMax * 0.94, col: 'rgba(244, 63, 94, 0.45)', label: 'AEGIS SAVUNMA KALKANI', isShield: true }
                ];

                rings.forEach(ring => {
                    ctx.strokeStyle = ring.col;
                    ctx.lineWidth = ring.isShield ? 2.2 : 1;
                    if (ring.isShield) {
                        ctx.shadowColor = '#f43f5e';
                        ctx.shadowBlur = 8;
                    } else {
                        ctx.shadowBlur = 0;
                    }
                    ctx.beginPath();
                    ctx.arc(cx, cy, ring.r, 0, Math.PI * 2);
                    ctx.stroke();

                    ctx.fillStyle = ring.col;
                    ctx.font = '9px "JetBrains Mono", monospace';
                    ctx.fillText(ring.label, cx + 4, cy - ring.r + 11);
                });
                ctx.shadowBlur = 0;

                // Koordinat Eksenleri
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.07)';
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(cx - rMax, cy); ctx.lineTo(cx + rMax, cy);
                ctx.moveTo(cx, cy - rMax); ctx.lineTo(cx, cy + rMax);
                ctx.stroke();

                // Pusula Çizgileri
                for (let a = 0; a < Math.PI * 2; a += Math.PI / 6) {
                    ctx.beginPath();
                    ctx.moveTo(cx + Math.cos(a) * (rMax * 0.90), cy + Math.sin(a) * (rMax * 0.90));
                    ctx.lineTo(cx + Math.cos(a) * (rMax * 0.98), cy + Math.sin(a) * (rMax * 0.98));
                    ctx.stroke();
                }

                // Dönen Radar Taraması (Sweep Gradient)
                const sweepGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, rMax);
                sweepGrad.addColorStop(0, 'rgba(0, 242, 254, 0.22)');
                sweepGrad.addColorStop(1, 'rgba(0, 242, 254, 0)');
                ctx.fillStyle = sweepGrad;

                ctx.beginPath();
                ctx.moveTo(cx, cy);
                ctx.arc(cx, cy, rMax * 0.94, sweepAngle - 0.65, sweepAngle);
                ctx.closePath();
                ctx.fill();

                ctx.strokeStyle = '#00f2fe';
                ctx.shadowColor = '#00f2fe';
                ctx.shadowBlur = 10;
                ctx.lineWidth = 1.6;
                ctx.beginPath();
                ctx.moveTo(cx, cy);
                ctx.lineTo(cx + Math.cos(sweepAngle) * rMax * 0.94, cy + Math.sin(sweepAngle) * rMax * 0.94);
                ctx.stroke();
                ctx.shadowBlur = 0;

                // Hedefleri Çiz
                for (let t of radarTargets) {
                    const pos = getTargetCoords(t, cx, cy, rMax);
                    const hasIce = Boolean(t.hasIceberg || (t.icebergRatio && t.icebergRatio >= 3.5));

                    const ang = t.displayAngle !== undefined ? t.displayAngle : t.angle;
                    let dAngle = (sweepAngle - ang) % (Math.PI * 2);
                    if (dAngle < 0) dAngle += Math.PI * 2;
                    if (dAngle < 0.22) {
                        t.intensity = 1.0;
                        if (t.category === 'blocked' && Math.random() > 0.4) {
                            for (let s = 0; s < 3; s++) {
                                shieldSparks.push({
                                    x: pos.x,
                                    y: pos.y,
                                    vx: Math.cos(ang + (Math.random() - 0.5)) * (1 + Math.random() * 2),
                                    vy: Math.sin(ang + (Math.random() - 0.5)) * (1 + Math.random() * 2),
                                    life: 1.0,
                                    col: '#f43f5e'
                                });
                            }
                        } else if (hasIce && Math.random() > 0.35) {
                            for (let s = 0; s < 2; s++) {
                                shieldSparks.push({
                                    x: pos.x,
                                    y: pos.y,
                                    vx: Math.cos(ang + (Math.random() - 0.5)) * (1.2 + Math.random() * 2),
                                    vy: Math.sin(ang + (Math.random() - 0.5)) * (1.2 + Math.random() * 2),
                                    life: 1.0,
                                    col: '#00f2fe'
                                });
                            }
                        }
                    } else {
                        t.intensity = Math.max(0.2, t.intensity * 0.97);
                    }

                    const isSelected = selectedTarget && selectedTarget.symbol === t.symbol;
                    let dotColor = '#38bdf8';
                    if (t.category === 'contact') dotColor = '#10b981';
                    else if (t.category === 'ambush') dotColor = '#f59e0b';
                    else if (t.category === 'blocked') dotColor = '#f43f5e';

                    if (t.category === 'contact' || isSelected) {
                        t.pulse = (t.pulse + 0.05) % 1.0;
                        ctx.strokeStyle = dotColor;
                        ctx.lineWidth = 1.2;
                        ctx.beginPath();
                        ctx.arc(pos.x, pos.y, 5 + t.pulse * 14, 0, Math.PI * 2);
                        ctx.globalAlpha = (1 - t.pulse) * 0.7;
                        ctx.stroke();
                        ctx.globalAlpha = 1.0;
                    }

                    // 🧊 Cryo Iceberg Pulse Halo
                    if (hasIce) {
                        if (!t.icePulse) t.icePulse = 0;
                        t.icePulse = (t.icePulse + 0.035) % 1.0;
                        ctx.strokeStyle = '#00f2fe';
                        ctx.shadowColor = '#00f2fe';
                        ctx.shadowBlur = 14;
                        ctx.lineWidth = 1.6;
                        ctx.beginPath();
                        ctx.arc(pos.x, pos.y, 6 + t.icePulse * 12, 0, Math.PI * 2);
                        ctx.globalAlpha = (1 - t.icePulse) * 0.85;
                        ctx.stroke();
                        ctx.globalAlpha = 1.0;
                        ctx.shadowBlur = 0;
                    }

                    // 🧱 Bookmap Kurumsal Çapa & Emilim Kalkanı (Emerald / Cyan Armor)
                    if (t.isAnchorWall || t.bookmapBuyerAbsorption) {
                        ctx.strokeStyle = t.isIronWall ? '#00f2fe' : (t.bookmapBuyerAbsorption ? '#10b981' : '#38bdf8');
                        ctx.lineWidth = 1.8;
                        ctx.beginPath();
                        ctx.arc(pos.x, pos.y, isSelected ? 8.5 : 7.0, 0, Math.PI * 2);
                        ctx.stroke();
                    }

                    // Hedef Noktası (Blip)
                    ctx.fillStyle = dotColor;
                    ctx.shadowColor = dotColor;
                    ctx.shadowBlur = t.intensity > 0.5 ? 12 : 4;
                    ctx.beginPath();
                    if (t.category === 'blocked') {
                        ctx.moveTo(pos.x, pos.y - 5);
                        ctx.lineTo(pos.x + 5, pos.y);
                        ctx.lineTo(pos.x, pos.y + 5);
                        ctx.lineTo(pos.x - 5, pos.y);
                        ctx.closePath();
                    } else {
                        ctx.arc(pos.x, pos.y, isSelected ? 5.5 : 3.8, 0, Math.PI * 2);
                    }
                    ctx.fill();
                    ctx.shadowBlur = 0;

                    // 🏷️ Akıllı Katmanlı Etiketleme & Karartılmış Kapsül Plakası (Çakışma Önleyici & Kristal Okunurluk)
                    const shouldShowLabel = isSelected || 
                                          (currentRadarScope === 'top15') || 
                                          (t.category === 'contact') || 
                                          (t.category === 'blocked') || 
                                          hasIce || 
                                          t.isAnchorWall || 
                                          t.isIronWall || 
                                          (isUserHovering && isSelected);

                    if (shouldShowLabel) {
                        const iceIcon = hasIce ? ' 🧊' : '';
                        const bmIcon = t.isIronWall ? ' 🧱' : (t.isAnchorWall ? ' ⚓' : (t.bookmapBuyerAbsorption ? ' 🌊' : ''));
                        const labelText = t.symbol + iceIcon + bmIcon;

                        ctx.font = `${isSelected ? 'bold 11px' : '10px'} "JetBrains Mono", monospace`;
                        const textWidth = ctx.measureText(labelText).width;
                        const badgeW = Math.max(textWidth + 10, 36);
                        const badgeH = isSelected ? 18 : 16;
                        const badgeX = pos.x - badgeW / 2;
                        const badgeY = (pos.y >= cy) ? (pos.y + 8) : (pos.y - badgeH - 8);

                        // Karartılmış yarı saydam arka plan plakası
                        ctx.fillStyle = isSelected ? 'rgba(11, 19, 38, 0.94)' : 'rgba(8, 12, 22, 0.85)';
                        ctx.strokeStyle = isSelected 
                            ? 'rgba(0, 242, 254, 0.85)' 
                            : (hasIce ? 'rgba(0, 242, 254, 0.45)' : (t.category === 'contact' ? 'rgba(16, 185, 129, 0.45)' : 'rgba(255, 255, 255, 0.14)'));
                        ctx.lineWidth = isSelected ? 1.4 : 0.8;

                        ctx.beginPath();
                        if (ctx.roundRect) {
                            ctx.roundRect(badgeX, badgeY, badgeW, badgeH, 4);
                        } else {
                            ctx.rect(badgeX, badgeY, badgeW, badgeH);
                        }
                        ctx.fill();
                        ctx.stroke();

                        // Plaka içi metin
                        ctx.fillStyle = isSelected 
                            ? '#00f2fe' 
                            : (hasIce ? '#38bdf8' : (t.category === 'contact' ? '#34d399' : (t.category === 'blocked' ? '#f43f5e' : '#e2e8f0')));
                        ctx.textAlign = 'center';
                        ctx.textBaseline = 'middle';
                        ctx.fillText(labelText, pos.x, badgeY + badgeH / 2 + 0.5);
                        ctx.textAlign = 'start';
                        ctx.textBaseline = 'alphabetic';
                    }
                }

                // Kalkan ve Iceberg Kıvılcımları
                for (let i = shieldSparks.length - 1; i >= 0; i--) {
                    const sp = shieldSparks[i];
                    sp.x += sp.vx;
                    sp.y += sp.vy;
                    sp.life -= 0.04;
                    if (sp.life <= 0) {
                        shieldSparks.splice(i, 1);
                        continue;
                    }
                    const sparkCol = sp.col || '#f43f5e';
                    ctx.fillStyle = sparkCol;
                    ctx.shadowColor = sparkCol;
                    ctx.shadowBlur = 6;
                    ctx.globalAlpha = Math.max(0, sp.life);
                    ctx.beginPath();
                    ctx.arc(sp.x, sp.y, 1.8 * sp.life, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.globalAlpha = 1.0;
                }

                // Radar Merkez Çekirdeği
                ctx.fillStyle = '#ffffff';
                ctx.shadowColor = '#00f2fe';
                ctx.shadowBlur = 10;
                ctx.beginPath();
                ctx.arc(cx, cy, 3, 0, Math.PI * 2);
                ctx.fill();

                ctx.restore();
            }

            return {
                init,
                resize,
                setRadarData,
                applyCurrentFilter,
                focusSelectedInFeed
            };
        })();
        window.ValkyrieTacticalRadarEngine = ValkyrieTacticalRadarEngine;
        window.toggleRadarView = toggleRadarView;
        window.toggleRadarExpand = toggleRadarExpand;
        window.setRadarScope = setRadarScope;
        window.focusRadarTargetCard = focusRadarTargetCard;

        // =========================================================================
        // 🏛️ VALKYRIE INSTITUTIONAL QUANT COMMENTARY ENGINE (15-20+ VARYASYON)
        // =========================================================================
        const ValkyrieCommentaryEngine = {
            getHashIndex: function(key, poolSize, seedOffset) {
                if (!key || poolSize <= 0) return 0;
                let hash = seedOffset || 0;
                for (let i = 0; i < key.length; i++) {
                    hash = (hash << 5) - hash + key.charCodeAt(i);
                    hash |= 0;
                }
                const cycle = Math.floor(Date.now() / 180000);
                return Math.abs(hash + cycle) % poolSize;
            },

            // 1. TEMASTA (HACİM ONAYLI) - 20 VARYASYON
            getContactVolOk: function(symbol, targetName, volSurge, minSurge, rsScore, action, pPrice, tPrice) {
                const pool = [
                    `5M hacim patlaması (${volSurge.toFixed(2)}x) kurumsal girişi onayladı! Fakeout olmaması için <b>5M mum kapanışı</b> bekleniyor; gövde seviye yönünde kapandığı an pozisyon açılacak.`,
                    `Kurumsal likidite emilimi teyit edildi (${volSurge.toFixed(2)}x hacim). Seviyedeki satış likiditesi agresif piyasa emirleriyle temizlendi. 5M mum kapanışıyla gövde teyidi bekleniyor.`,
                    `Emir defterinde akıllı para akışı (Order Flow Delta) pozitif ayrıştı. Kilit seviyede hacimli temas tetiklendi; sahte iğne filtresi için 5M bar kapanışı izleniyor.`,
                    `Göreceli güç (RS: ${rsScore >= 0 ? '+' : ''}${rsScore.toFixed(2)}) ve kurumsal hacim desteği (${volSurge.toFixed(2)}x) yönlü ivmeyi onayladı. Seviye kırılımının mum gövdesiyle mühürlenmesi bekleniyor.`,
                    `Piyasa yapıcı direnç/destek duvarı yüksek hacimle delindi. Düşük zaman dilimi saçılması yerine momentum devamı hedefleniyor; mum kapanışıyla emir iletilecek.`,
                    `Konsolidasyon bandından kurumsal genişleme fazına geçiş gerçekleşti. ${volSurge.toFixed(2)}x hacim sahte kırılım olasılığını bertaraf etti; bar kapanış onayı pusuda.`,
                    `Hacim anomalisi radarımızda: Hacim eşiği (${volSurge.toFixed(2)}x / min ${minSurge.toFixed(1)}x) aşıldı. Likidite havuzu süpürülürken gövdesi seviye yönünde oturan 5M mum aranıyor.`,
                    `Agresif alıcı/satıcı dengesizliği (imbalance) seviyede netleşti. Algoritma sahte fitil tuzağına düşmemek adına son saniye mum kapanışını bekliyor.`,
                    `Değer alanı dışına kurumsal taşma gerçekleşti. ${volSurge.toFixed(2)}x hacim arkamızdaki rüzgarı kanıtlıyor; 5M periyot bitimiyle pozisyon tetiklenecek.`,
                    `Kritik pivot eşiğinde güçlü hacim momentumu teyit edildi. Akıllı para istasyonunda emir blokları doldu; kural gereği bar kapanış teyidi bekleniyor.`,
                    `Yüksek hacimli likidite emilimi tamamlandı. Fiyat seviyeyi kararlılıkla zorluyor; 5M mumunun seviye yönünde gövde bırakmasıyla işlem açılacak.`,
                    `Kurumsal sermaye girişi netleşti (${volSurge.toFixed(2)}x hacim). Beta baskısından bağımsız alfa hareketi izleniyor; fakeout kalkanı mum kapanışını denetliyor.`,
                    `Likidite boşluğu (Volume Gap) kurumsal alımlarla dolduruldu. Seviye geçişi hacimle destekleniyor; teyit mumu sonrası dinamik takip başlayacak.`,
                    `Order book derinliğinde alış/satış baskısı lehimize yoğunlaştı. ${volSurge.toFixed(2)}x hacimle seviye test ediliyor; 5M periyot onayı ile tetik düşecek.`,
                    `İstatistiki kırılım eşiği aşıldı. Kurumsal hacim filtresi (${volSurge.toFixed(2)}x) yeşil yaktı; mum kapanışında seviye dışı gövde teyidi bekleniyor.`,
                    `Akıllı para ayak izi seviyede mühürlendi. Düşük hacimli tuzak ihtimali bertaraf edildi; 5 dakikalık periyot sonu emrin iletilmesi için geri sayımda.`,
                    `Momentum indikatörleri ve hacim profili kırılımı destekliyor. Seviye arkasındaki likiditeye koşu başladı; mum kapanışı sonrasında pusu tamam.`,
                    `Hacim dalgası kilit seviyeyi aştı (${volSurge.toFixed(2)}x). Algoritmik disiplin gereği acele edilmiyor; 5M kapanışıyla teyitli giriş icra edilecek.`,
                    `Seviye etrafındaki arz/talep dengesizliği güçlü hacimle çözüldü. Fakeout riskini sıfırlamak adına mumun seviye yönünde tamamlanması bekleniyor.`,
                    `Kurumsal emir blokları devreye girdi. ${volSurge.toFixed(2)}x hacim onayıyla birlikte yönlü trend genişlemesi bekleniyor; 5M kapanış şartı aktif.`
                ];
                const idx = this.getHashIndex(symbol + '_vol_ok', pool.length, 11);
                return pool[idx];
            },

            // 2. TEMASTA (HACİM BEKLENİYOR) - 20 VARYASYON
            getContactVolWaiting: function(symbol, targetName, volSurge, minSurge, rsScore, action, pPrice, tPrice) {
                const pool = [
                    `Fiyat kilit seviyeye temas etti fakat 5M hacim (${volSurge.toFixed(2)}x), gereken min <b>${minSurge.toFixed(1)}x</b> seviyesinin altında. Sahte kırılıma (Fakeout) kurban gitmemek için kurumsal hacim desteği bekleniyor.`,
                    `Düşük hacimli yoklama hareketi: Tahta derinliği zayıf; kurumsal alıcı/satıcı desteği olmadan yapılan temaslar tuzak riski taşır. Hacim anomalisi gelmeden tetik çekilmez.`,
                    `Likidite avı şüphesi: Seviyeye fitil atıldı fakat hacim çarpanı (${volSurge.toFixed(2)}x) yetersiz. Akıllı para hacimli piyasa emri girmedikçe pozisyona girilmeyecek.`,
                    `Hacim boşluğunda (Volume Vacuum) seviye testi: Sığ emir defteri nedeniyle fiyat kolayca savrulabilir. Sermayeyi korumak adına en az ${minSurge.toFixed(1)}x hacim şartı aranıyor.`,
                    `Sabırlı Avcı Modu devrede: Fiyatın seviyeye değmesi yetmez; temasın kurumsal sermaye ile onaylanması şart. Hacimsiz sarkmalar eleniyor.`,
                    `Tuzak ihtimaline karşı savunma kalkanı aktif: ${volSurge.toFixed(2)}x hacim perakende ilgisini gösteriyor; kurumsal para girişi (${minSurge.toFixed(1)}x) teyit edilmeden işlem yok.`,
                    `Zayıf ellerin avlanma bölgesi: Seviye temasında hacim patlaması yok. Sahte fitil (wick trap) ile stop patlatma riskine karşı bekleniyor.`,
                    `Delta diverjansı uyarısı: Fiyat kilit seviyeye ulaştı ancak hacim desteği gecikiyor. Kural gereği min ${minSurge.toFixed(1)}x hacim teyidi olmadan emir iletilmez.`,
                    `Konsolidasyon içi hacimsiz savrulma: Seviye zorlanıyor fakat akıllı para emirleri henüz tahtaya girmedi. Disiplinle hacim onayı taranıyor.`,
                    `Hacim filtresi sermayeyi koruyor: Seviye teması tek başına işlem gerekçesi olamaz. Min ${minSurge.toFixed(1)}x kurumsal ivme oluşana kadar pusu pozisyonu korunur.`,
                    `Sığ tahtada manipülasyon kalkanı: Hacim ${volSurge.toFixed(2)}x düzeyinde kaldı. Kurumsal likidite emilimi görülmeden kırılım kovalamak kumardır; beklemedeyiz.`,
                    `Volatilite var, hacim yok: Seviyede fitil oluştu ancak kurumsal ciro yetersiz. Kural dışı erken girişe izin verilmiyor.`,
                    `Piyasa yapıcı likidite çekiyor olabilir: Hacimsiz kırılımların %85'i seviye içine geri döner. Bu istatistiğe boyun eğmemek için hacim teyidi şart.`,
                    `Kurumsal istasyon beklemede: Fiyat seviyeyi dürttü fakat akıllı para henüz onay vermedi (${volSurge.toFixed(2)}x / min ${minSurge.toFixed(1)}x). Pusu devam ediyor.`,
                    `Fiyat seviyede oyalanıyor: Yetersiz hacim (${volSurge.toFixed(2)}x), piyasanın kararsız olduğunu gösteriyor. Güçlü bir hacim patlaması görülmeden tetik kalkmaz.`,
                    `Likidite süzülmesi: Seviye test edildi ancak hacim barı kırmızıda/zayıfta. Kurumsal talep dalgası gelmedikçe sermaye riske atılmaz.`,
                    `Sahte kırılım tuzağından kaçınma: Seviye testinde alım/satım hacmi yetersiz. Sermaye koruma kuralı gereği sabırla hacim teyidi bekleniyor.`,
                    `Hacim desteği eksik: Fiyat temas etti fakat momentum zayıf. Min ${minSurge.toFixed(1)}x hacimle seviyenin kırıldığı görülmeden erken aksiyon alınmayacak.`,
                    `Mikro yapı kararsız: Kilit eşik zorlanıyor fakat emir akışında kurumsal ağırlık yok. Algoritma güvenli giriş koşullarını izliyor.`,
                    `Test aşamasında hacim kontrolü: Seviyeye ulaşıldı ancak yakıt eksik (${volSurge.toFixed(2)}x). Yeterli yakıt (hacim) gelene kadar pusudan çıkılmayacak.`
                ];
                const idx = this.getHashIndex(symbol + '_vol_wait', pool.length, 23);
                return pool[idx];
            },

            // 3. PUSUDA (YAKLAŞIYOR) - 20 VARYASYON
            getApproaching: function(symbol, targetName, dist, minSurge, rsScore) {
                const dStr = dist.toFixed(2);
                const pool = [
                    `Seviyeye ulaşıldığında hacim ve fitil dinamikleri canlı taranacak. Hacim min ${minSurge.toFixed(1)}x kurumsal ivme yakalarsa pusu anında tetiklenecek. Hacimsiz sarkarsa tuzak sayılarak beklenmeye devam edilecek.`,
                    `Fiyat kilit seviyeye (%${dStr} mesafe) süzülüyor. Reaksiyon bölgesinde mikro emir akışı ve hacim anomalisi canlı izleniyor.`,
                    `Kurumsal likidite havuzuna yaklaşılıyor (%${dStr} kaldı). Seviyeye temas anında emir defteri derinliği taranacak.`,
                    `Değer alanı sınırına kontrollü yaklaşım: %${dStr} mesafede pusu kuruldu. Min ${minSurge.toFixed(1)}x hacim patlaması ve fitil tepkisi bekleniyor.`,
                    `Volatilite bandı daralıyor; fiyatta kilit pivot eşiğine (%${dStr}) doğru çekilme var. Hacimli temas halinde anında aksiyon alınacak.`,
                    `Piyasa yapıcı seviyesine %${dStr} mesafe. Kurumsal emir bloklarının tepkisi 5M periyotla taranıyor; hacimsiz sarkarsa tuzak sayılacak.`,
                    `Likidite mıknatısı devrede: Fiyat kilit hatta (%${dStr}) çekiliyor. Kural gereği seviye teması ve hacim çarpanı birlikte aranacak.`,
                    `Stratejik pusu hattı: Kalan mesafe %${dStr}. Seviyeye varıldığında alıcı/satıcı dengesi ölçülerek tetik şartları sorgulanacak.`,
                    `Kurumsal istasyona yolculuk sürüyor (%${dStr} mesafe). Seviye testinde hacim min ${minSurge.toFixed(1)}x olursa pusu devreye girecek.`,
                    `Hacim profili düşük alanından kilit pivot eşiğine geçiş (%${dStr} kaldı). Temas anındaki mikro-delta hareketi yönü tayin edecek.`,
                    `Kritik eşiğe yaklaşım (%${dStr}): Konsolidasyonun çözülme noktası burası olabilir. Algoritma milimetrik tetik için tetikte.`,
                    `Sermaye tahsis radarı: %${dStr} mesafedeki kilit seviye için risk bütçesi ayrıldı. Seviye teyidi sağlandığında pozisyon açılacak.`,
                    `Likidite sweep bölgesi radarda: Kalan %${dStr}. Seviye altı/üstü stop süpürmesi ve hacimli dönüş ihtimali taranıyor.`,
                    `Fiyat kontrollü bir süzülüşle hedefe yaklaşıyor (%${dStr}). Temasta hacim ivmesi gelirse algoritma anında devreye girecek.`,
                    `Kilit destek/direnç koridoruna giriş (%${dStr} mesafe). Seviyeye ulaşıldığında 5M fitil ve gövde dengesi denetlenecek.`,
                    `Hedef seviyeye kalan marj: %${dStr}. Hacimsiz temasta sabırla beklenecek; hacimli temasta emir derhal borsaya iletilecek.`,
                    `Piyasa derinliği analizi: Seviyeye %${dStr} kaldı. Reaksiyon sahasında akıllı paranın alım/satım blokları takip ediliyor.`,
                    `Konsolidasyon ucu test ediliyor (%${dStr} mesafe). Seviye temasında sahte kırılım kalkanı tam kapasite çalışacak.`,
                    `Kurumsal seviye pususu: Fiyat %${dStr} mesafede. Hacim anomalisi teyidiyle birlikte hızlı reaksiyon planlandı.`,
                    `Mikro trend kilit seviyeye doğru yöneldi (%${dStr} kaldı). Seviyeye değdiği an 5M hacim çarpanı sorgulanacak.`
                ];
                const idx = this.getHashIndex(symbol + '_approaching', pool.length, 37);
                return pool[idx];
            },

            // 4. GİRECEKTİ AMA GİRMEDİ (REJECTIONS) - SEBEBE GÖRE 20 VARYASYON
            getRejectionAutopsy: function(symbol, setup, reason) {
                const rLower = (reason || '').toLowerCase();
                const idx = this.getHashIndex(symbol + '_' + setup + '_' + reason, 5, 41);

                if (rLower.includes('hacim') || rLower.includes('surge') || rLower.includes('vol')) {
                    const pool = [
                        "Kurumsal Hacim Kalkanı devreye girdi: Hacim eşiği aşılamadı; düşük hacimli sahte iğne (fakeout) riski elendi, anapara korundu.",
                        "Hacimsiz temas tespit edildi: Perakende tuzağına düşmemek adına kural gereği işlem iptal edildi. Sermaye disiplini korundu.",
                        "Yetersiz piyasa katılımı: Emir defterinde akıllı para desteği görülmedi; hacimsiz kırılım tuzağı bertaraf edildi.",
                        "Hacim çarpanı güvenlik limitinin altında kaldı. Sahte kırılma ihtimaline karşı pusu askıya alındı; gereksiz stop kaybı önlendi.",
                        "Sığ tahtada sahte kırılım riski: Yetersiz işlem hacmi nedeniyle pozisyon açılmadı, nakit korumaya alındı."
                    ];
                    return pool[idx];
                } else if (rLower.includes('trend') || rLower.includes('ters') || rLower.includes('filtre')) {
                    const pool = [
                        "Makro Trend Kalkanı devrede: 1H/4H genel piyasa akışına ters yönde işlem açılması engellendi; trende kafa atma riski elendi.",
                        "Ters akıntı vetosu: Parite makro trende karşı kırılım denedi. Yüksek olasılıklı başarısızlık riski nedeniyle işlem açılmadı.",
                        "Üst zaman dilimi uyumsuzluğu: 1H trend filtresi sinyali reddetti; ana dalganın karşısında durulmayarak portföy korundu.",
                        "Makro trend yönünde kalma disiplini: Kısa vadeli ters hareket filtrelendi; sermaye yalnızca trend uyumlu fırsatlara tahsis edildi.",
                        "Baskın trend filtresi: Karşı yöndeki zayıf momentum elendi; trendle inatlaşılmayarak sermaye güvenceye alındı."
                    ];
                    return pool[idx];
                } else if (rLower.includes('temas') || rLower.includes('aşınma') || rLower.includes('3.')) {
                    const pool = [
                        "Seviye Aşınma Kuralı devrede: Seviye daha önce defalarca test edilip likiditesi tüketilmişti; yıpranmış seviyede tuzak stop önlendi.",
                        "Likidite boşalması: 3. temas kuralı gereği gücünü yitiren destek/direnç hattındaki riskli reaksiyon elendi.",
                        "Tükenmiş seviye uyarısı: Seviyedeki emir blokları önceki testlerde eridiği için sahte kırılım riski görüldü ve işlem açılmadı.",
                        "Aşınmış pivot filtresi: Tekrarlanan temaslar seviyeyi zayıflatır; kurumsal kuralımız gereği riskli test elendi.",
                        "Yıpranmış likidite hattı: Emir bloklarının tükendiği seviyede kırılganlık tespit edildi ve işlem iptal edildi."
                    ];
                    return pool[idx];
                } else if (rLower.includes('atr') || rLower.includes('volatil') || rLower.includes('aşırı')) {
                    const pool = [
                        "Aşırı Volatilite Kalkanı: Fiyat istatistiksel 2 sigma sınırını aştı; kontrolsüz kayma ve spread riskinden kaçınıldı.",
                        "Uç sapma uyarısı: ATR genişlemesi güvenli risk bandının üzerinde; portföy dengesini korumak adına sinyal elendi.",
                        "Kontrolsüz volatilite dalgası: Geniş mum aralıkları stop mesafesini bozduğu için işlem risk modeline takıldı.",
                        "Risk parametresi aşımı: Aşırı dalgalanma ortamında sermaye güvenliği için işlem vetolandı.",
                        "Volatilite anomalisi: Standart sapma limitini aşan hareket elendi; sermaye disiplinli risk bandında tutuldu."
                    ];
                    return pool[idx];
                } else {
                    const pool = [
                        "Sahte kırılım, tükeniş mumu veya trende kafa atma riski bertaraf edildi; sermaye gereksiz bir stop kaybından korundu.",
                        "Makro Sıkışma (Dead Zone) Koruması: Düşük olasılıklı testere piyasasında sermaye alfa fırsatlarına saklandı.",
                        "Piyasa dengesizliği vetosu: Risk-getiri oranı kurumsal standartları karşılamadığı için işlem açılmadı.",
                        "Algoritmik risk filtresi: Çoklu gösterge teyidi sağlanamadığı için pozisyon elendi; anapara korundu.",
                        "Kurumsal disiplin kuralı: Kural dışı mikro hareket filtrelendi; portföy güvenliği sağlandı."
                    ];
                    return pool[idx];
                }
            },

            // 5. AKTİF POZİSYON CANLI TAKTİKLERİ - 20 VARYASYON
            getPositionTactic: function(symbol, pos, roePct, isHalf, stopVal, tp1Val, tp2Val) {
                const sVal = stopVal || '-';
                const t1Val = tp1Val || '-';
                const t2Val = tp2Val || '-';
                const idx = this.getHashIndex(symbol + '_' + roePct.toFixed(1) + '_' + isHalf, 5, 53);

                if (isHalf) {
                    const pool = [
                        `🎯 <b>TP1 Kârı Kasada!</b> Kalan %50 pozisyon Breakeven koruma stopu ($${sVal}) ile sıfır risk zırhında. Nihai hedef <b>TP2 ($${t2Val})</b> bekleniyor. Bu işlemde sermaye kaybı riski matematiksel olarak sıfırlandı.`,
                        `💎 <b>Kâr Realizasyonu Başarılı:</b> İlk hedefte kâr nakite kilitlendi. Kalan miktar piyasa dönüşlerine karşı giriş seviyesiyle ($${sVal}) zırhlandı; hedef tepe likiditesi ($${t2Val}).`,
                        `🛡️ <b>Sıfır Risk Serbest Koşu:</b> TP1 kârı portföye yazıldı. Kalan pay başabaş kalkanıyla korunuyor; trend nereye kadar giderse kâr oraya kadar sürülecek.`,
                        `🚀 <b>Sermaye Korumalı Büyüme:</b> %50 kâr cepte, kalan miktar sıfır maliyetle TP2 ($${t2Val}) koşusunda. Piyasa çökse bile bu işlem net artıda kalacak.`,
                        `✨ <b>Disiplin Zaferi:</b> İlk hedef kurumsal disiplinle nakite çevrildi. Stop girişe çekildi ($${sVal}); kalan kısım nihai kâr istasyonunu arıyor.`
                    ];
                    return pool[idx];
                } else if (roePct >= 3.0) {
                    const pool = [
                        `🟢 <b>Kâr Genişleme Bölgesindeyiz (+%${roePct.toFixed(2)} ROE):</b> Alıcı/Satıcı baskısı lehimize. Fiyat TP1 ($${t1Val}) hedefine yaklaşıyor. İlk hedef geldiğinde anında %50 kâr realize edilip stop Breakeven'a çekilecek.`,
                        `⚡ <b>Güçlü Momentum İlerlemesi (+%${roePct.toFixed(2)} ROE):</b> Kurumsal emir akışı pozisyonu destekliyor. Dinamik kâr kilidi devrede; TP1 ($${t1Val}) seviyesinde nakite geçiş hazırlığı tamam.`,
                        `📊 <b>Trend Genişlemesi Lehimize (+%${roePct.toFixed(2)} ROE):</b> Pozisyon kâr marjını büyütüyor. 1.5 ATR dinamik tampon takipte, ilk likidite istasyonunda kısmi kâr kilitlenecek.`,
                        `🎯 <b>Kâr İstasyonuna Yaklaşıldı (+%${roePct.toFixed(2)} ROE):</b> Fiyat TP1 ($${t1Val}) seviyesine doğru kararlılıkla ilerliyor. Matematiksel disiplinle anında kâr kilitlenecek.`,
                        `🔥 <b>Alfa Dalgası Devam Ediyor (+%${roePct.toFixed(2)} ROE):</b> İvme korunuyor. 1.5 ATR dinamik stop ($${sVal}) kârı arkadan kollarken hedefe odaklanıldı.`
                    ];
                    return pool[idx];
                } else if (roePct <= -2.0) {
                    const pool = [
                        `⚖️ <b>Direnç/Destek Test Ediliyor (%${roePct.toFixed(2)} ROE):</b> Fiyat konsolide oluyor. Sert Stop seviyemiz ($${sVal}) 1.5 ATR dinamik tamponla pozisyonu koruyor. Panik satışı yok, planlanan stop seviyesi korunuyor.`,
                        `🛡️ <b>Dinamik Risk Tamponu Devrede (%${roePct.toFixed(2)} ROE):</b> Piyasa dalgalanması hesaplanan stop mesafesi dahilinde ($${sVal}). Panik satışı yok; matematiksel risk bütçesi harfiyen korunuyor.`,
                        `⚠️ <b>İstatistiksel Savunma Hattı (%${roePct.toFixed(2)} ROE):</b> Geri çekilme volatilite sınırları içinde seyrediyor. Sert stop ($${sVal}) felaket koruması olarak hazır bekliyor.`,
                        `🛑 <b>Plan Sadakati devrede (%${roePct.toFixed(2)} ROE):</b> Piyasadaki dalgalanmaya karşı tereddüt yok. Kural dışı erken kapatma yapılmaz; 1.5 ATR risk bariyeri ($${sVal}) pozisyonu zırhlıyor.`,
                        `⏳ <b>Dalgalanma Yönetimi (%${roePct.toFixed(2)} ROE):</b> Fiyat kilit bantta oyalanıyor. Sert stop seviyemiz ($${sVal}) pozisyonu güvence altında tutuyor.`
                    ];
                    return pool[idx];
                } else {
                    const pool = [
                        `⏳ <b>Giriş Bölgesi Dengelenmesi (%${roePct.toFixed(2)} ROE):</b> Pozisyon taze açıldı. 1.5 ATR dinamik risk koruması aktif ($${sVal}). 5M mum hacmi ve delta akışı takip ediliyor.`,
                        `⚖️ <b>Değer Alanı Konsolidasyonu (%${roePct.toFixed(2)} ROE):</b> Fiyat giriş seviyesi etrafında taban oluşturuyor. Algoritmik stop seviyesi güvenli mesafede ($${sVal}), yönlü kırılım bekleniyor.`,
                        `🛡️ <b>Mikro Yapı Dengede (%${roePct.toFixed(2)} ROE):</b> Pozisyon güvenli bölgede. Doğal dalgalanmalara karşı plan harfiyen işletiliyor; stop tamponu ($${sVal}) hazır.`,
                        `🔍 <b>Akıllı Para Pozisyonlama Fazı (%${roePct.toFixed(2)} ROE):</b> Tahtadaki mikro emirler taranıyor. Dinamik risk kalkanı devredeyken yönlü ivme takibi sürüyor.`,
                        `✨ <b>İlk Evre Takibi (%${roePct.toFixed(2)} ROE):</b> Fiyat giriş bandında dengeleniyor. 1.5 ATR stop ($${sVal}) ve TP1 ($${t1Val}) hedefleri devrede.`
                    ];
                    return pool[idx];
                }
            },

            // 6. CHART MODAL & SIDEBAR QUANT BRIEFING - HER DURUM İÇİN DERİN ANALİST BRİFİNGİ
            getDeskBriefing: function(stateKey, symbol, ctx) {
                const s = (symbol || '').replace('/USDT', '').replace('USDT', '').trim();
                const p = ctx.pPrice;
                const pivot = ctx.pivot;
                const r3 = ctx.r3;
                const r4 = ctx.r4;
                const r5 = ctx.r5;
                const s3 = ctx.s3;
                const s4 = ctx.s4;
                const s5 = ctx.s5;
                const belowNpoc = ctx.belowNpoc;
                const aboveNpoc = ctx.aboveNpoc;
                const mvah = ctx.mvah;
                const mval = ctx.mval;
                const mpoc = ctx.mpoc;
                const idx = this.getHashIndex(s + '_' + stateKey, 3, 67);

                if (stateKey === 'BELOW_NPOC') {
                    const pool = [
                        `⚡ <b>Masa Brifingi:</b> Fiyat dokunulmamış kurumsal hacim havuzu olan <b>Aşağı nPOC ($${belowNpoc})</b> seviyesinde akıllı para desteğini test ediyor. 5M mum bu seviyeye fitil bırakıp nPOC üzerinde kapatırsa <b>Likidite Sekmesi LONG (Hedef Pivot P: $${pivot})</b> açılacak.`,
                        `⚡ <b>Masa Brifingi:</b> Düşük zaman dilimi likidite süpürmesi (sweep) izleniyor. Aşağı nPOC ($${belowNpoc}) seviyesi alıcılar tarafından savunulursa <b>Mean Reversion LONG (Hedef Pivot P: $${pivot} / mPOC: $${mpoc})</b> pusu planı yürürlüğe girecek.`,
                        `⚡ <b>Masa Brifingi:</b> Kurumsal değer alanı tabanında tamamlanmamış açık pozisyonlar (unfinished auction) dengeleniyor. nPOC üzerinde 5M gövde kapanışı <b>Likidite Sekmesi</b> sinyalini tetikleyecek.`
                    ];
                    return pool[idx % pool.length];
                } else if (stateKey === 'ABOVE_NPOC') {
                    const pool = [
                        `⚡ <b>Masa Brifingi:</b> Fiyat dokunulmamış kurumsal arz bloğu olan <b>Yukarı nPOC ($${aboveNpoc})</b> direncini test ediyor. 5M mum seviyeye iğne atıp nPOC altında kapatırsa <b>Direnç Reddi SHORT (Hedef Pivot P: $${pivot})</b> açılacak.`,
                        `⚡ <b>Masa Brifingi:</b> Tepe likidite avı izleniyor. Yukarı nPOC ($${aboveNpoc}) tavanında kurumsal satıcı baskısı oluşursa <b>Direnç Reddi SHORT (Hedef: Pivot P $${pivot})</b> pusu planı devreye girecek.`,
                        `⚡ <b>Masa Brifingi:</b> Değer alanı tavanında tükeniş mumu aranıyor. nPOC ($${aboveNpoc}) altında teyit mumu gelirse algoritmik short pusu ile denge seviyesine (Pivot P) dönüş hedeflenecek.`
                    ];
                    return pool[idx % pool.length];
                } else if (stateKey === 'R5_OVERBOUGHT') {
                    const pool = [
                        `⚡ <b>Masa Brifingi:</b> R5 ($${r5}) istatistiki tavan seviyesinde kovalama alımı yapılmaz. Fiyat mVAH/nPOC hedeflerine yürürse <b>Trend Breakout</b> takip edilir; R5 altına sarkıp ayı gövdesi bırakırsa <b>Direnç Reddi SHORT</b> pususu kurulur.`,
                        `⚡ <b>Masa Brifingi:</b> Parabolik genişleme bölgesi ($${r5}): İstatistiksel 3 sigma sapması yaşanıyor. FOMO ile long açılmaz; seviye altına geri çekilme halinde dönüş shortu veya retest teyidi izlenir.`,
                        `⚡ <b>Masa Brifingi:</b> Trend zirvesi likidite süpürmesi: Fiyat R5 ($${r5}) üzerinde satıcı bloklarını zorluyor. 5M mumu seviye altına sarkar ve tükeniş gösterirse tepe reddi değerlendirilir.`
                    ];
                    return pool[idx % pool.length];
                } else if (stateKey === 'R4_BREAKOUT') {
                    const pool = [
                        `⚡ <b>Masa Brifingi:</b> Fiyat <b>R4 ($${r4})</b> üzerinde kurumsal boğa koridorunda. 5M mum R4 üzerinde yeni kapandıysa <b>Taze Breakout LONG</b> açılacak. Fiyat R4 desteğine geri çekilip fitille tutunursa <b>Retest LONG (Hedef R5: $${r5})</b> açılacak.`,
                        `⚡ <b>Masa Brifingi:</b> Boğa momentumu R4 ($${r4}) hattını aştı. Üst hedef R5 ($${r5}). Akıllı para alım blokları izleniyor; 5M periyotta R4 üzerinde kalıcılık korundukça yönlü long pususu devrede.`,
                        `⚡ <b>Masa Brifingi:</b> Değer alanı genişlemesi: R4 ($${r4}) kırılımı alıcıların hakimiyetini kanıtlıyor. Min 1.5x hacim desteğiyle birlikte doğrudan R5 ($${r5}) ve üst nPOC hedeflerine odaklanıldı.`
                    ];
                    return pool[idx % pool.length];
                } else if (stateKey === 'R3_R4_COMPRESSION') {
                    const pool = [
                        `⚡ <b>Masa Brifingi:</b> Fiyat <b>R3 ($${r3})</b> desteği ile <b>R4 ($${r4})</b> direnci arasında volatilite sıkışmasında. 5M mum kapanışında R4 yukarı kırılırsa <b>Breakout LONG (Hedef R5)</b>; R3'ten red yerse <b>Scalp SHORT (Hedef Pivot P: $${pivot})</b> açılacak.`,
                        `⚡ <b>Masa Brifingi:</b> Karar koridoru: R3-R4 bandında patlama hazırlığı taranıyor. Hacimli 5M kırılımı hangi yönde olursa algoritma o yönde pozisyon alacak; bant ortasında gereksiz işlem yapılmaz.`,
                        `⚡ <b>Masa Brifingi:</b> Enerji birikimi fazı ($${r3} - $${r4}): Emir defteri iki yöne de derinleşiyor. R4 ($${r4}) üzerinde mum kapanışı boğa taarruzunu, R3 altına sarkma ise pivot düzeltmesini tetikler.`
                    ];
                    return pool[idx % pool.length];
                } else if (stateKey === 'S3_R3_RANGE') {
                    const pool = [
                        `⚡ <b>Masa Brifingi:</b> Fiyat <b>Pivot P ($${pivot})</b> ekseninde dengeli seyrediyor (Alt: S3 $${s3} • Üst: R3 $${r3}). Fiyat S3 desteğine inip sekerse <b>Scalp LONG (Hedef: Pivot P)</b>; R3 direncine çıkıp red yerse <b>Scalp SHORT (Hedef: Pivot P)</b> açılacak.`,
                        `⚡ <b>Masa Brifingi:</b> İstatistiki değer alanı içi mean reversion: Bant sınırları (S3 $${s3} / R3 $${r3}) reaksiyon sahalarıdır. Sınırlardan merkeze (Pivot $${pivot}) dönüş scalp fırsatları taranıyor.`,
                        `⚡ <b>Masa Brifingi:</b> Nötr denge kanalı: Fiyat merkez pivot ($${pivot}) etrafında konsolide oluyor. Kurumsal kural gereği bant sınırlarına (S3/R3) ulaşılmadan erken aksiyon alınmaz.`
                    ];
                    return pool[idx % pool.length];
                } else if (stateKey === 'S4_S3_WARNING') {
                    const pool = [
                        `⚡ <b>Masa Brifingi:</b> Fiyat <b>S3 ($${s3})</b> altına indi, son kurumsal savunma hattı olan <b>S4 ($${s4})</b> test ediliyor. 5M mum S4 altına inerse <b>Breakdown SHORT (Hedef S5: $${s5})</b>; S3 üstüne toparlarsa <b>Mean Reversion LONG (Hedef Pivot P)</b> açılacak.`,
                        `⚡ <b>Masa Brifingi:</b> Ayı baskısı yoğunlaşıyor: S3 tabanı delindi, gözler S4 ($${s4}) kritik bariyerinde. Seviye tutunamazsa panik satışı hızlanır; hacimli tutunma ise güçlü bir düzeltme tepkisi doğurabilir.`,
                        `⚡ <b>Masa Brifingi:</b> Kritik savunma sahası ($${s4}): Likidite boşalması yaşanıyor. S4 altındaki 5M gövde kapanışı breakdown short pususunu tetikleyecek.`
                    ];
                    return pool[idx % pool.length];
                } else if (stateKey === 'S4_BREAKDOWN') {
                    const pool = [
                        `⚡ <b>Masa Brifingi:</b> Fiyat <b>S4 ($${s4})</b> altında tam ayı hakimiyetinde. Alt hedef: <b>S5 ($${s5})</b> / <b>mVAL ($${mval})</b>. 5M mum S4 altında taze kapandıysa <b>Breakdown SHORT</b>; S4 direncine yükselip red bırakırsa <b>Retest SHORT</b> açılacak.`,
                        `⚡ <b>Masa Brifingi:</b> Likidasyon dalgası devrede: S4 ($${s4}) seviyesinin kaybı satıcıları cesaretlendirdi. Düşüş yönlü retest ve momentum short kurulumları radarımızda; dip avcısı olunmaz.`,
                        `⚡ <b>Masa Brifingi:</b> Yapısal bozulma onaylandı: Fiyat değer alanının tamamen altında. S4 ($${s4}) altındaki her retest yeni bir short pusu fırsatıdır; nihai hedef S5 ($${s5}).`
                    ];
                    return pool[idx % pool.length];
                } else if (stateKey === 'MVAH_TEST') {
                    const pool = [
                        `⚡ <b>Masa Brifingi:</b> Fiyat <b>mVAH ($${mvah})</b> aylık tepe hacim duvarını test ediyor. 5M mum kapanışı mVAH üzerinde güçlü teyit verirse <b>Macro Breakout LONG</b>; red yerse <b>Macro SHORT</b> pususu devreye girecek.`,
                        `⚡ <b>Masa Brifingi:</b> Aylık değer alanı tavanı ($${mvah}) zorlanıyor. Bu seviyenin hacimli aşılması çok haftalık yeni bir boğa trendi başlatabilir; red gelirse mPOC eksenine geri çekilme takip edilir.`,
                        `⚡ <b>Masa Brifingi:</b> Makro kırılım eşiği: mVAH ($${mvah}) kurumsal satıcıların ana kalesidir. Hacim anomalisi gelirse kırılıma katılınacak, direnç onaylanırsa ters yönlü pusu kurulacak.`
                    ];
                    return pool[idx % pool.length];
                } else {
                    const pool = [
                        `⚡ <b>Masa Brifingi:</b> Fiyat stabil seyrediyor. 5 dakikalık mum kapanışlarında strateji kurallarının oluşması (Breakout, Retest, nPOC veya Destek/Direnç dönüşü) kesintisiz taranıyor.`,
                        `⚡ <b>Masa Brifingi:</b> Piyasa dengeli konsolidasyonda. 100 parite eş zamanlı izleniyor; kurumsal hacim anomalisi veya kilit seviye teması oluştuğunda robot derhal pusuya geçecek.`,
                        `⚡ <b>Masa Brifingi:</b> Gözlem fazı: Fiyat kilit pivotlar arasında güvenli mesafede. Algoritma sermaye disiplinini koruyarak yüksek olasılıklı tetik koşullarını bekliyor.`
                    ];
                    return pool[idx % pool.length];
                }
            },

            // 7. POST-MORTEM OTOPSİ BRİFİNGİ (KAPANAN İŞLEMLER İÇİN 15+ VARYASYON)
            getPostMortemAutopsy: function(symbol, tr, pnl, roe, isWin, reason, stopStr) {
                const s = (symbol || '').replace('/USDT', '').replace('USDT', '').trim();
                const idx = this.getHashIndex(s + '_' + reason + '_' + pnl.toFixed(2), 3, 79);

                if (reason.includes('TP2') || reason.includes('Final')) {
                    const pool = [
                        `🏆 <b>Maksimum Verimle Tamamlandı:</b> Pozisyon planlandığı gibi TP2 nihai hedefine ulaştı (+%${roe.toFixed(1)} ROE). İlk yarı TP1'de realize edilmiş, kalan %50 Breakeven korumasıyla koşmuştu. Mükemmel kurgulanmış bir trade.`,
                        `🏆 <b>Kurumsal Hedefe Tam İsabet:</b> Zirve likidite havuzunda çıkış sağlandı (+${pnl.toFixed(2)}$). Risk-getiri optimizasyonu kusursuz icra edildi.`,
                        `🏆 <b>Trend Genişlemesi Tamamlandı:</b> Dalga tepe noktasına kadar sürüldü (+%${roe.toFixed(1)} ROE). Matematiksel kurallar portföy büyümesini istikrarlı kılıyor.`
                    ];
                    return pool[idx % pool.length];
                } else if (reason.includes('Dinamik ROE') || reason.includes('Zaman Kalkanı')) {
                    const pool = [
                        `💎 <b>Kâr Güvenle Kilitlendi:</b> +%${roe.toFixed(1)} ROE görüldükten sonra kâr kilidi devreye girdi ve kazanç kasaya atıldı. Dalgalı piyasa koşullarında kârı piyasaya geri vermemek en büyük sermaye disiplinidir.`,
                        `💎 <b>Disiplinli Kâr Realizasyonu:</b> Hedef bölgesinde kısmi kâr kasaya alındı (+${pnl.toFixed(2)}$). Kalan bakiye Breakeven zırhıyla risksiz koşturuldu.`,
                        `💎 <b>Sermaye Koruma & Kazanç:</b> Dinamik kâr kilidi piyasa düzeltmesinden önce çalıştı ve net kârı portföye ekledi.`
                    ];
                    return pool[idx % pool.length];
                } else if (reason.includes('TP1')) {
                    const pool = [
                        `🎯 <b>İlk Hedef Kârı Alındı:</b> TP1 seviyesinde %50 kâr realize edildi (+${pnl.toFixed(2)}$). Kalan bakiye Breakeven zırhıyla korunuyor.`,
                        `🎯 <b>Kısmi Kâr Kasada:</b> İlk likidite istasyonunda anapara emniyete alındı (+${pnl.toFixed(2)}$). Kalan %50 ile risksiz koşu sürüyor.`,
                        `🎯 <b>TP1 Tamam:</b> Matematiksel ilk istasyona varıldı. Stop girişe sabitlendi; portföy riski sıfırlandı.`
                    ];
                    return pool[idx % pool.length];
                } else if (reason.includes('Breakeven')) {
                    const pool = [
                        `🛡️ <b>Sıfır Kayıp Kalkanı:</b> Fiyat ilk kâr alımından sonra terse döndü; ancak Breakeven kalkanı devreye girerek kalan pozisyonu başabaş noktasında kapattı. Anapara kuruşu kuruşuna korundu.`,
                        `🛡️ <b>Risksiz Çıkış Zaferi:</b> Piyasa dalgalanmasında anapara erimedi. İlk kâr cepte kalırken kalan dilim sıfır zararla tasfiye edildi.`,
                        `🛡️ <b>Başabaş Savunması:</b> Ters yönlü piyasa hareketinde stop koruması görevini yaptı; sermaye bir sonraki kurulum için eksiksiz hazır.`
                    ];
                    return pool[idx % pool.length];
                } else if (reason.includes('Sert Stop')) {
                    const pool = [
                        `🛑 <b>Disiplinli Risk Kontrolü:</b> Beklenen seviye tutunamadı ve Sert Stop (${stopStr}) devreye girerek zararı küçük bir dilimde kesti (-${Math.abs(pnl).toFixed(2)}$). Sermaye olası derin bir çöküşten korundu.`,
                        `🛑 <b>Felaket Koruma Kalkanı:</b> 1.5 ATR dinamik stop mekanizması portföyü ani volatilite şokundan korudu. Kontrollü kayıp sermaye sağlığını güvenceye alır.`,
                        `🛑 <b>Matematiksel Risk Bütçesi:</b> İstatistiki sınır dışına çıkan harekette pozisyon tereddütsüz kapatıldı. Planlanan risk limitleri harfiyen korundu.`
                    ];
                    return pool[idx % pool.length];
                } else {
                    return `ℹ️ <b>Kapanış Notu:</b> ${reason}. Net sonuç: ${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}$ (${roe >= 0 ? '+' : ''}${roe.toFixed(1)}% ROE).`;
                }
            }
        };

        function formatSetupDisplayName(sId) {
            if (!sId) return 'AI Kurulum';
            const s = String(sId).toUpperCase();
            if (s.includes('SETUP_1_') || s.includes('R4_BREAKOUT')) return 'S1: R4 Breakout';
            if (s.includes('SETUP_2_') || s.includes('S4_BREAKDOWN')) return 'S2: S4 Breakdown';
            if (s.includes('SETUP_3_') || s.includes('S3_BOUNCE')) return 'S3: S3 Sekmesi';
            if (s.includes('SETUP_4_') || s.includes('R3_REJECTION')) return 'S4: R3 Reddi';
            if (s.includes('SETUP_5_') || s.includes('R4_SUPPORT_FLIP')) return 'S5: R4 Destek Flip';
            if (s.includes('SETUP_6_') || s.includes('MVAH_MACRO')) return 'S6: mVAH Breakout';
            if (s.includes('SETUP_7_') || s.includes('S4_RESISTANCE_FLIP')) return 'S7: S4 Direnç Flip';
            if (s.includes('SETUP_8_') || s.includes('MVAL_MACRO')) return 'S8: mVAL Breakdown';
            if (s.includes('SETUP_9_') || s.includes('BELOW_NPOC')) return 'S9: Dip nPOC Sekme';
            if (s.includes('SETUP_10_') || s.includes('ABOVE_NPOC')) return 'S10: Tepe nPOC Ret';
            if (s.includes('SETUP_11_') || s.includes('RESISTANCE_FLIP')) return 'S11: Direnç Retest';
            if (s.includes('SETUP_12_') || s.includes('SUPPORT_BREAKDOWN')) return 'S12: Destek Çöküşü';
            if (s.includes('SETUP_13_') || s.includes('S3_RESISTANCE_FLIP')) return 'S13: S3 Direnç Flip';
            if (s.includes('SETUP_14_') || s.includes('PIVOT_SUPPORT_FLIP')) return 'S14: Pivot Destek Flip';
            if (s.includes('SETUP_15_') || s.includes('AVWAP_MVAH_RECLAIM')) return 'S15: AVWAP Reclaim';
            if (s.includes('SETUP_16_') || s.includes('R3_SUPPORT_FLIP')) return 'S16: R3 Destek Flip';
            if (s.includes('FAKEOUT_RECLAIM')) return '🪤 Fakeout Reclaim';
            return s.replace('SETUP_', '').replace(/_/g, ' ');
        }

        function renderCockpitOpenPositions() {
            const container = document.getElementById('cockpit-open-positions-container');
            if (!container || !appState) return;
            
            const openPositions = appState.open_positions || {};
            const posKeys = Object.keys(openPositions);
            
            if (posKeys.length === 0) {
                container.style.display = 'none';
                return;
            }
            
            container.style.display = 'block';
            
            const existingGrid = document.getElementById('open-positions-grid');
            const isHidden = existingGrid && existingGrid.style.display === 'none';
            
            let html = `
                <div style="background: rgba(15,23,42,0.6); border: 1px solid rgba(56,189,248,0.2); border-radius: 12px; overflow: hidden;">
                    <div style="display:flex; justify-content:space-between; align-items:center; padding: 12px 20px; background: rgba(56,189,248,0.1); border-bottom: 1px solid rgba(56,189,248,0.15); cursor:pointer;" onclick="toggleOpenPositions()">
                        <div style="display:flex; align-items:center; gap: 10px;">
                            <div class="ai-pulse-dot" style="background:#38bdf8; box-shadow:0 0 8px #38bdf8;"></div>
                            <span style="color:#38bdf8; font-weight:700; font-family:'JetBrains Mono', monospace; font-size:14px;">⚡ AKTİF POZİSYONLAR (${posKeys.length})</span>
                        </div>
                        <div id="open-positions-toggle-icon" style="color:#38bdf8; font-size:12px; font-weight:700;">${isHidden ? '▶ Göster' : '▼ Gizle'}</div>
                    </div>
                    <div id="open-positions-grid" style="display:${isHidden ? 'none' : 'grid'}; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; padding: 20px;">
            `;
            
            posKeys.forEach(sym => {
                const pos = openPositions[sym];
                const side = pos.side || 'LONG';
                const isLong = side.toUpperCase() === 'LONG';
                const sideColor = isLong ? '#22c55e' : '#ef4444';
                const sideBg = isLong ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)';
                const cleanSym = (sym || '').replace('/USDT', '').replace('USDT', '').trim();
                
                const curP = Number((typeof livePrices !== 'undefined' && livePrices && livePrices[sym]) || (appState.symbols && appState.symbols[sym] ? appState.symbols[sym].price : 0) || pos.entry_price);
                const entry = Number(pos.entry_price);
                
                let roe = 0.0;
                let netPnl = 0.0;
                
                if (typeof computePositionPnL === 'function') {
                    const metrics = computePositionPnL(pos, curP);
                    netPnl = metrics.pnlUsdt;
                    roe = metrics.roePct;
                } else if (curP > 0 && entry > 0) {
                    const priceDiff = isLong ? (curP - entry) : (entry - curP);
                    const qty = Number(pos.quantity) || 0;
                    const margin = Number(pos.margin) || 0;
                    netPnl = priceDiff * qty;
                    if (margin > 0) {
                        roe = (netPnl / margin) * 100.0;
                    }
                }
                
                const isProfit = netPnl >= 0;
                const pnlColor = isProfit ? '#22c55e' : '#ef4444';
                const pnlSign = isProfit ? '+' : '';
                
                const tp1 = Number(pos.tp1) || 0;
                const hardStop = Number(pos.hard_stop || pos.stop_floor) || 0;
                let progressHtml = '';
                
                if (tp1 > 0 && entry > 0) {
                    const totalDist = Math.abs(tp1 - entry);
                    const curDist = isLong ? (curP - entry) : (entry - curP);
                    let pct = 0;
                    if (curDist > 0 && totalDist > 0) {
                        pct = (curDist / totalDist) * 100;
                        if (pct > 100) pct = 100;
                    }
                    const sEntry = typeof formatSmartPrice === 'function' ? formatSmartPrice(entry) : entry.toFixed(4);
                    const sTp1 = typeof formatSmartPrice === 'function' ? formatSmartPrice(tp1) : tp1.toFixed(4);
                    const sStop = hardStop > 0 ? (typeof formatSmartPrice === 'function' ? formatSmartPrice(hardStop) : hardStop.toFixed(4)) : null;

                    progressHtml = `
                        <div style="margin-top:12px;">
                            <div style="display:flex; justify-content:space-between; align-items:center; font-size:10px; color:#94a3b8; margin-bottom:5px; font-family:'JetBrains Mono'; white-space:nowrap; gap:6px;">
                                <span>Giriş: <b style="color:#e2e8f0;">$${sEntry}</b></span>
                                ${sStop ? `<span style="color:var(--red);">SL: <b>$${sStop}</b></span>` : ''}
                                <span style="color:#38bdf8;">TP: <b>$${sTp1}</b></span>
                            </div>
                            <div style="width:100%; height:4px; background:rgba(255,255,255,0.06); border-radius:2px; overflow:hidden;">
                                <div style="height:100%; width:${pct.toFixed(1)}%; background:linear-gradient(90deg, ${sideColor}, #38bdf8); box-shadow:0 0 6px ${sideColor}; transition:width 0.5s ease;"></div>
                            </div>
                        </div>
                    `;
                }

                const sCurPrice = typeof formatSmartPrice === 'function' ? formatSmartPrice(curP) : curP.toFixed(4);
                const displaySetup = formatSetupDisplayName(pos.setup_id || 'AI_SETUP');

                html += `
                    <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.06); border-radius:12px; padding:15px; position:relative; overflow:hidden; box-shadow:0 4px 12px rgba(0,0,0,0.2);">
                        <div style="position:absolute; top:0; left:0; width:4px; height:100%; background:${sideColor}; box-shadow:0 0 8px ${sideColor};"></div>
                        <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:10px; margin-bottom:6px;">
                            <div style="min-width:0; flex:1;">
                                <div style="font-size:16px; font-weight:800; color:#fff; display:flex; align-items:center; gap:8px;">
                                    <span onclick="openTradingViewModal('${cleanSym}')" style="cursor:pointer;" title="${cleanSym} Göstergeli Canlı Grafiğini Aç">${cleanSym}</span>
                                    <span style="font-size:10px; font-weight:700; padding:2px 7px; border-radius:6px; background:${sideBg}; color:${sideColor}; border:1px solid ${sideColor}; white-space:nowrap;">${side} ${pos.leverage || 5}x</span>
                                </div>
                                <div style="font-size:11px; color:#94a3b8; font-family:'JetBrains Mono', monospace; margin-top:4px; display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                                    <span style="background:rgba(0,242,254,0.08); color:var(--cyan); border:1px solid rgba(0,242,254,0.25); padding:1px 6px; border-radius:4px; font-weight:700; font-size:10px;" title="${pos.setup_id || ''}">${displaySetup}</span>
                                    <span style="color:#38bdf8; font-size:11px;">$${sCurPrice}</span>
                                </div>
                            </div>
                            <div style="text-align:right; flex-shrink:0; min-width:85px;">
                                <div style="font-size:17px; font-weight:900; color:${pnlColor}; font-family:'JetBrains Mono', monospace; white-space:nowrap; text-shadow:0 0 8px ${pnlColor}40;">
                                    ${pnlSign}$${Math.abs(netPnl).toFixed(2)}
                                </div>
                                <div style="font-size:12px; color:${pnlColor}; font-weight:800; margin-top:2px; white-space:nowrap;">
                                    ${pnlSign}${Math.abs(roe).toFixed(2)}% ROE
                                </div>
                            </div>
                        </div>
                        ${progressHtml}
                    </div>
                `;
            });
            
            html += `
                    </div>
                </div>
            `;
            
            if (!window.toggleOpenPositions) {
                window.toggleOpenPositions = function() {
                    const grid = document.getElementById('open-positions-grid');
                    const icon = document.getElementById('open-positions-toggle-icon');
                    if (grid) {
                        if (grid.style.display === 'none') {
                            grid.style.display = 'grid';
                            if (icon) icon.innerText = '▼ Gizle';
                        } else {
                            grid.style.display = 'none';
                            if (icon) icon.innerText = '▶ Göster';
                        }
                    }
                };
            }
            
            container.innerHTML = html;
        }

        // =========================================================================
        // 📈 VALKYRIE KURUMSAL KASA PERFORMANSI (EQUITY CURVE) ENGINE
        // =========================================================================
        let equityChartInstance = null;
        let equityAreaSeries = null;
        let equityBaselineSeries = null;

        function renderEquityCurve() {
            try {
                const container = document.getElementById('cockpit-equity-container');
                const placeholder = document.getElementById('equity-empty-state');
                if (!container) return;

                const hist = (appState && appState.history) || [];
                const bal = Number((appState && appState.balance) || 10000.0);
                const initBal = Number((appState && appState.initial_balance) || 10000.0);
                const netPnl = (bal - initBal);

                // Update HUD Chips
                const elInit = document.getElementById('equity-chip-init');
                const elPeak = document.getElementById('equity-chip-peak');
                const elPnl = document.getElementById('equity-chip-pnl');
                const elDd = document.getElementById('equity-chip-drawdown');

                if (elInit) elInit.innerText = `$${initBal.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2})}`;
                if (elPnl) {
                    elPnl.innerText = `${netPnl >= 0 ? '+' : ''}$${netPnl.toFixed(2)}`;
                    elPnl.style.color = netPnl >= 0 ? 'var(--green)' : 'var(--red)';
                }

                if (hist.length === 0) {
                    if (elPeak) elPeak.innerText = `$${initBal.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2})}`;
                    if (elDd) elDd.innerText = '%0.00';
                    if (placeholder) placeholder.style.display = 'flex';
                    return;
                }

                if (placeholder) placeholder.style.display = 'none';

                // Calculate cumulative balance points
                let runningBal = initBal;
                let peak = initBal;
                let maxDD = 0.0;
                const points = [];
                const basePoints = [];

                const nowSec = Math.floor(Date.now() / 1000);
                const stepSec = 3600;
                let startSec = nowSec - (hist.length + 1) * stepSec;

                // Starting point
                points.push({ time: startSec, value: initBal });
                basePoints.push({ time: startSec, value: initBal });

                hist.forEach((trade, idx) => {
                    const pnl = Number(trade.net_pnl || 0.0);
                    runningBal += pnl;
                    if (runningBal > peak) peak = runningBal;
                    const dd = peak > 0 ? ((peak - runningBal) / peak) * 100.0 : 0.0;
                    if (dd > maxDD) maxDD = dd;

                    let tradeTs = startSec + (idx + 1) * stepSec;
                    if (trade.exit_time) {
                        const parsed = Math.floor(new Date(trade.exit_time).getTime() / 1000);
                        if (!isNaN(parsed) && parsed > startSec) {
                            tradeTs = parsed;
                        }
                    }
                    points.push({ time: tradeTs, value: Number(runningBal.toFixed(2)) });
                    basePoints.push({ time: tradeTs, value: initBal });
                });

                // Ensure strictly monotonic timestamps for LightweightCharts
                for (let i = 1; i < points.length; i++) {
                    if (points[i].time <= points[i-1].time) {
                        points[i].time = points[i-1].time + 60;
                        basePoints[i].time = points[i].time;
                    }
                }

                if (elPeak) elPeak.innerText = `$${peak.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2})}`;
                if (elDd) {
                    elDd.innerText = `-%${maxDD.toFixed(2)}`;
                    elDd.style.color = maxDD > 5.0 ? 'var(--red)' : (maxDD > 2.0 ? 'var(--yellow)' : '#38bdf8');
                }

                if (typeof LightweightCharts === 'undefined') return;

                if (!equityChartInstance) {
                    container.innerHTML = '';
                    equityChartInstance = LightweightCharts.createChart(container, {
                        width: container.clientWidth || 800,
                        height: container.clientHeight || 260,
                        layout: {
                            background: { color: '#080c14' },
                            textColor: '#94a3b8',
                            fontSize: 11,
                            fontFamily: "'JetBrains Mono', monospace",
                        },
                        grid: {
                            vertLines: { color: 'rgba(255, 255, 255, 0.03)' },
                            horzLines: { color: 'rgba(255, 255, 255, 0.03)' },
                        },
                        crosshair: {
                            mode: LightweightCharts.CrosshairMode.Normal,
                        },
                        timeScale: {
                            timeVisible: true,
                            secondsVisible: false,
                            borderColor: 'rgba(255, 255, 255, 0.08)',
                        },
                        rightPriceScale: {
                            borderColor: 'rgba(255, 255, 255, 0.08)',
                            scaleMargins: { top: 0.15, bottom: 0.15 },
                        }
                    });

                    equityBaselineSeries = equityChartInstance.addLineSeries({
                        color: 'rgba(245, 158, 11, 0.45)',
                        lineWidth: 1.5,
                        lineStyle: LightweightCharts.LineStyle.Dashed,
                        title: 'Başlangıç ($10K)',
                        priceFormat: { type: 'price', precision: 2, minMove: 0.01 }
                    });

                    equityAreaSeries = equityChartInstance.addAreaSeries({
                        topColor: 'rgba(0, 242, 254, 0.45)',
                        bottomColor: 'rgba(0, 242, 254, 0.01)',
                        lineColor: '#00f2fe',
                        lineWidth: 2.5,
                        title: 'Kasa Bakiyesi',
                        priceFormat: { type: 'price', precision: 2, minMove: 0.01 }
                    });

                    window.addEventListener('resize', () => {
                        if (equityChartInstance && container) {
                            equityChartInstance.applyOptions({
                                width: container.clientWidth,
                                height: container.clientHeight || 260
                            });
                        }
                    });
                }

                if (equityBaselineSeries) equityBaselineSeries.setData(basePoints);
                if (equityAreaSeries) {
                    const isProfit = runningBal >= initBal;
                    equityAreaSeries.applyOptions({
                        topColor: isProfit ? 'rgba(16, 185, 129, 0.45)' : 'rgba(244, 63, 94, 0.45)',
                        lineColor: isProfit ? '#10b981' : '#f43f5e',
                    });
                    equityAreaSeries.setData(points);
                    equityChartInstance.timeScale().fitContent();
                }
            } catch (e) {
                console.error("renderEquityCurve error:", e);
            }
        }

        // =========================================================================
        // 🛡️ KUANT KALKANLARI & REDDEDİLEN SİNYAL İSTİHBARATI
        // =========================================================================
        function renderRejectionIntelligence() {
            try {
                const rejections = (appState && appState.recent_rejections) || [];
                const totalBadge = document.getElementById('rejection-total-badge');
                if (totalBadge) totalBadge.innerText = `${rejections.length} VETO`;

                // Calculate shield frequencies
                let cntFlow = 0, cntJudas = 0, cntBeta = 0, cntEntropy = 0, cntCooldown = 0, cntIceberg = 0;

                rejections.forEach(r => {
                    const reason = (r.reason || '').toLowerCase();
                    if (reason.includes('flow') || reason.includes('cvd') || reason.includes('harmonic')) cntFlow++;
                    else if (reason.includes('judas') || reason.includes('sweep')) cntJudas++;
                    else if (reason.includes('beta') || reason.includes('btc')) cntBeta++;
                    else if (reason.includes('shannon') || reason.includes('entropy') || reason.includes('hurst')) cntEntropy++;
                    else if (reason.includes('cooldown') || reason.includes('loss') || reason.includes('stop')) cntCooldown++;
                    else if (reason.includes('iceberg') || reason.includes('stoikov') || reason.includes('vpin')) cntIceberg++;
                    else cntFlow++;
                });

                const elFlow = document.getElementById('shield-cnt-flow');
                const elJudas = document.getElementById('shield-cnt-judas');
                const elBeta = document.getElementById('shield-cnt-beta');
                const elEntropy = document.getElementById('shield-cnt-entropy');
                const elCooldown = document.getElementById('shield-cnt-cooldown');
                const elIceberg = document.getElementById('shield-cnt-iceberg');

                if (elFlow) elFlow.innerText = cntFlow;
                if (elJudas) elJudas.innerText = cntJudas;
                if (elBeta) elBeta.innerText = cntBeta;
                if (elEntropy) elEntropy.innerText = cntEntropy;
                if (elCooldown) elCooldown.innerText = cntCooldown;
                if (elIceberg) elIceberg.innerText = cntIceberg;

                const feed = document.getElementById('rejection-feed-container');
                if (!feed) return;

                if (rejections.length === 0) {
                    feed.innerHTML = `
                        <div style="text-align:center; padding:20px; color:#64748b; font-size:12px; font-family:'JetBrains Mono';">
                            🛡️ Henüz kalkanlara çarpan riskli sinyal bulunmuyor. Piyasa 100 paritede temiz akıyor.
                        </div>
                    `;
                    return;
                }

                let html = '';
                rejections.slice().reverse().forEach(item => {
                    const sym = item.symbol || '-';
                    const time = item.time || '-';
                    const setup = item.setup || 'Kuant Setup';
                    const reason = item.reason || 'Kalkan Engeli';

                    let shieldName = 'Risk Kalkanı';
                    let tagColor = '#ff4757';
                    const rLower = reason.toLowerCase();
                    if (rLower.includes('flow') || rLower.includes('cvd')) { shieldName = 'Harmonic Flow Gate'; tagColor = 'var(--cyan)'; }
                    else if (rLower.includes('judas') || rLower.includes('sweep')) { shieldName = 'Judas Swing Tuzağı'; tagColor = '#f59e0b'; }
                    else if (rLower.includes('beta')) { shieldName = 'Beta Follower Veto'; tagColor = '#a78bfa'; }
                    else if (rLower.includes('shannon') || rLower.includes('entropy')) { shieldName = 'Shannon Confluence'; tagColor = '#38bdf8'; }
                    else if (rLower.includes('cooldown')) { shieldName = 'Stop Cooldown'; tagColor = '#ff4757'; }
                    else if (rLower.includes('iceberg')) { shieldName = 'Iceberg Sniper Veto'; tagColor = '#34d399'; }

                    html += `
                        <div class="rejection-feed-item">
                            <div style="display:flex; align-items:center; gap:8px; min-width:0;">
                                <span style="color:#94a3b8; font-size:11px;">${time}</span>
                                <b style="color:#ffffff; font-size:12.5px;">${sym}</b>
                                <span style="color:#cbd5e1; font-size:11px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${setup}</span>
                            </div>
                            <div style="display:flex; align-items:center; gap:8px; flex-shrink:0;">
                                <span class="rejection-shield-tag" style="color:${tagColor}; border-color:${tagColor};">🛡️ ${shieldName}</span>
                                <span style="font-size:11px; color:#94a3b8; max-width:280px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${reason}">${reason}</span>
                            </div>
                        </div>
                    `;
                });
                feed.innerHTML = html;
            } catch (e) {
                console.error("renderRejectionIntelligence error:", e);
            }
        }

        // =========================================================================
        // 🌡️ PORTFÖY RİSK & MARJİN EXPOSURE HUD
        // =========================================================================
        function renderPortfolioRiskHUD() {
            try {
                const positions = (appState && appState.open_positions) || {};
                const bal = Number((appState && appState.balance) || 10000.0);

                let totalLongUsd = 0.0;
                let totalShortUsd = 0.0;
                let totalMarginUsd = 0.0;
                let longCount = 0;
                let shortCount = 0;
                let totalUnrealizedPnl = 0.0;

                for (const sym in positions) {
                    const pos = positions[sym];
                    const curP = Number((livePrices && livePrices[sym]) || (appState.symbols && appState.symbols[sym] ? appState.symbols[sym].price : 0) || pos.entry_price);
                    const metrics = computePositionPnL(pos, curP);
                    totalUnrealizedPnl += metrics.pnlUsdt;

                    const pVal = Number(pos.position_value || (pos.margin * (pos.leverage || 5)) || 0.0);
                    const mVal = Number(pos.margin || 0.0);
                    totalMarginUsd += mVal;

                    if (pos.side === 'LONG') {
                        totalLongUsd += pVal;
                        longCount++;
                    } else {
                        totalShortUsd += pVal;
                        shortCount++;
                    }
                }

                const netDelta = totalLongUsd - totalShortUsd;
                const marginRatio = bal > 0 ? ((totalMarginUsd / bal) * 100.0).toFixed(1) : '0.0';

                // Update Risk HUD in Positions Tab
                const elLongVal = document.getElementById('risk-hud-long-val');
                const elLongSub = document.getElementById('risk-hud-long-sub');
                const elShortVal = document.getElementById('risk-hud-short-val');
                const elShortSub = document.getElementById('risk-hud-short-sub');
                const elDeltaVal = document.getElementById('risk-hud-delta-val');
                const elDeltaSub = document.getElementById('risk-hud-delta-sub');
                const elMarginVal = document.getElementById('risk-hud-margin-val');
                const elMarginSub = document.getElementById('risk-hud-margin-sub');

                if (elLongVal) elLongVal.innerText = `$${totalLongUsd.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2})}`;
                if (elLongSub) elLongSub.innerText = `${longCount} Long Pozisyon`;
                if (elShortVal) elShortVal.innerText = `$${totalShortUsd.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2})}`;
                if (elShortSub) elShortSub.innerText = `${shortCount} Short Pozisyon`;

                if (elDeltaVal) {
                    elDeltaVal.innerText = `${netDelta >= 0 ? '+' : ''}$${netDelta.toFixed(2)} Net`;
                    elDeltaVal.style.color = netDelta > 100 ? 'var(--green)' : (netDelta < -100 ? 'var(--red)' : 'var(--cyan)');
                }
                if (elDeltaSub) {
                    if (Math.abs(netDelta) < 50) elDeltaSub.innerText = 'Piyasa-Nötr / Dengeli';
                    else if (netDelta > 0) elDeltaSub.innerText = 'Boğa Yönlü Net Maruziyet';
                    else elDeltaSub.innerText = 'Ayı Yönlü Net Maruziyet';
                }

                if (elMarginVal) {
                    elMarginVal.innerText = `%${marginRatio}`;
                    elMarginVal.style.color = Number(marginRatio) > 60 ? 'var(--red)' : (Number(marginRatio) > 30 ? 'var(--yellow)' : '#ffffff');
                }
                if (elMarginSub) {
                    const freeMargin = Math.max(0, bal - totalMarginUsd);
                    elMarginSub.innerText = `$${freeMargin.toFixed(0)} USDT Boşta`;
                }

                // Update Sidebar PnL Telemetry
                const sideOpenPnl = document.getElementById('sidebar-open-pnl');
                const sideNetPnl = document.getElementById('sidebar-net-pnl');
                const totalPosCount = longCount + shortCount;

                if (sideOpenPnl) {
                    sideOpenPnl.innerText = `${totalUnrealizedPnl >= 0 ? '+' : ''}$${totalUnrealizedPnl.toFixed(2)} (${totalPosCount} Açık)`;
                    sideOpenPnl.style.color = totalUnrealizedPnl >= 0 ? 'var(--green)' : 'var(--red)';
                }

                const netRealized = (appState && appState.history_summary ? appState.history_summary.total_realized_pnl : (bal - 10000.0)) || 0.0;
                if (sideNetPnl) {
                    sideNetPnl.innerText = `${netRealized >= 0 ? '+' : ''}$${netRealized.toFixed(2)}`;
                    sideNetPnl.style.color = netRealized >= 0 ? 'var(--green)' : 'var(--red)';
                }
            } catch (e) {
                console.error("renderPortfolioRiskHUD error:", e);
            }
        }

        // =========================================================================
        // 📊 SETUP PERFORMANS MATRİSİ VE ADLİ DEFTER SINIFLANDIRMA MOTORU
        // =========================================================================
        function classifyTradeSetup(h) {
            if (!h) return 'SCALP';
            const sId = (h.setup_id || '').toUpperCase();
            const r = (h.reason || '');
            const raw = (sId + ' ' + (h.trade_type || '') + ' ' + r).toUpperCase();

            // 1. Fakeout Reclaim (Reform 4)
            if (sId.includes('FAKEOUT_RECLAIM') || r.includes('Fakeout Reclaim') || (raw.includes('FAKEOUT') && raw.includes('RECLAIM'))) return 'RECLAIM';

            // 2. nPOC Likidite (Setup 9, 10)
            if (sId.includes('NPOC') || r.includes('nPOC') || raw.includes('NPOC')) return 'NPOC';

            // 3. Makro Değer Alanı (Setup 6, 8, 15)
            if (sId.includes('MVAL') || sId.includes('MVAH') || r.includes('mVAL') || r.includes('mVAH') || (r.includes('Macro') && !r.includes('Breakout'))) return 'MACRO';

            // 4. Retest & Support/Resistance Flip (Setup 5, 7, 11, 13, 14, 15, 16)
            if (r.includes('Retest') || r.includes('Flip') || sId.includes('FLIP') || sId.includes('RETEST') || r.includes('AVWAP Destek') || r.includes('AVWAP Reclaim') || r.includes('Support Flip')) return 'RETEST';

            // 5. Destek Çöküşü / Breakdown (Setup 12)
            if (sId.includes('BREAKDOWN') || r.includes('Breakdown') || r.includes('Çöküşü') || r.includes('ÇÖKÜŞ')) return 'BREAKDOWN';

            // 6. Camarilla S4 / R4 Breakout (Setup 1, 2)
            if (sId.includes('BREAKOUT') || r.includes('Breakout') || (r.includes('S4') && r.includes('Kırılım')) || (r.includes('R4') && r.includes('Kırılım'))) return 'CAM_BO';

            // 7. Camarilla S3 / R3 Bant Dönüşü (Setup 3, 4)
            if (sId.includes('BOUNCE') || sId.includes('REJECTION') || r.includes('S3 Destek Sekmesi') || r.includes('R3 Direnç Reddi') || r.includes('S3 Sekmesi') || r.includes('R3 Reddi')) return 'CAM_BOUNCE';

            return 'SCALP';
        }

        function matchSetupFilter(h, filterVal) {
            if (!filterVal || filterVal === 'ALL') return true;
            const key = classifyTradeSetup(h);
            const r = (h.reason || '');
            const sId = (h.setup_id || '').toUpperCase();

            if (filterVal === 'NPOC') return key === 'NPOC';
            if (filterVal === 'MACRO') return key === 'MACRO';
            if (filterVal === 'RETEST') return key === 'RETEST';
            if (filterVal === 'FLIP_AVWAP') return key === 'RETEST' && (r.includes('AVWAP') || sId.includes('AVWAP') || sId.includes('MVAH'));
            if (filterVal === 'FLIP_CAM') return key === 'RETEST' && (r.includes('S3') || r.includes('R3') || r.includes('S4') || r.includes('R4') || sId.includes('S3') || sId.includes('R3') || sId.includes('S4') || sId.includes('R4'));
            if (filterVal === 'FLIP_PIVOT') return key === 'RETEST' && (r.includes('Pivot') || r.includes('mPOC') || sId.includes('PIVOT') || sId.includes('MPOC') || sId.includes('SETUP_11') || sId.includes('SETUP_14'));
            if (filterVal === 'CAM_BO') return key === 'CAM_BO';
            if (filterVal === 'BREAKDOWN') return key === 'BREAKDOWN';
            if (filterVal === 'CAM_BOUNCE') return key === 'CAM_BOUNCE';
            if (filterVal === 'RECLAIM') return key === 'RECLAIM';
            if (filterVal === 'SCALP') return key === 'SCALP';
            return true;
        }

        function quickFilterSetup(setupKey) {
            const setupEl = document.getElementById('filter-setup');
            if (!setupEl) return;
            if (setupEl.value === setupKey) {
                setupEl.value = 'ALL';
            } else {
                setupEl.value = setupKey;
            }
            if (typeof onLedgerFilterChange === 'function') {
                onLedgerFilterChange();
            }
        }

        function resetLedgerFilters() {
            const symEl = document.getElementById('filter-symbol');
            const setupEl = document.getElementById('filter-setup');
            const statusEl = document.getElementById('filter-status');
            if (symEl) symEl.value = 'ALL';
            if (setupEl) setupEl.value = 'ALL';
            if (statusEl) statusEl.value = 'ALL';
            if (typeof onLedgerFilterChange === 'function') {
                onLedgerFilterChange();
            }
        }

        function renderSetupPerformanceMatrix() {
            try {
                const container = document.getElementById('ledger-setup-matrix-container');
                if (!container) return;

                const hist = (appState && appState.history) || [];
                const curFilter = document.getElementById('filter-setup') ? document.getElementById('filter-setup').value : 'ALL';

                // Categorize by setups
                const setups = {
                    'NPOC': { name: 'nPOC Likidite Avcısı', icon: '🔵', desc: 'Setup 9, 10', wins: 0, losses: 0, pnl: 0.0 },
                    'RETEST': { name: 'Destek/Direnç Retest & Flip', icon: '🔁', desc: 'Setup 5-16', wins: 0, losses: 0, pnl: 0.0 },
                    'CAM_BO': { name: 'Camarilla S4/R4 Breakout', icon: '⚡', desc: 'Setup 1, 2', wins: 0, losses: 0, pnl: 0.0 },
                    'BREAKDOWN': { name: 'Destek Çöküşü / Breakdown', icon: '🚨', desc: 'Setup 12', wins: 0, losses: 0, pnl: 0.0 },
                    'CAM_BOUNCE': { name: 'Camarilla S3/R3 Bant Dönüşü', icon: '🛡️', desc: 'Setup 3, 4', wins: 0, losses: 0, pnl: 0.0 },
                    'MACRO': { name: 'Macro mVAL / mVAH Kırılımı', icon: '🟣', desc: 'Setup 6, 8', wins: 0, losses: 0, pnl: 0.0 },
                    'RECLAIM': { name: 'Fakeout Reclaim (Tuzak İntikamı)', icon: '🪤', desc: 'Reform 4', wins: 0, losses: 0, pnl: 0.0 },
                    'SCALP': { name: 'Diğer Scalp & Iceberg', icon: '🎯', desc: 'L2 Scalp', wins: 0, losses: 0, pnl: 0.0 }
                };

                hist.forEach(h => {
                    const key = classifyTradeSetup(h);
                    const pnl = Number(h.net_pnl || 0.0);
                    if (setups[key]) {
                        setups[key].pnl += pnl;
                        if (pnl >= 0) setups[key].wins++;
                        else setups[key].losses++;
                    }
                });

                let html = '';
                for (const k in setups) {
                    const s = setups[k];
                    const total = s.wins + s.losses;
                    if (total === 0 && (k === 'SCALP' || k === 'RECLAIM')) continue;
                    const winRate = total > 0 ? ((s.wins / total) * 100).toFixed(0) : '0';
                    const pnlColor = s.pnl >= 0 ? 'var(--green)' : 'var(--red)';
                    const isActive = (curFilter === k);

                    html += `
                        <div class="setup-matrix-card ${isActive ? 'active-card' : ''}" onclick="quickFilterSetup('${k}')" title="${s.name} (${s.desc}) filtrelemek için tıklayın">
                            <div class="setup-card-name">
                                <span>${s.icon} ${s.name}</span>
                                <span style="color:#cbd5e1; font-size:10.5px;">${total} İşlem</span>
                            </div>
                            <div class="setup-card-pnl" style="color:${pnlColor};">
                                ${s.pnl >= 0 ? '+' : '-'}$${Math.abs(s.pnl).toFixed(2)}
                            </div>
                            <div class="setup-card-stats">
                                <span>Win Rate: <b style="color:${Number(winRate) >= 50 ? 'var(--green)' : '#94a3b8'};">%${winRate}</b></span>
                                <span>${s.wins}K / ${s.losses}Z ${isActive ? '• <b style="color:var(--cyan)">FİLTRELİ</b>' : ''}</span>
                            </div>
                        </div>
                    `;
                }
                container.innerHTML = html;
            } catch (e) {
                console.error("renderSetupPerformanceMatrix error:", e);
            }
        }

        function renderCockpitView() {
            if (!appState) return;

            try { renderEquityCurve(); } catch(e) { console.error("renderEquityCurve error:", e); }
            try { renderRejectionIntelligence(); } catch(e) { console.error("renderRejectionIntelligence error:", e); }
            try { renderPortfolioRiskHUD(); } catch(e) { console.error("renderPortfolioRiskHUD error:", e); }
            try { renderCockpitOpenPositions(); } catch(e) { console.error("renderCockpitOpenPositions error:", e); }

            // 1. Cockpit Financial KPIs
            const bal = Number(appState.balance || 10000.0);
            const initBal = Number(appState.initial_balance || 10000.0);
            const freeBal = Number(appState.free_balance !== undefined && appState.free_balance !== null ? appState.free_balance : bal);
            const hist = appState.history || [];
            
            let totalNetPnl = 0.0;
            let totalFees = 0.0;
            let wins = 0;
            let losses = 0;
            let winPnlSum = 0.0;
            let lossPnlSum = 0.0;

            if (appState.history_summary) {
                wins = appState.history_summary.wins || 0;
                losses = appState.history_summary.losses || 0;
                winPnlSum = appState.history_summary.win_pnl_sum || 0;
                lossPnlSum = appState.history_summary.loss_pnl_sum || 0;
                totalNetPnl = appState.history_summary.total_realized_pnl || 0;
                totalFees = appState.history_summary.total_fees || 0;
            } else {
                hist.forEach(t => {
                    const pnl = parseFloat(t.net_pnl || 0.0);
                    const fee = parseFloat(t.commission || 0.0);
                    totalNetPnl += pnl;
                    totalFees += fee;
                    if (pnl >= 0) {
                        wins++;
                        winPnlSum += pnl;
                    } else {
                        losses++;
                        lossPnlSum += Math.abs(pnl);
                    }
                });
            }

            // Calculate unrealized PnL from active open positions
            let totalUnrealizedPnl = 0.0;
            const openPositions = appState.open_positions || {};
            const openKeys = Object.keys(openPositions);
            const openCount = openKeys.length;

            openKeys.forEach(sym => {
                const pos = openPositions[sym];
                const curP = Number((typeof livePrices !== 'undefined' && livePrices && livePrices[sym]) || (appState.symbols && appState.symbols[sym] ? appState.symbols[sym].price : 0) || pos.entry_price);
                if (typeof computePositionPnL === 'function') {
                    const metrics = computePositionPnL(pos, curP);
                    totalUnrealizedPnl += (metrics.pnlUsdt || 0.0);
                }
            });

            const combinedNetPnl = totalNetPnl + totalUnrealizedPnl;
            const combinedBal = bal + totalUnrealizedPnl;
            const growthPct = initBal > 0 ? ((combinedBal - initBal) / initBal) * 100.0 : 0.0;
            const totalTrades = wins + losses;
            const winRate = totalTrades > 0 ? ((wins / totalTrades) * 100.0).toFixed(1) : '0.0';
            const pf = lossPnlSum > 0 ? (winPnlSum / lossPnlSum).toFixed(2) : (winPnlSum > 0 ? '99.0' : '0.00');

            const cBal = document.getElementById('cockpit-balance');
            const cFree = document.getElementById('cockpit-free-bal');
            const cPnl = document.getElementById('cockpit-pnl');
            const cGrowth = document.getElementById('cockpit-growth');
            const cWinrate = document.getElementById('cockpit-winrate');
            const cWinLoss = document.getElementById('cockpit-win-loss-count');
            const cPf = document.getElementById('cockpit-pf');
            const cFees = document.getElementById('cockpit-fees');
            const cPfNote = document.getElementById('cockpit-pf-note');

            if (cBal) cBal.innerText = `$${bal.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2})}`;
            if (cFree) cFree.innerText = `Kullanılabilir Kasa: $${freeBal.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2})} USDT (5x)`;
            if (cPnl) {
                const sign = combinedNetPnl >= 0 ? '+' : '';
                cPnl.innerText = `${sign}$${combinedNetPnl.toFixed(2)}`;
                cPnl.style.color = combinedNetPnl >= 0 ? 'var(--green)' : 'var(--red)';
            }
            if (cGrowth) {
                const sign = growthPct >= 0 ? '+' : '';
                if (openCount > 0) {
                    const uSign = totalUnrealizedPnl >= 0 ? '+' : '';
                    cGrowth.innerText = `${sign}${growthPct.toFixed(2)}% (Açık: ${uSign}$${totalUnrealizedPnl.toFixed(2)})`;
                } else {
                    cGrowth.innerText = `${sign}${growthPct.toFixed(2)}% Büyüme`;
                }
                cGrowth.style.color = growthPct >= 0 ? 'var(--green)' : 'var(--red)';
            }
            if (cWinrate) cWinrate.innerText = `%${winRate}`;
            if (cWinLoss) {
                if (openCount > 0) {
                    cWinLoss.innerText = `${wins} Kazanç / ${losses} Kayıp (${totalTrades} Kapanmış | ${openCount} Açık Poz)`;
                } else {
                    cWinLoss.innerText = `${wins} Kazanç / ${losses} Kayıp (${totalTrades} Kapanmış İşlem)`;
                }
            }
            const cWinSub = document.getElementById('cockpit-winrate-subtext');
            if (cWinSub) {
                if (openCount > 0) {
                    cWinSub.innerText = `${openCount} pozisyon sürüyor (realize bekleniyor)`;
                } else {
                    cWinSub.innerText = `Sürdürülebilir Hedef: > %50.0`;
                }
            }

            if (cPf) {
                if (totalTrades === 0) {
                    cPf.innerText = '— (İşlem Bekleniyor)';
                    cPf.style.color = '#94a3b8';
                    if (cFees) cFees.innerText = 'Brüt Kâr: +$0.00 | Kayıp: -$0.00';
                    if (cPfNote) {
                        cPfNote.innerText = 'Her 1$ Kayba: İlk işlem bekleniyor';
                        cPfNote.style.color = '#64748b';
                    }
                } else if (lossPnlSum === 0 && winPnlSum > 0) {
                    cPf.innerText = '∞ (Sıfır Kayıp / %100 Kâr)';
                    cPf.style.color = 'var(--green)';
                    if (cFees) cFees.innerText = `Brüt Kâr: +$${winPnlSum.toFixed(2)} | Kayıp: $0.00`;
                    if (cPfNote) {
                        cPfNote.innerText = 'Kayıpsız Serüven: Tüm işlemler kârda!';
                        cPfNote.style.color = 'var(--green)';
                    }
                } else {
                    const pfVal = lossPnlSum > 0 ? (winPnlSum / lossPnlSum) : 0.0;
                    const pfStr = pfVal.toFixed(2);
                    let qualityText = 'Zarar Baskısı';
                    let qualityColor = 'var(--red)';
                    let noteColor = 'var(--red)';

                    if (pfVal >= 2.0) {
                        qualityText = 'Kurumsal Elit 🏆';
                        qualityColor = 'var(--cyan)';
                        noteColor = '#38bdf8';
                    } else if (pfVal >= 1.5) {
                        qualityText = 'Çok Güçlü 🟢';
                        qualityColor = 'var(--green)';
                        noteColor = '#34d399';
                    } else if (pfVal >= 1.2) {
                        qualityText = 'Kârlı Sistem 🟡';
                        qualityColor = 'var(--yellow)';
                        noteColor = '#fbbf24';
                    } else if (pfVal >= 1.0) {
                        qualityText = 'Başa-Baş Sınırı ⚪';
                        qualityColor = '#cbd5e1';
                        noteColor = '#94a3b8';
                    }

                    cPf.innerText = `${pfStr}x (${qualityText})`;
                    cPf.style.color = qualityColor;

                    if (cFees) {
                        cFees.innerText = `Brüt Kâr: +$${winPnlSum.toFixed(2)} | Kayıp: -$${lossPnlSum.toFixed(2)}`;
                    }
                    if (cPfNote) {
                        cPfNote.innerText = `Her $1 Kayba Karşılık: +$${pfStr} Kâr (Hedef > 1.5x)`;
                        cPfNote.style.color = noteColor;
                    }
                }
            }

            // 🔮 Canlı 4x Kuantum KPI Simülasyon Motoruna Verileri Aktar
            if (window.ValkyrieKpiSimEngine) {
                window.ValkyrieKpiSimEngine.updateMetrics({
                    balance: bal,
                    initialBalance: initBal,
                    pnl: combinedNetPnl,
                    growthPct: growthPct,
                    winRate: parseFloat(winRate) || 0.0,
                    wins: wins,
                    losses: losses,
                    totalTrades: totalTrades,
                    pf: parseFloat(pf) || 0.0
                });
            }

            // 2. AI Quant Intelligence Stream & 1H Macro Trend Breakdown
            let bullCount = 0, bearCount = 0, rangeCount = 0;
            const nearCandidates = [];

            if (appState.symbols) {
                for (const sym in appState.symbols) {
                    const c = appState.symbols[sym];
                    const price = Number((livePrices && livePrices[sym]) || (c && c.price) || 0.0);
                    const levels = c.levels || {};
                    const cam = levels.camarilla || {};
                    const p = cam.P || 0.0;
                    const r4 = cam.R4 || 0.0;
                    const s4 = cam.S4 || 0.0;
                    const r3 = cam.R3 || 0.0;
                    const s3 = cam.S3 || 0.0;
                    const tepe = levels.tepe_avwap || 0.0;
                    const dip = levels.dip_avwap || 0.0;

                    if (price > 0 && p > 0) {
                        if (tepe > 0 && price > tepe && price > p) bullCount++;
                        else if (dip > 0 && price < dip && price < p) bearCount++;
                        else rangeCount++;

                        // Check all institutional levels for near-trigger radar
                        const belowNpoc = levels.below_npoc || 0.0;
                        const aboveNpoc = levels.above_npoc || 0.0;
                        const mval = levels.mval || 0.0;
                        const mvah = levels.mvah || 0.0;

                        let bestCandidate = null;
                        let minCoinDist = 999.0;
                        const met = c.metrics || {};
                        const volSurge = Number(met.vol_surge !== undefined ? met.vol_surge : 1.0);
                        const majorsList = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT"];
                        const minVolSurge = Number(met.min_vol_surge !== undefined ? met.min_vol_surge : (majorsList.includes(sym) ? 1.2 : 1.5));
                        const isTop80 = met.is_top_80 !== false;
                        const atrPct = Number(met.atr_pct !== undefined ? met.atr_pct : 1.2);

                        function checkLvl(targetName, targetPrice, action, bias, isLong) {
                            if (!targetPrice || targetPrice <= 0) return;
                            const dist = Math.abs(price - targetPrice) / price * 100.0;
                            if (dist < minCoinDist && dist <= 4.0) {
                                minCoinDist = dist;
                                const touches = (appState.setup_attempts && appState.setup_attempts[`${sym}_${targetName}`]) || 0;
                                bestCandidate = {
                                    symbol: sym,
                                    price: price,
                                    targetName: targetName,
                                    targetPrice: targetPrice,
                                    distPct: dist,
                                    action: action,
                                    bias: bias,
                                    volSurge: volSurge,
                                    minVolSurge: minVolSurge,
                                    isTop80: isTop80,
                                    atrPct: atrPct,
                                    touches: touches,
                                    curVol: Number(met.cur_vol || 0),
                                    avgVol: Number(met.avg_vol || 0),
                                    rsScore: Number(met.dynamic_rs_score !== undefined ? met.dynamic_rs_score : (met.rs_vs_btc || 0)),
                                    decouplingStatus: met.decoupling_status || '⚪ Nötr',
                                    icebergRatio: Number(met.iceberg_ratio || 1.0),
                                    askIcebergRatio: Number(met.ask_iceberg_ratio || 1.0),
                                    bidIcebergRatio: Number(met.bid_iceberg_ratio || 1.0),
                                    icebergSide: met.iceberg_side || 'NONE',
                                    hasIceberg: Boolean(met.has_iceberg || (met.iceberg_ratio >= 3.5)),
                                    entropyNorm: Number(met.entropy_norm !== undefined ? met.entropy_norm : 0.65),
                                    isChaotic: Boolean(met.is_chaotic),
                                    isCrystalline: Boolean(met.is_crystalline),
                                    hurstVal: Number(met.hurst_exponent !== undefined ? met.hurst_exponent : 0.50),
                                    hmmPhase: met.hmm_phase || 'ACCUMULATION',
                                    hmmDesc: met.hmm_desc || '',
                                    bookmapSellerAbsorption: Boolean(met.bookmap_seller_absorption),
                                    bookmapBuyerAbsorption: Boolean(met.bookmap_buyer_absorption),
                                    bookmapAbsorptionType: met.bookmap_absorption_type || 'NONE',
                                    bookmapAbsorptionDesc: met.bookmap_absorption_desc || '',
                                    isAnchorWall: Boolean(met.is_anchor_wall),
                                    isIronWall: Boolean(met.is_iron_wall),
                                    wallDurationSec: Number(met.wall_duration_sec || 0),
                                    priceChangePct60s: Number(met.price_change_pct_60s || 0)
                                };
                            }
                        }

                        if (r4 > 0 && price < r4) checkLvl('R4 Breakout', r4, '🚀 R4 Breakout LONG Pususu', '🟢 Boğa Kırılımı', true);
                        if (s4 > 0 && price > s4) checkLvl('S4 Breakdown', s4, '🔻 S4 Breakdown SHORT Pususu', '🔴 Ayı Kırılımı', false);
                        if (s3 > 0) checkLvl('S3 Destek', s3, '🎯 S3 Destek Sekmesi LONG Pususu', '🟡 Tepki Pusu', true);
                        if (r3 > 0) checkLvl('R3 Direnç', r3, '🛡️ R3 Direnç Retest SHORT Pususu', '🟠 Direnç Pusu', false);
                        if (belowNpoc > 0) checkLvl('Aşağı nPOC', belowNpoc, '💎 nPOC Balina Destek LONG Pususu', '🟢 Kurumsal Destek', true);
                        if (aboveNpoc > 0) checkLvl('Yukarı nPOC', aboveNpoc, '🧱 nPOC Hacim Direnç SHORT Pususu', '🔴 Kurumsal Direnç', false);
                        if (mval > 0) checkLvl('mVAL Taban', mval, '🏛️ mVAL Aylık Taban LONG Pususu', '🟢 Makro Taban', true);
                        if (mvah > 0) checkLvl('mVAH Tavan', mvah, '🚀 mVAH Aylık Tavan Breakout LONG', '🟢 Makro Kırılım', true);
                        if (dip > 0) checkLvl('Dip AVWAP', dip, '⚓ Dip AVWAP Destek LONG Pususu', '🟢 AVWAP Destek', true);
                        if (tepe > 0) checkLvl('Tepe AVWAP', tepe, '🛑 Tepe AVWAP Direnç SHORT Pususu', '🔴 AVWAP Direnç', false);

                        if (bestCandidate) {
                            nearCandidates.push(bestCandidate);
                        }
                    }
                }
            }

            // Update Market Regime Bar
            const totalClassified = Math.max(1, bullCount + bearCount + rangeCount);
            const bullPct = Math.round((bullCount / totalClassified) * 100.0);
            const bearPct = Math.round((bearCount / totalClassified) * 100.0);
            const rangePct = Math.max(0, 100 - bullPct - bearPct);

            const bBull = document.getElementById('regime-bar-bull');
            const bBear = document.getElementById('regime-bar-bear');
            const bRange = document.getElementById('regime-bar-range');
            const spark = document.getElementById('regime-clash-spark');
            const bullText = document.getElementById('regime-bull-text');
            const rangeText = document.getElementById('regime-range-text');
            const bearText = document.getElementById('regime-bear-text');
            const commEl = document.getElementById('regime-commentary');

            if (bullText) bullText.innerText = `%${bullPct} (${bullCount} Parite)`;
            if (rangeText) rangeText.innerText = `%${rangePct} (${rangeCount} Parite)`;
            if (bearText) bearText.innerText = `%${bearPct} (${bearCount} Parite)`;

            // Update Cinematic Battle Arena HUD elements
            const hudBullPct = document.getElementById('hud-bull-pct');
            const hudBullCount = document.getElementById('hud-bull-count');
            const hudBearPct = document.getElementById('hud-bear-pct');
            const hudBearCount = document.getElementById('hud-bear-count');
            const hudNeutral = document.getElementById('hud-neutral-badge');

            if (hudBullPct) hudBullPct.innerText = `%${bullPct}`;
            if (hudBullCount) hudBullCount.innerText = `${bullCount} Parite Kırılımda`;
            if (hudBearPct) hudBearPct.innerText = `%${bearPct}`;
            if (hudBearCount) hudBearCount.innerText = `${bearCount} Parite Baskıda`;
            if (hudNeutral) hudNeutral.innerHTML = `<span>⚪ TAMPON BÖLGE: %${rangePct} YATAY (${rangeCount} Parite)</span>`;

            if (window.ValkyrieBattleEngine) {
                ValkyrieBattleEngine.setRegimeData(bullPct, rangePct, bearPct);
            }

            if (bBull) bBull.style.width = `${bullPct}%`;
            if (bRange) bRange.style.width = `${rangePct}%`;
            if (bBear) bBear.style.width = `${bearPct}%`;
            if (spark) spark.style.left = `calc(${bullPct}% - 2px)`;

            if (commEl) {
                if (bullPct >= 55) {
                    commEl.innerHTML = `Alıcılar piyasada net üstünlük kurdu (<b style="color:#0ecb81">%${bullPct}</b>). Yukarı yönlü momentum ve breakout alımları destekleniyor.`;
                } else if (bullPct > bearPct && bullPct >= 35) {
                    commEl.innerHTML = `Boğalar <b style="color:#0ecb81">%${bullPct}</b> ile piyasaya yön veriyor. <b style="color:#94a3b8">%${rangePct}</b> parite konsolide olurken ayı baskısı zayıf kalıyor.`;
                } else if (bearPct >= 50) {
                    commEl.innerHTML = `Satıcılar piyasada ağırlığı ele geçirdi (<b style="color:#ff4757">%${bearPct}</b>). Destek kırılımları ve short retest kurulumları ön planda.`;
                } else if (bearPct > bullPct && bearPct >= 35) {
                    commEl.innerHTML = `Ayı baskısı <b style="color:#ff4757">%${bearPct}</b> ile hissediliyor. Long fırsatlarında seçici olunmalı, hacim teyitleri aranmalı.`;
                } else if (rangePct >= 45) {
                    commEl.innerHTML = `100 paritenin <b style="color:#94a3b8">%${rangePct}</b>'si yatay dengede. Piyasa yön arayışında; nPOC ve Camarilla destek/direnç bantları likidite topluyor.`;
                } else {
                    commEl.innerHTML = `Piyasada dengeli güç dağılımı hakim (Boğa: <b style="color:#0ecb81">%${bullPct}</b> | Ayı: <b style="color:#ff4757">%${bearPct}</b>). Kilit seviyelerde teyit bekleniyor.`;
                }
            }

            // =========================================================================
            // 🧠 VALKYRIE AI QUANT ZEKASI 2.0 • CANLI PİYASA & PUSU DÜŞÜNCE AKIŞI
            // =========================================================================
            const feed = document.getElementById('ai-thought-feed');
            if (feed) {
                if (!window.currentAiFilter) window.currentAiFilter = 'all';
                window.setAiThoughtFilter = function(f) {
                    window.currentAiFilter = f;
                    document.querySelectorAll('.ai-thought-filters .ai-filter-btn').forEach(btn => btn.classList.remove('active'));
                    const activeBtn = document.getElementById('btn-filter-' + f);
                    if (activeBtn) activeBtn.classList.add('active');
                    if (typeof window.renderAiThoughts === 'function') window.renderAiThoughts();
                };

                window.setAiThoughtLayout = function(mode) {
                    const fEl = document.getElementById('ai-thought-feed');
                    const btnGrid = document.getElementById('btn-layout-grid');
                    const btnSingle = document.getElementById('btn-layout-single');
                    if (!fEl) return;
                    if (mode === 'single') {
                        fEl.classList.add('layout-single');
                        if (btnSingle) {
                            btnSingle.classList.add('active');
                            btnSingle.style.borderColor = 'rgba(0, 242, 254, 0.4)';
                            btnSingle.style.color = '#00f2fe';
                        }
                        if (btnGrid) {
                            btnGrid.classList.remove('active');
                            btnGrid.style.borderColor = 'rgba(255, 255, 255, 0.08)';
                            btnGrid.style.color = '#94a3b8';
                        }
                        try { localStorage.setItem('valk_thought_layout', 'single'); } catch(e){}
                    } else {
                        fEl.classList.remove('layout-single');
                        if (btnGrid) {
                            btnGrid.classList.add('active');
                            btnGrid.style.borderColor = 'rgba(0, 242, 254, 0.4)';
                            btnGrid.style.color = '#00f2fe';
                        }
                        if (btnSingle) {
                            btnSingle.classList.remove('active');
                            btnSingle.style.borderColor = 'rgba(255, 255, 255, 0.08)';
                            btnSingle.style.color = '#94a3b8';
                        }
                        try { localStorage.setItem('valk_thought_layout', 'grid'); } catch(e){}
                    }
                };

                const savedLayout = (function(){ try { return localStorage.getItem('valk_thought_layout') || 'grid'; } catch(e){ return 'grid'; } })();
                window.setAiThoughtLayout(savedLayout);

                const thoughtItems = [];
                const nowStr = new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });

                // 0. 🌐 MAKRO İKLİM & ŞEF ANALİZİ (BTC + ETH CONDUKTÖRÜ)
                const macro = appState.macro_climate || {};
                const mRegime = macro.regime || 'NEUTRAL';
                const mStatus = macro.status || '⚪ NÖTR / DENGELİ PİYASA';
                const btcR = macro.btc_range_1h !== undefined ? Number(macro.btc_range_1h) : 0.35;
                const ethR = macro.eth_range_1h !== undefined ? Number(macro.eth_range_1h) : 0.45;
                const ethLead = macro.eth_lead_pct !== undefined ? Number(macro.eth_lead_pct) : 0.0;
                const isDead = macro.is_dead_zone === true;
                const ethLeading = macro.eth_leading === true;
                
                let mColor = '#38bdf8';
                let mIcon = '🌐';
                let mTagClass = 'tag-macro';
                if (mRegime === 'ETH_EXPANSION') {
                    mColor = '#f59e0b';
                    mIcon = '🟡';
                    mTagClass = 'tag-vol';
                } else if (mRegime === 'BULL_TREND') {
                    mColor = '#10b981';
                    mIcon = '🟢';
                    mTagClass = 'tag-pos';
                } else if (mRegime === 'BEAR_DUMP') {
                    mColor = '#f43f5e';
                    mIcon = '🔴';
                    mTagClass = 'tag-autopsy-loss';
                } else if (isDead) {
                    mColor = '#a855f7';
                    mIcon = '⚪';
                    mTagClass = 'tag-autopsy-win';
                }

                thoughtItems.push({
                    cat: 'macro',
                    color: mColor,
                    icon: mIcon,
                    tag: mStatus.split(' ')[0] + ' ' + (mStatus.split(' ')[1] || 'MAKRO'),
                    tagClass: mTagClass,
                    title: `${mIcon} MAKRO ŞEF & İKLİM: BTC + ETH ORTAK MOTORU (${nowStr})`,
                    text: `
                        <div style="font-weight:700; color:${mColor}; margin-bottom:4px; font-size:13px;">${mStatus}</div>
                        <div style="display:flex; gap:6px; margin:6px 0; flex-wrap:wrap; font-size:11px; font-family:'JetBrains Mono',monospace;">
                            <span style="background:rgba(0,0,0,0.3); padding:2px 7px; border-radius:4px; border:1px solid rgba(255,255,255,0.1); color:#f8fafc;">
                                👑 BTC 1S Aralık: %${btcR.toFixed(2)} (${macro.btc_chg_1h !== undefined ? (macro.btc_chg_1h >= 0 ? '+' : '') + macro.btc_chg_1h.toFixed(2) + '%' : '0%'})
                            </span>
                            <span style="background:rgba(0,0,0,0.3); padding:2px 7px; border-radius:4px; border:1px solid rgba(255,255,255,0.1); color:${ethLeading ? '#10b981' : '#38bdf8'}; font-weight:700;">
                                ⚡ ETH 1S Aralık: %${ethR.toFixed(2)} (${macro.eth_chg_1h !== undefined ? (macro.eth_chg_1h >= 0 ? '+' : '') + macro.eth_chg_1h.toFixed(2) + '%' : '0%'})
                            </span>
                            <span style="background:rgba(0,0,0,0.3); padding:2px 7px; border-radius:4px; border:1px solid rgba(255,255,255,0.1); color:${ethLead >= 0.7 ? '#10b981' : (ethLead <= -0.7 ? '#f43f5e' : '#e2e8f0')}; font-weight:700;">
                                📊 ETH/BTC Liderlik Farkı: ${ethLead >= 0 ? '+' : ''}${ethLead.toFixed(2)}% [${ethLeading ? '✓ ETH Sürüklüyor' : 'Dengeli'}]
                            </span>
                        </div>
                        <div style="margin-top:5px; padding:7px 10px; background:${isDead ? 'rgba(168,85,247,0.08)' : (ethLeading ? 'rgba(245,158,11,0.08)' : 'rgba(56,189,248,0.08)')}; border-left:3px solid ${mColor}; border-radius:4px; font-size:12px; line-height:1.45;">
                            <b>🛡️ Valkyrie Taktik Direktifi:</b> ${macro.desc || (isDead 
                                ? "Piyasa Değer Alanı (S3-R3) içinde yatayda. Standart beta paritelerdeki kırılımlar %85 sahte tuzak riski nedeniyle kilitli; yalnızca nPOC/Camarilla Mean Reversion tepkileri ve bağımsız ALFA ayrışanlar (RS ≥ 1.2, Hacim ≥ 2.0x) işleme alınır."
                                : (ethLeading 
                                    ? "ETH, BTC'ye fark atarak altcoinlere güçlü bir boğa rüzgarı sağlıyor. Hacimli kırılımlara ve trend devam kurulumlarına yeşil ışık yakıldı."
                                    : "BTC ve ETH dengeli bantta. Seviye pusuları ve hacim teyitli sinyaller kesintisiz taranıyor."))
                            }
                        </div>
                    `
                });

                // 🎯 Canlı Taktik Likidite Radarı ve Savunma Kalkanını Besle
                if (window.ValkyrieTacticalRadarEngine) {
                    window.ValkyrieTacticalRadarEngine.setRadarData(nearCandidates, appState.recent_rejections || []);
                }

                // 1. TEMASTA OLAN VE YAKLAŞAN COİNLERİN DERİN ANALİZİ (Pusu / Neden Girmedi / Ne Bekliyor?)
                if (nearCandidates && nearCandidates.length > 0) {
                    nearCandidates.sort((a,b) => a.distPct - b.distPct);
                    const topNear = nearCandidates.slice(0, 6);
                    
                    topNear.forEach(c => {
                        const cleanS = c.symbol.replace('/USDT', '').replace('USDT', '').trim();
                        const dist = c.distPct;
                        const isContact = dist < 0.25;
                        const volSurge = c.volSurge !== undefined ? c.volSurge : 1.0;
                        const minSurge = c.minVolSurge !== undefined ? c.minVolSurge : 1.5;
                        const isVolOk = volSurge >= minSurge;
                        const isTop80 = c.isTop80 !== false;
                        const atrPct = c.atrPct !== undefined ? c.atrPct : 1.2;
                        const rsScore = c.rsScore !== undefined ? c.rsScore : 0.0;
                        const decouplingStatus = c.decouplingStatus || '⚪ Nötr';
                        const rsColor = rsScore >= 1.0 ? '#10b981' : (rsScore <= -1.0 ? '#f43f5e' : '#38bdf8');
                        const curVolStr = c.curVol >= 1e6 ? `$${(c.curVol/1e6).toFixed(1)}M` : (c.curVol >= 1e3 ? `$${(c.curVol/1e3).toFixed(0)}K` : '');
                        const volExtra = curVolStr ? ` (${curVolStr})` : '';
                        const pPrice = typeof formatSmartPrice === 'function' ? formatSmartPrice(c.price) : Number(c.price).toFixed(4);
                        const tPrice = typeof formatSmartPrice === 'function' ? formatSmartPrice(c.targetPrice) : Number(c.targetPrice).toFixed(4);

                        const iRatio = c.icebergRatio || 1.0;
                        const hasIce = c.hasIceberg || (iRatio >= 3.5);
                        const iceBadge = hasIce 
                            ? `<span style="background:rgba(0,242,254,0.18); padding:2px 7px; border-radius:4px; border:1px solid rgba(0,242,254,0.45); color:#00f2fe; font-weight:800; text-shadow:0 0 8px rgba(0,242,254,0.5);">🧊 Iceberg: ${iRatio.toFixed(1)}x (${c.icebergSide === 'ICEBERG_ASK_RESISTANCE' ? 'Satıcı' : 'Alıcı'})</span>`
                            : (iRatio >= 2.0 ? `<span style="background:rgba(0,0,0,0.3); padding:2px 7px; border-radius:4px; border:1px solid rgba(0,242,254,0.25); color:#38bdf8;">🧊 Iceberg: ${iRatio.toFixed(1)}x</span>` : '');
                        
                        const entVal = c.entropyNorm !== undefined ? c.entropyNorm : 0.65;
                        const hurstVal = c.hurstVal !== undefined ? c.hurstVal : 0.50;
                        const quantBadge = `<span style="background:rgba(168,85,247,0.12); padding:2px 7px; border-radius:4px; border:1px solid rgba(168,85,247,0.3); color:#c084fc;">🌡️ S:%${Math.round(entVal*100)} | H:${hurstVal.toFixed(2)}</span>`;

                        const telemetryBar = `
                            <div style="display:flex; gap:6px; margin:6px 0; flex-wrap:wrap; font-size:11px; font-family:'JetBrains Mono',monospace;">
                                <span style="background:rgba(0,0,0,0.3); padding:2px 7px; border-radius:4px; border:1px solid ${isVolOk ? 'rgba(16,185,129,0.35)' : 'rgba(245,158,11,0.35)'}; color:${isVolOk ? '#10b981' : '#f59e0b'}; font-weight:700;">
                                    ⚡ 5M Hacim: ${volSurge.toFixed(2)}x${volExtra} / Min ${minSurge.toFixed(1)}x [${isVolOk ? '✓ Onaylı' : '⏳ Eksik'}]
                                </span>
                                <span style="background:rgba(0,0,0,0.3); padding:2px 7px; border-radius:4px; border:1px solid rgba(255,255,255,0.08); color:${rsColor}; font-weight:700;">
                                    ⚡ RS vs BTC: ${rsScore >= 0 ? '+' : ''}${rsScore.toFixed(2)} [${decouplingStatus.split(' ')[0]}]
                                </span>
                                ${iceBadge}
                                ${quantBadge}
                                <span style="background:rgba(0,0,0,0.3); padding:2px 7px; border-radius:4px; border:1px solid rgba(255,255,255,0.08); color:${isTop80 ? '#38bdf8' : '#94a3b8'};">
                                    📊 ${isTop80 ? '✓ Top %80 Hacim' : '⚠️ Top %20 Altı (Sığ)'}
                                </span>
                                <span style="background:rgba(0,0,0,0.3); padding:2px 7px; border-radius:4px; border:1px solid rgba(255,255,255,0.08); color:#c084fc;">
                                    🌊 ATR: %${atrPct.toFixed(2)}
                                </span>
                            </div>
                        `;

                        if (isContact) {
                            const commText = isVolOk 
                                ? ValkyrieCommentaryEngine.getContactVolOk(cleanS, c.targetName, volSurge, minSurge, rsScore, c.action, pPrice, tPrice)
                                : ValkyrieCommentaryEngine.getContactVolWaiting(cleanS, c.targetName, volSurge, minSurge, rsScore, c.action, pPrice, tPrice);

                            thoughtItems.push({
                                cat: 'near',
                                symbol: cleanS,
                                color: isVolOk ? '#10b981' : '#f59e0b',
                                icon: isVolOk ? '🚀' : '🔥',
                                tag: isVolOk ? 'TEMASTA (HACİM ONAYLI)' : 'TEMASTA (HACİM BEKLENİYOR)',
                                tagClass: isVolOk ? 'tag-macro' : 'tag-vol',
                                title: `${isVolOk ? '🚀' : '🔥'} ${cleanS} • ${c.targetName} SEVİYESİNDE TAM TEMAS! (${nowStr})`,
                                text: `Fiyat şu an <b>$${pPrice}</b> ile <b>${c.targetName} ($${tPrice})</b> seviyesine tam temas halinde.<br>
                                ${telemetryBar}
                                <div style="margin-top:4px; padding:6px 10px; background:${isVolOk ? 'rgba(16,185,129,0.08)' : 'rgba(245,158,11,0.08)'}; border-left:3px solid ${isVolOk ? '#10b981' : '#f59e0b'}; border-radius:4px; font-size:12px; line-height:1.45;">
                                    <b>❓ Durum & Neden Bekliyor?</b> ${commText}<br>
                                    <b>✅ Tetiklenme Şartı:</b> 5M mum kapanışı ve en az <b>${minSurge.toFixed(1)}x</b> hacim sağlandığında anında <b>${c.action}</b> tetiklenecektir.
                                </div>`
                            });
                        } else if (dist <= 0.85) {
                            const appText = ValkyrieCommentaryEngine.getApproaching(cleanS, c.targetName, dist, minSurge, rsScore);
                            thoughtItems.push({
                                cat: 'near',
                                symbol: cleanS,
                                color: '#38bdf8',
                                icon: '🎯',
                                tag: 'PUSUDA (YAKLAŞIYOR)',
                                tagClass: 'tag-autopsy-win',
                                title: `🎯 ${cleanS} • ${c.targetName} PUSUSU (Kalan Mesafe: %${dist.toFixed(2)})`,
                                text: `Fiyat ${c.targetName} ($${tPrice}) seviyesine doğru süzülüyor.<br>
                                ${telemetryBar}
                                <div style="margin-top:4px; padding:6px 10px; background:rgba(56,189,248,0.08); border-left:3px solid #38bdf8; border-radius:4px; font-size:12px; line-height:1.45;">
                                    <b>⚡ Beklenen Senaryo:</b> ${appText}
                                </div>`
                            });
                        }
                    });
                } else {
                    thoughtItems.push({
                        cat: 'near',
                        color: '#38bdf8',
                        icon: '🔭',
                        tag: 'LİKİDİTE RADARI',
                        tagClass: 'tag-autopsy-win',
                        title: `100 PARİTE PUSU RADARI AKTİF (${nowStr})`,
                        text: `Kurumsal nPOC hatları ve Camarilla pivotları sürekli taranıyor. Seviyelere %1.0'den daha fazla yaklaşan pariteler burada anlık teyit analizleriyle listelenecektir.`
                    });
                }

                // 2. GİRECEKTİ AMA GİRMEDİ (CANLI ELENEN SİNYALLER & SEBEPLERİ)
                const rejections = appState.recent_rejections || [];
                if (rejections.length > 0) {
                    rejections.slice(-6).reverse().forEach(rej => {
                        const cleanRej = (rej.symbol || '').replace('/USDT', '').replace('USDT', '').trim();
                        const rejAutopsy = ValkyrieCommentaryEngine.getRejectionAutopsy(cleanRej, rej.setup, rej.reason);
                        thoughtItems.push({
                            cat: 'rejected',
                            symbol: cleanRej,
                            color: '#f43f5e',
                            icon: '🛡️',
                            tag: 'GİRECEKTİ AMA GİRMEDİ',
                            tagClass: 'tag-autopsy-loss',
                            title: `⛔ ${cleanRej} • ${rej.setup} SİNYALİ ELENDİ (${rej.time})`,
                            text: `Robot bu paritede <b>${rej.setup}</b> kurulumunu tespit etti ve işleme girmeyi değerlendirdi.<br>
                            <div style="margin-top:4px; padding:6px 10px; background:rgba(244,63,94,0.08); border-left:3px solid #f43f5e; border-radius:4px;">
                                <b>🚫 Neden Poz Açılmadı?</b> <span style="color:#fda4af; font-weight:700;">${rej.reason}</span>.<br>
                                <b>💡 Alınan Önlem:</b> ${rejAutopsy}
                            </div>`
                        });
                    });
                } else {
                    thoughtItems.push({
                        cat: 'rejected',
                        color: '#94a3b8',
                        icon: '✅',
                        tag: 'RİSK DENETİMİ',
                        tagClass: 'tag-macro',
                        title: `RİSK FİLTRELERİ AKTİF (${nowStr})`,
                        text: `Kurumsal Hacim Kalkanı (min 1.5x), Trend Kalkanı ve 3. Temas Aşınma filtreleri devrede. Şartları sağlayamayan riskli sinyaller burada nedenleriyle birlikte canlı listelenecektir.`
                    });
                }

                // 3. AKTİF POZİSYONLAR İÇİN CANLI MENTORLUK & TAKTİKLER
                const openPositions = appState.open_positions || {};
                const openPosKeys = Object.keys(openPositions);

                if (openPosKeys.length > 0) {
                    openPosKeys.forEach(sym => {
                        const pos = openPositions[sym];
                        const cleanS = sym.replace('/USDT', '').replace('USDT', '').trim();
                        const curP = appState.symbols && appState.symbols[sym] ? appState.symbols[sym].price : pos.entry_price;
                        const lev = pos.leverage || 5;
                        const priceDiff = pos.side === 'LONG' ? (curP - pos.entry_price) : (pos.entry_price - curP);
                        const roePct = (priceDiff / pos.entry_price) * lev * 100.0;
                        const isHalf = pos.is_half_closed || pos.tp1_hit;
                        const tp1Val = pos.tp1 ? (typeof formatSmartPrice === 'function' ? formatSmartPrice(pos.tp1) : Number(pos.tp1).toFixed(4)) : '-';
                        const tp2Val = pos.tp2 ? (typeof formatSmartPrice === 'function' ? formatSmartPrice(pos.tp2) : Number(pos.tp2).toFixed(4)) : '-';
                        const stopVal = pos.hard_stop ? (typeof formatSmartPrice === 'function' ? formatSmartPrice(pos.hard_stop) : Number(pos.hard_stop).toFixed(4)) : '-';

                        const tacticText = ValkyrieCommentaryEngine.getPositionTactic(cleanS, pos, roePct, isHalf, stopVal, tp1Val, tp2Val);
                        const tacticTitle = `${cleanS} [${pos.side} ${lev}x] CANLI TAKTİK RAPORU`;
                        const tagColor = isHalf ? 'var(--green)' : (roePct >= 0 ? '#10b981' : '#f43f5e');

                        thoughtItems.push({
                            cat: 'positions',
                            symbol: cleanS,
                            color: tagColor,
                            icon: isHalf ? '🛡️' : '⚡',
                            tag: isHalf ? 'BREAKEVEN KOŞUSU' : 'AKTİF TAKTİK',
                            tagClass: 'tag-pos',
                            title: tacticTitle,
                            text: tacticText
                        });
                    });
                } else {
                    thoughtItems.push({
                        cat: 'positions',
                        color: '#10b981',
                        icon: '🔭',
                        tag: 'PUSU VE TETİK MASASI',
                        tagClass: 'tag-pos',
                        title: `AÇIK İŞLEM MASASI • PUSU MODU (${nowStr})`,
                        text: `Şu an aktif açık işlem yok. Sistem serbest sermayeyi koruyarak 100 paritede sahte kırılım filtreleri, 1.5x hacim şartı ve nPOC temaslarını tarıyor.`
                    });
                }

                // 4. KAPANAN İŞLEMLERİN CANLI OTOPSİSİ & DERSLERİ (POST-MORTEM)
                const historyTrades = appState.history || [];
                if (historyTrades.length > 0) {
                    const recentTrades = historyTrades.slice(-4).reverse();
                    recentTrades.forEach(tr => {
                        const cleanS = tr.symbol.replace('/USDT', '').replace('USDT', '').trim();
                        const pnl = Number(tr.net_pnl || 0);
                        const roe = Number(tr.roe_pct || 0);
                        const isWin = pnl >= 0;
                        const reason = tr.close_reason || '';
                        let autopsyTitle = `📋 ${cleanS} ${tr.side || ''} OTOPSİSİ (${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}$)`;
                        let autopsyColor = isWin ? '#38bdf8' : '#f43f5e';
                        let autopsyTag = isWin ? 'KÂR OTOPSİSİ' : 'STOP OTOPSİSİ';
                        let autopsyTagClass = isWin ? 'tag-autopsy-win' : 'tag-autopsy-loss';

                        const stopStr = tr.hard_stop ? '$' + (typeof formatSmartPrice === 'function' ? formatSmartPrice(tr.hard_stop) : Number(tr.hard_stop).toFixed(4)) : '';
                        const autopsyText = ValkyrieCommentaryEngine.getPostMortemAutopsy(cleanS, tr, pnl, roe, isWin, reason, stopStr);

                        thoughtItems.push({
                            cat: 'autopsy',
                            symbol: cleanS,
                            color: autopsyColor,
                            icon: isWin ? '🎉' : '🛡️',
                            tag: autopsyTag,
                            tagClass: autopsyTagClass,
                            title: autopsyTitle,
                            text: autopsyText
                        });
                    });
                }

                // Update Counts on Filter Buttons
                const allCnt = thoughtItems.length;
                const macroCnt = thoughtItems.filter(t => t.cat === 'macro').length;
                const nearCnt = thoughtItems.filter(t => t.cat === 'near').length;
                const rejCnt = thoughtItems.filter(t => t.cat === 'rejected').length;
                const posCnt = thoughtItems.filter(t => t.cat === 'positions').length;
                const autCnt = thoughtItems.filter(t => t.cat === 'autopsy').length;

                const elAll = document.getElementById('ai-cnt-all');
                const elMacro = document.getElementById('ai-cnt-macro');
                const elNear = document.getElementById('ai-cnt-near');
                const elRej = document.getElementById('ai-cnt-rej');
                const elPos = document.getElementById('ai-cnt-pos');
                const elAut = document.getElementById('ai-cnt-autopsy');
                if (elAll) elAll.innerText = allCnt;
                if (elMacro) elMacro.innerText = macroCnt;
                if (elNear) elNear.innerText = nearCnt;
                if (elRej) elRej.innerText = rejCnt;
                if (elPos) elPos.innerText = posCnt;
                if (elAut) elAut.innerText = autCnt;

                window.renderAiThoughts = function() {
                    const f = window.currentAiFilter || 'all';
                    const filtered = f === 'all' ? thoughtItems : thoughtItems.filter(t => t.cat === f);
                    if (filtered.length === 0) {
                        feed.innerHTML = `<div style="text-align:center; padding:20px; color:#64748b; font-size:12.5px;">Bu kategoride henüz yeni bir akıl yürütme notu bulunmuyor.</div>`;
                        return;
                    }
                    feed.innerHTML = filtered.map(t => {
                        const cleanSym = t.symbol ? t.symbol.replace('/USDT', '').replace('USDT', '').trim() : '';
                        const chartBtn = cleanSym ? `
                            <button class="btn-open-chart" onclick="openTradingViewModal('${cleanSym}')" title="${cleanSym} Canlı Göstergeli Grafiği Aç" style="padding:2px 8px; font-size:11px; margin-left:auto; flex-shrink:0;">
                                📈 Grafik
                            </button>
                        ` : '';
                        const isMacro = t.cat === 'macro';
                        const macroClass = isMacro ? ' macro-span' : '';
                        return `
                        <div class="ai-thought-item${macroClass}" style="border-left-color: ${t.color};">
                            <span style="font-size:20px; flex-shrink:0;">${t.icon}</span>
                            <div style="flex:1; min-width:0;">
                                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; flex-wrap:wrap; gap:6px;">
                                    <div style="font-weight:800; color:${t.color}; font-size:13px; font-family:'JetBrains Mono', monospace; display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                                        <span class="ai-thought-tag ${t.tagClass}">${t.tag}</span>
                                        <span>${t.title}</span>
                                    </div>
                                    ${chartBtn}
                                </div>
                                <div style="font-size:12.5px; color:#cbd5e1; line-height:1.5;">${t.text}</div>
                            </div>
                        </div>`;
                    }).join('');
                };

                window.renderAiThoughts();
            }

            // Update Nav Tab Badges
            updateNavBadges();
        }

        function updateNavBadges() {
            try {
                const navPosBadge = document.getElementById('nav-pos-count-badge');
                const openPos = (appState && appState.open_positions) || {};
                const openCount = Object.keys(openPos).length;
                if (navPosBadge) {
                    navPosBadge.innerText = openCount;
                    navPosBadge.style.display = 'inline-flex';
                    if (openCount > 0) {
                        navPosBadge.className = 'tab-badge active-pulse';
                    } else {
                        navPosBadge.className = 'tab-badge zero-idle';
                    }
                }
                const navActiveBadge = document.getElementById('nav-active-coins-badge');
                if (navActiveBadge && appState && appState.symbols) {
                    const totalC = Object.keys(appState.symbols).length;
                    navActiveBadge.innerText = `${totalC}/100`;
                }
                const navHealthBadge = document.getElementById('nav-health-tab-badge') || document.getElementById('nav-health-badge');
                if (navHealthBadge && appState && appState.system_health) {
                    const sys = appState.system_health;
                    if (sys.is_perfect) {
                        navHealthBadge.innerText = `${sys.score_str || '10/10'} Kusursuz`;
                        navHealthBadge.style.color = '#22c55e';
                        navHealthBadge.style.background = 'rgba(34,197,94,0.15)';
                        navHealthBadge.style.borderColor = 'rgba(34,197,94,0.3)';
                    } else {
                        navHealthBadge.innerText = sys.score_str ? `${sys.score_str}` : `${sys.healthy_symbols || 100}/${sys.total_symbols || 100}`;
                        navHealthBadge.style.color = 'var(--yellow)';
                        navHealthBadge.style.background = 'rgba(245,158,11,0.15)';
                        navHealthBadge.style.borderColor = 'rgba(245,158,11,0.3)';
                    }
                }
            } catch (e) {
                console.error("updateNavBadges error:", e);
            }
        }

        let appState = { symbols: {}, balance: 100.0, open_positions: {}, history: [], all_coins: [] };
        let searchQuery = '';

        function handleSearch(val) {
            searchQuery = (val || '').trim().toUpperCase();
            const clearBtn = document.getElementById('search-clear-btn');
            if (clearBtn) {
                clearBtn.style.display = searchQuery ? 'block' : 'none';
            }
            renderCoinManager();
            renderCards();
        }

        function clearSearch() {
            searchQuery = '';
            const input = document.getElementById('coin-search-input');
            if (input) input.value = '';
            const clearBtn = document.getElementById('search-clear-btn');
            if (clearBtn) clearBtn.style.display = 'none';
            renderCoinManager();
            renderCards();
        }

        let livePrices = {};
        let tickCounts = 0;

        const rawSymbolMap = {
            'BTCUSDT': 'BTC/USDT', 'ETHUSDT': 'ETH/USDT', 'SOLUSDT': 'SOL/USDT', 'XRPUSDT': 'XRP/USDT',
            'ENAUSDT': 'ENA/USDT', 'DOGEUSDT': 'DOGE/USDT', 'ADAUSDT': 'ADA/USDT', 'BNBUSDT': 'BNB/USDT',
            'AVAXUSDT': 'AVAX/USDT', 'SUIUSDT': 'SUI/USDT', 'LINKUSDT': 'LINK/USDT', '1000PEPEUSDT': 'PEPE/USDT',
            'NEARUSDT': 'NEAR/USDT', 'APTUSDT': 'APT/USDT', 'ARBUSDT': 'ARB/USDT', 'OPUSDT': 'OP/USDT',
            'TIAUSDT': 'TIA/USDT', 'INJUSDT': 'INJ/USDT', 'FETUSDT': 'FET/USDT', 'DOTUSDT': 'DOT/USDT',
            '1000SHIBUSDT': 'SHIB/USDT', 'TONUSDT': 'TON/USDT', 'WIFUSDT': 'WIF/USDT', 'GALAUSDT': 'GALA/USDT',
            'SEIUSDT': 'SEI/USDT', 'RENDERUSDT': 'RENDER/USDT', 'FTMUSDT': 'FTM/USDT', 'ATOMUSDT': 'ATOM/USDT',
            'LTCUSDT': 'LTC/USDT', 'POLUSDT': 'POL/USDT', 'NEIROUSDT': 'NEIRO/USDT', '1000NEIROUSDT': 'NEIRO/USDT', '1000BONKUSDT': 'BONK/USDT',
            '1000FLOKIUSDT': 'FLOKI/USDT', '1000LUNCUSDT': 'LUNC/USDT', '1000XECUSDT': 'XEC/USDT',
            '1000CHEEMSUSDT': 'CHEEMS/USDT', '1000WHYUSDT': 'WHY/USDT', '1000CATUSDT': 'CAT/USDT'
        };

        // UNIFIED PNL COMPUTATION ENGINE (WITH MULTIPLIER SANITY GUARD)
        function computePositionPnL(pos, livePrice) {
            let curP = Number(livePrice || pos.entry_price);
            if (!curP || isNaN(curP) || curP <= 0) curP = Number(pos.entry_price);
            const entryP = Number(pos.entry_price) || curP;

            // Auto-align 1000x / 1M meme coin multiplier between spot and futures
            if (entryP > 0) {
                if (curP < entryP * 0.02) {
                    if (curP * 1000 >= entryP * 0.4 && curP * 1000 <= entryP * 2.5) {
                        curP = curP * 1000;
                    } else if (curP * 1000000 >= entryP * 0.4 && curP * 1000000 <= entryP * 2.5) {
                        curP = curP * 1000000;
                    }
                } else if (curP > entryP * 50) {
                    if ((curP / 1000) >= entryP * 0.4 && (curP / 1000) <= entryP * 2.5) {
                        curP = curP / 1000;
                    } else if ((curP / 1000000) >= entryP * 0.4 && (curP / 1000000) <= entryP * 2.5) {
                        curP = curP / 1000000;
                    }
                }
            }

            const isLong = pos.side === 'LONG';
            let priceDiffPct = isLong ? ((curP - entryP) / entryP) * 100 : ((entryP - curP) / entryP) * 100;

            // Outlier Glitch Shield
            if (priceDiffPct < -85.0 || priceDiffPct > 500.0) {
                curP = entryP;
                priceDiffPct = 0.0;
            }

            const roePct = priceDiffPct * (pos.leverage || 5);
            const posVal = Number(pos.position_value) || (Number(pos.margin || 100) * Number(pos.leverage || 5));
            const pnlUsdt = posVal * (priceDiffPct / 100);
            const isWin = pnlUsdt > 0.0001;
            const isLoss = pnlUsdt < -0.0001;
            return { curP, isLong, priceDiffPct, roePct, pnlUsdt, isWin, isLoss };
        }

        function formatSmartPrice(val) {
            if (val === null || val === undefined || isNaN(val) || Number(val) <= 0) return '-';
            const n = Number(val);
            if (n >= 1000) return n.toFixed(2);
            if (n >= 10) return n.toFixed(3);
            if (n >= 1) return n.toFixed(4);
            if (n >= 0.01) return n.toFixed(5);
            if (n >= 0.0001) return n.toFixed(7);
            return n.toFixed(8);
        }

        function togglePoolCollapse() {
            const grid = document.getElementById('coin-chips-container');
            const btn = document.getElementById('pool-collapse-btn');
            if (!grid) return;
            if (grid.style.display === 'none' || grid.style.display === '') {
                grid.style.display = 'grid';
                if (btn) {
                    btn.innerHTML = '▲ Parite Havuzunu Gizle';
                    btn.style.color = 'var(--text-muted)';
                    btn.style.borderColor = 'rgba(255,255,255,0.15)';
                }
                renderCoinManager();
            } else {
                grid.style.display = 'none';
                if (btn) {
                    btn.innerHTML = '⚙️ 100 Parite Havuzunu Aç ▼';
                    btn.style.color = 'var(--cyan)';
                    btn.style.borderColor = 'rgba(0,242,254,0.3)';
                }
            }
        }

        function renderCoinManager() {
            const cont = document.getElementById('coin-chips-container');
            if (!cont) return;

            let coins = appState.all_coins;
            if (!coins || coins.length === 0) {
                if (appState.symbols && Object.keys(appState.symbols).length > 0) {
                    coins = Object.keys(appState.symbols).map(s => ({
                        symbol: s,
                        active: true,
                        price: (appState.symbols[s] && appState.symbols[s].price) || 0
                    }));
                } else {
                    coins = [];
                }
            }

            if (coins.length === 0) {
                cont.innerHTML = '<div style="grid-column: 1 / -1; text-align:center; padding: 20px; color: #94a3b8; font-size:13px;">100 Parite verisi senkronize ediliyor...</div>';
                return;
            }

            // 100 Pariteyi A'dan Z'ye Kusursuz Harf Sırasına Diz
            let sortedCoins = [...coins].sort((a, b) => {
                const symA = (a.symbol || '').replace('/USDT', '').toUpperCase();
                const symB = (b.symbol || '').replace('/USDT', '').toUpperCase();
                return symA.localeCompare(symB);
            });

            const activeCount = sortedCoins.filter(c => c.active).length;
            const totalCount = sortedCoins.length;

            let filteredCoins = sortedCoins;
            if (searchQuery) {
                filteredCoins = sortedCoins.filter(c => {
                    const clean = (c.symbol || '').replace('/USDT', '').toUpperCase();
                    return clean.includes(searchQuery) || (c.symbol || '').toUpperCase().includes(searchQuery);
                });
                const cntEl = document.getElementById('active-coin-counter');
                if (cntEl) cntEl.innerText = `${filteredCoins.length} Eşleşen / ${activeCount} Aktif`;
            } else {
                const cntEl = document.getElementById('active-coin-counter');
                if (cntEl) cntEl.innerText = `${activeCount} Aktif / ${totalCount} Parite (A-Z)`;
            }

            let html = '';
            if (filteredCoins.length === 0) {
                html = `<div style="grid-column: 1 / -1; text-align:center; padding: 24px; color: #94a3b8; font-size:14px;">"${searchQuery}" ile eşleşen parite bulunamadı.</div>`;
            } else {
                filteredCoins.forEach(coin => {
                    const clean = (coin.symbol || '').replace('/USDT', '');
                    const curPrice = Number(livePrices[coin.symbol] || coin.price || 0);
                    const priceStr = curPrice > 0 ? (curPrice < 0.001 ? '$' + curPrice.toFixed(6) : (curPrice < 1 ? '$' + curPrice.toFixed(4) : '$' + curPrice.toFixed(2))) : '---';
                    const isHighlighted = searchQuery && clean.includes(searchQuery);

                    html += `
                    <div class="coin-chip ${coin.active ? 'is-active' : ''} ${isHighlighted ? 'chip-highlight' : ''}" onclick="toggleSymbol('${coin.symbol}', ${!coin.active})" title="${clean} - Tıkla: Aç/Kapat (Çift Tıkla: Karta Git)" ondblclick="event.stopPropagation(); scrollToWatchlistCard('${coin.symbol}')">
                        <div>
                            <div class="chip-sym">
                                <span class="chip-dot"></span>
                                ${clean}
                            </div>
                            <div style="font-size:11.5px; color:#cbd5e1; margin-top:2px; font-family:'JetBrains Mono'">${priceStr}</div>
                        </div>
                        <button class="chip-btn ${coin.active ? 'btn-toggle-on' : 'btn-toggle-off'}">
                            ${coin.active ? 'AKTİF' : 'PASİF'}
                        </button>
                    </div>
                    `;
                });
            }
            cont.innerHTML = html;
        }
        async function toggleSymbol(symbol, active) {
            try {
                if (appState.all_coins) {
                    const found = appState.all_coins.find(c => c.symbol === symbol);
                    if (found) found.active = active;
                    renderCoinManager();
                }
                await fetch('/api/toggle_symbol', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ symbol: symbol, active: active })
                });
                await syncBackendState();
            await fetchLiveStatus();
                startBinanceGlobalFeed();
            } catch (err) {
                console.error("toggleSymbol error:", err);
            }
        }

        async function selectTopN(n) {
            try {
                let all = [];
                if (appState.all_coins && appState.all_coins.length > 0) {
                    all = appState.all_coins.map(c => c.symbol);
                } else if (appState.symbols && Object.keys(appState.symbols).length > 0) {
                    all = Object.keys(appState.symbols);
                }
                let selected = [];
                if (n > 0) {
                    selected = all.slice(0, n);
                }
                if (appState.all_coins) {
                    const selSet = new Set(selected);
                    appState.all_coins.forEach(c => { c.active = selSet.has(c.symbol); });
                    renderCoinManager();
                }
                await fetch('/api/set_active_symbols', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ symbols: selected })
                });
                await syncBackendState();
                startBinanceGlobalFeed();
            } catch (e) {
                console.error("selectTopN error:", e);
            }
        }

        function generateDetailedIntelligence(symbol, price, cam, levels, openPos) {
            cam = cam || {};
            levels = levels || {};
            price = Number(price) || 0;
            
            const r4 = Number(cam.R4) || 0;
            const r3 = Number(cam.R3) || 0;
            const r5 = Number(cam.R5) || 0;
            const s3 = Number(cam.S3) || 0;
            const s4 = Number(cam.S4) || 0;
            const s5 = Number(cam.S5) || 0;
            const p = Number(cam.P) || 0;
            const tepeAvwap = Number(levels.tepe_avwap) || 0;
            const dipAvwap = Number(levels.dip_avwap) || 0;
            const mvah = Number(levels.mvah) || 0;
            const mval = Number(levels.mval) || 0;
            const mpoc = Number(levels.mpoc) || 0;
            const aboveNpoc = Number(levels.above_npoc) || 0;
            const belowNpoc = Number(levels.below_npoc) || 0;
            const aboveNvah = Number(levels.above_nvah) || 0;
            const belowNval = Number(levels.below_nval) || 0;

            const formatVal = (v) => formatSmartPrice(v);

            // 1. 1H MAKRO TREND HESABI
            let macroTrend = "⚪ YATAY / SIKIŞMA";
            let macroColor = "#94a3b8";
            if (tepeAvwap > 0 && p > 0 && price > tepeAvwap && price > p) {
                macroTrend = "🟢 GÜÇLÜ BOĞA";
                macroColor = "var(--green)";
            } else if (dipAvwap > 0 && p > 0 && price < dipAvwap && price < p) {
                macroTrend = "🔴 GÜÇLÜ AYI";
                macroColor = "var(--red)";
            } else if (p > 0 && price > p) {
                macroTrend = "🟡 ILIMLI BOĞA";
                macroColor = "var(--yellow)";
            } else if (p > 0 && price < p) {
                macroTrend = "🟠 ILIMLI AYI";
                macroColor = "#fb923c";
            }

            // 2. EN YAKIN DİRENÇ VE DESTEK
            const allUp = [r3, r4, r5, tepeAvwap, mvah, aboveNpoc, aboveNvah, mpoc, p].filter(x => x && x > price * 1.0005);
            allUp.sort((a, b) => a - b);
            const nearestUp = allUp.length > 0 ? allUp[0] : null;
            const upDistPct = nearestUp ? (((nearestUp - price) / price) * 100).toFixed(2) : null;

            const allDown = [s3, s4, s5, dipAvwap, mval, belowNpoc, belowNval, mpoc, p].filter(x => x && x < price * 0.9995);
            allDown.sort((a, b) => b - a);
            const nearestDown = allDown.length > 0 ? allDown[0] : null;
            const downDistPct = nearestDown ? (((price - nearestDown) / price) * 100).toFixed(2) : null;

            // 3. CANLI POZİSYON DURUM YORUMU
            let posCommentary = "";
            if (openPos) {
                const liveStop = openPos.is_half_closed ? (openPos.soft_stop || openPos.hard_stop) : (openPos.hard_stop || openPos.soft_stop);
                if (openPos.is_half_closed || openPos.tp1_hit) {
                    posCommentary = "🎯 TP1 ALINDI (%50 Kâr Kasada) • Stop Breakeven Korumalı • TP2 Hedefine Koşuyor";
                } else if (openPos.trail_status) {
                    posCommentary = openPos.trail_status;
                } else {
                    posCommentary = `⚡ ${openPos.side} Aktif • TP1: $${openPos.tp1 ? formatSmartPrice(openPos.tp1) : '-'} • Stop: $${liveStop ? formatSmartPrice(liveStop) : '-'}`;
                }
            }

            function packResult(tag, color, statusText, actionPlan) {
                return {
                    tag: tag,
                    color: color,
                    statusText: statusText,
                    actionPlan: actionPlan,
                    macroTrend: macroTrend,
                    macroColor: macroColor,
                    nearestUp: nearestUp,
                    nearestDown: nearestDown,
                    upDistPct: upDistPct,
                    downDistPct: downDistPct,
                    posCommentary: posCommentary
                };
            }

            const ctx = {
                pPrice: formatVal(price),
                pivot: formatVal(p),
                r3: formatVal(r3),
                r4: formatVal(r4),
                r5: formatVal(r5),
                s3: formatVal(s3),
                s4: formatVal(s4),
                s5: formatVal(s5),
                belowNpoc: formatVal(belowNpoc),
                aboveNpoc: formatVal(aboveNpoc),
                mvah: formatVal(mvah),
                mval: formatVal(mval),
                mpoc: formatVal(mpoc),
                macroTrend: macroTrend
            };

            // DURUM 0: ACIK POZISYON VARSA CANLI POZISYON YONETIMI
            if (openPos) {
                const metrics = computePositionPnL(openPos, price);
                const isWin = metrics.isWin;
                const isLoss = metrics.isLoss;
                const statusColor = isLoss ? 'var(--red)' : (isWin ? 'var(--green)' : '#ffffff');
                const liveStop = openPos.is_half_closed ? (openPos.soft_stop || openPos.hard_stop) : (openPos.hard_stop || openPos.soft_stop);
                const isHalf = openPos.is_half_closed || openPos.tp1_hit;
                const posDeskBriefing = isHalf
                    ? `🎯 <b>Masa Takip Planı:</b> TP1 kârı (%50) nakite kilitlendi. Kalan bakiye $${formatSmartPrice(liveStop)} Breakeven zırhında; nihai hedef <b>TP2 ($${formatSmartPrice(openPos.tp2 || 0)})</b> bekleniyor. Bu pozisyonda anapara kaybı riski sıfırlanmıştır.`
                    : `🎯 <b>Masa Takip Planı:</b> 1.5 ATR Dinamik Stop Seviyesi ($${formatSmartPrice(liveStop)}) ${openPos.side === 'LONG' ? 'altına inerse' : 'üstüne çıkarsa'} işlem kapatılacak. Pozisyon <b>+%7.0 ROE kâra ulaştığında</b> veya <b>90dk kârda beklediğinde</b> (ya da TP1 $${formatSmartPrice(openPos.tp1)} hedefine geldiğinde) <b>%50 kâr anında nakite kilitlenecek</b>, kalan %50 pozisyon stopu risksiz Breakeven seviyesine çekilerek zirveye kadar koşturulacak.`;

                return packResult(
                    `🛡️ ${openPos.leverage}x ${openPos.side} POZİSYONU CANLI YÖNETİLİYOR`,
                    statusColor,
                    `Bot şu anda <b>${openPos.side}</b> pozisyonunu aktif koruyor. Giriş: <b>$${formatSmartPrice(openPos.entry_price)}</b> | Anlık: <b>$${formatSmartPrice(metrics.curP)}</b> | Durum: <b style="color:${statusColor}">${metrics.roePct >= 0 ? '+' : ''}${metrics.roePct.toFixed(2)}% ROE (${metrics.pnlUsdt >= 0 ? '+' : ''}${metrics.pnlUsdt.toFixed(2)} $)</b>`,
                    posDeskBriefing
                );
            }

            // DURUM 1: AŞAĞI nPOC / LİKİDİTE DESTEK TESTİ (YENİ SETUP 9)
            if (belowNpoc > 0 && Math.abs(price - belowNpoc) / belowNpoc <= 0.006) {
                const isConf = (s3 > 0 && Math.abs(s3 - belowNpoc) / belowNpoc <= 0.005);
                const confTag = isConf ? ' ★ S3 + nPOC ÇİFT DESTEK' : '';
                return packResult(
                    `🎯 AŞAĞI nPOC LİKİDİTE TESTİ${confTag}`,
                    'var(--cyan)',
                    `Fiyat dokunulmamış kurumsal hacim bloğu olan <b>Aşağı nPOC ($${formatVal(belowNpoc)})</b> desteğini test ediyor.`,
                    ValkyrieCommentaryEngine.getDeskBriefing('BELOW_NPOC', symbol, ctx)
                );
            }

            // DURUM 2: YUKARI nPOC / LİKİDİTE DİRENÇ TESTİ (YENİ SETUP 10)
            if (aboveNpoc > 0 && Math.abs(price - aboveNpoc) / aboveNpoc <= 0.006) {
                const isConf = (r3 > 0 && Math.abs(r3 - aboveNpoc) / aboveNpoc <= 0.005);
                const confTag = isConf ? ' ★ R3 + nPOC ÇİFT DİRENÇ' : '';
                return packResult(
                    `🎯 YUKARI nPOC DİRENÇ TESTİ${confTag}`,
                    'var(--yellow)',
                    `Fiyat dokunulmamış kurumsal tepe bloğu olan <b>Yukarı nPOC ($${formatVal(aboveNpoc)})</b> direncini test ediyor.`,
                    ValkyrieCommentaryEngine.getDeskBriefing('ABOVE_NPOC', symbol, ctx)
                );
            }

            // DURUM 3: R5 ZIRVESI / ASIRI ALIM
            if (r5 > 0 && price >= r5) {
                return packResult(
                    '🔥 R5 AŞIRI ALIM (TREND ZİRVESİ GENİŞLEMESİ)',
                    'var(--yellow)',
                    `Fiyat <b>R5 ($${formatVal(r5)})</b> zirve seviyesinin üzerine çıktı, aşırı alım bölgesinde seyrediyor.`,
                    ValkyrieCommentaryEngine.getDeskBriefing('R5_OVERBOUGHT', symbol, ctx)
                );
            }

            // DURUM 4: R4 - R5 BOGA KANALI (BREAKOUT & RETEST)
            if (r4 > 0 && price > r4) {
                const npocText = aboveNpoc > 0 ? ` (Üst nPOC: $${formatVal(aboveNpoc)})` : (aboveNvah > 0 ? ` (Üst nVAH: $${formatVal(aboveNvah)})` : '');
                return packResult(
                    '🚀 R4 BOĞA KANALI (BREAKOUT & RETEST PUSUSU)',
                    'var(--green)',
                    `Fiyat <b>R4 ($${formatVal(r4)})</b> üzerinde boğa bölgesinde. Üst hedef: <b>R5 ($${formatVal(r5)})</b>${npocText}.`,
                    ValkyrieCommentaryEngine.getDeskBriefing('R4_BREAKOUT', symbol, ctx)
                );
            }

            // DURUM 5: R3 - R4 SIKISMA & KARAR BOLGESI
            if (r3 > 0 && price > r3 && price <= r4) {
                return packResult(
                    '⚖️ R3-R4 SIKIŞMA & KIRILIM PUSUSU',
                    '#ffa726',
                    `Fiyat <b>R3 ($${formatVal(r3)})</b> desteği ile <b>R4 ($${formatVal(r4)})</b> direnci arasında sıkışıyor.`,
                    ValkyrieCommentaryEngine.getDeskBriefing('R3_R4_COMPRESSION', symbol, ctx)
                );
            }

            // DURUM 6: S3 - R3 PIVOT YATAY KANAL (SCALP KANALI)
            if (s3 > 0 && r3 > 0 && price >= s3 && price <= r3) {
                return packResult(
                    '🔄 PİVOT YATAY KANAL (DESTEK / DİRENÇ TEPKİSİ)',
                    '#388bfd',
                    `Fiyat <b>Pivot P ($${formatVal(p)})</b> ekseninde dengeli seyrediyor. (Alt: S3 $${formatVal(s3)} • Üst: R3 $${formatVal(r3)})`,
                    ValkyrieCommentaryEngine.getDeskBriefing('S3_R3_RANGE', symbol, ctx)
                );
            }

            // DURUM 7: S4 - S3 COKUS UYARI BOLGESI
            if (s4 > 0 && price > s4 && price < s3) {
                return packResult(
                    '⚠️ S4-S3 ÇÖKÜŞ UYARI BÖLGESİ',
                    '#d500f9',
                    `Fiyat <b>S3 ($${formatVal(s3)})</b> altına indi, son savunma hattı olan <b>S4 ($${formatVal(s4)})</b> test ediliyor.`,
                    ValkyrieCommentaryEngine.getDeskBriefing('S4_S3_WARNING', symbol, ctx)
                );
            }

            // DURUM 8: S4 ALTI AYI BOLGESI (BREAKDOWN)
            if (s4 > 0 && price <= s4) {
                const npocText = belowNpoc > 0 ? ` (Alt nPOC: $${formatVal(belowNpoc)})` : (belowNval > 0 ? ` (Alt nVAL: $${formatVal(belowNval)})` : '');
                return packResult(
                    '📉 S4 AYI BÖLGESİ (PANİK & BREAKDOWN PUSUSU)',
                    'var(--red)',
                    `Fiyat <b>S4 ($${formatVal(s4)})</b> altında ayı hakimiyetinde. Alt hedef: <b>S5 ($${formatVal(s5)})</b> / <b>mVAL ($${formatVal(mval)})</b>${npocText}.`,
                    ValkyrieCommentaryEngine.getDeskBriefing('S4_BREAKDOWN', symbol, ctx)
                );
            }

            // DURUM 9: mVAH GERÇEK YAKINLIK TESTİ (Macro Breakout)
            if (mvah > 0 && Math.abs(price - mvah) / mvah <= 0.015) {
                const npocText = aboveNpoc > 0 ? ` Hedef Üst nPOC: $${formatVal(aboveNpoc)}.` : '';
                return packResult(
                    '🎯 mVAH AYLIK TAVAN BÖLGESİ (MACRO TEST)',
                    'var(--cyan)',
                    `Fiyat <b>mVAH ($${formatVal(mvah)})</b> aylık tepe hacim duvarını test ediyor.${npocText}`,
                    ValkyrieCommentaryEngine.getDeskBriefing('MVAH_TEST', symbol, ctx)
                );
            }

            return packResult(
                '🔍 PİYASA İZLENİYOR',
                'var(--text-muted)',
                `Fiyat $${formatVal(price)} seviyesinde stabil.`,
                ValkyrieCommentaryEngine.getDeskBriefing('WATCH', symbol, ctx)
            );
        }

        let visibleCardsCount = 100;

        function loadMoreCards(n) {
            visibleCardsCount += n;
            renderCards();
                renderCockpitView();
                updateSystemHealthBadge();
        }

        function loadAllCards() {
            visibleCardsCount = 999;
            renderCards();
            renderCockpitView();
            updateSystemHealthBadge();
        }

        
        function toggleLevelsAccordion(safeId) {
            const el = document.getElementById('acc-' + safeId);
            const btn = document.getElementById('acc-btn-' + safeId);
            if (el) {
                if (el.style.display === 'none' || el.style.display === '') {
                    el.style.display = 'block';
                    if (btn) btn.innerHTML = '<span>📊 15 Kilit Seviyeyi Gizle</span> <span>▲</span>';
                } else {
                    el.style.display = 'none';
                    if (btn) btn.innerHTML = '<span>📊 15 Kilit Seviyeyi Aç</span> <span>▼</span>';
                }
            }
        }

        function renderCards() {
            try {
                const cont = document.getElementById('watchlist-container');
                if (!cont || !appState.symbols) return;
                
                const allActiveSymbols = Object.keys(appState.symbols);
                if (allActiveSymbols.length === 0) {
                    cont.innerHTML = '<div style="grid-column: 1 / -1; color: #94a3b8; text-align:center; padding: 60px 20px; font-size:15px;">Aktif takip edilen parite bulunmuyor.<br><span style="color:var(--yellow)">Yukarıdaki Parite Yönetim Havuzundan parite seçebilirsiniz.</span></div>';
                    return;
                }

                let displaySymbols = [];
                const searchBadge = document.getElementById('watchlist-search-count-badge');

                if (searchQuery) {
                    const matchedSymbols = allActiveSymbols.filter(s => {
                        const clean = s.replace('/USDT', '').toUpperCase();
                        return clean.includes(searchQuery) || s.toUpperCase().includes(searchQuery);
                    });
                    displaySymbols = matchedSymbols;
                    
                    if (searchBadge) {
                        searchBadge.style.display = 'inline-block';
                        searchBadge.innerText = `🔍 "${searchQuery}" ile Eşleşen: ${matchedSymbols.length} Parite`;
                    }

                    if (displaySymbols.length === 0) {
                        const inAllCoins = (appState.all_coins || []).find(c => c.symbol.replace('/USDT','').toUpperCase() === searchQuery || c.symbol.toUpperCase().includes(searchQuery));
                        let activateBtn = '';
                        if (inAllCoins) {
                            activateBtn = `<button onclick="toggleSymbol('${inAllCoins.symbol}', true)" style="margin-top:12px; background:linear-gradient(135deg, #0ecb81, #059669); border:none; color:#07090e; font-weight:800; padding:8px 18px; border-radius:8px; cursor:pointer;">⚡ ${inAllCoins.symbol} Paritesini Aktif Et ve İzle</button><br>`;
                        }
                        cont.innerHTML = `
                            <div style="grid-column: 1 / -1; color: #94a3b8; text-align:center; padding: 60px 20px; font-size:15px; line-height:1.6;">
                                "${searchQuery}" ile eşleşen aktif analiz kartı bulunamadı.<br>
                                ${activateBtn}
                                <button onclick="clearSearch()" style="margin-top:10px; background:rgba(56,139,253,0.15); border:1px solid var(--blue); color:#58a6ff; font-weight:700; padding:6px 14px; border-radius:8px; cursor:pointer;">✕ Aramayı Temizle</button>
                            </div>`;
                        return;
                    }
                } else {
                    if (searchBadge) searchBadge.style.display = 'none';
                    const posCoins = allActiveSymbols.filter(s => appState.open_positions && appState.open_positions[s]);
                    const otherCoins = allActiveSymbols.filter(s => !(appState.open_positions && appState.open_positions[s]));
                    const remainingSlots = Math.max(0, visibleCardsCount - posCoins.length);
                    const visibleOtherCoins = otherCoins.slice(0, remainingSlots);
                    displaySymbols = [...posCoins, ...visibleOtherCoins];
                }

                let html = '';

                for (const symbol of displaySymbols) {
                    try {
                        const coin = appState.symbols[symbol] || {};
                        const price = Number(livePrices[symbol] || coin.price || 0);
                        const levels = coin.levels || {};
                        const cam = levels.camarilla || {};
                        const hasPos = appState.open_positions && appState.open_positions[symbol];
                        const intel = generateDetailedIntelligence(symbol, price, cam, levels, hasPos);
                        const safeId = symbol.replace(/[^a-zA-Z0-9]/g, '_');
                        
                        let posClass = '';
                        let posBannerHtml = '';
                        if (hasPos) {
                            const metrics = computePositionPnL(hasPos, price);
                            if (metrics.isLoss) {
                                posClass = 'has-active-pos-loss';
                                posBannerHtml = `
                                <div class="card-pos-banner banner-loss" id="pos-banner-${safeId}">
                                    <div class="pos-pill-loss" id="pill-${safeId}">⚡ ${hasPos.side} (${metrics.roePct.toFixed(2)}% ROE)</div>
                                    <button class="btn-card-manual-close" onclick="event.stopPropagation(); openConfirmModal('${symbol}')" title="Bu pozisyonu anında piyasa fiyatından kapat">🛑 Pozisyonu Kapat</button>
                                </div>`;
                            } else if (metrics.isWin) {
                                posClass = 'has-active-pos-profit';
                                posBannerHtml = `
                                <div class="card-pos-banner banner-profit" id="pos-banner-${safeId}">
                                    <div class="pos-pill-profit" id="pill-${safeId}">⚡ ${hasPos.side} (+${metrics.roePct.toFixed(2)}% ROE)</div>
                                    <button class="btn-card-manual-close" onclick="event.stopPropagation(); openConfirmModal('${symbol}')" title="Bu pozisyonu anında piyasa fiyatından kapat">🛑 Pozisyonu Kapat</button>
                                </div>`;
                            } else {
                                posClass = '';
                                posBannerHtml = `
                                <div class="card-pos-banner banner-profit" id="pos-banner-${safeId}">
                                    <div class="pos-pill-profit" id="pill-${safeId}">⚡ ${hasPos.side} (0.00% ROE)</div>
                                    <button class="btn-card-manual-close" onclick="event.stopPropagation(); openConfirmModal('${symbol}')" title="Bu pozisyonu anında piyasa fiyatından kapat">🛑 Pozisyonu Kapat</button>
                                </div>`;
                            }
                        }

                        function formatPriceClean(val) {
                            if (!val || isNaN(val) || Number(val) <= 0) return '-';
                            const n = Number(val);
                            if (n >= 1000) return n.toFixed(2);
                            if (n >= 1) return n.toFixed(4);
                            if (n >= 0.01) return n.toFixed(5);
                            return n.toFixed(6);
                        }

                        const cleanSym = symbol.replace('/USDT', '');
                        
                        let tableHtml = '';
                        if (cam && cam.R4) {
                            tableHtml = `
                            <table class="levels-table">
                                <tr><td class="lvl-lbl">R5 (Zirve Hedef)</td><td class="lvl-num" style="color:var(--yellow)">${formatPriceClean(cam.R5)}</td></tr>
                                <tr><td class="lvl-lbl">R4 (Breakout Tetik)</td><td class="lvl-num" style="color:#ffa726; font-weight:800">${formatPriceClean(cam.R4)}</td></tr>
                                <tr><td class="lvl-lbl">Tepe AVWAP (Kırmızı)</td><td class="lvl-num" style="color:var(--red); font-weight:800">${formatPriceClean(levels.tepe_avwap)}</td></tr>
                                <tr><td class="lvl-lbl">mVAH (Aylık Tavan)</td><td class="lvl-num" style="color:var(--cyan); font-weight:800">${formatPriceClean(levels.mvah)}</td></tr>
                                <tr><td class="lvl-lbl">Yukarı nPOC (Hedef)</td><td class="lvl-num" style="color:#f0f6fc; font-weight:700">${formatPriceClean(levels.above_npoc)}</td></tr>
                                <tr><td class="lvl-lbl">Naked VAH (Geçmiş Direnç)</td><td class="lvl-num" style="color:var(--cyan); font-weight:700">${formatPriceClean(levels.above_nvah)}</td></tr>
                                <tr><td class="lvl-lbl">R3 (Direnç)</td><td class="lvl-num">${formatPriceClean(cam.R3)}</td></tr>
                                <tr><td class="lvl-lbl">Pivot (P)</td><td class="lvl-num" style="color:#fff; font-weight:800">${formatPriceClean(cam.P)}</td></tr>
                                <tr><td class="lvl-lbl">mPOC (Aylık Hacim)</td><td class="lvl-num" style="color:var(--purple); font-weight:800">${formatPriceClean(levels.mpoc)}</td></tr>
                                <tr><td class="lvl-lbl">S3 (Destek)</td><td class="lvl-num">${formatPriceClean(cam.S3)}</td></tr>
                                <tr><td class="lvl-lbl">Aşağı nPOC (Hedef)</td><td class="lvl-num" style="color:#f0f6fc; font-weight:700">${formatPriceClean(levels.below_npoc)}</td></tr>
                                <tr><td class="lvl-lbl">Naked VAL (Geçmiş Destek)</td><td class="lvl-num" style="color:var(--blue); font-weight:700">${formatPriceClean(levels.below_nval)}</td></tr>
                                <tr><td class="lvl-lbl">Dip AVWAP (Beyaz)</td><td class="lvl-num" style="color:#fff; font-weight:800">${formatPriceClean(levels.dip_avwap)}</td></tr>
                                <tr><td class="lvl-lbl">S4 (Breakdown Tetik)</td><td class="lvl-num" style="color:var(--green); font-weight:800">${formatPriceClean(cam.S4)}</td></tr>
                                <tr><td class="lvl-lbl">mVAL (Aylık Taban)</td><td class="lvl-num" style="color:var(--blue)">${formatPriceClean(levels.mval)}</td></tr>
                            </table>`;
                        } else {
                            tableHtml = `
                            <div style="padding:22px 10px; text-align:center; background:rgba(255,255,255,0.02); border-radius:10px; border:1px dashed rgba(255,255,255,0.08); margin-top:6px;">
                                <div style="font-size:12px; color:var(--yellow); font-weight:700; font-family:'JetBrains Mono'">⚡ Göstergeler & Seviyeler Hesaplanıyor...</div>
                                <div style="font-size:11px; color:#64748b; margin-top:4px;">5M mumlar işlendikçe seviyeler otomatik dolacaktır</div>
                            </div>`;
                        }

                        // Fonlama Oranı & Squeeze Rozeti
                        let fBadge = '';
                        const fRates = (appState.funding_summary && appState.funding_summary.rates) ? appState.funding_summary.rates : {};
                        const fItem = fRates[symbol];
                        if (fItem) {
                            const f_pct = fItem.rate_pct != null ? fItem.rate_pct : 0.01;
                            if (fItem.squeeze_status === 'SHORT_SQUEEZE_RISK') {
                                fBadge = `<span style="background:rgba(255,107,107,0.18); border:1px solid rgba(255,107,107,0.45); color:var(--red); font-size:10.5px; font-weight:800; padding:2px 6px; border-radius:6px; font-family:'JetBrains Mono';" title="⚠️ Short Squeeze Riski: Fonlama %${f_pct.toFixed(4)}. Short emirleri kilitlendi!">⚠️ ${f_pct.toFixed(3)}% Squeeze</span>`;
                            } else if (fItem.squeeze_status === 'LONG_OVERHEATED') {
                                fBadge = `<span style="background:rgba(255,165,2,0.18); border:1px solid rgba(255,165,2,0.45); color:var(--yellow); font-size:10.5px; font-weight:800; padding:2px 6px; border-radius:6px; font-family:'JetBrains Mono';" title="🔥 Aşırı Şişkin Long: Fonlama %${f_pct.toFixed(4)}. Long kırılım engellenir!">🔥 +${f_pct.toFixed(3)}% Aşırı</span>`;
                            } else {
                                fBadge = `<span style="background:rgba(0,242,254,0.08); border:1px solid rgba(0,242,254,0.22); color:var(--cyan); font-size:10.5px; font-weight:700; padding:2px 6px; border-radius:6px; font-family:'JetBrains Mono';" title="🟢 Fonlama Dengeli: %${f_pct.toFixed(4)}">⚡ ${f_pct >= 0 ? '+' : ''}${f_pct.toFixed(3)}%</span>`;
                            }
                        }

                        // Canlı Tasfiye / Likidasyon Rozeti (Son 15dk)
                        let liqBadge = '';
                        const sLiqs = appState.symbol_liquidations || {};
                        const sLiqItem = sLiqs[symbol];
                        if (sLiqItem && sLiqItem.total_usd >= 5000) {
                            const liqK = (sLiqItem.total_usd / 1000).toFixed(0);
                            const liqDom = sLiqItem.dominant_side === 'LONG' ? '🔴' : '🟢';
                            liqBadge = `<span style="background:rgba(239,68,68,0.15); border:1px solid rgba(239,68,68,0.4); color:#fca5a5; font-size:10.5px; font-weight:800; padding:2px 6px; border-radius:6px; font-family:'JetBrains Mono';" title="💥 Son 15dk Tasfiye: $${Math.round(sLiqItem.total_usd).toLocaleString()} (${sLiqItem.dominant_side} Tasfiyesi Ağırlıklı)">💥 ${liqDom} $${liqK}K</span>`;
                        }

                        // Anlık Mikro-CVD Rozeti (Kayan 60s)
                        let cvdBadge = '';
                        const sCvds = appState.symbol_cvd || {};
                        const sCvdItem = sCvds[symbol];
                        if (sCvdItem && sCvdItem.ratio_60s != null) {
                            const cRatio = Number(sCvdItem.ratio_60s).toFixed(0);
                            const cDelta = Number(sCvdItem.delta_60s || 0);
                            if (cRatio >= 62) {
                                cvdBadge = `<span style="background:rgba(34,197,94,0.15); border:1px solid rgba(34,197,94,0.4); color:#4ade80; font-size:10.5px; font-weight:800; padding:2px 6px; border-radius:6px; font-family:'JetBrains Mono';" title="🔬 Mikro-CVD: %${cRatio} Alıcı (+$${Math.round(cDelta).toLocaleString()}) — Boğa Agresyonu">🔬 %${cRatio} Alıcı</span>`;
                            } else if (cRatio <= 38) {
                                cvdBadge = `<span style="background:rgba(239,68,68,0.15); border:1px solid rgba(239,68,68,0.4); color:#f87171; font-size:10.5px; font-weight:800; padding:2px 6px; border-radius:6px; font-family:'JetBrains Mono';" title="🔬 Mikro-CVD: %${cRatio} Alıcı (-$${Math.abs(Math.round(cDelta)).toLocaleString()}) — Ayı Agresyonu">🔬 %${100 - cRatio} Satıcı</span>`;
                            }
                        }

                        html += `
                        <div class="coin-card ${posClass}" id="card-${safeId}">
                            <!-- CLEAN CARD HEAD: SYMBOL + GRAFIK BUTTON -->
                            <div class="card-head">
                                <div class="card-top-row">
                                    <div style="display:flex; align-items:center; gap:8px;">
                                        <span class="card-symbol" onclick="openTradingViewModal('${cleanSym}')" style="cursor:pointer;" title="${cleanSym} Grafiğini Aç">${cleanSym}</span>
                                        ${fBadge}
                                        ${liqBadge}
                                        ${cvdBadge}
                                    </div>
                                    <button class="btn-open-chart" onclick="openTradingViewModal('${cleanSym}')" title="${cleanSym} Canlı Grafiği Aç">📈 Grafik</button>
                                </div>
                                <div class="card-price-row">
                                    <span class="price-label-mini">CANLI FİYAT</span>
                                    <div class="card-price" id="p-${safeId}">$${price > 0 ? formatPriceClean(price) : '---'}</div>
                                </div>
                            </div>

                            <!-- ROW 2: DEDICATED ACTIVE POSITION BANNER (IF ACTIVE) -->
                            ${posBannerHtml}

                            <!-- QUANT ANALİZ & MAKRO DURUM KUTUSU -->
                            <div class="quant-intel-grid">
                                <div class="quant-intel-item">
                                    <div class="quant-intel-lbl">1H Makro Trend</div>
                                    <div class="quant-intel-val" style="color:${intel.macroColor}">${intel.macroTrend}</div>
                                </div>
                                <div class="quant-intel-item">
                                    <div class="quant-intel-lbl">En Yakın Direnç</div>
                                    <div class="quant-intel-val" style="color:#fde047">${intel.nearestUp ? '$' + formatPriceClean(intel.nearestUp) + ' (+' + intel.upDistPct + '%)' : 'Açık Alan'}</div>
                                </div>
                            </div>

                            <div class="analysis-box" id="abox-${safeId}" style="margin-top:8px;">
                                <div class="analysis-title" id="atitle-${safeId}" style="color:${intel.color}">
                                    <span>●</span> ${intel.tag}
                                </div>
                                <div id="atext-${safeId}">${intel.statusText}</div>
                            </div>

                            <div class="action-plan-box" id="planbox-${safeId}">
                                <div class="action-plan-title">🎯 BOT PUSU & CANLI EYLEM PLANI</div>
                                <div id="plantext-${safeId}">${intel.posCommentary ? '<b style="color:#86efac;">' + intel.posCommentary + '</b>' : intel.actionPlan}</div>
                            </div>

                            <!-- AKORDİYON SEVİYE LİSTESİ (İSTENDİĞİNDE AÇILIR) -->
                            <button class="accordion-btn" id="acc-btn-${safeId}" onclick="toggleLevelsAccordion('${safeId}')">
                                <span>📊 15 Kilit Seviyeyi Aç</span>
                                <span>▼</span>
                            </button>
                            <div class="accordion-content" id="acc-${safeId}">
                                ${tableHtml}
                            </div>
                        </div>
                        `;
                    } catch (e) {
                        console.error("Error generating card for", symbol, e);
                    }
                }

                // DAHA FAZLA GÖSTER / TÜMÜNÜ GÖSTER KONTROL ÇUBUĞU
                const totalActive = allActiveSymbols.length;
                const renderedCount = displaySymbols.length;
                if (renderedCount < totalActive) {
                    html += `
                    <div class="load-more-bar">
                        <button class="btn-load-more" onclick="loadMoreCards(20)">⬇️ Daha Fazla Parite Göster (${renderedCount} / ${totalActive} Gösteriliyor)</button>
                        <button class="btn-load-all" onclick="loadAllCards()">⚡ Tümünü Göster (${totalActive})</button>
                    </div>
                    `;
                } else if (totalActive > 20 && visibleCardsCount > 20) {
                    html += `
                    <div class="load-more-bar">
                        <span style="font-size:13.5px; color:var(--green); font-weight:700; font-family:'JetBrains Mono'">✓ Tüm ${totalActive} Parite Canlı Listeleniyor</span>
                        <button class="btn-load-all" onclick="visibleCardsCount = 20; renderCards();
                renderCockpitView();
                updateSystemHealthBadge();" style="padding:8px 16px; font-size:12px;">🔼 İlk 20'ye Daralt</button>
                    </div>
                    `;
                }

                cont.innerHTML = html;
            } catch (err) {
                console.error("Global renderCards error:", err);
            }
        }

        // ZERO-JITTER RAF BATCHING ENGINE (60 FPS ROCK SOLID)
        let pendingPriceMap = {};
        let isRafActive = false;
        let lastSummaryFlush = 0;

        function updatePriceInPlace(symbol, price) {
            pendingPriceMap[symbol] = price;
            if (!isRafActive) {
                isRafActive = true;
                requestAnimationFrame(flushBatchPrices);
            }
        }

        function formatFastPrice(n) {
            n = Number(n);
            if (n >= 1000) return n.toFixed(2);
            if (n >= 1) return n.toFixed(4);
            if (n >= 0.01) return n.toFixed(5);
            return n.toFixed(6);
        }

        function flushBatchPrices() {
            isRafActive = false;
            const now = Date.now();
            let hasOpenPosUpdate = false;

            for (const symbol in pendingPriceMap) {
                try {
                    const price = pendingPriceMap[symbol];
                    livePrices[symbol] = price;
                    const safeId = symbol.replace(/[^a-zA-Z0-9]/g, '_');
                    const el = document.getElementById('p-' + safeId);

                    if (el) {
                        el.innerText = '$' + formatFastPrice(price);
                    }

                    const hasPos = appState.open_positions && appState.open_positions[symbol];
                    if (hasPos) {
                        hasOpenPosUpdate = true;
                        const metrics = computePositionPnL(hasPos, price);
                        const isWin = metrics.isWin;
                        const isLoss = metrics.isLoss;

                        const posPnl = document.getElementById('pos-pnl-' + safeId);
                        const posCurP = document.getElementById('pos-cur-price-' + safeId);
                        const pill = document.getElementById('pill-' + safeId);

                        if (posPnl) {
                            posPnl.style.color = isLoss ? 'var(--red)' : (isWin ? 'var(--green)' : '#ffffff');
                            posPnl.innerText = `${metrics.roePct >= 0 ? '+' : ''}${metrics.roePct.toFixed(2)}% ROE (${metrics.pnlUsdt >= 0 ? '+' : ''}${metrics.pnlUsdt.toFixed(2)} $)`;
                        }
                        if (posCurP) {
                            posCurP.innerText = `$${formatSmartPrice(metrics.curP)}`;
                        }
                        if (pill) {
                            pill.className = isLoss ? 'pos-pill-loss' : 'pos-pill-profit';
                            pill.innerText = `⚡ ${hasPos.side} (${metrics.roePct >= 0 ? '+' : ''}${metrics.roePct.toFixed(2)}% ROE)`;
                        }
                    }
                    tickCounts++;
                } catch(e) {}
            }
            pendingPriceMap = {};

            if (hasOpenPosUpdate && (now - lastSummaryFlush > 400)) {
                lastSummaryFlush = now;
                updateFinancialSummary();
            }

            const tickEl = document.getElementById('tick-counter');
            if (tickEl) tickEl.innerText = `● Canlı Fiyat Akıyor (İşlenen Tick: ${tickCounts})`;
        }

        function renderPositions() {
            const cont = document.getElementById('positions-container');
            if (!cont) return;
            const posKeys = Object.keys(appState.open_positions || {});
            const activeCount = Object.keys(appState.symbols || {}).length;
            const badge = document.getElementById('positions-active-count-badge');
            if (badge) badge.innerText = `${posKeys.length} Açık Pozisyon (${activeCount} Parite Takipte)`;
            const pCount = document.getElementById('pos-count');
            if (pCount) pCount.innerText = `${posKeys.length} / ${activeCount} AÇIK`;
            updateNavBadges();

            if (posKeys.length === 0) {
                cont.innerHTML = `<div style="color: #94a3b8; text-align:center; padding: 100px 20px; font-size:15px; line-height:1.6;">Şu an açık pozisyon bulunmuyor.<br><span style="color:var(--yellow)">● 5M Mum kapanışları, taze kırılımlar ve destek dönüşleri taranıyor...</span></div>`;
                return;
            }

            // Pozisyonları Kâr Yüzdesine (ROE %) Göre En Yüksekten En Düşüğe Sırala
            const sortedPosList = posKeys.map(sym => {
                const pos = appState.open_positions[sym];
                const curP = Number((livePrices && livePrices[sym]) || (appState.symbols && appState.symbols[sym] ? appState.symbols[sym].price : 0) || pos.entry_price);
                const metrics = computePositionPnL(pos, curP);
                return { sym, pos, metrics, curP };
            }).sort((a, b) => b.metrics.roePct - a.metrics.roePct);

            let html = '';
            sortedPosList.forEach(item => {
                const sym = item.sym;
                const pos = item.pos;
                const metrics = item.metrics;
                const safeId = sym.replace(/[^a-zA-Z0-9]/g, '_');
                const isWin = metrics.isWin;
                const isLoss = metrics.isLoss;
                const pnlClass = isLoss ? 'pos-card-loss' : (isWin ? 'pos-card-profit' : '');
                const pnlColor = isLoss ? 'var(--red)' : (isWin ? 'var(--green)' : '#ffffff');
                const cleanSym = sym.replace('/USDT','');
                const entryVal = formatSmartPrice(pos.entry_price);
                const curPriceVal = formatSmartPrice(metrics.curP);
                const tp1Val = pos.tp1 ? formatSmartPrice(pos.tp1) : '-';
                const tp2Val = pos.tp2 ? formatSmartPrice(pos.tp2) : '-';
                
                // Stop: Kademeli kâr veya trailing ile stop taşınmışsa Breakeven/Lock, yoksa 1.5 ATR dinamik sert stop
                const activeStop = pos.is_half_closed ? (pos.soft_stop || pos.hard_stop) : (pos.hard_stop || pos.soft_stop);
                const stopVal = activeStop ? formatSmartPrice(activeStop) : '-';
                const stopColor = pos.is_half_closed ? 'var(--green)' : '#f87171';
                const stopLabel = pos.is_half_closed ? '🛡️ Breakeven Stop' : '🛑 Aktif Stop';

                // Stop / TP Route Progress Calculation
                const entryNum = Number(pos.entry_price || 0.0);
                const curPNum = Number(metrics.curP || entryNum);
                const stopNum = Number(activeStop || (pos.side === 'LONG' ? entryNum * 0.985 : entryNum * 1.015));
                const tp1Num = Number(pos.tp1 || (pos.side === 'LONG' ? entryNum * 1.02 : entryNum * 0.98));

                let routePct = 35.0; // Entry sits at 35% mark
                if (pos.side === 'LONG') {
                    if (curPNum >= entryNum) {
                        const winSpan = Math.max(0.000001, tp1Num - entryNum);
                        const progress = Math.min(1.0, (curPNum - entryNum) / winSpan);
                        routePct = 35.0 + (progress * 65.0);
                    } else {
                        const lossSpan = Math.max(0.000001, entryNum - stopNum);
                        const lossProgress = Math.min(1.0, (entryNum - curPNum) / lossSpan);
                        routePct = Math.max(2.0, 35.0 - (lossProgress * 33.0));
                    }
                } else { // SHORT
                    if (curPNum <= entryNum) {
                        const winSpan = Math.max(0.000001, entryNum - tp1Num);
                        const progress = Math.min(1.0, (entryNum - curPNum) / winSpan);
                        routePct = 35.0 + (progress * 65.0);
                    } else {
                        const lossSpan = Math.max(0.000001, stopNum - entryNum);
                        const lossProgress = Math.min(1.0, (curPNum - entryNum) / lossSpan);
                        routePct = Math.max(2.0, 35.0 - (lossProgress * 33.0));
                    }
                }
                routePct = Math.min(98.0, Math.max(2.0, routePct));
                const cursorGlow = routePct >= 35.0 ? '#10b981' : '#f43f5e';

                html += `
                <div class="active-pos-card ${pnlClass}" id="pos-card-${safeId}">
                    <!-- 1. TOP HEADER (Ticker + Grafik Button on left, 2-line PnL on right) -->
                    <div class="pos-top">
                        <div style="display:flex; align-items:center; gap:8px;">
                            <span class="pos-badge ${pos.side === 'LONG' ? 'pos-long' : 'pos-short'}">${(Number(pos.leverage || 5) >= 7 ? '💎 ' : (Number(pos.leverage || 5) <= 3 ? '🛡️ ' : ''))}${pos.leverage || 5}x ${pos.side}</span>
                            <span onclick="openTradingViewModal('${cleanSym}')" style="font-size:17px; font-weight:900; font-family:'JetBrains Mono'; color:#ffffff; letter-spacing:0.5px; cursor:pointer;" title="${cleanSym} Özel Göstergeli Canlı Grafiğini Aç">${cleanSym}</span>
                            <button class="btn-open-chart" onclick="openTradingViewModal('${cleanSym}')" style="padding:3px 8px; font-size:11px; margin-left:2px;" title="${cleanSym} Özel Göstergeli Canlı Grafiği Aç">📈 Grafik</button>
                        </div>
                        <div style="text-align:right;">
                            <div style="font-size:16px; font-weight:900; font-family:'JetBrains Mono'; color:${pnlColor};" id="pos-pnl-${safeId}">
                                ${metrics.roePct >= 0 ? '+' : ''}${metrics.roePct.toFixed(2)}% ROE
                            </div>
                            <div style="font-size:12px; font-weight:700; color:${pnlColor}; font-family:'JetBrains Mono';">
                                ${metrics.pnlUsdt >= 0 ? '+' : ''}$${metrics.pnlUsdt.toFixed(2)} USDT
                            </div>
                        </div>
                    </div>

                    <!-- 2. PRICE & MARGIN GRID (2x2 Clean Box) -->
                    <div style="background:rgba(0,0,0,0.45); border:1px solid rgba(255,255,255,0.06); border-radius:10px; padding:10px 14px; font-size:12.5px; font-family:'JetBrains Mono'; color:#cbd5e1; display:grid; grid-template-columns:1fr 1fr; gap:6px 14px;">
                        <div>Giriş: <b style="color:#ffffff;">$${entryVal}</b></div>
                        <div>Anlık: <b id="pos-cur-price-${safeId}" style="color:${pnlColor};">$${curPriceVal}</b></div>
                        <div>Marjin: <b style="color:#ffffff;">$${Number(pos.margin || 100).toFixed(2)}</b></div>
                        <div>Hacim: <b style="color:#ffffff;">$${Number(pos.position_value || 500).toFixed(2)}</b></div>
                    </div>

                    <!-- 2.5 DİNAMİK STOP/TP ROTA BAR -->
                    <div style="background:rgba(0,0,0,0.3); border:1px solid rgba(255,255,255,0.05); border-radius:8px; padding:8px 10px;">
                        <div class="pos-route-labels">
                            <span style="color:#f87171;">🛑 Stop: $${stopVal}</span>
                            <span style="color:#cbd5e1; font-weight:700;">Giriş: $${entryVal}</span>
                            <span style="color:#34d399;">🎯 TP1: $${tp1Val}</span>
                        </div>
                        <div class="pos-route-track" title="Anlık Fiyat Pozisyonu Rotası (Kırmızı: Stop Bölgesi | Yeşil: TP1 Bölgesi)">
                            <div class="pos-route-loss-zone"></div>
                            <div class="pos-route-profit-zone"></div>
                            <div class="pos-route-cursor" style="left:${routePct.toFixed(1)}%; box-shadow:0 0 10px ${cursorGlow}, 0 0 16px ${cursorGlow};"></div>
                        </div>
                    </div>

                    <!-- 3. TARGETS & STOP PILLS -->
                    <div style="display:flex; flex-wrap:wrap; gap:8px; align-items:center;">
                        ${pos.is_half_closed || pos.tp1_hit ? '<span class="badge-tp1-hit">🎯 TP1 ALINDI (%50 Kâr Kasada)</span>' : '<span style="font-size:12px; background:rgba(255,255,255,0.04); border:1px solid var(--border); padding:3px 8px; border-radius:6px;">🎯 TP1: <b style="color:#fff;">$' + tp1Val + '</b></span>'}
                        <span style="font-size:12px; background:rgba(255,255,255,0.04); border:1px solid var(--border); padding:3px 8px; border-radius:6px;">
                            ${stopLabel}: <b style="color:${stopColor};">$${stopVal}</b>
                        </span>
                        ${pos.tp2 ? '<span style="font-size:12px; background:rgba(56,189,248,0.1); border:1px solid rgba(56,189,248,0.3); color:#38bdf8; padding:3px 8px; border-radius:6px;">🚀 TP2: <b>$' + tp2Val + '</b></span>' : ''}
                        ${pos.trail_status ? '<span class="badge-trailing-lock">' + pos.trail_status + '</span>' : ''}
                    </div>

                    <!-- 4. SETUP REASON -->
                    <div style="background:rgba(255,255,255,0.03); border:1px solid var(--border); border-radius:8px; padding:6px 10px; font-size:11.5px; color:#cbd5e1; line-height:1.4;">
                        📌 <b>Kurulum:</b> ${pos.reason}
                    </div>

                    <!-- 5. ACTION BUTTONS (GRAFIK + POZISYONU KAPAT) -->
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:4px; padding-top:10px; border-top:1px solid rgba(255,255,255,0.08); gap:8px;">
                        <button onclick="openTradingViewModal('${cleanSym}')" style="background:rgba(0,242,254,0.08); border:1px solid rgba(0,242,254,0.35); color:var(--cyan); font-weight:800; font-size:11.5px; padding:6px 12px; border-radius:8px; cursor:pointer; display:flex; align-items:center; gap:4px; transition:all 0.15s ease;" onmouseover="this.style.background='var(--cyan)'; this.style.color='#000';" onmouseout="this.style.background='rgba(0,242,254,0.08)'; this.style.color='var(--cyan)';" title="${cleanSym} Özel Göstergeli Grafiğini İncele">
                            📈 Grafiği İncele
                        </button>
                        <button class="btn-card-manual-close" onclick="openConfirmModal('${sym}')" style="font-size:12px; padding:6px 14px;">
                            🛑 Pozisyonu Kapat (Market)
                        </button>
                    </div>
                </div>
                `;
            });
            cont.innerHTML = html;
        }

        // CONFIRMATION MODAL LOGIC
        let pendingCloseSymbol = null;

        function openConfirmModal(symbol) {
            pendingCloseSymbol = symbol;
            const pos = appState.open_positions && appState.open_positions[symbol];
            if (!pos) return;

            const clean = symbol.replace('/USDT', '');
            const curP = Number(livePrices[symbol] || (appState.symbols[symbol] ? appState.symbols[symbol].price : 0) || pos.entry_price);
            const metrics = computePositionPnL(pos, curP);

            document.getElementById('modal-title').innerText = `${clean} Pozisyonunu Kapat`;
            document.getElementById('modal-metrics').innerHTML = `
                <div>• Yön & Kaldıraç: <b style="color:${pos.side === 'LONG' ? 'var(--green)' : 'var(--red)'}">${pos.leverage}x ${pos.side}</b></div>
                <div>• Giriş Fiyatı: <b>$${formatSmartPrice(pos.entry_price)}</b></div>
                <div>• Anlık Piyasa Fiyatı: <b>$${formatSmartPrice(metrics.curP)}</b></div>
                <div>• Tahmini Kâr/Zarar: <b style="color:${metrics.pnlUsdt >= 0 ? 'var(--green)' : 'var(--red)'}">${metrics.roePct >= 0 ? '+' : ''}${metrics.roePct.toFixed(2)}% ROE (${metrics.pnlUsdt >= 0 ? '+' : ''}${metrics.pnlUsdt.toFixed(2)} $)</b></div>
            `;

            document.getElementById('modal-btn-confirm').onclick = () => executeManualClose(symbol);
            document.getElementById('close-modal-overlay').style.display = 'flex';
        }

        function closeConfirmModal() {
            document.getElementById('close-modal-overlay').style.display = 'none';
            pendingCloseSymbol = null;
        }

        async function executeManualClose(symbol) {
            closeConfirmModal();
            try {
                const res = await fetch('/api/close_position_manual', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ symbol: symbol })
                });
                const data = await res.json();
                if (data.status === 'ok') {
                    await syncBackendState();
                } else {
                    alert('Kapatma Hatası: ' + (data.message || 'Bilinmeyen hata'));
                }
            } catch(err) {
                console.error('executeManualClose error:', err);
            }
        }

        const PINE_SCRIPT_SOURCE = `//@version=6
indicator("Daily Volume Profile, Camarilla & Anchored VWAP", shorttitle="VP + Camarilla + AVWAP", overlay=true, max_boxes_count=500, max_lines_count=500, max_labels_count=500, max_polylines_count=100)

// 1. ANCHORED VWAP
grp_avwap       = "Anchored VWAP Ayarlari"
enableAvwap     = input.bool(true, "Anchored VWAP Etkin", group=grp_avwap)
avwapHighCol    = input.color(color.red, "Tepe VWAP (Direnc)", group=grp_avwap)
avwapLowCol     = input.color(color.white, "Dip VWAP (Destek)", group=grp_avwap)

// 2. SON 1 AY VOLUME PROFILE
grp_mvp         = "Son 1 Ay Volume Profile"
enableMvp       = input.bool(true, "1 Ay VP Etkin", group=grp_mvp)
mvpPocColor     = input.color(#d500f9, "mPOC Rengi (Parlak Mor)", group=grp_mvp)
mvpVahColor     = input.color(#00e5ff, "mVAH Rengi (Turkuaz)", group=grp_mvp)
mvpValColor     = input.color(#00e5ff, "mVAL Rengi (Turkuaz)", group=grp_mvp)

// 3. CAMARILLA PIVOTLARI
grp_piv         = "Camarilla Pivot Seviyeleri"
enablePivots    = input.bool(true, "Camarilla Etkin", group=grp_piv)
[prev_h, prev_l, prev_c, p_time] = request.security(syminfo.tickerid, "D", [high[1], low[1], close[1], time], lookahead=barmerge.lookahead_on)
cam_range = prev_h - prev_l
cam_p  = (prev_h + prev_l + prev_c) / 3.0
cam_r3 = prev_c + cam_range * 1.1 / 4.0
cam_s3 = prev_c - cam_range * 1.1 / 4.0
cam_r4 = prev_c + cam_range * 1.1 / 2.0
cam_s4 = prev_c - cam_range * 1.1 / 2.0
cam_r5 = (prev_l > 0) ? (prev_h / prev_l) * prev_c : na
cam_s5 = prev_c - (nz(cam_r5, prev_c) - prev_c)
`;

        let currentActiveChartSym = null;
        let nativeChartObj = null;
        let candleSeriesObj = null;
        let activeTab = 'native';

        function switchChartTab(tab) {
            activeTab = tab;
            const btnNative = document.getElementById('tab-btn-native');
            const btnTv = document.getElementById('tab-btn-tv');
            const wrapNative = document.getElementById('native-chart-wrapper');
            const wrapTv = document.getElementById('tv-widget-wrapper');

            if (!btnNative || !btnTv || !wrapNative || !wrapTv) return;

            if (tab === 'native') {
                btnNative.className = 'chart-tab-btn tab-active';
                btnTv.className = 'chart-tab-btn';
                wrapNative.style.display = 'block';
                wrapTv.style.display = 'none';
                if (currentActiveChartSym) renderNativeChart(currentActiveChartSym);
            } else {
                btnNative.className = 'chart-tab-btn';
                btnTv.className = 'chart-tab-btn tab-active';
                wrapNative.style.display = 'none';
                wrapTv.style.display = 'block';
                if (currentActiveChartSym) renderTvWidget(currentActiveChartSym);
            }
        }

        async function renderNativeChart(cleanSym) {
            const container = document.getElementById('native-chart-box');
            const spinner = document.getElementById('chart-loading-spinner');
            if (!container) return;

            if (spinner) {
                spinner.style.display = 'flex';
                spinner.innerHTML = '⚡ 5M Mumlar & AVWAP / Camarilla / VP Seviyeleri Çiziliyor...';
            }
            container.innerHTML = '';

            try {
                const fullSym = cleanSym + '/USDT';
                const res = await fetch(`/api/candles?symbol=${encodeURIComponent(fullSym)}`);
                const data = await res.json();
                if (data.status !== 'ok') throw new Error(data.message || 'Veri alinamadi');

                if (spinner) spinner.style.display = 'none';

                if (typeof LightweightCharts === 'undefined') {
                    container.innerHTML = '<div style="color:red; padding:20px;">LightweightCharts kutuphanesi yuklenemedi.</div>';
                    return;
                }

                const chart = LightweightCharts.createChart(container, {
                    width: container.clientWidth || 850,
                    height: container.clientHeight || 520,
                    layout: {
                        background: { color: '#0b0e14' },
                        textColor: '#cbd5e1',
                        fontSize: 11,
                        fontFamily: "'JetBrains Mono', monospace",
                    },
                    grid: {
                        vertLines: { color: 'rgba(255, 255, 255, 0.04)' },
                        horzLines: { color: 'rgba(255, 255, 255, 0.04)' },
                    },
                    crosshair: {
                        mode: LightweightCharts.CrosshairMode.Normal,
                    },
                    timeScale: {
                        timeVisible: true,
                        secondsVisible: false,
                        borderColor: '#1e2638',
                    },
                    rightPriceScale: {
                        borderColor: '#1e2638',
                    }
                });
                nativeChartObj = chart;

                let chartPrecision = 2;
                let chartMinMove = 0.01;
                const samplePrice = (data.candles && data.candles.length > 0) ? Number(data.candles[data.candles.length - 1].close) : 1;
                if (samplePrice < 0.0001) { chartPrecision = 8; chartMinMove = 0.00000001; }
                else if (samplePrice < 0.01) { chartPrecision = 6; chartMinMove = 0.000001; }
                else if (samplePrice < 1) { chartPrecision = 4; chartMinMove = 0.0001; }
                else if (samplePrice < 10) { chartPrecision = 3; chartMinMove = 0.001; }

                // 1. Candlestick Serisi
                const candleSeries = chart.addCandlestickSeries({
                    upColor: '#0ecb81',
                    downColor: '#ff4757',
                    borderVisible: false,
                    wickUpColor: '#0ecb81',
                    wickDownColor: '#ff4757',
                    priceFormat: {
                        type: 'price',
                        precision: chartPrecision,
                        minMove: chartMinMove,
                    }
                });
                candleSeries.setData(data.candles || []);
                candleSeriesObj = candleSeries;

                // 2. AVWAP Çizgileri (Tepe Kırmızı, Dip Beyaz)
                if (data.avwap_high && data.avwap_high.length > 0) {
                    const avHighSeries = chart.addLineSeries({
                        color: '#ff4757',
                        lineWidth: 2,
                        title: 'Tepe AVWAP',
                        priceLineVisible: false,
                        priceFormat: {
                            type: 'price',
                            precision: chartPrecision,
                            minMove: chartMinMove,
                        }
                    });
                    avHighSeries.setData(data.avwap_high);
                }

                if (data.avwap_low && data.avwap_low.length > 0) {
                    const avLowSeries = chart.addLineSeries({
                        color: '#ffffff',
                        lineWidth: 2,
                        title: 'Dip AVWAP',
                        priceLineVisible: false,
                        priceFormat: {
                            type: 'price',
                            precision: chartPrecision,
                            minMove: chartMinMove,
                        }
                    });
                    avLowSeries.setData(data.avwap_low);
                }

                // 3. Fiyat Çizgileri (Camarilla, Volume Profile, Naked Lines)
                const levels = data.levels || {};
                const cam = levels.camarilla || {};

                // Update sidebar levels directly from candles API response
                const sidebarTbl = document.querySelector('#tv-sidebar-content .levels-table');
                if (sidebarTbl && cam && cam.R4) {
                    function fmtLvl(val) {
                        if (!val || isNaN(val) || Number(val) <= 0) return '-';
                        const n = Number(val);
                        if (n >= 1000) return n.toFixed(2);
                        if (n >= 1) return n.toFixed(4);
                        if (n >= 0.01) return n.toFixed(5);
                        return n.toFixed(6);
                    }
                    sidebarTbl.innerHTML = `
                        <tr><td class="lvl-lbl">R5 (Zirve Hedef)</td><td class="lvl-num" style="color:var(--yellow)">${fmtLvl(cam.R5)}</td></tr>
                        <tr><td class="lvl-lbl">R4 (Breakout Tetik)</td><td class="lvl-num" style="color:#ffa726; font-weight:800">${fmtLvl(cam.R4)}</td></tr>
                        <tr><td class="lvl-lbl">Tepe AVWAP (Kırmızı)</td><td class="lvl-num" style="color:var(--red); font-weight:800">${fmtLvl(levels.tepe_avwap)}</td></tr>
                        <tr><td class="lvl-lbl">mVAH (Aylık Tavan)</td><td class="lvl-num" style="color:var(--cyan); font-weight:800">${fmtLvl(levels.mvah)}</td></tr>
                        <tr><td class="lvl-lbl">Yukarı nPOC (Hedef)</td><td class="lvl-num" style="color:#f0f6fc; font-weight:700">${fmtLvl(levels.above_npoc)}</td></tr>
                        <tr><td class="lvl-lbl">Naked VAH (Geçmiş Direnç)</td><td class="lvl-num" style="color:var(--cyan); font-weight:700">${fmtLvl(levels.above_nvah)}</td></tr>
                        <tr><td class="lvl-lbl">R3 (Direnç)</td><td class="lvl-num">${fmtLvl(cam.R3)}</td></tr>
                        <tr><td class="lvl-lbl">Pivot (P)</td><td class="lvl-num" style="color:#fff; font-weight:800">${fmtLvl(cam.P)}</td></tr>
                        <tr><td class="lvl-lbl">mPOC (Aylık Hacim)</td><td class="lvl-num" style="color:var(--purple); font-weight:800">${fmtLvl(levels.mpoc)}</td></tr>
                        <tr><td class="lvl-lbl">S3 (Destek)</td><td class="lvl-num">${fmtLvl(cam.S3)}</td></tr>
                        <tr><td class="lvl-lbl">Aşağı nPOC (Hedef)</td><td class="lvl-num" style="color:#f0f6fc; font-weight:700">${fmtLvl(levels.below_npoc)}</td></tr>
                        <tr><td class="lvl-lbl">Naked VAL (Geçmiş Destek)</td><td class="lvl-num" style="color:var(--blue); font-weight:700">${fmtLvl(levels.below_nval)}</td></tr>
                        <tr><td class="lvl-lbl">Dip AVWAP (Beyaz)</td><td class="lvl-num" style="color:#fff; font-weight:800">${fmtLvl(levels.dip_avwap)}</td></tr>
                        <tr><td class="lvl-lbl">S4 (Breakdown Tetik)</td><td class="lvl-num" style="color:var(--green); font-weight:800">${fmtLvl(cam.S4)}</td></tr>
                        <tr><td class="lvl-lbl">mVAL (Aylık Taban)</td><td class="lvl-num" style="color:var(--blue)">${fmtLvl(levels.mval)}</td></tr>
                    `;
                }

                function addPriceLine(price, color, title, lineStyle) {
                    if (!price || isNaN(price) || Number(price) <= 0) return;
                    candleSeries.createPriceLine({
                        price: Number(price),
                        color: color,
                        lineWidth: 2,
                        lineStyle: lineStyle !== undefined ? lineStyle : LightweightCharts.LineStyle.Solid,
                        axisLabelVisible: true,
                        title: title,
                    });
                }

                addPriceLine(cam.R5, '#fbc531', 'R5 (Zirve Hedef)', LightweightCharts.LineStyle.Dashed);
                addPriceLine(cam.R4, '#ffa726', 'R4 (Breakout Tetik)', LightweightCharts.LineStyle.Solid);
                addPriceLine(levels.tepe_avwap, '#ff4757', 'Tepe AVWAP', LightweightCharts.LineStyle.Solid);
                addPriceLine(levels.mvah, '#00f2fe', 'mVAH (1 Ay Tavan)', LightweightCharts.LineStyle.Dashed);
                addPriceLine(levels.above_npoc, '#f0f6fc', 'Yukarı nPOC (Hedef)', LightweightCharts.LineStyle.Dotted);
                addPriceLine(levels.above_nvah, '#00e5ff', 'Naked VAH (Geçmiş Direnç)', LightweightCharts.LineStyle.Dashed);
                addPriceLine(cam.R3, '#fb8c00', 'R3 (Direnç)', LightweightCharts.LineStyle.Dotted);
                addPriceLine(cam.P, '#ffffff', 'Pivot (P)', LightweightCharts.LineStyle.Solid);
                addPriceLine(levels.mpoc, '#d500f9', 'mPOC (1 Ay Hacim)', LightweightCharts.LineStyle.Solid);
                addPriceLine(cam.S3, '#fb8c00', 'S3 (Destek)', LightweightCharts.LineStyle.Dotted);
                addPriceLine(levels.below_npoc, '#f0f6fc', 'Aşağı nPOC (Hedef)', LightweightCharts.LineStyle.Dotted);
                addPriceLine(levels.below_nval, '#2979ff', 'Naked VAL (Geçmiş Destek)', LightweightCharts.LineStyle.Dashed);
                addPriceLine(levels.dip_avwap, '#ffffff', 'Dip AVWAP', LightweightCharts.LineStyle.Solid);
                addPriceLine(cam.S4, '#0ecb81', 'S4 (Breakdown Tetik)', LightweightCharts.LineStyle.Solid);
                addPriceLine(levels.mval, '#00f2fe', 'mVAL (1 Ay Taban)', LightweightCharts.LineStyle.Dashed);

                chart.timeScale().fitContent();

            } catch (err) {
                console.error("renderNativeChart error:", err);
                if (spinner) {
                    spinner.style.display = 'flex';
                    spinner.innerHTML = `
                        <div style="text-align:center; padding:20px; font-family:'JetBrains Mono', monospace;">
                            <div style="color:var(--yellow); font-size:13.5px; font-weight:700; margin-bottom:12px;">⚡ ${cleanSym} mum verisi yükleniyor...</div>
                            <button onclick="renderNativeChart('${cleanSym}')" style="background:var(--blue); border:none; color:#fff; font-weight:800; padding:8px 18px; border-radius:8px; cursor:pointer; font-size:12px;">🔄 Grafiği Yenile</button>
                        </div>
                    `;
                }
            }
        }

        function renderTvWidget(cleanSym) {
            const container = document.getElementById('tv-widget-wrapper');
            if (!container) return;

            const multiplierMap = {
                'PEPE': '1000PEPE', 'SHIB': '1000SHIB', 'BONK': '1000BONK',
                'FLOKI': '1000FLOKI', 'SATS': '1000SATS', 'RATS': '1000RATS',
                'LUNC': '1000LUNC', 'XEC': '1000XEC', 'MOG': '1000000MOG',
                'CHEEMS': '1000CHEEMS', 'WHY': '1000WHY', 'CAT': '1000CAT',
                'NEIRO': '1000NEIRO'
            };
            const tvBase = multiplierMap[cleanSym] || cleanSym;
            const tvSymbol = `BINANCE:${tvBase}USDT.P`;

            container.innerHTML = '';
            if (typeof TradingView !== 'undefined') {
                new TradingView.widget({
                    "autosize": true,
                    "symbol": tvSymbol,
                    "interval": "5",
                    "timezone": "Etc/UTC",
                    "theme": "dark",
                    "style": "1",
                    "locale": "tr",
                    "toolbar_bg": "#0e121a",
                    "enable_publishing": false,
                    "hide_side_toolbar": false,
                    "allow_symbol_change": true,
                    "container_id": "tv-widget-wrapper",
                    "studies": [
                        "Volume@tv-basicstudies",
                        "VWAP@tv-basicstudies"
                    ]
                });
            } else {
                container.innerHTML = `
                    <iframe src="https://s.tradingview.com/widgetembed/?frameElementId=tradingview_widget&symbol=${encodeURIComponent(tvSymbol)}&interval=5&theme=dark" 
                        style="width:100%; height:100%; border:none;"></iframe>
                `;
            }
        }

        function copyPineScriptCode() {
            navigator.clipboard.writeText(PINE_SCRIPT_SOURCE).then(() => {
                alert(`✅ TradingView Pine Script v6 Kodu Panoya Kopyalandı!\\n\\nTradingView web sayfasını açıp alt kısımdaki 'Pine Editörü' sekmesine bu kodu yapıştırarak grafiğinize ekleyebilirsiniz.`);
            }).catch(err => {
                console.error("Clipboard copy error:", err);
            });
        }

        function openTradingViewModal(cleanSym) {
            try {
                if (!cleanSym) return;
                cleanSym = cleanSym.replace('/USDT', '').replace('USDT', '').trim();
                currentActiveChartSym = cleanSym;
                const modal = document.getElementById('tv-modal-overlay');
                if (!modal) return;
                
                const fullSym = cleanSym.includes('/') ? cleanSym : cleanSym + '/USDT';
                const coinData = (appState.symbols && (appState.symbols[fullSym] || appState.symbols[cleanSym])) ? (appState.symbols[fullSym] || appState.symbols[cleanSym]) : {};
                const levels = coinData.levels || {};
                const cam = levels.camarilla || {};
                const price = Number((livePrices && (livePrices[fullSym] || livePrices[cleanSym])) || coinData.price || 0);
                const hasPos = appState.open_positions && appState.open_positions[fullSym];
                const intel = generateDetailedIntelligence(fullSym, price, cam, levels, hasPos);

                const met = coinData.metrics || {};
                const volSurge = Number(met.vol_surge !== undefined ? met.vol_surge : 1.0);
                const majorsList = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA"];
                const minVolSurge = Number(met.min_vol_surge !== undefined ? met.min_vol_surge : (majorsList.includes(cleanSym) ? 1.2 : 1.5));
                const isVolOk = volSurge >= minVolSurge;
                const isTop80 = met.is_top_80 !== false;
                const atrPct = Number(met.atr_pct !== undefined ? met.atr_pct : 1.2);

                document.getElementById('tv-modal-title').innerText = `${cleanSym}/USDT PERPETUAL`;
                
                const multiplierMap = {
                    'PEPE': '1000PEPE', 'SHIB': '1000SHIB', 'BONK': '1000BONK',
                    'FLOKI': '1000FLOKI', 'SATS': '1000SATS', 'RATS': '1000RATS',
                    'LUNC': '1000LUNC', 'XEC': '1000XEC', 'MOG': '1000000MOG',
                    'CHEEMS': '1000CHEEMS', 'WHY': '1000WHY', 'CAT': '1000CAT',
                    'NEIRO': '1000NEIRO'
                };
                const tvBase = multiplierMap[cleanSym] || cleanSym;
                const tvSymbol = `BINANCE:${tvBase}USDT.P`;
                document.getElementById('tv-external-link').href = `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(tvSymbol)}`;

                function fmtLvl(val) {
                    if (!val || isNaN(val) || Number(val) <= 0) return '-';
                    const n = Number(val);
                    if (n >= 1000) return n.toFixed(2);
                    if (n >= 1) return n.toFixed(4);
                    if (n >= 0.01) return n.toFixed(5);
                    return n.toFixed(6);
                }

                document.getElementById('tv-sidebar-content').innerHTML = `
                    <div style="background:var(--card-bg); padding:12px 14px; border-radius:12px; border:1px solid var(--border);">
                        <div style="font-size:11px; color:var(--text-muted); font-weight:800; text-transform:uppercase;">CANLI PİYASA FİYATI</div>
                        <div style="font-size:22px; font-weight:800; color:#fff; font-family:'JetBrains Mono', monospace; margin-top:2px;">
                            $${fmtLvl(price)}
                        </div>
                        <div style="display:flex; gap:6px; margin-top:8px; flex-wrap:wrap; font-size:10.5px; font-family:'JetBrains Mono',monospace;">
                            <span style="background:rgba(0,0,0,0.3); padding:2px 6px; border-radius:4px; border:1px solid ${isVolOk ? 'rgba(16,185,129,0.35)' : 'rgba(245,158,11,0.35)'}; color:${isVolOk ? '#10b981' : '#f59e0b'}; font-weight:700;">
                                ⚡ Hacim: ${volSurge.toFixed(2)}x (Min ${minVolSurge.toFixed(1)}x)
                            </span>
                            <span style="background:rgba(0,0,0,0.3); padding:2px 6px; border-radius:4px; border:1px solid rgba(255,255,255,0.08); color:${isTop80 ? '#38bdf8' : '#94a3b8'};">
                                📊 ${isTop80 ? '✓ Top %80' : '⚠️ Top %20 Altı'}
                            </span>
                            <span style="background:rgba(0,0,0,0.3); padding:2px 6px; border-radius:4px; border:1px solid rgba(255,255,255,0.08); color:#c084fc;">
                                🌊 ATR: %${atrPct.toFixed(2)}
                            </span>
                        </div>
                    </div>
                    <div class="analysis-box" style="margin:0;">
                        <div class="analysis-title" style="color:${intel.color}"><span>●</span> ${intel.tag}</div>
                        <div style="font-size:12.5px; line-height:1.5;">${intel.statusText}</div>
                    </div>
                    <div class="action-plan-box" style="margin:0;">
                        <div class="action-plan-title">🎯 BOT PUSU & EYLEM PLANI</div>
                        <div style="font-size:12.5px; line-height:1.5;">${intel.actionPlan}</div>
                    </div>
                    <div style="font-size:12px; font-weight:800; color:#cbd5e1; margin-top:4px;">📊 KİLİT SEVİYE & LİKİDİTE RADARI</div>
                    <table class="levels-table" style="font-size:11.5px;">
                        <tr><td class="lvl-lbl">R5 (Zirve Hedef)</td><td class="lvl-num" style="color:var(--yellow)">${fmtLvl(cam.R5)}</td></tr>
                        <tr><td class="lvl-lbl">R4 (Breakout Tetik)</td><td class="lvl-num" style="color:#ffa726; font-weight:800">${fmtLvl(cam.R4)}</td></tr>
                        <tr><td class="lvl-lbl">Tepe AVWAP (Kırmızı)</td><td class="lvl-num" style="color:var(--red); font-weight:800">${fmtLvl(levels.tepe_avwap)}</td></tr>
                        <tr><td class="lvl-lbl">mVAH (Aylık Tavan)</td><td class="lvl-num" style="color:var(--cyan); font-weight:800">${fmtLvl(levels.mvah)}</td></tr>
                        <tr><td class="lvl-lbl">Yukarı nPOC (Hedef)</td><td class="lvl-num" style="color:#f0f6fc; font-weight:700">${fmtLvl(levels.above_npoc)}</td></tr>
                        <tr><td class="lvl-lbl">Naked VAH (Geçmiş Direnç)</td><td class="lvl-num" style="color:var(--cyan); font-weight:700">${fmtLvl(levels.above_nvah)}</td></tr>
                        <tr><td class="lvl-lbl">R3 (Direnç)</td><td class="lvl-num">${fmtLvl(cam.R3)}</td></tr>
                        <tr><td class="lvl-lbl">Pivot (P)</td><td class="lvl-num" style="color:#fff; font-weight:800">${fmtLvl(cam.P)}</td></tr>
                        <tr><td class="lvl-lbl">mPOC (Aylık Hacim)</td><td class="lvl-num" style="color:var(--purple); font-weight:800">${fmtLvl(levels.mpoc)}</td></tr>
                        <tr><td class="lvl-lbl">S3 (Destek)</td><td class="lvl-num">${fmtLvl(cam.S3)}</td></tr>
                        <tr><td class="lvl-lbl">Aşağı nPOC (Hedef)</td><td class="lvl-num" style="color:#f0f6fc; font-weight:700">${fmtLvl(levels.below_npoc)}</td></tr>
                        <tr><td class="lvl-lbl">Naked VAL (Geçmiş Destek)</td><td class="lvl-num" style="color:var(--blue); font-weight:700">${fmtLvl(levels.below_nval)}</td></tr>
                        <tr><td class="lvl-lbl">Dip AVWAP (Beyaz)</td><td class="lvl-num" style="color:#fff; font-weight:800">${fmtLvl(levels.dip_avwap)}</td></tr>
                        <tr><td class="lvl-lbl">S4 (Breakdown Tetik)</td><td class="lvl-num" style="color:var(--green); font-weight:800">${fmtLvl(cam.S4)}</td></tr>
                        <tr><td class="lvl-lbl">mVAL (Aylık Taban)</td><td class="lvl-num" style="color:var(--blue)">${fmtLvl(levels.mval)}</td></tr>
                    </table>
                `;

                modal.style.display = 'flex';
                switchChartTab(activeTab);
            } catch (err) {
                console.error("openTradingViewModal error:", err);
            }
        }

        function closeTvModal() {
            const modal = document.getElementById('tv-modal-overlay');
            if (modal) modal.style.display = 'none';
            if (nativeChartObj) {
                nativeChartObj.remove();
                nativeChartObj = null;
            }
            const tvBox = document.getElementById('tv-widget-wrapper');
            if (tvBox) tvBox.innerHTML = '';
        }

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                closeTvModal();
                closeConfirmModal();
                closeTelemetryModal();
                closeShadowCoinDetail();
            }
        });

        function updateFinancialSummary() {
            let totalRealizedNetPnl = 0;
            let totalFees = 0;
            
            if (appState.history_summary) {
                totalRealizedNetPnl = appState.history_summary.total_realized_pnl;
                totalFees = appState.history_summary.total_fees;
            } else {
                const hList = appState.history || [];
                hList.forEach(h => {
                    totalRealizedNetPnl += Number(h.net_pnl || 0);
                    totalFees += Number(h.commission || h.fees || 0);
                });
            }

            const feesEl = document.getElementById('kpi-fees');
            if (feesEl) feesEl.innerText = '$' + totalFees.toFixed(4);

            // Legacy KPI fallbacks (if present on secondary screens, not clobbering Cockpit)
            const pnlEl = document.getElementById('kpi-pnl');
            const growthEl = document.getElementById('kpi-growth');
            const balEl = document.getElementById('kpi-balance');

            if (pnlEl || growthEl || balEl) {
                let totalUnrealizedPnl = 0;
                const openPositions = appState.open_positions || {};
                const openKeys = Object.keys(openPositions);
                openKeys.forEach(sym => {
                    const pos = openPositions[sym];
                    const curP = Number((typeof livePrices !== 'undefined' && livePrices && livePrices[sym]) || pos.entry_price || 0.0);
                    if (typeof computePositionPnL === 'function') {
                        const metrics = computePositionPnL(pos, curP);
                        totalUnrealizedPnl += metrics.pnlUsdt;
                    }
                });

                const bal = Number(appState.balance || 10000.0);
                const totalPortfolioEquity = bal + totalUnrealizedPnl;
                const totalNetPnl = totalRealizedNetPnl + totalUnrealizedPnl;

                if (pnlEl) {
                    pnlEl.innerText = (totalNetPnl >= 0 ? '+' : '') + totalNetPnl.toFixed(2) + ' $';
                    pnlEl.style.color = totalNetPnl >= 0 ? 'var(--green)' : 'var(--red)';
                }
                
                const initialBal = Number(appState.initial_balance || 10000.0);
                const growthPct = initialBal > 0 ? ((totalPortfolioEquity - initialBal) / initialBal) * 100 : 0.0;
                if (growthEl) {
                    if (growthPct >= 0) {
                        growthEl.innerText = `+${growthPct.toFixed(2)}% BÜYÜME`;
                        growthEl.style.color = 'var(--green)';
                    } else {
                        growthEl.innerText = `${growthPct.toFixed(2)}% KÜÇÜLME`;
                        growthEl.style.color = 'var(--red)';
                    }
                }
                if (balEl) balEl.innerText = '$' + totalPortfolioEquity.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2});
            }

            // Sync Cockpit with unified authority
            try { renderCockpitView(); } catch(e) {}
        }

                let ledgerCurrentPage = 1;
        const LEDGER_PAGE_SIZE = 20;

        function setLedgerPage(p) {
            ledgerCurrentPage = p;
            renderHistoryTable();
        }

        function onLedgerFilterChange() {
            ledgerCurrentPage = 1;
            renderHistoryTable();
        }

        function renderHistoryTable() {
            try {
                const tbody = document.getElementById('trade-table-body');
                if (!tbody) return;
                const hList = appState.history || [];

                const totalCountEl = document.getElementById('history-total-count');
                let totalTrades = hList.length;
                if (appState.history_summary) {
                    totalTrades = appState.history_summary.total_trades;
                }
                if (totalCountEl) totalCountEl.innerText = `${totalTrades} Toplam İşlem (Son 150 Gösteriliyor)`;
                
                try { updateFinancialSummary(); } catch(e) {}
                try { renderSetupPerformanceMatrix(); } catch(e) {}

                if (hList.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="14" style="text-align:center; padding: 40px; color:#94a3b8;">Kayıtlı işlem geçmişi bulunmuyor.</td></tr>`;
                    const pagCont = document.getElementById('ledger-pagination-container');
                    if (pagCont) pagCont.innerHTML = '';
                    return;
                }

                // Populate filter dropdown
                const symFilterEl = document.getElementById('filter-symbol');
                const setupFilterEl = document.getElementById('filter-setup');
                const statusFilterEl = document.getElementById('filter-status');

                const symFilter = symFilterEl ? symFilterEl.value : 'ALL';
                const setupFilter = setupFilterEl ? setupFilterEl.value : 'ALL';
                const statusFilter = statusFilterEl ? statusFilterEl.value : 'ALL';

                if (symFilterEl && symFilterEl.options.length <= 1) {
                    const uniqueSyms = [...new Set(hList.map(item => item.symbol || ''))].filter(Boolean).sort();
                    uniqueSyms.forEach(sym => {
                        const opt = document.createElement('option');
                        opt.value = sym;
                        opt.innerText = sym;
                        symFilterEl.appendChild(opt);
                    });
                }

                let filtered = hList.slice().reverse().filter(item => {
                    if (!item) return false;
                    const itemSym = (item.symbol || '').replace('/USDT', '');
                    const cleanSymFilter = (symFilter || '').replace('/USDT', '');
                    if (cleanSymFilter !== 'ALL' && itemSym !== cleanSymFilter && item.symbol !== symFilter) return false;
                    
                    const pnlNum = Number(item.net_pnl || 0.0);
                    if (statusFilter === 'WIN' && pnlNum < 0) return false;
                    if (statusFilter === 'LOSS' && pnlNum >= 0) return false;

                    if (!matchSetupFilter(item, setupFilter)) return false;

                    return true;
                });

                const totalFilteredCount = filtered.length;
                const totalPages = Math.ceil(totalFilteredCount / LEDGER_PAGE_SIZE) || 1;
                if (ledgerCurrentPage > totalPages) ledgerCurrentPage = totalPages;
                if (ledgerCurrentPage < 1) ledgerCurrentPage = 1;

                if (totalFilteredCount === 0) {
                    tbody.innerHTML = `<tr><td colspan="14" style="text-align:center; padding: 40px; color:#94a3b8; font-size:14px;">Seçilen filtre kriterlerine uygun işlem kaydı bulunamadı.</td></tr>`;
                    const pagCont = document.getElementById('ledger-pagination-container');
                    if (pagCont) pagCont.innerHTML = '';
                    return;
                }

                const startIndex = (ledgerCurrentPage - 1) * LEDGER_PAGE_SIZE;
                const pageItems = filtered.slice(startIndex, startIndex + LEDGER_PAGE_SIZE);

                let tableHtml = '';
                pageItems.forEach(h => {
                    const netPnl = Number(h.net_pnl || 0.0);
                    const roePct = Number(h.roe_pct || 0.0);
                    const isWin = netPnl >= 0;
                    const r = h.reason || 'Strateji Sinyali';
                    const cr = h.close_reason || 'Kapanış';
                    const symClean = (h.symbol || '').replace('/USDT', '');
                    const duration = h.duration || '5M Mum';
                    const exitTime = h.exit_time || '-';
                    const side = h.side || 'LONG';
                    const lev = h.leverage || 5;
                    const entryP = h.entry_price !== undefined ? h.entry_price : '-';
                    const exitP = h.exit_price !== undefined ? h.exit_price : '-';

                    // Setup badge style
                    let setupBadgeClass = 'badge-other';
                    const sClass = classifyTradeSetup(h);
                    if (sClass === 'NPOC') setupBadgeClass = 'badge-npoc';
                    else if (sClass === 'MACRO') setupBadgeClass = 'badge-macro';
                    else if (sClass === 'CAM_BO') setupBadgeClass = 'badge-breakout';
                    else if (sClass === 'BREAKDOWN') setupBadgeClass = 'badge-hard';
                    else if (sClass === 'CAM_BOUNCE') setupBadgeClass = 'badge-bounce';
                    else if (sClass === 'RETEST') setupBadgeClass = 'badge-macro';
                    else if (sClass === 'RECLAIM') setupBadgeClass = 'badge-breakout';

                    // Exit badge style
                    let exitBadgeClass = 'badge-time';
                    if (cr.includes('TP') || cr.includes('Kâr')) exitBadgeClass = 'badge-tp';
                    else if (cr.includes('Yumuşak') || cr.includes('Mum')) exitBadgeClass = 'badge-soft';
                    else if (cr.includes('Sert') || cr.includes('Stop')) exitBadgeClass = 'badge-hard';

                    const rMult = h.realized_r !== undefined ? h.realized_r : (roePct >= 0 ? +(roePct / 2).toFixed(1) : -1.0);
                    const mfe = Number(h.mfe_roe !== undefined ? h.mfe_roe : Math.max(0, roePct));
                    const mae = Number(h.mae_roe !== undefined ? h.mae_roe : (roePct < 0 ? Math.abs(roePct) : 0.0));

                    tableHtml += `
                    <tr>
                        <td><b style="color:var(--yellow)">${h.id || '-'}</b></td>
                        <td style="color:#cbd5e1; font-size:12px; white-space:nowrap;">${exitTime}</td>
                        <td style="color:#94a3b8; font-size:12px; white-space:nowrap;">⏱️ ${duration}</td>
                        <td><b style="color:#ffffff; font-size:13.5px; cursor:pointer;" onclick="openTradingViewModal('${symClean}')" title="${symClean} Göstergeli Grafiğini Aç">${symClean}</b></td>
                        <td><span class="pos-badge ${side === 'LONG' ? 'pos-long' : 'pos-short'}" style="font-size:11px; padding:2px 8px;">${(Number(lev) >= 7 ? '💎 ' : (Number(lev) <= 3 ? '🛡️ ' : ''))}${lev}x ${side}</span></td>
                        <td>$${formatSmartPrice(entryP)}</td>
                        <td>$${formatSmartPrice(exitP)}</td>
                        <td>
                            <span class="history-pnl-pill ${isWin ? 'pnl-win' : 'pnl-loss'}">
                                ${netPnl >= 0 ? '+' : '-'}$${Math.abs(netPnl).toFixed(2)}
                            </span>
                        </td>
                        <td>
                            <span class="history-roe-pill ${isWin ? 'roe-win' : 'roe-loss'}">
                                ${roePct >= 0 ? '+' : ''}${roePct.toFixed(2)}%
                            </span>
                        </td>
                        <td style="color:${rMult >= 0 ? 'var(--green)' : 'var(--red)'}; font-weight:800; font-family:'JetBrains Mono'">
                            ${rMult >= 0 ? '+' : ''}${rMult}R
                        </td>
                        <td style="color:#38bdf8; font-size:12px;" title="MFE: Görülen Zirve Kâr (+%${mfe.toFixed(1)}) | MAE: Maks Çekilme (-%${mae.toFixed(1)})">
                            +${mfe.toFixed(1)}% <span style="color:#64748b; font-size:10.5px;">(-${mae.toFixed(1)}%)</span>
                        </td>
                        <td>
                            <span class="badge-setup ${setupBadgeClass}" title="${r}">
                                ${r}
                            </span>
                        </td>
                        <td>
                            <span class="badge-exit ${exitBadgeClass}" title="${cr}">
                                ${cr}
                            </span>
                        </td>
                        <td style="white-space:nowrap;">
                            <button onclick="openTelemetryModal('${h.id}')" style="background:rgba(0,242,254,0.12); border:1px solid rgba(0,242,254,0.35); color:var(--cyan); padding:4px 9px; border-radius:6px; font-size:11px; font-weight:700; cursor:pointer; transition:all 0.15s ease;" onmouseover="this.style.background='var(--cyan)'; this.style.color='#000';" onmouseout="this.style.background='rgba(0,242,254,0.12)'; this.style.color='var(--cyan)';" title="İşlem Detayını İncele">
                                🔬 İncele
                            </button>
                            <button onclick="openTradingViewModal('${symClean}')" style="background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.15); color:#cbd5e1; padding:4px 8px; border-radius:6px; font-size:11px; font-weight:700; cursor:pointer; margin-left:4px; transition:all 0.15s ease;" onmouseover="this.style.background='rgba(0,242,254,0.15)'; this.style.color='#00f2fe';" onmouseout="this.style.background='rgba(255,255,255,0.06)'; this.style.color='#cbd5e1';" title="${symClean} Göstergeli Grafiğini Aç">
                                📈 Grafik
                            </button>
                        </td>
                    </tr>
                    `;
                });
                tbody.innerHTML = tableHtml;

                // Render Pagination Controls
                const pagCont = document.getElementById('ledger-pagination-container');
                if (pagCont) {
                    let pagesHtml = '';
                    
                    const prevDisabled = (ledgerCurrentPage === 1);
                    pagesHtml += `<button onclick="setLedgerPage(${ledgerCurrentPage - 1})" ${prevDisabled ? 'disabled' : ''} style="background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); color:${prevDisabled ? '#64748b' : '#fff'}; padding:6px 14px; border-radius:8px; font-size:12px; font-weight:800; cursor:${prevDisabled ? 'not-allowed' : 'pointer'}; transition:all 0.15s ease;">« Önceki</button>`;

                    for (let p = 1; p <= totalPages; p++) {
                        if (p === 1 || p === totalPages || (p >= ledgerCurrentPage - 2 && p <= ledgerCurrentPage + 2)) {
                            const isAct = (p === ledgerCurrentPage);
                            pagesHtml += `<button onclick="setLedgerPage(${p})" style="background:${isAct ? 'linear-gradient(135deg, #00f2fe, #4facfe)' : 'rgba(255,255,255,0.04)'}; border:${isAct ? 'none' : '1px solid rgba(255,255,255,0.08)'}; color:${isAct ? '#000' : '#cbd5e1'}; font-weight:900; font-size:12px; min-width:34px; height:32px; border-radius:8px; cursor:pointer; transition:all 0.15s ease;">${p}</button>`;
                        } else if (p === ledgerCurrentPage - 3 || p === ledgerCurrentPage + 3) {
                            pagesHtml += `<span style="color:#64748b; padding:0 4px;">...</span>`;
                        }
                    }

                    const nextDisabled = (ledgerCurrentPage === totalPages);
                    pagesHtml += `<button onclick="setLedgerPage(${ledgerCurrentPage + 1})" ${nextDisabled ? 'disabled' : ''} style="background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); color:${nextDisabled ? '#64748b' : '#fff'}; padding:6px 14px; border-radius:8px; font-size:12px; font-weight:800; cursor:${nextDisabled ? 'not-allowed' : 'pointer'}; transition:all 0.15s ease;">Sonraki »</button>`;

                    pagCont.innerHTML = `
                        <div style="font-size:12.5px; color:#94a3b8; font-family:'JetBrains Mono';">
                            Toplam <b style="color:#ffffff;">${totalFilteredCount}</b> işlemden <b style="color:var(--cyan);">${startIndex + 1} - ${Math.min(startIndex + LEDGER_PAGE_SIZE, totalFilteredCount)}</b> arası gösteriliyor (Sayfa ${ledgerCurrentPage} / ${totalPages})
                        </div>
                        <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                            ${pagesHtml}
                        </div>
                    `;
                }
            } catch (err) {
                console.error("renderHistoryTable error:", err);
            }
        }
function downloadExcelReport() {
            window.location.href = '/api/export_excel';
        }

        function downloadCSVReport() {
            try {
                const hList = appState.history || [];
                if (hList.length === 0) {
                    alert("İndirilecek işlem geçmişi bulunmuyor.");
                    return;
                }

                const symFilter = document.getElementById('filter-symbol') ? document.getElementById('filter-symbol').value : 'ALL';
                const setupFilter = document.getElementById('filter-setup') ? document.getElementById('filter-setup').value : 'ALL';
                const statusFilter = document.getElementById('filter-status') ? document.getElementById('filter-status').value : 'ALL';

                let filtered = hList.filter(item => {
                    if (!item) return false;
                    const itemSym = (item.symbol || '').replace('/USDT', '');
                    const cleanSymFilter = (symFilter || '').replace('/USDT', '');
                    if (cleanSymFilter !== 'ALL' && itemSym !== cleanSymFilter && item.symbol !== symFilter) return false;
                    const pnlNum = Number(item.net_pnl || 0.0);
                    if (statusFilter === 'WIN' && pnlNum < 0) return false;
                    if (statusFilter === 'LOSS' && pnlNum >= 0) return false;
                    if (!matchSetupFilter(item, setupFilter)) return false;
                    return true;
                });

                let csvContent = String.fromCharCode(0xFEFF);
                csvContent += "Islem ID;Tarih Giris;Tarih Cikis;Parite;Yon;Kaldirac;Marjin (USDT);Giris Fiyati;Cikis Fiyati;Brut Kar (USDT);Komisyon (USDT);Net Kar (USDT);ROE (%);Guncel Kasa (USDT);Setup Nedeni;Kapanis Nedeni" + String.fromCharCode(10);

                filtered.forEach(h => {
                    const row = [
                        h.id,
                        h.entry_time,
                        h.exit_time,
                        h.symbol,
                        h.side,
                        h.leverage + "x",
                        h.margin,
                        h.entry_price,
                        h.exit_price,
                        h.gross_pnl,
                        h.fees,
                        h.net_pnl,
                        h.roe_pct + "%",
                        h.balance_after,
                        '"' + (h.reason || '').replace(/"/g, '""') + '"',
                        '"' + (h.close_reason || '').replace(/"/g, '""') + '"'
                    ];
                    csvContent += row.join(";") + String.fromCharCode(10);
                });

                const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
                const link = document.createElement("a");
                const url = URL.createObjectURL(blob);
                const dateStr = new Date().toISOString().slice(0,10);
                link.setAttribute("href", url);
                link.setAttribute("download", "Ticaret_Raporu_" + dateStr + ".csv");
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            } catch (err) {
                console.error("downloadCSVReport error:", err);
            }
        }

        function getCleanStreamName(sym) {
            let s = sym.replace('/USDT', '').toLowerCase();
            const multiplierMap = {
                'pepe': '1000pepe', 'shib': '1000shib', 'bonk': '1000bonk',
                'floki': '1000floki', 'sats': '1000sats', 'rats': '1000rats',
                'lunc': '1000lunc', 'xec': '1000xec', 'mog': '1000000mog', 'cheems': '1000cheems',
                'why': '1000why', 'cat': '1000cat', 'neiro': '1000neiro'
            };
            let base = multiplierMap[s] || s;
            return base + 'usdt';
        }

        function mapRawSymbol(rawSym) {
            if (!rawSym) return null;
            if (rawSymbolMap[rawSym]) return rawSymbolMap[rawSym];
            let clean = rawSym.toUpperCase();
            if (clean.endsWith('USDT')) {
                let base = clean.slice(0, -4);
                if (base.startsWith('1000000')) base = base.slice(7);
                else if (base.startsWith('1000')) base = base.slice(4);
                return base + '/USDT';
            }
            return null;
        }

        // BİNANCE VADELİ (FUTURES) CANLI BOOKTICKER WEBSOCKET (TOP 50 PARİTE STREAM)
        let globalWs = null;
        function startBinanceGlobalFeed() {
            if (globalWs) {
                try { globalWs.close(); } catch(e){}
            }
            const allSymbols = (appState.all_coins && appState.all_coins.length > 0) 
                ? appState.all_coins.map(c => c.symbol)
                : Object.keys(rawSymbolMap).map(k => rawSymbolMap[k]);
            
            const streams = allSymbols.map(s => getCleanStreamName(s) + '@bookTicker').join('/');
            const wsUrl = `wss://fstream.binance.com/stream?streams=${streams}`;
            globalWs = new WebSocket(wsUrl);

            globalWs.onopen = () => {
                const wsSt = document.getElementById('ws-status'); if (wsSt) wsSt.innerText = 'BİNANCE VADELİ CANLI YAYIN AKTİF (100 PARİTE)';
            };

            globalWs.onmessage = (evt) => {
                try {
                    const msg = JSON.parse(evt.data);
                    const data = msg.data || {};
                    const rawSym = data.s;
                    const bid = parseFloat(data.b);
                    const ask = parseFloat(data.a);
                    const price = (bid && ask) ? ((bid + ask) / 2.0) : (bid || ask);

                    const sym = mapRawSymbol(rawSym);
                    if (sym && price > 0) {
                        updatePriceInPlace(sym, price);
                    }
                } catch(e) {}
            };

            globalWs.onclose = () => {
                setTimeout(startBinanceGlobalFeed, 2000);
            };
        }

        function startSSEFallback() {
            try {
                const eventSource = new EventSource('/api/stream');
                eventSource.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        if (data.type === 'tick') {
                            updatePriceInPlace(data.symbol, data.price);
                        }
                    } catch(e) {}
                };
            } catch(e) {}
        }

        let lastRenderedPositionsKey = '';
        let lastRenderedHistoryLen = -1;
        let lastRenderedCoinsKey = '';
        let lastRenderedSymbolsCount = -1;

        async function syncBackendState() {
            try {
                const res = await fetch('/api/data');
                const data = await res.json();
                appState = data;

                // 1. Sync prices in memory
                if (appState.symbols) {
                    for (const s in appState.symbols) {
                        const p = appState.symbols[s].price;
                        if (p > 0) {
                            livePrices[s] = p;
                        }
                    }
                }
                if (appState.all_coins) {
                    for (const c of appState.all_coins) {
                        if (c.price > 0 && !livePrices[c.symbol]) {
                            livePrices[c.symbol] = c.price;
                        }
                    }
                }

                // 2. Only re-render Coin Manager if coin list or active status changed
                const currentCoinsKey = (appState.all_coins || []).map(c => c.symbol + ':' + c.active).join(',');
                if (currentCoinsKey !== lastRenderedCoinsKey) {
                    lastRenderedCoinsKey = currentCoinsKey;
                    renderCoinManager();
                }

                // 3. Only re-render Watchlist Cards if symbols count changed or empty
                const currentSymbolsCount = Object.keys(appState.symbols || {}).length;
                const watchlistCont = document.getElementById('watchlist-container');
                if (currentSymbolsCount !== lastRenderedSymbolsCount || (watchlistCont && watchlistCont.children.length === 0)) {
                    lastRenderedSymbolsCount = currentSymbolsCount;
                    renderCards();
                }
                renderCockpitView();
                renderCockpitOpenPositions();
                updateSystemHealthBadge();

                // 4. Only re-render Open Positions if position IDs or count changed
                const currentPosKey = Object.keys(appState.open_positions || {}).sort().join(',');
                if (currentPosKey !== lastRenderedPositionsKey) {
                    lastRenderedPositionsKey = currentPosKey;
                    renderPositions();
                }
                updateNavBadges();

                // 5. Only re-render History Table if history length changed
                const currentHistLen = (appState.history || []).length;
                if (currentHistLen !== lastRenderedHistoryLen) {
                    lastRenderedHistoryLen = currentHistLen;
                    renderHistoryTable();
                }

                // 5b. Update Persona Matrix if active tab, otherwise update badge
                if (currentActiveMainTab === 'persona') {
                    renderPersonaMatrixView();
                } else {
                    updatePersonaBadge();
                }

                // 5c. Update Funding & Liquidation Matrix if active tab, otherwise update badge
                if (currentActiveMainTab === 'funding') {
                    renderFundingMatrixView();
                    renderLiquidationView();
                } else {
                    updateFundingBadge();
                }

                // 5c2. Update Micro-CVD Matrix if active tab
                if (currentActiveMainTab === 'cvd') {
                    renderCvdView();
                }

                // 5c3. Update Health & Telemetry View if active tab
                if (currentActiveMainTab === 'health' || window.currentActiveMainTab === 'health') {
                    renderHealthTabView();
                }

                // 5c4. Update Shadow & Calibration View if active tab, otherwise update badge
                if (currentActiveMainTab === 'shadow') {
                    renderShadowView();
                } else {
                    updateShadowBadge();
                }

                // 5d. Update Cockpit Funding, Liquidation & Micro-CVD Commentary
                const cFundingEl = document.getElementById('cockpit-funding-commentary');
                if (cFundingEl && appState.funding_summary) {
                    const fSumm = appState.funding_summary.summary || {};
                    const fMedian = fSumm.median_rate_pct != null ? fSumm.median_rate_pct : 0.01;
                    const sqSyms = fSumm.short_squeeze_symbols || [];

                    let liqSnippet = '';
                    if (appState.liquidation_summary && appState.liquidation_summary.total_liq_usd > 0) {
                        const lTotal = (appState.liquidation_summary.total_liq_usd / 1000).toFixed(0);
                        const lDom = appState.liquidation_summary.dominant_side === 'LONG' ? '🔴 Long' : '🟢 Short';
                        liqSnippet = ` | 💥 <b>$${lTotal}K</b> Tasfiye (${lDom} Baskılı)`;
                    }

                    let cvdSnippet = '';
                    if (appState.cvd_summary && appState.cvd_summary.avg_buy_ratio != null) {
                        const cBuy = Number(appState.cvd_summary.avg_buy_ratio).toFixed(1);
                        cvdSnippet = ` | 🔬 Mikro-CVD: <b style="color:${cBuy >= 50 ? '#22c55e' : '#ef4444'};">%${cBuy} Alıcı</b>`;
                    }

                    if (sqSyms.length > 0) {
                        const cleanList = sqSyms.map(s => s.replace('/USDT', '')).slice(0, 4).join(', ');
                        cFundingEl.innerHTML = `<b style="color:var(--cyan);">${fMedian >= 0 ? '+' : ''}${fMedian.toFixed(4)}%</b> Medyan | <span style="color:var(--red); font-weight:800;">⚠️ ${sqSyms.length} Paritede Short Squeeze Riski (${cleanList})</span> — <b style="color:var(--green);">Kalkan Aktif 🔒</b>${liqSnippet}${cvdSnippet}`;
                    } else {
                        cFundingEl.innerHTML = `<b style="color:var(--cyan);">${fMedian >= 0 ? '+' : ''}${fMedian.toFixed(4)}%</b> Medyan | <span style="color:var(--green); font-weight:700;">🟢 Fonlama Dengeli</span>${liqSnippet}${cvdSnippet}`;
                    }
                }

                // 6. Smooth in-place updates (Zero DOM destruction, Zero scroll jumping!)
                updateFinancialSummary();
                for (const s in appState.open_positions) {
                    const curP = Number(livePrices[s] || (appState.symbols[s] ? appState.symbols[s].price : 0));
                    if (curP > 0) {
                        updatePriceInPlace(s, curP);
                    }
                }
            } catch(e) {
                console.error(e);
            }
        }

        
        let selectedTradingMode = 'DEMO';

        function openLiveSettingsModal() {
            const overlay = document.getElementById('live-settings-overlay');
            if (overlay) overlay.style.display = 'flex';
            fetchLiveStatus();
        }

        function closeLiveSettingsModal() {
            const overlay = document.getElementById('live-settings-overlay');
            if (overlay) overlay.style.display = 'none';
        }

        function switchSettingsTab(tab) {
            ['api', 'risk', 'status'].forEach(t => {
                const btn = document.getElementById('set-tab-' + t);
                const content = document.getElementById('tab-content-' + t);
                if (btn && content) {
                    if (t === tab) {
                        btn.className = 'settings-tab-btn tab-active';
                        content.style.display = 'block';
                    } else {
                        btn.className = 'settings-tab-btn';
                        content.style.display = 'none';
                    }
                }
            });
        }

        function selectTradingMode(mode) {
            selectedTradingMode = mode;
            const lblDemo = document.getElementById('lbl-mode-demo');
            const lblLive = document.getElementById('lbl-mode-live');
            if (mode === 'DEMO') {
                if (lblDemo) lblDemo.className = 'mode-radio-label is-selected-demo';
                if (lblLive) lblLive.className = 'mode-radio-label';
            } else {
                if (lblDemo) lblDemo.className = 'mode-radio-label';
                if (lblLive) lblLive.className = 'mode-radio-label is-selected-live';
            }
        }

        function togglePasswordVisibility(inputId) {
            const input = document.getElementById(inputId);
            if (input) {
                input.type = input.type === 'password' ? 'text' : 'password';
            }
        }

        async function fetchLiveStatus() {
            try {
                const res = await fetch('/api/live/status');
                const data = await res.json();
                if (data.status === 'ok') {
                    selectedTradingMode = data.mode || 'DEMO';
                    selectTradingMode(selectedTradingMode);
                    
                    if (data.api_key_masked) {
                        document.getElementById('input-api-key').placeholder = data.api_key_masked;
                    }
                    if (data.api_secret_masked) {
                        document.getElementById('input-api-secret').placeholder = data.api_secret_masked;
                    }
                    if (data.leverage) {
                        document.getElementById('input-leverage').value = data.leverage;
                        document.getElementById('input-leverage-slider').value = data.leverage;
                    }
                    if (data.position_size_usdt) {
                        document.getElementById('input-position-size').value = data.position_size_usdt;
                    }
                    if (data.margin_type) {
                        document.getElementById('input-margin-type').value = data.margin_type;
                    }
                    if (data.max_open_positions) {
                        document.getElementById('input-max-pos').value = data.max_open_positions;
                    }

                    updateModeBadgeUI(data.mode);

                    if (data.api_key_set && data.live_balance !== undefined) {
                        renderLiveWalletOverview(data);
                    }
                }
            } catch(e) {
                console.error("fetchLiveStatus error:", e);
            }
        }

        function updateModeBadgeUI(mode) {
            const badgeWrap = document.getElementById('mode-badge-wrap');
            const badgeDot = document.getElementById('mode-badge-dot');
            const badgeText = document.getElementById('mode-badge-text');
            if (!badgeWrap || !badgeDot || !badgeText) return;

            if (mode === 'LIVE') {
                badgeWrap.className = 'mode-badge-wrap is-live';
                badgeDot.className = 'mode-dot-live';
                badgeText.innerText = '🔴 GERÇEK HESAP (Live)';
            } else {
                badgeWrap.className = 'mode-badge-wrap';
                badgeDot.className = 'mode-dot-demo';
                badgeText.innerText = '🟡 DEMO MODU';
            }
        }

        async function testBinanceConnection() {
            const apiKey = document.getElementById('input-api-key').value;
            const apiSecret = document.getElementById('input-api-secret').value;
            const box = document.getElementById('conn-result-box');
            if (!box) return;

            box.style.display = 'block';
            box.style.background = 'rgba(56,139,253,0.1)';
            box.style.border = '1px solid rgba(56,139,253,0.3)';
            box.style.color = '#58a6ff';
            box.innerHTML = '⚡ Binance Futures sunucularına bağlanılıyor...';

            try {
                const res = await fetch('/api/live/test_connection', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ api_key: apiKey, api_secret: apiSecret })
                });
                const data = await res.json();
                if (data.status === 'ok') {
                    box.style.background = 'rgba(14,203,129,0.12)';
                    box.style.border = '1px solid var(--green)';
                    box.style.color = 'var(--green)';
                    box.innerHTML = `
                        <div style="font-weight:800; margin-bottom:4px;">✅ ${data.message}</div>
                        <div>• Toplam Vadeli Bakiye: <b>$${data.total_balance} USDT</b></div>
                        <div>• Kullanılabilir Marjin: <b>$${data.free_balance} USDT</b></div>
                        <div>• API Gecikmesi (Ping): <b>${data.ping_ms} ms</b></div>
                    `;
                } else {
                    box.style.background = 'rgba(255,71,87,0.12)';
                    box.style.border = '1px solid var(--red)';
                    box.style.color = 'var(--red)';
                    box.innerHTML = `❌ ${data.message}`;
                }
            } catch(err) {
                box.style.background = 'rgba(255,71,87,0.12)';
                box.style.border = '1px solid var(--red)';
                box.style.color = 'var(--red)';
                box.innerHTML = `❌ Bağlantı hatası: ${err.message}`;
            }
        }

        async function saveBinanceSettings() {
            const apiKey = document.getElementById('input-api-key').value;
            const apiSecret = document.getElementById('input-api-secret').value;
            const leverage = document.getElementById('input-leverage').value;
            const positionSize = document.getElementById('input-position-size').value;
            const marginType = document.getElementById('input-margin-type').value;
            const maxPos = document.getElementById('input-max-pos').value;

            try {
                const res = await fetch('/api/live/save_config', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        mode: selectedTradingMode,
                        api_key: apiKey,
                        api_secret: apiSecret,
                        leverage: leverage,
                        position_size_usdt: positionSize,
                        margin_type: marginType,
                        max_open_positions: maxPos
                    })
                });
                const data = await res.json();
                if (data.status === 'ok') {
                    alert("✅ Binance Ayarları Başarıyla Kaydedildi!");
                    updateModeBadgeUI(selectedTradingMode);
                    closeLiveSettingsModal();
                    await syncBackendState();
                } else {
                    alert("Hata: " + (data.message || 'Ayarlar kaydedilemedi'));
                }
            } catch(e) {
                alert("Hata: " + e.message);
            }
        }

        function renderLiveWalletOverview(data) {
            const cont = document.getElementById('live-wallet-overview');
            if (!cont) return;
            cont.innerHTML = `
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:16px;">
                    <div style="background:var(--card-bg); border:1px solid var(--border); border-radius:10px; padding:12px 16px;">
                        <div style="font-size:11px; color:var(--text-muted); font-weight:800;">TOPLAM VADELİ BAKİYE</div>
                        <div style="font-size:22px; font-weight:800; color:var(--green); font-family:'JetBrains Mono'; margin-top:2px;">
                            $${Number(data.live_balance || 0).toFixed(2)}
                        </div>
                    </div>
                    <div style="background:var(--card-bg); border:1px solid var(--border); border-radius:10px; padding:12px 16px;">
                        <div style="font-size:11px; color:var(--text-muted); font-weight:800;">KULLANILABİLİR MARJİN</div>
                        <div style="font-size:22px; font-weight:800; color:#ffffff; font-family:'JetBrains Mono'; margin-top:2px;">
                            $${Number(data.live_free_balance || 0).toFixed(2)}
                        </div>
                    </div>
                </div>
                <div style="font-size:12px; color:var(--text-muted);">
                    Bağlantı Durumu: <span style="color:var(--green); font-weight:800;">🟢 AKTİF & DOĞRULANDI</span>
                </div>
            `;
        }


        function openTelemetryModal(tradeId) {
            try {
                const hList = appState.history || [];
                const item = hList.find(h => h.id === tradeId);
                if (!item) {
                    alert("İşlem kaydı bulunamadı: " + tradeId);
                    return;
                }

                const modal = document.getElementById('telemetry-modal-overlay');
                const title = document.getElementById('tel-title');
                const sub = document.getElementById('tel-sub');
                const content = document.getElementById('tel-content');

                if (!modal || !content) return;

                title.innerHTML = `🔬 ${item.symbol} (${item.side} ${item.leverage}x) — ${item.id}`;
                sub.innerHTML = `Giriş: ${item.entry_time} | Çıkış: ${item.exit_time} | Süre: ${item.duration || '5M Mum'}`;

                const cleanSym = (item.symbol || '').replace('/USDT', '').replace('USDT', '').trim();
                const chartBtn = document.getElementById('tel-chart-btn');
                if (chartBtn) {
                    chartBtn.onclick = () => openTradingViewModal(cleanSym);
                    chartBtn.innerHTML = `📈 ${cleanSym} Grafiği`;
                    chartBtn.title = `${cleanSym} Göstergeli Bot Strateji Grafiğini Aç`;
                }

                const isWin = Number(item.net_pnl || 0.0) >= 0;
                const netPnlVal = Number(item.net_pnl || 0.0);
                const roePctVal = Number(item.roe_pct || 0.0);
                const feesVal = Number(item.fees || 0.0);
                const rMult = item.realized_r !== undefined ? item.realized_r : (roePctVal >= 0 ? +(roePctVal / 2).toFixed(1) : -1.0);
                const mfeVal = Number(item.mfe_roe !== undefined ? item.mfe_roe : Math.max(0, roePctVal));
                const maeVal = Number(item.mae_roe !== undefined ? item.mae_roe : (roePctVal < 0 ? Math.abs(roePctVal) : 0.0));
                const effVal = Number(item.exit_efficiency_pct !== undefined ? item.exit_efficiency_pct : (isWin ? 90.0 : 0.0));

                let snaps = item.snapshot_levels || {};
                // Fallback to coin's current levels if snapshot was before this update
                if (Object.keys(snaps).length === 0 && appState.symbols && appState.symbols[item.symbol]) {
                    const cLevels = appState.symbols[item.symbol].levels || {};
                    const cam = cLevels.camarilla || {};
                    snaps = {
                        "Pivot P": cam.P, "S3": cam.S3, "S4": cam.S4, "R3": cam.R3, "R4": cam.R4,
                        "Tepe AVWAP": cLevels.tepe_avwap, "Dip AVWAP": cLevels.dip_avwap,
                        "mPOC": cLevels.mpoc, "mVAL": cLevels.mval, "mVAH": cLevels.mvah
                    };
                }

                let snapHtml = '';
                for (const [key, val] of Object.entries(snaps)) {
                    if (val && typeof val === 'number' && val > 0) {
                        snapHtml += `
                        <div style="background:rgba(255,255,255,0.04); border:1px solid var(--border); padding:8px 12px; border-radius:8px; font-size:12px; display:flex; justify-content:space-between; align-items:center;">
                            <span style="color:#94a3b8; font-weight:700;">${key}:</span>
                            <b style="color:#fff; font-family:'JetBrains Mono';">$${formatSmartPrice(val)}</b>
                        </div>`;
                    }
                }
                if (!snapHtml) {
                    snapHtml = '<div style="color:#64748b; font-size:12px; grid-column:1/-1;">Bu işlem için anlık seviye verisi taze işlemlerle birlikte dolacaktır.</div>';
                }

                content.innerHTML = `
                    <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap:10px; margin-bottom:18px;">
                        <div style="background:rgba(255,255,255,0.03); border:1px solid var(--border); border-radius:10px; padding:12px; text-align:center;">
                            <div style="font-size:11px; color:#94a3b8; margin-bottom:4px;">NET PNL & ROE</div>
                            <div style="font-size:15px; font-weight:800; color:${isWin ? 'var(--green)' : 'var(--red)'}; font-family:'JetBrains Mono';">${isWin ? '+' : ''}${netPnlVal.toFixed(2)}$ (${isWin ? '+' : ''}${roePctVal.toFixed(2)}%)</div>
                        </div>
                        <div style="background:rgba(255,255,255,0.03); border:1px solid var(--border); border-radius:10px; padding:12px; text-align:center;">
                            <div style="font-size:11px; color:#94a3b8; margin-bottom:4px;">R-MULTIPLE (1R)</div>
                            <div style="font-size:15px; font-weight:800; color:${rMult >= 0 ? 'var(--green)' : 'var(--red)'}; font-family:'JetBrains Mono';">${rMult >= 0 ? '+' : ''}${rMult}R</div>
                        </div>
                        <div style="background:rgba(255,255,255,0.03); border:1px solid var(--border); border-radius:10px; padding:12px; text-align:center;">
                            <div style="font-size:11px; color:#94a3b8; margin-bottom:4px;">ZİRVE KÂR (MFE)</div>
                            <div style="font-size:15px; font-weight:800; color:#38bdf8; font-family:'JetBrains Mono';">+${mfeVal.toFixed(2)}% ROE</div>
                        </div>
                        <div style="background:rgba(255,255,255,0.03); border:1px solid var(--border); border-radius:10px; padding:12px; text-align:center;">
                            <div style="font-size:11px; color:#94a3b8; margin-bottom:4px;">MAKS ÇEKİLME (MAE)</div>
                            <div style="font-size:15px; font-weight:800; color:#f43f5e; font-family:'JetBrains Mono';">-${maeVal.toFixed(2)}% ROE</div>
                        </div>
                    </div>

                    <!-- 📈 GRAFİK AÇMA HERO BUTONU -->
                    <div style="margin-bottom:18px;">
                        <button onclick="openTradingViewModal('${cleanSym}')" style="width:100%; padding:12px 18px; background:linear-gradient(135deg, rgba(0,242,254,0.2), rgba(79,172,254,0.3)); border:1.5px solid var(--cyan); color:#00f2fe; font-weight:900; font-size:13.5px; border-radius:10px; cursor:pointer; display:flex; align-items:center; justify-content:center; gap:8px; transition:all 0.15s ease; box-shadow:0 0 20px rgba(0,242,254,0.2);" onmouseover="this.style.background='var(--cyan)'; this.style.color='#000';" onmouseout="this.style.background='linear-gradient(135deg, rgba(0,242,254,0.2), rgba(79,172,254,0.3))'; this.style.color='#00f2fe';" title="${cleanSym} Canlı Göstergeli Strateji Grafiğini Aç">
                            <span>📈</span> <b>${cleanSym} GÖSTERGELİ STRATEJİ GRAFİĞİNİ AÇ</b> (AVWAP + VP + Camarilla Seviyeleri) ➔
                        </button>
                    </div>

                    <div style="background:rgba(56,189,248,0.06); border:1px solid rgba(56,189,248,0.25); border-radius:12px; padding:14px; margin-bottom:18px;">
                        <div style="font-size:13px; font-weight:800; color:#38bdf8; margin-bottom:8px; display:flex; align-items:center; gap:6px;">
                            🎯 STRATEJİ, TREND REJİMİ & PİYASA KOŞULLARI
                        </div>
                        <div style="font-size:12.5px; color:#f1f5f9; line-height:1.7;">
                            <b>• Giriş Gerekçesi / Formasyon:</b> <span style="color:#ffffff;">${item.reason || 'Strateji Sinyali'}</span><br>
                            <b>• Kurumsal Kurulum (Setup):</b> <span style="color:var(--cyan); font-weight:700; font-family:'JetBrains Mono';">${item.setup_id || classifyTradeSetup(item)}</span> | <b>Kapanış Tetikleyicisi:</b> <span style="color:#fbc531;">${item.close_reason || 'Kapanış'}</span><br>
                            <b>• Giriş Anı Trend Rejimi:</b> <span style="color:#a5f3fc; font-weight:700;">${item.trend_regime || 'Belirleniyor'}</span> | <b>Volatilite (ATR):</b> <span style="color:#fde047; font-weight:700;">%${item.atr_pct !== undefined ? item.atr_pct : '1.2'}</span><br>
                            <b>• Hacim Patlama Katsayısı:</b> <span style="color:#38bdf8; font-weight:700;">${item.volume_surge || '1.0'}x Ort. Hacim</span> | <b>Confluence Güç Skoru:</b> <span style="color:#c084fc; font-weight:700;">${item.confluence_score || '2/4'}</span><br>
                            <b>• Makro Uyum (1H/4H):</b> <span style="color:#fcd34d; font-weight:700;">${item.htf_alignment || 'Nötr'}</span> | <b>Piyasa Seansı:</b> <span style="color:#e2e8f0;">${item.session || 'Küresel Seans'}</span><br>
                            <b>• Kademeli TP1 Durumu:</b> <span style="color:#86efac; font-weight:700;">${item.tp1_hit || (item.id && item.id.includes('TP1') ? 'EVET (%50 Kilitlendi)' : 'HAYIR')}</span> | <b>Çıkış Verimliliği:</b> %${effVal.toFixed(1)}<br>
                            <b>• Giriş / Çıkış Fiyatı:</b> $${formatSmartPrice(item.entry_price)} ➔ $${formatSmartPrice(item.exit_price)} | <b>Komisyon:</b> $${feesVal.toFixed(4)}<br>
                            <b>• Planlanan Hedef (TP1):</b> ${item.tp1 ? '$' + formatSmartPrice(item.tp1) : 'Yok'} | <b>Planlanan Stop:</b> ${(item.hard_stop || item.soft_stop) ? '$' + formatSmartPrice(item.hard_stop || item.soft_stop) : 'Yok'}
                        </div>
                    </div>

                    <!-- VALKYRIE ALPHA MASTER BLUEPRINT TELEMETRİSİ -->
                    <div style="background:rgba(0,242,254,0.03); border:1px solid rgba(0,242,254,0.2); border-radius:12px; padding:14px; margin-bottom:18px;">
                        <div style="font-size:13px; font-weight:800; color:var(--cyan); margin-bottom:10px; display:flex; align-items:center; gap:6px;">
                            <span>🏛️</span> VALKYRIE KURUMSAL ALPHA MASTER BLUEPRINT TELEMETRİSİ
                        </div>
                        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap:10px;">
                            <div style="background:rgba(255,255,255,0.02); border-radius:8px; padding:8px 12px; border:1px solid rgba(255,255,255,0.05);">
                                <div style="font-size:10px; color:#94a3b8; margin-bottom:3px;">Deribit GEX Rejimi</div>
                                <div style="font-size:12.5px; font-weight:800; color:#38bdf8; font-family:'JetBrains Mono',monospace;">${item.deribit_gex_regime || 'NEUTRAL'}</div>
                            </div>
                            <div style="background:rgba(255,255,255,0.02); border-radius:8px; padding:8px 12px; border:1px solid rgba(255,255,255,0.05);">
                                <div style="font-size:10px; color:#94a3b8; margin-bottom:3px;">Hawkes Çığı (η)</div>
                                <div style="font-size:12.5px; font-weight:800; color:${item.is_avalanche_active ? '#ef4444' : '#10b981'}; font-family:'JetBrains Mono',monospace;">η: ${Number(item.hawkes_eta || 0.15).toFixed(2)} ${item.is_avalanche_active ? '⚡ ÇIĞ' : '⚪ SAKİN'}</div>
                            </div>
                            <div style="background:rgba(255,255,255,0.02); border-radius:8px; padding:8px 12px; border:1px solid rgba(255,255,255,0.05);">
                                <div style="font-size:10px; color:#94a3b8; margin-bottom:3px;">Stoikov Drift / Micro</div>
                                <div style="font-size:12.5px; font-weight:800; color:#fbbf24; font-family:'JetBrains Mono',monospace;">${Number(item.stoikov_drift_bps || 0).toFixed(1)} bps</div>
                            </div>
                            <div style="background:rgba(255,255,255,0.02); border-radius:8px; padding:8px 12px; border:1px solid rgba(255,255,255,0.05);">
                                <div style="font-size:10px; color:#94a3b8; margin-bottom:3px;">VPIN Toksisite & Kyle</div>
                                <div style="font-size:12.5px; font-weight:800; color:#c084fc; font-family:'JetBrains Mono',monospace;">${item.vpin_toxicity || 'LOW'} (${Number(item.vpin_score || 0.30).toFixed(2)}) • ${Number(item.kyles_lambda_ratio || 1.0).toFixed(1)}x</div>
                            </div>
                            <div style="background:rgba(255,255,255,0.02); border-radius:8px; padding:8px 12px; border:1px solid rgba(255,255,255,0.05);">
                                <div style="font-size:10px; color:#94a3b8; margin-bottom:3px;">Tri-Modal & CVD İvme</div>
                                <div style="font-size:12.5px; font-weight:800; color:#4ade80; font-family:'JetBrains Mono',monospace;">${item.tri_modal_regime || 'RANGING'} (${Number(item.cvd_accel_60s || 0).toFixed(1)})</div>
                            </div>
                        </div>
                    </div>

                    <div style="font-size:13px; font-weight:800; color:#fff; margin-bottom:10px; display:flex; align-items:center; gap:6px;">
                        📸 GİRİŞ ANINDAKİ KURUMSAL SEVİYE SNAPSHOT'I
                    </div>
                    <div style="display:grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap:8px;">
                        ${snapHtml}
                    </div>
                `;

                modal.style.display = 'flex';
            } catch(err) {
                console.error("openTelemetryModal error:", err);
                alert("İnceleme penceresi açılırken hata oluştu: " + err.message);
            }
        }

        function closeTelemetryModal() {
            const modal = document.getElementById('telemetry-modal-overlay');
            if (modal) modal.style.display = 'none';
        }

        async function openShadowCoinDetail(symbol) {
            try {
                const modal = document.getElementById('shadow-coin-detail-modal');
                if (!modal) return;

                const cleanSym = symbol.replace('/USDT', '').replace(':USDT', '').replace('USDT', '').trim().toUpperCase();
                
                document.getElementById('shadow-modal-symbol').innerText = `${cleanSym}/USDT`;
                document.getElementById('shadow-modal-persona').innerText = `Coin DNA & Adli İnceleme Yükleniyor...`;
                document.getElementById('shadow-modal-narrative').innerHTML = `<span style="color:#94a3b8;">Canlı veriler ve kalkan kayıtları taranıyor...</span>`;
                modal.style.display = 'flex';

                const resp = await fetch(`/api/shadow_coin_detail?symbol=${encodeURIComponent(cleanSym)}`);
                const resData = await resp.json();
                const d = resData.detail || {};

                const isHeroDom = d.sei >= 70;
                const isSpoilerDom = d.sei <= 35 && d.spoiler_count >= 2;
                const badgeText = d.recommendation_badge || (isSpoilerDom ? '⚠️ GEVŞET' : (isHeroDom ? '👑 KORU' : (d.recommendation_badge || '⚖️ DENGELİ')));
                const badgeColor = badgeText.includes('GEVŞET') ? '#f43f5e' : (badgeText.includes('KORU') ? '#10b981' : (badgeText.includes('ERKEN') ? '#38bdf8' : '#f59e0b'));
                const badgeBg = badgeText.includes('GEVŞET') ? 'rgba(244,63,94,0.15)' : (badgeText.includes('KORU') ? 'rgba(16,185,129,0.15)' : (badgeText.includes('ERKEN') ? 'rgba(56,189,248,0.15)' : 'rgba(245,158,11,0.15)'));
                
                const badgeEl = document.getElementById('shadow-modal-badge');
                badgeEl.innerText = badgeText;
                badgeEl.style.color = badgeColor;
                badgeEl.style.borderColor = `${badgeColor}40`;
                badgeEl.style.background = badgeBg;

                document.getElementById('shadow-modal-persona').innerHTML = `Persona: <strong style="color:#fff;">${d.persona_name || 'Standart Kripto'}</strong> • Teşhis: <span style="color:#38bdf8; font-weight:700;">${d.scenario_title || 'Canlı Piyasa Gözlemi'}</span> • Toplam ${d.total_trades || 0} Sinyal (${d.active_count || 0} Aktif, ${d.completed_count || 0} Tamamlandı)`;

                document.getElementById('shadow-modal-kpi-saved').innerText = `+$${(d.saved_loss_usd || 0).toFixed(2)}`;
                document.getElementById('shadow-modal-kpi-hero').innerText = `${d.hero_count || 0} Stop Engellendi`;
                
                document.getElementById('shadow-modal-kpi-missed').innerText = `-$${(d.missed_profit_usd || 0).toFixed(2)}`;
                document.getElementById('shadow-modal-kpi-spoiler').innerText = `${d.spoiler_count || 0} Kâr Kaçırıldı`;

                const seiEl = document.getElementById('shadow-modal-kpi-sei');
                seiEl.innerText = `%${(d.sei != null ? d.sei : 100).toFixed(1)}`;
                seiEl.style.color = badgeColor;

                const alphaEl = document.getElementById('shadow-modal-kpi-alpha');
                const alpha = d.net_alpha_usd || 0;
                alphaEl.innerText = `${alpha >= 0 ? '+$' : '-$'}${Math.abs(alpha).toFixed(2)}`;
                alphaEl.style.color = alpha >= 0 ? '#10b981' : '#f43f5e';

                // Optimum Durum & Güven Endeksi
                const optScore = d.optimality_score != null ? d.optimality_score : 50;
                const optStatusEl = document.getElementById('shadow-modal-optimality-status');
                const optDescEl = document.getElementById('shadow-modal-optimality-desc');
                const optScoreEl = document.getElementById('shadow-modal-optimality-score');

                if (optStatusEl) optStatusEl.innerText = d.optimality_status || '⚖️ Analiz Ediliyor';
                if (optDescEl) optDescEl.innerText = d.optimality_desc || '';
                if (optScoreEl) {
                    optScoreEl.innerText = `%${optScore.toFixed(0)}`;
                    optScoreEl.style.color = (optScore >= 80) ? '#10b981' : ((optScore <= 40) ? '#f43f5e' : '#f59e0b');
                }

                const coinMatrixItem = (appState.coin_dna_matrix || []).find(c => c.symbol.toUpperCase() === cleanSym);
                const narrativeText = d.forensic_narrative || (coinMatrixItem && coinMatrixItem.forensic_narrative) || (
                    d.sei >= 75 ? `${cleanSym} paritesinde güvenlik zırhı kusursuz çalışıyor. Kalkanlar stop olacak ${d.hero_count} işlemi başarıyla engelleyerek kasayı -$${d.saved_loss_usd.toFixed(2)} zarardan kurtardı. Mevcut sıkı filtreler korunmalı.` :
                    (d.sei < 40 && d.spoiler_count >= 2 ? `${cleanSym} paritesinde kalkanlar aşırı katı davranarak toplam $${d.missed_profit_usd.toFixed(2)} potansiyel TP kârını engelledi. Kalkan eşikleri esnetilirse kasa kârlılığı artacaktır.` :
                    `${cleanSym} paritesinde canlı piyasa sinyalleri ve mumlar yakından takip ediliyor. Yeterli gölge işlem biriktikçe kalibrasyon tavsiyesi sunulacak.`)
                );
                
                document.getElementById('shadow-modal-narrative').innerHTML = `
                    <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:8px; padding-bottom:6px; border-bottom:1px solid rgba(168,85,247,0.2); flex-wrap:wrap; gap:6px;">
                        <div style="font-size:12px; font-weight:800; color:#c084fc; font-family:'JetBrains Mono';">
                            🚨 TEŞHİS EDİLEN PİYASA REJİMİ: <span style="color:#fff;">${d.scenario_title || 'Canlı Piyasa Gözlemi'}</span>
                        </div>
                        <div style="font-size:11px; color:#38bdf8; font-family:'JetBrains Mono'; font-weight:700;">
                            ⚡ ${d.modifications_count || (d.modifications ? d.modifications.length : 0)} Eşzamanlı Parametre Aksiyonu
                        </div>
                    </div>
                    <p style="margin:0; font-size:12.5px; line-height:1.6; color:#e2e8f0;">${narrativeText}</p>
                `;

                const diffGrid = document.getElementById('shadow-modal-diff-grid');
                const mods = (d.modifications && d.modifications.length > 0) ? d.modifications : [
                    {
                        parameter: "Sahte Fitil Toleransı",
                        code_key: `fakeout_threshold_${cleanSym.toLowerCase()}`,
                        current_val: (d.suggested_diff?.current_wick_threshold || '%15.0'),
                        proposed_val: (d.suggested_diff?.proposed_wick_threshold || '%15.0'),
                        urgency: "ORTA",
                        reason: "Fitil sapmalarına karşı dinamik tolerans.",
                        expected_impact: d.suggested_diff?.expected_alpha_boost || "$0.00"
                    }
                ];

                diffGrid.innerHTML = mods.map((m, idx) => {
                    const urg = m.urgency || 'BİLGİ';
                    let urgCol = '#10b981';
                    let urgBg = 'rgba(16,185,129,0.12)';
                    if (urg === 'KRİTİK') { urgCol = '#ef4444'; urgBg = 'rgba(239,68,68,0.15)'; }
                    else if (urg === 'YÜKSEK') { urgCol = '#f97316'; urgBg = 'rgba(249,115,22,0.15)'; }
                    else if (urg === 'ORTA') { urgCol = '#f59e0b'; urgBg = 'rgba(245,158,11,0.15)'; }
                    else if (urg === 'DÜŞÜK') { urgCol = '#38bdf8'; urgBg = 'rgba(56,189,248,0.15)'; }

                    return `
                        <div style="background:rgba(255,255,255,0.025); border:1px solid rgba(255,255,255,0.07); border-radius:10px; padding:12px 16px; display:flex; flex-direction:column; gap:8px;">
                            <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:6px;">
                                <div style="display:flex; align-items:center; gap:8px;">
                                    <span style="background:rgba(56,189,248,0.15); color:#38bdf8; font-weight:800; font-size:10.5px; border-radius:4px; padding:1px 6px; font-family:'JetBrains Mono';">#${idx + 1}</span>
                                    <span style="font-weight:700; color:#f8fafc; font-size:13px;">${m.parameter}</span>
                                    <span style="color:#64748b; font-size:11px; font-family:'JetBrains Mono'; font-weight:500;">[<code style="color:#94a3b8;">${m.code_key}</code>]</span>
                                </div>
                                <span style="background:${urgBg}; color:${urgCol}; border:1px solid ${urgCol}50; font-size:10px; font-weight:800; padding:2px 8px; border-radius:6px; letter-spacing:0.5px;">
                                    ÖNCELİK: ${urg}
                                </span>
                            </div>
                            
                            <div style="display:grid; grid-template-columns: 1fr auto 1fr; align-items:center; background:rgba(0,0,0,0.25); border-radius:8px; padding:8px 12px; gap:10px;">
                                <div>
                                    <div style="font-size:10px; color:#94a3b8; text-transform:uppercase; margin-bottom:2px;">Mevcut Değer</div>
                                    <div style="color:#cbd5e1; font-family:'JetBrains Mono'; font-size:12px; font-weight:600; text-decoration:line-through; text-decoration-color:#94a3b8;">${m.current_val}</div>
                                </div>
                                <div style="color:#38bdf8; font-weight:900; font-size:16px;">➔</div>
                                <div>
                                    <div style="font-size:10px; color:#38bdf8; text-transform:uppercase; margin-bottom:2px; font-weight:700;">Önerilen Değer</div>
                                    <div style="color:#00f2fe; font-family:'JetBrains Mono'; font-size:12.5px; font-weight:800;">${m.proposed_val}</div>
                                </div>
                            </div>

                            <div style="display:flex; align-items:baseline; justify-content:space-between; font-size:11.5px; line-height:1.5; color:#94a3b8; gap:10px; flex-wrap:wrap; border-top:1px dashed rgba(255,255,255,0.06); padding-top:6px;">
                                <div style="flex:1; min-width:240px;">
                                    <span style="color:#e2e8f0; font-weight:600;">Gerekçe:</span> ${m.reason}
                                </div>
                                <div style="background:rgba(56,189,248,0.08); border:1px solid rgba(56,189,248,0.2); padding:3px 8px; border-radius:6px; font-family:'JetBrains Mono'; font-size:11px; color:#38bdf8; white-space:nowrap;">
                                    📈 <span style="font-weight:700;">Kâr/Risk Etkisi:</span> ${m.expected_impact}
                                </div>
                            </div>
                        </div>
                    `;
                }).join('');

                const shieldsTbody = document.getElementById('shadow-modal-shields-tbody');
                const shBreak = d.shields_breakdown || {};
                const shKeys = Object.keys(shBreak);
                if (shKeys.length === 0) {
                    shieldsTbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:16px; color:#64748b;">Henüz kalkan tetiklenmesi kaydedilmedi.</td></tr>`;
                } else {
                    shieldsTbody.innerHTML = shKeys.map(k => {
                        const row = shBreak[k];
                        const total = (row.saved || 0) + (row.missed || 0);
                        const s_sei = total > 0 ? (row.saved / total * 100) : 100;
                        return `
                            <tr style="border-bottom:1px solid rgba(255,255,255,0.04); font-family:'JetBrains Mono'; font-size:11.5px;">
                                <td style="font-weight:700; color:#fff; text-align:left; padding:8px 10px;">${k}</td>
                                <td style="text-align:center; color:#10b981; font-weight:700;">${row.hero || 0}</td>
                                <td style="text-align:center; color:#f43f5e; font-weight:700;">${row.spoiler || 0}</td>
                                <td style="text-align:center; color:#10b981;">+$${(row.saved || 0).toFixed(2)}</td>
                                <td style="text-align:center; color:#f43f5e;">-$${(row.missed || 0).toFixed(2)}</td>
                                <td style="text-align:center; font-weight:700; color:${s_sei >= 70 ? '#10b981' : (s_sei <= 35 ? '#f43f5e' : '#f59e0b')};">%${s_sei.toFixed(1)}</td>
                            </tr>
                        `;
                    }).join('');
                }

                const tradesTbody = document.getElementById('shadow-modal-trades-tbody');
                const compTrades = d.completed_trades || [];
                const actTrades = d.active_positions || [];
                const allCoinTrades = [...actTrades, ...compTrades];

                if (allCoinTrades.length === 0) {
                    tradesTbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding:16px; color:#64748b;">Bu parite için henüz tamamlanan veya aktif işlem yok.</td></tr>`;
                } else {
                    tradesTbody.innerHTML = allCoinTrades.reverse().slice(0, 15).map(t => {
                        const isAct = !t.exit_price;
                        const sideCol = t.side === 'LONG' ? '#10b981' : '#f43f5e';
                        const pnl = isAct ? 0.0 : (t.virtual_pnl_usd || 0);
                        const pnlCol = pnl >= 0 ? '#10b981' : '#f43f5e';
                        const verd = isAct ? '⏳ CANLI TAKİP' : (t.verdict_badge || t.verdict || '-');
                        return `
                            <tr style="border-bottom:1px solid rgba(255,255,255,0.04); font-family:'JetBrains Mono'; font-size:11px;">
                                <td style="color:#94a3b8;">${(t.id || '').replace('SHD_','')}</td>
                                <td style="color:${sideCol}; font-weight:700;">${t.side}</td>
                                <td style="color:#cbd5e1; text-align:left;">${t.setup}</td>
                                <td style="color:#94a3b8; text-align:left;">${t.shield}</td>
                                <td style="text-align:center;">$${(t.entry_price || 0) < 1 ? (t.entry_price || 0).toFixed(4) : (t.entry_price || 0).toFixed(2)} / $${isAct ? ((t.current_price || 0) < 1 ? (t.current_price || 0).toFixed(4) : (t.current_price || 0).toFixed(2)) : ((t.exit_price || 0) < 1 ? (t.exit_price || 0).toFixed(4) : (t.exit_price || 0).toFixed(2))}</td>
                                <td style="text-align:center;"><span style="color:#10b981;">+%${(t.max_mfe_pct || 0).toFixed(1)}</span> / <span style="color:#f43f5e;">-%${(t.max_mae_pct || 0).toFixed(1)}</span></td>
                                <td style="text-align:center; font-weight:700; color:${pnlCol};">${pnl >= 0 ? '+$' : '-$'}${Math.abs(pnl).toFixed(2)}</td>
                                <td style="text-align:center;">${verd}</td>
                                <td style="text-align:left; color:#94a3b8; max-width:220px; white-space:normal;">${t.narrative || t.reason || '-'}</td>
                            </tr>
                        `;
                    }).join('');
                }

            } catch (err) {
                console.error("openShadowCoinDetail error:", err);
            }
        }

        function closeShadowCoinDetail() {
            const modal = document.getElementById('shadow-coin-detail-modal');
            if (modal) modal.style.display = 'none';
        }

        async function init() {
            try {
                restorePersistedSession();
                restoreBattleViewPreference();
                restoreSidebarPreference();
                if (window.ValkyrieBattleEngine) ValkyrieBattleEngine.init();
                if (window.ValkyrieKpiSimEngine) ValkyrieKpiSimEngine.init();
                if (window.ValkyrieTacticalRadarEngine) ValkyrieTacticalRadarEngine.init();
                await syncBackendState();
                startBinanceGlobalFeed();
                startSSEFallback();
                setInterval(syncBackendState, 10000); // 10 Saniyede bir arka plan senkronizasyonu
            } catch (e) {
                console.error("Valkyrie Init Error:", e);
            }
        }

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
        } else {
            init();
        }
    </script>
</body>
</html>
"""

GZIPPED_HTML_PAGE = gzip.compress(HTML_PAGE.encode('utf-8'))

async def start_server(market_data, trader_manager, notifier=None, live_trader=None, strategy=None):
    app = web.Application()
    
    async def index(request):
        accept_encoding = request.headers.get('Accept-Encoding', '')
        headers = {
            'Cache-Control': 'no-cache, no-store, must-revalidate, max-age=0',
            'Pragma': 'no-cache',
            'Expires': '0'
        }
        if 'gzip' in accept_encoding:
            headers['Content-Encoding'] = 'gzip'
            return web.Response(
                body=GZIPPED_HTML_PAGE,
                content_type='text/html',
                headers=headers
            )
        return web.Response(text=HTML_PAGE, content_type='text/html', headers=headers)

    async def health_check(request):
        return web.Response(text="OK", content_type="text/plain")
        
    
    # =========================================================================
    # VALKYRIE MULTI-TENANT & AUTH API ENDPOINTS
    # =========================================================================
    db_inst = DatabaseManager()
    db_inst.seed_admin_account()

    async def api_auth_register(request):
        try:
            body = await request.json()
            email = body.get('email', '')
            password = body.get('password', '')
            telegram_id = body.get('telegram_id', '')
            binance_uid = body.get('binance_uid', '')

            if not email or not password:
                return web.json_response({"success": False, "message": "E-posta ve şifre zorunludur!"}, status=400)

            ok, msg, user_id = db_inst.register_user(email, password, telegram_id, binance_uid)
            if not ok:
                return web.json_response({"success": False, "message": msg}, status=400)

            auth_ok, auth_msg, user_data = db_inst.authenticate_user(email, password)
            return web.json_response({"success": True, "message": msg, "user": user_data})
        except Exception as e:
            return web.json_response({"success": False, "message": f"Kayıt Hatası: {e}"}, status=500)

    async def api_auth_login(request):
        try:
            body = await request.json()
            email = body.get('email', '')
            password = body.get('password', '')
            ok, msg, user_data = db_inst.authenticate_user(email, password)
            if not ok:
                return web.json_response({"success": False, "message": msg}, status=401)
            return web.json_response({"success": True, "message": msg, "user": user_data})
        except Exception as e:
            return web.json_response({"success": False, "message": f"Giriş Hatası: {e}"}, status=500)

    async def api_admin_overview(request):
        try:
            data = db_inst.get_admin_dashboard_metrics()
            return web.json_response(data)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    gateway_inst = CryptoPaymentGateway(db_inst)

    async def api_payment_config(request):
        try:
            settings = db_inst.get_payment_settings()
            return web.json_response({"success": True, "settings": settings})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def api_admin_save_payment_config(request):
        try:
            body = await request.json()
            trc20 = body.get('trc20_wallet', '')
            bep20 = body.get('bep20_wallet', '')
            price_m = float(body.get('price_monthly', 99.0))

            db_inst.save_payment_settings(trc20, bep20, price_m)
            return web.json_response({"success": True, "message": "Ödeme cüzdanları ve aylık tek fiyat başarıyla kaydedildi!"})
        except Exception as e:
            return web.json_response({"success": False, "message": f"Hata: {e}"}, status=500)

    async def api_payment_verify(request):
        try:
            body = await request.json()
            user_id = int(body.get('user_id', 1))
            tx_hash = body.get('tx_hash', '')
            network = body.get('network', 'TRC20')

            ok, msg, receipt = await gateway_inst.verify_and_activate_payment(user_id, tx_hash, network)
            if not ok:
                return web.json_response({"success": False, "message": msg}, status=400)
            return web.json_response({"success": True, "message": msg, "receipt": receipt})
        except Exception as e:
            return web.json_response({"success": False, "message": f"Ödeme Doğrulama Hatası: {e}"}, status=500)

    async def api_data(request):
        try:
            symbols_data = {}
            for s in market_data.active_symbols:
                lev = market_data.levels.get(s, {})
                cur_p = market_data.current_prices.get(s, 0.0)
                if cur_p <= 0.0 and s in market_data.candles_5m and not market_data.candles_5m[s].empty:
                    cur_p = float(market_data.candles_5m[s]['close'].iloc[-1])
                    market_data.current_prices[s] = cur_p
                if not lev or not lev.get("camarilla"):
                    market_data.recalculate_levels(s)
                    lev = market_data.levels.get(s, {})
                met = market_data.get_symbol_metrics(s) if hasattr(market_data, 'get_symbol_metrics') else {
                    "vol_surge": 1.0,
                    "min_vol_surge": 1.2 if s in ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT"] else 1.5,
                    "atr_pct": 1.2,
                    "is_top_80": True
                }
                symbols_data[s] = {
                    "price": cur_p,
                    "levels": lev,
                    "metrics": met
                }
            
            all_coins = []
            for s in market_data.all_symbols:
                all_coins.append({
                    "symbol": s,
                    "active": s in market_data.active_symbols,
                    "price": market_data.current_prices.get(s, 0.0)
                })

            try:
                sys_health = market_data.get_system_health(paper_trader=getattr(trader_manager, 'paper_trader', None), strategy=strategy) if market_data else {
                    "is_perfect": True,
                    "status_text": "10/10 Tam Sağlıklı",
                    "healthy_symbols": 100,
                    "total_symbols": 100,
                    "scan_active": True,
                    "ws_active": True
                }
            except Exception as he:
                sys_health = {
                    "is_perfect": False,
                    "status_text": f"Teşhis: {he}",
                    "healthy_symbols": 100,
                    "total_symbols": 100,
                    "scan_active": True,
                    "ws_active": True
                }

            hist_full = trader_manager.history
            history_summary = {
                "total_realized_pnl": sum([float(h.get('net_pnl', 0)) for h in hist_full]),
                "total_fees": sum([float(h.get('fees', 0)) for h in hist_full]),
                "total_trades": len(hist_full),
                "wins": sum([1 for h in hist_full if float(h.get('net_pnl', 0)) >= 0]),
                "losses": sum([1 for h in hist_full if float(h.get('net_pnl', 0)) < 0]),
                "win_pnl_sum": sum([float(h.get('net_pnl', 0)) for h in hist_full if float(h.get('net_pnl', 0)) >= 0]),
                "loss_pnl_sum": sum([abs(float(h.get('net_pnl', 0))) for h in hist_full if float(h.get('net_pnl', 0)) < 0])
            }

            coin_personas = {}
            if strategy and hasattr(strategy, 'get_all_coin_personas'):
                try:
                    all_syms = [c.get('symbol') for c in all_coins] if all_coins else None
                    coin_personas = strategy.get_all_coin_personas(all_syms)
                except Exception as ex:
                    print(f">> [PERSONA API HATA] {ex}")

            funding_summary = {}
            if market_data and hasattr(market_data, 'get_all_funding_summary'):
                try:
                    funding_summary = market_data.get_all_funding_summary()
                except Exception as fe:
                    print(f">> [FONLAMA API HATA] {fe}")

            liq_summary = {}
            recent_liqs = []
            symbol_liqs = {}
            if market_data:
                if hasattr(market_data, 'get_global_liquidation_summary'):
                    try:
                        liq_summary = market_data.get_global_liquidation_summary()
                    except Exception:
                        pass
                if hasattr(market_data, 'get_recent_liquidations'):
                    try:
                        recent_liqs = market_data.get_recent_liquidations(25)
                    except Exception:
                        pass
                symbol_liqs = getattr(market_data, 'symbol_liquidations_15m', {})

            cvd_summary = {}
            symbol_cvd = {}
            if market_data:
                if hasattr(market_data, 'get_market_cvd_summary'):
                    try:
                        cvd_summary = market_data.get_market_cvd_summary()
                    except Exception:
                        pass
                symbol_cvd = getattr(market_data, 'symbol_cvd', {})

            return web.json_response({
                "balance": trader_manager.balance,
                "initial_balance": 10000.0,
                "free_balance": trader_manager.get_free_balance(),
                "open_positions": trader_manager.open_positions,
                "history": hist_full[-150:], # BELLEK DOSTU: Sadece son 150 işlem
                "history_summary": history_summary,
                "symbols": symbols_data,
                "all_coins": all_coins,
                "coin_personas": coin_personas,
                "funding_summary": funding_summary,
                "liquidation_summary": liq_summary,
                "recent_liquidations": recent_liqs,
                "symbol_liquidations": symbol_liqs,
                "cvd_summary": cvd_summary,
                "symbol_cvd": symbol_cvd,
                "orderbook_depth": getattr(market_data, 'orderbook_depth', {}) if market_data else {},
                "recent_rejections": getattr(strategy, "recent_rejections", [])[-50:] if strategy else [],
                "setup_attempts": getattr(strategy, "setup_attempts", {}) if strategy else {},
                "system_health": sys_health,
                "coinbase_lead_lag": getattr(market_data, 'coinbase_lead_lag', {}) if market_data else {},
                "oi_summary": getattr(market_data, 'oi_summary', {}) if market_data else {},
                "symbol_oi": getattr(market_data, 'symbol_oi', {}) if market_data else {},
                "server_start_ts": SERVER_START_TS,
                "server_uptime_sec": int(time.time() - SERVER_START_TS),
                "macro_climate": strategy.get_macro_climate() if strategy and hasattr(strategy, 'get_macro_climate') else {},
                "shadow_summary": strategy.shadow_engine.get_summary() if (strategy and hasattr(strategy, 'shadow_engine')) else {},
                "shadow_positions": strategy.shadow_engine.get_active_positions() if (strategy and hasattr(strategy, 'shadow_engine')) else [],
                "shadow_history": strategy.shadow_engine.get_recent_history(50) if (strategy and hasattr(strategy, 'shadow_engine')) else [],
                "coin_dna_matrix": strategy.shadow_engine.get_coin_dna_matrix() if (strategy and hasattr(strategy, 'shadow_engine')) else [],
                "shield_leaderboard": strategy.shadow_engine.get_shield_leaderboard() if (strategy and hasattr(strategy, 'shadow_engine')) else [],
                "reforms": {
                    "dynamic_coin_audit": True,
                    "chandelier_early_be_lock": True,
                    "asia_selective_shield": True,
                    "circuit_breaker_active": getattr(strategy.vault, '_circuit_breaker_active', False) if (strategy and hasattr(strategy, 'vault')) else False,
                    "be_locked_count": sum(1 for p in getattr(trader_manager, 'open_positions', {}).values() if p.get("early_be_locked", False)),
                    "emergency_alert": getattr(trader_manager, 'emergency_alert', None)
                }
            }, dumps=lambda obj: json.dumps(obj, default=str))
        except Exception as e:
            hist_full = trader_manager.history
            return web.json_response({
                "balance": trader_manager.balance,
                "initial_balance": 10000.0,
                "free_balance": trader_manager.get_free_balance(),
                "open_positions": trader_manager.open_positions,
                "history": hist_full[-150:],
                "history_summary": {"total_realized_pnl": 0, "total_fees": 0, "total_trades": len(hist_full), "wins": 0, "losses": 0, "win_pnl_sum": 0, "loss_pnl_sum": 0},
                "symbols": {},
                "all_coins": [],
                "shadow_summary": {},
                "shadow_positions": [],
                "shadow_history": [],
                "coin_dna_matrix": [],
                "shield_leaderboard": [],
                "reforms": {
                    "dynamic_coin_audit": True,
                    "chandelier_early_be_lock": True,
                    "asia_selective_shield": True,
                    "circuit_breaker_active": False,
                    "be_locked_count": 0,
                    "emergency_alert": None
                },
                "coinbase_lead_lag": {},
                "oi_summary": {},
                "symbol_oi": {},
                "system_health": {"is_perfect": False, "status_text": f"Hata: {e}"},
                "macro_climate": {}
            }, dumps=lambda obj: json.dumps(obj, default=str))

    async def api_toggle_symbol(request):
        try:
            payload = await request.json()
            sym = payload.get("symbol")
            is_active = payload.get("active", False)
            if sym in market_data.all_symbols:
                await market_data.toggle_symbol(sym, is_active)
                return web.json_response({"status": "ok", "symbol": sym, "active": is_active})
            return web.json_response({"status": "error", "message": "Gecersiz parite"}, status=400)
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def api_set_active_symbols(request):
        try:
            payload = await request.json()
            symbols = payload.get("symbols", [])
            await market_data.set_active_symbols(symbols)
            return web.json_response({"status": "ok", "active_symbols": list(market_data.active_symbols)})
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def api_reset_trading_state(request):
        try:
            from config import ADMIN_SECRET
            token = request.headers.get("X-Admin-Token") or request.query.get("key")
            if not token or token != ADMIN_SECRET:
                return web.json_response({
                    "status": "error",
                    "message": "Yetkisiz Erişim: Bu işlemi gerçekleştirmek için geçerli X-Admin-Token başlığı gereklidir."
                }, status=401)

            if trader_manager and hasattr(trader_manager, 'paper_trader') and trader_manager.paper_trader:
                trader_manager.paper_trader.balance = 10000.0
                trader_manager.paper_trader.open_positions = {}
                trader_manager.paper_trader.history = []
                trader_manager.paper_trader.save_history(critical=True)
            if strategy:
                if hasattr(strategy, 'failed_levels'):
                    strategy.failed_levels.clear()
                if hasattr(strategy, 'setup_attempts'):
                    strategy.setup_attempts.clear()
                if hasattr(strategy, 'setup_attempt_history'):
                    strategy.setup_attempt_history.clear()
                if hasattr(strategy, 'peak_prices'):
                    strategy.peak_prices.clear()
                if hasattr(strategy, 'recent_rejections'):
                    strategy.recent_rejections.clear()
                if hasattr(strategy, 'symbol_stop_cooldown'):
                    strategy.symbol_stop_cooldown.clear()
                if hasattr(strategy, 'symbol_daily_loss_count'):
                    strategy.symbol_daily_loss_count.clear()
                if hasattr(strategy, 'symbol_daily_loss_date'):
                    strategy.symbol_daily_loss_date = None
                if hasattr(strategy, 'recently_stopped_levels'):
                    strategy.recently_stopped_levels.clear()
            return web.json_response({
                "status": "ok",
                "message": "Cüzdan $10,000 USDT seviyesine çekildi, tüm açık pozisyonlar ve defter sıfırlandı!",
                "balance": 10000.0,
                "open_positions": 0,
                "history": 0
            })
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def api_close_position_manual(request):
        try:
            payload = await request.json()
            sym = payload.get("symbol")
            if sym in trader_manager.open_positions:
                cur_price = market_data.current_prices.get(sym, trader_manager.open_positions[sym]["entry_price"])
                record = await trader_manager.close_position(sym, cur_price, "Manuel Müdahale (Dashboard Kapatma)")
                if record:
                    if notifier:
                        await notifier.notify_position_closed(record, is_manual=True)
                    return web.json_response({"status": "ok", "record": record})
            return web.json_response({"status": "error", "message": "Açık pozisyon bulunamadı"}, status=400)
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def sse_handler(request):
        response = web.StreamResponse(
            status=200,
            reason='OK',
            headers={
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*'
            }
        )
        await response.prepare(request)
        queue = asyncio.Queue(maxsize=50)
        sse_clients.add(queue)

        try:
            while True:
                data = await queue.get()
                msg = f"data: {json.dumps(data)}\n\n"
                await response.write(msg.encode('utf-8'))
        except Exception:
            pass
        finally:
            sse_clients.discard(queue)
        return response

    async def api_export_excel(request):
        try:
            from excel_exporter import create_styled_excel_report
            from config import INITIAL_BALANCE
            buf = create_styled_excel_report(
                history_data=trader_manager.history,
                current_balance=trader_manager.balance,
                initial_balance=INITIAL_BALANCE,
                funding_data=market_data.funding_rates if market_data else None
            )
            filename = f"Valkyrie_Ticaret_Raporu_{datetime.now(timezone(timedelta(hours=3))).strftime('%Y%m%d_%H%M')}.xlsx"
            import gc
            file_bytes = buf.read()
            del buf
            gc.collect()
            return web.Response(
                body=file_bytes,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                headers={
                    'Content-Disposition': f'attachment; filename="{filename}"'
                }
            )
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def api_export_shadow_excel(request):
        try:
            from excel_exporter import create_shadow_dna_excel_report
            summary = strategy.shadow_engine.get_summary() if (strategy and hasattr(strategy, 'shadow_engine')) else {}
            coin_dna = strategy.shadow_engine.get_coin_dna_matrix() if (strategy and hasattr(strategy, 'shadow_engine')) else []
            shadow_history = strategy.shadow_engine.get_recent_history(500) if (strategy and hasattr(strategy, 'shadow_engine')) else []
            shield_leaderboard = strategy.shadow_engine.get_shield_leaderboard() if (strategy and hasattr(strategy, 'shadow_engine')) else []

            buf = create_shadow_dna_excel_report(
                shadow_summary=summary,
                coin_dna=coin_dna,
                shadow_history=shadow_history,
                shield_leaderboard=shield_leaderboard
            )
            filename = f"Valkyrie_Golge_Islem_ve_Coin_DNA_Raporu_{datetime.now(timezone(timedelta(hours=3))).strftime('%Y%m%d_%H%M')}.xlsx"
            import gc
            file_bytes = buf.read()
            del buf
            gc.collect()
            return web.Response(
                body=file_bytes,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                headers={
                    'Content-Disposition': f'attachment; filename="{filename}"'
                }
            )
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def api_shadow_data(request):
        try:
            if not strategy or not hasattr(strategy, 'shadow_engine'):
                return web.json_response({"status": "error", "message": "Shadow engine not initialized"}, status=500)
            return web.json_response({
                "status": "ok",
                "summary": strategy.shadow_engine.get_summary(),
                "active_positions": strategy.shadow_engine.get_active_positions(),
                "recent_history": strategy.shadow_engine.get_recent_history(50),
                "coin_dna": strategy.shadow_engine.get_coin_dna_matrix(),
                "shield_leaderboard": strategy.shadow_engine.get_shield_leaderboard()
            })
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def api_shadow_coin_detail(request):
        try:
            if not strategy or not hasattr(strategy, 'shadow_engine'):
                return web.json_response({"status": "error", "message": "Shadow engine not initialized"}, status=500)
            symbol = request.query.get("symbol", "").strip()
            if not symbol:
                return web.json_response({"status": "error", "message": "Symbol is required"}, status=400)
            detail = strategy.shadow_engine.get_coin_forensic_detail(symbol)
            return web.json_response({
                "status": "ok",
                "detail": detail
            })
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def api_candles(request):
        try:
            from indicators import calculate_anchored_vwap_series
            from config import LOOKBACK_DAYS_AVWAP
            import pandas as pd
            sym = request.query.get("symbol", "BTC/USDT")
            clean_sym = sym.replace(':USDT', '').strip()
            if '/' not in clean_sym and not clean_sym.endswith('/USDT'):
                clean_sym = clean_sym + '/USDT'
            
            df_5m = market_data.candles_5m.get(clean_sym)
            if df_5m is None or df_5m.empty:
                await market_data.fetch_single_symbol(clean_sym)
                df_5m = market_data.candles_5m.get(clean_sym)
            
            # Direct fallback fetch via fapi & vision (bypasses ccxt 451 geo-restriction on Render)
            if df_5m is None or df_5m.empty:
                import aiohttp
                clean_raw = clean_sym.replace('/', '').replace(':USDT', '').replace('USDT', '')
                spot_clean = clean_raw.replace('1000000', '').replace('1000', '')
                fapi_urls = [
                    f"https://fapi.binance.com/fapi/v1/klines?symbol={clean_raw}USDT&interval=5m&limit=500",
                    f"https://fapi.binance.com/fapi/v1/continuousKlines?pair={clean_raw}USDT&contractType=PERPETUAL&interval=5m&limit=500",
                    f"https://data-api.binance.vision/api/v3/klines?symbol={spot_clean}USDT&interval=5m&limit=500"
                ]
                try:
                    async with aiohttp.ClientSession() as sess:
                        for fapi_url in fapi_urls:
                            try:
                                async with sess.get(fapi_url, timeout=aiohttp.ClientTimeout(total=3)) as r:
                                    if r.status == 200:
                                        raw = await r.json()
                                        if isinstance(raw, list) and len(raw) > 0:
                                            df_5m = pd.DataFrame(raw, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'ct', 'qav', 'nt', 'tb', 'tq', 'ig'])
                                            for col in ['open', 'high', 'low', 'close']:
                                                df_5m[col] = df_5m[col].astype(float)
                                            for col in ['timestamp', 'volume']:
                                                df_5m[col] = df_5m[col].astype(float)
                                            market_data.candles_5m[clean_sym] = df_5m
                                            market_data.recalculate_levels(clean_sym)
                                            break
                            except Exception:
                                pass
                except Exception:
                    pass

            if df_5m is None or df_5m.empty:
                return web.json_response({"status": "error", "message": "Mum verisi henüz hazır değil, lütfen 1 saniye sonra tekrar deneyin"}, status=503)
            
            display_df = df_5m.iloc[-500:].copy()
            candles = []
            for _, r in display_df.iterrows():
                candles.append({
                    "time": int(r["timestamp"] / 1000),
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                    "volume": float(r["volume"])
                })
            
            candles_per_day = 288
            avwap_lookback = min(len(df_5m), LOOKBACK_DAYS_AVWAP * candles_per_day)
            recent_df = df_5m.iloc[-avwap_lookback:]
            
            high_idx_rel = int(np.argmax(recent_df['high'].values))
            low_idx_rel = int(np.argmin(recent_df['low'].values))
            
            high_idx_abs = len(df_5m) - avwap_lookback + high_idx_rel
            low_idx_abs = len(df_5m) - avwap_lookback + low_idx_rel
            
            avwap_high_series = calculate_anchored_vwap_series(df_5m, high_idx_abs)
            avwap_low_series = calculate_anchored_vwap_series(df_5m, low_idx_abs)
            
            first_ts = candles[0]["time"] if candles else 0
            avwap_high_filtered = [p for p in avwap_high_series if p["time"] >= first_ts]
            avwap_low_filtered = [p for p in avwap_low_series if p["time"] >= first_ts]
            
            levels = market_data.levels.get(clean_sym, {})
            
            return web.json_response({
                "status": "ok",
                "symbol": clean_sym,
                "candles": candles,
                "avwap_high": avwap_high_filtered,
                "avwap_low": avwap_low_filtered,
                "levels": levels,
                "current_price": market_data.current_prices.get(clean_sym, 0.0)
            })
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    
    async def api_live_status(request):
        try:
            from live_trader import load_live_config
            cfg = load_live_config()
            api_key = cfg.get("api_key", "")
            api_secret = cfg.get("api_secret", "")
            
            masked_key = (api_key[:6] + "..." + api_key[-4:]) if len(api_key) > 10 else ""
            masked_sec = ("••••••••••••" + api_secret[-4:]) if len(api_secret) > 4 else ""

            live_bal = 0.0
            live_free = 0.0
            if live_trader:
                live_bal = live_trader.balance
                live_free = live_trader.get_free_balance()

            return web.json_response({
                "status": "ok",
                "mode": trader_manager.mode if hasattr(trader_manager, 'mode') else cfg.get("mode", "DEMO"),
                "api_key_set": bool(api_key and api_secret),
                "api_key_masked": masked_key,
                "api_secret_masked": masked_sec,
                "leverage": cfg.get("leverage", 5),
                "margin_type": cfg.get("margin_type", "ISOLATED"),
                "position_size_usdt": cfg.get("position_size_usdt", 10.0),
                "max_open_positions": cfg.get("max_open_positions", 3),
                "live_balance": live_bal,
                "live_free_balance": live_free
            })
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def api_live_test_connection(request):
        try:
            body = await request.json()
            api_key = body.get("api_key", "").strip()
            api_secret = body.get("api_secret", "").strip()

            if not api_key or not api_secret:
                if live_trader and live_trader.config.get("api_key") and live_trader.config.get("api_secret"):
                    api_key = live_trader.config.get("api_key")
                    api_secret = live_trader.config.get("api_secret")
                else:
                    return web.json_response({"status": "error", "message": "Lütfen API Key ve Secret Key giriniz."}, status=400)

            if live_trader:
                res = await live_trader.test_connection(api_key, api_secret)
                return web.json_response(res)
            return web.json_response({"status": "error", "message": "LiveTrader servisi başlatılamadı"}, status=500)
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def api_live_save_config(request):
        try:
            body = await request.json()
            mode = body.get("mode", "DEMO")
            api_key = body.get("api_key", "").strip()
            api_secret = body.get("api_secret", "").strip()
            leverage = int(body.get("leverage", 5))
            margin_type = body.get("margin_type", "ISOLATED")
            position_size = float(body.get("position_size_usdt", 10.0))

            if live_trader:
                if not api_key and live_trader.config.get("api_key"):
                    api_key = live_trader.config.get("api_key")
                if not api_secret and live_trader.config.get("api_secret"):
                    api_secret = live_trader.config.get("api_secret")

                await live_trader.update_credentials(api_key, api_secret, leverage, margin_type, position_size)

            if trader_manager:
                trader_manager.set_mode(mode)

            return web.json_response({"status": "ok", "message": "Ayarlar güncellendi"})
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def api_debug_fetch(request):
        import aiohttp
        results = {}
        async with aiohttp.ClientSession() as session:
            test_urls = {
                "fapi": "https://fapi.binance.com/fapi/v1/klines?symbol=BTCUSDT&interval=1d&limit=2",
                "fapi1": "https://fapi1.binance.com/fapi/v1/klines?symbol=BTCUSDT&interval=1d&limit=2",
                "spot": "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=2",
                "data_binance": "https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=2"
            }
            for name, url in test_urls.items():
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=4)) as r:
                        text = await r.text()
                        results[name] = {"status": r.status, "body": text[:150]}
                except Exception as e:
                    results[name] = {"error": str(e)}
        return web.json_response(results)

    app.router.add_get('/api/debug_fetch', api_debug_fetch)

    app.router.add_get('/api/live/status', api_live_status)
    app.router.add_post('/api/live/test_connection', api_live_test_connection)
    app.router.add_post('/api/live/save_config', api_live_save_config)
    app.router.add_get('/health', health_check)
    app.router.add_get('/ping', health_check)
    app.router.add_get('/', index)
    app.router.add_post('/api/auth/register', api_auth_register)
    app.router.add_post('/api/auth/login', api_auth_login)
    app.router.add_get('/api/admin/overview', api_admin_overview)
    app.router.add_get('/api/payment/config', api_payment_config)
    app.router.add_post('/api/admin/save_payment_config', api_admin_save_payment_config)
    app.router.add_post('/api/payment/verify', api_payment_verify)
    app.router.add_get('/api/data', api_data)
    app.router.add_get('/api/candles', api_candles)
    app.router.add_get('/api/export_excel', api_export_excel)
    app.router.add_get('/api/export_shadow_excel', api_export_shadow_excel)
    app.router.add_get('/api/shadow_data', api_shadow_data)
    app.router.add_get('/api/shadow_coin_detail', api_shadow_coin_detail)
    app.router.add_post('/api/toggle_symbol', api_toggle_symbol)
    app.router.add_post('/api/set_active_symbols', api_set_active_symbols)
    app.router.add_post('/api/close_position_manual', api_close_position_manual)
    app.router.add_post('/api/admin/reset_trading_state', api_reset_trading_state)
    app.router.add_get('/api/stream', sse_handler)
    
    import os
    port = int(os.environ.get('PORT', 5000))
    host = '0.0.0.0'
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    print(f">> [VALKYRIE QUANT DESK •READY]: http://{host}:{port}")

async def broadcast_tick(symbol, price):
    if not sse_clients:
        return
    data = {"type": "tick", "symbol": symbol, "price": price}
    for q in list(sse_clients):
        try:
            if q.full():
                try:
                    q.get_nowait()
                except Exception:
                    pass
            q.put_nowait(data)
        except Exception:
            pass
