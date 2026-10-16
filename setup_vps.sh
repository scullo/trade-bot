#!/bin/bash
# ==============================================================================
# 🛡️ VALKYRIE QUANT DESK - 1-CLICK 24/7 VPS AUTO INSTALLER & SYSTEM HARDENING
# ==============================================================================
# Ubuntu / Debian tabanlı küçük/orta ölçekli VPS sunucuları için
# bellek korumalı (Swap), kalıcı veritabanı destekli, kurumsal kurulum betiği.
# ==============================================================================

set -e

echo "======================================================"
echo "⚡ VALKYRIE QUANT DESK - 24/7 VPS KURULUMU BAŞLATILIYOR"
echo "======================================================"

# 1. Sistem Paketlerini Güncelle ve Gerekli Araçları Yükle
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip python3-venv git curl ufw logrotate

# 2. OOM (Out-of-Memory) Koruması: 2GB Swap Alanı Tahsisi
SWAP_SIZE_MB=$(free -m | awk '/^Swap:/ {print $2}')
if [ -z "$SWAP_SIZE_MB" ] || [ "$SWAP_SIZE_MB" -lt 1024 ]; then
    echo "⚡ 2GB Swap hafıza tahsis ediliyor (512MB/1GB VPS OOM Çökme Koruması)..."
    sudo swapoff -a 2>/dev/null || true
    sudo fallocate -l 2G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    if ! grep -q '/swapfile' /etc/fstab; then
        echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    fi
    echo "vm.swappiness=10" | sudo tee -a /etc/sysctl.conf
    sudo sysctl -p 2>/dev/null || true
    echo "✅ 2GB Swap alanı başarıyla aktif edildi."
else
    echo "✅ Mevcut Swap alanı yeterli ($SWAP_SIZE_MB MB)."
fi

# 3. Dizin ve Çevre Dosyası Hazırlığı
CURRENT_DIR=$(pwd)
CURRENT_USER=$(whoami)

mkdir -p "$CURRENT_DIR/db"
mkdir -p "$CURRENT_DIR/forensic_blackbox"
mkdir -p "$CURRENT_DIR/templates"

if [ ! -f "$CURRENT_DIR/.env" ] && [ -f "$CURRENT_DIR/.env.example" ]; then
    echo "⚡ .env.example şablonundan .env dosyası oluşturuluyor..."
    cp "$CURRENT_DIR/.env.example" "$CURRENT_DIR/.env"
    chmod 600 "$CURRENT_DIR/.env"
fi

if [ ! -f "$CURRENT_DIR/live_config.json" ] && [ -f "$CURRENT_DIR/live_config.example.json" ]; then
    echo "⚡ live_config.example.json şablonundan live_config.json oluşturuluyor..."
    cp "$CURRENT_DIR/live_config.example.json" "$CURRENT_DIR/live_config.json"
fi

# 4. Sanal Ortam (venv) ve Bağımlılıkların Kurulumu
echo "⚡ Python sanal ortamı hazırlanıyor..."
python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# 5. Kurumsal Log Döner Sistemi (Logrotate) Yapılandırması
sudo tee /etc/logrotate.d/valkyrie > /dev/null <<EOF
$CURRENT_DIR/valkyrie.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    copytruncate
}
EOF

# 6. Systemd Servisi Yapılandırması (Otomatik Yeniden Başlatma, Dosya Sınırı ve .env Desteği)
sudo tee /etc/systemd/system/valkyrie.service > /dev/null <<EOF
[Unit]
Description=Valkyrie Quant Desk 24/7 Automated Trade Bot
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$CURRENT_DIR
EnvironmentFile=-$CURRENT_DIR/.env
Environment=PYTHONUNBUFFERED=1
ExecStart=$CURRENT_DIR/venv/bin/python $CURRENT_DIR/main.py
Restart=always
RestartSec=5
LimitNOFILE=65535
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable valkyrie.service
sudo systemctl restart valkyrie.service

# 7. Güvenlik Duvarı (UFW) Yapılandırması
if command -v ufw > /dev/null; then
    sudo ufw allow 5000/tcp comment 'Valkyrie Dashboard Port' 2>/dev/null || true
    sudo ufw allow 22/tcp comment 'SSH Port' 2>/dev/null || true
    sudo ufw --force enable 2>/dev/null || true
fi

PUBLIC_IP=$(curl -s --connect-timeout 3 ifconfig.me || curl -s --connect-timeout 3 icanhazip.com || echo "SUNUCU_IP_ADRESINIZ")

echo "======================================================"
echo "🎉 KURULUM VE GÜVENLİK YAPILANDIRMASI TAMAMLANDI!"
echo "======================================================"
echo "Botunuz 24/7 arka planda izole systemd servisiyle çalışıyor."
echo "Dashboard Adresiniz: http://$PUBLIC_IP:5000"
echo ""
echo "Faydalı Yönetim Komutları:"
echo "  Durum Kontrol  : sudo systemctl status valkyrie"
echo "  Canlı Loglar   : sudo journalctl -u valkyrie -f"
echo "  Uygulama Logu  : tail -f valkyrie.log"
echo "  Yeniden Başlat : sudo systemctl restart valkyrie"
echo "  Durdur         : sudo systemctl stop valkyrie"
echo "  Backtest Çalıştır: venv/bin/python backtest_engine.py --symbol BTC/USDT --days 60"
echo "======================================================"
