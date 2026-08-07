# 📂 功能模組分類索引 (MODULE INDEX)

> **用途**：改嘢之前睇呢份文件，一次過知道「呢個分類涉及邊啲地方」— 唔使逐個檔案搵。
> **更新規則**：每完成一次改動，更新相關分類嘅「涉及檔案」+「注意事項」。

---

## 1️⃣ Web Server 核心 (Flask)

| 項目 | 位置 |
|------|------|
| 主程式 | `server/app.py` (951 行) |
| WSGI 入口 | `wsgi.py` / `start.sh` / `start_server.py` / `start5001.py` |
| 端口 | **5001**（`PORT` env） |
| 啟動方式 | `bash agent/restart_all.sh`（單實例模式） |
| **MT5 自動開啟** | `ensure_mt5_running()`（2026-08）— 所有 MT5 相關 API（install-local/deploy/toggle/remove-local/retry-compile）開頭偵測 MT5 → 冇就自動開返 + 等登入；**tasklist 查詢一定要 bytes 檢查（GBK 輸出 decode 會炸）** |

**關鍵 endpoints：**
- `/` → index.html (L78)
- `/dashboard` → dashboard.html (L84)
- `/register` (L89) / `/login` (L105) / `/logout` (L160)
- `/health` (L899) — 單實例守衛用
- `/api/dashboard` (L249) / `/api/analysis` (L366) / `/api/ea-report` (L462)

**注意事項：**
- ⚠️ **Hermes 會 respawn server** — 唔可以直接改 app.py 就當生效，要用 `restart_all.sh` 重啟
- ⚠️ **單實例守衛**（`if __name__ == '__main__'`）：已有 healthy server 就退出，唔會 duplicates
- ⚠️ **唔好用 SO_REUSEADDR bind** — Windows 會造成多個 server 搶 port（Bug #44）
- Flask dev server 唔支援 WebSocket upgrade → Socket.IO 要 `transports=['polling']`

---

## 2️⃣ 用戶認證 / Login / MT5 綁定

| 項目 | 位置 |
|------|------|
| Login 邏輯 | `server/app.py` L105-135（`login()`） |
| Register 邏輯 | `server/app.py` L89-104 |
| MT5 verify | `server/app.py` L904（`/api/verify-mt5`，cache-based） |
| 綁定 account | `server/app.py` L874（`/api/bind-account`） |
| User model | `server/app.py` L30-60（`bound_account` column） |
| Login 頁面 | `server/templates/login.html`（shadcn + Lucide） |
| 註冊頁面 | `server/templates/register.html` |
| 首頁 | `server/templates/index.html` |

**Login 流程：** username/password → `/api/verify-mt5`（比對 `_auto_trade_cache["account_info"]`）→ `/login`（mt5_account 匹配 bound_account 先成功）

**注意事項：**
- ⚠️ `mt5.login()` password 驗證喺 build 6061 唔 work（`(-2, Invalid params)` / `(-6, Authorization failed)`）— 只用 account number
- ⚠️ verify-mt5 用 **cache** 而唔直接 call MT5（singleton 衝突）
- ⚠️ DB migration：`bound_account` column 要 `ALTER TABLE`（`server/instance/mt5cloud.db`）
- login.html JS：先 call `/api/verify-mt5` 再 `/login`（兩步）

---

## 3️⃣ EA 倉庫（平台庫 / 社群庫 / 用戶庫）

