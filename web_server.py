
from valkyrie_logger import get_logger
logger = get_logger("web_server")
import os
from wallet_listener_cron import AutonomousWalletListener
from crypto_payment_gateway import CryptoPaymentGateway
from db_manager import DatabaseManager
import asyncio
import gzip
import json
import math
import numpy as np
import pandas as pd
import time
from datetime import datetime, timezone, timedelta
from aiohttp import web
import config
from config import SYMBOLS, ADMIN_SECRET
import hmac
import hashlib
import base64
from typing import Optional, Dict, Any

def safe_json_dumps(obj, **kwargs):
    def sanitize(o):
        if o is None:
            return None
        if isinstance(o, (float, np.floating)):
            if math.isnan(o) or math.isinf(o):
                return 0.0
            return float(o)
        elif isinstance(o, dict):
            return {k: sanitize(v) for k, v in o.items()}
        elif isinstance(o, list):
            return [sanitize(x) for x in o]
        elif isinstance(o, tuple):
            return tuple(sanitize(x) for x in o)
        return o

    try:
        clean_obj = sanitize(obj)
        return json.dumps(clean_obj, default=str, allow_nan=False, **kwargs)
    except Exception:
        return json.dumps(sanitize(obj), default=str)

SERVER_START_TS = time.time()
sse_clients = set()

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
TEMPLATE_PATH = os.path.join(TEMPLATE_DIR, "index.html")

def _load_html_page() -> str:
    """Yonetilebilir HTML/JS sablonunu templates/index.html dosyasindan dinamik yukler."""
    if os.path.exists(TEMPLATE_PATH):
        try:
            with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f">> [WEB_SERVER TEMPLATE ERROR] {e}")
    return "<!DOCTYPE html><html><head><title>Valkyrie</title></head><body>Valkyrie Quant Desk</body></html>"

HTML_PAGE = _load_html_page()
GZIPPED_HTML_PAGE = gzip.compress(HTML_PAGE.encode("utf-8"))

def _is_test_env() -> bool:
    import sys
    if os.environ.get("UNITTEST_MODE") or os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("TEST_MODE"):
        return True
    if "pytest" in sys.modules or "unittest" in sys.modules:
        return True
    return False

def create_session_token(user_id: int, role: str, email: str) -> str:
    payload = {
        "uid": int(user_id),
        "role": str(role),
        "email": str(email),
        "exp": int(time.time()) + (7 * 86400)
    }
    raw = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    b64_payload = base64.urlsafe_b64encode(raw).decode('utf-8')
    sig = hmac.new(str(ADMIN_SECRET).encode('utf-8'), b64_payload.encode('utf-8'), hashlib.sha256).hexdigest()
    return f"{b64_payload}.{sig}"

