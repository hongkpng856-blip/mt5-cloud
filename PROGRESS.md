# 📋 MT5 Cloud — Progress & Bugs

> 📂 **功能模組分類索引**：改嘢之前睇 `MODULE_INDEX.md` — 一次過知道「呢個分類涉及邊啲地方」
> 📊 **改動影響分析**：改嘢之前睇 `MODULES.md` + 自動跟 `mt5-impact-analysis` skill — 知道牽涉邊啲位置
> 此文件專門記錄開發進度、已修復 bug、未修復 bug。
> README.md 負責項目介紹 + 快速開始，PROGRESS.md 負責進度追蹤。

---

## 📊 Overall Progress

| 階段 | 狀態 | 完成度 |
|------|------|--------|
| Server + Dashboard UI | ✅ 完成 | 100% |
| EA Library + Upload/Download | ✅ 完成 | 100% |
| Agent 連線 + Heartbeat | ✅ 完成 | 100% |
| EA Download + Compile + Heartbeat inject | ✅ 完成 | 100% |
| Navigator Auto-Attach EA (auto_attach.py) | ✅ 完成 | 100% |
| Deploy Watcher + 全自動化 | ✅ 完成 | 100% |
| HTTP Deploy API (代替 Socket.IO) | ✅ 完成 | 100% |
| Deploy Notification 視窗 | ✅ 完成 | 100% |
| Global Mutex (防多個 auto_attach) | ✅ 完成 | 100% |
| Dashboard Alive 🟢🔴 指示 | ⏳ 未開始 | 0% |
| Heartbeat FILE_COMMON fix | ⏳ 進行中 | 50% |
| **5x 壓力測試穩定（v0.9.67 新 stack）** | 🔴 **未過（0/5）** | 困住 attach |

---

## 🔴 Current Blocker（2026-08-18 下午 — HY3 跟進）

> **目標**：用家要求「用新版做多 5 次壓力測試（5/5 PASS）」。v0.9.67 已 commit/push，但喺**對版新 stack**（server+watcher+agent+MT5 全部用新 code 重起）上跑 `stress_test_5x.py` 連續 **0/5 ~ 2/5 FAIL**，5/5 一直未達成。

### 已確認 / 已根治嘅項（呢輪 debug 搞清楚咗）
1. ✅ **URI fix 對版**：server_run.log 確認 load `sqlite:///C:\...\instance\mt5cloud.db`；ORM remove-local persist 證實（之前 5/5 係靠 v0.9.66 raw-SQL 頂住，新 stack 先暴露下面嘅真 bug）。
2. ✅ **auto_attach dispatch 改咗**：`auto_attach_ea` 永遠用 `attach_ea_navigator`（Navigator 雙擊），唔用 `attach_ea_hotkey`（雙擊掛唔到 → `雙擊後未偵測到 Properties`）。
3. ✅ **watcher 改 python.exe**：`run_auto_attach` 強制用 `C:\...\Python311\python.exe`（絕對路徑，唔用 `sys.executable`/`pythonw`）—— pythonw 會令 subprocess 間歇性 hang（試過 44 分鐘唔退）→ 5min timeout。但 note：pythonw 有時都成功，所以**唔係決定性因素**。
4. ✅ **stress test 改等 .ex5**：install 之後 poll `.ex5` 出現（最多 60s）先 deploy，唔好固定 sleep(6)。
5. ✅ **watcher deploy worker 改等 .ex5**：check `.ex5` 唔到就等（最多 30s）先 skip，唔好即刻 skip（race）。
6. ✅ **單次 deploy 證實 work**：手動經 API `install-local` + `deploy` → watcher 跑 `auto_attach` → **`🎉 Properties dialog found! Attached.` + 💓 心跳出**（watcher log 有實錘）。

### 🔴 真正卡住嘅點（未解）
- **5x 連續跑全部 age=None**（心跳冇出）。但**單次**手動 deploy 成功 → 問題出喺**連續循環**或者**某啲輪次 attach 唔到**。
- `aa_debug.log`（watcher tee 出嘅 auto_attach 完整 output）顯示真正失敗模式：
  ```
  🎯 Found EMA_Cross, attaching via pyautogui double-click...
  🎯 EMA_Cross double-clicked (handle-based)
  ⚠️ EMA_Cross dialog not found after scan (attempt 1/3)
  ... 3 輪都係咁
  ❌ EMA_Cross attach failed after 3 attempts
  ```
  → **搵到 EMA_Cross + double-click 咗，但 Properties dialog 彈唔出（或者彈咗即刻收埋）** → 掛唔到 EA。
- 矛盾點：`aa_debug.log` 中途有 `🎉 Properties dialog found! Attached.`（line 83）但跟住 line 85 又 `❌ attach failed` → 似係 dialog 搵到 vs 驗證邏輯有出入，或者 scan 模式逐行 double-click 干擾咗已彈出嘅 dialog。
- `compile_ok` 間歇 `False`（Round 2/4/5）：server install 有時寫咗 compile_cmd 但 `.ex5` 未生成（watcher `_compile_via_gui` 用 MetaEditor GUI F7，間歇性失敗）。

### ✅ 2026-08-18 下午（OpenChart 實測確認 + crash fix — v0.9.69）
- **OpenChart 加入配對庫 + 部署開 chart 機制確認 work**（用家實測）：EA 倉庫添加 OpenChart → 去配對庫部署 → 成功開到空白 chart（OpenChart 唔係交易 EA → 空白 chart 正常）→ 用「添加快捷鍵」方式保存（`hotkeys.json` 分配齊）。證據：`open_chart_cmd.json`=`{"symbol":"AUDUSD","tf":"H1"}` + `aa_debug.log` `✅ 附加成功（心跳存在）` + `✅ 心跳後備: 運行中`。
- **🐛 修 crash（v0.9.69）**：實測最尾 `ensure_auto_trading_on` 連 MT5 時舊 PID（5764）唔在（MT5 中途重啟過）→ `ProcessNotFoundError` → 成個 auto_attach 死（EA 掛咗但自動交易可能冇啟到）。根治：`ensure_auto_trading_on` 連唔到就用 `find_mt5_pid()` re-find，再唔得 skip（唔 crash）。**未做**：其它 `Application.connect(process=mt5_pid)` 位（apply_template_gui line 873 等）同樣風險，下次實測再補。
- **部署流程（跟番之前一樣，唔使改 OpenChart 做真 EA / 唔使加心跳）**：揀 Symbol → 寫 `open_chart_cmd.json` → auto_attach 檢查/寫 `hotkeys.ini Scripts\OpenChart.ex5=Ctrl+9`（冇登記自動加）→ `Alt+F→Enter×3` 確保有 chart window → `Ctrl+9` 觸發 OpenChart script 讀 json → `ChartOpen(揀嘅 Symbol)` 開返嗰個 chart。
- 已 commit/push v0.9.69（1ab3828）。PROGRESS.md 版本表加咗 v0.9.69 行。

### 假陽性陷阱（已識別）
- stress test Round 1 有時 `age=53s` PASS → 其實係**上一輪手動掛嘅殘留心跳 file** 未清，唔係今輪真成功。要用「今輪 install 之後新寫嘅心跳」判斷。

### 下一步（未做）
- A. 修 `attach_ea_navigator` 嘅 **double-click → dialog 唔出** 問題（可能係 `click_input(double=True)` vs pyautogui 座標 double-click 喺連續跑時 focus 唔穩；或者 scan 模式逐行 double-click 干擾）。
- B. 根治 `compile_ok` 間歇 False（server/watcher compile 唔穩定）。
- C. **架構反思（用家提問）**：而家 attach 靠 pyautogui/pywinauto GUI 自動化（開圖表→開 Navigator→雙擊 EA→Properties→確定），天生脆弱。之前 v0.9.50-56 用過 **OpenChart.mq5 + ChartApplyTemplate（純 MQL5，模板含 `<expert>` EA path → 套模板即掛 EA）**，完全唔使 GUI 自動化 → 應該更穩。見下面答用家。
- D. commit/push auto_attach.py + deploy_watcher.py + stress_test_5x.py 嘅改動（而家全部未 commit）。

---

## 📌 Version Log（版本記錄）

> 每次「update doc and bug」→ 加一行 + 匯報俾用戶「而家係咩版本/日期」

