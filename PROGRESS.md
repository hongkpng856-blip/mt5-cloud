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
| **Navigator Auto-Attach EA** | 🔧 進行中 | **90% — terminal 成功，Agent 背景仍需解決** |
| AgentHelper (command file auto-deploy) | ✅ 完成 | **100% — 已測試成功 🎉** |
| Dashboard Alive 🟢🔴 指示 | ⏳ 未開始 | 0% |
| 已有 EA chart 替換 dialog | ⏳ 未開始 | 0% |
| E2E Dashboard 完整測試 | 🔧 進行中 | **60% — compile+heartbeat+AgentHelper OK, Agent 背景 attach 未通過** |

---

## 🗓️ Session Log

### 2026-07-30（凌晨 01:00~02:40 — 繼續 debug）

**目標**：Compile AgentHelper FILE_COMMON 更新 + E2E 流程測試

**成果**：
- 🎉 **AgentHelper FILE_COMMON 已 compile + 部署成功**（12582 bytes, 0 errors）
- 🎉 **AgentHelper command file 處理成功**（file deleted = proof）
- 🎉 **Bollinger_Band 已 deploy** 🟢（terminal auto_attach）
- 🎉 **4 個 EA 同時運行中**：ADX_Trend, ATR_Stop, Bollinger_Band, AgentHelper
- ✅ `FileIsExist` 唔支援 `FILE_COMMON` flag → 改用 `FileOpen` 直接 check
- ✅ 改用 `ChartFirst()` + `ChartNext()` 掃描現有 chart（代替 `ChartOpen`）

**關鍵技術發現**：
1. **`ChartApplyTemplate` 喺 MQL5 code 唔會 attach EA** — 只 apply chart 設定（顏色/indicator），EA section 被 ignore。EA 只能經 GUI template apply 或 Navigator double-click 先 attach。
2. **`ChartOpen` 喺 MT5 build 6061 返回 0** — 可能 restricted 或 build 限制，開唔到新 chart
3. **`FileIsExist(filename, FILE_COMMON)` 唔通過 compile** — 呢個 build 唔支援 `common_flag` 參數
4. **改用 `FileOpen(filename, FILE_READ|FILE_TXT|FILE_COMMON)` check file 存在** — 得咗
5. **`FILE_READ|FILE_TXT|FILE_ANSI|FILE_COMMON` 有衝突** — FILE_ANSI 同 FILE_COMMON 可能 bit 位置重疊
6. **`0x4000` 同 `FILE_COMMON` 喺 FileOpen 都 work** — 但 `FileIsExist` 兩個都唔得

**Git commits**：
- `8ec16a3` — Found: ChartApplyTemplate in MQL5 code doesn't attach EA
- `9b73e7e` — Fix AgentHelper: FileIsExist doesn't support FILE_COMMON
- `d1ce282` — Update PROGRESS.md with handoff notes
- `ed21f37` — PROGRESS: add Handoff Notes + system architecture diagram
- `fd1ecd9` — AgentHelper deployed! + FILE_COMMON fix

---

## 🐛 Fixed Bugs

| # | Bug | 原因 | Fix | 日期 |
|---|-----|------|-----|------|
| 1~23 | 見之前版本 | — | — | 07-27~29 |
| 24 | Navigator double-click 對新 EA 冇效 | MT5 需要 EA 先經 install flow 註冊 | Agent install flow download+save+compile | 07-30 |
| 25 | AgentHelper command file 唔 processing | `FileIsExist` 冇 `FILE_COMMON` 支援 | 改用 `FileOpen` + `FILE_COMMON` | 07-30 |
| 26 | metaeditor64 CLI 間中冇 .ex5 輸出 | CLI mode 缺 dll/路徑 | 用 MetaEditor GUI（F7） | 07-30 |
| 27 | MT5 語言係阿拉伯文 | 安裝時 default locale | 改 `terminal.ini` | 07-30 |
| 28 | auto_attach.py 重啟 MT5 | 重啟後 registration 丟失 | 移除 restart logic | 07-30 |
| **29** | **`ChartApplyTemplate` 喺 MQL5 code 唔 attach EA** | Build 6061 限制 / MQL5 設計 | 用 terminal `auto_attach.py` 代替 | 07-30 |
| **30** | **`ChartOpen` 返回 0（開唔到新 chart）** | Build 6061 可能 restricted | 改用 `ChartFirst()` + `ChartNext()` 掃現有 chart | 07-30 |
| **31** | **`FileIsExist(filename, FILE_COMMON)` compile error** | Build 6061 唔支援 `common_flag` 參數 | 改用 `FileOpen` 直接 open/check | 07-30 |
| **32** | **`FILE_ANSI | FILE_COMMON` bit 衝突** | 兩個 constant 可能相同 bit 值 | 省略 `FILE_ANSI` | 07-30 |

