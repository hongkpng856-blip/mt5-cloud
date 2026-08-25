# 📋 Multi-User 改動計劃 —「每個人登錄控制自己部電腦嘅 MT5」

> 版本: v1.0（2026-08-26）— 用戶確認方向
> 目標: 由「單機單 MT5」變成「多用戶各自控制自己部機嘅 MT5」

---

## 1. 🎯 現況 vs 目標

### 而家（單機模式）
```
[雲端 Server (tunnel)] ←── 1 部電腦（你部機）
                          ├─ 1 個 MT5 terminal（5053721681）
                          ├─ deploy_watcher（本機 process）
                          ├─ auto_attach（GUI 操作 — 本機）
                          ├─ alert_worker（警告視窗 — 本機）
                          └─ agent.py（本機收集資料）
所有用戶登入 → 控制同一部機
```

### 目標（多機模式）
```
[雲端 Server (tunnel)]
 ├─ User A ←→ Agent A（A 部機）←→ A 嘅 MT5
 ├─ User B ←→ Agent B（B 部機）←→ B 嘅 MT5
 └─ User C ←→ Agent C（C 部機）←→ C 嘅 MT5
每個用戶：自己帳戶 → 自己 agent → 自己 MT5
```

---

## 2. ✅ 已有嘅 multi-user 基礎（唔使改）

| 組件 | 現況 |
|------|------|
| User model（username/password/bound_account）| ✅ 已有 |
| Agent model（user_id — 每 user 一個 agent）| ✅ 已有 |
| ea_config（每用戶獨立 EA 配對）| ✅ 已有 |
| deals/positions（每 agent 獨立）| ✅ 已有 |
| `/api/agent-download` + `/api/agent-py`（agent 分發）| ✅ 已有 |
| `/api/agent-poll-deploy`（agent 拉取部署指令）| ✅ 已有 |
| `/api/watcher-report`（watcher 上報）| ✅ 已有 |
| `/api/verify-mt5` + `/api/bind-account`（MT5 驗證）| ✅ 已有 |

---

## 3. 🔧 要改動嘅部分（按優先度）

### Phase 1 — Agent 上報分離（核心 — 每機獨立狀態）

**問題**：而家 server 直接讀**本機**檔案（hotkeys.ini / state_*.json / trades_*.json / Experts 目錄）— 但多機後每部機各自有呢啲檔。

**改動**：
| 檔案 | 改咩 |
|------|------|
| `agent/agent.py` | ①收集完本機資料（account/positions/deals/EA inventory）→ **帶 agent_id 上報**（已有 SERVER_URL）②加「心跳上報」loop（每 5-10 秒）③加「檔案同步」：state/trades/hotkeys 內容 upload 俾 server |
| `server/app.py` | ①`/api/watcher-report` 加 **agent_id 識別**（而家假設單機）②讀 EA 狀態改為「由 agent 上報嘅副本」（唔直接讀本機）③deploy 指令寫入「目標 user 嘅 agent」deploy_queue（已有 per-agent deploy_queue） |
| `agent/deploy_watcher.py` | ①poll 自己 user 嘅 deploy_queue（唔係單一）②執行完上報結果 (agent_id) |

**關鍵**：每部機嘅 agent/watcher 都要知自己屬於邊個 user（agent_id + token）— 安裝時綁定。

### Phase 2 — 部署指令轉發（唔再「本機直接執行」）

**問題**：而家 `api_deploy` 直接 `mt5.initialize()` + 寫本機 hotkeys.ini + 叫本機 watcher。

**改動**：
| 檔案 | 改咩 |
|------|------|
| `server/app.py` `api_deploy` | 唔好直接操作本機 — **寫入 `Agent.deploy_queue`**（agent_id 對應嗰個 user）→ 等佢部機嘅 watcher 拉走執行 |
| `agent/auto_attach.py` | 唔改（已經係本機 GUI 操作 — 每部機都有自己嘅 copy） |
| `agent/deploy_watcher.py` | poll 自己 deploy_queue → spawn auto_attach（本機）→ 上報結果 |

**即係**：server 變成「指令路由」— 每條指令帶 user_id → 路由去嗰個 user 部機執行。

### Phase 3 — 狀態/統計資料路由

**問題**：`/api/ea-config` / `/api/analysis` / `/api/trade-report` 讀本機檔案 + `agent.deals`。

**改動**：
| API | 改咩 |
|-----|------|
| `ea-config` | ea_stats 改讀「該 user agent 上報嘅 trades/state 副本」（每 agent 獨立） |
| `analysis` / `trade-report` | deals 已係 per-agent ✅ — 讀自己 agent 嘅 deals（已做） — 但 trades_*.json 檔案要改為「agent 上報」 |
| `refresh-status` | hotkeys/state 由 agent 上報副本讀（唔直接本機） |

