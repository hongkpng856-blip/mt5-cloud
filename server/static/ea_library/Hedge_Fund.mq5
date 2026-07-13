//+------------------------------------------------------------------+
//| Hedge_Fund.mq5                                                 |
//| 測試用 EA #20 - 對沖策略              |
//+------------------------------------------------------------------+
#property copyright      "測試策略 #20"
#property version        "1.00"
#property description    "對沖策略"
#property description    "雙向持倉對沖"

input double LotSize     = 0.01;     // 每單手數
input int    MagicNumber = 20240020; // EA ID
input bool   EnableLog   = true;     // 啟用日誌

int OnInit()
{
   if(EnableLog) Print("✅ Hedge_Fund 已啟動！策略：對沖策略");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 Hedge_Fund 已停止");
}

void OnTick()
{
   static datetime lastBar = 0;
   if(TimeCurrent() - lastBar < 60) return;
   lastBar = TimeCurrent();

   Comment("對沖策略\n雙向持倉對沖\nMagic: " + IntegerToString(MagicNumber) + "\n狀態：等待交易信號");
}
//+------------------------------------------------------------------+
