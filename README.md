# ☁️ MT5 Cloud

**MT5 Cloud** — 一個 SaaS 平台，幫你經 **Web Dashboard** 管理 MetaTrader 5 EA，自動下載、編譯、部署，唔使開 chart / drag EA。

---

## ✅ Current Status

| 功能 | 狀態 | 備註 |
|------|------|------|
| EA Upload + 配對庫 | ✅ 完成 | 支援 .mq5 / .ex5 |
| EA Download + Compile | ✅ 完成 | Agent 自動拉 + metaeditor64 編譯 |
| Heartbeat injection | ✅ 完成 | OnInit + OnTick 寫 heartbeat file |
| Deploy via Socket.IO | ✅ 完成 | 即時（非 polling） |
| Deploy via HTTP poll | ✅ 完成 | DB fallback |
| Auto-install EA on connect | ✅ 完成 | 背景 thread 執行 |
| Dashboard 分析 (Trades/Win/P&L) | ✅ 完成 | 即時 WebSocket sync |
| Correlation Matrix | ✅ 完成 | Per-magic+symbol P&L |
| Magic 選擇 | ✅ 完成 | 列舉所有用過嘅 magic |
| Symbol dropdown | ✅ 完成 | Broker correct 名 |
| 一鍵 Dev Login | ✅ 完成 | dev/dev1234 |
| Cloudflare Tunnel | ✅ 完成 | 免費，無 bandwidth limit |
| Render deploy support | ✅ 完成 | wsgi.py + render.yaml |
| **Navigator auto-attach EA** | 🔧 進行中 | 手動測試成功 ✅，Agent 自動化未通過 ❌ |
| **Dashboard Alive 🟢🔴 指示** | ⏳ 未開始 | Heartbeat tracking 已完成，前端未嵌入 |
| **已有 EA chart 替換 dialog** | ⏳ 未開始 | 目前假設 chart 冇 EA |

---

## 🔧 Navigator Auto-Attach（核心難題）

### 已驗證嘅成功流程（手動）

```
1. 唔開新 chart（如果已有 chart 就直接用）
2. AHK nav_on.ahk → 開 Navigator panel
3. pywinauto children[2] → 選擇 EA交易 節點（locale-independent）
4. select(ea_node) + ensure_visible(ea_node) → EA 滾到 TreeView 最頂
5. pyautogui.doubleClick(tv_rect.left+50, tv_rect.top+9) → 彈出 EA Properties dialog
6. send_keys('{ENTER}') → 確認 dialog
7. send_keys('^e') → AutoTrading ON
8. 確認 heartbeat file mtime 更新 → 🟢
```

### 關鍵發現

| 發現 | 詳情 |
|------|------|
| `select() + ensure_visible()` 後 EA 喺 TreeView 最頂 | double-click `tv_rect.top + 9` 就中，唔使逐行掃描 |
| `select() + Enter` 唔等同 double-click | Enter 只 expand/collapse 節點，唔觸發 attach |
| 開新 chart (Ctrl+N) 會自動收埋 Navigator | 必須開 chart 後再開 Navigator |
| MT5 Navigator 語言因 locale 而異 | 我哋嘅 MT5 係阿拉伯文：`المستشارون المختصون`。用 `children[2]` 位置索引唔靠文字匹配 |
| Navigator TreeView `visible=False` 時所有 click 方法都唔 work | 必須先確認 Navigator panel 可見 |
| `uia` backend 搵唔到 MT5 TreeView | 必須用 `win32` backend |
| ctypes 64-bit hwnd overflow | callback 用 `c_size_t`，Win32 API 呼叫時要 `c_void_p(hwnd)` cast |
| AHK `ControlTreeView` 對 MT5 卡住 | MT5 custom TreeView 唔支援 AHK ControlTreeView 操作 |

### Agent 自動化目前失敗嘅原因

1. **AHK nav_on.ahk 坐標唔穩定** — 用 `wx+120, wy+28` 點擊 View menu，但 MT5 重啟後 window position 會變，坐標可能唔啱
2. **開新 chart 後 Navigator 收埋** — Agent 每次先開 chart 再開 Navigator，但 Navigator toggle 唔可靠
3. **MT5 可能被 Agent 不斷重啟** — 失敗後 Agent 會 taskkill MT5 重試，導致 chart 丟失

