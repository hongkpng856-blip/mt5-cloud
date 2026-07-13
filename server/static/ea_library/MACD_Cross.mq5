//+------------------------------------------------------------------+
//| MACD_Cross.mq5                                                 |
//| 測試用 EA #04 - MACD 交叉              |
//+------------------------------------------------------------------+
#property copyright      "測試策略 #04"
#property version        "1.00"
#property description    "MACD 交叉"
#property description    "MACD(12,26,9)"

input double LotSize     = 0.01;     // 每單手數
input int    MagicNumber = 20240004; // EA ID
input bool   EnableLog   = true;     // 啟用日誌

int OnInit()
{
   if(EnableLog) Print("✅ MACD_Cross 已啟動！策略：MACD 交叉");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 MACD_Cross 已停止");
}

void OnTick()
{
   static datetime lastBar = 0;
   if(TimeCurrent() - lastBar < 60) return;
   lastBar = TimeCurrent();

   Comment("MACD 交叉\nMACD(12,26,9)\nMagic: " + IntegerToString(MagicNumber) + "\n狀態：等待交易信號");
}
//+------------------------------------------------------------------+
