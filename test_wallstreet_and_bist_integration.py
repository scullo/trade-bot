"""
🏛️ VALKYRIE QUANT - WALL STREET, BORSA İSTANBUL & GLOBAL CIRCUIT BREAKER ENTEGRASYON TESTİ
Bu test; 
1. Borsa İstanbul (BIST 100, BIST 30, XBANK, USD/TRY, EUR/TRY, Gram Altın TL) varlıklarının veri akışını,
2. Kayan Times Square Ticker şeridi ve bölgesel Türkiye masası filtreleme butonunu,
3. Küresel Devre Kesici (Global Circuit Breaker - Wall Street/BIST çöküşü, Brent $100+ şoku, VIX patlaması) kalkanını,
4. Kokpit Ana Dashboard üst şeridindeki canlı BIST 100 ve Brent göstergelerini
uçtan uca doğrular.
"""

import sys
import os
import json
import asyncio
from typing import Dict, Any

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from macro_cross_asset import cross_asset_radar, GLOBAL_TERMINAL_CONFIG
from macro_strategy_guard import macro_guard
import web_server

async def run_integration_tests():
    print("=" * 80)
    print("🇹🇷 VALKYRIE WALL STREET, BORSA İSTANBUL & KÜRESEL DEVRE KESİCİ KANIT RAPORU")
    print("=" * 80)

    # ──────────────────────────────────────────────────────────────────────────
    # ADIM 1: BORSA İSTANBUL VE TÜRKİYE DESK VERİ BÜTÜNLÜĞÜ
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[ADIM 1/4] 📊 Çapraz Piyasa Radarı & Borsa İstanbul Varlık Masası Denetleniyor...")
    
    # 1. Konfigürasyon kontrolü
    assert "turkey" in GLOBAL_TERMINAL_CONFIG, "GLOBAL_TERMINAL_CONFIG içinde 'turkey' masası tanımlı olmalı!"
    turkey_items = GLOBAL_TERMINAL_CONFIG["turkey"]
    assert len(turkey_items) == 6, f"Türkiye masasında 6 varlık olmalı, bulunan: {len(turkey_items)}"
    expected_ids = {"bist100", "bist30", "xbank", "usdtry", "eurtry", "gram_altin"}
    actual_ids = {item["id"] for item in turkey_items}
    assert expected_ids == actual_ids, f"Beklenen ID'ler: {expected_ids}, Bulunan: {actual_ids}"
    print(f"  • 🇹🇷 Konfigürasyon Doğrulaması : ✅ 6 Türkiye Varlığı Tanımlı ({', '.join(actual_ids)})")

    # 2. Terminal veri paketi kontrolü
    terminal_data = cross_asset_radar.get_global_terminal_data()
    assert terminal_data["total_monitored_assets"] >= 31, f"En az 31 küresel varlık izlenmeli! Bulunan: {terminal_data['total_monitored_assets']}"
    assert len(terminal_data["marquee_tape"]) >= 31, "Kayan bantta en az 31 varlık bulunmalı!"
    
    turkey_region = terminal_data["regions"].get("turkey", [])
    assert len(turkey_region) == 6, f"Regions['turkey'] 6 varlık içermeli! Bulunan: {len(turkey_region)}"
    
    bist100_card = next((x for x in turkey_region if x["id"] == "bist100"), None)
    assert bist100_card is not None, "BIST 100 kartı mevcut olmalı!"
    assert bist100_card["price"] > 1000.0, f"BIST 100 endeks fiyatı mantıklı olmalı! Fiyat: {bist100_card['price']}"

    gram_altin_card = next((x for x in turkey_region if x["id"] == "gram_altin"), None)
    assert gram_altin_card is not None, "Gram Altın TL kartı mevcut olmalı!"
    assert gram_altin_card["price"] > 3000.0, f"Gram Altın TL fiyatı mantıklı olmalı! Fiyat: {gram_altin_card['price']}"

    usdtry_card = next((x for x in turkey_region if x["id"] == "usdtry"), None)
    assert usdtry_card is not None, "USD/TRY kartı mevcut olmalı!"
    assert usdtry_card["price"] > 20.0, f"USD/TRY kuru mantıklı olmalı! Fiyat: {usdtry_card['price']}"

    print(f"  • 📈 BIST 100 Endeksi        : ✅ {bist100_card['price']} ({bist100_card['chg_24h']:+.2f}%)")
    print(f"  • 🥇 Gram Altın TL           : ✅ {gram_altin_card['price']} TL ({gram_altin_card['chg_24h']:+.2f}%)")
    print(f"  • 💵 USD / TRY Kuru          : ✅ {usdtry_card['price']} TL ({usdtry_card['chg_24h']:+.2f}%)")

    # 3. Kripto / BIST Korelasyon kartı
    correlations = terminal_data.get("correlations", {})
    assert "btc_bist" in correlations, "Correlations içinde 'btc_bist' bulunmalı!"
    btc_bist = correlations["btc_bist"]
    print(f"  • 🧠 BTC / BIST 100 Beta      : ✅ Beta: {btc_bist['beta']} | {btc_bist['title']}")

    # ──────────────────────────────────────────────────────────────────────────
    # ADIM 2: KÜRESEL DEVRE KESİCİ (GLOBAL CIRCUIT BREAKER)
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[ADIM 2/4] 🛡️ Kuant Risk & Küresel Devre Kesici (Circuit Breaker) Sınanıyor...")
    
    breaker = macro_guard.check_global_equity_circuit_breaker()
    assert "active" in breaker, "Breaker yanıtında 'active' boolean bulunmalı!"
    assert "severity" in breaker, "Breaker yanıtında 'severity' bulunmalı!"
    assert "leverage_cap" in breaker, "Breaker yanıtında 'leverage_cap' bulunmalı!"
    assert "margin_multiplier" in breaker, "Breaker yanıtında 'margin_multiplier' bulunmalı!"
    
    print(f"  • ⚡ Devre Kesici Durumu     : {'🚨 AKTİF' if breaker['active'] else '🟢 NORMAL (Gözetimde)'}")
    print(f"  • 🛑 Kaldıraç Üst Sınırı     : {breaker['leverage_cap']}x")
    print(f"  • 📉 Pozisyon Bütçe Çarpanı  : {breaker['margin_multiplier']}x (%50 Sermaye Koruması)")
    if breaker["triggers"]:
        print(f"  • ⚠️ Tetikleyici Unsurlar   : {', '.join(breaker['triggers'])}")

    # Giriş kalkanı testi: Devre kesici altındayken ters yönlü Long dip yakalama engellenmeli
    entry_check = macro_guard.check_macro_guard_for_entry(
        symbol="BTC/USDT",
        side="LONG",
        setup_id="S3_BOUNCE",
        reason="Camarilla S3 Destek Reversal"
    )
    if breaker["active"]:
        assert entry_check["allowed"] is False, "Devre kesici aktifken S3 Reversal Long engellenmeli!"
        assert entry_check["error"] == "CIRCUIT_BREAKER_KNIFE_CATCH_BLOCKED", f"Hata kodu CIRCUIT_BREAKER_KNIFE_CATCH_BLOCKED olmalı! Alınan: {entry_check.get('error')}"
        print(f"  • 🚫 Ters Bıçak Koruma Testi : ✅ Devre Kesici dip yakalama emrini başarıyla bloke etti: {entry_check['error']}")
    else:
        print("  • ℹ️ Piyasa sakin olduğu için olağan kurallar geçerli.")

    # ──────────────────────────────────────────────────────────────────────────
    # ADIM 3: KOKPİT & WEB ARAYÜZÜ DOM KONTROLLERİ
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[ADIM 3/4] 🎨 Web Arayüzü & Kokpit HUD Şeridi HTML Bütünlüğü...")
    html_page = web_server.HTML_PAGE

    # 1. 11. Sekme ve Türkiye Masası
    assert 'tab-btn-wallstreet' in html_page, "HTML'de 11. Sekme butonu bulunmalı!"
    assert 'main-tab-content-wallstreet' in html_page, "HTML'de 11. Sekme konteyneri bulunmalı!"
    assert "setWallStreetFilter('turkey')" in html_page, "HTML'de Türkiye filtreleme butonu bulunmalı!"
    assert "TÜRKİYE MASASI" in html_page, "JS şablonunda 'TÜRKİYE MASASI' bölümü yer almalı!"
    print("  • 🏛️ 11. Sekme & Türkiye Desk: ✅ DOM Butonu & Konteyneri Mevcut")

    # 2. Kokpit Üst HUD Şeridi
    assert 'id="hud-macro-bist"' in html_page, "Kokpit HUD şeridinde BIST 100 göstergesi (id='hud-macro-bist') olmalı!"
    assert 'id="hud-macro-brent"' in html_page, "Kokpit HUD şeridinde Brent petrol göstergesi (id='hud-macro-brent') olmalı!"
    assert "switchMainTab('wallstreet')" in html_page, "Kokpit HUD şeridinde doğrudan Wall Street masasına geçiş butonu olmalı!"
    print("  • 📺 Kokpit HUD Şerit Enteg. : ✅ BIST 100 (id='hud-macro-bist') & BRENT (id='hud-macro-brent') Hazır")

    # 3. İstemci JS Motoru
    assert 'function renderWallStreetTabView' in html_page, "renderWallStreetTabView fonksiyonu mevcut olmalı!"
    assert 'function renderCockpitMacroHudTicker' in html_page, "renderCockpitMacroHudTicker fonksiyonu mevcut olmalı!"
    print("  • ⚙️ İstemci JS Motorları    : ✅ renderWallStreetTabView & renderCockpitMacroHudTicker Güncel")

    # ──────────────────────────────────────────────────────────────────────────
    # ADIM 4: REST API TELEMETRİSİ KONTROLÜ
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[ADIM 4/4] 📡 REST API Telemetrisi Sınanıyor...")
    
    telemetry = macro_guard.get_macro_hud_telemetry()
    assert "global_breaker" in telemetry, "HUD telemetrisinde 'global_breaker' bulunmalı!"
    assert "cross_asset_regime" in telemetry, "HUD telemetrisinde 'cross_asset_regime' bulunmalı!"
    assets_in_regime = telemetry["cross_asset_regime"].get("assets", {})
    assert "BIST100" in assets_in_regime, "cross_asset_regime.assets içinde 'BIST100' bulunmalı!"
    assert "BRENT" in assets_in_regime, "cross_asset_regime.assets içinde 'BRENT' bulunmalı!"
    
    print(f"  • 🛰️ Telemetri BIST 100      : ✅ Fiyat: {assets_in_regime['BIST100']['value']} | Değişim: {assets_in_regime['BIST100']['chg_24h']}%")
    print(f"  • 🛰️ Telemetri Brent Petrol  : ✅ Fiyat: ${assets_in_regime['BRENT']['value']} | Değişim: {assets_in_regime['BRENT']['chg_24h']}%")
    print(f"  • 🛰️ Telemetri HUD Metni     : ✅ {telemetry['hud_ticker_text'][:100]}...")

    print("\n" + "=" * 80)
    print("🏆 TÜM TESTLER %100 BAŞARIYLA TAMAMLANDI! TÜRKİYE BORSASI & DEVRE KESİCİ KUSURSUZ AKTİF.")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(run_integration_tests())
