"""
state_store.py - Render'ın geçici (ephemeral) diskine karşı kalıcılık katmanı.

Render her deploy/restart'ta diski siler. Bu modül, kritik dosyaları GitHub
deposunun izole 'state' dalına yedekler ve açılışta geri yükler.

Kapsam:
  - live_config.json          (API anahtarları HARİÇ - bkz. SENSITIVE_KEYS)
  - live_trade_history.json   (canlı işlem defteri)
  - live_positions_state.json (canlı açık pozisyonların stop/TP meta verisi)
  - valkyrie_platform.db      (kullanıcı/ödeme veritabanı, SQLite backup API ile tutarlı kopya)
"""
import base64
import json
import os
import sqlite3
import tempfile
import threading
import time
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# API anahtarları GitHub'a ASLA yazılmaz (vault ana anahtarı repoda gömülü olduğundan
# şifreli hali de güvenli sayılmaz). Canlıda anahtarlar Render ortam değişkenlerinden okunur.
SENSITIVE_KEYS = ("api_key", "api_secret")


def _token() -> str:
    try:
        from paper_trader import GITHUB_TOKEN
        return GITHUB_TOKEN or ""
    except Exception:
        return os.environ.get("GITHUB_TOKEN", "")


def _repo() -> str:
    return os.environ.get("GITHUB_REPO", "scullo/trade-bot")


def _branch() -> str:
    return os.environ.get("GITHUB_STATE_BRANCH", "state")


def _is_test() -> bool:
    import sys
    return bool(os.environ.get("UNITTEST_MODE") or os.environ.get("PYTEST_CURRENT_TEST")) or \
        any("test" in str(a).lower() for a in sys.argv)


_locks = {}
_last_push = {}
_sha_cache = {}


def _api(remote_name: str) -> str:
    return f"https://api.github.com/repos/{_repo()}/contents/{remote_name}"


def _headers(tok: str) -> dict:
    return {
        "Authorization": f"token {tok}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "TradeBot/1.0",
    }


def fetch_remote(remote_name: str):
    """GitHub state dalından dosya içeriğini (bytes) indirir; yoksa None."""
    tok = _token()
    if not tok or _is_test():
        return None
    try:
        req = urllib.request.Request(f"{_api(remote_name)}?ref={_branch()}", headers=_headers(tok))
        data = json.loads(urllib.request.urlopen(req, timeout=15).read().decode("utf-8"))
        _sha_cache[remote_name] = data.get("sha")
        content = data.get("content", "")
        if not content and data.get("download_url"):
            # >1MB dosyalarda içerik boş döner, raw URL'den indir
            raw_req = urllib.request.Request(data["download_url"], headers=_headers(tok))
            return urllib.request.urlopen(raw_req, timeout=30).read()
        return base64.b64decode(content)
    except Exception as e:
        if "404" not in str(e):
            print(f">> [STATE STORE] {remote_name} indirilemedi: {e}")
        return None


def push_remote(remote_name: str, payload: bytes, message: str = "") -> bool:
    tok = _token()
    if not tok or _is_test():
        return False
    lock = _locks.setdefault(remote_name, threading.Lock())
    with lock:
        for attempt in range(1, 4):
            try:
                try:
                    req = urllib.request.Request(f"{_api(remote_name)}?ref={_branch()}", headers=_headers(tok))
                    gh = json.loads(urllib.request.urlopen(req, timeout=10).read().decode("utf-8"))
                    _sha_cache[remote_name] = gh.get("sha")
                except Exception:
                    pass
                body = {
                    "message": message or f"[BOT] state backup {remote_name} ({time.strftime('%H:%M:%S')})",
                    "content": base64.b64encode(payload).decode("utf-8"),
                    "branch": _branch(),
                }
                if _sha_cache.get(remote_name):
                    body["sha"] = _sha_cache[remote_name]
                req = urllib.request.Request(_api(remote_name), data=json.dumps(body).encode("utf-8"), method="PUT",
                                             headers={**_headers(tok), "Content-Type": "application/json"})
                resp = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
                _sha_cache[remote_name] = resp.get("content", {}).get("sha")
                return True
            except Exception as e:
                print(f">> [STATE STORE] {remote_name} push denemesi {attempt}/3 hata: {e}")
                time.sleep(2 * attempt)
    return False


def _strip_sensitive(local_path: str, raw: bytes) -> bytes:
    if os.path.basename(local_path) != "live_config.json":
        return raw
    try:
        cfg = json.loads(raw.decode("utf-8"))
        for k in SENSITIVE_KEYS:
            cfg.pop(k, None)
        return json.dumps(cfg, ensure_ascii=False, indent=2).encode("utf-8")
    except Exception:
        return raw


