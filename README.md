# MT5 Cloud — 公開網站 + Windows Agent
# 將你嘅 MT5 交易平台放上雲端，任何 browser 都用得

## 系統架構

```
🌐 Cloud Server (Linux VPS)
├── 用戶註冊/登入
├── Web Dashboard (EA配對+分析+Correlation)
├── WebSocket 同 Agent 溝通
└── Database (用戶資料)
     ↑ WebSocket / HTTPS ↓
🖥️ 你嘅 Windows 機 (有 MT5)
├── MT5 Cloud Agent
└── MetaTrader 5
```

## Deploy Server

### 1. 租 VPS（建議配置）

| 供應商 | Plan | 月費 |
|-------|------|------|
| DigitalOcean | Basic $6 | ~$6 USD |
| 阿里雲 | 輕量應用伺服器 | ~$34 HKD |
| AWS Lightsail | $5 plan | ~$5 USD |
| Linode | Nanode 1GB | ~$5 USD |

### 2. 裝 Server

```bash
# SSH 入你嘅 VPS
ssh root@your-server-ip

# Install Python + dependencies
apt update && apt install -y python3 python3-pip git

# Clone project
git clone https://github.com/hongkpng855-lang/mt5-trading-bot.git
cd mt5-cloud/server

# Install requirements
pip install -r requirements.txt

# Set SECRET_KEY (change this!)
export SECRET_KEY="your-random-secret-key-here"

# Run with gunicorn (production)
gunicorn -k eventlet -w 1 -b 0.0.0.0:80 app:app
```

### 3. 用 systemd 開機自啟動

```bash
# /etc/systemd/system/mt5cloud.service
[Unit]
Description=MT5 Cloud Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/mt5-cloud/server
Environment=SECRET_KEY=your-secret-key
ExecStart=/usr/bin/gunicorn -k eventlet -w 1 -b 0.0.0.0:80 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

### 4. Set Domain + HTTPS（免費）

```bash
# Install nginx + certbot
apt install -y nginx certbot python3-certbot-nginx

# /etc/nginx/sites-available/mt5cloud
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:80;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}

# Get HTTPS certificate
certbot --nginx -d your-domain.com
```

## Windows Agent

### Quick Start

```bash
# 喺你部有 MT5 嘅 Windows 機
pip install MetaTrader5 python-socketio[client] requests

python agent.py --server https://your-server.com --agent-id YOUR_AGENT_ID
```

### Build .exe（俾人直接下載）

```bash
pip install pyinstaller
python build_agent.py
# 產出：dist/MT5 Cloud Agent.exe
```

## 用戶流程

```
1️⃣ 上 your-domain.com → Register
2️⃣ 記低 Agent ID
3️⃣ Download MT5 Cloud Agent.exe
4️⃣ 開 Agent → 入 Server URL + Agent ID
5️⃣ MT5 自動上線 → 網頁 Dashboard 用到晒所有功能！
```
