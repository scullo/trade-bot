#!/bin/bash
# ==========================================
# VALKYRIE QUANT DESK - 1-CLICK 24/7 VPS AUTO INSTALLER
# ==========================================

echo "======================================================"
echo "⚡ VALKYRIE QUANT DESK - 24/7 VPS KURULUMU BASLATILIYOR"
echo "======================================================"

sudo apt-get update -y
sudo apt-get install -y python3 python3-pip python3-venv git curl

python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

CURRENT_DIR=$(pwd)
CURRENT_USER=$(whoami)

sudo tee /etc/systemd/system/valkyrie.service > /dev/null <<EOF
[Unit]
Description=Valkyrie Quant Desk 24/7 Automated Trade Bot
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$CURRENT_DIR
ExecStart=$CURRENT_DIR/venv/bin/python $CURRENT_DIR/main.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable valkyrie.service
sudo systemctl restart valkyrie.service

if command -v ufw > /dev/null; then
    sudo ufw allow 5000/tcp
    sudo ufw reload
fi

PUBLIC_IP=$(curl -s ifconfig.me || curl -s icanhazip.com || echo "SUNUCU_IP_ADRESINIZ")

echo "======================================================"
echo "🎉 KURULUM BASARIYLA TAMAMLANDI!"
echo "======================================================"
echo "Botunuz 24/7 arka planda calismaya basladi."
echo "Dashboard Adresiniz: http://$PUBLIC_IP:5000"
echo ""
echo "Faydali Komutlar:"
echo "  Durum Kontrol: sudo systemctl status valkyrie"
echo "  Canli Loglar:  sudo journalctl -u valkyrie -f"
echo "  Yeniden Baslat: sudo systemctl restart valkyrie"
echo "  Durdur:        sudo systemctl stop valkyrie"
echo "======================================================"