**簡化建議**：Agent 表加一欄 `files_snapshot`（JSON — 每 10 秒上報 state/trades/hotkeys 內容）→ server 讀呢個 snapshot 做顯示。

### Phase 4 — 帳號安全（登入 → 唯一 access 到自己）

| 改動 | 內容 |
|------|------|
| **移除 Quick Dev Access**（或者 localhost 先顯示）| dev 後門唔可以出街 |
| **MT5 綁定變硬** | 登入必須填 MT5 account + 同「該用戶 agent 上報嘅 login」一致先放行（cache 未 ready → 唔係照入 — 顯示「agent 未連接」） |
| **Agent token** | 每 agent 安裝時生成 secret token — server 確認上報係「正牌 agent」（防偽造） |
| **Rate limit** | 登入失敗 5 次鎖 15 分鐘 |
| **Session 過期** | 30 分鐘 idle 登出 |

### Phase 5 — 客戶部機安裝套件

**每用戶部機要裝**（`install_agent.bat` — 已有）：
```
1. Python 3.11（含 pywinauto / MetaTrader5 / requests）
2. MT5 terminal（佢自己登入自己帳號）
3. agent 套件（由 /api/agent-download 下載）：
   ├─ agent.py（收集上報）
   ├─ deploy_watcher.py（poll + 執行）
   ├─ auto_attach.py（GUI 操作）
   ├─ alert_worker.py（警告視窗）
   └─ watchdog.py（自癒 — 開機自啟）
4. 安裝時填：server URL + username + agent token（綁定）
```

---

## 4. 📐 新架構圖

```
┌─────────── 雲端 Server（Tradotcom）───────────┐
│  Flask + DB                                     │
│  ├─ User A ──ea_config──┐                       │
│  ├─ User B ──ea_config──┤                       │
│  └─ User C ──ea_config  │                       │
│                         ↓                       │
│  Agent A（A 部機）←──[deploy_queue + token]─── │
│  Agent B（B 部機）                              │
│  Agent C（C 部機）                              │
│     ↑ 10 秒心跳上報（account/state/trades）     │
└────────────────────────────────────────────────┘
```

## 5. ⏱️ 實行順序（建議）

| 階段 | 內容 | 驗收 |
|------|------|------|
| **P1** | Agent 上報分離（agent 帶自己 agent_id + files_snapshot 上報）| 兩個 agent 各自上報 — server 分得開 |
| **P2** | 部署指令路由（server 寫 deploy_queue → 各機 watcher 執行）| A 機部署唔影響 B 機 |
| **P3** | 狀態顯示路由（ea-config/analysis 讀 per-agent snapshot）| 各用戶睇到自己部機 EA |
| **P4** | 安全（移除 dev 後門 + token + rate limit + session）| 冇後門 + 綁定硬驗證 |
| **P5** | 客戶安裝套件測試（第二部機完整流程）| 兩部機各自部署成功 |

## 6. ⚠️ 要注意嘅坑

1. **hotkeys.ini 係本機嘢** — 每部機各自有自己 hotkeys — 唔可以「server 統一管理」，要「agent 上報 + 每機自己寫」
2. **auto_attach GUI 操作**（Alt+F/Ctrl+W/熱鍵）全部係本機 pywinauto — **每部機都要裝**（Windows 限定）
3. **tunnel**：而家單一 tunnel 指去本機 — 多機後 server 行雲端（或某部機）— 客戶機只做「agent 執行」
4. **DB**：User.ea_config / Agent.deploy_queue 已 per-user — 唔使改 schema（最多加 agent token 欄）
5. **權限**：User 唔可以睇到其他人嘅 EA（而家 query 已 filter user_id ✅）

## 7. 📂 檔案改動清單（總結）

| 檔案 | 改動 |
|------|------|
| `server/app.py` | deploy 路由去 agent_id / 讀 agent snapshot / token 驗證 / 安全（P4）|
| `server/models.py`（或 app.py）| Agent 加 `token` / `files_snapshot` 欄 |
| `agent/agent.py` | 心跳上報 + snapshot 上報（agent_id 帶住）|
| `agent/deploy_watcher.py` | poll 自己 deploy_queue + 上報帶 agent_id |
| `agent/install_agent.bat` | 安裝時填 server URL + username + token |
| `server/templates/login.html` | 移除 dev 後門 / 綁定硬驗證 |
| `server/templates/dashboard.html` | 顯示「自己部機」資料（已經係 per-user — 大體唔變）|

---

*準備好可以開始 Phase 1 — 要開始就話我知*


---

## 8. ☁️ 雲端部署建議（正式版 — Server 上雲）

