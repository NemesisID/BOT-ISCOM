# Setup Lavalink Server di Proxmox

## Prerequisites

- Proxmox VM/LXC dengan Debian/Ubuntu
- Java 17+
- Akun Spotify Developer (untuk fitur Spotify)

---

## 1. Install Java 17+

```bash
sudo apt update
sudo apt install openjdk-17-jre-headless -y
java -version
```

## 2. Buat directory dan download Lavalink

```bash
sudo mkdir -p /opt/lavalink
cd /opt/lavalink
sudo wget https://github.com/lavalink-devs/Lavalink/releases/download/4.0.8/Lavalink.jar
```

> Cek versi terbaru di https://github.com/lavalink-devs/Lavalink/releases

## 3. Buat config `application.yml`

```bash
sudo nano /opt/lavalink/application.yml
```

```yaml
server:
  port: 2333
  address: 0.0.0.0

lavalink:
  plugins:
    - dependency: "com.github.topi314.lavasrc:lavasrc-plugin:4.3.0"
      repository: "https://maven.lavalink.dev/releases"
    - dependency: "dev.lavalink.youtube:youtube-plugin:1.11.5"
      repository: "https://maven.lavalink.dev/releases"
  server:
    password: "ganti_dengan_password_kamu"
    sources:
      youtube: false
      bandcamp: true
      soundcloud: true
      twitch: true
      vimeo: true
      http: true
      local: false
    bufferDurationMs: 400
    frameBufferDurationMs: 5000
    playerUpdateInterval: 5
    youtubeSearchEnabled: true
    soundcloudSearchEnabled: true
    gc-warnings: true

plugins:
  youtube:
    enabled: true
    clients:
      - MUSIC
      - WEB
      - ANDROID_TESTSUITE
  lavasrc:
    providers:
      - "ytsearch:\"%ISRC%\""
      - "ytsearch:%QUERY%"
    sources:
      spotify: true
      applemusic: false
      deezer: false
      yandexmusic: false
    spotify:
      clientId: "SPOTIFY_CLIENT_ID_KAMU"
      clientSecret: "SPOTIFY_CLIENT_SECRET_KAMU"
      countryCode: "ID"

logging:
  file:
    path: ./logs/
  level:
    root: INFO
    lavalink: INFO
```

## 4. Dapat Spotify Credentials

1. Buka https://developer.spotify.com/dashboard
2. Create App
3. Copy **Client ID** dan **Client Secret**
4. Masukkan ke `application.yml` di bagian `plugins.lavasrc.spotify`

## 5. Buat systemd service

```bash
sudo nano /etc/systemd/system/lavalink.service
```

```ini
[Unit]
Description=Lavalink Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/lavalink
ExecStart=/usr/bin/java -jar /opt/lavalink/Lavalink.jar
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## 6. Start service

```bash
sudo systemctl daemon-reload
sudo systemctl enable lavalink
sudo systemctl start lavalink
sudo systemctl status lavalink
```

## 7. Konfigurasi Bot

Tambahkan ke `.env` bot:

```env
LAVALINK_URI=http://localhost:2333
LAVALINK_PASSWORD=ganti_dengan_password_kamu
```

## 8. Verifikasi

```bash
# Cek Lavalink jalan
curl http://localhost:2333/version

# Restart bot
sudo systemctl restart iscom-bot

# Cek log Lavalink
sudo journalctl -u lavalink -n 30

# Cek log bot
sudo journalctl -u iscom-bot -n 30
```

---

## Catatan

- Plugin akan auto-download saat Lavalink pertama kali start (~10 detik)
- Spotify links di-resolve ke YouTube secara otomatis oleh LavaSrc
- Karena Lavalink di localhost, tidak perlu expose ke internet/Cloudflare
- Bot code sudah dikonfigurasi membaca `LAVALINK_URI` dan `LAVALINK_PASSWORD` dari environment variable
- `retries` sudah diset ke 3 untuk auto-reconnect jika koneksi sempat putus

## Troubleshooting

| Masalah | Solusi |
|---------|--------|
| `InvalidNodeException` | Cek `sudo systemctl status lavalink` — pastikan service running |
| Plugin gagal download | Cek koneksi internet di Proxmox, pastikan bisa akses maven.lavalink.dev |
| Spotify link tidak resolve | Pastikan clientId dan clientSecret benar di application.yml |
| YouTube "No matches" | Pastikan youtube-plugin terload di log Lavalink |
| Port 2333 tidak bisa diakses | Cek firewall: `sudo ufw allow 2333` (hanya perlu jika bot di mesin berbeda) |
