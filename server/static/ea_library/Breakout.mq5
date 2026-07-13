//+------------------------------------------------------------------+
//| Breakout.mq5                                                 |
//| 測試用 EA #15 - 區間突破              |
//+------------------------------------------------------------------+
#property copyright      "測試策略 #15"
#property version        "1.00"
#property description    "區間突破"
#property description    "20日高低突破"

input double LotSize     = 0.01;     // 每單手數
input int    MagicNumber = 20240015; // EA ID
input bool   EnableLog   = true;     // 啟用日誌

int OnInit()
{
   if(EnableLog) Print("✅ Breakout 已啟動！策略：區間突破");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 Breakout 已停止");
}

void OnTick()
{
   static datetime lastBar = 0;
   if(TimeCurrent() - lastBar < 60) return;
   lastBar = TimeCurrent();

   Comment("區間突破\n20日高低突破\nMagic: " + IntegerToString(MagicNumber) + "\n狀態：等待交易信號");
}
//+------------------------------------------------------------------+
