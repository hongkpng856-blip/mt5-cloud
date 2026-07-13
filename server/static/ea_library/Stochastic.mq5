//+------------------------------------------------------------------+
//| Stochastic.mq5                                                 |
//| 測試用 EA #06 - 隨機指標              |
//+------------------------------------------------------------------+
#property copyright      "測試策略 #06"
#property version        "1.00"
#property description    "隨機指標"
#property description    "Stoch(14,3,3) 超買80 超賣20"

input double LotSize     = 0.01;     // 每單手數
input int    MagicNumber = 20240006; // EA ID
input bool   EnableLog   = true;     // 啟用日誌

int OnInit()
{
   if(EnableLog) Print("✅ Stochastic 已啟動！策略：隨機指標");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 Stochastic 已停止");
}

void OnTick()
{
   static datetime lastBar = 0;
   if(TimeCurrent() - lastBar < 60) return;
   lastBar = TimeCurrent();

   Comment("隨機指標\nStoch(14,3,3) 超買80 超賣20\nMagic: " + IntegerToString(MagicNumber) + "\n狀態：等待交易信號");
}
//+------------------------------------------------------------------+