| 項目 | 位置 |
|------|------|
| 列表 API | `server/app.py` L597（`/api/ea-library`） |
| 下載 | `server/app.py` L651（`/api/ea-library/<filename>`） |
| Dev 上傳 | `server/app.py` L626（`/api/ea-library/dev-upload`） |
| 用戶上傳 | `server/app.py` L743（`/api/ea-library/upload` — **自動安裝落本機 + 排 compile**） |
| **安裝落本機** | `server/app.py` L744（`/api/ea-library/install-local/<filename>` — 複製 .mq5 + 寫 config + 排 compile + **寫 web_add flag**） |
| **剷除本機檔案** | `server/app.py` L711（`/api/ea-library/remove-local/<filename>`，POST — **寫 web_delete flag + 網頁剷除 activity log**） |
| **重試 compile** | `server/app.py`（`/api/ea-library/retry-compile/<name>` — 手動重觸發 compile + double-check） |
| Compile 排隊 | server 寫 `compile_cmd_*.json` → watcher `process_compile_cmd()`（GUI compile + 失敗自動重試 3 次） |
| **來源分辨** | watcher `_notify_ea_change()` — 檢查 `web_add_<name>.flag` / `web_delete_<name>.flag` → 「網頁」；冇 flag → 「電腦」 |
| **通知去重** | watcher `_web_action_window` — 同 base + 同 type 60 秒內只出一條通知（.mq5 + .ex5 兩次變化） |
| **配對庫過濾** | dashboard `loadEAConfig()` — 只顯示本機有檔案嘅 EA（`eaDeployStatus[name]`），MT5 剷除咗自動消失 |
| **電腦剷除自動清理** | watcher `_purge_config()` → `POST /api/ea-config/<name>/purge?agent_id=`（移除 config 配對） |
| Dashboard 顯示 | `server/templates/dashboard.html`（`officialTable`，loadEALibrary JS ~L1007） |

**目錄：**
- 平台官方：`server/static/ea_library/`（32 個 .mq5 源碼）
- 社群：`server/static/community_ea/`
- 用戶上傳：`server/static/user_ea/<username>/`

**⚠️ MetaEditor compile 一定要用 GUI 方式（Bug #55）：**
- CLI `/compile` 喺 background 靜默失敗（冇 desktop access）
- Watcher 用 pywinauto：開 MetaEditor → Ctrl+O → 輸入路徑 → 開啟 → F7
- 自動處理「外部修改」dialog（click「是」）

**⚠️ 聯動機制（移去配對 / 上傳）：**
- EA 倉庫「移去配對」→ `install-local` → 複製落本機 + 排 compile → 配對庫即刻出現
- 上傳自己 EA → 自動安裝落本機 + 排 compile → 配對庫即刻出現

---

## 4️⃣ 我的配對庫（EA 管理 + 狀態 + 信號）

| 項目 | 位置 |
|------|------|
| EA config CRUD | `server/app.py` L167（`/api/ea-config`）、L179（DELETE）、L197（toggle） |
| Dashboard 表格 | `server/templates/dashboard.html`（`eaTableBody`，loadEAConfig JS ~L697） |
| 排序邏輯 | loadEAConfig JS：🟢 運行中喺上，⚪ 停止中喺下；已配對優先 |
| 狀態欄 | 喺「來源」右方：`EA \| 來源 \| 狀態 \| Magic \| Symbol \| TF \| Signal \| SMA10 \| SMA30 \| Trades \| Win \| P&L \| Lots \| 操作` |
| 操作按鈕 | 🚀 部署 / 📊 報告 / ⏸️ 暫停 / 🗑️ 剷除（冇「移去配對」） |
| DB | `server/instance/mt5cloud.db` → `user.ea_config` JSON column |

**注意事項：**
- ⚠️ 本機 EA 顯示用 `eaDeployStatus`（detector inventory 餵）— `fetchEAInventory()` 每 30 秒更新
- ⚠️ 信號欄用 `detectorSignals`（fetchAutoTradeStatus 每 5 秒更新）→ 自動 re-render
- ⚠️ 剷除 = 兩步：`remove-local`（刪本機檔案）+ `DELETE /api/ea-config`（移除設定）
- `_default_lot` 預設 **1.00**（用戶要求，唔係 0.01）
- Magic 預設 240701

---

## 5️⃣ 部署 Pipeline（Dashboard → MT5）

