//+------------------------------------------------------------------+
//| Divergence.mq5                                                 |
//| 測試用 EA #23 - 背離交易              |
//+------------------------------------------------------------------+
#property copyright      "測試策略 #23"
#property version        "1.00"
#property description    "背離交易"
#property description    "RSI/MACD 背離"

input double LotSize     = 0.01;     // 每單手數
input int    MagicNumber = 20240023; // EA ID
input bool   EnableLog   = true;     // 啟用日誌

int OnInit()
{
   if(EnableLog) Print("✅ Divergence 已啟動！策略：背離交易");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 Divergence 已停止");
}

void OnTick()
{
   static datetime lastBar = 0;
   if(TimeCurrent() - lastBar < 60) return;
   lastBar = TimeCurrent();

   Comment("背離交易\nRSI/MACD 背離\nMagic: " + IntegerToString(MagicNumber) + "\n狀態：等待交易信號");
}
//+------------------------------------------------------------------+
