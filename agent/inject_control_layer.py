# -*- coding: utf-8 -*-
"""控制層注入器（Control Layer Injector）
喺 EA 源碼（.mq5）自動注入控制層 — 令 EA 可以透過網頁操控：
  - 每個 tick 檢查 Common/Files/ctrl_<EA名>.json（網頁指令）
  - 收到 "stop"/"pause" → 寫狀態 stopped → ExpertRemove()（EA 自己移除）
  - 每 5 秒寫心跳 Common/Files/state_<EA名>.json（running + 時間戳）

用法：
    from inject_control_layer import inject_control_layer
    inject_control_layer(r"C:\\...\\MQL5\\Experts\\Bollinger_Band.mq5")

⚠️ 影響分析（mt5-impact-analysis）：
  - B 類（EA 配置）：改 .mq5 源碼（加控制層）— 唔影響原 EA 邏輯（只喺 OnTick 開頭加一行 call）
  - 失敗（冇 OnTick）→ 返回 False — 用原版 compile（唔阻塞部署）
  - 已注入（__mt5c_process 存在）→ skip（唔會重複注入）
"""
import os
import re
import sys

# ─── 控制層 MQL5 代碼（注入到每個 EA）───
# 設計：喺 OnTick 開頭加 __mt5c_process() — tick 驅動（EA 必有 OnTick — 唔同 OnTimer 衝突）
# 心跳每 5 秒寫一次（tick 密集都唔會寫爆）；控制檔讀完即刪（唔會重複執行）
CONTROL_LAYER_SOURCE = r'''
//+------------------------------------------------------------------+
//| 控制層（自動注入 — 網頁操控 EA）                                |
//| 指令檔: Common/Files/ctrl_<EA名>.json  {"cmd":"stop"}            |
//| 狀態檔: Common/Files/state_<EA名>.json 心跳（running/stopped）   |
//+------------------------------------------------------------------+
// ⚠️ 唔可以喺全局初始化 call MQLInfoString（MQL5 runtime 函數 — 會 crash）
// → 空字串 + __mt5c_process 第一次 call 時 lazy init
string __mt5c_ctrl_file   = "";
string __mt5c_state_file  = "";
datetime __mt5c_last_beat = 0;

void __mt5c_write_state(string status) {
   int h = FileOpen(__mt5c_state_file, FILE_WRITE|FILE_TXT|FILE_COMMON);
   if (h != INVALID_HANDLE) {
      FileWrite(h, StringFormat("{\"ea\":\"%s\",\"status\":\"%s\",\"ts\":%d}",
               MQLInfoString(MQL_PROGRAM_NAME), status, (int)TimeCurrent()));
      FileClose(h);
   }
}

void __mt5c_process() {
   if (__mt5c_ctrl_file == "") {
      __mt5c_ctrl_file  = "ctrl_"  + MQLInfoString(MQL_PROGRAM_NAME) + ".json";
      __mt5c_state_file = "state_" + MQLInfoString(MQL_PROGRAM_NAME) + ".json";
   }
   if (FileIsExist(__mt5c_ctrl_file, FILE_COMMON)) {
      int h = FileOpen(__mt5c_ctrl_file, FILE_READ|FILE_TXT|FILE_COMMON);
      if (h != INVALID_HANDLE) {
         string c = FileReadString(h);
         FileClose(h);
         FileDelete(__mt5c_ctrl_file, FILE_COMMON);
         if (StringFind(c, "stop") >= 0 || StringFind(c, "pause") >= 0) {
            __mt5c_write_state("stopped");
            ExpertRemove();
            return;
         }
      }
   }
   if (TimeCurrent() - __mt5c_last_beat >= 5) {
      __mt5c_write_state("running");
      __mt5c_last_beat = TimeCurrent();
   }
}
'''


def inject_control_layer(mq5_path):
    """喺 .mq5 注入控制層（compile 前呼叫）
    返回：True = 注入成功/已注入過；False = 失敗（冇 OnTick — 用原版 compile）"""
    try:
        if not os.path.isfile(mq5_path):
            print(f"⚠️ [注入器] {mq5_path} 唔存在")
            return False

        with open(mq5_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
            src = f.read()

        # 1. 防重複（已注入過就 skip）
        if '__mt5c_process' in src:
            print(f"   ⏩ {os.path.basename(mq5_path)} 已注入控制層，skip")
            return True

        # 1.5 🚨 2026-08-10：移除 AgentHelper bootstrap（ChartApplyTemplate 套用模板 → reason=7 移除 EA）
        #     ADX_Trend 案例：配對用原版 .mq5（有 bootstrap）→ 啟動 1 秒被移除
        bootstrap_pat = re.compile(r'\n\s*// One-shot bootstrap.*?\n\s*if\(!g_bootstrapDone\)\{.*?\n\s*\}\n', re.S)
        if bootstrap_pat.search(src):
            src = bootstrap_pat.sub('\n', src)
            print(f"   🗑️ [注入器] {os.path.basename(mq5_path)} 已移除 AgentHelper bootstrap")

        # 2. 搵 OnTick 函數（EA 必有 — 控制層靠 tick 驅動）
        m = re.search(r'void\s+OnTick\s*\([^)]*\)\s*\{', src)
        if not m:
            print(f"   ⚠️ [注入器] {os.path.basename(mq5_path)} 冇 OnTick — 唔注入（用原版）")
            return False

        # 3. 控制層代碼插入位置：#property 區塊之後（第一個函數之前）
        #    搵最後一個 #property 行（或者 #include 之後）
        prop_end = 0
        for pm in re.finditer(r'^#property[^\n]*\n', src, re.MULTILINE):
            prop_end = pm.end()
        # 如果冇 #property — 用檔頭（第一個函數前）
        if prop_end == 0:
            m2 = re.search(r'\n\s*(int|void|double|bool|string|datetime|color)\s+\w+\s*\(', src)
            if m2:
                prop_end = m2.start()
        insert_pos = prop_end

        # 4. 組裝：控制層代碼 + 原源碼（OnTick 開頭加 __mt5c_process();）
        call_inject = "\n   __mt5c_process();"
        # OnTick 開頭（'{' 之後）插入
        on_tick_pos = m.end()
        new_src = (src[:insert_pos]
                   + CONTROL_LAYER_SOURCE
                   + "\n"
                   + src[insert_pos:on_tick_pos]
                   + call_inject
                   + src[on_tick_pos:])

        # 5. 寫返（保留 BOM — MetaEditor 用 UTF-8 BOM）
        with open(mq5_path, 'w', encoding='utf-8-sig') as f:
            f.write(new_src)
        print(f"   ✅ [注入器] {os.path.basename(mq5_path)} 已注入控制層")
        return True
    except Exception as e:
        print(f"   ❌ [注入器] 注入失敗: {e}")
        return False


if __name__ == '__main__':
    # CLI 測試：python inject_control_layer.py <path.mq5>
    if len(sys.argv) > 1:
        ok = inject_control_layer(sys.argv[1])
        print(f"結果: {'成功' if ok else '失敗'}")
    else:
        print("用法: python inject_control_layer.py <path.mq5>")
