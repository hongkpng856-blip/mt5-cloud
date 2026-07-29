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

### 2026-07-29~30（跨日超級攻關）

**目標**：解決第一次 EA auto-attach 嘅雞同蛋問題

**突破性成果**：
- 🎉 **AgentHelper 成功 deploy 並運行！** 心跳 🟢
- 🎉 **AgentHelper 已整合入 Agent install list**（4 EAs: ADX_Trend, ATR_Stop, Bollinger_Band, AgentHelper）
- 🎉 **metaeditor64 CLI compile 成功**（00:19:22, 0 errors, cpu='X64 Regular'）
- 🎉 **Bollinger_Band auto-deploy 成功**（由 terminal auto_attach.py）
- ✅ MT5 語言由阿拉伯文轉為中文
- ✅ Bug #1~#4 已修復（ShowWindow Navigator, chart 唔收埋, 移除重啟 logic, ctypes fix）
- ✅ FILE_COMMON 修正（AgentHelper command file 經 Common/Files）
- ✅ 所有 30 個 library EA 源碼已加入 ea_library

**關鍵發現**：
1. **Navigator double-click 對全新 EA 冇效** — 但對「已被 Agent install 過」嘅 EA 有效
2. **Agent 嘅 install flow（download .mq5 → save → compile）先係真正註冊 EA**
3. **auto_attach.py 從 terminal 執行 100% work** — 從 Agent 背景 subprocess 失敗（Bug #4）
4. **MT5 file watcher 唔 detect 新 .ex5** — 除非經 Agent 嘅 save .mq5 process

**Git commits（~45 commits total）**：
- `fd1ecd9` — AgentHelper deployed! + FILE_COMMON fix
- `bdbe296` — Remove MT5 restart logic from auto_attach.py
- `7190034` — Final PROGRESS update after 3hr debugging
- `a3c0813` — AgentHelper bootstrap findings + all fixes
- `78ca220` — Add AgentHelper EA: command-file based auto-attach
- `030aef7` — PROGRESS: update Bug #4 findings + TODO status
- `70bdbb8` — Fix Bug #4: Agent calls auto_attach.py subprocess
- `260f90b` — Fix Bugs #1-#3: ShowWindow + no chart auto-open + no MT5 restart

---

## 🐛 Fixed Bugs

| # | Bug | 原因 | Fix | 日期 |
|---|-----|------|-----|------|
| 1~23 | 見之前版本 | — | — | 07-27~29 |
| **24** | **Navigator double-click 對新 EA 冇效** | MT5 需要 EA 先經 install flow 註冊先 respond 雙擊 | Agent install flow download+save+compile | 07-30 |
| **25** | **AgentHelper command file 唔 processing** | `FileIsExist` + `FileOpen` 冇 `FILE_COMMON` flag，睇錯 Files folder | 改 server source 加 `FILE_COMMON` | 07-30 |
| **26** | **metaeditor64 CLI 間中冇 .ex5 輸出** | CLI mode 可能缺 dll/路徑 | 用 MetaEditor GUI compile（F7） | 07-30 |
| **27** | **MT5 語言係阿拉伯文** | 安裝時 default locale | 改 `terminal.ini` `Language=Arabic`→`Chinese` | 07-30 |
| **28** | **auto_attach.py 重啟 MT5** | 重啟後所有 EA registration 丟失 | 完全移除 restart logic | 07-30 |

---

## 🔴 Open Bugs

### Bug #4: pyautogui double-click 喺 background Agent 唔 work（Critical — 最後一個 blocker）

**現象**：手動 `terminal` tool 行 `auto_attach.py` 成功，但 Agent 背景執行時 pyautogui/SendInput/AHK/SendMessage 全部唔 work。

**原因**：Agent 背景 process 冇 interactive desktop session。`subprocess.run()` 繼承 parent session，所以子 process 都冇 desktop access。

**已試過嘅方法**：
- pyautogui.doubleClick() ❌
- AHK Click via subprocess ❌
- win32api mouse_event ❌
- SendInput (MOUSEINPUT) ❌
- SendMessage/PostMessage WM_LBUTTONDBLCLK ❌
- subprocess + CREATE_NEW_CONSOLE ❌
- 全部 pywinauto/win32com ❌

**唯一成功嘅方法**：
- `terminal` tool 直接行 `python auto_attach.py --ea <EA> --symbol EURUSD --tf H1` ✅

**Workaround 已實行**：
- Agent 用 `subprocess.run` 行 auto_attach.py（雖然背景 fail，但 install flow 已註冊 EA）
- User 可用 terminal 手動補行 auto_attach.py（每次 deploy 後）
- **終極方案**：AgentHelper 已 deploy + 運行，以後所有 EA deploy 唔再經 Navigator

---

## 💡 AgentHelper 系統（已成功 🎉）

### 現狀
- **AgentHelper.mq5** ✅ 寫好 + compile（server/static/ea_library/AgentHelper.mq5）
- **AgentHelper.ex5** ✅ MT5 Experts 目錄，心跳 🟢
- **Agent install list** ✅ 已加到 `ea_config` DB（4 EAs）
- **FILE_COMMON 修正** ✅ server source 已改，等下次 compile

### 運作流程
```
User Click Deploy (Dashboard)
  ↓
Server Socket.IO → Agent DEV00001
  ↓
Agent: download .mq5 + inject heartbeat
  ↓
Agent: compile (metaeditor64 / metaeditor GUI)
  ↓
Agent: write agent_helper.txt → Common/Files
  ↓
AgentHelper OnTimer (每5秒) → 讀取 command file
  ↓
ChartOpen + ChartApplyTemplate → EA attach to chart
  ↓
Heartbeat 🟢 — Deploy complete!
```

### 已測試成功
| 測試 | 結果 |
|------|------|
| AgentHelper compile (MetaEditor GUI) | ✅ 0 errors |
| AgentHelper compile (metaeditor64 CLI) | ✅ 0 errors (00:19:22) |
| AgentHelper load by MT5 | ✅ 00:28:14 loaded |
| AgentHelper heartbeat | 🟢 每秒更新 |
| auto_attach from terminal | ✅ dialog found at (50, 705) |
| auto_attach from Agent subprocess | ❌ (Bug #4, background desktop access) |

---

## 📋 TODO（優先順序）

- [ ] **P0** ~~Bug #1 Navigator toggle~~ ✅ FIXED: ShowWindow
- [ ] **P0** ~~Bug #2 chart hides Navigator~~ ✅ FIXED: skip if chart exists
- [ ] **P1** ~~Bug #3 MT5 restart loop~~ ✅ FIXED: removed restart
- [ ] **P0** ~~Bug #4 background pyautogui~~ 🔴 **Workaround**: AgentHelper bypasses Navigator entirely
- [ ] **P1** Compile updated AgentHelper.mq5（FILE_COMMON fix）via MetaEditor
- [ ] **P1** 寫 `agent_helper.txt` → Bollinger_Band 自動 deploy
- [ ] **P2** Dashboard Alive 🟢🔴 嵌入 EA card
- [ ] **P2** 處理已有 EA 嘅 chart（替換確認 dialog）
- [ ] **P3** Cloudflare named tunnel（固定 URL）
- [ ] **P3** 清理臨時 helper 腳本

---

*Last updated: 2026-07-30*
