# Tradotcom 網站重建 — Agent 交接文檔（Draft v1）

> 對象：接手整網站嘅另一位 Agent
> 日期：2026-08-27
> 項目：Tradotcom（前 MT5 Cloud）— MT5 遠端控制平台（multi-user）

---

## 1. 項目係咩？

**Tradotcom = 網頁控制 MetaTrader 5（MT5）交易平台**

用戶喺網頁登入 → 安裝 Agent 去一部電腦（嗰部機有 MT5）→ 之後可以**喺網頁遠端控制嗰部機嘅 MT5**（部署 EA / 剷除 EA / 睇交易報告 / 睇 Correlation 分析）。

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  網頁 (UI)   │ ──► │  Server      │ ──► │  Agent      │ ──► MT5
│  (你要整)    │     │  (Flask+DB)  │     │  (每部機)   │
└─────────────┘     └──────────────┘     └─────────────┘
   用戶操作           中央控制            執行器（控制 MT5）
```

- **Server**：Flask + SQLite + SocketIO（中央 — 所有決策/數據）
- **Agent**：每部電腦一個（Python）— 收到 server 指令 → 控制本機 MT5
- **多用戶**：每個 account 綁定自己 agent → 控制自己部機（方案 A：1 User → N Agent）

---

## 2. 重點功能（你嘅網站要有）

### 2.1 用戶帳戶
| 功能 | 說明 |
|------|------|
| 註冊 / 登入 / 登出 | Email + 密碼（已有 register.html / login.html）|
| 帳戶綁定 MT5 | 登入時填 MT5 帳戶號（`bound_account`）|
| Agent 安裝資料 | 顯示 Agent ID + Token + 「下載桌面安裝程式」一粒掣 |

### 2.2 Dashboard（主控制台）
| 功能 | 說明 |
|------|------|
| **Agent 卡** | 顯示 Agent ID + Online/Offline 綠/紅燈（`last_seen` 新鮮先算 Online）|
| **部署到 MT5** | 揀 EA → 揀 symbol → 確認部署（有警告視窗）|
| **EA 倉庫** | 平台提供嘅 EA 列表（官方）+ 上傳自己 EA |
| **我的配對庫** | 已部署嘅 EA 列表（Trades / Win Rate / P&L dropdown 8 指標 / 排序）|
| **剷除** | 移除 EA（連 MT5 圖表 + 本機 .ex5 + DB config 完整移除）|
| **活動記錄** | 所有操作歷史（永久保存 — 唔刪除）|

### 2.3 分析功能
| 功能 | 說明 |
|------|------|
| **Correlation Matrix** | EA 之間相關性（Heatmap 漸變色 + 散點圖 + EA 名顯示）|
| **EA 診斷報告** | 單隻 EA：Trades / Win Rate / P&L / Equity Curve / Monthly P&L / Max Drawdown |
| **交易歷史報告** | 帳戶交易歷史（可匯出）|

### 2.4 安全/控制
| 功能 | 說明 |
|------|------|
| **AI 控制警告視窗** | 每次操控 MT5 前彈警告（網站 modal + MT5 端 tkinter 一致）— 可緊急停止 |
| **防雙開** | 一部機只可以一個 Agent（agent.lock）|
| **Token 驗證** | Agent register/sync 要驗證 token（防冒認）|
| **操作防重複** | 同一 EA 30 秒內唔可以重複部署 |

---

## 3. 優點（賣點）

1. **遠端控制任何電腦嘅 MT5** — 唔使坐喺嗰部機前面
2. **多用戶隔離** — 每個 account 控制自己 agent / 自己部機（數據完全分離）
3. **一鍵安裝** — 網頁下載 → double-click → 安裝精靈（好似裝軟件咁簡單）
4. **真實驗證** — 部署成功有 4 項檢查（MT5 log / 心跳 / 圖表 / activity log）— 唔造假
5. **完整分析** — Correlation / Equity Curve / P&L 多指標 / 診斷報告
6. **安全** — Token 驗證 + 警告視窗 + 防雙開 + 操作記錄
7. **穩定架構** — Server 可上雲（VPS）+ Agent 每部機獨立（熄一部唔影響其他）

---

## 4. 比較（vs 市面）

| | **Tradotcom** | MT5 自帶 (VPS) | 其他第三方 |
|---|---|---|---|
| 遠端控制 | ✅ 網頁任何地方 | ❌ 要裝 MT5 VPS | 部分有 |
| 多用戶 | ✅ 每 account 獨立 | ❌ 單機 | 部分 |
| 安裝 | ✅ 一鍵（好似軟件）| ❌ 複雜（VPS 設定）| 中 |
| EA 部署 | ✅ 網頁撳（有驗證）| ⚠️ 手動 | 部分 |
| 分析 | ✅ Correlation + 報告 | ❌ 冇 | 部分 |
| 中文介面 | ✅（可改多語言）| ❌ | — |

---

## 5. 重要截圖（你需要嘅）

> ⚠️ 我建議你**先跑起 server 再截圖**（`python server/app.py` — 登入 dev / dev1234）

| # | 截圖 | 內容 | 用途 |
|---|------|------|------|
| 1 | **登入頁** | login.html（橙黑 Binance 風格）| 首頁 |
| 2 | **Dashboard 全貌** | Agent 卡（Online 綠燈）+ 部署區 + EA 倉庫 + 配對庫 + 活動記錄 | 主截圖（最重點）|
| 3 | **EA 倉庫** | 官方 EA 列表（+ 上傳自己 EA）| 展示功能 |
| 4 | **配對庫 + P&L dropdown** | 已部署 EA + P&L 8 指標選擇 + 排序 | 展示分析 |
| 5 | **部署流程** | 揀 EA → symbol → 確認（警告視窗彈出）| 展示流程 |
| 6 | **Correlation Matrix** | Heatmap 漸變 + 散點圖 | 展示分析深度 |
| 7 | **EA 診斷報告** | Equity Curve + Monthly P&L + 統計 | 展示報告 |
| 8 | **Agent 安裝資料** | Agent ID/Token + 下載安裝程式 | 展示安裝流程 |
| 9 | **活動記錄** | 操作歷史列表 | 展示追蹤 |
| 10 | **交易歷史報告** | 帳戶歷史（匯出）| 展示報告 |

---

## 6. 設計規範（跟足 — 用戶定案）

```
🎨 橙黑 Binance 風格：
  - 主色：#f0b90b（橙）
  - 背景：#0b0e11（黑）
  - 字體：DM Sans
  - 已套用：登入/註冊/Dashboard/報告 4 頁

