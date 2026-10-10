"""
🧪 FAZ 4 ADLİ DOĞRULAMA VE STRATEJİ ENTEGRASYON TESTİ
(TEST PHASE 4: STRATEGY & TRADE SETUP MACRO INTEGRATION)
Bu test; ekonomik takvim (macro_calendar), çapraz piyasa (macro_cross_asset),
haber istihbaratı (macro_news_sentinel) ve Bizans mutabakatının (macro_quorum)
işlem motoruna (strategy.py / macro_strategy_guard.py) entegrasyonunu kanıtlar:
1. Pre-Event (<15dk): Kârdaki pozisyonun stopunu True Net BE'ye çekmesi.
2. Pre-Event Dondurma (<5dk): Yeni işlem açılışını engellemesi.
3. Flash-Shock Kalkanı (0-60s): Akut veri anında yeni işlemleri dondurması.
4. Top 20 Likidite Filtresi: Makro şokta düşük likiditeli altcoinleri eleyip majörlere izin vermesi.
5. Setup Muting & Breakout Booster:
   - Ayı şokunda S3 Reversal Long'un susturulması (Muted).
   - Boğa şokunda R3 Reversal Short'un susturulması (Muted).
   - Boğa şokunda R4 Breakout Long'a 1.25x marjin ve +%20 TP2 genişletmesi verilmesi.
"""

import sys
import os
import time

# UTF-8 Konsol Desteği
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from macro_strategy_guard import macro_guard
from macro_calendar import calendar_manager

