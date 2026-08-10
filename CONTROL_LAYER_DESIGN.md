# 控制層注入方案（Control Layer Injection）— 詳細設計

**目標**：網頁可以簡單、穩定咁操控 EA（暫停/停止/狀態查詢）— 唔使脆嘅 GUI 自動化（right-click menu）
**日期**：2026-08-05
**狀態**：設計完成，待實現

---

## 1. 架構總覽

```
網頁（Dashboard）
   │ 撳「暫停」按鈕
   ▼
Server :5001（/api/ea-config/<ea>/toggle）
   │ 寫控制檔 Common/Files/ctrl_<EA名>.json（{"cmd":"stop"}）
   ▼
EA（圖表上運行 — 內置控制層）
   │ 每個 tick 檢查控制檔（OnTick 開頭）
   │ 收到 "stop" → ExpertRemove()（EA 自己移除自己）
   ▼
EA 寫狀態檔 Common/Files/state_<EA名>.json（心跳）
   ▼
Server 讀狀態檔 → 網頁顯示「運行中 / 已停止」
```

**核心突破**：**EA 自己移除自己**（ExpertRemove — MQL5 內建）— 唔使 GUI 自動化操作 MT5！

---

## 2. 控制層代碼（MQL5 — 自動注入每個 EA）

```mql5
//+------------------------------------------------------------------+
//| 控制層（自動注入 — 網頁操控 EA）                                |
//| 每個部署嘅 EA compile 前自動加入呢段 — 唔影響原 EA 邏輯          |
//+------------------------------------------------------------------+
string __mt5c_ctrl_file   = "ctrl_"  + MQLInfoString(MQL_PROGRAM_NAME) + ".json";
string __mt5c_state_file  = "state_" + MQLInfoString(MQL_PROGRAM_NAME) + ".json";
datetime __mt5c_last_beat = 0;

// 寫狀態檔（心跳）— 每 5 秒一次（tick 密集都唔會寫爆）
void __mt5c_write_state(string status) {
   int h = FileOpen(__mt5c_state_file, FILE_WRITE|FILE_TXT|FILE_COMMON);
   if (h != INVALID_HANDLE) {
      FileWrite(h, StringFormat("{\"ea\":\"%s\",\"status\":\"%s\",\"ts\":%d}",
               MQLInfoString(MQL_PROGRAM_NAME), status, (int)TimeCurrent()));
      FileClose(h);
   }
}

// 控制處理（每個 tick 呼叫）
void __mt5c_process() {
   // 1. 檢查控制檔（server 寫入）
   if (FileIsExist(__mt5c_ctrl_file, FILE_COMMON)) {
      int h = FileOpen(__mt5c_ctrl_file, FILE_READ|FILE_TXT|FILE_COMMON);
      if (h != INVALID_HANDLE) {
         string c = FileReadString(h);
         FileClose(h);
         FileDelete(__mt5c_ctrl_file, FILE_COMMON);   // 讀完刪除 — 唔會重複執行
         if (StringFind(c, "stop") >= 0 || StringFind(c, "pause") >= 0) {
            __mt5c_write_state("stopped");            // 寫停止狀態
            ExpertRemove();                            // EA 自己移除自己
            return;
         }
      }
   }
   // 2. 心跳（每 5 秒寫 running）
   if (TimeCurrent() - __mt5c_last_beat >= 5) {
      __mt5c_write_state("running");
      __mt5c_last_beat = TimeCurrent();
   }
}
```

**注入位置**：
- 控制層函數 + 變數 → 插喺 `#property` 區塊之後（第一個函數之前）
- `__mt5c_process();` → 加喺 **`void OnTick()` 開頭**（EA 必有 OnTick — tick 驅動 — 唔使 EventSetTimer / 唔會同 EA 自己嘅 OnTimer 衝突！）

---

## 3. 注入器設計（Python — inject_control_layer.py）

```python
def inject_control_layer(mq5_path: str) -> bool:
    """喺 .mq5 注入控制層（compile 前呼叫）
    返回 True = 注入成功 / 已注入過；False = 失敗（EA 冇 OnTick — 唔注入）"""
    with open(mq5_path, 'r', encoding='utf-8-sig') as f:
        src = f.read()
    # 1. 防重複（已注入過就跳過）
    if '__mt5c_process' in src:
        return True
    # 2. 搵 OnTick 函數（EA 必有）
    m = re.search(r'void\s+OnTick\s*\([^)]*\)\s*\{', src)
    if not m:
        return False
    # 3. 控制層代碼（見上節）插入 #property 之後
    control_code = CONTROL_LAYER_SOURCE  # 完整 MQL5 代碼
    # 搵最後一個 #property 行嘅結尾
    ...
    # 4. __mt5c_process() 插入 OnTick 開頭
    pos = m.end()  # '{' 之後
    src = src[:pos] + '\n   __mt5c_process();' + src[pos:]
    # 5. 寫返
    with open(mq5_path, 'w', encoding='utf-8-sig') as f:
        f.write(src)
    return True
```

**防護**：
- 注入失敗（冇 OnTick）→ log 警告 + 用原版 compile（唔阻塞部署）
- 注入後 MetaEditor compile 驗證 — 失敗 → 自動 retry 原版