| 項目 | 位置 |
|------|------|
| Deploy API | `server/app.py`（`POST /api/deploy`，寫 deploy_cmd JSON — 2026-08 加熱鍵 reload 檢查） |
| Watcher | `agent/deploy_watcher.py`（3 秒 polling，COMMON/Files/deploy_cmd_*.json） |
| **熱鍵部署（主力）** | `agent/auto_attach.py` `attach_ea_hotkey()`（send 熱鍵 → Properties/代替確認 dialog 自動處理） |
| Auto-attach（fallback） | `agent/auto_attach.py` `attach_ea_navigator()`（6093 下唔可靠） |
| 通知視窗 | `agent/deploy_notify.py`（tkinter「AI 控制中」）+ `agent/control_guard.py`（🛡️ AI 控制守衛） |
| 緊急停止 | `agent/kill_all.bat` + control_guard「🚨 緊急停止」按鈕 |
| 流程 | Dashboard `deployEA()` → `/api/deploy` → watcher detect → auto_attach.py（熱鍵優先）→ MT5 chart |

**🎯 熱鍵方案（2026-08-06 用戶發現 — 解決 6093 double-click 問題）：**
- **設定檔**：`<Terminal>\config\hotkeys.ini`（UTF-16 LE）— 格式 `[experts]`：`Experts\MT5Cloud_EA\<EA>.ex5=Ctrl+N`（**只有 `<experts>` section + 乾淨 CRLF — 用戶實測格式**）
- **生效條件**：**關閉 MT5 → 寫檔 → 開 MT5**（運行中寫會被 MT5 覆寫；MT5 只認「啟動時讀」）
- **⚠️ 格式**：唔可以用 `\r\r\n`（雙 CR — MT5 解析唔到）— 要乾淨 `\r\n`（0d 0a）+ 冇 `<indicators>` section
- **dialog 處理**：Properties（撳確定）+ 代替確認（「MetaTrader 5」dialog — 文字喺 Static — 撳是）— **BM_CLICK（SendMessage）**（確定按鈕喺 dialog 邊界外 — pywinauto click 唔到）
- **熱鍵分配**：配對 → `assign_hotkey()`（下一個可用 Ctrl+N — 唔重複）→ 剷除 → `release_hotkey()`（位置釋放）

**auto_attach.py 流程：**
1. `control_guard.acquire()` — 彈警告視窗 + 寫 lock
2. generate_template（.tpl）
3. 開/搵 MT5 + Navigator 統一 + 圖表平鋪（Alt+R）
4. **開新圖表**（Ctrl+N → Enter — 2026-08：每個 EA 一個圖表 — 唔代替）
5. **熱鍵優先**：`attach_ea_hotkey()`（send 熱鍵 → dialog 循環處理）— fallback `attach_ea_navigator()`
6. ensure_auto_trading_on
7. verify（heartbeat + EA log）
8. `control_guard.release()` — 關視窗 + 清 lock

**⚠️ 注意：**
- ⚠️ **watcher 鎖**：deploy worker 寫 `.auto_attach_running` 用 os.getpid（watcher 自己）— `is_auto_attach_running()` 要 skip 自己 PID（2026-08 修 — 唔係會永遠 queuing）
- ⚠️ deploy_cmd 積壓會卡死 watcher — 積壓時要清 + 重啟（**刪除已搬入 finally — 防 Tcl crash 漏刪**）
- ⚠️ 6093 對 Navigator double-click 免疫（pyautogui/SendMessage/AHK 全試過）— 熱鍵係唯一可靠
- ⚠️ **開新圖表**：Ctrl+N 要跟 Enter（接受默認品種）— 淨 send Ctrl+N 會彈 dialog 冇接受
- ⚠️ **部署前確保熱鍵**（`ensure_hotkey_for_ea()`）：MT5 重啟會覆寫 hotkeys.ini（未經 GUI 設定嘅新 EA 熱鍵會冇）→ 部署前檢查 + 冇就分配 + 關 MT5 → 寫 → 開（reload）
- ⚠️ **Watchdog**（2026-08）：`agent/watchdog.py`（+ ~/.hermes/scripts/mt5_watchdog.py）+ Hermes cron 每分鐘 — watcher/server/detector 死咗自動重啟

