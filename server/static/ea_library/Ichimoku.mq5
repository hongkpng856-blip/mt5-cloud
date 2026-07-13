//+------------------------------------------------------------------+
//| Ichimoku.mq5                                                 |
//| 測試用 EA #09 - 一目均衡表              |
//+------------------------------------------------------------------+
#property copyright      "測試策略 #09"
#property version        "1.00"
#property description    "一目均衡表"
#property description    "Ichimoku(9,26,52)"

input double LotSize     = 0.01;     // 每單手數
input int    MagicNumber = 20240009; // EA ID
input bool   EnableLog   = true;     // 啟用日誌

int OnInit()
{
   if(EnableLog) Print("✅ Ichimoku 已啟動！策略：一目均衡表");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 Ichimoku 已停止");
}

void OnTick()
{
   static datetime lastBar = 0;
   if(TimeCurrent() - lastBar < 60) return;
   lastBar = TimeCurrent();

   Comment("一目均衡表\nIchimoku(9,26,52)\nMagic: " + IntegerToString(MagicNumber) + "\n狀態：等待交易信號");
}
//+------------------------------------------------------------------+
