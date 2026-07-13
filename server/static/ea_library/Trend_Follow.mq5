//+------------------------------------------------------------------+
//| Trend_Follow.mq5                                                 |
//| 測試用 EA #16 - 趨勢追蹤              |
//+------------------------------------------------------------------+
#property copyright      "測試策略 #16"
#property version        "1.00"
#property description    "趨勢追蹤"
#property description    "EMA(50) 趨勢方向"

input double LotSize     = 0.01;     // 每單手數
input int    MagicNumber = 20240016; // EA ID
input bool   EnableLog   = true;     // 啟用日誌

int OnInit()
{
   if(EnableLog) Print("✅ Trend_Follow 已啟動！策略：趨勢追蹤");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 Trend_Follow 已停止");
}

void OnTick()
{
   static datetime lastBar = 0;
   if(TimeCurrent() - lastBar < 60) return;
   lastBar = TimeCurrent();

   Comment("趨勢追蹤\nEMA(50) 趨勢方向\nMagic: " + IntegerToString(MagicNumber) + "\n狀態：等待交易信號");
}
//+------------------------------------------------------------------+
