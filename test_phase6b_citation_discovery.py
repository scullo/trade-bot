"""
═══════════════════════════════════════════════════════════════════════════════
FAZ 6B TESTİ: ALINTI GRAFİĞİ (CITATION GRAPH) & GÖLGE HAVUZ (SHADOW SANDBOX)
═══════════════════════════════════════════════════════════════════════════════
Bu test; Valkyrie Macro Oracle'ın doğrulanmış flaş haber bültenlerinden (@handle,
domain, analist) alıntıları NLP ile otonom keşfetmesini, 3 atıf alan adayları
Gölge Gözlem Havuzu'na (Shadow Sandbox) almasını ve %80+ doğruluk sağlayan
adayları otonom olarak Asil İstihbarat Kaynaklarına terfi ettirmesini doğrular.
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from macro_source_evolution import source_evolution_engine
from macro_news_sentinel import macro_news

def run_phase6b_tests():
    print("\n" + "=" * 80)
    print("🕸️ [FAZ 6B TESTİ BAŞLIYOR] CITATION GRAPH CRAWLER & SHADOW SANDBOX")
    print("=" * 80)

    # Test öncesi temiz başlangıç
    for k in ["@ELEANORTERRETT", "@ERICBALCHUNAS"]:
        source_evolution_engine.discovered_citations.pop(k, None)
        source_evolution_engine.shadow_sandbox.pop(k, None)
        source_evolution_engine.sources.pop(k, None)

    # 1. TEST: Metinlerden Alıntı Cımbızlama (NLP Citation Extraction)
    print("\n[ADIM 1] Doğrulanmış Haber Akışından Alıntı Cımbızlama...")
    sample_news_1 = "BREAKING: SEC Commissioner Hester Peirce hints at S-1 progress, per @EleanorTerrett via reuters.com"
    enrolled_1 = source_evolution_engine.crawl_and_extract_citations(sample_news_1, wire_source="TREENEWS")
    
    citations = source_evolution_engine.get_discovered_citations_leaderboard()
    print(f"  ✓ 1. Haber Tarandı: {len(citations)} farklı potansiyel referans hafızaya alındı.")
    
    # @ELEANORTERRETT kaydı oluştu mu?
    ent_el = source_evolution_engine.discovered_citations.get("@ELEANORTERRETT")
    assert ent_el is not None, "@ELEANORTERRETT keşfedilmedi!"
    print(f"  ✓ Keşfedilen Kişi: {ent_el['display_name']} | Atıf Sayısı: {ent_el['citation_count']} | Referans Bültenler: {ent_el['citing_wires']}")
    assert ent_el["citation_count"] == 1, "İlk haberde atıf sayısı 1 olmalı!"

    # 2. TEST: İkinci ve Üçüncü Atıflar ile Eşik Değerini Aşma (Auto-Enrollment Threshold)
    print("\n[ADIM 2] 2. ve 3. Atıf ile Gölge Havuz Eşiği (Threshold >= 3 veya 2 farklı ajans)...")
    sample_news_2 = "ETF analyst confirms new filing details citing @EleanorTerrett on Fox Business"
    source_evolution_engine.crawl_and_extract_citations(sample_news_2, wire_source="WALTER_BLOOMBERG")
    
    # 2 farklı ajans (TREENEWS ve WALTER_BLOOMBERG) tarafından referans verildi -> Auto-Enrollment tetiklenmeli!
    sandbox_candidates = source_evolution_engine.get_shadow_sandbox_list()
    print(f"  ✓ Gölge Havuzdaki Aday Sayısı: {len(sandbox_candidates)}")
    
    target_sandbox = None
    for cand in sandbox_candidates:
        if cand["entity_key"] == "@ELEANORTERRETT":
            target_sandbox = cand
            break

    assert target_sandbox is not None, "@ELEANORTERRETT Gölge Gözlem Havuzu'na (Shadow Sandbox) alınmalıydı!"
    print(f"  ✓ [OTONOM ADAY KAYIT]: {target_sandbox['display_name']} | Statü: {target_sandbox['status']}")
    print(f"  ✓ Referans Veren Ajanslar: {target_sandbox['citing_wires']}")
    assert target_sandbox["status"] == "SHADOW_SANDBOX", "Statü SHADOW_SANDBOX olmalı!"
    assert target_sandbox["is_promoted"] is False, "Aday hemen terfi ettirilmemeli!"

    # 3. TEST: Aday Kaynak Asil Listede Değil (İşlem Açamaz)
    print("\n[ADIM 3] Gölge Adayın Canlı İşlem Masasına Doğrudan Karışmadığının Teyidi...")
    # Kaynak profili sorgulandığında henüz asil kaynak olmamalı
    assert "@ELEANORTERRETT" not in source_evolution_engine.sources, "Aday kaynak hemen asil sources'a girmemeli!"

    # 4. TEST: Gölge Performans Takibi (Shadow Performance Attribution)
    print("\n[ADIM 4] Gölge Gözlem Havuzunda Haber Doğruluk Takibi (14 Günlük Simülasyon)...")
    # 1. Olay: Doğru haber
    res1 = source_evolution_engine.record_shadow_event("@ELEANORTERRETT", "SEC crypto approval tweet", is_accurate=True)
    print(f"  ✓ 1. Gölge Olay: Doğruluk: %{res1['shadow_accuracy_pct']} | Terfi Etti mi: {res1['promoted']}")
    assert res1["promoted"] is False, "Tek olayla terfi edemez!"

    # 2. Olay: Doğru haber
    res2 = source_evolution_engine.record_shadow_event("@ELEANORTERRETT", "CFTC guidance update", is_accurate=True)
    print(f"  ✓ 2. Gölge Olay: Doğruluk: %{res2['shadow_accuracy_pct']} | Terfi Etti mi: {res2['promoted']}")
    assert res2["promoted"] is False, "2 olayla terfi edemez (Eşik: >= 3 olay)!"

    # 3. Olay: Doğru haber -> %100 Doğruluk ve 3 Olay Tamamlandı -> OTONOM TERFİ (Darwinian Ascension)!
    res3 = source_evolution_engine.record_shadow_event("@ELEANORTERRETT", "Senate banking committee schedule", is_accurate=True)
    print(f"  ✓ 3. Gölge Olay: Doğruluk: %{res3['shadow_accuracy_pct']} | Terfi Etti mi: {res3['promoted']}")
    assert res3["promoted"] is True, "3 olay ve %100 doğruluk ile OTONOM TERFİ gerçekleşmeliydi!"
    assert res3["status"] == "PROMOTED_TO_ACTIVE", "Statü PROMOTED_TO_ACTIVE olmalı!"

    # 5. TEST: Asil Kaynak Listesine Geçiş ve Oy Ağırlığı Teyidi
    print("\n[ADIM 5] Asil Kaynak Tescili ve Byzantine Quorum Oy Yetkisi...")
    promoted_prof = source_evolution_engine.get_source_profile("@ELEANORTERRETT")
    print(f"  ✓ Yeni Asil Kaynak Profili: {promoted_prof['title']}")
    print(f"  ✓ ELO Güven Puanı: {promoted_prof['elo_rating']}")
    print(f"  ✓ Statü: {promoted_prof['status']}")
    print(f"  ✓ Oy Ağırlığı: {source_evolution_engine.get_source_voting_weight('@ELEANORTERRETT')}x")
    
    assert promoted_prof["elo_rating"] >= 70.0, "Terfi eden kaynağın başlangıç ELO'su >= 70 olmalı!"
    assert promoted_prof["status"] == "ACTIVE", "Statü ACTIVE olmalı!"
    assert source_evolution_engine.get_source_voting_weight("@ELEANORTERRETT") >= 0.8, "Oy ağırlığı geçerli olmalı!"

    # 6. TEST: Canlı Haber Akışı Sentinel Entegrasyonu
    print("\n[ADIM 6] Canlı MacroNewsSentinel Entegrasyonu...")
    # macro_news _analyze_headline çağrıldığında citation crawler otomatik tetiklenmeli
    parsed_item = macro_news._analyze_headline(
        title="SEC filing confirms new advisor @EricBalchunas reports",
        source="TreeNews:wire",
        raw_ts=time.time()
    )
    ent_eric = source_evolution_engine.discovered_citations.get("@ERICBALCHUNAS")
    assert ent_eric is not None, "@ERICBALCHUNAS haber analizinden otomatik keşfedilmeliydi!"
    print(f"  ✓ Canlı Sentinel'den Keşif: {ent_eric['display_name']} | Atıf: {ent_eric['citation_count']}")

    print("\n" + "=" * 80)
    print("✅ [FAZ 6B TESTİ BAŞARIYLA GEÇTİ] ALINTI GRAFİĞİ VE GÖLGE HAVUZ %100 KUSURSUZ ÇALIŞIYOR!")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    run_phase6b_tests()
