# ☁️ MT5 Cloud

**MT5 Cloud** — 一個 SaaS 平台，幫你經 **Web Dashboard** 管理 MetaTrader 5 EA，自動下載、編譯、部署，唔使開 chart / drag EA。

---

## 🚀 快速開始

### 1. 部 Server

```bash
cd server
pip install -r requirements.txt
python app.py
```

Server 會行喺 `http://localhost:5000`

### 2. 開 Tunnel（可選）

外網存取 Dashboard：

```bash
# Cloudflare Tunnel（免費，唔使 CC）
cloudflared tunnel --url http://localhost:5000
```

### 3. 起 Agent

```bash
cd agent
python agent.py --server http://localhost:5000 --agent-id DEV00001
```

> Agent 同 Server 可以喺同一部機行，亦可以分開。

### 4. 開 Browser

去 `http://localhost:5000` 或 Cloudflare URL，用 `dev / dev1234` 登入。

---

## 📦 架構

```
┌─────────────────┐     WebSocket      ┌──────────────────┐
│   Dashboard     │◄──────────────────►│   Flask Server   │
│  (Browser/手機)  │                    │  (localhost:5000) │
└─────────────────┘                    └────────┬─────────┘
                                                │
                                ┌───────────────┴───────────────┐
                                │           SQLite DB           │
                                │  (user, ea_config, agent,     │
                                │   deploy_queue, account_info) │
                                └───────────────────────────────┘
                                                │
                          ┌─────────────────────┴─────────────────────┐
                          │         Agent (背景執行)                   │
                          │  - WebSocket 連接 server                  │
                          │  - 每 2s HTTP poll deploy_queue           │
                          │  - 每 10s sync MT5 數據                   │
                          │  - Download + Compile EA (.mq5)           │
                          │  - MT5 Python API 落單                    │
                          └─────────────────┬────────────────────────┘
                                            │
                          ┌──────────────────┴──────────────────┐
                          │       MetaTrader 5 Terminal         │
                          │   Account: IC Markets Demo 52781843 │
                          └─────────────────────────────────────┘
```

---

## 🌐 Symbol 對應

Web UI 用嘅名 vs Broker（IC Markets）實際名：

| UI 顯示 | MT5 名 | 狀態 |
|---------|--------|------|
| EURUSD | EURUSD | ✅ 可交易 |
| GBPUSD | GBPUSD | ✅ 可交易 |
| US30 | US30 | ✅ 可交易 |
| **DAX40** | **DE40** | ⚠️ close only |
| **SP500** | **US500** | ⚠️ close only |
| **NAS100** | — | ❌ 無此 symbol |

Agent 嘅 `execute_deploy()` 自動 mapping：`DAX40→DE40`、`SP500→US500`。

---

## 🚢 部署

### Cloudflare Tunnel（免費，推薦）

```bash
# 安裝 cloudflared
curl -L -o cloudflared.exe https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe

# 啟動 tunnel（每次 restart 會出新 URL）
cloudflared tunnel --url http://localhost:5000
```

⚠️ Quick Tunnel 每次 restart 會出新 URL。想固定 URL 要用 Cloudflare account：

```bash
cloudflared tunnel login
cloudflared tunnel create mt5-cloud
cloudflared tunnel route dns mt5-cloud mt5.example.com
```

### Render（需 CC 驗證）

```bash
gunicorn -k eventlet -w 1 --bind 0.0.0.0:$PORT wsgi:app
```

### ngrok

```bash
ngrok http 5000
```

---

## 🔧 Debug

| 問題 | 檢查 |
|------|------|
| Agent 連唔到 server | `curl http://localhost:5000/` |
| Deploy 唔生效 | `curl "http://localhost:5000/api/agent-poll-deploy?agent_id=DEV00001"` |
| Socket.IO 斷線 | Agent log 有 `🔴 Disconnected` |
| MT5 冇新 trade | 確認 symbol 可交易 (`trade_mode=3`) |
| Port 5000 佔用 | `python -c "import psutil; [p.kill() for p in psutil.process_iter() if any(c.laddr.port==5000 for c in p.connections())]"` |

---

## 📁 目錄結構

```
mt5-cloud/
├── server/
│   ├── app.py              # Flask + Socket.IO server
│   ├── requirements.txt
│   ├── static/ea_library/  # 官方 30 EA (.mq5)
│   ├── static/user_ea/     # 用戶上傳 EA
│   └── templates/
│       ├── index.html
│       ├── login.html
│       ├── dashboard.html
│       └── register.html
├── agent/
│   ├── agent.py            # Windows Agent
│   └── install_agent.bat
├── wsgi.py                 # Render 入口
├── render.yaml             # Render Blueprint
└── README.md
```

---

## 🔐 預設帳號

| Username | Password | Agent ID |
|----------|----------|----------|
| dev | dev1234 | DEV00001 |

---

Built with ❤️ for algorithmic trading automation.