### 所有試過嘅 double-click 方法（~250 次嘗試）

| 方法 | 結果 | 原因 |
|------|------|------|
| `select() + Enter` | ❌ | Enter 只 expand/collapse |
| `ClickInput(double=True)` | ❌ | pywinauto 唔觸發 MT5 TreeView |
| 右鍵 + 選單鍵盤操作 | ❌ | 太多步驟，唔可靠 |
| `WM_LBUTTONDBLCLK` SendMessage | ❌ | 坐標落到 chart 區域 |
| pyautogui 逐行掃描 | ✅（手動） | 成功但慢（~60s），Agent 自動化時 Navigator 收埋 |
| AHK `ControlTreeView DoubleClick` | ❌ | MT5 custom TreeView 唔支援 |
| AHK `ControlClick` 掃描 | ❌ | 坐標計算錯誤，click 到 Market Watch |
| AutoIt `control_tree_view` | ❌ | 搵唔到 SysTreeView32 control |
| `TVM_GETITEMRECT` + WriteProcessMemory | ❌ | Python 進程冇 SeDebugPrivilege |
| **pyautogui.doubleClick(tv_rect.top+9)** | ✅（手動） | select+ensure_visible 後 EA 喺最頂，一次 click 就中 |

---

## 🐛 Fixed Bugs & Issues

| # | 問題 | 原因 | Fix | Commit |
|---|------|------|-----|--------|
| 1 | Symbol dropdown 揀嘢彈走 | auto-refresh rebuild 成個 table | `_updateEAData()` 只改數字 cell | — |
| 2 | DAX40 用唔到 | Broker 叫 DE40，trade_mode=4 | Symbol mapping `DAX40→DE40` | — |
| 3 | SP500 用唔到 | Broker 叫 US500，trade_mode=4 | Symbol mapping `SP500→US500` | — |
| 4 | Agent deploy 唔識郁 | eventlet crash + Socket.IO 阻塞 + sync_loop hang | threading + bg threads + cleaner loop | — |
| 5 | Port conflict | eventlet zombie process | 用 threading mode | — |
| 6 | ngrok bandwidth exceeded | Free tier 1GB limit | 轉 Cloudflare Tunnel（無 limit） | — |
| 7 | Socket.IO disconnect during install | install 阻塞 event loop | 背景 thread install | — |
| 8 | Agent 連唔到 server | polling transport namespace bug | 只行 WebSocket | — |
| 9 | retcode=10027 = 交易失敗 | `CLIENT_DISABLES_AT` = AutoTrading OFF | 改用 auto-attach，唔用 order_send | `4ade117` |
| 10 | 儲存配對按鈕多餘 | 同 Deploy 功能重疊 | 合併入 Deploy 按鈕 | `4ade117` |
| 11 | 一鍵加入配對要手動 save | 用戶期望即時生效 | `addEAToPairing()` 自動 save | `4ade117` |
| 12 | heartbeat file 唔存在 | EA source 冇 FileWrite heartbeat | 注入 OnInit + OnTick heartbeat code | `893b4ca` |
| 13 | metaeditor64 compile 失敗 | `/s` 參數錯誤 | 改用 `/log:` 參數（MT5 必需） | `893b4ca` |
| 14 | heartbeat file 編碼錯誤 | UTF-8 write | 改用 UTF-16 LE（MT5 標準） | — |
| 15 | `'EA交易' not found` | MT5 語言因 locale 而異 | `children[2]` 位置索引 | `c6e1ba7` |
| 16 | `name 'subprocess' not defined` | AHK 調用需要 subprocess | 加入 `import subprocess` | `23fa257` |
| 17 | `name 'threading' not defined` | 被誤刪 | 還原 `import threading` | — |
| 18 | ctypes `OverflowError: int too long` | 64-bit hwnd 喺 WINFUNCTYPE callback overflow | callback 用 `c_size_t`，API 呼叫用 `c_void_p(hwnd)` cast | `6c6290b` |
| 19 | `EnsureVisible()` deprecation | pywinauto 新版 API | 改用 `ensure_visible()` | `a6f669e` |
| 20 | AHK `Loop % var` syntax error | AHK v2 唔用 `%` 做 expression | 改用 `rowCount := ... ; Loop rowCount` | — |
| 21 | Navigator TreeView `visible=False` | 開新 chart 自動收埋 Navigator | 先開 chart，再開 Navigator | `7a67334` |
| 22 | pyautogui 掃描太慢（~60s） | 逐行掃描成個 TreeView | `select()+ensure_visible()` 後 EA 喺最頂，一次 click | `c6e1ba7` |
| 23 | Agent auto-attach 仍失敗 | AHK nav_on.ahk 坐標唔穩定 + Navigator toggle 唔可靠 | **未解決** — 見下方 Open Bugs | — |

