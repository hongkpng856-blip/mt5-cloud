# 📋 MT5 Cloud — Progress & Bugs

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
| **Navigator Auto-Attach EA** | 🔧 進行中 | 70% — 手動成功，Agent 自動化未通過 |
| Dashboard Alive 🟢🔴 指示 | ⏳ 未開始 | 0% |
| 已有 EA chart 替換 dialog | ⏳ 未開始 | 0% |
| E2E Dashboard 完整測試 | 🔧 進行中 | 40% — compile+heartbeat OK, attach 未通過 |

---

## 🗓️ Session Log

### 2026-07-29（今日）

**目標**：解決 Navigator double-click attach 新 EA 問題

**成果**：
- ✅ 手動成功 attach ATR_Stop + Bollinger_Band（pyautogui double-click）
- ✅ 發現 `select()+ensure_visible()` 會將 EA 滾到 TreeView 最頂 → 唔使逐行掃描
- ✅ 發現 MT5 係阿拉伯文 locale → 改用 `children[2]` 位置索引
- ✅ 修復 ctypes 64-bit hwnd overflow（`c_size_t` + `c_void_p(hwnd)` cast）
- ✅ AHK `nav_on.ahk` 可以手動開 Navigator
- ❌ Agent 自動化 attach 仍失敗（Navigator toggle 唔可靠 + 開 chart 後 Navigator 收埋）
- ❌ Agent 失敗後不斷重啟 MT5，導致 chart 丟失惡性循環

**Git commits**：
- `7a67334` — Navigator attach: pyautogui double-click (not select+Enter)
- `a6f669e` — AHK nav_on.ahk + ctypes 64-bit fix
- `23fa257` — AHK-first attach: attach_ea.ahk full solution + subprocess import fix
- `c6e1ba7` — Navigator attach: direct click at TreeView top (no scan needed)
- `6c6290b` — Fix ctypes 64-bit hwnd overflow: c_void_p(hwnd) cast in callback

### 2026-07-28

**目標**：Agent auto-attach EA 到 chart

**成果**：
- ✅ Heartbeat injection（OnInit + OnTick FileWrite）
- ✅ metaeditor64 /compile /log: 參數修正
- ✅ retcode=10027 → 改用 auto-attach（唔用 order_send）
- ✅ Dashboard 儲存按鈕合併入 Deploy
- ✅ Dashboard 一鍵加入配對 + 自動 save
- ❌ Navigator select()+Enter 唔觸發 EA attach（Enter 只 expand/collapse）
- ❌ uia backend 搵唔到 MT5 TreeView

### 2026-07-27

**目標**：Agent deploy + Dashboard 功能

**成果**：
- ✅ Socket.IO 即時 deploy
- ✅ HTTP poll fallback
- ✅ Dashboard 分析（Trades/Win/P&L）
- ✅ Correlation Matrix
- ✅ Symbol mapping（DAX40→DE40, SP500→US500）
- ✅ Cloudflare Tunnel
- ✅ Heartbeat 追蹤 + Alive 指示

### 2026-07-07 ~ 07-26

**成果**：
- ✅ Server + Flask + Socket.IO + SQLite
- ✅ Dashboard UI（登入、EA table、分析）
- ✅ EA Library（30 個 EA .mq5）
- ✅ Agent 基本架構（連線、sync、install）
- ✅ MT5 Python API 整合
- ✅ 多個 bug 修復（eventlet crash、port conflict 等）

---

## 🐛 Fixed Bugs

