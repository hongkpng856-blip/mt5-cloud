//+------------------------------------------------------------------+
//| Multi_TimeFrame.mq5                                                 |
//| 測試用 EA #24 - 多時間框架              |
//+------------------------------------------------------------------+
#property copyright      "測試策略 #24"
#property version        "1.00"
#property description    "多時間框架"
#property description    "H1+D1 共振"

input double LotSize     = 0.01;     // 每單手數
input int    MagicNumber = 20240024; // EA ID
input bool   EnableLog   = true;     // 啟用日誌

int OnInit()
{
   if(EnableLog) Print("✅ Multi_TimeFrame 已啟動！策略：多時間框架");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 Multi_TimeFrame 已停止");
}

void OnTick()
{
   static datetime lastBar = 0;
   if(TimeCurrent() - lastBar < 60) return;
   lastBar = TimeCurrent();

   Comment("多時間框架\nH1+D1 共振\nMagic: " + IntegerToString(MagicNumber) + "\n狀態：等待交易信號");
}
//+------------------------------------------------------------------+