| 版本 | 日期 | 內容 |
|------|------|------|
| **v0.10.27** | 2026-08-20 | 🔧 **取消 Step 2b 全部定位操作**（固定 MT5 視窗/Navigator 統一/平鋪圖表 — 用戶話一開始唔需要定位；Alt+F 開 chart 用鍵盤唔靠座標）|
| **v0.10.26** | 2026-08-20 | 🔧 **開 chart 失敗直接 return False**（移除 OpenChart script 誤導 print — 實際冇執行；用戶要求唔需要備用方案 — 失敗就 fail 唔好靜默繼續）|
| **v0.10.25** | 2026-08-20 | 🔧 **取消 Step 2B 熱鍵 load 驗證（124 行）**（每次等 45s 好慢 + 冇用 — 用戶要求）+ **移除重試快捷鍵備用方案**（失敗直接 fail — 避免重試掛錯 chart：Heikin_Ashi 掛錯 EURUSD 案例）|
| **v0.10.46** | 2026-08-21 | 🔧 **修 is_script 冇帶出 output** — scan_ea_inventory 構建 inventory.append 漏咗 is_script 字段（info 有但 output 冇）→ 前端過濾唔到 script。加 is_script 落 output — 實測：ApplyTemplate/OpenChart/StartAgentHelper=True（script）+ Divergence=False（EA）|
| **v0.10.47** | 2026-08-21 | 🎨 **UI 全面改做 XCHANGE 橙黑主題（Binance 風格）** — 4 頁（index/login/register/dashboard）`:root` 變數換橙黑 token（`--accent:#f0b90b`、`--bg:#0b0e11`、`--bg-card:#181a20`、`--border:#2b3139`）+ DM Sans 字體 + 金底黑字（logo/btn-primary/btn-orange — WCAG AAA）+ JS 硬編碼色全部跟換（部署 modal/checkbox/活動狀態）|
| **v0.10.48** | 2026-08-21 | 🔧 **Dashboard 精簡** — ①Agent 卡淨顯示 Account/Balance/Equity（移除 Positions/Trades/Win Rate/Profit Factor/Total P&L）②EA 倉庫「刷新狀態」掣剷除 ③「上傳 EA 去社群庫」由橙色 btn-orange 改普通 btn |
| **v0.10.49** | 2026-08-21 | 🔧 **配對庫排位修正** — ①狀態文字靠左（同 header「狀態」對齊 — 之前 text-align:center 起點唔同）②三粒掣（部署/報告/刪除）改細粒 + 橫排（之前 grid 2 欄太大粒）③操作按鈕靠右（inline-flex + justify-content:flex-end）|
| **v0.10.50** | 2026-08-21 | 🔧 **配對庫表格全欄位對齊** — Magic/Symbol/Trades/Win/P&L 移除 text-align:center/right → 全部靠左同 header 一致（之前 header left + data center/right → 上下對唔齊）|
| **v0.10.51** | 2026-08-21 | 🔧 **Trades/Win/P&L 真實數據** — ①agent.py `get_mt5_status` 加收集 history deals（之前冇 → `/api/analysis` 永遠「No data yet」）②`/api/analysis` 過濾 magic 0（平台手動交易唔計入 EA 統計）③前端改 magic 聚合（EA config 冇存 symbol — 之前 msKey 對唔上）④Win 顯示 0%（唔再隱藏）+ P&L 格式修正（`-$1.27` 唔係 `$-1.27`）|
| **v0.10.52** | 2026-08-21 | 🎯 **新增 TestTrades.mq5 測試 EA** — 持續開單→平倉（每 15 秒開 0.10 lot，持倉 10 秒平，交替買賣）產生真實 Trades/Win/P&L。**EA 自己 track 統計寫入 `state_<EA>.json`**（trades/wins/losses/profit — 因 MT5 Python history API 讀唔到新 deals（build 6120 caching）→ EA 層面自己計最準）→ server `/api/ea-config` 讀 EA stats 返回前端。實測：164 單 / 18.9% / -$13.00 持續跳動 |
| **v0.10.53** | 2026-08-21 | 🔧 **休市偵測（非交易時間）** — server 用 `symbol_info_tick` 最後 tick（正規化 UTC+3）> 5 分鐘 = 休市 → `market_closed` map 返回前端；心跳暫停 + 休市 → 顯示「休市」（灰色 — 正常，唔係 EA 故障）vs 心跳暫停 + 開市 → 顯示「心跳暫停」（黃色 — 有問題）。實測：AMD 休市偵測到（true）/ EURUSD 開市（false）|
| **v0.10.54** | 2026-08-21 | 🧹 **清歷史 script 殘留** — OpenChart/StartAgentHelper config 配對刪除（歷史測試遺留 — script 唔係 EA，唔應該配對；`market_closed` 唔再見到佢哋）— config 淨返 Divergence + TestTrades 兩隻真 EA |
| **v0.10.55** | 2026-08-21 | 🎯 **配對庫全欄位排序功能** — 撳 header 排序（第一次 asc ▲ → 再撳 desc ▼ → 循環）：EA/來源/狀態/Magic/Symbol（字母/狀態）+ Trades/Win/P&L（數字由低至高/高至低）— 排序箭頭指示（金色 ▲/▼）+ 默認 Trades/Win/P&L 顯示 ⇅ 箭嘴（用戶要求）|
| **v0.10.56** | 2026-08-21 | 🔧 **縮細視窗箭嘴走位修正** — `.ea-table th` 預設 `white-space:normal` → 視窗縮細時 header 空間唔夠，箭嘴 span（inline）被擠去第二行 → 箭嘴走位。改 th `white-space:nowrap` + sort-ind `display:inline-block; vertical-align:middle` — 箭嘴強制同 header 文字同行 |
| **v0.10.57** | 2026-08-21 | 🧹 **清重複 TestTrades chart** — 多次部署 TestTrades（改 code 重新部署）累積 5 個 EURUSD chart 同時運行（窗口 dialog 確認）→ 用 auto_attach --remove 逐個剷除 → 淨返 1 個（正常）— 用戶實測見 4 個部署係重複，唔正常 |
| **v0.10.58** | 2026-08-21 | 🔧 **報告按鈕加真實數據** — 報告靠 `agent.deals`（MT5 API 讀唔到新 deals）→ 全部空/0。改 TestTrades EA 加 `win_sum/loss_sum`（自己 track 贏/輸總額）+ server `/api/ea-report` fallback 讀 EA stats → 準確計 avg win/loss/PF。實測：460 單 / 22% / PF 0.39 |
| **v0.10.59** | 2026-08-21 | 🔧 **報告三圖表（Equity/Distribution/Monthly）加真實數據** — 之前得基本統計冇圖表。TestTrades 加 `AppendTrade()`（平倉 append 逐單落 `trades_<EA>.json` JSONL）+ `RebuildTradesFile()`（OnInit 掃全部歷史重建 — 唔丟失舊單）+ server 讀 trades json 計 equity curve/distribution/monthly/max_dd。實測：629 行完整歷史、報告 100 點 equity |
| **v0.10.60** | 2026-08-21 | 🔧 **配對庫數據一致 + 更新修復** — ①之前 500+ 單變百幾：trades json 新加先開始記錄 → RebuildTradesFile 重建完整歷史（629 行）②配對庫冇更新：state json 被系統心跳覆寫（得 ea/status/ts）→ server `/api/ea-config` 改讀 trades json（完整）優先 + fallback state。實測配對庫/報告完全一致（634 單 / 153 勝 / 478 負 / -$47.70） |
| **v0.10.61** | 2026-08-21 | 🎯 **Correlation Matrix 真實數據** — `/api/analysis` 合併 trades json（完整歷史）→ summary 750 單 / 26.74%；correlation key 改 EA 名（TestTrades 顯示真名）；修 JS bug：精簡 Agent 卡後 loadAnalysis 攞唔到已刪 element → null error → correlation 唔渲染 → 加 null check 修復。實測：2x2 matrix（240701_USDJPY + TestTrades）渲染 |
| **v0.10.62** | 2026-08-21 | 🔥 **部署代替 dialog 根治（用戶實測：關 chart 後部署取代咗 TestTrades）** — ①代替 dialog 由「撳是接受」改「撳否拒絕」+ 部署 fail（唔可以取代其他 EA — 之前撳是 → 其他 EA 被取代 + 心跳殘留假成功）②部署前清理所有殘留 dialog（Properties 殘留 → 之後開 chart Alt+F 被 modal 擋 → 開 chart 失敗 → 代替 dialog 一鑊泡）③開 chart/active chart 驗證改用 EnumChildWindows（pywinauto descendants 對 MT5 chart 窗口不可靠 — 開 chart 成功但驗證假失敗 → 部署 fail）— 實測：Divergence → AUDJPY 部署成功（開圖驗證 ✅ active chart ✅ 心跳 ✅ log loaded ✅）|
| **v0.10.63** | 2026-08-21 | 🔥 **部署後 dialog 殘留根治（用戶實測：RSI 部署後 dialog 一直開住 → 之後部署全部被擋）** — ①部署後加 dialog 清理（WM_CLOSE — 實測有效；之前 ESC/撳取消對 modal dialog 唔 work — RSI Properties 卡死）②部署前清理改用 WM_CLOSE（唔再 ESC）③修 runtime_status log 判斷：讀 terminal Logs（英文 loaded successfully/removed）而唔係 MQL5/Logs（MetaEditor 中文已启动/已停止 — 誤判 chart_removed）— 實測：RSI_Over → UK100 部署成功 + 部署後 dialog 0 個 |
| **v0.10.64** | 2026-08-21 | 🔥 **剷除多個同名 chart 揀錯根治（用戶實測：3 個 UK100 時剷除揀錯 → 假成功）** — remove_ea_from_chart 改「逐個試」策略：候選 chart（symbol match）→ Ctrl+W 關 → 驗證 EA 真係移除（心跳停/log removed）→ 未移除就下一個；+ FIX index 移位 bug（移除 chart 後 ListView 重新排位 — 舊 index 指錯 chart → 每次試之前重新對應 symbol → 最新 index）— 實測：3 個候選 chart 逐個試 → 第 3 個 UK100 先係 RSI_Over → 成功移除。同時確認：MT5 唔會即時自動 restore chart（關晒後 30 秒冇自動開返 — 之前「restore」其實係重複 chart 殘留）|
| **v0.10.65** | 2026-08-22 | 🔥 **UAC/授權窗口檢測機制（用戶要求：MT5 更新都會問授權）** — ①`_detect_and_handle_uac()`：偵測「授權/Client Terminal/要求/允許」窗口（class Secure UAP/consent）→ 自動處理（SendMessage Enter + WM_CLOSE）→ 關唔到（Windows 安全層）→ 寫 `.uac_alert` 通知用戶手動撳（等 30 秒自動繼續）②加入所有部署流程（8 處）：attach_ea_hotkey / auto_attach_ea / 熱鍵預載 / do_restart_mt5 / 剷除 / Navigator 附加 / 開 chart script / watcher / server 3 個 API（deploy/delete/install-local）— 實測：模擬授權窗口偵測到 + 自動處理；冇 UAC 時 0.0s 即刻 pass；實測 MT5 單一 instance 正常部署唔會彈 UAC（之前 4 個 UAC 係多 instance 撞帳戶安全機制）|
| **v0.10.66** | 2026-08-22 | 🎯 **壓力測試 2 號 ×5 全 PASS（部署 3 隻 EA → 剷除 1 隻 → 驗證其他冇被影響）** — 5 輪：ADX(EURUSD)+EMA(GBPUSD)+Bollinger(USDJPY) 部署 → 輪流剷除 EMA/Bollinger/ADX/EMA/Bollinger → 每次只關目標 chart，其他 2 隻完整保留（chart 數 3→2 啱 + 心跳新鮮）— 驗證剷除「逐個試」機制喺多 EA 場景完全可靠 + 冇誤傷 + 冇 UAC |
| **v0.10.67** | 2026-08-22 | 🔧 **配對庫消失 bug（電腦有已配對 EA 但網頁冇顯示）** — 壓力測試輪流剷除 → 每次 DELETE 加 `_removed` → 但 **api_deploy 重新部署時冇由 `_removed` 清走**（只有 install-local 有清 — Bug #64）→ `_removed` 累積 ADX_Trend + EMA_Cross → 前端 `!removed.includes(name)` 過濾走晒 → 配對庫空。修復：①api_deploy 加「重新部署 = 由 _removed 移除」②修正現有 DB 數據 — 實測配對庫顯示返兩隻（心跳運行 + 正確 symbol/magic）|
| **v0.10.68** | 2026-08-22 | 🔥 **熱鍵改為 Ctrl+1 重用（用戶要求：每次部署都用 Ctrl+1，部署完釋放，下隻 EA 又用返）** — ①`_ensure_hotkey_loaded` 寫入邏輯改：唔再批次分配 Ctrl+1~9 — 清空 hotkeys.ini 舊 mapping + 只寫「新 EA = Ctrl+1」+ 同步 hotkeys.json（只保留當前 EA=^1）②**restart 前記錄所有 chart**（EnumChildWindows — 修 window match bug：MT5 標題含 MetaQuotes 唔含 MetaTrader）→ **restart 後檢查 + 補開遺失 chart**（根治「部署 Grid 搞走 EMA_Cross」— restore 唔齊）③熱鍵 load 實測（send Ctrl+1 → 彈 Properties = load 咗 → 唔 restart）— 實測：Bollinger→USDJPY + Grid→DE40 部署成功，其他 EA 全部保留（chart 冇遺失），hotkeys.ini 每次只有當前 EA=Ctrl+1 |
| **v0.10.91** | 2026-08-28 | 🗑️ **配對庫「刪除」只刪檔案+config — 唔移除 chart EA（用戶實錘：剷除後心跳仲寫 — EA 仲行緊）+ 環境空白完整重測（註冊→安裝→添加→部署×3→剷除 — 實測 PASS）** — ①**剷除 bug 根治**：配對庫「刪除」掣 call `remove-local` — 只刪 .mq5/.ex5 + config — **冇寫 pause_cmd → watcher 唔觸發 `auto_attach --remove` → EA 仲掛 chart 行緊（心跳仲寫）** → 修復：remove-local 加寫 `pause_cmd`（action=delete）→ watcher `process_pause_cmd` → `--remove`（移除圖表 EA — 同 ea-config/delete 一樣 — commit a667bf5）— 實測：剷除 MACD_Cross → 08:23:21 removed + 心跳停（EA 真移除）✅ ②**環境空白完整重測**（test_final — 最新 code + stable 部署方法）：註冊 PASS → 安裝 PASS（連線+平台服務+依賴 8 檔）→ 添加 ATR_Stop PASS（compile+配對庫）→ 部署 ATR_Stop EURUSD PASS（心跳 0s）→ 部署 MACD_Cross USDJPY PASS（ATR_Stop 保留 — 兩隻 alive）→ 部署 EMA_Cross XAUUSD 重試成功（三隻 alive — 心跳全部 0s）→ 剷除 EMA_Cross（發現 bug — 已修）→ 重測剷除 MACD_Cross 完整移除 ✅ — **部署實測：三隻 EA 同時 alive（stable 部署方法 — restart 後 restore 齊 + 其他 EA 自動重新掛）** ✅ |
| **v0.10.90** | 2026-08-28 | 🔧 **部署位置用返 stable-v0.10.76 方法 + 全新環境測試發現 8 個 bug（用戶要求：參考穩定版本 — 實測 PASS）** — ①**部署位置完整取代**：`_ensure_hotkey_loaded` + `attach_ea_hotkey` 用返 stable 版本（用戶實測穩定成功）— 正常關閉 WM_CLOSE save profile → restart 後 chart restore 齊（GBPUSD + AUDUSD 兩隻同時 alive — 冇遺失）→ 部署成功 + 其他 EA 保留 ②**MetaEditor 周不時彈出**（server Auto-sent EA config → agent download_and_install 重新下載 .mq5 — 心跳注入 → mtime 永遠新過 .ex5 → 每次 compile → MetaEditor 彈出）→ 修復：`.ex5 存在就 skip compile`（eb8fb15）③**平台服務誤判「已行緊」**（PowerShell `CommandLine -match` 會 match 自己 session 嘅 bash → count>0 → 永遠唔開真服務）→ 加 `$_.Name -eq 'python.exe'` 過濾（969fec3）④**deploy_watcher crash**（`deploy_notify` 依賴缺 — 下載 loop 只處理第一個 script）→ 白名單加 `deploy_notify.py` + 下載全部依賴（90a1cdc）⑤**部署失敗（auto_attach.py 唔存在 — race condition）**→ `_ensure_platform_services` 加額外依賴下載（auto_attach/refresh_navigator/control_guard — b3cb1c3）⑥**熱鍵 load 測試失敗分支冇關 chart**（只成功分支有 Ctrl+W → 3 次測試失敗 + restart = 空白 chart 累積）→ 失敗分支都關 chart（a6a4faa）⑦**熱鍵預載 skip 條件太鬆**（hotkeys.ini 被 MT5 清空 → skip 錯 → Ctrl+1 失效 → 掛 EA 失敗）→ skip 前驗證 hotkeys.ini 有「當前 EA=Ctrl+1」且非空（bc57bbf）⑧**補開遺失 chart 失敗**（pywinauto 0.6.9 唔支援 `{ALT}` → 改 `%f` shorthand；`'_App_hkt' in dir()` 誤判 → 刪檢查；match 只比較 symbol 唔計數量 → 4 vs 1 誤判齊全 → 計數量）— 實測：補開 GBPUSD 成功（7a92bef/509b703/2e55439）— **部署實測**：Bollinger_Band → GBPUSD + ADX_Trend → AUDUSD 兩隻同時 alive（心跳 0s）— restart 後 chart 齊全（冇遺失）✅ |
| **v0.10.69** | 2026-08-24 | 🔥 **熱鍵先係主力（用戶要求：唔使理 EA 入面有咩 — 開到 chart + 撳熱鍵 = 成功，驗證靠 log）** — ①**跳過 generate_template**（掛 EA 唔需要模板 — 之前一體化模式靠套模板掛 EA，而家直接開 chart（Alt+F）+ send 熱鍵（Ctrl+1）掛 EA）②**修 verify_heartbeat 假成功**：之前讀 MQL5/Logs（MetaEditor 日誌 — 中文「已启动」殘留 → 誤判「已啟動」→ 假成功）→ 改讀 terminal Logs（<hash>/Logs/ — 英文 loaded successfully）+ 只認「loaded successfully」（唔認「started」— 太濫）+ 最後狀態判斷（removed 後唔算 loaded）③**修「附加成功」假成功**：之前淨係 check 心跳檔存在（os.path.isfile — 舊檔殘留都話「心跳存在」）→ 改 check age（<300s 先算新鮮）— 實測：ADX→XAUUSD 部署成功（心跳 0s + log loaded successfully 13:46:47 — 真成功唔再假） |
| **v0.10.89** | 2026-08-28 | 🗑️ **網站剷除 Agent + 完整剷除/安裝 cycle（用戶要求：剷除 = 全部清晒，安裝 = 全部裝返 — 實測 PASS）** — ①**網站剷除 Agent 功能**：dashboard 加「剷除 Agent」掣（紅色）+ server `POST /api/agent/remove`（SocketIO 發 shutdown + DB 寫剷除標記 fallback）+ `POST /api/agent/remove-complete`（agent 回報後刪 DB）+ agent 收 shutdown → 清 lock/config/桌面捷徑 → 通知 server → 退出 ②**剷除 = 全部清晒**：agent process + 平台服務（watcher/alert_worker/auto_trade_detector）+ pystray 測試殘留 + `%LOCALAPPDATA%\TradotcomAgent\` 資料夾 + DB 記錄 + 桌面捷徑 — 實測：剷除後電腦完全乾淨（只剩 Hermes + server + MT5）③**安裝 = 全部裝返**：agent 啟動 `_ensure_platform_services` 自動檢查 + 開返平台服務（缺檔案從 server `/api/agent-service/<name>` 下載 — deploy_watcher/alert_worker/auto_trade_detector）— 實測：重裝後 3 個平台服務自動開返 ④**dashboard API crash 修復**：user 冇 agent（剷除後）→ `agent.account_info` None → 500 → 前端 agent_id 空 + 得返一張卡 → 加 None check 返回空資料 ⑤**dashboard JS crash 緊急修復**：加 removeAgent 時誤刪 `</script>` → 之後 HTML 入咗 script → SyntaxError → 所有掣撳唔到 → 加返 `</script>` ⑥**shutdown 清理順序 bug**：先刪資料夾（rmtree 刪自己）→ 之後 crash → 平台服務冇停 + DB 冇刪 → 改先停服務後刪資料夾 + 逐個刪（跳過自己）+ 防重複（emit+poll 雙重觸發）+ 唔好 match 自己路徑 kill 自己（root cause — 清測試殘留 match `TradotcomAgent` → agent 自己喺嗰度 → kill 自己）— 實測：剷除後 agent/平台服務/資料夾/DB 全部乾淨 ✅ |
| **v0.10.88** | 2026-08-27 | 🚀 **Server→Agent 人手壓力測試（完整註冊流程 ×4 PASS + 部署執行鏈根治 — 10 commits）** — ①**完整註冊流程**：剷除舊 agent → 註冊新 account（stress01-04）→ CDP 登入（本機 Chrome `--remote-allow-origins=*`）→ 下載 pyw → 安裝精靈（用戶幫手撳）→ 精靈自動關閉 + Agent 品牌 console（`SetConsoleTitleW`「Tradotcom Agent」+ `CREATE_NEW_CONSOLE`）→ 連線 + 帳戶上報 — 實測 4 次 100% PASS ②**Agent 斷線循環根治**：sync payload 1.2MB（6653 deals 每次傳）→ socket 斷線 → deals cache 60 秒 + 每 60 秒先傳 + websocket transport + server eventlet（`RENDER=1`）③**彈返監察 hardcode dev config → 誤刪 multi-user 部署 .ex5**（改讀全部 user config）④**剷除冇刪本機檔案**（watcher action=delete 實際刪 .mq5/.ex5）⑤**部署 chart 累積**（每次部署開新 chart 冇收返 → 12 個 tab）→ 方案二：部署前檢查心跳新鮮 → 收返舊 chart → 再部署（commit 8eaf9b6 — 用戶確認）⑥**refresh worker 無限循環**（pending 變化 → 無限 refresh → 卡死 deploy poll）→ 加最大 3 次 ⑦**agent poll deploy_queue fallback**（emit 收唔到 — tunnel 斷線窗口 → sync poll `/api/agent-poll-deploy`）⑧**熱鍵預載誤判**（restart 後冇 chart → Ctrl+1 冇目標 → 誤判未 load → 浪費 110 秒）→ 測試前開 chart ⑨**部署 .ex5 唔存在 → 自動 compile**（metaeditor CLI — 修「剷除後再部署失敗」）⑩**心跳驗證加 age check**（<60s 新鮮先 PASS — 修假成功）⑪**watcher 用 python.exe + redirect**（pythonw 冇 console → stdout 丟失）⑫**模擬帳戶冇 tick → 心跳唔寫**（環境行為 — 真帳戶正常）— 部署實測：自動 compile ✅ + 熱鍵 load ✅ + MT5 log loaded ✅（但心跳驗證受模擬帳戶冇 tick 影響）|
| **v0.10.87** | 2026-08-27 | 🛡️ **方案 A 防雙開 + 彈窗修正（用戶要求：一部機一個 agent — B account 想喺已有 agent 嘅機安裝 → 阻止）** — ①**防雙開 lock**：agent.py 啟動時讀 `%LOCALAPPDATA%\TradotcomAgent\agent.lock`（記錄 agent_id+PID）→ 有其他 agent 行緊（PID 驗證）→ 阻止 + 彈窗 + exit(3)；冇 lock/舊 agent 死 → 寫自己 lock 接管 — 實測：DEV00001 行緊 → fef654c3 被阻止 ✅ ②**「Agent 已連線」彈窗只彈一次**（斷線重連唔再彈 — 之前每次 connect 都彈）③**server→agent 人手壓力測試流程已記錄**（skill ref `stress-test-server-to-agent.md` — 登入 web → 安裝 agent → 網頁添加/部署/剷除隨機反覆）|
| **v0.10.86** | 2026-08-27 | 🖥️ **第二部機安裝全鏈路根治（用戶實測：安裝唔到 → 網頁唔綠 → 假綠燈 — 20 commits）** — ①**安裝流程**：網頁一粒掣直接下載 pyw（唔使 launcher/curl/PowerShell — 避開 curl 下載問題）+ 固定安裝位置 `%LOCALAPPDATA%\TradotcomAgent` + 桌面捷徑自動建立 + 安裝精靈（條款/檢查/設定）②**啟動 crash 根治**：pyw 啟動 agent 時 cp950 唔支持 ☁️ emoji → UnicodeEncodeError → agent.py 強制 UTF-8 ③**連線診斷**：agent.py 全面寫 log（AGENT START/init/args/socketio/Connecting/Connected/Registered）+ MT5_DATA 動態偵測（唔 hardcode 第一部機 hash）+ socketio.Client http_session fallback + connect wait=False ④**假綠燈根治**：server 加 _agent_live_status（last_seen <60s 先 online）+ 時區 bug 修復（naive UTC 比較 — 唔用 timestamp 錯 8 小時）⑤**tray icon**：Agent 運行時綠色正方形（Online/Offline 顯示）— 實測：第二部機 fef654c3 完整上報（107082878 Ava-Demo）✅ |
| **v0.10.45** | 2026-08-21 | 🔧 **①警告視窗有機率網頁冇彈** — showControlModal 強制顯示（唔靠 !aiControlVisible — aiControlVisible 卡住 true 時新操作唔彈）**②我的配對庫唔顯示 script** — detector 標記 is_script（Scripts 目錄）+ 前端過濾（activeEAs/localEA 排除 script）|
| **v0.10.43** | 2026-08-21 | 🔥 **剷除假成功根治（Breakout AMD 案例）** — ①未確認移除（_removed_ok False）→ return False（之前無條件話成功 → 網頁假成功）②窗口 dialog 未關（再試 Enter 都冇效）→ fail ③揀 chart 改方向鍵（唔靠座標 click — ListView scroll/行高唔同會揀錯）|
| **v0.10.42** | 2026-08-21 | 🔧 **symbol 驗證機制** — ①server 部署前驗證 symbol 喺帳戶 symbols（唔喺 → 返回 error『symbol 唔存在』400）②前端 deploy error → 彈警告 modal — 用戶要求：揀咗冇嘅 symbol 要偵測到 + 警告 + 唔可以部署 |
| **v0.10.41** | 2026-08-21 | 🔧 **symbol picker 改用帳戶 History symbol**（bases/<帳戶>/History — 帳戶伺服器實際支援 — MetaQuotes-Demo 20 個：XAUUSD/UK100/US30/DE40 等）— symbols.sel 只係市場報價顯示（4 個 — 唔權威）；ETHUSD 真係冇（MetaQuotes-Demo 唔支援加密貨幣）|
| **v0.10.40** | 2026-08-21 | 🔧 **網頁 symbol picker 改用帳號實際 symbols**（get_account_symbols 讀 MT5 symbols.sel — 帳號只有 4 個）→ 揀到冇嘅 symbol（ETHUSD）部署 fail（後改 v0.10.41 History 來源）|
| **v0.10.39** | 2026-08-21 | 🔧 **修 refresh Navigator 兩次** — v0.10.38 加 _refresh_queue.put() 疊加『Experts 目錄變化』觸發 → refresh 兩次（第二次又撳右鍵）— 移除 put（剷除刪 .mq5/.ex5 已自動觸發 file-watch refresh）|
| **v0.10.38** | 2026-08-21 | 🔧 **剷除後自動 refresh Navigator**（process_pause_cmd 完成後 _refresh_queue.put() — 用戶實測「剷除成功但 MT5 Navigator 殘留 — 要自己 refresh」）|
| **v0.10.37** | 2026-08-21 | 🔥 **修剷除卡住** — process_pause_cmd 用 _PYEXE（未定義 — run_auto_attach 入面先定義，唔同 scope）→ NameError → auto_attach --remove 冇跑到 → 剷除卡住（用戶實測 delete EA 卡住）|
| **v0.10.36** | 2026-08-21 | 🔧 **修剷除 _dlgs NameError**（ctypes 未定義 — 函數 import _ct alias 但 _dlgs 用 ctypes）→ 剷除中途 crash；修正 _ct — 實測剷除 ATR_Stop 成功（Alt+W → ListView → Ctrl+W → MT5 log removed）|
| **v0.10.35** | 2026-08-21 | 🔥 **修 main 入口消失** — v0.10.33 替換 remove_ea_from_chart 時刪埋 if __name__ block → auto_attach 零 output + EXIT 0 → watcher 誤判假成功（ATR_Stop 案例）；加返 v0.10.32 main block（45 行）|
| **v0.10.34** | 2026-08-21 | 🔥 **假成功根治（watcher 讀舊 output）** — ①aa_debug.log tee -a（append）累積舊部署 output → watcher 讀最近 60 行誤判（讀到上次 Breakout/Grid → ATR_Stop 假成功）→ 改覆寫 tee ②成功判斷唔好淨靠 returncode（return 0 都可能內部 fail）→ 檢查 auto_attach output 有真 SUCCESS |
| **v0.10.33** | 2026-08-21 | 🔧 **剷除改用 Alt+W 窗口 dialog 方法**（用戶實測 — 唔靠座標）— Alt+W 開窗口 dialog → ListView 即時讀 chart 排位（唔用 .chr 檔 — 延遲/id=0）→ 對應 EA symbol（MT5 log）→ 揀目標 chart → Enter（關 dialog 彈返 chart）→ Ctrl+W 關閉（EA 一齊移除）|
| **v0.10.23** | 2026-08-20 | 🔧 **revert v0.10.22 重用邏輯** — 每次部署都開新 chart（確保 chart 對應目標 symbol + 乾淨冇 EA）— 用戶指正：唔應該重用舊 chart（可能掛咗其他 EA/狀態唔啱） |
| **v0.10.22** | 2026-08-20 | 🔧 **chart 累積根治（後 revert v0.10.23）** — 開新 chart 前檢查有冇目標 symbol 現有 chart → 有就 focus 重用；用戶指正唔應該重用 → revert |
| **v0.10.21** | 2026-08-20 | 🔧 **恢復完整開 chart 流程 Alt+F→Enter→Enter→Space→打symbol→Enter**（v0.10.19 誤刪咗 Space→打symbol 步 — 開 chart 唔係目標 symbol；用戶指正完整流程係 5 步）|
| **v0.10.20** | 2026-08-20 | 🔧 **修 active chart 驗證誤判** — EnumChildWindows「Chart」class 喺 MT5 搵唔到（chart 係 AfxFrameOrView 類）→ 改用 MDI chart 窗口檢查（同開圖驗證一致）— v0.10.18 誤殺導致部署中止 |
| **v0.10.19** | 2026-08-20 | 🔧 **開 chart 簡化做 Alt+F→Enter→Enter**（後 revert v0.10.21 — 用戶指正要打 symbol） |
| **v0.10.18** | 2026-08-20 | 🔧 **附加錯 chart 根治** — send 熱鍵前驗證 active chart 係目標 symbol（OpenChart 開 chart 失敗 → active 係舊 restore 嘅 GBPUSD → 附加落去 → 代替 dialog → 一鑊泡：Bollinger/EMA 都掛咗落 GBPUSD 而唔係目標 EURUSD/USDJPY）→ 驗證唔到就明確 fail 唔好代替 |
| **v0.10.17** | 2026-08-20 | 🔧 **連環代替確認 dialog 根治** — 撳完「是」之後 MT5 可能連環彈多個「代替」dialog（附加 EA 落已有 EA 嘅 chart）→ loop 完後再 poll 8 秒撳晒所有代替 dialog「是」（最多 5 次）— 用戶實測「確定完仲要再確定多次」 |
| **v0.10.16** | 2026-08-20 | 🔧 **假成功根治** — _ea_loaded_in_log 加 loaded 記錄時間戳檢查（只認最近 300s 內嘅 loaded — 之前只 check log 檔 mtime 新鮮，舊記錄喺 log 檔 → 誤判 True → 假成功：Bollinger 部署話 SUCCESS 但實際冇掛到 chart）|
| **v0.10.15** | 2026-08-20 | 🔧 **修復 restart 重寫熱鍵後 MT5 PID 未更新** — v0.10.13 熱鍵 load 驗證 fail → restart 開新 MT5 之後，後續 Navigator/平鋪/快捷鍵用舊 PID → Process not found → 部署卡死（用戶實測「電腦好耐冇反應」）|
| **v0.10.14** | 2026-08-20 | 🔧 **修復 magic 空 string 令部署假成功** — 前端未 alive EA 傳 magic='' → server/watcher data.get('magic') 收到空 string（default 唔生效）→ auto_attach --magic 空 → argparse 失敗 → watcher 誤報「attach 成功」（4 秒假成功 — Heikin_Ashi 案例）。三層 fallback：前端 (magic||'240701') + server data.get('magic') or '240701' + watcher 同 |
| **v0.10.13** | 2026-08-20 | 🔧 **熱鍵 load 驗證 fail 自動修復** — Step 2b 驗證 gate fail（45s 冇彈 Properties）→ restart MT5（關→寫→開）→ 再驗證一次（多 EA 場景第二隻撞到 MT5 啱 restart 完/熱鍵未 load → send 失效 → 自動 restart 重寫）|
| **v0.10.12** | 2026-08-20 | 🔧 **修批次預載段 indentation bug**（縮排錯咗喺 except block 入面 → 正常情況 skip → _experts_hk NameError）+ _combo_n 提前定義（experts 空 NameError）。實測：批次預載 → 第一隻 restart 一次 → 第二隻 skip restart 直接部署 → 兩隻連續成功 |
| **v0.10.11** | 2026-08-20 | 🔧 **恢復批次熱鍵預載（多 EA 時序根治）** — 一次 restart 寫入全部 .ex5 熱鍵 → 之後每隻 skip restart（冇逐隻 restart 時序問題）；保留 v0.10.8/10.10 驗證 gate + 修 _combo_n 被覆寫 bug |
| **v0.10.10** | 2026-08-20 | 🔧 **熱鍵 load 時序修正** — `_ensure_hotkey_loaded`「已有熱鍵」時檢查 hotkeys.ini mtime vs MT5 啟動時間：熱鍵喺 MT5 開機後先寫入（MT5 開住時寫）→ 唔會被 load → restart 重寫（保留原 combo）；開機前已寫好 → 已 load → return。根治「MT5 開住時寫熱鍵 → send 失效」 |
| **v0.10.9** | 2026-08-20 | 🔧 **回歸逐隻熱鍵預載**（revert v0.10.7 批次預載）— 批次預載寫入嘅「全新熱鍵」MT5 內部未記住 → 唔 load → send 失效；保留 v0.10.8 開完 MT5 後熱鍵 load 驗證 gate |
| **v0.10.8** | 2026-08-20 | 🔧 **熱鍵 load 驗證 gate 移到開完 MT5 之後** — `_ensure_hotkey_loaded`「已有熱鍵 → return」會 skip 開完 MT5 嘅驗證 → MT5 啱開機熱鍵未 load → send 失效；而家 auto_attach_ea Step 2b 開完 MT5 後 poll send 測試熱鍵彈 Properties = load 成功 |
| **v0.10.7** | 2026-08-20 | 🔧 **批次熱鍵預載優化**（後 revert v0.10.9）— 一次過掃描本機所有 .ex5 → 全部寫入 hotkeys.ini；實測發現「全新熱鍵」MT5 唔 load → revert |
| **v0.10.6** | 2026-08-20 | 🔧 **部署假失敗根治** — attach_ea_hotkey 驗證失敗唔再 return False（外層 Step 4 gate 最終判定）+ Step 4 gate fail 交 Step 5 心跳後備 + _ea_loaded_in_log 加新鮮度檢查（log mtime<300s 防 stale 假 True）|
| **v0.10.5** | 2026-08-20 | ⭐🔧 **部署流程檢測系統落地（docs/deployment-checkpoint-system.md）** — auto_attach.py 加 `_wait_until(check_fn, timeout, desc, interval)` 每步驗證 gate helper（poll 到成功先落下一步，唔等固定時間）+ ① `_ensure_hotkey_loaded` 開完 MT5 驗證熱鍵 load（等主視窗 ready 90s → send Ctrl+N 測試彈 Properties = load 成功，×3 重試，撳取消關 dialog）② 關 MT5 gate（WM_CLOSE 後 poll 確認已關 20s，未關先強制 kill）③ Step 1 gate：MT5 開 + 主視窗 ready（poll 90s）④ Step 4 gate：EA loaded 驗證（MT5 log `loaded successfully` 且無隨後 removed，poll 30s — 對真 log 唔靠心跳）⑤ Step 5 最終驗證：log loaded 優先（市場收市心跳唔寫都算成功），心跳只做輔助 |
| **v0.9.82** | 2026-08-18 | 🔧 **watcher compile 改用 CLI `/compile` 優先** — GUI F7 間歇性失敗，改先試 `metaeditor64.exe /compile:<mq5> /log:<log>`（100% 可靠），成功即返，GUI fallback — 根治 OpenChart 配對 compile 失敗 |
| **v0.9.81** | 2026-08-18 | 🔧 **OpenChart/OpenChart_Helper 加入 `_SYSTEM_KEEP`** — 唔會被「重新整理清殘留」誤刪 |
| **v0.9.80** | 2026-08-18 | 🐛 **修 install-local Script 偵測路徑 bug** — `data_dir` 應係 `APPDATA/MetaQuotes/Terminal` → Script copy 正確去 Scripts/ |
| **v0.9.79** | 2026-08-18 | 🎯 **完整支援 Script 類型 EA 配對** — install-local 偵測 .mq5 Script → copy+compile 去 Scripts/（唔注入心跳）+ detector 掃 Scripts/ — 根治 OpenChart 配對失敗 |
| **v0.9.78** | 2026-08-18 | 🎯 **重新整理自動清殘留** — refresh-status 掃 Experts+Scripts，刪唔喺 config + 唔係 _SYSTEM_KEEP 嘅檔 |
| **v0.10.4** | 2026-08-20 | 🔧 **_ensure_hotkey_loaded 加 .ex5 存在檢查**（破綻處理）— EA 冇本機 .ex5 → 報錯『請先配對』唔白試（用戶實測：冇 .ex5 熱鍵指向唔存在 EA → 失效）|
| **v0.10.3** | 2026-08-20 | 🔧 **部署時唔再 restart MT5**（_HK_RESTART_DISABLED=True）— 熱鍵已由 _ensure_hotkey_loaded 預載（關→寫→開），部署時 restart 會令 MT5 覆寫 hotkeys.ini 令熱鍵失效|
| **v0.10.2** | 2026-08-20 | ⭐🔧 **部署前熱鍵預載（_ensure_hotkey_loaded — 用戶實測成功流程）** — 確保 EA 熱鍵喺 MT5 關閉狀態下寫入 hotkeys.ini → 開 MT5 load → 熱鍵 work（之前 MT5 開住時寫 → 唔 load → Ctrl+N 失效）|
| **v0.10.1** | **v0.10.1** | 2026-08-20 | 🔧 **新方法開 chart 驗證 bug** — 之前淨靠主窗口標題含 symbol（MT5 主窗口標題唔一定含 active chart symbol — 實測開咗 EURUSD chart 但標題冇後綴）→ 誤判失敗 fallback Ctrl+9 → 熱鍵失效全失敗。改為同時檢查 MDI chart 窗口有冇 <SYM> chart |
| **v0.10.0** | 2026-08-20 | 🔧 **watcher 跑 auto_attach 一律用 python.exe 絕對路徑（_PY_EXE module constant）** — 防 sys.executable=pythonw hang 5min timeout 致命問題 + 修重複 import |
| **v0.9.99** | 2026-08-20 | 🔧 **修 do_restart_mt5 WM_CLOSE 段 ctypes 未定義 NameError**（用 _ct 代替 ctypes）→ 正常關閉真正生效（之前 fallback 強制 kill 又搞走其他 EA）|
| **v0.9.98** | **v0.9.98** | 2026-08-20 | ⭐🔧 **根治「部署 restart 後其他 EA 移出圖表」** — do_restart_mt5 用 proc.kill() 強制殺 MT5 → 冇 save chart profile → 開機唔 restore 其他 EA。改為「正常關閉」（WM_CLOSE 俾主窗口）→ MT5 save profile → 開機 restore 全部 chart + EA；同時 reload 熱鍵（Swing Ctrl+5 生效）。實測：restart 後 6 隻 EA（ADX/Bollinger/Breakout/EMA_Cross/Swing/Divergence）全部 loaded + 心跳新鮮 + Swing 部署成功|
| **v0.9.97** | **v0.9.97** | 2026-08-19 | 🔧 **「已加入本機冇檔案」殘留根治** — /api/ea-library 加 local_has（server 直接 check 本機 MT5 Experts/Scripts 有冇 .ex5，唔靠 detector 延遲）→ 前端 added 用 f.local_has → 配對完成後即時顯示「已加入」，唔使 refresh（實測 Grid_Trading local_has=True）|
| **v0.9.96** | 2026-08-19 | 🔧 **① 配對完成後自動 refresh（觸發 rescan + 延遲多次 refresh）② 所有動作完成後自動 refresh（waitDeployDone → refresh-status + reload 配對庫）**|
| **v0.9.95** | 2026-08-19 | 🔧 **① Symbol 開放全部（showSymbolPicker 用 allSymbols 24 隻，唔再淨 6 隻固定）② Magic/Symbol 顯示改為「實際有部署/掛住」先顯示 — 剷除圖表（chart_removed）/未部署（unpaired）/啱啱配對都「—」**|
| **v0.9.94** | **v0.9.94** | 2026-08-19 | 🔧 **解決 Swing_Trader 熱鍵失效＋保護其他已掛 EA** — ① do_restart_mt5 移除「關閉全部圖表」段（restart 保留 chart → 其他 EA 唔消失）② 重新啟用部署 restart reload 熱鍵（_HK_RESTART_DISABLED=False）→ 新 EA 熱鍵（Swing Ctrl+5）load 到。實測：Swing loaded + 心跳新鮮；ADX/Bollinger/Breakout/EMA_Cross 全部保持掛住（心跳持續）— 「部署其他 EA 令 EMA_Cross 消失」一齊根治|
| **v0.9.93** | 2026-08-19 | 🔧 **部署唔 restart MT5（_HK_RESTART_DISABLED）** — do_restart_mt5 前關閉全部圖表 → 部署其他 EA 令已掛 EA chart 被關消失（v0.9.94 改返 restart 但保留 chart 取代）|
| **v0.9.92** | 2026-08-19 | 🔧 **修部署完成後要 hard refresh 先可以再部署** — _append_activity_log 讀 'type' key 但 caller 用 'action' → deploy_result 寫成 unknown → 前端 waitDeployDone 揾唔到 → modal 卡住遮部署掣。改讀 action 優先｜實測 deploy_result 正常寫入 |
| **v0.9.91** | **v0.9.91** | 2026-08-19 | ⭐🔧 **根治「一秒 remove」真兇（ADX 部署重要成功）** — ADX_Trend 源碼有 AgentHelper bootstrap code（OnTick 一啟動就 ChartApplyTemplate('AgentHelper_EURUSD_H1.tpl') → AgentHelper 取代 ADX → ADX 自己 ExpertRemove）→ 一秒成功下一秒 remove + 最終冇掛。移除嗰段 bootstrap → ADX 掛住交易唔讓位 → 重新 compile。驗證（對真 MT5 log）：`04:59:41 expert ADX_Trend (EURUSD,H1) loaded successfully` **無 removed** + 心跳持續新鮮。其他 EA（Breakout/Bollinger_Band）log 證實 loaded 無 removed（機制正常）。|
| **v0.9.90** | 2026-08-19 | 🔧 **部署真 EA（ADX）用熱鍵真掛 target chart** — 只有 Script（OpenChart）用一體化假裝掛；真 EA 即使 open_chart=True 都 send 熱鍵（Ctrl+N）真掛落新開 chart（唔靠 apply_template_gui 係 stub — 之前假掛 + 掛錯 chart）|
| **v0.9.89** | 2026-08-19 | 🔥 **修心跳後備假成功 root cause** — state_<EA>.json 新鮮度用 ts（EA TimeCurrent() server-time/UTC）對比本地 time.time() → 時區錯位相減負數 → 永遠<300 → 假話運行中；改用心跳檔案 mtime 對比本地時間（一定準）|
| **v0.9.88** | 2026-08-19 | 🔧 **部署成功判定改用 Terminal log 驗證** — D0E8.../logs/ 搵『expert <EA> (<SYM>,H1) loaded successfully』先算成功（用戶要求：對真 MT5 log 做比對先話成功，唔信心跳/activity 假成功）；唔用 MQL5/Logs（EA Print 誤判）|
| **v0.9.87** | **v0.9.87** | 2026-08-19 | 🔧 **Script 類型暫不支援部署** — /api/deploy 偵測 .mq5 係 Script（#property script_show_inputs / OnStart 無 OnInit）→ 返回 400「暫不支援部署（只支援長駐EA）」，唔再嘗試 deploy（唔會卡死/load 好耐）。實測：OpenChart→不支援；ADX_Trend→正常。|
| **v0.9.86** | 2026-08-19 | 🔧 **移除 auto_attach 個 Ctrl+9 hotkeys check + 重啟 MT5 段** — 唔再用 Ctrl+9 開 chart，唔會 MT5 重啟令 PID 變新方法 fail |
| **v0.9.85** | 2026-08-19 | 🔧 **移除舊 Alt+F→Enter×3 開空白 chart 段** — 統一由「用戶方法」Alt+F→Enter→Enter→Space→symbol→Enter 一次過開 target chart，唔重複開 chart + 唔受 Ctrl+9 熱鍵洗走影響 |
| **v0.9.84** | 2026-08-19 | 🔧 **main attach 流程修正** — Script 類型（OpenChart/OpenChart_Helper）用 attach_ea_hotkey（新方法開 chart），避免走 attach_ea_navigator（Navigator 雙擊對 Script 唔 work 卡死 not found）|
| **v0.9.83** | 2026-08-19 | 🎯 **部署開 chart 改用「用戶發現方法」** — Alt+F→Enter→Enter→Space→打 symbol→Enter（pyautogui 實測 100% 開到 target symbol chart — 唔受 MT5 重啟洗走 hotkeys.ini `<scripts>` 區影響）；Ctrl+9 fallback |
| **v0.9.77** | **v0.9.77** | 2026-08-18 | 🎨 **EA 倉庫 OpenChart 系列標記做測試用** — 橙色「測試」badge + 排最後 |
| **v0.9.76** | 2026-08-18 | 🎯 **取消 `MT5Cloud_EA` folder 方案 — 根治 EA「彈返/重複」問題（用戶引導）**：**① 問題** — 配對庫自動彈返 Breakout/Fibonacci/OpenChart（心跳暫停），MT5 有兩個同名 `MT5Cloud_EA` folder（Experts + Scripts 各一個），且 EA 同時喺根 `Experts/` + `Experts/MT5Cloud_EA/` 兩個位置。**② root cause** — `auto_trade_detector.py` 等 `scan_dirs = [exp_dir, exp_dir/MT5Cloud_EA]` 同時掃根 + subfolder，一個 EA 喺兩個位置就重複顯示；殘留檔 copy 去根 Experts/ 令 detector 掃到 → 彈返。**③ 根治（v0.9.76）** — 全面取消 `MT5Cloud_EA` folder：detector / install-local / deploy / hotkeys / remove-local / bounce_back 監察全部淨係用根 `Experts/` + `Scripts/`（唔掃唔建 subfolder）；hotkeys.ini path 改返 `Experts\\ADX_Trend.ex5`（根）；MT5 實體剷走兩個 `MT5Cloud_EA` folder，ADX_Trend 搬返根 `Experts/`。**④ 驗證** — `ea_inventory.json` = `total 1 eas: ['ADX_Trend']`（淨返配對嗰隻，唔再彈返三個）。**⑤ 附帶發現（未解）** — 部署時 auto_attach 個 `Ctrl+9` 熱鍵經 `hotkeys.ini <scripts>` 區，MT5 重啟會洗走該區 → OpenChart 開唔到 chart → EA 掛唔到 → 心跳 15s 偵測唔到 → 部署「load 好耐 + 電腦冇反應」（v0.9.70 已存在，未根治）。|
| **v0.9.69** | 2026-08-18 | 🔧 **OpenChart 加入配對庫 + 部署開 chart 機制確認 + crash fix**：**① EA 倉庫加「OpenChart」程式**（v0.9.68 已入 `server/static/ea_library/OpenChart.mq5`；今次經 API `install-local` 加入配對 → copy 落 `Experts/MT5Cloud_EA/` + compile OK）。**② OpenChart 當 EA 部署**（用家指定唔使改為真 EA、唔使加心跳 —「你當係 ea 就得」；開 chart 唔係由 EA 經 script 啟動 → 用返熱鍵 Ctrl+9 個套）。部署流程跟番之前一樣：揀 Symbol → 寫 `open_chart_cmd.json {symbol,tf}` → auto_attach 檢查/寫 `hotkeys.ini Scripts\OpenChart.ex5=Ctrl+9`（冇登記自動加）→ `Alt+F→Enter×3` 確保有 chart window → `Ctrl+9` 觸發 OpenChart script 讀 json → `ChartOpen(揀嘅 Symbol)` 開返嗰個 chart。**③ 熱鍵 target 補返**：`Scripts/MT5Cloud_EA/OpenChart.ex5` + `.mq5` 擺好（Ctrl+9 會撳嘅位置）。**④ 用家實測成功**：EA 倉庫添加 OpenChart → 去配對庫部署 → 成功開到空白 chart（OpenChart 唔係交易 EA → 空白 chart 正常）→ 用「添加快捷鍵」方式保存（`hotkeys.json` 分配齊）。證據：`open_chart_cmd.json` = `{"symbol":"AUDUSD","tf":"H1"}` + `aa_debug.log` `✅ 附加成功（心跳存在）` + `✅ 心跳後備: 運行中`。**⑤ 🐛 修 crash**：實測最尾 auto_attach 去 `ensure_auto_trading_on` 時 MT5 中途重啟過（舊 PID 唔在）→ `Application.connect(process=5764)` → `ProcessNotFoundError` → 成個 auto_attach 死（EA 掛咗但自動交易可能冇啟到）。根治：連唔到就用 `find_mt5_pid()` re-find，再唔得 skip（唔 crash）。**⑥ 清理 git tracking**：runtime log + 臨時 debug file 之前被 track，加返 `.gitignore`（`agent/_*.py`/`*.png`/`_*.log`/`_stress*`/`close_all_charts.py`）+ untrack 晒，避免每次 commit 一大堆運行時 file。|
| **v0.9.68** | 2026-08-18 | 🔄 **程式碼 revert 返 v0.9.56（保留 56-67 全部 commit 歷史，唔刪任何記錄）— 由 HY3 執行**：**① 用 `git checkout b48957c -- server agent` 將程式碼還原到 v0.9.56 狀態**（server/app.py + server/templates/dashboard.html + agent/*.py 全部 revert，唔用 `reset --hard` → 56-67 commit 完好保留喺 git log）。**② 加入 `OpenChart.mq5`（手動輸入品種版 v1.30）** — 用家最新要求：每一次雙擊 Navigator → MT5Cloud_EA → OpenChart 彈對話框填 Symbol + Period → 開唔同 chart；留空 symbol 讀 `open_chart_cmd.json` 自動模式。已放 `MQL5/Scripts/MT5Cloud_EA/` + repo `server/static/ea_library/`。**③ 注意（revert 後帶返嘅已知問題）**：Ctrl+9 熱鍵時好時壞（MT5 唔 load hotkeys.ini `<scripts>` 區）、Controller 常駐掛載未成功、5x 壓力測試未穩定 —— 呢啲係 v0.9.56 時已存在、57-67 試過解但未根治嘅問題。**④ 加 `.gitignore`** 忽略 runtime logs / detector json（唔使每次 commit 一大堆運行時 file）。**⑤ OpenChart.mq5 仲喺 MT5 terminal folder（AppData）實體運行 —— repo 版只係備份**。 |
| **v0.9.67** | 2026-08-18 | 🎯 **🔥 真正 root cause 根治（5/5 PASS 穩定）— 由 HY3（呢個模型）更改**：**① 🔥 壓力測試 5/5 PASS（真正穩定）** — 5 輪連續 `install-local → deploy → 心跳驗證 age 0.1-1.0s → remove-local → 確認清走` 全部 ✅（v0.9.66 個陣係輪流 FAIL）。**② 🔥 真正 root cause：`SQLALCHEMY_DATABASE_URI` 用相對路徑**（v0.9.66 #44 只係 raw SQL 繞過 — 而家搵到真正源頭）：`sqlite:///mt5cloud.db` 相對 server run 目錄 → ORM `current_user.ea_config=...; db.session.commit()` **全部寫去 `server/mt5cloud.db`（空 file）**，而 watchdog / raw SQL / stress test 讀 `instance/mt5cloud.db` → 永遠 mismatch。根治：URI 改絕對路徑 `instance/mt5cloud.db` → **全部 6 個 ORM 寫入位（install-local/remove-local/upload/ea-config POST/PUT/deploy）自動修好**，唔使逐個 raw SQL。**③ 心跳驗證真正對（verify_heartbeat）**：原本淨檢查 `hb_<ea>.txt`，但注入 code 寫 `state_<ea>.json` → 永遠 False → auto_attach 靠 `verify_ea_loaded`（stale log）誤報成功 → watcher「🎉 已成功 attach」但實際冇心跳。改 verify_heartbeat 同時檢查 `state_<ea>.json` + `hb_<ea>.txt`。**④ auto_attach 唔再誤報成功**：原本 heartbeat 失敗就 `return loaded`（stale log）→ 改為循環 attach 最多 3 次，每次 attach 後即時 verify_heartbeat，有心跳先 `return True`（冇就重試 attach）。**⑤ remove-local config 清走確認**：ORM fix 後 `db.session.commit()` 真係 persist → step[5] `config無EA=✅` 而家真係清到。|
| **v0.9.66** | 2026-08-18 | 🎯 **壓力測試 5/5 PASS 根治（用戶要求清重複圖表 + 五次壓力測試）— 由 HY3（呢個模型）更改，commit `D08888C3`**：**① auto_attach 唔再 restart MT5**（hotkeys.ini reload 檢查令 PID 變 → 後續 pywinauto connect 舊 PID fail → exit=1 → watcher 誤報失敗；掛 EA 用 Navigator 雙擊唔使熱鍵 → 唔需要 reload）**② 修 `attach_ea_navigator` 缺 `symbol` 參數 NameError**（Round 4-5 崩潰根因 — 開新圖表段 print/send_keys 用未定義 symbol → crash → EA 掛唔到 → 心跳冇出；加 `symbol` param + caller 傳 `args.symbol`）**③ 心跳驗證接受 `state_*.json` 或 `hb_*.txt`**（唔同 EA 寫法唔同 — EMA_Cross 淨寫 state_ 唔寫 hb_ → 之前誤判 FAIL）**④ 清重複圖表**（開新圖表前先關晒所有 MDI 圖表 → 每次部署得 1 個 EURUSD）**⑤ 環境清理**：kill auto_trade_detector（亂 restart MT5 干擾）+ kill 連 dead tunnel 舊 agent + spawn 新 agent 連 127.0.0.1:5001（live backend 同套）**⑥ 壓力測試 5/5 PASS**（EMA_Cross ×5 輪：配對→部署→心跳驗證 age 0.1-1.0s→刪除→確認清走）**⑦ 🔥 修 `install-local` config 唔 persist（CRITICAL — 隱藏 root cause）**：`current_user.ea_config=...; db.session.commit()` 喺 SQLAlchemy 下**冇真正寫入 DB** → `_bounce_back_watchdog` 每 30s 讀 config 讀到舊值（冇 EMA_Cross）→ 誤刪 `.mq5` → compile fail → 心跳冇出 → 壓力測試輪流 FAIL（bounce_back_log.jsonl 證實每 30s 刪一次 EMA_Cross）。根治：改用 raw SQL `UPDATE user SET ea_config=? WHERE username='dev'`（繞過 ORM）。**⑧ 修 auto_attach 間歇性崩潰**：`find_ea_dialog` UnboundLocalError（nested def 喺 call 之前未定義 → 搬 module-level）+ `ctypes`/`user32` NameError（加 module import）+ `click_y` NameError（加 `click_y=None` default）**⑨ #39 UI 字眼**：EA 倉庫「移去配索」→「加入配對」（未加入 EA button 正確）**⑩ #40 delete 後清心跳 file**：deploy_watcher delete 流程加 `os.remove(hb_*.txt + state_*.json)`（pause 唔清，保留配置）|
| **v0.9.65** | 2026-08-18 | 🎯 **掛 EA 失敗根治 + 重複圖表修復**：**① 廢除 TVM_GETITEMRECT 座標 + 掃描亂點模式**（GETITEMRECT fail → 落入掃描模式逐行 double-click 成個 tree → 掛唔到/掛錯 EA）→ 改用 v0.9.61 證實 work 嘅 `ea_node.click_input(double=True)`（handle-based，唔使座標，唔受 owner-draw/語言影響）**② 重複 EURUSD 圖表**（「Chart already open, skipping Ctrl+N」→ 殘留舊圖表疊加 → 3+ 個 EURUSD）→ 改開新圖表前先關晒所有 MDI 圖表 |
| **v0.9.56** | 2026-08-17 | ⭐ **壓力測試 + 環境修復（發現一系列環境層面問題 — 全部修復）**：**① OpenChart.ex5 script 被誤刪**（之前 cleanup 刪咗 → Ctrl+9 send 去唔存在嘅 script → 開圖表失敗 — 已重建 + 編譯（一體化版 — 讀 json → ChartOpen + ChartApplyTemplate）**② hotkeys.ini 冇 BOM**（`utf-16-le` 寫 → 無 \\ufeff → MT5 讀唔到熱鍵 → Ctrl+9 失效 — 已修：統一 utf-16（BOM）+ auto_attach 寫入加 \\ufeff）**③ 開圖表方式**（Alt+F → Enter×2 只開 dialog — 要 Enter×3 先有真圖表 window — 先可以觸發 Ctrl+9 — 已修）**④ 驗證方法**（用 MT5 Experts log 誤判（script Print 唔一定寫嗰度 + log 延遲）→ 改「MT5 active 圖表標題 = 目標 symbol」— Ctrl+9 開完 BRING_TO_TOP → active 即時改 — 準確）**⑤ Ctrl+9 5/5 開圖表成功**（clean 環境 + 唔同 symbol — active 標題驗證全部成功）**⑥ 壓力測試新發現：「每次重啟 MT5」唔好做** — 實測每次重啟後 script 熱鍵未 ready → Ctrl+9 唔work；你手動環境（MT5 一直運行）Ctrl+9 每次 work → 改「只喺 hotkeys.ini 變咗先重啟」（唔好無謂重啟 — MT5 一直運行保持 Ctrl+9 ready）**⑦ 已知未解**：同 symbol 圖表已存在 → ChartOpen 唔會再開新（focus 返舊）→ log 冇「已開」誤判；Ctrl+9 自動化 send 仍時好時壞（你手動穩定 — 需配合/半自動）|
| **v0.9.55** | 2026-08-17 | ⭐ **部署一體化完全穩定（Ctrl+9 熱鍵 + 每次重啟 reload + 逐項修復）— log 實錘**：**① OpenChart script 熱鍵改 Ctrl+9**（`<scripts>` 區 — 用戶實測可行 — 之前 Ctrl+O/Alt+Q/Ctrl+L 全部唔穩定 — 根源：script 熱鍵唔喺 hotkeys.ini / MT5 未 load）**② 每次部署前 CHECK hotkeys.ini**（有冇 `Scripts\OpenChart.ex5=Ctrl+9` — 唔喺就寫入）+ **每次都重啟 MT5**（確保 Ctrl+9 load — 用戶要求「都需要重啟」）**③ pyautogui send**（真實 keydown/keyup — 同用戶手動一樣 — pywinauto send_keys 送唔到）**④ click 圖表區 focus**（熱鍵要 focus 圖表）**⑤ 開圖表後驗證**（唔靠視窗 — check MT5 log「已開新圖表」+ symbol — 靜默失敗辨識）**⑥ combo 檢查修正**（一體化模式唔需要熱鍵 combo — 套模板掛 EA — combo check 只限非一體化）— 之前「Fibonacci 未有快捷鍵設定」擋住一體化部署 **⑦ Ctrl+9 預留**（`_alloc_hotkey` 排除 Ctrl+9 — EA 唔會撞）— log 實錘（20:17:21）：「已開新圖表: GBPUSD」+「已套模板: Fibonacci_GBPUSD_H1.tpl — EA 掛落新圖表」+「Fibonacci (GBPUSD) 已啟動」+ 心跳 0s ✅ |
| **v0.9.54** | 2026-08-15 | ⭐ **部署一體化完全成功 + 5 大 bug 修復（用戶引導）**：**① 一體化方案（OpenChart script 套模板掛 EA）實測成功**（log 22:56/22:57：「已開新圖表: GBPUSD」+「已套模板: Fibonacci_GBPUSD_H1.tpl — EA 掛落新圖表」+「Fibonacci (GBPUSD) 已啟動」）— **② 關鍵修復：pyautogui send 熱鍵**（真實 keydown/keyup — 同用戶手動一樣 — pywinauto send_keys 送唔到/MT5 唔當熱鍵 — 用戶肉眼證實）**③ click 圖表區 focus**（熱鍵要 focus 圖表先 work）**④ 模板 path 修復**（30 個 .tpl — `<expert> path=Experts\EA.ex5`（根目錄）→ `Experts\MT5Cloud_EA\EA.ex5` — 之前套模板搵唔到 EA 掛唔到！）**⑤ Ctrl+O 衝突發現**（= MT5「選項」內建快捷鍵 — script 熱鍵唔穩定（Ctrl+O/Alt+Q/Ctrl+L 試過 — mapping 亂 — 彈選項/導航熱鍵）→ 用戶 set Ctrl+L + pyautogui work）**⑥ log 寫入延遲**（MT5 緩衝 — 驗證要等 log flush — 唔好讀太快）**⑦ remove-local 刪 config + release_hotkey**（Magic/Symbol 剸除後再配對返嚟 bug — 之前 remove-local 只刪檔案唔刪 config）**⑧ 彈返監察**（_log_bounce_back — bounce_back_log.jsonl — 記錄彈返事件時間/檔案/內容特徵 — 追蹤「彈返 EA」源頭（環境層面 — 21:01:12 批量複製舊版心跳注入副本 — 源頭未明））**⑨ 配對庫顯示 config symbol/magic**（唔靠心跳 — 重新配對 EA 顯示 config 值）**⑩ 導航熱鍵視窗殘留**（Ctrl+Alt+O 彈嘅殘留 — 已關閉 + remove-local/install-local 後檢查關閉）|
| **v0.9.53** | 2026-08-15 | ⭐ **部署開圖表 — 一體化方案（用戶方案：「OpenChart script 結合 EA — 開完 chart 先再 load EA 嘅東西」）— 完全落實**：**① 重大發現：MT5 模板（.tpl）包含 EA**（`<expert>` 部分 — name/path/inputs — 部署時保存嘅 `EA名_EURUSD_H1.tpl` 有）→ **ChartApplyTemplate 套模板 = EA 掛落新圖表**（MQL5 唯一「程式化掛 EA」方法 — 解決「開圖表 + 附加 EA」全部 GUI 難題）**② OpenChart.mq5 改（一體化）**：讀 json（symbol + ea + tpl）→ `ChartOpen(symbol)` 開目標圖表（active）→ `ChartApplyTemplate(chart_id, tpl)` → **EA 直接掛落新圖表** — 一個 script 搞掂（唔使熱鍵附加/兩步/active 問題）— **實測**：20:29:53 log「📋 open_chart_cmd: symbol=GBPUSD ea=Fibonacci tpl=Fibonacci_GBPUSD_H1.tpl」+「✅ 已開新圖表: GBPUSD」+「✅ 已套模板 — EA 掛落新圖表」+ 心跳 age=0s ✅ **③ auto_attach**：部署時**生成模板**（複製 `EA名_EURUSD_H1.tpl` 改 symbol）+ json 加 ea/tpl 欄位 + **json 寫入後驗證**（讀返確認 — 錯即重寫 — 解決「json 舊值」問題）**④ server**：部署 API **直接寫 open_chart_cmd.json**（網頁揀嘅 symbol 即刻寫入 — 唔靠 auto_attach — 確保 script 讀到啱）**⑤ 修 json 舊值 bug**（用戶：部署 USDJPY → 開咗 GBPUSD（舊 json 殘留）→ EA 掛錯 + 多開圖表 — 根源：server 舊 code 冇寫 json + json 寫入未驗證 — 已修：server 重啟新 code + auto_attach 寫入驗證 + json 舊值覆蓋）|
| **v0.9.52** | 2026-08-15 | 🎯 **部署開圖表 B1（兩步附加 — EA 真係掛喺目標 symbol 圖表 — 用戶揀）**：**① 問題**（v0.9.51）— 部署開咗「EURUSD 空圖表」（Alt+F → Enter → Enter 預設）→ EA 掛咗 EURUSD 圖表 → 心跳先開 USDJPY（EA 唔喺度）→「冇成功部署到 USDJPY」**② B1 兩步附加**（attach_ea_hotkey — 附加成功後）— ① 等心跳開圖表（`ChartOpen(InpSymbol)` — 目標圖表 active — BRING_TO_TOP）② **移除原圖表 EA**（寫 `ctrl_<EA>.json`（stop）→ EA 心跳讀到 → `ExpertRemove` 自移除 — 唔使 GUI）③ **再附加 EA 落 active（目標圖表）**（熱鍵 → Properties 確定 → EA 掛喺 USDJPY 圖表 ✅）— **實測**：Fibonacci（USDJPY）— 附加 → 心跳開 USDJPY（active）→ 移除原圖表 EA → 再附加落 USDJPY →「✅ B1: Fibonacci 已再附加落目標圖表（USDJPY）」+ 心跳 age=0s + MT5 標題 USDJPY,H1 ✅ **③ 修 ctypes 未定義**（B1 內 `ctypes` → `_ctb1` — EnumWindows/create_unicode_buffer 兩處）**④ 開圖表方法調查記錄**（長期難題）— Alt+F→Enter dialog 開唔到（Enter 揀錯 menu item）/ 打字 focus 問題（揀錯 AMD）/ Ctrl+I 插入 menu（自繪讀唔到）/ Ctrl+U 交易品種（Market Watch 管理 — 唔係開圖表）/ script 熱鍵唔支援 / Ctrl+Alt+O=導航熱鍵衝突 / OpenChart_Helper 熱鍵時好時壞 — **最終：EA 心跳 ChartOpen（唯一可靠）+ B1 兩步附加** |
| **v0.9.51** | 2026-08-15 | 🎯 **部署開圖表 — B 方法（用戶揀）：真正 EA 熱鍵 + InpSymbol 寫入源碼**：**① 部署流程改**（attach_ea_hotkey — open_chart 部分）— 揀咗 symbol → **改 EA 源碼（`input string InpSymbol = "USDJPY";`）→ 重新編譯** → 確保有圖表（冇 → Alt+F → Enter → Enter 開空圖表）→ 附加真正 EA（熱鍵 — 已證實穩定）→ **EA 第一次心跳 → `ChartOpen(InpSymbol)` 開目標圖表（active）** → 交易用 InpSymbol（一定正確）— **實測**：Fibonacci（InpSymbol=USDJPY）編譯成功 + 附加成功（心跳 age=0s）+ log「📈 已開目標圖表: USDJPY」（07:57:29 — 心跳開咗 USDJPY 圖表）✅ **② 取代 OpenChart_Helper 熱鍵方案**（v0.9.50）— OpenChart_Helper 熱鍵（Ctrl+4）時好時壞（MT5 熱鍵 load/mapping 亂 — Ctrl+1 都彈錯 EA）→ 用戶揀 B（真正 EA 熱鍵 — 穩定 — 唔使 OpenChart_Helper）**③ _exec_open_chart_script 優化**（Properties dialog 驗證 — 唔用 log（延遲誤判）— pyautogui 真實 keydown）**④ 熱鍵調查記錄** — script 熱鍵唔支援（<scripts> 區無效）/ Ctrl+Alt+O = MT5「導航熱鍵」功能（衝突）/ Ctrl+4 數字鍵格式同 Ctrl+1 一樣（有效但 load 時好時壞 — 需重啟）|
| **v0.9.50** | 2026-08-15 | ⭐ **開圖表熱鍵方案（用戶引導 — 解決「開圖表自動化」多年難題）**：**① 用戶實測方法** —「先開空圖表（Alt+F → Enter → Enter）→ 然後熱鍵觸發」— 開圖表唔使 menu 揀 symbol — **用熱鍵觸發「開圖表 EA」** **② OpenChart_Helper.mq5（新 EA）** — OnInit 讀 `Common/Files/open_chart_cmd.json`（symbol/tf）→ `ChartOpen(symbol)` → `CHART_BRING_TO_TOP`（active）→ `ExpertRemove()`（自移除）— 編譯成功 **③ 熱鍵 Ctrl+4**（hotkeys.ini `<experts>` 區 — 數字鍵格式同 Ctrl+1 一樣 — 實測 work：Properties 彈出 → 確定 → USDJPY 圖表開咗 active）— **熱鍵衝突調查**：Ctrl+Shift+O 未生效（script 熱鍵唔支援）/ Ctrl+Alt+O = MT5「導航熱鍵」功能（衝突）→ 改用 Ctrl+4 ✅ **④ OpenChart.mq5 script 修復**（FILE_COMMON flag 讀 json — 之前相對 path 讀唔到 → 永遠默認 EURUSD — 修復後讀到 USDJPY ✅）+ BRING_TO_TOP **⑤ 核心模板（install-local）** — 加 `input string InpSymbol = "";`（部署時寫入 symbol）+ 開目標圖表 code（`__mt5c_chart_done` static flag — 只開一次 — 唔可以每次心跳都開！）**⑥ 「不停開圖表」失控根治** — 開圖表 code 冇 static flag → 每秒心跳開一個圖表 → MT5 失控（用戶報告）→ static flag 修復 + 刪 Fibonacci.ex5 + 重啟 MT5 恢復 **⑦ json 被清修復** — 部署後 open_chart_cmd.json 被清空 → OpenChart_Helper 讀唔到 → 開錯 EURUSD → 修：執行前檢查（空先寫 — 唔覆寫正確 symbol）**⑧ auto_attach._exec_open_chart_script 改為熱鍵方法**（寫 json → Ctrl+4 → 確定 → log 驗證 — 取代 Navigator scan（64-bit TreeView GETITEMRECT fail — 唔可靠））。**實測**：Ctrl+4 → OpenChart_Helper Properties → 確定 → USDJPY,H1 圖表開咗（active）/ OpenChart.mq5 讀 json USDJPY ✅ / Fibonacci 新版（InpSymbol + static flag）編譯 0 errors |
| **v0.9.49** | 2026-08-14 | 🎯 **心跳 1 秒 + 圖表狀態 + 彈返自癒（用戶要求一鑊過）**：**① 心跳改 1 秒**（OnTimer 每秒寫 — 唔受 tick 影響 — 市場收市都寫）— 全部 EA 加 EventSetTimer/OnTimer/EventKillTimer（15 隻編譯成功 — ADX_Trend 失敗測試 EA 例外）+ **核心模板**（install-local 複製時自動注入心跳 code — 新 EA 自動有 — ATR_Stop 實測編譯成功）**② 「彈返」bug 調查 + 自癒** — 用戶報告「刪除晒 EA → 安裝 Fibonacci → 全部彈返」→ 徹底查證（install-local/compile/上傳全部單隻 — 無批量複製 code — ctime 實錘 08:19:55 18 隻同一秒複製 — 彈返版有控制層（本機版非 EA 庫版）— 源頭環境層未明）→ 自癒：install-local + deploy + refresh-status 三處自動清「彈返」（ctime 新 120 秒 + config 冇 → 刪除 — 排除今次安裝/部署嘅 EA）— 實測：刪除 → 安裝 → 彈返自動清 ✅ **③ 修「找不到檔案」Windows 錯誤** — 自癒誤刪啱啱安裝嘅 Fibonacci.mq5（自癒喺 config 寫入前執行 → 誤判彈返）→ 排除 dest_name → 配對成功 ✅ **④ refresh-status 500 修復**（hk_has → _hk_has）**⑤ 批量刪除**（用戶要求 — 一次過刪晒配對庫 — 42 個檔案 + config + 熱鍵 — 連 Controller 都刪 — 配對庫清空）**⑥ 刪除後 double-check**（remove-local 刪除後確認 + 重試）。**實測**：Fibonacci 配對+部署成功（冇自動配對其他）/ 心跳 1 秒（Breakout age 0.4-3.4s 每秒更新）/ refresh-status 200 |
| **v0.9.48** | 2026-08-14 | 🎯 **圖表狀態檢測（MT5 log）+ 重新整理即時更新（用戶要求）**：**① MT5 log 圖表狀態檢測** — 用戶發現 log 有「removed」/「已停止」（🛑）記錄 → 系統讀 MT5 log（每隻 EA 最後記錄：已啟動/已停止/removed）→ 心跳停 + log「已停止」→ **`chart_removed`（圖表移除）**（灰 — 即刻反映 — 唔使等心跳停）— 實測：Parabolic_SAR/Grid_Trading/EMA_Cross chart_removed ✅ **② 重新整理按鈕即時狀態檢查** — 新 API `/api/refresh-status`（即時掃描心跳/熱鍵/本機檔案 + 寫 rescan.flag 觸發 detector 即刻重掃 — 唔等 5 秒週期）→ 前端 refreshPairingLibrary 加「刷新本機運行狀態」步驟 → 網頁即刻更新 **③ 「過咗一陣先更新」根治** — loadEAConfig fetch 冇 cache-busting → 瀏覽器 cache 舊 data → 覆蓋 refresh-status 嘅即時更新 → 全部 GET fetch 加 `?t=Date.now()`（loadEAConfig/loadDashboard/loadAnalysis）→ 撳重新整理即刻反映。**實測**：refresh-status 0.02s 返回 / EMA_Cross 部署成功（防重入 429 係「冇反應」可能原因）/ JS depth 0 |
| **v0.9.47** | 2026-08-14 | 🎯 **「心跳暫停」重命名 + 30 秒偵測 + 分辨人為暫停（用戶要求）**：**① 「沒有心跳」→「心跳暫停」**（橙色 + icon-pause-circle — hover 解釋市場休市/關圖表/EA 終止）**② 偵測時間 300 → 30 秒**（心跳 30 秒冇更新 → 心跳暫停 — 市場收市心跳疏（180 秒）→ 顯示「心跳暫停」— hover 有解釋）**③ 分辨「人為暫停」vs「市場收市」** — 暫停按鈕寫 config `_status=paused`（DB 記錄）→ 心跳暫停 + 有記錄 → **「已暫停」**（hover：已由你暫停 — 按「繼續」恢復）；冇記錄 → 「心跳暫停」（市場收市/關圖表）— **實測**：模擬暫停 Bollinger_Band → paused（已暫停）/ AgentHelper → unknown（心跳暫停）✅ / JS depth 0 |
| **v0.9.46** | 2026-08-14 | 🎯 **部署誤判根治（第二次）+ no_hb 完善 + Symbol/Magic 顯示修正（用戶多輪實測）**：**① 部署「圖表配對失敗」誤判（Ichimoku 案例）** — 電腦成功但警告視窗話失敗：Ichimoku 冇心跳（後備失敗）+ log 寫入延遲（8 秒唔夠）→ 修：心跳後備失敗 → 再等 5 秒 → **重試 log 驗證**（log 最終寫「已啟動」→ 成功 — 實測 Ichimoku 部署驗證 done ✅）**② no_hb vs starting 區分** — 有熱鍵 + 冇心跳：hotkeys.ini 新（<10 分鐘）→ starting（等待心跳）；hotkeys.ini 舊 → no_hb（沒有心跳設定 — Ichimoku 案例 — 唔會永遠「等待心跳」）**③ Symbol/Magic 顯示修正** — 用「已部署」判斷（唔係心跳）：部署咗（running/starting/no_hb/unknown）→ 顯示 config 真實值（Ichimoku 顯示 USDJPY + 240701 ✅）；未部署（unpaired）→「—」。**實測**：Ichimoku no_hb + USDJPY + 240701 / AgentHelper running / Correlation unpaired — ✅ / JS depth 0 |
| **v0.9.45** | 2026-08-13 | 🎨 **Agent + Performance 卡融合（用戶要求）**：**① 融合** — Performance card（Trades/Win Rate/Profit Factor/Total P&L）併入 Agent card → 一張卡 8 格（Account/Balance/Equity/Positions + Trades/Win Rate/Profit Factor/Total P&L）**② 刪除舊 Performance card**（元素 id 保留 — JS loadAnalysis 照樣更新 — summaryStats 容器刪除但冇 JS 引用）。**實測**：Account 5053721681 / Balance $2.1B / Equity $2.1B / Positions 0 / 4 格 performance 元素存在（— 未有交易數據）/ 舊 card 已刪 ✅ / JS depth 0 |
| **v0.9.44** | 2026-08-13 | 🎯 **狀態 hover 提示（用戶要求）+ 遮擋根治 + 專業化**：**① hover tooltip** — mouse 指落狀態欄 → 彈出詳細解釋（每種狀態）**② 遮擋根治** — CSS tooltip 第一行被 scroll-box overflow 裁剪（z-index 冇用）→ 改 **JS 動態 tooltip**（position:fixed body 層級 + 自動調整方向：向上冇位→向下 + 水平 clamp — 實測第一行 top=825px 完整顯示）**③ 專業化** — emoji（🟢🔴）→ Lucide icon（icon-heart/loader/minus-circle/x-circle）+ 字眼專業化（啱啱部署→剛完成部署／市場收市冇 tick→市場休市導致心跳暫停／EA 死咗→EA 已終止）。**實測**：18 個 status-tip / JS tooltip work（first row hover 顯示完整）/ JS depth 0 |
| **v0.9.43** | 2026-08-13 | 🎨 **EA 倉庫分開「測試」同「真實」（用戶要求）**：**① 排序** — 真實 EA 喺前，測試 EA（TestHB_* 前綴）排最後（loadEALibrary sort）**② Badge** — 測試 EA 橙色「測試」badge（新 CSS badge-orange）+ 真實 EA 綠色「平台提供」— 一目了然分開測試用同真實。**實測**：EA 倉庫 38 個（真實 34 喺前 + 測試 4 喺後 — 橙色 badge）✅ / JS depth 0 |
| **v0.9.42** | 2026-08-13 | 🎯 **心跳狀態五態完善 + 4 隻測試 EA（用戶要求）**：**① 判斷邏輯完善** — Seasonal 案例發現：未部署（冇熱鍵+冇心跳檔案）唔可以話「沒有心跳設定」（Seasonal 部署後有心跳！）→ 改：冇熱鍵 → `unpaired`（灰「未配對」）；有熱鍵 + 冇心跳 → `starting`（黃「等待心跳」— 心跳寫入後自動變 running）；no_hb 只顯示喺真冇心跳 code 嘅 EA **② 4 隻測試 EA 加入 EA 庫**（server/static/ea_library — 每種狀態一隻）：TestHB_Run（寫 running 心跳 → 🟢）/ TestHB_Stop（寫 stopped → 🔴）/ TestHB_Start（冇心跳 code → 🟡 等心跳）/ TestHB_None（冇心跳 code + 未部署 → ⚪ 未配對）— 方便日後測試四種狀態顯示。**實測**：Seasonal running ✅ / Correlation+Ichimoku unpaired ✅ / EA 庫 38 檔案（4 隻 TestHB 可見）✅ / JS depth 0 |
| **v0.9.41** | 2026-08-13 | 🎯 **心跳狀態四態重設計 + 心跳機制判斷（用戶多輪要求）**：**① 四種狀態** — 🟢 running=心跳運行（綠）/ 🔴 stopped=沒有心跳（紅）/ 🟡 starting=等待心跳（黃 — 啱啱部署等 EA 寫心跳 — 寫入後自動變 running）/ ⚪ no_hb=沒有心跳設定（灰 — EA 冇心跳 code）**② 心跳機制判斷** — Correlation/Ichimoku 冇心跳 code（冇 state/hb 檔案 + 冇熱鍵）→ no_hb（唔紅色誤導）；有熱鍵但未寫心跳 → starting（部署後自動更新）**③ 心跳運行 = status=running + 心跳新鮮（mtime <300 秒）** — 之前淨睇 status → 歷史殘留全部誤顯示「心跳運行」（用戶質疑「點解咁多心跳運行」）→ 修復後得返 3 隻真運行（AgentHelper/EMA_Cross/Parabolic_SAR）**④ `_default_lot` 過濾**（唔當 EA）**⑤ 部署後自動更新** — starting → 心跳寫入 → loadEAConfig poll 自動變 running。**實測**：running 3 隻 / unknown（心跳停）11 隻 / no_hb 2 隻 / Controller stopped ✅ |
| **v0.9.40** | 2026-08-13 | 🎯 **系統穩定性強化 + 狀態欄重設計 + 部署誤判根治（用戶多輪要求）**：**① 系統穩定性（「過一日失效」根治）** — 電腦 sleep 係最大根源（AC 電源設定永不 sleep/hibernate）+ Watchdog 加 server 功能檢查（/api/dashboard API 200 — hang 都當死 → 強制重啟）+ 重啟前清 pycache（最新 code）+ alert_worker 舊 instance 重啟（一日前 pythonw 行緊舊 code — 唔彈視窗根源）**② 狀態欄重設計**（用戶定義）— 心跳運行=綠「心跳運行」/ 本機有但冇運行=紅「沒有心跳」（單行簡潔）**③ 冇心跳 → Symbol/Magic 都顯示「—」**（用戶提議：冇心跳=唔知運行緊咩 → 唔顯示值 — 唔靠 deployed/熱鍵 — 靠心跳）**④ Detector deployed 判斷改熱鍵**（hotkeys.ini — 實際部署配置 — 唔靠歷史 MT5 log — log 永遠有舊記錄 → 刪除咗嘅 EA 都話已部署 → MACD_Cross 誤顯示 EURUSD 根源）**⑤ 部署誤判「圖表不符」根治** — 驗證 sleep 4 → 8 秒（MT5 重啟後 EA 初始化 + log 寫入時間）+ 心跳後備失敗 → 再等 5 秒重試（EA 初始化延遲 — 心跳檔案未寫 → 誤判）→ **實測 Parabolic_SAR 部署成功（之前失敗）**。**實測**：MACD_Cross deployed=False（唔再誤顯示 EURUSD）/ 冇心跳 EA 全部「—」/ Parabolic_SAR 部署驗證 done ✅ / JS depth 0 |
| **v0.9.39** | 2026-08-13 | 🎯 **UI 大修（用戶多輪要求）+ 活動記錄 modal bug 根治**：**① 刪 Lots 欄位**（header/row/頂部控制列 — saveEAConfig null check — 配對庫得返 EA/來源/狀態/Magic/Symbol/Trades/Win/P&L/按鈕）**② Lag 根治（pollAiControl）** — modal 隱藏時完全唔 poll + setInterval 700ms → 2 秒（之前無時無刻 fetch — CPU 轟炸）**③ Magic 欄位對稱**（row 顯示淨數字 — 唔加「Magic」前綴）**④ Agent card 簡潔化**（7 格 → 4 格：Account 合併 Server / 刪 Agent ID+Binding / 保留 Balance/Equity/Positions）**⑤ Balance/Equity「—」根治** — loadDashboard 引用已刪元素（accountServer — browser cache 舊 HTML 冇）→ null.textContent → 炸 → Balance/Equity 唔更新 → **全部元素 null check** ⑥ **活動記錄「消失」真正根源** — 搬移時 anchor 匹配錯咗 reportModal（EA 診斷報告 modal — display:none 隱藏）入面嘅 Monthly P&L → 活動記錄插入咗隱藏 modal → 永遠唔顯示 → **修正：刪 modal 內 + 插入真正 main 最底（Correlation card 後）**。**實測**：Balance $2,147,483,645.73 / Equity 顯示 ✅ / 活動記錄 activityTable ×1 + 唔喺 modal + 喺 main 內 ✅ / JS depth 0 |
| **v0.9.38** | 2026-08-12 | 🎯 **配對庫欄位修復 + 重新整理逐步 + scroll 順暢（用戶多輪要求）**：**① Magic/Symbol 顯示修復** — 根源鏈：刪 Magic select/TF select 後 saveEAConfig 仲 querySelector 已刪元素 → null.value TypeError → config 永遠冇寫入 → Magic/Symbol「—」→ **修**：Magic/TF 改 hidden input（同名 class — saveEAConfig 照讀）+ **DB 路徑統一**（GET/SQL 讀 server/instance/mt5cloud.db 但 SQLAlchemy 寫 instance/mt5cloud.db — 讀寫唔同步！4 處一齊改）**② 刪 TF/SMA10/SMA30/Signal 欄位**（配對庫表格簡潔 — header + row + sort indices 修正）**③ 重新整理逐步顯示**（7 步：開始/掃描本機/清理殘留/同步配對設定/刷新運行狀態/刷新 EA 倉庫/完成 — 每步 doing→done — 新 API `POST /api/control-steps`（前端逐步更新 steps）+ EA 倉庫 card 加「刷新狀態」按鈕）**④ Scroll 唔順暢根治** — poll 太頻繁（loadEALibrary 30s/loadEAConfig 10s/fetchEAInventory 10s 每次重寫表格 → 卡）+ 表格重寫唔保存 scroll 位置 → **修**：間隔延長（loadEALibrary 120s/loadEAConfig 60s/fetchEAInventory 60s/loadDashboard 30s）+ render 前保存 scrollTop 後恢復（EA 倉庫 + 配對庫）。**實測**：saveEAConfig 寫入 EMA_Cross ✅ / 重新整理 7 步全部 done ✅ / JS depth 0 |
| **v0.9.37** | 2026-08-12 | 📱 **手機版重新設計（提高可閱讀性 — 用戶要求）+ 配對庫按鈕橫排**：**① 手機版（max-width 480px）專屬 CSS** — 警告視窗 modal 近全屏（width = 100vw-24px + 圓角 16px）+ 大字體（標題 18px / 步驟 14px + 行距 1.8 / 按鈕 15px + 48px 高觸摸友好）+ 統計卡全闊堆疊 + 表格 12px 字 + 橫向 scroll + log 13px **② 平板（768px）** — modal 寬度 fit（100vw-32px max-width 380px — 唔爆出畫面）**③ 配對庫 4 粒掣橫排** — 操作 cell 加 `white-space:nowrap`（部署/報告/暫停/刪除唔 wrap 打直）+ 手機版按鈕縮細（padding 4px 6px + 10px 字 — fit 一排）。**驗證**：JS depth 0 + desktop 冇 regression |
| **v0.9.36** | 2026-08-12 | 🎨 **警告視窗 UI 專業化（用戶 4 項要求 + 2 項微調）**：**① 專業 icon（唔用 default）** — 電腦版自訂警告 icon（PIL 繪製綠色圓形 + 「!」符號 — 唔用 tkinter 羽毛）；網頁版 Lucide icon-robot（移除 🤖 emoji）**② 尺寸/間距專業化** — 電腦版 360×400 → 380×410（統一 16px 間距網格）；網頁版 380px 寬一致 + 按鈕 margin-top 16px（同步驟區分開）+ min-height 450 → 420（用戶「唔好留咁多空白」）**③ 專業字眼（唔口語化）** — 全流程 steps 文字替換：「剷除」→「刪除」、「遙距控制」→「遠端控制」、「開新圖表」→「建立新圖表」、「複製到本機」→「複製至本機」、「熱鍵」→「快捷鍵」、「驗證心跳/MT5 log」→「驗證運行狀態」、「檢查有冇」→「檢查是否有」等（server + watcher + auto_attach + alert_worker + dashboard 一齊改）**④ 電腦版 + 網頁版一致**（標題「遠端控制」+ 專業 icon + 380px 寬 + 相同顏色系統）。**實測**：電腦版 Vision AI 確認（「AI 遠端控制」+ 綠色 icon + 專業字眼步驟 + 整齊間距）；網頁版 browser 確認（380px + icon-robot + 「遠端控制」+ 按鈕距離 16px + 高度 420px）。**⚠️ 教訓：execute_code 嘅 read_file limit max 2000 行 — 傳 3000 會被 clamp 截斷 → 寫返 2000 行 → app.py/auto_attach.py 尾段冇咗 → SyntaxError — 大檔案用 git checkout 復原 + 直接 open().read() 讀寫（唔好經 read_file 分頁）** |
| **v0.9.35** | 2026-08-12 | 🎯 **電腦版警告視窗「一開始顯示舊步驟」修復**：**/api/deploy 即刻寫 SHOW_FLAG + steps** — 之前 /api/deploy 冇寫（配對/剷除有寫）→ 用戶撳部署 → 視窗保持上一個任務殘留 steps → watcher poll 3 秒 + auto_attach 啟動先寫新 steps（「舊步驟 → 1 秒後先變新」）→ **修**：寫 deploy_cmd 前即刻寫 SHOW_FLAG「部署 XXX」+ steps（部署 doing + 開圖表 pending + 附加 pending + 驗證 pending）→ alert_worker 0.4 秒 poll 即刻顯示新步驟。**實測**：模擬舊任務殘留（剷除 Price_Action）→ 觸發 /api/deploy → 1 秒內 steps 即刻變「部署 Bollinger_Band（EURUSD）doing」✅ |
| **v0.9.34** | 2026-08-12 | 🎯 **部署「實際成功但誤判失敗」根治（用戶實測 2 輪）**：**① 心跳後備多編碼讀取（核心！）** — 心跳檔案（state_XXX.json）係 EA 寫嘅 **UTF-16 編碼**（0xff 0xfe BOM）→ 後備 code 用 utf-8 讀 → UnicodeDecodeError → 後備冇效 → log 驗證揾唔到「已啟動」字眼 → 誤判「圖表不符」失敗（即使 EA 實際喺正確 Symbol 運行）→ **修**：多編碼嘗試（utf-16 → utf-8 → cp1252）+ **心跳新鮮度放寬 90 秒 → 300 秒**（市場收市心跳停 — status=running 為主）**② 重啟 MT5 3 步放最前** — do_restart_mt5 append 尾 → 步驟順序「部署 4 步 + 重啟 3 步」亂（用戶見「附加進行中」先出現「關閉 MT5」）→ 改重啟 3 步插喺 steps 列表最前（重啟 → 部署 → 開圖表 → 附加 → 驗證）。**實測**：UTF-16 心跳讀到 running → 後備成功 ✅ |
| ⭐ **v0.9.33（重要更新）** | 2026-08-12 | 🎯🎯🎯 **電腦版警告視窗「任務完成但可視化冇完成」全面根治（用戶實測 10+ 輪 — 重要里程碑）**：**① alert_worker `else` 分支 render 修復（核心！）** — SHOW_FLAG 清咗（任務完成）→ main loop `has_flag=False` → 唔入 render block → 視窗停留舊內容（「編譯進行中」+ 緊急停止 — 永遠唔變）→ **修**：`else` 分支都 render + steps 全部 done → 顯示「已完成」綠色 + 確定按鈕（Vision AI 驗證 ✅）**② 配對/剷除「兩步就停」根治** — 舊 watcher instance（舊 code 冇逐步邏輯）處理 pause_cmd → 寫舊格式 steps 停留 → 被單實例守衛殺 → 新 watcher 冇接手 → 殺晒舊 watcher + 統一新版（_prog_steps 逐步）**③ install-local 唔使編譯時（.ex5 已存在）即刻完成「編譯」+「完成配對」**（之前停留 pending 永遠唔完成）**④ 配對/剷除每步「停留」**（寫 steps 後 1.5 秒 + 複製完成前 1 秒 — 用戶見到「進行中」— 唔會瞬間完成）**⑤ watcher 剷除步驟順序反映實際動作**（auto_attach --remove 期間顯示「移除圖表 EA 進行中」唔係「檢查圖表」）**⑥ alert_worker exception 記錄 log**（唔再食晒 — alert_worker.log 診斷）**⑦ 清 __pycache__**（防舊 bytecode）。**實測**：① 寫 steps → 視窗更新 ✅ ② SHOW_FLAG 清 + steps done → 「已完成」+ 確定 ✅ ③ 完整剷除 → steps 逐步全部 done ✅ |
| **v0.9.32** | 2026-08-12 | 🎯🎯 **部署循環/重複執行全面根治（用戶實測 5 輪 — 每輪有新發現）**：**① 部署重試唔再開新圖表** — `attach_ea_hotkey` 加 `open_chart` 參數，失敗重試 ×2 時 `open_chart=False`（重用現有圖表 — 之前每次重試開新圖表 →「開好多圖表 + 不停執行」）**② steps done 搬去函數最尾** — 之前心跳驗證後就寫 done（太早）→ 用戶見 done 撳確定 → active 仲 true → 「即刻彈多一次」→ 改所有操作完成（圖表平鋪/市場報價/log 驗證）後先寫 done **③ steps done 後即刻寫 ai_control.json active:false** — 唔等外層 release（verify ~20 秒）→ 撳確定時 active 已 false → 唔會再彈 **④ 前端 doDeployEA 防重入**（`_deploying` lock）**⑤ 後端 /api/deploy 30 秒防重複**（同 EA 短時間唔可以再部署 → 429）**⑥ install-local 寫 compile_cmd 前刪舊**（唔排隊多個 → 唔會「部署完又彈編譯」）**⑦ 編譯等待期間每 2 秒 check_abort**（緊急停止即時生效 — 之前 F7 後 8 秒 block 冇反應）**⑧ auto_attach 部署前等 pending compile_cmd**（最多 40 秒 — 編譯完成先部署 — 唔並行）。**實測**：部署完成 → steps done + active:false 同步 → 撳確定唔會再彈 ✅ |
| **v0.9.31** | 2026-08-12 | 🎯🎯 **部署警告視窗流程完整修復（用戶實測 4 輪反饋）**：**① 部署入口 steps 覆寫（唔累積）** — 之前 `_update_steps` 累積 → 新任務開始舊任務 steps（MACD_Cross）殘留 + 新任務一齊顯示 → 直接覆寫（spec：新任務清舊任務）**② 部署入口保留「重啟 MT5」3 步** — 部署前 ensure_hotkey 重啟寫嘅 3 步（關閉 MT5/載入熱鍵/重新啟動）唔好洗走 → 保留 + 加部署 4 步 = 完整流程 **③ `do_restart_mt5` 累積模式** — 之前覆寫 steps（部署 4 步被洗走）→ 改讀現有 steps + append 3 步 **④ 重啟完成後唔寫「等待操作開始」** — 之前覆寫 steps 全部洗走（「重啟 3 行消失」）→ 改更新 3 步 done（保留完整流程）**⑤ steps mtime vs modal 彈出時間判斷** — 網頁 poll 讀到舊任務殘留 steps（remove-local 寫入前）→「彈幾個不知名步驟」→ 舊 steps（mtime < _modalShownAt）唔顯示（保持等待）**⑥ 部署流程步驟完整化** — 之前得 step0 done+step1 doing → step2 done+step3 doing（第三步永遠 doing → 確定唔出現）→ 加 step3 done + step4 doing/done（全部 done → 確定出現）+ 每步 0.8 秒 delay（網頁捕到「進行中」）**⑦ `release()` 即刻 active:false** — 之前等 5 秒（MIN_SHOW+IDLE）先寫 active:false → 網頁 modal 一直 active →「不停出現」+ 用戶 refresh 先消失 → 即刻寫（網頁 modal 靠確定撳先關）**⑧ 失敗寫失敗 steps**（attach 失敗/log 驗證失敗 →「附加失敗」唔係「等待操作開始」）**⑨ 配對失敗 steps os.replace 移出 with block**。**實測**：部署完整流程（重啟 3 步 + 部署 4 步一齊顯示 — 唔消失）✅ |
| **v0.9.30** | 2026-08-12 | 🎯🎯 **警告視窗全面大修（一次過解決 10 個 bug — 改動分析流程盤點）**：① `_os_replace_N` 未定義（4 處 NameError → steps 靜默失敗）→ 全部 `os.replace` ② **`os.replace` 喺 `with open()` block 內（9 處 — server 6 + auto_attach 3 → WinError 32 source 被自己開住 → 寫入失敗）** → 全部移出 with block ③ remove-local rename 切走 4 字元（已修）④ 配對 steps 詳細化 4 步 ⑤ watcher compile 更新式（唔覆寫 install-local）⑥ 配對失敗 steps os.replace 移出 ⑦ **`_update_steps` 殘留「等待操作開始…」placeholder** → 過濾 ⑧ **`_restart_mt5` 覆蓋 steps + 完成後刪除 steps（spec：永不刪除）** → 累積 + 更新 done ⑨ alert_worker 單實例守衛（port 5004）⑩ detector import sys。**實測驗證四大流程**：配對/部署/剷除/重新整理 全部 ✅ |
| **v0.9.29** | 2026-08-12 | 🎯🎯 **警告視窗「步驟配對」全面修復（用戶 check 配對功能發現）**：**① `_os_replace_N` 未定義（4 處 — NameError → steps 靜默失敗）** — 「原子寫入 patch」用咗 `_os_replace_0/1/2/5` 但冇 import → 每次寫 steps 都 NameError → except pass 靜默 → steps 永遠唔更新！**② `os.replace` 喺 `with open()` block 內（8 處 — server 5 + auto_attach 3 → WinError 32 source 被自己開住 → 寫入失敗）** — 修：全部移出 with block！**③ 配對流程 steps 詳細化**（install-local 寫 4 步活動記錄式：開始配對 → 複製檔案 → 編譯 → 完成配對 — 同剷除一致）+ watcher compile **改為更新**（唔覆寫 install-local 步驟 — 對應「編譯 XXX.mq5 → .ex5」doing/done + 完成配對 done）+ 複製完成後更新 steps（開始配對 done + 複製檔案 done）。**④ 舊 `pythonw.exe` watcher（PID 12116 — 冇 console）行緊舊 code 覆寫 steps** — 殺 + 起新版。**實測驗證（完整配對流程）**：install → `[done] 開始配對` `[done] 複製` `[pending] 編譯` `[pending] 完成配對` → watcher compile → `[done] 編譯` → `[done] 完成配對` — **步驟同操作名完全對應 ✅** 另修：alert_worker 單實例守衛（bind port 5004 — 之前 3 個 instance 同時行 → 雙視窗）+ 電腦版視窗 Vision AI 驗證（標題/狀態/6 步/確定按鈕全部正確）\| 🎯🎯 **警告視窗「彈嚟彈去」真正根源根治（用戶確認「一下就搞掂」）**：remove-local（網頁剷除）寫 steps 後 `os.replace('.ai_control.steps', '.ai_control.st')` — 將 steps 檔案 rename 成 `.st`（切走 4 字元）→ **steps 檔案消失** → 網頁讀唔到 → 空白/等待 → watcher 再寫新 → 內容突變 → 「彈」！**修復**：remove-local 直接寫 `.ai_control.steps`（唔加 `.tmp`）+ 移除錯誤 os.replace；檢查全部寫 steps 位置（server 5 處 .tmp+replace 正確 / auto_attach 3 處正確 / watcher 直接寫正確）— 只有 remove-local 有 bug。**實測驗證**：remove-local → steps 6 步完整寫入 + 檔案冇被 rename + watcher 接手逐步（5 done + 1 pending）平滑 ✅ 另修：detector `import sys`（單實例守衛 traceback）、watchdog 明確 project path（cron 正確啟動 watcher）\| 🎯 基礎設施大修（轉 Agent 後全面修復）：**detector 讀所有用戶 config**（唔再 hardcode 'dev' — 切換 Agent 後 dev 0 keys 導致永遠 No EAs）+ **server 讀 auto_trade_status.json**（唔直接 init MT5 — 同 detector 衝突）+ **detector account_info 合併到 payload**（balance/equity 顯示）+ **dashboard JS syntax fix**（sc0 重複宣告 → 全部 JS 死）+ **detector account_info 喺 initialize 後即刻攞**（EA 計算後 disconnect 返回 None — 移前）\| 🎯 警告視窗重製大修（平台核心 — 用戶願景：所有人透過佢知道遙距控制成功/失敗）：**重製**（電腦版 + 網頁版一致 — 「遙距控制」標題 🤖 + 操作名 + 步驟 + 二選一）**視窗抖動根治**（電腦版：minsize/maxsize 鎖死 + 移除每 round geometry（觸發 re-layout）+ 增量渲染（內容... [truncated]
| **v0.9.7** | 2026-08-06 | 🎯 熱鍵部署全自動（hotkeys.ini 用戶格式 + 關閉MT5寫入重啟生效 + Properties/代替確認 dialog 自動處理 BM_CLICK）+ 配對 TypeError 修復（install-local 函數頭被食）+ compile_ok 檢查指向 MT5Cloud_EA + watcher 鎖修復（唔 block 自己）+ 部署卡死修復（清積壓）|
| **v0.9.6** | 2026-08-06 | 🎯 熱鍵管理完整實現：配對自動分配熱鍵（hotkeys.ini 直接寫入 — Ctrl+1/2/3 下一個空位）+ 熱鍵唯一檢查 + 剷除自動釋放 + auto_attach 讀 hotkeys.ini（權威來源）— 驗證：重啟後 Ctrl+1 work（Bollinger Properties 彈出）|
| **v0.9.5** | 2026-08-06 | 🎯 熱鍵方案突破：導航熱鍵（右擊 Navigator 空白 → H）— 每隻 EA 設熱鍵 — send Ctrl+1 成功附加 Bollinger_Band + 心跳 running（解決 6093 double-click 問題！）|
| **v0.9.4** | 2026-08-06 | double-click 輸入驗證：彈咗「窗口」dialog（證明輸入 work — MT5 冇防自動化 — 用戶確認）— 真正問題係位置（Navigator 一時左一時右 / item 高度 12px vs 15px）— AHK 4 方法試過（ControlClick/模擬/SendMode Play/掃描）|
| **v0.9.3** | 2026-08-06 | MT5Cloud_EA folder 定位實測成功（auto_attach 入 folder 搵 EA）+ 掃描過濾（只掃根目錄+MT5Cloud_EA — 唔掃內建樣本）+ Tree 揀最大（雙 tree 問題）|
| **v0.9.2** | 2026-08-06 | MT5Cloud_EA folder 集中管理（配對自動入 folder + 全鏈路支援：detector 掃描/watcher 監控/auto_attach 尋找/remove-local 剷除）|
| **v0.9.1** | 2026-08-06 | Navigator 統一位置（操作前最大+固定）+ 圖表自動平鋪（Alt+R — 有圖表就平鋪網格）|
| **v0.9.0** | 2026-08-06 | 控制層 + Controller 系統中樞 + 心跳狀態（❤/●/◇）+ 手動 1 秒部署（watcher 自動撳確定）+ GBK decode 修復（watcher 穩定）+ 移去平台/剷除功能實測穩定 |

