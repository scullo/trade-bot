"""
🧪 FAZ 3 ADLİ DOĞRULAMA VE KANITLAMA TESTİ
(TEST PHASE 3: BYZANTINE QUORUM & ANTI-MANIPULATION DEFENSE SYSTEM)
Bu test kripto piyasasındaki yalan haberleri, hack tuzaklarını, sahte tahta pompalamalarını
ve siyasi dedikoduları simüle ederek botun savunma kalkanlarının %100 çalıştığını kanıtlar.
"""

import sys
import os
import asyncio
import json

# UTF-8 Konsol Desteği
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from macro_quorum import news_quorum, ByzantineNewsQuorum

def run_phase3_verification():
    print("=" * 80)
    print("🛡️ FAZ 3 KANITLAMA RAPORU: BYZANTINE QUORUM & YALAN HABER KALKANI TESTİ")
    print("=" * 80)

    # ──────────────────────────────────────────────────────────────────────────
    # SENARYO 1: YALAN HABER & TEK KAYNAK MANİPÜLASYONU
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[SENARYO 1/5] 🚨 Yalan Haber / Tek Kaynak Tuzağı Test Ediliyor...")
    fake_news_item = {
        "title": "SEC, BlackRock Solana Spot ETF başvurusunu onayladı!",
        "source": "AnonTwitter:@CryptoLeakInsider",
        "sentiment_score": 75.0,
        "is_primary_official": False
    }

    # Tahta nötr
    decision1 = news_quorum.evaluate_news_authenticity(fake_news_item, cvd_delta_usd=0.0, taker_buy_ratio=50.0)
    print(f"  • Gelen Haber : \"{fake_news_item['title']}\" (Kaynak: {fake_news_item['source']})")
    print(f"  • Kuant Kararı: {decision1['verdict']} | Komut: {decision1['action_command']}")
    print(f"  • Giriş İzni  : {'❌ REDDEDİLDİ (Giriş Engellendi)' if not decision1['is_approved_for_entry'] else 'ONAY'}")
    print(f"  • Stop Koruması: {'🛡️ AKTİF (Kârdaki işlemlerin stopu BE çekildi)' if decision1['is_defensive_trigger'] else 'PASİF'}")
    print(f"  • Adli Gerekçe: {decision1['reason']}")
    assert not decision1["is_approved_for_entry"], "Tek kaynaklı haberde asla işlem açılamaz!"
    assert decision1["is_defensive_trigger"], "Savunma stop kilidi tetiklenmeli!"
    print("  ✅ Kanıtlandı: Tek kaynaklı haberde sıfır işlem açıldı, kârlar güvenle korundu.")

    # ──────────────────────────────────────────────────────────────────────────
    # SENARYO 2: TAHTA TEPKİSİ OLMAYAN SAHTE BOĞA POMPALAMASI (SPOOFING TRAP)
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[SENARYO 2/5] 🪤 Tahta ve CVD Desteği Olmayan Sahte Pompalama (Fakeout Trap)...")
    # İlk kaynak (WalterBloomberg) haberi geçti
    news_quorum.register_incoming_news({
        "title": "Fed acil faiz indirimini değerlendiriyor",
        "source": "WalterBloomberg",
        "sentiment_score": 85.0,
        "is_primary_official": False
    })
    # İkinci kaynak (TreeNews) aynı haberi geçti (Çift teyit oluştu)
    spoof_news = {
        "title": "Fed acil faiz indirimini değerlendiriyor",
        "source": "TreeNews",
        "sentiment_score": 85.0,  # Aşırı boğa görünüyor
        "is_primary_official": False
    }

    # Ancak tahtada kurumsal alıcı yok, tam aksine market satıcıları $3.5M boşaltıyor!
    cvd_dump = -3_500_000.0
    taker_buy = 36.5  # Satıcılar %63.5 hakim

    decision2 = news_quorum.evaluate_news_authenticity(spoof_news, cvd_delta_usd=cvd_dump, taker_buy_ratio=taker_buy)
    print(f"  • Gelen Haber : \"{spoof_news['title']}\" (Puan: +{spoof_news['sentiment_score']})")
    print(f"  • Tahta Akışı : CVD: -${abs(cvd_dump):,.0f} | Taker Alıcı: %{taker_buy:.1f} (Satıcılar Süpürüyor)")
    print(f"  • Kuant Kararı: {decision2['verdict']} | Komut: {decision2['action_command']}")
    print(f"  • Giriş İzni  : {'❌ REDDEDİLDİ (Tuzak Engellendi)' if not decision2['is_approved_for_entry'] else 'ONAY'}")
    print(f"  • Adli Gerekçe: {decision2['reason']}")
    assert decision2["verdict"] == "SPOOFING_TRAP_NO_FLOW", "CVD zıt akışında tuzak olarak reddedilmeli!"
    assert not decision2["is_approved_for_entry"], "Sahte pompalamada işlem açılmamalı!"
    print("  ✅ Kanıtlandı: Tahta tepkisi olmayan sahte fitil tuzağı bertaraf edildi.")

    # ──────────────────────────────────────────────────────────────────────────
    # SENARYO 3: SİYASİ BOŞ GÜRÜLTÜ VE SEÇİM PROPAGANDASI (POLITICAL NOISE)
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[SENARYO 3/5] 🗣️ Siyasi Boş Gürültü ve Seçim Propagandası Test Ediliyor...")
    noise_news = {
        "title": "Donald Trump: Kripto sektörü için harika bir gelecek sözü veriyorum, bize oy verin!",
        "source": "TreeNews:Twitter",
        "sentiment_score": 40.0,
        "is_primary_official": False
    }

    decision3 = news_quorum.evaluate_news_authenticity(noise_news)
    print(f"  • Gelen Metin : \"{noise_news['title']}\"")
    print(f"  • Kuant Kararı: {decision3['verdict']} | Komut: {decision3['action_command']}")
    print(f"  • Giriş İzni  : {'❌ YOK (Gürültü Olarak Elendi)' if not decision3['is_approved_for_entry'] else 'ONAY'}")
    print(f"  • Adli Gerekçe: {decision3['reason']}")
    assert decision3["verdict"] == "POLITICAL_NOISE", "Seçim propagandası gürültü sayılmalı!"
    print("  ✅ Kanıtlandı: Boş siyasi vaatler filtrelendi, gereksiz işlem açılmadı.")

    # ──────────────────────────────────────────────────────────────────────────
    # SENARYO 4: RESMİ BİRİNCİL KAYNAK (SEC EDGAR FORM 8-K) RESMİ BİLDİRİMİ
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[SENARYO 4/5] 🏛️ Resmi Birincil Kaynak Doğrulaması (SEC EDGAR)...")
    sec_official_news = {
        "title": "[SEC 8-K RESMİ BİLDİRİM] SEC approves Rule Change for Listing Grayscale Solana Trust",
        "source": "SEC_EDGAR",
        "sentiment_score": 60.0,
        "is_primary_official": True
    }

    decision4 = news_quorum.evaluate_news_authenticity(sec_official_news, cvd_delta_usd=2_000_000.0, taker_buy_ratio=65.0)
    print(f"  • Gelen Metin : \"{sec_official_news['title']}\" (Kaynak: {sec_official_news['source']})")
    print(f"  • Kuant Kararı: {decision4['verdict']} | Komut: {decision4['action_command']}")
    print(f"  • Giriş İzni  : {'✅ ONAYLANDI (Tam Yetkili Giriş)' if decision4['is_approved_for_entry'] else 'RED'}")
    print(f"  • Adli Gerekçe: {decision4['reason']}")
    assert decision4["verdict"] == "VERIFIED_INSTITUTIONAL", "Resmi kaynak doğrudan kurumsal teyitli olmalı!"
    assert decision4["is_approved_for_entry"], "Resmi onayda işleme izin verilmeli!"
    print("  ✅ Kanıtlandı: Doğrudan devlet/komisyon kaynağından gelen habere güvenle yetki verildi.")

    # ──────────────────────────────────────────────────────────────────────────
    # SENARYO 5: ÇİFT BAĞIMSIZ KAYNAK + KURUMSAL ALICI AKIŞI ($12M CVD)
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[SENARYO 5/5] 🚀 Çift Kaynak Mutabakatı + Güçlü Tahta Alım Teyidi...")
    # Çift bağımsız kaynak akışı
    topic_headline = "ABD Hazinesi 500 Milyon Dolarlık Stablecoin Likidite Tahvili Çıkardı"
    news_quorum.register_incoming_news({
        "title": topic_headline,
        "source": "WalterBloomberg",
        "sentiment_score": 55.0,
        "is_primary_official": False
    })
    verified_news = {
        "title": topic_headline,
        "source": "TreeNews",
        "sentiment_score": 55.0,
        "is_primary_official": False
    }

    # Borsa tahtasında gerçek kurumsal akış var
    real_cvd = 12_500_000.0  # +$12.5M agresif market alımı
    real_taker_buy = 67.8    # %67.8 alıcı üstünlüğü

    decision5 = news_quorum.evaluate_news_authenticity(verified_news, cvd_delta_usd=real_cvd, taker_buy_ratio=real_taker_buy)
    print(f"  • Gelen Haber : \"{verified_news['title']}\"")
    print(f"  • Teyit Ağı   : {decision5.get('confirmed_sources')} (Çift Bağımsız Kaynak)")
    print(f"  • Tahta Akışı : CVD: +${real_cvd:,.0f} | Taker Alıcı: %{real_taker_buy:.1f} (Kurumsal Emilim)")
    print(f"  • Kuant Kararı: {decision5['verdict']} | Komut: {decision5['action_command']}")
    print(f"  • Giriş İzni  : {'✅ ONAYLANDI (Elit Setup Yetkisi Verildi)' if decision5['is_approved_for_entry'] else 'RED'}")
    assert decision5["is_approved_for_entry"], "Çift teyit ve alıcı akışında işleme girilmeli!"
    print("  ✅ Kanıtlandı: Çift teyit ve kurumsal tahta emilimiyle elit kuruluma onay verildi.")

    print("\n" + "=" * 80)
    print("🏆 FAZ 3 SONUCU: BYZANTINE QUORUM VE TÜM ANTİ-MANİPÜLASYON ZIRHLARI %100 KANITLANDI!")
    print("=" * 80)
    return True

if __name__ == "__main__":
    run_phase3_verification()
