# ☁️ MT5 Cloud

**MT5 Cloud** — 一個 SaaS 平台，幫你經 **Web Dashboard** 管理 MetaTrader 5 EA，自動下載、編譯、部署，唔使開 chart / drag EA。

---

## ✅ Current Status

| 功能 | 狀態 | 備註 |
|------|------|------|
| EA Upload + 配對庫 | ✅ 完成 | 支援 .mq5 / .ex5 |
| EA Download + Compile | ✅ 完成 | Agent 自動拉 + 編譯 |
| Deploy → MT5 API 落單 | ✅ 完成 | Market order (IOC) |
| Dashboard 分析 (Trades/Win/P&L) | ✅ 完成 | 即時 WebSocket sync |
| Correlation Matrix | ✅ 完成 | Per-magic+symbol P&L |
| Magic 選擇 | ✅ 完成 | 列舉所有用過嘅 magic |
| Symbol dropdown | ✅ 完成 | Broker correct 名 |
| 一鍵 Dev Login | ✅ 完成 | dev/dev1234 |
| Cloudflare Tunnel | ✅ 完成 | 免費，無 bandwidth limit |
| Render deploy support | ✅ 完成 | wsgi.py + render.yaml |
| Auto-install EA on connect | ✅ 完成 | 背景 thread 執行 |
| Deploy via Socket.IO | ✅ 完成 | 即時（非 polling） |
| Deploy via HTTP poll | ✅ 完成 | DB fallback |

---

## 🐛 Fixed Bugs & Issues

| 問題 | 原因 | Fix |
|------|------|-----|
| Symbol dropdown 揀嘢彈走 | auto-refresh rebuild 成個 table | → `_updateEAData()` 只改數字 cell |
| DAX40 用唔到 | Broker 叫 DE40，trade_mode=4 | → Symbol mapping `DAX40→DE40` |
| SP500 用唔到 | Broker 叫 US500，trade_mode=4 | → Symbol mapping `SP500→US500` |
| Agent deploy 唔識郁 | 1) eventlet crash 2) Socket.IO 阻塞 3) sync_loop hang | → threading + bg threads + cleaner loop |
| Port conflict | eventlet zombie process | → 用 threading mode |
| ngrok bandwidth exceeded | Free tier 1GB limit | → 轉 Cloudflare Tunnel（無 limit） |
| Socket.IO disconnect during install | install 阻塞 event loop | → 背景 thread install |
| Agent 連唔到 server | polling transport namespace bug | → 只行 WebSocket |

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

## 📦 完整 Deploy Flow

```
Dashboard 🚀 ──WebSocket──► Server ──DB deploy_queue──► Agent sync_loop (2s)
                                                              │
                                                              ▼
                                                    MT5 Python API
                                                    Market Order (IOC)
                                                    Magic + Comment
                                                              │
                                                              ▼
                                                    MT5 出現新 Position
                                                              │
                                                              ▼
                                                    Agent sync (10s)
                                                              │
                                                              ▼
                                                    Dashboard 分析更新
```

**唔需要開 chart、唔需要 drag EA、唔需要人手任何嘢。**

---

## 📡 Agent 機制

Agent 係一部 Windows 背景 process，做呢幾件事：

| 機制 | 方式 | 頻率 |
|------|------|------|
| 連線 Server | WebSocket | 長連接 |
| Deploy 指令 | HTTP poll (fallback) + Socket.IO | 每 2s |
| Sync MT5 數據 | Socket.IO emit | 每 10s |
| Install EA | 背景 thread | 連接時自動 |
| 落單 | MT5 Python API | 收到 deploy 指令時 |

Agent log 會顯示喺 terminal：
```
🟢 Connected
✅ Agent registered
📥 Bulk install: 9 EAs (background)
🚀 [POLL] Deploy: {ea_name, symbol, ...}
🖥️ MT5 已連接
💰 Account: 52781843
✅ → EURUSD H1 已啟動！
```

---

## 🌐 Symbol 對應

Web UI 用嘅名 vs Broker（IC Markets）實際名：

| UI 顯示 | MT5 名 | 可交易? | 備註 |
|---------|--------|---------|------|
| EURUSD | EURUSD | ✅ | |
| GBPUSD | GBPUSD | ✅ | |
| USDJPY | USDJPY | ✅ | |
| EURGBP | EURGBP | ✅ | |
| XAUUSD | XAUUSD | ✅ | |
| US30 | US30 | ⚠️ | close only（IC Markets Demo）|
| DAX40 | DE40 | ⚠️ | close only（IC Markets Demo）|
| SP500 | US500 | ⚠️ | close only（IC Markets Demo）|
| NAS100 | — | ❌ | 無此 symbol |

> Agent 自動 mapping：`DAX40→DE40`、`SP500→US500`。但 IC Markets Demo 限制 indices 只能 close only，**forex pairs 一切正常**。

---

## 🚢 部署選項

### Cloudflare Tunnel（免費，推薦）

```bash
curl -L -o cloudflared.exe https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe
cloudflared tunnel --url http://localhost:5000
```

⚠️ Quick Tunnel 每次 restart 出新 URL。想固定 URL 要用 Cloudflare account：
```bash
cloudflared tunnel login
cloudflared tunnel create mt5-cloud
cloudflared tunnel route dns mt5-cloud mt5.example.com
```

### Render（需 CC 驗證）

Push 去 GitHub → Render Dashboard → New Web Service → Connect repo

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
| Agent 連唔到 server | `curl http://localhost:5000/` 有 200? |
| Deploy 唔生效 | `curl "http://localhost:5000/api/agent-poll-deploy?agent_id=DEV00001"` 傳到? |
| Socket.IO 斷線 | Agent log 有 `🔴 Disconnected` |
| MT5 冇新 trade | Check `trade_mode=3`（both），`symbol_select(True)` |
| Port 5000 佔用 | `taskkill /F /PID $(netstat -ano | grep 5000 | awk '{print $5}')` |
| Agent log 冇 deploy output | sync_loop thread hang / error 未 flush |

---

## 📁 目錄結構

```
mt5-cloud/
├── server/
│   ├── app.py              # Flask + Socket.IO server（threading mode）
│   ├── requirements.txt
│   ├── static/
│   │   ├── ea_library/     # 官方 30 EA (.mq5)
│   │   └── user_ea/        # 用戶上傳 EA
│   └── templates/
│       ├── index.html      # Landing page
│       ├── login.html
│       ├── dashboard.html  # Main dashboard（EA table + analysis）
│       └── register.html
├── agent/
│   ├── agent.py            # Windows Agent（Socket.IO + MT5 API）
│   └── install_agent.bat
├── wsgi.py                 # Render entry point
├── render.yaml             # Render Blueprint
└── README.md
```

---

## 🔐 預設帳號

| Username | Password | Agent ID | MT5 Account |
|----------|----------|----------|-------------|
| dev | dev1234 | DEV00001 | IC Markets Demo 52781843 |

---

## ⚠️ Known Limitations

- **IC Markets Demo**：indices（US30/DE40/US500）只可以 close only，唔開得新單
- **Cloudflare Quick Tunnel**：每次 restart 出新 URL，要固定 URL 要用 cloudflared login
- **Free ngrok**：每月 1GB bandwidth limit，爆咗要等 reset
- **Agent sync_loop**：HTTP poll 去 localhost，如果 server 用 eventlet 可能 hang

---

Built with ❤️ for algorithmic trading automation.
Last updated: July 2026
