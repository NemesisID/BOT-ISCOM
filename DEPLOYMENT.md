# Deployment Guide - ISCOM Bot on Ubuntu 22.04 (Proxmox CT)

Panduan lengkap untuk deploy ISCOM Bot di server Ubuntu 22.04 yang berjalan di container Proxmox.

---

## 1. Persiapan Container Proxmox

### Spesifikasi Minimal Container
- **OS**: Ubuntu 22.04 LTS
- **RAM**: Minimal 2GB (4GB recommended)
- **Storage**: Minimal 20GB
- **CPU**: 2 cores
- **Network**: Bridge mode dengan IP static

### Buat Container di Proxmox
```bash
# Download template Ubuntu 22.04 (di node Proxmox)
pveam download local vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.zst

# Buat container baru (CT ID 100, sesuaikan)
pct create 100 local:vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.zst \
  --hostname iscom-bot \
  --memory 4096 \
  --cores 2 \
  --rootfs local-lvm:20 \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --unprivileged 1 \
  --start 1
```

---

## 2. Setup Awal Container

### Masuk ke Container
```bash
# Dari node Proxmox
pct enter 100

# Atau SSH ke container
ssh root@<IP_CONTAINER>
```

### Update System
```bash
apt update && apt upgrade -y
apt install -y curl wget git nano htop
```

### Set Timezone
```bash
timedatectl set-timezone Asia/Jakarta
```

---

## 3. Install Python 3.11+

### Install Dependencies
```bash
apt install -y software-properties-common
add-apt-repository ppa:deadsnakes/ppa -y
apt update
```

### Install Python 3.11
```bash
apt install -y python3.11 python3.11-venv python3.11-dev python3-pip
```

### Set Python 3.11 sebagai Default
```bash
update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1
```

### Install pip
```bash
curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11
```

---

## 4. Install MongoDB

### Install MongoDB 7.0
```bash
# Import GPG key
curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | \
  gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor

# Add repository
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | \
  tee /etc/apt/sources.list.d/mongodb-org-7.0.list

# Install
apt update
apt install -y mongodb-org
```

### Start MongoDB
```bash
systemctl start mongod
systemctl enable mongod
systemctl status mongod
```

### Buat Database User (Opsional tapi Recommended)
```bash
mongosh

# Di mongosh shell
use iscom
db.createUser({
  user: "GANTI_USERNAME_DISINI",
  pwd: "GANTI_PASSWORD_KUAT_DISINI",
  roles: [{ role: "readWrite", db: "iscom" }]
})
exit
```

---

## 5. Setup Bot Directory

### Buat User untuk Bot (Recommended)
```bash
useradd -m -s /bin/bash iscom
usermod -aG sudo iscom
```

### Clone/Copy Bot Files
```bash
# Sebagai user iscom
su - iscom

# Atau sebagai root, lalu chown
mkdir -p /opt/iscom-bot/BOT-ISCOM
cd /opt/iscom-bot/BOT-ISCOM

# Jika dari git
git clone https://github.com/NemesisID/BOT-ISCOM.git .

# Atau copy files via SCP/SFTP
```

### Set Permissions
```bash
chown -R iscom:iscom /opt/iscom-bot/BOT-ISCOM
```

---

## 6. Setup Python Environment

### Buat Virtual Environment
```bash
cd /opt/iscom-bot/BOT-ISCOM
python3 -m venv venv
source venv/bin/activate
```

### Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Setup .env File
```bash
cp .env.example .env  # Jika ada
nano .env
```

Isi dengan konfigurasi:
```env
TOKEN="YOUR_DISCORD_BOT_TOKEN"
PREFIX="!"
SHARD_COUNT="2"
BOT_NAME="ISCOM"

# OAuth2 / Dashboard Configuration
DISCORD_CLIENT_ID="YOUR_CLIENT_ID"
DISCORD_CLIENT_SECRET="YOUR_CLIENT_SECRET"
DASHBOARD_SECRET="iscom-random-secret-string-change-this"
DASHBOARD_BASE_URL="http://your-domain.com:25572"

# MongoDB Database Configuration
MONGO_URI="mongodb://GANTI_USERNAME:GANTI_PASSWORD@localhost:27017/iscom?authSource=iscom"

# Web / Dashboard
DASHBOARD_ENABLED="True"
WEB_HOST="0.0.0.0"
WEB_PORT="25572"

# Automation Features
SYNC_EMOJIS="False"

# Logging & Channel Configuration
REPORT_CHANNEL=""
GUILD_JOIN_WEBHOOK="1500926701494993043"
GUILD_LEAVE_WEBHOOK=""
SHARDS_LOG_WEBHOOK="1500927194422054995"

# Authorized Users
DEVELOPER_IDS="YOUR_DISCORD_ID"
```

---

## 7. Setup Systemd Service

### Buat Service File
```bash
nano /etc/systemd/system/iscom-bot.service
```

### Konfigurasi Service
```ini
[Unit]
Description=ISCOM Discord Bot
After=network.target mongod.service
Wants=mongod.service

[Service]
Type=simple
User=iscom
Group=iscom
WorkingDirectory=/opt/iscom-bot/BOT-ISCOM
Environment="PATH=/opt/iscom-bot/BOT-ISCOM/venv/bin"
ExecStart=/opt/iscom-bot/BOT-ISCOM/venv/bin/python main.py
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=10
TimeoutStopSec=30

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=iscom-bot

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

### Enable dan Start Service
```bash
systemctl daemon-reload
systemctl enable iscom-bot
systemctl start iscom-bot
systemctl status iscom-bot
```

---

## 8. Setup Nginx Reverse Proxy (Optional)

### Install Nginx
```bash
apt install -y nginx
```

### Konfigurasi Reverse Proxy
```bash
nano /etc/nginx/sites-available/iscom-bot
```

```nginx
server {
    listen 80;
    server_name dash-iscom.isslab.web.id;

    location / {
        proxy_pass http://127.0.0.1:25572;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
}
```

### Enable Site
```bash
sudo ln -s /etc/nginx/sites-available/iscom-bot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```