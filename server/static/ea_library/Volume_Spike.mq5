//+------------------------------------------------------------------+
//| Volume_Spike.mq5                                                 |
//| 測試用 EA #12 - 成交量突破              |
//+------------------------------------------------------------------+
#property copyright      "測試策略 #12"
#property version        "1.00"
#property description    "成交量突破"
#property description    "Volume > 均量 x 2"

input double LotSize     = 0.01;     // 每單手數
input int    MagicNumber = 20240012; // EA ID
input bool   EnableLog   = true;     // 啟用日誌

int OnInit()
{
   if(EnableLog) Print("✅ Volume_Spike 已啟動！策略：成交量突破");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 Volume_Spike 已停止");
}

void OnTick()
{
   static datetime lastBar = 0;
   if(TimeCurrent() - lastBar < 60) return;
   lastBar = TimeCurrent();

   Comment("成交量突破\nVolume > 均量 x 2\nMagic: " + IntegerToString(MagicNumber) + "\n狀態：等待交易信號");
}
//+------------------------------------------------------------------+