> 用戶問題：「點解用我部機做終端？唔係應該有 server/database 咩？」
> 解答：交易一定要喺實體機（MT5 桌面 App 冇得喺雲端虛擬跑），但 Server/DB 可以（亦應該）上雲。
> 你部機 = 開發模式（server + 第一個終端二合一）；正式版 = server 上雲 + 你部機淨做終端。

### 8.1 正式架構（雲端）

```
┌─────── 雲端 VPS（24/7 online）────────┐
│  • Tradotcom Server（Flask + SocketIO） │
│  • Database（SQLite → 可升 PostgreSQL） │
│  • Cloudflare Tunnel（或固定 IP + SSL） │
│  = 腦（決策/網頁/帳戶/DB）              │
└───────────────┬───────────────────────┘
                │ HTTPS（tunnel / 域名）
┌───────────────┼───────────────────────┐
│ 客戶 A 部機    │   客戶 B 部機           │
│  ├ MT5 Terminal│  ├ MT5 Terminal        │
│  ├ Agent       │  ├ Agent               │
│  └ Watcher     │  └ Watcher             │
│  = 手腳        │  = 手腳                │
└───────────────┴───────────────────────┘
```

### 8.2 VPS 揀咩（行內人建議）

| 方案 | 適合 | 成本 |
|------|------|------|
| **最低（起步）** | 2 vCPU / 2GB RAM / 40GB SSD — 5-10 用戶 | ~HK$60-100/月 |
| **標準（推薦）** | 2 vCPU / 4GB RAM / 80GB SSD — 20-50 用戶 | ~HK$150-250/月 |
| **進階** | 4 vCPU / 8GB RAM + PostgreSQL — 50+ 用戶 | ~HK$400+/月 |

**供應商**：DigitalOcean / Vultr / Linode / AWS Lightsail / 阿里雲 / 騰訊雲（香港節點 — 延遲低）
**OS**：Ubuntu 22.04 LTS（或 Windows Server — 如果想保留 Windows 環境）

### 8.3 Server 部署步驟（VPS）

```
1. VPS 裝 Python 3.11 + git
2. git clone mt5-cloud（server 部分 — server/ + instance/）
3. pip install -r requirements.txt
4. 環境變數：PORT / SECRET_KEY / DB 路徑
5. 啟動：systemd service（自動重啟）+ 開機自啟
6. Cloudflare Tunnel（或 Nginx + Let's Encrypt SSL）
7. 域名指向（tradotcom.com 或子域）
```

### 8.4 數據庫升級

| 而家 | 正式版 |
|------|--------|
| SQLite（單檔 — 單機 OK） | **PostgreSQL 14+**（多人並發 — 建議）|
| 或者繼續 SQLite（20 用戶內都 OK — 唔使急）| 但要 backup 排程（每日 dump）|

**簡化建議**：起步可以照用 SQLite（用戶少）→ 用戶多先遷移 PostgreSQL。

### 8.5 客戶機（終端）要求

| 項目 | 要求 |
|------|------|
| OS | **Windows 10/11**（MT5 + pywinauto GUI 操作需要）|
| 軟件 | MT5 terminal（客戶自己登入自己帳戶）|
| Python | 3.11 + pywinauto / MetaTrader5 / requests |
| Agent 套件 | 由平台 `/api/agent-download` 下載安裝 |
| 開機自啟 | watchdog.py（自癒 + 重啟）|
| 網絡 | 能 reach 平台 server（HTTPS — tunnel 冇問題）|

### 8.6 你部機嘅角色（遷移後）

```
而家（開發模式）：你部機 = server + agent + MT5 全部
正式版之後：      你部機 = 淨做「agent 終端」+ 你自己嘅 MT5
                 （server 搬上 VPS — 你部機唔使 24/7 開住做 server）
```

**遷移步驟（唔使好急）**：
1. 先用而家 code 將 server 部署上 VPS（照跑單機 mode — 但你部機 agent 連過去）
2. Phase 1-2 完成後（agent 上報分離）→ 你部機正式變「終端」
3. 第三部機（用戶 B）加入 → 驗證多用戶

### 8.7 安全（雲端版必做）

| 項目 | 做法 |
|------|------|
| HTTPS | Cloudflare Tunnel 自動（免費 SSL）或 Nginx + certbot |
| 登入 | Rate limit + 密碼強度 + 可選 2FA（Phase 4）|
| Agent token | 每 agent 安裝時生成 — server 驗證來源 |
| DB backup | 每日自動 dump（cron）|
| 防火牆 | VPS 只開 80/443 + SSH（限定 IP）|

---

*雲端部署可以喺 Phase 1-2 完成後隨時開始（server 照跑單機 mode 上雲 — agent 分離前都 work）*
