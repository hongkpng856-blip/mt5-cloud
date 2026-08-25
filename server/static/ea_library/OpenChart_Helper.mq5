//+------------------------------------------------------------------+
//| OpenChart_Helper.mq5 — 開圖表輔助 EA（2026-08-15 用戶建議）      |
//| 掛喺任何圖表 → OnInit 讀 Common/Files/open_chart_cmd.json        |
//| → ChartOpen(symbol, tf) 開目標圖表 → 自己移除（ExpertRemove）    |
//| 檔格式: {"symbol":"XAUUSD","tf":"H1"}                            |
//+------------------------------------------------------------------+
#property copyright "Tradotcom"
#property version   "1.00"
#property strict

input string CommandFile = "open_chart_cmd.json";  // 指令檔（Common/Files）

//+------------------------------------------------------------------+
int OnInit()
{
   // 讀指令檔
   string sym = "EURUSD";
   ENUM_TIMEFRAMES tf = PERIOD_H1;
   long h = FileOpen(CommandFile, FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(h != INVALID_HANDLE)
   {
      string content = "";
      while(!FileIsEnding(h))
         content += FileReadString(h);
      FileClose(h);
      // 解析 {"symbol":"XXX","tf":"H1"}
      int pos = StringFind(content, "\"symbol\"");
      if(pos >= 0)
      {
         int start = StringFind(content, "\"", pos + 8);
         int end = StringFind(content, "\"", start + 1);
         if(start >= 0 && end > start)
            sym = StringSubstr(content, start + 1, end - start - 1);
      }
      pos = StringFind(content, "\"tf\"");
      if(pos >= 0)
      {
         int start = StringFind(content, "\"", pos + 5);
         int end = StringFind(content, "\"", start + 1);
         if(start >= 0 && end > start)
         {
            string tfs = StringSubstr(content, start + 1, end - start - 1);
            if(tfs == "M15") tf = PERIOD_M15;
            else if(tfs == "M30") tf = PERIOD_M30;
            else if(tfs == "H4") tf = PERIOD_H4;
            else if(tfs == "D1") tf = PERIOD_D1;
            else if(tfs == "W1") tf = PERIOD_W1;
            else if(tfs == "MN1") tf = PERIOD_MN1;
            else tf = PERIOD_H1;
         }
      }
   }
   // 開目標圖表
   long chart_id = ChartOpen(sym, tf);
   if(chart_id > 0)
   {
      // 帶到最前（active — 方便之後附加 EA）
      ChartSetInteger(chart_id, CHART_BRING_TO_TOP, 0, true);
      Print("✅ OpenChart_Helper 已開新圖表: ", sym, " (id=", chart_id, ")");
   }
   else
   {
      Print("❌ OpenChart_Helper 開圖表失敗: ", sym, " err=", GetLastError());
   }
   // 任務完成 — 自己移除（唔會再運行）
   ExpertRemove();
   return(INIT_SUCCEEDED);
}
//+------------------------------------------------------------------+
void OnDeinit(const int reason) { }
void OnTick() { }
//+------------------------------------------------------------------+