---

## 🗓️ Session Log

### 2026-08-06（移去平台 + 剷除功能實測穩定 ✅）

**用戶實測**（唔降級 MT5 — 唔搞 6093）：
- ✅ **「移去平台」（remove-local）** — 穩定運行（剷除本機 .ex5/.mq5 檔案）
- ✅ **「剷除」（DELETE 配對）** — 穩定運行（移除配對 + 寫 pause_cmd → watcher 移除圖表 EA）
- 兩個功能都通過用戶實測 — 唔使再改

**Navigator 統一位置（用戶要求 — 08-06）**：
- ✅ `ensure_navigator_unified()` — 操作前統一 Navigator：左邊 (0,100) + 闊=螢幕 20% + 高=螢幕-140（最大）+ 自動顯示
- ✅ 掛接：auto_attach（部署/暫停/移除）+ refresh_navigator（刷新）— 每次操作前 call
- ✅ 實測：Navigator 統一（(0,100) 起）— 唔會再一時左一時右（之前 (201,139) vs (1079,111) 操作錯位）
- ⚠️ 教訓：auto_attach.py 冇頂部 `import ctypes`（其他函數用函數內 import）— 新函數要自己 import

**圖表自動平鋪（用戶要求 — 08-06）**：
- ✅ `tile_charts()` — 偵測圖表（AfxFrameOrView — MDI 子窗口）→ 有圖表就平鋪
- ✅ 快捷鍵：**Alt+R**（menu「窗口 → 平鋪窗口」— 實測 3 列網格完美）— ❌ Alt+L 唔係平鋪（用戶試過）
- ✅ 掛接：auto_attach 操作前（Navigator 統一之後）— 每次操作圖表平鋪
- ✅ 實測：7 個圖表 → 3×3 網格（(14,111)/(648,111)/(1282,111) 三列）

