//+------------------------------------------------------------------+
//| RSI_Over.mq5                                                 |
//| 測試用 EA #03 - RSI 超買超賣              |
//+------------------------------------------------------------------+
#property copyright      "測試策略 #03"
#property version        "1.00"
#property description    "RSI 超買超賣"
#property description    "RSI(14) 超買70 超賣30"

input double LotSize     = 0.01;     // 每單手數
input int    MagicNumber = 20240003; // EA ID
input bool   EnableLog   = true;     // 啟用日誌

int OnInit()
{
   if(EnableLog) Print("✅ RSI_Over 已啟動！策略：RSI 超買超賣");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 RSI_Over 已停止");
}

void OnTick()
{
   static datetime lastBar = 0;
   if(TimeCurrent() - lastBar < 60) return;
   lastBar = TimeCurrent();

   Comment("RSI 超買超賣\nRSI(14) 超買70 超賣30\nMagic: " + IntegerToString(MagicNumber) + "\n狀態：等待交易信號");
}
//+------------------------------------------------------------------+
