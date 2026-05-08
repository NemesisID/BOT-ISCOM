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
  user: "iscom_user",
  pwd: "password_yang_kuat",
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
mkdir -p /opt/iscom-bot
cd /opt/iscom-bot

# Jika dari git
git clone https://github.com/username/iscom-bot.git .

# Atau copy files via SCP/SFTP
```

### Set Permissions
```bash
chown -R iscom:iscom /opt/iscom-bot
```

---

## 6. Setup Python Environment

### Buat Virtual Environment
```bash
cd /opt/iscom-bot
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
MONGO_URI="mongodb://iscom_user:password_yang_kuat@localhost:27017/iscom?authSource=iscom"

# Web / Dashboard
DASHBOARD_ENABLED="True"
WEB_HOST="0.0.0.0"
WEB_PORT="25572"

# Automation Features
SYNC_EMOJIS="False"

# Logging & Channel Configuration
REPORT_CHANNEL="YOUR_CHANNEL_ID"
GUILD_JOIN_WEBHOOK=""
GUILD_LEAVE_WEBHOOK=""
SHARDS_LOG_WEBHOOK=""

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
WorkingDirectory=/opt/iscom-bot
Environment="PATH=/opt/iscom-bot/venv/bin"
ExecStart=/opt/iscom-bot/venv/bin/python main.py
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
    server_name your-domain.com;

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
ln -s /etc/nginx/sites-available/iscom-bot /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

### Setup SSL dengan Certbot
```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d your-domain.com
```

---

## 9. Setup Firewall

### Install UFW
```bash
apt install -y ufw
```

### Konfigurasi Rules
```bash
# Default policies
ufw default deny incoming
ufw default allow outgoing

# Allow SSH
ufw allow 22/tcp

# Allow Dashboard (jika tanpa nginx)
ufw allow 25572/tcp

# Allow HTTP/HTTPS (jika dengan nginx)
ufw allow 80/tcp
ufw allow 443/tcp

# Enable
ufw enable
```

### Check Status
```bash
ufw status verbose
```

---

## 10. Setup Log Rotation

### Buat Logrotate Config
```bash
nano /etc/logrotate.d/iscom-bot
```

```
/opt/iscom-bot/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 iscom iscom
    sharedscripts
    postrotate
        systemctl reload iscom-bot > /dev/null 2>&1 || true
    endscript
}
```

---

## 11. Monitoring & Maintenance

### Check Logs
```bash
# Systemd journal
journalctl -u iscom-bot -f

# Bot logs
tail -f /opt/iscom-bot/logs/*.log
```

### Check Service Status
```bash
systemctl status iscom-bot
```

### Restart Service
```bash
systemctl restart iscom-bot
```

### Update Bot
```bash
cd /opt/iscom-bot
systemctl stop iscom-bot
git pull  # atau upload files baru
source venv/bin/activate
pip install -r requirements.txt
systemctl start iscom-bot
```

---

## 12. Backup Strategy

### Backup Script
```bash
nano /opt/backup-iscom.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/backup/iscom"
DATE=$(date +%Y%m%d_%H%M%S)
BOT_DIR="/opt/iscom-bot"

mkdir -p $BACKUP_DIR

# Backup bot files
tar -czf $BACKUP_DIR/iscom-bot-$DATE.tar.gz -C $BOT_DIR .

# Backup MongoDB
mongodump --db iscom --out $BACKUP_DIR/mongo-$DATE

# Compress mongo backup
tar -czf $BACKUP_DIR/mongo-$DATE.tar.gz -C $BACKUP_DIR mongo-$DATE
rm -rf $BACKUP_DIR/mongo-$DATE

# Keep only last 7 days
find $BACKUP_DIR -type f -mtime +7 -delete

echo "Backup completed: $DATE"
```

### Cron Job untuk Backup Harian
```bash
chmod +x /opt/backup-iscom.sh
crontab -e
```

```
0 3 * * * /opt/backup-iscom.sh >> /var/log/iscom-backup.log 2>&1
```

---

## 13. Troubleshooting

### Bot Tidak Start
```bash
# Check logs
journalctl -u iscom-bot -n 50

# Check Python
cd /opt/iscom-bot
source venv/bin/activate
python main.py  # Run manual untuk debug
```

### MongoDB Connection Error
```bash
# Check MongoDB status
systemctl status mongod

# Test connection
mongosh "mongodb://localhost:27017/iscom"
```

### Dashboard Tidak Bisa Diakses
```bash
# Check port
netstat -tlnp | grep 25572

# Check firewall
ufw status

# Check nginx (jika pakai)
nginx -t
systemctl status nginx
```

### Memory Issues
```bash
# Check memory usage
free -h
htop

# Restart bot jika memory leak
systemctl restart iscom-bot
```

---

## 14. Quick Commands Reference

| Task | Command |
|------|---------|
| Start bot | `systemctl start iscom-bot` |
| Stop bot | `systemctl stop iscom-bot` |
| Restart bot | `systemctl restart iscom-bot` |
| Status bot | `systemctl status iscom-bot` |
| View logs | `journalctl -u iscom-bot -f` |
| Update bot | `cd /opt/iscom-bot && git pull && systemctl restart iscom-bot` |
| Backup | `/opt/backup-iscom.sh` |

---

## Checklist Deployment

- [ ] Container Proxmox dibuat
- [ ] System updated
- [ ] Python 3.11 installed
- [ ] MongoDB installed dan running
- [ ] Bot files di `/opt/iscom-bot`
- [ ] Virtual environment created
- [ ] Dependencies installed
- [ ] `.env` configured
- [ ] Systemd service created dan enabled
- [ ] Firewall configured
- [ ] Nginx reverse proxy (optional)
- [ ] SSL certificate (optional)
- [ ] Backup script setup
- [ ] Bot running successfully

---

**Selamat! ISCOM Bot Anda sudah berjalan di server Ubuntu 22.04.**
