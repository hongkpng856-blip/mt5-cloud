//+------------------------------------------------------------------+
//| Controller.mq5 — EA 控制器（網頁操控所有 EA）                    |
//| 永久附加喺圖表 — 讀 Common/Files/ctrl_controller.json 指令：     |
//|   {"cmd":"attach","ea":"RSI_Over","symbol":"EURUSD","tf":"H1"}   |
//|     → ChartApplyTemplate(tpl) 附加目標 EA（唔使 GUI 自動化）      |
//|   {"cmd":"remove","ea":"RSI_Over"}                               |
//|     → 寫 ctrl_RSI_Over.json（目標 EA 控制層自己移除）             |
//| 心跳：寫 state_controller.json（每 5 秒）                        |
//+------------------------------------------------------------------+
#property copyright      "MT5 Cloud"
#property version        "1.00"

string __ctrl_file   = "ctrl_controller.json";
string __state_file  = "state_controller.json";
datetime __last_beat = 0;

//+------------------------------------------------------------------+
//| 寫狀態檔（心跳）                                                  |
//+------------------------------------------------------------------+
void WriteState(string status) {
   int h = FileOpen(__state_file, FILE_WRITE|FILE_TXT|FILE_COMMON);
   if (h != INVALID_HANDLE) {
      FileWrite(h, StringFormat("{\"ea\":\"Controller\",\"status\":\"%s\",\"ts\":%d}",
               status, (int)TimeCurrent()));
      FileClose(h);
   }
}

//+------------------------------------------------------------------+
//| 解析 JSON 值（簡單 string search — 指令檔格式固定）              |
//+------------------------------------------------------------------+
string JsonGet(string content, string key) {
   string k = "\"" + key + "\"";
   int pos = StringFind(content, k);
   if (pos < 0) return "";
   pos = StringFind(content, ":", pos);
   if (pos < 0) return "";
   pos++; // 跳過 ':'
   while (pos < StringLen(content) && (StringGetCharacter(content, pos) == ' ' || StringGetCharacter(content, pos) == '\t')) pos++;
   if (pos < StringLen(content) && StringGetCharacter(content, pos) == '"') {
      pos++;
      string val = "";
      while (pos < StringLen(content) && StringGetCharacter(content, pos) != '"') {
         val += ShortToString(StringGetCharacter(content, pos));
         pos++;
      }
      return val;
   }
   return "";
}

//+------------------------------------------------------------------+
//| 執行指令                                                          |
//+------------------------------------------------------------------+
void ProcessCommand(string content) {
   string cmd = JsonGet(content, "cmd");
   if (cmd == "attach") {
      string ea = JsonGet(content, "ea");
      string symbol = JsonGet(content, "symbol");
      string tf = JsonGet(content, "tf");
      if (StringLen(ea) == 0) return;
      if (StringLen(symbol) == 0) symbol = Symbol();
      if (StringLen(tf) == 0) tf = "H1";
      // 生成 template 路徑（同 auto_attach generate_template 一致：<EA>_<SYMBOL>_<TF>.tpl）
      string tpl = "Templates\\" + ea + "_" + symbol + "_" + tf + ".tpl";
      Print("[Controller] attach ", ea, " via ChartApplyTemplate: ", tpl);
      long chart_id = ChartFirst();
      // 搵目標 symbol 圖表（冇就開一個）
      while (chart_id > 0) {
         if (ChartSymbol(chart_id) == symbol) break;
         chart_id = ChartNext(chart_id);
      }
      if (chart_id <= 0) {
         // 開新圖表（symbol + tf）
         chart_id = ChartOpen(symbol, StringToTimeframe(tf));
         if (chart_id <= 0) {
            Print("[Controller] ❌ 開唔到圖表: ", symbol);
            return;
         }
      }
      // Apply template（附加 EA）
      bool ok = ChartApplyTemplate(chart_id, tpl);
      Print("[Controller] ChartApplyTemplate ", (ok ? "✅ 成功" : "❌ 失敗（tpl 可能唔存在）"), " → ", ea);
   }
   else if (cmd == "remove") {
      string ea = JsonGet(content, "ea");
      if (StringLen(ea) == 0) return;
      // 寫目標 EA 控制檔（控制層 → ExpertRemove）
      string target_ctrl = "ctrl_" + ea + ".json";
      int h = FileOpen(target_ctrl, FILE_WRITE|FILE_TXT|FILE_COMMON);
      if (h != INVALID_HANDLE) {
         FileWrite(h, "{\"cmd\":\"stop\"}");
         FileClose(h);
      }
      Print("[Controller] remove 指令已轉發 → ", ea);
   }
}

//+------------------------------------------------------------------+
//| StringToTimeframe：字串 → ENUM_TIMEFRAMES                        |
//+------------------------------------------------------------------+
ENUM_TIMEFRAMES StringToTimeframe(string tf) {
   if (tf == "M1") return PERIOD_M1;
   if (tf == "M5") return PERIOD_M5;
   if (tf == "M15") return PERIOD_M15;
   if (tf == "M30") return PERIOD_M30;
   if (tf == "H4") return PERIOD_H4;
   if (tf == "D1") return PERIOD_D1;
   if (tf == "W1") return PERIOD_W1;
   if (tf == "MN1") return PERIOD_MN1;
   return PERIOD_H1;
}

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit() {
   Print("[Controller] 已啟動 — 網頁 EA 控制器");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick() {
   // 1. 檢查指令檔
   if (FileIsExist(__ctrl_file, FILE_COMMON)) {
      int h = FileOpen(__ctrl_file, FILE_READ|FILE_TXT|FILE_COMMON);
      if (h != INVALID_HANDLE) {
         string content = FileReadString(h);
         FileClose(h);
         FileDelete(__ctrl_file, FILE_COMMON);
         if (StringLen(content) > 0) {
            ProcessCommand(content);
         }
      }
   }
   // 2. 心跳（每 5 秒）
   if (TimeCurrent() - __last_beat >= 5) {
      WriteState("running");
      __last_beat = TimeCurrent();
   }
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason) {
   WriteState("stopped");
   Print("[Controller] 已停止 (reason=", reason, ")");
}