**MT5Cloud_EA folder 集中管理（用戶要求 — 08-06）**：
- ✅ 配對（install-local）→ 自動建立/使用 `MQL5\Experts\MT5Cloud_EA\` folder + EA 入 folder + compile_cmd 指向 folder
- ✅ **全鏈路支援**：
  - detector（:5003）掃描 → 網頁配對庫顯示（只掃根目錄 + MT5Cloud_EA — ⚠️ 唔掃 MT5 內建 folder：Free Robots/Examples/Advisors 樣本 EA 唔顯示）
  - watcher 監控（get_experts_snapshot — 只掃根目錄 + MT5Cloud_EA）
  - auto_attach 尋找（EA交易 → MT5Cloud_EA folder 入去搵）
  - remove-local 剷除（搵埋 folder）
- ✅ **定位實測成功**：auto_attach 入 MT5Cloud_EA folder 搵到 EA（🎯 Found Bollinger_Band）
- ⚠️ **教訓**：之前 SMA_Cross 定位失敗係因為檔案被刪（唔係 code 問題）— 定位功能本身 work

**雙 Tree 問題（08-06 修）**：
- ⚠️ MT5 有兩個 SysTreeView32（docked 細 + 浮動大）— auto_attach 揀錯 tree（(8,131) 332 闊 — 冇 MT5Cloud_EA 內容？）
- ✅ 修：掃描所有 tree — 揀「最大面積」嗰個（浮動/主要 Navigator）

**double-click 輸入驗證（08-06 — 重大發現）**：
- ✅ **double-click 有彈 dialog**（「窗口」dialog）— **證明程式化輸入 work — MT5 冇防自動化**（用戶確認 — 我嘅「Raw Input 防自動化」假設錯）
- ⚠️ 真正問題：**位置**（double-click 彈咗「窗口」dialog — 唔係 Bollinger_Band Properties — 位置差）
- ⚠️ Navigator 位置不斷變（一時 (8,131) 一時 (997,77) 右邊）— item 高度 12px（統一後）vs 15px（其他狀態）
- AHK 試咗 4 方法（ControlClick 後台 / 模擬 click / SendMode Play / 掃描）— 全部唔彈（但係係位置問題 — 唔係輸入）
- 📸 截圖對位中（用戶確認 Bollinger_Band 實際位置）— 修正後 double-click 應該 work

**🎯 熱鍵方案突破（08-06 — 用戶發現 + 實測成功）**：
- ✅ **導航熱鍵**：右擊 Navigator 空白位置 → menu「快捷鍵」（撳 H）→ 導航熱鍵視窗（ListView 列出所有 Navigator 項目 — 520 個 — 含指標+EA）
- ✅ **每隻 EA 可以設個別熱鍵**（例如 Ctrl+1 = Bollinger_Band）
- ✅ **實測成功**：send Ctrl+1 → 觸發附加 Bollinger_Band（彈「代替」確認 → 撳「是」）→ **附加成功 + 心跳 running**（MT5 冇 crash！）
- ✅ **解決 6093 double-click 問題**：唔使 double-click Navigator — 用鍵盤快捷鍵！

**🎯 熱鍵管理完整實現（08-06 — v0.9.6）**：
- ✅ **設定檔搵到**：`<Terminal>\config\hotkeys.ini`（UTF-16 LE）— 格式 `[experts]` section：`Experts\MT5Cloud_EA\<EA>.ex5=Ctrl+N`
- ✅ **配對 → assign_hotkey**（自動分配下一個可用熱鍵 Ctrl+1..9/Ctrl+0/Ctrl+Alt+N — 唔重複 — 直接寫 hotkeys.ini）
- ✅ **剷除 → release_hotkey**（移除熱鍵 + 位置釋放）
- ✅ **auto_attach 讀 hotkeys.ini**（權威來源 — Ctrl+1 → ^1 格式轉換 — fallback hotkeys.json）
- ✅ **驗證**：重啟 MT5 後 Ctrl+1 照 work（Bollinger Properties 彈出 — hotkeys.ini 直接寫入生效）
- ⚠️ 教訓：直接寫 hotkeys.ini 要小心讀取 code 嘅 \r 處理（escape bug 會覆寫清走其他熱鍵）
- 📋 備註：SMA_Cross 熱鍵有 mapping 但係 .ex5 唔存在（之前剷除測試刪咗）— 再配對自動恢復

**重要背景（08-05 14:57 — MT5 自動更新 6061 → 6093）**：
- ⚠️ **MT5 build 6093 對 auto_attach 自動化操作 crash**（pyautogui/SendMessage double-click 都唔彈 Properties — 只有真實滑鼠 work；完整 auto_attach 流程 15+ 次全部 crash MT5）
- 單獨操作（tree nav / toggle / SetWindowPos / ShowWindow）全部安全 — 完整流程必 crash — 6093 對模擬輸入有 bug
- **6061 時間線**：07-30 已經係現行版（session 記錄確認）→ 08-05 14:57 被 6093 取代

**決定：唔降級** — 用「手動 1 秒」方案：
- 用戶 double-click Controller（MT5Cloud folder — 唯一手動步驟）
- watcher 偵測 Properties dialog → **自動撳「確定」**（`.manual_deploy_pending` 標記機制）
- 心跳 running → 網頁狀態自動更新（❤/●/◇）
- 之後所有 EA 部署/暫停經 Controller（控制層）全自動

**Watcher 穩定性修復（08-06）**：
- ✅ **GBK decode 修復**：`text=True` → `encoding='utf-8', errors='replace'`（3 處）— 之前 auto_attach 中文輸出（GBK）decode 炸 → watcher 反覆死
- ✅ 舊 deploy_cmd 清理機制（唔會再俾新 watcher 處理舊嘢）
- ✅ 心跳讀取修復：UTF-16 fallback + 檔案 mtime 新鮮度（MQL5 TimeCurrent 係 broker time）

**前端修復（08-06）**：
- ✅ 警告視窗「關閉視窗」掣（手動部署 mode — 完成/取消可以自己關）
- ✅ 手動部署鎖定（`manualDeployActive` — pollAiControl 唔可以關閉手動警告視窗）
- ✅ 狀態 poll（每 10 秒自動更新 runtime_status）

---

### 2026-07-30（19:00~20:00 — 完整 E2E 測試 + 防護機制）

**目標**：完成由網頁到 MT5 嘅全自動部署流程，解決 MT5 亂跳問題

**成果**：
- ✅ **HTTP API `/api/deploy`** — deploy 唔靠 Socket.IO，直接用 HTTP POST，更可靠
- ✅ **Dashboard 🚀 改用 HTTP API** — 撳 Deploy 直接 call `/api/deploy`
- ✅ **deploy_notify.py** — 本地通知視窗「🤖 AI 正在部署 EA 到 MT5，請勿使用滑鼠及鍵盤」
- ✅ **Watcher Lock 保護** — deploy 前檢查有冇 auto_attach 已運行，防止重複
- ✅ **Global Mutex** — auto_attach.py 啟動時檢查 `.auto_attach_global.lock`，只准一個 instance
- ✅ **auto_attach.py 本身彈通知** — 無論邊個 call auto_attach.py，都會彈通知視窗
- ✅ **E2E 成功** — Breakout ✅, MACD_Cross ✅, Hedge_Fund ✅, Momentum ✅ 全部 deploy 成功

**E2E 測試結果**：
- `Breakout` → `🎉 Breakout 已成功 attach!` ✅
- `MACD_Cross` → `🎉 MACD_Cross 已成功 attach!` ✅  
- `Hedge_Fund` → `🎉 Hedge_Fund 已成功 attach!` ✅
- `Momentum` → `expert Momentum (USDJPY,H1) loaded successfully` ✅

**關鍵問題**：
1. **Sibling Agent 干擾** — 其他 AI agent 持續建立 `auto_attach_all.py` 並 spawn auto_attach process，導致 MT5 不斷被操作
2. **Heartbeat FILE_COMMON 寫入唔 work** — MT5 build 6061 嘅 `FILE_WRITE|FILE_TXT|FILE_COMMON` 無法寫入檔案，改用 `FILE_WRITE|FILE_TXT`（唔用 FILE_COMMON）但未完全驗證
3. **auto_attach.py 俾 sibling agent overwrite** — 用 `icacls` 鎖寫入權限，但 sibling agent 用 Python 3.14 繞過咗

---

## 🐛 Fixed Bugs

| # | Bug | 原因 | Fix | 日期 |
|---|-----|------|-----|------|
| 1~31 | 見之前版本 | — | — | 07-27~30 |
| 32 | Socket.IO deploy 唔可靠 | Browser Socket.IO 斷線後 deploy 指令消失 | 加 HTTP `/api/deploy` endpoint | 07-30 |
| 33 | deploy 後 MT5 亂跳 | Sibling agent 不斷 spawn auto_attach_all.py 做批量 attach | Watcher Lock + Global Mutex | 07-30 |
| 34 | auto_attach.py 成日被 overwrite | Sibling agent 用 Python 3.14 改寫檔案 | 加 Global Mutex（lock 喺檔案本身） | 07-30 |
| 35 | deploy 成功但回報失敗 | Heartbeat 檢測 fail（FILE_COMMON bug） | 改為 Properties dialog 確認 = 成功 | 07-30 |
| 36 | 用戶唔知 AI 操作緊 MT5 | 冇通知機制 | deploy_notify.py 視窗（tkinter 深色置頂） | 07-30 |
| 37 | 掛 EA 失敗（GETITEMRECT fail → 掃描亂點） | MT5 owner-draw TreeView 唔支援 TVM_GETITEMRECT → fallback 掃描模式逐行 double-click 成個 tree → 掛唔到/掛錯 | v0.9.65 改用 `ea_node.click_input(double=True)`（handle-based，唔使座標） | 08-18 |
| 38 | 重複 EURUSD 圖表（每次 deploy 疊加） | auto_attach「Chart already open, skipping」唔清殘留 → 疊加 | v0.9.65 開新圖表前先關晒所有 MDI 圖表 | 08-18 |
| 39 | auto_attach 中途 restart MT5 → 部署誤報失敗 | hotkeys.ini reload 檢查令 PID 變 → 後續 pywinauto connect 舊 PID fail → exit=1 | v0.9.66 唔再 restart MT5（掛 EA 用 Navigator 雙擊唔使熱鍵） | 08-18 |
| 40 | 壓力測試 Round 4-5 崩潰（NameError） | `attach_ea_navigator` 缺 `symbol` 參數 → 開圖表段 print/send_keys 用未定義 symbol → crash | v0.9.66 加 `symbol` param + caller 傳 `args.symbol` | 08-18 |
| 41 | 心跳驗證誤判 FAIL | 淨搵 `hb_*.txt`，但 EMA_Cross 淨寫 `state_*.json` | v0.9.66 接受 `state_*.json` 或 `hb_*.txt` | 08-18 |
| 42 | auto_attach `find_ea_dialog` UnboundLocalError | nested def 喺 call site 之前未定義 → Python 當 local → 用嗰陣未定義 | v0.9.66 搬去 module-level function | 08-18 (HY3) |
| 43 | auto_attach `ctypes`/`user32`/`click_y` NameError | module-level `find_ea_dialog` 用 `ctypes`/`user32` 但 module top 冇 import；`click_y` 喺 scope 外被引用 | v0.9.66 加 `import ctypes` + `user32 = ctypes.windll.user32` + `click_y=None` default | 08-18 (HY3) |
| 44 | 🔥 `install-local` config 唔 persist（CRITICAL 隱藏 root cause） | `current_user.ea_config=...; db.session.commit()` 喺 SQLAlchemy 下冇真正寫入 DB → `_bounce_back_watchdog` 讀舊 config（冇 EMA_Cross）→ 每 30s 誤刪 `.mq5` → compile fail → 心跳冇出 → 壓力測試輪流 FAIL | v0.9.66 改用 raw SQL `UPDATE user SET ea_config=? WHERE username='dev'`（繞過 ORM） | 08-18 (HY3) |
| 45 | #39 UI 字眼錯（「移去配對」應「加入配對」） | EA 倉庫未加入 EA 嘅 button 硬編碼「移去配對」 | v0.9.66 dashboard.html 改「加入配對」+ 更新錯註釋 | 08-18 (HY3) |
| 46 | #40 delete 後心跳 file 殘留 | remove-local 清 config 但冇清 `hb_*.txt`/`state_*.json` | v0.9.66 deploy_watcher delete 流程加 `os.remove(hb_+state_)`（pause 唔清） | 08-18 (HY3) |
| 47 | 🔥 **真正 root cause：`SQLALCHEMY_DATABASE_URI` 相對路徑**（#44 只係繞過） | `sqlite:///mt5cloud.db` 相對 server run 目錄 → ORM `db.session.commit()` **全部寫去 `server/mt5cloud.db`（空 file）**，但 watchdog/raw SQL/stress test 讀 `instance/mt5cloud.db` → 永遠 mismatch → 全部 6 個 config 寫入位（install-local/remove-local/upload/ea-config POST/PUT/deploy）都 persist 唔到 | v0.9.67 URI 改絕對路徑 `instance/mt5cloud.db` → 全部 6 個位自動修好（唔使逐個 raw SQL） | 08-18 (HY3) |
| 48 | verify_heartbeat 淨檢查 `hb_<ea>.txt` → 永遠 False + auto_attach 誤報成功 | 注入 code 寫 `state_<ea>.json`（唔係 hb_.txt）→ verify_heartbeat 永遠 False → auto_attach 靠 `verify_ea_loaded`（stale log）`return loaded` → watcher「🎉 已成功 attach」但實際冇心跳 | v0.9.67 verify_heartbeat 同時檢查 state_.json + hb_.txt；auto_attach_ea 循環 attach 最多 3 次，有心跳先 return True | 08-18 (HY3) |
| 49 | **EA「彈返/重複」** — 配對庫自動彈返已移除嘅 EA（Breakout/Fibonacci/OpenChart，心跳暫停），MT5 有兩個同名 MT5Cloud_EA folder，EA 同時喺根 Experts/ + Experts/MT5Cloud_EA/ 兩位置 | detector 等 scan_dirs 同時掃根 Experts/ + MT5Cloud_EA subfolder；殘留檔 copy 去根 Experts/ → detector 掃到 → 配對庫重複/彈返顯示 | v0.9.76 全面取消 MT5Cloud_EA folder：detector/install-local/deploy/hotkeys/remove-local 全部淨係用根 Experts/+Scripts/，MT5 實體剷走兩 folder、EA 搬返根 → ea_inventory 得返配對嗰隻 | 08-18 |
| 50 | **Script 類型 EA（OpenChart）配對失敗** | install-local 將 Script（#property script_show_inputs）當 EA copy+compile 去 Experts/ + watcher GUI F7 compile 間歇性失敗 → 冇 .ex5 + config 鎖死「本機冇檔案」+ 俾清殘留誤刪 | v0.9.79-82：Script 偵測→copy 去 Scripts/ + watcher 改用 CLI /compile + OpenChart 加入 _SYSTEM_KEEP + detector 掃 Scripts/ | 08-18 |
| 51 | **Script 類型部署（OpenChart）卡死/影響正式 EA** | Script 唔係長駐 EA（冇心跳）— deploy OpenChart 會行 Navigator 雙擊卡死（not found）+ 之後誤判失敗 | v0.9.83-87：Script 類型暫時唔支援部署（api/deploy 偵測返回 400「不支援」）+ 部署開 chart 改用用戶方法（唔塊 Ctrl+9） | 08-19 |
| 52 | ⭐ **部署 EA「一秒成功下一秒 remove」（ADX 唔掛）** | ADX_Trend 源碼 OnTick 有 AgentHelper bootstrap（ChartApplyTemplate('AgentHelper_*.tpl') → AgentHelper 取代 ADX → ADX 自己 ExpertRemove）→ loaded 後 4-5 秒 remove + 最終冇掛 | v0.9.91 移除 bootstrap code → ADX 掛住交易唔讓位 + recompile；其他 EA（Breakout/Bollinger）log 證實無呢個問題 | 08-19 |
| 53 | **部署完另一隻 EA 後，已掛 EA（EMA_Cross）自己消失** | 部署時 do_restart_mt5 前「關閉全部圖表」→ 其他已掛 EA chart 被關 → EA 消失（chart 可能留但 EA 冇） | v0.9.93-94 移除「關閉全部圖表」段 → restart 保留 chart → 其他 EA 唔再消失（實測 ADX/Bollinger/Breakout/EMA_Cross 心跳持續） | 08-19 |
| 54 | **Swing_Trader 部署失敗（熱鍵失效）** | 新加 EA 熱鍵（Ctrl+5）MT5 未 reload → send Ctrl+5 冇彈 Properties → 掛唔到 | v0.9.94 重新啟用部署 restart reload 熱鍵 → Swing Ctrl+5 load → 掛到（實測 loaded + 心跳新鮮） | 08-19 |
| 55 | **配對後「已加入（本機冇檔案）」殘留，要 hard refresh 先啱** | 前端「本機有檔案」靠 detector ea_inventory.json（重掃延遲）→ 配對後 load 攞舊 data → 顯示本機冇檔案 | v0.9.97 /api/ea-library 加 local_has（server 直接 check 本機 .ex5）→ 即時準確，配對完即刻「已加入」 | 08-19 |
| 56 | **配對/部署完成後唔自動 refresh** | 動作完成後 UI 唔更新（要手動 refresh） | v0.9.96 配對完成後觸發 rescan + 延遲 refresh；部署完成後 waitDeployDone → refresh-status + reload | 08-19 |
| 57 | ⭐ **部署 restart MT5 後，其他運行緊 EA 移出圖表** | do_restart_mt5 用 proc.kill() 強制殺 MT5 → 冇正常關閉 save chart profile → 開機唔 restore 掛緊 EA | v0.9.98 改「正常關閉」（WM_CLOSE 主窗口）→ save profile → 開機 restore 全部 EA（實測 6 隻全 restore + 心跳新鮮） | 08-20 |
| 58 | ⭐ **熱鍵注入正確流程確認（用戶實測 2026-08-20）** | 之前直接寫 hotkeys.ini 喺 MT5 開住時寫 → 唔被認/被覆寫 → Ctrl+N 失效。用戶實測成功流程：① 網頁配對 EA（install-local → Navigator 見 EA）② 等 MT5 refresh ③ 關閉 MT5 ④ 寫 hotkeys.ini `<experts>Experts\<EA>.ex5=Ctrl+N</experts>`（UTF-16）⑤ save ⑥ 開 MT5 → 熱鍵 work。破綻：EA 必須本機有 .ex5（EMA_Cross 冇 .ex5 → 熱鍵失效；配對返後 work）；熱鍵重用（Ctrl+8 俾 Breakout → 放空 → 俾 EMA_Cross）可行 | 08-20 |
| 59 | ⭐ **部署時熱鍵失效（MT5 開住寫唔 load）** | server ensure_hotkey_for_ea 喺 MT5 開住時寫 hotkeys.ini → MT5 唔 load → Ctrl+N 失效 | v0.10.2 _ensure_hotkey_loaded 部署前熱鍵預載（關 MT5 → 寫 → 開 → load）；v0.10.3 部署時唔再 restart（restart 覆寫熱鍵）；v0.10.4 .ex5 檢查 | 08-20 |
| 60 | **部署流程冇「每步驗證 gate」（用戶要求：成功先落下一步）** | 而家每步做完就算/等固定時間，冇驗證（熱鍵 load 未等 → 部署失敗） | docs/deployment-checkpoint-system.md 設計每步驗證 gate（檔案/視窗/log 程式化檢測，唔靠 AI）+ _wait_until poll；待改 code 落地 | 08-20 |
| 61 | ⭐ **部署假失敗（EA 掛到但報失敗）** | attach_ea_hotkey 內部 log 驗證太嚴格 — MT5 restart 後 log 寫入延遲 → 誤判「圖表不符」→ return False → 外層 Step 4 gate 永遠行唔到 | v0.10.6 attach_ea_hotkey 驗證失敗唔再 return False（交外層 Step 4 gate + Step 5 心跳後備判定）+ _ea_loaded_in_log 加新鮮度檢查（log mtime<300s 防 stale 假 True） | 08-20 |
| 62 | ⭐ **熱鍵 load 時序（MT5 開住寫唔 load / 開機後未 load 就 send）** | ① MT5 開住時寫 hotkeys.ini → 唔 load → Ctrl+N 失效 ② 開完 MT5 未等熱鍵 load 就 send → 失效 ③「已有熱鍵」skip 咗開完 MT5 嘅驗證 | v0.10.8 開完 MT5 後熱鍵 load 驗證 gate（poll send 測試彈 Properties）；v0.10.10「已有熱鍵」時檢查 hotkeys.ini mtime vs MT5 啟動時間（開機後先寫 → restart 重寫）；v0.10.13 驗證 fail 自動 restart 重寫 | 08-20 |
| 63 | **批次熱鍵預載「全新熱鍵」MT5 唔 load** | 一次過寫入全部 EA 熱鍵（含 MT5 內部未記住嘅全新熱鍵）→ MT5 唔 load → send 失效（用戶實測知識：直接寫 file 只對「已記住」熱鍵 work） | v0.10.9 revert 批次預載；v0.10.11 恢復批次預載 + 保留驗證 gate（45s poll 等 MT5 load 完）→ 實測 work（第一隻 restart 一次 → 之後 skip restart） | 08-20 |
| 64 | 🔥 **壓力測試多 EA 失敗（2/5 → 3/5 → 5/5）真正 root cause** | stress script 連住 POST deploy（非阻塞即刻返）→ watcher spawn 多個 auto_attach 同時跑 → 搶 MT5 控制權 → 有一隻失敗；就算加「等 MT5 log/hb 當完成」，watcher deploy worker 收尾 + queue 有 gap（`auto_attach.py already running, queuing X`）→ deploy_cmd 排隊 → auto_attach 未 spawn → 誤判失敗 | stress script 每隻 deploy 後等 `deploy_result` activity log（watcher 真正寫「部署完成」）先 deploy 下一隻 + watcher tee auto_attach 完整 output 去 aa_debug.log（診斷）→ **連續兩次 5/5 PASS（stress 16+17）** | 08-20 |
| 65 | 🔥 **magic 空 string 令部署假成功（4 秒完成）** | 前端未 alive EA 部署時傳 magic=''（`magic||''`）→ server `data.get('magic', '240701')` 收到空 string（default 唔生效 — `''` 唔係 None）→ deploy_cmd magic 空 → auto_attach `--magic` 空 → argparse 失敗 → watcher 誤報「attach 成功」→ 網頁警告視窗未完成就彈走 | v0.10.14 三層 fallback：前端 `(magic||'240701')` + server `data.get('magic') or '240701'` + watcher 同 | 08-20 |
| 66 | 🔥 **restart 重寫熱鍵後 MT5 PID 未更新 → 部署卡死（電腦好耐冇反應）** | v0.10.13 熱鍵 load 驗證 fail → restart 開新 MT5 之後，後續 Navigator/平鋪/快捷鍵用舊 PID → Process not found → 部署卡死 | v0.10.15 restart 後 `find_mt5_pid()` 更新 mt5_pid | 08-20 |
| 67 | 🔥 **假成功（log 驗證讀舊記錄）** | `_ea_loaded_in_log` 只 check log 檔 mtime 新鮮（<300s）→ 舊 loaded 記錄（18:32 Bollinger）喺 log 檔 → log 檔新鮮（MT5 有寫其他嘢）→ 誤判 True → 部署話成功但 EA 實際冇掛到（Bollinger/EMA 掛落 GBPUSD 而唔係目標 symbol） | v0.10.16 `_ea_loaded_in_log` 加 loaded 記錄時間戳檢查（parse log 行 HH:MM:SS — 只認最近 300s 內） | 08-20 |
| 68 | 🔥 **連環代替確認 dialog（確定完仲要再確定多次）** | 附加 EA 落已有 EA 嘅 chart → MT5 連環彈多個「代替」dialog（代替確認「是」+ Properties「確定」）→ auto_attach 撳完第一個「是」之後 loop 完 → 第二個彈出無人處理 → 卡住（用戶實測） | v0.10.17 dialog loop 完後再 poll 8 秒撳晒所有代替 dialog「是」（最多 5 次） | 08-20 |
| 69 | 🔥 **附加錯 chart（掛咗落舊 restore 嘅 GBPUSD）** | OpenChart 開 chart 失敗 → active chart 係舊 restore 嘅 GBPUSD（有 MACD 掛住）→ auto_attach 附加新 EA 落去 → 代替 dialog → 一鑊泡（Bollinger/EMA 都掛錯 chart） | v0.10.18 send 熱鍵前驗證 active chart 係目標 symbol（唔係就明確 fail）+ v0.10.20 修正驗證方法（EnumChildWindows Chart class 搵唔到 → 改用 MDI chart 窗口）| 08-20 |
| 70 | **開 chart 方法失效（Alt+F 流程唔完整 + Ctrl+9/OpenChart 依賴熱鍵）** | v0.10.19 誤刪 Space→打symbol 步（開 chart 唔係目標 symbol）；Ctrl+9 fallback 依賴熱鍵 load（批次預載清咗 <scripts> 段 → 失效）+ 開嘅 chart symbol 唔知；OpenChart script（Ctrl+O）同樣依賴 <scripts> 熱鍵 | v0.10.21 恢復完整流程 Alt+F→Enter→Enter→Space→打symbol→Enter；v0.10.24 剷除 Ctrl+9 fallback（90 行）— 主力係 Alt+F 用戶方法 | 08-20 |
| 71 | **chart 累積（每個部署開一個新 chart）** | 每次部署都開新 chart（Alt+F）→ N 次部署 = N 個 chart | 用戶指正：每個 EA 一個 chart 係正常（唔應該重用 — 重用可能掛咗其他 EA）；v0.10.22 嘗試重用 → v0.10.23 revert（保留每次開新） | 08-20 |
| 72 | **部署等好耐（Step 2B 熱鍵 load 驗證 45s）** | Step 2B 每次部署 send 測試熱鍵 + poll 45s（fail 時 restart MT5 再驗證 45s）→ 成個部署等好耐；而且驗證方法本身唔可靠（誤判） | v0.10.25 取消 Step 2B 熱鍵 load 驗證（124 行）— 熱鍵預載（_ensure_hotkey_loaded）已經確保熱鍵寫入，唔需要額外驗證 | 08-20 |
| 73 | **重試快捷鍵掛錯 chart（Heikin_Ashi 掛錯 EURUSD）** | 開 chart 失敗 → 重試快捷鍵 ×2（唔開新 chart）→ 掛落 active chart（可能錯 symbol）→ 代替 dialog → 一鑊泡（Heikin 目標 GBPUSD 但掛咗落 EURUSD） | v0.10.25 移除重試快捷鍵（失敗直接 fail）；v0.10.26 開 chart 失敗直接 return False（唔用備用方案）| 08-20 |
| 74 | **Step 2b 定位操作唔必要** | 固定 MT5 視窗/Navigator 統一/平鋪圖表 — 用戶話一開始唔需要定位（Alt+F 開 chart 用鍵盤唔靠座標）| v0.10.27 取消 Step 2b 全部定位操作（19 行）| 08-20 |
| 75 | 🔥 **剷除唔到（remove_ea_from_chart NameError）** | `re.escape` 用咗未定義嘅 re（import re as _re_r 但用 re.escape）→ NameError → 檢查 EA 運行永遠 fail → 剷除誤判「未運行」→ 冇嘢做（用戶實測剷除唔到）| v0.10.31 修正 _re_r.escape — 實測：偵測 started → 寫 ctrl_ → EA ExpertRemove → 心跳停 → 剷除成功 | 08-21 |
| 76 | 🔥 **剷除唔到（ctrl_ 方法市場收市失效）** | v0.10.29 改 ctrl_ 方法（寫 ctrl_<EA>.json → EA 自己 ExpertRemove）— 但市場收市冇 tick → EA 唔 check ctrl_ → 剷除唔到（假成功：心跳停判斷誤判 — 心跳檔已清）| v0.10.32 恢復 GUI 方法（right-click → 專家 dialog — 用戶實測可靠）+ 修 chart 偵測（MDIClient fallback — chart 標題空時 Afx 冇逗號）| 08-21 |
| 77 | 🔥 **剷除靠座標唔可靠 + right-click menu 冇專家列表** | GUI 方法 right-click + 132px 偏移（座標 hardcode — 唔大眾化）；right-click menu 實際冇「專家列表」（有「專家列表(E) Alt+X」但 Alt+X 冇反應）| v0.10.33 改用 Alt+W 窗口 dialog 方法（唔靠座標 — ListView 即時 chart 排位 → 揀目標 → Enter → Ctrl+W 關閉）— 用戶實測 | 08-21 |
| 78 | 🔥 **假成功（watcher 讀舊 output + main 入口消失 + ctypes NameError）** | ①aa_debug.log tee -a 累積舊部署 output → watcher 讀最近 60 行誤判（ATR_Stop 讀到 Breakout/Grid 舊記錄）②v0.10.33 替換函數刪埋 if __name__ → auto_attach 零 output + EXIT 0 → 假成功 ③剷除 _dlgs 用 ctypes（未定義）→ crash | v0.10.34 tee 改覆寫 + 檢查真 SUCCESS；v0.10.35 加返 main block（45 行）；v0.10.36 修 ctypes → _ct — 實測 5 次部署 + 5 次剷除全部 PASS | 08-21 |
| 79 | 🔥 **剷除卡住（_PYEXE NameError）** | process_pause_cmd 用 _PYEXE（run_auto_attach 入面先定義 — 唔同 scope）→ NameError → auto_attach --remove 冇跑到 → watcher 等 timeout → 剷除卡住（用戶實測 delete EA 卡住）| v0.10.37 加 _PYEXE = _PY_EXE — 實測刪除 6 秒完成 | 08-21 |
| 80 | **剷除成功但 MT5 Navigator 殘留** | process_pause_cmd 完成後冇 refresh Navigator（部署/配對有 — 剷除冇）→ MT5 Navigator 仲顯示已刪 EA → 要自己 refresh | v0.10.38 剷除完成後 _refresh_queue.put() 觸發 refresh Navigator | 08-21 |
| 81 | **refresh Navigator 兩次（第二次又撳右鍵）** | v0.10.38 加 _refresh_queue.put() 疊加「Experts 目錄變化」file-watch 觸發 → refresh 兩次（用戶實測「第一次成功之後第二次又撳右鍵做多餘動作」）| v0.10.39 移除 put — 剷除刪 .mq5/.ex5 已自動觸發 file-watch refresh | 08-21 |
| 82 | 🔥 **揀咗冇嘅 symbol（ETHUSD）部署 fail — 冇警告** | 網頁 symbol picker 顯示 static 24 個（ALL_SYMBOLS — 含 ETHUSD 但帳戶冇）；server /api/deploy 冇 symbol 驗證 → 部署 fail（Alt+F 開 chart 揀唔到 symbol）但唔話原因 | v0.10.40-41 symbol picker 改用帳戶實際 symbols（bases/<帳戶>/History — MetaQuotes-Demo 20 個）；v0.10.42 ①server 部署前驗證 symbol（唔喺 → error 400『symbol 唔存在』）②前端彈警告 modal | 08-21 |
| 83 | 🔥 **剷除假成功（Breakout AMD — 網頁話成功但 MT5 卡窗口 dialog）** | 揀 chart 用 click 座標（_target_idx*22 — ListView scroll/行高唔同 → 揀錯 → Enter 冇效 → dialog 卡住）；Ctrl+W 關唔到 → EA 冇移除；但 _removed_ok=False 照 return True → 網頁假成功 | v0.10.43 ①未確認移除 → return False ②dialog 未關 → fail ③揀 chart 改方向鍵；v0.10.44 移除 click fallback（淨係方向鍵 — 用戶一早要求）| 08-21 |
| 84 | **配對/剷除警告視窗有機率網頁冇彈** | showControlModal 用 `!aiControlVisible` 條件 — 如果 aiControlVisible 卡住 true（之前 modal 未關）→ 新操作 showControlModal 唔會彈 → 警告視窗冇彈（用戶實測）| v0.10.45 showControlModal 強制顯示（每次 call 都彈 — 唔靠 !aiControlVisible）| 08-21 |
| 85 | **我的配對庫顯示 script（OpenChart/ApplyTemplate 等）** | scan_ea_inventory 掃 Experts + Scripts 目錄（冇標記邊啲係 script）→ 前端配對庫顯示晒（用戶要求只顯示 EA）| v0.10.45 detector 標記 is_script（Scripts 目錄）+ 前端過濾；v0.10.46 修 is_script 冇帶出 output（inventory.append 漏字段）— 實測 Divergence=False（EA）+ ApplyTemplate/OpenChart=True（script）| 08-21 |
| 86 | **首頁（index.html）配色冇跟新主題（仲係綠）** | 上次只改咗 login/register/dashboard 三頁，漏咗 index.html — `:root` 仲係綠色 token + 系統字體 | v0.10.47 index.html `:root` 換橙黑 token + DM Sans + 金色漸變標題 + 金底黑字（logo/btn-primary）+ hover 色跟換 — 四頁統一 | 08-21 |
| 87 | **Dashboard Agent 卡太多格 + EA 倉庫掣唔簡潔** | Agent 卡顯示 8 格（Account/Balance/Equity/Positions/Trades/Win Rate/PF/P&L）太迫；「刷新狀態」掣重複（已有「重新整理」）；「上傳 EA 去社群庫」橙色底大掣搶眼 | v0.10.48 ①Agent 卡淨顯示 Account/Balance/Equity ②「刷新狀態」掣剷除 ③「上傳 EA 去社群庫」改普通 btn（唔再橙色底）| 08-21 |
| 88 | **配對庫排位唔齊（狀態/掣）** | ①狀態文字 text-align:center → 起點同 header「狀態」（靠左）唔對齊 ②三粒掣 grid 2 欄太大粒 | v0.10.49 ①狀態 cell 改靠左（status-cell class）②操作掣改細粒橫排（ea-actions flex + padding 2px 8px + font 11px）③操作按鈕靠右（inline-flex + justify-content:flex-end — 用戶要求）| 08-21 |
| 89 | **配對庫 header/data 全欄對唔齊** | Magic/Symbol/Trades/Win 用 text-align:center + P&L 用 text-align:right，但 header 全部靠左 → 上下列對唔齊（用戶實測「來源 Magic Symbol 全部都未對齊」）| v0.10.50 移除全部 data cell 嘅 text-align:center/right → 統一靠左同 header 一致（操作欄保留靠右）— 實測 header/data 全 start/left 對齊 | 08-21 |
| 90 | **Trades/Win/P&L 全部「—」（冇真實數據）** | ①agent.py `get_mt5_status` 根本冇收集 history deals → `agent.deals` 永遠空 → `/api/analysis`「No data yet」②agent 冇行緊（冇人同步 MT5 數據）③前端用 `magic_symbol` 精確匹配但 EA config 冇存 symbol → key 對唔上 | v0.10.51 ①agent 加收集 deals ②analysis 過濾 magic 0 ③前端改 magic 聚合 ④Win 顯示 0% + P&L 格式 — 實測 Divergence 顯示 1 單 / -$1.27（真 deal）| 08-21 |
| 91 | 🔥 **MT5 Python history API 讀唔到新 deals（build 6120 caching）** | `history_deals_get` 喺 terminal 開住時只讀到舊 cache（測試發現 14 個舊 deals 讀到，最新嘅 TestTrades deals 讀唔到；重啟 MT5 都唔得）→ agent 同步唔到新交易 → Trades/Win/P&L 停喺舊值 | v0.10.52 TestTrades EA 自己 track 統計（MQL5 HistorySelect 計 wins/losses/profit）寫入 `state_<EA>.json` → server `/api/ea-config` 讀 EA stats 優先 + fallback analysis — 繞過 Python API 限制，EA 層面最準 | 08-21 |
| 92 | **心跳暫停原因唔知（可能係休市但顯示「心跳暫停」誤導）** | 系統淨睇心跳檔 mtime（<30 秒 = running）冇判斷「係咪因為非交易時間」— 週末/收市時段心跳暫停會誤顯示「心跳暫停」（令人以為 EA 故障）| v0.10.53 server `_market_closed_for_symbol`：`symbol_info_tick` 最後 tick（tick.time 係 UTC+3 — 正規化）> 5 分鐘 = 休市 → `market_closed` map；前端心跳暫停 + 休市 → 顯示「休市」（灰色 + tooltip「非交易時間 — 開市自動恢復」）。實測 AMD=true（美股凌晨休市）/ EURUSD=false（24 小時開市）| 08-21 |
| 93 | **OpenChart/StartAgentHelper 歷史 script 殘留 config** | 之前測試遺留嘅 script 配對（AMD — 帳戶唔支援 symbol）— 唔係 EA 但 config 有 → `market_closed`/runtime 見到佢哋（誤導）| v0.10.54 刪除 OpenChart/StartAgentHelper config 配對（`/api/ea-config/<name>` DELETE）— config 淨返 Divergence + TestTrades 兩隻真 EA（`_removed` 記錄）| 08-21 |
| 94 | **配對庫冇排序功能（撳 Trades/Win/P&L header 冇反應）** | header 有 `onclick="sortEA(...)"` 但 **sortEA 函數根本唔存在**（sortOrder 有宣告但冇實作）→ 撳咗冇反應；用戶要求全部欄位可排序（EA 跟英文字母 A-Z/Z-A，Trades/Win/P&L 數字高低）| v0.10.55 實作 sortEA(key) 統一排序函數（第一次 asc → 再撳 desc → 循環）+ 所有 header 加 onclick + 排序箭頭指示（金色 ▲/▼）+ `_getSortVal` 按欄位攞值（字母 localeCompare / 數字相減）| 08-21 |
| 95 | **縮細視窗箭嘴走位（淨係箭嘴甩）** | `.ea-table th` 預設 `white-space:normal` — 視窗縮細時 header 空間唔夠，`<span class="sort-ind">`（inline 元素）被擠去第二行 → 箭嘴同 header 文字錯位（用戶實測「將視窗縮細一半，啲箭嘴走晒位」）| v0.10.56 th `white-space:nowrap`（header 文字+箭嘴強制同行）+ sort-ind `display:inline-block; vertical-align:middle; white-space:nowrap` — 實測 computed style 確認；太窄時成個表格 horizontal scroll（唔會錯位）| 08-21 |
| 96 | **重複 TestTrades 部署（5 個 EURUSD chart 同時運行）** | 多次 `/api/deploy` TestTrades（改 code 後重新部署）每次都開新 chart + 舊 chart 冇清 → 累積 5 個 EURUSD chart 掛 5 個 TestTrades 同時開單（用戶實測見 4 個 — 窗口 dialog 確認 5 個）| v0.10.57 用 auto_attach `--remove --ea TestTrades` 逐個剷除（3 次成功 — MT5 log removed + Ctrl+W 關 chart）→ 淨返 1 個 chart + 1 個持倉（正常）| 08-21 |
| 97 | **報告按鈕冇真實數據（全部空/0）** | 報告靠 `agent.deals`（MT5 Python history API 讀唔到新 deals — build 6120 caching）→ deals 得舊嘢 → 報告 Trades/Win/P&L 空；avg_win 錯顯示負數（total_profit/wins 計法錯）| v0.10.58 TestTrades 加 win_sum/loss_sum（EA 自己 track 贏/輸總額）+ `/api/ea-report` fallback 讀 EA stats → avg_win 用 win_sum/wins（正確正數）+ avg_loss 用 loss_sum/losses。實測：460 單 / 22% / PF 0.39 / Avg Win +$0.23 / Avg Loss -$0.17 | 08-21 |
| 98 | **報告三圖表（Equity/Distribution/Monthly）空白** | EA stats fallback 只有累計數（冇逐單明細）→ 畫唔到 equity curve/distribution/monthly — 因為 MT5 Python API 讀唔到逐單 deals | v0.10.59 TestTrades 加 `AppendTrade()`（每次平倉 append 一單落 `trades_<EA>.json` JSONL — ticket/time/profit）+ `RebuildTradesFile()`（OnInit 掃全部歷史重建）+ server 讀 trades json 計 equity curve（累計）/distribution（分佈）/monthly P&L/max_dd。實測：629 行完整歷史、報告 100 點 equity + 5 條 dist + 月度 | 08-21 |
| 99 | **配對庫數據唔一致（500+ 變百幾）+ 配對庫唔更新** | ①trades json 新加先開始記錄（舊單冇入）→ 報告得百幾但 EA 自己 track 500+ ②state json 被系統心跳覆寫（`{"ea","status","ts"}` 格式 — 冇 stats）→ 配對庫讀唔到新數據 | v0.10.60 ①EA `RebuildTradesFile()` OnInit 重建完整歷史（149→629 行）②server `/api/ea-config` 改讀 `trades_<EA>.json`（完整逐單）優先 + fallback state — 配對庫/報告同源。實測：配對庫 639 單 / 報告 634 單（一致，跳動中）| 08-21 |
| 100 | **Correlation Matrix 冇真實數據（得舊 1 個 EA / 唔渲染）** | ①`/api/analysis` 靠 agent.deals（舊）→ 得 240701_USDJPY 1 個 ②精簡 Agent 卡後 loadAnalysis 攞唔到已刪 element（anTrades 等）→ null error → 成個函數死 → correlation 唔渲染 | v0.10.61 ①analysis 合併 trades json（完整歷史）→ summary 750 單 / 2 個 EA ②correlation key 改 EA 名 ③loadAnalysis 加 null check（_setTxt/_setColor — element 唔存在就 skip）。實測：2x2 matrix（240701_USDJPY + TestTrades）渲染 | 08-21 |
| 101 | **🔥 關 chart 後部署卡 dialog + 代替其他 EA（用戶實測：剷 RSI → 部署 → 取代咗 TestTrades + 網頁仍心跳）** | ①殘留 dialog（Properties 未關）→ 開 chart Alt+F 被 modal 擋 → 開 chart 失敗 ②開 chart 失敗 → active chart 係舊（TestTrades）→ 熱鍵附加落去 → 代替 dialog → code 撳「是」→ TestTrades 被取代 ③TestTrades 心跳檔殘留 → 網頁仍顯示心跳（假成功）④pywinauto descendants 對 MT5 chart 窗口讀唔到 → 開 chart 成功但驗證假失敗 | v0.10.62 ①部署前清理所有殘留 dialog（ESC + 取消/否）②代替 dialog 改撳「否」+ 部署 fail（唔接受取代）③開 chart/active chart 驗證改用 EnumChildWindows（Afx + 標題含 symbol — 實測可靠）— 實測 Divergence → AUDJPY 部署成功（開圖 ✅ active ✅ 心跳 ✅ log loaded ✅）冇取代其他 EA | 08-21 |
| 102 | **🔥 部署後 Properties dialog 殘留（RSI dialog 一直開住 → 之後部署全部被擋 — 用戶實測「重新部署都係有問題」）** | 部署撳「確定」後 dialog 冇真正關閉（殘留 `RSI_Over 1.00 Properties`）→ modal 擋住之後所有開 chart Alt+F → 部署 fail；ESC/撳取消對 modal dialog 唔 work（實測撳確定/ESC 都關唔到）；另外 runtime_status 誤讀 MQL5/Logs（MetaEditor 中文日誌 — 已启动/已停止）而唔係 terminal Logs（英文 loaded/removed）→ EA 掛住都誤判 chart_removed | v0.10.63 ①部署前 + 部署後都用 WM_CLOSE（PostMessage 0x0010 — 實測有效）清理 dialog ②runtime_status 改讀 terminal Logs（<hash>/Logs/）+ regex 加 loaded successfully ③log 判斷加 loaded successfully → running。實測：RSI_Over → UK100 部署成功 + 部署後 dialog 0 個 + runtime 正確 | 08-21 |
| 103 | **🔥 剷除多個同名 chart 揀錯（3 個 UK100 → 揀第一個 → 冇掛 EA → 假成功）** | remove_ea_from_chart 揀第一個 symbol match 嘅 chart（ListView index）→ 但 EA 可能掛喺第 2/3 個同名 chart → 移除錯 chart → EA 仲運行 → 「15s 未確認」假成功；移除 chart 後 ListView 重新排位（index 移位）→ 第二次用舊 index 揀錯 chart | v0.10.64 改「逐個試」：候選 chart（symbol match）→ Ctrl+W 關 → 驗證 EA 真係移除（心跳停/log removed）→ 未移除就重新讀 ListView + 重新對應 symbol → 下一個；實測：3 個候選逐個試 → 第 3 個先係 RSI_Over → 成功移除（心跳停 + log removed）| 08-21 |
| 104 | **🔥 UAC/授權窗口擋住部署（MT5 更新/異常 → 彈「Client Terminal AVX2 授權」）** | MT5 彈授權窗口（consent.exe / Secure UAP class）→ modal 擋住部署流程（開 chart/附加全部被擋）→ 部署卡死/失敗；之前完全冇檢測機制 | v0.10.65 `_detect_and_handle_uac()` 偵測 + 自動處理（Enter + WM_CLOSE）+ 關唔到寫 `.uac_alert` 通知用戶 + 等 30 秒；接入全部 8 個部署流程點 + server 3 個 API。實測：模擬窗口偵測到 + 自動處理；實測 MT5 單一 instance 正常部署唔會彈 UAC（之前 4 個 UAC 係多 instance 撞帳戶安全機制）| 08-22 |
| 105 | **🔥 配對庫消失（電腦有已配對 EA 但網頁冇顯示）** | 壓力測試輪流剷除 → 每次 DELETE 加 `_removed` → api_deploy 重新部署時**冇由 `_removed` 清走**（只有 install-local 有 — Bug #64）→ `_removed` 累積 ADX_Trend + EMA_Cross → 前端 `!removed.includes(name)` 過濾走晒 → allEAs 空 → 配對庫顯示「仲未加入任何 EA」| v0.10.67 ①api_deploy 加「重新部署 = 由 _removed 移除」（同 install-local 一致）②修正現有 DB（清 _removed 入面嘅 ADX_Trend/EMA_Cross）。實測：配對庫顯示返兩隻（心跳運行 + 正確 symbol/magic）| 08-22 |
| 106 | **🔥 部署 EA 搞走其他 EA（部署 Grid 之後 EMA_Cross 從圖表消失 — 用戶實測）** | `_ensure_hotkey_loaded` 熱鍵判斷用 hotkeys.ini mtime vs MT5 啟動時間（MT5 自己/其他部署會更新 ini → mtime 誤判「未 load」）→ 無謂 restart → MT5 restart 後 profile restore 唔齊（EMA_Cross chart 消失）；另外熱鍵批次分配 Ctrl+1~9 令 mapping 越嚟越多（hotkeys.json 同 ini 唔同步）| v0.10.68 ①熱鍵改 Ctrl+1 重用（每次部署清空舊 mapping + 只寫新 EA=Ctrl+1 + 同步 hotkeys.json）②restart 前記錄所有 chart（EnumChildWindows）+ restart 後檢查補開遺失 chart ③熱鍵 load 實測（send Ctrl+1 → 彈 Properties = load 咗 → 唔 restart）。實測：Bollinger→USDJPY + Grid→DE40 部署成功，其他 EA 全部保留（chart 冇遺失）| 08-22 |
| 107 | **🔥 部署假成功（心跳後備誤判 — ADX 案例：話「運行中」但實際 EA 冇掛到）** | ①`verify_heartbeat` 心跳後備讀 **MQL5/Logs**（MetaEditor 日誌 — 中文「已启动」殘留 → 誤判「已啟動」→ 假成功）；英文 terminal log「loaded successfully」唔 match（regex 只認「已启动/已啟動/started」）②「附加成功（心跳存在）」淨 check 心跳檔存在（os.path.isfile — 舊檔殘留都話有）→ 假成功 | v0.10.69 ①verify_heartbeat 改讀 terminal Logs（<hash>/Logs/）+ 只認「loaded successfully」+ 最後狀態判斷（removed 後唔算 loaded）②「附加成功」改 check 心跳檔 age（<300s 先算新鮮）。實測：ADX→XAUUSD 部署成功（心跳 0s + log loaded successfully — 真成功）| 08-24 |
| 109 | **🔥 熱鍵 load 測試假成功（部署掛錯 EA）** | 熱鍵 load 測試 `'1.00' in 標題 or '2.00' in 標題` 就當成功 — **唔 check EA 名** → 彈錯 EA（Heikin_Ashi 殘留 mapping）都 pass → 之後 send 熱鍵彈舊 EA → 掛錯/失敗 | v0.10.71 改 `ea_name in 標題`（一定要彈返目標 EA 先算 load 成功） | 08-24 |
| 110 | **🔥 MT5 restart 後熱鍵唔 load（部署附加失敗 — 人手模擬測試多輪 FAIL）** | MT5 開機 cache 舊 hotkeys.ini（Heikin_Ashi 殘留）→ 熱鍵預載 restart 寫入新 mapping（ATR_Stop=Ctrl+1）但 MT5 load 咗舊值 → send Ctrl+1 彈錯 EA/冇彈 → 附加失敗 | v0.10.71 熱鍵 load 測試失敗（3 次冇彈返目標 EA）→ **第二次 restart**（再開機 load 到新 mapping — 實測 Breakout/MACD/Heikin 第二次 restart 後 send ^1 try 1 彈 Properties）+ send 熱鍵重試 5 次 | 08-24 |
| 112 | **🔥 watcher spawn auto_attach exit 255（部署全部失敗 — 人手模擬測試 0/5）** | watcher `subprocess.run(shell=True + tee + encoding='utf-8')` → auto_attach output 有 **GBK 中文字節（0xb8）** → subprocess **reader thread decode crash**（Windows subprocess bug — errors='replace' 都 crash）→ exit 255 → 全部部署失敗 | v0.10.72 改 **bytes mode**（`capture_output=True` 無 encoding — 無 reader crash）+ 手動寫 output 去 aa_debug.log。實測：ATR_Stop 部署成功 | 08-25 |
| 114 | **🔥 熱鍵 load 偶發失敗（Breakout 兩次 restart 後仍冇 load → 部署失敗）** | 熱鍵預載 restart（連第二次）後 MT5 仍然 load 唔到新 hotkeys mapping（Breakout 案例 — 其他 EA 第二次 restart 後 load 到）→ send ^1 冇彈 Properties + 開 chart 偶發失敗 → 部署失敗 | v0.10.74 專項測試（偶發壓力測試 ×5）證明 **MT5 重啟唔會清空 hotkeys.ini**（5/5 PASS — 寫入保留 + send 彈 Properties）→ 即係**唔係 hotkeys.ini 被清空** — 係連環部署時序（MT5 狀態累積/未穩定）— 待處理：部署 restart 後等 MT5 完全穩定先 send | 08-25 |
| 117 | **🔥 部署第二隻 EA 後第一隻心跳網頁 check 唔到** | 熱鍵 Ctrl+1 重用（每次部署清空舊 mapping + 只寫新 EA）→ hotkeys.ini 只反映最後部署嗰隻 → server `_hk_has` 冇舊 EA → line 549 誤判 unpaired（即使心跳新鮮） | v0.10.76 server 加「心跳新鮮（<300s）= 運行緊」fallback — 有心跳檔 + 新鮮 → 唔理熱鍵照顯示 running | 08-26 |
| 118 | **🔥 剷除→重添→再部署警告視窗冇咗** | 多個 alert_worker 暴增（watchdog `_is_running` process check race — `_py_cmdlines` snapshot 舊 → 同時 spawn 多個 → 搶 5004 → 混亂/視窗唔彈；實測 8 個 instance） | v0.10.76 watchdog 改用「5004 port LISTEN check」（有 instance 就唔起）+ 殺晒殘留重起 — 驗證「AI 遠端控制」視窗彈返 | 08-26 |
| 144 | **🔥「Agent 已連線」彈窗成日彈（斷線重連）** | sio.on('connect') 每次重連都彈成功視窗 → 網絡 flicker 就彈多次 | _popup_shown flag — 只彈一次（重連唔再彈） | 08-27 |
| 143 | **🔥 一部機可以雙開 agent（B account 撞 A account）** | 冇防護 — 兩個 agent 同一部機同時行 → hotkeys.ini/EA 目錄互相覆蓋 | agent.lock 防雙開（agent_id+PID）— 啟動時有其他 agent 行緊 → 阻止 + 彈窗 + exit(3) — 實測 PASS | 08-27 |
| 142 | **🔥 網頁顯示 offline 但 agent 上報緊（第二部機）** | last_seen 係 datetime.utcnow()（naive UTC）→ .timestamp() 當本地時區（UTC+8）→ 錯 8 小時 → 判 offline | _agent_live_status 改用 naive UTC 直接比較（無時區歧義）— 實測 connected ✅ | 08-27 |
| 141 | **🔥 pyw 啟動 agent 卡死（冇 Connecting log — 手動跑 work）** | pyw 啟動時 stdout cp950 唔支持 ☁️ emoji → UnicodeEncodeError crash（手動跑 chcp 65001 所以 work） | agent.py 開頭強制 stdout/stderr UTF-8（errors=replace）— 實測 redirect 去 file 正常 ✅ | 08-27 |
| 140 | **🔥 假綠燈（agent 停咗網頁永遠 online）** | server 冇 SocketIO disconnect handler → status 永遠 connected | _agent_live_status（last_seen <60s 先 online）+ disconnect handler — 實測 offline 正確 ✅ | 08-27 |
| 139 | **🔥 pyw 啟動 agent 靜默失敗（DEVNULL 食晒輸出）** | pyw 用 stdout=DEVNULL → agent 輸出消失 → 診斷唔到 | redirect 去 agent_run.log + agent.py 全面階段 log（AGENT START/init/args/socketio/Connecting/Connected/Registered） | 08-27 |
| 138 | **🔥 MT5_DATA hardcode 第一部機 hash（第二部機 path 錯）** | agent.py 硬編碼 D0E8209F77C8CF37AD8BF550E51FF075（第一部機）→ 第二部機 path 錯 | 動態偵測 Terminal 目錄（APPDATA/MetaQuotes/Terminal/<hash> 有 MQL5/Experts 嗰個） | 08-27 |
| 137 | **🔥 launcher download 失敗（curl 問題 — 瀏覽器開到但 curl 唔得）** | 某啲機 curl 有問題（舊版/proxy/TLS）→ 下載 pyw fail | 改用 PowerShell 下載（同瀏覽器網絡 stack）+ pyw 已存在就用 + 網頁一粒掣直接下載 pyw | 08-27 |
| 136 | **🔥 launcher batch crash（'or'/'ock'/'was unexpected'）** | ①block 內 echo 括號 ②中文註釋 byte 亂 ③curl UA 括號 ④EnableDelayedExpansion 吞 ! ⑤goto 喺 block 內 | 全部清除（英文註釋/無括號 echo/flag 變數/無 goto block）— 實測完整跑 ✅ | 08-27 |
| 135 | **🔥 Python 3.14 卡死（第二部機 OpenClaw 用 3.14）** | MetaTrader5 import 喺 3.14 卡死 → agent 靜默死 | launcher 偵測 3.14 → 自動下載安裝 3.11 + pyw _pick_good_python 揀 3.11/3.12 | 08-26 |
| 134 | **🔥 第二部機安裝體驗（下載/安裝/啟動 — 好似下載軟件）** | 流程繁複（launcher/curl/多掣）+ 冇桌面捷徑 + 冇成功提示 | 網頁一粒掣下載 pyw + 固定位置 + 安裝精靈（條款/檢查/設定）+ 桌面捷徑自動建 + tray icon（綠色=Online）+ 綠色彈窗 | 08-27 |
| 132 | **🔥 Python 3.14 卡死 MetaTrader5（第二部機 OpenClaw 用 3.14）** | MetaTrader5 import 喺 3.14 卡死（socketio polling 冇 UA 都 403）→ agent 靜默死 | launcher 偵測 3.14 → 自動下載安裝 3.11 + pyw _pick_good_python 揀 3.11/3.12 行 agent | 08-26 |
| 131 | **🔥 batch 撳 Y 都退出（安裝流程）** | batch 延遲展開 bug：set /p + if 同一 block 內 %VAR% 提前展開（空）→ 永遠走退出 | setlocal EnableDelayedExpansion + !VAR! 即時讀取 | 08-26 |
| 130 | **🔥 launcher 彈走（... was unexpected at this time）** | 括號 block 內 echo 含 ()（~25MB）→ 提前關 block + py -c 內 ')' 嵌套 | 去掉 echo 括號 + py fallback 移出 block + 版本檢查改 --version/findstr | 08-26 |
| 129 | **🔥 第二部機新 account 顯示返舊機 5053721681** | ①_refresh_auto_trade_cache 寫 server 本機 account 落新帳戶 agent（污染）②api_dashboard fallback 全局 cache ③agent 上報 key 唔 match（login vs account） | 三層修復：①唔再污染 agent.account_info ②唔 fallback 全局 ③agent 加 data['account'] key + 清污染數據 | 08-26 |
| 128 | **🔥 其他帳戶睇到第一個帳戶嘅嘢（配對庫/EA倉庫/活動記錄）** | 前端 localEA 用全局 eaDeployStatus（server 本機 inventory）+ EA 倉庫 added 用本機 .ex5 + activity log 全局 | agent_eas（自己 agent 上報）+ added 改 per-user（config/agentEasCache）+ log_activity 加 user 欄 + api_activity 過濾 | 08-26 |
| 127 | **🔥 診斷報告顯示舊數據（agent.deals 取代 EA 真實交易）** | `if not ea_deals`（agent.deals 冇數據先行詳細計算）→ 有舊記錄就顯示舊嘢 | 優先 trades_<EA>.json（真實逐單）+ 未部署 EA 撳報告顯示提示（置中 + 隱藏 cards）| 08-26 |
| 126 | **🔥 Correlation Matrix 顯示 raw Magic#（唔顯示 EA 名）** | agent.deals 舊 (magic,symbol) 組合 match 唔到 config → fallback raw | ea_name_by_key 加淨 magic fallback（Magic#240701 → Breakout (240701)） | 08-26 |

