//+------------------------------------------------------------------+
//| Bollinger_Band.mq5                                                 |
//| 測試用 EA #05 - 保力加通道              |
//+------------------------------------------------------------------+
#property copyright      "測試策略 #05"
#property version        "1.00"
#property description    "保力加通道"
#property description    "BB(20,2) 突破上下軌"

input double LotSize     = 0.01;     // 每單手數
input int    MagicNumber = 20240005; // EA ID
input bool   EnableLog   = true;     // 啟用日誌

int OnInit()
{
   if(EnableLog) Print("✅ Bollinger_Band 已啟動！策略：保力加通道");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 Bollinger_Band 已停止");
}

void OnTick()
{
   static datetime lastBar = 0;
   if(TimeCurrent() - lastBar < 60) return;
   lastBar = TimeCurrent();

   Comment("保力加通道\nBB(20,2) 突破上下軌\nMagic: " + IntegerToString(MagicNumber) + "\n狀態：等待交易信號");
}
//+------------------------------------------------------------------+
