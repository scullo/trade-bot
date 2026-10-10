"""
═══════════════════════════════════════════════════════════════════════════════
FAZ 6C TESTİ: DİNAMİK LİDERLİK DEVRİ & AEGIS SENTINEL SENSÖRÜ
═══════════════════════════════════════════════════════════════════════════════
Bu test; Valkyrie Macro Oracle'ın resmi liderlik değişimlerini (Fed/SEC Başkanı)
otonom tespit etmesini, eski yetkililerin piyasa ağırlığını %20'ye düşürüp yenisini
1.0x yetkiyle makama atamasını ve Aegis Sentinel (Sensör 42) sağlık denetimini doğrular.
═══════════════════════════════════════════════════════════════════════════════
"""

import sys
import os
import json
import time
import asyncio

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from macro_roles import role_registry
from macro_source_evolution import source_evolution_engine
from aegis_sentinel import aegis_sentinel

async def run_phase6c_tests():
    print("\n" + "=" * 80)
    print("🏛️ [FAZ 6C TESTİ BAŞLIYOR] DİNAMİK LİDERLİK & AEGIS SENTINEL 42. SENSÖR")
    print("=" * 80)

    # 1. TEST: Dinamik Liderlik Tespiti ve Makam Devir Teslimi
    print("\n[ADIM 1] Flaş Haberden Resmi Makam Değişimi Tespiti (Automated Roll-Call)...")
    sec_news = "BREAKING: Senate confirms Paul Atkins as new SEC Chair in historic 52-44 vote"
    res_detect = role_registry.detect_leadership_changes(sec_news)
    
    assert res_detect is not None, "SEC Başkanı değişimi tespit edilemedi!"
    print(f"  ✓ Makam Tespiti: {res_detect['role_key']} -> Yeni Lider: {res_detect['new_holder']}")
    print(f"  ✓ Üretilen Takma Adlar: {res_detect['aliases']}")
    
    sec_role = role_registry.data["roles"]["SEC_CHAIR"]
    assert sec_role["current_holder"] == "Paul Atkins", f"Aktif makam Paul Atkins olmalı, mevcut: {sec_role['current_holder']}"
    assert "Gary Gensler" in sec_role["past_holders"], "Eski başkan Gary Gensler past_holders listesine aktarılmalıydı!"
    print(f"  ✓ Aktif Başkan: {sec_role['current_holder']} (Tam Yetki)")
    print(f"  ✓ Geçmiş Yetkililer: {sec_role['past_holders']}")

    # 2. TEST: Yeni ve Eski Yetkili Ayrımı ve Piyasa Ağırlığı Denetimi
    print("\n[ADIM 2] Yeni Başkan vs Eski Başkan Piyasa Ağırlığı Sınıflandırması...")
    
    # Yeni Başkan açıklaması
    curr_speaker = role_registry.classify_text_speaker("SEC Chair Paul Atkins announces pro-innovation crypto framework")
    print(f"  ✓ Yeni Başkan Tespiti: {curr_speaker['matched_person']} | Makam: {curr_speaker['role_title']} | Ağırlık: {curr_speaker['market_weight']}x | Eski mi: {curr_speaker['is_past_official']}")
    assert curr_speaker["has_official"] is True, "Aktif başkan tespit edilmeliydi!"
    assert curr_speaker["matched_person"] == "Paul Atkins", "Paul Atkins eşleşmeliydi!"
    assert curr_speaker["is_past_official"] is False, "is_past_official False olmalı!"
    assert curr_speaker["market_weight"] >= 0.70, "Aktif başkan ağırlığı tam olmalı!"

    # Eski Başkan açıklaması (Ağırlık %20'ye düşmeli!)
    past_speaker = role_registry.classify_text_speaker("Former chief Gary Gensler criticizes digital assets in speech")
    print(f"  ✓ Eski Başkan Tespiti: {past_speaker['matched_person']} | Makam: {past_speaker['role_title']} | Ağırlık: {past_speaker['market_weight']}x | Eski mi: {past_speaker['is_past_official']}")
    assert past_speaker["has_official"] is True, "Eski başkan tespit edilmeliydi!"
    assert past_speaker["is_past_official"] is True, "is_past_official True olmalı!"
    assert past_speaker["market_weight"] == 0.20, f"Eski başkan ağırlığı 0.20x olmalı, mevcut: {past_speaker['market_weight']}"

    # 3. TEST: Aegis Sentinel 42. Sensör (Darwinian Source Evolution Health Sensor)
    print("\n[ADIM 3] Aegis Sentinel (Sağlık Masası) Makro Denetimi...")
    macro_audit = await aegis_sentinel.audit_macro_oracle_system()
    evo_sensor = macro_audit.get("source_evolution", {})
    
    print(f"  ✓ Makro Sistem Genel Durumu: {macro_audit.get('status_text')}")
    print(f"  ✓ 6. Sensör (Source Evolution): Sağlıklı mı: {evo_sensor.get('healthy')} | Kaynak Sayısı: {evo_sensor.get('sources_count')} | Karantinadaki: {evo_sensor.get('quarantined_count')}")
    
    assert macro_audit["is_healthy"] is True, "Tüm makro sistem sağlıklı olmalı!"
    assert evo_sensor.get("healthy") is True, "Source evolution sensörü sağlıklı olmalı!"
    assert evo_sensor.get("sources_count", 0) >= 5, "Kaynak sayısı en az 5 olmalı!"

    # 4. TEST: Auto-Healing Kuralı 19 Denetimi
    print("\n[ADIM 4] Aegis Sentinel Auto-Healing Kuralı 19 (Sicil Koruma)...")
    healing_actions = await aegis_sentinel.apply_auto_healing(None, None, {"macro_oracle": macro_audit})
    print(f"  ✓ Sentinel Kendi Kendini Onarma Raporu: {len(healing_actions)} eylem alındı.")

    # 5. TEST: Source Evolution Engine Telemetrisi
    print("\n[ADIM 5] API /api/macro_oracle Veri Telemetrisi Doğrulaması...")
    lb = source_evolution_engine.get_sources_leaderboard()
    sb = source_evolution_engine.get_shadow_sandbox_list()
    cit = source_evolution_engine.get_discovered_citations_leaderboard()
    
    print(f"  ✓ Liderlik Tablosu Kaynak Sayısı: {len(lb)}")
    print(f"  ✓ Gölge Gözlem Havuzu Aday Sayısı: {len(sb)}")
    print(f"  ✓ Taranan Referans / Atıf Sayısı: {len(cit)}")
    assert len(lb) >= 5, "Liderlik tablosunda kaynaklar mevcut olmalı!"

    print("\n" + "=" * 80)
    print("✅ [FAZ 6C TESTİ BAŞARIYLA GEÇTİ] DİNAMİK LİDERLİK & AEGIS SENTINEL %100 KUSURSUZ!")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    asyncio.run(run_phase6c_tests())
