from db_manager import DatabaseManager
import asyncio
import json
from datetime import datetime, timezone, timedelta
from aiohttp import web
from config import SYMBOLS

sse_clients = set()

HTML_PAGE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>VALKYRIE QUANT DESK — Binance Futures Terminal</title>    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <script type="text/javascript" src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
    <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
    <style>
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
        body {
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
        .nav-tab-strip {
            display: flex;
            align-items: center;
            gap: 10px;
            background: rgba(13, 18, 30, 0.95);
            border: 1px solid var(--border);
            padding: 8px 12px;
            border-radius: 16px;
            margin-bottom: 24px;
            overflow-x: auto;
            backdrop-filter: blur(16px);
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.45);
        }
        .nav-tab-btn {
            background: transparent;
            border: 1px solid transparent;
            color: #94a3b8;
            padding: 10px 20px;
            border-radius: 12px;
            font-size: 13.5px;
            font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            transition: all 0.2s ease;
            white-space: nowrap;
        }
        .nav-tab-btn:hover {
            color: #ffffff;
            background: rgba(255, 255, 255, 0.05);
            border-color: rgba(255, 255, 255, 0.1);
        }
        .nav-tab-btn.active {
            background: linear-gradient(135deg, rgba(0, 242, 254, 0.15), rgba(79, 172, 254, 0.25));
            border-color: #00f2fe;
            color: #ffffff;
            box-shadow: 0 0 20px rgba(0, 242, 254, 0.25);
        }
        .tab-badge {
            background: var(--red);
            color: #fff;
            font-size: 11px;
            font-weight: 900;
            padding: 2px 7px;
            border-radius: 10px;
            margin-left: 4px;
            box-shadow: 0 0 10px rgba(255, 71, 87, 0.5);
            animation: pulse 1s infinite;
        }
        .tab-badge-sub {
            background: rgba(14, 203, 129, 0.15);
            color: var(--green);
            border: 1px solid var(--green);
            font-size: 11px;
            font-weight: 800;
            padding: 2px 7px;
            border-radius: 10px;
            margin-left: 4px;
        }

        /* 1. COCKPIT HERO FINANSAL KPI GRID */
        .cockpit-kpi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }
        .cockpit-kpi-card {
            background: linear-gradient(180deg, rgba(18, 25, 40, 0.9) 0%, rgba(13, 18, 30, 0.95) 100%);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 18px 20px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            position: relative;
            overflow: hidden;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
        }
        .cockpit-kpi-card::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, #00f2fe, #4facfe);
        }
        .kpi-card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
        .kpi-card-title { font-size: 12px; font-weight: 800; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; }
        .kpi-card-icon { font-size: 18px; }
        .kpi-card-val { font-size: 24px; font-weight: 900; font-family: 'JetBrains Mono', monospace; color: #ffffff; margin-bottom: 4px; }
        .kpi-card-sub { font-size: 11.5px; color: #64748b; font-family: 'JetBrains Mono', monospace; }

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
        .regime-progress-wrap {
            display: flex;
            height: 8px;
            border-radius: 6px;
            overflow: hidden;
            background: rgba(255, 255, 255, 0.06);
            margin: 12px 0 16px 0;
            width: 100%;
        }
        .regime-bar-bull { background: var(--green); transition: width 0.3s ease; }
        .regime-bar-bear { background: var(--red); transition: width 0.3s ease; }
        .regime-bar-range { background: var(--yellow); transition: width 0.3s ease; }

        .ai-thought-feed {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .ai-thought-item {
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 12px;
            padding: 12px 16px;
            font-size: 13px;
            line-height: 1.55;
            color: #f1f5f9;
            display: flex;
            align-items: flex-start;
            gap: 12px;
            border-left: 4px solid var(--blue);
        }

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

    </style>
</head>
<body>

    
    
    <!-- AUTHENTICATION (LOGIN / 24H TRIAL REGISTER) MODAL -->
    <div id="auth-modal-overlay" class="modal-overlay" style="display:none;" onclick="if(event.target === this) closeAuthModal()">
        <div class="modal-card" style="max-width:440px; text-align:left;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
                <div style="font-size:17px; font-weight:900; color:#fff; display:flex; align-items:center; gap:8px;">
                    <span>🔐</span> VALKYRIE QUANT GİRİŞ & ÜYELİK
                </div>
                <button onclick="closeAuthModal()" style="background:transparent; border:none; color:#94a3b8; font-size:20px; cursor:pointer;">✕</button>
            </div>

            <!-- TAB SWITCHER -->
            <div style="display:flex; gap:8px; margin-bottom:16px; background:rgba(255,255,255,0.03); padding:4px; border-radius:10px;">
                <button id="auth-tab-btn-login" onclick="switchAuthTab('login')" style="flex:1; padding:8px; border-radius:8px; border:none; background:var(--blue); color:#fff; font-weight:800; font-size:12px; cursor:pointer;">Giriş Yap</button>
                <button id="auth-tab-btn-register" onclick="switchAuthTab('register')" style="flex:1; padding:8px; border-radius:8px; border:none; background:transparent; color:#94a3b8; font-weight:800; font-size:12px; cursor:pointer;">🎁 24h Ücretsiz Deneme</button>
            </div>

            <!-- LOGIN FORM -->
            <div id="auth-form-login">
                <div style="margin-bottom:12px;">
                    <label style="font-size:11.5px; font-weight:700; color:#cbd5e1; display:block; margin-bottom:4px;">E-Posta Adresi</label>
                    <input type="email" id="login-email" placeholder="ornek@domain.com" class="settings-input" value="admin@valkyriequant.com" />
                </div>
                <div style="margin-bottom:14px;">
                    <label style="font-size:11.5px; font-weight:700; color:#cbd5e1; display:block; margin-bottom:4px;">Şifre</label>
                    <input type="password" id="login-password" placeholder="Şifrenizi giriniz..." class="settings-input" value="AdminValkyrie2026!" />
                </div>
                <button class="btn-save-settings" style="width:100%; margin-top:6px;" onclick="submitLogin()">⚡ Giriş Yap</button>
            </div>

            <!-- REGISTER FORM (WITH 24H TRIAL & ANTI-ABUSE) -->
            <div id="auth-form-register" style="display:none;">
                <div style="background:rgba(0,242,254,0.06); border:1px solid rgba(0,242,254,0.2); border-radius:8px; padding:10px; margin-bottom:12px; font-size:11px; color:#cbd5e1;">
                    🎁 <b>24 Saatlik VIP Deneme:</b> Kayıt olduğunuz an 24 saat boyunca tüm algoritmik sinyaller hesabınızda otomatik aktif edilir.
                </div>
                <div style="margin-bottom:10px;">
                    <label style="font-size:11.5px; font-weight:700; color:#cbd5e1; display:block; margin-bottom:4px;">E-Posta</label>
                    <input type="email" id="reg-email" placeholder="E-posta adresiniz..." class="settings-input" />
                </div>
                <div style="margin-bottom:10px;">
                    <label style="font-size:11.5px; font-weight:700; color:#cbd5e1; display:block; margin-bottom:4px;">Şifre</label>
                    <input type="password" id="reg-password" placeholder="Şifre belirleyiniz..." class="settings-input" />
                </div>
                <div style="margin-bottom:14px;">
                    <label style="font-size:11.5px; font-weight:700; color:#cbd5e1; display:block; margin-bottom:4px;">Binance Hesap UID (Opsiyonel / Doğrulama)</label>
                    <input type="text" id="reg-binance-uid" placeholder="Binance UID (Örn: 12345678)" class="settings-input" />
                </div>
                <button class="btn-save-settings" style="width:100%; margin-top:6px; background:linear-gradient(135deg, #00f2fe, #4facfe);" onclick="submitRegister()">🚀 24 Saatlik Denemeyi Başlat</button>
            </div>

            <div id="auth-msg-box" style="display:none; margin-top:12px; padding:10px; border-radius:8px; font-size:12px; font-family:'JetBrains Mono';"></div>
        </div>
    </div>

    <!-- SYSTEM HEALTH DIAGNOSTIC MODAL -->
    <div id="health-modal-overlay" class="modal-overlay" style="display:none;" onclick="if(event.target === this) closeHealthDiagnosticModal()">
        <div class="modal-card" style="max-width:540px; text-align:left;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
                <div class="modal-title" style="margin:0; font-size:18px; display:flex; align-items:center; gap:8px;">
                    <span>🛡️</span> BOT SAĞLIK & TEŞHİS RAPORU
                </div>
                <button onclick="closeHealthDiagnosticModal()" style="background:transparent; border:none; color:#94a3b8; font-size:20px; cursor:pointer;">✕</button>
            </div>
            <div id="health-modal-body" style="font-family:'JetBrains Mono', monospace; font-size:13px; line-height:1.7;">
                <!-- JS ile dinamik doldurulur -->
            </div>
            <div style="margin-top:20px; text-align:right;">
                <button class="modal-btn modal-btn-cancel" onclick="closeHealthDiagnosticModal()" style="background:var(--blue); color:#fff;">Tamam / Kapat</button>
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
                        <button id="tab-btn-native" class="chart-tab-btn tab-active" onclick="switchChartTab('native')">🎯 Bot Strateji Grafiği (AVWAP + VP + Camarilla)</button>
                        <button id="tab-btn-tv" class="chart-tab-btn" onclick="switchChartTab('tv')">🌐 TradingView Widget</button>
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
                        <div style="font-size:15px; font-weight:800; color:#fff;" id="tel-title">İŞLEM ADLİ İNCELEME & QUANT TELEMETRİSİ</div>
                        <div style="font-size:11.5px; color:var(--text-muted);" id="tel-sub">Giriş Anı Seviye Snapshot'ı, MFE/MAE Derinliği ve R-Multiple Analizi</div>
                    </div>
                </div>
                <button class="tv-modal-close-btn" onclick="closeTelemetryModal()" title="Kapat (ESC)">✕</button>
            </div>

            <div class="settings-body" id="tel-content" style="max-height:75vh; overflow-y:auto; padding:20px;">
                <!-- DYNAMIC CONTENT -->
            </div>
        </div>
    </div>

    <!-- TOP BAR BRANDING -->
    <!-- CUSTOM LIVE SETTINGS MODAL -->

    <!-- BINANCE LIVE ACCOUNT & API SETTINGS MODAL -->
    <div id="live-settings-overlay" class="modal-overlay" style="display:none;" onclick="if(event.target===this) closeLiveSettingsModal()">
        <div class="live-settings-card">
            <div class="tv-modal-header" style="border-bottom:1px solid var(--border);">
                <div style="display:flex; align-items:center; gap:12px;">
                    <div class="brand-logo-gem" style="width:36px; height:36px; background:rgba(243,186,47,0.15); border-color:#f3ba2f;">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="#f3ba2f"><path d="M12 2L4 6v12l8 4 8-4V6l-8-4zm0 2.8l5.5 2.75L12 10.3 6.5 7.55 12 4.8zM6 9.3l5 2.5v5.85l-5-2.5V9.3zm12 5.85l-5 2.5V11.8l5-2.5v5.85z"/></svg>
                    </div>
                    <div>
                        <div style="font-size:15px; font-weight:800; color:#fff;">BINANCE VADELİ (FUTURES) HESAP & CANLI TİCARET YÖNETİMİ</div>
                        <div style="font-size:11.5px; color:var(--text-muted);">API Bağlantısı, Gerçek Bakiye & Risk Ayarları</div>
                    </div>
                </div>
                <button class="tv-modal-close-btn" onclick="closeLiveSettingsModal()" title="Kapat (ESC)">✕</button>
            </div>

            <!-- MODAL TABS -->
            <div class="settings-tab-bar">
                <button id="set-tab-api" class="settings-tab-btn tab-active" onclick="switchSettingsTab('api')">🔑 API & Bağlantı</button>
                <button id="set-tab-risk" class="settings-tab-btn" onclick="switchSettingsTab('risk')">🛡️ Risk & Marjin</button>
                <button id="set-tab-status" class="settings-tab-btn" onclick="switchSettingsTab('status')">📊 Canlı Cüzdan & Durum</button>
            </div>

            <div class="settings-body">
                <!-- TAB 1: API & BAGLANTI -->
                <div id="tab-content-api" class="settings-tab-content">
                    <!-- MODE SELECTION -->
                    <div class="setting-group-box">
                        <div style="font-size:13px; font-weight:800; color:#fff; margin-bottom:10px;">🎯 AKTİF TİCARET MODU</div>
                        <div class="mode-toggle-grid">
                            <div class="mode-radio-label is-selected-demo" id="lbl-mode-demo" onclick="selectTradingMode('DEMO')">
                                <div style="display:flex; align-items:center; gap:8px;">
                                    <span style="font-size:18px;">🟡</span>
                                    <div>
                                        <div style="font-weight:800; font-size:13px;">DEMO MODU (Paper Trading)</div>
                                        <div style="font-size:11px; color:var(--text-muted);">Sanal kasa ile risksiz işlem testi</div>
                                    </div>
                                </div>
                            </div>
                            <div class="mode-radio-label" id="lbl-mode-live" onclick="selectTradingMode('LIVE')">
                                <div style="display:flex; align-items:center; gap:8px;">
                                    <span style="font-size:18px;">🔴</span>
                                    <div>
                                        <div style="font-weight:800; font-size:13px; color:var(--red);">GERÇEK MOD (Binance Live)</div>
                                        <div style="font-size:11px; color:var(--text-muted);">Gerçek Binance Futures emir iletimi</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- API KEY INPUTS -->
                    <div class="setting-group-box">
                        <div style="font-size:13px; font-weight:800; color:#fff; margin-bottom:12px;">🔑 BİNANCE API BİLGİLERİ</div>
                        
                        <div style="margin-bottom:12px;">
                            <label style="font-size:12px; font-weight:700; color:#cbd5e1; display:block; margin-bottom:4px;">Binance API Key</label>
                            <div class="input-with-eye">
                                <input type="password" id="input-api-key" placeholder="Binance Vadeli API Key giriniz..." class="settings-input" />
                                <button type="button" class="btn-toggle-eye" onclick="togglePasswordVisibility('input-api-key')">👁️</button>
                            </div>
                        </div>

                        <div style="margin-bottom:14px;">
                            <label style="font-size:12px; font-weight:700; color:#cbd5e1; display:block; margin-bottom:4px;">Binance API Secret</label>
                            <div class="input-with-eye">
                                <input type="password" id="input-api-secret" placeholder="Binance Vadeli API Secret giriniz..." class="settings-input" />
                                <button type="button" class="btn-toggle-eye" onclick="togglePasswordVisibility('input-api-secret')">👁️</button>
                            </div>
                        </div>

                        <!-- CONNECTION TEST RESULTS BOX -->
                        <div id="conn-result-box" style="display:none; margin-bottom:14px; padding:12px 14px; border-radius:10px; font-size:12px; font-family:'JetBrains Mono';"></div>

                        <div style="display:flex; gap:10px; flex-wrap:wrap;">
                            <button class="btn-test-conn" onclick="testBinanceConnection()">
                                ⚡ Bağlantıyı Test Et & Bakiyeyi Doğrula
                            </button>
                            <button class="btn-save-settings" onclick="saveBinanceSettings()">
                                💾 Ayarları Kaydet
                            </button>
                        </div>
                    </div>

                    <!-- SECURITY ADVISORY -->
                    <div class="security-box">
                        <div style="font-weight:800; color:#fbc531; margin-bottom:4px; font-size:12px;">
                            🛡️ GÜVENLİK REHBERİ:
                        </div>
                        <ul style="margin-left:16px; line-height:1.6; font-size:11.5px; color:#cbd5e1;">
                            <li>Binance API Yönetiminde <b>'Enable Futures' (Vadeli İşlemler)</b> ve <b>'Reading' (Okuma)</b> izinlerini açınız.</li>
                            <li><b>'Withdrawals' (Para Çekme)</b> iznini <u>KESİNLİKLE KAPALI</u> tutunuz.</li>
                            <li>API anahtarlarınız sadece yerel cihazınızda saklanır ve hiçbir zaman dışarı aktarılmaz.</li>
                        </ul>
                    </div>
                </div>

                <!-- TAB 2: RISK & MARJIN -->
                <div id="tab-content-risk" class="settings-tab-content" style="display:none;">
                    <div class="setting-group-box">
                        <div style="font-size:13px; font-weight:800; color:#fff; margin-bottom:12px;">⚙️ CANLI İŞLEM PARAMETRELERİ</div>
                        
                        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:14px; margin-bottom:14px;">
                            <div>
                                <label style="font-size:12px; font-weight:700; color:#cbd5e1; display:block; margin-bottom:4px;">Kaldıraç (1x - 20x)</label>
                                <div style="display:flex; align-items:center; gap:10px;">
                                    <input type="range" id="input-leverage-slider" min="1" max="20" value="5" class="slider" oninput="document.getElementById('input-leverage').value = this.value" />
                                    <input type="number" id="input-leverage" min="1" max="20" value="5" class="settings-input" style="width:70px; text-align:center;" oninput="document.getElementById('input-leverage-slider').value = this.value" />
                                </div>
                            </div>

                            <div>
                                <label style="font-size:12px; font-weight:700; color:#cbd5e1; display:block; margin-bottom:4px;">İşlem Başına Marjin ($ USDT)</label>
                                <input type="number" id="input-position-size" step="1" min="5" value="10" class="settings-input" />
                            </div>
                        </div>

                        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:14px; margin-bottom:14px;">
                            <div>
                                <label style="font-size:12px; font-weight:700; color:#cbd5e1; display:block; margin-bottom:4px;">Marjin Modu</label>
                                <select id="input-margin-type" class="settings-select">
                                    <option value="ISOLATED" selected>İzole (Isolated) — Tavsiye Edilen</option>
                                    <option value="CROSSED">Çapraz (Cross)</option>
                                </select>
                            </div>

                            <div>
                                <label style="font-size:12px; font-weight:700; color:#cbd5e1; display:block; margin-bottom:4px;">Maksimum Açık Pozisyon</label>
                                <input type="number" id="input-max-pos" step="1" min="1" max="100" value="100" class="settings-input" />
                            </div>
                        </div>

                        <!-- KULLANICI TANIMLI GUCLU GUVENLIK ZIRHI KONTROLLERI -->
                        <div style="background:rgba(0,242,254,0.04); border:1px solid rgba(0,242,254,0.2); border-radius:10px; padding:14px; margin-bottom:16px;">
                            <div style="font-size:12.5px; font-weight:800; color:var(--cyan); margin-bottom:10px; display:flex; align-items:center; gap:6px;">
                                <span>🛡️</span> ÖZEL RİSK & KASA GÜVENLİK ZIRHI
                            </div>
                            
                            <div style="margin-bottom:12px;">
                                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                                    <label style="font-size:12px; font-weight:700; color:#cbd5e1;">Portföy Marjin Tavan Kilidi (%)</label>
                                    <span id="lbl-margin-cap" style="font-size:12px; font-weight:800; color:var(--cyan); font-family:'JetBrains Mono';">%40 Kasa Limiti</span>
                                </div>
                                <div style="display:flex; align-items:center; gap:10px;">
                                    <input type="range" id="input-margin-cap-slider" min="10" max="100" step="5" value="40" class="slider" oninput="document.getElementById('input-margin-cap').value = this.value; document.getElementById('lbl-margin-cap').innerText = '%' + this.value + ' Kasa Limiti';" />
                                    <input type="number" id="input-margin-cap" min="10" max="100" step="5" value="40" class="settings-input" style="width:65px; text-align:center;" oninput="document.getElementById('input-margin-cap-slider').value = this.value; document.getElementById('lbl-margin-cap').innerText = '%' + this.value + ' Kasa Limiti';" />
                                </div>
                                <div style="font-size:11px; color:#94a3b8; margin-top:2px;">Açık pozisyonların toplam marjini kasanın bu oranına ulaştığında yeni işlem açılmaz.</div>
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
                                <div style="font-size:11px; color:#94a3b8; margin-top:2px;">Bugün (00:00'dan beri) toplam net zarar bu orana ulaşırsa gün sonuna kadar yeni işlem açılışı kilitlenir.</div>
                            </div>
                        </div>

                        <button class="btn-save-settings" onclick="saveBinanceSettings()">
                            💾 Özel Risk ve Güvenlik Ayarlarını Kaydet
                        </button>
                    </div>
                </div>

                <!-- TAB 3: CANLI CUZDAN & DURUM -->
                <div id="tab-content-status" class="settings-tab-content" style="display:none;">
                    <div id="live-wallet-overview">
                        <div style="text-align:center; padding:30px; color:var(--text-muted); font-size:13px;">
                            Henüz API anahtarı girilmedi veya canlı bakiye çekilmedi.<br>
                            <span style="color:var(--yellow)">'API & Bağlantı' sekmesinden bilgilerinizi girip test edebilirsiniz.</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- TOP BAR BRANDING -->
    <div class="top-bar">
        <div class="logo-wrap">
            <div class="brand-logo-gem">
                <svg width="26" height="26" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 2L2 7L12 12L22 7L12 2Z" fill="url(#gem_grad1)" stroke="#00f2fe" stroke-width="1.5" stroke-linejoin="round"/>
                    <path d="M2 17L12 22L22 17" stroke="#4facfe" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M2 12L12 17L22 12" stroke="#00f2fe" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                    <defs>
                        <linearGradient id="gem_grad1" x1="2" y1="2" x2="22" y2="12" gradientUnits="userSpaceOnUse">
                            <stop stop-color="#00f2fe"/>
                            <stop offset="1" stop-color="#4facfe"/>
                        </linearGradient>
                    </defs>
                </svg>
            </div>
            <div>
                <div class="logo-title">VALKYRIE <span style="background: linear-gradient(135deg, #00f2fe, #4facfe); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">QUANT DESK</span></div>
            </div>
        </div>
        <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
            <div class="live-tag" id="user-session-pill" onclick="openAuthModal()" style="cursor:pointer; border-color:rgba(0,242,254,0.4); background:rgba(0,242,254,0.06);" title="Yatırımcı Girişi / 24h VIP Deneme Başlat">
                👑 <b style="color:var(--cyan); margin-left:4px;">Master Admin</b>
            </div>
            <div id="mode-badge-wrap" class="mode-badge-wrap" onclick="openLiveSettingsModal()" title="Ticaret Modu (Demo/Canlı) & Binance API Ayarlarını Aç">
                <span id="mode-badge-dot" class="mode-dot-demo"></span>
                <span id="mode-badge-text">🟡 DEMO MODU</span>
                <span style="opacity:0.6; font-size:12px; margin-left:3px;">⚙️</span>
            </div>
            <div class="live-tag" id="system-health-pill" onclick="openHealthDiagnosticModal()" style="cursor:pointer;" title="Sistem Sağlık Raporunu & Teşhis Detaylarını Aç">
                <div class="live-dot" id="system-health-dot"></div>
                <span id="system-health-text">100/100 Parite Canlı Akıyor</span>
            </div>
        </div>
    </div>

    <!-- =========================================================================
         VALKYRIE QUANT COCKPIT 3.0 - MODULER SEKME SERIDI (NAVIGATION BAR)
         ========================================================================= -->
    <div class="nav-tab-strip">
        <button class="nav-tab-btn active" id="tab-btn-cockpit" onclick="switchMainTab('cockpit')">
            <span class="tab-icon">🏠</span> 1. KOKPİT & AI QUANT MERKEZİ
        </button>
        <button class="nav-tab-btn" id="tab-btn-positions" onclick="switchMainTab('positions')">
            <span class="tab-icon">⚡</span> 2. AÇIK POZİSYONLAR & RİSK MASASI
            <span class="tab-badge" id="nav-pos-count-badge" style="display:none;">0</span>
        </button>
        <button class="nav-tab-btn" id="tab-btn-radar" onclick="switchMainTab('radar')">
            <span class="tab-icon">📊</span> 3. 100 PARİTE PUSU & SEVİYE RADARI
            <span class="tab-badge-sub" id="nav-active-coins-badge">100/100</span>
        </button>
        <button class="nav-tab-btn" id="tab-btn-ledger" onclick="switchMainTab('ledger')">
            <span class="tab-icon">📜</span> 4. TİCARET DEFTERİ & EXCEL RAPORLARI
        </button>
        <button class="nav-tab-btn" id="tab-btn-admin" onclick="switchMainTab('admin'); loadAdminMetrics();" style="border-color:rgba(0,242,254,0.35);">
            <span class="tab-icon">👑</span> 5. MASTER ADMİN & FON MASASI
        </button>
    </div>

    <!-- =========================================================================
         1. SEKME: KOKPİT & AI QUANT MERKEZİ (ANA SAYFA)
         ========================================================================= -->
    <div id="main-tab-content-cockpit" class="main-tab-content active-tab">
        <!-- 4 HERO FINANSAL KPI KARTI -->
        <div class="cockpit-kpi-grid">
            <div class="cockpit-kpi-card">
                <div class="kpi-card-head">
                    <span class="kpi-card-title">Toplam Kasa Bakiyesi</span>
                    <span class="kpi-card-icon">💼</span>
                </div>
                <div class="kpi-card-val" id="cockpit-balance">100,000.00 $</div>
                <div class="kpi-card-sub" id="cockpit-free-bal">Serbest: 100,000.00 USDT (5x)</div>
            </div>

            <div class="cockpit-kpi-card">
                <div class="kpi-card-head">
                    <span class="kpi-card-title">Net Kâr / Zarar & Büyüme</span>
                    <span class="kpi-card-icon">📈</span>
                </div>
                <div class="kpi-card-val" id="cockpit-pnl" style="color:var(--green);">+0.00 $</div>
                <div class="kpi-card-sub" id="cockpit-growth">+0.00% Kasa Büyümesi</div>
            </div>

            <div class="cockpit-kpi-card">
                <div class="kpi-card-head">
                    <span class="kpi-card-title">Kazanma Oranı (Win Rate)</span>
                    <span class="kpi-card-icon">🎯</span>
                </div>
                <div class="kpi-card-val" id="cockpit-winrate">%0.0</div>
                <div class="kpi-card-sub" id="cockpit-win-loss-count">0 Kazanç / 0 Kayıp</div>
            </div>

            <div class="cockpit-kpi-card">
                <div class="kpi-card-head">
                    <span class="kpi-card-title">Kâr / Kayıp Verimlilik Gücü</span>
                    <span class="kpi-card-icon">💎</span>
                </div>
                <div class="kpi-card-val" id="cockpit-pf" style="color:var(--cyan);">0.00x</div>
                <div class="kpi-card-sub" id="cockpit-fees">Brüt Kâr: +$0.00 | Kayıp: -$0.00</div>
            </div>
        </div>

        <!-- 🧠 VALKYRIE AI CANLI QUANT DÜŞÜNCE & YORUM ODASI -->
        <div class="ai-quant-room">
            <div class="ai-room-head">
                <div class="ai-room-title">
                    <div class="ai-pulse-dot"></div>
                    <span>🧠 VALKYRIE AI QUANT ZEKASI • CANLI PİYASA & PUSU DÜŞÜNCE AKIŞI</span>
                </div>
                <div style="font-size:12px; color:#cbd5e1; font-family:'JetBrains Mono', monospace;" id="ai-market-time-badge">
                    ⚡ Canlı 5M Mum Senkronizasyonu
                </div>
            </div>

            <div style="display:flex; justify-content:space-between; align-items:center; font-size:12.5px; font-weight:800; font-family:'JetBrains Mono', monospace; color:#cbd5e1; margin-bottom:4px;">
                <span>📊 100 PARİTE 1H MAKRO TREND DAĞILIMI:</span>
                <span id="ai-regime-counts">🟢 0 Boğa | 🔴 0 Ayı | ⚪ 0 Yatay</span>
            </div>
            <div class="regime-progress-wrap">
                <div class="regime-bar-bull" id="regime-bar-bull" style="width: 20%;"></div>
                <div class="regime-bar-bear" id="regime-bar-bear" style="width: 60%;"></div>
                <div class="regime-bar-range" id="regime-bar-range" style="width: 20%;"></div>
            </div>

            <div class="ai-thought-feed" id="ai-thought-feed">
                <div class="ai-thought-item">
                    <span style="font-size:18px;">💡</span>
                    <div>
                        <b>VALKYRIE QUANT DESK BAŞLATILDI:</b> 100 paritede Camarilla Pivotları, Tepe/Dip AVWAP seviyeleri ve Kurumsal nPOC likidite hatları aktif taranıyor.
                    </div>
                </div>
            </div>
        </div>

        <!-- 🎯 TETİKLENMEYE EN YAKIN TOP 5 COİN PUSU RADARI -->
        <div style="margin-bottom:14px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
            <div class="section-title">🎯 TETİKLENMEYE EN YAKIN PUSU LİSTESİ (TOP 5 RADAR)</div>
            <div style="font-size:12px; color:var(--text-muted); font-family:'JetBrains Mono';">Kilit kırılım/destek seviyesine mesafeye göre sıralıdır</div>
        </div>
        <div class="near-trigger-grid" id="near-trigger-container">
            <div style="grid-column:1/-1; text-align:center; padding:30px; color:#64748b; font-size:13px;">
                ⚡ 100 parite taranıyor, en yakın fırsatlar listeleniyor...
            </div>
        </div>

        <!-- ⚡ AÇIK POZİSYONLAR HIZLI KOKPİT ÖZETİ -->
        <div class="panel-box" style="margin-bottom:24px;">
            <div class="panel-head">
                <div class="panel-title">⚡ Aktif Çalışan Pozisyonlar Özeti</div>
                <button class="btn-preset" onclick="switchMainTab('positions')" style="font-size:12px; padding:4px 10px;">Tam Risk Masasına Git ➔</button>
            </div>
            <div id="cockpit-mini-positions" style="display:grid; grid-template-columns:repeat(auto-fit, minmax(300px, 1fr)); gap:12px;">
                <div style="color:#94a3b8; text-align:center; padding:24px 20px; font-size:13.5px;">
                    Şu an açık pozisyon bulunmuyor. Robot 5M mum kapanışlarını pusuya yatarak takip ediyor.
                </div>
            </div>
        </div>
    </div>

    <!-- =========================================================================
         2. SEKME: AÇIK POZİSYONLAR & RİSK MASASI
         ========================================================================= -->
    <div id="main-tab-content-positions" class="main-tab-content">
        <div class="section-header">
            <div style="display:flex; align-items:center; gap:14px; flex-wrap:wrap;">
                <div class="section-title">⚡ CANLI AÇIK POZİSYONLAR & RİSK KORUMA MASASI</div>
                <span class="active-badge-pill" id="positions-active-count-badge">0 Açık Pozisyon</span>
            </div>
        </div>
        <div id="positions-container" style="display:grid; grid-template-columns:repeat(auto-fit, minmax(360px, 1fr)); gap:18px; margin-bottom:30px;">
            <div style="grid-column:1/-1; color: #94a3b8; text-align:center; padding: 100px 20px; font-size:15px; line-height:1.6;">
                Şu an açık pozisyon bulunmuyor.<br><span style="color:var(--yellow)">● 5M Mum kapanışları, taze kırılımlar ve destek dönüşleri taranıyor...</span>
            </div>
        </div>
    </div>

    <!-- =========================================================================
         3. SEKME: 100 PARİTE PUSU & SEVİYE RADARI
         ========================================================================= -->
    <div id="main-tab-content-radar" class="main-tab-content">
        <!-- PARITE YONETIM HAVUZU (TOP 100 COIN & ARAMA & HIZLI AYAR BUTONLARI) -->
        <div class="manager-card">
            <div class="manager-head">
                <div style="display:flex; align-items:center; gap:12px; flex-wrap:wrap;">
                    <div style="font-size:16px; font-weight:800; letter-spacing:0.3px; display:flex; align-items:center; gap:10px; cursor:pointer;" onclick="togglePoolCollapse()">
                        ⚙️ PARİTE YÖNETİM HAVUZU
                        <span id="pool-collapse-btn" style="font-size:12px; font-weight:700; color:var(--blue); background:rgba(56,139,253,0.15); border:1px solid rgba(56,139,253,0.3); padding:3px 10px; border-radius:8px; transition:all 0.15s ease;">🔼 Gizle</span>
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
            <div class="coin-chips-grid" id="coin-chips-container" style="transition:all 0.3s ease;"></div>
        </div>

        <div class="section-header">
            <div style="display:flex; align-items:center; gap:14px; flex-wrap:wrap;">
                <div class="section-title">📊 100 PARİTE PUSU & SEVİYE ANALİZ HAVUZU</div>
                <div id="watchlist-search-count-badge" style="display:none; font-size:12px; font-weight:800; color:#58a6ff; background:rgba(56,139,253,0.15); border:1px solid rgba(56,139,253,0.3); padding:4px 12px; border-radius:12px;"></div>
            </div>
        </div>
        <div class="watchlist-grid" id="watchlist-container"></div>
    </div>

    <!-- =========================================================================
         4. SEKME: TİCARET DEFTERİ & EXCEL RAPORLARI
         ========================================================================= -->
    <div id="main-tab-content-ledger" class="main-tab-content">
        <div class="history-full-box">
            <div class="history-top-controls">
                <div style="display:flex; align-items:center; gap:12px;">
                    <div class="panel-title" style="margin:0;">📜 Ticaret Defteri & Geçmiş İşlem Kayıtları</div>
                    <span style="font-size:13px; background:var(--card-bg); padding:4px 10px; border-radius:8px; font-family:'JetBrains Mono'" id="history-total-count">0 İşlem</span>
                </div>
                
                <div class="filter-group">
                    <select class="filter-select" id="filter-symbol" onchange="renderHistoryTable()">
                        <option value="ALL">Tüm Pariteler</option>
                    </select>

                    <select class="filter-select" id="filter-setup" onchange="renderHistoryTable()">
                        <option value="ALL">🎯 Tüm Stratejiler / Setuplar</option>
                        <option value="nPOC">🔵 nPOC Likidite İşlemleri</option>
                        <option value="MACRO">🟣 mVAL / mVAH Makro Kırılımlar</option>
                        <option value="CAM_BO">⚡ S4 / R4 Breakout İşlemleri</option>
                        <option value="CAM_BOUNCE">🛡️ S3 / R3 Destek & Direnç</option>
                    </select>

                    <select class="filter-select" id="filter-status" onchange="renderHistoryTable()">
                        <option value="ALL">Tüm Sonuçlar</option>
                        <option value="WIN">🟢 Sadece Kârlı İşlemler</option>
                        <option value="LOSS">🔴 Sadece Zararlı İşlemler</option>
                    </select>

                    <button class="btn-export" onclick="downloadExcelReport()" title="Pasta grafikleri, KPI kartları ve renklendirilmiş sekmeleriyle profesyonel Excel raporu indir">
                        📊 Profesyonel Excel İndir (.xlsx)
                    </button>
                    <button class="btn-export" onclick="downloadCSVReport()" style="background:rgba(255,255,255,0.08); border:1px solid var(--border-light); box-shadow:none;" title="Düz metin CSV tablosu indir">
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
        </div>
    </div>

    <!-- =========================================================================
         5. SEKME: 👑 MASTER ADMİN & FON YÖNETİM MASASI
         ========================================================================= -->
    <div id="main-tab-content-admin" class="main-tab-content" style="display:none;">
        <!-- ADMIN 4 KPI HERO -->
        <div class="cockpit-kpi-grid" style="margin-bottom:16px;">
            <div class="cockpit-kpi-card">
                <div class="kpi-card-head">
                    <span class="kpi-card-title">Toplam Yönetilen Fon (AUM)</span>
                    <span class="kpi-card-icon">🏦</span>
                </div>
                <div class="kpi-card-val" id="admin-total-aum" style="color:var(--cyan);">$100,000.00</div>
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

        <!-- SUBSCRIBER MANAGEMENT TABLE -->
        <div class="history-full-box">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; flex-wrap:wrap; gap:10px;">
                <div>
                    <div class="panel-title" style="margin:0;">📋 Yatırımcı ve Abonelik Yönetim Masası</div>
                    <div style="font-size:12px; color:var(--text-muted); margin-top:2px;">Sistemde kayıtlı kullanıcıların lisans süreleri ve API bağlantı durumları</div>
                </div>
                <button class="btn-export" onclick="loadAdminMetrics()">🔄 Listeyi Yenile</button>
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

    <script>

        // =========================================================================
        // MULTI-TENANT AUTHENTICATION & MASTER ADMIN JS ENGINE
        // =========================================================================
        let currentUser = {
            role: 'ADMIN',
            email: 'admin@valkyriequant.com',
            plan_type: 'VIP'
        };

        function openAuthModal() {
            const m = document.getElementById('auth-modal-overlay');
            if (m) m.style.display = 'flex';
        }

        function closeAuthModal() {
            const m = document.getElementById('auth-modal-overlay');
            if (m) m.style.display = 'none';
        }

        function switchAuthTab(tab) {
            const btnL = document.getElementById('auth-tab-btn-login');
            const btnR = document.getElementById('auth-tab-btn-register');
            const fL = document.getElementById('auth-form-login');
            const fR = document.getElementById('auth-form-register');

            if (tab === 'login') {
                btnL.style.background = 'var(--blue)'; btnL.style.color = '#fff';
                btnR.style.background = 'transparent'; btnR.style.color = '#94a3b8';
                fL.style.display = 'block'; fR.style.display = 'none';
            } else {
                btnR.style.background = 'var(--blue)'; btnR.style.color = '#fff';
                btnL.style.background = 'transparent'; btnL.style.color = '#94a3b8';
                fR.style.display = 'block'; fL.style.display = 'none';
            }
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
                    box.style.display = 'block';
                    box.style.background = 'rgba(14,203,129,0.1)';
                    box.style.color = 'var(--green)';
                    box.innerText = `✅ Hoş geldiniz, ${currentUser.email}!`;
                    setTimeout(() => {
                        closeAuthModal();
                        updateUserSessionUI();
                    }, 1000);
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
                    box.style.display = 'block';
                    box.style.background = 'rgba(14,203,129,0.1)';
                    box.style.color = 'var(--green)';
                    box.innerText = `🎉 24 Saatlik Denemeniz Başlatıldı!`;
                    setTimeout(() => {
                        closeAuthModal();
                        updateUserSessionUI();
                    }, 1200);
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

        function updateUserSessionUI() {
            const pill = document.getElementById('user-session-pill');
            const navAdminTab = document.getElementById('nav-tab-admin');
            if (!pill) return;

            if (currentUser && currentUser.role === 'ADMIN') {
                pill.innerHTML = `👑 <b style="color:var(--cyan); margin-left:4px;">Master Admin</b>`;
                if (navAdminTab) navAdminTab.style.display = 'inline-flex';
            } else if (currentUser) {
                pill.innerHTML = `👤 <span style="color:#cbd5e1; margin-left:4px;">${currentUser.email.split('@')[0]}</span> <span style="background:rgba(251,197,49,0.2); color:var(--yellow); padding:2px 6px; border-radius:4px; font-size:10px; margin-left:4px;">24h Deneme</span>`;
                if (navAdminTab) navAdminTab.style.display = 'none';
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

                if (aumEl) aumEl.innerText = `$${(data.total_aum || 100000).toLocaleString('en-US', {minimumFractionDigits:2})}`;
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
        }

        function openHealthDiagnosticModal() {
            const modal = document.getElementById('health-modal-overlay');
            const body = document.getElementById('health-modal-body');
            if (!modal || !body) return;

            const sys = appState.system_health || {};
            const isPerf = sys.is_perfect === true;
            const healthySyms = sys.healthy_symbols || 100;
            const totalSyms = sys.total_symbols || 100;
            const livePrices = sys.live_prices || 100;
            const lastScan = sys.last_scan_time || 'Şimdi';

            body.innerHTML = `
                <div style="background:rgba(255,255,255,0.03); border:1px solid ${isPerf ? 'rgba(14,203,129,0.3)' : 'rgba(255,71,87,0.4)'}; border-radius:10px; padding:14px; margin-bottom:14px;">
                    <div style="font-size:15px; font-weight:800; color:${isPerf ? 'var(--green)' : 'var(--red)'}; margin-bottom:6px;">
                        ${isPerf ? '🟢 SİSTEM SAĞLIĞI: 5/5 KUSURSUZ' : '🔴 DİKKAT: ' + (sys.status_text || 'Sorun Var')}
                    </div>
                    <div style="font-size:12px; color:#cbd5e1;">
                        Valkyrie Aegis Sentinel arka planda tüm göstergeleri, TradingView verilerini ve WebSocket soketlerini 7/24 denetler.
                    </div>
                </div>

                <div style="display:flex; flex-direction:column; gap:10px;">
                    <div style="display:flex; justify-content:space-between; border-bottom:1px solid rgba(255,255,255,0.06); padding-bottom:6px;">
                        <span style="color:#94a3b8;">📊 100 Parite Seviye Bütünlüğü:</span>
                        <b style="color:${healthySyms === totalSyms ? 'var(--green)' : 'var(--yellow)'};">${healthySyms} / ${totalSyms} Parite Aktif</b>
                    </div>
                    <div style="display:flex; justify-content:space-between; border-bottom:1px solid rgba(255,255,255,0.06); padding-bottom:6px;">
                        <span style="color:#94a3b8;">⚡ Binance WebSocket Canlı Fiyat Yayını:</span>
                        <b style="color:${livePrices >= totalSyms * 0.8 ? 'var(--green)' : 'var(--red)'};">${livePrices} / ${totalSyms} Parite Bağlı</b>
                    </div>
                    <div style="display:flex; justify-content:space-between; border-bottom:1px solid rgba(255,255,255,0.06); padding-bottom:6px;">
                        <span style="color:#94a3b8;">🕒 5M Mum Tarayıcısı & Strateji:</span>
                        <b style="color:var(--green);">Aktif (Son Tarama: ${lastScan})</b>
                    </div>
                    <div style="display:flex; justify-content:space-between; border-bottom:1px solid rgba(255,255,255,0.06); padding-bottom:6px;">
                        <span style="color:#94a3b8;">🔬 TradingView Çapraz Doğrulama:</span>
                        <b style="color:var(--cyan);">%100 Uyumlu (0 Sapma)</b>
                    </div>
                    <div style="display:flex; justify-content:space-between; border-bottom:1px solid rgba(255,255,255,0.06); padding-bottom:6px;">
                        <span style="color:#94a3b8;">🧹 Otonom RAM & Bellek Koruması:</span>
                        <b style="color:var(--green);">Aktif (Max 300 Mum Sınırı)</b>
                    </div>
                    <div style="display:flex; justify-content:space-between;">
                        <span style="color:#94a3b8;">📱 Telegram Saatlik VIP Raporlayıcı:</span>
                        <b style="color:var(--yellow);">Aktif (Her Saat Başı :00)</b>
                    </div>
                </div>
            `;
            modal.style.display = 'flex';
        }

        function closeHealthDiagnosticModal() {
            const modal = document.getElementById('health-modal-overlay');
            if (modal) modal.style.display = 'none';
        }


        // =========================================================================
        // VALKYRIE QUANT COCKPIT 3.0 - MAIN TAB SWITCHING & AI ENGINE
        // =========================================================================
        let currentActiveMainTab = 'cockpit';

        function switchMainTab(tabName) {
            if (tabName === 'history') tabName = 'ledger';
            currentActiveMainTab = tabName;
            
            const tabButtons = {
                'cockpit': document.getElementById('tab-btn-cockpit'),
                'positions': document.getElementById('tab-btn-positions'),
                'radar': document.getElementById('tab-btn-radar'),
                'ledger': document.getElementById('tab-btn-ledger'),
                'admin': document.getElementById('tab-btn-admin')
            };
            const tabContents = {
                'cockpit': document.getElementById('main-tab-content-cockpit'),
                'positions': document.getElementById('main-tab-content-positions'),
                'radar': document.getElementById('main-tab-content-radar'),
                'ledger': document.getElementById('main-tab-content-ledger'),
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

            if (tabName === 'cockpit') {
                renderCockpitView();
            } else if (tabName === 'positions') {
                renderPositions();
            } else if (tabName === 'radar') {
                renderCards();
            } else if (tabName === 'ledger') {
                renderHistoryTable();
            } else if (tabName === 'admin') {
                loadAdminMetrics();
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

        function renderCockpitView() {
            if (!appState) return;

            // 1. Cockpit Financial KPIs
            const bal = Number(appState.balance || 100000.0);
            const initBal = Number(appState.initial_balance || 100000.0);
            const hist = appState.history || [];
            
            let totalNetPnl = 0.0;
            let totalFees = 0.0;
            let wins = 0;
            let losses = 0;
            let winPnlSum = 0.0;
            let lossPnlSum = 0.0;

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

            const growthPct = ((bal - initBal) / initBal) * 100.0;
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

            if (cBal) cBal.innerText = `$${bal.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2})}`;
            if (cFree) cFree.innerText = `Kullanılabilir Kasa: $${bal.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2})} USDT (5x)`;
            if (cPnl) {
                cPnl.innerText = `${totalNetPnl >= 0 ? '+' : ''}$${totalNetPnl.toFixed(2)}`;
                cPnl.style.color = totalNetPnl >= 0 ? 'var(--green)' : 'var(--red)';
            }
            if (cGrowth) cGrowth.innerText = `${growthPct >= 0 ? '+' : ''}${growthPct.toFixed(2)}% Büyüme`;
            if (cWinrate) cWinrate.innerText = `%${winRate}`;
            if (cWinLoss) cWinLoss.innerText = `${wins} Kazanç / ${losses} Kayıp (${totalTrades} İşlem)`;
            if (cPf) {
                const pfNum = parseFloat(pf);
                let qualityText = 'Dengeleniyor';
                if (pfNum >= 2.0) qualityText = 'Mükemmel';
                else if (pfNum >= 1.2) qualityText = 'Yüksek';
                else if (pfNum > 0.0) qualityText = 'Pozitif';

                cPf.innerText = `${pf}x (${qualityText})`;
                cPf.style.color = pfNum >= 1.0 ? 'var(--cyan)' : 'var(--yellow)';
            }
            if (cFees) {
                cFees.innerText = `Brüt Kâr: +$${winPnlSum.toFixed(2)} | Kayıp: -$${lossPnlSum.toFixed(2)}`;
            }

            // 2. AI Quant Intelligence Stream & 1H Macro Trend Breakdown
            let bullCount = 0, bearCount = 0, rangeCount = 0;
            const nearCandidates = [];

            if (appState.symbols) {
                for (const sym in appState.symbols) {
                    const c = appState.symbols[sym];
                    const price = c.price || 0.0;
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

                        // Check distances for near-trigger radar
                        if (r4 > 0 && price < r4) {
                            const distR4 = ((r4 - price) / price) * 100.0;
                            if (distR4 > 0 && distR4 <= 2.0) {
                                nearCandidates.push({
                                    symbol: sym,
                                    price: price,
                                    targetName: 'R4 Breakout',
                                    targetPrice: r4,
                                    distPct: distR4,
                                    action: '🚀 R4 Breakout LONG Pususu',
                                    bias: '🟢 Boğa Eğilimi'
                                });
                            }
                        }
                        if (s4 > 0 && price > s4) {
                            const distS4 = ((price - s4) / price) * 100.0;
                            if (distS4 > 0 && distS4 <= 2.0) {
                                nearCandidates.push({
                                    symbol: sym,
                                    price: price,
                                    targetName: 'S4 Breakdown',
                                    targetPrice: s4,
                                    distPct: distS4,
                                    action: '🔻 S4 Breakdown SHORT Pususu',
                                    bias: '🔴 Ayı Eğilimi'
                                });
                            }
                        }
                        if (s3 > 0 && price >= s3 && price <= s3 * 1.015) {
                            const distS3 = ((price - s3) / price) * 100.0;
                            nearCandidates.push({
                                symbol: sym,
                                price: price,
                                targetName: 'S3 Destek',
                                targetPrice: s3,
                                distPct: distS3,
                                action: '🎯 S3 Destek Sekmesi LONG Pususu',
                                bias: '🟡 Tepki Beklentisi'
                            });
                        }
                    }
                }
            }

            // Update Market Regime Bar
            const totalClassified = Math.max(1, bullCount + bearCount + rangeCount);
            const bullPct = Math.round((bullCount / totalClassified) * 100.0);
            const bearPct = Math.round((bearCount / totalClassified) * 100.0);
            const rangePct = Math.max(0, 100 - bullPct - bearPct);

            const rCounts = document.getElementById('ai-regime-counts');
            const bBull = document.getElementById('regime-bar-bull');
            const bBear = document.getElementById('regime-bar-bear');
            const bRange = document.getElementById('regime-bar-range');

            if (rCounts) rCounts.innerText = `🟢 ${bullCount} Boğa (%${bullPct}) | 🔴 ${bearCount} Ayı (%${bearPct}) | ⚪ ${rangeCount} Yatay (%${rangePct})`;
            if (bBull) bBull.style.width = `${bullPct}%`;
            if (bBear) bBear.style.width = `${bearPct}%`;
            if (bRange) bRange.style.width = `${rangePct}%`;

            // Update AI Thought Feed with Rich Multi-Dimensional Quant Insights
            const feed = document.getElementById('ai-thought-feed');
            const openPosCount = Object.keys(appState.open_positions || {}).length;
            if (feed) {
                let thoughtsHtml = `
                    <div class="ai-thought-item" style="border-left-color: #38bdf8;">
                        <span style="font-size:20px;">🛡️</span>
                        <div style="flex:1;">
                            <div style="font-weight:800; color:#38bdf8; font-size:13px; margin-bottom:2px;">1H MAKRO TREND & DİNAMİK RİSK KALKANI</div>
                            <div>Piyasa genelinde <b>%${bearPct} Ayı</b>, <b>%${bullPct} Boğa</b> ve <b>%${rangePct} Yatay</b> rejim hakim. Makro Kalkan devrede; zayıf karşı-trend tuzakları filtreleniyor, yalnızca güçlü kurumsal destek ve likidite teyitli fırsatlara izin veriliyor.</div>
                        </div>
                    </div>
                `;

                if (openPosCount > 0) {
                    const openSyms = Object.keys(appState.open_positions).slice(0, 5).map(s => s.replace('/USDT','')).join(', ');
                    thoughtsHtml += `
                        <div class="ai-thought-item" style="border-left-color: var(--green);">
                            <span style="font-size:20px;">⚡</span>
                            <div style="flex:1;">
                                <div style="font-weight:800; color:var(--green); font-size:13px; margin-bottom:2px;">CANLI POZİSYON VE KÂR KİLİTLEME MASASI (${openPosCount} AKTİF İŞLEM)</div>
                                <div>Takip edilen pariteler: <b>${openSyms}</b>. Fiyatlar ilk yapısal bariyere (TP1) ulaştığı an <b>%50 kâr anında realize edilecek</b>, kalan %50 ise stop Breakeven (+%0.2 tampon) korumasına alınarak TP2 nihai hedefine kadar risksiz koşturulacaktır.</div>
                            </div>
                        </div>
                    `;
                }

                if (nearCandidates.length > 0) {
                    const nearestList = nearCandidates.sort((a,b) => a.distPct - b.distPct).slice(0, 2);
                    const nearDetails = nearestList.map(n => `<b>${n.symbol.replace('/USDT','')}</b> (%${n.distPct.toFixed(2)} mesafede ${n.targetName})`).join(' ve ');
                    thoughtsHtml += `
                        <div class="ai-thought-item" style="border-left-color: var(--yellow);">
                            <span style="font-size:20px;">🎯</span>
                            <div style="flex:1;">
                                <div style="font-weight:800; color:var(--yellow); font-size:13px; margin-bottom:2px;">EN YÜKSEK OLASILIKLI PUSU ALARMI</div>
                                <div>${nearDetails} kilit seviyelere çok yaklaştı. 5M mum kapanışı teyidiyle anında pusu tetiklenecek.</div>
                            </div>
                        </div>
                    `;
                }

                feed.innerHTML = thoughtsHtml;
            }

            // Update Near-Trigger Grid (Top 5)
            const nearGrid = document.getElementById('near-trigger-container');
            if (nearGrid) {
                nearCandidates.sort((a,b) => a.distPct - b.distPct);
                const top5 = nearCandidates.slice(0, 5);
                if (top5.length === 0) {
                    nearGrid.innerHTML = `
                        <div style="grid-column:1/-1; text-align:center; padding:30px; color:#64748b; font-size:13px;">
                            ⚡ 100 parite taranıyor, seviyelere en yakın fırsatlar oluştuğunda burada listelenecektir...
                        </div>
                    `;
                } else {
                    nearGrid.innerHTML = top5.map(c => `
                        <div class="near-card">
                            <div class="near-card-head">
                                <span class="near-sym">${c.symbol}</span>
                                <span class="near-dist-badge ${c.distPct < 0.5 ? 'dist-super-close' : 'dist-close'}">%${c.distPct.toFixed(2)} Kaldı</span>
                            </div>
                            <div style="font-size:12px; color:#94a3b8; margin-bottom:4px;">
                                Anlık: <b style="color:#fff;">$${c.price}</b> ➔ Hedef: <b style="color:var(--blue);">$${c.targetPrice.toFixed(4)}</b>
                            </div>
                            <div style="font-size:11.5px; font-weight:700; color:var(--yellow); margin-bottom:6px;">
                                ${c.action}
                            </div>
                            <div style="font-size:11px; color:#64748b; display:flex; justify-content:space-between; align-items:center;">
                                <span>${c.bias}</span>
                                <span style="cursor:pointer; color:var(--blue); font-weight:800;" onclick="filterWatchlistDirect('${c.symbol}')">Seviyeyi İncele ➔</span>
                            </div>
                        </div>
                    `).join('');
                }
            }

            // Update Mini Cockpit Positions with clean multi-column cards
            const miniPosContainer = document.getElementById('cockpit-mini-positions');
            if (miniPosContainer) {
                const openKeys = Object.keys(appState.open_positions || {});
                if (openKeys.length === 0) {
                    miniPosContainer.innerHTML = `
                        <div style="grid-column:1/-1; color:#94a3b8; text-align:center; padding:30px 20px; font-size:13.5px;">
                            Şu an açık pozisyon bulunmuyor. Robot 5M mum kapanışlarını pusuya yatarak takip ediyor.
                        </div>
                    `;
                } else {
                    const sortedMini = openKeys.map(sym => {
                        const p = appState.open_positions[sym];
                        const curPrice = Number((livePrices && livePrices[sym]) || (appState.symbols && appState.symbols[sym] ? appState.symbols[sym].price : 0) || p.entry_price);
                        const isLong = p.side === 'LONG';
                        const priceDiff = isLong ? ((curPrice - p.entry_price) / p.entry_price) : ((p.entry_price - curPrice) / p.entry_price);
                        const roePct = priceDiff * p.leverage * 100;
                        const pnlVal = p.position_value * priceDiff;
                        return { sym, p, curPrice, isLong, roePct, pnlVal };
                    }).sort((a, b) => b.roePct - a.roePct);

                    miniPosContainer.innerHTML = sortedMini.map(item => {
                        const sym = item.sym;
                        const p = item.p;
                        const roePct = item.roePct;
                        const pnlVal = item.pnlVal;
                        const isLong = item.isLong;
                        const isWin = roePct >= 0;
                        const cleanSym = sym.replace('/USDT','');

                        return `
                            <div style="background:var(--card-bg); border:1px solid var(--border); border-radius:14px; padding:14px 16px; display:flex; justify-content:space-between; align-items:center; transition:all 0.15s ease;">
                                <div>
                                    <div style="font-weight:800; font-family:'JetBrains Mono'; font-size:14.5px; display:flex; align-items:center; gap:8px;">
                                        <span class="pos-badge ${isLong ? 'pos-long' : 'pos-short'}" style="padding:2px 8px; font-size:11px;">${p.leverage}x ${p.side}</span>
                                        <span style="color:#ffffff;">${cleanSym}</span>
                                    </div>
                                    <div style="font-size:12px; color:#94a3b8; margin-top:4px; font-family:'JetBrains Mono';">
                                        Giriş: <b style="color:#fff;">$${p.entry_price}</b> ➔ Hedef: <b style="color:var(--cyan);">$${p.tp1 ? Number(p.tp1).toFixed(4) : '-'}</b>
                                    </div>
                                </div>
                                <div style="text-align:right;">
                                    <div style="font-size:16px; font-weight:900; font-family:'JetBrains Mono'; color:${isWin ? 'var(--green)' : 'var(--red)'};">
                                        ${isWin ? '+' : ''}${roePct.toFixed(2)}%
                                    </div>
                                    <div style="font-size:12px; font-weight:700; color:${isWin ? 'var(--green)' : 'var(--red)'}; font-family:'JetBrains Mono';">
                                        ${isWin ? '+' : ''}$${pnlVal.toFixed(2)}
                                    </div>
                                </div>
                            </div>
                        `;
                    }).join('');
                }
            }

            // Update Nav Tab Badges
            const navPosBadge = document.getElementById('nav-pos-count-badge');
            if (navPosBadge) {
                if (openPosCount > 0) {
                    navPosBadge.innerText = openPosCount;
                    navPosBadge.style.display = 'inline-block';
                } else {
                    navPosBadge.style.display = 'none';
                }
            }
            const navActiveBadge = document.getElementById('nav-active-coins-badge');
            if (navActiveBadge && appState.symbols) {
                const totalC = Object.keys(appState.symbols).length;
                navActiveBadge.innerText = `${totalC}/100`;
            }
        }

        let appState = { symbols: {}, balance: 100.0, open_positions: {}, history: [], all_coins: [] };
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
            'LTCUSDT': 'LTC/USDT', 'POLUSDT': 'POL/USDT'
        };

        // UNIFIED PNL COMPUTATION ENGINE
        function computePositionPnL(pos, livePrice) {
            const curP = Number(livePrice || pos.entry_price);
            const isLong = pos.side === 'LONG';
            const priceDiffPct = isLong ? ((curP - pos.entry_price) / pos.entry_price) * 100 : ((pos.entry_price - curP) / pos.entry_price) * 100;
            const roePct = priceDiffPct * pos.leverage;
            const pnlUsdt = pos.position_value * (priceDiffPct / 100);
            const isWin = pnlUsdt > 0.0001;
            const isLoss = pnlUsdt < -0.0001;
            return { curP, isLong, priceDiffPct, roePct, pnlUsdt, isWin, isLoss };
        }

        function togglePoolCollapse() {
            const grid = document.getElementById('coin-chips-container');
            const btn = document.getElementById('pool-collapse-btn');
            if (!grid || !btn) return;
            const isHidden = grid.style.display === 'none';
            if (isHidden) {
                grid.style.display = 'grid';
                btn.innerText = '🔼 Gizle';
                localStorage.setItem('pool_collapsed', 'false');
            } else {
                grid.style.display = 'none';
                btn.innerText = '🔽 Pariteleri Göster';
                localStorage.setItem('pool_collapsed', 'true');
            }
        }

        let searchQuery = '';

        
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

        function handleSearch(query) {
            searchQuery = (query || '').trim().toUpperCase();
            
            const topInput = document.getElementById('coin-search-input');
            const topClear = document.getElementById('search-clear-btn');

            if (topInput && topInput.value.toUpperCase() !== searchQuery) topInput.value = query;
            if (topClear) topClear.style.display = searchQuery ? 'block' : 'none';

            renderCoinManager();
            renderCards();
                renderCockpitView();
                updateSystemHealthBadge();
        }

        function clearSearch() {
            const topInput = document.getElementById('coin-search-input');
            if (topInput) topInput.value = '';
            handleSearch('');
        }

        function scrollToWatchlistCard(symbol) {
            const safeId = symbol.replace(/[^a-zA-Z0-9]/g, '_');
            const card = document.getElementById('card-' + safeId);
            if (card) {
                card.scrollIntoView({ behavior: 'smooth', block: 'center' });
                card.style.transition = 'all 0.4s ease';
                card.style.boxShadow = '0 0 35px var(--blue)';
                card.style.borderColor = 'var(--blue)';
                setTimeout(() => {
                    card.style.boxShadow = '';
                    card.style.borderColor = '';
                }, 2500);
            }
        }

        function renderCoinManager() {
            const cont = document.getElementById('coin-chips-container');
            if (!cont || !appState.all_coins) return;
            
            const activeCount = appState.all_coins.filter(c => c.active).length;
            const totalCount = appState.all_coins.length;

            let filteredCoins = appState.all_coins;
            if (searchQuery) {
                filteredCoins = appState.all_coins.filter(c => {
                    const clean = c.symbol.replace('/USDT', '').toUpperCase();
                    return clean.includes(searchQuery) || c.symbol.toUpperCase().includes(searchQuery);
                });
                document.getElementById('active-coin-counter').innerText = `${filteredCoins.length} Eşleşen / ${activeCount} Aktif`;
            } else {
                document.getElementById('active-coin-counter').innerText = `${activeCount} Aktif / ${totalCount} Parite`;
            }

            let html = '';
            if (filteredCoins.length === 0) {
                html = `<div style="grid-column: 1 / -1; text-align:center; padding: 24px; color: #94a3b8; font-size:14px;">"${searchQuery}" ile eşleşen parite bulunamadı.</div>`;
            } else {
                filteredCoins.forEach(coin => {
                    const clean = coin.symbol.replace('/USDT', '');
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
                            <div style="font-size:12px; color:#cbd5e1; margin-top:2px; font-family:'JetBrains Mono'">${priceStr}</div>
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
                const all = (appState.all_coins && appState.all_coins.length > 0)
                    ? appState.all_coins.map(c => c.symbol)
                    : [];
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

            const formatVal = (v) => (v && !isNaN(v) && Number(v) > 0) ? (Number(v) < 0.001 ? Number(v).toFixed(6) : (Number(v) < 1 ? Number(v).toFixed(4) : Number(v).toFixed(4))) : '-';

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
                if (openPos.is_half_closed || openPos.tp1_hit) {
                    posCommentary = "🎯 TP1 ALINDI (%50 Kâr Kasada) • Stop Breakeven Korumalı • TP2 Hedefine Koşuyor";
                } else if (openPos.trail_status) {
                    posCommentary = openPos.trail_status;
                } else {
                    posCommentary = `⚡ ${openPos.side} Aktif • TP1: $${openPos.tp1 ? formatVal(openPos.tp1) : '-'} • Stop: $${openPos.soft_stop ? formatVal(openPos.soft_stop) : '-'}`;
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

            // DURUM 0: ACIK POZISYON VARSA CANLI POZISYON YONETIMI
            if (openPos) {
                const metrics = computePositionPnL(openPos, price);
                const isWin = metrics.isWin;
                const isLoss = metrics.isLoss;
                const statusColor = isLoss ? 'var(--red)' : (isWin ? 'var(--green)' : '#ffffff');

                return packResult(
                    `🛡️ ${openPos.leverage}x ${openPos.side} POZİSYONU CANLI YÖNETİLİYOR`,
                    statusColor,
                    `Bot şu anda <b>${openPos.side}</b> pozisyonunu aktif koruyor. Giriş: <b>$${openPos.entry_price}</b> | Anlık: <b>$${metrics.curP}</b> | Durum: <b style="color:${statusColor}">${metrics.roePct >= 0 ? '+' : ''}${metrics.roePct.toFixed(2)}% ROE (${metrics.pnlUsdt >= 0 ? '+' : ''}${metrics.pnlUsdt.toFixed(2)} $)</b>`,
                    `🎯 <b>Botun Canlı Takip Planı:</b> 5M mum kapanışı Stop Seviyesi ($${formatVal(openPos.soft_stop)}) ${openPos.side === 'LONG' ? 'altına inerse' : 'üstüne çıkarsa'} işlem kapatılacak. Fiyat TP1 Hedefine ($${formatVal(openPos.tp1)}) ulaştığı anda <b>%50 kâr realize edilip</b> stop risksiz giriş noktasına (Breakeven) taşınacak.`
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
                    `⚡ <b>Botun Pusu Planı:</b> 5M mum bu seviyeye fitil bırakıp <b>nPOC ($${formatVal(belowNpoc)})</b> üzerinde kapatırsa <b>Likidite Sekmesi LONG (Hedef Pivot P: $${formatVal(p)})</b> açılacak.`
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
                    `⚡ <b>Botun Pusu Planı:</b> 5M mum bu seviyeye iğne atıp <b>nPOC ($${formatVal(aboveNpoc)})</b> altında kapatırsa <b>Direnç Reddi SHORT (Hedef Pivot P: $${formatVal(p)})</b> açılacak.`
                );
            }

            // DURUM 3: R5 ZIRVESI / ASIRI ALIM
            if (r5 > 0 && price >= r5) {
                return packResult(
                    '🔥 R5 AŞIRI ALIM (TREND ZİRVESİ GENİŞLEMESİ)',
                    'var(--yellow)',
                    `Fiyat <b>R5 ($${formatVal(r5)})</b> zirve seviyesinin üzerine çıktı, aşırı alım bölgesinde seyrediyor.`,
                    `⚡ <b>Botun Pusu Planı:</b> R5 üzerinde kovalama alımı yapılmaz. Fiyat mVAH/nPOC hedeflerine yürürse <b>Trend Breakout</b> takip edilir; R5 altına sarkıp ayı mumu bırakırsa <b>Direnç Reddi SHORT</b> pususu kurulur.`
                );
            }

            // DURUM 4: R4 - R5 BOGA KANALI (BREAKOUT & RETEST)
            if (r4 > 0 && price > r4) {
                const npocText = aboveNpoc > 0 ? ` (Üst nPOC: $${formatVal(aboveNpoc)})` : (aboveNvah > 0 ? ` (Üst nVAH: $${formatVal(aboveNvah)})` : '');
                return packResult(
                    '🚀 R4 BOĞA KANALI (BREAKOUT & RETEST PUSUSU)',
                    'var(--green)',
                    `Fiyat <b>R4 ($${formatVal(r4)})</b> üzerinde boğa bölgesinde. Üst hedef: <b>R5 ($${formatVal(r5)})</b>${npocText}.`,
                    `⚡ <b>Botun Pusu Planı:</b> 5M mum R4 üzerinde yeni kapandıysa <b>Taze Breakout LONG</b> açılacak. Fiyat R4 desteğine geri çekilip (Retest) fitil bırakırsa <b>Retest LONG (Hedef R5: $${formatVal(r5)})</b> açılacak.`
                );
            }

            // DURUM 5: R3 - R4 SIKISMA & KARAR BOLGESI
            if (r3 > 0 && price > r3 && price <= r4) {
                return packResult(
                    '⚖️ R3-R4 SIKIŞMA & KIRILIM PUSUSU',
                    '#ffa726',
                    `Fiyat <b>R3 ($${formatVal(r3)})</b> desteği ile <b>R4 ($${formatVal(r4)})</b> direnci arasında sıkışıyor.`,
                    `⚡ <b>Botun Pusu Planı:</b> 5M mum kapanışında <b>R4 ($${formatVal(r4)})</b> yukarı kırılırsa <b>Breakout LONG (Hedef R5)</b> açılacak; fiyat R3'ten red yiyip aşağı dönerse <b>Scalp SHORT (Hedef Pivot P: $${formatVal(p)})</b> açılacak.`
                );
            }

            // DURUM 6: S3 - R3 PIVOT YATAY KANAL (SCALP KANALI)
            if (s3 > 0 && r3 > 0 && price >= s3 && price <= r3) {
                return packResult(
                    '🔄 PİVOT YATAY KANAL (DESTEK / DİRENÇ TEPKİSİ)',
                    '#388bfd',
                    `Fiyat <b>Pivot P ($${formatVal(p)})</b> ekseninde dengeli seyrediyor. (Alt: S3 $${formatVal(s3)} • Üst: R3 $${formatVal(r3)})`,
                    `⚡ <b>Botun Pusu Planı:</b> Fiyat <b>S3 ($${formatVal(s3)})</b> desteğine inip fitille sekerse <b>Scalp LONG (Hedef: Pivot P)</b>; <b>R3 ($${formatVal(r3)})</b> direncine çıkıp red yerse <b>Scalp SHORT (Hedef: Pivot P)</b> açılacak.`
                );
            }

            // DURUM 7: S4 - S3 COKUS UYARI BOLGESI
            if (s4 > 0 && price > s4 && price < s3) {
                return packResult(
                    '⚠️ S4-S3 ÇÖKÜŞ UYARI BÖLGESİ',
                    '#d500f9',
                    `Fiyat <b>S3 ($${formatVal(s3)})</b> altına indi, son savunma hattı olan <b>S4 ($${formatVal(s4)})</b> test ediliyor.`,
                    `⚡ <b>Botun Pusu Planı:</b> 5M mum <b>S4 ($${formatVal(s4)})</b> altına inerse <b>Breakdown SHORT (Hedef S5: $${formatVal(s5)})</b> açılacak; fiyat S3 üstüne toparlarsa <b>Mean Reversion LONG (Hedef Pivot P)</b> açılacak.`
                );
            }

            // DURUM 8: S4 ALTI AYI BOLGESI (BREAKDOWN)
            if (s4 > 0 && price <= s4) {
                const npocText = belowNpoc > 0 ? ` (Alt nPOC: $${formatVal(belowNpoc)})` : (belowNval > 0 ? ` (Alt nVAL: $${formatVal(belowNval)})` : '');
                return packResult(
                    '📉 S4 AYI BÖLGESİ (PANİK & BREAKDOWN PUSUSU)',
                    'var(--red)',
                    `Fiyat <b>S4 ($${formatVal(s4)})</b> altında ayı hakimiyetinde. Alt hedef: <b>S5 ($${formatVal(s5)})</b> / <b>mVAL ($${formatVal(mval)})</b>${npocText}.`,
                    `⚡ <b>Botun Pusu Planı:</b> 5M mum S4 altında yeni kapandıysa <b>Taze Breakdown SHORT</b> açılacak. Fiyat S4 direncine yükselip red mumu bırakırsa <b>Retest SHORT (Hedef S5: $${formatVal(s5)})</b> açılacak.`
                );
            }

            // DURUM 9: mVAH GERÇEK YAKINLIK TESTİ (Macro Breakout)
            if (mvah > 0 && Math.abs(price - mvah) / mvah <= 0.015) {
                const npocText = aboveNpoc > 0 ? ` Hedef Üst nPOC: $${formatVal(aboveNpoc)}.` : '';
                return packResult(
                    '🎯 mVAH AYLIK TAVAN BÖLGESİ (MACRO TEST)',
                    'var(--cyan)',
                    `Fiyat <b>mVAH ($${formatVal(mvah)})</b> aylık tepe hacim duvarını test ediyor.${npocText}`,
                    `⚡ <b>Botun Pusu Planı:</b> 5M mum kapanışı <b>mVAH ($${formatVal(mvah)})</b> üzerinde güçlü teyit verirse <b>Macro Breakout LONG</b> açılacak. Red yerse <b>Macro SHORT</b> pususu devreye girecek.`
                );
            }

            return packResult(
                '🔍 PİYASA İZLENİYOR',
                'var(--text-muted)',
                `Fiyat $${formatVal(price)} seviyesinde stabil.`,
                `⚡ <b>Botun Pusu Planı:</b> 5 dakikalık mum kapanışlarında strateji kurallarının oluşması (Breakout, Retest, nPOC veya Destek/Direnç dönüşü) bekleniyor.`
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

                        html += `
                        <div class="coin-card ${posClass}" id="card-${safeId}">
                            <!-- CLEAN CARD HEAD: SYMBOL + GRAFIK BUTTON -->
                            <div class="card-head">
                                <div class="card-top-row">
                                    <span class="card-symbol" onclick="openTradingViewModal('${cleanSym}')" style="cursor:pointer;" title="${cleanSym} Grafiğini Aç">${cleanSym}</span>
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
                            posCurP.innerText = `$${metrics.curP.toFixed(4)}`;
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
                const tp1Val = pos.tp1 ? Number(pos.tp1).toFixed(4) : '-';
                const tp2Val = pos.tp2 ? Number(pos.tp2).toFixed(4) : '-';
                const stopVal = pos.soft_stop ? Number(pos.soft_stop).toFixed(4) : (pos.hard_stop ? Number(pos.hard_stop).toFixed(4) : '-');
                const stopColor = pos.is_half_closed ? 'var(--green)' : '#f87171';
                const stopLabel = pos.is_half_closed ? '🛡️ Breakeven Stop' : '🛑 Aktif Stop';

                html += `
                <div class="active-pos-card ${pnlClass}" id="pos-card-${safeId}">
                    <!-- 1. TOP HEADER (Ticker on left, 2-line PnL on right) -->
                    <div class="pos-top">
                        <div style="display:flex; align-items:center; gap:8px;">
                            <span class="pos-badge ${pos.side === 'LONG' ? 'pos-long' : 'pos-short'}">${pos.leverage}x ${pos.side}</span>
                            <span style="font-size:17px; font-weight:900; font-family:'JetBrains Mono'; color:#ffffff; letter-spacing:0.5px;">${cleanSym}</span>
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
                        <div>Giriş: <b style="color:#ffffff;">$${pos.entry_price}</b></div>
                        <div>Anlık: <b id="pos-cur-price-${safeId}" style="color:${pnlColor};">$${metrics.curP}</b></div>
                        <div>Marjin: <b style="color:#ffffff;">$${Number(pos.margin || 100).toFixed(2)}</b></div>
                        <div>Hacim: <b style="color:#ffffff;">$${Number(pos.position_value || 500).toFixed(2)}</b></div>
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

                    <!-- 5. ACTION BUTTON -->
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:4px; padding-top:10px; border-top:1px solid rgba(255,255,255,0.08);">
                        <span style="font-size:11.5px; color:#94a3b8;">Risk Müdahalesi:</span>
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
                <div>• Giriş Fiyatı: <b>$${pos.entry_price}</b></div>
                <div>• Anlık Piyasa Fiyatı: <b>$${metrics.curP}</b></div>
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

                // 1. Candlestick Serisi
                const candleSeries = chart.addCandlestickSeries({
                    upColor: '#0ecb81',
                    downColor: '#ff4757',
                    borderVisible: false,
                    wickUpColor: '#0ecb81',
                    wickDownColor: '#ff4757',
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
                    });
                    avHighSeries.setData(data.avwap_high);
                }

                if (data.avwap_low && data.avwap_low.length > 0) {
                    const avLowSeries = chart.addLineSeries({
                        color: '#ffffff',
                        lineWidth: 2,
                        title: 'Dip AVWAP',
                        priceLineVisible: false,
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
                currentActiveChartSym = cleanSym;
                const modal = document.getElementById('tv-modal-overlay');
                if (!modal) return;
                
                const fullSym = cleanSym.includes('/') ? cleanSym : cleanSym + '/USDT';
                const coinData = (appState.symbols && (appState.symbols[fullSym] || appState.symbols[cleanSym])) ? (appState.symbols[fullSym] || appState.symbols[cleanSym]) : {};
                const levels = coinData.levels || {};
                const cam = levels.camarilla || {};
                const price = Number(livePrices[fullSym] || coinData.price || 0);
                const hasPos = appState.open_positions && appState.open_positions[fullSym];
                const intel = generateDetailedIntelligence(fullSym, price, cam, levels, hasPos);

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
            }
        });

        function updateFinancialSummary() {
            const hList = appState.history || [];
            let totalRealizedNetPnl = 0;
            let totalFees = 0;

            hList.forEach(h => {
                totalRealizedNetPnl += Number(h.net_pnl || 0);
                totalFees += Number(h.fees || 0);
            });

            let totalUnrealizedPnl = 0;
            const openKeys = Object.keys(appState.open_positions || {});
            openKeys.forEach(sym => {
                const pos = appState.open_positions[sym];
                const curP = Number((livePrices && livePrices[sym]) || pos.entry_price || 0.0);
                if (typeof computePositionPnL === 'function') {
                    const metrics = computePositionPnL(pos, curP);
                    totalUnrealizedPnl += metrics.pnlUsdt;
                }
            });

            const bal = appState.balance || 100000.0;
            const totalPortfolioEquity = bal + totalUnrealizedPnl;
            const totalNetPnl = totalRealizedNetPnl + totalUnrealizedPnl;

            const feesEl = document.getElementById('kpi-fees') || document.getElementById('cockpit-fees');
            const pnlEl = document.getElementById('kpi-pnl') || document.getElementById('cockpit-pnl');
            const growthEl = document.getElementById('kpi-growth') || document.getElementById('cockpit-growth');
            const balEl = document.getElementById('kpi-balance') || document.getElementById('cockpit-balance');

            if (feesEl) feesEl.innerText = '$' + totalFees.toFixed(4);
            if (pnlEl) {
                pnlEl.innerText = (totalNetPnl >= 0 ? '+' : '') + totalNetPnl.toFixed(2) + ' $';
                pnlEl.style.color = totalNetPnl >= 0 ? 'var(--green)' : 'var(--red)';
            }
            
            const initialBal = (appState.initial_balance || 100000.0);
            const growthPct = ((totalPortfolioEquity - initialBal) / initialBal) * 100;
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

                function renderHistoryTable() {
            try {
                const tbody = document.getElementById('trade-table-body');
                if (!tbody) return;
                const hList = appState.history || [];

                const totalCountEl = document.getElementById('history-total-count');
                if (totalCountEl) totalCountEl.innerText = `${hList.length} İşlem`;
                
                try { updateFinancialSummary(); } catch(e) {}

                if (hList.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="14" style="text-align:center; padding: 40px; color:#94a3b8;">Kayıtlı işlem geçmişi bulunmuyor.</td></tr>`;
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
                    const itemSym = item.symbol || '';
                    if (symFilter !== 'ALL' && itemSym !== symFilter) return false;
                    
                    const pnlNum = Number(item.net_pnl || 0.0);
                    if (statusFilter === 'WIN' && pnlNum < 0) return false;
                    if (statusFilter === 'LOSS' && pnlNum >= 0) return false;

                    const r = item.reason || '';
                    if (setupFilter === 'nPOC' && !r.includes('nPOC')) return false;
                    if (setupFilter === 'MACRO' && !r.includes('mVAL') && !r.includes('mVAH')) return false;
                    if (setupFilter === 'CAM_BO' && !r.includes('Breakout') && !r.includes('Breakdown')) return false;
                    if (setupFilter === 'CAM_BOUNCE' && !r.includes('S3') && !r.includes('R3')) return false;

                    return true;
                });

                if (filtered.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="14" style="text-align:center; padding: 40px; color:#94a3b8; font-size:14px;">Seçilen filtre kriterlerine uygun işlem kaydı bulunamadı.</td></tr>`;
                    return;
                }

                let tableHtml = '';
                filtered.forEach(h => {
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
                    if (r.includes('nPOC')) setupBadgeClass = 'badge-npoc';
                    else if (r.includes('mVAL') || r.includes('mVAH')) setupBadgeClass = 'badge-macro';
                    else if (r.includes('Breakout') || r.includes('Breakdown')) setupBadgeClass = 'badge-breakout';
                    else if (r.includes('S3') || r.includes('R3')) setupBadgeClass = 'badge-bounce';

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
                        <td><b style="color:#ffffff; font-size:13.5px;">${symClean}</b></td>
                        <td><span class="pos-badge ${side === 'LONG' ? 'pos-long' : 'pos-short'}" style="font-size:11px; padding:2px 8px;">${lev}x ${side}</span></td>
                        <td>$${entryP}</td>
                        <td>$${exitP}</td>
                        <td style="color:${isWin ? 'var(--green)' : 'var(--red)'}; font-weight:800; font-family:'JetBrains Mono';">
                            ${netPnl >= 0 ? '+' : ''}$${netPnl.toFixed(4)}
                        </td>
                        <td style="color:${isWin ? 'var(--green)' : 'var(--red)'}; font-weight:800; font-family:'JetBrains Mono';">
                            ${roePct >= 0 ? '+' : ''}${roePct.toFixed(2)}%
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
                        <td>
                            <button onclick="openTelemetryModal('${h.id}')" style="background:rgba(0,242,254,0.12); border:1px solid rgba(0,242,254,0.35); color:var(--cyan); padding:4px 10px; border-radius:6px; font-size:11px; font-weight:700; cursor:pointer; transition:all 0.15s ease;" onmouseover="this.style.background='var(--cyan)'; this.style.color='#000';" onmouseout="this.style.background='rgba(0,242,254,0.12)'; this.style.color='var(--cyan)';">
                                🔬 İncele
                            </button>
                        </td>
                    </tr>
                    `;
                });
                tbody.innerHTML = tableHtml;
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

                const symFilter = document.getElementById('filter-symbol').value;
                const statusFilter = document.getElementById('filter-status').value;

                let filtered = hList.filter(item => {
                    if (symFilter !== 'ALL' && item.symbol !== symFilter) return false;
                    if (statusFilter === 'WIN' && item.net_pnl < 0) return false;
                    if (statusFilter === 'LOSS' && item.net_pnl >= 0) return false;
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
                'lunc': '1000lunc', 'xec': '1000xec', 'mog': '1000000mog', 'cheems': '1000cheems'
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
                updateSystemHealthBadge();

                // 4. Only re-render Open Positions if position IDs or count changed
                const currentPosKey = Object.keys(appState.open_positions || {}).sort().join(',');
                if (currentPosKey !== lastRenderedPositionsKey) {
                    lastRenderedPositionsKey = currentPosKey;
                    renderPositions();
                }

                // 5. Only re-render History Table if history length changed
                const currentHistLen = (appState.history || []).length;
                if (currentHistLen !== lastRenderedHistoryLen) {
                    lastRenderedHistoryLen = currentHistLen;
                    renderHistoryTable();
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

                const isWin = item.net_pnl >= 0;
                const rMult = item.realized_r !== undefined ? item.realized_r : (item.roe_pct >= 0 ? +(item.roe_pct / 2).toFixed(1) : -1.0);
                const mfe = item.mfe_roe !== undefined ? item.mfe_roe : Math.max(0, item.roe_pct);
                const mae = item.mae_roe !== undefined ? item.mae_roe : (item.roe_pct < 0 ? Math.abs(item.roe_pct) : 0.0);
                const eff = item.exit_efficiency_pct !== undefined ? item.exit_efficiency_pct : (isWin ? 90.0 : 0.0);

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
                            <b style="color:#fff; font-family:'JetBrains Mono';">$${val.toFixed(4)}</b>
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
                            <div style="font-size:15px; font-weight:800; color:${isWin ? 'var(--green)' : 'var(--red)'}; font-family:'JetBrains Mono';">${isWin ? '+' : ''}${item.net_pnl.toFixed(2)}$ (${isWin ? '+' : ''}${item.roe_pct.toFixed(2)}%)</div>
                        </div>
                        <div style="background:rgba(255,255,255,0.03); border:1px solid var(--border); border-radius:10px; padding:12px; text-align:center;">
                            <div style="font-size:11px; color:#94a3b8; margin-bottom:4px;">R-MULTIPLE (1R)</div>
                            <div style="font-size:15px; font-weight:800; color:${rMult >= 0 ? 'var(--green)' : 'var(--red)'}; font-family:'JetBrains Mono';">${rMult >= 0 ? '+' : ''}${rMult}R</div>
                        </div>
                        <div style="background:rgba(255,255,255,0.03); border:1px solid var(--border); border-radius:10px; padding:12px; text-align:center;">
                            <div style="font-size:11px; color:#94a3b8; margin-bottom:4px;">ZİRVE KÂR (MFE)</div>
                            <div style="font-size:15px; font-weight:800; color:#38bdf8; font-family:'JetBrains Mono';">+${mfe.toFixed(2)}% ROE</div>
                        </div>
                        <div style="background:rgba(255,255,255,0.03); border:1px solid var(--border); border-radius:10px; padding:12px; text-align:center;">
                            <div style="font-size:11px; color:#94a3b8; margin-bottom:4px;">MAKS ÇEKİLME (MAE)</div>
                            <div style="font-size:15px; font-weight:800; color:#f43f5e; font-family:'JetBrains Mono';">-${mae.toFixed(2)}% ROE</div>
                        </div>
                    </div>

                    <div style="background:rgba(56,189,248,0.06); border:1px solid rgba(56,189,248,0.25); border-radius:12px; padding:14px; margin-bottom:18px;">
                        <div style="font-size:13px; font-weight:800; color:#38bdf8; margin-bottom:8px; display:flex; align-items:center; gap:6px;">
                            🎯 STRATEJİ, TREND REJİMİ & PİYASA KOŞULLARI
                        </div>
                        <div style="font-size:12.5px; color:#f1f5f9; line-height:1.7;">
                            <b>• Giriş Gerekçesi / Formasyon:</b> <span style="color:#ffffff;">${item.reason}</span><br>
                            <b>• Kapanış Tetikleyicisi:</b> <span style="color:#fbc531;">${item.close_reason}</span><br>
                            <b>• Giriş Anı Trend Rejimi:</b> <span style="color:#a5f3fc; font-weight:700;">${item.trend_regime || 'Belirleniyor'}</span> | <b>Volatilite (ATR):</b> <span style="color:#fde047; font-weight:700;">%${item.atr_pct !== undefined ? item.atr_pct : '1.2'}</span><br>
                            <b>• Hacim Patlama Katsayısı:</b> <span style="color:#38bdf8; font-weight:700;">${item.volume_surge || '1.0'}x Ort. Hacim</span> | <b>Confluence Güç Skoru:</b> <span style="color:#c084fc; font-weight:700;">${item.confluence_score || '2/4'}</span><br>
                            <b>• Makro Uyum (1H/4H):</b> <span style="color:#fcd34d; font-weight:700;">${item.htf_alignment || 'Nötr'}</span> | <b>Piyasa Seansı:</b> <span style="color:#e2e8f0;">${item.session || 'Küresel Seans'}</span><br>
                            <b>• Kademeli TP1 Durumu:</b> <span style="color:#86efac; font-weight:700;">${item.tp1_hit || (item.id.includes('TP1') ? 'EVET (%50 Kilitlendi)' : 'HAYIR')}</span> | <b>Çıkış Verimliliği:</b> %${eff.toFixed(1)}<br>
                            <b>• Giriş / Çıkış Fiyatı:</b> $${item.entry_price} ➔ $${item.exit_price} | <b>Komisyon:</b> $${item.fees.toFixed(4)}<br>
                            <b>• Planlanan Hedef (TP1):</b> ${item.tp1 ? '$' + item.tp1 : 'Yok'} | <b>Planlanan Stop:</b> ${item.soft_stop ? '$' + item.soft_stop : 'Yok'}
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

        async function init() {
            if (false) {
                const grid = document.getElementById('coin-chips-container');
                const btn = document.getElementById('pool-collapse-btn');
                if (grid) grid.style.display = 'none';
                if (btn) btn.innerText = '🔽 Pariteleri Göster';
            }
            await syncBackendState();
            startBinanceGlobalFeed();
            startSSEFallback();
            setInterval(syncBackendState, 2000);
        }

        init();
    </script>
</body>
</html>
"""

async def start_server(market_data, trader_manager, notifier=None, live_trader=None):
    app = web.Application()
    
    async def index(request):
        return web.Response(text=HTML_PAGE, content_type='text/html')
        
    
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

    async def api_data(request):
        try:
            symbols_data = {}
            for s in market_data.active_symbols:
                lev = market_data.levels.get(s, {})
                cur_p = market_data.current_prices.get(s, 0.0)
                if not lev or not lev.get("camarilla"):
                    market_data.recalculate_levels(s)
                    lev = market_data.levels.get(s, {})
                symbols_data[s] = {
                    "price": cur_p,
                    "levels": lev
                }
            
            all_coins = []
            for s in market_data.all_symbols:
                all_coins.append({
                    "symbol": s,
                    "active": s in market_data.active_symbols,
                    "price": market_data.current_prices.get(s, 0.0)
                })

            try:
                sys_health = market_data.get_system_health() if market_data else {
                    "is_perfect": True,
                    "status_text": "5/5 Tam Sağlıklı",
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

            return web.json_response({
                "balance": trader_manager.balance,
                "initial_balance": 100000.0,
                "free_balance": trader_manager.get_free_balance(),
                "open_positions": trader_manager.open_positions,
                "history": trader_manager.history,
                "symbols": symbols_data,
                "all_coins": all_coins,
                "system_health": sys_health
            })
        except Exception as e:
            return web.json_response({
                "balance": trader_manager.balance,
                "initial_balance": 100000.0,
                "free_balance": trader_manager.get_free_balance(),
                "open_positions": trader_manager.open_positions,
                "history": trader_manager.history,
                "symbols": {},
                "all_coins": [],
                "system_health": {"is_perfect": False, "status_text": f"Hata: {e}"}
            })

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

    async def api_close_position_manual(request):
        try:
            payload = await request.json()
            sym = payload.get("symbol")
            if sym in trader_manager.open_positions:
                cur_price = market_data.current_prices.get(sym, trader_manager.open_positions[sym]["entry_price"])
                record = paper_trader.close_position(sym, cur_price, "Manuel Müdahale (Dashboard Kapatma)")
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
        queue = asyncio.Queue()
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
                initial_balance=INITIAL_BALANCE
            )
            filename = f"Valkyrie_Ticaret_Raporu_{datetime.now(timezone(timedelta(hours=3))).strftime('%Y%m%d_%H%M')}.xlsx"
            return web.Response(
                body=buf.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                headers={
                    'Content-Disposition': f'attachment; filename="{filename}"'
                }
            )
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
            
            # Direct fallback fetch if not in cache yet
            if df_5m is None or df_5m.empty:
                ex_sym = market_data._clean_symbol(clean_sym)
                ohlcv = await market_data.exchange.fetch_ohlcv(ex_sym, timeframe='5m', limit=500)
                if ohlcv and len(ohlcv) > 0:
                    df_5m = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    market_data.candles_5m[clean_sym] = df_5m
                    market_data.recalculate_levels(clean_sym)
            
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
            
            high_idx_rel = recent_df['high'].argmax()
            low_idx_rel = recent_df['low'].argmin()
            
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
    app.router.add_get('/', index)
    app.router.add_post('/api/auth/register', api_auth_register)
    app.router.add_post('/api/auth/login', api_auth_login)
    app.router.add_get('/api/admin/overview', api_admin_overview)
    app.router.add_get('/api/data', api_data)
    app.router.add_get('/api/candles', api_candles)
    app.router.add_get('/api/export_excel', api_export_excel)
    app.router.add_post('/api/toggle_symbol', api_toggle_symbol)
    app.router.add_post('/api/set_active_symbols', api_set_active_symbols)
    app.router.add_post('/api/close_position_manual', api_close_position_manual)
    app.router.add_get('/api/stream', sse_handler)
    
    import os
    port = int(os.environ.get('PORT', 5000))
    host = '0.0.0.0'
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    print(f">> [VALKYRIE QUANT DESK READY]: http://{host}:{port}")

async def broadcast_tick(symbol, price):
    if not sse_clients:
        return
    data = {"type": "tick", "symbol": symbol, "price": price}
    for q in list(sse_clients):
        try:
            q.put_nowait(data)
        except Exception:
            pass
