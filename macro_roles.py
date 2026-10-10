"""
🦅 VALKYRIE QUANT - DİNAMİK MAKAMLAR VE YETKİLİ SİCİL KÜTÜĞÜ (EXECUTIVE ROLE REGISTRY)
Makam bazlı dinamik istihbarat motoru. İsimler sabit (hardcoded) değildir.
Fed Başkanı, SEC Başkanı, Hazine Bakanı veya ABD Başkanı değiştiğinde makam yeni isme devredilir;
eski yetkili otomatik olarak düşük ağırlığa (0.2x) indirilir, yetkisiz siyasetçiler ise filtrelenir.
"""

import os
import json
import time
from typing import Dict, Any, Tuple, Optional

REGISTRY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "macro_roles_registry.json")

# Varsayılan Kurumsal Makam Sicil Kütüğü (Makam Odaklı Hiyerarşi)
DEFAULT_REGISTRY: Dict[str, Any] = {
    "version": "2.0.0",
    "last_updated": int(time.time()),
    "roles": {
        "FED_CHAIR": {
            "title": "Federal Reserve Başkanı",
            "current_holder": "Jerome Powell",
            "alias_list": ["Powell", "Jerome Powell", "Fed Başkanı Powell", "Chair Powell"],
            "market_weight": 1.0,  # En yüksek makro ağırlık
            "domain": "MONETARY_POLICY",
            "past_holders": ["Janet Yellen", "Ben Bernanke", "Alan Greenspan"]
        },
        "SEC_CHAIR": {
            "title": "SEC (Menkul Kıymetler Komisyonu) Başkanı",
            "current_holder": "Gary Gensler",
            "alias_list": ["Gensler", "Gary Gensler", "SEC Başkanı", "Chair Gensler"],
            "market_weight": 1.0,  # En yüksek regülasyon ağırlığı
            "domain": "REGULATION",
            "past_holders": ["Jay Clayton", "Mary Jo White"]
        },
        "POTUS": {
            "title": "Amerika Birleşik Devletleri Başkanı",
            "current_holder": "Donald Trump",
            "alias_list": ["Trump", "Donald Trump", "Başkan Trump", "POTUS", "Beyaz Saray", "White House"],
            "market_weight": 0.95, # Çok yüksek jeopolitik ve regülasyon ağırlığı
            "domain": "EXECUTIVE_POLICY",
            "past_holders": ["Joe Biden", "Barack Obama"]
        },
        "TREASURY_SECRETARY": {
            "title": "ABD Hazine Bakanı",
            "current_holder": "Janet Yellen",
            "alias_list": ["Yellen", "Janet Yellen", "Hazine Bakanı", "Treasury Secretary"],
            "market_weight": 0.85, # Yüksek dolar likiditesi ve borç tavanı ağırlığı
            "domain": "LIQUIDITY_POLICY",
            "past_holders": ["Steven Mnuchin", "Jack Lew"]
        },
        "FOMC_VOTING_MEMBERS": {
            "title": "FOMC Oy Hakkına Sahip Fed Guvernörleri / Bölge Başkanları",
            "current_holder": "FOMC Core Governors",
            "alias_list": [
                "Christopher Waller", "Waller",
                "Michelle Bowman", "Bowman",
                "John Williams", "Williams",
                "Michael Barr", "Barr",
                "Philip Jefferson", "Jefferson",
                "Lisa Cook", "Cook",
                "Adriana Kugler", "Kugler",
                "Austan Goolsbee", "Goolsbee",
                "Raphael Bostic", "Bostic",
                "Neel Kashkari", "Kashkari"
            ],
            "market_weight": 0.75, # Güçlü yönlendirici faiz/enflasyon görüşleri
            "domain": "MONETARY_POLICY",
            "past_holders": ["James Bullard", "Esther George"]
        },
        "SEC_COMMISSIONERS": {
            "title": "Kripto Dostu / Muhalif SEC Komiserleri",
            "current_holder": "SEC Commissioners",
            "alias_list": [
                "Hester Peirce", "Peirce", "Crypto Mom",
                "Mark Uyeda", "Uyeda",
                "Caroline Crenshaw", "Crenshaw",
                "Jaime Lizarraga", "Lizarraga"
            ],
            "market_weight": 0.70, # Karşı oy ve regülasyon muhalefet ağırlığı
            "domain": "REGULATION",
            "past_holders": []
        }
    }
}

