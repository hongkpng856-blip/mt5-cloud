# 📊 MODULES.md — 改動影響分析流程

> **用途**：每次改動之前，用呢份矩陣自動檢查「改咗 X 會牽涉邊啲地方」。
> **兩層**：本文件（項目內參考）+ 永久 skill（`mt5-impact-analysis`，每個 session 自動載入）。
> 詳細檔案位置：`MODULE_INDEX.md`（功能模組分類）。

---

## 影響分析流程（IMPACT ANALYSIS FLOW）

### Step 0 — 收到改動要求
先問自己：
1. 呢個改動屬於邊個模組？（睇 MODULE_INDEX.md）
2. 係「新增」、「修改」定「刪除」？
3. 影響範圍係：前端 UI？API？後台邏輯？GUI 自動化？DB？

### Step 1 — 對照影響矩陣（下面）
用「改動目標 → 牽涉位置」搵出所有要一齊改嘅檔案。

### Step 2 — 檢查依賴鏈
```
前端 JS → API endpoint → server 邏輯 → DB / 檔案系統
                          ↓
                    deploy_watcher / detector（獨立進程）
                          ↓
                    GUI 自動化（auto_attach / refresh_navigator）
```

### Step 3 — 改完之後
1. 重啟相關進程（`bash agent/restart_all.sh`）
2. 瀏覽器硬 refresh（Ctrl+Shift+R）
3. 實測 E2E（唔可以淨係話成功）
4. 更新 PROGRESS.md + MODULE_INDEX.md

---

## 🎯 影響矩陣（改動目標 → 牽涉位置）

### A. 改「時間」相關（timeframe / 間隔 / 週期）

| 改動目標 | 牽涉位置 | 要唔要一齊改 |
|----------|---------|-------------|
| Detector 信號刷新間隔（30s） | `agent/auto_trade_detector.py` `loop()` `time.sleep(30)` | ✅ 要 — 改間隔同時考慮 static JSON 寫入頻率 |
| Dashboard 拉取間隔（5s） | `dashboard.html` `setInterval(loadDashboard, 5000)` | ✅ 要 — 同 detector 間隔匹配，太密會塞爆 |
| EA Inventory 刷新（30s） | `dashboard.html` `setInterval(fetchEAInventory, 30000)` | ✅ 要 — 同 detector 寫 JSON 頻率一致 |
| Watcher polling（3s） | `agent/deploy_watcher.py` `POLL_INTERVAL = 3` | ✅ 要 — 部署反應時間 |
| Navigator refresh cooldown（3s） | `agent/deploy_watcher.py` `_refresh_cooldown = 3` | ✅ 要 — 太短會連環 refresh |
| Heartbeat 檢測 timeout（60s） | `agent/auto_attach.py` `verify_heartbeat(timeout=60)` | ✅ 要 — 配合 agent heartbeat 寫入頻率 |
| Agent heartbeat 寫入頻率 | `agent/agent.py`（heartbeat file 寫入 loop） | ✅ 要 — 同 dashboard 檢測一致 |
| auto_attach timeout（5min） | `agent/deploy_watcher.py` `TimeoutExpired (5 min)` | ⚠️ 檢查 — 太短 attach 未完成就 fail |
| MT5 log 讀取「最近 3 個」 | `agent/auto_trade_detector.py` `log_files[:3]` | ⚠️ 檢查 — 跨午夜 bug 修復（Bug #43） |

### B. 改「EA 配置」相關（config / 配對庫）

| 改動目標 | 牽涉位置 | 要唔要一齊改 |
|----------|---------|-------------|
| ea_config 格式（加欄位） | `server/app.py` `/api/ea-config`（L167）+ `dashboard.html` loadEAConfig JS（~L697）+ `agent/auto_trade_detector.py` 讀 config | ✅ 要 — 三處都讀同一個 JSON |
| 預設 lot size（1.00） | `dashboard.html` `defaultLot` + `eaMappings['_default_lot']` | ✅ 要 — 前端 input + 後端 default |
| Magic number 邏輯 | `dashboard.html` magic select + `auto_attach.py` `--magic` | ✅ 要 — 兩處一致 |
| 暫停/繼續 EA（_status） | `server/app.py` `/api/ea-config/<name>/toggle` + `dashboard.html` toggleEA JS + `agent/auto_trade_detector.py` 檢查 `_status != 'running'` | ✅ 要 — detector 要識別 PAUSED |
| 剷除 EA | `server/app.py` remove-local endpoint（L667）+ `dashboard.html` deleteEA JS + watcher 目錄監控 | ✅ 要 — 三層一致（檔案+config+refresh） |

### C. 改「API」相關

| 改動目標 | 牽涉位置 | 要唔要一齊改 |
|----------|---------|-------------|
| 加新 endpoint | `server/app.py` + `dashboard.html` 前端 fetch + （如果需要）`deploy_watcher.py` / `auto_trade_detector.py` | ✅ 要 |
| 改 login 流程 | `server/app.py` L105 + `login.html` JS（verify-mt5 → login）+ User model | ✅ 要 — 前端兩步流程 |
| 改 account 綁定 | `server/app.py` L874 bind-account + `dashboard.html` bindingStatus JS | ✅ 要 |
| 改 deploy 流程 | `server/app.py` L833 /api/deploy + `dashboard.html` deployEA JS + `deploy_watcher.py` + `auto_attach.py` | ✅ 要 — 全鏈路 |