📐 UI 定案（2026-08-21）：
  - Agent 卡淨 3 格（精簡）
  - 配對庫 3 掣細粒橫排靠右 + 全欄靠左對齊
  - 已刪「刷新狀態」掣
  - 上傳掣唔要橙色
  - 灰框低調（配對庫 P&L dropdown）
  - 表格簡潔（EA 倉庫唔要狀態欄）
```

---

## 7. 技術 stack（而家）

```
Backend: Python Flask + SQLite + python-socketio
Frontend: 單頁 dashboard.html（原生 JS + Lucide icons）+ login/register.html
Agent: 獨立 Python process（每部機）
通訊: HTTP API + SocketIO（deploy 指令經 room 路由俾 agent）
部署: server 5001 + Cloudflare Tunnel（https://mt5cloud.esgov.org）
```

---

## 8. 接手 checklist

```
✅ 跑起 server：python server/app.py（PORT=5001）
✅ 登入：dev / dev1234（測試帳戶）
✅ 瀏覽所有頁面（dashboard 主頁 + 報告 modal + Correlation）
✅ 確認 Agent 卡顯示（DEV00001 — 如果 agent 行緊會 Online）
✅ 截圖（上面 10 張）
✅ 如果要做新 UI — 先做獨立 preview/ 版俾用戶睇 → 確認先改 production
```

---

*此為 Draft v1 — 你睇完話我知要改咩（功能/截圖/比較/語氣），我再 update。*