def backup_file(local_path: str, remote_name: str = None, critical: bool = False, min_interval: float = 15.0):
    """Dosyayı GitHub state dalına yedekler. critical=False ise arka planda ve throttle'lı."""
    remote_name = remote_name or os.path.basename(local_path)
    if not os.path.exists(local_path):
        return

    def _do():
        try:
            if local_path.endswith(".db"):
                payload = _sqlite_snapshot(local_path)
            else:
                with open(local_path, "rb") as f:
                    payload = f.read()
                payload = _strip_sensitive(local_path, payload)
            if payload:
                if push_remote(remote_name, payload):
                    print(f">> [STATE STORE] {remote_name} GitHub state dalına yedeklendi.")
        except Exception as e:
            print(f">> [STATE STORE] {remote_name} yedekleme hatası: {e}")

    now = time.time()
    if not critical and now - _last_push.get(remote_name, 0) < min_interval:
        return
    _last_push[remote_name] = now
    if critical:
        _do()
    else:
        threading.Thread(target=_do, daemon=True).start()


def _sqlite_snapshot(db_path: str) -> bytes:
    """Çalışan SQLite veritabanının tutarlı kopyasını (online backup API) alır."""
    fd, tmp = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(tmp)
        with dst:
            src.backup(dst)
        src.close()
        dst.close()
        with open(tmp, "rb") as f:
            return f.read()
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass


def restore_file(local_path: str, remote_name: str = None, merge_json: bool = False) -> bool:
    """
    Açılışta GitHub'daki yedeği diske geri yükler.
    - Yerel dosya yoksa: doğrudan yazar.
    - merge_json=True (live_config): uzak yedeği temel alır, yerelde olan anahtarları korur.
    """
    remote_name = remote_name or os.path.basename(local_path)
    raw = fetch_remote(remote_name)
    if raw is None:
        return False
    try:
        if merge_json and os.path.exists(local_path):
            with open(local_path, "r", encoding="utf-8") as f:
                local = json.load(f)
            remote = json.loads(raw.decode("utf-8"))
            remote.update({k: v for k, v in local.items() if k in SENSITIVE_KEYS and v})
            raw = json.dumps(remote, ensure_ascii=False, indent=2).encode("utf-8")
        elif os.path.exists(local_path) and os.path.getsize(local_path) > 0 and not local_path.endswith(".db"):
            # Yerel veri zaten varsa, gecerli JSON kontrolu yap; kucuk/temiz reset dosyalarini engelleme
            try:
                json.loads(raw.decode("utf-8"))
            except Exception:
                if os.path.getsize(local_path) >= len(raw):
                    return False
        elif local_path.endswith(".db") and os.path.exists(local_path):
            # Yeni boş oluşturulmuş DB'yi yedekle değiştir (sadece Render cold-start'ında anlamlı)
            if os.path.getsize(local_path) >= len(raw):
                return False
        tmp = local_path + ".restore_tmp"
        with open(tmp, "wb") as f:
            f.write(raw)
        os.replace(tmp, local_path)
        print(f">> [STATE STORE] {remote_name} GitHub state dalından geri yüklendi ({len(raw)} bayt).")
        return True
    except Exception as e:
        print(f">> [STATE STORE] {remote_name} geri yükleme hatası: {e}")
        return False


PERSISTED_FILES = [
    ("trade_history.json", False),
    ("live_config.json", True),
    ("live_trade_history.json", False),
    ("live_positions_state.json", False),
    ("valkyrie_platform.db", False),
]


def restore_all():
    """Uygulama açılışında (diğer modüller dosyaları okumadan ÖNCE) çağrılmalıdır."""
    for name, merge in PERSISTED_FILES:
        restore_file(os.path.join(BASE_DIR, name), name, merge_json=merge)


def start_periodic_backup(interval_sec: float = 300.0):
    """Değişen dosyaları (mtime) periyodik olarak yedekler. DB yazımları için emniyet ağı."""
    mtimes = {}

    def _loop():
        while True:
            time.sleep(interval_sec)
            for name, _ in PERSISTED_FILES:
                p = os.path.join(BASE_DIR, name)
                try:
                    m = os.path.getmtime(p)
                except OSError:
                    continue
                if mtimes.get(name) != m:
                    mtimes[name] = m
                    backup_file(p, name, critical=True)

    threading.Thread(target=_loop, daemon=True, name="StateStoreBackup").start()
