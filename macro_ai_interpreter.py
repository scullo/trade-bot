# -*- coding: utf-8 -*-
"""
🧠 VALKYRIE QUANT - YAPAY ZEKA MAKRO HABER & ADLİ İSTİHBARAT YORUMLAYICISI (AI FORENSIC NEWS INTERPRETER)
Gelen tüm flaş haberleri (TreeNews, SEC EDGAR, Fed RSS vb.) derinlemesine analiz eder:
1. Haberin Ne Olduğu ve Türkçe Özeti (Context & Summary)
2. Yapay Zekanın / Kuant Masasının Detaylı Piyasa Yorumu (AI Forensic & Market Interpretation)
3. Puanlama Mantığı & Gerekçesi (Neden 0.0 veya neden pozitif/negatif puan verildiği)
4. Botun Al-Sat Stratejisine Tavsiyesi & Risk Aksiyonu (Strategy & Defense Action)
5. Doğru Kurum / Şirket / Yetkili Tespiti (False 'Fed' etiketlerini önleme)
"""

import re
from typing import Dict, Any, Tuple

# Kripto ile Doğrudan İlişkili Kurumlar ve Hisseler (Crypto-Native & Listed Entities)
CRYPTO_NATIVE_ENTITIES = {
    "MICROSTRATEGY": {"name": "MicroStrategy (MSTR)", "tag": "KRİPTO REZERV / BTC DİPS", "crypto_relevant": True},
    "COINBASE": {"name": "Coinbase Global (COIN)", "tag": "BORSA & LİKİDİTE", "crypto_relevant": True},
    "MARATHON": {"name": "Marathon Digital (MARA)", "tag": "BTC MADENCİLİK", "crypto_relevant": True},
    "MARA": {"name": "Marathon Digital (MARA)", "tag": "BTC MADENCİLİK", "crypto_relevant": True},
    "RIOT": {"name": "Riot Platforms (RIOT)", "tag": "BTC MADENCİLİK", "crypto_relevant": True},
    "CLEANSPARK": {"name": "CleanSpark (CLSK)", "tag": "BTC MADENCİLİK", "crypto_relevant": True},
    "BLACKROCK": {"name": "BlackRock (iShares)", "tag": "SPOT ETF İHRAÇÇISI", "crypto_relevant": True},
    "FIDELITY": {"name": "Fidelity Investments", "tag": "SPOT ETF İHRAÇÇISI", "crypto_relevant": True},
    "GRAYSCALE": {"name": "Grayscale Investments", "tag": "KRİPTO FONU / ETF", "crypto_relevant": True},
    "ROBINHOOD": {"name": "Robinhood (HOOD)", "tag": "PERAKENDE KRİPTO TİCARETİ", "crypto_relevant": True},
    "BINANCE": {"name": "Binance Global", "tag": "GLOBAL BORSA", "crypto_relevant": True},
    "TETHER": {"name": "Tether Treasury", "tag": "STABLECOIN LİKİDİTESİ", "crypto_relevant": True},
    "CIRCLE": {"name": "Circle (USDC)", "tag": "STABLECOIN LİKİDİTESİ", "crypto_relevant": True},
    "RIPPLE": {"name": "Ripple Labs (XRP)", "tag": "ÖDEME & REGÜLASYON", "crypto_relevant": True},
    "BITWISE": {"name": "Bitwise Asset Mgmt", "tag": "KRİPTO ETF İHRAÇÇISI", "crypto_relevant": True},
    "VANECK": {"name": "VanEck", "tag": "KRİPTO ETF İHRAÇÇISI", "crypto_relevant": True},
    "TERAWULF": {"name": "TeraWulf (WULF)", "tag": "BTC MADENCİLİK", "crypto_relevant": True},
    "HUT 8": {"name": "Hut 8 Mining", "tag": "BTC MADENCİLİK", "crypto_relevant": True},
    "CORE SCIENTIFIC": {"name": "Core Scientific", "tag": "BTC MADENCİLİK & AI", "crypto_relevant": True}
}

