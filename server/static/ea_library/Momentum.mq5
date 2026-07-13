//+------------------------------------------------------------------+
//| Momentum.mq5                                                 |
//| 測試用 EA #27 - 動量策略              |
//+------------------------------------------------------------------+
#property copyright      "測試策略 #27"
#property version        "1.00"
#property description    "動量策略"
#property description    "動量突破追入"

input double LotSize     = 0.01;     // 每單手數
input int    MagicNumber = 20240027; // EA ID
input bool   EnableLog   = true;     // 啟用日誌

int OnInit()
{
   if(EnableLog) Print("✅ Momentum 已啟動！策略：動量策略");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 Momentum 已停止");
}

void OnTick()
{
   static datetime lastBar = 0;
   if(TimeCurrent() - lastBar < 60) return;
   lastBar = TimeCurrent();

   Comment("動量策略\n動量突破追入\nMagic: " + IntegerToString(MagicNumber) + "\n狀態：等待交易信號");
}
//+------------------------------------------------------------------+
