//+------------------------------------------------------------------+
//| Correlation.mq5                                                 |
//| 測試用 EA #25 - 相關性套利              |
//+------------------------------------------------------------------+
#property copyright      "測試策略 #25"
#property version        "1.00"
#property description    "相關性套利"
#property description    "EURGBP 相關對"

input double LotSize     = 0.01;     // 每單手數
input int    MagicNumber = 20240025; // EA ID
input bool   EnableLog   = true;     // 啟用日誌

int OnInit()
{
   if(EnableLog) Print("✅ Correlation 已啟動！策略：相關性套利");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 Correlation 已停止");
}

void OnTick()
{
   static datetime lastBar = 0;
   if(TimeCurrent() - lastBar < 60) return;
   lastBar = TimeCurrent();

   Comment("相關性套利\nEURGBP 相關對\nMagic: " + IntegerToString(MagicNumber) + "\n狀態：等待交易信號");
}
//+------------------------------------------------------------------+