**⚠️ 重要（Bug #50）：**
- ⚠️ **refresh_navigator 一定要 in-process call**（`importlib` + `mod.refresh_navigator()`）— spawn subprocess 冇 desktop access 會 pyautogui 卡死 timeout
- ⚠️ **Single worker + queue**（`_refresh_worker_loop` + `_refresh_queue`）— 多 thread 同時 pyautogui 會搶滑鼠互卡
- ⚠️ **`control_guard` 所有 tkinter 操作要用 `after(0, ...)` 排隊** — 直接 destroy 喺非 tk thread 會 hang 成個 process

---

## 6️⃣ Auto-Trade Detector（獨立信號雷達）

| 項目 | 位置 |
|------|------|
| Detector 主程式 | `agent/auto_trade_detector.py`（:5003，ThreadingHTTPServer） |
| 信號 API | `GET /api/auto-trade-status`（:5003） |
| Inventory API | `GET /api/ea-inventory`（:5003） |
| **Static JSON bridge** | 每 30 秒寫 → `server/static/detector/{auto_trade_status,ea_inventory}.json` |
| DB 讀取 | 直接讀 `server/instance/mt5cloud.db` user.ea_config |
| MT5 log 讀取 | UTF-16 解碼，最近 3 個 log 檔 |

**原理：** SMA10/SMA30 crossover → BUY/SELL/WAIT（金叉/死叉）
- 每 30 秒：讀 config → 檢查 MT5 → 下載 M1 rates → 重組 TF → 計 SMA → 判斷交叉
- 部署/刪除/暫停 EA → 下一輪（≤30s）自動感應

**Dashboard 讀取：** `fetch('/static/detector/xxx.json?t=' + Date.now())` — **同源，唔用 localhost:5003**（HTTPS tunnel 混合內容封鎖，Bug #44）

**注意事項：**
- ⚠️ 單實例守衛：:5003 已被佔就退出
- ⚠️ MT5 唔會自己開 — detector 只檢查唔啟動
- ⚠️ 暫停嘅 EA 顯示 PAUSED，唔計信號
- ⚠️ detector 獨佔 MT5 Python API（避免 singleton 衝突）— server 唔可以同時 initialize

---

## 7️⃣ MT5 Navigator 自動 Refresh + 即時通知 + 活動記錄

