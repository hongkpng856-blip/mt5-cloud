//+------------------------------------------------------------------+
//| ADX_Trend.mq5                                                 |
//| 測試用 EA #07 - ADX 趨勢跟蹤              |
//+------------------------------------------------------------------+
#property copyright      "測試策略 #07"
#property version        "1.00"
#property description    "ADX 趨勢跟蹤"
#property description    "ADX(14) 趨勢強度>25"

input double LotSize     = 0.01;     // 每單手數
input int    MagicNumber = 20240007; // EA ID
input bool   EnableLog   = true;     // 啟用日誌

int OnInit()
{
   if(EnableLog) Print("✅ ADX_Trend 已啟動！策略：ADX 趨勢跟蹤");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 ADX_Trend 已停止");
}

void OnTick()
{
   static datetime lastBar = 0;
   if(TimeCurrent() - lastBar < 60) return;
   lastBar = TimeCurrent();

   Comment("ADX 趨勢跟蹤\nADX(14) 趨勢強度>25\nMagic: " + IntegerToString(MagicNumber) + "\n狀態：等待交易信號");
}
//+------------------------------------------------------------------+