---

## 🔴 Open Bugs

### Bug #4: pyautogui double-click 喺 background Agent 唔 work（Critical — 最後 blocker）

**現象**：手動 `terminal` tool 行 `auto_attach.py` 成功，Agent 背景 `subprocess` 失敗。

**原因**：Agent background process 冇 interactive desktop session。

**已試過嘅方法（全部 ❌）**：
pyautogui, AHK, win32api, SendInput, SendMessage, PostMessage, subprocess, CREATE_NEW_CONSOLE

**唯一成功**：`terminal` tool 直接行 `python auto_attach.py --ea <EA> --symbol EURUSD --tf H1`

**Workaround**：Agent 負責 download+save+compile（註冊 EA），用戶用 terminal auto_attach.py 完成部署。完整流程見下方。

---

## 💡 完整部署流程（最終推薦版）

```
Dashboard Click Deploy
  ↓
Agent: download .mq5 + inject heartbeat + compile     ← 註冊 EA 🟢
  ↓
Agent: write agent_helper.txt → Common/Files            ← 通知 AgentHelper
  ↓
AgentHelper OnTimer(5s): 讀取 + 刪除 command file       ← 確認收到 ✅
  ↓
用戶/下一位 Agent 用 terminal 行 auto_attach.py        ← 實際 attach EA 🎯
  ↓
EA attached + Heartbeat 🟢 — Deploy complete!
```

### auto_attach.py 執行指令（唯一可靠方法）

```bash
# 一定要從 terminal tool 行（唔可以從 execute_code 或 Agent background）
cd /c/Users/hongk/Desktop/mt5-cloud
timeout 120 python -u agent/auto_attach.py --ea <EA_NAME> --symbol EURUSD --tf H1
```

### 已知 MQL5 限制（Build 6061）

| API | 結果 | 備註 |
|-----|------|------|
| `ChartOpen(symbol, tf)` | ❌ 返回 0 | 不能開新 chart |
| `ChartApplyTemplate(chart_id, template)` | ❌ 唔 attach EA | 只改 chart 設定 |
| `FileIsExist(file, FILE_COMMON)` | ❌ compile error | 唔支援 common_flag |
| `FileOpen(file, FILE_READ\|FILE_TXT\|FILE_COMMON)` | ✅ | 正確用法 |
| `FileDelete(file, FILE_COMMON)` | ✅ | 正確用法 |
| `GlobalVariableSet/Check` | ✅ | 冇限制 |

---

## 📊 Current Status（2026-07-30 02:40）

### 服務

| 服務 | 狀態 |
|------|------|
| Flask Server :5002 | ✅ |
| Cloudflare Tunnel | ✅ `having-bent-bunch-theater.trycloudflare.com` |
| MT5（Chinese UI） | ✅ PID varies |
| Agent DEV00001 | ✅ monitoring |

### EA Heartbeats

| EA | Symbol | TF | Heartbeat | Deploy 方法 |
|----|--------|----|-----------|------------|
| ADX_Trend | EURUSD | H1 | 🟢 | Agent install |
| ATR_Stop | EURUSD | H1 | 🟢 | Agent install |
| Bollinger_Band | EURUSD | H1 | 🟢 | terminal auto_attach |
| AgentHelper | EURUSD | H1 | 🟢 | MetaEditor compile + terminal auto_attach |

### Key Files

| File | 狀態 |
|------|------|
| `server/static/ea_library/AgentHelper.mq5` | ✅ 已更新（heartbeat + FILE_COMMON + ChartFirst fallback） |
| `agent/AgentHelper.mq5` | ✅ 已更新（心跳注入版） |
| `agent/auto_attach.py` | ✅ 已修復（冇 restart logic, c_void_p fix） |
| `agent/agent.py` | ✅ 已修復（ShowWindow, subprocess, c_void_p） |
| `agent/nav_on.ahk` | ✅ AHK Navigator toggle |
| `PROGRESS.md` | ✅ 完整 handoff notes |

