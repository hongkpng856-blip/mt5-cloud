//+------------------------------------------------------------------+
//| Price_Action.mq5                                                 |
//| 測試用 EA #14 - 價格行為 Pin Bar              |
//+------------------------------------------------------------------+
#property copyright      "測試策略 #14"
#property version        "1.00"
#property description    "價格行為 Pin Bar"
#property description    "Pin Bar 反轉形態"

input double LotSize     = 0.01;     // 每單手數
input int    MagicNumber = 20240014; // EA ID
input bool   EnableLog   = true;     // 啟用日誌

int OnInit()
{
   if(EnableLog) Print("✅ Price_Action 已啟動！策略：價格行為 Pin Bar");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 Price_Action 已停止");
}

void OnTick()
{
   static datetime lastBar = 0;
   if(TimeCurrent() - lastBar < 60) return;
   lastBar = TimeCurrent();

   Comment("價格行為 Pin Bar\nPin Bar 反轉形態\nMagic: " + IntegerToString(MagicNumber) + "\n狀態：等待交易信號");
}
//+------------------------------------------------------------------+