---

## 4. 指令協定（Server ↔ EA）

### 控制檔（Server → EA）
```
路徑：Common/Files/ctrl_<EA名>.json
內容：{"cmd":"stop"}
行為：EA 讀完即刻刪除（唔會重複執行）；收到 stop/pause → ExpertRemove()
```

### 狀態檔（EA → Server）— 心跳
```
路徑：Common/Files/state_<EA名>.json
內容：{"ea":"Bollinger_Band","status":"running","ts":1785927000}
行為：EA 每 5 秒更新（running）；收到 stop 指令 → 寫 stopped 然後移除
```

### 狀態判斷（Server 讀取）
| state 檔 | 判斷 |
|----------|------|
| status=running + ts 新鮮（<30 秒）| 🟢 運行中 |
| status=stopped | ⚪ 已停止 |
| 冇檔 / ts 過期（>30 秒）| ⚫ 未知（EA 可能未部署/圖表關咗）|

---

## 5. Server API 改動

| API | 改動 |
|-----|------|
| `POST /api/ea-config/<ea>/toggle`（暫停）| **直接寫 `ctrl_<ea>.json` {"cmd":"stop"}** — 代替而家嘅 pause_cmd（GUI 移除）— watcher 唔使參與！|
| `POST /api/ea-config/<ea>/toggle`（恢復）| 照舊寫 deploy_cmd（重新附加）|
| `GET /api/ea-config`（狀態）| 讀 Common/Files/state_*.json — 返回 running/stopped/unknown（解決 Bug #81）|
| `DELETE /api/ea-config/<ea>`（剷除）| 先寫 ctrl_ stop → 等狀態 stopped → 刪檔案 + config |
| `POST /api/ea-library/remove-local/<name>`| 同剷除（先 stop 再刪檔案）|

---

## 6. 流程改動

### 部署（install → compile → attach）
```
install-local：複製 .mq5 去 Experts 目錄（原版）
watcher compile 前：inject_control_layer() 注入控制層 → MetaEditor compile → .ex5（帶控制層）
auto_attach：附加（照舊 — Navigator double-click）
EA 啟動 → 心跳寫 state_<ea>.json（running）→ 網頁顯示 🟢
```

### 暫停（網頁撳按鈕）
```
server 寫 ctrl_<ea>.json {"cmd":"stop"}
→ EA 下一個 tick 讀到 → ExpertRemove（自己移除）→ 寫 stopped
→ 網頁 poll → 顯示 ⚪ 已暫停
✅ 唔使 watcher、唔使 GUI、MT5 唔會死！
```

### 剷除
```
server 寫 ctrl_ stop → 等 stopped（≤30 秒）→ 刪 .ex5/.mq5 + config
```

### 恢復
```
照舊 deploy_cmd → auto_attach 附加（控制層自動帶上）
```

---

## 7. 邊界情況處理

| 情況 | 處理 |
|------|------|
| EA 已有 OnTick（全部 EA 都有）| ✅ 直接注入 |
| EA 冇 OnTick（罕見）| 唔注入 + log 警告（原版 compile）|
| 控制檔讀取 race（server 寫緊 EA 讀）| FileOpen FILE_READ 失敗 → 下個 tick 再試 |
| 變數名衝突（EA 自己有 __mt5c_）| 獨特前綴 `__mt5c_`（極罕有）|
| 注入破壞語法 | compile 失敗 → retry 原版（自動回退）|
| EA 被手動移除/圖表關閉 | 心跳停 → 網頁顯示 ⚫ 未知（ts 過期）|
| 官方 EA 唔 Print log | ✅ 心跳解決（Bug #81 根治）|

---

## 8. 風險評估

| 風險 | 級別 | 緩解 |
|------|------|------|
| 注入改壞源碼 | 低 | compile 驗證 + 自動回退原版 |
| MQL5 語法錯誤 | 低 | 控制層代碼簡短 + 多 EA 實測 |
| 控制檔殘留 | 低 | EA 讀完即刪 + server 寫前清舊 |
| FileOpen 權限（Common 目錄）| 低 | FILE_COMMON 標誌（MT5 內建支援）|
| ExpertRemove 即時性 | 低 | tick 驅動（幾秒內執行）|

---

## 9. 實施步驟

1. **寫 `agent/inject_control_layer.py`**（注入器 + 控制層代碼）
2. **單元測試**：對 Bollinger_Band / RSI_Over / TestRunner 注入 → MetaEditor compile → 驗證 .ex5 正常
3. **watcher 整合**：compile 前呼叫注入器
4. **server 改動**：toggle 暫停 → 寫 ctrl_ 檔；狀態 → 讀 state_ 檔
5. **前端**：狀態顯示（心跳）+ 暫停即時反映
6. **E2E 實測**：部署 → 心跳 running → 暫停 → stopped → 剷除
7. **文件更新**：PROGRESS.md / MODULE_INDEX.md

**預計效果**：暫停/狀態 100% 穩定（唔使 GUI）— 部署仍然用 auto_attach（之後可以試 ChartApplyTemplate 簡化）