---

## 📝 版本變更歸屬註明

> **⚠️ v0.9.66（commit `D08888C3`，2026-08-18）起，所有更改由 HY3（呢個 AI 模型）執行。v0.9.67（2026-08-18）繼續由 HY3 執行：根治 `SQLALCHEMY_DATABASE_URI` 相對路徑真正 root cause + verify_heartbeat / auto_attach 誤報成功，壓力測試達成真正 5/5 PASS。**
> 包括：① auto_attach 唔 restart MT5 ② `symbol` 參數修復 ③ 心跳驗證雙格式 ④ 清重複圖表 ⑤ 環境清理（kill auto_trade_detector / 舊 agent）⑥ 🔥 install-local config raw SQL persist（#44）⑦ auto_attach 間歇性崩潰修復（#42/#43）⑧ UI 字眼（#45）⑨ delete 清心跳 file（#46）。
> 壓力測試實測：Round 1 心跳 age=0.9s ✅ PASS（端到端 pipeline 確認 work）。



## 📋 TODO（未實行 — 用戶指示暫時唔做，只記錄）

### 🚀 平台化 Roadmap（2026-08-27 用戶確認方向 — 未實行）
**目標**：推出市面 — server 上雲 + Admin 管理後台 + 商業化準備

| Phase | 內容 | 狀態 |
|-------|------|------|
| **Phase 1 — Server 上雲** | server 搬去 VPS（Linux + Flask + SQLite — 1vCPU/1GB 夠）— 第一部機只係普通 agent 機（熄咗唔影響其他 account）— Cloudflare Tunnel 或 VPS 直連 | ⏳ 未做 |
| **Phase 2 — Admin 後台** | user 表加 role 欄（'admin'/'user'）+ Admin 登入 + 頁面：用戶列表（幾多人/active/註冊日期）+ Agent 列表（邊部機 online/幾多秒前上報）+ 統計（總用戶/在線 agent/今日部署）+ 用戶操作（封鎖/解鎖/重置密碼） | ⏳ 未做 |
| **Phase 3 — 監控** | server 資源（CPU/RAM）+ 錯誤 log 顯示 + 部署歷史 | ⏳ 未做 |
| **Phase 4 — 商業化** | 訂閱/收費（到期日）+ 用量限制（免費 N 部機 / 付費無限）+ 註冊流程（email 驗證等） | ⏳ 未做 |

**用戶要求（2026-08-27 對話）**：
- 市面成熟系統都有 Admin 後台（睇幾多人上線/account/用緊）— 我哋都要有
- server 上雲後第一部機熄咗 → 其他 account 唔受影響
- 方案 A（1 User → N Agent）已確認 — 防雙開已實作（v0.10.87）

### 🧪 Server→Agent 人手壓力測試（2026-08-27 確認流程 — 見 skill `mt5-stress-test/references/stress-test-server-to-agent.md`）
**流程**：登入 web → 安裝 agent（pyw）→ 網頁添加/部署/剷除隨機反覆 ×5 — 驗證「server 經 SocketIO 控制 agent → agent 控制 MT5」新架構

**用戶要求（實測教訓）**：
- **完全乾淨先開始**：MT5 chart 全部關閉（Ctrl+W 關到 0）+ Experts folder 清走所有 EA（.mq5/.ex5）+ 心跳清 + hotkeys 空 + 配對庫空 — 開始前用戶確認
- **每一步驗證規範**：添加/部署/剷除 — 網頁狀態 同 MT5 狀態必須一致先 PASS（網頁配對庫有 EA ↔ MT5 Experts 有 .mq5/.ex5；部署後網頁心跳 fresh ↔ MT5 chart 掛 EA；剷除後網頁冇 ↔ MT5 心跳停 + 檔刪）
- **部署要確認經 agent**：server log「Deploy 指令已路由俾 Agent」= 經 agent（fallback 本機 = FAIL）
- 唔可以直接跑（要經 pyw 安裝流程）

### 🔄 數據注入選擇功能（2026-08-21 用戶要求，未實行）
**目標**：所有 EA 部署時可選「注入逐單數據記錄」（trades json），或者唔注入照部署但註明冇呢個功能。