---

## 📋 TODO（優先順序）

- [ ] **P0** ~~Bug #1~#3~~ ✅ FIXED
- [ ] **P1** ~~Bug #4 background pyautogui~~ 🔴 **Workaround**: 經 terminal auto_attach.py 完成
- [ ] **P1** ~~ChartApplyTemplate/ChartOpen MQL5 限制~~ 🔴 改用 terminal auto_attach.py
- [ ] **P2** Dashboard Alive 🟢🔴 嵌入 EA card
- [ ] **P2** 處理已有 EA 嘅 chart（替換確認 dialog）
- [ ] **P3** Cloudflare named tunnel（固定 URL）
- [ ] **P3** 整合自動化：cron job 定時行 auto_attach.py 處理 pending deploy

---

## 🤝 Handoff Notes（下一位 Agent 必讀）

### 系統架構

```
┌─────────────┐  Socket.IO  ┌─────────────┐  terminal tool  ┌─────┐
│  Flask Server│ ←────────→ │   Agent     │ ←─────────────→ │ MT5 │
│  :5002       │            │  DEV00001   │  auto_attach.py │     │
│  +SQLite     │            │  agent.py   │  (pyautogui)    │ PID │
│  +Dashboard  │            │  +heartbeat  │                 │ ????│
└──────┬───────┘            └──────┬───────┘                 └─────┘
       │                           │
       ▼                           ▼
  ea_library/                  MQL5/Experts/
  32 .mq5 sources              4 EAs .ex5
  AgentHelper.mq5              AgentHelper.ex5
```

### 快速接手步驟

```bash
# 1. 檢查各服務
curl -s http://localhost:5002/api/status
curl -s http://localhost:5002/api/heartbeats

# 2. 檢查 MT5 + MetaEditor
tasklist | grep -i "terminal64\|metaeditor"

# 3. 檢查 EA heartbeats
ls -la /c/Users/hongk/AppData/Roaming/MetaQuotes/Terminal/Common/Files/hb_*.txt

# 4. Deploy EA（如果 Agent 已 install）
cd /c/Users/hongk/Desktop/mt5-cloud
timeout 120 python -u agent/auto_attach.py --ea <EA_NAME> --symbol EURUSD --tf H1

# 5. 如果需要 compile（MetaEditor GUI）
# 先確保 MetaEditor 已開
# 用 pywinauto: Ctrl+O → 選 .mq5 → F7
```

### 關鍵規則（唔好再試）

- ❌ `ChartApplyTemplate` 喺 MQL5 code 唔 attach EA
- ❌ `ChartOpen` build 6061 restricted（返回 0）
- ❌ `FileIsExist` 唔支援 `FILE_COMMON` flag
- ❌ pyautogui 唔 work 喺 Agent background / execute_code sandbox
- ❌ `metaeditor64.exe CLI` 唔可靠（有時冇 .ex5）
- ✅ **terminal tool + auto_attach.py** — 唯一可靠方法
- ✅ **MetaEditor GUI（F7）** — 唯一可靠 compile 方法
- ✅ **Agent install flow（download+save+compile）** — 唯一註冊 EA 方法

### 常用除錯指令

```bash
# MT5 log
tail -n 20 "$(ls -t /c/Users/hongk/AppData/Roaming/MetaQuotes/Terminal/D0E8209F77C8CF37AD8BF550E51FF075/Logs/*.log | head -1)" | iconv -f utf-16le -t utf-8 2>/dev/null

# MetaEditor compile log
cat /c/Users/hongk/AppData/Roaming/MetaQuotes/Terminal/D0E8209F77C8CF37AD8BF550E51FF075/Logs/metaeditor.log | iconv -f utf-16le -t utf-8 2>/dev/null | grep -i "error\|warning"

# MT5 PID
python -c "import psutil; [print(f'{p.pid}: {p.name()}') for p in psutil.process_iter() if 'terminal64' in p.name() or 'metaeditor' in p.name()]"

# Agent log
process action=poll session_id=<agent_proc_id>
```

---

*Last updated: 2026-07-30 02:40*

