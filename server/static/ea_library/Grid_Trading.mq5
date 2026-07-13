//+------------------------------------------------------------------+
//| Grid_Trading.mq5                                                 |
//| 測試用 EA #18 - 網格交易              |
//+------------------------------------------------------------------+
#property copyright      "測試策略 #18"
#property version        "1.00"
#property description    "網格交易"
#property description    "等差間隔網格"

input double LotSize     = 0.01;     // 每單手數
input int    MagicNumber = 20240018; // EA ID
input bool   EnableLog   = true;     // 啟用日誌

int OnInit()
{
   if(EnableLog) Print("✅ Grid_Trading 已啟動！策略：網格交易");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 Grid_Trading 已停止");
}

void OnTick()
{
   static datetime lastBar = 0;
   if(TimeCurrent() - lastBar < 60) return;
   lastBar = TimeCurrent();

   Comment("網格交易\n等差間隔網格\nMagic: " + IntegerToString(MagicNumber) + "\n狀態：等待交易信號");
}
//+------------------------------------------------------------------+