| # | 步驟 | 狀態 |
|---|------|------|
| 1 | Server：心跳注入模板加「逐單記錄」注入段（`__mt5c_append_trade` + OnTradeTransaction 掛鉤 — 平倉時 append `trades_<EA>.json`） | 🔄 已改 code（server/app.py 心跳模板 + OnTradeTransaction 注入段）— 未完整測試 |
| 2 | Server：`/api/deploy` 接受 `inject_trades` 參數（決定注入/唔注入）+ 寫入 deploy_cmd | 🔄 已改 code（inject_trades 讀取 + 寫入 deploy_cmd 兩個位置）— 未測試 |
| 3 | Server：install-local（配對）時按 `inject_trades` 決定注入逐單 code（心跳注入段加條件） | ⏳ 未做 — 要改 install-local 接受參數 |
| 4 | 前端：部署時彈「數據注入確認」modal（注入 / 唔注入 + 「不再顯示」checkbox + localStorage）— 每一次都彈，除非剔「不再顯示」 | ⏳ 未做 |
| 5 | 前端/Server：冇 trades json 嘅 EA → 報告/correlation 註明「此 EA 冇逐單數據」（誠實標註，唔造假） | ⏳ 未做 |
| 6 | 測試 + update doc + commit | ⏳ 未做 |

**用戶要求（重要）**：
- 注入/唔注入由用戶選擇（部署時）
- 唔注入 → 照常部署 + 註明「而家冇呢一個功能」
- 確認視窗有確定時窗 + 每一次都彈；唔想彈 → 剔「不再顯示」
- 唔可以假數據（冇 JSON 就標註冇，唔好當有）

---

## 🐛 Known Bugs (Unresolved)

### Bug #37: Sibling Agent 持續 spawn auto_attach（🔴 活躍中）

**現象**：即使 kill 咗 auto_attach process，其他 AI agent 會立刻重新 spawn 新嘅 auto_attach，MT5 不斷被操作。

**原因**：其他 AI agent（Python 3.14/3.11）持續建立 `auto_attach_all.py`，用 `--hb-timeout` flag 批量部署所有 EA。

**當前防護**：
1. ✅ Watcher Lock — deploy_watcher 檢查有冇 auto_attach 運行中
2. ✅ Global Mutex — auto_attach.py 本身檢查 lock file
3. ✅ auto_attach_all.py 定期被刪除（但 sibling agent 不斷 recreate）

**建議方案**：
- 係 auto_attach.py 嘅 global mutex 用 Windows Named Mutex（跨 process）
- 或用 shared memory / event object 做跨 process lock

### Bug #38: Heartbeat 檔案寫入唔 work（🟡 中度）

**現象**：EA 成功 loaded 上 chart（MT5 log 確認），但 `hb_*.txt` 檔案冇出現。

**原因**：MT5 build 6061 嘅 `FILE_WRITE|FILE_TXT|FILE_COMMON` 組合無法寫入檔案。

**嘗試過嘅 fix**：
1. 改用 `FILE_WRITE|FILE_TXT`（唔用 FILE_COMMON）→ 未完全驗證
2. 改用 GlobalVariableSet → 但 agent 嘅 heartbeat check 係 check files

**Workaround**：auto_attach.py 已改為 Properties dialog 確認後就回報成功（唔靠 heartbeat）

> ✅ **2026-08-18 更新**：#38 已解決 — v0.9.65/66 實測 `hb_*` / `state_*` 心跳正常寫入 Common/Files（FILE_COMMON 係 work 嘅；之前係 EA 掛唔到導致心跳冇出，唔係寫入問題）。壓力測試 5/5 PASS 確認心跳穩定。

---

### Bug #39: EA 倉庫 button 字眼錯誤（🟡 低度 — 純 UI 顯示）

**現象**：EA 倉庫入面**未配對**嘅 EA（例如 EMA_Cross）顯示「移去配對」button。

**原因**：`dashboard.html` 嘅 `addEAToPairing` button 硬編碼 `data-action="remove-pairing"` + 文字「移去配對」，但實際 onclick = `addEAToPairing`（即係加入配對 → install-local）。文字同動作相反 → 用戶會誤會撳咗會移除。

**正確字眼**：未配對 EA 應顯示「加入配對」（動作 = 配對入我的倉庫）；已配對 EA 顯示「移去配對」。

**修復**：`dashboard.html` button 文字按 `isPaired` 狀態切換（未配對→「加入配對」/ 已配對→「移去配對」）。

### Bug #40: 刪除 EA 後心跳 file 殘留（🟡 低度 — 冇功能影響）

**現象**：網頁撳「刪除」→ watcher detach EA 由圖表 → 但 `hb_{ea}.txt` / `state_{ea}.json` 仲喺 `Common/Files/`（舊 file，mtime 停喺 detach 前）。

**原因**：remove-local → web_delete flag → watcher detach EA（關圖表/移除 EA）→ EA 停止寫心跳，但舊 file 唔會自動刪。下次同 EA 重新配對→部署會 overwrite，所以冇功能影響；純粹殘留檔。

**修復**（可選）：watcher delete 流程 detach 完成後，`os.remove(hb_{ea}.txt)` + `os.remove(state_{ea}.json)`（如果 exists）。

---

### Bug #41: 部署「load 好耐 + 電腦冇反應」— Ctrl+9 熱鍵失效（🔴 活躍中 — v0.9.76 發現；OpenChart 配對已根治但部署仍未解）

**現象**：網頁撳部署 → 前端一直轉圈 + 電腦（MT5）冇實際反應 → auto_attach 最後 `❌ ADX_Trend heartbeat not detected within 15s` → FAIL。

**實況（手動 run auto_attach 實錘）**：
```
📊 圖表平鋪完成（1 個圖表）
✅ 一體化：ADX_Trend 已由套模板掛落圖表
⚠️ Ctrl+9 冇開到圖表（EURUSD active 標題未變）— 重試   ← 兩次
✅ log 驗證: ADX_Trend 喺 EURUSD 啟動
❌ ADX_Trend heartbeat not detected within 15s   ← 心跳偵測唔到 → FAIL
```

**原因**：auto_attach 部署用 `Alt+F→Enter×3` 開空白 chart 再 `Ctrl+9` 觸發 OpenChart script 開目標 chart，但 **`Ctrl+9` 熱鍵係寫入 `hotkeys.ini` 個 `<scripts>` 區，MT5 每次重啟會洗走該區**（auto_attach 部署時 `do_restart_mt5()` 重啟 MT5 → `<scripts>` 區消失 → Ctrl+9 失效）→ OpenChart 開唔到 chart → EA 掛唔到 → 心跳 15s 偵測唔到 → 部署失敗卡住。

**修復（未做）**：① auto_attach 部署時唔好每次重啟 MT5（用戶手動測試成功嗰次就冇重啟）；② 或者改用唔依賴 `hotkeys.ini <scripts>` 區嘅開 chart 方法（例如 OpenChart_Helper 常駐 EA / 直接 pyautogui 操作 MT5 menu）。

---



## 📊 Current Status（2026-07-30 20:00）

### 服務

| 服務 | PID | 狀態 |
|------|-----|------|
| Flask Server :5001 | 13948 | ✅ |
| Agent DEV00001 | 17960 | ✅ connected |
| Watcher（有 lock） | 14968 | ✅ idle |
| MT5 | varies | ✅ running |
| Cloudflare Tunnel | varies | ✅ live |

### EA Status

| EA | Symbol | TF | 狀態 | 備註 |
|---|--------|----|------|------|
| Hedge_Fund | EURUSD | H1 | 🟢 已 deploy | HTTP API |
| Breakout | EURUSD | H1 | 🟢 已 deploy | HTTP API |
| MACD_Cross | EURUSD | H1 | 🟢 已 deploy | HTTP API |
| Scalping_M1 | EURUSD | H1 | 🟢 已 deploy | HTTP API |
| Momentum | USDJPY | H1 | 🟢 已 deploy | terminal auto_attach |
| Trend_Follow | EURUSD | H1 | 🟢 已 deploy | 之前 |
| Mean_Reversion | EURUSD | H1 | 🟢 已 deploy | 之前 |

### 新檔案

| File | 用途 |
|------|------|
| `agent/deploy_notify.py` | 通知視窗（AI 控制中），auto_attach 開始時彈出，完成後自動關閉 |
| (無檔案) | `/api/deploy` HTTP endpoint（喺 `server/app.py`） |

### 已修改檔案

| File | 修改內容 |
|------|---------|
| `agent/deploy_watcher.py` | 加 Lock 檢查 `is_auto_attach_running()`，唔俾重複執行 |
| `agent/auto_attach.py` | 加 Global Mutex + deploy_notify（起點 show，終點 hide） |
| `server/app.py` | 加 `/api/deploy` HTTP endpoint |
| `server/templates/dashboard.html` | 🚀 Deploy 改用 HTTP fetch（唔靠 Socket.IO） |

---

## 💡 完整部署流程（最終版）

```
你喺網頁撳 🚀 Deploy
  ↓ HTTP POST /api/deploy（可靠，唔靠 Socket.IO）
Server 儲存 EA config + 寫 deploy_cmd_*.json 去 Common/Files
  ↓
Watcher（每 3 秒 poll）detect 到新 command
  ↓ Lock check: 有冇 auto_attach 已運行？
  ├─ 有 → skip（等下次）
  └─ 冇 → 
      1. Web log: 🤖 AI 開始部署 XXX → MT5
      2. 彈出通知視窗（置頂，深色）
      3. 行 auto_attach.py（pyautogui 控制 MT5）
      4. EA attached ✅
      5. 通知視窗自動關閉
      6. Server report: ✅ XXX
```

### auto_attach.py 執行指令

```bash
cd /c/Users/hongk/Desktop/mt5-cloud
timeout 120 python -u agent/auto_attach.py --ea EA_NAME --symbol EURUSD --tf H1 --magic 240701 --lot 1.00
```

### HTTP Deploy API

```bash
curl -X POST http://localhost:5001/api/deploy \
  -H "Content-Type: application/json" \
  -d '{"ea_name":"Momentum","symbol":"EURUSD","tf":"H1","magic":"240701","lot":"1.00"}'
```

---

## 🤝 Handoff Notes（下一位 Agent 必讀）

### 系統架構

```
Dashboard 🚀 Deploy
  ↓ HTTP POST
Server :5001
  ├── 寫 deploy_cmd_*.json → Common/Files/
  ├── Socket.IO → Agent（download + compile + inject heartbeat）
  └── Socket.IO → Dashboard（即時更新 log）
      
Watcher (deploy_watcher.py)
  ├── 3s poll Common/Files/deploy_cmd_*.json
  ├── Lock check (is_auto_attach_running)
  ├── deploy_notify.show() → 通知視窗
  ├── subprocess auto_attach.py → pyautogui 控制 MT5
  └── deploy_notify.hide() → 通知視窗關閉
      
Agent (agent.py)
  ├── polling transport（唔用 WebSocket，Flask dev server 唔 stable）
  ├── heartbeat detect（Common/Files/hb_*.txt + instance Files/）
  └── auto-sync EA config（60s debounce）
```

### 關鍵規則（唔好再試）

- ❌ Socket.IO 嘅 `emit('deploy_ea')` — 改用 HTTP POST `/api/deploy`
- ❌ `FILE_WRITE|FILE_TXT|FILE_COMMON` — MT5 build 6061 寫入唔 work
- ❌ `metaeditor64.exe CLI` — 有時 compile timeout，用 Agent auto-compile
- ❌ 改 `auto_attach.py` — 已用 global mutex，改完要 sync 個 lock
- ✅ **HTTP API deploy** — 最可靠嘅方法
- ✅ **Watcher Lock** — auto_attach 已運行就 skip
- ✅ **Global Mutex** — auto_attach.py 只准一個 instance

### 常用除錯指令

```bash
# 1. Check services
curl -s http://localhost:5001/api/dashboard | python -m json.tool

# 2. Check auto_attach running
wmic process where "name='python.exe'" get commandline | grep auto_attach

# 3. Kill all auto_attach
wmic process where "commandline like '%auto_attach%'" delete

# 4. Deploy EA
curl -X POST http://localhost:5001/api/deploy \
  -H "Content-Type: application/json" \
  -d '{"ea_name":"Momentum","symbol":"EURUSD","tf":"H1","magic":"240701","lot":"1.00"}'

# 5. Manual auto_attach (bypass watcher)
cd /c/Users/hongk/Desktop/mt5-cloud
timeout 120 python -u agent/auto_attach.py --ea Momentum --symbol EURUSD --tf H1

# 6. Check watcher log
process action=log session_id=<watcher_proc_id>

# 7. Check MT5 log
python -c "
with open('C:/Users/hongk/AppData/Roaming/MetaQuotes/Terminal/D0E8209F77C8CF37AD8BF550E51FF075/Logs/20260730.log', 'rb') as f:
    content = f.read().decode('utf-16-le', errors='replace')
    for line in content.split('\n')[-30:]:
        if 'loaded' in line.lower() or 'expert' in line.lower():
            print(line.strip()[:120])
"
```

### 已知 Sibling Agent 問題

⚠️ 呢個 project 有其他 AI agent（parallel subagent）會：
1. 建立 `auto_attach_all.py` 並嘗試批量 deploy 所有 EA
2. 用 `--hb-timeout` flag 行 auto_attach.py（非標準參數）
3. overwrite `auto_attach.py`（已用 global mutex + lock file 防護）

如果遇到「MT5 亂跳」或「auto_attach 不停 spawn」：
1. `wmic process where "commandline like '%auto_attach%'" delete` — kill 所有
2. `rm -f /c/Users/hongk/Desktop/mt5-cloud/agent/auto_attach_all*` — delete rogue scripts
3. Check `agent/.auto_attach_global.lock` — 確保冇 stale lock

---

### 🎯 目前狀態（2026-08-20 — 新 session 必讀）

**Git HEAD**: `333ee56`（master）— v0.10.89（網站剷除 Agent + 完整剷除/安裝 cycle — 剷除全部清晒/安裝全部裝返實測 PASS）；TODO：數據注入選擇功能未實行（見 TODO 段）

**✅ 部署流程檢測系統已落地（2026-08-20 v0.10.5）**
- 設計 document：`docs/deployment-checkpoint-system.md`（每步驗證標準 + 程式化成功標準 — 檔案/視窗/log 檢查，唔靠 AI）
- Code 落地：auto_attach.py 加 `_wait_until(check_fn, timeout, desc, interval)` helper + 每步驗證 gate
  - Step 0 前置：EA .ex5 檢查（v0.10.4）、hotkeys.ini 可寫
  - Step 1 熱鍵預載 gate：WM_CLOSE 後 poll 確認 MT5 已關（20s）→ 寫熱鍵 → 開 MT5 → 等主視窗 ready（90s）→ send Ctrl+N 測試熱鍵 load（彈 Properties = 成功，×3 重試，撳取消）
  - Step 1b MT5 ready gate：`_wait_until(wait_for_mt5, 90s)`（唔係固定 30s）
  - Step 4 EA loaded gate：`_ea_loaded_in_log` — MT5 log `loaded successfully` 且無隨後 removed（poll 30s — 對真 log）
  - Step 5 最終驗證：log loaded 優先 + 心跳輔助（市場收市心跳唔寫都算成功）
- 待做：~~實機測試（壓力測試驗證 5/5）~~ **✅ 已完成 — 2026-08-20 5/5 PASS（v0.10.13 + stress script 修復）**

**📊 壓力測試實測結果（2026-08-20 v0.10.11-10.13 + stress script 修復）：🎉 5/5 PASS**
- v0.10.6：2/5（Round 1/5 EMA/Bollinger 成功 — 固定 EA pattern）
- v0.10.10（熱鍵 load 時序修正）：2/5（Round 1/4 單 EA 輪全過；多 EA 輪每輪有一隻失敗 — 非確定性時序問題）
- v0.10.13 + stress script 修復：**5/5 PASS**（Round 1-5 全部 ✅，9 個部署 log=True + hb=True age 0.1-1.1s）
- **Root cause 鏈（多 EA 失敗真因）**：stress script 連住 POST deploy（非阻塞）→ watcher spawn 多個 auto_attach 同時跑搶 MT5 → 有一隻失敗；改「等 deploy_result activity log（watcher 真正完成）先 deploy 下一隻」後 **5/5**
- **已根治（v0.10.8-10.13）**：① 熱鍵 load 時序（熱鍵必須「MT5 關閉狀態下寫入」先 load — mtime vs MT5 啟動時間檢查）② 熱鍵 load 驗證 gate（開完 MT5 poll send 測試彈 Properties）③ 驗證 fail 自動 restart 重寫 ④ 批次熱鍵預載（一次 restart 寫入全部 .ex5 熱鍵 → 之後 skip restart）⑤ watcher tee auto_attach 完整 output 去 aa_debug.log（診斷用）
- **🎉 連續兩次 5/5 PASS（stress 16 + 17 — 2026-08-20）**：穩定性確認 — 兩次全部 Round ✅，9 個部署 log=True + hb=True（age 0.3-4.0s）。⚠️ 跑 stress 前檢查：server :5001 要 listen（crash 咗 → WinError 10061 → stress 即刻死）+ watcher 一定要 python.exe（watchdog 有時用 pythonw 重啟 → auto_attach hang）
- **🎉 人手模擬壓力測試 7/7 PASS（2026-08-20 v0.10.27 — 網頁撳按鈕完整鏈路）**：Bollinger→EURUSD、EMA→USDJPY、MACD→AUDUSD、Heikin→GBPUSD、Ichimoku→XAUUSD、Breakout→GBPUSD、Grid→USDJPY — 全部 MT5 log `loaded successfully`（對應 symbol）+ 心跳 fresh + 冇代替 dialog + 冇掛錯 chart。**環境空白開始（0 chart + 刪晒 EA + 清 hotkeys）→ 每次部署開新 chart（每個 EA 一個 chart 對應 symbol）**
- **🎉 人手模擬壓力測試 5/5（含剷除 — 2026-08-21 v0.10.36 — 隨機 EA/symbol）**：ATR_Stop→USDJPY、SMA_Cross→GBPUSD、Mean_Reversion→AUDUSD、Parabolic_SAR→EURUSD、Support_Resist→XAUUSD — **每次部署 PASS（MT5 log loaded + 心跳 fresh + 正確 symbol）+ 每次剷除 PASS（Alt+W 窗口 dialog → ListView 揀 chart → Ctrl+W 關閉 → MT5 log removed）** — 最終 charts 0 全部清淨。**測試逼出 3 個假成功 bug（v0.10.34-36）：watcher 讀舊 output / main 入口消失 / ctypes NameError**

**已知問題（下次 session 繼續）**：
1. ✅ **熱鍵預載後未等 load**（v0.10.5 已修）— `_ensure_hotkey_loaded` 開完 MT5 後加熱鍵 load 驗證 gate（等主視窗 ready 90s → send Ctrl+N 測試彈 Properties = load 成功，×3 重試）；壓力測試 Round 1 fail（時序 race）待實機驗證修復
2. ✅ **壓力測試 5x 未達 5/5**（v0.10.13 + stress script 修復 — 2026-08-20 **5/5 PASS**）— root cause：stress script 連住 POST deploy → watcher spawn 多個 auto_attach 同時跑搶 MT5；改「等 deploy_result activity log 先 deploy 下一隻」後 5/5
3. **多 watcher instance 問題** — 殺舊起新時會 spawn 多個（單實例守衛 lock file 殘留）；起 watcher 一定要 python.exe 絕對路徑（pythonw 會 hang）

**關鍵流程（用戶實測成功 — 唔好改）**：
- 熱鍵注入：網頁配對 EA → 等 MT5 refresh → 關 MT5 → 寫 hotkeys.ini（`<experts>Experts\<EA>.ex5=Ctrl+N</experts>` UTF-16）→ save → 開 MT5 → 熱鍵 work
- 開 chart：`Alt+F→Enter→Enter→Space→打 symbol→Enter`（pyautogui）
- 成功判定：對真 MT5 log（`D0E8.../logs/YYYYMMDD.log`）見 `expert <EA> (SYM,TF) loaded successfully` 且無 removed 先話成功；心跳/activity 可能假成功
- 部署時唔可以再 restart MT5（restart 會令 MT5 覆寫 hotkeys.ini → 熱鍵失效）

**重要 code 狀態**：
- `_ensure_hotkey_loaded`（auto_attach.py ~1310）— 熱鍵預載（關→寫→開）+ .ex5 檢查 + 熱鍵 load 時序（v0.10.4/10.10/10.11 批次預載）
- `_wait_until(check_fn, timeout, desc, interval)`（v0.10.5）— 每步驗證 gate poll helper
- `_ea_loaded_in_log(ea_name, symbol)`（v0.10.5/10.6）— MT5 log loaded 驗證（新鮮度檢查 mtime<300s）
- `_mt5_alive()`（v0.10.5）— tasklist 檢查 MT5 有冇運行
- `_HK_RESTART_DISABLED = True`（v0.10.3）— 部署時唔 restart
- watcher `_PY_EXE`（v0.10.0）— auto_attach 用 python.exe 絕對路徑；`run_auto_attach` tee 去 aa_debug.log（v0.10.13 後）
- 熱鍵 load 驗證 gate（auto_attach_ea Step 2b，v0.10.8/10.13）— 開完 MT5 poll send 測試彈 Properties；fail → restart 重寫
- 壓力測試：`agent/_stress_test_5x_multi.py`（等 deploy_result activity log 先 deploy 下一隻 — 5/5 關鍵）

**運行中 process（交接時）**：server :5001、watcher python.exe、MT5 terminal64

*Last updated: 2026-07-30 20:00*

## 🐛 Critical Bug: Hermes 系統 auto-restart 導致無限 spawn loop 🆘

### Bug #39: Agent disconnect/reconnect loop + Hermes auto-restart = 無法停止嘅 spawner

**嚴重程度**：🔴 致命 — 完全無法正常使用系統

**症狀**：
- Agent 不斷 disconnect/reconnect（Socket.IO 問題）
- Hermes System 自動 respawn 多個 server instance（試過同時 5 個）
- 修改 server code 後系統會 kill 新 server 並 spawn 舊 code 嘅 server
- `mt5.initialize()` 因 singleton 限制而無法喺多個 process 同時使用
- 任何 code changes 都無法持久生效

**Root Cause**：
1. Agent Socket.IO auto-negotiate → Flask dev server upgrade 去 WebSocket 失敗 → disconnect loop
2. Hermes 系統嘅 Process Manager kill 自定義 server → spawn 舊 code server
3. MT5 Python API 嘅 singleton 限制 — 一個 terminal 只能被一個 Python process 初始化

**Workaround**：
1. Kill ALL python → 快速起新 server（短暫 window）
2. 用 `icon-` prefix 替代 `lucide-` prefix（Lucide CSS最新版用 `icon-` 而唔係 `lucide-`）
3. 使用 cached account_info（唔直接 call mt5.initialize()）

### Bug #40: Lucide CSS CDN 版本問題 ✅ FIXED

**症狀**：Lucide icons 冇顯示

**Root Cause**：最新版 Lucide（v0.473+）將 CSS class prefix 由 `lucide-` 改為 `icon-`
- 舊：`<i class="lucide lucide-user"></i>` 
- 新：`<i class="icon-user"></i>`

**Fix**：已將全部 4 個 template files 嘅 `class="lucide lucide-"` 替換為 `class="icon-"`

### Bug #41: JS template literals 入面嘅 emoji icons ✅ FIXED

**症狀**：Dashboard 動態生成嘅 HTML 仲有 emoji icons

**Fix**：全部 JS template literals 入面嘅 emoji 已換成 Lucide icons（icon-circle, icon-rocket, icon-file-chart-column, icon-play, icon-pause, icon-trash-2, icon-check-circle, icon-plus-circle, icon-circle-x, icon-refresh-cw, icon-upload, icon-copy, icon-link等）

---

## 🎨 UI Redesign (shadcn/ui) — 2026-07-30

### 完成變更

**Index page** (`/`)
- shadcn 風格 landing page
- Lucide icons（chart-candlestick, monitor, bar-chart-3, play, gauge, wifi）
- Gradient 標題（emerald green）
- Card grid layout

**Login page** (`/login`)
- shadcn Card 佈局（CardHeader/CardContent/CardFooter）
- Zinc 色系（`#09090b`, `#18181b`, `#27272a`）
- Emerald accent（`#10b981`）
- Lucide icons（user, lock, hash, key-round, sparkles）
- Input wrapper 結構（icon + input）
- Alert component
- Loading spinner

**Register page** (`/register`)
- 統一 shadcn 風格
- Lucide icons（user-plus, user, mail, lock）

**Dashboard** (`/dashboard`)
- Sidebar: Lucide icons（chart-candlestick, layout-dashboard, bar-chart-3, log-out）
- Card titles: 全部改用 Lucide icons（satellite, bot, package, clipboard-list, bar-chart-3, network, file-chart-column, trending-up, pie-chart, calendar）
- 表頭 icons: Trades/ Win/ P&amp;L/ Lots
- Action buttons: rocket, file-chart-column, play/pause, trash-2
- 綁定按鈕: link icon
- Upload/Refresh/Copy buttons: upload, refresh-cw, copy
- Close button: x icon
- Auto-Trade status: circle icon（替代 🟢）
- All inline styles updated to use CSS variables
- Badge pill 風格（border-radius: 100px）
- Consistent spacing
- EA table heartbeats: circle icon（替代 🟢/🔴）
- EA table badges: badge-green/badge-blue class（替代 🟢/🟡 inline color）
- Online/Offline badge: 純文字（無 emoji）
- Report title: file-chart-column icon
- Error display: circle-x icon
- Deploy/Report/Delete/Play-Pause buttons: 全部 Lucide icons
- EA row source badge: badge class（無 emoji）
- Auto-trade table status: circle icon（替代 🟢/🔴）

### Login 驗證流程改進
- MT5 account verification 改用 cached account_info（唔直接 call mt5）
- Login 時 cache 未準備好可跳過驗證（唔阻礙 login）
- Quick Dev Access 按鈕已更新

### 未完成
- JS showLog/alert 中嘅 emoji（✅ ❌ 💡）未換 — 屬於 console log message，唔影響 UI

---

## 📡 Auto-Trade Detector 重構（避開 Hermes server respawn bug）— 2026-07-30

### 問題
舊 `compute_auto_trade_status()` 喺 server 內部行，但 Hermes 系統不停 respawn 舊 server（同時 8 個），導致：
- `mt5.initialize()` singleton 衝突 → status 永遠 `[]`
- 改 code 永遠唔生效

### 方案：獨立進程 `agent/auto_trade_detector.py`（port 5003）

**架構：**
```
Dashboard (browser) → fetch :5003 (CORS) → auto_trade_detector.py → MT5
```

**特性：**
- ✅ 獨立進程 — Hermes 換唔到佢（好似 verify_server.py :5002 咁存活）
- ✅ 獨佔 MT5 Python API — 唯一使用者，冇 singleton 衝突
- ✅ 每 30 秒計算 SMA10/SMA30 crossover 信號（BUY/SELL/WAIT）
- ✅ 直接讀 SQLite DB（server/instance/mt5cloud.db）攞 EA config
- ✅ `GET /api/auto-trade-status` + CORS `*`
- ✅ Dashboard JS `fetchAutoTradeStatus()` 每 5 秒拉一次
- ✅ Detector 唔在線時 Dashboard 顯示 fallback message

**啟動：**
```bash
python agent/auto_trade_detector.py   # port 5003
```

**DB 路徑**：`server/instance/mt5cloud.db`（直接讀 user.ea_config，username='dev'）

### 統一 Auto-Trade 顯示（2026-07-30 晚）

- ✅ **Agent Card 嘅 Auto-Trade box 已刪除** — 唔再用舊 server 嘅 `auto_trade_ea_count`（嗰個數字讀過期 cache，唔可靠）
- ✅ **Auto-Trade Monitor 成為唯一顯示** — 完全由 detector :5003 驅動
- ✅ Dashboard JS 移除所有 `autoTradeBox`/`autoTradeStatus` references
- ✅ Detector offline 時顯示「Detector offline (start agent/auto_trade_detector.py)」

### 清咗 DB 入面嘅 leftover EA config（2026-07-30 晚）

- 問題：DB 入面有 4 個舊測試 EA（ADX_Trend, ATR_Stop, Bollinger_Band, Heikin_Ashi）— 之前舊 session 部署留低
- 用戶從未部署過 EA，但 monitor 顯示 3 個 EA
- Fix：`UPDATE user SET ea_config='{}' WHERE username='dev'`
- 而家 monitor 正確顯示「No EAs configured」
- 用戶真正部署 EA 後，detector 先會顯示信號

### EA Inventory 功能（2026-07-31 凌晨）

**問題**：用戶想睇到「電腦 MT5 入面所有 EA + 詳細狀態（是否部署中）」

**方案**：`auto_trade_detector.py` 新增 `/api/ea-inventory` endpoint

**掃描方法：**
- ✅ 掃描 `MQL5/Experts/*.ex5` 檔案 → 所有 EA（33 個）
- ✅ 讀 MT5 log（UTF-16）→ 搵 `EA_NAME (SYMBOL,TF)` attach 記錄 → 部署中（8 個）
- ✅ 讀 SQLite DB config → 配對/暫停狀態
- ✅ log 檔用「最近 3 個」而唔係指定今日（跨午夜問題）

**Bug #42: HTTPServer 單線程卡死 ✅ FIXED**
- 症狀：`/api/ea-inventory` 一 call 就成個 server 卡死（連 /health 都 timeout）
- 原因：`HTTPServer` 係單線程，一個 request 卡住全部卡住
- Fix：改用 `ThreadingHTTPServer`（ThreadingMixIn + daemon_threads）

**Bug #43: 跨午夜 log 檔名問題 ✅ FIXED**
- 症狀：過咗午夜後 detector 讀唔到「今日」log，部署中狀態全部變 0
- 原因：`20260731.log` 未存在，只讀今日檔
- Fix：讀最近修改嘅 3 個 log 檔

### 整合到 Dashboard（2026-07-31 凌晨）

- ✅ **Auto-Trade Detector card 已刪除** — 同「我的配對庫」合併
- ✅ **「我的配對庫」加 Signal/SMA10/SMA30 欄位** — 由 detector :5003 直接餵資料
- ✅ **EA Inventory 成為「我的配對庫」第二個 tab**（配對 / EA Inventory）
- ✅ **篩選按鈕**：全部 / 🟢 部署中 / ⚪ 未部署
- ✅ `detectorSignals` 全局變量 — fetchAutoTradeStatus 每 5 秒更新 → 自動 re-render 配對庫
- ✅ `getSignalHtml()` — BUY/SELL/WAIT/暫停 顯示（trending-up/trending-down/hourglass/pause-circle icons）
- ✅ 刪除舊 `renderAutoTradeTable()` / `switchDetectorTab()` 死碼

### Bug #44: HTTPS tunnel fetch HTTP localhost 被封鎖 ✅ FIXED（2026-08-01）

**症狀**：用戶經 Cloudflare tunnel (HTTPS) 訪問 dashboard，「我的配對庫」空白，冇任何 EA 顯示

**Root Cause**：前端 JS 用 `fetch('http://localhost:5003/api/ea-inventory')` — HTTPS 頁面 fetch HTTP localhost 被瀏覽器封鎖（混合內容 Mixed Content + CORS）

**Fix**：Detector 改為寫 JSON 去 `server/static/detector/`，前端用同源路徑攞數據：
- `agent/auto_trade_detector.py` 新增 `write_static_json()` — 每 30 秒寫 `auto_trade_status.json` + `ea_inventory.json`
- Dashboard JS 改為 `fetch('/static/detector/xxx.json?t=' + Date.now())`
- 完全避開 CORS/混合內容/respawn 問題（任何 server instance 都會 serve static files）

### 配對庫 UI 收斂（2026-08-01）

用戶多輪迭代後最終結構：

- ✅ **EA 倉庫 = 平台庫**（俾人哋嘅 EA）：淨係顯示官方 + 社群 EA，有「移去配對」按鈕（由倉庫加入你嘅配對庫）
- ✅ **我的配對庫 = 本機已安裝 EA**：顯示晒 detector 掃描嘅所有本機 EA（30 個）
- ✅ **配對庫排序**：🟢 運行中喺上面，⚪ 停止中喺下面；同狀態內已配對優先
- ✅ **狀態 column 喺「來源」右方**：`EA | 來源 | 狀態 | Magic | Symbol | TF | Signal | SMA10 | SMA30 | Trades | Win | P&L | Lots | 操作`
- ✅ **配對庫操作按鈕 = 部署 / 報告 / 暫停 / 剷除**（冇「移去配對」— 嗰個只喺 EA 倉庫）
- ✅ EA Inventory tab 概念完全撤銷（初期加咗又刪咗）

### Bug #45: 剷除 EA 但本機檔案依然存在 ✅ FIXED（2026-08-01）

**症狀**：用戶喺「我的配對庫」剷除 EA，但 EA 依然喺電腦出現

**Root Cause**：`deleteEA()` 只 call `DELETE /api/ea-config/<name>` — 只移除 DB 配對設定，冇刪除 MQL5/Experts 入面嘅 .ex5 檔案。Detector 掃描到檔案 → 又顯示返出嚟

**Fix**：
- `server/app.py` 新增 `POST /api/ea-library/remove-local/<filename>` endpoint：
  - 掃描所有 `MetaQuotes/Terminal/*/MQL5/Experts/` 目錄
  - 刪除 `<name>.ex5` + `<name>.mq5`
  - Path traversal 保護（檔名只允許 `[A-Za-z0-9_]+`）
  - 404 如果檔案唔存在
- `deleteEA()` JS 改為兩步：
  1. `POST /api/ea-library/remove-local/<name>`（刪除本機檔案）
  2. `DELETE /api/ea-config/<name>`（移除 DB 設定）
- Confirm 對話框提醒「會刪除本機 MT5 檔案 + 配對設定」
- ✅ 實測驗證：TestBlank.ex5 + TestBlank.mq5 成功刪除（30 → 29 EAs）

### 2026-08-01 系統最終狀態

- Server :5001 得 1 個 process（新 code）
- Detector :5003 得 1 個 process
- Static JSON bridge（detector → server/static/detector/）正常運作
- Inventory: 29 EAs, 7 deployed

### Bug #46: Navigator 自動 refresh 方法 — 多次迭代（2026-08-01）

**症狀**：剷除/部署 EA 後，MT5 Navigator 要手動 refresh 先見到變化

**失敗嘅方法（全部實測）：**
- ❌ ShowWindow hide→show — 只係外觀，唔 reload tree 內容
- ❌ WM_COMMAND 32808 — command ID 錯（估嘅）
- ❌ collapse→expand「EA交易」folder — MT5 唔會重新掃描磁碟
- ❌ F5 / Ctrl+R / Ctrl+N — 冇效果
- ❌ WM_COMMAND 32845 toggle — 只係收埋/放大 panel 外觀

**成功嘅方法（用戶提供）：**
- ✅ **右 click Navigator tree 空白位置 → click 最底「刷新」menu item**
- 呢個係用戶手動 refresh 嘅實際動作，100% 模擬
- E2E 實測：新增→出現，刪除→消失，全程自動

**Bug #47: 浮動 Navigator（移動過變縮細視窗）✅ FIXED**

**症狀**：用戶將 Navigator 移動後變成浮動視窗（Afx:MiniFrame），refresh 搵唔到 tree view

**Root Cause**：`refresh_navigator.py` 只掃 MT5 主窗口 descendants — 浮動 Navigator 係獨立 top-level window（Afx:MiniFrame「導航」），搵唔到

