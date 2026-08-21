# 網頁部署 + 刪除 + MT5 人手刪除 — 完整流程

> 2026-08-21 用戶要求：詳細記錄
> 1. 網頁添加/部署、刪除流程（每一步做咩）
> 2. 電腦 MT5 人手刪除 EA 插件後，系統點反應

---

## 第一部分：網頁添加 EA → 配對 → 部署流程

### 階段 A：添加 EA 去 EA 倉庫（EA Library）

| 步驟 | 操作 | 系統做咩 | 驗證 |
|------|------|---------|------|
| A1 | 網頁「EA 管理」→ 上傳/添加 EA (.mq5) | 檔案存入 `server/static/ea_library/`（官方）或 `uploads/<user>/`（自訂） | 檔案存在 + 列表顯示 |
| A2 | （選）上傳社群庫 | 存入 `community/` | 列表顯示 |
| A3 | 自動 refresh EA 倉庫 | `/api/ea-library/refresh` 掃描所有目錄 | count 更新 |

### 階段 B：配對（安裝去本機 MT5）

| 步驟 | 操作 | 系統做咩 | 驗證 |
|------|------|---------|------|
| B1 | 網頁 EA 倉庫揀 EA → 「安裝到本機」 | `POST /api/ea-library/install-local/<name>` | - |
| B2 | 複製 .mq5 去 MT5 | `MQL5/Experts/<EA>.mq5`（Script → `MQL5/Scripts/`） | 檔案存在 |
| B3 | **心跳注入**（EA 類型） | 喺 .mq5 加 `__mt5c_process()`（1 秒心跳寫 `state_<EA>.json` + ctrl 指令檢查）+ `EventSetTimer(1)` + OnTimer 掛鉤 + OnTradeTransaction 掛鉤 | source code 含 `__mt5c_process` |
| B4 | 編譯 | MetaEditor CLI / watcher compile → `.ex5` | `compile_ok: True` |
| B5 | 配對記錄 | DB `ea_config[<EA>] = {symbol, tf, magic, lot}` + 快捷鍵分配 | config 有記錄 |
| B6 | 刷新 Navigator | watcher 自動 refresh（用戶唔使手動） | Navigator 見到 EA |

⚠️ **配對係「安裝 + 編譯 + 心跳注入」** — 唔等於部署（未掛 chart）。

### 階段 C：部署（掛 EA 落 MT5 chart）

| 步驟 | 操作 | 系統做咩 | 驗證 Gate |
|------|------|---------|-----------|
| C1 | 網頁配對庫揀 EA → 「部署」→ 揀 Symbol/Timeframe/Magic/Lot → 確認 | `POST /api/deploy`（防重複 30s） | - |
| C2 | **Symbol 驗證** | `get_account_symbols()` 檢查 symbol 喺帳戶 | symbol 存在（唔喺 → 400 警告） |
| C3 | 儲存 config | `ea_config[<EA>] = symbol/tf/magic/lot` | DB 更新 |
| C4 | 寫 deploy_cmd | `Common/Files/deploy_cmd_<EA>_<ts>.json`（watcher 偵測） | 檔案存在 |
| C5 | 寫 open_chart_cmd | `Common/Files/open_chart_cmd.json` `{symbol, tf}` | 檔案存在 |
| C6 | **AI 控制警告視窗** | 網頁 modal + MT5 tkinter alert（可緊急停止） | 視窗彈出 |
| C7 | **部署前 dialog 閘門** | `_ensure_no_dialog()` — 掃描所有 #32770 dialog → WM_CLOSE 清理 → 確認冇先繼續 | 冇 dialog |
| C8 | 熱鍵預載（如需） | 關 MT5 → 寫 hotkeys.ini → 開 MT5（熱鍵 load 測試 ×3） | 熱鍵 load |
| C9 | MT5 ready gate | poll 主視窗 ready（最多 90s） | window ready |
| C10 | **開 chart**（新方法） | `Alt+F → Enter → Enter → Space → symbol → Enter` | **EnumChildWindows 驗證 `<SYM>,H1` chart 存在** |
| C11 | **active chart 驗證** | EnumChildWindows Afx 窗口標題 | active chart = 目標 symbol（唔啱 → fail，唔附加） |
| C12 | **dialog 閘門 #2** | send 熱鍵前確認冇 dialog | 冇 dialog |
| C13 | 掛 EA（熱鍵） | send 熱鍵（Ctrl+N）→ Properties dialog 彈出 → BM_CLICK「確定」 | `_saw_props` |
| C14 | **代替 dialog 防護** | 如果彈「代替」dialog（目標 chart 已有 EA）→ **撳「否」+ 部署 fail**（唔接受取代） | 冇代替 |
| C15 | **部署後 dialog 閘門** | 心跳驗證前 `_ensure_no_dialog()` — Properties 殘留 → WM_CLOSE | 冇 dialog |
| C16 | 心跳驗證 | `state_<EA>.json` mtime 新鮮（<300s） | 心跳存在 |
| C17 | **log 驗證**（最終判定） | MT5 Terminal log `expert <EA> (<SYM>,H1) loaded successfully`（新鮮 <5min + 無隨後 removed） | log loaded |
| C18 | AutoTrading 確保 ON | Ctrl+E（已 ON 就 skip） | enabled |
| C19 | 圖表平鋪 + 收埋市場報價 | Alt+R + minimize | - |
| C20 | 寫 steps 全部 done + release 控制 | `ai_control.json active:false` | 網頁確定掣出現 |

