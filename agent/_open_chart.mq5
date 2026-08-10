//+------------------------------------------------------------------+
//| OpenChart.mq5 — 程式化開新圖表（EA 版 v2 — 2026-08-07）
//| 附加後 OnTimer 延遲 1 秒 → ChartOpen 開圖表 → ExpertRemove 自己移除
//| （OnInit 直接 ChartOpen 會卡 MT5 — 改用 OnTimer 唔卡）
//| 讀 Common/Files/open_chart_cmd.json 指定 symbol: {"symbol":"USDJPY","tf":"H1"}
//+------------------------------------------------------------------+
#property copyright "MT5 Cloud"
#property version   "2.00"
#property strict

string g_symbol = "EURUSD";

//+------------------------------------------------------------------+
void ReadCmdSymbol()
{
   string sym = "EURUSD";
   string path = "Common\\Files\\open_chart_cmd.json";
   long h = FileOpen(path, FILE_READ | FILE_TXT | FILE_ANSI);
   if(h != INVALID_HANDLE)
   {
      string content = "";
      while(!FileIsEnding(h))
         content += FileReadString(h);
      FileClose(h);
      int pos = StringFind(content, "\"symbol\"");
      if(pos >= 0)
      {
         int start = StringFind(content, "\"", pos + 8);
         int end = StringFind(content, "\"", start + 1);
         if(start >= 0 && end > start)
            sym = StringSubstr(content, start + 1, end - start - 1);
      }
      FileDelete(path);  // 用咗就刪（避免重用）
   }
   g_symbol = sym;
   Print("📋 OpenChart 讀取: symbol=", sym);
}
//+------------------------------------------------------------------+
int OnInit()
{
   ReadCmdSymbol();
   EventSetTimer(1);  // 1 秒後開圖表（唔卡 OnInit）
   return INIT_SUCCEEDED;
}
//+------------------------------------------------------------------+
void OnTimer()
{
   EventKillTimer();
   long chart_id = ChartOpen(g_symbol, PERIOD_H1);
   if(chart_id > 0)
      Print("✅ 已開新圖表: ", g_symbol, " (id=", chart_id, ")");
   else
      Print("❌ 開圖表失敗: ", g_symbol, " err=", GetLastError());
   ExpertRemove();  // 開完自己移除
}
//+------------------------------------------------------------------+
void OnTick()
{
   // 唔需要（OnTimer 已處理）
}
//+------------------------------------------------------------------+