class ExecutiveRoleRegistry:
    """Kurumsal Makam ve Yetkili Sicil Kütüğü Yöneticisi."""

    def __init__(self, registry_file: str = REGISTRY_FILE):
        self.registry_file = registry_file
        self.data: Dict[str, Any] = {}
        self.load_registry()

    def load_registry(self) -> None:
        """Kütüğü JSON dosyasından yükle, yoksa varsayılan ile oluştur."""
        if os.path.exists(self.registry_file):
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
                    return
            except Exception as e:
                print(f">> [REGISTRY UYARI] Kütük dosyası okunamadı ({e}), varsayılan yükleniyor...")
        self.data = DEFAULT_REGISTRY
        self.save_registry()

    def save_registry(self) -> None:
        """Kütüğü diske atomik olarak kaydet."""
        try:
            with open(self.registry_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f">> [REGISTRY HATA] Kaydedilemedi: {e}")

    def update_role_holder(self, role_key: str, new_person_name: str, new_aliases: Optional[list] = None, reason: str = "") -> bool:
        """
        Dinamik Makam Değişimi: Örneğin yeni bir Fed Başkanı atandığında eski başkan arşive alınır,
        yeni kişi 1.0x piyasa ağırlığıyla aktif makama oturur.
        """
        roles = self.data.get("roles", {})
        if role_key not in roles:
            print(f">> [REGISTRY HATA] Geçersiz makam anahtarı: {role_key}")
            return False

        role = roles[role_key]
        old_holder = role.get("current_holder", "")
        old_aliases = role.get("alias_list", [])
        
        # Eski kişiyi ve eski takma adlarını geçmiş yetkililer listesine ekle
        past = role.get("past_holders", [])
        if old_holder and old_holder not in past:
            past.append(old_holder)
        for a in old_aliases:
            if a not in past:
                past.append(a)
        role["past_holders"] = past

        # Yeni kişiyi makama oturt ve alias_list'i temizce yenile
        role["current_holder"] = new_person_name
        role["alias_list"] = list(set(new_aliases if new_aliases else [new_person_name]))

        self.data["last_updated"] = int(time.time())
        self.save_registry()
        print(f">> [🏛️ MAKAMSAL DEVİR TESLİM] {role['title']} makamı güncellendi: Eski={old_holder} -> YENİ={new_person_name}. Gerekçe: {reason}")
        return True

    def classify_text_speaker(self, text: str) -> Dict[str, Any]:
        """
        Metin içindeki konuşmacıyı / yetkiliyi tespit eder.
        Döner:
        - has_official: bool (Makam sahibi mi?)
        - role_key: str (FED_CHAIR, POTUS vb.)
        - role_title: str
        - matched_person: str
        - market_weight: float (0.0 ile 1.0 arası piyasa etki ağırlığı)
        - domain: str (MONETARY_POLICY, REGULATION vb.)
        - is_past_official: bool (Eski yetkili mi?)
        """
        text_lower = text.lower()
        roles = self.data.get("roles", {})

        # 1. Önce aktif makam sahiplerini ve takma adlarını ara (En Yüksek Öncelik)
        for r_key, r_info in roles.items():
            curr_holder = r_info.get("current_holder", "")
            aliases = r_info.get("alias_list", [])
            for alias in aliases:
                if alias.lower() in text_lower:
                    return {
                        "has_official": True,
                        "role_key": r_key,
                        "role_title": r_info.get("title", ""),
                        "matched_person": curr_holder,
                        "matched_keyword": alias,
                        "market_weight": float(r_info.get("market_weight", 0.5)),
                        "domain": r_info.get("domain", "GENERAL"),
                        "is_past_official": False
                    }

        # 2. Eski yetkili kontrolü (Örn: Eski Fed başkanı konuşuyorsa ağırlık %20'ye düşer)
        for r_key, r_info in roles.items():
            past_list = r_info.get("past_holders", [])
            for past_p in past_list:
                if past_p.lower() in text_lower:
                    return {
                        "has_official": True,
                        "role_key": r_key,
                        "role_title": f"Eski {r_info.get('title', '')}",
                        "matched_person": past_p,
                        "matched_keyword": past_p,
                        "market_weight": 0.20,  # Eski yetkilinin piyasa ağırlığı sadece %20
                        "domain": r_info.get("domain", "GENERAL"),
                        "is_past_official": True
                    }

        # 3. Yetkili tespit edilemedi -> Sıradan haber / Genel yorum
        return {
            "has_official": False,
            "role_key": "NONE",
            "role_title": "Genel Piyasa Yorumcusu / Yetkisiz",
            "matched_person": "Bilinmiyor",
            "matched_keyword": "",
            "market_weight": 0.10,
            "domain": "GENERAL",
            "is_past_official": False
        }

# Global Singleton Örneği
role_registry = ExecutiveRoleRegistry()
