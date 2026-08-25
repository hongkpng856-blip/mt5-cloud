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