def run_phase4_verification():
    print("=" * 80)
    print("🦅 FAZ 4 KANITLAMA RAPORU: STRATEJİ & TRADE SETUP MAKRO ENTEGRASYONU")
    print("=" * 80)

    # ──────────────────────────────────────────────────────────────────────────
    # SENARYO 1: PRE-EVENT (<15 DAKİKA KALA) TRUE NET BREAKEVEN KİLİDİ
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[SENARYO 1/5] 🛡️ Pre-Event Kârdaki Pozisyonu True Net BE'ye Kilitleme...")
    now = time.time()
    
    # 10 dakika sonra gerçekleşecek yapay olmayan gerçek formatlı bir CPI olayı
    mock_cpi_event = {
        "title": "US Core CPI (YoY)",
        "country": "USD",
        "impact": "CRITICAL",
        "category": "INFLATION_CPI",
        "timestamp": now + 600,  # 10 dakika sonra (T-10m)
        "iso_date": "2026-10-10T15:30:00",
        "forecast": "3.1%",
        "previous": "3.2%",
        "actual": ""
    }
    # Takvimin ilk sırasına ekle
    calendar_manager.events.insert(0, mock_cpi_event)

    # Açık kârlı pozisyon: BTC/USDT Long (Giriş: $64,000, Şu An: $65,500, Stop: $63,200)
    mock_open_positions = {
        "BTC/USDT": {
            "symbol": "BTC/USDT",
            "side": "LONG",
            "entry_price": 64000.0,
            "current_price": 65500.0,
            "hard_stop": 63200.0,
            "soft_stop": 63200.0,
            "quantity": 0.1,
            "accumulated_funding_fee": 0.50,
            "is_half_closed": False
        }
    }

    secured = macro_guard.enforce_pre_event_defenses(mock_open_positions)
    pos_btc = mock_open_positions["BTC/USDT"]
    new_stop = pos_btc["hard_stop"]

    print(f"  • Yaklaşan Olay : {mock_cpi_event['title']} (T-10 Dakika)")
    print(f"  • BTC Pozisyonu : Giriş: ${pos_btc['entry_price']:,.2f} | Eski Stop: $63,200.00")
    print(f"  • Yeni Stop     : ${new_stop:,.2f} (True Net Breakeven Kilidi)")
    print(f"  • Kilit Durumu  : {pos_btc.get('macro_be_locked')} | Gerekçe: {pos_btc.get('macro_lock_reason')}")

    assert pos_btc.get("macro_be_locked") is True, "Pre-Event kâr koruma BE kilidi aktifleşmeli!"
    assert new_stop > 64000.0, "Stop seviyesi giriş + komisyon üzerine çıkmalı!"
    print("  ✅ Kanıtlandı: Haber öncesi açık kâr garantilendi, stop başabaşa kilitlendi.")

    # ──────────────────────────────────────────────────────────────────────────
    # SENARYO 2: PRE-EVENT DONDURMA (<5 DAKİKA KALA YENİ EMİR KİLİDİ)
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[SENARYO 2/5] 🕒 Pre-Event Dondurma (<5 Dakika Kala Yeni Emir Engeli)...")
    mock_cpi_event["timestamp"] = now + 180  # 3 dakika kala (T-3m)

    res_entry_5m = macro_guard.evaluate_macro_entry_permission(
        symbol="ETH/USDT",
        side="LONG",
        setup_id="SETUP_1_R4_BREAKOUT",
        reason="R4 Breakout Long",
        spread_pct=0.015
    )
    print(f"  • Kalan Süre   : 3 Dakika")
    print(f"  • Giriş İzni   : {'❌ ENGELLENDİ' if not res_entry_5m['allowed'] else 'ONAY'}")
    print(f"  • Hata Kodu    : {res_entry_5m.get('error')}")
    print(f"  • Adli Gerekçe : {res_entry_5m.get('reason')}")

    assert not res_entry_5m["allowed"], "T-5dk kala yeni emir açılması yasaktır!"
    assert res_entry_5m["error"] == "BLOCK_PRE_EVENT_FREEZE", "Hata kodu BLOCK_PRE_EVENT_FREEZE olmalıdır!"
    print("  ✅ Kanıtlandı: Veri öncesi son 5 dakikada yeni işlem açılışı kesin olarak kilitlendi.")

    # ──────────────────────────────────────────────────────────────────────────
    # SENARYO 3: FLASH-SHOCK KALKANI (VERİ ANI İLK 60 SANİYE)
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[SENARYO 3/5] ⚡ Flash-Shock Kalkanı (Veri Anı -60s / +60s)...")
    mock_cpi_event["timestamp"] = now + 10  # 10 saniye sonra (tam veri anı)

    res_flash = macro_guard.evaluate_macro_entry_permission(
        symbol="SOL/USDT",
        side="LONG",
        setup_id="SETUP_1_R4_BREAKOUT",
        reason="R4 Breakout Long",
        spread_pct=0.020
    )
    print(f"  • Durum        : Tam Veri Anı (Flash-Shock)")
    print(f"  • Giriş İzni   : {'❌ ENGELLENDİ' if not res_flash['allowed'] else 'ONAY'}")
    print(f"  • Hata Kodu    : {res_flash.get('error')}")
    print(f"  • Adli Gerekçe : {res_flash.get('reason')}")

    assert not res_flash["allowed"], "Flash-Shock anında yeni emir açılamaz!"
    assert res_flash["error"] == "BLOCK_FLASH_SHOCK_ACTIVE", "Hata kodu BLOCK_FLASH_SHOCK_ACTIVE olmalı!"
    print("  ✅ Kanıtlandı: Veri anındaki 60 saniyelik akut fitil tuzağında emirler kilitlendi.")

    # Takvim test olayını temizle
    calendar_manager.events.pop(0)

    # ──────────────────────────────────────────────────────────────────────────
    # SENARYO 4: MAKRO ŞOK ALTINDA TOP 20 LİKİDİTE FİLTRESİ
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[SENARYO 4/6] 🌊 Makro Şok Altında Top 20 Likidite Filtresi...")
    macro_guard.quorum.audit_history = []  # Önceki test kayıtlarını sıfırla
    macro_guard.set_override_regime("BEAR_MACRO_SHOCK")

    # Düşük likiditeli meme coin (BOME/USDT)
    res_bome = macro_guard.evaluate_macro_entry_permission(
        symbol="BOME/USDT",
        side="SHORT",
        setup_id="SETUP_2_S4_BREAKDOWN",
        reason="S4 Breakdown Short"
    )
    print(f"  • BOME/USDT (Meme / Düşük Hacim) : {'❌ ENGELLENDİ' if not res_bome['allowed'] else 'ONAY'}")
    print(f"  • Hata Kodu                     : {res_bome.get('error')}")
    print(f"  • Adli Gerekçe                  : {res_bome.get('reason')}")
    assert not res_bome["allowed"], "Makro şokta düşük likiditeli altcoin engellenmeli!"
    assert res_bome["error"] == "BLOCK_LOW_LIQUIDITY_MACRO"

    # Top 20 Majör Parite (SOL/USDT)
    res_sol = macro_guard.evaluate_macro_entry_permission(
        symbol="SOL/USDT",
        side="SHORT",
        setup_id="SETUP_2_S4_BREAKDOWN",
        reason="S4 Breakdown Short"
    )
    print(f"  • SOL/USDT (Top 20 Majör Likidite) : {'✅ ONAYLANDI' if res_sol['allowed'] else 'RED'}")
    assert res_sol["allowed"], "Top 20 majör parite makro şokta izinli olmalı!"
    print("  ✅ Kanıtlandı: Likidite boşalma riskine karşı meme coinler kilitlendi, majörler çalıştı.")

    # ──────────────────────────────────────────────────────────────────────────
    # SENARYO 5: SETUP MUTING (SUSTURMA) & BREAKOUT RUNNER BOOSTER
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[SENARYO 5/5] 🎯 Setup Muting & Breakout Runner Booster Testi...")

    # 5.1: Ayı Makro Şokunda Camarilla S3 Reversal Long SUSTURULUR (MUTED)
    res_mute_s3 = macro_guard.evaluate_macro_entry_permission(
        symbol="BTC/USDT",
        side="LONG",
        setup_id="SETUP_3_S3_BOUNCE",
        reason="Camarilla S3 Destek Sekmesi Reversal Long"
    )
    print(f"  • [AYI ŞOKU] S3 Reversal Long : {'❌ SUSTURULDU (MUTED)' if not res_mute_s3['allowed'] else 'ONAY'}")
    print(f"  • Adli Gerekçe                : {res_mute_s3.get('reason')}")
    assert not res_mute_s3["allowed"], "Ayı şokunda karşı-trend S3 Long susturulmalı!"
    assert res_mute_s3["error"] == "MUTED_BEAR_MACRO_REVERSAL_LONG"

    # 5.2: Boğa Makro Şokuna Geç
    macro_guard.set_override_regime("BULL_MACRO_SHOCK")

    # Boğa Makro Şokunda Camarilla R3 Reversal Short SUSTURULUR (MUTED)
    res_mute_r3 = macro_guard.evaluate_macro_entry_permission(
        symbol="BTC/USDT",
        side="SHORT",
        setup_id="SETUP_4_R3_REJECTION",
        reason="Camarilla R3 Direnç Reddi Reversal Short"
    )
    print(f"  • [BOĞA ŞOKU] R3 Reversal Short: {'❌ SUSTURULDU (MUTED)' if not res_mute_r3['allowed'] else 'ONAY'}")
    print(f"  • Adli Gerekçe                 : {res_mute_r3.get('reason')}")
    assert not res_mute_r3["allowed"], "Boğa şokunda karşı-trend R3 Short susturulmalı!"
    assert res_mute_r3["error"] == "MUTED_BULL_MACRO_REVERSAL_SHORT"

    # 5.3: Boğa Makro Şokunda R4 Breakout Long için 1.25x Marjin ve +%20 TP2 Teşviki
    base_margin = 100.0
    base_tp1 = 66000.0
    base_tp2 = 68000.0
    entry_p = 65000.0

    boost = macro_guard.apply_macro_setup_boost(
        symbol="BTC/USDT",
        side="LONG",
        setup_id="SETUP_1_R4_BREAKOUT",
        reason="R4 Breakout Long",
        base_margin=base_margin,
        base_tp1=base_tp1,
        base_tp2=base_tp2,
        entry_price=entry_p
    )
    print(f"  • [BOĞA ŞOKU] R4 Breakout Long Güçlendirmesi:")
    print(f"    - Standart Marjin : ${base_margin:.1f} -> Teşvikli Marjin: ${boost['margin']:.1f} (1.25x)")
    print(f"    - Standart TP2    : ${base_tp2:.1f} -> Genişletilmiş TP2: ${boost['tp2']:.1f} (+%20 R)")
    print(f"    - Hawkes Runner   : {boost.get('runner_mode')}")
    print(f"    - Gerekçe         : {boost.get('reason')}")

    assert boost["boosted"] is True, "Makro teşvik devreye girmeli!"
    assert boost["margin"] == 125.0, "Marjin tam 1.25x ($125) olmalı!"
    assert boost["tp2"] == 68600.0, "TP2 mesafesi ($3000 * 1.20 = $3600 -> $68600) olmalı!"
    print("  ✅ Kanıtlandı: R4 Breakout setup'ına makro rüzgarla 1.25x marjin ve Hawkes runner verildi.")

    # ──────────────────────────────────────────────────────────────────────────
    # SENARYO 6: BYZANTINE QUORUM SAHTE POMPALAMA (SPOOFING TRAP) KİLİDİ
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[SENARYO 6/6] 🪤 Byzantine Quorum Sahte Pompalama (Spoofing) Kalkanı...")
    macro_guard.quorum.audit_history.append({
        "timestamp": time.time(),
        "title": "AnonTweet: Elon Musk Dogecoin ile Mars'a roket yolluyor",
        "verdict": "SPOOFING_TRAP_NO_FLOW",
        "action_command": "BLOCK_TRADES_30S"
    })
    res_spoof = macro_guard.evaluate_macro_entry_permission(
        symbol="BTC/USDT",
        side="LONG",
        setup_id="SETUP_1_R4_BREAKOUT",
        reason="R4 Breakout Long"
    )
    print(f"  • BTC/USDT (Sahte Pompalama Sonrası): {'❌ ENGELLENDİ' if not res_spoof['allowed'] else 'ONAY'}")
    print(f"  • Hata Kodu                         : {res_spoof.get('error')}")
    print(f"  • Adli Gerekçe                      : {res_spoof.get('reason')}")
    assert not res_spoof["allowed"], "Tahta emilimi olmayan sahte haberde işlemler kilitlenmeli!"
    assert res_spoof["error"] == "BLOCK_SPOOFING_TRAP"
    print("  ✅ Kanıtlandı: Tahta ve CVD akışı olmayan sahte pompalamada 30 saniyelik işlem kilidi devrede.")

    # Override rejimini sıfırla
    macro_guard.set_override_regime(None)

    # ──────────────────────────────────────────────────────────────────────────
    # HUD TELEMETRİSİ DOĞRULAMASI
    # ──────────────────────────────────────────────────────────────────────────
    hud = macro_guard.get_macro_hud_telemetry()
    print("\n[HUD TELEMETRİSİ] 📺 Main Dashboard Ticker Çıktısı:")
    print(f"  • HUD Metni: \"{hud.get('hud_ticker_text')}\"")

    print("\n" + "=" * 80)
    print("🏆 FAZ 4 SONUCU: STRATEJİ & TRADE SETUP MAKRO ENTEGRASYONU %100 KANITLANDI!")
    print("=" * 80)
    return True

if __name__ == "__main__":
    run_phase4_verification()