| 項目 | 位置 |
|------|------|
| Refresh 腳本 | `agent/refresh_navigator.py`（225 行） |
| 目錄監控 | `agent/deploy_watcher.py`（`check_experts_changes()`，3 秒） |
| Refresh worker | `agent/deploy_watcher.py`（`_refresh_worker_loop` single worker + `_refresh_queue`） |
| Deploy worker | `agent/deploy_watcher.py`（`_deploy_worker_loop` + `_deploy_queue` — 唔 block 主 loop） |
| **Compile worker** | `agent/deploy_watcher.py`（`process_compile_cmd()` + `_compile_via_gui()` — MetaEditor GUI compile + **control_guard 警告視窗 + 用完自動關閉 MetaEditor** + 失敗重試 3 次 + 緊急停止唔重試 + 「外部修改」dialog 開 file 後即刻 click 是） |
| **Auto-Attach** | `agent/auto_attach.py` — 只掃 `app.windows()`（MT5 process，唔可以用 Desktop 掃全部 — 會掃到 MetaEditor tree）；**tree visible 用 rect 判斷**（MT5 custom draw — WS_VISIBLE 唔可靠）；**EA交易 folder 先 text match 後 index**（新版加咗「訂閱」— index 由 2 變 3）；`wait_for_mt5` 用 win32 backend（uia 卡死 60 秒）；**AutoTrading 喺 double-click 前確保 ON**（OnInit 即刻開單 — Properties 後先開太遲 retcode 10027；**send ^e 前要 pause_window 隱藏警告視窗** — tkinter 視窗 deiconify 搶 focus 令 send_keys 落錯；唔可以 toggle 兩次 = ON→OFF）；**「代替」dialog 自動撳「是」**（title 係「MetaTrader 5」唔含 EA 名 — 要掃 Static 內容）；失敗時清殘留 dialog（撳否/取消）；heartbeat 驗證 timeout 15 秒；**`--remove` 模式（真暫停）**：right-click → Alt+X 開「專家」dialog → 列表揀 EA → 「移除」按鈕（「專家顧問」menu 讀唔到 items — MT5 owner-draw） |
| **GUI 互斥鎖** | `agent/deploy_watcher.py`（`_refresh_lock` — compile 同 refresh 共用，兩個 pywinauto 唔可以同時操作 GUI） |
| **即時通知** | `agent/deploy_watcher.py`（`_notify_ea_change()` → `server/static/detector/notifications.json`） |
| **持久化 Activity Log** | `server/activity_log.jsonl`（JSONL append）+ `server/app.py` `log_activity()` + `GET /api/activity?include_db=1`（db_update 預設過濾） |
| **資料庫更新記錄** | `agent/auto_trade_detector.py`（`log_db_update()` — 每 30 秒寫「已更新資料庫」）+ Dashboard checkbox「顯示資料庫更新」 |
| 前端通知 | `server/templates/dashboard.html`（`fetchNotifications()` + toast） |
| **前端活動記錄** | `server/templates/dashboard.html`（`fetchActivity()` + 活動記錄 card） |
| **AI 控制狀態 bridge** | `agent/control_guard.py`（`_write_status()` → `server/static/detector/ai_control.json`）+ dashboard `pollAiControl()`（2 秒 poll — 電腦操控都彈警告視窗；404 都會關視窗） |
| **AI 控制警告視窗（電腦版）** | `agent/control_guard.py` — **常駐視窗**（`_ensure_window_thread()` + `_run_tk()`：daemon thread + mainloop 永遠行，只 show/hide 切換，**唔 destroy**）；**預建**（`init_window()` — watcher 啟動時建好隱藏，動作開始即刻顯示）；**右下角**（唔遮 Navigator → 唔使 pause/resume）；icon-bot 用 tkinter Canvas 畫（唔用 PhotoImage — GC 殺 process）；release() idle timeout（最少 3 秒 + 最後動作 2 秒內關）+ 續命 + 緊急停止；`_write_status()` 同步網站狀態 |
| 監控目錄 | `MQL5/Experts/`（snapshot 比對 name+size+mtime） |
| Cooldown | queue coalesce（變化密集時合併成一次 refresh） |

**流程：** 檔案新增/刪除 → watcher 偵測 → 寫通知 JSON + activity log + 觸發 queue → worker in-process refresh → dashboard 彈 toast + 更新列表 + 活動記錄

**支援三種 Navigator 狀態（Bug #47）：**
1. Docked（嵌喺主窗口）→ 掃主窗口 descendants
2. **Floating（浮動視窗 Afx:MiniFrame「導航」）** → `EnumWindows` 掃所有 top-level windows
3. 關閉 → 自動嘗試 Ctrl+N / Alt+V+N / WM_COMMAND 32845 開返

**注意事項：**
- ⚠️ **只有「右鍵→刷新」menu 模擬先 work**（Bug #46）— 其他方法全部失敗（ShowWindow toggle / WM_COMMAND 32808/32845 / collapse-expand / F5）
- ⚠️ pyautogui 要 `FAILSAFE = False`（MT5 maximized 時滑鼠會去角落）
- ⚠️ 64-bit handle 要 `int(h)` cast（OverflowError）
- popup menu 係 `#32768` class；「刷新」喺 menu 最底（`rect.bottom - 11`）

---

## 8️⃣ Dashboard UI（shadcn + Lucide）

| 項目 | 位置 |
|------|------|
| Dashboard | `server/templates/dashboard.html`（~1250 行） |
| Index | `server/templates/index.html` |
| Login | `server/templates/login.html` |
| Register | `server/templates/register.html` |
| Lucide CSS | `https://cdn.jsdelivr.net/npm/lucide-static@latest/font/lucide.css` |

**UI 規則（用戶要求）：**
- ✅ shadcn 風格：zinc 色系（--bg #09090b, card #18181b）+ emerald accent
- ✅ **只用 Lucide icons，零 emoji**（static HTML 已 0 emoji；JS showLog 內嘅 emoji 可接受）
- ✅ **Lucide class 用 `icon-` prefix**（≥v0.473 用 `icon-xxx`，唔係 `lucide-xxx`）
- ✅ 擴展現有 list 加 columns，唔加新 cards/tabs（用戶偏好）
- ✅ 驗證：改完要 browser 硬 refresh（Ctrl+Shift+R）+ 真係 render 過

