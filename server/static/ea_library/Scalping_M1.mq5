//+------------------------------------------------------------------+
//| Scalping_M1.mq5                                                 |
//| 測試用 EA #17 - 超短線 M1 剝頭皮              |
//+------------------------------------------------------------------+
#property copyright      "測試策略 #17"
#property version        "1.00"
#property description    "超短線 M1 剝頭皮"
#property description    "M1 快閃交易"

input double LotSize     = 0.01;     // 每單手數
input int    MagicNumber = 20240017; // EA ID
input bool   EnableLog   = true;     // 啟用日誌

int OnInit()
{
   if(EnableLog) Print("✅ Scalping_M1 已啟動！策略：超短線 M1 剝頭皮");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 Scalping_M1 已停止");
}

void OnTick()
{
   static datetime lastBar = 0;
   if(TimeCurrent() - lastBar < 60) return;
   lastBar = TimeCurrent();

   Comment("超短線 M1 剝頭皮\nM1 快閃交易\nMagic: " + IntegerToString(MagicNumber) + "\n狀態：等待交易信號");
}
//+------------------------------------------------------------------+