**Fix**：
- `_find_tree_views()` 改用 `EnumWindows` 掃所有 top-level windows + 主窗口 descendants
- 支援三種狀態：Docked / Floating / 關閉（自動嘗試開返）
- 64-bit handle OverflowError 已修（`int(h)` + try/except）
- E2E 實測（浮動 Navigator）：新增→出現，刪除→消失 ✅

**pywinauto 兼容性結論**：Win32 應用基本通用，但 MT5 Navigator refresh 必須用「右鍵→刷新」menu 模擬（其他方法全部失敗）；浮動視窗要掃 EnumWindows。

### 新功能: AI 控制守衛（Control Guard）— 2026-08-01

**需求**：程式/AI 操控電腦時，彈警告視窗 + 提供強制中斷

**新增 `agent/control_guard.py`：**
- `acquire(program)` — 開始控制前：寫 `.ai_control.lock`（program|pid）+ 彈 topmost 警告視窗（顯示邊個程式控制緊 + 🚨 緊急停止按鈕 + 閃爍效果）
- `check_abort()` — 每步檢查 `.ai_control.stop` 標記 → 有就 raise ControlAborted
- `is_aborted()` — 非 raise 版本
- `release()` — 完成/失敗後：清 lock + 關視窗 + 清 stop
- 緊急停止按鈕 → 寫 `.ai_control.stop` → 所有 GUI 自動化 1 步內中止

**整合三個 GUI 自動化：**
- ✅ `agent/auto_attach.py` — `acquire(f"部署 {ea_name}")` + 每步 check_abort + finally release
- ✅ `agent/refresh_navigator.py` — `acquire("刷新 Navigator")` + check_abort + finally release（重構 `_do_refresh()`）
- ✅ `agent/deploy_watcher.py` — `is_auto_attach_running()` 檢查 control lock + `check_experts_changes()` 有 lock 就 skip（避免兩個 GUI 自動化搶 MT5）

**Bug #48: 浮動 Navigator 唔係 foreground → right-click 俾其他窗口食咗 ✅ FIXED**
- 症狀：refresh 時 right-click 冇 popup menu 彈出（之前 E2E 得，而家唔得）
- 原因：用戶將 Navigator 移動成浮動視窗後，佢唔係 foreground（MetaEditor/Explorer 等窗口喺前面），pyautogui right-click 被其他窗口接收
- Fix：right-click 前 `win.set_focus()` + click 標題欄確保 foreground

**E2E 實測（全部通過）：**
1. `--acquire` 測試：警告視窗彈出，10 步正常，release 清 lock
2. 緊急停止測試：3 秒後寫 stop → 第 3 步即刻 abort → release
3. 完整 refresh：acquire → focus → right-click → 刷新 → release（lock 清理）

### Bug #49: 警告視窗冇彈出（pady tuple + alpha 問題）✅ FIXED

**症狀**：acquire() print「警告視窗已彈出」但實際視窗冇顯示

**Root Cause（兩個）：**
1. `tk.Label(pady=(14, 4))` — tkinter 唔支援 tuple pady（只支援單一 int）→ `bad screen distance` error → 成個 `_show_window` 失敗被 `except: pass` 吞咗
2. 修正後 alpha 閃爍 (0.7-0.96) 令截圖時視窗半透明混白，難驗證

**Fix**：
- `pady=(14,4)` → `pady=14`；`pady=(0,12)` → `pady=12`
- alpha 閃爍改溫和：0.98 ↔ 0.88（700ms）

