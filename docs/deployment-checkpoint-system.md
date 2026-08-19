# 部署流程檢測系統（每步驗證 gate）

> 2026-08-20 用戶要求：**每個步驟完成之後，檢測到成功咗，先落去下一個步驟**。
> 唔可以「做完就算」/「等固定時間」——每一步都要有驗證 gate（成功 → 下一步；失敗 → 重試/報錯）。

## 核心原則

1. **每步一 gate**：完成動作 → 驗證（真實驗證，唔可以假成功）→ 成功先落下一步
2. **驗證要「等」**：唔可以即刻 check（資料未就緒 → 假失敗）——poll 到成功或者 timeout
3. **失敗處理**：驗證 fail → 重試（有限次數）→ 都 fail → 明確報錯（唔好繼續落去）
4. **真實驗證**：用 MT5 Terminal log / 心跳 mtime / 視窗狀態 —— 唔好用「print 成功」當成功

---

## 部署流程（auto_attach）— 每步驗證標準

### Step 0：前置檢查
| 檢查 | 驗證方法 | 成功標準 |
|------|---------|---------|
| EA .ex5 存在 | 掃 `MQL5/Experts/<EA>.ex5` | 檔案存在（唔存在 → 報錯「請先配對」） |
| hotkeys.ini 可寫 | 讀取 hotkeys.ini | 讀到（UTF-16/UTF-8） |
| MT5 狀態 | tasklist terminal64.exe | 有 PID（冇 → 開 MT5） |

### Step 1：熱鍵預載（關 MT5 → 寫 hotkeys.ini → 開 MT5）
| 驗證 gate | 方法 | 成功標準 |
|-----------|------|---------|
| MT5 已關閉 | tasklist 冇 terminal64.exe | 已關閉（或強制 kill 後） |
| 熱鍵已寫入 | 讀 hotkeys.ini | `<experts>Experts\<EA>.ex5=Ctrl+N</experts>` 存在 |
| MT5 已開 + ready | poll MT5 window（pywinauto connect）| window ready |
| **熱鍵已 load** | send Ctrl+N（測試）| **彈出 `<EA> Properties` dialog**（彈咗 = 熱鍵 load 成功） |
| 熱鍵 load 失敗 | 重試 send（×2）| 彈出 Properties / 失敗報錯 |

⚠️ **熱鍵 load 驗證係關鍵**：開完 MT5 唔可以即刻部署——要等 MT5 load 完熱鍵（send Ctrl+N 測試）。未 load → 等/重試。

### Step 2：固定視窗 + Navigator
| 驗證 gate | 方法 | 成功標準 |
|-----------|------|---------|
| MT5 視窗固定 | pywinauto window rect | 視窗存在 + 位置固定（1920x1040 @ 0,0） |
| Navigator 統一 | Navigator tree 存在 | 搵到 Navigator（位置固定） |

### Step 3：開 chart（新方法 Alt+F→Enter→Enter→Space→symbol→Enter）
| 驗證 gate | 方法 | 成功標準 |
|-----------|------|---------|
| **chart 開咗** | check MDI chart 窗口（`win.descendants`）| 有 `<SYM>,H1` chart 存在 |
| 失敗處理 | 重試開 chart（×2）| chart 出現 / 報錯 |

⚠️ 驗證唔可以淨靠主窗口標題（MT5 主窗口標題唔一定含 symbol）——用 MDI chart 窗口。

### Step 4：掛 EA（熱鍵 Ctrl+N → Properties → 確定）
| 驗證 gate | 方法 | 成功標準 |
|-----------|------|---------|
| **Properties 彈出** | EnumWindows 搵 `#32770` dialog | 有 `<EA> 1.00 (<SYM>,H1)` dialog |
| Properties 冇彈 | 重試 send 熱鍵（×2）| 彈出 / 報錯 |
| 撳確定 | BM_CLICK 確定按鈕 | 撳到 |
| **EA loaded** | 等 4s + 讀 MT5 Terminal log | `expert <EA> (<SYM>,H1) loaded successfully` 出現 |

⚠️ loaded 驗證要「等」（OnInit 未行完/log flush 延遲 → 假失敗）。

### Step 5：最終驗證（成功判定）
| 驗證 gate | 方法 | 成功標準 |
|-----------|------|---------|
| **MT5 log loaded**（優先） | 讀 `D0E8.../logs/YYYYMMDD.log` | `expert <EA> (<SYM>,H1) loaded successfully` 且**無隨後 removed** |
| 心跳新鮮（後備） | check `hb_<EA>.txt` / `state_<EA>.json` mtime | mtime < 120s |
| 心跳舊 + log 有 | 用 log 後備 | log 有 = 成功（市場收市心跳停） |

⚠️ **成功判定原則**（用戶定立）：對真 MT5 log——`loaded successfully` 出現先話成功。心跳/activity log 話成功都可能假。

---

## 失敗處理（通用）

1. 每步驗證 fail → **重試 ×2**（每步之間 `check_abort()` 緊急停止檢查）
2. 重試都 fail → **明確報錯**（print `❌ <step> 失敗 — <原因>`）→ 唔好繼續下一步
3. 緊急停止：任何時候 `control_guard.check_abort()` → 即刻停

## 驗證用「等」嘅位（唔可以即刻 check）

| 位 | 等幾耐 | 原因 |
|----|--------|------|
| MT5 開完 → window ready | poll 最多 90s | MT5 啟動慢 |
| MT5 開完 → 熱鍵 load | send Ctrl+N 測試（最多 3 次） | hotkeys load 延遲 |
| 撳確定 → EA loaded | 等 4-5s | OnInit 未行完 / log flush |
| 心跳首跳 | 等 120s | 市場收市 OnTimer 首 tick 慢 |

## 點樣落地（改 code 方向）

auto_attach 每個 step 加 `_wait_until(check_fn, timeout, desc)` helper：
```python
def _wait_until(check_fn, timeout=60, desc=''):
    """poll check_fn 直到 True 或者 timeout — 每步驗證 gate"""
    start = time.time()
    while time.time() - start < timeout:
        if check_fn():
            print(f"✅ {desc}")
            return True
        time.sleep(2)
    print(f"❌ {desc} — timeout {timeout}s")
    return False
```

然後每步：
```python
# Step 1: 熱鍵預載
if not _wait_until(lambda: _mt5_ready(), 90, 'MT5 已開 + ready'):
    return False
if not _wait_until(lambda: _hotkey_loads(ea_name, combo), 30, '熱鍵 load（Ctrl+N 彈 Properties）'):
    return False
# Step 3: 開 chart
if not _wait_until(lambda: _chart_exists(symbol), 30, 'chart 開咗'):
    return False
# Step 4: EA loaded
if not _wait_until(lambda: _ea_loaded_in_log(ea_name, symbol), 30, 'EA loaded（MT5 log）'):
    return False
```