| # | Bug | 原因 | Fix | 日期 |
|---|-----|------|-----|------|
| 1 | Symbol dropdown 彈走 | auto-refresh rebuild table | `_updateEAData()` 只改數字 cell | 07-27 |
| 2 | DAX40 交易失敗 | Broker 叫 DE40 | Symbol mapping | 07-27 |
| 3 | SP500 交易失敗 | Broker 叫 US500 | Symbol mapping | 07-27 |
| 4 | Agent deploy 唔郁 | eventlet crash + Socket.IO 阻塞 | threading mode | 07-26 |
| 5 | Port 5000 zombie | eventlet process 不死 | 改用 port 5002 | 07-26 |
| 6 | ngrok bandwidth exceeded | Free tier 1GB | Cloudflare Tunnel | 07-26 |
| 7 | Socket.IO 斷線 | install 阻塞 event loop | 背景 thread | 07-27 |
| 8 | Agent 連唔到 server | polling namespace bug | 只行 WebSocket | 07-27 |
| 9 | retcode=10027 | AutoTrading OFF, order_send 失敗 | 改 auto-attach | 07-28 |
| 10 | 儲存配對按鈕多餘 | 同 Deploy 重疊 | 合併入 Deploy | 07-28 |
| 11 | 一鍵加入配對要手動 save | UX 問題 | `addEAToPairing()` 自動 save | 07-28 |
| 12 | Heartbeat file 唔存在 | EA source 冇 FileWrite | 注入 OnInit+OnTick | 07-28 |
| 13 | metaeditor compile 失敗 | `/s` 參數錯 | 改用 `/log:` | 07-28 |
| 14 | Heartbeat file 編碼錯 | UTF-8 | UTF-16 LE | 07-28 |
| 15 | `'EA交易' not found` | MT5 阿拉伯文 locale | `children[2]` 位置索引 | 07-29 |
| 16 | `import subprocess` missing | 新加 AHK 調用 | 加入 import | 07-29 |
| 17 | `import threading` missing | 誤刪 | 還原 | 07-29 |
| 18 | ctypes OverflowError | 64-bit hwnd overflow | `c_size_t` + `c_void_p(hwnd)` | 07-29 |
| 19 | `EnsureVisible()` deprecated | pywinauto 新 API | `ensure_visible()` | 07-29 |
| 20 | AHK `Loop % var` error | AHK v2 語法 | `Loop rowCount` | 07-29 |
| 21 | Navigator 收埋 | Ctrl+N 開 chart 自動隱藏 | 先 chart 後 Navigator | 07-29 |
| 22 | pyautogui 掃描太慢 | 逐行 60s | `ensure_visible` 後 click 頂部 | 07-29 |
| 23 | AHK ControlTreeView 卡住 | MT5 custom TreeView | 改用 pyautogui | 07-29 |

---

## 🔴 Open Bugs

### Bug #1: Navigator Toggle 唔可靠（Critical）

**現象**：Agent 嘅 `nav_on.ahk` 用固定坐標 `(wx+120, wy+28)` 點擊 View menu，MT5 重啟後坐標偏移，Navigator panel 開唔到。

**影響**：Agent auto-attach 100% 失敗，因為冇 Navigator 就冇得 double-click。

**建議 Fix**：
- 搵 MT5 toolbar Navigator 按鈕坐標（toolbar 入面約第 5-7 個按鈕）
- 或用 `TB_GETRECT` message 取 button rect
- 或用 MT5 嘅 keyboard shortcut（如果有）

**相關代碼**：`agent/nav_on.ahk`、`agent/agent.py` Step 2

---

### Bug #2: 開新 chart 自動收埋 Navigator（Critical）

**現象**：Agent 每次 attach 先 `Ctrl+N` 開新 chart，MT5 自動關閉 Navigator panel。之後 toggle Navigator 唔可靠（見 Bug #1）。

**影響**：同 Bug #1 疊加，導致完全失敗。

**建議 Fix**：
- 唔開新 chart，用現有 chart（如果已有 open chart）
- 或：開 chart → 等 5s → 開 Navigator → 等 3s → double-click
- 關鍵：Navigator 開啟後要 **驗證 TreeView visible=True** 先繼續

**相關代碼**：`agent/agent.py` Step 1-2

---

### Bug #3: Agent 失敗後不斷重啟 MT5（High）

**現象**：Agent attach 失敗 3 次 → `taskkill MT5` → 重啟 → chart 丟失 → 下一個 EA 又失敗 → 又重啟 → 惡性循環。

**影響**：已成功 attach 嘅 EA（如 ADX_Trend）會因為 MT5 重啟而丟失 chart，heartbeat 消失。

**建議 Fix**：
- 失敗後 **唔重啟 MT5**，改為 skip 呢個 EA + 繼續下一個
- 重啟後要等 MT5 完全 load 完（至少 10s）
- 保持已 attach 嘅 EA chart

**相關代碼**：`agent/agent.py` attach retry + MT5 restart logic

---

### Bug #4: pyautogui double-click 喺 background Agent 唔 work（Critical）

**現象**：手動 Python console 測試 `pyautogui.doubleClick(tv_rect.top+9)` 成功，但 Agent 背景執行時 pyautogui/SendInput/AHK Click/SendMessage 全部唔 work。`auto_attach.py` 從 terminal tool 直接跑成功，但被 Agent 用 subprocess 調用時 timeout。

**原因**：Agent 背景 process 冇 interactive desktop session。`subprocess.run()` 繼承 parent 嘅 session context，所以子 process 都冇 desktop access。

**已試過嘅方法**：
- pyautogui.doubleClick() ❌
- AHK Click via subprocess ❌
- win32api mouse_event ❌
- SendInput (MOUSEINPUT) ❌
- SendMessage WM_LBUTTONDBLCLK ❌
- PostMessage WM_LBUTTONDBLCLK ❌
- TVM_SELECTITEM(TVGN_DBLCLICK) ❌
- subprocess 調用 auto_attach.py ❌（timeout）
- subprocess + CREATE_NEW_CONSOLE ❌

