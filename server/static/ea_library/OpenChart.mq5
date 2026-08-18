//+------------------------------------------------------------------+
//| OpenChart.mq5 — 開圖表 Script（MT5 Cloud）                       |
//| 用法：Navigator → 腳本 → MT5Cloud_EA → OpenChart 雙擊            |
//|   彈出對話框，填：                                               |
//|     InpSymbol = 交易品種 (例 EURUSD / GBPUSD / XAUUSD)           |
//|     InpPeriod = 時間框架 (M1/M5/M15/H1/H4/D1...)                 |
//|   確定即開新圖表 —— 每一次都可以填唔同品種開唔同 chart。         |
//|                                                                  |
//| 自動模式（留空 InpSymbol）：讀 Common/Files/open_chart_cmd.json  |
//|   {"symbol":"EURUSD","tf":"H1"}  ← 自動化部署用                  |
//|                                                                  |
//| 所有 MT5 Cloud 檔案統一放 MQL5/Scripts/MT5Cloud_EA/              |
//+------------------------------------------------------------------+
#property copyright "MT5 Cloud"
#property version   "1.30"
#property strict
#property script_show_inputs

input string           InpSymbol = "";        // 交易品種（留空 = 讀 json / 用默認 EURUSD）
input ENUM_TIMEFRAMES  InpPeriod = PERIOD_H1; // 時間框架

//+------------------------------------------------------------------+
//| 讀 Common/Files/open_chart_cmd.json                             |
//+------------------------------------------------------------------+
bool ReadCmd(string &sym, ENUM_TIMEFRAMES &tf)
{
   sym = "";
   tf  = PERIOD_H1;
   long h = FileOpen("open_chart_cmd.json", FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(h == INVALID_HANDLE) return false;
   string content = "";
   while(!FileIsEnding(h)) content += FileReadString(h);
   FileClose(h);

   int pos = StringFind(content, "\"symbol\"");
   if(pos >= 0)
   {
      int s = StringFind(content, "\"", pos + 8);
      int e = StringFind(content, "\"", s + 1);
      if(s >= 0 && e > s) sym = StringSubstr(content, s + 1, e - s - 1);
   }
   pos = StringFind(content, "\"tf\"");
   if(pos >= 0)
   {
      int s = StringFind(content, "\"", pos + 4);
      int e = StringFind(content, "\"", s + 1);
      if(s >= 0 && e > s)
      {
         string tfs = StringSubstr(content, s + 1, e - s - 1);
         if(tfs == "M1")       tf = PERIOD_M1;
         else if(tfs == "M5")  tf = PERIOD_M5;
         else if(tfs == "M15") tf = PERIOD_M15;
         else if(tfs == "M30") tf = PERIOD_M30;
         else if(tfs == "H4")  tf = PERIOD_H4;
         else if(tfs == "D1")  tf = PERIOD_D1;
         else if(tfs == "W1")  tf = PERIOD_W1;
         else if(tfs == "MN1") tf = PERIOD_MN1;
         else                  tf = PERIOD_H1;
      }
   }
   return (sym != "");
}

//+------------------------------------------------------------------+
//| OnStart                                                          |
//+------------------------------------------------------------------+
void OnStart()
{
   string           sym = InpSymbol;
   ENUM_TIMEFRAMES  tf  = InpPeriod;

   if(sym == "")
   {
      string jsym; ENUM_TIMEFRAMES jtf;
      if(ReadCmd(jsym, jtf))
      {
         sym = jsym; tf = jtf;
         Print("📋 讀 open_chart_cmd.json: ", sym, " ", EnumToString(tf));
      }
      else
      {
         sym = "EURUSD";
         Print("⚠️ 無手動輸入亦無 json，用默認: ", sym);
      }
   }
   else
   {
      Print("📋 手動輸入: ", sym, " ", EnumToString(tf));
   }

   // 品種存在性檢查（避免 typo 開唔到圖表又無提示）
   if(!SymbolInfoInteger(sym, SYMBOL_EXIST))
      Print("⚠️ 警告：品種 '", sym, "' 可能唔存在於此帳戶，仍嘗試開圖表");

   long chart_id = ChartOpen(sym, tf);
   if(chart_id > 0)
   {
      ChartSetInteger(chart_id, CHART_BRING_TO_TOP, 0, true);
      Print("✅ 已開新圖表: ", sym, " ", EnumToString(tf), " (id=", chart_id, ")");

      // 🔧 2026-08-18：部署模式（自動模式 = 留空 symbol 讀 json）開完目標 chart，
      // 關閉所有其它 chart（包括部署前 Alt+F 開嘅空白 chart + 任何重複 chart）
      // → 解決「開咗空白 chart 再開目標 chart 再開多一個」變 3 個 chart 嘅問題。
      // 手動模式（用家自己填 symbol）唔關其它 chart，保護用家手動 workspace。
      if(InpSymbol == "" )
      {
         // MQL5 列舉 chart：ChartFirst → ChartNext（冇 ChartsTotal/ChartId）
         long cid = ChartFirst();
         while(cid != 0)
         {
            long next = ChartNext(cid);
            if(cid != chart_id)
               ChartClose(cid);
            cid = next;
         }
         Print("🧹 已關閉其它 chart（保留目標 ", sym, "）");
      }
   }
   else
   {
      Print("❌ 開圖表失敗: ", sym, " err=", GetLastError());
   }
}
//+------------------------------------------------------------------+
