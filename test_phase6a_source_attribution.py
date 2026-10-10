"""
═══════════════════════════════════════════════════════════════════════════════
FAZ 6A TESTİ: DARWINIAN SOURCE ATTRIBUTION & ELO REPUTATION PRUNING
═══════════════════════════════════════════════════════════════════════════════
Bu test; Valkyrie Macro Oracle'ın haber kaynaklarını geriye dönük piyasa
fiyat tepkisi (t+30s, t+5m) ve kasa PnL'ine göre dinamik puanlamasını,
yalan haber/sahte fitil üreten kaynakları otonom karantinaya almasını (Auto-Muting)
ve karantinadaki kaynakların Byzantine Quorum tarafından anında veto edilmesini
%100 matematiksel ve adli olarak doğrular.
═══════════════════════════════════════════════════════════════════════════════
"""

import sys
import os
import json
import time

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# Proje ana dizinini dahil et
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from macro_source_evolution import source_evolution_engine, SourceEvolutionEngine
from macro_quorum import news_quorum

def run_phase6a_tests():
    print("\n" + "=" * 80)
    print("🧬 [FAZ 6A TESTİ BAŞLIYOR] SOURCE ATTRIBUTION & ELO REPUTATION PRUNING")
    print("=" * 80)

    # 1. TEST: Başlangıç Sicil Kütüğü ve Tohum Kaynak Doğrulaması
    print("\n[ADIM 1] Başlangıç Sicil Kütüğü ve Kaynak Profilleri...")
    tree_prof = source_evolution_engine.get_source_profile("TREENEWS")
    sec_prof = source_evolution_engine.get_source_profile("SEC_EDGAR")
    
    assert tree_prof["elo_rating"] >= 90.0, f"TreeNews ELO düşük: {tree_prof['elo_rating']}"
    assert tree_prof["status"] == "HIGH_TRUST", f"TreeNews statü beklenmeyen: {tree_prof['status']}"
    assert sec_prof["elo_rating"] >= 95.0, f"SEC EDGAR ELO düşük: {sec_prof['elo_rating']}"
    
    weight_tree = source_evolution_engine.get_source_voting_weight("TREENEWS")
    print(f"  ✓ TreeNews ELO: {tree_prof['elo_rating']} | Statü: {tree_prof['status']} | Oy Ağırlığı: {weight_tree}x")
    print(f"  ✓ SEC EDGAR ELO: {sec_prof['elo_rating']} | Statü: {sec_prof['status']} | Oy Ağırlığı: {source_evolution_engine.get_source_voting_weight('SEC_EDGAR')}x")

    # 2. TEST: Doğru Haber Sonrası ELO Artışı (Post-Facto Attribution)
    print("\n[ADIM 2] Gerçek Kurumsal Haber ve Fiyat Teyidi (Concordant Flow)...")
    evt_id = source_evolution_engine.register_news_event(
        source="TREENEWS",
        title="BlackRock files updated S-1 for Solana Trust",
        initial_price=65000.0,
        initial_cvd=150000.0,
        sentiment_score=35.0,
        symbol="BTC/USDT"
    )
    old_elo = source_evolution_engine.get_source_profile("TREENEWS")["elo_rating"]
    
    # 30s sonra fiyat %0.15 arttı, 300s sonra %0.25 arttı, CVD pozitif, işlem PnL +$120.0
    audit_res = source_evolution_engine.evaluate_attribution(
        event_id=evt_id,
        price_t30=65097.5,   # +%0.15
        price_t300=65162.5,  # +%0.25
        cvd_t30=450000.0,
        taker_buy_ratio_t30=0.62,
        trade_pnl_usd=120.0,
        latency_ms=110.0
    )
    new_elo = audit_res["new_elo"]
    print(f"  ✓ Olay ID: {evt_id}")
    print(f"  ✓ Fiyat Değişimi: t+30s: %{audit_res['price_pct_30s']} | t+300s: %{audit_res['price_pct_300s']}")
    print(f"  ✓ ELO Değişimi: {old_elo} -> {new_elo} (ΔELO: {audit_res['delta_elo']:+})")
    assert audit_res["is_accurate"] is True, "Haber doğrulanmış olarak işaretlenmeliydi!"
    assert audit_res["is_fakeout"] is False, "Haber sahte fitil olmamalıydı!"
    assert new_elo >= old_elo, f"Yeni ELO ({new_elo}) eski ELO'dan ({old_elo}) küçük olamaz!"

    # 3. TEST: Bilinmeyen Aday Kaynak ve Sahte Fitil (Fakeout / Trap) Cezası
    print("\n[ADIM 3] Bilinmeyen Kaynak Keşfi ve Fitil Tuzağı (Fakeout) Cezası...")
    bad_source = "ANON_LEAK_PUMP"
    if bad_source in source_evolution_engine.sources:
        del source_evolution_engine.sources[bad_source]
    bad_prof = source_evolution_engine.get_source_profile(bad_source)
    print(f"  ✓ Yeni Aday Kaynak Eklendi: {bad_source} | Başlangıç ELO: {bad_prof['elo_rating']} | Statü: {bad_prof['status']}")
    assert bad_prof["elo_rating"] == 60.0, "Aday kaynak başlangıç puanı 60.0 olmalı!"

    # 1. Tuzak Olayı: Haber aşırı boğa, ilk 30s fitil attı (+%0.10), sonra feci çöktü (-%0.35)
    evt_bad_1 = source_evolution_engine.register_news_event(
        source=bad_source,
        title="RUMOR: Apple secretly buying 50,000 BTC",
        initial_price=65000.0,
        initial_cvd=50000.0,
        sentiment_score=45.0,
        symbol="BTC/USDT"
    )
    audit_bad_1 = source_evolution_engine.evaluate_attribution(
        event_id=evt_bad_1,
        price_t30=65065.0,   # +%0.10 fitil
        price_t300=64772.5,  # -%0.35 çöküş
        cvd_t30=-300000.0,   # Tahtada gizli satış
        taker_buy_ratio_t30=0.38,
        trade_pnl_usd=-150.0,
        latency_ms=850.0
    )
    print(f"  ✓ 1. Tuzak Sonrası: ELO {audit_bad_1['old_elo']} -> {audit_bad_1['new_elo']} (ΔELO: {audit_bad_1['delta_elo']:+})")
    assert audit_bad_1["is_fakeout"] is True, "Sahte fitil tespit edilmeliydi!"
    assert audit_bad_1["delta_elo"] < -8.0, "Sahte fitil için ağır ceza puanı kesilmeliydi!"

    # 2. Tuzak Olayı: İkinci kez yalan haber üretimi
    evt_bad_2 = source_evolution_engine.register_news_event(
        source=bad_source,
        title="RUMOR: Gensler resigns immediately after secret meeting",
        initial_price=65000.0,
        initial_cvd=10000.0,
        sentiment_score=50.0,
        symbol="BTC/USDT"
    )
    audit_bad_2 = source_evolution_engine.evaluate_attribution(
        event_id=evt_bad_2,
        price_t30=65070.0,
        price_t300=64700.0,
        cvd_t30=-500000.0,
        taker_buy_ratio_t30=0.32,
        trade_pnl_usd=-180.0,
        latency_ms=1200.0
    )
    print(f"  ✓ 2. Tuzak Sonrası: ELO {audit_bad_2['old_elo']} -> {audit_bad_2['new_elo']} (ΔELO: {audit_bad_2['delta_elo']:+})")

    # 4. TEST: Otonom Karantinaya Alma (Auto-Pruning / Quarantined)
    print("\n[ADIM 4] Otonom Karantina ve Susturma (Auto-Quarantine) Denetimi...")
    is_quarantined, q_reason = source_evolution_engine.is_source_quarantined(bad_source)
    bad_prof_updated = source_evolution_engine.get_source_profile(bad_source)
    print(f"  ✓ Kaynak: {bad_source} | Güncel ELO: {bad_prof_updated['elo_rating']} | Statü: {bad_prof_updated['status']}")
    print(f"  ✓ Karantina Durumu: {is_quarantined} | Gerekçe: {q_reason}")
    print(f"  ✓ Oy Ağırlığı: {source_evolution_engine.get_source_voting_weight(bad_source)}x")
    
    assert is_quarantined is True, "ELO < 45.0 olan kaynak karantinaya alınmalıydı!"
    assert bad_prof_updated["status"] == "QUARANTINED", "Statü QUARANTINED olmalıydı!"
    assert source_evolution_engine.get_source_voting_weight(bad_source) == 0.0, "Karantinadaki kaynağın oyu 0.0 olmalı!"

    # 5. TEST: Byzantine Quorum Entegrasyonu ve Karantinadaki Kaynağı Veto Etme
    print("\n[ADIM 5] Byzantine Quorum Entegrasyonu: Karantinadaki Kaynak Haberi...")
    quarantined_news = {
        "title": "URGENT: Major Exchange Insolvency Rumor Confirmed",
        "source": bad_source,
        "sentiment_score": -60.0
    }
    verdict = news_quorum.evaluate_news_authenticity(quarantined_news)
    print(f"  ✓ Byzantine Kararı: {verdict['verdict']}")
    print(f"  ✓ Komut: {verdict['action_command']}")
    print(f"  ✓ Gerekçe: {verdict['reason']}")
    print(f"  ✓ İşlem İzni: {verdict['is_approved_for_entry']}")

    assert verdict["verdict"] == "REJECTED_QUARANTINED_SOURCE", f"Beklenen REJECTED_QUARANTINED_SOURCE, gelen: {verdict['verdict']}"
    assert verdict["is_approved_for_entry"] is False, "Karantinadaki kaynaktan asla yeni işlem açılamaz!"
    assert verdict["action_command"] == "IGNORE_NOISE", "Komut IGNORE_NOISE olmalı!"

    # 6. TEST: Liderlik Tablosu (Leaderboard) Sıralaması
    print("\n[ADIM 6] Kaynak İtibar Liderlik Tablosu (Leaderboard)...")
    leaderboard = source_evolution_engine.get_sources_leaderboard()
    print(f"{'SIRA':<5} {'KAYNAK':<20} {'ELO':<8} {'STATÜ':<15} {'AĞIRLIK':<10} {'DOĞRU':<8} {'TUZAK':<8}")
    print("-" * 75)
    for idx, s in enumerate(leaderboard, 1):
        print(f"{idx:<5} {s.get('source_key', s.get('title')):<20} {s.get('elo_rating'):<8} {s.get('status'):<15} {s.get('quorum_weight'):<10} {s.get('accurate_count'):<8} {s.get('fakeout_count'):<8}")

    print("\n" + "=" * 80)
    print("✅ [FAZ 6A TESTİ BAŞARIYLA GEÇTİ] TÜM ELO VE OTONOM KARANTİNA TESTLERİ %100 BAŞARILI!")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    run_phase6a_tests()
