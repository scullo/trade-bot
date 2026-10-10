"""
VALKYRIE GÖRSEL ADLİ KARA KUTU & MİKROSKOBİK MUM OTOPSİ MOTORU
Modül: forensic_blackbox_manager.py
Amaç: İşlem kapandığında tetikleme matrisine göre arka planda non-blocking olarak
1600x900 kompozit adli görsel ve JSON otopsi raporu üretir.
Tarihsel klasörleme, akıllı yaşam döngüsü (pruning) ve Hall of Fame yönetimini sağlar.
"""

import os
import io
import json
import time
import shutil
import asyncio
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from chart_engine_v2 import forensic_chart_engine_v2
from forensic_autopsy import forensic_autopsy_engine


class ForensicBlackboxManager:
    """
    Adli Kara Kutu Orkestratörü ve Depolama Yaşam Döngüsü Yöneticisi.
    """

    BASE_DIR = "forensic_blackbox"
    SNAPSHOTS_DIR = os.path.join(BASE_DIR, "snapshots")
    REPORTS_DIR = os.path.join(BASE_DIR, "reports")
    HALL_OF_FAME_DIR = os.path.join(BASE_DIR, "hall_of_fame")
    CATALOG_FILE = os.path.join(BASE_DIR, "catalog.json")

    MAX_SHADOW_SNAPSHOTS = 300
    HOT_RETENTION_DAYS = 7

    def __init__(self):
        self._ensure_directories()
        self._lock = threading.Lock()
        self._draw_lock = threading.Lock()
        self.catalog = self._load_catalog()
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ValkyrieForensic")

    def _ensure_directories(self):
        os.makedirs(self.SNAPSHOTS_DIR, exist_ok=True)
        os.makedirs(self.REPORTS_DIR, exist_ok=True)
        os.makedirs(self.HALL_OF_FAME_DIR, exist_ok=True)

    def _load_catalog(self) -> List[Dict[str, Any]]:
        if os.path.exists(self.CATALOG_FILE):
            try:
                with open(self.CATALOG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
            except Exception as e:
                print(f"[FORENSIC] Katalog okuma hatasi: {e}")
        return []

    def _save_catalog(self):
        try:
            temp_file = self.CATALOG_FILE + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self.catalog, f, ensure_ascii=False, indent=2)
            os.replace(temp_file, self.CATALOG_FILE)
        except Exception as e:
            print(f"[FORENSIC] Katalog kaydetme hatasi: {e}")

    # =========================================================================
    # TETİKLEME MATRİSİ: İŞLEM GÖRSELLEŞTİRİLMELİ Mİ?
    # =========================================================================
    def should_trigger_snapshot(self, trade_record: Dict[str, Any], is_shadow: bool = False) -> bool:
        """
        Görsel Adli Kara Kutu Tetikleme Kuralı:
        - Gerçek ve Paper Kasa İşlemleri: %100 Görselleme (Sermaye kanıtı ve adli arşiv)
        - Manuel İstekler (Canlı Radar Snapshot Al): %100 Görselleme
        - Gölge (Shadow) İşlemler: Otomatik PNG üretimi KAPALI (Sıfır kirlilik, sıfır disk maliyeti).
          Gölge işlemler arka planda Coin DNA ve optimizasyon motorunu saf sayısal JSON olarak besler.
        """
        # Manuel canlı inceleme talepleri her zaman görsel üretir
        is_manual = bool(
            trade_record.get("is_manual_scan")
            or trade_record.get("is_manual")
            or ("MANUAL" in str(trade_record.get("id", "")))
            or trade_record.get("close_reason") == "MANUEL_ANLIK_SNAPSHOT_KONTROLÜ"
        )
        if is_manual:
            return True

        # Gölge işlemler için otomatik görsel üretimi kesinlikle KAPALI
        if is_shadow:
            return False

        # Gerçek ve Paper kasa işlemleri %100 belgelenir
        return True

    # =========================================================================
    # GÖRSEL ÜRETİMİ VE ARŞİVLEME (SENKRON & ASENKRON)
    # =========================================================================
    def process_closed_trade_sync(
        self,
        trade_record: Dict[str, Any],
        df_5m: Optional[pd.DataFrame] = None,
        levels: Optional[Dict[str, Any]] = None,
        is_shadow: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        İşlemi inceler, otopsisini yapar, 1600x900 infografiği çizer ve diske kaydeder.
        """
        if not self.should_trigger_snapshot(trade_record, is_shadow=is_shadow):
            return None

        symbol = str(trade_record.get("symbol", "UNKNOWN")).replace("/USDT", "")
        side = str(trade_record.get("side", "LONG")).upper()
        roe = float(trade_record.get("roe_pct") or trade_record.get("virtual_pnl_pct") or 0.0)
        now_dt = datetime.now(timezone(timedelta(hours=3)))
        date_folder = now_dt.strftime("%Y-%m-%d")
        ts_str = now_dt.strftime("%Y%m%d_%H%M%S")

        target_dir = os.path.join(self.SNAPSHOTS_DIR, date_folder)
        os.makedirs(target_dir, exist_ok=True)

        # 1. Yerel kural tabanlı adli otopsi
        autopsy = forensic_autopsy_engine.perform_autopsy(trade_record, df_5m=df_5m, levels=levels)

        # 2. Dosya Adlandırma Standardı
        trade_category = "SHADOW" if is_shadow else "REAL"
        cr_upper = str(trade_record.get("close_reason") or "").upper()
        net_pnl_raw = float(trade_record.get("net_pnl") or trade_record.get("virtual_pnl_usd") or 0.0)

        # 🏛️ MODEL 1: Birleşik Yaşam Döngüsü Uyumlu Sonuç Belirleme
        # Eğer genel işlem net kârla kapandıysa (+ROE > 0.35%), 2. bacak breakeven ile çıkmış olsa dahi işlem KAZANAN (WIN) mühürlenir.
        if net_pnl_raw > 0.0 and roe > 0.35:
            outcome_tag = "WIN"
        elif net_pnl_raw < -0.10 and roe < -0.35:
            outcome_tag = "LOSS"
        else:
            outcome_tag = "BE"

        roe_clean = f"PLUS{roe:.1f}" if roe >= 0 else f"MINUS{abs(roe):.1f}"
        diag_short = autopsy["diagnosis_code"].replace("_", "")[:12]

        file_prefix = f"{trade_category}_{outcome_tag}_{symbol}_{ts_str}_{roe_clean}PCT_{diag_short}"
        png_filename = f"{file_prefix}.png"
        json_filename = f"{file_prefix}.json"

        png_path = os.path.join(target_dir, png_filename)
        json_path = os.path.join(target_dir, json_filename)

        # 3. Grafik Çizimi (df_5m varsa)
        has_image = False
        if df_5m is not None and not df_5m.empty:
            try:
                with self._draw_lock:
                    buf = forensic_chart_engine_v2.generate_composite_snapshot(
                        trade_record=trade_record,
                        df_5m=df_5m,
                        levels=levels,
                        autopsy_data=autopsy
                    )
                    if buf:
                        with open(png_path, "wb") as f_img:
                            f_img.write(buf.getvalue())
                        has_image = True
            except Exception as e:
                print(f"[FORENSIC] Grafik cizim hatasi ({symbol}): {e}")

        # 4. JSON Metadata Kaydı
        snapshot_id = f"snap_{symbol}_{ts_str}_{abs(int(roe*10))}"
        catalog_entry = {
            "id": snapshot_id,
            "symbol": f"{symbol}/USDT",
            "side": side,
            "trade_category": trade_category,
            "outcome": outcome_tag,
            "entry_price": float(trade_record.get("entry_price") or 0.0),
            "exit_price": float(trade_record.get("exit_price") or 0.0),
            "net_pnl": float(trade_record.get("net_pnl") or trade_record.get("virtual_pnl_usd") or 0.0),
            "roe_pct": roe,
            "setup_id": str(trade_record.get("setup_id") or trade_record.get("reason") or "SETUP_QUANT"),
            "close_reason": str(trade_record.get("close_reason") or ""),
            "duration": str(trade_record.get("duration") or ""),
            "candle_count": int(trade_record.get("candle_count") or 1),
            "date": date_folder,
            "created_at": now_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "png_path": png_path if has_image else None,
            "json_path": json_path,
            "has_image": has_image,
            "is_starred": False,
            "is_reviewed": False,
            "autopsy": autopsy
        }

        try:
            with open(json_path, "w", encoding="utf-8") as f_json:
                json.dump(catalog_entry, f_json, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[FORENSIC] JSON kayit hatasi ({symbol}): {e}")

        # 5. Kataloğu güncelle ve buda (Pruning) - Thread Güvenli
        with self._lock:
            self.catalog.insert(0, catalog_entry)
            self._prune_storage()
            self._save_catalog()

        print(f">> [ADLI KARA KUTU] #{symbol} {side} ({roe:+.1f}% ROE) snapshot uretildi -> {png_filename if has_image else json_filename}")
        return catalog_entry

    def enqueue_closed_trade(
        self,
        trade_record: Dict[str, Any],
        df_5m: Optional[pd.DataFrame] = None,
        levels: Optional[Dict[str, Any]] = None,
        is_shadow: bool = False
    ):
        """
        Trading tick'ini kilitlememek için görsel üretimini arka plandaki ThreadPool'a atar.
        """
        try:
            if not self.should_trigger_snapshot(trade_record, is_shadow=is_shadow):
                return

            # Kopya oluşturarak thread güvenliği sağla
            df_copy = df_5m.copy() if df_5m is not None and not df_5m.empty else None
            rec_copy = dict(trade_record)
            lvl_copy = dict(levels) if levels else {}

            self.executor.submit(
                self.process_closed_trade_sync,
                rec_copy,
                df_copy,
                lvl_copy,
                is_shadow
            )
        except Exception as e:
            print(f"[FORENSIC] Asenkron kuyruk hatasi: {e}")

    # =========================================================================
    # AKILLI YAŞAM DÖNGÜSÜ & DİSK BUDAMA (SMART PRUNING)
    # =========================================================================
    def _prune_storage(self):
        """
        Diski koruma politikası:
        1. Gölge işlemler: En fazla 300 adet (FIFO ile eskiler silinir).
        2. İncelenmiş & Onaylanmış: PNG silinir, hafif JSON kalır.
        3. Hall of Fame (Yıldızlılar): Asla silinmez.
        """
        try:
            # Gölge işlem tavanı kontrolü
            shadow_entries = [e for e in self.catalog if e.get("trade_category") == "SHADOW" and not e.get("is_starred", False)]
            if len(shadow_entries) > self.MAX_SHADOW_SNAPSHOTS:
                excess_count = len(shadow_entries) - self.MAX_SHADOW_SNAPSHOTS
                # En eskiler listenin sonunda
                to_delete = shadow_entries[-excess_count:]
                for item in to_delete:
                    self._remove_snapshot_files(item)
                    if item in self.catalog:
                        self.catalog.remove(item)

            # Toplam katalog tavanı (maks 1000 kayıt)
            if len(self.catalog) > 1000:
                oldest_unstarred = [e for e in self.catalog if not e.get("is_starred", False)][800:]
                for item in oldest_unstarred:
                    self._remove_snapshot_files(item)
                    if item in self.catalog:
                        self.catalog.remove(item)

        except Exception as e:
            print(f"[FORENSIC] Disk budama hatasi: {e}")

    def _remove_snapshot_files(self, entry: Dict[str, Any]):
        try:
            png_p = entry.get("png_path")
            if png_p and os.path.exists(png_p):
                os.remove(png_p)
            json_p = entry.get("json_path")
            if json_p and os.path.exists(json_p):
                os.remove(json_p)
            hof_p = entry.get("hall_of_fame_path")
            if hof_p and os.path.exists(hof_p):
                os.remove(hof_p)
        except Exception:
            pass

    # =========================================================================
    # KULLANICI AKSİYONLARI (STAR, REVIEW, DELETE)
    # =========================================================================
    def toggle_star(self, snapshot_id: str) -> bool:
        """Grafiği Hall of Fame (Yıldızlılar) arşivine ekler veya çıkarır."""
        with self._lock:
            for item in self.catalog:
                if item.get("id") == snapshot_id:
                    new_state = not item.get("is_starred", False)
                    item["is_starred"] = new_state
                    png_path = item.get("png_path")

                    if new_state and png_path and os.path.exists(png_path):
                        # Hall of Fame klasörüne kopyala
                        dest_p = os.path.join(self.HALL_OF_FAME_DIR, os.path.basename(png_path))
                        shutil.copy2(png_path, dest_p)
                        item["hall_of_fame_path"] = dest_p
                    elif not new_state:
                        # Yıldız kaldırıldığında Hall of Fame kopyasını temizle
                        hof_p = item.get("hall_of_fame_path")
                        if hof_p and os.path.exists(hof_p):
                            try:
                                os.remove(hof_p)
                            except Exception:
                                pass
                        item["hall_of_fame_path"] = None

                    self._save_catalog()
                    return new_state
            return False

    def mark_reviewed(self, snapshot_id: str) -> bool:
        """Kullanıcı tarafından incelendi olarak işaretlenir; PNG silinip 1KB JSON bırakılır."""
        with self._lock:
            for item in self.catalog:
                if item.get("id") == snapshot_id:
                    item["is_reviewed"] = True
                    png_path = item.get("png_path")
                    if png_path and os.path.exists(png_path) and not item.get("is_starred", False):
                        try:
                            os.remove(png_path)
                            item["png_path"] = None
                            item["has_image"] = False
                        except Exception:
                            pass
                    self._save_catalog()
                    return True
            return False

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Görseli ve raporu diskten kalıcı olarak siler."""
        with self._lock:
            for item in list(self.catalog):
                if item.get("id") == snapshot_id:
                    self._remove_snapshot_files(item)
                    self.catalog.remove(item)
                    self._save_catalog()
                    return True
            return False

    # =========================================================================
    # WEB UI ARAMA VE FİLTRELEME
    # =========================================================================
    def get_snapshots(
        self,
        filter_category: str = "ALL",
        search: str = "",
        page: int = 1,
        page_size: int = 30
    ) -> Dict[str, Any]:
        """
        Web kokpiti için filtrelenmiş ve sayfalanmış adli kayıtları döner.
        Filtreler: ALL, LOSS, WIN, TRAP, STARRED, SHADOW, REAL
        """
        with self._lock:
            filtered = list(self.catalog)

        # Kategori filtresi
        is_be_entry = lambda x: (x.get("outcome") == "BE") or (abs(float(x.get("roe_pct", 0))) <= 0.35) or ("BREAKEVEN" in str(x.get("close_reason", "")).upper()) or ("BAŞA-BAŞ" in str(x.get("close_reason", "")).upper()) or ("BE" in str(x.get("close_reason", "")).upper())
        is_win_entry = lambda x: (x.get("outcome") == "WIN") or (float(x.get("roe_pct", 0)) > 0.35 and not is_be_entry(x))
        is_loss_entry = lambda x: (x.get("outcome") == "LOSS") or (float(x.get("roe_pct", 0)) < -0.35 and not is_be_entry(x))

        if filter_category == "LOSS":
            filtered = [x for x in filtered if is_loss_entry(x)]
        elif filter_category == "WIN":
            filtered = [x for x in filtered if is_win_entry(x)]
        elif filter_category == "BE":
            filtered = [x for x in filtered if is_be_entry(x)]
        elif filter_category == "TRAP":
            filtered = [x for x in filtered if "FAKEOUT" in str(x.get("autopsy", {}).get("diagnosis_code", "")) or "HUNT" in str(x.get("autopsy", {}).get("diagnosis_code", ""))]
        elif filter_category == "STARRED":
            filtered = [x for x in filtered if x.get("is_starred", False)]
        elif filter_category == "SHADOW":
            filtered = [x for x in filtered if x.get("trade_category") == "SHADOW"]
        elif filter_category == "REAL":
            filtered = [x for x in filtered if x.get("trade_category") == "REAL"]

        # Arama filtresi
        if search:
            q = search.lower().strip()
            filtered = [
                x for x in filtered
                if q in x.get("symbol", "").lower()
                or q in x.get("setup_id", "").lower()
                or q in x.get("autopsy", {}).get("diagnosis_title", "").lower()
            ]

        # KPI İstatistikleri
        total_count = len(self.catalog)
        loss_count = sum(1 for x in self.catalog if is_loss_entry(x))
        win_count = sum(1 for x in self.catalog if is_win_entry(x))
        be_count = sum(1 for x in self.catalog if is_be_entry(x))
        trap_count = sum(1 for x in self.catalog if "FAKEOUT" in str(x.get("autopsy", {}).get("diagnosis_code", "")) or "HUNT" in str(x.get("autopsy", {}).get("diagnosis_code", "")))
        starred_count = sum(1 for x in self.catalog if x.get("is_starred", False))

        # Disk boyutu hesabı
        total_bytes = 0
        try:
            for root, _, files in os.walk(self.BASE_DIR):
                for f in files:
                    total_bytes += os.path.getsize(os.path.join(root, f))
        except Exception:
            pass
        disk_mb = round(total_bytes / (1024 * 1024), 1)

        # Sayfalama
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paged_items = filtered[start_idx:end_idx]

        return {
            "total_items": len(filtered),
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (len(filtered) + page_size - 1) // page_size),
            "stats": {
                "total_count": total_count,
                "loss_count": loss_count,
                "win_count": win_count,
                "be_count": be_count,
                "trap_count": trap_count,
                "starred_count": starred_count,
                "disk_mb": disk_mb
            },
            "snapshots": paged_items
        }


# Singleton yönetici
forensic_blackbox_manager = ForensicBlackboxManager()