**注意事項：**
- ⚠️ 用戶會 cap 圖驗證 — 改完唔可以淨係話成功
- ⚠️ `var(--success)` / `var(--danger)` / `var(--text-muted)` 係 CSS variables
- ⚠️ icon 唔 render 通常係 prefix 錯（`lucide-` vs `icon-`）或者 CDN 302

---

## 9️⃣ 系統穩定性 / 重啟

| 項目 | 位置 |
|------|------|
| 一鍵重啟 | `agent/restart_all.sh`（殺全部 python → 起 server + detector） |
| 緊急停止 | `agent/kill_all.bat`（用戶雙擊） |
| 單實例守衛 | `server/app.py` `if __name__ == '__main__'` + `agent/auto_trade_detector.py` |
| Health check | `GET /health`（server）+ `GET /health`（detector） |

**restart_all.sh 流程：**
1. `taskkill -f -im python.exe`
2. 確認 :5001 + :5003 釋放
3. `nohup python server/app.py` + `nohup python agent/auto_trade_detector.py`
4. 健康檢查

**注意事項：**
- ⚠️ Hermes 會 auto-restart python — 所以單實例守衛係必需（否則 5+ server 搶 :5001）
- ⚠️ 壓力測試：同時 spawn 5 server + 3 detector → 只有 1+1 活到
- ⚠️ 殺完所有 python 之後要即刻 start（快過 Hermes respawn）

---

## 🔟 環境 / 系統事實

| 事實 | 值 |
|------|-----|
| MT5 Build | 6061（FILE_COMMON 寫入 bug → 用 FILE_TXT） |
| MT5 Account | 5053721681（MetaQuotes-Demo，Python API 開嘅 demo） |
| MT5 路徑 | `C:\Program Files\MetaTrader 5\terminal64.exe` |
| MT5 數據目錄 | `%APPDATA%\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\` |
| DB 路徑 | `server/instance/mt5cloud.db` |
| Login | dev / dev1234（devLogin() 一鍵填入） |
| Tunnel（固定） | **`https://mt5cloud.esgov.org`** → localhost:5001（Cloudflare named tunnel `mt5cloud` ID `9ce5c130-ff5d-4ff0-9460-95ab2aab50dd`；config `C:\Users\hongk\.cloudflared\config.yml`；**service 一定要 `http://127.0.0.1:5001`** — localhost 會被解析做 IPv6 ::1 連唔到（Bug #75）） |
| 舊臨時 Tunnel | `olive-frequency-cool-plan.trycloudflare.com`（已廢棄 — 快速 tunnel 重啟 URL 會變） |
| Python | 3.11（系統）/ 3.14（sibling） |
| 端口 | 5001 server / 5003 detector |

---

## 🗺️ 快速改動指南

| 想做咩 | 改邊度 |
|--------|--------|
| 加 UI 功能 | `server/templates/dashboard.html`（JS + HTML） |
| 加 API | `server/app.py`（route + 邏輯） |
| 改 EA 部署 | `agent/auto_attach.py` + `agent/deploy_watcher.py` |
| 改信號邏輯 | `agent/auto_trade_detector.py` |
| 改 Navigator refresh | `agent/refresh_navigator.py` + `agent/deploy_watcher.py` |
| 改登入/綁定 | `server/app.py` L105-135 + L874 + `login.html` |
| 重啟系統 | `bash agent/restart_all.sh`（server+detector；watcher 要手動）+ 開機自動：`start_auto.bat`（啟動資料夾 `MT5Cloud_Start.bat` — Server/Detector/Watcher/Tunnel 登入自動行） |
| 緊急停 | 雙擊 `agent/kill_all.bat` |

**每次改完之後：**
1. `bash agent/restart_all.sh`（如果改咗 server/detector）
2. 瀏覽器 Ctrl+Shift+R 硬 refresh
3. 更新本文件相關分類 + PROGRESS.md