---

## 🐛 Open Bugs（下一位 Agent 需修復）

### Bug #1: Navigator 開啟唔可靠（Critical）

**現象**：Agent 嘅 `attach_ea_navigator()` 嘗試開 Navigator panel，但 AHK `nav_on.ahk` 用固定坐標 `(wx+120, wy+28)` 點擊 View menu，MT5 重啟後 window 位置改變，坐標唔啱。

**建議 Fix**：
- 方法 A：搵 MT5 toolbar 嘅 Navigator 按鈕（標準 toolbar 入面約第 5-7 個按鈕），用 `TB_GETRECT` 取坐標再 click
- 方法 B：用 `WinMenuSelectItem`（MT5 可能唔支援標準 menu）
- 方法 C：用 MT5 嘅 keyboard shortcut（如果有嘅話）

### Bug #2: 開新 chart 後 Navigator 自動收埋（Critical）

**現象**：Agent 每次 attach 都先開新 chart (`Ctrl+N`)，但開 chart 後 Navigator panel 自動關閉。之後 AHK/鍵盤 toggle Navigator 唔可靠。

**建議 Fix**：
- 唔開新 chart，直接用現有 chart（如果已有 open chart）
- 或者：先開 chart → 等 chart load 完 → 再開 Navigator → 等 Navigator load 完 → 再 double-click
- 加更長嘅 sleep wait 時間

### Bug #3: Agent 失敗後不斷重啟 MT5（High）

**現象**：Agent attach 失敗 3 次後會 `taskkill` MT5 重啟，但重啟後 chart 丟失，heartbeat 亦消失。下一個 EA attach 亦會失敗，形成惡性循環。

**建議 Fix**：
- 失敗後唔重啟 MT5，改為只 skip 呢個 EA
- 重啟後要等 MT5 完全 load 完（至少 10s）先操作
- 保持已 attach 嘅 EA chart，唔好因為新 EA attach 失敗而重啟

### Bug #4: pyautogui double-click 喺 Agent 自動化時可能唔觸發（Medium）

**現象**：手動測試 `pyautogui.doubleClick(tv_rect.top+9)` 成功，但 Agent 背景執行時可能因為 window focus / z-order 問題而 click 唔中。

**建議 Fix**：
- 確保 click 前用 `win.set_focus()` + `time.sleep(0.5)`
- 或改用 AHK `Click x y 2` 做更可靠嘅 mouse event

### Bug #5: ctypes `find_ea_dialog` 喺 fallback scan 時重新定義（Low）

**現象**：`find_ea_dialog()` 喺 Step 5 定義咗一次，喺 fallback scan 又定義咗一次（nested），可能導致混淆。

**建議 Fix**：將 `find_ea_dialog()` 提取到 function 層級，唔好嵌套喺 loop 入面。

---

## 📦 完整 Deploy Flow

```
Dashboard 🚀 ──WebSocket──► Server ──DB deploy_queue──► Agent sync_loop (2s)
                                                              │
                                                              ▼
                                                    Download .mq5 from server
                                                    Inject heartbeat code (OnInit + OnTick)
                                                    metaeditor64 /compile /log:xxx
                                                    Create .tpl template
                                                              │
                                                              ▼
                                                    Auto-Attach to chart (Navigator double-click)
                                                    Verify heartbeat file mtime
                                                              │
                                                              ▼
                                                    MT5 EA 運行中 🟢
                                                    Agent sync (10s) → Dashboard 更新
```

### Auto-Attach 詳細流程（agent.py L290 `attach_ea_navigator()`）