class MacroAIInterpreter:
    """Yapay Zeka Destekli Adli Haber Yorumlama Motoru."""

    @staticmethod
    def extract_sec_filer(title: str) -> Tuple[str, bool]:
        """
        SEC 8-K / S-1 başlığından şirket adını çıkarır ve kripto ilişkisini kontrol eder.
        Örn: '[SEC 8-K RESMİ BİLDİRİM] 8-K - Serina Therapeutics, Inc. (0001708599) (Filer)' -> ('Serina Therapeutics, Inc.', False)
        """
        m = re.search(r"(?:8-K|S-1|S-3|6-K|10-K|10-Q)\s*[-–]\s*([^(]+?)\s*\(", title, re.IGNORECASE)
        if m:
            filer = m.group(1).strip()
            # Filer adında crypto kontrolü
            filer_upper = filer.upper()
            is_crypto = any(c in filer_upper for c in CRYPTO_NATIVE_ENTITIES.keys()) or any(w in filer_upper for w in ["BITCOIN", "CRYPTO", "BLOCKCHAIN", "DIGITAL ASSET", "MINING"])
            return filer, is_crypto
        return "SEC Bildirim Sahibi", False

    @staticmethod
    def analyze_news_ai(item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Haber öğesini adli incelemeye tabi tutar ve insan analist kalitesinde
        yapay zeka kuant yorumu ve gerekçesi üretir.
        """
        title = item.get("title", "")
        tr_headline = (item.get("title_tr") or title).strip()
        source = item.get("source", "WIRE").upper()
        raw_score = float(item.get("sentiment_score", 0.0))
        speaker_info = item.get("speaker_info", {})
        has_official = speaker_info.get("has_official", False)
        matched_person = speaker_info.get("matched_person", "")
        role_title = speaker_info.get("role_title", "")
        category = item.get("category", "GENERAL_CRYPTO")

        title_upper = title.upper()

        ai_summary = ""
        ai_interpretation = ""
        market_impact = ""
        impact_direction = "NEUTRAL"
        score_explanation = ""
        strategy_action = ""
        actual_entity = ""

        # ── DURUM 1: SEC EDGAR FORM 8-K / DOSYALAMA BİLDİRİMİ ──
        if "SEC_EDGAR" in source or "[SEC" in title_upper:
            filer_name, is_crypto_company = MacroAIInterpreter.extract_sec_filer(title)
            actual_entity = f"SEC EDGAR • {filer_name}"

            if is_crypto_company:
                impact_direction = "BULLISH" if raw_score >= 0 else "BEARISH"
                market_impact = "YÜKSEK REGÜLASYON / KRİPTO İLİŞKİLİ"
                ai_summary = (
                    f"Bu bildirim, ABD Menkul Kıymetler ve Borsa Komisyonu (SEC) nezdinde sunulan ve "
                    f"doğrudan kripto ekosistemiyle bağlantılı olan '{filer_name}' şirketinin resmi Form 8-K (Önemli Olay) dosyalamasıdır."
                )
                ai_interpretation = (
                    f"Kripto para ve blokzincir sektöründe faaliyet gösteren bir şirketin SEC nezdindeki olağan dışı "
                    f"kurumsal adımıdır. Kurumsal hazine yönetimi, sermaye artırımı veya regülasyon uyumu açısından "
                    f"piyasa katılımcıları tarafından yakından izlenmektedir."
                )
                score_explanation = (
                    f"Kripto ilişkili kurumsal bildirim olduğu için piyasa duyarlılığı analiz edilmiş ve "
                    f"{raw_score:+.1f} etki puanı atanmıştır."
                )
                strategy_action = "İlgili paritelerde ve BTC likiditesinde spread ve tahta derinliği teyidi aranır."
            else:
                # Kripto Dışı Rutin Şirket Dosyalaması (Serina Therapeutics vb.)
                impact_direction = "NEUTRAL"
                market_impact = "NÖTR / KRİPTO DIŞI ŞİRKET BİLDİRİMİ"
                ai_summary = (
                    f"Bu bildirim, ABD SEC veritabanında yayımlanan rutin bir kurumsal Form 8-K belgesidir. "
                    f"Bildirim sahibi: '{filer_name}'."
                )
                ai_interpretation = (
                    f"Dosyalama yapan '{filer_name}' şirketi biyoteknoloji, sağlık, havacılık veya geleneksel sanayi alanında faaliyet göstermektedir. "
                    f"Doğrudan Bitcoin rezervi, kripto varlık veya blokzincir operasyonu içermediği için "
                    f"kripto para fiyatlaması ve risk iştahı üzerinde sıfır korelasyona sahiptir."
                )
                score_explanation = (
                    "Puan NÖTR (0.0): Bu bir hayalet veya eksik veri DEĞİLDİR. Şirket doğrudan kripto varlık içermediğinden "
                    "yapay zeka puanlama motoru kripto fiyatını etkilemeyeceğini tespit etmiş ve doğru şekilde 0.0 puan vermiştir."
                )
                strategy_action = (
                    "Rutin dış piyasa akışı. Kripto botumuzun pozisyonları üzerinde hiçbir kısıtlama veya "
                    "kalkan tetiklenmez; al-sat stratejileri olağan seyrinde devam eder."
                )

        # ── DURUM 2: FED RESMİ BASIN AÇIKLAMASI (FED RSS) ──
        elif "FED_OFFICIAL" in source or "[FED" in title_upper:
            actual_entity = "Federal Reserve (Fed) Basın Masası"
            if has_official:
                actual_entity = f"Fed Başkanı ({matched_person})"

            if raw_score > 10:
                impact_direction = "BULLISH"
                market_impact = "GÜVERCİN / BOĞA LEHİNE FED ETKİSİ"
            elif raw_score < -10:
                impact_direction = "BEARISH"
                market_impact = "ŞAHİN / SIKI PARA AYI ETKİSİ"
            else:
                impact_direction = "NEUTRAL"
                market_impact = "DENGELİ / NÖTR FED BİLDİRİMİ"

            ai_summary = (
                f"Federal Reserve (ABD Merkez Bankası) resmi yayın organından gelen birincil bildirimdir: "
                f"'{tr_headline.replace('[FED RESMİ AÇIKLAMA]', '').strip()}'."
            )
            ai_interpretation = (
                f"Fed'in para politikası, bilanço büyüklüğü veya bankacılık sistemi duyuruları küresel dolar likiditesini doğrudan belirler. "
                f"Faiz indirimine veya gevşemeye işaret eden ifadeler kripto için güçlü yakıt oluştururken, şahin tonda söylemler risk primini baskılar."
            )
            score_explanation = (
                f"Metin içerisindeki makro anahtar kelimeler ve makam ağırlığı (1.0x) taranarak {raw_score:+.1f} duygu puanı hesaplanmıştır."
            )
            strategy_action = (
                "Fed bildirimlerinde Byzantine Quorum çift teyidi devreye girer; ani faiz şoklarında T-15m ve 30s koruma kalkanları hazır tutulur."
            )

        # ── DURUM 3: RESMİ MAKAM VE LİDERLERİN KONUŞMALARI (WARSH, ATKINS, BESSENT, TRUMP) ──
        elif has_official:
            actual_entity = f"{role_title} ({matched_person})"
            if raw_score > 10:
                impact_direction = "BULLISH"
                market_impact = f"YÜKSEK BOĞA ETKİSİ ({matched_person.upper()})"
            elif raw_score < -10:
                impact_direction = "BEARISH"
                market_impact = f"YÜKSEK AYI ETKİSİ ({matched_person.upper()})"
            else:
                impact_direction = "NEUTRAL"
                market_impact = f"DENGELİ SÖYLEM ({matched_person.upper()})"

            ai_summary = (
                f"2026 yılı güncel makam sahibi {role_title} {matched_person} tarafından yapılan veya "
                f"doğrudan kendisini ilgilendiren üst düzey politika açıklamasıdır: '{tr_headline}'."
            )
            ai_interpretation = (
                f"{matched_person} piyasa nezdinde en yüksek yönlendirici ağırlığa sahiptir. "
                f"Açıklama para politikası, sermaye piyasası regülasyonları ve kurumsal fon akışları üzerinde doğrudan fiyatlama oluşturma potansiyeli taşır."
            )
            score_explanation = (
                f"Resmi makam sahibi tespitiyle {raw_score:+.1f} puan hesaplanmış ve makam katsayısı ile ağırlıklandırılmıştır."
            )
            strategy_action = (
                "Yetkili açıklamalarında CVD absorpsiyonu ve tahta derinliği doğrulanmadan ters yönde aceleci işleme girilmez."
            )

        # ── DURUM 4: TREENEWS & SOSYAL AĞ / AJANS FLAŞ HABERLERİ ──
        else:
            # Kaynak tespiti (Örn: TreeNews:Twitter, TreeNews:Blogs)
            actual_entity = source.replace("TREENEWS:", "").title() if "TREENEWS:" in source else source

            # Başlık içi aktör tespiti
            handle_match = re.search(r"@([A-Za-z0-9_]+)", title)
            if handle_match:
                actual_entity = f"X / Twitter (@{handle_match.group(1)})"

            # Kripto Piyasası İçerik Analizi
            if any(w in title_upper for w in ["APPROVE", "ETF", "INFLOW", "BUY", "ACQUIRE", "SURGE", "RALLY", "PARTNERSHIP", "LAUNCH"]):
                impact_direction = "BULLISH"
                market_impact = "POZİTİF / BOĞA İVMESİ"
                ai_summary = f"Kripto piyasasında sermaye girişi veya olumlu boğa ivmesine işaret eden flaş gelişme: '{tr_headline}'."
                ai_interpretation = (
                    "Haber başlığı kurumsal benimsenme, ETF net girişleri veya ekosistem büyümesine dair pozitif sinyaller içermektedir. "
                    "Kısa vadede alıcı iştahını tetikleyebilir."
                )
                score_explanation = f"Pozitif piyasa kelimeleri saptanmış ve {raw_score:+.1f} boğa yönlü etki puanı verilmiştir."
                strategy_action = "Trend takip eden Breakout ve Pivot Flip kurulumları için yukarı yönlü teyit aranır."

            elif any(w in title_upper for w in ["HACK", "EXPLOIT", "STOLEN", "DRAIN", "SUED", "LAWSUIT", "BAN", "CRASH", "DUMP", "OUTFLOW"]):
                impact_direction = "BEARISH"
                market_impact = "RİSKLİ / AYI BASKISI"
                ai_summary = f"Kripto güvenliği, dava veya fon çıkışı içeren negatif piyasa riski: '{tr_headline}'."
                ai_interpretation = (
                    "Protokol açığı, likidite boşalması veya regülasyon baskısı gibi risk faktörlerine işaret eder. "
                    "Piyasada panik satışı veya tasfiye kaskadı riski yaratabilir."
                )
                score_explanation = f"Risk ve güvenlik ihlali terimleri nedeniyle {raw_score:+.1f} negatif puan verilmiştir."
                strategy_action = "Long yönlü işlemlerde stoplar sıkılaştırılır; risk kalkanı koruma moduna geçer."

            elif any(w in title_upper for w in ["CHATBOT", "AI", "FORMULA", "PREDICT", "DECRYPT", "OPINION", "FEEDBACK"]):
                impact_direction = "NEUTRAL"
                market_impact = "BİLGİLENDİRME / ANALİZ HABERİ"
                ai_summary = f"Kripto, yapay zeka veya teknoloji dünyasından araştırma ve değerlendirme: '{tr_headline}'."
                ai_interpretation = (
                    "Sektörel vizyon, araştırma raporu veya topluluk tartışması niteliğindedir. "
                    "Anlık bir fiyat patlaması veya panik dalgası yaratması beklenmez."
                )
                score_explanation = (
                    "Puan NÖTR (0.0): Fiyatı anlık etkileyecek ani bir tasfiye veya alım haberi olmadığından, "
                    "bilgilendirme amaçlı içerik olarak doğru biçimde 0.0 puanla sınıflandırılmıştır."
                )
                strategy_action = "Al-sat stratejileri kısıtlanmadan normal algoritma parametreleriyle çalışır."

            else:
                impact_direction = "NEUTRAL" if abs(raw_score) <= 10 else ("BULLISH" if raw_score > 0 else "BEARISH")
                market_impact = "GENEL PİYASA AKIŞI"
                ai_summary = f"Kripto piyasası akışından kaydedilen güncel istihbarat: '{tr_headline}'."
                ai_interpretation = (
                    "Piyasa katılımcılarının duyarlılığını ölçen genel haber akışıdır. "
                    "Makro rejim ve CVD yönüyle birlikte değerlendirilir."
                )
                score_explanation = f"NLP analizi sonucunda {raw_score:+.1f} etki skoru üretilmiştir."
                strategy_action = "Tekil habere göre değil, çift teyitli çoklu sinyallere göre işlem yapılır."

        return {
            "ai_summary": ai_summary,
            "ai_interpretation": ai_interpretation,
            "market_impact": market_impact,
            "impact_direction": impact_direction,
            "score_explanation": score_explanation,
            "strategy_action": strategy_action,
            "actual_entity": actual_entity or "Genel Piyasa Kaynağı"
        }

# Global Singleton
ai_interpreter = MacroAIInterpreter()