**成功標準**（用戶定立）：MT5 log `loaded successfully` + 心跳新鮮 + 圖表實際掛住 — 三者齊先話成功。

---

## 第二部分：網頁刪除 EA（配對庫 → 刪除）

| 步驟 | 操作 | 系統做咩 | 驗證 |
|------|------|---------|------|
| D1 | 網頁配對庫揀 EA → 「刪除」 | `DELETE /api/ea-config/<EA>` | - |
| D2 | Controller 保護 | Controller 唔可以刪（403） | - |
| D3 | 確保 MT5 開 | `ensure_mt5_running()` | MT5 開住 |
| D4 | 寫 pause_cmd | `Common/Files/pause_cmd_<EA>_<ts>.json` `{ea_name, action: delete}` | 檔案存在 |
| D5 | watcher 偵測 | poll 3 秒 → 發現 pause_cmd | log 顯示 |
| D6 | **移除圖表 EA** | `auto_attach.py --remove --ea <EA>` → 開窗口 dialog（Alt+W）→ 列舉 chart → 揀目標 chart（MT5 log 最新 loaded）→ Enter → 確認移除 | log「removed」 |
| D7 | 刪除 config | `ea_config` 移除 <EA> 所有 key + 加 `_removed` | config 更新 |
| D8 | 釋放快捷鍵 | `release_hotkey(<EA>)` | hotkeys 釋放 |
| D9 | 刪除本機檔案 | 掃 `MQL5/Experts/<EA>.mq5/.ex5`（+ Scripts）→ 刪除 | 檔案移除 |
| D10 | Activity Log | 「<EA> 配對已刪除（圖表 EA 已排隊移除）」 | log 顯示 |

**刪除 = 完整移除**：本機 .mq5/.ex5 檔案 + DB config + 圖表 EA + 快捷鍵 — 唔可以淨係移 config。

---

## 第三部分：電腦 MT5 人手刪除 EA 插件（唔經網頁）

### 場景：用戶喺 MT5 手動移除 EA / 關 chart

| 時間 | 發生咩 | 系統偵測 | 網頁顯示 |
|------|--------|---------|---------|
| T+0 | 用戶喺 MT5 移除 EA（右鍵刪除 / 關 chart） | - | 仲顯示 running（心跳未停） |
| T+0~30s | EA 停止寫心跳（`state_<EA>.json` mtime 停） | server 心跳檢查（mtime <30s = running） | 心跳開始「老化」 |
| T+30s+ | 心跳停 >30 秒 | `runtime_status = unknown`（心跳暫停） | **「心跳暫停」**（黃色） |
| T+即刻 | MT5 log 寫 `removed` | server log 檢查（`_log_last` — terminal Logs） | **「chart_removed」**（優先 — 唔使等心跳停） |
| T+市場休市 | 心跳停 + 市場冇報價 | `market_closed`（symbol_info_tick 最後 tick >5min） | **「休市」**（灰色 — 正常） |

### 偵測機制（3 層）

```
1. 心跳檢查（每 30 秒）：state_<EA>.json mtime <30s = running
2. MT5 log 檢查：最後一條 `removed` = chart_removed（最優先）
   └─ 最後一條 `loaded successfully` = running（2026-08-21 修復 — 之前誤讀 MetaEditor 中文日誌）
3. 市場休市檢查：symbol_info_tick 最後 tick >5min = 休市（心跳停都唔當問題）
```

### ⚠️ 已知行為（測試確認）

1. **MT5 自動 restore chart**：手動關 chart 後，MT5 可能根據 profile **自動 load 返 chart + EA**（log `loaded successfully`）→ 心跳繼續 → 網頁仍顯示 running。呢個係 MT5 本身行為。
2. **多個同名 chart**（重複部署殘留）：窗口 dialog 有 3 個 UK100 時，剷除流程揀第一個可能**揀錯冇掛 EA 嗰個** →「15s 未確認移除」→ 假成功（watcher 照寫「已暫停」但實際冇移除）。→ **需要修：揀「最新 loaded 嗰個 chart」而唔係第一個同名**（TODO）。
3. **人手刪除 EA 之後再部署**：如果殘留 Properties dialog（之前部署冇關乾淨）→ 新部署開 chart 被 modal 擋 → 失敗。→ **已修：Dialog Gate（部署前/後檢查）**。

---

## 第四部分：狀態顯示一覽

| 狀態 | 顯示 | 條件 |
|------|------|------|
| running | 🟢 心跳運行 | 心跳新鮮（<30s）或 log loaded |
| chart_removed | ⚪ 圖表移除 | MT5 log 最後 removed |
| 心跳暫停 | 🟡 心跳暫停 | 心跳停 >30s + 市場開市 |
| 休市 | ⚪ 休市 | 心跳停 + 市場冇報價（週末/收市） |
| unpaired | ⚪ 未配對 | 冇 config / 冇心跳檔案 |

---

## 相關檔案

- `agent/auto_attach.py` — 部署/剷除核心（attach_ea_hotkey / auto_attach_ea / --remove）
- `agent/deploy_watcher.py` — deploy_cmd / pause_cmd 偵測 + spawn auto_attach
- `server/app.py` — /api/deploy / /api/ea-config DELETE / runtime_status / market_closed
- `docs/deployment-checkpoint-system.md` — 每步驗證 gate 概念