```
Step 0: 確認 MT5 PID + win32 connect
Step 1: 開新 chart (Ctrl+N → Enter)          ← Bug: 會收埋 Navigator
Step 2: 開 Navigator panel (AHK nav_on.ahk)   ← Bug: 坐標唔穩定
Step 3: 搵 SysTreeView32 + verify visible
Step 4: children[2] → EA交易 → expand → select EA → ensure_visible
Step 5: pyautogui.doubleClick(tv_rect.top+9)  ← ✅ 手動成功，Agent 未通過
Step 6: 確認 #32770 dialog → Enter
Step 7: AutoTrading ON (Ctrl+E)
Step 8: Heartbeat verify
```

---

## 🚀 快速開始

### 1. 部 Server

```bash
cd server
pip install -r requirements.txt
python app.py
```

Server 會行喺 `http://localhost:5002`（port 5000 有 zombie process 問題，改用 5002）

### 2. 開 Tunnel（可選）

外網存取 Dashboard：

```bash
# Cloudflare Tunnel（免費，唔使 CC）
cloudflared tunnel --url http://localhost:5002
```

### 3. 起 Agent

```bash
cd agent
python agent.py --server http://localhost:5002 --agent-id DEV00001
```

> Agent 同 Server 可以喺同一部機行，亦可以分開。
> Agent 需要喺 Windows 上行（MT5 + pywinauto + AHK v2）。

### 4. 開 Browser

去 `http://localhost:5002` 或 Cloudflare URL，用 `dev / dev1234` 登入。

---

## 📡 Agent 機制

Agent 係一部 Windows 背景 process，做呢幾件事：

| 機制 | 方式 | 頻率 |
|------|------|------|
| 連線 Server | WebSocket | 長連接 |
| Deploy 指令 | HTTP poll (fallback) + Socket.IO | 每 2s |
| Sync MT5 數據 | Socket.IO emit | 每 10s |
| Install EA | 背景 thread | 連接時自動 |
| Auto-Attach EA | Navigator double-click | 收到 deploy 指令時 |
| Heartbeat 監控 | Common/Files mtime check | 每 10s |

### 依賴

| 依賴 | 版本 | 用途 |
|------|------|------|
| MetaTrader5 (Python) | — | MT5 API（login, order_send, positions） |
| pywinauto | — | Win32 UI automation（Navigator tree 操作） |
| pyautogui | — | Mouse double-click（Treeview attach） |
| AutoHotkey v2 | `C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe` | Navigator panel toggle |
| socketio (client) | — | WebSocket 連線 server |

Agent log 範例：
```
✅ Connected to http://localhost:5002
🆔 Registered: {'status': 'ok'}
📥 Bulk install: 3 EAs (background)
📥 Installing EA: ADX_Trend.mq5
   💉 Heartbeat injected (OnInit + OnTick)
   💾 Saved: ...\MQL5\Experts\ADX_Trend.mq5
   ✅ Compiled: ADX_Trend.ex5 (9676 bytes)
🚀 Auto-Attach: ADX_Trend → EURUSD H1
🖱️ Double-clicking at TreeView top for ADX_Trend...
🎉 ADX_Trend Properties dialog found!
🟢 AutoTrading is ON
💓 Heartbeats: {'ADX_Trend': 'alive', 'ATR_Stop': 'alive', ...}
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
cloudflared tunnel --url http://localhost:5002
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
ngrok http 5002
```

---

## 🔧 Debug

| 問題 | 檢查 |
|------|------|
| Agent 連唔到 server | `curl http://localhost:5002/` 有 200? |
| Deploy 唔生效 | `curl "http://localhost:5002/api/agent-poll-deploy?agent_id=DEV00001"` 傳到? |
| Socket.IO 斷線 | Agent log 有 `🔴 Disconnected` |
| MT5 冇新 trade | Check `trade_mode=3`（both），`symbol_select(True)` |
| Heartbeat 冇更新 | Check `Common/Files/hb_<EA>.txt` mtime；AutoTrading ON? |
| Navigator 唔開 | `nav_on.ahk` 坐標唔啱？手動喺 MT5 撳 View→Navigator |
| Port 佔用 | `taskkill /F /PID <pid>`（唔好用 5000，用 5002） |
| Compile 失敗 | metaeditor64 exit code 1=成功；check /log: output |
| ctypes overflow | `c_void_p(hwnd)` cast 喺 callback 入面嘅 Win32 API call |

---

## 📁 目錄結構

