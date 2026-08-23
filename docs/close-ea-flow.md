# 電腦關閉 EA 流程（剷除 / 暫停）— 壓力測試用

> 2026-08-21 用戶要求：撮寫電腦關閉 EA 嘅完整流程 — 用於新壓力測試（電腦）
> 對應 code：`agent/auto_attach.py → remove_ea_from_chart()`（`python -u agent/auto_attach.py --remove --ea <EA>`）

---

## 流程總覽

```
觸發（網頁刪除 / CLI --remove）
  ↓
① 檢查 EA 係咪真係運行（MT5 log 最後狀態 + 心跳）
  ↓
② Alt+W 開「窗口」dialog → 讀 ListView（列出所有 chart）
  ↓
③ 由 MT5 log 搵目標 EA 掛邊個 symbol
  ↓
④ 揀候選 chart（symbol match — 可能多個同名）
  ↓
⑤ 逐個試：方向鍵揀 chart → Enter → Ctrl+W 關閉
  ↓
⑥ 驗證：心跳停 / MT5 log「removed」
  ↓
⑦ 未移除 → 重新讀 ListView（index 移位 FIX）→ 試下一個
  ↓
⑧ 移除成功 → return True；試晒都唔得 → return False
```

---

## 詳細步驟（每一步做咩 + 驗證）

### Step 0：前置檢查
| 檢查 | 方法 | 結果 |
|------|------|------|
| MT5 有冇開 | `tasklist terminal64.exe` | 冇開 → 「冇嘢要移除」→ return True |
| 連 MT5 | pywinauto connect(process=pid) | 連到主視窗 |

### Step 1：確認 EA 真係運行（唔好無謂移除）
| 檢查 | 方法 |
|------|------|
| MT5 log 最後狀態 | 讀 terminal `Logs/2026*.log` → `expert <EA> (SYM,TF) loaded successfully` = started；`removed` = stopped |
| 心跳新鮮 | `state_<EA>.json` / `hb_<EA>.txt` mtime < 60s |

**兩個都唔係運行 → 「唔使移除」→ return True**（省時間）

### Step 2：開「窗口」dialog + 讀 chart 列表
```
send_keys('%w')  ← Alt+W
```
- 搵 `#32770` + title 含「窗口」嘅 dialog
- 搵 `SysListView32`（chart 列表 — 排位 = 開 chart 順序）
- 讀全部 item（LVM_GETITEMCOUNT + get_item）

**實測輸出**：
```
📋 窗口 dialog 有 10 個 chart：
  [0] EURUSD,H1:  Euro vs US Dollar
  [1] AMD,H1:  Advanced Micro Devices Inc
  [2] EURJPY,H1:  Euro vs Yen
  ...
  [6] UK100,H1:  FTSE 100 Index
  [7] UK100,H1:  FTSE 100 Index
```

### Step 3：由 MT5 log 搵目標 EA 掛邊個 symbol
```
讀 terminal Logs → regex: expert <EA> (SYM,TF)
→ 最後一條 loaded = 目標 symbol
```
```
🎯 目標 EA RSI_Over 掛喺 UK100（MT5 log）
```

### Step 4：揀候選 chart（多個同名）
- 全部 match symbol 嘅 chart index → `_candidates`
- 冇 match → 全部 chart 都試

```
📌 目標 symbol UK100 → 候選 chart: [6, 7]
```

### Step 5：逐個試移除（核心 — 2026-08-21 根治多個同名揀錯）
**每個候選 chart 都試**：
1. `{HOME}` + `{DOWN}` × index → 揀 chart（方向鍵 — 唔靠座標）
2. `{ENTER}` → dialog 關閉 + 彈返該 chart
3. 確認 dialog 關咗（再試 Enter / 都唔得 → fail）
4. **`Ctrl+W` 關閉 chart（EA 一齊移除）**
5. **驗證移除**：
   - 心跳停：`state_<EA>.json` / `hb_<EA>.txt` mtime > 30s
   - 或 MT5 log 最後 30 行有 `removed`
6. 未移除 → 重新開窗口 dialog + **重新讀 ListView**（index 移位 FIX — 移除 chart 後重新排位）→ 試下一個

**實測輸出**：
```
📌 試移除 chart [1]（EURJPY）→ RSI_Over 仲運行 → 下一個
📌 試移除 chart [2]（AUDJPY）→ RSI_Over 仲運行 → 下一個
📌 試移除 chart [3]（UK100）→ ✅ MT5 log 確認 RSI_Over removed
✅ 暫停/剷除 RSI_Over 完成
```

### Step 6：最終結果
| 結果 | 行為 |
|------|------|
| ✅ 移除成功 | return True（watcher 寫 activity log「已暫停」） |
| ❌ 試晒都唔得 | return False（唔好話成功 — 假成功防護） |

---

## 觸發方式

### 1. 網頁刪除（用戶操作）
```
網頁配對庫 → 揀 EA → 「刪除」
→ DELETE /api/ea-config/<EA> → 寫 pause_cmd_<EA>_<ts>.json
→ watcher 偵測 → 行 auto_attach.py --remove --ea <EA>
```

### 2. CLI 直接（壓力測試用）
```bash
cd ~/Desktop/mt5-cloud
python -u agent/auto_attach.py --remove --ea <EA_NAME>
```

---

## 壓力測試場景建議

| 場景 | 點做 | 預期 |
|------|------|------|
| 單一 EA 剷除 | 部署 1 隻 EA → `--remove` | 心跳停 + log removed |
| 多個同名 EA | 部署 3 隻 EA 落 3 個同名 chart → `--remove` | 逐個試直到移除 |
| EA 已冇掛 chart | 直接 `--remove`（EA 唔運行） | 「唔使移除」→ True |
| MT5 冇開 | 直接 `--remove` | 「MT5 未開」→ True |
| 殘留 dialog | 開住 Properties dialog → `--remove` | dialog 清理 + 正常剷除 |
| 剷除後再部署 | `--remove` 完 → 部署 | 唔會代替/卡 dialog |

---

## 驗證標準（成功 = 真實驗證）

1. **心跳停**：`state_<EA>.json` / `hb_<EA>.txt` mtime > 30s（EA 已移除 — 唔再寫心跳）
2. **MT5 log removed**：`expert <EA> (SYM,TF) removed` 出現
3. **chart 實際少咗**：EnumChildWindows 數 chart 數目減少

⚠️ **唔可以淨靠 activity log / 網頁顯示話成功** — 要對真 MT5 狀態（用戶要求）。
