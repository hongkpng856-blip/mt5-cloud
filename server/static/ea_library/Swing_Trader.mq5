//+------------------------------------------------------------------+
//| Swing_Trader.mq5                                                 |
//| 測試用 EA #22 - 波段交易              |
//+------------------------------------------------------------------+
#property copyright      "測試策略 #22"
#property version        "1.00"
#property description    "波段交易"
#property description    "H4 波段持倉"

input double LotSize     = 0.01;     // 每單手數
input int    MagicNumber = 20240022; // EA ID
input bool   EnableLog   = true;     // 啟用日誌

int OnInit()
{
   if(EnableLog) Print("✅ Swing_Trader 已啟動！策略：波段交易");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 Swing_Trader 已停止");
}

void OnTick()
{
   static datetime lastBar = 0;
   if(TimeCurrent() - lastBar < 60) return;
   lastBar = TimeCurrent();

   Comment("波段交易\nH4 波段持倉\nMagic: " + IntegerToString(MagicNumber) + "\n狀態：等待交易信號");
}
//+------------------------------------------------------------------+
