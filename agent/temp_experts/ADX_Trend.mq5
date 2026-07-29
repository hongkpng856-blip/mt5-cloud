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

   // Delay AgentHelper bootstrap to OnTimer (ChartOpen doesn't work in OnInit)
   if(GlobalVariableCheck("AGENTHELPER_RUNNING")==false){
      EventSetTimer(3);  // Will trigger OnTimer in 3 seconds
   }

   if(EnableLog) Print("✅ ADX_Trend 已啟動！策略：ADX 趨勢跟蹤");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 ADX_Trend 已停止");
}

void OnTimer()
{
   // One-shot: bootstrap AgentHelper
   if(GlobalVariableCheck("AGENTHELPER_RUNNING")==false){
      long chart_id=ChartOpen("EURUSD",PERIOD_H1);
      if(chart_id>0){
         if(ChartApplyTemplate(chart_id,"AgentHelper_EURUSD_H1.tpl")){
            GlobalVariableSet("AGENTHELPER_RUNNING",1);
            if(EnableLog) Print("✅ AgentHelper bootstrapped via ChartApplyTemplate");
         }
      } else {
         if(EnableLog) Print("⚠️ AgentHelper bootstrap: ChartOpen failed");
      }
   }
   EventKillTimer();  // One-shot only
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