### D. 改「MT5 狀態顯示」相關（運行中/停止中/信號）

| 改動目標 | 牽涉位置 | 要唔要一齊改 |
|----------|---------|-------------|
| 信號計算邏輯（SMA 參數） | `agent/auto_trade_detector.py` compute_signals | ⚠️ 檢查 — 只影響 detector |
| 信號顯示格式 | `dashboard.html` getSignalHtml JS | ✅ 要 — 同 detector 返回嘅 signal 值一致（BUY/SELL/WAIT/PAUSED） |
| 運行中/停止中狀態 | `agent/auto_trade_detector.py` scan_ea_inventory（log 讀取）+ `dashboard.html` eaDeployStatus | ✅ 要 — 狀態來源係 detector |
| 排序邏輯（運行中喺上） | `dashboard.html` loadEAConfig sort | ⚠️ 檢查 — 前端 only |

### E. 改「UI / 前端」相關

| 改動目標 | 牽涉位置 | 要唔要一齊改 |
|----------|---------|-------------|
| 任何 UI 製作/修改 | **一律用 `shadcn` skill**（先 load）+ `references/flask-jinja2-adaptation.md` | ✅ 要 — zinc+emerald tokens + `icon-` prefix + 0 emoji；tkinter 視窗同配色 |
| 加 UI 欄位 | `dashboard.html` table header + row rendering + （如有）data source | ✅ 要 — header 同 body 同步 |
| 加新 card/tab | `dashboard.html` + 相關 JS function | ⚠️ 檢查 — 用戶偏好：**擴展現有 list，唔加新 cards** |
| 改 Lucide icons | `dashboard.html` 所有 `<i class="icon-*">` | ✅ 要 — **`icon-` prefix 唔係 `lucide-`** |
| 改顏色/主題 | `dashboard.html` CSS variables（--bg, --card, --accent 等） | ⚠️ 檢查 — design tokens 集中喺 `<style>` 開頭 |

### F. 改「系統架構 / 進程」相關

| 改動目標 | 牽涉位置 | 要唔要一齊改 |
|----------|---------|-------------|
| 改 server port | `server/app.py` PORT + `restart_all.sh` + `deploy_watcher.py` SERVER_URL + `agent/agent.py` SERVER_URL | ✅ 要 — 四處一致 |
| 改 detector port | `agent/auto_trade_detector.py` 5003 + `dashboard.html` static path（唔係 port！）+ `restart_all.sh` | ⚠️ 檢查 — 前端用 static JSON 唔用 port |
| 加新 sidecar 進程 | 新 .py + `restart_all.sh` + 單實例守衛 + static JSON bridge（如有） | ✅ 要 |
| 改 DB schema | `server/app.py` model + migration SQL + 所有讀嗰個 column 嘅地方 | ✅ 要 |

### G. 改「部署 / GUI 自動化」相關

| 改動目標 | 牽涉位置 | 要唔要一齊改 |
|----------|---------|-------------|
| auto_attach 流程 | `agent/auto_attach.py`（634 行）+ `deploy_watcher.py` 調用 | ✅ 要 |
| Navigator refresh 方法 | `agent/refresh_navigator.py` + `deploy_watcher.py` check_experts_changes | ✅ 要 — 方法改咗要 E2E 驗證 |
| GUI automation 座標 | `auto_attach.py` / `refresh_navigator.py` pyautogui 座標 | ⚠️ 檢查 — 每部機屏幕唔同，用 tree.rectangle() 攞動態座標 |

---

## ⚠️ 常犯錯誤（bugs 累積）

1. **改咗 app.py 但 server 冇重啟** — Hermes 會 respawn 舊 code，一定要 `restart_all.sh`
2. **改咗前端但冇硬 refresh** — 瀏覽器 cache，要 Ctrl+Shift+R
3. **改咗 detector 但 static JSON 未更新** — detector 每 30 秒先寫一次，測試要等
4. **改咗 API 但前端仲 fetch localhost:5003** — 一定要用 `/static/detector/xxx.json`（Bug #44）
5. **改咗 Navigator refresh 方法** — 只有「右鍵→刷新」work（Bug #46），其他全部失敗
6. **改咗 server 但冇單實例守衛** — 多個 server 搶 port，新 endpoint 404（Bug #44）
7. **改咗 lot size 但冇改 default** — 用戶要 1.00 唔係 0.01
8. **改咗 icon 但用錯 prefix** — `icon-` 唔係 `lucide-`
9. **改咗 EA 配置格式但 detector 未同步** — detector 直接讀 DB，格式要一致
10. **改咗時間間隔但冇考慮 cooldown** — 連環觸發會令 MT5 被 GUI 操作騷擾

---

## ✅ 完成 checklist（每次改動後）

- [ ] 影響矩陣對照過（涉及嘅檔案全部改晒）
- [ ] `bash agent/restart_all.sh` 重啟（如改咗 server/detector/watcher）
- [ ] 瀏覽器 Ctrl+Shift+R 硬 refresh
- [ ] 實際 E2E 驗證（新增/刪除 EA、login、deploy）
- [ ] 更新 PROGRESS.md（bugs + changelog）
- [ ] 更新 MODULE_INDEX.md（涉及嘅分類）
