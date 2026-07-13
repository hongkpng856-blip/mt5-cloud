//+------------------------------------------------------------------+
//| Mean_Reversion.mq5                                                 |
//| 測試用 EA #26 - 均值回歸              |
//+------------------------------------------------------------------+
#property copyright      "測試策略 #26"
#property version        "1.00"
#property description    "均值回歸"
#property description    "偏離布林帶回歸"

input double LotSize     = 0.01;     // 每單手數
input int    MagicNumber = 20240026; // EA ID
input bool   EnableLog   = true;     // 啟用日誌

int OnInit()
{
   if(EnableLog) Print("✅ Mean_Reversion 已啟動！策略：均值回歸");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 Mean_Reversion 已停止");
}

void OnTick()
{
   static datetime lastBar = 0;
   if(TimeCurrent() - lastBar < 60) return;
   lastBar = TimeCurrent();

   Comment("均值回歸\n偏離布林帶回歸\nMagic: " + IntegerToString(MagicNumber) + "\n狀態：等待交易信號");
}
//+------------------------------------------------------------------+
