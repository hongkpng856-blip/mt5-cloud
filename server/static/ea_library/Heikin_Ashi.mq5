//+------------------------------------------------------------------+
//| Heikin_Ashi.mq5                                                 |
//| 測試用 EA #11 - Heikin Ashi 平滑              |
//+------------------------------------------------------------------+
#property copyright      "測試策略 #11"
#property version        "1.00"
#property description    "Heikin Ashi 平滑"
#property description    "HA 轉向信號"

input double LotSize     = 0.01;     // 每單手數
input int    MagicNumber = 20240011; // EA ID
input bool   EnableLog   = true;     // 啟用日誌

int OnInit()
{
   if(EnableLog) Print("✅ Heikin_Ashi 已啟動！策略：Heikin Ashi 平滑");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 Heikin_Ashi 已停止");
}

void OnTick()
{
   static datetime lastBar = 0;
   if(TimeCurrent() - lastBar < 60) return;
   lastBar = TimeCurrent();

   Comment("Heikin Ashi 平滑\nHA 轉向信號\nMagic: " + IntegerToString(MagicNumber) + "\n狀態：等待交易信號");
}
//+------------------------------------------------------------------+
