# .chr 部署模板（2026-09-01 user實測確立 — 可靠基底）

## 背景
- **user實測**：用記事本手寫 .chr（有齊欄位 + `<expert>` 區 + **`InpSymbol=`**）→ 放返入 Euro folder → 開 MT5 → **自動開 chart + 掛 EA** ✅
- 之前 code 自動生成嘅 .chr（冇 InpSymbol= / 漏欄位）→ **唔掛** ❌
- 所以：**部署用呢個模板做基底**（取代 _deleted 複製方法）

## 模板檔案
`agent/chr_template_base.chr.txt`（user 提供嘅完整格式 — AUDUSD + Breakout）

## 關鍵格式要求（MT5 接受）
1. **`<chart>` 區**：id=0 / symbol / description / 所有欄位（scale/window_left/...）/ **`windows_total=1`**
2. **`<expert>` 區**（喺 <chart> 內、<window> 之前）：
   ```
   <expert>
   name=<EA名>
   path=Experts\<EA名>.ex5
   expertmode=1
   <inputs>
   LotSize=0.01
   MagicNumber=<magic>
   EnableLog=true
   InpSymbol=          ← 必須有（之前冇 → 唔掛）
   </inputs>
   </expert>
   ```
3. **`<window>` 區**（height + indicator Main）— 有齊先完整
4. **行尾**：`\r\n`（記事本風格 — 唔好淨 `\n`）
5. **編碼**：UTF-16 LE with BOM（`\xff\xfe`）

## 部署流程（用模板）
1. 讀模板 → 改 id（隨機 14 位）+ symbol + description + EA 名/path/Magic
2. 寫入 `MQL5/Profiles/Charts/<profile>/chartXX.chr`（UTF-16）
3. 更新 order.wnd（加 chartXX）
4. 開 MT5 → restore 自動掛 EA（.ex5 必須存在）
5. 平鋪窗口

## 驗證
- MT5 log：`expert <EA> (SYM,H1) loaded successfully`
- 心跳 `state_<EA>.json` FRESH
