//+------------------------------------------------------------------+
//| ADX_Trend.mq5                                                 |
//| 測試用 EA #07 - ADX 趨勢跟蹤              |
//+------------------------------------------------------------------+
#property copyright      "測試策略 #07"
#property version        "1.00"
#property description    "ADX 趨勢跟蹤"
#property description    "ADX(14) 趨勢強度>25"

input double LotSize     = 0.01;     // 每單手數
input int    MagicNumber = 20240007; // EA ID
input bool   EnableLog   = true;     // 啟用日誌

int OnInit()
{
   // Heartbeat
   GlobalVariableSet("HB_ADX_Trend",TimeCurrent());
   int hb_fh=FileOpen("hb_ADX_Trend.txt",FILE_WRITE|FILE_TXT|FILE_COMMON);
   if(hb_fh!=INVALID_HANDLE){FileWrite(hb_fh,TimeCurrent());FileClose(hb_fh);}

   if(EnableLog) Print("✅ ADX_Trend 已啟動！策略：ADX 趨勢跟蹤");
      EventSetTimer(1);

      return(INIT_SUCCEEDED);
}

void OnTimer()
{
   __mt5c_process();
}

void OnDeinit(const int reason)
{
      EventKillTimer();

      if(EnableLog) Print("🛑 ADX_Trend 已停止");
}


void OnTick()
{
   // Heartbeat
   GlobalVariableSet("HB_ADX_Trend",TimeCurrent());
   int hb_fh=FileOpen("hb_ADX_Trend.txt",FILE_WRITE|FILE_TXT|FILE_COMMON);
   if(hb_fh!=INVALID_HANDLE){FileWrite(hb_fh,TimeCurrent());FileClose(hb_fh);}

      static datetime lastBar = 0;
   if(TimeCurrent() - lastBar < 60) return;
   lastBar = TimeCurrent();

   Comment("ADX 趨勢跟蹤\nADX(14) 趨勢強度>25\nMagic: " + IntegerToString(MagicNumber) + "\n狀態：等待交易信號");
}
//+------------------------------------------------------------------+

// ---- MT5 Cloud 心跳（自動注入 2026-08-14 — 每秒寫心跳 + 暫停指令檢查）----
// 🚨 2026-08-15：交易品種參數（部署時自動寫入揀好嘅 symbol — EA 用呢個 symbol 交易/開圖表 — 唔理圖表本身）
input string InpSymbol = "";
string __mt5c_ctrl_file = "";
string __mt5c_state_file = "";
void __mt5c_process() {
   if(__mt5c_ctrl_file == "") {
      __mt5c_ctrl_file = "ctrl_" + MQLInfoString(MQL_PROGRAM_NAME) + ".json";
      __mt5c_state_file = "state_" + MQLInfoString(MQL_PROGRAM_NAME) + ".json";
   }
   // 🚨 2026-08-15 FIX：開目標圖表（只開一次 — static flag — 唔可以每次心跳都開！）
   static bool __mt5c_chart_done = false;
   if(!__mt5c_chart_done) {
      __mt5c_chart_done = true;
      if(InpSymbol != "" && Symbol() != InpSymbol) {
         long _cid = ChartOpen(InpSymbol, PERIOD_CURRENT);
         if(_cid > 0) { ChartSetInteger(_cid, CHART_BRING_TO_TOP, 0, true); Print("📈 已開目標圖表: ", InpSymbol); }
      }
   }
   if(FileIsExist(__mt5c_ctrl_file, FILE_COMMON)) {
      int h = FileOpen(__mt5c_ctrl_file, FILE_READ|FILE_TXT|FILE_COMMON);
      if(h != INVALID_HANDLE) {
         string c = FileReadString(h);
         FileClose(h);
         FileDelete(__mt5c_ctrl_file, FILE_COMMON);
         if(StringFind(c, "stop") >= 0) {
            int h2 = FileOpen(__mt5c_state_file, FILE_WRITE|FILE_TXT|FILE_COMMON);
            if(h2 != INVALID_HANDLE) { FileWrite(h2, "{\"status\":\"stopped\"}"); FileClose(h2); }
            ExpertRemove();
            return;
         }
      }
   }
   int h = FileOpen(__mt5c_state_file, FILE_WRITE|FILE_TXT|FILE_COMMON);
   if(h != INVALID_HANDLE) {
      FileWrite(h, StringFormat("{\"ea\":\"%s\",\"status\":\"running\",\"ts\":%d}", MQLInfoString(MQL_PROGRAM_NAME), (int)TimeCurrent()));
      FileClose(h);
   }
}
// ---- 心跳結束 ----

