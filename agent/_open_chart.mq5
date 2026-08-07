//+------------------------------------------------------------------+
//| OpenChart.mq5 — 程式化開新圖表（EA 版 — 2026-08-07）
//| 附加後 OnInit 執行 → ChartOpen 開圖表 → ExpertRemove 自己移除
//| 配熱鍵 — send 熱鍵即開圖表（唔使 double-click）
//| 讀 Common/Files/open_chart_cmd.json 指定 symbol: {"symbol":"USDJPY","tf":"H1"}
//+------------------------------------------------------------------+
#property copyright "MT5 Cloud"
#property version   "1.00"
#property strict

//+------------------------------------------------------------------+
string ReadCmdSymbol()
{
   string sym = "EURUSD";          // 默認
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
      // 用咗就刪（避免重用舊設定）
      FileDelete(path);
   }
   Print("📋 open_chart_cmd: symbol=", sym);
   return sym;
}
//+------------------------------------------------------------------+
int OnInit()
{
   string sym = ReadCmdSymbol();
   long chart_id = ChartOpen(sym, PERIOD_H1);
   if(chart_id > 0)
   {
      Print("✅ 已開新圖表: ", sym, " (id=", chart_id, ")");
   }
   else
   {
      Print("❌ 開圖表失敗: ", sym, " err=", GetLastError());
   }
   // 開完圖表即刻移除自己（EA 唔使留低）
   ExpertRemove();
   return INIT_SUCCEEDED;
}
//+------------------------------------------------------------------+
void OnTick()
{
   // 唔需要（OnInit 已處理）
}
//+------------------------------------------------------------------+