```
mt5-cloud/
├── server/
│   ├── app.py              # Flask + Socket.IO server（threading mode, port 5002）
│   ├── requirements.txt
│   ├── instance/mt5cloud.db # SQLite DB
│   ├── static/
│   │   ├── ea_library/     # 官方 30 EA (.mq5)
│   │   └── user_ea/        # 用戶上傳 EA
│   └── templates/
│       ├── index.html      # Landing page
│       ├── login.html
│       ├── dashboard.html  # Main dashboard（EA table + analysis + deploy）
│       └── register.html
├── agent/
│   ├── agent.py            # Windows Agent（Socket.IO + MT5 API + auto-attach）
│   ├── auto_attach.py      # Standalone auto-attach 測試工具
│   ├── attach_ea.py        # Legacy attach tool
│   ├── agent_deploy.py     # Deploy sub-module
│   ├── build_agent.py      # Build tool
│   ├── nav_on.ahk          # AHK v2: Navigator panel toggle（menu click）
│   └── install_agent.bat   # Windows 安裝 bat
├── wsgi.py                 # Render entry point
├── render.yaml             # Render Blueprint
├── railway.toml            # Railway config
├── start_server.py         # Server 啟動 helper
├── restart_server.py       # Server 重啟 helper
└── README.md
```

---

## 🔐 預設帳號

| Username | Password | Agent ID | MT5 Account |
|----------|----------|----------|-------------|
| dev | dev1234 | DEV00001 | IC Markets Demo 52781843 |

---

## 🔑 關鍵路徑（下一位 Agent 必讀）

### MT5 路徑

| 路徑 | 用途 |
|------|------|
| `C:\Users\hongk\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075` | MT5 Terminal data |
| `...\MQL5\Experts\` | EA .mq5 / .ex5 存放位置 |
| `...\Profiles\Templates\` | .tpl chart 模板 |
| `...\Logs\` | MT5 log（UTF-16 LE） |
| `C:\Users\hongk\AppData\Roaming\MetaQuotes\Terminal\Common\Files` | Heartbeat files (`hb_<EA>.txt`) |

### AHK 路徑

```
C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe
```

### Server / Agent 啟動

```bash
# Server
cd ~/Desktop/mt5-cloud && python server/app.py          # port 5002

# Agent  
cd ~/Desktop/mt5-cloud && python agent/agent.py --server http://localhost:5002 --agent-id DEV00001

# Tunnel
cloudflared tunnel --url http://localhost:5002
```

### Git

```
Repo: hongkpng856-blip/mt5-cloud
Latest commit: 6c6290b 🔧 Fix ctypes 64-bit hwnd overflow
```

---

## ⚠️ Known Limitations

- **IC Markets Demo**：indices（US30/DE40/US500）只可以 close only，唔開得新單
- **Cloudflare Quick Tunnel**：每次 restart 出新 URL，要固定 URL 要用 cloudflared login
- **Agent auto-attach**：手動成功但 Agent 自動化未通過（Navigator toggle 唔可靠）
- **MT5 locale**：阿拉伯文介面，所有 UI automation 需用位置索引而非文字匹配
- **Port 5000 zombie**：歷史遺留，改用 port 5002
- **MT5 重啟後 chart 丟失**：Agent 失敗時重啟 MT5 會清走所有 chart

---

## 📋 TODO（優先順序）

1. **修復 Navigator toggle 唔可靠** — 找 MT5 toolbar Navigator 按鈕坐標，取代固定 menu 坐標
2. **修復開 chart 後 Navigator 收埋** — 改流程：唔開新 chart / 或者先 chart 後 Navigator + 更長 wait
3. **Agent 失敗後唔重啟 MT5** — 改為 skip + 繼續下一個 EA
4. **完整 E2E Dashboard 測試** — Deploy → auto_attach → heartbeat 🟢 → Dashboard 顯示
5. **Dashboard Alive 🟢🔴 嵌入 EA card** — 前端顯示
6. **處理已有 EA 嘅 chart** — 替換確認 dialog
7. **Cloudflare named tunnel** — 固定 URL
8. **清理臨時 helper 腳本** — start5001.py, start5002.py, kill_port.ps1 等

---

Built with ❤️ for algorithmic trading automation.
Last updated: 2026-07-29
