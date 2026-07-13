//+------------------------------------------------------------------+
//| News_Trader.mq5                                                 |
//| 測試用 EA #21 - 新聞交易              |
//+------------------------------------------------------------------+
#property copyright      "測試策略 #21"
#property version        "1.00"
#property description    "新聞交易"
#property description    "數據公佈突破"

input double LotSize     = 0.01;     // 每單手數
input int    MagicNumber = 20240021; // EA ID
input bool   EnableLog   = true;     // 啟用日誌

int OnInit()
{
   if(EnableLog) Print("✅ News_Trader 已啟動！策略：新聞交易");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 News_Trader 已停止");
}

void OnTick()
{
   static datetime lastBar = 0;
   if(TimeCurrent() - lastBar < 60) return;
   lastBar = TimeCurrent();

   Comment("新聞交易\n數據公佈突破\nMagic: " + IntegerToString(MagicNumber) + "\n狀態：等待交易信號");
}
//+------------------------------------------------------------------+