**唯一成功嘅方法**：
- Terminal tool 直接行 `python agent/auto_attach.py --ea Bollinger_Band --symbol EURUSD --tf H1` ✅

**建議 Fix**：
- 方案 A：改 Agent 用 `terminal()` Hermes tool 代替 subprocess 去執行 attach（但 Agent 本身係 Python script，call 唔到 Hermes tool）
- 方案 B：Agent 將 attach 指令寫入一個 queue file，由 Hermes cron job 或 user 手動執行
- 方案 C：用 `CreateProcessAsUser` 或 `STARTF_USESHOWWINDOW` 旗標開新 console process
- 方案 D：用 `wmic` 或 `schtasks` 開一個 scheduled task 行 auto_attach.py

---

### Bug #5: `find_ea_dialog()` 嵌套定義（Low）

**現象**：`find_ea_dialog()` 喺 Step 5 定義一次，fallback scan 又定義一次（nested），可能導致混淆。

**建議 Fix**：提取到 function 層級。

---

## 🔑 關鍵發現（下一位 Agent 必讀）

### Navigator Attach 正確流程

```
1. 唔開新 chart（用現有 chart）
2. 開 Navigator panel（AHK nav_on.ahk 或鍵盤）
3. pywinauto win32 backend → children[2] = EA交易（locale-independent）
4. select(ea_node) + ensure_visible(ea_node)
5. pyautogui.doubleClick(tv_rect.left+50, tv_rect.top+9)
6. 確認 #32770 dialog → Enter → AutoTrading ON
7. Heartbeat verify
```

### 已驗證嘅手動成功紀錄

| EA | 日期 | 方法 | Heartbeat |
|----|------|------|-----------|
| ATR_Stop | 07-29 | pyautogui double-click @ tv_rect.top+9 | 🟢 |
| Bollinger_Band | 07-29 | pyautogui double-click scan @ y=705 | 🟢 |
| ADX_Trend | 07-28 | select()+Enter（EA 已 attach） | 🟢 |

### 所有失敗嘅方法（唔好再試）

| 方法 | 結果 | 原因 |
|------|------|------|
| `select() + Enter` | ❌ | Enter 只 expand/collapse，唔觸發 attach |
| `ClickInput(double=True)` | ❌ | pywinauto 唔觸發 MT5 TreeView |
| 右鍵 + 鍵盤操作 | ❌ | 太多步驟，唔可靠 |
| `WM_LBUTTONDBLCLK` SendMessage | ❌ | 坐標落錯區域 |
| AHK `ControlTreeView DoubleClick` | ❌ | MT5 custom TreeView 唔支援 |
| AHK `ControlClick` 掃描 | ❌ | 坐標計算錯誤 |
| AutoIt `control_tree_view` | ❌ | 搵唔到 SysTreeView32 control |
| `TVM_GETITEMRECT` + WriteProcessMemory | ❌ | 冇 SeDebugPrivilege |
| uia backend | ❌ | 返回 0 Tree controls |

### MT5 環境特點

| 特點 | 值 |
|------|-----|
| MT5 語言 | 阿拉伯文（المستشارون المختصون = EA交易） |
| MT5 PID | 會因 Agent 重啟而改變 |
| MT5 主視窗 class | `MetaQuotes::MetaTrader::5.00` |
| Navigator TreeView class | `SysTreeView32` |
| EA dialog class | `#32770` |
| Heartbeat file 路徑 | `C:\Users\hongk\AppData\Roaming\MetaQuotes\Terminal\Common\Files\hb_<EA>.txt` |
| Heartbeat file 編碼 | UTF-16 LE |
| MT5 Log 編碼 | UTF-16 LE |
| MT5 自動重啟 | taskkill 後 ~3s 自動重啟，新 PID |
| 開新 chart 後 | Navigator 自動收埋 |

---

## 📋 TODO（優先順序）

- [ ] **P0** ~~修復 Navigator toggle 唔可靠~~ ✅ Bug #1 FIXED: ShowWindow
- [ ] **P0** ~~修復開 chart 後 Navigator 收埋~~ ✅ Bug #2 FIXED: skip if chart exists
- [ ] **P1** ~~Agent 失敗後唔重啟 MT5~~ ✅ Bug #3 FIXED: removed restart
- [ ] **P0** 修復 background Agent double-click 唔 work（Bug #4）
- [ ] **P1** 完整 E2E Dashboard 測試：Deploy → auto_attach → heartbeat 🟢
- [ ] **P2** Dashboard Alive 🟢🔴 嵌入 EA card
- [ ] **P2** 處理已有 EA 嘅 chart（替換確認 dialog）
- [ ] **P3** Cloudflare named tunnel（固定 URL）
- [ ] **P3** 清理臨時 helper 腳本

---

*Last updated: 2026-07-29*