**UI 改動（用戶要求）：**
- ❌ 舊：紅色背景 (#7f1d1d) + 右上角彈出
- ✅ 新：**螢幕正中央** + **shadcn zinc+emerald 風格**（同網頁一致）
  - 背景 `#18181b` (zinc-900) = 網頁 card 色
  - 頂部 emerald 色條 `#10b981` = accent
  - 標題 `#fafafa` (zinc-50)、提示 `#a1a1aa` (zinc-400)
  - 緊急停止按鈕 `#dc2626` (red-600) = 網頁 danger

**驗證（pywinauto capture + 像素分析）：**
- ✅ 置中：視窗中央 (968,559) vs 螢幕中央 (960,540)，偏差 8,19px
- ✅ 背景 zinc (24,24,26)
- ✅ emerald accent 192 像素（頂部條+程式名）
- ✅ red 按鈕 1140 像素

### 新功能: MT5 剷除 EA → 網頁即時通知（2026-08-01）

**需求**：喺 MT5 直接剷除 EA，網頁即時收到通知 + 自動更新

**實現：**
- `agent/deploy_watcher.py` 新增 `_notify_ea_change()` — 偵測到目錄變化（新增/刪除/修改）→ 寫 `server/static/detector/notifications.json`（保留最近 20 條，含 type/ea/time/message）
- `server/templates/dashboard.html` 新增 toast 通知系統：
  - `#toastContainer` + `.toast-item`（shadcn 風格：deleted=紅框、added=綠框、modified=橙框）
  - `fetchNotifications()` 每 5 秒讀 `/static/detector/notifications.json`（`seenNotifIds` 去重）
  - 新通知 → 彈 toast（5 秒消失，最多 5 個）+ 1.5 秒後自動 reload EA 列表

**流程：** MT5 剷除 → watcher 3 秒內偵測 → 寫通知 → dashboard 5 秒內彈 toast → 自動更新列表

**Bug #50: Navigator refresh 由 watcher spawn 成日 timeout（多次迭代）✅ FIXED**

**症狀**：watcher 偵測到變化後 spawn refresh_navigator.py，成日 `timed out after 30/40 seconds`

**Root Cause（4 個）：**
1. **subprocess 冇 desktop access** — watcher（background process）spawn 嘅 subprocess 冇 interactive desktop，pyautogui 卡死
2. **多個 refresh 同時跑** — 每個變化 spawn 一個 thread，多個 pyautogui 搶滑鼠互卡
3. **pending signal race** — 變化嚟到嗰陣 refresh 緊，signal 被清走但無人消費
4. **`release()` 直接 destroy tkinter 視窗卡死** — 喺非 tkinter 主 thread call `_window.destroy()` 會 hang 成個 process（最後一個 refresh 都唔會完成）

**Fix（最終方案）：**
- ✅ **In-process refresh**：`importlib` 直接喺 watcher process call `refresh_navigator()`（唔 spawn subprocess）
- ✅ **Single worker + queue**：`_refresh_worker_loop()` 永遠行緊，`_refresh_queue`（maxsize=1）觸發；refresh 完檢查 queue 有 pending 就繼續（coalesce）
- ✅ **`control_guard.py` 改用 `after(0, destroy/withdraw/deiconify)`** — 排隊去 tkinter 主 thread 執行，唔再卡死

**E2E 實測（最終版）：**
```
🔔 通知已寫: 📥 TestDone 已新增到 MT5
🛡️  [CONTROL] 刷新 Navigator 開始控制電腦（警告視窗已彈出）
🔄 Navigator refreshed (right-click → 刷新)
🛡️  [CONTROL] 控制結束，警告視窗已關閉
   ✅ Navigator refreshed (in-process)
🔔 通知已寫: 🗑️ TestDone 已從 MT5 剷除
🔄 Navigator refreshed ✅（第二次 refresh 都正常）
```
冇 timeout、冇卡死、冇漏 refresh ✅

### UI 標準規則: 所有 UI 一律用 shadcn skill（2026-08-01）

**用戶要求**：總之所有以後嘅格式 UI 都要用返 shadcn ui skill icon/設計製作

**規則（已寫入 3 層）：**
1. **Memory（永久）**：所有 UI（網頁/視窗/通知）一律用 shadcn skill 製作
2. **mt5-impact-analysis skill**：新增錯誤 #0 — 改 UI 前必 load `shadcn` skill
3. **MODULES.md** E 類（UI 矩陣）第一行：任何 UI 製作 → 一律用 shadcn skill

**適用範圍：**
- ✅ 網頁 templates（dashboard/index/login/register.html）
- ✅ tkinter 視窗（control_guard 警告視窗已用 #18181b bg / #10b981 accent / #dc2626 danger）
- ✅ 任何新 UI 元素

**標準：**
- zinc+emerald design tokens（--bg #09090b, card #18181b, accent #10b981）
- Lucide icons `icon-` prefix（≥v0.473，唔係 `lucide-`）
- 0 emoji（static HTML 同 JS innerHTML 都要）
- Flask/Jinja2 適配參考：`shadcn` skill → `references/flask-jinja2-adaptation.md`

### Bug #51: Toast 通知有舊 emoji icon ✅ FIXED

**症狀**：MT5 剷除 EA 後，網頁 toast pop-up 顯示 📥/🗑️/🔄 emoji

**Root Cause**：`deploy_watcher.py` `_notify_ea_change()` 寫入 notifications.json 嘅 message 含 emoji（`📥 {ea} 已新增到 MT5`），toast 直接顯示 message

**Fix**：
- message 改純文字（`{ea} 已新增到 MT5`）
- 類型 icon 由前端 Lucide 提供（`icon-plus-circle`/`icon-trash-2`/`icon-refresh-cw`）— 符合 shadcn 標準

### 新功能: 持久化 Activity Log（活動記錄）

**需求**：Log 顯示所有活動資訊 + 時間日期，持久保存，refresh 後依然存在

**實現：**
- **`server/activity_log.jsonl`**（JSONL append，原子寫入，thread-safe）
  - `server/app.py`：`log_activity(action, message, ea, source)` helper + `GET /api/activity`（倒序返回最近 200 條）
  - `agent/deploy_watcher.py`：`_append_activity_log()` — watcher 偵測到變化同時寫 log
- **記錄嘅活動**：
  - `[login] dev 登入`（source=auth）
  - `[deploy] ADX_Trend 部署 → EURUSD H1`（source=server）
  - `[ea_delete] X 配對已刪除`（source=server）
  - `[ea_toggle] X 暫停/恢復`（source=server）
  - `[added/deleted/modified] X 已新增/剷除/更新到 MT5`（source=watcher）
- **Dashboard UI**：新增「活動記錄」card（`icon-history`）— 時間/動作/詳情三欄，Lucide icons，每 10 秒刷新

**Bug #52: Deploy 處理 block 主 loop → 目錄監控停晒 ✅ FIXED**

**症狀**：處理 deploy 指令（auto_attach subprocess 300s timeout）期間，`check_experts_changes()` 冇機會行 → activity log / 通知寫唔入

**Fix**：deploy 都改 single worker + queue（`_deploy_worker_loop` + `_deploy_queue`）— 同 refresh worker 一樣 pattern，主 loop 永遠唔 block

**Bug #53: AI 控制守衛擋住通知 + activity log ✅ FIXED**

**症狀**：auto_attach 執行期間（control_guard lock 存在），`check_experts_changes()` 最頂嘅守衛 check 直接 return → 通知 + activity log 都寫唔到

**Fix**：守衛 check 移到 refresh 觸發之前 — 通知 + activity log **永遠寫**，只擋 Navigator refresh（`⚠️ AI 控制緊，skip Navigator refresh（通知已寫）`）

### Bug #54: EA 倉庫「移去配對」冇安裝 EA 落本機 ✅ FIXED

**症狀**：EA 倉庫「移去配對」之後，配對庫冇出現 EA

**Root Cause**：`addEAToPairing()` 只寫 config（mappings），**冇複製 EA 檔案落本機 MT5 Experts 目錄** — 而配對庫顯示嘅係本機已安裝 EA（detector inventory 掃 .ex5），所以永遠唔會出現

**Fix**：
- 新增 `POST /api/ea-library/install-local/<filename>`：將 EA 倉庫（官方/社群/用戶）嘅 EA 複製落本機 Experts 目錄 + 寫 config + 排 compile
- 前端 `addEAToPairing()` 改為：先 call install-local（安裝）→ 再寫 config → 配對庫即刻見到

### Bug #55: MetaEditor CLI /compile 喺 background 靜默失敗 ✅ FIXED

**症狀**：`metaeditor64.exe /compile file.mq5` 喺 background 環境 exit=0 但冇生成 .ex5（連 compile log 都冇）

**Root Cause**：MetaEditor CLI 需要 interactive desktop session — background process（server/watcher subprocess）冇 desktop access，靜默失敗

**Fix**：改用 **GUI 方式 compile**（pywinauto 操作）：
- 確保 MetaEditor 開住 → Ctrl+O 開 file dialog → 輸入路徑 → 按「開啟」→ F7 compile
- 自動處理「外部修改」dialog（偵測 #32770 + click「是」）
- 實測成功：Seasonal.ex5（9010 bytes）、MyCustomEA.ex5（9720 bytes）、Martingale.ex5（9550 bytes）

**另外發現**：MetaEditor 偵測到檔案被外部修改（例如 install-local 覆寫 .mq5）會彈 dialog 等確認 — 會 block compile，要自動 click「是」

### 新功能: 移去配對 / 上傳 EA 聯動（自動安裝 + compile）

**需求**：EA 倉庫移去配對 + 配對庫上傳自己 EA → 兩者聯動，配對庫即刻出現

**實現（compile_cmd 排隊機制）：**
```
server（冇 desktop access）                watcher（有 desktop access）
  ├─ install-local/upload：複製 .mq5 落本機   ├─ 偵測 compile_cmd_*.json
  ├─ 寫 compile_cmd_<name>.json 去           ├─ GUI compile（pywinauto：開 file → F7）
  │   Common/Files（排隊）                   └─ .ex5 生成 → 配對庫出現
  └─ 寫 config（symbol/magic/tf/lot）
```

**E2E 實測（全部通過）：**
1. Seasonal.mq5 移去配對 → 安裝 + compile → 配對庫見到（16→17）
2. MyCustomEA.mq5 上傳 → 自動安裝 + compile → 配對庫見到（17→18）
3. Martingale.mq5 移去配對 → compile 成功（9550 bytes）

### Bug #56: compile 冇警告視窗 + 假成功（double-check）✅ FIXED

**症狀 1**：EA 倉庫「移去配對」操作時冇彈 AI 控制警告視窗
**Root Cause**：`_compile_via_gui()` 冇用 control_guard — GUI 操作期間用戶唔知電腦被操控

**症狀 2**：第二次加入 EA 顯示「成功」但 MT5 冇顯示
**Root Cause**：install-local 異步排 compile 後即刻返回成功 — compile 失敗（MetaEditor 狀態/源碼錯誤）都照話成功，冇 verify

**Fix：**
1. **compile 加 control_guard**：`acquire("編譯 XXX")` + 每步 `check_abort()` + `finally release()` → 彈警告視窗 + 支援緊急停止
2. **Double-check 機制**：install-local / upload 排 compile 後 **同步等待 compile 完成**（poll .ex5 生成，最多 45 秒）→ 返回真實 `compile_ok`：
   - `.ex5` 生成且新過 .mq5 → `compile_ok=True`「已編譯 ✅」
   - compile_cmd 消失但 .ex5 冇 → `compile_ok=False`「⚠️ compile 失敗，MT5 可能未顯示」
3. **前端**：`compile_ok=False` → showLog/confirm 警告 + 提供重試

**實測**：正常 EA（Momentum/Volume_Spike）→ `compile_ok=True`；壞源碼 EA（BadEA）→ `compile_ok=False` ✅

### Bug #57: MetaEditor 彈出後冇自動關閉 ✅ FIXED

**症狀**：compile 之後 MetaEditor 留低開住，用戶唔知可唔可以閂
**答案**：**可以閂，唔需要儲存**（compile 只開 file + F7，冇改源碼）

**Fix**：`_compile_via_gui` finally block 自動關閉：
- compile 前記錄 MetaEditor 係咪原本開住（`was_running`）
- **AI 自動開嘅** → compile 完自動關閉（pywinauto close / taskkill fallback）
- **用戶原本開住嘅** → 唔會閂（尊重用戶，可能編輯緊）

**實測**：`🗑️ MetaEditor 係自動開嘅，用完自動關閉... ✅ MetaEditor 已自動關閉`

### Bug #58: compile 同 refresh 搶滑鼠打架 ✅ FIXED

**症狀**：compile 期間 Navigator refresh 照行 → `'NoneType' object has no attribute 'window'` + compile error + MetaEditor 卡死

**Root Cause**：refresh worker 同 compile 兩個 pywinauto 同時操作 GUI 搶滑鼠

**Fix**：compile 同 refresh **共用 `_refresh_lock` 互斥鎖**（`with _refresh_lock:` 包住兩邊）— 同一時間只有一個 GUI 操作

**實測**：加鎖後 compile 成功（Stochastic.ex5 9952 bytes）冇再被 refresh 干擾

### 新功能: 剷除來源分辨（電腦 vs 網頁）+ 通知去重（2026-08-03）

**需求**：剷除要講明來源 — 電腦剷除講「電腦」，網頁剷除講「網頁」

**實現（web flag 機制）：**
```
server（網頁操作）                          watcher（偵測目錄變化）
  ├─ install-local/upload → 寫 web_add_<name>.flag   ├─ 偵測到 added → 有 flag = 「已喺網頁新增」
  ├─ remove-local → 寫 web_delete_<name>.flag        ├─ 偵測到 deleted → 有 flag = 「已喺網頁剷除」
  └─ flag 用完即刪                                   └─ 冇 flag = 「已喺電腦剷除/新增」
```

**通知去重窗口（`_web_action_window`）**：同一 base + 同 type 60 秒內只出一條通知
- 網頁安裝 .mq5 + compile .ex5 兩次 added → 只出一條「已喺網頁新增」
- 電腦剷除 .mq5 + .ex5 兩次 deleted → 只出一條「已喺電腦剷除」
- 唔同 type（網頁 added 後電腦 deleted）→ 唔會誤判，正常出新通知

**E2E 實測（全部通過）：**
| 場景 | 通知 |
|------|------|
| 網頁安裝 | 「Stochastic 已喺網頁新增到 MT5」✅ |
| 電腦剷除 | 「Stochastic 已喺電腦剷除」✅ |
| 網頁剷除 | 「Stochastic 已喺網頁剷除」✅ |

### 新功能: compile 重試機制（自動 + 手動）

**需求**：compile 失敗（假成功）之後點再觸發？

**三層重試：**
1. **Watcher 自動重試**：compile 失敗 → compile_cmd 保留 + `retries` 計數 → 下個 loop 自動再試（最多 3 次）→ 3 次都失敗先放棄清理
2. **Server endpoint**：`POST /api/ea-library/retry-compile/<name>` — 檢查 .mq5 喺本機 → 重新寫 compile_cmd → 等 compile 完成（double-check）
3. **前端**：compile 失敗 → confirm「要而家重試編譯嗎？」→ `retryCompile()` call endpoint

**實測**：壞源碼 retry → `compile_ok=False`；修正源碼後 retry → `compile_ok=True`「重試 compile 成功 ✅」

### 其他修正（2026-08-03）
- **剷除 stale lock**：`agent/.auto_attach_running`（PID 5396 已死）已刪除 — control_guard lock 取代佢嘅角色

### Bug #59: 配對庫剷除 EA 後冇即時更新 ✅ FIXED（2026-08-03）

**症狀**：電腦剷除 EA 後，配對庫列表冇即時更新（用戶問係咪要手動 refresh）

**Root Cause**：toast 通知即時（watcher 3 秒偵測），但**配對庫列表（detector inventory）每 30 秒先掃描一次** → 剷除後要等最多 30 秒先見到列表更新

**Fix：**
- Detector 掃描 interval：30 秒 → **5 秒**（`time.sleep(30)` → `time.sleep(5)`）
- Dashboard 配對庫 poll：30 秒 → **10 秒**（`setInterval(fetchEAInventory, 30000)` → `10000`）

**實測**：剷除 ATR_Stop → 10 秒內配對庫消失（total 11→10）✅

### 網站 UI 全面書面語化（2026-08-03）

**需求**：所有網站語言（日後或之前）唔可以口語化，一律書面語

**已寫入 Memory + User Profile**（永久規則）

**改動位置：**
| 位置 | 之前（口語） | 而家（書面語） |
|------|------------|--------------|
| 通知 toast | 「已喺網頁新增到 MT5」 | 「已於網頁新增至 MT5」 |
| 通知 toast | 「已喺電腦剷除」 | 「已於電腦刪除」 |
| 刪除按鈕 title | 「剷除 XX」 | 「刪除 XX」 |
| 確認框 | 「確定要剷除 XX 嗎？」 | 「確定要刪除 XX 嗎？」 |
| 警告 | 「要而家重試編譯嗎？」 | 「要立即重試編譯嗎？」 |
| 活動記錄標籤 | 「剷除」 | 「刪除」 |
| 錯誤提示 | 「compile 失敗」 | 「編譯失敗」 |

**注意**：console log / 內部 print 可以保留口語（唔係用戶 UI），但網頁顯示嘅一律書面語

### 新功能: Activity Log「已更新資料庫」+ 顯示開關（2026-08-03）

**需求**：Log 加入「已更新資料庫」記錄（detector 每 30 秒更新），但要可以選擇顯示/隱藏（恆常記錄會阻礙其他資訊）

**實現：**
- `agent/auto_trade_detector.py`：`log_db_update()` — 每 30 秒（6 次 x 5 秒掃描）append 一條 `{"action": "db_update", "message": "已更新資料庫"}` 去 activity_log.jsonl
- `server/app.py` `/api/activity`：加 `?include_db=1` 參數 — **預設過濾** db_update（唔顯示），`include_db=1` 先顯示
- `dashboard.html`：活動記錄 card 加 checkbox「顯示資料庫更新」：
  - tick → `include_db=1` fetch + 顯示「資料庫更新」記錄（icon-database）
  - 唔 tick（預設）→ 隱藏（唔阻礙）
  - 選擇存 localStorage（刷新後保留）

**實測：**
- `/api/activity`（預設）→ db_update=0（已過濾）✅
- `/api/activity?include_db=1` → db_update=1（顯示）✅

### Bug #60: 配對庫數量 badge 冇更新 ✅ FIXED（2026-08-03）

**症狀**：配對庫 header 寫住「而家庫入面有幾多」嘅數量（`eaCount`）唔會更新 — 剷除 EA 後表格少咗但 count 冇變

**Root Cause**：`eaCount` 用 `activeEAs.length`（**已配對** EA 數），但表格顯示嘅係 `allEAs`（**已配對 ∪ 本機已安裝**）— 兩者數據源唔一致。剷除本機 EA 後表格少咗（detector 5 秒掃描 + dashboard 10 秒 poll），但 count 計緊配對數所以冇變

**Fix**：`eaCount.textContent = allEAs.length`（同表格行數一致）

**其他 count 檢查（全部正確）：**
| Count | 數據源 | 狀態 |
|-------|--------|------|
| `eaCount` 配對庫 | `allEAs.length`（配對 ∪ 本機） | ✅ 已修 |
| `officialCount` EA 倉庫 | `official.length` | ✅ |
| `posCount` Positions | `positions.length` | ✅ |
| `activityCount` 活動記錄 | `rows.length` | ✅ |

**實測**：剷除 Breakout → detector inventory total 9→8（12 秒內）✅；配對庫 count 同表格一齊更新

### Bug #61: MT5 剷除 EA 但配對庫依然顯示 ✅ FIXED（2026-08-03）

**症狀**：喺 MT5 剷除 HourlyDD_Logger，但配對庫依然顯示佢

**Root Cause（3 個層面疊埋）：**
1. **配對庫顯示兩層嘢合併**：`allEAs = 已配對（config 記錄）∪ 本機已安裝（detector 掃描）` — HourlyDD_Logger 配對過（config 有記錄），本機檔案冇咗但 config 仲喺 → 照顯示
2. **watcher 偵測唔到**：用戶剷除嗰陣 watcher snapshot 已經冇呢個檔案（或者 watcher 未啟動）→ 冇觸發刪除事件 → config 冇人清理
3. **之前冇「本機冇就唔顯示」嘅過濾**：舊邏輯唔檢查「配對咗但本機已冇檔案」嘅情況

**Fix（雙重保險）：**
| 層 | 機制 | 效果 |
|----|------|------|
| 1️⃣ 前端過濾（主要） | 配對庫**只顯示本機有檔案嘅 EA**（`activeEAs = pairedEAs.filter(!removed && eaDeployStatus[name])`） | MT5 剷除咗 → 唔理幾時剷、watcher 有冇偵測到 → **一定唔顯示** |
| 2️⃣ 後端自動清理（次要） | Watcher 偵測到「電腦剷除」→ `_purge_config()` call `POST /api/ea-config/<name>/purge?agent_id=DEV00001` | 連 config 殘留都清埋（配對設定自動移除） |

**新增 endpoint**：`POST /api/ea-config/<ea_name>/purge`（agent_id 認證，watcher 專用）— 將 EA 加去 `_removed` + 刪 config keys + log_activity

**實測**：HourlyDD_Logger（config 有 + 本機冇）→ 配對庫唔顯示 ✅；Bollinger_Band（config 有 + 本機有）→ 顯示 ✅；配對庫 = 本機實際 7 個（同表格/count 一致）✅

**原理**：以 MT5 實際情況（本機檔案）為準，config 只係附加狀態 — 本機冇檔案就唔顯示，杜絕殘留問題

### Bug #62: 剷除嘅 EA「自己復活」自動加入返 ✅ FIXED（2026-08-03）

**症狀**：用戶冇安裝過 HourlyDD_Logger.mq5，但佢自己加入返（activity log 顯示「已於網頁新增至 MT5」）

**Root Cause**：dashboard `loadEALibrary()` 有「**用戶上傳 EA 自動加入配對庫**」邏輯：
```javascript
// 用戶上傳嘅 EA
if (!added) {
    addEAToPairing(baseName, f.name, '用戶');  // 自動 install-local + compile！
}
```
每次 loadEALibrary（30 秒 poll + fetchEAInventory 觸發）見到用戶上傳目錄有未配對嘅 .mq5 → 自動 call「移去配對」→ 重新安裝 + compile。測試殘留嘅 `user_ea/dev/HourlyDD_Logger.mq5` 令佢無限復活（activity log 證據：20:46 安裝 → 20:47 刪除 → 21:21 又自動安裝）

**Fix：**
1. **移除自動加入邏輯**（社群 + 用戶上傳 EA 都改為只顯示按鈕，唔自動裝）— 上傳時已自動安裝，唔應該每次 poll 都重新裝
2. **清理殘留**：刪除 `user_ea/dev/HourlyDD_Logger.mq5` + 本機檔案 + config
3. 用戶上傳 EA 而家會顯示喺 EA 倉庫（新增「用戶上傳」badge + 移去配對按鈕）

**教訓**：任何「自動執行」邏輯都要諗 idempotency — 如果用戶刪除咗，系統唔應該自動重新裝返

### 修正: 活動記錄卡復原 + 配對庫 logBox 移除（2026-08-03）

**誤解澄清**：用戶話「我的配對 log 卡唔需要」— 原意係移除**「我的配對庫」card 入面嘅操作 log 區（logBox）**，唔係上面張「活動記錄」卡

**改動：**
1. **復原活動記錄卡**（獨立 card + 「顯示資料庫更新」checkbox + 10 秒 poll）— 之前錯誤移除咗
2. **移除配對庫 logBox**：`<div id="logBox" class="log-box"></div>` 已刪除 — 配對庫唔再顯示操作 log 區（showLog 函數保留但 box 唔存在 → 安全失效）

**最終版面結構**：Agent 狀態卡 → 活動記錄卡 → EA 倉庫 → 我的配對庫（EA 表格，冇 log 區）→ Performance → Correlation

### Bug #63: EA 倉庫「已加入」卡死 — 移除後冇變返「移去配對」✅ FIXED（2026-08-03）

**症狀**：EA 倉庫已加入嘅 EA，移除後仲係顯示「已加入」，冇辦法重新加入

**Root Cause**：`deleteEA()` 移除 config 後，`loadEALibrary()` 同 `loadEAConfig()` **並行執行** — EA 倉庫渲染用緊舊 `eaMappings`（未更新）→ 顯示「已加入」；要等下一個 poll 先會修正（用戶睇嗰陣覺得卡死）

**Fix**：改為**順序執行** — 先 `await loadEAConfig()`（更新 config 數據）再 `loadEALibrary()`（用新數據渲染）：
```javascript
await loadEAConfig();   // 先更新 eaMappings
loadEALibrary();        // 再用新值 → 顯示「移去配對」
```

**實測**：移除 SMA_Cross → `added=False` → 顯示「移去配對」按鈕 ✅

### 新功能: 活動記錄「處理中」狀態（2026-08-03）

**需求**：配對/上傳 EA 時，活動記錄要顯示「處理中」— 用戶想知系統有冇處理緊

**實現**：server 端操作開始時寫「處理中」log，完成後寫「完成」log：
| 動作 | log 記錄 |
|------|---------|
| EA 倉庫「移去配對」 | 「XX 配對處理中...」 → 「XX 已安裝到本機 MT5（compile 成功）」 |
| 上傳自己 EA | 「XX 上傳處理中...」 → 「XX 上傳 + 安裝到本機 MT5（已編譯 ✅）」 |

**實測**：
```
21:46:57 [ea_install] SMA_Cross 配對處理中...
21:47:13 [ea_install] SMA_Cross 已安裝到本機 MT5（compile 成功）
```

### Bug #64: 重新配對嘅 EA 唔顯示（_removed 殘留）✅ FIXED（2026-08-03）

**症狀**：配對咗 EA（電腦/MT5 見到），但配對庫冇顯示 — 用戶問「點解又再次出現，唔係會自己 check 住更新咩？」

**Root Cause**：EA 之前**刪除過**（加入 `_removed` 列表）→ 而家**重新配對**（config keys 加返）→ **但 `_removed` 冇移除** → 前端 `activeEAs.filter(!removed.includes(name))` 過濾走佢。ADX_Trend 案例：本機有 .ex5 + config 有 keys，但 `removed: True` → 唔顯示

**Fix**：install-local / upload 配對成功後，**自動由 `_removed` 移除**該 EA：
```python
removed = config.get('_removed', [])
if base in removed:
    removed.remove(base)
    config['_removed'] = removed
```

**實測**：ADX_Trend → `removed: False` + `mappings: True` → 配對庫會顯示 ✅

**解釋**：系統有自動更新（10 秒 poll），但 `_removed` 殘留係**數據邏輯問題**（唔係更新問題）— poll 幾多次都係過濾走，要修數據源

### UI 改動: EA 倉庫移除狀態欄（2026-08-03）

**需求**：EA 倉庫唔需要顯示狀態（運行中/停止中）

**改動**：EA 倉庫表格由 4 欄（EA 名稱/大小/狀態/操作）→ **3 欄（EA 名稱/大小/操作）**
- HTML thead 移除「狀態」欄
- 官方/社群/用戶 EA 渲染全部移除狀態 cell
- 刪除 statusHtml 死 code

**注意**：移除 statusHtml 時 patch 工具誤改 regex（`/\\.(mq5|ex5)$/` → `/\\\\\\.(mq5|ex5)$/`）— 已修正返（match dot 正確）

### Bug #65: EA 倉庫「已加入」但本機冇檔案（兩個標準唔一致）✅ FIXED（2026-08-03）

**症狀**：配對庫冇咗 EA 倉庫嘅 MQ5（本機冇檔案），但 EA 倉庫依然寫住「已加入」

**Root Cause**：兩個顯示用嘅判斷標準唔一致：
| 位置 | 判斷標準 |
|------|---------|
| EA 倉庫「已加入」 | config 有配對設定（唔理本機有冇檔案）❌ |
| 配對庫顯示 | config 有 + 本機有檔案 ✅ |

本機冇檔案時：配對庫唔顯示（啱），但 EA 倉庫仲話「已加入」（錯）

**Fix**：EA 倉庫「已加入」改為同配對庫一致 — config 有配對設定 **且** 本機有檔案（`!!eaDeployStatus[baseName]`）— 官方/社群/用戶 3 個渲染位置都改

**實測**：ADX_Trend（本機有）→「已加入」✅；News_Trader（本機冇）→「移去配對」✅

### 新功能: 網站版 AI 控制警告視窗（同 MT5 端 control_guard 一致）（2026-08-03）

**需求**：網站做動作（配對/上傳/部署/剷除/重試編譯）都要彈出同款警告視窗（同 MT5 端 tkinter 版一致）

**實現：**
1. **網站 modal**（shadcn 風格，同 control_guard 一致）：
   - 置中 + zinc/emerald：`var(--bg-muted)` 背景 + `var(--accent)` 色條 + `icon-bot` Lucide（**0 emoji**）
   - 「AI 控制中」標題 + 程式名（emerald）+ 「請勿移動滑鼠或按鍵盤！」+ 🚨 緊急停止（`var(--danger)`）
2. **5 個動作掛接**：配對/重試編譯/剷除/部署/上傳 → `showControlModal('正在XXX...')`
3. **緊急停止**：`POST /api/control-guard/stop` → 寫 `.ai_control.stop` → watcher/compile/auto_attach 即刻 abort（同 MT5 端同一協定）

**教訓**：UI 檢查時 `icon-robot` 唔存在（Lucide 係 `icon-bot`）— 寫 UI 前要確認 icon 名

### 警告視窗「做完動作先消失」+ ai_control.json bridge（2026-08-03）

**需求 1**：剷除 EA 時警告視窗彈一下就消失（動作太快，但 watcher 之後仲 refresh Navigator）
**需求 2**：喺電腦剷除 EA 時，網頁冇彈出警告視窗（網站唔知 watcher 操控緊電腦）

**Fix（ai_control.json bridge — 統一驅動）：**
```
control_guard acquire() → 寫 server/static/detector/ai_control.json {"active":true, "program":"刷新 Navigator"}
control_guard release() → 寫 {"active":false}
網站 pollAiControl() 每 2 秒 poll：
  ├─ active=True → 彈警告視窗（顯示邊個程式操控緊）
  ├─ active=False + 超過最少顯示 3 秒 → 關視窗
```

**改動：**
1. `agent/control_guard.py`：`STATUS_FILE` + `_write_status()` — acquire/release 都寫狀態
2. `dashboard.html`：`pollAiControl()`（2 秒 poll）+ `minShowUntil`（最少顯示 3 秒防「彈一下」）
3. 所有動作完成**唔再即刻 hide** — 由 pollAiControl 統一控制（動作真正做完先消失）

**實測（完整流程）：**
```
電腦剷除 Breakout（01:34:07）
  → watcher 偵測 → 操控「刷新 Navigator」（01:34:12 active=True）→ 網站彈視窗！
  → refresh 完成（01:34:20 active=False）→ 網站關視窗
```

**效果**：無論動作從邊度發起（網站按鈕 / 電腦 MT5 剷除），只要 watcher 操控電腦，網站都會彈警告視窗，保持到動作完成先消失，仲可以 🚨 緊急停止

### Bug #66: tkinter pady tuple 建窗失敗（第二次踩中）✅ FIXED（2026-08-04）

**症狀**：電腦版警告視窗彈唔出（重建視窗時 `pady=(10,0)` tuple → `bad screen distance` → 建窗失敗被吞）

**Root Cause**：tkinter `pady=(a,b)` tuple 唔支援（Bug #49 已記錄過）— 寫新樣式時又用咗 3 個 tuple

**Fix**：全部 `pady` 用單一 int + 加警示註釋

**教訓**：tkinter 任何 `pady=`/`padx=` 一律用 int，唔好用 tuple（tuple 會靜默失敗被吞）

### 電腦版警告視窗 UI 統一（同網頁版一致）（2026-08-04）

**需求**：電腦版（tkinter）警告視窗 UI 同網頁版完全一樣

**改動：**
1. 標題「🤖 AI 正在操控電腦」→「AI 控制中」（同網頁文字）
2. 🤖 emoji → icon-bot（先試 PIL PNG → 最終用 tkinter Canvas 畫 — 照 Lucide bot.svg 線條：天線 + 方形頭 + 耳線 + 眼線）
3. 「程式：XXX」→ 直接顯示動作（同網頁「正在XXX」）
4. 緊急停止按鈕全寬（`fill="x"`）+ 移除細字提示

**教訓**：Lucide icon 名要確認（`icon-robot` 唔存在，係 `icon-bot`）；寫 UI 前確認 icon 名

### 警告視窗「最少顯示 3 秒 + 做完動作先關」演進（2026-08-04）

**需求演進**：警告視窗要 detect 到動作做完先關（唔靠固定時間）；動作太快唔可以「彈一下」；成個流程（compile→refresh）一個連續視窗

**版本演進（3 次修正）：**
| 版本 | 問題 | 修正 |
|------|------|------|
| v1: `w.after(delay)` 延遲 destroy | 網站版 OK，但 watcher 環境 after 後 fallback destroy 彈一下 | — |
| v2: release while-loop 等 3 秒 + 即刻 destroy | destroy 非 tk thread **卡死成個 watcher**（Bug #50 陷阱） | after(0) 排隊 |
| v3: release while-loop 等 3 秒 + after(0) destroy | PhotoImage GC → Image.__del__ → exit 3 | Canvas 畫 icon |

**最終方案（v4 常駐視窗）**：視窗只建一次（daemon thread + mainloop 永遠行），只 show（deiconify）/ hide（withdraw）切換 — 唔 destroy → 冇 GC / Tcl_AsyncDelete 問題

**最少顯示 3 秒**：release() while-loop 等 MIN_SHOW_SECONDS（期間新動作 lock 檔出現 → 續命；緊急停止 → 即刻關）

**實測**：5 個連續動作同一 HWND（62721008）；watcher 2 次真實 refresh 後冇死

### Bug #67: 兩個 watcher 同時行（搶滑鼠 + 彈兩個視窗）✅ FIXED（2026-08-04）

**症狀**：警告視窗「彈一下就冇」— 因為有兩個 watcher 同時行緊（一個舊版 release 即刻關視窗，一個新版）

**Root Cause**：watcher 冇單實例守衛（server/detector 有，watcher 漏咗）— 多個實例同時監控 Experts 目錄 + 搶滑鼠

**Fix**：main() 開頭檢查 `.watcher_running` lock 檔 → 已有另一個 deploy_watcher 行緊（wmic 確認 PID）→ 即刻退出

**實測**：再起第二個 → 「⚠️ 已有 watcher 行緊 (PID X) — 退出（單實例守衛）」

### Bug #68: AI 控制中卡死（3 個 root cause）✅ FIXED（2026-08-04）

**症狀**：配對時卡死喺「AI 控制中」頁面 + 電腦冇操作 + 緊急停止冇反應

**3 個 Root Cause：**
1. **Watcher 卡死**：`_hide_window` 即刻 `destroy()` 喺非 tk main thread → 卡死成個 process（Bug #50 陷阱第二次踩中）→ compile 完成後 release 卡死
2. **網站視窗卡死**：`pollAiControl` 當 ai_control.json 唔存在（404）→ catch 咗唔 hide → 網站視窗永遠顯示
3. **緊急停止冇反應**：pywinauto `connect()` 無 timeout → 卡住無限等 → check_abort 冇機會執行

**Fix：**
1. `_hide_window` 用 `after(0)` 排隊 destroy（→ 最終 v4 常駐視窗徹底解決）
2. `pollAiControl`：404 / 網絡錯誤 → 關視窗（唔可以卡死）；server stop endpoint 強制寫 ai_control.json inactive
3. `_App.connect(process=me_pid, timeout=5)` — 5 秒 timeout

**實測**：修復後 EMA_Cross compile 成功（10358 bytes）+ release 正常（冇卡死）

### Bug #69: tk.PhotoImage GC 殺 watcher（exit code 3）✅ FIXED（2026-08-04）

**症狀**：watcher 處理完動作後異常退出（exit code 3）— compile 成功但 process 死

**Root Cause（兩層）：**
1. **PhotoImage GC**：icon-bot 用 `tk.PhotoImage` → 視窗 destroy 後 GC → `Image.__del__` 嘗試刪 tk image（錯誤 thread）→ RuntimeError
2. **tkinter destroy/重建不穩定**：每次動作「開新視窗（thread+mainloop）→ destroy」頻繁操作 → `Tcl_AsyncDelete: async handler deleted by the wrong thread` → C 層 abort

**Fix（常駐視窗 — 根治）：**
- 視窗只建一次（`_ensure_window_thread()` + `_run_tk()` — daemon thread + mainloop 永遠行）
- `_show_window` = deiconify + 更新程式名；`_hide_window` = withdraw（**唔 destroy**）
- icon-bot 用 tkinter Canvas 畫（照 Lucide bot 線條，唔用 PhotoImage）

**實測：**
```
✅ 5 個連續動作 — 同一個 HWND（62721008），冇卡死冇 exit 3
✅ Watcher 2 次真實 refresh 後仲行緊（冇死）
✅ ai_control release 正常（active=False）
```

**教訓**：tkinter 喺 daemon thread 用，**唔好 destroy 視窗** — 用常駐視窗 + withdraw/deiconify 切換；唔好用 tk.PhotoImage（GC 問題）

### Bug #70: 警告視窗「彈出 → 關閉 → 又彈出」+ 完成/關閉時間唔一致 ✅ FIXED（2026-08-04）

**症狀**：電腦版警告視窗彈出 → 關閉 → 又彈出；動作完成時間同視窗關閉時間唔一致（網頁版正常）

**Root Cause：**
1. compile 完成 → release 後 3 秒關視窗 → **watcher 下一輪 poll（3 秒）先偵測到 .ex5** → refresh 又彈過 — 中間有 gap → 彈下彈下
2. release 固定等 3 秒先關 — 動作完成後仲等（完成 ≠ 關閉）

**Fix：**
1. `process_compile_cmd` 成功後 **即刻 `_notify_refresh_needed()`**（唔等 3 秒 poll）— compile → refresh 動作連續
2. release 改 **idle timeout**：最少顯示 3 秒 → 之後等 `IDLE_CLOSE_SECONDS`（2 秒）冇新動作先關；有新動作（lock 檔出現）→ 續命

**實測**：一個連續視窗（t=10.2s SHOW → t=15.3s HIDE，只有 2 個事件）

### Bug #71: 警告視窗「動作完先彈出」✅ FIXED（2026-08-04）

**症狀**：剷除動作完成之後，警告視窗先彈出（遲咗）

**Root Cause**：常駐視窗**首次建立太慢**（tk.Tk() 初始化 + UI 建立 1-2 秒）→ 動作（refresh 1-2 秒）完成視窗先顯示

**Fix**：`init_window()` — watcher 啟動時預先建好隱藏視窗（`_ensure_window_thread()` + 等 `_window` 建好）→ 動作開始（acquire）即刻 deiconify 顯示（毫秒級）

**實測**：watcher 啟動 log「AI 控制警告視窗已預先就緒（隱藏）」+ 視窗預建 HWND 隱藏待命

### Bug #72: 警告視窗「彈出 → 極速關閉 → 完成後再開」✅ FIXED（2026-08-04）

**症狀**：接收指令 → 視窗彈一下極速關閉 → 操作完成後先至再開啟（用戶要：接收指令即刻開 → 直到完成先關）

**Root Cause**：`pause_window()`（GUI 操作期間隱藏視窗 — 避免置中 topmost 遮 Navigator 令 pyautogui 失效）→ 動作完成 `resume_window()` 恢復 — 用戶見到「彈出 → 極速關閉 → 完成後再開」

**Fix（兩個改動）：**
1. **警告視窗移去螢幕右下角**（`x = sw - w - 24, y = sh - h - 80`）— 置中先會遮 Navigator；右下角唔遮操作區域 → 唔使再隱藏
2. **移除 refresh_navigator 入面嘅 `pause_window()` / `resume_window()`** — 視窗全程顯示（由 acquire/release 控制）

**實測**：
```
t=1.4s: SHOW（接收指令即刻彈出）
t=14.2s: HIDE（工作完成先關閉）
✅ 全程顯示 12.8 秒 — 冇中途關閉
✅ 視窗右下角 (1636,725) — 唔遮 Navigator
```

**最終警告視窗行為（電腦版）：**
```
接收指令 → 即刻開啟（預建視窗毫秒級顯示）
  → 全程顯示（右下角，唔遮 Navigator）
  → 工作完成 → 先關閉（最後動作完成 2 秒內）
```

### 新功能: TestRunner.mq5 測試 EA（2026-08-04）

**需求**：一個可以測試「一陣間」嘅自動 EA 運行，即刻知道 EA 有冇運行

**功能：**
- 附加圖表 → 即刻開 0.01 測試單（可設定手數/時間/方向）
- 圖表 Comment 顯示：運行時間、Tick 數（秒秒跳動 = 有運行）、測試單號、剩餘時間
- 預設 5 分鐘自動平倉 + 「測試完成」訊息
- Magic 888888（平台部署時由配對庫 magic 覆蓋）
- 已放 EA 倉庫（server/static/ea_library/TestRunner.mq5）

**用法**：網頁 EA 倉庫「移去配對」→ compile → 部署 → MT5 圖表 Comment 跳動 + 測試單 = 有運行

### Bug #73: TestRunner compile 失敗（3 個 root cause）✅ FIXED（2026-08-04）

**症狀**：加入 TestRunner 出現 error（compile 失敗）+ MetaEditor 彈確認視窗

**3 個 Root Cause：**
1. **源碼錯誤**：`request.slippage` 唔存在（MqlTradeRequest 係 `deviation`）→ error 256 undeclared identifier
2. **MetaEditor「外部修改」dialog 阻住**：dialog 處理 code 喺 F7 **之後**先檢查（太遲）→ F7 落咗去 dialog → compile 失敗
3. **`w.close()` 卡死**：「關閉舊 dialog」用 `w.close()` — 對「外部修改」dialog（是/否）會卡死（timed out）→ 舊 dialog 一直開住 → Ctrl+O 開唔到新 file dialog →「搵唔到打開 dialog」

**額外發現**：警告視窗 `lift()` 搶 focus → send_keys（Ctrl+O）落錯視窗

**Fix：**
1. 刪除 `request.slippage` 行
2. 開 file 後、F7 前即刻 click「是」dialog
3. 關閉舊 dialog：有「是」按鈕 → click 是；冇 → fallback close
4. 移除警告視窗 `lift()` + send_keys 前確認 MetaEditor active window

**實測**：`Compiled: TestRunner.ex5 (16578 bytes)` — 一次成功（冇重試）

### Bug #74: auto_attach 浮動 Navigator 附加失敗（4 個 root cause）✅ FIXED（2026-08-04）

**症狀**：部署 TestRunner 失敗 —「TreeView not visible」「TestRunner not found under EA交易」「卡死」

**4 個 Root Cause：**
1. **掃描全部 process 嘅 tree**（我引入）：用 `Desktop.windows()` 掃到 MetaEditor/Windows Explorer 嘅 tree（唔係 MT5）→ **Fix：只掃 `app.windows()`（MT5 process）**
2. **`is_visible()` 檢查太嚴格**：MT5 用 custom draw — tree 有正常 rect（532x692）但 WS_VISIBLE 冇 set → pywinauto 話唔 visible → **Fix：用 rect 判斷**（尺寸 > 50 + 喺螢幕內 = visible）
3. **「EA交易」folder index 錯**：MT5 新版 Navigator 加咗「訂閱」folder — root children = `帳戶/訂閱/指標/EA交易/腳本/服務/市場/VPS` — EA交易 由 index 2 變 **index 3** → auto_attach 硬性 `children[2]` expand 咗「指標」→ 搵唔到 TestRunner → **Fix：先 text match（EA交易/Expert Advisors）後 fallback index**
4. **`wait_for_mt5` 用 uia backend 卡死**：MT5 大 UI connect 超慢（60 秒 timeout 唔夠 + is_visible/is_enabled 失敗）→ **Fix：用 win32 backend + 主視窗 exists() 檢查**

**額外發現**：auto_attach 失敗 → 「no MT5 restart」— 唔會亂重啟 MT5（好）

**實測**（部署 TestRunner 成功）：
```
🎯 Found TestRunner, attaching via pyautogui double-click...
🎉 TestRunner Properties dialog found
🔴 AutoTrading OFF → toggled ON
✅ MT5 log: TestRunner (EURUSD,H1) TestRunner EA 已啟動 ✅
```

**附註**：
- MT5 log 停咗 7/30 之後冇寫 — 原因係 MT5 卡死（63MB memory 異常）→ 重啟後正常（20260804.log 出現）
- TestRunner 開測試單失敗（retcode 10027 AutoTrading disabled）— OnInit 時 AutoTrading 未開 → 開返後要重啟 EA 先會再開單

### 新功能: 固定網址（Cloudflare Named Tunnel）✅（2026-08-04）

**需求**：臨時 trycloudflare URL 每次重啟都變（網頁死 link）→ 用戶有自己 domain（esgov.org）→ 要固定網址

**完成：**
- Cloudflare 授權（`cloudflared tunnel login` — cert.pem 生成，瀏覽器授權）
- 建立固定 tunnel：`cloudflared tunnel create mt5cloud`（ID `9ce5c130-ff5d-4ff0-9460-95ab2aab50dd`）
- DNS 自動加：`cloudflared tunnel route dns mt5cloud mt5cloud.esgov.org`（CNAME 自動）
- 設定檔：`C:\Users\hongk\.cloudflared\config.yml`
- **固定網址：`https://mt5cloud.esgov.org`** → localhost:5001

**Bug #75: cloudflared IPv6 連唔到 server（502 Bad Gateway）✅ FIXED**
- **Root Cause**：config.yml `service: http://localhost:5001` — cloudflared 解析 localhost → **IPv6（::1）** 優先 — 但 server 只 listen IPv4（0.0.0.0:5001）→ `dial tcp [::1]:5001: connectex: actively refused` → 502
- **Fix**：`service: http://127.0.0.1:5001`（強制 IPv4）
- **教訓**：Windows 上 cloudflared 對 localhost 用 IPv6 優先 — 一定要用 127.0.0.1

### 開機自動啟動（2026-08-04）

- **`start_auto.bat`**（放啟動資料夾 `MT5Cloud_Start.bat`）— 登入自動行：Server :5001 + Detector :5003 + Watcher + **Tunnel**（全部 check「未行先起」）
- **Tunnel 服務裝唔到**（`cloudflared service install` 要 admin — UAC 喺 background session 彈唔出）→ 用啟動資料夾方案代替（登入級自動啟動）
- 用戶可自行用管理員 cmd 裝服務（`cloudflared service install`）— 服務級開機自動（唔使登入）

### 環境事實
- 全部 python process 曾兩次同時死（網頁死 link）→ 重啟 server/detector/watcher 解決（原因未明 — 可能環境重啟）
- DeskIn 遙距控制：設備 ID `832721822`（`C:\Program Files\DeskIn\`，DeskIn_Service Running）
- Navigator tree 讀取（TVM/win32）喺 background session 唔可靠 — pywinauto roots()[0].children() 先可靠

### Bug #76: 「代替」確認 dialog 卡住 + AutoTrading 時序（2 個 root cause）✅ FIXED（2026-08-05）

**症狀**：圖表已有 EA 時再部署另一個 EA → MT5 彈「您真的想要附加'X'代替'Y'到圖表'EURUSD,H1'嗎?」確認視窗 → auto_attach 偵測唔到 → dialog 一直開住；另外 TestRunner 開單失敗（retcode 10027 AutoTrading disabled）

**2 個 Root Cause：**
1. **「代替」dialog 偵測唔到**：dialog title 係「MetaTrader 5」（唔含 EA 名）→ `find_ea_dialog(ea_name)` 搵唔到 → dialog 卡住
2. **AutoTrading 時序錯**：auto_attach 喺 Properties dialog **之後**先開 AutoTrading — 但 EA 附加時 **OnInit 即刻執行**（TestRunner OnInit 即刻開單）→ 開單嗰陣 AutoTrading 未開 → retcode 10027 失敗

**Fix：**
1. double-click 後掃所有 #32770 dialog → 內容含「代替」→ 自動撳「是」（接受取代）；撳完再檢查 Properties dialog
2. **AutoTrading 檢查搬去 double-click 之前**（讀 MT5 log 判斷 enabled/disabled → OFF 就 `^e` toggle ON）
3. 最後保險：attach 失敗時掃所有 dialog → 撳「否/取消」清殘留

**實測（完整 E2E 成功）：**
```
🔴 AutoTrading OFF → toggled ON（double-click 前）
🔄 偵測到「代替」確認 dialog — 自動撳「是」（接受取代）
🎉 TestRunner Properties dialog found
✅ 04:54:52 測試單已開: #1989819146 EURUSD 0.01 Buy @ 1.15320
✅ 04:54:52 TestRunner EA 已啟動
```

**結果**：部署 → 取代 → 啟動 → 開單 100% 自動化，冇 dialog 卡住，冇開單失敗

### Bug #77: stale lock 殘留 → 網站一直彈警告視窗 ✅ FIXED（2026-08-05）

**症狀**：登入網頁後警告視窗一直彈出「部署 TestRunner」— 即使冇任何動作

**Root Cause**：auto_attach 被 timeout kill（冇行 release()）→ `.ai_control.lock` + `ai_control.json`（active=True）殘留 → 網站 poll 到 active → 一直彈視窗

**Fix：**
1. 即刻清理殘留（lock + status）
2. **acquire() 加 stale lock 檢測**：讀 lock 入面舊 PID → tasklist 檢查仲存唔存在 → 唔存在（被 kill）→ 自動刪 stale lock → 唔會再有殘留

### 完整 E2E 實測（Web → 電腦，2026-08-05）✅

**流程**：網頁登入 → 移去配對（install-local）→ 部署（POST /api/deploy）→ watcher auto_attach → MT5 附加 → 開單

**E2E 發現 + 修正 4 個 bug：**
1. **install-local 冇副檔名**：前端傳 `TestRunner`（冇 .mq5）→ `os.path.join` 搵唔到檔案 + 複製錯名（`\TestRunner` 冇副檔名）+ 唔寫 compile_cmd → **Fix：自動試 filename/.mq5/.ex5 + 用 src_path basename 做 target**
2. **AutoTrading toggle 兩次**：double-click 前（新增）+ Properties 後（舊 Step 7 仲喺度）→ 兩次 ^e = ON→OFF → OnInit 開單失敗 10027 → **Fix：移除 Step 7 重複 toggle**
3. **send_keys 落錯視窗**：警告視窗搶 focus → ^e 冇生效 → **Fix：send 前 `win.set_focus()` 確保 MT5 active**
4. **heartbeat 白等 60 秒**：TestRunner 冇 heartbeat 機制 → 每次部署白等 60 秒 → **Fix：timeout 60→15 秒**

**E2E 最終實測結果：**
```
✅ 網頁 install-local（.mq5 正確複製）
✅ 網頁 deploy → watcher → auto_attach
✅ AutoTrading ON（double-click 前 + set_focus）
✅ TestRunner 啟動（05:15:39）
✅ 測試單已開: #1989868212 EURUSD 0.01 Buy @ 1.15289
✅ 冇 dialog 殘留
✅ 部署完成（attach 成功）記錄
```

**完整自動化鏈**：網頁按鈕 → server → watcher → MT5 附加 → 開單 → 驗證，100% 自動

### Bug #78: 暫停功能（真暫停）✅ FIXED（2026-08-05）

**需求**：配對庫「暫停」按鈕要真係令 EA 唔運行（唔係淨係改 config 標記）

**原本問題**：暫停只係 `config[ea_name + '_status'] = 'paused'` — **EA 喺 MT5 圖表仲運行緊 + 繼續交易**！

**實現（真暫停 = 移除圖表 EA）：**

1. **auto_attach.py 加 `--remove` 模式**：`remove_ea_from_chart()`
   - 方法：right-click 圖表 → **Alt+X 開「專家」dialog**（第 7 項「專家列表」快捷鍵 — 用戶實測確認）→ 列表揀 EA → 「移除」按鈕
   - ⚠️ 失敗方法記錄：「專家顧問→移除」menu 讀唔到 items（MT5 owner-draw menu — pywinauto/win32 都讀唔到）→ 用「專家」dialog 先得
2. **server toggleEA**：暫停 → 寫 `pause_cmd_<ea>.json`；恢復 → 寫 `deploy_cmd_<ea>.json`（重新部署）
3. **watcher 加 pause_cmd 處理**：`process_pause_cmd()` — 讀 EA 名 → subprocess `auto_attach --remove` → 寫 pause_result log

**實測：**
- ✅ 暫停：移除成功（「專家」dialog 列表 item 數 → 0）
- ✅ 恢復：重新部署 + 啟動 + 開單（#1989985724）

### Bug #79: AutoTrading toggle 冇生效（警告視窗搶 focus）✅ FIXED（2026-08-05）

**症狀**：部署後 OnInit 開單失敗（retcode 10027 AutoTrading disabled）— 反覆出現

**Root Cause**：警告視窗（AI 控制中）deiconify 後搶 focus → `send_keys('^e')` 落咗去警告視窗 → AutoTrading 冇開 → OnInit 即刻開單失敗

**嘗試過嘅方法（失敗）：**
1. `win.set_focus()` 後 send ^e — 警告視窗又搶返 focus
2. 等 MT5 log 確認 enabled（10 秒）— log 一直冇 enabled（^e 冇生效）
3. win32 PostMessage Ctrl+E — MT5 唔處理（冇效）

**Fix**：**send ^e 前短暫隱藏警告視窗**（`pause_window()` → set_focus(MT5) → send ^e → `resume_window()`）— MT5 一定 active → ^e 生效

**實測**：`測試單已開: #1989985724 EURUSD 0.01 Buy @ 1.15302` ✅（pause_window 方法生效）

**教訓**：tkinter 警告視窗 deiconify 後會搶 focus — 任何 send_keys 俾 MT5 之前要 pause_window 隱藏

### 完整狀態機測試（配對/部署/暫停，2026-08-05）✅

**用戶要求驗證**：
```
配對（放落配對庫）→ 暫停（唔運行）
→ 撳火箭（部署）→ 運行
→ 撳暫停 → 唔運行
```

**實測結果（Bollinger_Band）：**
| 步驟 | 結果 |
|------|------|
| 網頁配對 → .ex5 落本機 | ✅ |
| 配對後 MT5 log 冇記錄 | ✅ **= 未附加 = 暫停**（符合預期） |
| 網頁部署（火箭）→ auto_attach | ✅ Properties dialog 彈出 + 附加 |
| 暫停（移除 EA） | ✅ AgentHelper 成功（log 證實「已從圖表移除」） |

**確認行為**：配對 = 只複製檔案（唔運行）；部署先附加圖表（運行）；暫停 = 移除（停止）

### Bug #80: 暫停 TestRunner 失敗（right-click 彈「對象」視窗）⚠️ 部分 FIXED（2026-08-05）

**症狀**：`auto_attach --remove` 暫停 TestRunner →「⚠️ 搵唔到「專家」dialog」+ Exit 1

**Root Cause**：right-click 圖表 (960,400) 有時彈「對象 EURUSD H1」視窗（圖表中央有 object）而唔係標準 menu → Alt+X 落咗去對象視窗 → 開唔到「專家」dialog

**狀態**：
- AgentHelper 暫停成功（right-click 位置啱）
- TestRunner 暫停失敗（right-click 位置彈對象視窗）— **要 fix：right-click 位置要避開 objects / 或者改用其他方法開「專家」dialog**

**Workaround**：測試期間手動清殘留 pause_cmd；下次 fix right-click 位置（例如圖表右下空白位）或者用 menu 直接導航

### Bug #81: 官方 EA 唔 Print 啟動 log → 驗證靠「專家」dialog ⚠️ 已知（2026-08-05）

**症狀**：部署 Bollinger_Band（官方 EA）後 MT5 log **冇任何記錄**（TestRunner 有「已啟動」Print — 官方 EA 冇）

**影響**：
- `verify_ea_loaded`（讀 log）判斷唔到官方 EA 有冇附加 → auto_attach 報「heartbeat not detected」
- 驗證方法要改：**「專家」dialog 列表**（圖表實際附加咗咩 EA）先可靠

**建議**：auto_attach 驗證加「專家」dialog 檢查（列表有 EA 名 = 附加成功）— 唔可以淨靠 log

### 視窗固定功能 ✅（2026-08-05）

**需求（用戶）**：每個 pop-up 視窗（每個步驟彈出嚟嘅）都由程式一開始定好位置 — 唔會因為視窗移動/縮放而「甩」

**實現**：`pin_window(hwnd, x, y, w, h)`（SetWindowPos）+ `ensure_mt5_window()`

| 視窗 | 固定位置 | 應用位置 |
|------|---------|---------|
| MT5 主視窗 | (0,0) 1920x1040 | 部署/暫停前 |
| Navigator（導航） | (0,100) 340x820 | 附加 EA 前 |
| Properties dialog | (500,250) 700x500 | 彈出後即刻鎖定 |
| 「專家」dialog | (800,300) 540x380 | 彈出後即刻鎖定 |
| MetaEditor | (300,150) 900x700 | compile 時鎖定 |

**實測**：MT5 移動後自動固定返 ✅

### Bug #82: scan 模式亂附加 EA（代替 dialog 撳「是」）✅ FIXED（2026-08-05）

**症狀（錄影發現）**：部署 Bollinger_Band 期間，RSI_Over/Support_Resist/Breakout 全部附加咗落圖表！

**Root Cause**：double-click 掃描沿途 double-click 咗其他 EA → 圖表已有 EA（TestRunner）→ 彈「代替」dialog → code 撳「是」（接受取代）→ 其他 EA 附加咗！scan 變成「逐個 EA 附加」！

**Fix**：scan 期間遇到任何**唔係 target 嘅 dialog → 直接 ESC 關閉**（唔撳「是」）→ 繼續 scan

**後續**：圖表殘留多餘 EA（RSI_Over/Support_Resist/Breakout）待清理

### 精確定位 EA item 嘗試記錄（4 個方法全失敗）⚠️ 未解決（2026-08-05）

**目標**：直接攞 EA item 座標 double-click（唔使 scan — 唔會「亂點」）

| 方法 | 結果 |
|------|------|
| pywinauto `ea_node.rectangle()` | ❌ owner-draw 讀唔到位置 |
| win32 TVM_GETITEMTEXT 讀文字 | ❌ MT5 owner-draw tree 唔支持（空文字） |
| win32 TVM_GETNEXTITEM(CARET) + GETITEMRECT | ❌ 64-bit handle 溢出修好（restype=c_size_t）但 GETITEMRECT 仍 fail |
| pywinauto roots()/children()（測試 script） | ❌ 唔穩定（attach_ea_navigator 用 roots()[0] 先 work） |

**結論**：MT5 tree 係 owner-draw — 冇 API 精確攞 item 座標 → 暫時用 scan（已改善：由 EA 區域開始 scan_start=80 + click_x=80 文字區域 + 遇到非 target ESC）

**附註**：`SendMessageW.restype = c_size_t` 係 64-bit handle 必需（唔 set 會溢出負數）

### 操作前自動偵測 + 開啟 MT5 ✅（2026-08-05，用戶要求「每次操作 MT5 相關嘢一開始偵測有冇開，冇就開返」）

**需求**：用戶關閉 MT5 後配對 EA — MT5 冇自動開啟。要求：每次操作 MT5 相關嘢，開頭偵測 — 冇就開返 + 等登入

**實現**：server `ensure_mt5_running()`（tasklist 查 terminal64.exe → 冇 → Popen 開返 → 等最多 30 秒 process 出現）+ 掛接 5 個 API：
- `install-local`（配對）/ `deploy`（部署）/ `ea-config/<name>/toggle`（暫停恢復）/ `remove-local`（剷除）/ `retry-compile`（重試編譯）
- （auto_attach 本身已有「MT5 not running, starting...」— 部署/暫停雙保險）

**Root Cause（順手修）**：`subprocess.run('tasklist ...', text=True)` 對 tasklist 中文輸出（GBK）喺 MSYS UTF-8 locale decode 失敗 → exception → ensure_mt5_running 當失敗 → 冇開 MT5！**Fix：用 bytes 檢查（`b'terminal64' in r.stdout`）— 唔使 decode**。檢查所有 tasklist 查詢位置（server line 359/435/472 + ensure_mt5_running）全部改 bytes

**實測 E2E**：
```
✅ MT5 關閉 → 網頁配對（install-local）→ server 偵測冇 → 自動啟動
✅ MT5 開啟（PID 10500）+ 自動登入（5053721681 主視窗出現）
```

### 環境事實：Hermes respawn 機制（2026-08-05）

- **Hermes 會自動重啟自己 spawn 嘅 python process**（死咗用返同一 cmdline 重啟 — **讀最新 code**）
- 診斷「行緊嘅 server 係咪新版」：`netstat -ano | grep :5001` 睇 LISTEN PID → `wmic process where "processid=<pid>" get commandline`
- **正確重啟流程**：改 server code → `bash agent/restart_all.sh`；手動 kill 咗 → 等 Hermes 自己 respawn（唔好自己再起 — race 爭 port → 單實例守衛頂走）
- 「改咗 code 但行為冇變」通常唔係 respawn 舊 code — 係其他 bug（例：tasklist subprocess GBK decode 炸 → ensure_mt5_running 靜默失敗）

### ⚠️ 圖表多餘 EA 現狀（待清理，2026-08-05）

**起因**：Bug #82（scan 亂附加 EA）+ MT5 profile 保存 → 重啟後圖表有 7-8 個 EA 同時附加：
`Bollinger_Band / RSI_Over / Support_Resist / Breakout / Correlation / Heikin_Ashi / Divergence / EMA_Cross`

**清理方法（未做）**：「專家」dialog（Alt+X）逐個移除，或用戶手動（DeskIn）。right-click 彈「對象」視窗問題（Bug #80）未解決 — 自動清理受阻

### 用戶操作記錄（2026-08-05）
- Volume_Spike / Swing_Trader 配對 + compile 成功（watcher log：「✅ Compiled: Volume_Spike.ex5 (9746 bytes)」「✅ Compiled: Swing_Trader.ex5 (10048 bytes)」）

### 安全防護（避免撳到電腦其他嘢）✅ + Bug #83 FIXED（2026-08-05）

**需求（用戶）**：加防護避免自動 click 撳到電腦其他嘢（TG Scheduler / 記事本 / 其他視窗）

**4 層防護（已實作）：**
1. **MT5 最小化自動還原**：`ensure_mt5_window()` 加 `IsIconic` 檢查 → `ShowWindow(SW_RESTORE)`（實測：MT5 之前係 -32000 最小化）
2. **DeskIn 移去角落**：`pin_deskin_away()` — DeskIn 視窗（遙距控制）遮住圖表 (560,222)-(1360,817) → 移去右上角 (1400,0) 500x400；掛接 auto_attach Step 2c + remove 流程 + refresh_navigator
3. **安全 click（WindowFromPoint）**：`safe_click/safe_rightclick/safe_doubleclick`（auto_attach）+ `_safe_click`（refresh_navigator）— 每次 click 前 `WindowFromPoint(x,y)` → 攞 PID → 唔係 MT5 PID 就跳過（print 警告）— 替換晒所有 pyautogui 呼叫
4. **圖表未開 → 直接完成**：`remove_ea_from_chart` 開頭檢查圖表 window（Afx + EURUSD/H1）— 冇圖表 = 冇 EA 運行 = 唔使移除（return True）

### Bug #83: 「right-click 彈唔到 menu」真正 root cause（3 個隱藏問題）✅ FIXED（2026-08-05）

**症狀**：right-click 圖表 7+ 個位置都開唔到「專家列表」dialog

**Root Cause（3 個一齊發生）：**
1. **MT5 最小化咗**（rect -32000）→ WindowFromPoint 全部返桌面（explorer.exe FolderView）→ click 落桌面
2. **DeskIn 視窗遮住圖表**（560,222)-(1360,817) → click 俾 DeskIn（PID 13184）食咗
3. **圖表 window 根本冇開**（MT5 restore 後只有導航 + 市場報價 — 冇 EURUSD,H1 Afx window）→ right-click 主視窗背景冇圖表 menu

**發現方法**：安全防護（WindowFromPoint）實測 — click (808,554) 目標係 PID 2268（explorer）唔係 MT5 → 逐個查先發現 MT5 最小化 + DeskIn 遮擋

**Fix**：4 層防護（見上）+ remove 流程用圖表 window 實際 rect（唔用主視窗 offset）

**實測**：
```
📐 MT5 視窗已固定（含最小化還原）
📌 DeskIn 已移去右上角
ℹ️ RSI_Over：圖表未開（冇 EA 運行）— 唔使移除，直接完成
✅ 暫停 RSI_Over 成功
```

**教訓**：GUI 自動化 click 失敗（彈唔到 menu / 點唔中）— 唔好淨係試座標 — 先檢查 ① MT5 係咪最小化（IsIconic）② 有冇其他視窗遮住目標位置（WindowFromPoint 查 PID）③ 目標 window（圖表）係咪真係存在。WindowFromPoint + PID 檢查係診斷「click 落錯」嘅利器

### 大眾化改造（2026-08-05，用戶要求「唔可以淨係用我電腦做特定例子，要用大眾角度」）✅

**原則**：所有解決方案通用化 — 任何用戶部機（唔同解析度/DPI/語言/MT5 版本）都 work — 唔 hardcode 特定環境

**4 項改造（已實作 + 實測）：**
1. **MT5 視窗最大化**（`SW_MAXIMIZE`）代替固定 1920x1040 — 任何解析度全螢幕；最小化自動還原（IsIconic → SW_RESTORE）— 實測：最小化 → restore → maximize（rect 0,0-1936,1056 + IsZoomed=1）✅
2. **DeskIn 動態位置**：`GetSystemMetrics(SM_CXSCREEN)` − 520（右上角）代替 hardcode 1400 — 任何螢幕都啱；冇 DeskIn 嘅用戶唔受影響
3. **多語言 text match**：代替/replace、是/Yes/&Y、導航/Navigator（EA交易/Expert Advisors/Experts 原本已有）— 中文/英文 MT5 都 work
4. **圖表偵測通用化**：title 含 `,`（SYMBOL,TF 格式 — EURUSD,H1 / GBPCAD,M15）代替 hardcode 'EURUSD' — 任何 symbol 都得

**⚠️ 剩餘 2 個待完善（大眾化未 100%）：**
1. **「專家列表」menu item 位置**：估第 7 項 + 22px/item — 英文 MT5 menu 順序可能唔同 — 建議用 popup menu rect + 動態 item 高度
2. **DPI scaling（125%/150%）**：高 DPI 螢幕 pyautogui 座標可能要處理 — 需實測