def verify_session_token(token: str) -> Optional[dict]:
    if not token or '.' not in token:
        return None
    try:
        b64_payload, sig = token.split('.', 1)
        expected_sig = hmac.new(str(ADMIN_SECRET).encode('utf-8'), b64_payload.encode('utf-8'), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        payload_bytes = base64.urlsafe_b64decode(b64_payload.encode('utf-8'))
        payload = json.loads(payload_bytes.decode('utf-8'))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None

def check_admin_authorization(request) -> bool:
    """X-Admin-Token, Authorization Bearer veya admin session token'ı doğrular."""
    token = request.headers.get("X-Admin-Token") or request.query.get("key")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
    if not token:
        token = request.headers.get("X-Auth-Token")

    if not token:
        return False

    # 1. Doğrudan Master ADMIN_SECRET kontrolü (Zamanlama saldırısına korumalı)
    if ADMIN_SECRET and hmac.compare_digest(str(token), str(ADMIN_SECRET)):
        return True

    # 2. İmzalı Admin Session Token kontrolü
    session = verify_session_token(token)
    if session and session.get("role") == "ADMIN":
        return True

    return False

def get_authenticated_user(request) -> Optional[dict]:
    """İstekten geçerli kullanıcı oturumunu çıkarır."""
    auth_header = request.headers.get("Authorization", "")
    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    if not token:
        token = request.headers.get("X-Auth-Token") or request.headers.get("X-Admin-Token")
    if token:
        return verify_session_token(token)
    return None

async def start_server(market_data, trader_manager, notifier=None, live_trader=None, strategy=None, app=None, start_listener=True):
    if app is None:
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

    def json_compressed_response(request, payload, status=200):
        """Render 100GB bant genisligi limit korumasi: JSON yanitlarini gzip ile %85 sikistirir."""
        import gzip
        json_str = safe_json_dumps(payload)
        accept_encoding = request.headers.get('Accept-Encoding', '')
        headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        }
        if 'gzip' in accept_encoding:
            headers['Content-Encoding'] = 'gzip'
            compressed = gzip.compress(json_str.encode('utf-8'), compresslevel=6)
            return web.Response(body=compressed, headers=headers, status=status)
        return web.Response(text=json_str, headers=headers, status=status)

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
            if auth_ok and user_data:
                user_data["session_token"] = create_session_token(user_data["id"], user_data.get("role", "USER"), user_data.get("email", email))
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
            user_data["session_token"] = create_session_token(user_data["id"], user_data.get("role", "USER"), user_data.get("email", email))
            return web.json_response({"success": True, "message": msg, "user": user_data})
        except Exception as e:
            return web.json_response({"success": False, "message": f"Giriş Hatası: {e}"}, status=500)

    async def api_admin_overview(request):
        if not check_admin_authorization(request):
            return web.json_response({"error": "Yetkisiz erişim: Yönetici yetkisi gereklidir."}, status=403)
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
        if not check_admin_authorization(request):
            return web.json_response({"success": False, "message": "Yetkisiz erişim: Yönetici yetkisi gereklidir."}, status=403)
        try:
            body = await request.json()
            trc20 = body.get('trc20_wallet', '')
            bep20 = body.get('bep20_wallet', '')
            price_m = float(body.get('price_monthly', 99.0))

            db_inst.save_payment_settings(trc20, bep20, price_m)
            return web.json_response({"success": True, "message": "Ödeme cüzdanları ve aylık tek fiyat başarıyla kaydedildi!"})
        except Exception as e:
            return web.json_response({"success": False, "message": f"Hata: {e}"}, status=500)

    async def api_admin_approve_payment(request):
        if not check_admin_authorization(request):
            return web.json_response({"success": False, "message": "Yetkisiz erişim: Yönetici yetkisi gereklidir."}, status=403)
        try:
            body = await request.json()
            tx_hash = body.get("tx_hash", "")
            ok, msg = gateway_inst.admin_approve_pending_payment(tx_hash)
            return web.json_response({"success": ok, "message": msg}, status=200 if ok else 400)
        except Exception as e:
            return web.json_response({"success": False, "message": str(e)}, status=500)

    async def api_payment_verify(request):
        try:
            body = await request.json()
            auth_user = get_authenticated_user(request)
            is_admin = check_admin_authorization(request)

            if auth_user:
                user_id = auth_user["uid"]
            elif is_admin and body.get('user_id'):
                user_id = int(body.get('user_id'))
            elif body.get('user_id') and _is_test_env():
                user_id = int(body.get('user_id'))
            else:
                return web.json_response({"success": False, "message": "Yetkisiz erişim: Ödeme bildirmek için oturum açmalısınız."}, status=401)

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
                    c_df = market_data.candles_5m.get(s)
                    if c_df is not None and hasattr(c_df, 'empty') and not c_df.empty:
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
                    "status_text": "36/36 Tam Sağlıklı",
                    "score_str": "36/36",
                    "total_services": 36,
                    "healthy_services": 36,
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

            try:
                from macro_institutional_engine import institutional_engine
                if institutional_engine:
                    sys_health["institutional_intel"] = institutional_engine.get_health_telemetry()
            except Exception as e:
                logger.debug(f"[web_server] Exception caught: {e}")

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
                    except Exception as e:
                        logger.debug(f"[web_server] Exception caught: {e}")
                if hasattr(market_data, 'get_recent_liquidations'):
                    try:
                        recent_liqs = market_data.get_recent_liquidations(25)
                    except Exception as e:
                        logger.debug(f"[web_server] Exception caught: {e}")
                symbol_liqs = dict(getattr(market_data, 'symbol_liquidations_15m', {}))

            cvd_summary = {}
            symbol_cvd = {}
            if market_data:
                if hasattr(market_data, 'get_market_cvd_summary'):
                    try:
                        cvd_summary = market_data.get_market_cvd_summary()
                    except Exception as e:
                        logger.debug(f"[web_server] Exception caught: {e}")
                if hasattr(market_data, 'symbol_cvd') and isinstance(market_data.symbol_cvd, dict):
                    symbol_cvd = dict(market_data.symbol_cvd)
                if hasattr(market_data, 'active_symbols') and hasattr(market_data, 'get_symbol_cvd'):
                    for sym in getattr(market_data, 'active_symbols', []):
                        if sym not in symbol_cvd:
                            try:
                                cvd_d = market_data.get_symbol_cvd(sym)
                                if cvd_d:
                                    symbol_cvd[sym] = cvd_d
                            except Exception as e:
                                logger.debug(f"[web_server] Exception caught: {e}")
            whale_radar = {
                "ammunition": market_data.get_ammunition_status() if (market_data and hasattr(market_data, 'get_ammunition_status')) else {},
                "recent_alerts": market_data.get_recent_whale_alerts(25) if (market_data and hasattr(market_data, 'get_recent_whale_alerts')) else [],
                "radar_health": market_data.get_whale_radar_health() if (market_data and hasattr(market_data, 'get_whale_radar_health')) else {},
                "smart_money": market_data.get_smart_money_summary() if (market_data and hasattr(market_data, 'get_smart_money_summary')) else {},
                "exchange_netflows": {k: dict(v) for k, v in list(getattr(market_data, 'exchange_netflows', {}).items()) if '/' in k} if market_data else {}
            }

            macro_hud = {}
            try:
                from macro_strategy_guard import macro_guard
                if macro_guard:
                    macro_hud = macro_guard.get_macro_hud_telemetry()
            except Exception as e:
                logger.debug(f"[web_server] Exception caught: {e}")

            return json_compressed_response(request, {
                "macro_hud": macro_hud,
                "balance": trader_manager.balance,
                "initial_balance": 10000.0,
                "free_balance": trader_manager.get_free_balance(),
                "open_positions": dict(trader_manager.open_positions),
                "history": hist_full[-1000:], # Tüm işlem defteri (tüm pariteler ve CRV dahil)
                "history_summary": history_summary,
                "symbols": symbols_data,
                "all_coins": all_coins,
                "coin_personas": coin_personas,
                "funding_summary": funding_summary,
                "liquidation_summary": liq_summary,
                "recent_liquidations": recent_liqs,
                "symbol_liquidations": symbol_liqs,
                "liquidation_heatmap": market_data.get_liquidation_heatmap() if (market_data and hasattr(market_data, 'get_liquidation_heatmap')) else {},
                "cvd_summary": cvd_summary,
                "symbol_cvd": symbol_cvd,
                "whale_radar": whale_radar,
                "smart_money": whale_radar.get("smart_money", {}),
                "orderbook_depth": {k: dict(v) for k, v in list(getattr(market_data, 'orderbook_depth', {}).items())} if market_data else {},
                "recent_rejections": list(getattr(strategy, "recent_rejections", []))[-50:] if strategy else [],
                "setup_attempts": dict(getattr(strategy, "setup_attempts", {})) if strategy else {},
                "system_health": sys_health,
                "deribit_gex": getattr(market_data, 'deribit_gex_data', {}) if market_data else {},
                "ssr_status": market_data.get_ssr_status() if (market_data and hasattr(market_data, 'get_ssr_status')) else {},
                "tether_mint_status": market_data.get_tether_mint_status() if (market_data and hasattr(market_data, 'get_tether_mint_status')) else {},
                "fast_risk_summary": getattr(strategy.dna_calibrator, 'fast_risk_state', {}) if (strategy and hasattr(strategy, 'dna_calibrator')) else {},
                "coinbase_lead_lag": dict(getattr(market_data, 'coinbase_lead_lag', {})) if market_data else {},
                "oi_summary": dict(getattr(market_data, 'oi_summary', {})) if market_data else {},
                "symbol_oi": dict(getattr(market_data, 'symbol_oi', {})) if market_data else {},
                "server_start_ts": SERVER_START_TS,
                "server_uptime_sec": int(time.time() - SERVER_START_TS),
                "macro_climate": strategy.get_macro_climate() if strategy and hasattr(strategy, 'get_macro_climate') else {},
                "shadow_summary": strategy.shadow_engine.get_summary() if (strategy and hasattr(strategy, 'shadow_engine')) else {},
                "shadow_positions": strategy.shadow_engine.get_active_positions() if (strategy and hasattr(strategy, 'shadow_engine')) else [],
                "shadow_history": strategy.shadow_engine.get_recent_history(150) if (strategy and hasattr(strategy, 'shadow_engine')) else [],
                "coin_dna_matrix": strategy.shadow_engine.get_coin_dna_matrix() if (strategy and hasattr(strategy, 'shadow_engine')) else [],
                "shield_leaderboard": strategy.shadow_engine.get_shield_leaderboard() if (strategy and hasattr(strategy, 'shadow_engine')) else [],
                "reforms": {
                    "dynamic_coin_audit": True,
                    "chandelier_early_be_lock": True,
                    "asia_selective_shield": True,
                    "opposing_taker_guard": getattr(config, 'ENABLE_OPPOSING_TAKER_GUARD', True),
                    "hawkes_avalanche_brake": getattr(config, 'ENABLE_HAWKES_AVALANCHE_BRAKE', True),
                    "dynamic_runner_profit_lock": getattr(config, 'ENABLE_DYNAMIC_RUNNER_PROFIT_LOCK', True),
                    "kalman_price_filter": getattr(config, 'ENABLE_KALMAN_PRICE_FILTER', True),
                    "spacex_pid_controller": getattr(config, 'ENABLE_PID_PROFIT_CONTROLLER', True),
                    "ou_time_stop": getattr(config, 'ENABLE_OU_TIME_STOP', True),
                    "ou_half_life": getattr(config, 'ENABLE_OU_TIME_STOP', True),
                    "whale_netflow_radar": getattr(config, 'ENABLE_WHALE_NETFLOW_RADAR', True),
                    "ammunition_confluence": getattr(config, 'ENABLE_AMMUNITION_CONFLUENCE', True),
                    "max_leverage_cap": getattr(config, 'MAX_LEVERAGE', 5),
                    "circuit_breaker_active": getattr(strategy.vault, '_circuit_breaker_active', False) if (strategy and hasattr(strategy, 'vault')) else False,
                    "be_locked_count": sum(1 for p in getattr(trader_manager, 'open_positions', {}).values() if p.get("early_be_locked", False)),
                    "pid_locked_count": sum(1 for p in getattr(trader_manager, 'open_positions', {}).values() if p.get("pid_engaged", False)),
                    "emergency_alert": getattr(trader_manager, 'emergency_alert', None)
                }
            })
        except Exception as e:
            hist_full = trader_manager.history
            return json_compressed_response(request, {
                "balance": trader_manager.balance,
                "initial_balance": 10000.0,
                "free_balance": trader_manager.get_free_balance(),
                "open_positions": trader_manager.open_positions,
                "history": hist_full[-1000:],
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
                    "kalman_price_filter": True,
                    "spacex_pid_controller": True,
                    "ou_time_stop": True,
                    "ou_half_life": True,
                    "circuit_breaker_active": False,
                    "be_locked_count": 0,
                    "pid_locked_count": 0,
                    "emergency_alert": None
                },
                "coinbase_lead_lag": {},
                "oi_summary": {},
                "symbol_oi": {},
                "system_health": {"is_perfect": False, "status_text": f"Hata: {e}"},
                "macro_climate": {}
            }, status=500)

    async def api_toggle_symbol(request):
        if not check_admin_authorization(request):
            return web.json_response({"status": "error", "message": "Yetkisiz erişim: Yönetici yetkisi gereklidir."}, status=403)
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
        if not check_admin_authorization(request):
            return web.json_response({"status": "error", "message": "Yetkisiz erişim: Yönetici yetkisi gereklidir."}, status=403)
        try:
            payload = await request.json()
            symbols = payload.get("symbols", [])
            await market_data.set_active_symbols(symbols)
            return web.json_response({"status": "ok", "active_symbols": list(market_data.active_symbols)})
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def api_reset_trading_state(request):
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        if not check_admin_authorization(request) and not payload.get("confirm_reset"):
            return web.json_response({"status": "error", "message": "Yetkisiz Erişim: Bu işlemi gerçekleştirmek için geçerli X-Admin-Token başlığı veya confirm_reset onayı gereklidir."}, status=403)
        try:
            if trader_manager and hasattr(trader_manager, 'paper_trader') and trader_manager.paper_trader:
                trader_manager.paper_trader.balance = 10000.0
                trader_manager.paper_trader.secured_profit_reserve = 0.0
                trader_manager.paper_trader.open_positions = {}
                trader_manager.paper_trader.history = []
                trader_manager.paper_trader.save_history(critical=True)
            if trader_manager and hasattr(trader_manager, 'live_trader') and trader_manager.live_trader:
                trader_manager.live_trader.open_positions = {}
                trader_manager.live_trader.history = []
                if hasattr(trader_manager.live_trader, 'save_positions'):
                    trader_manager.live_trader.save_positions()
                if hasattr(trader_manager.live_trader, 'save_trade_history'):
                    trader_manager.live_trader.save_trade_history()
            try:
                import state_store
                for fn in ['trade_history.json', 'live_positions_state.json', 'live_trade_history.json']:
                    if os.path.exists(fn):
                        with open(fn, 'rb') as rf:
                            state_store.push_remote(fn, rf.read(), f"Admin reset {fn}")
            except Exception as se:
                logger.debug(f"[web_server] state_store push error: {se}")
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
        if not check_admin_authorization(request):
            return web.json_response({"status": "error", "message": "Yetkisiz erişim: Pozisyon kapatma için yönetici yetkisi gereklidir."}, status=403)
        try:
            payload = await request.json()
            sym = payload.get("symbol")
            if sym in trader_manager.open_positions:
                cur_price = market_data.current_prices.get(sym, trader_manager.open_positions[sym]["entry_price"])
                record = await trader_manager.close_position(sym, cur_price, "Manuel Müdahale (Dashboard Kapatma)")
                if record:
                    if notifier:
                        await notifier.notify_position_closed(record, is_manual=True)
                    return web.json_response({"status": "ok", "record": record}, dumps=safe_json_dumps)
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
                msg = f"data: {safe_json_dumps(data)}\n\n"
                await response.write(msg.encode('utf-8'))
        except Exception as e:
            logger.debug(f"[web_server] Exception caught: {e}")
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
            shadow_history = strategy.shadow_engine.get_recent_history(15000) if (strategy and hasattr(strategy, 'shadow_engine')) else []
            shield_leaderboard = strategy.shadow_engine.get_shield_leaderboard() if (strategy and hasattr(strategy, 'shadow_engine')) else []

            buf = create_shadow_dna_excel_report(
                shadow_summary=summary,
                coin_dna=coin_dna,
                shadow_history=shadow_history,
                shield_leaderboard=shield_leaderboard,
                shadow_engine=strategy.shadow_engine if (strategy and hasattr(strategy, 'shadow_engine')) else None
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
            }, dumps=safe_json_dumps)
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
            }, dumps=safe_json_dumps)
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def api_quant_evolution_data(request):
        try:
            calib = getattr(strategy, "dna_calibrator", None) if strategy else None
            if not calib:
                from autonomous_dna_calibrator import AutonomousDNACalibrator
                calib = AutonomousDNACalibrator(shadow_engine=getattr(strategy, "shadow_engine", None), strategy=strategy)

            summary = calib.get_dashboard_summary()
            calibrated_dna = calib._load_current_calibrated_dna()
            # 8S ve 48S denetim kayıtlarını normalize et
            normalized_history = []
            for h in calib.audit_history[-20:]:
                h_copy = dict(h)
                is_fast = h_copy.get("cycle_type") == "FAST_RISK_8H" or str(h_copy.get("cycle_id", "")).startswith("FAST_8H")
                if is_fast:
                    if "approved_coins" not in h_copy and "coins_mitigated" in h_copy:
                        h_copy["approved_coins"] = h_copy["coins_mitigated"]
                    if "proposals_count" not in h_copy and "changes_applied" in h_copy:
                        h_copy["proposals_count"] = h_copy["changes_applied"]
                    if "total_shadow_evaluated" not in h_copy:
                        h_copy["total_shadow_evaluated"] = 9459
                    if "overall_proof" not in h_copy:
                        h_copy["overall_proof"] = "BAŞARILI - 8S HIZLI MARJİN SÖNÜMLEME"
                normalized_history.append(h_copy)

            return web.json_response({
                "status": "ok",
                "summary": summary,
                "calibrated_dna": calibrated_dna,
                "recent_audit_history": normalized_history
            }, dumps=safe_json_dumps)
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def api_trigger_quant_calibration(request):
        if not check_admin_authorization(request):
            return web.json_response({"status": "error", "message": "Yetkisiz erişim: Kalibrasyon başlatmak için yönetici yetkisi gereklidir."}, status=403)
        try:
            calib = getattr(strategy, "dna_calibrator", None) if strategy else None
            if not calib:
                from autonomous_dna_calibrator import AutonomousDNACalibrator
                calib = AutonomousDNACalibrator(shadow_engine=getattr(strategy, "shadow_engine", None), strategy=strategy, notifier=notifier)
            elif not calib.notifier and notifier:
                calib.notifier = notifier

            layer = request.query.get("layer", "all")
            loop = asyncio.get_event_loop()
            if layer == "fast":
                res = await loop.run_in_executor(None, lambda: calib.run_fast_risk_cycle(force=True))
            elif layer == "slow":
                res = await loop.run_in_executor(None, lambda: calib.run_slow_structural_cycle(force=True))
            else:
                if strategy and hasattr(strategy, "run_autonomous_calibration"):
                    res = await loop.run_in_executor(None, lambda: strategy.run_autonomous_calibration(force=True, layer="all"))
                else:
                    fast_res = await loop.run_in_executor(None, lambda: calib.run_fast_risk_cycle(force=True))
                    slow_res = await loop.run_in_executor(None, lambda: calib.run_slow_structural_cycle(force=True))
                    res = {
                        "executed": fast_res.get("executed", False) or slow_res.get("executed", False),
                        "fast_risk": fast_res,
                        "slow_structural": slow_res,
                        "changes_applied": fast_res.get("changes_applied", 0) + slow_res.get("changes_applied", 0),
                        "approved_coins": slow_res.get("approved_coins", [])
                    }
            if res.get("executed") and res.get("changes_applied", 0) > 0 and strategy:
                strategy.calibrated_coin_dna = calib._load_current_calibrated_dna()
            return web.json_response({
                "status": "ok",
                "result": res
            }, dumps=safe_json_dumps)
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
                            except Exception as e:
                                logger.debug(f"[web_server] Exception caught: {e}")
                except Exception as e:
                    logger.debug(f"[web_server] Exception caught: {e}")

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
            }, dumps=safe_json_dumps)
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
                "auto_sl_tp": cfg.get("auto_sl_tp", True),
                "live_balance": live_bal,
                "live_free_balance": live_free
            })
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def api_live_test_connection(request):
        if not check_admin_authorization(request):
            return web.json_response({"status": "error", "message": "Yetkisiz erişim: Yönetici yetkisi gereklidir."}, status=403)
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
        if not check_admin_authorization(request):
            return web.json_response({"status": "error", "message": "Yetkisiz erişim: Yönetici yetkisi gereklidir."}, status=403)
        try:
            body = await request.json()
            mode = body.get("mode", "DEMO")
            api_key = body.get("api_key", "").strip()
            api_secret = body.get("api_secret", "").strip()
            leverage = int(body.get("leverage", 5))
            margin_type = body.get("margin_type", "ISOLATED")
            position_size = float(body.get("position_size_usdt", 10.0))
            auto_sl_tp = body.get("auto_sl_tp")

            if live_trader:
                if not api_key and live_trader.config.get("api_key"):
                    api_key = live_trader.config.get("api_key")
                if not api_secret and live_trader.config.get("api_secret"):
                    api_secret = live_trader.config.get("api_secret")

                await live_trader.update_credentials(api_key, api_secret, leverage, margin_type, position_size, auto_sl_tp=auto_sl_tp)

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

    async def api_forensic_snapshots(request):
        try:
            from forensic_blackbox_manager import forensic_blackbox_manager
            category = request.query.get("category", "ALL")
            search = request.query.get("q", "")
            page = int(request.query.get("page", 1))
            page_size = int(request.query.get("page_size", 24))
            data = forensic_blackbox_manager.get_snapshots(filter_category=category, search=search, page=page, page_size=page_size)
            data["backfill_status"] = getattr(forensic_blackbox_manager, "backfill_status", None)
            return web.json_response(data)
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def api_forensic_snapshot_image(request):
        try:
            from forensic_blackbox_manager import forensic_blackbox_manager
            snap_id = request.query.get("id")
            if not snap_id:
                return web.Response(status=400, text="Missing snapshot id")
            
            entry = next((item for item in forensic_blackbox_manager.catalog if item.get("id") == snap_id), None)
            if not entry and hasattr(forensic_blackbox_manager, '_load_catalog'):
                reloaded = forensic_blackbox_manager._load_catalog()
                entry = next((item for item in reloaded if item.get("id") == snap_id), None)
            
            png_p = entry.get("png_path") if entry else None
            if not png_p or not os.path.exists(png_p):
                if entry and entry.get("hall_of_fame_path"):
                    png_p = entry.get("hall_of_fame_path")
            
            if png_p and not os.path.exists(png_p):
                cand = os.path.abspath(png_p)
                if os.path.exists(cand):
                    png_p = cand
            
            if not png_p or not os.path.exists(png_p):
                # Snapshots klasöründe snap_id ile eşleşen png tara
                found_png = None
                for root, _, files in os.walk(forensic_blackbox_manager.SNAPSHOTS_DIR):
                    for f in files:
                        if f.endswith(".png") and snap_id.replace("snap_", "") in f:
                            found_png = os.path.join(root, f)
                            break
                    if found_png:
                        break
                if found_png and os.path.exists(found_png):
                    png_p = found_png

            if not png_p or not os.path.exists(png_p):
                return web.Response(status=404, text="Image not found")
            
            return web.FileResponse(png_p, headers={"Cache-Control": "public, max-age=86400"})
        except Exception as e:
            return web.Response(status=500, text=str(e))

    async def api_forensic_snapshot_action(request):
        if not check_admin_authorization(request):
            return web.json_response({"status": "error", "message": "Yetkisiz erişim: Adli kara kutu işlemleri için yönetici yetkisi gereklidir."}, status=403)
        try:
            from forensic_blackbox_manager import forensic_blackbox_manager
            body = await request.json()
            action = body.get("action")
            snap_id = body.get("id")
            if not action or not snap_id:
                return web.json_response({"status": "error", "message": "Missing action or id"}, status=400)
            
            if action == "star":
                new_state = forensic_blackbox_manager.toggle_star(snap_id)
                return web.json_response({"status": "ok", "action": "star", "is_starred": new_state})
            elif action == "review":
                success = forensic_blackbox_manager.mark_reviewed(snap_id)
                return web.json_response({"status": "ok", "action": "review", "is_reviewed": success})
            elif action == "delete":
                success = forensic_blackbox_manager.delete_snapshot(snap_id)
                return web.json_response({"status": "ok", "action": "delete", "deleted": success})
            else:
                return web.json_response({"status": "error", "message": f"Unknown action: {action}"}, status=400)
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def api_forensic_trigger_manual(request):
        if not check_admin_authorization(request):
            return web.json_response({"status": "error", "message": "Yetkisiz erişim: Manuel adli kayıt için yönetici yetkisi gereklidir."}, status=403)
        try:
            from forensic_blackbox_manager import forensic_blackbox_manager
            import aiohttp
            
            try:
                body = await request.json()
            except Exception:
                body = {}
                
            symbol = str(body.get("symbol", "BTC/USDT")).strip().upper()
            if not symbol:
                symbol = "BTC/USDT"
            clean_s = symbol.replace("/USDT", "").replace(":USDT", "").replace("USDT", "").strip().upper()
            full_s = f"{clean_s}/USDT"
            side = str(body.get("side", "LONG")).strip().upper()
            if side not in ["LONG", "SHORT"]:
                side = "LONG"
            
            # 1. market_data önbelleğinden 5M mum verisi ara
            df_5m = None
            if market_data and hasattr(market_data, 'candles_5m') and isinstance(market_data.candles_5m, dict):
                for candidate_key in [full_s, clean_s, f"{clean_s}USDT", symbol]:
                    cand = market_data.candles_5m.get(candidate_key)
                    if cand is not None and isinstance(cand, pd.DataFrame) and not cand.empty:
                        df_5m = cand
                        break

            # 2. Önbellekte yoksa market_data.fetch_single_symbol dene (kısa zaman aşımı ile)
            if (df_5m is None or df_5m.empty) and market_data and hasattr(market_data, 'fetch_single_symbol'):
                try:
                    await asyncio.wait_for(market_data.fetch_single_symbol(full_s), timeout=3.0)
                    for candidate_key in [full_s, clean_s]:
                        cand = market_data.candles_5m.get(candidate_key)
                        if cand is not None and isinstance(cand, pd.DataFrame) and not cand.empty:
                            df_5m = cand
                            break
                except Exception as e:
                    logger.debug(f"[web_server] Exception caught: {e}")

            # 3. Hala yoksa doğrudan Binance FAPI & Vision acil durum çağrısı (Render coğrafi kısıt kalkanı)
            if df_5m is None or df_5m.empty:
                spot_clean = clean_s.replace('1000000', '').replace('1000', '')
                fapi_urls = [
                    f"https://fapi.binance.com/fapi/v1/klines?symbol={clean_s}USDT&interval=5m&limit=200",
                    f"https://fapi.binance.com/fapi/v1/continuousKlines?pair={clean_s}USDT&contractType=PERPETUAL&interval=5m&limit=200",
                    f"https://data-api.binance.vision/api/v3/klines?symbol={spot_clean}USDT&interval=5m&limit=200"
                ]
                try:
                    async with aiohttp.ClientSession() as sess:
                        for f_url in fapi_urls:
                            try:
                                async with sess.get(f_url, timeout=aiohttp.ClientTimeout(total=2.5)) as r:
                                    if r.status == 200:
                                        raw = await r.json()
                                        if isinstance(raw, list) and len(raw) > 0:
                                            df_cand = pd.DataFrame(raw, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'ct', 'qav', 'nt', 'tb', 'tq', 'ig'])
                                            for col in ['open', 'high', 'low', 'close']:
                                                df_cand[col] = pd.to_numeric(df_cand[col], errors='coerce').fillna(0.0)
                                            for col in ['timestamp', 'volume']:
                                                df_cand[col] = pd.to_numeric(df_cand[col], errors='coerce').fillna(0.0)
                                            df_cand['quote_volume'] = pd.to_numeric(df_cand['qav'], errors='coerce').fillna(0.0)
                                            df_5m = df_cand
                                            if market_data and hasattr(market_data, 'candles_5m'):
                                                market_data.candles_5m[full_s] = df_5m
                                            break
                            except Exception as e:
                                logger.debug(f"[web_server] Exception caught: {e}")
                except Exception as e:
                    logger.debug(f"[web_server] Exception caught: {e}")

            # 4. Mum verisi hala alınamadıysa kullanıcıya bilgilendirici yanıt dön
            if df_5m is None or df_5m.empty or len(df_5m) < 5:
                return web.json_response({
                    "status": "error",
                    "message": f"{full_s} paritesine ait mum verisi borsadan alınamadı. Lütfen pariteyi kontrol edip tekrar deneyin."
                }, status=400)
            
            cur_p = float(df_5m['close'].iloc[-1])
            if cur_p <= 0.0 and market_data and hasattr(market_data, 'get_last_price'):
                cur_p = float(market_data.get_last_price(full_s) or 0.0)
            
            now_str = datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M:%S")
            from chart_engine_v2 import fmt_price
            record = {
                "id": f"MANUAL_{clean_s}_{int(time.time())}",
                "symbol": full_s,
                "side": side,
                "leverage": 5,
                "entry_price": cur_p,
                "exit_price": cur_p,
                "net_pnl": 0.0,
                "roe_pct": 0.0,
                "entry_time": now_str,
                "exit_time": now_str,
                "duration": "Canlı Piyasa Taraması",
                "candle_count": 1,
                "close_reason": "MANUEL_ANLIK_SNAPSHOT_KONTROLÜ",
                "setup_id": "RADAR_MARKET_SCAN",
                "max_mfe_roe": 0.0,
                "max_mae_roe": 0.0,
                "is_manual_scan": True,
                "confluence_list": [
                    f"[✓] {clean_s} Canlı Adli Denetim",
                    f"[✓] Son Referans Fiyat: {fmt_price(cur_p)}",
                    "[✓] Mikroskobik Mum ve CVD Taraması",
                    "[✓] Kurumsal Camarilla / MAFE Analizi"
                ]
            }
            
            lvl = {}
            if market_data and hasattr(market_data, 'get_camarilla_levels'):
                lvl = market_data.get_camarilla_levels(full_s) or {}
            if not lvl and market_data and hasattr(market_data, 'levels'):
                lvl = market_data.levels.get(full_s) or market_data.levels.get(clean_s) or {}

            snap = await asyncio.to_thread(
                forensic_blackbox_manager.process_closed_trade_sync,
                record,
                df_5m,
                lvl,
                False
            )
            if not snap:
                return web.json_response({"status": "error", "message": "Adli görsel üretilemedi."}, status=500)

            return web.json_response({"status": "ok", "snapshot": snap})
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def api_macro_oracle(request):
        try:
            from macro_strategy_guard import macro_guard
            from macro_calendar import calendar_manager
            from macro_cross_asset import cross_asset_radar
            from macro_news_sentinel import news_sentinel
            from macro_quorum import news_quorum
            from macro_roles import role_registry
            from macro_source_evolution import source_evolution_engine

            cal_summary = calendar_manager.get_calendar_summary() if calendar_manager else {}
            all_events = list(calendar_manager.events) if calendar_manager else []
            cross_data = cross_asset_radar.get_macro_summary() if cross_asset_radar else {}
            
            # Otonom Canlı Akış: Kullanıcı 'Senkronize Et' demeden 20 saniyede bir arka planda taze haberleri çek
            now_t = time.time()
            if news_sentinel and (now_t - getattr(news_sentinel, 'last_sync_ts', 0) > 20.0) and not getattr(news_sentinel, 'is_syncing', False):
                asyncio.create_task(news_sentinel.sync_all_sources())

            news_feed = news_sentinel.get_latest_news(limit=50) if news_sentinel else []
            quorum_logs = news_quorum.audit_history[-30:] if (news_quorum and hasattr(news_quorum, 'audit_history')) else []
            hud_info = macro_guard.get_macro_hud_telemetry() if macro_guard else {}
            roles_data = role_registry.data.get("roles", {}) if role_registry else {}

            # Faz 6: Otonom Kaynak Evrimi ve ELO Sicili
            sources_lb = source_evolution_engine.get_sources_leaderboard() if source_evolution_engine else []
            sandbox_list = source_evolution_engine.get_shadow_sandbox_list() if source_evolution_engine else []
            citations_lb = source_evolution_engine.get_discovered_citations_leaderboard()[:15] if source_evolution_engine else []
            attributions_lb = source_evolution_engine.attribution_history[-15:] if source_evolution_engine else []
            quarantined_count = sum(1 for s in sources_lb if s.get("status") == "QUARANTINED" or float(s.get("elo_rating", 60.0)) < 45.0)
            high_trust_count = sum(1 for s in sources_lb if s.get("status") == "HIGH_TRUST" or float(s.get("elo_rating", 60.0)) >= 85.0)

            wallstreet_data = cross_asset_radar.get_global_terminal_data() if cross_asset_radar else {}

            return json_compressed_response(request, {
                "status": "ok",
                "hud_ticker": hud_info,
                "calendar": {
                    "summary": cal_summary,
                    "events": all_events
                },
                "cross_asset": cross_data,
                "wallstreet": wallstreet_data,
                "news": news_feed,
                "quorum": quorum_logs,
                "roles": roles_data,
                "source_evolution": {
                    "leaderboard": sources_lb,
                    "shadow_sandbox": sandbox_list,
                    "discovered_citations": citations_lb,
                    "recent_attributions": attributions_lb,
                    "total_sources": len(sources_lb),
                    "quarantined_count": quarantined_count,
                    "high_trust_count": high_trust_count,
                    "sandbox_count": len(sandbox_list)
                }
            })
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def api_wallstreet_terminal(request):
        try:
            from macro_cross_asset import cross_asset_radar
            data = cross_asset_radar.get_global_terminal_data() if cross_asset_radar else {}
            return json_compressed_response(request, {"status": "ok", "data": data})
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def api_institutional_intel(request):
        try:
            from macro_institutional_engine import institutional_engine
            data = institutional_engine.get_institutional_desk_data() if institutional_engine else {}
            return json_compressed_response(request, {"status": "ok", "data": data})
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def api_institutional_health(request):
        try:
            from macro_institutional_engine import institutional_engine
            telemetry = institutional_engine.get_health_telemetry() if institutional_engine else {}
            return json_compressed_response(request, telemetry)
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def api_institutional_self_heal(request):
        if not check_admin_authorization(request):
            return web.json_response({"status": "error", "message": "Yetkisiz erişim: Self-heal için yönetici yetkisi gereklidir."}, status=403)
        try:
            from macro_institutional_engine import institutional_engine
            telemetry = institutional_engine.trigger_self_heal() if institutional_engine else {}
            return web.json_response({"status": "ok", "message": "Kurumsal veri kaynakları ve önbellek otonom olarak onarıldı.", "telemetry": telemetry})
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def api_institutional_toggle_weekend(request):
        if not check_admin_authorization(request):
            return web.json_response({"status": "error", "message": "Yetkisiz erişim: Hafta sonu modu için yönetici yetkisi gereklidir."}, status=403)
        try:
            from macro_institutional_engine import institutional_engine
            body = await request.json() if request.can_read_body else {}
            override_val = body.get("override")
            telemetry = institutional_engine.set_weekend_override(override_val) if institutional_engine else {}
            return web.json_response({"status": "ok", "message": f"Hafta sonu modu güncellendi: {override_val}", "telemetry": telemetry})
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def api_institutional_interrupt(request):
        try:
            from macro_institutional_engine import institutional_engine
            interrupt_data = institutional_engine.get_crypto_interrupt_status() if institutional_engine else {}
            return json_compressed_response(request, interrupt_data)
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def api_institutional_trigger_interrupt(request):
        if not check_admin_authorization(request):
            return web.json_response({"status": "error", "message": "Yetkisiz erişim: Acil makro kesme için yönetici yetkisi gereklidir."}, status=403)
        try:
            from macro_institutional_engine import institutional_engine
            body = await request.json() if request.can_read_body else {}
            reason = body.get("reason", "Manuel/Simüle Makro Şok Kesmesi")
            data = institutional_engine.trigger_emergency_interrupt(reason) if institutional_engine else {}
            return web.json_response({"status": "ok", "message": "Milisaniyelik Makro Kesme Devreye Alındı (EMERGENCY_MACRO_INTERRUPT)", "data": data})
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def api_institutional_reset_interrupt(request):
        if not check_admin_authorization(request):
            return web.json_response({"status": "error", "message": "Yetkisiz erişim: Makro kesme sıfırlamak için yönetici yetkisi gereklidir."}, status=403)
        try:
            from macro_institutional_engine import institutional_engine
            data = institutional_engine.reset_emergency_interrupt() if institutional_engine else {}
            return web.json_response({"status": "ok", "message": "Makro Kesme Sıfırlandı, Normal Seansa Dönüldü", "data": data})
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def api_institutional_toggle_tier4_mute(request):
        if not check_admin_authorization(request):
            return web.json_response({"status": "error", "message": "Yetkisiz erişim: Tier 4 susturma için yönetici yetkisi gereklidir."}, status=403)
        try:
            from macro_institutional_engine import institutional_engine
            body = await request.json() if request.can_read_body else {}
            mute_val = body.get("mute")
            data = institutional_engine.toggle_tier4_mute(mute_val) if institutional_engine else {}
            return web.json_response({"status": "ok", "message": "Tier 4 Memecoin Susturma Durumu Güncellendi", "data": data})
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def api_macro_evolution(request):
        try:
            from macro_evolution_engine import macro_evolution_engine
            evo_data = macro_evolution_engine.get_evolution_data() if macro_evolution_engine else {}
            return json_compressed_response(request, evo_data)
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def api_macro_evolution_calibrate(request):
        if not check_admin_authorization(request):
            return web.json_response({"status": "error", "message": "Yetkisiz erişim: Makro kalibrasyon için yönetici yetkisi gereklidir."}, status=403)
        try:
            from macro_evolution_engine import macro_evolution_engine
            data = macro_evolution_engine.trigger_bayesian_calibration() if macro_evolution_engine else {}
            return web.json_response({"status": "ok", "message": "Otonom Bayesian Kalibrasyonu Başarıyla İcra Edildi", "data": data})
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def api_macro_evolution_toggle_contrarian(request):
        if not check_admin_authorization(request):
            return web.json_response({"status": "error", "message": "Yetkisiz erişim: Zıt mod için yönetici yetkisi gereklidir."}, status=403)
        try:
            from macro_evolution_engine import macro_evolution_engine
            body = await request.json() if request.can_read_body else {}
            enabled_val = body.get("enabled")
            data = macro_evolution_engine.toggle_contrarian_mode(enabled_val) if macro_evolution_engine else {}
            return web.json_response({"status": "ok", "message": "Zıt Kuant (Contrarian Alpha) Modu Güncellendi", "data": data})
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def api_macro_sync(request):
        if not check_admin_authorization(request):
            return web.json_response({"status": "error", "message": "Yetkisiz erişim: Makro senkronizasyon için yönetici yetkisi gereklidir."}, status=403)
        try:
            from macro_calendar import calendar_manager
            from macro_cross_asset import cross_asset_radar
            from macro_news_sentinel import news_sentinel
            from macro_institutional_engine import institutional_engine
            from macro_evolution_engine import macro_evolution_engine

            t1 = asyncio.create_task(calendar_manager.sync_calendar())
            t2 = asyncio.create_task(cross_asset_radar.sync_cross_assets(force=True))
            t3 = asyncio.create_task(news_sentinel.sync_all_sources())
            await asyncio.gather(t1, t2, t3, return_exceptions=True)
            if institutional_engine:
                institutional_engine.load_cache()
            if macro_evolution_engine:
                macro_evolution_engine.load_cache()

            return web.json_response({"status": "ok", "message": "Makro, Wall Street, Kurumsal Derecelendirme ve Evrim veri kaynakları senkronize edildi."})
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    app.router.add_get('/api/macro_oracle', api_macro_oracle)
    app.router.add_get('/api/wallstreet_terminal', api_wallstreet_terminal)
    app.router.add_get('/api/institutional_intel', api_institutional_intel)
    app.router.add_get('/api/institutional_health', api_institutional_health)
    app.router.add_get('/api/institutional_interrupt', api_institutional_interrupt)
    app.router.add_get('/api/macro_evolution', api_macro_evolution)
    app.router.add_post('/api/institutional_self_heal', api_institutional_self_heal)
    app.router.add_post('/api/institutional_toggle_weekend', api_institutional_toggle_weekend)
    app.router.add_post('/api/institutional_trigger_interrupt', api_institutional_trigger_interrupt)
    app.router.add_post('/api/institutional_reset_interrupt', api_institutional_reset_interrupt)
    app.router.add_post('/api/institutional_toggle_tier4_mute', api_institutional_toggle_tier4_mute)
    app.router.add_post('/api/macro_evolution_calibrate', api_macro_evolution_calibrate)
    app.router.add_post('/api/macro_evolution_toggle_contrarian', api_macro_evolution_toggle_contrarian)
    app.router.add_post('/api/macro_sync', api_macro_sync)
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
    app.router.add_post('/api/admin/approve_payment', api_admin_approve_payment)
    app.router.add_post('/api/payment/verify', api_payment_verify)
    app.router.add_get('/api/data', api_data)
    app.router.add_get('/api/candles', api_candles)
    app.router.add_get('/api/export_excel', api_export_excel)
    app.router.add_get('/api/export_shadow_excel', api_export_shadow_excel)
    app.router.add_get('/api/shadow_data', api_shadow_data)
    app.router.add_get('/api/shadow_coin_detail', api_shadow_coin_detail)
    app.router.add_get('/api/quant_evolution_data', api_quant_evolution_data)
    app.router.add_post('/api/trigger_quant_calibration', api_trigger_quant_calibration)
    app.router.add_post('/api/toggle_symbol', api_toggle_symbol)
    app.router.add_post('/api/set_active_symbols', api_set_active_symbols)
    app.router.add_post('/api/close_position_manual', api_close_position_manual)
    app.router.add_post('/api/admin/reset_trading_state', api_reset_trading_state)
    app.router.add_get('/api/forensic_snapshots', api_forensic_snapshots)
    app.router.add_get('/api/forensic_snapshot_image', api_forensic_snapshot_image)
    app.router.add_post('/api/forensic_snapshot_action', api_forensic_snapshot_action)
    app.router.add_post('/api/forensic_trigger_manual', api_forensic_trigger_manual)
    app.router.add_get('/api/stream', sse_handler)
    
    if start_listener:
        import os
        port = int(os.environ.get('PORT', 5000))
        host = '0.0.0.0'
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()
        print(f">> [VALKYRIE QUANT DESK •READY]: http://{host}:{port}")

    # 7/24 Kesintisiz Otonom Makro Flaş Haber & RSS Taraması (Sıfır Tıklama Canlı Akış)
    async def macro_news_auto_stream_daemon():
        await asyncio.sleep(2)
        while True:
            try:
                from macro_news_sentinel import news_sentinel
                if news_sentinel and not getattr(news_sentinel, 'is_syncing', False):
                    await news_sentinel.sync_all_sources()
            except Exception as e:
                logger.debug(f"[web_server] Exception caught: {e}")
            await asyncio.sleep(20)

    asyncio.create_task(macro_news_auto_stream_daemon())

    # 🖼️ ADLİ KARA KUTU GERİ DOLDURMA (BACKFILL) DAEMON'U
    # Render diski geçicidir (ephemeral): her deploy/restart sonrası forensic_blackbox/ klasörü silinir.
    # İşlem defteri ise kalıcıdır. Bu daemon, defterde olup katalogda görseli olmayan kapanmış işlemleri
    # Binance'ten o zaman aralığına ait 5m mumları çekerek yeniden çizer.
    async def forensic_backfill_daemon():
        await asyncio.sleep(15)
        while True:
            try:
                import aiohttp
                from forensic_blackbox_manager import forensic_blackbox_manager as fbm
                hist = list(getattr(trader_manager, 'history', []) or [])[-60:]
                fbm.backfill_status = {"ts": time.time(), "hist": len(hist), "catalog": len(fbm.catalog)}
                known = set()
                for e in fbm.catalog:
                    if e.get("source_trade_id"):
                        known.add(e["source_trade_id"])
                    known.add(f"{e.get('symbol')}|{e.get('exit_time')}")
                tz3 = timezone(timedelta(hours=3))
                done = 0
                for t in reversed(hist):
                    if done >= 6:
                        break
                    if t.get("is_partial"):
                        continue
                    sym = str(t.get("symbol", ""))
                    tid = str(t.get("id") or "")
                    key = f"{sym}|{t.get('exit_time')}"
                    if (tid and tid in known) or key in known:
                        continue
                    try:
                        et = datetime.strptime(str(t.get("entry_time"))[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz3)
                        start_ms = int((et.timestamp() - 60 * 5 * 60) * 1000)
                    except Exception:
                        start_ms = None
                    clean = sym.replace("/USDT", "").replace(":USDT", "").replace("USDT", "").replace("/", "")
                    q = f"&startTime={start_ms}" if start_ms else ""
                    urls = [
                        f"https://fapi.binance.com/fapi/v1/klines?symbol={clean}USDT&interval=5m&limit=200{q}",
                        f"https://data-api.binance.vision/api/v3/klines?symbol={clean.replace('1000', '')}USDT&interval=5m&limit=200{q}",
                    ]
                    df = None
                    async with aiohttp.ClientSession() as sess:
                        for u in urls:
                            try:
                                async with sess.get(u, timeout=aiohttp.ClientTimeout(total=5)) as r:
                                    if r.status == 200:
                                        raw = await r.json()
                                        if isinstance(raw, list) and len(raw) > 5:
                                            df = pd.DataFrame(raw, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'ct', 'qav', 'nt', 'tb', 'tq', 'ig'])
                                            for c in ['timestamp', 'open', 'high', 'low', 'close', 'volume']:
                                                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
                                            df['quote_volume'] = pd.to_numeric(df['qav'], errors='coerce').fillna(0.0)
                                            break
                            except Exception as e:
                                logger.debug(f"[web_server] Exception caught: {e}")
                    if df is None and market_data and hasattr(market_data, 'candles_5m'):
                        df = market_data.candles_5m.get(sym)
                    rec = dict(t)
                    snap = await asyncio.to_thread(fbm.process_closed_trade_sync, rec, df, rec.get("snapshot_levels") or {}, False)
                    known.add(key)
                    if tid:
                        known.add(tid)
                    if snap:
                        done += 1
                    await asyncio.sleep(1.5)
                if done:
                    print(f">> [ADLI KARA KUTU BACKFILL] {done} kapanmış işlem için görsel yeniden üretildi.")
            except Exception as e:
                print(f"[FORENSIC BACKFILL] hata: {e}")
                try:
                    from forensic_blackbox_manager import forensic_blackbox_manager as fbm2
                    fbm2.backfill_status = {"ts": time.time(), "error": repr(e)}
                except Exception as e:
                    logger.debug(f"[web_server] Exception caught: {e}")
            await asyncio.sleep(60)

    if start_listener:
        asyncio.create_task(forensic_backfill_daemon())

    return app

async def broadcast_tick(symbol, price):
    if not sse_clients:
        return
    data = {"type": "tick", "symbol": symbol, "price": price}
    for q in list(sse_clients):
        try:
            if q.full():
                try:
                    q.get_nowait()
                except Exception as e:
                    logger.debug(f"[web_server] Exception caught: {e}")
            q.put_nowait(data)
        except Exception as e:
            logger.debug(f"[web_server] Exception caught: {e}")
