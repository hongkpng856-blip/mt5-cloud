//+------------------------------------------------------------------+
//| Seasonal.mq5                                                 |
//| 測試用 EA #29 - 季節性模式              |
//+------------------------------------------------------------------+
#property copyright      "測試策略 #29"
#property version        "1.00"
#property description    "季節性模式"
#property description    "特定時段交易"

input double LotSize     = 0.01;     // 每單手數
input int    MagicNumber = 20240029; // EA ID
input bool   EnableLog   = true;     // 啟用日誌

int OnInit()
{
   if(EnableLog) Print("✅ Seasonal 已啟動！策略：季節性模式");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 Seasonal 已停止");
}

void OnTick()
{
   static datetime lastBar = 0;
   if(TimeCurrent() - lastBar < 60) return;
   lastBar = TimeCurrent();

   Comment("季節性模式\n特定時段交易\nMagic: " + IntegerToString(MagicNumber) + "\n狀態：等待交易信號");
}
//+------------------------------------------------------------------+
